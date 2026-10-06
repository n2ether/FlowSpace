"""Camila's copy corrections for Nicholas's Nursery, checked on the live-record fixture."""
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from blueprint_consistency import companion_sections, internal_record
from blueprint_presentation import build_presentation
from email_service import email_body_html
from evergreen_copy import BEDTIME_RITUAL_BODY, BEDTIME_RITUAL_TITLE, find_time_sensitive
from image_board import board_spec, build_image_board, customer_board_text
from pdf_generator import build_pdf, companion_page_fill
from room_flow import zone_map_spec, zone_map_text

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "live_nicholas_nursery.json"
APP = ROOT.parent / "frontend" / "src" / "pages" / "BlueprintPreview.jsx"
STORY = "As Nicholas grows, we kept the space familiar and gave every part a clear job."

RITUAL = (
    "ONE-MINUTE BEDTIME RITUAL\n\n"
    "Bring your baby into the ritual from the beginning. Calmly narrate the same sequence you move through "
    "together: resetting the rocker, keeping the crib clear, closing the curtains, and dimming the lights. "
    "Repeat the same goodnight phrase. Then turn on the sound machine at a gentle volume—or sing a familiar "
    "song—as you settle your baby.\n\n"
    "These cues help make bedtime easier to read, even when your baby resists sleep. By the time you sit in "
    "the rocker, the room is ready for feeding, connection, and rest."
)

NEW = {
    "roadmap": "MAKE DAILY CARE EASY",
    "drafts": "REDUCE DRAFTS",
    "essentials": "The Companion Guide includes the room's safety and climate essentials.",
    "theme": "The space theme remains: planets, moon, rockets, and astronauts.",
    "keep": "Keep the room and the dresser you already have, so putting things away stays simple.",
    "views": "One complete after view for each photo. Swipe or use the buttons.",
    "disclaimer": "Representative examples for reference; prices and availability may vary.",
    "total": "Illustrative reference total: $195.",
}
OLD = (
    "KEEP IT",
    "WARM THE WINDOW",
    "Safety and climate are written once in the companion guide.",
    "Space theme stays:",
    "Keep the room and the dresser drawers you have, so putting things away stays one step.",
    "One complete after for each photo. Swipe, or use the buttons.",
    "LIST TOTAL",
    "List total",
)


def _live():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def _pairs():
    out = []
    for index in range(4):
        before, after = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (300, 400), (150, 120 + index * 10, 110)).save(before, format="JPEG")
        Image.new("RGB", (300, 400), (210, 196, 180 - index * 10)).save(after, format="JPEG")
        out.append({"label": f"SOURCE_{index + 1:02d}", "after_label": f"AFTER_{index + 1:02d}",
                    "before": before.getvalue(), "after": after.getvalue()})
    return {"source_pairs": out}


def _flat(text):
    return " ".join(str(text).split())


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


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


