"""My Spaces: customer-safe titles and statuses, and admin retry of a failed run."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from members import customer_status, public_space, space_title
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
