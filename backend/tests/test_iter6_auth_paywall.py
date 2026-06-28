"""Iter 6 — Auth + Paywall + Stripe-after-data backend tests.

Covers:
- GET /api/auth/me (401 unauth, 200 with bearer)
- GET /api/submissions (401 unauth, items list when authed)
- Free plan cap (2 free max → 402 on 3rd)
- Paid plan creates awaiting_payment + Stripe checkout url
- /submissions/{id}/confirm-payment: auth required, 404 unknown id, 403 not your sub,
  402 if Stripe says unpaid
- Ownership rules on GET /submissions/{id}
"""
import os
import base64
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Pre-existing user from /app/memory/test_credentials.md (2 free slots already used)
EXISTING_USER_ID = "user_d742bd346f6c"
EXISTING_TOKEN = "test_session_5837f1f2dc434ec78b25e7a0a5adef67"


# 1x1 PNG (red dot) base64
PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YA"
    "AAAASUVORK5CYII="
)


# ----------------- Fixtures -----------------
@pytest.fixture(scope="session")
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="session")
def fresh_user(mongo):
    """Create a brand-new user with 0 free slots used."""
    uid = f"test-user-iter6-{secrets.token_hex(4)}"
    token = f"test_session_iter6_{secrets.token_hex(8)}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"test.user.iter6.{secrets.token_hex(4)}@example.com",
        "name": "Iter6 Test User",
        "picture": "https://via.placeholder.com/150",
        "created_at": datetime.now(timezone.utc),
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": uid, "token": token}
    # Cleanup
    mongo.users.delete_one({"user_id": uid})
    mongo.user_sessions.delete_many({"user_id": uid})
    mongo.submissions.delete_many({"user_id": uid})
    mongo.payment_transactions.delete_many({"user_id": uid})


@pytest.fixture(scope="session")
def other_user(mongo):
    """Second user for ownership tests."""
    uid = f"test-user-other-{secrets.token_hex(4)}"
    token = f"test_session_other_{secrets.token_hex(8)}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"test.user.other.{secrets.token_hex(4)}@example.com",
        "name": "Other User",
        "picture": "https://via.placeholder.com/150",
        "created_at": datetime.now(timezone.utc),
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": uid, "token": token}
    mongo.users.delete_one({"user_id": uid})
    mongo.user_sessions.delete_many({"user_id": uid})
    mongo.submissions.delete_many({"user_id": uid})


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ----------------- Auth /me -----------------
class TestAuthMe:
    def test_me_unauth_returns_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401, r.text

    def test_me_with_bearer_returns_user(self, fresh_user):
        r = requests.get(f"{API}/auth/me", headers=_h(fresh_user["token"]))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user_id"] == fresh_user["user_id"]
        assert "email" in data
        assert data["free_cap"] == 2
        assert data["free_used"] == 0
        assert data["free_remaining"] == 2

    def test_me_existing_user_cap_consumed(self):
        r = requests.get(f"{API}/auth/me", headers=_h(EXISTING_TOKEN))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user_id"] == EXISTING_USER_ID
        assert d["free_cap"] == 2
        assert d["free_used"] >= 2
        assert d["free_remaining"] == 0


# ----------------- /submissions list -----------------
class TestSubmissionsList:
    def test_list_unauth_401(self):
        r = requests.get(f"{API}/submissions")
        assert r.status_code == 401

    def test_list_authed_returns_items(self):
        r = requests.get(f"{API}/submissions", headers=_h(EXISTING_TOKEN))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)
        if body["items"]:
            first = body["items"][0]
            for k in ["id", "plan_id", "status", "room_type",
                      "photos_total", "photos_done", "created_at"]:
                assert k in first, f"missing {k}"
            # no photo binaries
            assert "results" not in first
            assert "pdf_base64" not in first


# ----------------- Free plan cap -----------------
class TestFreeCap:
    def test_third_free_returns_402_for_capped_user(self):
        body = {
            "name": "Capped Tester",
            "email": "capped@test.example",
            "plan_id": "free",
            "room_type": "bedroom",
            "notes": "",
            "budget": None,
            "photos_base64": [PNG_1X1],
        }
        r = requests.post(f"{API}/submissions", json=body, headers=_h(EXISTING_TOKEN))
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", "")
        assert detail.startswith("You've used your 2 free projects"), detail

    def test_unauth_submission_returns_401(self):
        body = {
            "name": "x", "email": "x@x.com", "plan_id": "free",
            "room_type": "bedroom", "photos_base64": [PNG_1X1],
        }
        r = requests.post(f"{API}/submissions", json=body)
        assert r.status_code == 401


