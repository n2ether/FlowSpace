"""Backend tests for FlowSpace Branded PDF Deliverable feature."""
import io
import os
import pytest
import requests
from pypdf import PdfReader

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
# Fallback: read frontend/.env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_HEADERS = {"X-Admin-Token": "garage2025"}


# ------------------------- Fixtures -------------------------
@pytest.fixture(scope="module")
def lead_with_photo():
    r = requests.get(f"{BASE_URL}/api/admin/leads", headers=ADMIN_HEADERS, timeout=20)
    assert r.status_code == 200
    leads = r.json()
    for l in leads:
        if l.get("photos"):
            return l
    pytest.skip("No lead with photo found")


@pytest.fixture(scope="module")
def fresh_lead():
    # Create a new clean lead so we can test creating/updating deliverable
    r = requests.post(
        f"{BASE_URL}/api/leads",
        json={
            "name": "TEST_DeliverableUser",
            "email": "TEST_deliv@example.com",
            "space_type": "garage",
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------- Auth tests -------------------------
class TestDeliverableAuth:
    def test_get_requires_auth(self, lead_with_photo):
        r = requests.get(f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable", timeout=15)
        assert r.status_code == 401

    def test_put_requires_auth(self, lead_with_photo):
        r = requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable",
            json={"lead_id": lead_with_photo["id"]},
            timeout=15,
        )
        assert r.status_code == 401

    def test_pdf_requires_auth(self, lead_with_photo):
        r = requests.get(f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable/pdf", timeout=15)
        assert r.status_code == 401


# ------------------------- GET deliverable -------------------------
class TestGetDeliverable:
    def test_get_existing_lead_no_deliverable(self, fresh_lead):
        r = requests.get(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "lead" in data and data["lead"]["id"] == fresh_lead["id"]
        assert "deliverable" in data
        assert data["deliverable"] is None

    def test_get_nonexistent_lead_returns_404(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/leads/does-not-exist-1234/deliverable",
            headers=ADMIN_HEADERS, timeout=15,
        )
        assert r.status_code == 404


# ------------------------- PUT deliverable (upsert/idempotency) -------------------------
FULL_PAYLOAD = {
    "lead_id": "",
    "intro": "Welcome to your design plan.",
    "needs": ["More storage", "Better lighting"],
    "zones": [{"title": "Workshop", "desc": "tools + bench"}, {"title": "Storage", "desc": "shelves"}],
    "wall_color_name": "Sea Salt",
    "wall_color_code": "SW 6204",
    "wall_color_hex": "#cfd7d3",
    "wall_color_note": "Calm neutral that brightens the room.",
    "shopping_list": [
        {"name": "Pegboard", "qty": 2, "price": 49.50},
        {"name": "Bins", "qty": 6, "price": 12.00},
    ],
    "budget_note": "Approx range; varies by retailer.",
    "strategy": ["Lead with neutrals", "Add warm wood accents"],
    "action_plan": ["Paint walls", "Install pegboard", "Sort bins"],
    "benefits": ["Easier to clean", "Visual calm"],
    "notes": "Measurements approximate.",
    "summary": "A calmer, more functional space.",
    "attachment_note": "Quick video walkthrough included.",
    "shopping_links": [
        {"name": "Pegboard", "url": "https://example.com/pegboard"},
        {"name": "Bins", "url": "https://example.com/bins"},
    ],
    "front_view_url": "",
    "floor_plan_url": "",
    "view_1_url": "",
    "view_2_url": "",
    "view_3_url": "",
    "include_customer_photos": True,
}


class TestPutDeliverableIdempotent:
    def test_put_creates_then_updates_idempotent(self, fresh_lead):
        payload = {**FULL_PAYLOAD, "lead_id": fresh_lead["id"]}
        # First PUT
        r1 = requests.put(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload, timeout=20,
        )
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["intro"] == "Welcome to your design plan."
        assert len(d1["zones"]) == 2
        assert len(d1["shopping_list"]) == 2

        # GET verifies persistence
        rget = requests.get(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, timeout=15,
        )
        assert rget.status_code == 200
        assert rget.json()["deliverable"]["intro"] == "Welcome to your design plan."

        # Second PUT with changes - should update, not duplicate
        payload2 = {**payload, "intro": "Updated intro."}
        r2 = requests.put(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload2, timeout=20,
        )
        assert r2.status_code == 200
        assert r2.json()["intro"] == "Updated intro."

        # GET again - confirm only updated (no dup)
        rget2 = requests.get(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, timeout=15,
        )
        assert rget2.status_code == 200
        assert rget2.json()["deliverable"]["intro"] == "Updated intro."

    def test_put_nonexistent_lead_404(self):
        r = requests.put(
            f"{BASE_URL}/api/admin/leads/does-not-exist-xyz/deliverable",
            headers=ADMIN_HEADERS, json={**FULL_PAYLOAD, "lead_id": "does-not-exist-xyz"},
            timeout=15,
        )
        assert r.status_code == 404


# ------------------------- PDF generation -------------------------
def _read_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts), len(reader.pages)


class TestPdfGeneration:
    def test_pdf_with_customer_photo(self, lead_with_photo):
        # Save a deliverable with include_customer_photos=True and no rendering URLs
        payload = {**FULL_PAYLOAD, "lead_id": lead_with_photo["id"], "include_customer_photos": True}
        requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload, timeout=20,
        )

        r = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable/pdf",
            headers=ADMIN_HEADERS, timeout=30,
        )
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")
        assert r.content[:5] == b"%PDF-"

        text, page_count = _read_pdf_text(r.content)
        assert "FlowSpace" in text
        assert lead_with_photo["name"] in text
        space_cap = lead_with_photo["space_type"].capitalize()
        assert f"{space_cap} Design Plan" in text
        assert "Total" in text  # shopping list total appears
        assert "Reference Photo" in text  # since lead has photos and include=True
        assert "Design Summary" in text
        assert "Shopping Links" in text
        assert "The FlowSpace Design Team" in text
        assert page_count >= 3

    def test_pdf_without_customer_photos(self, lead_with_photo):
        payload = {**FULL_PAYLOAD, "lead_id": lead_with_photo["id"], "include_customer_photos": False}
        requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload, timeout=20,
        )
        r = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable/pdf",
            headers=ADMIN_HEADERS, timeout=30,
        )
        assert r.status_code == 200
        text, _ = _read_pdf_text(r.content)
        assert "Reference Photo" not in text

    def test_pdf_with_relative_gridfs_url(self, lead_with_photo):
        # Use the customer's own photo URL as a rendering URL — should be resolved via GridFS
        photo_url = lead_with_photo["photos"][0]
        # First: no images version
        payload_no_img = {**FULL_PAYLOAD, "lead_id": lead_with_photo["id"], "include_customer_photos": False}
        requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload_no_img, timeout=20,
        )
        r1 = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable/pdf",
            headers=ADMIN_HEADERS, timeout=30,
        )
        size_no_img = len(r1.content)

        # Now with a relative GridFS url in front_view
        payload_img = {**payload_no_img, "front_view_url": photo_url}
        requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload_img, timeout=20,
        )
        r2 = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_with_photo['id']}/deliverable/pdf",
            headers=ADMIN_HEADERS, timeout=30,
        )
        assert r2.status_code == 200
        size_with_img = len(r2.content)
        # PDF should be substantially larger when image is embedded
        # Even a small embedded image should add bytes vs placeholder
        assert size_with_img > size_no_img + 500, (size_with_img, size_no_img)

    def test_pdf_with_invalid_image_url_graceful(self, fresh_lead):
        payload = {
            **FULL_PAYLOAD,
            "lead_id": fresh_lead["id"],
            "front_view_url": "https://invalid.example.invalid/missing.jpg",
            "floor_plan_url": "/api/uploads/photo/000000000000000000000000",  # valid format but nonexistent
            "include_customer_photos": False,
        }
        requests.put(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable",
            headers=ADMIN_HEADERS, json=payload, timeout=20,
        )
        r = requests.get(
            f"{BASE_URL}/api/admin/leads/{fresh_lead['id']}/deliverable/pdf",
            headers=ADMIN_HEADERS, timeout=30,
        )
        assert r.status_code == 200
        text, _ = _read_pdf_text(r.content)
        # Placeholder should appear gracefully
        assert ("Image not provided" in text) or ("Image unavailable" in text)
