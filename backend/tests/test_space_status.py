"""My Spaces: customer-safe titles and statuses, and admin retry of a failed run."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from members import (
    DELAYED_NOTE,
    GENERATION_ESTIMATE_MINUTES,
    customer_status,
    public_space,
    space_title,
)
from tests.test_member_auth import FakeDB, _signup, client  # noqa: F401  (fixture)


def _space_lead(lead_id, member_id, **over):
    doc = {
        "id": lead_id,
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "space_type": "bedroom",
        "package_id": "plus",
        "member_id": member_id,
        "status": "review",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc.update(over)
    return doc


class TestHelpers:
    def test_space_title_uses_room_label_or_custom_other_name(self):
        assert space_title({"space_type": "bedroom"}) == "Bedroom"
        assert space_title({"space_type": "kids_room"}) == "Kids' room"
        assert space_title({"space_type": "other", "intake": {"space_type": "other", "other_label": "Craft room"}}) == "Craft room"
        assert space_title({"space_type": "other", "fact_sheet": {"space": {"type": "other", "label": "Playroom"}}}) == "Playroom"
        assert space_title({"space_type": "other"}) == "Other space"

    @pytest.mark.parametrize("raw", ["error", "review", "incomplete", "pdf_ready", "weird_new_state"])
    def test_held_and_unknown_statuses_read_in_review(self, raw):
        assert customer_status(raw) == {
            "status": "in_review",
            "status_label": "In review",
            "status_note": "Our beta team reviews every plan before it's sent.",
        }

    def test_progress_and_delivered(self):
        assert customer_status("processing")["status_label"] == "In progress"
        assert customer_status(None)["status_label"] == "In progress"
        assert customer_status("delivered")["status_label"] == "Delivered"

    def test_public_space_never_exposes_raw_error(self):
        space = public_space(
            {
                "id": "l1",
                "space_type": "garage",
                "status": "error",
                "automation_error": "Traceback: KeyError 'zones'",
                "automation_failed_at": "2026-10-10T12:00:00+00:00",
            }
        )
        assert space["title"] == "Garage"
        assert space["status"] == "in_review"
        assert "automation_error" not in space
        assert "automation_failed_at" not in space
        assert "error" not in str(space).lower()


class TestMySpacesApi:
    def test_failed_and_legacy_error_leads_render_as_in_review(self, client):  # noqa: F811
        c, db = client
        ada = _signup(c).json()
        mid = ada["member"]["id"]
        db.leads.docs.extend(
            [
                _space_lead(
                    "failed-1",
                    mid,
                    status="review",
                    package_status="review",
                    automation_failed=True,
                    automation_error="RuntimeError: OpenAI 500",
                    automation_failed_at="2026-10-10T12:00:00+00:00",
                ),
                _space_lead(
                    "legacy-1",
                    mid,
                    space_type="other",
                    intake={"space_type": "other", "other_label": "Craft room"},
                    status="error",
                    automation_error="KeyError: 'zones'",
                ),
                _space_lead("done-1", mid, space_type="closet", status="delivered", email_sent=True),
            ]
        )
        r = c.get("/api/me/spaces", headers={"Authorization": f"Bearer {ada['token']}"})
        assert r.status_code == 200, r.text
        spaces = {s["id"]: s for s in r.json()["spaces"]}
        assert spaces["failed-1"]["title"] == "Bedroom"
        assert spaces["failed-1"]["status_label"] == "In review"
        assert spaces["legacy-1"]["title"] == "Craft room"
        assert spaces["legacy-1"]["status"] == "in_review"
        assert spaces["legacy-1"]["status_label"] == "In review"
        assert spaces["done-1"]["title"] == "Closet"
        assert spaces["done-1"]["status_label"] == "Delivered"
        body = r.text.lower()
        assert "error" not in body
        assert "openai" not in body
        assert "keyerror" not in body


def test_admin_retry_restarts_a_failed_review_lead(monkeypatch):
    import server

    fake = FakeDB()
    fake.leads.docs.append(
        _space_lead(
            "failed-2",
            "m1",
            status="review",
            package_status="review",
            automation_failed=True,
            automation_error="boom",
        )
    )
    fake.leads.docs.append(_space_lead("legacy-2", "m1", status="error", automation_error="boom"))
    started = []

    async def fake_run(*, lead, db, fs_bucket):
        started.append(lead["id"])
        return True

    async def no_seed():
        return None

    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "run_automation", fake_run)
    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    headers = {"x-admin-token": server.ADMIN_PASSWORD}
    with TestClient(server.app) as c:
        for lead_id in ("failed-2", "legacy-2"):
            r = c.post(f"/api/admin/leads/{lead_id}/retry-automation", headers=headers)
            assert r.status_code == 200, r.text
        admin = c.get("/api/admin/leads", headers=headers)
    assert started == ["failed-2", "legacy-2"]
    assert all(doc["status"] == "processing" for doc in fake.leads.docs)
    assert admin.status_code == 200


class TestPaymentLabels:
    @pytest.mark.parametrize(
        "tx, label",
        [
            (None, "Awaiting payment"),
            ({"payment_status": "initiated", "status": "open"}, "Awaiting payment"),
            ({"payment_status": "unpaid", "status": "open"}, "Awaiting payment"),
            ({"payment_status": "failed", "status": "failed"}, "Payment not completed"),
            ({"payment_status": "expired", "status": "expired"}, "Checkout expired"),
            ({"payment_status": "unpaid", "status": "expired"}, "Checkout expired"),
            ({"payment_status": "paid", "status": "complete"}, "In progress"),
        ],
    )
    def test_unpaid_paid_package_never_reads_in_progress(self, tx, label):
        out = customer_status("new", paid_package=True, transaction=tx)
        assert out["status_label"] == label

    def test_free_and_processing_stay_in_progress(self):
        assert customer_status("new")["status_label"] == "In progress"
        assert customer_status("processing", paid_package=True)["status_label"] == "In progress"
        assert customer_status("paid", paid_package=True)["status_label"] == "In progress"

    def test_latest_transaction_prefers_paid_then_newest(self):
        from members import latest_transactions

        rows = [
            {"lead_id": "a", "payment_status": "expired", "status": "expired", "created_at": "2026-10-01"},
            {"lead_id": "a", "payment_status": "initiated", "status": "open", "created_at": "2026-10-02"},
            {"lead_id": "b", "payment_status": "paid", "status": "complete", "created_at": "2026-10-01"},
            {"lead_id": "b", "payment_status": "initiated", "status": "open", "created_at": "2026-10-03"},
        ]
        latest = latest_transactions(rows)
        assert latest["a"]["payment_status"] == "initiated"
        assert latest["b"]["payment_status"] == "paid"

    def test_my_spaces_reports_payment_states(self, client):  # noqa: F811
        c, db = client
        ada = _signup(c).json()
        mid = ada["member"]["id"]
        db.leads.docs.extend(
            [
                _space_lead("unpaid", mid, status="new"),
                _space_lead("declined", mid, status="new"),
                _space_lead("expired", mid, status="new"),
                _space_lead("paid", mid, status="processing"),
                _space_lead("free", mid, status="new", package_id="free"),
            ]
        )
        db.payment_transactions.docs.extend(
            [
                {"lead_id": "unpaid", "payment_status": "initiated", "status": "open", "created_at": "1"},
                {"lead_id": "declined", "payment_status": "failed", "status": "failed", "created_at": "1"},
                {"lead_id": "expired", "payment_status": "expired", "status": "expired", "created_at": "1"},
                {"lead_id": "paid", "payment_status": "paid", "status": "complete", "created_at": "1"},
            ]
        )
        r = c.get("/api/me/spaces", headers={"Authorization": f"Bearer {ada['token']}"})
        labels = {s["id"]: s["status_label"] for s in r.json()["spaces"]}
        assert labels == {
            "unpaid": "Awaiting payment",
            "declined": "Payment not completed",
            "expired": "Checkout expired",
            "paid": "In progress",
            "free": "In progress",
        }


class TestDelayNotice:
    NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

    def _space(self, minutes_ago, **over):
        started = (self.NOW - timedelta(minutes=minutes_ago)).isoformat()
        lead = {"id": "l1", "space_type": "bedroom", "status": "processing", "processing_started_at": started}
        lead.update(over)
        return public_space(lead, now=self.NOW)

    def test_within_the_estimate_reads_in_progress(self):
        space = self._space(GENERATION_ESTIMATE_MINUTES - 1)
        assert space["status"] == "in_progress"
        assert space["delayed"] is False
        assert space["estimate_minutes"] == GENERATION_ESTIMATE_MINUTES
        assert space["status_note"] == "We're preparing your Design Plan."

    def test_past_the_estimate_says_so_and_promises_an_email(self):
        space = self._space(GENERATION_ESTIMATE_MINUTES + 1)
        assert space["status"] == "in_progress"
        assert space["status_label"] == "In progress"
        assert space["delayed"] is True
        assert space["status_note"] == DELAYED_NOTE
        assert "email you" in space["status_note"]

    def test_legacy_lead_without_start_time_uses_created_at(self):
        created = (self.NOW - timedelta(minutes=45)).isoformat()
        space = self._space(0, processing_started_at=None, created_at=created)
        assert space["delayed"] is True

    @pytest.mark.parametrize("raw", ["review", "delivered", "incomplete"])
    def test_finished_work_is_never_delayed(self, raw):
        assert self._space(120, status=raw)["delayed"] is False

    def test_unpaid_checkout_is_never_delayed(self):
        out = public_space(
            {"id": "l1", "status": "new", "package_id": "plus", "created_at": "2026-01-01T00:00:00+00:00"},
            transaction={"payment_status": "initiated", "status": "open"},
            now=self.NOW,
        )
        assert out["status"] == "awaiting_payment"
        assert out["delayed"] is False

    def test_my_spaces_reports_delay_and_server_time(self, client):  # noqa: F811
        c, db = client
        ada = _signup(c).json()
        mid = ada["member"]["id"]
        long_ago = (datetime.now(timezone.utc) - timedelta(minutes=GENERATION_ESTIMATE_MINUTES + 5)).isoformat()
        just_now = datetime.now(timezone.utc).isoformat()
        db.leads.docs.extend(
            [
                _space_lead("slow", mid, status="processing", package_id="free", processing_started_at=long_ago),
                _space_lead("fresh", mid, status="processing", package_id="free", processing_started_at=just_now),
            ]
        )
        r = c.get("/api/me/spaces", headers={"Authorization": f"Bearer {ada['token']}"})
        body = r.json()
        spaces = {s["id"]: s for s in body["spaces"]}
        assert spaces["slow"]["delayed"] is True
        assert spaces["slow"]["status_note"] == DELAYED_NOTE
        assert spaces["fresh"]["delayed"] is False
        assert body["server_time"]


def test_claim_records_start_and_recovery_keeps_it(monkeypatch):
    import asyncio

    import server

    fake = FakeDB()
    fake.leads.docs.append(_space_lead("fresh", "m1", status="new", package_id="free"))
    first = "2026-10-14T11:00:00+00:00"
    fake.leads.docs.append(_space_lead("stuck", "m1", status="processing", processing_started_at=first))
    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "_schedule_automation", lambda *_a, **_k: None)

    async def run():
        await server._start_automation_for_lead(dict(fake.leads.docs[0]), None)
        await server._start_automation_for_lead(dict(fake.leads.docs[1]), None, force=True)

    asyncio.run(run())
    fresh, stuck = fake.leads.docs
    assert fresh["status"] == "processing"
    assert fresh["processing_started_at"]
    assert stuck["processing_started_at"] == first
