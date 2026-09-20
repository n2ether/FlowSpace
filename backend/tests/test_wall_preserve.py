"""Wall paint stays as photographed unless the customer explicitly asked."""
from ai_drafter import (
    KEEP_EXISTING_WALL_NAME,
    KEEP_EXISTING_WALL_NOTE,
    SYSTEM_PROMPT,
    _coerce,
    _summarize_lead,
    customer_requested_paint,
    is_keep_existing_wall,
)
from pdf_generator import _is_keep_existing_paint, _paint_block


INVENTED_PAINT = {
    "intro": "A calmer closet.",
    "needs": ["Clear floor"],
    "zones": [{"title": "Daily", "desc": "Keep the rod"}],
    "wall_color_name": "Warm Taupe",
    "wall_color_code": "SW 7036",
    "wall_color_hex": "#D1C7B8",
    "wall_color_note": "Optional — a cozy earth-tone accent wall.",
    "shopping_list": [{"name": "Bins", "qty": 2, "price": 8}],
    "action_plan": ["Declutter the floor"],
    "benefits": ["Less visual noise"],
}


def test_customer_color_prefs_are_not_a_paint_request():
    lead = {
        "color_prefs": ["earth"],
        "desired_feeling": ["warm"],
        "goals": "I want the closet to feel calmer",
    }
    assert customer_requested_paint(lead) is False


def test_customer_requested_paint_from_free_text():
    assert customer_requested_paint({"goals": "Please paint the walls a softer blue"}) is True
    assert customer_requested_paint({"bothers_other": "I hate the accent wall"}) is True
    assert customer_requested_paint({"biggest_challenge": "Need more hangers"}) is False


def test_coerce_does_not_invent_optional_paint_by_default():
    lead = {"space_type": "closet", "color_prefs": ["earth"]}
    out = _coerce(INVENTED_PAINT, lead=lead)
    assert out["wall_color_name"] == KEEP_EXISTING_WALL_NAME
    assert out["wall_color_code"] == ""
    assert out["wall_color_hex"] == ""
    assert out["wall_color_note"] == KEEP_EXISTING_WALL_NOTE
    assert "warm taupe" not in out["wall_color_name"].lower()
    assert is_keep_existing_wall(out) is True


def test_coerce_keeps_paint_when_customer_asked():
    lead = {"space_type": "closet", "goals": "Please paint the walls"}
    out = _coerce(INVENTED_PAINT, lead=lead)
    assert out["wall_color_name"] == "Warm Taupe"
    assert out["wall_color_code"] == "SW 7036"
    assert out["wall_color_hex"].lower() == "#d1c7b8"


def test_summarize_lead_scopes_color_prefs_to_soft_goods():
    text = _summarize_lead(
        {
            "space_type": "closet",
            "color_prefs": ["earth"],
            "goals": "More hangers",
        }
    ).lower()
    assert "not wall paint" in text
    assert "earth" in text
    assert "keep existing" in text
    assert "did not ask to paint" in text


def test_system_prompt_defaults_wall_fields_to_keep_existing():
    low = SYSTEM_PROMPT.lower()
    assert "keep existing / no paint change" in low
    assert "textiles and accessories only" in low or "never walls" in low


def test_pdf_omits_makeover_paint_block_when_keeping_existing():
    deliverable = {
        "wall_color_name": KEEP_EXISTING_WALL_NAME,
        "wall_color_code": "",
        "wall_color_hex": "",
        "wall_color_note": KEEP_EXISTING_WALL_NOTE,
    }
    assert _is_keep_existing_paint(deliverable) is True
    assert _paint_block(deliverable, 400) is None
