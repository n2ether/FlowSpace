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
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_STRIPE_TEST_EVENTS", "1")

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


# ──────────────────────────── Prod hardening ─────────────────────────────
class TestTestModeEvents:
    def test_test_mode_event_is_ignored_without_the_flag(self, webhook, monkeypatch):
        c, fake, runs = webhook
        monkeypatch.delenv("ALLOW_STRIPE_TEST_EVENTS", raising=False)
        r = _post(c, {**_event("evt_t1"), "livemode": False})
        assert r.status_code == 200
        assert r.json() == {"received": True, "ignored": "test_mode"}
        assert runs == []
        assert fake.stripe_events.docs == []
        assert _tx(fake)["payment_status"] == "initiated"

    @pytest.mark.parametrize("flag", ["0", "true", "yes", ""])
    def test_only_exactly_1_allows_test_events(self, webhook, monkeypatch, flag):
        c, _fake, runs = webhook
        monkeypatch.setenv("ALLOW_STRIPE_TEST_EVENTS", flag)
        assert _post(c, _event("evt_t2")).json().get("ignored") == "test_mode"
        assert runs == []

    def test_flag_allows_test_events_on_preview(self, webhook):
        c, _fake, runs = webhook
        r = _post(c, {**_event("evt_t3"), "livemode": False})
        assert r.status_code == 200 and "ignored" not in r.json()
        assert runs == ["lead-1"]

    def test_live_events_are_processed_without_the_flag(self, webhook, monkeypatch):
        c, _fake, runs = webhook
        monkeypatch.delenv("ALLOW_STRIPE_TEST_EVENTS", raising=False)
        r = _post(c, {**_event("evt_live"), "livemode": True})
        assert r.status_code == 200 and "ignored" not in r.json()
        assert runs == ["lead-1"]


class TestFailClosed:
    @pytest.mark.parametrize("env", [None, "production", "preview", ""])
    def test_missing_secret_outside_development_is_503(self, webhook, monkeypatch, env):
        c, fake, runs = webhook
        if env is None:
            monkeypatch.delenv("ENVIRONMENT", raising=False)
        else:
            monkeypatch.setenv("ENVIRONMENT", env)
        r = _post(c, {**_event("evt_f1"), "livemode": True})
        assert r.status_code == 503
        assert runs == []
        assert fake.stripe_events.docs == []

    def test_development_may_use_unsigned_events(self, webhook):
        c, _fake, runs = webhook
        assert _post(c, _event("evt_f2")).status_code == 200
        assert runs == ["lead-1"]

    def test_configured_secret_still_verifies_signatures(self, webhook, monkeypatch):
        import server

        c, _fake, runs = webhook
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setattr(server, "STRIPE_WEBHOOK_SECRET", "whsec_test")
        r = c.post(
            "/api/webhook/stripe",
            content=json.dumps({**_event("evt_f3"), "livemode": True}),
            headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=bad"},
        )
        assert r.status_code == 400
        assert runs == []


class TestEmailOnlyMatch:
    def _orphan(self, fake):
        tx = _tx(fake)
        tx["lead_id"] = None
        tx["metadata"] = {"package_id": "plus"}

    def test_email_only_match_does_not_start_automation(self, webhook, caplog):
        c, fake, runs = webhook
        self._orphan(fake)
        event = _event("evt_e1")
        event["data"]["object"]["metadata"] = {"package_id": "plus"}
        with caplog.at_level("WARNING"):
            r = _post(c, event)
        assert r.status_code == 200
        assert runs == []
        assert _lead(fake)["status"] == "new"
        assert fake.checkout_fulfillments.docs == []
        assert _tx(fake)["lead_match"] == "email_only"
        assert _tx(fake)["email_match_lead_id"] == "lead-1"
        assert any("email only" in rec.getMessage() for rec in caplog.records)

    def test_metadata_lead_id_still_fulfills(self, webhook):
        c, fake, runs = webhook
        self._orphan(fake)
        assert _post(c, _event("evt_e2")).status_code == 200
        assert runs == ["lead-1"]

    def test_transaction_lead_id_still_fulfills(self, webhook):
        c, _fake, runs = webhook
        event = _event("evt_e3")
        event["data"]["object"]["metadata"] = {"package_id": "plus"}
        assert _post(c, event).status_code == 200
        assert runs == ["lead-1"]

    def test_status_poll_with_email_only_does_not_fulfill(self, webhook):
        c, fake, runs = webhook
        self._orphan(fake)
        _tx(fake)["payment_status"] = "paid"
        r = c.get("/api/checkout/status/cs_1")
        assert r.status_code == 200
        assert runs == []


