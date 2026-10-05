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
    assert view["reset_title"] == "One-minute bedtime ritual"
    assert "companion guide" in view["warning_note"].lower()
    assert "DRAFT" not in view["headline"].upper()
    assert "DRAFT" not in (view["outcome"] or "").upper()
    assert "QA" not in (view["hero_label"] or "").upper()
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    board = Image.open(io.BytesIO(png))
    assert board.size[1] / board.size[0] == 1.5
