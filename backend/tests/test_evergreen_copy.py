"""Customer surfaces stay evergreen: no ages, dates, week labels, or countdowns."""
import copy
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from ai_drafter import SYSTEM_PROMPT
from blueprint_consistency import prepare_deliverable
from blueprint_presentation import build_presentation
from email_service import email_body_html
from evergreen_copy import STORY_TEMPLATE, evergreen_text, find_time_sensitive
from image_board import build_image_board
from pdf_generator import build_pdf, customer_project_title
from room_flow import outline_caption, zone_map_spec, zone_map_text
from space_rails import NURSERY_DRAFT_RULES, nursery_draft_addon

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json"
STORY = "As Nicholas grows, we kept the space familiar and gave every part a clear job."


def _stale_plan():
    """The nursery fixture with every kind of time-sensitive copy a drafter has produced."""
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lead = {**doc["lead"], "goals": "Nicholas just turned one. Keep the space theme and make the nursery safer."}
    d = copy.deepcopy(doc["deliverable"])
    d["intro"] = "Hi Camila. Nicholas is turning one, and at age 1 the floor matters more."
    d["summary"] = "Same nursery for your newly mobile toddler, calmer floor, dresser drawers kept."
    d["needs"] = ["Week 1: anchor the dresser so it cannot tip", "Keep a clear floor path for a newly mobile toddler"]
    d["strategy"] = [*d["strategy"], "Reset the floor in 60 seconds before bed.", "Warm the January window first."]
    d["action_plan"] = ["This week: anchor the six-drawer dresser.", "Strip the crib to one fitted sheet in 5 minutes."]
    d["notes"] = "Plan written October 6, 2026 for a 12-month-old."
    d["blueprint_layers"] = {
        "customer_instruction": {
            "start_here": "First move this week: anchor the dresser.",
            "do_this_week": ["Week 1 — anchor the dresser", "Install the thermal curtain in 10 minutes"],
            "do_not": ["Do not add a heater."],
            "weekly_reset": "10-minute reset: clear the floor path",
        }
    }
    return lead, d


def _pairs(count=4):
    out = []
    for index in range(count):
        before = io.BytesIO()
        Image.new("RGB", (240, 320), (140, 40 + index * 20, 40)).save(before, format="JPEG")
        after = io.BytesIO()
        Image.new("RGB", (240, 320), (20, 80 + index * 10, 90)).save(after, format="JPEG")
        out.append(
            {
                "label": f"SOURCE_{index + 1:02d}",
                "after_label": f"AFTER_{index + 1:02d}",
                "before": before.getvalue(),
                "after": after.getvalue(),
            }
        )
    return {"source_pairs": out}


def _board_text(monkeypatch, lead, deliverable, images):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    build_image_board(lead=lead, deliverable=deliverable, images=images)
    monkeypatch.undo()
    return "\n".join(drawn)


def _pdf_text(lead, deliverable, images):
    reader = PdfReader(io.BytesIO(build_pdf(lead=lead, deliverable=deliverable, images=images)))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"lead_id", "preview_path", "room_flow", "before_url", "after_url"}:
                continue
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _customer_surfaces(monkeypatch, lead, deliverable, images):
    title = customer_project_title(lead, prepare_deliverable(lead, deliverable))
    email = email_body_html(
        customer_name=lead["name"],
        space_type=lead["space_type"],
        project_title=title,
        outline_note=outline_caption(lead, deliverable),
        preview_src="cid:board",
        room_flow_src="cid:flow",
    )
    return {
        "board": _board_text(monkeypatch, lead, deliverable, images),
        "pdf": _pdf_text(lead, deliverable, images),
        "zone_map": zone_map_text(zone_map_spec(lead, deliverable, images, final=True)),
        "email": re.sub(r"<[^>]+>", " ", email),
        "presentation": "\n".join(_strings(build_presentation(lead, deliverable, images))),
    }


