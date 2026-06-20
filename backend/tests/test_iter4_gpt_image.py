"""Iteration 4 tests — hybrid Claude+GPT Image 1 pipeline.
- Free submission produces a non-empty `after` base64 string
- Malformed image_b64 → API returns 200 (graceful fallback, no 500)
- Regression: /api/plans, /api/checkout/session for plus/premium, PDF endpoint behavior
"""
import os
import io
import base64
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://organize-design.preview.emergentagent.com").rstrip("/")
TIMEOUT_LONG = 240  # hybrid pipeline can take 30-60s/photo


def _tiny_png_b64() -> str:
    """Smallest valid PNG (1x1 white) as raw base64 (no data: prefix)."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------- Regression: simple endpoints ----------
class TestRegression:
    def test_plans_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/plans", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"free", "plus", "premium"}
        assert data["free"]["max_photos"] == 2
        assert data["plus"]["pdf"] is True
        assert data["premium"]["max_photos"] == 4

    def test_checkout_session_plus(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "plus", "origin_url": BASE_URL, "customer_email": "TEST_iter4@example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["url"].startswith("http")
        assert data["session_id"]

    def test_checkout_session_premium(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "premium", "origin_url": BASE_URL, "customer_email": "TEST_iter4@example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["session_id"]

    def test_checkout_rejects_free(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "free", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 400

    def test_pdf_404_for_unknown(self):
        r = requests.get(f"{BASE_URL}/api/submissions/no-such-id/pdf", timeout=30)
        assert r.status_code == 404


# ---------- GPT Image 1 pipeline ----------
class TestImageGeneration:
    """The actual review_request — verify the hybrid pipeline returns a non-empty `after`."""

    @pytest.fixture(scope="class")
    def free_submission(self):
        """Submit ONE tiny PNG on the free plan, return the parsed response."""
        payload = {
            "email": "TEST_iter4_gpt@example.com",
            "name": "Iter4 Tester",
            "plan_id": "free",
            "room_type": "closet",
            "notes": "iter4 smoke test",
            "photos_base64": [_tiny_png_b64()],
        }
        r = requests.post(f"{BASE_URL}/api/submissions", json=payload, timeout=TIMEOUT_LONG)
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:500]}"
        return r.json()

    def test_submission_returns_200_with_results(self, free_submission):
        data = free_submission
        assert data["status"] == "completed"
        assert data["plan_id"] == "free"
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1

    def test_after_image_non_empty_base64(self, free_submission):
        after = free_submission["results"][0]["after"]
        assert isinstance(after, str), f"after is not string: {type(after)}"
        assert len(after) > 1000, (
            f"after looks empty/too short (len={len(after)}). "
            "Pipeline (Claude vision + GPT Image 1) likely failed — check backend logs."
        )
        # confirm it's valid base64 decodable to bytes
        raw = base64.b64decode(after, validate=True)
        assert len(raw) > 1000, "decoded after image too small"

    def test_before_preserved(self, free_submission):
        before = free_submission["results"][0]["before"]
        # Should NOT have data: prefix (server strips it before storage)
        assert not before.startswith("data:")
        # decodable
        base64.b64decode(before, validate=True)

    def test_result_persisted_via_get(self, free_submission):
        sub_id = free_submission["id"]
        r = requests.get(f"{BASE_URL}/api/submissions/{sub_id}", timeout=30)
        assert r.status_code == 200
        doc = r.json()
        assert doc["id"] == sub_id
        assert len(doc["results"]) == 1
        # after should still be present and non-empty when fetched back
        assert len(doc["results"][0]["after"]) > 1000

    def test_free_plan_no_pdf(self, free_submission):
        sub_id = free_submission["id"]
        r = requests.get(f"{BASE_URL}/api/submissions/{sub_id}/pdf", timeout=30)
        assert r.status_code == 402  # Free → must upgrade


# ---------- Robustness ----------
class TestRobustness:
    def test_malformed_image_no_crash(self):
        """Even with a garbage image, server must return 200 (after may be empty)."""
        payload = {
            "email": "TEST_iter4_bad@example.com",
            "plan_id": "free",
            "photos_base64": ["not-a-real-base64-image-####"],
        }
        r = requests.post(f"{BASE_URL}/api/submissions", json=payload, timeout=TIMEOUT_LONG)
        assert r.status_code == 200, f"server crashed on bad image: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["status"] == "completed"
        assert len(data["results"]) == 1
        # after may be "" on failure — this is the documented graceful fallback
        assert isinstance(data["results"][0]["after"], str)

    def test_empty_photos_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/submissions",
            json={"email": "TEST_iter4_empty@example.com", "plan_id": "free", "photos_base64": []},
            timeout=30,
        )
        assert r.status_code == 400

    def test_too_many_photos_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/submissions",
            json={
                "email": "TEST_iter4_many@example.com",
                "plan_id": "free",
                "photos_base64": [_tiny_png_b64()] * 3,  # free max=2
            },
            timeout=30,
        )
        assert r.status_code == 400
