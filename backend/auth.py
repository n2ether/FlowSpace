"""Member authentication helpers (password hashing + JWT).

Kept independent of FastAPI/Mongo so the crypto and token rules can be
unit-tested without a running database.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Request

COOKIE_NAME = "flowspace_session"
TOKEN_TTL_DAYS = 30
MIN_PASSWORD_LENGTH = 8
ALGORITHM = "HS256"


def jwt_secret() -> str:
    secret = (os.environ.get("JWT_SECRET") or os.environ.get("SESSION_SECRET") or "").strip()
    if secret:
        return secret
    # Local/test fallback only. Production must set JWT_SECRET.
    return os.environ.get("ADMIN_PASSWORD", "flowspace-dev-jwt-secret")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    return None


def create_token(member_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": member_id,
        "email": normalize_email(email),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    cookie = request.cookies.get(COOKIE_NAME)
    return cookie or None


def cookie_kwargs() -> Dict[str, Any]:
    """
    Cross-origin Railway FE + API need SameSite=None; Secure.
    Localhost uses Lax so the cookie still sets over http.
    """
    origins = (os.environ.get("CORS_ORIGINS") or "").lower()
    is_local = "localhost" in origins or "127.0.0.1" in origins
    secure_env = os.environ.get("COOKIE_SECURE", "").strip().lower()
    samesite_env = os.environ.get("COOKIE_SAMESITE", "").strip().lower()

    if samesite_env in {"lax", "strict", "none"}:
        samesite = samesite_env
    else:
        samesite = "lax" if is_local else "none"

    if secure_env in {"true", "1", "yes"}:
        secure = True
    elif secure_env in {"false", "0", "no"}:
        secure = False
    else:
        secure = samesite == "none"

    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "max_age": TOKEN_TTL_DAYS * 24 * 60 * 60,
        "path": "/",
    }
