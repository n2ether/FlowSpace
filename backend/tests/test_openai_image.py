"""OpenAI Images edit/generate wiring — no live API calls."""
import asyncio
import base64
import io
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image
from openai import AsyncOpenAI

from ai_image_generator import generate_front_view, generate_supporting_views


def _jpeg(*, size=(80, 40), color=(20, 80, 200), orientation=1) -> bytes:
    img = Image.new("RGB", size, color)
    exif = img.getexif()
    exif[274] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def _png() -> bytes:
    img = Image.new("RGB", (16, 16), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Images:
    def __init__(self, *, payload: bytes, edit_error: BaseException | None = None):
        self.edits = []
        self.generates = []
        self.payload_b64 = base64.b64encode(payload).decode("ascii")
        self.edit_error = edit_error

    async def edit(self, **kwargs):
        self.edits.append(kwargs)
        if self.edit_error:
            raise self.edit_error
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self.payload_b64, url=None)])

    async def generate(self, **kwargs):
        self.generates.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self.payload_b64, url=None)])


def _run(monkeypatch, *, photo=None, images=None, key="sk-test"):
    images = images or _Images(payload=b"\xff\xd8\xfffake-jpeg")
    monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setattr("ai_image_generator._openai_client", lambda api_key: SimpleNamespace(images=images))
    return asyncio.run(
        generate_front_view(
            lead={"space_type": "garage", "style_prefs": ["minimal"], "color_prefs": ["sage"]},
            deliverable={},
            fs_bucket=None,
            reference_photo_bytes=photo,
        )
    ), images


def test_missing_openai_key_fails_before_any_client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def boom(_api_key):
        raise AssertionError("OpenAI client should not be constructed")

    monkeypatch.setattr("ai_image_generator._openai_client", boom)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        asyncio.run(
            generate_front_view(
                lead={"space_type": "closet"},
                deliverable=None,
                fs_bucket=None,
            )
        )


def test_blank_openai_key_is_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        asyncio.run(
            generate_front_view(lead={}, deliverable=None, fs_bucket=None)
        )


def test_reference_photo_uses_image_edit_and_returns_bytes(monkeypatch):
    photo = _jpeg(size=(60, 40), orientation=1)
    (raw, mime), images = _run(monkeypatch, photo=photo)
    assert mime == "image/jpeg"
    assert raw.startswith(b"\xff\xd8\xff")
    assert images.generates == []
    assert len(images.edits) == 1
    call = images.edits[0]
    assert call["model"] == "gpt-image-2.5-sunburst"
    assert call["size"] == "auto"
    assert "flux" not in call["model"]
    assert "input_fidelity" not in call
    assert "do not change wall paint" in call["prompt"].lower()
    assert "gravity" in call["prompt"].lower()
    assert "window" in call["prompt"].lower()
    upload = call["image"]
    assert isinstance(upload, list) and len(upload) == 1
    filename, data, content_type = upload[0]
    assert filename == "room.jpg"
    assert content_type == "image/jpeg"
    assert data == photo


def test_edit_uprights_exif_before_openai(monkeypatch):
    sideways = _jpeg(size=(80, 40), orientation=6)
    (raw, mime), images = _run(monkeypatch, photo=sideways)
    assert mime == "image/jpeg"
    assert raw
    uploaded = images.edits[0]["image"][0][1]
    assert Image.open(io.BytesIO(uploaded)).size == (40, 80)


def test_png_reference_keeps_png_content_type(monkeypatch):
    photo = _png()
    _out, images = _run(monkeypatch, photo=photo)
    filename, _data, content_type = images.edits[0]["image"][0]
    assert filename == "room.png"
    assert content_type == "image/png"
    assert images.generates == []


def test_no_reference_photo_uses_text_to_image(monkeypatch):
    (raw, mime), images = _run(monkeypatch, photo=None)
    assert mime == "image/jpeg"
    assert raw.startswith(b"\xff\xd8\xff")
    assert images.edits == []
    assert len(images.generates) == 1
    call = images.generates[0]
    assert call["model"] == "gpt-image-2.5-sunburst"
    assert call["size"] == "1536x1152"
    assert call["output_format"] == "jpeg"
    assert "keep existing wall color" in call["prompt"].lower() or "wall paint" in call["prompt"].lower()
    assert "gravity" in call["prompt"].lower()


def test_openai_api_error_raises_runtime_error(monkeypatch):
    images = _Images(payload=b"\xff\xd8", edit_error=TimeoutError("upstream timeout"))
    with pytest.raises(RuntimeError, match="OpenAI image generation failed"):
        _run(monkeypatch, photo=_jpeg(), images=images)


def test_empty_openai_payload_raises(monkeypatch):
    images = _Images(payload=b"")
    images.payload_b64 = ""
    with pytest.raises(RuntimeError, match="did not include image bytes"):
        _run(monkeypatch, photo=_jpeg(), images=images)


