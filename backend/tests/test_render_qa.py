"""Post-generation QA parsing and skip behavior — no live Anthropic calls."""
from render_qa import RenderQAResult, _from_payload, _parse_qa_json, review_organized_render


def test_parse_qa_json_strips_fences():
    data = _parse_qa_json('```json\n{"ok": false, "windows_covered": true}\n```')
    assert data["windows_covered"] is True


def test_qa_prompt_flags_wall_repaint():
    from render_qa import QA_PROMPT

    low = QA_PROMPT.lower()
    assert "walls_repainted" in low
    assert "light blue" not in low
    assert "in either direction" in low
    assert "do not fail for clutter style, paint" not in low


def test_from_payload_fails_when_walls_repainted():
    qa = _from_payload(
        {
            "ok": True,  # model contradiction — walls_repainted wins
            "windows_covered": False,
            "gravity_wrong": False,
            "walls_repainted": True,
            "reasons": ["Walls shifted from light blue to taupe"],
        }
    )
    assert qa.failed is True
    assert qa.walls_repainted is True
    assert qa.ok is False


def test_from_payload_fails_when_window_covered():
    qa = _from_payload(
        {
            "ok": True,  # model contradiction — windows_covered wins
            "windows_covered": True,
            "gravity_wrong": False,
            "reasons": ["Shelves over the right window"],
            "suggested_rotate_degrees": 0,
        }
    )
    assert qa.failed is True
    assert qa.windows_covered is True
    assert qa.ok is False


def test_from_payload_gravity_suggests_rotate():
    qa = _from_payload(
        {
            "ok": False,
            "windows_covered": False,
            "gravity_wrong": True,
            "reasons": ["Ceiling fan is on the left wall"],
            "suggested_rotate_degrees": 90,
        }
    )
    assert qa.gravity_wrong is True
    assert qa.suggested_rotate_degrees == 90
    assert qa.failed is True


def test_review_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    qa = review_organized_render(after_bytes=b"\xff\xd8\xff")
    assert qa.skipped is True
    assert qa.ok is True
    assert qa.failed is False


def test_result_as_dict_roundtrip():
    qa = RenderQAResult(
        ok=False,
        windows_covered=True,
        walls_repainted=True,
        reasons=["covered"],
        attempt=2,
    )
    dumped = qa.as_dict()
    assert dumped["windows_covered"] is True
    assert dumped["walls_repainted"] is True
    assert dumped["attempt"] == 2


def test_qa_prompt_asks_about_a_changed_camera():
    from render_qa import qa_prompt

    low = qa_prompt().lower()
    assert "camera_changed" in low
    assert "close-up became a wide view" in low
    assert "aspect-ratio padding" in low


def test_from_payload_fails_when_camera_changed():
    """Preview closet of 24 Oct 2026: a shoe close-up came back as a wide view of a whole closet."""
    qa = _from_payload(
        {
            "ok": True,
            "windows_covered": False,
            "gravity_wrong": False,
            "walls_repainted": False,
            "camera_changed": True,
            "reasons": ["BEFORE is a close-up of shoes; AFTER is a wide view of a walk-in closet"],
        }
    )
    assert qa.failed is True
    assert qa.camera_changed is True
    assert qa.as_dict()["camera_changed"] is True
    assert _from_payload({"ok": True}).camera_changed is False


def test_same_shot_payload_and_skip_without_key(monkeypatch):
    from render_qa import review_same_shot, same_shot_from_payload

    assert same_shot_from_payload({"same_shot": False, "reason": " close-up became a  wide closet "}) == (
        False,
        "close-up became a wide closet",
    )
    assert same_shot_from_payload({"same_shot": "maybe"})[0] is None
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert review_same_shot(before_bytes=b"x", after_bytes=b"y") == (None, "no_api_key")


def test_orientation_payload_and_skip_without_key(monkeypatch):
    from render_qa import confirm_orientation_problem, orientation_from_payload

    assert orientation_from_payload({"sideways": False, "reason": "bulb hangs straight down"}) == (False, "bulb hangs straight down")
    assert orientation_from_payload({})[0] is None
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert confirm_orientation_problem(before_bytes=b"x", after_bytes=b"y") == (None, "no_api_key")


def test_unconfirmed_gravity_clears_only_the_rotation_failure():
    from render_qa import clear_unconfirmed_gravity

    only_gravity = RenderQAResult(ok=False, gravity_wrong=True, suggested_rotate_degrees=90)
    cleared = clear_unconfirmed_gravity(only_gravity, "upright")
    assert cleared.ok is True and cleared.gravity_wrong is False and cleared.suggested_rotate_degrees == 0
    assert any("not confirmed" in r for r in cleared.reasons)

    also_paint = RenderQAResult(ok=False, gravity_wrong=True, walls_repainted=True, suggested_rotate_degrees=90)
    assert clear_unconfirmed_gravity(also_paint, "upright").failed is True
