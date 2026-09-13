"""Unit tests for branded PDF generation (no Mongo / live API)."""
import io
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from blueprint_layers import ryan_answers
from pdf_generator import build_pdf, plan_title, space_label
from pdf_images import (
    COMPARE_AFTER_EMPTY,
    COMPARE_BEFORE_BANNER,
    COMPARE_BEFORE_EMPTY,
    HERO_PLACEHOLDER_LABEL,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bakeoff" / "garage_org_space.json"


LEAD = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "space_type": "garage",
    "style_prefs": ["minimal"],
    "desired_feeling": ["practical"],
    "must_stay": "Existing workbench, kids' bikes",
    "daily_improvement": "Park both cars and find the sports bag",
    "budget": "100_300",
    "storage_needs": ["tools", "sports"],
}

DELIVERABLE = {
    "intro": "A garage that is easy to park in and easy to find things.",
    "needs": ["Hidden storage for tools", "Clear floor for the car"],
    "zones": [
        {"title": "Parking Zone", "desc": "Keep the existing stall clear"},
        {"title": "Storage Zone", "desc": "Bins and wall-mounted shelves, no new walls"},
        {"title": "Circulation Zone", "desc": "Keep the existing walk path"},
        {"title": "Workbench", "desc": "Tools in labeled bins"},
    ],
    "wall_color_name": "Sea Salt",
    "wall_color_code": "SW 6204",
    "wall_color_hex": "#cfd7d3",
    "wall_color_note": "Optional — consider if it helps the goal.",
    "shopping_list": [
        {"name": "Lidded bins", "qty": 6, "price": 12.0},
        {"name": "Wall shelves", "qty": 2, "price": 39.0},
    ],
    "budget_note": "$100 – $300 typical for this starter kit",
    "strategy": ["Keep the layout balanced", "Hide clutter in matching bins"],
    "action_plan": ["Declutter", "Mount shelves", "Place bins"],
    "benefits": ["Less visual noise", "Better daily routine"],
    "notes": "",
    "summary": "Organize the garage you already have.",
    "shopping_links": [{"name": "Bins", "url": "https://example.com/bins"}],
}


def _text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _jpeg_bytes(color=(16, 92, 64), size=(480, 320)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _page_image_count(pdf_bytes: bytes, page: int = 0) -> int:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages[page].images)


def test_plan_titles_are_space_aware_not_bedroom_generic():
    assert plan_title("garage") == "Garage Organization Plan"
    assert plan_title("closet") == "Closet Blueprint"
    assert plan_title("laundry_room") == "Laundry Organization Plan"
    assert plan_title("pantry") == "Pantry Organization Plan"
    assert plan_title("mudroom") == "Mudroom Organization Plan"
    assert plan_title("bedroom") == "Bedroom Organization Plan"
    assert space_label("laundry_room") == "Laundry"


def test_pdf_matches_template_sections_without_fake_dimensions():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    assert pdf[:5] == b"%PDF-"
    text = _text(pdf)

    assert "FlowSpace" in text
    assert "Ada Lovelace" in text
    assert "Garage Organization Plan" in text
    assert "Bedroom Design Plan" not in text
    low = text.lower()
    assert "organized view" in low
    assert "room layout" in low or "flow guide" in low
    assert "Storage Zone" in text
    assert "curated selections" in low or "shopping list" in low
    assert "estimated total" in low
    assert "budget" in low or "retail" in low
    assert "implementation roadmap" in low or "simple action plan" in low
    assert "guiding principles" in low or "styling rules" in low
    assert "designer assessment" in low
    assert "Shopping Links" in text
    assert "The FlowSpace Design Team" in text
    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 3
    for layer_name in (
        "Observation",
        "Human need",
        "Spatial constraint",
        "Recommendation",
        "Validation",
        "Customer instruction",
    ):
        assert layer_name.lower() in low
    assert "routine" in low or "park" in low
    assert "workbench" in low or "possessions" in low
    assert "plan completeness" in low
    assert "measurement" in low
    assert "15 ft" not in text
    assert "15ft" not in text
    assert "optional" in text.lower()
    assert "95%" in text
    assert "consider" in text.lower()


def test_optional_paint_is_framed_not_required():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    text = _text(pdf)
    assert "Optional paint" in text
    assert "consider if it helps" in text.lower() or "Consider this color" in text or "consider if it helps" in text


def test_pdf_omits_reference_photos_when_none_supplied():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={"customer_photos": []})
    text = _text(pdf)
    assert "Reference Photo" not in text


def test_pdf_handles_empty_deliverable():
    pdf = build_pdf(lead={"name": "Sam", "space_type": "closet"}, deliverable={}, images={})
    text = _text(pdf)
    assert "Sam" in text
    assert "Closet Blueprint" in text
    assert "FlowSpace" in text
    assert "95%" in text
    assert "observation" in text.lower()
    assert pdf[:5] == b"%PDF-"