def test_png_response_mime_is_png(monkeypatch):
    png = _png()
    images = _Images(payload=png)
    (raw, mime), _images = _run(monkeypatch, photo=None, images=images)
    assert raw == png
    assert mime == "image/png"


def _mock_openai(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    def factory(api_key: str):
        assert api_key == "sk-test"
        return AsyncOpenAI(api_key=api_key, http_client=http_client, max_retries=0)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("ai_image_generator._openai_client", factory)
    return http_client


def test_edit_wire_format_posts_upright_photo(monkeypatch):
    from image_orientation import upright_bytes

    captured = {}
    reply = base64.b64encode(b"\xff\xd8\xffok").decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content
        return httpx.Response(200, json={"created": 1, "data": [{"b64_json": reply}]})

    http_client = _mock_openai(monkeypatch, handler)
    sideways = _jpeg(size=(80, 40), orientation=6)

    async def run():
        try:
            return await generate_front_view(
                lead={"space_type": "garage"},
                deliverable={},
                fs_bucket=None,
                reference_photo_bytes=sideways,
                stronger_rails=True,
                extra_constraint="Do not cover the right window.",
            )
        finally:
            await http_client.aclose()

    raw, mime = asyncio.run(run())
    assert mime == "image/jpeg"
    assert raw.startswith(b"\xff\xd8\xff")
    assert captured["url"].endswith("/v1/images/edits")
    assert captured["content_type"].startswith("multipart/form-data")
    body = captured["body"]
    assert b"gpt-image-2.5-sunburst" in body
    assert b"flux-kontext" not in body.lower()
    assert b"replicate" not in body.lower()
    assert upright_bytes(sideways) in body
    assert b"previous render failed qa" in body.lower()
    assert b"do not cover the right window" in body.lower()
    assert b"wall paint" in body.lower()


def test_text_to_image_wire_format_when_no_photo(monkeypatch):
    captured = {}
    reply = base64.b64encode(b"\xff\xd8\xffok").decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        captured["content_type"] = request.headers.get("content-type", "")
        return httpx.Response(200, json={"created": 1, "data": [{"b64_json": reply}]})

    http_client = _mock_openai(monkeypatch, handler)

    async def run():
        try:
            return await generate_front_view(
                lead={"space_type": "closet"},
                deliverable=None,
                fs_bucket=None,
                reference_photo_bytes=None,
            )
        finally:
            await http_client.aclose()

    raw, mime = asyncio.run(run())
    assert (raw, mime) == (b"\xff\xd8\xffok", "image/jpeg")
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["content_type"].startswith("application/json")
    body = captured["body"]
    assert b"gpt-image-2.5-sunburst" in body
    assert b"1536x1152" in body
    assert b"flux" not in body.lower()
    assert b"/v1/images/edits" not in captured["url"].encode()


def test_generator_does_not_call_flux_kontext():
    from pathlib import Path

    import ai_image_generator

    text = Path(ai_image_generator.__file__).read_text(encoding="utf-8")
    assert "flux-kontext-pro" not in text
    assert "flux-1.1-pro" not in text
    assert "REPLICATE_API_TOKEN" not in text
    assert "import replicate" not in text


def test_supporting_views_edit_the_organized_after_and_drop_qa_failures(monkeypatch):
    from render_qa import RenderQAResult

    organized = _jpeg(size=(40, 30), color=(20, 90, 70))
    original = _jpeg(size=(40, 30), color=(160, 190, 220))
    images = _Images(payload=_jpeg(size=(24, 16), color=(20, 90, 70)))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("ai_image_generator._openai_client", lambda api_key: SimpleNamespace(images=images))
    calls = {"n": 0}

    def review(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            return RenderQAResult(ok=False, walls_repainted=True, reasons=["walls repainted"])
        return RenderQAResult(ok=True)

    monkeypatch.setattr("render_qa.review_organized_render", review)
    found = asyncio.run(
        generate_supporting_views(
            lead={"space_type": "kids_room", "must_stay": "Six-drawer dresser"},
            deliverable={},
            reference_photo_bytes=original,
            organized_bytes=organized,
        )
    )
    assert set(found) == {"view_1", "view_3"}
    assert "view_2" not in found
    assert len(images.edits) == 3
    assert images.generates == []
    uploaded = images.edits[0]["image"][0][1]
    assert uploaded == organized
    prompt = images.edits[0]["prompt"].lower()
    assert "six-drawer" in prompt or "six drawer" in prompt
    assert "wall paint" in prompt
    assert "additional after view" in prompt


def test_supporting_views_skip_when_there_is_no_after(monkeypatch):
    def boom(_api_key):
        raise AssertionError("no image call without an organized after or a photo")

    monkeypatch.setattr("ai_image_generator._openai_client", boom)
    found = asyncio.run(
        generate_supporting_views(
            lead={"space_type": "kids_room"},
            deliverable={},
            reference_photo_bytes=None,
            organized_bytes=None,
        )
    )
    assert found == {}
