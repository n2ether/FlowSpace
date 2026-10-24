"""Password reset: token storage, generic response, expiry, single use, rate limits."""
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient

from auth import ALGORITHM, COOKIE_NAME, jwt_secret
from password_reset import (
    GENERIC_RESET_MESSAGE,
    RATE_LIMIT_PER_EMAIL,
    RATE_LIMIT_PER_IP,
    RESET_TOKEN_TTL_MINUTES,
    hash_token,
)

from .test_member_auth import FakeDB, _signup


@pytest.fixture
def reset_client(monkeypatch):
    fake = FakeDB()
    import server

    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://app.example.test/")

    async def no_seed():
        return None

    sent = []

    async def fake_send(*, to_email, reset_link, ttl_minutes):
        sent.append({"to": to_email, "link": reset_link, "ttl": ttl_minutes})
        return True, None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    monkeypatch.setattr(server, "send_password_reset", fake_send)
    with TestClient(server.app) as c:
        yield c, fake, sent


def _forgot(c, email="ada@example.com", ip="203.0.113.7"):
    return c.post("/api/auth/forgot-password", json={"email": email}, headers={"X-Forwarded-For": ip})


def _token_from(link):
    return parse_qs(urlparse(link).query)["token"][0]


def _request_token(c, sent, email="ada@example.com"):
    r = _forgot(c, email)
    assert r.status_code == 200, r.text
    return _token_from(sent[-1]["link"])


class TestForgotPassword:
    def test_creates_hashed_time_limited_token_and_emails_link(self, reset_client):
        c, db, sent = reset_client
        _signup(c)
        before = datetime.now(timezone.utc)
        r = _forgot(c)
        assert r.status_code == 200
        assert r.json() == {"ok": True, "message": GENERIC_RESET_MESSAGE}

        assert len(sent) == 1
        assert sent[0]["to"] == "ada@example.com"
        assert sent[0]["link"].startswith("https://app.example.test/reset-password?token=")
        token = _token_from(sent[0]["link"])
        assert len(token) >= 32

        assert len(db.password_resets.docs) == 1
        record = db.password_resets.docs[0]
        assert record["token_hash"] == hash_token(token)
        assert token not in str(record)
        assert record["used_at"] is None
        ttl = record["expires_at"] - before
        assert timedelta(minutes=RESET_TOKEN_TTL_MINUTES - 1) < ttl <= timedelta(minutes=RESET_TOKEN_TTL_MINUTES + 1)

    def test_unknown_email_gets_identical_response_and_no_email(self, reset_client):
        c, db, sent = reset_client
        _signup(c)
        known = _forgot(c, "ada@example.com", ip="198.51.100.1")
        unknown = _forgot(c, "nobody@example.com", ip="198.51.100.2")
        assert unknown.status_code == known.status_code == 200
        assert unknown.json() == known.json()
        assert [s["to"] for s in sent] == ["ada@example.com"]
        assert len(db.password_resets.docs) == 1

    def test_email_is_case_insensitive(self, reset_client):
        c, _, sent = reset_client
        _signup(c)
        assert _forgot(c, "ADA@Example.com").status_code == 200
        assert [s["to"] for s in sent] == ["ada@example.com"]

    def test_new_request_retires_earlier_token(self, reset_client):
        c, _, sent = reset_client
        _signup(c)
        first = _request_token(c, sent)
        second = _request_token(c, sent)
        assert first != second
        stale = c.post("/api/auth/reset-password", json={"token": first, "password": "brand-new-pass"})
        assert stale.status_code == 400
        fresh = c.post("/api/auth/reset-password", json={"token": second, "password": "brand-new-pass"})
        assert fresh.status_code == 200, fresh.text

    def test_token_never_logged(self, reset_client, caplog):
        c, _, sent = reset_client
        _signup(c)
        with caplog.at_level(logging.DEBUG):
            token = _request_token(c, sent)
            c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
        assert token not in caplog.text
        assert hash_token(token) not in caplog.text


