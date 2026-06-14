"""FlowSpace PDF deliverable tests (iteration 2)."""
import asyncio
import os
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://organize-design.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNiAAIAAAUAAeImBZsAAAAASUVORK5CYII="
)


# Helper to insert a fake-paid Stripe session directly via Mongo
async def _insert_paid_session(session_id: str, plan_id: str = "plus"):
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": f"txn-{session_id}",
        "session_id": session_id,
        "plan_id": plan_id,
        "amount": 10.0 if plan_id == "plus" else 20.0,
        "currency": "usd",
        "payment_status": "paid",
        "status": "completed",
        "created_at": now,
        "updated_at": now,
    })
    client.close()


# ---------- Free plan: PDF NOT generated ----------
class TestFreePlanNoPdf:
    free_sub_id = None

    def test_free_submission_pdf_available_is_false(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_free_pdf@example.com",
                "plan_id": "free",
                "room_type": "bedroom",
                "photos_base64": [TINY_PNG],
            },
            timeout=180,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan_id"] == "free"
        assert data.get("pdf_available") is False
        assert data.get("room_type") == "bedroom"
        TestFreePlanNoPdf.free_sub_id = data["id"]

    def test_free_pdf_endpoint_returns_402(self):
        if not TestFreePlanNoPdf.free_sub_id:
            pytest.skip("free submission not created")
        r = requests.get(f"{API}/submissions/{TestFreePlanNoPdf.free_sub_id}/pdf", timeout=30)
        assert r.status_code == 402, r.text
        body = r.json()
        msg = (body.get("detail") or "").lower()
        assert "upgrade" in msg and ("plus" in msg or "premium" in msg)


# ---------- Plus plan: must require paid session ----------
class TestPlusPlanRequiresPayment:
    def test_plus_without_session_id_returns_402(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_plus_nosess@example.com",
                "plan_id": "plus",
                "room_type": "bedroom",
                "photos_base64": [TINY_PNG],
            },
            timeout=60,
        )
        assert r.status_code == 402


# ---------- Plus plan: paid session => PDF generated ----------
class TestPlusPaidPdf:
    plus_sub_id = None
    session_id = "sess_test_paid_pdf_iter2"

    def test_seed_paid_session(self):
        asyncio.run(_insert_paid_session(self.session_id, "plus"))

    def test_plus_submission_with_paid_session_generates_pdf(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "name": "TEST_plus_user",
                "email": "TEST_plus_pdf@example.com",
                "plan_id": "plus",
                "room_type": "bedroom",
                "notes": "coastal calm, budget 200",
                "photos_base64": [TINY_PNG],
                "session_id": self.session_id,
            },
            timeout=240,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan_id"] == "plus"
        assert data.get("pdf_available") is True, f"Expected pdf_available=true, got {data}"
        TestPlusPaidPdf.plus_sub_id = data["id"]

    def test_paid_pdf_endpoint_returns_pdf_with_proper_filename(self):
        if not TestPlusPaidPdf.plus_sub_id:
            pytest.skip("plus submission missing")
        r = requests.get(f"{API}/submissions/{TestPlusPaidPdf.plus_sub_id}/pdf", timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        cd = r.headers.get("content-disposition", "")
        assert "FlowSpace-Bedroom-Design-Plan.pdf" in cd, cd
        # Validate PDF magic bytes + size
        assert r.content[:4] == b"%PDF", r.content[:10]
        assert len(r.content) > 5 * 1024, f"PDF only {len(r.content)} bytes (expected > 5KB)"


# ---------- PDF endpoint for non-existing submission ----------
class TestPdfEdgeCases:
    def test_pdf_endpoint_404_for_missing(self):
        r = requests.get(f"{API}/submissions/nonexistent-xxx/pdf", timeout=30)
        assert r.status_code == 404
