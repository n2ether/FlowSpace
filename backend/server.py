from fastapi import FastAPI, APIRouter, HTTPException, Request, BackgroundTasks, Response, Cookie, Header, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import asyncio
import secrets
import resend
import httpx
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
    CheckoutSessionRequest,
)
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

from design_plan import generate_design_plan
from pdf_generator import render_design_plan_pdf

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
DEV_LOGIN_PASSWORD = os.environ.get("DEV_LOGIN_PASSWORD", "")

resend.api_key = RESEND_API_KEY

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Keep strong references to in-flight background tasks so the event loop
# doesn't garbage-collect them mid-run (CPython asyncio footgun).
_BG_TASKS: set = set()

# ----- Auth helpers (Emergent-managed Google sign-in) -----
SESSION_COOKIE_NAME = "session_token"
SESSION_TTL_DAYS = 7
EMERGENT_SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
FREE_PROJECT_CAP = 2  # max free submissions per user before paywall

class User(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    free_used: int = 0
    free_cap: int = FREE_PROJECT_CAP
    free_remaining: int = FREE_PROJECT_CAP

def _extract_session_token(request: Request) -> Optional[str]:
    tok = request.cookies.get(SESSION_COOKIE_NAME)
    if tok:
        return tok
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None

async def _load_user_for_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    exp = session.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            exp = None
    if exp is None:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    return user

async def current_user(request: Request) -> Dict[str, Any]:
    token = _extract_session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await _load_user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user

async def optional_user(request: Request) -> Optional[Dict[str, Any]]:
    token = _extract_session_token(request)
    if not token:
        return None
    return await _load_user_for_token(token)

async def _free_count_for_user(user_id: str) -> int:
    return await db.submissions.count_documents({"user_id": user_id, "plan_id": "free"})

def _user_out(user: Dict[str, Any], free_used: int) -> User:
    return User(
        user_id=user["user_id"],
        email=user["email"],
        name=user.get("name") or user["email"].split("@")[0],
        picture=user.get("picture"),
        free_used=free_used,
        free_cap=FREE_PROJECT_CAP,
        free_remaining=max(0, FREE_PROJECT_CAP - free_used),
    )

# ----- Pricing (server-side only) -----
PLANS: Dict[str, Dict[str, Any]] = {
    "free":    {"name": "Free",    "price": 0.0,  "max_photos": 2, "pdf": False},
    "plus":    {"name": "Plus",    "price": 10.0, "max_photos": 3, "pdf": True},
    "premium": {"name": "Premium", "price": 20.0, "max_photos": 4, "pdf": True},
}

# ----- Models -----
class CheckoutCreateRequest(BaseModel):
    plan_id: str
    origin_url: str
    customer_email: Optional[EmailStr] = None
    customer_name: Optional[str] = None

class CheckoutCreateResponse(BaseModel):
    url: str
    session_id: str

class CheckoutStatusOut(BaseModel):
    status: str
    payment_status: str
    plan_id: Optional[str] = None
    amount_total: int
    currency: str

class SubmissionCreate(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    plan_id: str
    room_type: Optional[str] = None
    notes: Optional[str] = None
    budget: Optional[str] = None  # e.g. "$100 – $300"
    photos_base64: List[str]  # data URLs or raw base64
    session_id: Optional[str] = None  # for paid plans

class SubmissionPhotoOut(BaseModel):
    before: str  # base64 png
    after: str   # base64 png

class SubmissionOut(BaseModel):
    id: str
    plan_id: str
    status: str  # "awaiting_payment" | "pending" | "processing" | "completed" | "failed"
    room_type: Optional[str] = None
    pdf_available: bool = False
    photos_total: int = 0
    photos_done: int = 0
    error: Optional[str] = None
    checkout_url: Optional[str] = None
    checkout_session_id: Optional[str] = None
    results: List[SubmissionPhotoOut]

# ----- Helpers -----
def strip_data_url(b64: str) -> str:
    if b64.startswith("data:"):
        return b64.split(",", 1)[1]
    return b64

async def _describe_room(before_b64: str) -> str:
    """Use Claude vision to produce a short description of the user's room
    that we can hand to a text-to-image model. Falls back to a generic prompt."""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"describe-{uuid.uuid4()}",
            system_message=(
                "You describe rooms for an interior-design image generator. "
                "Reply with 2 short sentences ONLY: (1) room type + layout + "
                "key architectural features (walls, windows, flooring, lighting), "
                "(2) the most prominent furniture and built-ins visible. "
                "No clutter descriptions. No people. No brand names."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(
            text="Describe this room briefly so an image generator can recreate it organized.",
            file_contents=[ImageContent(strip_data_url(before_b64))],
        )
        response = await chat.send_message(msg)
        text = response if isinstance(response, str) else str(response)
        return text.strip()[:700]
    except Exception as e:
        logger.warning(f"Room description failed, using generic prompt: {e}")
        return "A residential room with neutral walls and standard fixtures."


async def generate_after_image(before_b64: str) -> Optional[str]:
    """Generate a photorealistic 'organized' version of the user's room using
    GPT Image 1. Pipeline: Claude vision describes the room → GPT Image 1
    renders the organized version from that description."""
    try:
        description = await _describe_room(before_b64)
        prompt = (
            f"{description} "
            "Photorealistic interior photograph of THIS SAME room, completely "
            "decluttered, professionally organized, and beautifully styled. "
            "Add tasteful matching storage bins with labels, neat shelving, clear "
            "floor space, neatly folded or hung items, and warm natural lighting. "
            "Preserve the room's architecture (walls, windows, doors, flooring) and "
            "general furniture footprint. Magazine-quality, bright, airy, calm, "
            "inviting. No people. No text overlays."
        )
        img_gen = OpenAIImageGeneration(api_key=EMERGENT_LLM_KEY)
        images = await img_gen.generate_images(
            prompt=prompt,
            model="gpt-image-1",
            number_of_images=1,
            quality="medium",
        )
        if images:
            return base64.b64encode(images[0]).decode("ascii")
    except Exception as e:
        logger.error(f"GPT Image 1 generation failed: {e}", exc_info=True)
    return None

def _photo_attachments(submission: Dict[str, Any]) -> list:
    """Return each AI-generated 'after' image (and the 'before' if no after) as a PNG attachment."""
    attachments = []
    room = (submission.get("room_type") or "Room").title().replace(" ", "-")
    for i, r in enumerate(submission.get("results", []), 1):
        # Prefer the AI-generated organized version
        after = (r or {}).get("after")
        if after:
            attachments.append({
                "filename": f"FlowSpace-{room}-Organized-Photo-{i}.png",
                "content": after,
            })
        elif r and r.get("before"):
            attachments.append({
                "filename": f"FlowSpace-{room}-Photo-{i}.png",
                "content": r["before"],
            })
    return attachments


def send_admin_email_sync(submission: Dict[str, Any]) -> None:
    plan = PLANS.get(submission["plan_id"], {})
    rows = ""
    for i, r in enumerate(submission.get("results", []), 1):
        before_src = f"data:image/png;base64,{r['before']}"
        after_src = f"data:image/png;base64,{r['after']}" if r.get("after") else ""
        rows += (
            f"<tr><td style='padding:8px;font-family:Inter,Arial,sans-serif;color:#0f172a'>"
            f"<strong>Photo {i}</strong><br/>"
            f"<img src='{before_src}' style='max-width:280px;border-radius:8px;margin:6px 0'/>"
            f"{('<br/><em>AI transformation:</em><br/><img src=' + chr(34) + after_src + chr(34) + ' style=' + chr(34) + 'max-width:280px;border-radius:8px;margin:6px 0' + chr(34) + '/>') if after_src else ''}"
            f"</td></tr>"
        )

    pdf_note = ""
    attachments = _photo_attachments(submission)
    if submission.get("pdf_base64"):
        room = submission.get("room_type") or "Room"
        room_pretty = room.title().replace(" ", "-")
        filename = f"FlowSpace-{room_pretty}-Design-Plan.pdf"
        attachments.insert(0, {"filename": filename, "content": submission["pdf_base64"]})
        pdf_note = (
            f"<p style='margin:14px 0 0;color:#047857;font-weight:600'>"
            f"PDF Design Plan attached: {filename}</p>"
        )

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;color:#0f172a;max-width:640px;margin:auto">
      <h2 style="color:#059669;margin:0 0 8px 0">New FlowSpace submission</h2>
      <p style="margin:0 0 16px 0;color:#475569">A new client just submitted photos for transformation.</p>
      <table cellpadding="0" cellspacing="0" style="width:100%;border:1px solid #e2e8f0;border-radius:12px;padding:16px">
        <tr><td><strong>Name:</strong> {submission.get('name') or '—'}</td></tr>
        <tr><td><strong>Customer email:</strong> {submission.get('email')}</td></tr>
        <tr><td><strong>Plan:</strong> {plan.get('name', submission.get('plan_id'))}</td></tr>
        <tr><td><strong>Room type:</strong> {submission.get('room_type') or '—'}</td></tr>
        <tr><td><strong>Budget:</strong> {submission.get('budget') or '—'}</td></tr>
        <tr><td><strong>Photos:</strong> {len(submission.get('results', []))}</td></tr>
        <tr><td><strong>Notes:</strong> {submission.get('notes') or '—'}</td></tr>
        <tr><td><strong>Submitted:</strong> {submission.get('created_at')}</td></tr>
      </table>
      {pdf_note}
      <h3 style="margin-top:24px;color:#0f172a">Photos</h3>
      <table cellpadding="0" cellspacing="0" style="width:100%">{rows}</table>
    </div>
    """
    params = {
        "from": f"FlowSpace <{SENDER_EMAIL}>",
        "to": [ADMIN_EMAIL],
        "subject": f"New {plan.get('name', 'FlowSpace')} submission from {submission.get('email')}",
        "html": html,
    }
    if attachments:
        params["attachments"] = attachments
    try:
        resend.Emails.send(params)
    except Exception as e:
        logger.error(f"Resend admin email failed: {e}")


def send_customer_email_sync(submission: Dict[str, Any], result_url: str) -> None:
    """Sends the customer their AI transformation summary (+ PDF for paid plans).
    Customer is the primary recipient; ADMIN_EMAIL is BCC'd for record-keeping."""
    plan = PLANS.get(submission["plan_id"], {})
    customer_email = submission.get("email", "")
    name = submission.get("name") or "there"

    if not customer_email:
        return

    attachments = _photo_attachments(submission)
    pdf_block = ""
    if submission.get("pdf_base64"):
        room = submission.get("room_type") or "Room"
        room_pretty = room.title().replace(" ", "-")
        filename = f"FlowSpace-{room_pretty}-Design-Plan.pdf"
        attachments.insert(0, {"filename": filename, "content": submission["pdf_base64"]})
        pdf_block = (
            "<p style='margin:16px 0 8px;font-weight:600;color:#047857'>"
            f"Your custom PDF Design Plan ({filename}) and {len(submission.get('results', []))} organized "
            "photo(s) are attached to this email."
            "</p>"
        )
    elif plan.get("pdf"):
        pdf_block = (
            "<p style='margin:16px 0 8px;color:#92400e'>"
            "Your PDF Design Plan will be ready shortly — check back on the link below."
            "</p>"
        )
    elif attachments:
        pdf_block = (
            "<p style='margin:16px 0 8px;color:#475569'>"
            f"Your {len(submission.get('results', []))} AI-organized photo(s) are attached."
            "</p>"
        )

    upgrade_block = ""
    if not plan.get("pdf"):
        upgrade_block = (
            "<div style='margin-top:16px;padding:12px 14px;border-radius:10px;"
            "background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;font-size:13px'>"
            "<strong>Want the full design plan?</strong> Upgrade to Plus or "
            "Premium to unlock your PDF Design Plan with floor plan, shopping "
            "list, wall colors, and action steps."
            "</div>"
        )

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;color:#0f172a;max-width:560px;margin:auto;padding:8px">
      <h2 style="color:#059669;margin:0 0 6px 0">Your FlowSpace transformation is ready</h2>
      <p style="margin:0;color:#475569">Hi {name} — thanks for using FlowSpace.</p>
      <p style="margin:14px 0 0">
        We&rsquo;ve generated your AI-organized room visuals on the
        <strong>{plan.get('name','FlowSpace')}</strong> plan. View them anytime:
      </p>
      <p style="margin:16px 0">
        <a href="{result_url}" style="display:inline-block;padding:11px 18px;
          background:#10b981;color:#fff;border-radius:9999px;text-decoration:none;
          font-weight:600">View my transformation</a>
      </p>
      {pdf_block}
      {upgrade_block}
      <p style="margin-top:22px;font-size:12px;color:#94a3b8">
        © FlowSpace.Solutions — Clear space. Create flow. Live better.
      </p>
    </div>
    """
    params = {
        "from": f"FlowSpace <{SENDER_EMAIL}>",
        "to": [customer_email],
        "bcc": [ADMIN_EMAIL] if ADMIN_EMAIL and ADMIN_EMAIL.lower() != customer_email.lower() else [],
        "subject": f"Your FlowSpace {plan.get('name','')} transformation is ready",
        "html": html,
    }
    if attachments:
        params["attachments"] = attachments
    try:
        resend.Emails.send(params)
    except Exception as e:
        logger.error(f"Resend customer email failed: {e}")

# ----- Routes -----
@api_router.get("/")
async def root():
    return {"message": "FlowSpace API"}

@api_router.get("/plans")
async def get_plans():
    return PLANS

# ===== AUTH =====
@api_router.post("/auth/session")
async def auth_session(request: Request, response: Response,
                       x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")):
    """Exchange an Emergent OAuth session_id (from URL fragment) for a backed
    session_token. Stores user + session, sets httpOnly cookie."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID header")
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(
                EMERGENT_SESSION_DATA_URL,
                headers={"X-Session-ID": x_session_id},
            )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Emergent session")
        data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergent /session-data failed: {e}")
        raise HTTPException(status_code=502, detail="Auth provider unreachable")

    email = (data.get("email") or "").lower().strip()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture") or None
    session_token = data.get("session_token") or secrets.token_urlsafe(32)
    if not email:
        raise HTTPException(status_code=400, detail="Missing email from auth provider")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture,
                      "last_login_at": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    })

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
        httponly=True,
        secure=True,
        samesite="none",
    )

    free_used = await _free_count_for_user(user_id)
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": _user_out(user_doc, free_used).model_dump()}

