"""Unit tests for Resend delivery (API mocked — no network, no secrets)."""
import asyncio

from email_service import send_blueprint, send_draft_package


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
    assert "draft" not in html
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
    assert "not final" in payload["subject"].lower()
    assert "not final" in payload["html"].lower()
    assert len(payload["attachments"]) == 2
    assert "DRAFT" in payload["attachments"][0]["filename"]