@pytest.fixture(scope="module")
def surfaces():
    import server

    lead, deliverable = _live()
    images = _pairs()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images=images)
    view = build_presentation(lead, deliverable, images)
    return {
        "lead": lead,
        "deliverable": deliverable,
        "images": images,
        "pdf": _flat("\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)),
        "board_spec": _flat(customer_board_text(board_spec(lead, deliverable, images))),
        "zone_map": _flat(zone_map_text(zone_map_spec(lead, deliverable, images, final=False))),
        "email": _flat(re.sub(r"<[^>]+>", " ", email_body_html(**server._email_inputs(lead, deliverable), preview_src="cid:b", room_flow_src="cid:f"))),
        "presentation": view,
        "presentation_text": _flat(" ".join(_strings(view))),
        "app": APP.read_text(encoding="utf-8"),
    }


def test_board_tiles_roadmap_and_room_flow_copy(monkeypatch, surfaces):
    drawn = _drawn(monkeypatch, surfaces["lead"], surfaces["deliverable"], surfaces["images"])
    flat = _flat(" ".join(drawn))
    assert NEW["roadmap"] in drawn
    assert NEW["drafts"] in drawn
    assert NEW["keep"] in flat
    assert "close the gap under the door" in flat
    assert NEW["total"] in drawn
    assert NEW["disclaimer"] in drawn
    spec = board_spec(surfaces["lead"], surfaces["deliverable"], surfaces["images"])
    assert spec["topdown"]["caption"].endswith(NEW["theme"])
    for text in (flat, surfaces["board_spec"]):
        for old in OLD:
            assert old not in text, old
    assert STORY in flat


def test_companion_guide_shopping_copy(surfaces):
    pdf = surfaces["pdf"]
    assert NEW["total"] in pdf
    assert NEW["disclaimer"] in pdf
    assert pdf.count("Illustrative reference total") == 1
    for old in ("LIST TOTAL", "List total", "WARM THE WINDOW", "KEEP IT"):
        assert old not in pdf
    assert STORY in pdf


def test_app_results_copy(surfaces):
    view = surfaces["presentation"]
    assert view["warning_note"] == NEW["essentials"]
    assert view["plan"]["caption"].endswith(NEW["theme"])
    assert view["shopping_total_line"] == NEW["total"]
    assert view["shopping_note"] == NEW["disclaimer"]
    assert [step["title"] for step in view["roadmap"]][-1] == NEW["roadmap"]
    assert NEW["drafts"] in [move["title"] for move in view["changes"]]
    app = surfaces["app"]
    assert NEW["views"] in app
    assert "Illustrative reference total" in app and NEW["disclaimer"] in app
    for old in OLD:
        assert old not in surfaces["presentation_text"], old
    for old in ("One complete after for each photo. Swipe, or use the buttons.", "List total"):
        assert old not in app


def test_bedtime_ritual_is_the_exact_approved_text(surfaces):
    view = surfaces["presentation"]
    assert f"{view['reset_title']}\n\n{view['reset']}" == RITUAL
    assert view["reset_paragraphs"] == RITUAL.split("\n\n")[1:]
    assert f"{BEDTIME_RITUAL_TITLE}\n\n{BEDTIME_RITUAL_BODY}" == RITUAL
    sections, _doc = companion_sections(surfaces["lead"], surfaces["deliverable"])
    assert sections["reset_title"] == BEDTIME_RITUAL_TITLE and sections["maintenance"] == BEDTIME_RITUAL_BODY
    record = internal_record(surfaces["lead"], surfaces["deliverable"])
    assert record["reset_title"] == BEDTIME_RITUAL_TITLE and record["reset"] == BEDTIME_RITUAL_BODY


def test_evergreen_lint_allows_only_the_approved_ritual(surfaces):
    assert find_time_sensitive(RITUAL) == []
    assert find_time_sensitive(surfaces["presentation_text"]) == []
    for name in ("pdf", "board_spec", "zone_map", "email"):
        assert find_time_sensitive(surfaces[name]) == [], name
    # Anything else with a duration is still flagged, including a reworded ritual.
    assert find_time_sensitive("One-minute bedtime ritual: dim the lights.")
    assert find_time_sensitive(RITUAL.replace("Repeat the same", "For 60 seconds, repeat the same"))


def test_customer_surfaces_keep_prior_gates(surfaces):
    for name in ("pdf", "board_spec", "zone_map", "email"):
        text = surfaces[name]
        for banned in ("SOURCE_", "AFTER_", "9dbedfba", "is ready"):
            assert banned not in text, (name, banned)
    assert STORY in surfaces["email"]
    assert "Measured room outline" in surfaces["zone_map"]
    lead, deliverable, images = surfaces["lead"], surfaces["deliverable"], surfaces["images"]
    spec = board_spec(lead, deliverable, images)
    assert spec["budget_display"] == "$195" and len(spec["products"]) == 9
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
    assert len(fills) == 6 and min(fills) >= 0.40, fills