class TestCheckoutStatusPrivacy:
    def test_status_returns_only_payment_fields(self, webhook):
        c, fake, _runs = webhook
        _tx(fake)["payment_status"] = "paid"
        _tx(fake)["metadata"] = {"lead_id": "lead-1", "member_id": "m-1", "email": "camila@example.com"}
        r = c.get("/api/checkout/status/cs_1")
        assert r.status_code == 200
        assert set(r.json()) == {"payment_status", "status", "amount_total", "currency"}
        for leaked in ("camila@example.com", "lead-1", "m-1", "lead_id", "member_id", "email"):
            assert leaked not in r.text

    def test_unpaid_status_poll_hides_stripe_metadata(self, webhook, monkeypatch):
        import stripe

        import server

        c, _fake, _runs = webhook
        session = stripe.checkout.Session.construct_from(
            {
                "id": "cs_1",
                "object": "checkout.session",
                "payment_status": "unpaid",
                "status": "open",
                "amount_total": 1000,
                "currency": "usd",
                "metadata": {"lead_id": "lead-1", "member_id": "m-1", "email": "camila@example.com"},
            },
            "sk_test",
        )
        monkeypatch.setattr(server.stripe_sdk.checkout.Session, "retrieve", lambda _sid: session)
        r = c.get("/api/checkout/status/cs_1")
        assert r.status_code == 200
        assert r.json() == {"payment_status": "unpaid", "status": "open", "amount_total": 1000, "currency": "usd"}


class TestStripeMetadata:
    def test_stripe15_object_metadata_parses(self, caplog):
        import stripe

        from server import _safe_metadata

        session = stripe.checkout.Session.construct_from(
            {"id": "cs_9", "object": "checkout.session", "metadata": {"lead_id": "L1", "package_id": "plus"}},
            "sk_test",
        )
        assert not isinstance(session.metadata, dict)
        with caplog.at_level("WARNING"):
            assert _safe_metadata(session) == {"lead_id": "L1", "package_id": "plus"}
        assert not any("Could not parse Stripe metadata" in rec.getMessage() for rec in caplog.records)

    def test_metadata_from_dicts_and_missing_values(self):
        from server import _safe_metadata

        assert _safe_metadata({"metadata": {"a": 1}}) == {"a": "1"}
        assert _safe_metadata(object()) == {}
        assert _safe_metadata({"metadata": None}) == {}

    def test_webhook_event_metadata_reaches_fulfillment(self, webhook, caplog):
        c, fake, runs = webhook
        self_tx = _tx(fake)
        self_tx["lead_id"] = None
        with caplog.at_level("WARNING"):
            assert _post(c, _event("evt_m1")).status_code == 200
        assert runs == ["lead-1"]
        assert not any("Could not parse Stripe metadata" in rec.getMessage() for rec in caplog.records)


class TestCheckoutOwnership:
    @pytest.fixture
    def checkout(self, monkeypatch):
        import server

        from tests.test_member_auth import FakeDB as _DB

        fake = _DB()
        monkeypatch.setattr(server, "db", fake)
        monkeypatch.setattr(server, "STRIPE_API_KEY", "")

        async def no_seed():
            return None

        monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
        with TestClient(server.app) as c:
            ada = c.post("/api/auth/signup", json={"name": "Ada", "email": "ada@example.com", "password": "password12"}).json()
            c.cookies.clear()
            grace = c.post("/api/auth/signup", json={"name": "Grace", "email": "grace@example.com", "password": "password12"}).json()
            c.cookies.clear()
            fake.leads.docs.append(
                {"id": "lead-ada", "member_id": ada["member"]["id"], "package_id": "plus", "photos": [P1], "status": "new"}
            )
            yield c, ada, grace

    def _start(self, c, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return c.post(
            "/api/checkout/session",
            json={"package_id": "plus", "origin_url": "http://localhost:3000", "metadata": {"lead_id": "lead-ada"}},
            headers=headers,
        )

    def test_other_member_cannot_check_out_the_lead(self, checkout):
        c, _ada, grace = checkout
        assert self._start(c, grace["token"]).status_code == 404

    def test_anonymous_caller_cannot_check_out_a_member_lead(self, checkout):
        c, _ada, _grace = checkout
        assert self._start(c).status_code == 404

    def test_owner_passes_the_ownership_check(self, checkout):
        c, ada, _grace = checkout
        # Payments are disabled in this test, so the owner reaches the 503 after ownership passes.
        r = self._start(c, ada["token"])
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "PAYMENTS_DISABLED"
