"""Email size budget, PDF photo recompression, and email preview / send parity."""
import asyncio
import base64
import io
import logging
import os

from PIL import Image
from pypdf import PdfReader

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "flowspace_email_budget_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-email-budget-32bytes")
os.environ.setdefault("ADMIN_PASSWORD", "flowspace2025")

import email_service  # noqa: E402
from email_service import (  # noqa: E402
    attachment_slug,
    email_body_html,
    encoded_message_size,
    package_attachments,
    send_blueprint,
    send_draft_package,
)
from pdf_generator import build_pdf, pdf_photo_bytes  # noqa: E402

PDF = b"%PDF-1.4 fake-pdf-bytes"
TITLE = "Nicholas's Nursery"
NOTE = "Room outline based on your measurements. Furniture footprints and zones are approximate."


def _photo(width=3200, height=2400, seed=0) -> bytes:
    """Camera-like JPEG: a gradient under grain, so it compresses like a real photo, not flat art."""
    gradient = Image.linear_gradient("L").resize((width, height))
    channels = [
        Image.blend(gradient.rotate(90 * (i + seed)).resize((width, height)), Image.effect_noise((width, height), 48), 0.35)
        for i in range(3)
    ]
    buf = io.BytesIO()
    Image.merge("RGB", channels).save(buf, format="JPEG", quality=94)
    return buf.getvalue()


def _png(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (31, 61, 44)).save(buf, format="PNG")
    return buf.getvalue()


PHOTOS = [_photo(seed=i) for i in range(2)]
VISUALS = [{"label": "Organized-1", "bytes": PHOTOS[0]}, {"label": "Organized-2", "bytes": PHOTOS[1]}]


def _package(budget, **kwargs):
    return package_attachments(
        title=TITLE,
        html="<html>body</html>",
        pdf_bytes=PDF,
        board_bytes=_png(),
        zone_map_bytes=_png(),
        extra_visuals=VISUALS,
        budget=budget,
        **kwargs,
    )


def _sizes(attachments):
    return {
        a["filename"]: Image.open(io.BytesIO(base64.b64decode(a["content"]))).size
        for a in attachments
        if a["content_type"] == "image/jpeg"
    }


def test_slug_is_readable_and_has_no_codes():
    assert attachment_slug(TITLE) == "Nicholas-Nursery"
    assert attachment_slug("Nicholas’s Nursery") == "Nicholas-Nursery"
    assert attachment_slug("") == "Blueprint"


def test_views_keep_full_resolution_when_they_fit(caplog):
    with caplog.at_level(logging.WARNING, logger="email_service"):
        attachments = _package(10**9)
    assert [a["filename"] for a in attachments] == [
        "Nicholas-Nursery-Blueprint.png",
        "Nicholas-Nursery-Room-Flow.png",
        "Organized-1.jpg",
        "Organized-2.jpg",
        "Nicholas-Nursery-Companion.pdf",
    ]
    assert _sizes(attachments) == {"Organized-1.jpg": (3200, 2400), "Organized-2.jpg": (3200, 2400)}
    assert "size budget" not in caplog.text


def test_views_step_down_only_when_the_budget_requires_it(caplog):
    full = encoded_message_size("<html>body</html>", _package(10**9))
    with caplog.at_level(logging.WARNING, logger="email_service"):
        attachments = _package(full - 1)
    assert encoded_message_size("<html>body</html>", attachments) <= full - 1
    sizes = _sizes(attachments)
    assert set(sizes) == {"Organized-1.jpg", "Organized-2.jpg"}
    assert all(max(size) <= 2400 for size in sizes.values())
    assert "stepped down" in caplog.text
    board = next(a for a in attachments if a["filename"].endswith("Blueprint.png"))
    assert base64.b64decode(board["content"]) == _png()


def test_views_are_dropped_last_and_the_send_still_goes(caplog):
    with caplog.at_level(logging.WARNING, logger="email_service"):
        attachments = _package(10)
    assert [a["filename"] for a in attachments] == [
        "Nicholas-Nursery-Blueprint.png",
        "Nicholas-Nursery-Room-Flow.png",
        "Nicholas-Nursery-Companion.pdf",
    ]
    assert "dropped 2 view photo attachments (Organized-1.jpg, Organized-2.jpg)" in caplog.text
    assert "sending anyway" in caplog.text


