"""The live Nicholas's Nursery record (old 'Week 1' / 'one year old' copy) renders whole sentences.

``fixtures/live_nicholas_nursery.json`` is the stored lead + deliverable as it
sits in production (customer email replaced). Every customer surface must open
with the Project Story, and no rewrite or fit may leave a dangling fragment.
"""
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from blueprint_consistency import companion_sections, prepare_deliverable, project_story_line
from copy_shape import complete_clip, ends_dangling, heading
from email_service import email_body_html
from evergreen_copy import find_time_sensitive
from image_board import _board_phrase, board_spec, build_image_board
from pdf_generator import build_pdf, companion_page_fill

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "live_nicholas_nursery.json"
STORY = "As Nicholas grows, we kept the space familiar and gave every part a clear job."
_DANGLING_END = re.compile(
    r"\b(?:the|a|an|and|or|but|of|to|for|with|in|on|at|by|from|every|each|any|your|its|this|that)\s*[.!?]$",
    re.I,
)


def _live():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def _pairs():
    out = []
    for index in range(4):
        before = io.BytesIO()
        Image.new("RGB", (300, 400), (150, 120 + index * 10, 110)).save(before, format="JPEG")
        after = io.BytesIO()
        Image.new("RGB", (300, 400), (210, 196, 180 - index * 10)).save(after, format="JPEG")
        out.append({"label": f"SOURCE_{index + 1:02d}", "after_label": f"AFTER_{index + 1:02d}",
                    "before": before.getvalue(), "after": after.getvalue()})
    return {"source_pairs": out}


def _drawn(monkeypatch, lead, deliverable, images):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    build_image_board(lead=lead, deliverable=deliverable, images=images)
    monkeypatch.undo()
    return drawn


def test_the_live_record_really_carries_the_old_copy():
    lead, deliverable = _live()
    raw = json.dumps(deliverable)
    assert "Week 1" in raw and "one year old" in raw
    assert "As Nicholas grows" not in raw


def test_story_line_resolves_from_the_live_record():
    lead, deliverable = _live()
    prepared = prepare_deliverable(lead, deliverable)
    assert prepared["project_story"] == STORY
    assert project_story_line(lead, deliverable) == STORY
    assert companion_sections(lead, deliverable)[0]["story"] == STORY


def test_pdf_opens_with_the_story_line():
    lead, deliverable = _live()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images=_pairs())
    first = " ".join((PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or "").split())
    assert STORY in first
    assert first.index(STORY) < first.index("Hi Camila.")
    assert first.index("Nicholas's Nursery") < first.index(STORY)


def test_board_outcome_is_the_story_line_in_full(monkeypatch):
    lead, deliverable = _live()
    assert board_spec(lead, deliverable, {})["subtitle"] == STORY
    drawn = " ".join(_drawn(monkeypatch, lead, deliverable, _pairs()))
    assert STORY in " ".join(drawn.split())


@pytest.mark.parametrize("draft", [False, True])
def test_email_opens_with_the_story_line(draft):
    import server

    lead, deliverable = _live()
    inputs = server._email_inputs(lead, deliverable)
    assert inputs["story"] == STORY
    html = email_body_html(**inputs, draft=draft, lead_id=lead["id"], preview_src="cid:board", room_flow_src="cid:flow")
    text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
    assert STORY in text
    assert text.index(STORY) < text.index("Hi Camila.")


