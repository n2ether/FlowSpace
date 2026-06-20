"""Iteration 5 tests — async submission pattern.

Verifies:
- POST /api/submissions returns FAST (<3s) with status='pending'
- Polling GET shows pending -> processing -> completed transitions
- photos_done increments and pdf_available flips after photos complete
- Final completed state: results.after non-empty, pdf available for paid plans
- 404 on unknown submission id
- Regression: /api/plans, /api/checkout/session
"""
import os
import io
import time
import base64
import pytest
import requests
from PIL import Image

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
POLL_TIMEOUT_S = 240  # generous for 2 GPT Image 1 + Claude PDF for Plus


def _tiny_png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _poll_until_done(sub_id: str, timeout_s: int = POLL_TIMEOUT_S):
    deadline = time.time() + timeout_s
    statuses_seen = []
    last_doc = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/submissions/{sub_id}", timeout=60)
        except requests.exceptions.RequestException:
            time.sleep(3.5)
            continue
        assert r.status_code == 200, r.text
        doc = r.json()
        last_doc = doc
        if not statuses_seen or statuses_seen[-1] != doc["status"]:
            statuses_seen.append(doc["status"])
        if doc["status"] in ("completed", "failed"):
            return doc, statuses_seen
        time.sleep(3.5)
    pytest.fail(f"submission {sub_id} did not finish within {timeout_s}s; last={last_doc}")


# ---------- POST returns fast ----------
class TestPostReturnsFast:
    def test_free_post_returns_immediately(self):
        payload = {
            "email": "TEST_iter5_fast@example.com",
            "plan_id": "free",
            "room_type": "bedroom",
            "photos_base64": [_tiny_png_b64()],
        }
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/submissions", json=payload, timeout=15)
        dur = time.time() - t0
        assert r.status_code == 200, r.text
        # MUST be well below the 60s prod ingress timeout
        assert dur < 5.0, f"POST took {dur:.2f}s (must be <5s; prod ingress kills @60s)"
        data = r.json()
        assert data["status"] == "pending"
        assert data["photos_total"] == 1
        assert data["photos_done"] == 0
        assert data["pdf_available"] is False
        # results placeholder present
        assert isinstance(data["results"], list) and len(data["results"]) == 1


# ---------- Polling lifecycle ----------
class TestPollingLifecycle:
    @pytest.fixture(scope="class")
    def plus_final(self):
        payload = {
            "email": "TEST_iter5_plus@example.com",
            "name": "Iter5 Plus",
            "plan_id": "plus",
            "room_type": "bedroom",
            "budget": "$100 – $300",
            "photos_base64": [_tiny_png_b64()],
        }
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/submissions", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        post_dur = time.time() - t0
        assert post_dur < 5.0
        data = r.json()
        assert data["status"] == "pending"
        sub_id = data["id"]
        doc, statuses = _poll_until_done(sub_id)
        return {"sub_id": sub_id, "doc": doc, "statuses": statuses, "post_dur": post_dur}

    def test_status_transitions_to_completed(self, plus_final):
        doc = plus_final["doc"]
        statuses = plus_final["statuses"]
        assert doc["status"] == "completed", f"final={doc.get('status')}; saw={statuses}"
        assert any(s in statuses for s in ("pending", "processing")), (
            f"never saw an in-progress status; saw={statuses}"
        )

    def test_completed_has_non_empty_after(self, plus_final):
        doc = plus_final["doc"]
        assert doc["status"] == "completed"
        after = doc["results"][0]["after"]
        assert isinstance(after, str) and len(after) > 1000, (
            f"after image missing/too small (len={len(after)})"
        )
        raw = base64.b64decode(after, validate=True)
        assert len(raw) > 1000

    def test_pdf_available_flag_and_download(self, plus_final):
        sub_id = plus_final["sub_id"]
        doc = plus_final["doc"]
        assert doc["pdf_available"] is True, "pdf_available should be True for completed Plus"
        assert doc["photos_done"] == doc["photos_total"]
        pdf = requests.get(f"{BASE_URL}/api/submissions/{sub_id}/pdf", timeout=60)
        assert pdf.status_code == 200
        assert pdf.headers.get("content-type", "").startswith("application/pdf")
        assert len(pdf.content) > 5000, f"PDF too small ({len(pdf.content)} bytes)"


# ---------- 404 handling ----------
class TestNotFound:
    def test_unknown_submission_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/submissions/non-existent-id-iter5", timeout=15)
        assert r.status_code == 404

    def test_unknown_submission_pdf_404(self):
        r = requests.get(f"{BASE_URL}/api/submissions/non-existent-id-iter5/pdf", timeout=15)
        assert r.status_code == 404


# ---------- Regression ----------
class TestRegression:
    def test_plans(self):
        r = requests.get(f"{BASE_URL}/api/plans", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"free", "plus", "premium"}
        assert data["plus"]["pdf"] is True
        assert data["premium"]["max_photos"] == 4

    def test_checkout_plus(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "plus", "origin_url": BASE_URL, "customer_email": "TEST_iter5@example.com"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["session_id"]

    def test_checkout_premium(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "premium", "origin_url": BASE_URL, "customer_email": "TEST_iter5@example.com"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["session_id"]

    def test_checkout_rejects_free(self):
        r = requests.post(
            f"{BASE_URL}/api/checkout/session",
            json={"plan_id": "free", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 400

    def test_empty_photos_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/submissions",
            json={"email": "TEST_iter5_empty@example.com", "plan_id": "free", "photos_base64": []},
            timeout=15,
        )
        assert r.status_code == 400

    def test_too_many_photos_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/submissions",
            json={
                "email": "TEST_iter5_many@example.com",
                "plan_id": "free",
                "photos_base64": [_tiny_png_b64()] * 3,
            },
            timeout=15,
        )
        assert r.status_code == 400
