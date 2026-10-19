"""Stripe webhook idempotency: one automation per event and per checkout session."""
import json

import pytest
from fastapi.testclient import TestClient

from tests.test_member_auth import FakeDB

P1 = "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture
def webhook(monkeypatch):
    import server

    fake = FakeDB()
    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(server, "STRIPE_API_KEY", "")

    runs = []

    async def fake_run_automation(*, lead, db, fs_bucket):
        runs.append(lead["id"])

    async def no_seed():
        return None

    monkeypatch.setattr(server, "run_automation", fake_run_automation)
    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)

    fake.leads.docs.append(
        {"id": "lead-1", "email": "camila@example.com", "package_id": "plus", "photos": [P1], "status": "new"}
    )
    fake.payment_transactions.docs.append(
        {
            "session_id": "cs_1",
            "package_id": "plus",
            "lead_id": "lead-1",
            "email": "camila@example.com",
            "payment_status": "initiated",
            "status": "open",
            "metadata": {"lead_id": "lead-1", "package_id": "plus"},
        }
    )
    with TestClient(server.app) as c:
        yield c, fake, runs


def _event(event_id, event_type="checkout.session.completed", session_id="cs_1", payment_status="paid", status="complete"):
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_status": payment_status,
                "status": status,
                "customer_email": "camila@example.com",
                "metadata": {"lead_id": "lead-1", "package_id": "plus"},
            }
        },
    }


def _post(c, payload):
    return c.post("/api/webhook/stripe", content=json.dumps(payload), headers={"Content-Type": "application/json"})


def _tx(fake, session_id="cs_1"):
    return next(d for d in fake.payment_transactions.docs if d["session_id"] == session_id)


def _lead(fake):
    return next(d for d in fake.leads.docs if d["id"] == "lead-1")


class TestEventIdempotency:
    def test_duplicate_event_creates_no_second_automation(self, webhook):
        c, fake, runs = webhook
        first = _post(c, _event("evt_1"))
        assert first.status_code == 200, first.text
        assert runs == ["lead-1"]
        assert _tx(fake)["payment_status"] == "paid"

        # Even if the lead became restartable, a redelivered event does nothing.
        _lead(fake)["status"] = "error"
        second = _post(c, _event("evt_1"))
        assert second.status_code == 200
        assert second.json().get("duplicate") is True
        assert runs == ["lead-1"]
        assert [d["event_id"] for d in fake.stripe_events.docs] == ["evt_1"]

    def test_new_event_for_same_session_is_fulfilled_once(self, webhook):
        c, fake, runs = webhook
        assert _post(c, _event("evt_1")).status_code == 200
        _lead(fake)["status"] = "new"
        r = _post(c, _event("evt_2", event_type="checkout.session.async_payment_succeeded"))
        assert r.status_code == 200
        assert runs == ["lead-1"]
        assert [d["session_id"] for d in fake.checkout_fulfillments.docs] == ["cs_1"]

    def test_status_poll_after_webhook_does_not_refulfill(self, webhook):
        c, fake, runs = webhook
        assert _post(c, _event("evt_1")).status_code == 200
        _lead(fake)["status"] = "new"
        r = c.get("/api/checkout/status/cs_1")
        assert r.status_code == 200
        assert r.json()["payment_status"] == "paid"
        assert runs == ["lead-1"]

    def test_unpaid_completion_does_not_claim_session(self, webhook):
        c, fake, runs = webhook
        r = _post(c, _event("evt_1", payment_status="unpaid"))
        assert r.status_code == 200
        assert runs == []
        assert fake.checkout_fulfillments.docs == []
        r = _post(c, _event("evt_2", event_type="checkout.session.async_payment_succeeded"))
        assert r.status_code == 200
        assert runs == ["lead-1"]

    def test_processing_error_releases_event_for_retry(self, webhook, monkeypatch):
        import server

        c, fake, runs = webhook
        calls = {"n": 0}
        real = server._find_lead_for_checkout

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("db hiccup")
            return await real(**kwargs)

        monkeypatch.setattr(server, "_find_lead_for_checkout", flaky)
        assert _post(c, _event("evt_1")).status_code == 500
        assert fake.stripe_events.docs == []
        assert fake.checkout_fulfillments.docs == []
        assert _post(c, _event("evt_1")).status_code == 200
        assert runs == ["lead-1"]

    def test_unhandled_event_types_are_acknowledged_without_recording(self, webhook):
        c, fake, runs = webhook
        r = _post(c, {"id": "evt_x", "object": "event", "type": "customer.created", "data": {"object": {"id": "cus_1"}}})
        assert r.status_code == 200
        assert fake.stripe_events.docs == []
        assert runs == []


class TestUnpaidOutcomes:
    def test_expired_session_is_marked_expired_without_automation(self, webhook):
        c, fake, runs = webhook
        r = _post(c, _event("evt_exp", event_type="checkout.session.expired", payment_status="unpaid", status="expired"))
        assert r.status_code == 200
        tx = _tx(fake)
        assert tx["payment_status"] == "expired"
        assert tx["status"] == "expired"
        assert runs == []
        assert _lead(fake)["status"] == "new"

    def test_async_payment_failed_is_marked_failed_without_automation(self, webhook):
        c, fake, runs = webhook
        r = _post(c, _event("evt_fail", event_type="checkout.session.async_payment_failed", payment_status="unpaid"))
        assert r.status_code == 200
        tx = _tx(fake)
        assert tx["payment_status"] == "failed"
        assert tx["status"] == "failed"
        assert runs == []

    def test_late_expiry_never_downgrades_a_paid_session(self, webhook):
        c, fake, runs = webhook
        assert _post(c, _event("evt_1")).status_code == 200
        r = _post(c, _event("evt_exp", event_type="checkout.session.expired", payment_status="unpaid", status="expired"))
        assert r.status_code == 200
        assert _tx(fake)["payment_status"] == "paid"
        assert runs == ["lead-1"]
