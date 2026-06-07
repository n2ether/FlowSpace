"""Emergent-managed Google authentication for FlowSpace."""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Request, Response, Header

from db import db
from plans import plan_cfg

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "camila@flowspace.solutions").lower()
SESSION_DAYS = 7

auth_router = APIRouter(prefix="/api/auth")


def _clean(doc: dict) -> dict:
    return {k: v for k, v in (doc or {}).items() if k != "_id"}


async def ensure_period(user: dict) -> dict:
    """Reset monthly credits for paid plans when the 30-day window rolls over."""
    cfg = plan_cfg(user.get("subscription_plan", "free"))
    if cfg["lifetime"]:
        return user
    ps = user.get("period_start")
    try:
        start = datetime.fromisoformat(ps) if isinstance(ps, str) else ps
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    except Exception:
        start = None
    now = datetime.now(timezone.utc)
    if not start or (now - start) > timedelta(days=30):
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"monthly_generations_used": 0, "period_start": now.isoformat()}},
        )
        user["monthly_generations_used"] = 0
        user["period_start"] = now.isoformat()
    return user


async def get_current_user(request: Request) -> dict:
    token = None
    authz = request.headers.get("Authorization")
    if authz and authz.startswith("Bearer "):
        token = authz[7:]
    if not token:
        token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = sess.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return await ensure_period(user)


@auth_router.post("/session")
async def create_session(request: Request, response: Response, x_session_id: Optional[str] = Header(default=None)):
    session_id = x_session_id
    if not session_id:
        try:
            body = await request.json()
            session_id = body.get("session_id")
        except Exception:
            session_id = None
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    try:
        resp = requests.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth exchange failed: {e}")

    email = (data.get("email") or "").lower()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture") or ""
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Incomplete auth data")

    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        cfg = plan_cfg("free")
        user = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": name,
            "picture": picture,
            "subscription_plan": "free",
            "stripe_customer_id": None,
            "monthly_generation_limit": cfg["limit"],
            "monthly_generations_used": 0,
            "period_start": now.isoformat(),
            "is_admin": email == ADMIN_EMAIL,
            "created_at": now.isoformat(),
        }
        await db.users.insert_one(dict(user))
    else:
        await db.users.update_one(
            {"email": email},
            {"$set": {"name": name, "picture": picture, "is_admin": user.get("is_admin") or email == ADMIN_EMAIL}},
        )
        user["name"], user["picture"] = name, picture

    expires_at = now + timedelta(days=SESSION_DAYS)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
    })

    response.set_cookie(
        key="session_token", value=session_token, max_age=SESSION_DAYS * 24 * 3600,
        httponly=True, secure=True, samesite="none", path="/",
    )
    return _clean(user)


@auth_router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    return _clean(user)


@auth_router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    authz = request.headers.get("Authorization")
    if not token and authz and authz.startswith("Bearer "):
        token = authz[7:]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}
