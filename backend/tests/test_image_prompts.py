"""FLUX Kontext must stay the primary path when a customer photo exists."""
from ai_image_generator import (
    KONTEXT_MODEL,
    TEXT_TO_IMAGE_MODEL,
    _build_kontext_prompt,
    _build_text_to_image_prompt,
)


def test_kontext_prompt_keeps_windows_and_skips_paint():
    prompt = _build_kontext_prompt(
        {
            "space_type": "garage",
            "style_prefs": ["minimal"],
            "color_prefs": ["sage"],
            "storage_needs": ["tools"],
        },
        {"wall_color_name": "Sea Salt", "wall_color_hex": "#cfd7d3"},
    ).lower()
    assert "95%" in prompt or "~95%" in prompt
    assert "window" in prompt
    assert "repaint the walls" not in prompt
    assert "do not change wall paint" in prompt or "paint is not part of the transform" in prompt
    # Wall color from the deliverable must not be injected into the visual prompt
    assert "sea salt" not in prompt
    assert "#cfd7d3" not in prompt
    assert KONTEXT_MODEL == "black-forest-labs/flux-kontext-pro"


def test_text_to_image_does_not_force_a_paint_makeover():
    prompt = _build_text_to_image_prompt(
        {"space_type": "closet"},
        {"wall_color_name": "Sea Salt", "wall_color_hex": "#cfd7d3"},
    ).lower()
    assert "painted-wall makeover" in prompt or "keep existing wall color" in prompt
    assert "sea salt" not in prompt
    assert TEXT_TO_IMAGE_MODEL == "black-forest-labs/flux-1.1-pro"
    assert KONTEXT_MODEL != TEXT_TO_IMAGE_MODEL
