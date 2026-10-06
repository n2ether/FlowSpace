"""Portrait presentation shares one plan with the phone page and the board."""
import io
import json
from pathlib import Path

from PIL import Image

from blueprint_presentation import build_presentation
from image_board import build_image_board

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json"


def _jpeg(color, size=(80, 60)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def test_presentation_is_customer_copy_with_separate_cards():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lead, deliverable = doc["lead"], doc["deliverable"]
    images = {
        "source_pairs": [
            {"label": "SOURCE_01", "after_label": "AFTER_01", "after": _jpeg((20, 80, 70))},
            {"label": "SOURCE_02", "after_label": "AFTER_02", "after": None},
        ]
    }
    media = [
        {"before_url": "/api/uploads/photo/a", "after_url": "/api/uploads/photo/a-after"},
        {"before_url": "/api/uploads/photo/b", "after_url": None},
    ]
    view = build_presentation(lead, deliverable, images, lead_id="9dbedfba", media=media)
    assert view["preview_path"] == "/admin/leads/9dbedfba/blueprint"
    assert view["review"]["final"] is False
    assert len(view["gallery"]) == 2
    assert view["gallery"][0]["missing"] is False
    assert view["gallery"][0]["caption"] == "Window and crib"
    assert "SOURCE_" not in view["gallery"][0]["caption"]
    assert "AFTER_" not in view["gallery"][1]["caption"]
    assert view["gallery"][1]["missing"] is True
    assert view["gallery"][1]["after_url"] is None
    assert view["safety"]
    assert view["climate"]
    assert view["reset"]
    assert "fewer decisions" in view["why_it_helps"]
    assert not any("do not" in line.lower() for line in view["safety"])
    assert view["shopping_total"] == "$174"
    assert view["headline"] == "Nicholas's Nursery"
    assert [item["name"] for item in view["plan"]["legend"]] == [
        "Sleep",
        "Change",
        "Comfort",
        "Play + Storage",
    ]
    places = {place["id"]: place for place in view["plan"]["places"]}
    assert places["dresser"]["zone"] == "Change"
    assert places["crib"]["zone"] == "Sleep"
    assert places["rocker"]["zone"] == "Comfort"
    assert view["plan"]["measured_outline"] is True
    assert view["plan"]["board_caption"] == "Room outline based on your measurements. Furniture footprints and zones are approximate."
    assert view["plan"]["room_flow"]["outline_source"] == "measured"
    assert len(view["changes"]) == 4
    assert view["reset_title"] == "ONE-MINUTE BEDTIME RITUAL"
    assert "companion guide" in view["warning_note"].lower()
    assert "DRAFT" not in view["headline"].upper()
    assert "DRAFT" not in (view["outcome"] or "").upper()
    assert "QA" not in (view["hero_label"] or "").upper()
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    board = Image.open(io.BytesIO(png))
    assert board.size == (1600, 2540)


def test_presentation_carries_the_design_plan_sections_in_board_order():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    view = build_presentation(doc["lead"], doc["deliverable"], {})
    plan = view["design_plan"]
    assert plan["label"] == "FlowSpace Design Plan"
    assert plan["title"] == "Nicholas's Nursery"
    assert plan["review_pill"] == "DRAFT / REVIEW"
    assert view["review"]["released"] is False
    assert [zone["title"] for zone in plan["zones"]] == ["Sleep", "Change", "Comfort", "Play + Storage"]
    assert plan["snapshot"]["note"] == "Representative examples for reference; prices and availability may vary."
    assert len(plan["snapshot"]["items"]) <= 5
    assert len(plan["roadmap"]) == 3
    assert plan["why"]["headline"] == "Each part of the room gets one clear job."
    assert view["companion_modules"] == ["safety", "climate", "maintenance", "styling", "assessment", "shopping", "views"]
    assert view["styling"] and view["assessment"]["zones"]
