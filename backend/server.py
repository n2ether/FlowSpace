from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from gridfs.errors import NoFile
from pymongo.errors import DuplicateKeyError
import base64
import io
import os
import logging
import asyncio
import zipfile
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Any, Dict, List, Optional, Tuple
import uuid
from datetime import datetime, timezone

import stripe as stripe_sdk
import httpx

from image_board import build_image_board
from room_flow import build_zone_map, outline_caption
from blueprint_consistency import internal_record, prepare_deliverable, project_story_line
from blueprint_presentation import build_presentation
from design_plan_standards import is_released, package_version, version_tag
from pdf_generator import build_pdf, customer_project_title, plan_title
from pdf_images import assemble_pdf_images, choose_hero
from contact_sheet import build_contact_sheet
from email_service import email_body_html, send_blueprint, send_contact_sheet, send_draft_package
from source_photos import draft_send_block_reason, final_email_block_reason, mapping_is_own_source
from blueprint_layers import coerce_layers
from ai_drafter import draft_deliverable
from ai_image_generator import generate_front_view, refine_after_image
from rug_refine import describe_rug, refine_one, resolve_refine_rug
from automation import run_automation
from image_orientation import UnreadableImage, is_heif_upload, normalize_photo_bytes, upright_bytes
from admin_session import create_admin_token, password_matches, verify_admin_token
from photo_access import (
    PHOTO_URL_PREFIX,
    canonicalize_photo_urls,
    gridfs_key,
    photo_id_from_url,
    sign_photo_urls,
    signed_photo_url,
    store_photo,
    upload_token,
    verify_signature,
    verify_upload_token,
)
from fulfillment import checkout_lead_lookups, should_auto_start_automation
from intake import IntakeError, build_fact_sheet, chargeable_block_reason, validate_intake
from auth import (
    COOKIE_NAME,
    cookie_kwargs,
    create_token,
    decode_token,
    extract_token,
    normalize_email,
    validate_password,
    verify_password,
)
from members import (
    claim_leads_for_email,
    ensure_member_indexes,
    free_limit_error,
    is_free_package,
    new_member_doc,
    public_member,
    public_plan,
    public_space,
    usage_for_member,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="uploads")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

