"""OpenAI image edit must stay the primary path when a customer photo exists."""
from ai_image_generator import (
    IMAGE_MODEL,
    WALL_PRESERVE_RAILS,
    WALL_RETRY_CONSTRAINT,
    _build_kontext_prompt,
    _build_text_to_image_prompt,
    edit_api_params,
    generate_api_params,
    _soft_goods_colors,
)


def _assert_wall_preserve_rails(prompt: str) -> None:
    low = prompt.lower()
    assert "existing wall paint" in low or "wall paint lock" in low or "wall paint must match" in low
    assert "never" in low and "wall" in low
    assert "textile" in low
    assert "do not change wall paint" in low or "keep existing wall color" in low
    assert "cool gray-blue" in low or "light blue" in low
    assert "taupe" in low


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
    assert IMAGE_MODEL == "gpt-image-2.5-sunburst"
    assert "flux" not in IMAGE_MODEL
    assert "kontext" not in IMAGE_MODEL
    assert "six-drawer" not in prompt
    assert "image_prompt" not in prompt


def test_kontext_prompt_applies_color_prefs_only_to_soft_goods():
    prompt = _build_kontext_prompt(
        {
            "space_type": "closet",
            "color_prefs": ["earth"],
        }
    )
    low = prompt.lower()
    assert "earth" in low
    assert "never walls" in low
    assert "textile" in low
    assert "light blue" in low or "cool gray-blue" in low or "gray-blue" in low
    assert "taupe" in low  # called out as a wall color we must not shift toward
    assert "warm neutrals with soft sage accents" not in low
    # color_prefs must not be framed as a room/wall palette
    assert "earth tones textiles and accessories." not in low
    assert low.index("wall paint") < low.index("earth") or "wall paint lock" in low


def test_color_fallback_is_not_warm_neutrals():
    assert "warm" not in _soft_goods_colors({}).lower()
    assert "sage" not in _soft_goods_colors({}).lower()
    assert "textile" in _soft_goods_colors({}).lower()
    assert "wall paint" in WALL_PRESERVE_RAILS.lower()
    assert WALL_PRESERVE_RAILS.lower().startswith("critical") or "must match" in WALL_PRESERVE_RAILS.lower()


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
    assert generate_api_params(prompt)["model"] == IMAGE_MODEL
    assert generate_api_params(prompt)["size"] == "1536x1152"
    assert "warm neutrals with soft sage accents" not in prompt


def test_openai_edit_params_match_the_source_and_skip_replicate_knobs():
    payload = edit_api_params("keep the walls")
    assert payload["model"] == "gpt-image-2.5-sunburst"
    assert payload["size"] == "auto"
    assert payload["output_format"] == "jpeg"
    assert payload["quality"] == "high"
    assert "input_fidelity" not in payload
    assert "prompt_upsampling" not in payload
    assert "guidance" not in payload
    assert "guidance_scale" not in payload
    assert "prompt_strength" not in payload
    assert "aspect_ratio" not in payload
    assert "flux" not in payload["model"]


def test_nursery_prompt_keeps_the_dresser_and_skips_cubbies():
    lead = {
        "space_type": "kids_room",
        "must_stay": "Six-drawer dresser, crib",
        "storage_needs": ["clothing"],
    }
    prompt = _build_kontext_prompt(lead).lower()
    assert "six-drawer" in prompt or "six drawer" in prompt
    assert "do not replace drawers with baskets" in prompt or "do not add baskets in place of drawers" in prompt
    assert "large open cubbies" in prompt
    assert "matching baskets, labeled bins" not in prompt
    text_prompt = _build_text_to_image_prompt(lead).lower()
    assert "large open cubbies" in text_prompt
    assert "modular shelving, labeled bins, baskets" not in text_prompt


def test_garage_prompt_still_allows_bins():
    prompt = _build_kontext_prompt({"space_type": "garage", "storage_needs": ["tools"]}).lower()
    assert "labeled bins" in prompt
    assert "nursery / kids room lock" not in prompt


def test_nursery_prompt_clears_the_crib_and_strengthens_a_space_theme():
    lead = {
        "space_type": "kids_room",
        "must_stay": "Six-drawer dresser, crib, space-themed wall decor",
        "goals": "Keep the space theme",
    }
    prompt = _build_kontext_prompt(lead, {"summary": "Keep the planets and the moon."}).lower()
    assert "teddy" in prompt
    assert "sleep sack" in prompt
    assert "fitted sheet" in prompt
    assert "loose cushion" in prompt
    assert "astronaut" in prompt
    assert "planets" in prompt
    assert "nursery animals" in prompt
    assert "do not repaint the walls to create it" in prompt or "do not repaint the walls" in prompt
    plain = _build_kontext_prompt({"space_type": "kids_room", "must_stay": "Six-drawer dresser, crib"}).lower()
    assert "teddy" in plain
    assert "sleep sack" in plain
    assert "astronaut" not in plain
    garage = _build_kontext_prompt({"space_type": "garage", "storage_needs": ["tools"]}).lower()
    assert "teddy" not in garage
    assert "astronaut" not in garage
    assert "crib interior" not in garage


def test_supporting_views_target_distinct_focal_points():
    from space_rails import supporting_view_plan

    nursery = supporting_view_plan({"space_type": "kids_room", "must_stay": "crib"})
    captions = [caption for _slot, _instruction, caption in nursery]
    assert captions == ["Dresser and changing station", "Rocker", "Door and circulation"]
    blob = " ".join(instruction for _slot, instruction, _caption in nursery).lower()
    assert "dresser" in blob
    assert "rocker" in blob or "rocking" in blob
    assert "door" in blob
    assert "window-and-crib" in blob
    assert "closer to the sleep" not in blob
    general = supporting_view_plan({"space_type": "garage"})
    general_blob = " ".join(instruction for _slot, instruction, _caption in general).lower()
    assert "crib" not in general_blob
    assert [caption for _slot, _instruction, caption in general] == [
        "Main storage",
        "Daily-use zone",
        "Door and circulation",
    ]


def test_supporting_prompt_keeps_nursery_rails_and_wall_lock():
    from ai_image_generator import _supporting_prompt
    from space_rails import supporting_view_plan

    instruction = supporting_view_plan({"space_type": "kids_room"})[0][1]
    prompt = _supporting_prompt(
        {"space_type": "kids_room", "must_stay": "Six-drawer dresser, crib, space-themed wall decor", "goals": "space theme"},
        {},
        instruction,
    ).lower()
    assert "six-drawer" in prompt or "six drawer" in prompt
    assert "do not replace drawers with baskets" in prompt or "do not add baskets in place of drawers" in prompt
    assert "wall paint" in prompt
    assert "additional after view" in prompt
    assert "dresser and changing station" in prompt
    assert "teddy" in prompt
    assert "astronaut" in prompt
    assert "measured floor plan" not in prompt or "invent a new floor plan" in prompt


def test_drafter_system_prompt_includes_window_and_fixture_rails():
    from ai_drafter import SYSTEM_PROMPT

    prompt = SYSTEM_PROMPT.lower()
    assert "over or in front of windows" in prompt
    assert "ceiling fans" in prompt
    assert "gravity-correct" in prompt or "floor at the bottom" in prompt
    assert "keep existing / no paint change" in prompt
    assert "do not invent optional" in prompt or "warm taupe" in prompt
    assert "six-drawer" in prompt
    assert "one kit total" in prompt
