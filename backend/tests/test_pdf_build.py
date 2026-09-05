"""Unit tests for branded PDF generation (no Mongo / live API)."""
import io

from pypdf import PdfReader

from pdf_generator import build_pdf


LEAD = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "space_type": "bedroom",
    "style_prefs": ["coastal", "minimal"],
    "desired_feeling": ["calm"],
}

DELIVERABLE = {
    "intro": "A space that feels welcoming, peaceful and easy to live in.",
    "needs": ["Hidden storage for clothes", "Clear surfaces for rest"],
    "zones": [
        {"title": "Sleeping Zone", "desc": "Bed anchored, nightstands paired"},
        {"title": "Storage Zone", "desc": "Dresser + baskets, no new walls"},
        {"title": "Circulation Zone", "desc": "Keep the existing walk path"},
        {"title": "Calm Corner", "desc": "Chair and a plant, not a remodel"},
    ],
    "wall_color_name": "Sea Salt",
    "wall_color_code": "SW 6204",
    "wall_color_hex": "#cfd7d3",
    "wall_color_note": "Optional accent direction only.",
    "shopping_list": [
        {"name": "Table lamps (set of 2)", "qty": 1, "price": 48.0},
        {"name": "Area rug (8x10)", "qty": 1, "price": 129.0},
    ],
    "budget_note": "$100 – $300 typical for this starter kit",
    "strategy": ["Keep the layout balanced", "Add greenery"],
    "action_plan": ["Declutter", "Add new curtains", "Place bins"],
    "benefits": ["More restful environment", "Better daily routine"],
    "notes": "Note: Measurements are approximate. Adjust to your room as needed.",
    "summary": "Organize the room you already have.",
    "shopping_links": [{"name": "Bins", "url": "https://example.com/bins"}],
}


def _text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def test_pdf_matches_template_sections_without_fake_dimensions():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    assert pdf[:5] == b"%PDF-"
    text = _text(pdf)

    assert "FlowSpace" in text
    assert "Ada Lovelace" in text
    assert "Bedroom Design Plan" in text
    assert "COASTAL" in text or "Coastal" in text or "MINIMAL" in text
    assert "3D VISUAL" in text
    assert "Room Layout & Zones" in text
    assert "Sleeping Zone" in text
    assert "Shopping List" in text
    assert "Estimated Total" in text
    assert "BUDGET RANGE" in text or "Budget" in text
    assert "Design Strategy" in text
    assert "Simple Action Plan" in text
    assert "Benefits" in text
    assert "More restful environment" in text
    assert "Design Summary" in text
    assert "Shopping Links" in text
    assert "The FlowSpace Design Team" in text
    assert "15 ft" not in text
    assert "15ft" not in text
    assert "do not invent" in text.lower() or "Floor plan not included" in text


def test_pdf_omits_reference_photos_when_none_supplied():
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={"customer_photos": []})
    text = _text(pdf)
    assert "Reference Photo" not in text


def test_pdf_handles_empty_deliverable():
    pdf = build_pdf(lead={"name": "Sam", "space_type": "closet"}, deliverable={}, images={})
    text = _text(pdf)
    assert "Sam" in text
    assert "Closet Design Plan" in text
    assert "FlowSpace" in text
    assert pdf[:5] == b"%PDF-"