class TestRateLimit:
    def test_per_email_limit(self, reset_client):
        c, _, sent = reset_client
        _signup(c)
        for i in range(RATE_LIMIT_PER_EMAIL):
            assert _forgot(c, ip=f"192.0.2.{i}").status_code == 200
        blocked = _forgot(c, ip="192.0.2.200")
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "RATE_LIMITED"
        assert len(sent) == RATE_LIMIT_PER_EMAIL

    def test_per_ip_limit(self, reset_client):
        c, _, _ = reset_client
        for i in range(RATE_LIMIT_PER_IP):
            assert _forgot(c, f"user{i}@example.com", ip="192.0.2.50").status_code == 200
        assert _forgot(c, "another@example.com", ip="192.0.2.50").status_code == 429
        assert _forgot(c, "another@example.com", ip="192.0.2.51").status_code == 200

    def test_unknown_emails_are_limited_the_same_way(self, reset_client):
        c, _, _ = reset_client
        codes = [_forgot(c, "ghost@example.com", ip=f"192.0.2.{i}").status_code for i in range(RATE_LIMIT_PER_EMAIL + 1)]
        assert codes == [200] * RATE_LIMIT_PER_EMAIL + [429]

    def test_limit_resets_after_an_hour(self, reset_client):
        c, db, _ = reset_client
        for i in range(RATE_LIMIT_PER_EMAIL):
            _forgot(c, ip=f"192.0.2.{i}")
        assert _forgot(c, ip="192.0.2.99").status_code == 429
        for doc in db.password_reset_requests.docs:
            doc["created_at"] -= timedelta(hours=1, minutes=1)
        assert _forgot(c, ip="192.0.2.99").status_code == 200


class TestResetPassword:
    def test_reset_signs_in_and_changes_password(self, reset_client):
        c, _, sent = reset_client
        _signup(c, password="old-password")
        c.cookies.clear()
        token = _request_token(c, sent)
        r = c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token"]
        assert body["member"]["email"] == "ada@example.com"
        assert "password_hash" not in body["member"]
        assert r.cookies.get(COOKIE_NAME)

        assert c.post("/api/auth/login", json={"email": "ada@example.com", "password": "old-password"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass"}).status_code == 200

    def test_token_is_single_use(self, reset_client):
        c, db, sent = reset_client
        _signup(c)
        token = _request_token(c, sent)
        assert c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"}).status_code == 200
        again = c.post("/api/auth/reset-password", json={"token": token, "password": "another-pass"})
        assert again.status_code == 400
        assert again.json()["detail"]["code"] == "INVALID_RESET_TOKEN"
        assert db.password_resets.docs[0]["used_at"] is not None

    def test_expired_token_rejected(self, reset_client):
        c, db, sent = reset_client
        _signup(c)
        token = _request_token(c, sent)
        db.password_resets.docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        r = c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_RESET_TOKEN"

    @pytest.mark.parametrize("token", ["", "not-a-real-token", "x" * 1000])
    def test_unknown_token_rejected(self, reset_client, token):
        c, _, _ = reset_client
        r = c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
        assert r.status_code == 400

    def test_signup_password_rules_apply_and_do_not_burn_token(self, reset_client):
        c, db, sent = reset_client
        _signup(c)
        token = _request_token(c, sent)
        weak = c.post("/api/auth/reset-password", json={"token": token, "password": "short"})
        assert weak.status_code == 400
        assert weak.json()["detail"]["code"] == "WEAK_PASSWORD"
        assert db.password_resets.docs[0]["used_at"] is None
        assert c.post("/api/auth/reset-password", json={"token": token, "password": "long-enough"}).status_code == 200

    def test_sessions_from_before_reset_stop_working(self, reset_client):
        c, db, sent = reset_client
        member_id = _signup(c).json()["member"]["id"]
        c.cookies.clear()
        issued = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
        old_session = jwt.encode(
            {"sub": member_id, "email": "ada@example.com", "iat": issued, "exp": issued + 3600},
            jwt_secret(),
            algorithm=ALGORITHM,
        )
        headers = {"Authorization": f"Bearer {old_session}"}
        assert c.get("/api/auth/me", headers=headers).status_code == 200

        token = _request_token(c, sent)
        fresh = c.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"}).json()["token"]
        c.cookies.clear()
        assert c.get("/api/auth/me", headers=headers).status_code == 401
        assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200