# ----------------- Plus checkout-first flow -----------------
class TestPlusCheckoutFirst:
    def test_post_plus_returns_awaiting_payment_and_checkout_url(self, fresh_user, mongo):
        body = {
            "name": "Plus Tester",
            "email": "plus@test.example",
            "plan_id": "plus",
            "room_type": "bedroom",
            "notes": "test",
            "budget": "$100 – $300",
            "photos_base64": [PNG_1X1],
        }
        r = requests.post(f"{API}/submissions", json=body, headers=_h(fresh_user["token"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "awaiting_payment"
        assert d["photos_done"] == 0
        assert d["checkout_url"] and d["checkout_url"].startswith("https://checkout.stripe.com/"), d["checkout_url"]
        assert d["checkout_session_id"]
        sub_id = d["id"]

        # payment_transactions row exists
        pt = mongo.payment_transactions.find_one({"submission_id": sub_id})
        assert pt is not None
        assert pt["user_id"] == fresh_user["user_id"]
        assert pt["session_id"] == d["checkout_session_id"]
        assert pt["payment_status"] == "pending"

        # submission has session_id pinned and is owned by user
        sub = mongo.submissions.find_one({"id": sub_id})
        assert sub["user_id"] == fresh_user["user_id"]
        assert sub["status"] == "awaiting_payment"
        assert sub["session_id"] == d["checkout_session_id"]
        assert sub["photos_done"] == 0

        # Free count for fresh_user must still be 0 (plus shouldn't consume free quota)
        time.sleep(0.5)
        me = requests.get(f"{API}/auth/me", headers=_h(fresh_user["token"])).json()
        assert me["free_used"] == 0

        # store on fresh_user dict for downstream test
        fresh_user["plus_sub_id"] = sub_id


# ----------------- /confirm-payment -----------------
class TestConfirmPayment:
    def test_confirm_unauth_401(self):
        r = requests.post(f"{API}/submissions/anything/confirm-payment")
        assert r.status_code == 401

    def test_confirm_unknown_id_404(self, fresh_user):
        r = requests.post(
            f"{API}/submissions/does-not-exist-xyz/confirm-payment",
            headers=_h(fresh_user["token"]),
        )
        assert r.status_code == 404, r.text

    def test_confirm_someone_elses_returns_403(self, fresh_user, other_user):
        # use the plus submission created earlier (owned by fresh_user)
        sub_id = fresh_user.get("plus_sub_id")
        assert sub_id, "expected plus_sub_id from earlier test"
        r = requests.post(
            f"{API}/submissions/{sub_id}/confirm-payment",
            headers=_h(other_user["token"]),
        )
        assert r.status_code == 403, r.text

    def test_confirm_owner_unpaid_returns_402(self, fresh_user):
        sub_id = fresh_user.get("plus_sub_id")
        assert sub_id
        r = requests.post(
            f"{API}/submissions/{sub_id}/confirm-payment",
            headers=_h(fresh_user["token"]),
        )
        # Stripe will say not paid → 402
        assert r.status_code == 402, r.text


# ----------------- Ownership on GET /submissions/{id} -----------------
class TestOwnership:
    def test_get_unauth_public_ok(self, fresh_user):
        # The Plus sub UUID is unguessable; unauthenticated GET should return 200
        sub_id = fresh_user.get("plus_sub_id")
        assert sub_id
        r = requests.get(f"{API}/submissions/{sub_id}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == sub_id

    def test_get_owner_ok(self, fresh_user):
        sub_id = fresh_user.get("plus_sub_id")
        r = requests.get(f"{API}/submissions/{sub_id}", headers=_h(fresh_user["token"]))
        assert r.status_code == 200

    def test_get_other_user_returns_403(self, fresh_user, other_user):
        sub_id = fresh_user.get("plus_sub_id")
        r = requests.get(f"{API}/submissions/{sub_id}", headers=_h(other_user["token"]))
        assert r.status_code == 403


# ----------------- Fresh user free flow (single free submission, not full e2e) -----------------
class TestFreshUserFreeSubmit:
    def test_fresh_user_can_post_free(self, fresh_user):
        # fresh_user used 0 free slots → first free submission should succeed
        body = {
            "name": "Fresh Free",
            "email": "fresh@test.example",
            "plan_id": "free",
            "room_type": "closet",
            "photos_base64": [PNG_1X1],
        }
        r = requests.post(f"{API}/submissions", json=body, headers=_h(fresh_user["token"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending"
        assert d["checkout_url"] is None
        assert d["photos_total"] == 1
        # Don't wait for full AI completion — just verify state is pending
        fresh_user["free_sub_id"] = d["id"]