@api_router.get("/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(current_user)):
    free_used = await _free_count_for_user(user["user_id"])
    return _user_out(user, free_used).model_dump()

@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = _extract_session_token(request)
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", samesite="none", secure=True)
    return {"ok": True}


class DevLoginRequest(BaseModel):
    email: EmailStr
    password: str

@api_router.post("/auth/dev-login")
async def auth_dev_login(payload: DevLoginRequest, response: Response):
    """Dev-only username/password login for workflow testing.
    Disabled unless DEV_LOGIN_PASSWORD env var is set (i.e. preview only)."""
    if not DEV_LOGIN_PASSWORD:
        raise HTTPException(status_code=404, detail="Not found")
    if not secrets.compare_digest(payload.password, DEV_LOGIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid dev credentials")

    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": email.split("@")[0].replace(".", " ").title(),
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        })
        user = await db.users.find_one({"email": email}, {"_id": 0})
    else:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}},
        )

    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    })

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
        httponly=True,
        secure=True,
        samesite="none",
    )

    free_used = await _free_count_for_user(user["user_id"])
    return {"user": _user_out(user, free_used).model_dump()}

# ===== STRIPE =====
@api_router.post("/checkout/session", response_model=CheckoutCreateResponse)
async def create_checkout_session(payload: CheckoutCreateRequest, request: Request):
    if payload.plan_id not in PLANS or PLANS[payload.plan_id]["price"] <= 0:
        raise HTTPException(status_code=400, detail="Invalid paid plan")

    plan = PLANS[payload.plan_id]
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/#packages"
    metadata = {
        "plan_id": payload.plan_id,
        "customer_email": payload.customer_email or "",
        "customer_name": payload.customer_name or "",
    }
    req = CheckoutSessionRequest(
        amount=float(plan["price"]),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(req)

    doc = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "plan_id": payload.plan_id,
        "amount": float(plan["price"]),
        "currency": "usd",
        "customer_email": payload.customer_email or None,
        "customer_name": payload.customer_name or None,
        "payment_status": "pending",
        "status": "open",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(doc)

    return CheckoutCreateResponse(url=session.url, session_id=session.session_id)

@api_router.get("/checkout/status/{session_id}", response_model=CheckoutStatusOut)
async def get_checkout_status(session_id: str, request: Request):
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)

    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    plan_id = (existing or {}).get("plan_id") or status.metadata.get("plan_id")
    if existing and existing.get("payment_status") != status.payment_status:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "status": status.status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    return CheckoutStatusOut(
        status=status.status,
        payment_status=status.payment_status,
        plan_id=plan_id,
        amount_total=status.amount_total,
        currency=status.currency,
    )

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = await stripe_checkout.handle_webhook(body, sig)
        await db.payment_transactions.update_one(
            {"session_id": event.session_id},
            {"$set": {
                "payment_status": event.payment_status,
                "status": event.event_type,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=False,
        )
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook handling failed")
    return {"received": True}

async def _process_submission(sub_id: str, payload: SubmissionCreate, origin: str) -> None:
    """Background worker — runs after POST /api/submissions has already returned.
    Fills in AI 'after' images, PDF (Plus/Premium), then sends notification emails."""
    try:
        await db.submissions.update_one(
            {"id": sub_id},
            {"$set": {"status": "processing"}},
        )

        plan = PLANS[payload.plan_id]
        befores = [strip_data_url(p) for p in payload.photos_base64]

        # Generate each AI 'after' sequentially so we can update progress between photos
        results: List[Dict[str, str]] = []
        for idx, before in enumerate(befores):
            after = await generate_after_image(before)
            results.append({"before": before, "after": after or ""})
            await db.submissions.update_one(
                {"id": sub_id},
                {"$set": {"results": results, "photos_done": idx + 1}},
            )

        # PDF for paid plans
        pdf_b64 = ""
        design_plan: Optional[Dict[str, Any]] = None
        if plan["pdf"]:
            try:
                primary_after = next((r["after"] for r in results if r["after"]), "")
                design_plan = await generate_design_plan(
                    room_type=payload.room_type,
                    after_image_b64=primary_after or None,
                    user_notes=payload.notes,
                    budget=payload.budget,
                    api_key=EMERGENT_LLM_KEY,
                )
                main_img = primary_after or (results[0]["before"] if results else "")
                additional = [r["after"] or r["before"] for r in results[1:]]
                pdf_bytes = await asyncio.to_thread(
                    render_design_plan_pdf,
                    plan=design_plan,
                    main_image_b64=main_img,
                    additional_images=additional,
                    user_name=payload.name,
                )
                pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            except Exception as e:
                logger.error(f"PDF generation failed: {e}", exc_info=True)

        # Final write — mark completed
        final_set = {
            "status": "completed",
            "design_plan": design_plan,
            "pdf_base64": pdf_b64,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.submissions.update_one({"id": sub_id}, {"$set": final_set})

        # Mark payment transaction as used (kept for future paid-flow re-enable)
        if payload.session_id:
            await db.payment_transactions.update_one(
                {"session_id": payload.session_id},
                {"$set": {"submission_id": sub_id,
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
            )

        # Send emails (sync resend calls — already non-blocking from caller's perspective)
        doc = await db.submissions.find_one({"id": sub_id}, {"_id": 0})
        if doc:
            try:
                send_admin_email_sync(doc)
            except Exception as e:
                logger.error(f"admin email failed: {e}")
            try:
                send_customer_email_sync(doc, f"{origin.rstrip('/')}/result/{sub_id}")
            except Exception as e:
                logger.error(f"customer email failed: {e}")

    except Exception as e:
        logger.error(f"Submission processing crashed: {e}", exc_info=True)
        await db.submissions.update_one(
            {"id": sub_id},
            {"$set": {"status": "failed", "error": str(e)[:300]}},
        )


@api_router.post("/submissions", response_model=SubmissionOut)
async def create_submission(payload: SubmissionCreate, request: Request,
                            user: Dict[str, Any] = Depends(current_user)):
    """For FREE plan: validates user hasn't hit the 2-project cap, then creates
    a 'pending' submission and kicks off AI processing in the background.

    For PLUS/PREMIUM: creates an 'awaiting_payment' submission with all photos
    + form data stored, then returns a Stripe checkout URL. AI processing only
    begins after the payment success page calls /api/submissions/{id}/confirm-payment.
    """
    if payload.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    plan = PLANS[payload.plan_id]
    if len(payload.photos_base64) == 0:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if len(payload.photos_base64) > plan["max_photos"]:
        raise HTTPException(status_code=400, detail=f"Max {plan['max_photos']} photos for {plan['name']}")

    # Enforce free-plan cap
    if payload.plan_id == "free":
        used = await _free_count_for_user(user["user_id"])
        if used >= FREE_PROJECT_CAP:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"You've used your {FREE_PROJECT_CAP} free projects. "
                    "Upgrade to Plus or Premium to keep transforming rooms."
                ),
            )

    sub_id = str(uuid.uuid4())
    befores = [strip_data_url(p) for p in payload.photos_base64]
    initial_results = [{"before": b, "after": ""} for b in befores]

    # Paid plans wait for Stripe success before processing
    initial_status = "pending" if plan["price"] == 0 else "awaiting_payment"

    doc = {
        "id": sub_id,
        "user_id": user["user_id"],
        "plan_id": payload.plan_id,
        "name": payload.name,
        "email": payload.email,
        "room_type": payload.room_type,
        "notes": payload.notes,
        "budget": payload.budget,
        "session_id": None,
        "results": initial_results,
        "design_plan": None,
        "pdf_base64": "",
        "status": initial_status,
        "photos_total": len(befores),
        "photos_done": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.submissions.insert_one(doc)

    checkout_url: Optional[str] = None
    checkout_session_id: Optional[str] = None

    if plan["price"] > 0:
        # Create Stripe checkout, pin it to this submission via metadata
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        origin = (request.headers.get("origin") or host_url).rstrip("/")
        success_url = f"{origin}/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin}/upload/{payload.plan_id}?canceled=1&sub={sub_id}"
        metadata = {
            "plan_id": payload.plan_id,
            "submission_id": sub_id,
            "user_id": user["user_id"],
        }
        req = CheckoutSessionRequest(
            amount=float(plan["price"]),
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        session = await stripe_checkout.create_checkout_session(req)
        checkout_url = session.url
        checkout_session_id = session.session_id

        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "submission_id": sub_id,
            "user_id": user["user_id"],
            "plan_id": payload.plan_id,
            "amount": float(plan["price"]),
            "currency": "usd",
            "payment_status": "pending",
            "status": "open",
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.submissions.update_one(
            {"id": sub_id},
            {"$set": {"session_id": session.session_id}},
        )
    else:
        # FREE plan — start AI processing immediately
        origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
        task = asyncio.create_task(_process_submission(sub_id, payload, origin))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)

    return SubmissionOut(
        id=sub_id,
        plan_id=payload.plan_id,
        status=initial_status,
        room_type=payload.room_type,
        pdf_available=False,
        photos_total=len(befores),
        photos_done=0,
        checkout_url=checkout_url,
        checkout_session_id=checkout_session_id,
        results=[SubmissionPhotoOut(**r) for r in initial_results],
    )


@api_router.post("/submissions/{sub_id}/confirm-payment", response_model=SubmissionOut)
async def confirm_payment_and_start(sub_id: str, request: Request,
                                    user: Dict[str, Any] = Depends(current_user)):
    """Called by the success page once Stripe confirms paid. Verifies payment
    and kicks off AI processing for an awaiting_payment submission."""
    doc = await db.submissions.find_one({"id": sub_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if doc.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your submission")
    if doc.get("status") != "awaiting_payment":
        # Idempotent — return current state
        return SubmissionOut(
            id=doc["id"],
            plan_id=doc["plan_id"],
            status=doc.get("status", "completed"),
            room_type=doc.get("room_type"),
            pdf_available=bool(doc.get("pdf_base64")),
            photos_total=int(doc.get("photos_total") or 0),
            photos_done=int(doc.get("photos_done") or 0),
            error=doc.get("error"),
            results=[SubmissionPhotoOut(**r) for r in doc.get("results", [])],
        )

    # Verify payment via Stripe
    session_id = doc.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="No payment session attached")

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    if status.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment not yet complete")

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"payment_status": "paid", "status": status.status,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    await db.submissions.update_one(
        {"id": sub_id},
        {"$set": {"status": "pending"}},
    )

    # Kick off the background processing now
    payload = SubmissionCreate(
        name=doc.get("name"),
        email=doc.get("email"),
        plan_id=doc["plan_id"],
        room_type=doc.get("room_type"),
        notes=doc.get("notes"),
        budget=doc.get("budget"),
        photos_base64=[r["before"] for r in doc.get("results", [])],
        session_id=session_id,
    )
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    task = asyncio.create_task(_process_submission(sub_id, payload, origin))
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

    return SubmissionOut(
        id=sub_id,
        plan_id=doc["plan_id"],
        status="pending",
        room_type=doc.get("room_type"),
        pdf_available=False,
        photos_total=int(doc.get("photos_total") or 0),
        photos_done=0,
        results=[SubmissionPhotoOut(**r) for r in doc.get("results", [])],
    )


@api_router.get("/submissions")
async def list_my_submissions(user: Dict[str, Any] = Depends(current_user)):
    """List the signed-in user's projects, newest first. No photo binaries in the list."""
    cursor = db.submissions.find(
        {"user_id": user["user_id"]},
        {"_id": 0, "results": 0, "pdf_base64": 0, "design_plan": 0},
    ).sort("created_at", -1).limit(60)
    items = []
    async for d in cursor:
        items.append({
            "id": d["id"],
            "plan_id": d["plan_id"],
            "status": d.get("status", "completed"),
            "room_type": d.get("room_type"),
            "photos_total": d.get("photos_total", 0),
            "photos_done": d.get("photos_done", 0),
            "created_at": d.get("created_at"),
        })
    return {"items": items}

@api_router.get("/submissions/{sub_id}", response_model=SubmissionOut)
async def get_submission(sub_id: str, user: Optional[Dict[str, Any]] = Depends(optional_user)):
    doc = await db.submissions.find_one({"id": sub_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    # Enforce ownership for non-public access (allow if unauth or matching user)
    if doc.get("user_id") and user and doc["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your submission")
    return SubmissionOut(
        id=doc["id"],
        plan_id=doc["plan_id"],
        status=doc.get("status", "completed"),
        room_type=doc.get("room_type"),
        pdf_available=bool(doc.get("pdf_base64")),
        photos_total=int(doc.get("photos_total") or len(doc.get("results", []))),
        photos_done=int(doc.get("photos_done") or 0),
        error=doc.get("error"),
        checkout_url=None,
        checkout_session_id=doc.get("session_id"),
        results=[SubmissionPhotoOut(**r) for r in doc.get("results", [])],
    )

@api_router.get("/submissions/{sub_id}/pdf")
async def download_submission_pdf(sub_id: str):
    doc = await db.submissions.find_one({"id": sub_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if doc.get("plan_id") not in ("plus", "premium"):
        raise HTTPException(
            status_code=402,
            detail="Upgrade to Plus or Premium to unlock your full PDF Design Plan.",
        )
    pdf_b64 = doc.get("pdf_base64") or ""
    if not pdf_b64:
        raise HTTPException(status_code=404, detail="PDF not yet generated")
    pdf_bytes = base64.b64decode(pdf_b64)
    room_key = (doc.get("design_plan") or {}).get("room_key", "Room")
    room_pretty = (doc.get("room_type") or room_key or "Room").title().replace(" ", "-")
    filename = f"FlowSpace-{room_pretty}-Design-Plan.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
