"""Draft JSON recovery — no live Anthropic calls.

Camila's Kids' room lead (9dbedfba) failed because Claude's draft was cut off
mid-string and _extract_json raised JSONDecodeError. These tests lock the
fence / truncation repair and the single retry.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

import ai_drafter
from ai_drafter import (
    DRAFT_MAX_TOKENS,
    DraftJSONError,
    _coerce,
    _extract_json,
    draft_deliverable,
)


TRUNCATED_KIDS_ROOM = """{
  "intro": "A calmer kids' storage corner.",
  "needs": ["Bins for toys"],
  "zones": [{"title": "Toys", "desc": "Low bins under the window"}],
  "wall_color_name": "Warm Taupe",
  "wall_color_hex": "#D1C7B8",
  "blueprint_layers": {
    "observation": {"space_seen": "Crib and window"},
    "customer_instruction": {
      "start_here": "Clear the floor",
      "weekly_reset": "Ten quiet minutes that got cut off without a quote
"""


def test_extracts_fenced_json_with_preamble():
    raw = (
        "Here is the plan:\n"
        "```json\n"
        '{"intro": "Calm closet", "summary": "Bins by the door"}\n'
        "```\n"
        "Let me know if you want changes."
    )
    plan = _extract_json(raw)
    assert plan["intro"] == "Calm closet"
    assert plan["summary"] == "Bins by the door"


def test_extracts_unclosed_fence():
    raw = '```json\n{"intro": "Mudroom hooks", "needs": ["A landing zone"]}'
    plan = _extract_json(raw)
    assert plan["intro"] == "Mudroom hooks"
    assert plan["needs"] == ["A landing zone"]


def test_truncated_tail_keeps_completed_fields():
    """The failure mode in the 14:13 UTC log: unterminated string after a nested }."""
    plan = _extract_json(TRUNCATED_KIDS_ROOM)
    assert plan["intro"].startswith("A calmer")
    assert plan["needs"] == ["Bins for toys"]
    assert plan["zones"][0]["title"] == "Toys"
    assert plan["blueprint_layers"]["observation"]["space_seen"] == "Crib and window"
    assert plan["blueprint_layers"]["customer_instruction"]["start_here"] == "Clear the floor"
    assert "weekly_reset" not in plan["blueprint_layers"]["customer_instruction"]


def test_truncated_fenced_draft_repairs():
    raw = "```json\n" + TRUNCATED_KIDS_ROOM
    plan = _extract_json(raw)
    assert plan["zones"][0]["desc"].startswith("Low bins")


def test_trailing_comma_and_prose_still_parse():
    raw = 'Note:\n{"intro": "Pantry zones", "summary": "Decant first",}\nThanks!'
    plan = _extract_json(raw)
    assert plan["intro"] == "Pantry zones"
    assert plan["summary"] == "Decant first"


def test_keeps_escaped_quotes_and_drops_cut_off_field():
    raw = r'{"intro": "Say \"hi\"", "notes": "cut off'
    plan = _extract_json(raw)
    assert plan["intro"] == 'Say "hi"'
    assert "notes" not in plan


def test_garbage_raises_retryable_draft_error():
    with pytest.raises(DraftJSONError) as caught:
        _extract_json("this is not json {unterminated")
    err = caught.value
    assert not isinstance(err, json.JSONDecodeError)
    message = str(err)
    assert "Retry this lead" in message
    assert "JSONDecodeError" not in message
    assert "Expecting" not in message
    assert "Unterminated" not in message


def test_empty_object_is_not_usable():
    with pytest.raises(DraftJSONError):
        _extract_json("{}")


def test_repaired_plan_still_keeps_existing_wall_color():
    plan = _extract_json(TRUNCATED_KIDS_ROOM)
    coerced = _coerce(plan, lead={"space_type": "closet", "goals": "More toy bins"})
    assert coerced["wall_color_name"] == "Keep existing / no paint change"
    assert coerced["wall_color_hex"] == ""
    assert "warm taupe" not in json.dumps(coerced).lower()


class _ScriptedMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text, stop = self.replies[len(self.calls) - 1]
        return SimpleNamespace(
            content=[SimpleNamespace(text=text)],
            stop_reason=stop,
        )


def _install_client(monkeypatch, replies):
    messages = _ScriptedMessages(replies)

    class _Client:
        def __init__(self, api_key):
            self.api_key = api_key
            self.messages = messages

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-live-key")
    monkeypatch.setattr(ai_drafter.anthropic, "Anthropic", _Client)
    return messages


def _sent_text(kwargs):
    content = kwargs["messages"][0]["content"]
    if isinstance(content, str):
        return content
    return content[-1]["text"]


def test_draft_uses_repaired_json_without_a_second_call(monkeypatch):
    messages = _install_client(
        monkeypatch,
        [(TRUNCATED_KIDS_ROOM, "max_tokens")],
    )
    plan = asyncio.run(
        draft_deliverable({"space_type": "closet", "name": "Camila", "goals": "Toy storage"})
    )
    assert len(messages.calls) == 1
    assert messages.calls[0]["max_tokens"] == DRAFT_MAX_TOKENS
    assert messages.calls[0]["max_tokens"] > 4096
    assert plan["intro"].startswith("A calmer")
    assert plan["wall_color_hex"] == ""
    assert plan["wall_color_name"] == "Keep existing / no paint change"


def test_draft_retries_once_when_json_is_unusable(monkeypatch):
    good = json.dumps(
        {
            "intro": "Laundry landing zone.",
            "zones": [{"title": "Hampers", "desc": "One per person"}],
            "wall_color_name": "Warm Taupe",
            "wall_color_hex": "#D1C7B8",
        }
    )
    messages = _install_client(
        monkeypatch,
        [("no json here", "end_turn"), (good, "end_turn")],
    )
    plan = asyncio.run(draft_deliverable({"space_type": "laundry", "goals": "Sort by person"}))
    assert len(messages.calls) == 2
    assert "was truncated or was not valid JSON" in _sent_text(messages.calls[1])
    assert "compact JSON" in _sent_text(messages.calls[1])
    assert plan["intro"] == "Laundry landing zone."
    assert plan["zones"][0]["title"] == "Hampers"
    assert plan["wall_color_hex"] == ""


def test_draft_raises_retryable_error_when_both_attempts_fail(monkeypatch):
    messages = _install_client(
        monkeypatch,
        [("nope", "max_tokens"), ("still nope {", "end_turn")],
    )
    with pytest.raises(DraftJSONError) as caught:
        asyncio.run(draft_deliverable({"space_type": "pantry"}))
    assert len(messages.calls) == 2
    message = str(caught.value)
    assert "Retry this lead" in message
    assert "JSONDecodeError" not in message
    assert not isinstance(caught.value, json.JSONDecodeError)
