"""Unit tests for Resend delivery (API mocked — no network, no secrets)."""
import asyncio
import base64
import io

from PIL import Image

from email_service import (
    BLUEPRINT_COPY,
    ROOM_FLOW_COPY,
    customer_email_html,
    display_filename,
    send_blueprint,
    send_draft_package,
)


PDF = b"%PDF-1.4 fake-pdf-bytes"


def _sideways_jpeg() -> bytes:
    """A 40x20 landscape buffer tagged EXIF Orientation=6 (displays as 20x40 portrait)."""
    img = Image.new("RGB", (40, 20), (200, 180, 160))
    exif = img.getexif()
    exif[274] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _png(color=(10, 120, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 24), color).save(buf, format="PNG")
    return buf.getvalue()


VISUALS = [
    {"label": "Organized-1", "bytes": _sideways_jpeg()},
    {"label": "Organized-2", "bytes": _png()},
    {"label": "Organized-3", "bytes": b"not an image"},
]


def test_skips_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada",
            customer_email="ada@example.com",
            space_type="garage",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is False
    assert "RESEND_API_KEY" in (err or "")


def test_skips_when_customer_email_missing(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada",
            customer_email="  ",
            space_type="garage",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is False
    assert "email" in (err or "").lower()


def test_sends_customer_then_admin(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("ADMIN_EMAIL", "owner@flowspace.solutions")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "FlowSpace <blueprints@flowspace.solutions>")
    calls = []

    def fake_send(payload):
        calls.append(payload)
        return {"id": f"msg_{len(calls)}"}

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)

    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada Lovelace",
            customer_email="ada@example.com",
            space_type="garage",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is True
    assert err is None
    assert len(calls) == 2
    customer, admin = calls
    assert customer["to"] == ["ada@example.com"]
    assert "Garage Organization Plan" in customer["subject"]
    assert customer["attachments"][0]["filename"].endswith(".pdf")
    assert customer["attachments"][0]["content_type"] == "application/pdf"
    assert admin["to"] == ["owner@flowspace.solutions"]
    assert customer["from"] == "FlowSpace <blueprints@flowspace.solutions>"


def test_customer_success_survives_admin_failure(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []

    def fake_send(payload):
        calls.append(payload)
        if len(calls) == 2:
            raise RuntimeError("admin inbox rejected")
        return {"id": "ok"}

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)

    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada",
            customer_email="ada@example.com",
            space_type="closet",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is True
    assert err is None


def test_customer_failure_is_reported(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    def fake_send(_payload):
        raise RuntimeError("domain not verified")

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)

    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada",
            customer_email="ada@example.com",
            space_type="garage",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is False
    assert "domain not verified" in (err or "")


def test_sends_image_board_and_companion(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []

    def fake_send(payload):
        calls.append(payload)
        return {"id": "ok"}

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)
    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Camila",
            customer_email="camila@example.com",
            space_type="kids_room",
            lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
            pdf_bytes=PDF,
            board_bytes=b"\x89PNG\r\n\x1a\nboard",
        )
    )
    assert sent is True
    assert err is None
    attachments = calls[0]["attachments"]
    assert len(attachments) == 3
    assert [a["content_type"] for a in attachments] == ["image/png", "image/png", "application/pdf"]
    assert attachments[0]["filename"] == attachments[1]["filename"] == "Kids' room Organization Plan — Design Plan.png"
    assert attachments[0].get("content_id") == "blueprint-preview"
    assert "content_id" not in attachments[1]
    assert attachments[2]["filename"] == "Kids-room-Organization-Plan-Companion.pdf"
    html = calls[0]["html"].lower()
    assert "cid:blueprint-preview" in html
    assert html.find("blueprint") < html.find("companion")
    assert html.find("<img") < html.find("companion guide")
    assert "DRAFT. Review version. Not yet approved. Customer release held." in calls[0]["html"]
    assert "is ready" not in html
    assert "is Ready" not in calls[0]["html"]
    assert "qa" not in html
    assert "lead" not in html
    assert "SOURCE_" not in calls[0]["html"]
    assert "AFTER_" not in calls[0]["html"]
    assert "9dbedfba-81fc-45e0-b99d-36e0a1de01bb" not in calls[0]["html"]
    assert "9dbedfba-81fc-45e0-b99d-36e0a1de01bb" in calls[1]["html"]