STRIPE_API_KEY      = os.environ.get("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
ADMIN_PASSWORD      = os.environ.get("ADMIN_PASSWORD", "flowspace2025")

PACKAGES: Dict[str, Dict[str, Any]] = {
    "free":    {"id": "free",    "name": "Free",    "price": 0.0,   "currency": "usd", "max_photos": 2},
    "plus":    {"id": "plus",    "name": "Plus",    "price": 10.0,  "currency": "usd", "max_photos": 3},
    "premium": {"id": "premium", "name": "Premium", "price": 20.0,  "currency": "usd", "max_photos": 4},
}

STARTER_GALLERY = [
    {
        "id": str(uuid.uuid4()),
        "title": "Closet — Calm and categorized",
        "category": "closet",
        "before_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=1400&q=80",
        "after_url":  "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?auto=format&fit=crop&w=1400&q=80",
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Garage — Workshop reset",
        "category": "garage",
        "before_url": "https://images.unsplash.com/photo-1570129476815-ba368ac77013?auto=format&fit=crop&w=1400&q=80",
        "after_url":  "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1400&q=80",
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Pantry — Categorized storage",
        "category": "storage",
        "before_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?auto=format&fit=crop&w=1400&q=80",
        "after_url":  "https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=1400&q=80",
    },
]

app = FastAPI(title="FlowSpace API")
api_router = APIRouter(prefix="/api")


# ──────────────────────────── Models ─────────────────────────────
class Lead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    phone: Optional[str] = None
    space_type: str
    package_id: Optional[str] = None
    biggest_challenge: Optional[str] = None
    goals: Optional[str] = None
    timeline: Optional[str] = None
    photos: List[Any] = []
    bothers_about: List[str] = []
    bothers_other: Optional[str] = None
    desired_feeling: List[str] = []
    feeling_other: Optional[str] = None
    must_stay: Optional[str] = None
    storage_needs: List[str] = []
    style_prefs: List[str] = []
    color_prefs: List[str] = []
    budget: Optional[str] = None
    diy_level: Optional[str] = None
    daily_improvement: Optional[str] = None
    language: str = "en"
    intake: Optional[Dict[str, Any]] = None
    fact_sheet: Optional[Dict[str, Any]] = None
    status: str = "new"
    member_id: Optional[str] = None
    stripe_session_id: Optional[str] = None
    email_sent: Optional[bool] = None
    email_error: Optional[str] = None
    automation_error: Optional[str] = None
    automation_failed: Optional[bool] = None
    automation_failed_at: Optional[str] = None
    package_status: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    space_type: str
    package_id: Optional[str] = None
    biggest_challenge: Optional[str] = None
    goals: Optional[str] = None
    timeline: Optional[str] = None
    photos: List[Any] = []
    bothers_about: List[str] = []
    bothers_other: Optional[str] = None
    desired_feeling: List[str] = []
    feeling_other: Optional[str] = None
    must_stay: Optional[str] = None
    storage_needs: List[str] = []
    style_prefs: List[str] = []
    color_prefs: List[str] = []
    budget: Optional[str] = None
    diy_level: Optional[str] = None
    daily_improvement: Optional[str] = None
    language: str = "en"
    intake: Optional[Dict[str, Any]] = None
    password: Optional[str] = None


class MemberSignup(BaseModel):
    name: str
    email: EmailStr
    password: str


class MemberLogin(BaseModel):
    email: EmailStr
    password: str


class GalleryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: str
    before_url: str
    after_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GalleryCreate(BaseModel):
    title: str
    category: str
    before_url: str
    after_url: str


class AdminLoginRequest(BaseModel):
    password: str


class CheckoutRequest(BaseModel):
    package_id: str
    origin_url: str
    email: Optional[EmailStr] = None
    metadata: Optional[Dict[str, str]] = None


class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    package_id: str
    amount: float
    currency: str
    email: Optional[str] = None
    lead_id: Optional[str] = None
    payment_status: str = "initiated"
    status: str = "open"
    metadata: Dict[str, str] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShoppingItem(BaseModel):
    name: str
    qty: float = 1
    price: float = 0
    # "functional" or "decorative" (optional styling). Empty means classify by name.
    priority: Optional[str] = None


class Zone(BaseModel):
    title: str
    desc: str = ""


class ShoppingLink(BaseModel):
    name: str
    url: str = ""
    retailer: str = ""
    link_type: str = ""  # "product" or "search"
    label: str = ""


class Deliverable(BaseModel):
    lead_id: str
    intro: Optional[str] = None
    needs: List[str] = []
    zones: List[Zone] = []
    wall_color_name: Optional[str] = None
    wall_color_code: Optional[str] = None
    wall_color_hex: Optional[str] = None
    wall_color_note: Optional[str] = None
    shopping_list: List[ShoppingItem] = []
    budget_note: Optional[str] = None
    strategy: List[str] = []
    action_plan: List[str] = []
    benefits: List[str] = []
    notes: Optional[str] = None
    summary: Optional[str] = None
    attachment_note: Optional[str] = None
    shopping_links: List[ShoppingLink] = []
    front_view_url: Optional[str] = None
    floor_plan_url: Optional[str] = None
    view_1_url: Optional[str] = None
    view_2_url: Optional[str] = None
    view_3_url: Optional[str] = None
    source_afters: List[Dict[str, Any]] = []
    non_room_uploads: List[Dict[str, Any]] = []
    package_status: Optional[str] = None
    # Missing means version 1. The number advances on regenerate only after this
    # copy has been emailed for review (see sent_for_review).
    package_version: Optional[int] = None
    # Highest package_version successfully emailed by send-draft or send-final.
    # Missing means nothing has been sent, so regenerate keeps preparing Versão 2.
    sent_for_review: Optional[int] = None
    # Reviewer sign-off on the Design Plan. Until set, every surface reads DRAFT / REVIEW.
    design_plan_approved: bool = False
    contact_sheet_url: Optional[str] = None
    include_customer_photos: bool = True
    blueprint_layers: Optional[Dict[str, Any]] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────── Helpers ─────────────────────────────
def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _stripe_dict(obj: Any) -> Dict[str, Any]:
    """Plain dict from a Stripe object or dict.

    stripe>=15 objects are no longer dict subclasses: ``.items()``, ``.get()``
    and ``dict(obj)`` all fail. ``to_dict()`` is the supported accessor.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        out = to_dict()
        return out if isinstance(out, dict) else {}
    return {}


def _safe_metadata(sess: Any) -> Dict[str, str]:
    """String metadata from a Stripe checkout session (object or dict)."""
    if isinstance(sess, dict):
        raw = sess.get("metadata")
    else:
        raw = getattr(sess, "metadata", None)
    try:
        data = _stripe_dict(raw)
        return {str(k): str(v) for k, v in data.items() if v is not None}
    except Exception:
        logging.warning("Could not parse Stripe metadata safely; defaulting to {}")
        return {}


def _doc(model: BaseModel) -> dict:
    d = model.model_dump()
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = _iso(v)
    return d


def _hydrate(doc: dict, dt_fields: List[str]) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for f in dt_fields:
        if f in doc and isinstance(doc[f], str):
            try:
                doc[f] = datetime.fromisoformat(doc[f])
            except Exception:
                pass
    return doc


def is_admin_token(token: Optional[str]) -> bool:
    """A session token from /admin/login. The raw password is still accepted for
    existing API scripts, but is no longer handed to the browser."""
    return verify_admin_token(token) or password_matches(token, ADMIN_PASSWORD)


async def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> bool:
    if not is_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


def _cors_origins() -> List[str]:
    """Explicit origins only — browsers reject Access-Control-Allow-Origin: * with cookies."""
    raw = (os.environ.get("CORS_ORIGINS") or "").strip()
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://flowspace.solutions",
        "https://www.flowspace.solutions",
    ]
    if not raw or raw == "*":
        return defaults
    origins = [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
    return origins or defaults


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, **cookie_kwargs())


def _clear_session_cookie(response: Response) -> None:
    kwargs = cookie_kwargs()
    response.delete_cookie(
        COOKIE_NAME,
        path=kwargs.get("path", "/"),
        samesite=kwargs.get("samesite"),
        secure=kwargs.get("secure"),
        httponly=True,
    )


async def optional_member(request: Request) -> Optional[Dict[str, Any]]:
    token = extract_token(request)
    payload = decode_token(token) if token else None
    if not payload or not payload.get("sub"):
        return None
    member = await db.members.find_one({"id": payload["sub"]}, {"_id": 0})
    return member


async def require_member(request: Request) -> Dict[str, Any]:
    member = await optional_member(request)
    if not member:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "ACCOUNT_REQUIRED",
                "message": "Log in or create a free account to continue.",
            },
        )
    return member


async def _usage_for(member_id: str) -> Dict[str, Any]:
    return await usage_for_member(db, member_id, PACKAGES)


async def _auth_payload(member: Dict[str, Any], token: str, claimed_spaces: int = 0) -> Dict[str, Any]:
    usage = await _usage_for(member["id"])
    return {
        "token": token,
        "member": public_member(member, usage),
        "claimed_spaces": claimed_spaces,
    }


async def _signup_or_authenticate(
    *,
    name: str,
    email: str,
    password: str,
    allow_login: bool,
) -> tuple:
    """Create a member or, when allow_login=True, sign them in if the email exists."""
    email_n = normalize_email(email)
    existing = await db.members.find_one({"email": email_n}, {"_id": 0})
    if existing:
        if not allow_login:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "EMAIL_IN_USE",
                    "message": "An account with this email already exists. Log in to continue.",
                },
            )
        if not verify_password(password, existing.get("password_hash") or ""):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid email or password.",
                },
            )
        claimed = await claim_leads_for_email(db, existing["id"], email_n)
        token = create_token(existing["id"], existing["email"])
        return existing, token, claimed

    pw_err = validate_password(password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)
    doc = new_member_doc(name, email_n, password)
    await db.members.insert_one(doc)
    claimed = await claim_leads_for_email(db, doc["id"], email_n)
    token = create_token(doc["id"], doc["email"])
    return doc, token, claimed


async def _resolve_member_for_lead(
    payload: "LeadCreate",
    request: Request,
    response: Response,
) -> Dict[str, Any]:
    member = await optional_member(request)
    if member:
        return member
    if payload.password:
        member, token, _ = await _signup_or_authenticate(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            allow_login=True,
        )
        _set_session_cookie(response, token)
        return member
    raise HTTPException(
        status_code=401,
        detail={
            "code": "ACCOUNT_REQUIRED",
            "message": "Create a free account (or log in) to keep this plan and start your Blueprint.",
        },
    )


async def seed_gallery_if_empty():
    count = await db.gallery.count_documents({})
    if count == 0:
        for item in STARTER_GALLERY:
            doc = {**item, "created_at": _iso(datetime.now(timezone.utc))}
            await db.gallery.insert_one(doc)


async def _find_lead_for_checkout(
    *,
    metadata: Optional[Dict[str, Any]] = None,
    customer_email: Optional[str] = None,
    transaction_lead_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve the customer lead for a paid Stripe session. Prefer lead_id over email."""
    for reason, query in checkout_lead_lookups(
        metadata=metadata,
        customer_email=customer_email,
        transaction_lead_id=transaction_lead_id,
    ):
        lead = await db.leads.find_one(query, {"_id": 0})
        if lead:
            logging.info("Matched lead %s for checkout via %s", lead.get("id"), reason)
            return lead
    return None


async def _start_automation_for_lead(
    lead: Dict[str, Any],
    background_tasks: BackgroundTasks,
    extra_fields: Optional[Dict[str, Any]] = None,
    *,
    force: bool = False,
) -> bool:
    """
    Claim the lead and queue the Claude → OpenAI image → board + PDF → Resend pipeline.

    Skips if the lead is already processing/delivered unless force=True (admin retry).
    """
    extra_fields = extra_fields or {}
    lead_id = lead.get("id")
    if not lead_id:
        return False
    now = _iso(datetime.now(timezone.utc))
    query: Dict[str, Any] = {"id": lead_id}
    if not force and not should_auto_start_automation(lead.get("status")):
        logging.info("Skipping automation for lead %s — status=%s", lead_id, lead.get("status"))
        return False
    if not force:
        query["status"] = {"$nin": ["processing", "delivered", "review", "incomplete"]}
    res = await db.leads.update_one(
        query,
        {"$set": {**extra_fields, "status": "processing", "updated_at": now}},
    )
    if res.matched_count == 0:
        logging.info("Skipping automation for lead %s — already in flight or delivered", lead_id)
        return False
    queued = {**lead, **extra_fields, "status": "processing"}
    background_tasks.add_task(run_automation, lead=queued, db=db, fs_bucket=fs_bucket)
    logging.info("Automation queued for lead %s", lead_id)
    return True


async def _fulfill_paid_checkout(
    *,
    session_id: str,
    metadata: Dict[str, str],
    customer_email: Optional[str],
    background_tasks: BackgroundTasks,
    payment_status: str = "paid",
    stripe_status: str = "complete",
) -> None:
    """Link a paid Stripe session to its lead and start PDF email automation.

    Fulfillment runs at most once per session_id: the webhook, its retries and
    the success-page poll all race to claim ``checkout_fulfillments`` (unique
    on session_id) and only the winner queues automation.
    """
    existing_tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "payment_status": payment_status,
                "status": stripe_status,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
    )
    if payment_status != "paid":
        return

    if not await _claim_fulfillment(session_id):
        logging.info("Checkout %s already fulfilled — skipping", session_id)
        return

    try:
        lead = await _find_lead_for_checkout(
            metadata=metadata,
            customer_email=customer_email,
            transaction_lead_id=(existing_tx or {}).get("lead_id"),
        )
        if not lead:
            logging.warning(
                "Paid checkout %s has no matching lead (email=%s metadata_lead_id=%s tx_lead_id=%s)",
                session_id,
                customer_email,
                (metadata or {}).get("lead_id"),
                (existing_tx or {}).get("lead_id"),
            )
            # Release so a later trigger can match the lead once it exists.
            await db.checkout_fulfillments.delete_one({"session_id": session_id})
            return

        pkg = (metadata or {}).get("package_id") or lead.get("package_id") or ""
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"lead_id": lead["id"]}},
        )
        await db.checkout_fulfillments.update_one(
            {"session_id": session_id},
            {"$set": {"lead_id": lead["id"]}},
        )
        await _start_automation_for_lead(
            lead,
            background_tasks,
            extra_fields={
                "stripe_session_id": session_id,
                "package_id": pkg,
            },
        )
    except Exception:
        await db.checkout_fulfillments.delete_one({"session_id": session_id})
        raise


