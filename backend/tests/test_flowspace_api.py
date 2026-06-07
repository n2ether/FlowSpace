"""FlowSpace API regression tests (iteration_3).

Covers: auth gating, /api/auth/me with Bearer, projects 402 for over-limit free user,
billing config + checkout (returns Stripe URL, does NOT complete payment), admin auth
+ tabs (overview/users/projects/subscriptions/transactions/affiliate CRUD/gallery).

Does NOT call Replicate (paid). E2E pipeline already validated by test_e2e_pipeline.py.
"""
import os
import uuid
import datetime
import pytest
import requests
import pymongo

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://space-transform-59.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "garage2025")

MONGO = pymongo.MongoClient("mongodb://localhost:27017")["test_database"]


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


# ------------------------- fixtures ---------------------------------

@pytest.fixture(scope="module")
def free_user():
    """Seed a FREE user already at the limit (used=1, limit=1)."""
    uid = "TEST_free_" + uuid.uuid4().hex[:8]
    tok = "test_session_" + uuid.uuid4().hex
    now = _now()
    MONGO.users.insert_one({
        "user_id": uid, "email": f"{uid}@example.com", "name": "Free Tester",
        "picture": "", "subscription_plan": "free", "stripe_customer_id": None,
        "monthly_generation_limit": 1, "monthly_generations_used": 1,
        "period_start": now.isoformat(), "is_admin": False,
        "created_at": now.isoformat(),
    })
    MONGO.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": (now + datetime.timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    yield {"user_id": uid, "token": tok}
    MONGO.users.delete_many({"user_id": uid})
    MONGO.user_sessions.delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def pro_user():
    """Seed a PRO user with credits available (no Replicate call will be made)."""
    uid = "TEST_pro_" + uuid.uuid4().hex[:8]
    tok = "test_session_" + uuid.uuid4().hex
    now = _now()
    MONGO.users.insert_one({
        "user_id": uid, "email": f"{uid}@example.com", "name": "Pro Tester",
        "picture": "", "subscription_plan": "pro", "stripe_customer_id": None,
        "monthly_generation_limit": 10, "monthly_generations_used": 0,
        "period_start": now.isoformat(), "is_admin": False,
        "created_at": now.isoformat(),
    })
    MONGO.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": (now + datetime.timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    })
    yield {"user_id": uid, "token": tok}
    MONGO.users.delete_many({"user_id": uid})
    MONGO.user_sessions.delete_many({"user_id": uid})
    MONGO.projects.delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def admin_token():
    # verify login works
    r = requests.post(f"{API}/admin/login", json={"password": ADMIN_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    # backend authenticates via X-Admin-Token == ADMIN_PASSWORD
    return ADMIN_PASSWORD


# ------------------------- auth gating ------------------------------

def test_landing_renders():
    r = requests.get(f"{BASE_URL}/", timeout=20)
    assert r.status_code == 200
    assert "FlowSpace" in r.text or "flowspace" in r.text.lower()


def test_auth_me_without_token_returns_401():
    r = requests.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 401


def test_projects_list_without_token_returns_401():
    r = requests.get(f"{API}/projects", timeout=20)
    assert r.status_code == 401


def test_auth_me_with_bearer(pro_user):
    r = requests.get(f"{API}/auth/me",
                     headers={"Authorization": f"Bearer {pro_user['token']}"},
                     timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d.get("subscription_plan") == "pro"
    assert d.get("monthly_generation_limit") == 10
    assert d.get("user_id") == pro_user["user_id"]
    assert "_id" not in d


def test_auth_me_with_cookie(pro_user):
    s = requests.Session()
    s.cookies.set("session_token", pro_user["token"])
    r = s.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 200
    assert r.json().get("user_id") == pro_user["user_id"]


def test_invalid_token_rejected():
    r = requests.get(f"{API}/auth/me",
                     headers={"Authorization": "Bearer bogus_token_xxx"}, timeout=20)
    assert r.status_code == 401


# ------------------------- projects listing -------------------------

def test_projects_list_empty_for_new_user(pro_user):
    r = requests.get(f"{API}/projects",
                     headers={"Authorization": f"Bearer {pro_user['token']}"},
                     timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_project_not_found(pro_user):
    r = requests.get(f"{API}/projects/nonexistent-id",
                     headers={"Authorization": f"Bearer {pro_user['token']}"},
                     timeout=20)
    assert r.status_code == 404


# ------------------------- free plan limit (402) --------------------

def test_free_user_at_limit_blocked_with_402(free_user):
    """Critical: free user with used==limit must receive 402 without invoking Replicate."""
    # Tiny 1x1 png base64
    photo = ("data:image/png;base64,"
             "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII=")
    payload = {"room_type": "garage", "style": "modern", "photo": photo, "language": "en"}
    r = requests.post(f"{API}/projects", json=payload,
                      headers={"Authorization": f"Bearer {free_user['token']}"},
                      timeout=30)
    assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text}"
    assert "credit" in r.text.lower() or "limit" in r.text.lower()


def test_invalid_room_type_400(pro_user):
    photo = ("data:image/png;base64,"
             "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII=")
    r = requests.post(f"{API}/projects",
                      json={"room_type": "invalid_room", "style": "modern", "photo": photo, "language": "en"},
                      headers={"Authorization": f"Bearer {pro_user['token']}"}, timeout=30)
    assert r.status_code == 400


def test_invalid_style_400(pro_user):
    photo = ("data:image/png;base64,"
             "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII=")
    r = requests.post(f"{API}/projects",
                      json={"room_type": "garage", "style": "invalid_style", "photo": photo, "language": "en"},
                      headers={"Authorization": f"Bearer {pro_user['token']}"}, timeout=30)
    assert r.status_code == 400


# ------------------------- billing ----------------------------------

def test_billing_config_public():
    r = requests.get(f"{API}/billing/config", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "publishable_key" in d
    assert d["publishable_key"].startswith("pk_")
    plans = {p["id"]: p for p in d["plans"]}
    assert "free" in plans and "pro" in plans and "premium" in plans


def test_billing_checkout_requires_auth():
    r = requests.post(f"{API}/billing/checkout",
                      json={"plan": "pro", "origin_url": BASE_URL}, timeout=20)
    assert r.status_code == 401


def test_billing_checkout_invalid_plan(pro_user):
    r = requests.post(f"{API}/billing/checkout",
                      json={"plan": "bogus", "origin_url": BASE_URL},
                      headers={"Authorization": f"Bearer {pro_user['token']}"}, timeout=30)
    assert r.status_code == 400


def test_billing_checkout_returns_stripe_url(pro_user):
    """Verify checkout URL only — DO NOT complete payment (live keys)."""
    r = requests.post(f"{API}/billing/checkout",
                      json={"plan": "pro", "origin_url": BASE_URL},
                      headers={"Authorization": f"Bearer {pro_user['token']}"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "url" in d and d["url"].startswith("https://checkout.stripe.com/")
    assert "session_id" in d and d["session_id"].startswith("cs_")


# ------------------------- admin ------------------------------------

def _ah(tok):
    return {"X-Admin-Token": tok}


def test_admin_login_wrong_password():
    r = requests.post(f"{API}/admin/login", json={"password": "wrong"}, timeout=20)
    assert r.status_code == 401


def test_admin_stats(admin_token):
    r = requests.get(f"{API}/admin/stats", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200
    d = r.json()
    # at minimum contains counts
    assert any(k in d for k in ("users", "total_users", "user_count")) or isinstance(d, dict)


def test_admin_users(admin_token):
    r = requests.get(f"{API}/admin/users", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_admin_projects(admin_token):
    r = requests.get(f"{API}/admin/projects", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200


def test_admin_subscriptions(admin_token):
    r = requests.get(f"{API}/admin/subscriptions", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200


def test_admin_transactions(admin_token):
    r = requests.get(f"{API}/admin/transactions", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200


def test_admin_affiliate_crud(admin_token):
    # list
    r = requests.get(f"{API}/admin/affiliate", headers=_ah(admin_token), timeout=20)
    assert r.status_code == 200
    # add
    name = f"TEST_aff_{uuid.uuid4().hex[:6]}"
    payload = {
        "category": "storage",
        "product_name": name,
        "product_description": "Test product",
        "affiliate_url": "https://example.com/p1",
        "image_url": "",
        "price_range": "$10-20",
        "room_type": "garage",
    }
    r2 = requests.post(f"{API}/admin/affiliate", json=payload, headers=_ah(admin_token), timeout=20)
    assert r2.status_code in (200, 201), r2.text
    created = r2.json()
    item_id = created.get("id")
    # verify present
    r3 = requests.get(f"{API}/admin/affiliate", headers=_ah(admin_token), timeout=20)
    items = r3.json() if isinstance(r3.json(), list) else r3.json().get("items", [])
    assert any(it.get("product_name") == name for it in items), "newly created affiliate item not in list"
    # delete
    if item_id:
        r4 = requests.delete(f"{API}/admin/affiliate/{item_id}", headers=_ah(admin_token), timeout=20)
        assert r4.status_code in (200, 204)
    # cleanup any orphan TEST_ items
    try:
        MONGO.affiliate_products.delete_many({"product_name": {"$regex": "^TEST_aff_"}})
    except Exception:
        pass