def _capture(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []
    monkeypatch.setattr("email_service.resend.Emails.send", lambda payload: calls.append(payload) or {"id": "ok"})
    return calls


def test_both_sends_apply_the_budget_instead_of_failing(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(email_service, "EMAIL_SIZE_BUDGET", 1000)
    common = dict(
        customer_name="Camila Sales",
        space_type="kids_room",
        lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
        pdf_bytes=PDF,
        board_bytes=_png(),
        zone_map_bytes=_png(),
        project_title=TITLE,
        extra_visuals=VISUALS,
        outline_note=NOTE,
    )
    assert asyncio.run(send_draft_package(to_email="camila@example.com", **common)) == (True, None)
    assert asyncio.run(send_blueprint(customer_email="camila@example.com", **common)) == (True, None)
    customer_payloads = [payload for payload in calls if payload["to"] == ["camila@example.com"]]
    assert len(customer_payloads) == 2
    for payload in customer_payloads:
        names = [a["filename"] for a in payload["attachments"]]
        assert not any(name.endswith(".jpg") for name in names)
        assert names[-1].endswith(".pdf")
        assert "cid:blueprint-preview" in payload["html"] and "cid:room-flow" in payload["html"]


def test_the_sent_body_is_the_body_builder_output(monkeypatch):
    calls = _capture(monkeypatch)
    common = dict(
        customer_name="Camila Sales",
        space_type="kids_room",
        lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
        pdf_bytes=PDF,
        board_bytes=_png(),
        zone_map_bytes=_png(),
        project_title=TITLE,
        outline_note=NOTE,
    )
    asyncio.run(send_draft_package(to_email="camila@example.com", **common))
    asyncio.run(send_blueprint(customer_email="camila@example.com", **common))
    body = dict(customer_name="Camila Sales", space_type="kids_room", project_title=TITLE, outline_note=NOTE)
    cids = dict(preview_src="cid:blueprint-preview", room_flow_src="cid:room-flow")
    assert calls[0]["html"] == email_body_html(**body, draft=True, lead_id=common["lead_id"], **cids)
    assert calls[1]["html"] == email_body_html(**body, **cids)
    assert NOTE in calls[0]["html"] and NOTE in calls[1]["html"]


class _Request:
    query_params: dict = {}


LEAD = {"id": "9dbedfba-81fc-45e0-b99d-36e0a1de01bb", "name": "Camila Sales", "email": "camila@example.com", "space_type": "kids_room"}


def _stub_server(monkeypatch, images, *, board, zone_map, build_pdf=lambda **_kw: PDF):
    import server

    deliverable = {"lead_id": LEAD["id"], "project_title": TITLE}

    async def render_inputs(_lead_id, _request):
        return LEAD, deliverable, images

    monkeypatch.setattr(server, "_blueprint_render_inputs", render_inputs)
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: board)
    monkeypatch.setattr(server, "build_zone_map", lambda **_kw: zone_map)
    monkeypatch.setattr(server, "build_pdf", build_pdf)
    monkeypatch.setattr(server, "draft_send_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "final_email_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "outline_caption", lambda _lead, _d: NOTE)

    class _Collection:
        async def update_one(self, *_args, **_kwargs):
            return None

    class _DB:
        leads = _Collection()
        deliverables = _Collection()

    monkeypatch.setattr(server, "db", _DB())
    return server


def test_email_preview_endpoint_matches_what_send_draft_and_send_final_email(monkeypatch):
    lead = LEAD
    board, zone_map = _png((40, 60)), _png((30, 30))
    server = _stub_server(monkeypatch, {"source_pairs": []}, board=board, zone_map=zone_map)
    calls = _capture(monkeypatch)

    def preview(draft):
        response = asyncio.run(server.render_customer_email_preview(lead["id"], _Request(), draft=draft, _=True))
        html = response.body.decode("utf-8")
        for png, cid in ((board, "cid:blueprint-preview"), (zone_map, "cid:room-flow")):
            html = html.replace("data:image/png;base64," + base64.b64encode(png).decode("ascii"), cid)
        return html

    asyncio.run(server.send_draft_package_endpoint(lead["id"], _Request(), to=None, _=True))
    asyncio.run(server.send_final_package(lead["id"], _Request(), _=True))
    draft_sent, final_sent = calls[0]["html"], calls[1]["html"]
    assert preview(draft=True) == draft_sent
    assert preview(draft=False) == final_sent
    assert NOTE in final_sent


def test_send_draft_and_send_final_attach_organized_photos_but_not_befores(monkeypatch):
    befores = [_photo(320, 240, seed=i) for i in range(2)]
    afters = [_photo(320, 240, seed=i + 2) for i in range(2)]
    pairs = [
        {"label": f"SOURCE_0{i + 1}", "before": befores[i], "after": afters[i], "status": "approved"}
        for i in range(2)
    ]
    pdf_inputs = []

    def build_pdf(**kw):
        pdf_inputs.append(kw["images"])
        return PDF

    board, zone_map = _png((40, 60)), _png((30, 30))
    server = _stub_server(monkeypatch, {"source_pairs": pairs}, board=board, zone_map=zone_map, build_pdf=build_pdf)
    calls = _capture(monkeypatch)

    assert [v["label"] for v in server._client_facing_visuals({"source_pairs": pairs})] == ["Organized-1", "Organized-2"]

    asyncio.run(server.send_draft_package_endpoint(LEAD["id"], _Request(), to=None, _=True))
    asyncio.run(server.send_final_package(LEAD["id"], _Request(), _=True))
    draft, final = calls[0], next(c for c in calls[1:] if c["to"] == [LEAD["email"]])

    slug = attachment_slug(server._customer_title(LEAD, {"lead_id": LEAD["id"], "project_title": TITLE}))
    for payload, suffix in ((draft, "-DRAFT"), (final, "")):
        attachments = payload["attachments"]
        assert [a["filename"] for a in attachments] == [
            f"{slug}-Blueprint{suffix}.png",
            f"{slug}-Room-Flow{suffix}.png",
            "Organized-1.jpg",
            "Organized-2.jpg",
            f"{slug}-Companion{suffix}.pdf",
        ]
        assert [a.get("content_id") for a in attachments] == ["blueprint-preview", "room-flow", None, None, None]
        assert base64.b64decode(attachments[0]["content"]) == board
        assert base64.b64decode(attachments[1]["content"]) == zone_map
        assert base64.b64decode(attachments[-1]["content"]) == PDF
        assert "cid:blueprint-preview" in payload["html"] and "cid:room-flow" in payload["html"]
        for att in attachments:
            assert "before" not in att["filename"].lower()
            for banned in ("SOURCE_", "AFTER_", "9dbedfba"):
                assert banned not in att["filename"]
    assert "DRAFT" in draft["subject"]

    assert len(pdf_inputs) == 2
    for images in pdf_inputs:
        assert [p["before"] for p in images["source_pairs"]] == befores
        assert [p["after"] for p in images["source_pairs"]] == afters


def test_pdf_photos_are_resampled_for_their_printed_size():
    photo = _photo(4032, 3024)
    out = pdf_photo_bytes(photo, 360, 270)
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
    assert 1000 <= img.size[0] <= 1100 and len(out) < len(photo) / 4
    small = _photo(400, 300)
    assert Image.open(io.BytesIO(pdf_photo_bytes(small, 360, 270))).size == (400, 300)
    art = _png((1200, 900))
    assert pdf_photo_bytes(art, 100, 75)[:8] == b"\x89PNG\r\n\x1a\n"


def test_companion_pdf_is_a_few_mb_with_identical_text(monkeypatch):
    import json
    from pathlib import Path

    import pdf_generator

    fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json").read_text())
    photos = [_photo(4032, 3024, seed=i) for i in range(4)]
    pairs = [
        {"label": f"SOURCE_0{i + 1}", "before": photos[2 * i], "after": photos[2 * i + 1], "status": "approved"}
        for i in range(2)
    ]
    images = {"before": photos[0], "after": photos[1], "source_pairs": pairs}
    pdf = build_pdf(lead=fixture["lead"], deliverable=fixture["deliverable"], images=images)
    monkeypatch.setattr(pdf_generator, "pdf_photo_bytes", lambda data, *_a, **_k: data)
    original = build_pdf(lead=fixture["lead"], deliverable=fixture["deliverable"], images=images)
    assert len(pdf) < 6_000_000 < len(original)
    text = lambda raw: [page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages]  # noqa: E731
    assert text(pdf) == text(original)
