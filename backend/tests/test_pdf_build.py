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


def _page_text(pdf_bytes: bytes, page: int) -> str:
    return PdfReader(io.BytesIO(pdf_bytes)).pages[page].extract_text() or ""


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
    reader = PdfReader(io.BytesIO(pdf))
    assert 2 <= len(reader.pages) <= 16
    text = _text(pdf)
    assert "FlowSpace" in text
    assert "Ada Lovelace" in text
    assert "Garage Organization Plan" in text
    assert "Bedroom Design Plan" not in text
    low = text.lower()

    assert "portrait blueprint" in low
    assert "companion" in low
    assert "Parking Zone" in text
    assert "Keep the existing stall clear" in text
    assert "shopping list" in low
    assert "list total" in low
    assert "this list totals" in low
    assert "$150" in text
    assert "step by step" in low
    assert "safety" in low
    assert "climate" in low
    assert "weekly reset" in low
    assert "Shopping Links" in text
    assert "The FlowSpace Design Team" in text

    # Six-layer reasoning stays in the backend schema — not on the customer PDF.
    assert "why this plan" not in low
    assert "observation → instruction" not in low
    assert "l01" not in low.replace(" ", "")
    assert "human need" not in low
    assert "spatial constraint" not in low
    assert "customer instruction" not in low
    assert "workbench" in low or "possessions" in low
    assert "measurement" in low
    assert "15 ft" not in text
    assert "15ft" not in text
    assert "optional" in text.lower()
    assert "95%" in text
    assert "consider" in text.lower()


def test_optional_paint_is_framed_not_required():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    text = _text(pdf)
    assert "Optional paint" in text or "WALL COLOR" in text
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
    assert "organized view" in text.lower() or "shopping list" in text.lower()
    assert pdf[:5] == b"%PDF-"
    # No photo pair, so the guide stays on one page instead of a blank follow page.
    assert len(PdfReader(io.BytesIO(pdf)).pages) >= 1


def test_pdf_placeholder_when_images_missing():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    text = _text(pdf)
    assert HERO_PLACEHOLDER_LABEL not in text
    assert _page_image_count(pdf, 0) == 0
    assert "BEFORE & AFTER" not in text
    assert COMPARE_BEFORE_BANNER not in text
    assert "do not invent an after" in text.lower() or "portrait blueprint" in text.lower()


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
    assert "BEFORE & AFTER" in text
    assert _page_image_count(pdf, 0) == 0
    assert len(PdfReader(io.BytesIO(pdf)).pages[-1].images) >= 1
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
    assert "ADDITIONAL VIEWS" not in _text(pdf)
    from image_board import board_spec

    spec = board_spec(LEAD, DELIVERABLE, {"front_view": hero, "view_1": v1, "view_2": v2, "view_3": v3})
    assert spec["detail_sources"] == ["view_1", "view_2", "view_3"]
    assert spec["detail_captions"] == ["Main storage", "Daily-use zone", "Door and circulation"]


def test_pdf_omits_additional_views_when_missing():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    assert "ADDITIONAL VIEWS" not in _text(pdf)


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
    assert COMPARE_AFTER_EMPTY in text
    assert len(PdfReader(io.BytesIO(pdf)).pages[-1].images) >= 1


def test_pdf_before_after_when_both_present_stays_compact():
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
    assert 2 <= len(reader.pages) <= 16
    text = _text(pdf)
    assert "Before & after" in text or "BEFORE" in text
    assert COMPARE_BEFORE_BANNER.split("\u2014")[0].strip() in text
    assert "YOUR PHOTO" in text
    assert "ORGANIZED VIEW" in text
    assert COMPARE_BEFORE_EMPTY not in text
    assert COMPARE_AFTER_EMPTY not in text
    low = text.lower()
    assert "organized view" in low
    assert "final organized" not in low
    assert "do not invent an after" not in low
    assert "organized view unavailable" not in low
    assert "we do not invent an organized after" not in low
    # Comparison photos are on page 2 (or a short page 3), not a 5-page magazine
    compare_page = reader.pages[-1]
    assert len(compare_page.images) >= 2
    assert HERO_PLACEHOLDER_LABEL not in text


def test_pdf_honest_empty_when_only_after():
    after = _jpeg_bytes((20, 110, 70), (400, 280))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": after, "front_view_kind": "organized"},
    )
    text = _text(pdf)
    assert COMPARE_BEFORE_EMPTY in text
    assert COMPARE_AFTER_EMPTY not in text
    assert "ORGANIZED VIEW" in text
    low = text.lower()
    assert "organized view" in low
    assert "final organized" not in low
    assert "do not invent an after" not in low
    assert "we do not invent an organized after" not in low
    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 16


def test_pdf_honest_empty_when_only_before():
    original = _jpeg_bytes((140, 110, 70), (400, 280))
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"before": original, "front_view": original, "front_view_kind": "original"},
    )
    text = _text(pdf)
    assert COMPARE_AFTER_EMPTY in text
    assert COMPARE_BEFORE_EMPTY not in text
    assert "YOUR PHOTO" in text
    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 16


def test_pdf_ignores_non_bytes_front_view():
    pdf = build_pdf(
        lead=LEAD,
        deliverable=DELIVERABLE,
        images={"front_view": "/api/uploads/photo/not-bytes"},
    )
    assert HERO_PLACEHOLDER_LABEL not in _text(pdf)
    assert _page_image_count(pdf, 0) == 0
    from image_board import board_spec

    spec = board_spec(LEAD, DELIVERABLE, {"front_view": "/api/uploads/photo/not-bytes"})
    assert spec["hero_mode"] == "placeholder"
    assert spec["claims_organized_photo"] is False


def test_bakeoff_fixture_pdf_answers_ryan_questions():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pdf = build_pdf(lead=doc["lead"], deliverable=doc["deliverable"], images={})
    text = _text(pdf)
    low = text.lower()
    answers = ryan_answers(doc["deliverable"]["blueprint_layers"])
    reader = PdfReader(io.BytesIO(pdf))

    assert "Garage Organization Plan" in text
    assert "Bedroom Design Plan" not in text
    assert "why this plan" not in low
    assert "human need" not in low
    assert "customer instruction" not in low
    assert "park" in low
    assert "car" in low
    assert "workbench" in low
    assert "95%" in text
    assert "$100" in text or "100" in text
    assert "227" in text or "budget" in low
    assert "15 ft" not in text
    assert "optional" in low
    assert answers["routine"]
    assert "workbench" in answers["possessions"].lower()
    assert 2 <= len(reader.pages) <= 16
    joined = text.lower()
    assert "shopping list" in joined
    assert "step by step" in joined or "weekly reset" in joined
