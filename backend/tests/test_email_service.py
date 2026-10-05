"""Unit tests for Resend delivery (API mocked — no network, no secrets)."""
import asyncio

from email_service import customer_email_html, send_blueprint, send_draft_package


PDF = b"%PDF-1.4 fake-pdf-bytes"


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
    assert len(attachments) == 2
    assert attachments[0]["content_type"] == "image/png"
    assert attachments[0]["filename"].endswith("_Blueprint_Camila.png")
    assert attachments[0].get("content_id") == "blueprint-preview"
    assert attachments[1]["content_type"] == "application/pdf"
    assert attachments[1]["filename"].endswith("_Companion_Camila.pdf")
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
    assert len(payload["attachments"]) == 2
    assert "DRAFT" in payload["attachments"][0]["filename"]
    assert payload["attachments"][0].get("content_id") == "blueprint-preview"
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
    assert "safety essentials, climate comfort, why it helps, the shopping list, and each before and after" in html
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
    assert [a.get("content_id") for a in attachments] == ["blueprint-preview", "room-flow", None]
    assert "DRAFT_Room_Flow" in attachments[1]["filename"]
    assert "cid:room-flow" in calls[0]["html"]
