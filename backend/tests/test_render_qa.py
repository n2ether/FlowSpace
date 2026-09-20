"""Post-FLUX QA parsing and skip behavior — no live Anthropic calls."""
from render_qa import RenderQAResult, _from_payload, _parse_qa_json, review_organized_render


def test_parse_qa_json_strips_fences():
    data = _parse_qa_json('```json\n{"ok": false, "windows_covered": true}\n```')
    assert data["windows_covered"] is True


def test_qa_prompt_flags_wall_repaint():
    from render_qa import QA_PROMPT

    low = QA_PROMPT.lower()
    assert "walls_repainted" in low
    assert "light blue" in low or "blue-gray" in low
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