def test_pdf_placeholder_when_images_missing():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    text = _text(pdf)
    assert HERO_PLACEHOLDER_LABEL in text
    assert _page_image_count(pdf, 0) == 0
    assert "BEFORE & AFTER" not in text
    assert COMPARE_BEFORE_BANNER not in text


def test_pdf_embeds_front_view_bytes_in_hero():
    organized = _jpeg_bytes((20, 110, 70), (640, 420))
    empty = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": organized, "front_view_kind": "organized"},
    )
    text = _text(pdf)
    assert HERO_PLACEHOLDER_LABEL not in text
    assert "ORGANIZED VIEW" in text
    assert "YOUR PHOTO" not in text or "RE-ZONED" in text
    assert _page_image_count(pdf, 0) >= 1
    assert len(pdf) > len(empty) + 800


def test_pdf_embeds_detail_card_views_when_provided():
    hero = _jpeg_bytes((20, 110, 70), (400, 280))
    v1 = _jpeg_bytes((40, 80, 50), (200, 140))
    v2 = _jpeg_bytes((50, 90, 60), (200, 140))
    v3 = _jpeg_bytes((30, 70, 40), (200, 140))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": hero, "view_1": v1, "view_2": v2, "view_3": v3},
    )
    assert HERO_PLACEHOLDER_LABEL not in _text(pdf)
    assert _page_image_count(pdf, 0) >= 4


def test_pdf_labels_original_photo_as_interim_hero():
    original = _jpeg_bytes((90, 80, 60), (400, 280))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": original, "front_view_kind": "original"},
    )
    text = _text(pdf)
    assert HERO_PLACEHOLDER_LABEL not in text
    assert "YOUR PHOTO" in text
    assert "ORGANIZED VIEW UNAVAILABLE" in text
    assert _page_image_count(pdf, 0) >= 1


def test_pdf_last_page_before_after_when_both_present():
    before = _jpeg_bytes((140, 110, 70), (640, 420))
    after = _jpeg_bytes((20, 110, 70), (640, 420))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={
            "front_view": after,
            "front_view_kind": "organized",
            "before": before,
            "after": after,
        },
    )
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 4
    last = reader.pages[-1]
    last_text = last.extract_text() or ""
    assert "Before & after" in last_text or "BEFORE" in last_text
    assert COMPARE_BEFORE_BANNER.split("—")[0].strip() in last_text
    assert "YOUR PHOTO" in last_text
    assert "ORGANIZED VIEW" in last_text
    assert COMPARE_BEFORE_EMPTY not in last_text
    assert COMPARE_AFTER_EMPTY not in last_text
    assert len(last.images) >= 2
    # Page 1 hero still shows the organized render
    assert HERO_PLACEHOLDER_LABEL not in _text(pdf)
    assert _page_image_count(pdf, 0) >= 1


def test_pdf_last_page_honest_empty_when_only_after():
    after = _jpeg_bytes((20, 110, 70), (400, 280))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": after, "front_view_kind": "organized"},
    )
    last_text = PdfReader(io.BytesIO(pdf)).pages[-1].extract_text() or ""
    assert COMPARE_BEFORE_EMPTY in last_text
    assert COMPARE_AFTER_EMPTY not in last_text
    assert "ORGANIZED VIEW" in last_text


def test_pdf_last_page_honest_empty_when_only_before():
    original = _jpeg_bytes((140, 110, 70), (400, 280))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"before": original, "front_view": original, "front_view_kind": "original"},
    )
    last_text = PdfReader(io.BytesIO(pdf)).pages[-1].extract_text() or ""
    assert COMPARE_AFTER_EMPTY in last_text
    assert COMPARE_BEFORE_EMPTY not in last_text
    assert "YOUR PHOTO" in last_text


def test_pdf_ignores_non_bytes_front_view():
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": "/api/uploads/photo/not-bytes"},
    )
    assert HERO_PLACEHOLDER_LABEL in _text(pdf)
    assert _page_image_count(pdf, 0) == 0


def test_bakeoff_fixture_pdf_answers_ryan_questions():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pdf = build_pdf(lead=doc["lead"], deliverable=doc["deliverable"], images={})
    text = _text(pdf)
    low = text.lower()
    answers = ryan_answers(doc["deliverable"]["blueprint_layers"])

    assert "Garage Organization Plan" in text
    assert "Bedroom Design Plan" not in text
    assert "observation" in low and "human need" in low
    assert "spatial constraint" in low and "recommendation" in low
    assert "validation" in low and "customer instruction" in low
    assert "park both cars" in low
    assert "workbench" in low
    assert "95%" in text
    assert "$100" in text or "100" in text
    assert "227" in text or "budget" in low
    assert "why" in low or "should work" in low or "routine is park" in low
    assert "15 ft" not in text
    assert "optional" in low
    assert answers["routine"]
    assert "workbench" in answers["possessions"].lower()
    # Compact magazine plan — layers add a third page at most
    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 3