@pytest.mark.parametrize(
    "phrase",
    [
        "just turned one",
        "Nicholas is turning one",
        "age 1",
        "a 12-month-old",
        "first birthday",
        "Week 1",
        "this week",
        "60 seconds",
        "one-minute bedtime ritual",
        "10-minute reset",
        "October 6, 2026",
        "the January window",
        "newly mobile toddler",
    ],
)
def test_lint_flags_time_sensitive_phrases(phrase):
    assert find_time_sensitive(f"Keep the floor clear, {phrase}.")


@pytest.mark.parametrize(
    "phrase",
    [
        "Keep the room about 68–72°F with the heating you already have.",
        "Thermal blackout curtain panel (single, 52×84 in., warm taupe or oatmeal linen-look)",
        "Qty 2 · $30 each · $60",
        "Illustrative reference total: $195.",
        "Your stated budget: $100 – $300.",
        "Felt wall decor — moon or planet accent (warm gray or terra cotta, lightweight, 8–10 in.)",
        "You may move the rocker once a week.",
        "Bedtime ritual: smooth the fitted sheet.",
    ],
)
def test_lint_leaves_sizes_prices_and_temperatures_alone(phrase):
    assert find_time_sensitive(phrase) == []


def test_rewrites_keep_the_useful_part_of_a_line():
    assert evergreen_text("Week 1: anchor the dresser so it cannot tip") == "Anchor the dresser so it cannot tip"
    assert evergreen_text("Reset the floor in 60 seconds before bed.") == "Reset the floor before bed."
    assert evergreen_text("Keep a clear floor path for a newly mobile toddler") == "Keep a clear floor path for a child"
    assert evergreen_text("Hi Camila. Nicholas is turning one, and this refresh keeps the nursery.") == "Hi Camila."


def test_every_customer_surface_is_evergreen(monkeypatch):
    lead, deliverable = _stale_plan()
    for images in ({}, _pairs()):
        for surface, text in _customer_surfaces(monkeypatch, lead, deliverable, images).items():
            hits = find_time_sensitive(text)
            assert hits == [], f"{surface}: {hits}"


def test_project_story_names_the_child_without_an_age(monkeypatch):
    lead, deliverable = _stale_plan()
    prepared = prepare_deliverable(lead, deliverable)
    assert prepared["intro"] == STORY
    assert prepared["project_story"] == STORY
    assert STORY_TEMPLATE.format(child="Nicholas") == STORY
    assert customer_project_title(lead, prepared) == "Nicholas's Nursery"
    view = build_presentation(lead, deliverable, {})
    assert view["intro"] == STORY
    assert view["headline"] == "Nicholas's Nursery"


def test_customer_surfaces_keep_existing_gates(monkeypatch):
    lead, deliverable = _stale_plan()
    surfaces = _customer_surfaces(monkeypatch, lead, deliverable, _pairs())
    # The phone-page model is an admin review view that carries the lead id and source labels.
    surfaces.pop("presentation")
    for surface, text in surfaces.items():
        for banned in ("SOURCE_", "AFTER_", "9dbedfba", "QA "):
            assert banned not in text, f"{surface}: {banned}"
        assert not re.search(r"\b(?:plan|blueprint|package|guide) is ready\b", text, re.I), surface
    # The measured outline is the Room Flow sheet's claim; the Design Plan does not draw the map.
    assert "MEASURED OUTLINE" not in surfaces["board"]
    assert "Measured room outline" in surfaces["zone_map"]


def test_copy_writer_prompts_forbid_ages_dates_and_countdowns():
    lead, _deliverable = _stale_plan()
    for prompt in (SYSTEM_PROMPT, NURSERY_DRAFT_RULES):
        low = prompt.lower()
        assert "evergreen" in low or "do not name the child's age" in low
    assert "Evergreen copy" in SYSTEM_PROMPT
    assert "60 seconds" in SYSTEM_PROMPT  # named as a forbidden example
    assert find_time_sensitive(nursery_draft_addon(lead)) == []


def test_curated_room_flow_record_is_evergreen():
    record = json.loads(
        (FIXTURE.parents[1] / "room_flows" / "9dbedfba-81fc-45e0-b99d-36e0a1de01bb.json").read_text(encoding="utf-8")
    )
    blob = json.dumps({k: v for k, v in record.items() if k not in {"outline", "walls", "furniture", "path"}})
    assert find_time_sensitive(blob) == []
