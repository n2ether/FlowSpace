"""FlowSpace backend API tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://organize-design.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# 1x1 PNG base64
TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNiAAIAAAUAAeImBZsAAAAASUVORK5CYII="
)


# ---------- /api/plans ----------
class TestPlans:
    def test_get_plans_returns_three_plans(self):
        r = requests.get(f"{API}/plans", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) >= {"free", "plus", "premium"}
        assert data["free"]["max_photos"] == 2 and data["free"]["price"] == 0
        assert data["plus"]["max_photos"] == 3 and data["plus"]["price"] == 10
        assert data["premium"]["max_photos"] == 4 and data["premium"]["price"] == 20
        assert data["free"]["pdf"] is False
        assert data["plus"]["pdf"] is True
        assert data["premium"]["pdf"] is True


# ---------- /api/checkout/session ----------
class TestCheckout:
    def test_checkout_session_for_plus(self):
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "plus", "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        assert "stripe.com" in data["url"]
        assert isinstance(data["session_id"], str) and len(data["session_id"]) > 0
        TestCheckout.plus_session_id = data["session_id"]

    def test_checkout_session_for_premium(self):
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "premium", "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "stripe.com" in data["url"]
        assert data["session_id"]

    def test_checkout_session_rejects_free(self):
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "free", "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 400

    def test_checkout_session_rejects_invalid(self):
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "nope", "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 400

    def test_checkout_status_returns_open(self):
        # Create a session first
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "plus", "origin_url": "https://example.com"},
            timeout=30,
        )
        sid = r.json()["session_id"]
        s = requests.get(f"{API}/checkout/status/{sid}", timeout=30)
        assert s.status_code == 200, s.text
        body = s.json()
        assert body["status"] in ("open", "complete")
        assert body["payment_status"] in ("unpaid", "paid", "no_payment_required")
        assert body["plan_id"] == "plus"
        assert body["currency"].lower() == "usd"


# ---------- /api/submissions ----------
class TestSubmissions:
    submission_id = None

    def test_free_submission_creates_results(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "name": "TEST_user",
                "email": "TEST_free@example.com",
                "plan_id": "free",
                "photos_base64": [TINY_PNG],
            },
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert data["plan_id"] == "free"
        assert isinstance(data["results"], list) and len(data["results"]) == 1
        assert "before" in data["results"][0]
        assert "after" in data["results"][0]  # may be empty string
        TestSubmissions.submission_id = data["id"]

    def test_get_submission_by_id(self):
        if not TestSubmissions.submission_id:
            pytest.skip("submission_id missing")
        r = requests.get(f"{API}/submissions/{TestSubmissions.submission_id}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == TestSubmissions.submission_id
        assert data["plan_id"] == "free"
        assert len(data["results"]) >= 1

    def test_get_submission_not_found(self):
        r = requests.get(f"{API}/submissions/nonexistent-id-xxx", timeout=30)
        assert r.status_code == 404

    def test_paid_plan_rejected_without_session(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_paid@example.com",
                "plan_id": "plus",
                "photos_base64": [TINY_PNG],
            },
            timeout=60,
        )
        assert r.status_code == 402

    def test_paid_plan_rejected_with_unpaid_session(self):
        # create a session, then try to submit with it (unpaid)
        cs = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "plus", "origin_url": "https://example.com"},
            timeout=30,
        )
        sid = cs.json()["session_id"]
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_unpaid@example.com",
                "plan_id": "plus",
                "photos_base64": [TINY_PNG],
                "session_id": sid,
            },
            timeout=60,
        )
        assert r.status_code == 402

    def test_photo_limit_enforced(self):
        # Free plan max 2 — send 3
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_limit@example.com",
                "plan_id": "free",
                "photos_base64": [TINY_PNG, TINY_PNG, TINY_PNG],
            },
            timeout=60,
        )
        assert r.status_code == 400

    def test_invalid_plan_rejected(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_invalid@example.com",
                "plan_id": "ultra",
                "photos_base64": [TINY_PNG],
            },
            timeout=30,
        )
        assert r.status_code == 400

    def test_empty_photos_rejected(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_empty@example.com",
                "plan_id": "free",
                "photos_base64": [],
            },
            timeout=30,
        )
        assert r.status_code == 400
