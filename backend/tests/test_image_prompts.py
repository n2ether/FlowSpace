"""FLUX Kontext must stay the primary path when a customer photo exists."""
from ai_image_generator import (
    KONTEXT_MODEL,
    TEXT_TO_IMAGE_MODEL,
    WALL_PRESERVE_RAILS,
    WALL_RETRY_CONSTRAINT,
    _build_kontext_prompt,
    _build_text_to_image_prompt,
    _soft_goods_colors,
)


def _assert_wall_preserve_rails(prompt: str) -> None:
    low = prompt.lower()
    assert "existing wall paint" in low or "existing wall color" in low
    assert "never" in low and "wall" in low
    assert "textile" in low
    assert "do not change wall paint" in low or "keep existing wall color" in low


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
    assert "do not change wall paint" in prompt or "paint is not part of the transform" in prompt
    _assert_wall_preserve_rails(prompt)
    # Wall color from the deliverable must not be injected into the visual prompt
    assert "sea salt" not in prompt
    assert "#cfd7d3" not in prompt
    assert "never place shelves" in prompt
    assert "window" in prompt and "door" in prompt
    assert "ceiling fan" in prompt or "ceiling fans" in prompt
    assert "gravity" in prompt
    assert KONTEXT_MODEL == "black-forest-labs/flux-kontext-pro"


def test_kontext_prompt_applies_color_prefs_only_to_soft_goods():
    prompt = _build_kontext_prompt(
        {
            "space_type": "closet",
            "color_prefs": ["earth"],
        }
    )
    low = prompt.lower()
    assert "earth" in low
    assert "only to textiles and accessories (never walls)" in low
    assert "light blue" in low or "blue-gray" in low
    assert "taupe" in low  # called out as a wall color we must not shift toward
    assert "warm neutrals with soft sage accents" not in low
    # color_prefs must not be framed as a room/wall palette
    assert "earth tones textiles and accessories." not in low


def test_color_fallback_is_not_warm_neutrals():
    assert "warm" not in _soft_goods_colors({}).lower()
    assert "sage" not in _soft_goods_colors({}).lower()
    assert "textile" in _soft_goods_colors({}).lower()
    assert WALL_PRESERVE_RAILS.lower().startswith("hard constraint")


def test_kontext_retry_rails_are_stronger():
    prompt = _build_kontext_prompt(
        {"space_type": "laundry"},
        stronger_rails=True,
        extra_constraint="Do not cover the right window.",
    ).lower()
    assert "previous render failed qa" in prompt
    assert "do not cover the right window" in prompt
    assert "ceiling" in prompt
    assert "wall color" in prompt or "wall paint" in prompt


def test_kontext_wall_retry_constraint_is_loud():
    prompt = _build_kontext_prompt(
        {"space_type": "closet", "color_prefs": ["earth"]},
        stronger_rails=True,
        extra_constraint=WALL_RETRY_CONSTRAINT,
    ).lower()
    assert "original light wall color from the photo" in prompt
    assert "textiles" in prompt
    assert "never walls" in prompt or "never to walls" in prompt


def test_text_to_image_does_not_force_a_paint_makeover():
    prompt = _build_text_to_image_prompt(
        {"space_type": "closet"},
        {"wall_color_name": "Sea Salt", "wall_color_hex": "#cfd7d3"},
    ).lower()
    assert "painted-wall makeover" in prompt or "keep existing wall color" in prompt
    assert "never wall paint" in prompt or "never walls" in prompt
    assert "sea salt" not in prompt
    assert "over windows" in prompt or "over windows or doors" in prompt
    assert "ceiling" in prompt
    assert TEXT_TO_IMAGE_MODEL == "black-forest-labs/flux-1.1-pro"
    assert KONTEXT_MODEL != TEXT_TO_IMAGE_MODEL
    assert "warm neutrals with soft sage accents" not in prompt


def test_drafter_system_prompt_includes_window_and_fixture_rails():
    from ai_drafter import SYSTEM_PROMPT

    prompt = SYSTEM_PROMPT.lower()
    assert "over or in front of windows" in prompt
    assert "ceiling fans" in prompt
    assert "gravity-correct" in prompt or "floor at the bottom" in prompt
    assert "keep existing / no paint change" in prompt
    assert "do not invent optional" in prompt or "warm taupe" in prompt