async def _claim_fulfillment(session_id: str) -> bool:
    try:
        await db.checkout_fulfillments.insert_one(
            {"session_id": session_id, "claimed_at": _iso(datetime.now(timezone.utc))}
        )
    except DuplicateKeyError:
        return False
    return True


async def _record_stripe_event(event_id: str, event_type: str) -> bool:
    """Persist a Stripe event id; False when it was already processed."""
    try:
        await db.stripe_events.insert_one(
            {"event_id": event_id, "type": event_type, "received_at": _iso(datetime.now(timezone.utc))}
        )
    except DuplicateKeyError:
        return False
    return True


async def _mark_checkout_unpaid(session_id: str, outcome: str) -> None:
    """Record an expired or failed checkout. Never downgrades a paid transaction."""
    await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {
            "$set": {
                "payment_status": outcome,
                "status": outcome,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
    )


async def ensure_payment_indexes(database) -> None:
    try:
        await database.stripe_events.create_index("event_id", unique=True)
        await database.checkout_fulfillments.create_index("session_id", unique=True)
    except Exception as e:
        logging.warning("Could not create payment idempotency indexes: %s", e)


async def _resolve_image_bytes(url: Optional[str], request: Request) -> Optional[bytes]:
    if not url:
        return None
    try:
        if url.startswith(PHOTO_URL_PREFIX):
            key = gridfs_key(photo_id_from_url(url))
            if key is None:
                return None
            try:
                stream = await fs_bucket.open_download_stream(key)
            except NoFile:
                return None
            return upright_bytes(await stream.read())
        if url.startswith("http://") or url.startswith("https://"):
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as ac:
                r = await ac.get(url)
                r.raise_for_status()
                return upright_bytes(r.content)
    except Exception as e:
        logging.warning(f"image fetch failed for {url}: {e}")
    return None


# ──────────────────────────── Public Routes ─────────────────────────────
@api_router.get("/")
async def root():
    return {"message": "FlowSpace API", "status": "ok"}


@api_router.get("/packages")
async def get_packages():
    return {"packages": list(PACKAGES.values())}


@api_router.post("/auth/signup")
async def member_signup(payload: MemberSignup, response: Response):
    member, token, claimed = await _signup_or_authenticate(
        name=payload.name,
        email=str(payload.email),
        password=payload.password,
        allow_login=False,
    )
    _set_session_cookie(response, token)
    return await _auth_payload(member, token, claimed)


@api_router.post("/auth/login")
async def member_login(payload: MemberLogin, response: Response):
    email_n = normalize_email(str(payload.email))
    member = await db.members.find_one({"email": email_n}, {"_id": 0})
    if not member or not verify_password(payload.password, member.get("password_hash") or ""):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."},
        )
    claimed = await claim_leads_for_email(db, member["id"], email_n)
    token = create_token(member["id"], member["email"])
    _set_session_cookie(response, token)
    return await _auth_payload(member, token, claimed)


@api_router.post("/auth/logout")
async def member_logout(response: Response):
    _clear_session_cookie(response)
    return {"ok": True}


@api_router.get("/auth/me")
async def member_me(member: Dict[str, Any] = Depends(require_member)):
    usage = await _usage_for(member["id"])
    return public_member(member, usage)


