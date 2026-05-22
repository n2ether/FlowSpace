"""ClearSpace backend API tests.

Covers:
- Public: /api/, /api/packages, /api/gallery, /api/leads
- Admin auth: /api/admin/login, X-Admin-Token guard
- Admin gallery CRUD: POST /api/admin/gallery, DELETE /api/admin/gallery/{id}
- Admin leads & transactions
- Stripe checkout: /api/checkout/session, /api/checkout/status/{session_id}
- MongoDB JSON serializability (no _id leakage)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://flowspace-preview-1.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = "garage2025"


# ------------------------- Fixtures -------------------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_headers():
    return {"X-Admin-Token": ADMIN_PASSWORD, "Content-Type": "application/json"}


def _no_underscore_id(obj):
    """Recursively assert _id is not present (Mongo serialization check)."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in response: {obj}"
        for v in obj.values():
            _no_underscore_id(v)
    elif isinstance(obj, list):
        for it in obj:
            _no_underscore_id(it)


# ------------------------- Public endpoints -------------------------
class TestPublic:
    def test_root_ok(self, api):
        r = api.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "ClearSpace" in data.get("message", "")

    def test_packages_returns_three(self, api):
        r = api.get(f"{BASE_URL}/api/packages")
        assert r.status_code == 200
        data = r.json()
        pkgs = data["packages"]
        assert isinstance(pkgs, list) and len(pkgs) == 3
        by_id = {p["id"]: p for p in pkgs}
        assert by_id["basic"]["price"] == 79.0
        assert by_id["standard"]["price"] == 149.0
        assert by_id["premium"]["price"] == 299.0
        for p in pkgs:
            assert p["currency"] == "usd"
            assert "name" in p

    def test_gallery_seeded(self, api):
        r = api.get(f"{BASE_URL}/api/gallery")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 3
        cats = {it["category"] for it in items}
        # Seeded categories
        for required in ("garage", "closet", "storage"):
            assert required in cats, f"Missing seeded category {required}: {cats}"
        for it in items:
            assert it["before_url"].startswith("http")
            assert it["after_url"].startswith("http")
            assert "id" in it
        _no_underscore_id(items)


# ------------------------- Leads -------------------------
class TestLeads:
    def test_create_lead_minimal_required_fields(self, api):
        payload = {
            "name": "TEST_Jane Doe",
            "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
            "space_type": "garage",
        }
        r = api.post(f"{BASE_URL}/api/leads", json=payload)
        assert r.status_code == 200, r.text
        lead = r.json()
        assert lead["name"] == payload["name"]
        assert lead["email"] == payload["email"]
        assert lead["space_type"] == "garage"
        assert isinstance(lead["id"], str) and len(lead["id"]) > 0
        assert lead["status"] == "new"
        _no_underscore_id(lead)

    def test_create_lead_persists(self, api, admin_headers):
        email = f"test_persist_{uuid.uuid4().hex[:6]}@example.com"
        r = api.post(
            f"{BASE_URL}/api/leads",
            json={"name": "TEST_Persist", "email": email, "space_type": "closet", "package_id": "basic"},
        )
        assert r.status_code == 200
        new_id = r.json()["id"]

        # Verify via admin list
        r2 = requests.get(f"{BASE_URL}/api/admin/leads", headers=admin_headers)
        assert r2.status_code == 200
        ids = [x["id"] for x in r2.json()]
        assert new_id in ids
        _no_underscore_id(r2.json())

    def test_create_lead_invalid_package(self, api):
        r = api.post(
            f"{BASE_URL}/api/leads",
            json={
                "name": "TEST_Bad",
                "email": "bad@example.com",
                "space_type": "garage",
                "package_id": "nonexistent",
            },
        )
        assert r.status_code == 400
        assert "Invalid" in r.json().get("detail", "")

    def test_create_lead_missing_required(self, api):
        # Missing space_type
        r = api.post(f"{BASE_URL}/api/leads", json={"name": "x", "email": "x@y.com"})
        assert r.status_code == 422


