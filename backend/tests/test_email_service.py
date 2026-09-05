"""Unit tests for Resend delivery (API mocked — no network, no secrets)."""
import asyncio

from email_service import send_blueprint


PDF = b"%PDF-1.4 fake-pdf-bytes"


def test_skips_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    sent, err = asyncio.run(
        send_blueprint(
            customer_name="Ada",
            customer_email="ada@example.com",
            space_type="bedroom",
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
            space_type="bedroom",
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
            space_type="bedroom",
            lead_id="lead-1",
            pdf_bytes=PDF,
        )
    )
    assert sent is True
    assert err is None
    assert len(calls) == 2
    customer, admin = calls
    assert customer["to"] == ["ada@example.com"]
    assert "Blueprint" in customer["subject"]
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
