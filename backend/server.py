from fastapi import FastAPI, APIRouter, HTTPException, Request, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import asyncio
import resend
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
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

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

resend.api_key = RESEND_API_KEY

app = FastAPI()
api_router = APIRouter(prefix="/api")

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
    photos_base64: List[str]  # data URLs or raw base64
    session_id: Optional[str] = None  # for paid plans

class SubmissionPhotoOut(BaseModel):
    before: str  # base64 png
    after: str   # base64 png

class SubmissionOut(BaseModel):
    id: str
    plan_id: str
    status: str
    room_type: Optional[str] = None
    pdf_available: bool = False
    results: List[SubmissionPhotoOut]

# ----- Helpers -----
def strip_data_url(b64: str) -> str:
    if b64.startswith("data:"):
        return b64.split(",", 1)[1]
    return b64

async def generate_after_image(before_b64: str) -> Optional[str]:
    """Use Gemini Nano Banana image-to-image to produce an organized version."""
    try:
        prompt = (
            "Reimagine this exact same room from the same camera angle, but completely "
            "decluttered, clean, and professionally organized. Add tasteful labeled "
            "storage bins, neat shelving, clear floor space, neatly folded items, and "
            "good lighting. Keep the room's architecture and furniture footprint the "
            "same. Photorealistic, magazine-quality, bright and airy."
        )
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"floorspace-{uuid.uuid4()}",
            system_message="You are an interior organization designer that transforms cluttered rooms.",
        ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
            modalities=["image", "text"]
        )
        msg = UserMessage(
            text=prompt,
            file_contents=[ImageContent(strip_data_url(before_b64))],
        )
        _text, images = await chat.send_message_multimodal_response(msg)
        if images:
            return images[0]["data"]  # base64
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
    return None

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
    attachments = []
    if submission.get("pdf_base64"):
        room = submission.get("room_type") or "Room"
        room_pretty = room.title().replace(" ", "-")
        filename = f"FlowSpace-{room_pretty}-Design-Plan.pdf"
        attachments = [{"filename": filename, "content": submission["pdf_base64"]}]
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

    attachments = []
    pdf_block = ""
    if submission.get("pdf_base64"):
        room = submission.get("room_type") or "Room"
        room_pretty = room.title().replace(" ", "-")
        filename = f"FlowSpace-{room_pretty}-Design-Plan.pdf"
        attachments = [{"filename": filename, "content": submission["pdf_base64"]}]
        pdf_block = (
            "<p style='margin:16px 0 8px;font-weight:600;color:#047857'>"
            f"Your custom PDF Design Plan ({filename}) is attached to this email."
            "</p>"
        )
    elif plan.get("pdf"):
        pdf_block = (
            "<p style='margin:16px 0 8px;color:#92400e'>"
            "Your PDF Design Plan will be ready shortly — check back on the link below."
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

@api_router.post("/submissions", response_model=SubmissionOut)
async def create_submission(payload: SubmissionCreate, background: BackgroundTasks, request: Request):
    if payload.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    plan = PLANS[payload.plan_id]
    if len(payload.photos_base64) == 0:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if len(payload.photos_base64) > plan["max_photos"]:
        raise HTTPException(status_code=400, detail=f"Max {plan['max_photos']} photos for {plan['name']}")

    # If paid plan, payment verification is currently bypassed —
    # all plans (Free, Plus, Premium) can submit without a paid session.
    # (Stripe checkout flow remains in place but is unused from the UI.)

    sub_id = str(uuid.uuid4())
    results: List[Dict[str, str]] = []

    # Generate AI transformation for each photo (in parallel)
    befores = [strip_data_url(p) for p in payload.photos_base64]
    afters = await asyncio.gather(*(generate_after_image(b) for b in befores))
    for b, a in zip(befores, afters):
        results.append({"before": b, "after": a or ""})

    # For Plus/Premium plans — generate the PDF design plan
    pdf_b64 = ""
    design_plan: Optional[Dict[str, Any]] = None
    if plan["pdf"]:
        try:
            primary_after = next((r["after"] for r in results if r["after"]), "")
            design_plan = await generate_design_plan(
                room_type=payload.room_type,
                after_image_b64=primary_after or None,
                user_notes=payload.notes,
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

    doc = {
        "id": sub_id,
        "plan_id": payload.plan_id,
        "name": payload.name,
        "email": payload.email,
        "room_type": payload.room_type,
        "notes": payload.notes,
        "session_id": payload.session_id,
        "results": results,
        "design_plan": design_plan,
        "pdf_base64": pdf_b64,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.submissions.insert_one(doc)

    # Mark txn as used
    if payload.session_id:
        await db.payment_transactions.update_one(
            {"session_id": payload.session_id},
            {"$set": {"submission_id": sub_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    # Email admin + customer (non-blocking)
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    result_url = f"{origin}/result/{sub_id}"
    background.add_task(send_admin_email_sync, doc)
    background.add_task(send_customer_email_sync, doc, result_url)

    return SubmissionOut(
        id=sub_id,
        plan_id=payload.plan_id,
        status="completed",
        room_type=payload.room_type,
        pdf_available=bool(pdf_b64),
        results=[SubmissionPhotoOut(**r) for r in results],
    )

@api_router.get("/submissions/{sub_id}", response_model=SubmissionOut)
async def get_submission(sub_id: str):
    doc = await db.submissions.find_one({"id": sub_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return SubmissionOut(
        id=doc["id"],
        plan_id=doc["plan_id"],
        status=doc.get("status", "completed"),
        room_type=doc.get("room_type"),
        pdf_available=bool(doc.get("pdf_base64")),
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
