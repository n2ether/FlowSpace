"""Private photo storage: unguessable ids, HMAC-signed read URLs, URL canonicalization.

Stored references stay canonical (``/api/uploads/photo/{id}``). Only URLs handed
to a browser are signed (``?exp=…&sig=…``). The backend itself reads GridFS
directly and never needs a signature.

Legacy uploads use GridFS ObjectIds; they keep resolving here, but are now
readable only with a signature, an admin session, or the owning member.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

from bson import ObjectId

from pdf_images import as_gridfs_source

PHOTO_URL_PREFIX = "/api/uploads/photo/"
SIGNED_URL_TTL_SECONDS = 60 * 60
_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{24}$")
_UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def _secret() -> bytes:
    secret = (os.environ.get("PHOTO_URL_SECRET") or "").strip()
    if not secret:
        from auth import jwt_secret

        secret = "photo-url:" + jwt_secret()
    return secret.encode("utf-8")


def new_photo_id() -> str:
    """32 hex chars from uuid4 — 122 random bits, not enumerable."""
    return uuid.uuid4().hex


def gridfs_key(photo_id: str) -> Optional[Any]:
    """GridFS ``_id`` for a public photo id, or None if the id is malformed."""
    text = str(photo_id or "").strip().lower()
    if _UUID_HEX_RE.match(text):
        return text
    if _OBJECT_ID_RE.match(text):
        return ObjectId(text)
    return None


def photo_id_from_url(url: Optional[str]) -> str:
    if not url or PHOTO_URL_PREFIX not in str(url):
        return ""
    path = urlsplit(str(url)).path if "://" in str(url) else str(url).split("?", 1)[0].split("#", 1)[0]
    return path.rstrip("/").rsplit("/", 1)[-1]


def canonical_photo_url(url: str) -> str:
    """Drop any signature so a stored reference never carries an expiring token."""
    if not isinstance(url, str) or PHOTO_URL_PREFIX not in url:
        return url
    return url.split("?", 1)[0].split("#", 1)[0]


def canonicalize_photo_urls(value: Any) -> Any:
    if isinstance(value, str):
        return canonical_photo_url(value)
    if isinstance(value, list):
        return [canonicalize_photo_urls(v) for v in value]
    if isinstance(value, dict):
        return {k: canonicalize_photo_urls(v) for k, v in value.items()}
    return value


def _mac(message: str) -> str:
    digest = hmac.new(_secret(), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:24]).decode("ascii").rstrip("=")


def signature(photo_id: str, exp: int) -> str:
    return _mac(f"read:{photo_id.lower()}:{int(exp)}")


def verify_signature(photo_id: str, exp: Any, sig: Optional[str], *, now: Optional[float] = None) -> bool:
    if not sig or exp in (None, ""):
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(now if now is not None else time.time()):
        return False
    return hmac.compare_digest(signature(photo_id, exp_i), str(sig))


def signed_photo_url(url: str, *, ttl: int = SIGNED_URL_TTL_SECONDS, now: Optional[float] = None) -> str:
    """Short-lived read URL for a browser. Non-photo URLs pass through unchanged."""
    if not isinstance(url, str) or PHOTO_URL_PREFIX not in url:
        return url
    base = canonical_photo_url(url)
    photo_id = photo_id_from_url(base)
    if not gridfs_key(photo_id):
        return url
    # Round expiry up to the next 5 minutes so repeated responses share one URL and
    # the browser cache stays useful.
    issued = int(now if now is not None else time.time())
    exp = ((issued + int(ttl)) // 300 + 1) * 300
    return f"{base}?exp={exp}&sig={signature(photo_id, exp)}"


def sign_photo_urls(value: Any, *, ttl: int = SIGNED_URL_TTL_SECONDS) -> Any:
    """Deep copy of an API payload with every stored photo URL signed."""
    if isinstance(value, str):
        return signed_photo_url(value, ttl=ttl)
    if isinstance(value, list):
        return [sign_photo_urls(v, ttl=ttl) for v in value]
    if isinstance(value, tuple):
        return [sign_photo_urls(v, ttl=ttl) for v in value]
    if isinstance(value, dict):
        return {k: sign_photo_urls(v, ttl=ttl) for k, v in value.items()}
    return value


def signature_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    query = parse_qs(urlsplit(url).query)
    return (query.get("exp") or [None])[0], (query.get("sig") or [None])[0]


def upload_token(photo_id: str) -> str:
    """Per-photo capability returned only to the uploader, to refresh an expired preview."""
    return _mac(f"owner:{photo_id.lower()}")


def verify_upload_token(photo_id: str, token: Optional[str]) -> bool:
    return bool(token) and hmac.compare_digest(upload_token(photo_id), str(token))


async def store_photo(
    fs_bucket,
    *,
    filename: str,
    data: bytes,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Persist bytes under a fresh unguessable id and return the canonical URL."""
    photo_id = new_photo_id()
    await fs_bucket.upload_from_stream_with_id(
        photo_id,
        filename,
        as_gridfs_source(data),
        metadata=metadata or {},
    )
    return f"{PHOTO_URL_PREFIX}{photo_id}"