def test_send_draft_package_not_final(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "FlowSpace <blueprints@flowspace.solutions>")
    calls = []

    def fake_send(payload):
        calls.append(payload)
        return {"id": "msg_draft"}

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)
    sent, err = asyncio.run(
        send_draft_package(
            to_email="reviewer@example.com",
            customer_name="Camila Sales",
            space_type="kids_room",
            lead_id="lead-9",
            pdf_bytes=PDF,
            board_bytes=b"PNG",
            cc_emails=["rb@example.com"],
        )
    )
    assert sent is True
    assert err is None
    assert len(calls) == 1
    payload = calls[0]
    assert payload["to"] == ["reviewer@example.com"]
    assert payload["cc"] == ["rb@example.com"]
    assert "DRAFT" in payload["subject"]
    assert "review version" in payload["subject"].lower()
    assert "not yet approved" in payload["subject"].lower()
    assert "not yet approved" in payload["html"].lower()
    assert "customer release held" in payload["html"].lower()
    assert "is ready" not in payload["html"].lower()
    assert len(payload["attachments"]) == 3
    assert [a.get("content_id") for a in payload["attachments"]] == ["blueprint-preview", None, None]
    assert payload["attachments"][1]["filename"].endswith(" — Design Plan.png")
    assert "DRAFT" in payload["attachments"][2]["filename"]
    html = payload["html"]
    low = html.lower()
    assert "cid:blueprint-preview" in low
    assert low.find("<img") < low.find("companion guide")
    assert "draft" in low
    assert "review version" in low
    assert "not yet approved" in low
    assert "customer release held" in low
    assert "is ready" not in low
    assert "Open the mobile preview" in html
    assert ">https://" not in html
    assert "email_sent" not in low
    assert "package_status" not in low


def test_customer_email_uses_the_nursery_title_and_in_body_preview(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []

    def fake_send(payload):
        calls.append(payload)
        return {"id": "ok"}

    monkeypatch.setattr("email_service.resend.Emails.send", fake_send)
    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Camila",
            customer_email="camila@example.com",
            space_type="kids_room",
            lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
            pdf_bytes=PDF,
            board_bytes=b"\x89PNG\r\n\x1a\nboard",
            project_title="Nicholas's Nursery",
        )
    )
    assert sent is True
    assert err is None
    html = calls[0]["html"]
    assert "Nicholas's Nursery" in html
    assert "Camila's Kids" not in html
    assert "Kids' room" not in html
    assert "cid:blueprint-preview" in html
    assert html.lower().find("<img") < html.lower().find("companion guide")
    assert "9dbedfba-81fc-45e0-b99d-36e0a1de01bb" not in html
    assert "Nicholas" in calls[0]["subject"]
    assert "DRAFT. Review version. Not yet approved. Customer release held." in html
    assert "is ready" not in html.lower()
    assert "Your FlowSpace Blueprint is Ready" not in html


def test_customer_email_preview_uses_the_review_status_line():
    html = customer_email_html(
        "Camila Sales",
        "kids_room",
        project_title="Nicholas's Nursery",
        preview_src="data:image/png;base64,abc",
    )
    status = "DRAFT. Review version. Not yet approved. Customer release held."
    assert html.count(status) >= 2
    assert "Your Blueprint is ready, Camila Sales" not in html
    assert "Your FlowSpace Blueprint is Ready" not in html
    assert "is ready" not in html.lower()
    assert "final" not in html.lower()


def test_email_preview_shows_the_room_flow_map_without_codes():
    html = customer_email_html(
        "Camila Sales",
        "kids_room",
        project_title="Nicholas's Nursery",
        preview_src="data:image/png;base64,board",
        room_flow_src="data:image/png;base64,zonemap",
    )
    low = html.lower()
    assert "data:image/png;base64,zonemap" in html
    assert low.find("base64,board") < low.find("room flow") < low.find("companion guide")
    assert "safety, climate comfort, maintenance, styling rules, the designer assessment, the shopping list, and each before and after" in html
    assert "weekly reset" not in low
    assert "DRAFT. Review version. Not yet approved. Customer release held." in html
    for banned in ("SOURCE_", "AFTER_", "9dbedfba", "is ready"):
        assert banned not in html


