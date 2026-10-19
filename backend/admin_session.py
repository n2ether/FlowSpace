"""Admin session tokens. The admin password is a login secret, never a bearer token."""
from __future__ import annotations

import hmac
import os
import secrets
import time
from typing import Optional

import jwt

ADMIN_SESSION_TTL_SECONDS = 12 * 60 * 60
_ALGORITHM = "HS256"
_AUDIENCE = "flowspace-admin"


def _secret() -> str:
    secret = (os.environ.get("ADMIN_SESSION_SECRET") or "").strip()
    if secret:
        return secret
    from auth import jwt_secret

    return "admin-session:" + jwt_secret()


def create_admin_token(*, now: Optional[float] = None, ttl: int = ADMIN_SESSION_TTL_SECONDS) -> str:
    issued = int(now if now is not None else time.time())
    payload = {
        "sub": "admin",
        "aud": _AUDIENCE,
        "iat": issued,
        "exp": issued + int(ttl),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def verify_admin_token(token: Optional[str]) -> bool:
    if not token or token.count(".") != 2:
        return False
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM], audience=_AUDIENCE)
    except jwt.PyJWTError:
        return False
    return payload.get("sub") == "admin"


def password_matches(candidate: Optional[str], password: str) -> bool:
    if not candidate or not password:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), password.encode("utf-8"))
