"""Tests for FlowSpace questionnaire leads + GridFS uploads."""
import io
import os
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://flowspace-preview-1.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "garage2025"


def _img_bytes(size=(40, 40), color=(120, 200, 150)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    return s


class TestPhotoUpload:
    def test_upload_valid_image(self, session):
        files = {"file": ("test.jpg", _img_bytes(), "image/jpeg")}
        r = session.post(f"{BASE_URL}/api/uploads/photo", files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data and "url" in data
        assert data["url"].startswith("/api/uploads/photo/")
        # Stream back
        r2 = session.get(f"{BASE_URL}{data['url']}", timeout=30)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/")
        assert len(r2.content) > 100
        # store id for next test
        pytest.uploaded_photo = data

    def test_reject_non_image(self, session):
        files = {"file": ("hack.txt", b"hello world", "text/plain")}
        r = session.post(f"{BASE_URL}/api/uploads/photo", files=files, timeout=30)
        assert r.status_code == 400

    def test_reject_too_large(self, session):
        big = b"\xff" * (11 * 1024 * 1024)
        files = {"file": ("huge.jpg", big, "image/jpeg")}
        r = session.post(f"{BASE_URL}/api/uploads/photo", files=files, timeout=60)
        assert r.status_code == 413

    def test_get_invalid_id(self, session):
        r = session.get(f"{BASE_URL}/api/uploads/photo/notanid", timeout=15)
        assert r.status_code == 400
        # valid format but non-existent ObjectId
        r2 = session.get(f"{BASE_URL}/api/uploads/photo/507f1f77bcf86cd799439011", timeout=15)
        assert r2.status_code == 404


class TestLeadsQuestionnaire:
    def test_create_lead_with_all_questionnaire_fields(self, session):
        # upload photo first
        files = {"file": ("lead.jpg", _img_bytes(color=(50, 100, 200)), "image/jpeg")}
        up = session.post(f"{BASE_URL}/api/uploads/photo", files=files, timeout=30).json()
        photo_url = up["url"]

        payload = {
            "name": "TEST_QuestionnaireUser",
            "email": "test_questionnaire@example.com",
            "phone": "555-9999",
            "space_type": "garage",
            "package_id": "standard",
            "photos": [photo_url],
            "bothers_about": ["clutter", "no_storage", "stressful"],
            "bothers_other": "Squeaky door",
            "desired_feeling": ["calm", "minimal", "airy"],
            "feeling_other": "Spa-like",
            "must_stay": "Workbench, tool chest, bikes",
            "storage_needs": ["shelves", "bins"],
            "style_prefs": ["modern", "scandi"],
            "color_prefs": ["white", "wood"],
            "budget": "1000_3000",
            "diy_level": "some",
            "daily_improvement": "Walk in and immediately find any tool",
            "language": "en",
        }
        r = session.post(f"{BASE_URL}/api/leads", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["bothers_about"] == payload["bothers_about"]
        assert data["desired_feeling"] == payload["desired_feeling"]
        assert data["storage_needs"] == payload["storage_needs"]
        assert data["style_prefs"] == payload["style_prefs"]
        assert data["color_prefs"] == payload["color_prefs"]
        assert data["budget"] == "1000_3000"
        assert data["diy_level"] == "some"
        assert data["daily_improvement"] == payload["daily_improvement"]
        assert data["must_stay"] == payload["must_stay"]
        assert data["photos"] == [photo_url]
        assert "id" in data
        pytest.created_lead_id = data["id"]

    def test_admin_leads_returns_new_fields(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/leads",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            timeout=30,
        )
        assert r.status_code == 200
        leads = r.json()
        assert isinstance(leads, list) and len(leads) > 0
        match = next((l for l in leads if l.get("id") == getattr(pytest, "created_lead_id", None)), None)
        assert match is not None, "Recently created lead not found in admin list"
        # Verify all questionnaire fields preserved
        assert match["bothers_about"] == ["clutter", "no_storage", "stressful"]
        assert match["desired_feeling"] == ["calm", "minimal", "airy"]
        assert match["storage_needs"] == ["shelves", "bins"]
        assert match["style_prefs"] == ["modern", "scandi"]
        assert match["color_prefs"] == ["white", "wood"]
        assert match["budget"] == "1000_3000"
        assert match["diy_level"] == "some"
        assert match["bothers_other"] == "Squeaky door"
        assert match["feeling_other"] == "Spa-like"
        assert match["must_stay"] == "Workbench, tool chest, bikes"
        assert match["daily_improvement"] == "Walk in and immediately find any tool"
        assert len(match["photos"]) == 1
        assert match["photos"][0].startswith("/api/uploads/photo/")

    def test_admin_leads_requires_auth(self, session):
        r = session.get(f"{BASE_URL}/api/admin/leads", timeout=15)
        assert r.status_code == 401
        r2 = session.get(
            f"{BASE_URL}/api/admin/leads",
            headers={"X-Admin-Token": "wrong"},
            timeout=15,
        )
        assert r2.status_code == 401
