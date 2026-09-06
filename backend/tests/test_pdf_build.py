"""Unit tests for branded PDF generation (no Mongo / live API)."""
import io

from pypdf import PdfReader

from pdf_generator import build_pdf, plan_title, space_label


LEAD = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "space_type": "garage",
    "style_prefs": ["minimal"],
    "desired_feeling": ["practical"],
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
    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 2
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
    assert pdf[:5] == b"%PDF-"
