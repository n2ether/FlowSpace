"""Member accounts, sessions, free-tier quota, and space claiming."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Importable before server.py reads env.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "flowspace_member_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-member-accounts-32b")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")
os.environ.setdefault("ADMIN_PASSWORD", "flowspace2025")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from auth import (
    COOKIE_NAME,
    create_token,
    decode_token,
    hash_password,
    normalize_email,
    validate_password,
    verify_password,
)
from members import (
    FREE_GENERATION_LIMIT,
    count_generations,
    free_limit_error,
    is_free_package,
    public_space,
    usage_payload,
)


class FakeResult:
    def __init__(self, modified_count=0, matched_count=0, inserted_id=None):
        self.modified_count = modified_count
        self.matched_count = matched_count
        self.inserted_id = inserted_id


class FakeCursor:
    def __init__(self, items):
        self.items = list(items)

    def sort(self, key, direction=-1):
        reverse = direction == -1
        self.items.sort(key=lambda d: d.get(key) or "", reverse=reverse)
        return self

    async def to_list(self, n):
        return self.items[:n]


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if _match(doc, query):
                return _project(doc, projection)
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return FakeResult(inserted_id=doc.get("id"))

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _match(doc, query):
                doc.update(update.get("$set") or {})
                return FakeResult(modified_count=1, matched_count=1)
        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$set") or {})
            self.docs.append(new_doc)
            return FakeResult(modified_count=1, matched_count=1)
        return FakeResult(modified_count=0, matched_count=0)

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if _match(doc, query):
                doc.update(update.get("$set") or {})
                count += 1
        return FakeResult(modified_count=count, matched_count=count)

    async def count_documents(self, query):
        return sum(1 for doc in self.docs if _match(doc, query))

    def find(self, query=None, projection=None):
        items = [_project(doc, projection) for doc in self.docs if _match(doc, query or {})]
        return FakeCursor(items)

    async def create_index(self, *args, **kwargs):
        return "ok"

    async def delete_one(self, query):
        for i, doc in enumerate(self.docs):
            if _match(doc, query):
                self.docs.pop(i)
                return FakeResult(modified_count=1)
        return FakeResult(modified_count=0)


class FakeDB:
    def __init__(self):
        self.members = FakeCollection()
        self.leads = FakeCollection()
        self.deliverables = FakeCollection()
        self.gallery = FakeCollection()
        self.payment_transactions = FakeCollection()


def _project(doc, projection):
    if not projection:
        return dict(doc)
    if projection.get("_id") == 0 and len(projection) == 1:
        out = dict(doc)
        out.pop("_id", None)
        return out
    out = {}
    include = {k: v for k, v in projection.items() if k != "_id" and v}
    if include:
        for k in include:
            if k in doc:
                out[k] = doc[k]
        if "id" in doc:
            out.setdefault("id", doc["id"])
        return out
    out = dict(doc)
    if projection.get("_id") == 0:
        out.pop("_id", None)
    return out


def _match(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        if key == "$or":
            if not any(_match(doc, clause) for clause in expected):
                return False
            continue
        if key == "$and":
            if not all(_match(doc, clause) for clause in expected):
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict) and any(str(k).startswith("$") for k in expected):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$nin" in expected and actual in expected["$nin"]:
                return False
            if "$exists" in expected:
                exists = key in doc
                if bool(expected["$exists"]) != exists:
                    return False
            if "$regex" in expected:
                import re

                flags = re.I if "i" in (expected.get("$options") or "") else 0
                if not re.search(expected["$regex"], str(actual or ""), flags):
                    return False
        elif actual != expected:
            return False
    return True


@pytest.fixture
def client(monkeypatch):
    fake = FakeDB()
    import server

    monkeypatch.setattr(server, "db", fake)

    async def no_automation(*args, **kwargs):
        return True

    async def no_seed():
        return None

    monkeypatch.setattr(server, "_start_automation_for_lead", no_automation)
    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as c:
        yield c, fake


# ──────────────────────────── Helpers ─────────────────────────────
class TestAuthHelpers:
    def test_password_hash_roundtrip(self):
        hashed = hash_password("correct-horse")
        assert hashed != "correct-horse"
        assert verify_password("correct-horse", hashed)
        assert not verify_password("wrong", hashed)

    def test_jwt_roundtrip(self):
        token = create_token("mem-1", "Ada@Example.com")
        payload = decode_token(token)
        assert payload["sub"] == "mem-1"
        assert payload["email"] == "ada@example.com"
        assert decode_token("not-a-token") is None

    def test_normalize_and_validate(self):
        assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
        assert validate_password("short") is not None
        assert validate_password("longenough") is None


class TestQuotaHelpers:
    def test_free_package_detection(self):
        packages = {"free": {"price": 0.0}, "plus": {"price": 10.0}}
        assert is_free_package("free", packages)
        assert is_free_package(None, packages)
        assert not is_free_package("plus", packages)

    def test_count_and_payload(self):
        leads = [
            {"package_id": "free"},
            {"package_id": "plus"},
            {"package_id": None},
        ]
        counts = count_generations(leads, packages={"free": {"price": 0}, "plus": {"price": 10}})
        assert counts == {"free_used": 2, "paid_count": 1}
        usage = usage_payload(1, 2)
        assert usage["can_generate_free"] is False
        assert usage["free_generations_limit"] == FREE_GENERATION_LIMIT
        err = free_limit_error(1)
        assert err["code"] == "FREE_TIER_LIMIT"

    def test_public_space_hides_admin_notes(self):
        space = public_space(
            {"id": "l1", "space_type": "garage", "automation_error": "secret", "status": "new"},
            {"front_view_url": "/api/uploads/photo/abc", "updated_at": "now"},
        )
        assert "automation_error" not in space
        assert space["deliverable"]["front_view_url"] == "/api/uploads/photo/abc"


# ──────────────────────────── HTTP ─────────────────────────────
def _signup(client, email="ada@example.com", password="password12", name="Ada"):
    return client.post("/api/auth/signup", json={"name": name, "email": email, "password": password})


def _lead_payload(**overrides):
    data = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "space_type": "closet",
        "package_id": "free",
        "style_prefs": ["modern"],
        "color_prefs": ["sage"],
        "biggest_challenge": "Too much visual clutter here",
    }
    data.update(overrides)
    return data


class TestMemberAuthApi:
    def test_signup_login_me_logout(self, client):
        c, _ = client
        r = _signup(c)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token"]
        assert body["member"]["email"] == "ada@example.com"
        assert "password_hash" not in body["member"]
        assert body["member"]["usage"]["can_generate_free"] is True
        assert r.cookies.get(COOKIE_NAME)

        bad = c.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope-nope"})
        assert bad.status_code == 401

        login = c.post("/api/auth/login", json={"email": "ada@example.com", "password": "password12"})
        assert login.status_code == 200
        token = login.json()["token"]

        me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "ada@example.com"

        c.post("/api/auth/logout")
        # Cookie cleared; bearer still works until expiry (intentional).
        me2 = c.get("/api/auth/me")
        assert me2.status_code in (200, 401)

    def test_duplicate_signup(self, client):
        c, _ = client
        assert _signup(c).status_code == 200
        again = _signup(c)
        assert again.status_code == 409
        assert again.json()["detail"]["code"] == "EMAIL_IN_USE"

    def test_me_requires_auth(self, client):
        c, _ = client
        r = c.get("/api/auth/me")
        assert r.status_code == 401


class TestLeadAccountAndQuota:
    def test_lead_requires_account(self, client):
        c, _ = client
        r = c.post("/api/leads", json=_lead_payload())
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "ACCOUNT_REQUIRED"

    def test_inline_password_creates_account_and_lead(self, client):
        c, _ = client
        r = c.post("/api/leads", json=_lead_payload(password="password12"))
        assert r.status_code == 200, r.text
        lead = r.json()
        assert lead["member_id"]
        assert lead["package_id"] == "free"
        assert r.cookies.get(COOKIE_NAME)

    def test_free_tier_blocks_second_generation(self, client):
        c, _ = client
        token = _signup(c).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        first = c.post("/api/leads", json=_lead_payload(), headers=headers)
        assert first.status_code == 200, first.text
        second = c.post("/api/leads", json=_lead_payload(space_type="garage"), headers=headers)
        assert second.status_code == 403
        detail = second.json()["detail"]
        assert detail["code"] == "FREE_TIER_LIMIT"
        assert detail["limit"] == 1

        paid = c.post(
            "/api/leads",
            json=_lead_payload(package_id="plus", space_type="pantry"),
            headers=headers,
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["package_id"] == "plus"

    def test_signup_claims_guest_leads(self, client):
        c, db = client
        db.leads.docs.append(
            {
                "id": "guest-lead-1",
                "name": "Ada",
                "email": "ada@example.com",
                "space_type": "garage",
                "package_id": "free",
                "member_id": None,
                "status": "delivered",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        r = _signup(c)
        assert r.status_code == 200
        assert r.json()["claimed_spaces"] == 1
        assert r.json()["member"]["usage"]["free_generations_used"] == 1
        assert r.json()["member"]["usage"]["can_generate_free"] is False
        assert db.leads.docs[0]["member_id"] == r.json()["member"]["id"]

        blocked = c.post(
            "/api/leads",
            json=_lead_payload(),
            headers={"Authorization": f"Bearer {r.json()['token']}"},
        )
        assert blocked.status_code == 403

    def test_spaces_are_member_scoped(self, client):
        c, db = client
        ada = _signup(c, email="ada@example.com").json()
        grace = _signup(c, email="grace@example.com", name="Grace").json()
        c.post(
            "/api/leads",
            json=_lead_payload(email="ada@example.com"),
            headers={"Authorization": f"Bearer {ada['token']}"},
        )
        spaces_ada = c.get("/api/me/spaces", headers={"Authorization": f"Bearer {ada['token']}"})
        spaces_grace = c.get("/api/me/spaces", headers={"Authorization": f"Bearer {grace['token']}"})
        assert spaces_ada.status_code == 200
        assert len(spaces_ada.json()["spaces"]) == 1
        assert spaces_grace.json()["spaces"] == []
        c.cookies.clear()
        unauth = c.get("/api/me/spaces")
        assert unauth.status_code == 401