@api_router.get("/me/spaces")
async def my_spaces(member: Dict[str, Any] = Depends(require_member)):
    leads = (
        await db.leads.find({"member_id": member["id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(500)
    )
    lead_ids = [lead.get("id") for lead in leads if lead.get("id")]
    deliverables = []
    if lead_ids:
        deliverables = await db.deliverables.find(
            {"lead_id": {"$in": lead_ids}}, {"_id": 0}
        ).to_list(500)
    by_lead = {d.get("lead_id"): d for d in deliverables}
    return {
        "spaces": [public_space(lead, by_lead.get(lead.get("id"))) for lead in leads],
        "usage": await _usage_for(member["id"]),
    }


async def _member_plan_or_404(lead_id: str, member: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The member's own lead and its deliverable. Someone else's lead reads as missing, not forbidden."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead or not member.get("id") or lead.get("member_id") != member["id"]:
        raise HTTPException(status_code=404, detail="Plan not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Plan not found")
    return lead, d


@api_router.get("/me/spaces/{lead_id}/plan")
async def my_space_plan(lead_id: str, member: Dict[str, Any] = Depends(require_member)):
    """Read-only plan for the owner. Never emails anyone or changes the lead status."""
    lead, d = await _member_plan_or_404(lead_id, member)
    return sign_photo_urls(public_plan(lead, d))


def check_lead_intake(data: Dict[str, Any]) -> None:
    """Reject over-cap photos and, for the beta intake, any answer the browser should have caught."""
    pkg = PACKAGES.get(data.get("package_id") or "free") or PACKAGES["free"]
    photos = data.get("photos") or []
    if len(photos) > pkg["max_photos"]:
        raise HTTPException(
            status_code=422,
            detail=IntakeError(
                "INTAKE_INVALID",
                f"The {pkg['name']} plan includes up to {pkg['max_photos']} photos.",
                [{"field": "photos", "message": f"The {pkg['name']} plan includes up to {pkg['max_photos']} photos."}],
            ).as_detail(),
        )
    intake = data.get("intake")
    if not intake:
        return
    errors = validate_intake(intake, package=pkg, photos=photos)
    if errors:
        only_photos = all(e["field"] == "photos" for e in errors)
        code = "PHOTO_REQUIRED" if only_photos else "INTAKE_INVALID"
        raise HTTPException(
            status_code=422,
            detail=IntakeError(code, errors[0]["message"], errors).as_detail(),
        )


@api_router.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate, request: Request, response: Response, background_tasks: BackgroundTasks):
    """
    Create a lead owned by a member account.
    - Free tier (or no package selected): fire the automation pipeline immediately
      unless the member has already used their one free generation.
    - Paid tier: return the lead, frontend then creates a Stripe checkout session
    """
    if payload.package_id and payload.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package_id")
    check_lead_intake(canonicalize_photo_urls(payload.model_dump(exclude={"password"})))

    member = await _resolve_member_for_lead(payload, request, response)
    usage = await _usage_for(member["id"])
    free = is_free_package(payload.package_id, PACKAGES)
    if free and not usage["can_generate_free"]:
        raise HTTPException(status_code=403, detail=free_limit_error(usage["free_generations_used"]))

    data = canonicalize_photo_urls(payload.model_dump(exclude={"password"}))
    data["email"] = normalize_email(str(member.get("email") or data.get("email") or ""))
    if member.get("name") and not (data.get("name") or "").strip():
        data["name"] = member["name"]
    data["member_id"] = member["id"]
    if data.get("intake"):
        data["fact_sheet"] = build_fact_sheet(data)
    lead = Lead(**data)
    await db.leads.insert_one(_doc(lead))

    if free:
        await _start_automation_for_lead(_doc(lead), background_tasks)

    return sign_photo_urls(_doc(lead))


@api_router.get("/gallery", response_model=List[GalleryItem])
async def list_gallery():
    await seed_gallery_if_empty()
    items = await db.gallery.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_hydrate(sign_photo_urls(it), ["created_at"]) for it in items]


# ──────────────────────────── Uploads (GridFS) ─────────────────────────────
def _upload_filename(name: Optional[str]) -> str:
    stem = Path(name or "upload").stem or "upload"
    return f"{stem}.jpg"


@api_router.post("/uploads/photo")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    """Store an upright JPEG under an unguessable id.

    Anonymous intake can upload. The response carries a short-lived signed
    ``url`` for the preview and an ``upload_token`` that lets the same browser
    refresh that preview later; nobody else can read the photo.
    """
    ct = (file.content_type or "").lower()
    heif = is_heif_upload(ct, file.filename)
    if not ct.startswith("image/") and not heif:
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    try:
        contents, orientation = normalize_photo_bytes(contents)
        ct = orientation.get("content_type") or "image/jpeg"
    except UnreadableImage:
        raise HTTPException(status_code=400, detail="Could not read image")
    member = await optional_member(request)
    metadata: Dict[str, Any] = {
        "content_type": ct,
        "uploaded_at": _iso(datetime.now(timezone.utc)),
        "orientation_normalized": True,
        "exif_orientation": orientation.get("exif_orientation"),
        "applied_exif": bool(orientation.get("applied")),
        "width": orientation.get("width"),
        "height": orientation.get("height"),
        "original_content_type": (file.content_type or "").lower(),
        "converted_from_heif": heif,
    }
    if member:
        metadata["member_id"] = member["id"]
    stored_url = await store_photo(
        fs_bucket,
        filename=_upload_filename(file.filename),
        data=contents,
        metadata=metadata,
    )
    photo_id = photo_id_from_url(stored_url)
    return {
        "id": photo_id,
        "url": signed_photo_url(stored_url),
        "stored_url": stored_url,
        "upload_token": upload_token(photo_id),
        "orientation": {
            "exif_orientation": orientation.get("exif_orientation"),
            "applied": bool(orientation.get("applied")),
            "width": orientation.get("width"),
            "height": orientation.get("height"),
            "is_landscape": bool(orientation.get("is_landscape")),
        },
    }


class PhotoPreviewRequest(BaseModel):
    upload_token: str


@api_router.post("/uploads/photo/{photo_id}/preview")
async def refresh_photo_preview(photo_id: str, payload: PhotoPreviewRequest):
    """A fresh signed preview URL for the browser that uploaded this photo."""
    if gridfs_key(photo_id) is None or not verify_upload_token(photo_id, payload.upload_token):
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": photo_id, "url": signed_photo_url(f"{PHOTO_URL_PREFIX}{photo_id}")}


async def _member_can_read_photo(request: Request, photo_id: str, metadata: Dict[str, Any]) -> bool:
    member = await optional_member(request)
    if not member or not member.get("id"):
        return False
    member_id = member["id"]
    if metadata.get("member_id") == member_id:
        return True
    lead_id = metadata.get("lead_id")
    if lead_id and await db.leads.find_one({"id": lead_id, "member_id": member_id}, {"_id": 0, "id": 1}):
        return True
    url = f"{PHOTO_URL_PREFIX}{photo_id}"
    for query in ({"member_id": member_id, "photos": url}, {"member_id": member_id, "photos.url": url}):
        if await db.leads.find_one(query, {"_id": 0, "id": 1}):
            return True
    return False


@api_router.get("/uploads/photo/{photo_id}")
async def get_photo(
    photo_id: str,
    request: Request,
    exp: Optional[str] = None,
    sig: Optional[str] = None,
    x_admin_token: Optional[str] = Header(default=None),
):
    """Serve a photo to a signed URL, an admin, or the member who owns it. Never public."""
    key = gridfs_key(photo_id)
    if key is None:
        raise HTTPException(status_code=400, detail="Invalid id")
    signed = verify_signature(photo_id, exp, sig)
    try:
        stream = await fs_bucket.open_download_stream(key)
    except NoFile:
        raise HTTPException(status_code=404, detail="Not found")
    metadata = dict(getattr(stream, "metadata", None) or {})
    if not (signed or is_admin_token(x_admin_token) or await _member_can_read_photo(request, photo_id, metadata)):
        # Same answer as a missing file so ids cannot be probed.
        raise HTTPException(status_code=404, detail="Not found")
    data = await stream.read()
    media = metadata.get("content_type", "image/jpeg")
    return Response(
        content=data,
        media_type=media,
        headers={
            "Cache-Control": "private, max-age=3600" if signed else "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ──────────────────────────── Admin Routes ─────────────────────────────
@api_router.post("/admin/login")
async def admin_login(payload: AdminLoginRequest):
    if not password_matches(payload.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": create_admin_token(), "token_type": "admin_session"}


@api_router.get("/admin/leads", response_model=List[Lead])
async def admin_leads(_: bool = Depends(require_admin)):
    items = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return [_hydrate(sign_photo_urls(it), ["created_at"]) for it in items]


@api_router.post("/admin/leads/{lead_id}/retry-automation")
async def retry_automation(lead_id: str, background_tasks: BackgroundTasks, _: bool = Depends(require_admin)):
    """Manually trigger the full automation pipeline for a lead (retry or re-send)."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await _start_automation_for_lead(lead, background_tasks, force=True)
    return {"message": "Automation started", "lead_id": lead_id}


@api_router.post("/admin/gallery", response_model=GalleryItem)
async def admin_add_gallery(payload: GalleryCreate, _: bool = Depends(require_admin)):
    item = GalleryItem(**payload.model_dump())
    await db.gallery.insert_one(_doc(item))
    return item


@api_router.delete("/admin/gallery/{item_id}")
async def admin_delete_gallery(item_id: str, _: bool = Depends(require_admin)):
    res = await db.gallery.delete_one({"id": item_id})
    return {"deleted": res.deleted_count}


@api_router.get("/admin/transactions")
async def admin_transactions(_: bool = Depends(require_admin)):
    items = (
        await db.payment_transactions.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(2000)
    )
    return [_hydrate(it, ["created_at", "updated_at"]) for it in items]


# ──────────────────────────── Deliverable / PDF ─────────────────────────────
@api_router.get("/admin/leads/{lead_id}/deliverable")
async def get_deliverable(lead_id: str, _: bool = Depends(require_admin)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0})
    if d:
        d = _hydrate(sign_photo_urls(d), ["updated_at"])
    return {"lead": _hydrate(sign_photo_urls(lead), ["created_at"]), "deliverable": d}


@api_router.put("/admin/leads/{lead_id}/deliverable", response_model=Deliverable)
async def upsert_deliverable(lead_id: str, payload: Deliverable, _: bool = Depends(require_admin)):
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    payload.lead_id = lead_id
    payload.updated_at = datetime.now(timezone.utc)
    if payload.blueprint_layers:
        payload.blueprint_layers = coerce_layers(payload.blueprint_layers)
    doc = canonicalize_photo_urls(_doc(payload))
    await db.deliverables.update_one({"lead_id": lead_id}, {"$set": doc}, upsert=True)
    return sign_photo_urls(doc)


@api_router.post("/admin/leads/{lead_id}/deliverable/draft")
async def ai_draft_deliverable(lead_id: str, _: bool = Depends(require_admin)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    reference_photo_bytes = None
    first_photo = (lead.get("photos") or [None])[0]
    if first_photo:
        photo_url = first_photo if isinstance(first_photo, str) else first_photo.get("url")
        reference_photo_bytes = await _resolve_image_bytes(photo_url, None)
    try:
        plan = await draft_deliverable(lead, reference_photo_bytes=reference_photo_bytes)
    except Exception as e:
        logging.exception("AI draft failed")
        raise HTTPException(status_code=502, detail=f"AI draft failed: {e}")
    return {"draft": plan}


@api_router.post("/admin/leads/{lead_id}/deliverable/generate-image")
async def ai_generate_image(lead_id: str, slot: str = "front_view", _: bool = Depends(require_admin)):
    valid_slots = {"front_view", "view_1", "view_2", "view_3", "floor_plan"}
    if slot not in valid_slots:
        raise HTTPException(status_code=400, detail=f"Invalid slot. Use: {sorted(valid_slots)}")
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    deliverable = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}

    reference_photo_bytes = None
    first_photo = (lead.get("photos") or [None])[0]
    if first_photo:
        photo_url = first_photo if isinstance(first_photo, str) else first_photo.get("url")
        if photo_url and PHOTO_URL_PREFIX in photo_url:
            try:
                stream = await fs_bucket.open_download_stream(gridfs_key(photo_id_from_url(photo_url)))
                reference_photo_bytes = upright_bytes(await stream.read())
            except Exception:
                reference_photo_bytes = None

    try:
        png_bytes, mime = await generate_front_view(
            lead=lead,
            deliverable=deliverable,
            fs_bucket=fs_bucket,
            reference_photo_bytes=reference_photo_bytes,
        )
    except Exception as e:
        logging.exception("AI image generation failed")
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}")
    ext = "jpg" if "jpeg" in (mime or "") else "png"
    url = await store_photo(
        fs_bucket,
        filename=f"ai_{slot}_{lead_id}.{ext}",
        data=png_bytes,
        metadata={"content_type": mime or "image/png", "uploaded_at": _iso(datetime.now(timezone.utc)), "source": "ai", "lead_id": lead_id, "slot": slot},
    )
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {"$set": {f"{slot}_url": url, "lead_id": lead_id, "updated_at": _iso(datetime.now(timezone.utc))}},
        upsert=True,
    )
    return {"slot": slot, "url": signed_photo_url(url), "stored_url": url}


async def _blueprint_render_inputs(lead_id: str, request: Request):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {"lead_id": lead_id}
    fetched = {
        "front_view": await _resolve_image_bytes(d.get("front_view_url"), request),
        "floor_plan": await _resolve_image_bytes(d.get("floor_plan_url"), request),
        "view_1": await _resolve_image_bytes(d.get("view_1_url"), request),
        "view_2": await _resolve_image_bytes(d.get("view_2_url"), request),
        "view_3": await _resolve_image_bytes(d.get("view_3_url"), request),
    }
    customer_photos = []
    if d.get("include_customer_photos", True):
        for p in (lead.get("photos") or [])[:8]:
            url = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
            b = await _resolve_image_bytes(url, request)
            if b:
                customer_photos.append(b)
    first_original = customer_photos[0] if customer_photos else None
    if not first_original:
        first_photo = (lead.get("photos") or [None])[0]
        if first_photo:
            url = first_photo if isinstance(first_photo, str) else first_photo.get("url")
            first_original = await _resolve_image_bytes(url, request)
    source_pairs = []
    for index, entry in enumerate(d.get("source_afters") or []):
        if not isinstance(entry, dict):
            continue
        source_pairs.append(
            {
                "label": entry.get("label") or f"SOURCE_{index + 1:02d}",
                "after_label": entry.get("after_label") or f"AFTER_{index + 1:02d}",
                "source_photo_id": entry.get("source_photo_id") or "",
                "status": entry.get("status") or "",
                "before": await _resolve_image_bytes(entry.get("source_url"), request),
                "after": await _resolve_image_bytes(entry.get("after_url"), request) if entry.get("after_url") else None,
            }
        )
    # Several source afters are the angles. Stale hero crops must not fill a gap.
    if len(source_pairs) >= 2:
        fetched["view_1"] = None
        fetched["view_2"] = None
        fetched["view_3"] = None
    organized = fetched.get("front_view")
    before = first_original
    if source_pairs:
        before = source_pairs[0].get("before") or before
        approved = next((pair.get("after") for pair in source_pairs if pair.get("after")), None)
        if approved:
            organized = approved
    hero_bytes, hero_kind = choose_hero(
        organized_bytes=organized,
        original_bytes=before,
    )
    images = assemble_pdf_images(
        hero_bytes=hero_bytes,
        hero_kind=hero_kind,
        before=before,
        after=organized,
        customer_photos=customer_photos,
        source_pairs=source_pairs,
        fetched=fetched,
    )
    return lead, d, images


def _customer_title(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    """Title a customer sees. Nursery plans use the child's name when the plan states it."""
    return customer_project_title(lead, deliverable) or plan_title(lead.get("space_type"))


def _blueprint_filenames(lead: Dict[str, Any], deliverable: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str]:
    safe_name = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in (lead.get("name") or "client")
    )
    title = _customer_title(lead, deliverable or {})
    stem = "".join(ch if ch.isalnum() else "_" for ch in title)
    while "__" in stem:
        stem = stem.replace("__", "_")
    stem = stem.strip("_") or "Design_Plan"
    tag = version_tag(package_version(deliverable))
    board = f"FlowSpace_{stem}_Design_Plan_{safe_name}_{tag}.png"
    pdf = f"FlowSpace_{stem}_Companion_Guide_{safe_name}_{tag}.pdf"
    package = f"FlowSpace_{stem}_Design_Plan_{safe_name}_{tag}.zip"
    return board, pdf, package


def _zone_map_filenames(lead: Dict[str, Any], deliverable: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str, str]:
    board, pdf, package = _blueprint_filenames(lead, deliverable)
    return board, pdf, package, board.replace("_Design_Plan_", "_Room_Flow_", 1)


@api_router.get("/admin/leads/{lead_id}/deliverable/presentation")
async def deliverable_presentation(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    """Phone-page model for a lead. Does not email anyone or mark the package final."""
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    media = []
    for entry in d.get("source_afters") or []:
        if not isinstance(entry, dict):
            continue
        media.append(
            {
                "label": entry.get("label") or "",
                "after_label": entry.get("after_label") or "",
                "before_url": entry.get("source_url") or None,
                "after_url": entry.get("after_url") or None,
            }
        )
    if not media and (d.get("front_view_url") or images.get("after")):
        first_photo = (lead.get("photos") or [None])[0]
        before_url = None
        if isinstance(first_photo, str):
            before_url = first_photo
        elif isinstance(first_photo, dict):
            before_url = first_photo.get("url")
        media.append({"before_url": before_url, "after_url": d.get("front_view_url") or None})
    return sign_photo_urls(build_presentation(lead, d, images, lead_id=lead_id, media=media or None))


@api_router.get("/admin/leads/{lead_id}/deliverable/pdf")
async def render_deliverable_pdf(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    pdf_bytes = build_pdf(lead=lead, deliverable=d, images=images)
    _board_name, filename, _package = _blueprint_filenames(lead, d)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "no-store"},
    )


@api_router.get("/admin/leads/{lead_id}/deliverable/board")
async def render_deliverable_board(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    png_bytes = build_image_board(lead=lead, deliverable=d, images=images)
    filename, _pdf_name, _package = _blueprint_filenames(lead, d)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "no-store"},
    )


@api_router.get("/me/spaces/{lead_id}/board")
async def my_space_board(lead_id: str, request: Request, member: Dict[str, Any] = Depends(require_member)):
    await _member_plan_or_404(lead_id, member)
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    png_bytes = build_image_board(lead=lead, deliverable=d, images=images)
    filename, _pdf_name, _package = _blueprint_filenames(lead, d)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@api_router.get("/me/spaces/{lead_id}/pdf")
async def my_space_pdf(lead_id: str, request: Request, member: Dict[str, Any] = Depends(require_member)):
    await _member_plan_or_404(lead_id, member)
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    pdf_bytes = build_pdf(lead=lead, deliverable=d, images=images)
    _board_name, filename, _package = _blueprint_filenames(lead, d)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@api_router.get("/admin/leads/{lead_id}/deliverable/internal-record")
async def deliverable_internal_record(lead_id: str, _: bool = Depends(require_admin)):
    """Do Not list, extended notes, and full safety copy kept off the customer guide. Admin only."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
    return {"lead_id": lead_id, "final": False, **internal_record(lead, d)}


@api_router.get("/admin/leads/{lead_id}/deliverable/zone-map")
async def render_deliverable_zone_map(
    lead_id: str,
    request: Request,
    review: bool = False,
    _: bool = Depends(require_admin),
):
    """Conceptual Zone Map / Flow Plan PNG. ``review=1`` adds the status banner with the lead id."""
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    png_bytes = build_zone_map(
        lead=lead,
        deliverable=d,
        images=images,
        final=str(d.get("package_status") or "") == "final",
        review=review,
        lead_id=lead_id,
    )
    _board, _pdf, _package, zone_map_name = _zone_map_filenames(lead, d)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{zone_map_name}"', "Cache-Control": "no-store"},
    )


def _email_inputs(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> Dict[str, str]:
    """Body inputs shared by send-draft, send-final, and the email preview, so the preview is the sent body."""
    return {
        "customer_name": lead.get("name") or "",
        "space_type": lead.get("space_type") or "space",
        "project_title": _customer_title(lead, deliverable),
        "outline_note": outline_caption(lead, deliverable),
        "story": project_story_line(lead, deliverable),
    }


def _png_data_uri(png: Optional[bytes]) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii") if png else ""


@api_router.get("/admin/leads/{lead_id}/deliverable/email-preview")
async def render_customer_email_preview(
    lead_id: str,
    request: Request,
    draft: bool = False,
    _: bool = Depends(require_admin),
):
    """The HTML send-final (or send-draft with ``?draft=true``) emails, with images inlined. Does not send."""
    lead, deliverable, images = await _blueprint_render_inputs(lead_id, request)
    board = build_image_board(lead=lead, deliverable=deliverable, images=images)
    zone_map = build_zone_map(lead=lead, deliverable=deliverable, images=images, final=not draft)
    html = email_body_html(
        **_email_inputs(lead, deliverable),
        draft=draft,
        released=is_released(deliverable),
        lead_id=lead_id,
        preview_src=_png_data_uri(board),
        room_flow_src=_png_data_uri(zone_map) if board else "",
    )
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@api_router.get("/admin/leads/{lead_id}/deliverable/package")
async def render_deliverable_package(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    """Zip of the image board, the room-flow zone map, and the companion guide, for a revise or QA."""
    lead, d, images = await _blueprint_render_inputs(lead_id, request)
    pdf_bytes = build_pdf(lead=lead, deliverable=d, images=images)
    png_bytes = build_image_board(lead=lead, deliverable=d, images=images)
    zone_map = build_zone_map(
        lead=lead, deliverable=d, images=images, final=str(d.get("package_status") or "") == "final"
    )
    board_name, pdf_name, package_name, zone_map_name = _zone_map_filenames(lead, d)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(board_name, png_bytes)
        archive.writestr(zone_map_name, zone_map)
        archive.writestr(pdf_name, pdf_bytes)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{package_name}"', "Cache-Control": "no-store"},
    )


async def _contact_sheet_png(lead_id: str, request: Request):
    """Build the review sheet from persisted source → after mappings. Does not mark final."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
    _lead, _deliverable, images = await _blueprint_render_inputs(lead_id, request)
    pairs = images.get("source_pairs") or []
    if not pairs:
        raise HTTPException(
            status_code=404,
            detail="No per-source afters yet. Retry automation before requesting a contact sheet.",
        )
    incomplete = str(d.get("package_status") or "") == "incomplete" or any(not pair.get("after") for pair in pairs)
    png = build_contact_sheet(
        pairs,
        customer_name=lead.get("name") or "",
        incomplete=incomplete,
    )
    return lead, d, png, incomplete


@api_router.get("/admin/leads/{lead_id}/deliverable/contact-sheet")
async def render_contact_sheet(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    """SOURCE_01→AFTER_01 review sheet. Does not email the customer or mark the package final."""
    lead, _deliverable, png, _incomplete = await _contact_sheet_png(lead_id, request)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (lead.get("name") or "client"))
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="FlowSpace_Contact_Sheet_{safe_name}.png"',
            "Cache-Control": "no-store",
        },
    )


@api_router.post("/admin/leads/{lead_id}/deliverable/contact-sheet/send")
async def send_review_contact_sheet(
    lead_id: str,
    request: Request,
    to: Optional[str] = None,
    _: bool = Depends(require_admin),
):
    """Email the review sheet to Flo or Camila. The customer final package is not sent."""
    lead, deliverable, png, incomplete = await _contact_sheet_png(lead_id, request)
    recipient = (to or os.environ.get("ADMIN_EMAIL") or "hello@flowspace.solutions").strip()
    sent, error = await send_contact_sheet(
        to_email=recipient,
        customer_name=lead.get("name") or "",
        lead_id=lead_id,
        png_bytes=png,
        incomplete=incomplete,
    )
    if not sent:
        raise HTTPException(status_code=502, detail=error or "Contact sheet was not sent")
    return {
        "sent": True,
        "final": False,
        "package_status": deliverable.get("package_status"),
        "to": recipient,
    }




class AfterRefineRequest(BaseModel):
    # Explicit rug fields (shape, diameter_ft, diameter_m, color, texture, pattern, edge, placement).
    rug: Optional[Dict[str, Any]] = None
    # Limit to some views by label ("SOURCE_02") or after label ("AFTER_02"). Empty means every approved after.
    labels: List[str] = []


async def _run_after_refine(lead_id: str, rug_override: Optional[Dict[str, Any]], labels: List[str]) -> Dict[str, Any]:
    """Rug-consistency edit of each approved after. No email; package_status is not touched."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0}) or {}
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
    entries = [dict(e) if isinstance(e, dict) else e for e in (d.get("source_afters") or [])]
    wanted = {str(x).strip().upper() for x in labels if str(x).strip()}
    approved = [
        (i, e) for i, e in enumerate(entries)
        if mapping_is_own_source(e)
    ]
    sources = [await _resolve_image_bytes(e.get("source_url"), None) for _i, e in approved]
    afters = [await _resolve_image_bytes(e.get("after_url"), None) for _i, e in approved]
    first_after = afters[0] if afters else None
    rug = resolve_refine_rug(lead, d, rug_override)
    rug = await asyncio.to_thread(describe_rug, [s for s in sources if s], first_after, rug)
    reference: Optional[bytes] = None
    report: List[Dict[str, Any]] = []
    replaced_urls: Dict[str, str] = {}
    for position, ((index, entry), source, after) in enumerate(zip(approved, sources, afters)):
        label = str(entry.get("label") or f"SOURCE_{index + 1:02d}")
        after_label = str(entry.get("after_label") or f"AFTER_{index + 1:02d}")
        if wanted and label.upper() not in wanted and after_label.upper() not in wanted:
            continue
        if not after:
            report.append({"label": label, "after_label": after_label, "replaced": False, "reasons": ["after image could not be read"]})
            continue
        outcome = await refine_one(
            lead=lead,
            deliverable=d,
            rug=rug,
            label=label,
            after_label=after_label,
            source=source,
            after=after,
            reference=None if position == 0 else (reference or first_after),
            edit=refine_after_image,
        )
        row = outcome.report()
        if outcome.replaced and outcome.after_bytes:
            mime = "image/png" if outcome.after_bytes.startswith(b"\x89PNG") else "image/jpeg"
            ext = "png" if mime == "image/png" else "jpg"
            new_url = await store_photo(
                fs_bucket,
                filename=f"ai_{after_label.lower()}_rug_{lead_id}.{ext}",
                data=outcome.after_bytes,
                metadata={
                    "content_type": mime,
                    "uploaded_at": _iso(datetime.now(timezone.utc)),
                    "source": "rug_refine",
                    "lead_id": lead_id,
                    "slot": after_label.lower(),
                    "source_photo_id": entry.get("source_photo_id") or "",
                    "refined_from": entry.get("after_url") or "",
                },
            )
            replaced_urls[str(entry.get("after_url") or "")] = new_url
            history = list(entry.get("after_history") or [])
            history.append(
                {
                    "after_url": entry.get("after_url"),
                    "replaced_at": _iso(datetime.now(timezone.utc)),
                    "reason": "rug_consistency",
                }
            )
            entries[index] = {
                **entry,
                "after_url": new_url,
                "after_history": history,
                "refine": {"kind": "rug_consistency", "qa": outcome.qa, "rug_check": outcome.rug_check},
            }
            row["after_url"] = new_url
            if position == 0:
                reference = outcome.after_bytes
        elif position == 0:
            reference = after
        report.append(row)

    update: Dict[str, Any] = {
        "rug": {k: v for k, v in rug.items() if k != "described_by"},
        "after_refine": {
            "status": "done",
            "finished_at": _iso(datetime.now(timezone.utc)),
            "report": report,
        },
        "updated_at": _iso(datetime.now(timezone.utc)),
    }
    if replaced_urls:
        update["source_afters"] = entries
        front = str(d.get("front_view_url") or "")
        if front in replaced_urls:
            update["front_view_url"] = replaced_urls[front]
        pairs = [
            {
                "label": e.get("label"),
                "after_label": e.get("after_label"),
                "status": e.get("status"),
                "before": await _resolve_image_bytes(e.get("source_url"), None),
                "after": await _resolve_image_bytes(e.get("after_url"), None) if e.get("after_url") else None,
            }
            for e in entries
            if isinstance(e, dict)
        ]
        sheet = build_contact_sheet(
            pairs,
            customer_name=lead.get("name") or "",
            incomplete=str(d.get("package_status") or "") == "incomplete" or any(not p["after"] for p in pairs),
        )
        update["contact_sheet_url"] = await store_photo(
            fs_bucket,
            filename=f"contact_sheet_{lead_id}.png",
            data=sheet,
            metadata={"content_type": "image/png", "uploaded_at": _iso(datetime.now(timezone.utc)), "source": "rug_refine", "lead_id": lead_id, "slot": "contact_sheet"},
        )
    await db.deliverables.update_one({"lead_id": lead_id}, {"$set": update})
    return {
        "lead_id": lead_id,
        "rug": update["rug"],
        "replaced": sum(1 for row in report if row.get("replaced")),
        "views": report,
        "package_status": d.get("package_status"),
        "emailed": False,
    }


async def _run_after_refine_logged(lead_id: str, rug_override: Optional[Dict[str, Any]], labels: List[str]) -> None:
    try:
        await _run_after_refine(lead_id, rug_override, labels)
    except Exception as exc:
        logging.exception("After refine failed for %s", lead_id)
        await db.deliverables.update_one(
            {"lead_id": lead_id},
            {"$set": {"after_refine": {"status": "error", "error": str(exc), "finished_at": _iso(datetime.now(timezone.utc))}}},
        )


@api_router.post("/admin/leads/{lead_id}/deliverable/afters/refine")
async def refine_deliverable_afters(
    lead_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[AfterRefineRequest] = None,
    wait: bool = False,
    _: bool = Depends(require_admin),
):
    """Rug-consistency edit of every approved AFTER image, each replaced only when QA passes.

    Keeps SOURCE_n → AFTER_n mappings and package_status. Sends no email.
    Runs in the background by default (poll the GET route); ``?wait=true`` runs inline.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
    if not any(mapping_is_own_source(e) for e in (d.get("source_afters") or [])):
        raise HTTPException(status_code=409, detail="No approved per-source afters to refine.")
    payload = payload or AfterRefineRequest()
    if wait:
        return sign_photo_urls(await _run_after_refine(lead_id, payload.rug, payload.labels))
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {"$set": {"after_refine": {"status": "running", "started_at": _iso(datetime.now(timezone.utc))}}},
    )
    background_tasks.add_task(_run_after_refine_logged, lead_id, payload.rug, payload.labels)
    return {"lead_id": lead_id, "status": "running", "package_status": d.get("package_status"), "emailed": False}