def test_send_attaches_the_zone_map_beside_the_board(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []
    monkeypatch.setattr("email_service.resend.Emails.send", lambda payload: calls.append(payload) or {"id": "ok"})
    sent, _err = asyncio.run(
        send_draft_package(
            to_email="reviewer@example.com",
            customer_name="Camila Sales",
            space_type="kids_room",
            lead_id="lead-9",
            pdf_bytes=PDF,
            board_bytes=b"PNG",
            zone_map_bytes=b"ZONEMAP",
        )
    )
    assert sent is True
    attachments = calls[0]["attachments"]
    assert [a.get("content_id") for a in attachments] == ["blueprint-preview", "room-flow", None, None, None]
    assert attachments[3]["filename"].endswith(" — Room Flow.png")
    assert base64.b64decode(attachments[3]["content"]) == b"ZONEMAP"
    assert "cid:room-flow" in calls[0]["html"]


BLUEPRINT_NAME = "Nicholas's Nursery — Design Plan.png"
ROOM_FLOW_NAME = "Nicholas's Nursery — Room Flow.png"


def _assert_visual_files(attachments, *, draft: bool):
    suffix = "-DRAFT" if draft else ""
    assert [a["filename"] for a in attachments] == [
        BLUEPRINT_NAME,
        ROOM_FLOW_NAME,
        BLUEPRINT_NAME,
        ROOM_FLOW_NAME,
        "Organized-1.jpg",
        "Organized-2.jpg",
        f"Nicholas-Nursery-Companion{suffix}.pdf",
    ]
    assert [a.get("content_id") for a in attachments] == ["blueprint-preview", "room-flow"] + [None] * 5
    assert attachments[0]["content"] == attachments[2]["content"]
    assert attachments[1]["content"] == attachments[3]["content"]
    views = attachments[4:6]
    for att in views:
        assert att["content_type"] == "image/jpeg"
        assert "content_id" not in att
        raw = base64.b64decode(att["content"])
        assert raw[:3] == b"\xff\xd8\xff"
        assert not Image.open(io.BytesIO(raw)).getexif()
    upright = Image.open(io.BytesIO(base64.b64decode(views[0]["content"])))
    assert upright.size == (20, 40)
    for att in attachments:
        assert not att["filename"].startswith("Before")
        for banned in ("SOURCE_", "AFTER_", "9dbedfba", "lead-9"):
            assert banned not in att["filename"]


def test_send_draft_attaches_full_size_views_and_keeps_embeds(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []
    monkeypatch.setattr("email_service.resend.Emails.send", lambda payload: calls.append(payload) or {"id": "ok"})
    sent, _err = asyncio.run(
        send_draft_package(
            to_email="camila@example.com",
            customer_name="Camila Sales",
            space_type="kids_room",
            lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
            pdf_bytes=PDF,
            board_bytes=b"PNG",
            zone_map_bytes=b"ZONEMAP",
            project_title="Nicholas's Nursery",
            extra_visuals=VISUALS,
        )
    )
    assert sent is True
    payload = calls[0]
    attachments = payload["attachments"]
    assert attachments[-1]["filename"].endswith(".pdf")
    _assert_visual_files(attachments, draft=True)
    html = payload["html"]
    assert "cid:blueprint-preview" in html and "cid:room-flow" in html
    assert BLUEPRINT_COPY in html and ROOM_FLOW_COPY in html
    assert html.find(BLUEPRINT_COPY) < html.find('src="cid:blueprint-preview"')
    assert html.find(ROOM_FLOW_COPY) < html.find('src="cid:room-flow"')
    assert "Customer release held." in html and "Not yet approved." in html
    assert "Hi Camila." in html
    assert "Camila Sales" not in html
    assert "9dbedfba" not in payload["subject"]


def test_send_final_attaches_full_size_views_and_greets_by_first_name(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    calls = []
    monkeypatch.setattr("email_service.resend.Emails.send", lambda payload: calls.append(payload) or {"id": "ok"})
    sent, _err = asyncio.run(
        send_blueprint(
            customer_name="Camila Sales",
            customer_email="camila@example.com",
            space_type="kids_room",
            lead_id="9dbedfba-81fc-45e0-b99d-36e0a1de01bb",
            pdf_bytes=PDF,
            board_bytes=b"\x89PNG\r\n\x1a\nboard",
            zone_map_bytes=b"ZONEMAP",
            project_title="Nicholas's Nursery",
            extra_visuals=VISUALS,
        )
    )
    assert sent is True
    customer = calls[0]
    _assert_visual_files(customer["attachments"], draft=False)
    assert customer["attachments"][-1]["content_type"] == "application/pdf"
    assert BLUEPRINT_COPY in customer["html"] and ROOM_FLOW_COPY in customer["html"]
    assert 'src="cid:blueprint-preview"' in customer["html"] and 'src="cid:room-flow"' in customer["html"]
    assert "Hi Camila." in customer["html"]
    assert "Camila Sales" not in customer["html"]
    assert "ready" not in customer["subject"].lower()
    assert "Nicholas's Nursery" in customer["subject"]


def test_display_filenames_keep_the_apostrophe_and_em_dash():
    assert BLUEPRINT_COPY == "Your Design Plan is shown below and attached as a full-size image."
    assert ROOM_FLOW_COPY == "The Room Flow map is its own page, shown below and attached as a separate full-size image."
    assert display_filename("Nicholas's Nursery", "Design Plan") == "Nicholas's Nursery — Design Plan.png"
    assert display_filename("Nicholas's Nursery", "Room Flow") == "Nicholas's Nursery — Room Flow.png"
    assert display_filename('A/B: "Den"?', "Design Plan") == "AB Den — Design Plan.png"
    assert display_filename("", "Room Flow") == "FlowSpace — Room Flow.png"


def test_room_flow_block_carries_the_outline_sentence():
    note = "Room outline based on your measurements. Furniture footprints and zones are approximate."
    html = customer_email_html(
        "Camila Sales",
        "kids_room",
        project_title="Nicholas's Nursery",
        preview_src="data:image/png;base64,board",
        room_flow_src="data:image/png;base64,zonemap",
        outline_note=note,
    )
    assert note in html
    assert "not a measured" not in html.lower()
