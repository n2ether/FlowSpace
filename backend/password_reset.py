"""Password reset tokens and request rate limiting.

Only the SHA-256 of a reset token is stored; the raw token exists in the
emailed link and nowhere else. Tokens are single use and expire after
RESET_TOKEN_TTL_MINUTES.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from auth import normalize_email

RESET_TOKEN_TTL_MINUTES = 60
RATE_LIMIT_WINDOW = timedelta(hours=1)
RATE_LIMIT_PER_EMAIL = 5
RATE_LIMIT_PER_IP = 5

GENERIC_RESET_MESSAGE = (
    "If an account exists for that email, we've sent a link to reset your password. "
    f"The link expires in {RESET_TOKEN_TTL_MINUTES} minutes."
)
INVALID_TOKEN_MESSAGE = "This reset link is invalid or has expired. Request a new one."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _hash_key(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def new_reset_token() -> str:
    return secrets.token_urlsafe(32)


def reset_url(base_url: str, token: str) -> str:
    return f"{(base_url or '').rstrip('/')}/reset-password?token={token}"


def client_ip(headers: Dict[str, str], fallback: Optional[str]) -> str:
    """First hop of X-Forwarded-For (Railway's proxy sets it), else the socket peer."""
    forwarded = (headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (fallback or "unknown")


async def rate_limited(db, email: str, ip: str, *, now: Optional[datetime] = None) -> bool:
    """Record this request unless the email or IP already hit its hourly limit."""
    now = now or _now()
    since = now - RATE_LIMIT_WINDOW
    email_key = _hash_key(normalize_email(email))
    ip_key = _hash_key(ip)
    by_email = await db.password_reset_requests.count_documents(
        {"email_key": email_key, "created_at": {"$gte": since}}
    )
    by_ip = await db.password_reset_requests.count_documents({"ip_key": ip_key, "created_at": {"$gte": since}})
    if by_email >= RATE_LIMIT_PER_EMAIL or by_ip >= RATE_LIMIT_PER_IP:
        return True
    await db.password_reset_requests.insert_one({"email_key": email_key, "ip_key": ip_key, "created_at": now})
    return False


async def issue_reset_token(db, member: Dict[str, Any], *, now: Optional[datetime] = None) -> str:
    """Store a fresh token for the member, retiring any earlier unused ones."""
    now = now or _now()
    await db.password_resets.update_many(
        {"member_id": member["id"], "used_at": None},
        {"$set": {"used_at": now, "superseded": True}},
    )
    token = new_reset_token()
    await db.password_resets.insert_one(
        {
            "token_hash": hash_token(token),
            "member_id": member["id"],
            "created_at": now,
            "expires_at": now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
            "used_at": None,
        }
    )
    return token


async def consume_reset_token(db, token: str, *, now: Optional[datetime] = None) -> Optional[str]:
    """Mark the token used and return its member_id, or None if invalid, expired, or already used."""
    if not token or len(token) > 256:
        return None
    now = now or _now()
    token_hash = hash_token(token)
    record = await db.password_resets.find_one(
        {"token_hash": token_hash, "used_at": None, "expires_at": {"$gt": now}},
        {"_id": 0},
    )
    if not record:
        return None
    # The used_at guard makes the claim atomic: two concurrent submits cannot both win.
    claimed = await db.password_resets.update_one(
        {"token_hash": token_hash, "used_at": None},
        {"$set": {"used_at": now}},
    )
    if not getattr(claimed, "modified_count", 0):
        return None
    return record.get("member_id")


async def retire_member_tokens(db, member_id: str, *, now: Optional[datetime] = None) -> None:
    await db.password_resets.update_many(
        {"member_id": member_id, "used_at": None},
        {"$set": {"used_at": now or _now(), "superseded": True}},
    )


async def ensure_reset_indexes(db) -> None:
    try:
        await db.password_resets.create_index("token_hash", unique=True)
        await db.password_resets.create_index("member_id")
        await db.password_resets.create_index("expires_at", expireAfterSeconds=24 * 60 * 60)
        await db.password_reset_requests.create_index("email_key")
        await db.password_reset_requests.create_index("ip_key")
        await db.password_reset_requests.create_index(
            "created_at", expireAfterSeconds=int(RATE_LIMIT_WINDOW.total_seconds())
        )
    except Exception:
        return