def test_board_tiles_are_whole_headings_and_whole_sentences(monkeypatch):
    lead, deliverable = _live()
    spec = board_spec(lead, deliverable, _pairs())
    drawn = _drawn(monkeypatch, lead, deliverable, _pairs())
    joined = " ".join(" ".join(drawn).split())
    for move in spec["moves"]:
        title, body = move["title"], move["body"]
        assert title in drawn, f"tile title was cut: {title}"
        assert not title.endswith(".") and not ends_dangling(title), title
        assert len(title.split()) >= 2
        assert body.endswith(".") and not ends_dangling(body), body
        assert body in joined, f"tile body was cut: {body}"
    for step in spec["roadmap"]:
        assert step["title"] in drawn
        phrase = _board_phrase(step["title"], step["body"], words=18)
        assert phrase.endswith(".") and not _DANGLING_END.search(phrase), phrase
    for line in drawn:
        line = line.strip()
        assert not _DANGLING_END.search(line), f"board line ends on a fragment: {line!r}"
        assert not re.search(r"\b(?:or|the|a|and)\.$", line)


def test_no_live_copy_is_left_dangling_after_the_rewrite():
    lead, deliverable = _live()
    prepared = prepare_deliverable(lead, deliverable)
    sections = companion_sections(lead, deliverable)[0]
    texts = [prepared.get(k) or "" for k in ("intro", "summary", "notes", "budget_note", "project_story")]
    for key in ("needs", "strategy", "action_plan", "benefits"):
        texts.extend(prepared.get(key) or [])
    for zone in prepared.get("zones") or []:
        texts.append(zone.get("desc") or "")
    texts.extend(sections["safety_essentials"] + sections["climate_essentials"] + [sections["why"], sections["maintenance"]])
    for text in texts:
        if not text:
            continue
        assert not _DANGLING_END.search(text), text
        assert not ends_dangling(text), text
        assert not text.rstrip().endswith("every drawer."), text
        assert find_time_sensitive(text) == [], text
    # The rewrite keeps the useful part of a line rather than dropping it.
    assert any("warmer nursery in winter" in need.lower() for need in prepared["needs"])
    assert any("anchor the dresser and shelves" in step.lower() for step in prepared["action_plan"])
    assert not any("child to preschooler" in line for line in prepared["benefits"])


def test_every_customer_surface_is_evergreen_for_the_live_record(monkeypatch):
    import server

    lead, deliverable = _live()
    images = _pairs()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images=images)
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    board = "\n".join(_drawn(monkeypatch, lead, deliverable, images))
    email = re.sub(r"<[^>]+>", " ", email_body_html(**server._email_inputs(lead, deliverable), preview_src="cid:b"))
    for name, text in (("pdf", pdf_text), ("board", board), ("email", email)):
        assert find_time_sensitive(text) == [], name
        for banned in ("SOURCE_", "AFTER_", "9dbedfba"):
            assert banned not in text, (name, banned)
        assert not re.search(r"\b(?:plan|blueprint|package|guide) is ready\b", text, re.I), name
    assert "Illustrative reference total: $195." in " ".join(pdf_text.split())


def test_live_guide_pages_stay_full_with_the_story_line():
    lead, deliverable = _live()
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=_pairs())
    assert len(fills) == 8, fills
    assert min(fills) >= 0.40, fills


@pytest.mark.parametrize(
    "text, words",
    [
        ("Anchor every tall or heavy piece (dresser, shelves) to the wall with anti-tip kits, and secure or remove reachable cords and unstable decor.", 20),
        ("Install the thermal blackout curtain panels over the existing rod to reduce window drafts. Apply the film.", 8),
        ("Clear circulation and easy cleaning: open floor path, intentional furniture placement, and minimal tripping hazards.", 12),
    ],
)
def test_clipping_never_ends_mid_phrase(text, words):
    clipped = complete_clip(text, words)
    assert clipped.endswith(".")
    assert not ends_dangling(clipped), clipped
    assert clipped.count("(") == clipped.count(")"), clipped


def test_headings_never_end_on_a_function_word():
    assert heading("Install the thermal blackout curtain panels", 2) == "Install the thermal"
    assert heading("Anchor every tall or heavy piece", 3) == "Anchor every tall"
    assert not ends_dangling(heading("Keep this room and the dresser drawers", 4))
    assert not heading("Install the. blackout", 3).endswith(".")
