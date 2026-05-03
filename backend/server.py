from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
    CheckoutSessionRequest,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "garage2025")

# Server-side package definitions
PACKAGES: Dict[str, Dict[str, Any]] = {
    "basic": {"id": "basic", "name": "Basic", "price": 79.0, "currency": "usd"},
    "standard": {"id": "standard", "name": "Standard", "price": 149.0, "currency": "usd"},
    "premium": {"id": "premium", "name": "Premium", "price": 299.0, "currency": "usd"},
}

STARTER_GALLERY = [
    {
        "id": str(uuid.uuid4()),
        "title": "Garage — Workshop reset",
        "category": "garage",
        "before_url": "https://images.unsplash.com/photo-1570129476815-ba368ac77013?auto=format&fit=crop&w=1400&q=80",
        "after_url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1400&q=80",
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Walk-in closet — Daily clarity",
        "category": "closet",
        "before_url": "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?auto=format&fit=crop&w=1400&q=80",
        "after_url": "https://images.unsplash.com/photo-1551298370-9d3d53740c72?auto=format&fit=crop&w=1400&q=80",
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Pantry — Categorized storage",
        "category": "storage",
        "before_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?auto=format&fit=crop&w=1400&q=80",
        "after_url": "https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=1400&q=80",
    },
]

app = FastAPI(title="ClearSpace API")
api_router = APIRouter(prefix="/api")


# ------------------------- Models -------------------------
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
    photos: List[str] = []
    language: str = "en"
    status: str = "new"
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
    photos: List[str] = []
    language: str = "en"


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
    payment_status: str = "initiated"
    status: str = "open"
    metadata: Dict[str, str] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------- Helpers -------------------------
def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


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


async def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> bool:
    if not x_admin_token or x_admin_token != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


async def seed_gallery_if_empty():
    count = await db.gallery.count_documents({})
    if count == 0:
        for item in STARTER_GALLERY:
            doc = {**item, "created_at": _iso(datetime.now(timezone.utc))}
            await db.gallery.insert_one(doc)


# ------------------------- Public Routes -------------------------
@api_router.get("/")
async def root():
    return {"message": "ClearSpace API", "status": "ok"}


@api_router.get("/packages")
async def get_packages():
    return {"packages": list(PACKAGES.values())}


@api_router.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate):
    if payload.package_id and payload.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package_id")
    lead = Lead(**payload.model_dump())
    await db.leads.insert_one(_doc(lead))
    return lead


@api_router.get("/gallery", response_model=List[GalleryItem])
async def list_gallery():
    await seed_gallery_if_empty()
    items = await db.gallery.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_hydrate(it, ["created_at"]) for it in items]


# ------------------------- Admin Routes -------------------------
@api_router.post("/admin/login")
async def admin_login(payload: AdminLoginRequest):
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": ADMIN_PASSWORD}


@api_router.get("/admin/leads", response_model=List[Lead])
async def admin_leads(_: bool = Depends(require_admin)):
    items = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return [_hydrate(it, ["created_at"]) for it in items]


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


# ------------------------- Stripe -------------------------
def _get_stripe(request: Request) -> StripeCheckout:
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@api_router.post("/checkout/session")
async def create_checkout(req: CheckoutRequest, request: Request):
    if req.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package")
    pkg = PACKAGES[req.package_id]
    origin = req.origin_url.rstrip("/")
    success_url = f"{origin}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/?canceled=1#packages"

    metadata: Dict[str, str] = {
        "package_id": pkg["id"],
        "package_name": pkg["name"],
        "source": "clearspace_web",
    }
    if req.email:
        metadata["email"] = str(req.email)
    if req.metadata:
        for k, v in req.metadata.items():
            metadata[str(k)] = str(v)

    stripe = _get_stripe(request)
    checkout_req = CheckoutSessionRequest(
        amount=float(pkg["price"]),
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    try:
        session: CheckoutSessionResponse = await stripe.create_checkout_session(checkout_req)
    except Exception as e:
        logging.exception("Stripe checkout creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    tx = PaymentTransaction(
        session_id=session.session_id,
        package_id=pkg["id"],
        amount=float(pkg["price"]),
        currency=pkg["currency"],
        email=str(req.email) if req.email else None,
        payment_status="initiated",
        status="open",
        metadata=metadata,
    )
    await db.payment_transactions.insert_one(_doc(tx))

    return {"url": session.url, "session_id": session.session_id}


@api_router.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, request: Request):
    existing = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")

    if existing.get("payment_status") == "paid":
        return {
            "payment_status": "paid",
            "status": existing.get("status", "complete"),
            "amount_total": int(float(existing.get("amount", 0)) * 100),
            "currency": existing.get("currency", "usd"),
            "metadata": existing.get("metadata", {}),
        }

    stripe = _get_stripe(request)
    try:
        status_resp: CheckoutStatusResponse = await stripe.get_checkout_status(session_id)
    except Exception as e:
        logging.exception("Stripe status failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "payment_status": status_resp.payment_status,
                "status": status_resp.status,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
    )

    return {
        "payment_status": status_resp.payment_status,
        "status": status_resp.status,
        "amount_total": status_resp.amount_total,
        "currency": status_resp.currency,
        "metadata": status_resp.metadata,
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    stripe = _get_stripe(request)
    try:
        event = await stripe.handle_webhook(body, sig)
    except Exception as e:
        logging.exception("Webhook failure")
        raise HTTPException(status_code=400, detail=str(e))

    if getattr(event, "session_id", None):
        await db.payment_transactions.update_one(
            {"session_id": event.session_id},
            {
                "$set": {
                    "payment_status": event.payment_status,
                    "updated_at": _iso(datetime.now(timezone.utc)),
                }
            },
        )
    return {"received": True}


# ------------------------- App wiring -------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