@api_router.get("/admin/leads/{lead_id}/deliverable/afters/refine")
async def refine_deliverable_afters_status(lead_id: str, _: bool = Depends(require_admin)):
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return sign_photo_urls({"lead_id": lead_id, "rug": d.get("rug"), **(d.get("after_refine") or {"status": "never_run"})})


def _client_facing_visuals(images: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Full-size organized (after) photos for email attachment.

    Before photos are not attached as separate files; the before/after pairs
    live in the companion PDF only.
    """
    visuals: List[Dict[str, Any]] = []
    for index, pair in enumerate(images.get("source_pairs") or []):
        if not isinstance(pair, dict):
            continue
        after = pair.get("after")
        if after:
            visuals.append({"label": f"Organized-{index + 1}", "bytes": after})
    return visuals


@api_router.post("/admin/leads/{lead_id}/deliverable/send-draft")
async def send_draft_package_endpoint(
    lead_id: str,
    request: Request,
    to: Optional[str] = None,
    _: bool = Depends(require_admin),
):
    """Email DRAFT board + companion PDF for Flo/Camila review. Does not mark final."""
    lead, deliverable, images = await _blueprint_render_inputs(lead_id, request)
    reason = draft_send_block_reason(deliverable)
    if reason:
        raise HTTPException(status_code=409, detail=reason)
    pdf_bytes = build_pdf(lead=lead, deliverable=deliverable, images=images)
    board_bytes = build_image_board(lead=lead, deliverable=deliverable, images=images)
    zone_map_bytes = build_zone_map(lead=lead, deliverable=deliverable, images=images)
    recipient = (to or lead.get("email") or os.environ.get("ADMIN_EMAIL") or "hello@flowspace.solutions").strip()
    cc_raw = (request.query_params.get("cc") or "").strip()
    cc_emails = [p.strip() for p in cc_raw.split(",") if p.strip()] if cc_raw else []
    sent, error = await send_draft_package(
        **_email_inputs(lead, deliverable),
        to_email=recipient,
        lead_id=lead_id,
        pdf_bytes=pdf_bytes,
        board_bytes=board_bytes,
        cc_emails=cc_emails or None,
        zone_map_bytes=zone_map_bytes,
        extra_visuals=_client_facing_visuals(images),
    )
    if not sent:
        raise HTTPException(status_code=502, detail=error or "Draft package was not sent")
    now = _iso(datetime.now(timezone.utc))
    sent_version = package_version(deliverable)
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {"$set": {"sent_for_review": sent_version, "updated_at": now}},
    )
    return {
        "sent": True,
        "final": False,
        "package_status": deliverable.get("package_status"),
        "package_version": sent_version,
        "sent_for_review": sent_version,
        "to": recipient,
        "cc": cc_emails,
    }


@api_router.post("/admin/leads/{lead_id}/deliverable/send-final")
async def send_final_package(lead_id: str, request: Request, _: bool = Depends(require_admin)):
    """Email the customer board and companion PDF. Refuses an incomplete package."""
    lead, deliverable, images = await _blueprint_render_inputs(lead_id, request)
    reason = final_email_block_reason(deliverable)
    if reason:
        # Refuse the customer send. Do not rewrite a review lead and do not mark it final.
        raise HTTPException(status_code=409, detail=reason)
    pdf_bytes = build_pdf(lead=lead, deliverable=deliverable, images=images)
    board_bytes = build_image_board(lead=lead, deliverable=deliverable, images=images)
    zone_map_bytes = build_zone_map(lead=lead, deliverable=deliverable, images=images, final=True)
    sent, error = await send_blueprint(
        **_email_inputs(lead, deliverable),
        customer_email=lead.get("email") or "",
        lead_id=lead_id,
        pdf_bytes=pdf_bytes,
        board_bytes=board_bytes,
        zone_map_bytes=zone_map_bytes,
        extra_visuals=_client_facing_visuals(images),
        released=is_released(deliverable),
    )
    now = _iso(datetime.now(timezone.utc))
    if not sent:
        await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"status": "pdf_ready", "email_sent": False, "email_error": error, "updated_at": now}},
        )
        raise HTTPException(status_code=502, detail=error or "Final email was not sent")
    sent_version = package_version(deliverable)
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {"$set": {"package_status": "final", "sent_for_review": sent_version, "updated_at": now}},
    )
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$set": {
                "status": "delivered",
                "package_status": "final",
                "email_sent": True,
                "email_error": None,
                "automation_error": None,
                "updated_at": now,
            }
        },
    )
    return {
        "sent": True,
        "final": True,
        "package_status": "final",
        "status": "delivered",
        "package_version": sent_version,
        "sent_for_review": sent_version,
    }


@api_router.post("/admin/leads/{lead_id}/deliverable/regenerate")
async def regenerate_package(lead_id: str, _: bool = Depends(require_admin)):
    """Rewrite the held review copy and re-apply package rules.

    Does not email, and does not mark the package final or approved. The version
    number stays put until send-draft or send-final has emailed that copy.
    """
    from package_facts import next_release

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    stored = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0})
    if not stored:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    release = next_release(stored)
    prepared = prepare_deliverable(lead, stored)
    update = {key: value for key, value in prepared.items() if key != "_id"}
    for key in (
        "source_afters",
        "front_view_url",
        "floor_plan_url",
        "view_1_url",
        "view_2_url",
        "view_3_url",
        "contact_sheet_url",
        "non_room_uploads",
        "shopping_links",
        "sent_for_review",
    ):
        if key in stored and key not in update:
            update[key] = stored[key]
    now = _iso(datetime.now(timezone.utc))
    update.update(
        {
            "lead_id": lead_id,
            "package_version": release["package_version"],
            "package_status": release["package_status"],
            "design_plan_approved": False,
            "updated_at": now,
        }
    )
    if release.get("sent_for_review"):
        update["sent_for_review"] = release["sent_for_review"]
    update.pop("emailed", None)
    await db.deliverables.update_one({"lead_id": lead_id}, {"$set": update})
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$set": {
                "status": release["package_status"],
                "package_status": release["package_status"],
                "email_sent": False,
                "updated_at": now,
            }
        },
    )
    base = f"/api/admin/leads/{lead_id}/deliverable"
    return {
        "lead_id": lead_id,
        "package_version": release["package_version"],
        "version_label": release["version_label"],
        "package_status": release["package_status"],
        "emailed": False,
        "pieces": {
            "board": f"{base}/board",
            "zone_map": f"{base}/zone-map",
            "pdf": f"{base}/pdf",
        },
    }


# ──────────────────────────── Stripe ─────────────────────────────
PAYMENTS_DISABLED_MESSAGE = "Payments are disabled in this preview. No charge will be made."
STRIPE_UNPAID_OUTCOMES = {
    "checkout.session.expired": "expired",
    "checkout.session.async_payment_failed": "failed",
}
STRIPE_HANDLED_EVENTS = frozenset(
    {"checkout.session.completed", "checkout.session.async_payment_succeeded", *STRIPE_UNPAID_OUTCOMES}
)


def _stripe_mode(key: str) -> Optional[str]:
    if key.startswith(("sk_test_", "rk_test_")):
        return "test"
    if key.startswith(("sk_live_", "rk_live_")):
        return "live"
    return None


@api_router.get("/checkout/config")
async def checkout_config():
    """Tell the intake up front whether paid checkout can start on this server.

    Never returns the key itself — only whether one is set and its mode.
    """
    enabled = bool(STRIPE_API_KEY)
    return {
        "enabled": enabled,
        "mode": _stripe_mode(STRIPE_API_KEY) if enabled else None,
        "message": None if enabled else PAYMENTS_DISABLED_MESSAGE,
    }


@api_router.post("/checkout/session")
async def create_checkout(req: CheckoutRequest, request: Request):
    if req.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package")
    pkg = PACKAGES[req.package_id]
    if pkg["price"] == 0.0:
        raise HTTPException(status_code=400, detail="Free tier does not require checkout")
    lead_id = str((req.metadata or {}).get("lead_id") or "").strip()
    if not lead_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "LEAD_REQUIRED", "message": "Finish your project details before payment."},
        )
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Project not found")
    reason = chargeable_block_reason(lead, pkg)
    if reason:
        raise HTTPException(
            status_code=409,
            detail={"code": "PHOTO_REQUIRED", "message": reason, "errors": [{"field": "photos", "message": reason}]},
        )
    if not STRIPE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={"code": "PAYMENTS_DISABLED", "message": PAYMENTS_DISABLED_MESSAGE},
        )

    stripe_sdk.api_key = STRIPE_API_KEY
    origin = req.origin_url.rstrip("/")
    success_url = f"{origin}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/?canceled=1#packages"

    metadata: Dict[str, str] = {
        "package_id": pkg["id"],
        "package_name": pkg["name"],
        "source": "flowspace_web",
    }
    if req.email:
        metadata["email"] = str(req.email)
    if req.metadata:
        metadata.update({str(k): str(v) for k, v in req.metadata.items()})
    metadata["lead_id"] = lead_id
    member = await optional_member(request)
    checkout_email = str(req.email) if req.email else None
    if member:
        metadata["member_id"] = member["id"]
        checkout_email = checkout_email or member.get("email")
        if checkout_email and not metadata.get("email"):
            metadata["email"] = checkout_email

    try:
        session = await asyncio.to_thread(
            stripe_sdk.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": pkg["currency"],
                    "product_data": {"name": f"FlowSpace Design Plan — {pkg['name']}"},
                    "unit_amount": int(pkg["price"] * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=checkout_email,
            metadata=metadata,
        )
    except Exception as e:
        logging.exception("Stripe checkout creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    tx = PaymentTransaction(
        session_id=session.id,
        package_id=pkg["id"],
        amount=float(pkg["price"]),
        currency=pkg["currency"],
        email=checkout_email,
        lead_id=lead_id,
        payment_status="initiated",
        status="open",
        metadata=metadata,
    )
    await db.payment_transactions.insert_one(_doc(tx))
    return {"url": session.url, "session_id": session.id}


@api_router.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, background_tasks: BackgroundTasks):
    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    if existing.get("payment_status") == "paid":
        # Backup trigger: if the Stripe webhook never reached this backend
        # (wrong URL or missing secret), still start the PDF → Resend pipeline
        # when the success page confirms payment.
        meta = existing.get("metadata") or {}
        await _fulfill_paid_checkout(
            session_id=session_id,
            metadata=meta,
            customer_email=existing.get("email") or meta.get("email"),
            background_tasks=background_tasks,
            payment_status="paid",
            stripe_status=existing.get("status", "complete"),
        )
        return {
            "payment_status": "paid",
            "status": existing.get("status", "complete"),
            "amount_total": int(float(existing.get("amount", 0)) * 100),
            "currency": existing.get("currency", "usd"),
            "metadata": meta,
        }

    stripe_sdk.api_key = STRIPE_API_KEY
    try:
        sess = await asyncio.to_thread(stripe_sdk.checkout.Session.retrieve, session_id)
        new_payment_status = getattr(sess, "payment_status", "unknown")
        new_status = getattr(sess, "status", "unknown")
        amount_total = getattr(sess, "amount_total", None) or 0
        currency = getattr(sess, "currency", existing.get("currency", "usd"))
        metadata = _safe_metadata(sess)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"payment_status": new_payment_status, "status": new_status, "updated_at": _iso(datetime.now(timezone.utc))}},
    )
    if new_payment_status == "paid":
        customer_email = existing.get("email") or metadata.get("email")
        await _fulfill_paid_checkout(
            session_id=session_id,
            metadata=metadata,
            customer_email=customer_email,
            background_tasks=background_tasks,
            payment_status=new_payment_status,
            stripe_status=new_status,
        )
    return {
        "payment_status": new_payment_status,
        "status": new_status,
        "amount_total": amount_total,
        "currency": currency,
        "metadata": metadata,
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Stripe webhooks.
    On checkout.session.completed (or async_payment_succeeded) with payment_status=paid:
      1. Mark transaction as paid
      2. Link the lead
      3. Fire automation pipeline in background (once per session)
    On checkout.session.expired / async_payment_failed: mark the transaction
    expired / failed; no automation.

    Each event.id is recorded in ``stripe_events`` (unique) before handling, so
    Stripe redeliveries are acknowledged without doing the work twice.
    """
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe_sdk.Webhook.construct_event(body, sig, STRIPE_WEBHOOK_SECRET)
        else:
            # Dev mode — trust all events
            import json
            event = stripe_sdk.Event.construct_from(json.loads(body), stripe_sdk.api_key)
    except Exception as e:
        logging.exception("Webhook verification failed")
        raise HTTPException(status_code=400, detail=str(e))

    event_type = getattr(event, "type", "")
    if event_type not in STRIPE_HANDLED_EVENTS:
        return {"received": True}

    event_id = str(getattr(event, "id", "") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Event has no id")
    if not await _record_stripe_event(event_id, event_type):
        logging.info("Stripe event %s (%s) already processed — skipping", event_id, event_type)
        return {"received": True, "duplicate": True}

    try:
        sess = event.data.object
        session_id = sess.id
        if event_type in STRIPE_UNPAID_OUTCOMES:
            await _mark_checkout_unpaid(session_id, STRIPE_UNPAID_OUTCOMES[event_type])
        else:
            metadata = _safe_metadata(sess)
            customer_email = getattr(sess, "customer_email", None) or metadata.get("email")
            await _fulfill_paid_checkout(
                session_id=session_id,
                metadata=metadata,
                customer_email=customer_email,
                background_tasks=background_tasks,
                payment_status=getattr(sess, "payment_status", "unknown"),
                stripe_status=getattr(sess, "status", "complete"),
            )
    except Exception:
        # Forget the event so Stripe's retry is processed, log the FULL
        # traceback for Railway, and return a clean 500 so Stripe retries.
        await db.stripe_events.delete_one({"event_id": event_id})
        logging.exception("Webhook processing failed for %s", event_type)
        raise HTTPException(status_code=500, detail="Internal error processing webhook")

    return {"received": True}


# ──────────────────────────── App wiring ─────────────────────────────
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def _startup():
    await seed_gallery_if_empty()
    await ensure_member_indexes(db)
    await ensure_payment_indexes(db)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