# ------------------------- Admin auth -------------------------
class TestAdminAuth:
    def test_admin_login_success(self, api):
        r = api.post(f"{BASE_URL}/api/admin/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert r.json().get("token") == ADMIN_PASSWORD

    def test_admin_login_wrong(self, api):
        r = api.post(f"{BASE_URL}/api/admin/login", json={"password": "wrong"})
        assert r.status_code == 401

    def test_admin_leads_no_header_unauthorized(self):
        r = requests.get(f"{BASE_URL}/api/admin/leads")
        assert r.status_code == 401

    def test_admin_leads_with_header_ok(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/leads", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        _no_underscore_id(data)

    def test_admin_transactions_with_auth(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/transactions", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        _no_underscore_id(data)

    def test_admin_transactions_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/transactions")
        assert r.status_code == 401


# ------------------------- Admin Gallery CRUD -------------------------
class TestAdminGallery:
    created_id = None

    def test_admin_add_gallery_requires_auth(self, api):
        r = api.post(
            f"{BASE_URL}/api/admin/gallery",
            json={
                "title": "TEST_unauth",
                "category": "garage",
                "before_url": "https://x/y.jpg",
                "after_url": "https://x/z.jpg",
            },
        )
        assert r.status_code == 401

    def test_admin_add_gallery_ok(self, admin_headers):
        payload = {
            "title": "TEST_New Garage Reset",
            "category": "garage",
            "before_url": "https://example.com/before.jpg",
            "after_url": "https://example.com/after.jpg",
        }
        r = requests.post(f"{BASE_URL}/api/admin/gallery", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        item = r.json()
        assert item["title"] == payload["title"]
        assert item["category"] == "garage"
        assert isinstance(item["id"], str)
        TestAdminGallery.created_id = item["id"]
        _no_underscore_id(item)

    def test_gallery_lists_added_item(self):
        assert TestAdminGallery.created_id, "Previous test must have run"
        r = requests.get(f"{BASE_URL}/api/gallery")
        assert r.status_code == 200
        ids = [it["id"] for it in r.json()]
        assert TestAdminGallery.created_id in ids

    def test_admin_delete_gallery_requires_auth(self):
        assert TestAdminGallery.created_id
        r = requests.delete(f"{BASE_URL}/api/admin/gallery/{TestAdminGallery.created_id}")
        assert r.status_code == 401

    def test_admin_delete_gallery_ok(self, admin_headers):
        assert TestAdminGallery.created_id
        r = requests.delete(
            f"{BASE_URL}/api/admin/gallery/{TestAdminGallery.created_id}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json().get("deleted") == 1

        # Verify removal
        r2 = requests.get(f"{BASE_URL}/api/gallery")
        ids = [it["id"] for it in r2.json()]
        assert TestAdminGallery.created_id not in ids


# ------------------------- Stripe Checkout -------------------------
class TestCheckout:
    session_id = None

    def test_checkout_invalid_package(self, api):
        r = api.post(
            f"{BASE_URL}/api/checkout/session",
            json={"package_id": "ultra", "origin_url": "https://example.com"},
        )
        assert r.status_code == 400

    def test_checkout_session_creates(self, api):
        r = api.post(
            f"{BASE_URL}/api/checkout/session",
            json={
                "package_id": "standard",
                "origin_url": "https://flowspace-preview-1.preview.emergentagent.com",
                "email": "test_buyer@example.com",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and body["url"].startswith("http")
        assert "session_id" in body and body["session_id"]
        TestCheckout.session_id = body["session_id"]

    def test_transaction_record_created(self, admin_headers):
        assert TestCheckout.session_id, "checkout session must exist"
        r = requests.get(f"{BASE_URL}/api/admin/transactions", headers=admin_headers)
        assert r.status_code == 200
        txs = r.json()
        match = [t for t in txs if t.get("session_id") == TestCheckout.session_id]
        assert len(match) == 1, f"Expected 1 transaction for session, found {len(match)}"
        tx = match[0]
        assert tx["package_id"] == "standard"
        assert tx["amount"] == 149.0
        assert tx["currency"] == "usd"
        assert tx["payment_status"] == "initiated"
        _no_underscore_id(tx)

    def test_checkout_status(self, api):
        assert TestCheckout.session_id
        r = api.get(f"{BASE_URL}/api/checkout/status/{TestCheckout.session_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "payment_status" in body
        # initial state likely 'unpaid' or 'initiated'
        assert body["payment_status"] in ("unpaid", "initiated", "paid", "open")

    def test_checkout_status_unknown(self, api):
        r = api.get(f"{BASE_URL}/api/checkout/status/sess_does_not_exist_xyz")
        assert r.status_code == 404
