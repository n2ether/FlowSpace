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
    assert "never place shelves" in prompt
    assert "window" in prompt and "door" in prompt
    assert "ceiling fan" in prompt or "ceiling fans" in prompt
    assert "gravity" in prompt
    assert KONTEXT_MODEL == "black-forest-labs/flux-kontext-pro"


def test_kontext_retry_rails_are_stronger():
    prompt = _build_kontext_prompt(
        {"space_type": "laundry"},
        stronger_rails=True,
        extra_constraint="Do not cover the right window.",
    ).lower()
    assert "previous render failed qa" in prompt
    assert "do not cover the right window" in prompt
    assert "ceiling" in prompt


def test_text_to_image_does_not_force_a_paint_makeover():
    prompt = _build_text_to_image_prompt(
        {"space_type": "closet"},
        {"wall_color_name": "Sea Salt", "wall_color_hex": "#cfd7d3"},
    ).lower()
    assert "painted-wall makeover" in prompt or "keep existing wall color" in prompt
    assert "sea salt" not in prompt
    assert "over windows" in prompt or "over windows or doors" in prompt
    assert "ceiling" in prompt
    assert TEXT_TO_IMAGE_MODEL == "black-forest-labs/flux-1.1-pro"
    assert KONTEXT_MODEL != TEXT_TO_IMAGE_MODEL


def test_drafter_system_prompt_includes_window_and_fixture_rails():
    from ai_drafter import SYSTEM_PROMPT

    prompt = SYSTEM_PROMPT.lower()
    assert "over or in front of windows" in prompt
    assert "ceiling fans" in prompt
    assert "gravity-correct" in prompt or "floor at the bottom" in prompt
