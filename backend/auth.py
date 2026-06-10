"""Email/password authentication (JWT) for FlowSpace."""
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from db import db
from plans import plan_cfg
import email_service

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 7
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "camila@flowspace.solutions").lower()
MAX_FAILED = 5
LOCKOUT_MINUTES = 15

auth_router = APIRouter(prefix="/api/auth")


# ----------------------------- helpers -----------------------------
def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email, "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _set_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="lax", max_age=ACCESS_TOKEN_DAYS * 24 * 3600, path="/",
    )


def _clean(doc: dict) -> dict:
    return {k: v for k, v in (doc or {}).items() if k not in ("_id", "password_hash")}


async def ensure_period(user: dict) -> dict:
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
    token = request.cookies.get("access_token")
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return await ensure_period(user)


def _new_user_doc(email: str, name: str, password_hash: str) -> dict:
    cfg = plan_cfg("free")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": email, "name": name, "password_hash": password_hash, "picture": "",
        "subscription_plan": "free", "stripe_customer_id": None,
        "monthly_generation_limit": cfg["limit"], "monthly_generations_used": 0,
        "period_start": now, "is_admin": email == ADMIN_EMAIL, "created_at": now,
    }


# ----------------------------- models -----------------------------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class ForgotReq(BaseModel):
    email: EmailStr
    origin_url: str


class ResetReq(BaseModel):
    token: str
    password: str


# ----------------------------- routes -----------------------------
@auth_router.post("/register")
async def register(payload: RegisterReq, response: Response):
    email = payload.email.lower().strip()
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    name = (payload.name or email.split("@")[0]).strip()
    user = _new_user_doc(email, name, hash_password(payload.password))
    await db.users.insert_one(dict(user))
    _set_cookie(response, create_access_token(user["user_id"], email))
    return _clean(user)


@auth_router.post("/login")
async def login(payload: LoginReq, request: Request, response: Response):
    email = payload.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    ident = f"{ip}:{email}"

    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= MAX_FAILED:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        now = datetime.now(timezone.utc)
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1},
             "$set": {"locked_until": (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": ident})
    _set_cookie(response, create_access_token(user["user_id"], email))
    return _clean(user)


@auth_router.get("/me")
async def me(request: Request):
    return _clean(await get_current_user(request))


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@auth_router.post("/forgot-password")
async def forgot_password(payload: ForgotReq):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0, "name": 1})
    # Always return ok (don't reveal whether the email exists).
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token, "email": email, "used": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        link = f"{payload.origin_url.rstrip('/')}/reset-password?token={token}"
        await email_service.send_password_reset_email(email, user.get("name", "there"), link)
    return {"ok": True}


@auth_router.post("/reset-password")
async def reset_password(payload: ResetReq, response: Response):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    rec = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="This reset link is invalid or already used")
    if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This reset link has expired")
    await db.users.update_one({"email": rec["email"]},
                              {"$set": {"password_hash": hash_password(payload.password)}})
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    user = await db.users.find_one({"email": rec["email"]}, {"_id": 0})
    _set_cookie(response, create_access_token(user["user_id"], rec["email"]))
    return _clean(user)
