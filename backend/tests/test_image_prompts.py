"""FLUX Kontext must stay the primary path when a customer photo exists."""
from ai_image_generator import (
    KONTEXT_MODEL,
    TEXT_TO_IMAGE_MODEL,
    _build_kontext_prompt,
    _build_text_to_image_prompt,
)


def test_kontext_prompt_preserves_shell_and_does_not_repaint():
    prompt = _build_kontext_prompt(
        {
            "space_type": "bedroom",
            "style_prefs": ["coastal"],
            "color_prefs": ["sage"],
            "storage_needs": ["clothing"],
        },
        {"wall_color_name": "Sea Salt", "wall_color_hex": "#cfd7d3"},
    )
    assert "exact same room" in prompt.lower()
    assert "same walls" in prompt.lower()
    assert "same windows" in prompt.lower()
    assert "repaint the walls" not in prompt.lower()
    assert "do not change the wall paint" in prompt.lower() or "same wall paint" in prompt.lower()
    assert "invent" in prompt.lower()
    assert KONTEXT_MODEL == "black-forest-labs/flux-kontext-pro"


def test_text_to_image_is_only_the_no_photo_fallback():
    prompt = _build_text_to_image_prompt({"space_type": "garage"})
    assert "Photorealistic" in prompt
    assert TEXT_TO_IMAGE_MODEL == "black-forest-labs/flux-1.1-pro"
    assert KONTEXT_MODEL != TEXT_TO_IMAGE_MODEL
