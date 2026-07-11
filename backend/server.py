from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from gridfs.errors import NoFile
import asyncio
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
import stripe as stripe_sdk
import httpx

from pdf_generator import build_pdf, build_room_transformation_pdf
from ai_drafter import draft_deliverable, draft_room_plan
from ai_image_generator import generate_front_view, generate_room_transformation
from video_generator import generate_walkthrough_video

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="uploads")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB per photo

STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "garage2025")
ROOM_JOB_ACTIVE: set[str] = set()

ROOM_JOB_STATUSES = {
    "pending",
    "uploaded",
    "image_processing",
    "image_complete",
    "plan_generating",
    "pdf_generating",
    "video_generating",
    "complete",
    "failed",
}

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

app = FastAPI(title="FlowSpace API")
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
    # Questionnaire fields
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


class ShoppingItem(BaseModel):
    name: str
    qty: float = 1
    price: float = 0


class Zone(BaseModel):
    title: str
    desc: str = ""


class ShoppingLink(BaseModel):
    name: str
    url: str = ""


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
    # Image refs (any URL — relative /api/uploads/photo/{id} or absolute http)
    front_view_url: Optional[str] = None
    floor_plan_url: Optional[str] = None
    view_1_url: Optional[str] = None
    view_2_url: Optional[str] = None
    view_3_url: Optional[str] = None
    include_customer_photos: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomJobCreate(BaseModel):
    customer_name: str
    email: EmailStr
    phone: Optional[str] = None
    room_type: str
    pain_point: str
    budget: str
    preferred_stores: List[str] = Field(default_factory=list)
    style_preference: str
    rent_or_own: str
    mounting_allowed: bool = False
    photos: List[str]
    package_id: Optional[str] = "standard"


class JobActionRequest(BaseModel):
    job_id: str


class RoomJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    email: EmailStr
    phone: Optional[str] = None
    room_type: str
    pain_point: str
    budget: str
    preferred_stores: List[str] = Field(default_factory=list)
    style_preference: str
    rent_or_own: str
    mounting_allowed: bool = False
    photos: List[str]
    package_id: Optional[str] = "standard"
    status: str = "pending"
    modified_images: List[Dict[str, Any]] = Field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    pdf_url: Optional[str] = None
    video_url: Optional[str] = None
    video_status: Optional[str] = None
    email_status: Optional[str] = None
    stage_errors: List[Dict[str, Any]] = Field(default_factory=list)
    cost_estimate: float = 0.0
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


def _hydrate_room_job(doc: dict) -> dict:
    return _hydrate(doc, ["created_at", "updated_at"])


async def _save_artifact(
    *,
    contents: bytes,
    filename: str,
    content_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    file_id = await fs_bucket.upload_from_stream(
        filename,
        contents,
        metadata={
            "content_type": content_type,
            "uploaded_at": _iso(datetime.now(timezone.utc)),
            **(metadata or {}),
        },
    )
    return f"/api/uploads/photo/{file_id}"


async def _resolve_artifact(url: Optional[str]) -> tuple[Optional[bytes], Optional[str]]:
    if not url:
        return None, None
    try:
        if url.startswith("/api/uploads/photo/"):
            photo_id = url.rsplit("/", 1)[-1]
            oid = ObjectId(photo_id)
            stream = await fs_bucket.open_download_stream(oid)
            data = await stream.read()
            content_type = "image/jpeg"
            if stream.metadata and stream.metadata.get("content_type"):
                content_type = stream.metadata["content_type"]
            return data, content_type
        if url.startswith("http://") or url.startswith("https://"):
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as ac:
                resp = await ac.get(url)
                resp.raise_for_status()
                return resp.content, resp.headers.get("content-type", "application/octet-stream")
    except Exception as e:
        logging.warning("Artifact resolve failed for %s: %s", url, e)
    return None, None


async def _update_room_job(job_id: str, *, status: Optional[str] = None, **fields: Any) -> None:
    update = {**fields, "updated_at": _iso(datetime.now(timezone.utc))}
    if status:
        if status not in ROOM_JOB_STATUSES:
            raise ValueError(f"Invalid room job status: {status}")
        update["status"] = status
    await db.room_jobs.update_one({"id": job_id}, {"$set": update})


async def _add_room_job_error(job_id: str, stage: str, message: str, **extra: Any) -> None:
    error = {
        "stage": stage,
        "message": message,
        "at": _iso(datetime.now(timezone.utc)),
        **extra,
    }
    await db.room_jobs.update_one(
        {"id": job_id},
        {
            "$push": {"stage_errors": error},
            "$set": {"updated_at": _iso(datetime.now(timezone.utc))},
        },
    )


async def _load_room_job(job_id: str) -> dict:
    job = await db.room_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _hydrate_room_job(job)


async def _generate_plan_for_job(job: Dict[str, Any]) -> Dict[str, Any]:
    plan = await draft_room_plan({**job, "job_id": job["id"]})
    await _update_room_job(job["id"], plan=plan)
    return plan


async def _generate_pdf_for_job(job: Dict[str, Any]) -> str:
    plan = job.get("plan") or await _generate_plan_for_job(job)
    original_images: List[Optional[bytes]] = []
    for photo_url in job.get("photos") or []:
        data, _ = await _resolve_artifact(photo_url)
        original_images.append(data)

    modified_images: List[Optional[bytes]] = []
    for image in job.get("modified_images") or []:
        if image.get("status") != "complete":
            continue
        data, _ = await _resolve_artifact(image.get("modified_url"))
        if data:
            modified_images.append(data)

    pdf_bytes = build_room_transformation_pdf(
        job=job,
        plan=plan,
        original_images=original_images,
        modified_images=modified_images,
    )
    safe_room = (job.get("room_type") or "room").replace(" ", "_")
    pdf_url = await _save_artifact(
        contents=pdf_bytes,
        filename=f"flowspace_{safe_room}_{job['id']}.pdf",
        content_type="application/pdf",
        metadata={"source": "room_job_pdf", "job_id": job["id"]},
    )
    await _update_room_job(job["id"], pdf_url=pdf_url, cost_estimate=float(job.get("cost_estimate") or 0) + 0.01)
    return pdf_url


async def _generate_video_for_job(job: Dict[str, Any]) -> Optional[str]:
    source_frames: List[bytes] = []
    for image in job.get("modified_images") or []:
        if image.get("status") != "complete":
            continue
        data, _ = await _resolve_artifact(image.get("modified_url"))
        if data:
            source_frames.append(data)
    video_bytes, mime, provider = await generate_walkthrough_video(source_frames[:4])
    ext = "mov" if "quicktime" in mime else "mp4"
    video_url = await _save_artifact(
        contents=video_bytes,
        filename=f"flowspace_walkthrough_{job['id']}.{ext}",
        content_type=mime or "video/mp4",
        metadata={"source": "room_job_video", "job_id": job["id"], "provider": provider},
    )
    await _update_room_job(
        job["id"],
        video_url=video_url,
        video_status="complete",
        cost_estimate=float(job.get("cost_estimate") or 0) + 0.30,
    )
    return video_url


async def _send_completion_email(job: Dict[str, Any]) -> None:
    """Send completion email when SMTP is configured; otherwise record a skipped status."""
    smtp_host = os.environ.get("SMTP_HOST")
    if not smtp_host:
        await _update_room_job(job["id"], email_status="skipped_no_smtp")
        logging.info("SMTP_HOST not configured; skipped completion email for job %s", job["id"])
        return

    import smtplib
    from email.message import EmailMessage

    site_url = os.environ.get("PUBLIC_APP_URL") or os.environ.get("FRONTEND_URL") or ""
    result_url = f"{site_url.rstrip('/')}/results/{job['id']}" if site_url else f"/results/{job['id']}"
    msg = EmailMessage()
    msg["Subject"] = "Your FlowSpace room transformation is ready"
    msg["From"] = os.environ.get("SMTP_FROM", "Ryan at FlowSpace <hello@flowspace.solutions>")
    msg["To"] = job["email"]
    msg.set_content(
        f"Hi {job.get('customer_name') or 'there'},\n\n"
        "Your FlowSpace room organization deliverable is ready.\n\n"
        f"View your results: {result_url}\n"
        f"PDF: {job.get('pdf_url') or 'available on your results page'}\n"
        f"Video: {job.get('video_url') or 'video was not generated for this job'}\n\n"
        "Warmly,\nRyan at FlowSpace"
    )
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, port, timeout=20) as smtp:
            if os.environ.get("SMTP_STARTTLS", "true").lower() == "true":
                smtp.starttls()
            if os.environ.get("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        await _update_room_job(job["id"], email_status="sent")
    except Exception as e:
        logging.exception("Completion email failed")
        await _update_room_job(job["id"], email_status="failed")
        await _add_room_job_error(job["id"], "email", str(e))


async def process_room_job(job_id: str) -> None:
    if job_id in ROOM_JOB_ACTIVE:
        return
    ROOM_JOB_ACTIVE.add(job_id)
    try:
        job = await _load_room_job(job_id)
        await _update_room_job(job_id, status="uploaded")
        job = await _load_room_job(job_id)

        await _update_room_job(job_id, status="image_processing")
        modified_images: List[Dict[str, Any]] = []
        for idx, photo_url in enumerate(job.get("photos") or [], 1):
            try:
                data, mime = await _resolve_artifact(photo_url)
                if not data:
                    raise RuntimeError("Original upload could not be loaded")
                out_bytes, out_mime, provider, prompt = await generate_room_transformation(
                    image_bytes=data,
                    mime_type=mime or "image/jpeg",
                    intake=job,
                )
                modified_url = await _save_artifact(
                    contents=out_bytes,
                    filename=f"flowspace_organized_{job_id}_{idx}.png",
                    content_type=out_mime or "image/png",
                    metadata={
                        "source": "room_job_image",
                        "job_id": job_id,
                        "original_url": photo_url,
                        "provider": provider,
                        "prompt": prompt,
                    },
                )
                modified_images.append(
                    {
                        "index": idx,
                        "original_url": photo_url,
                        "modified_url": modified_url,
                        "provider": provider,
                        "status": "complete",
                    }
                )
            except Exception as e:
                logging.exception("Image %s failed for job %s", idx, job_id)
                modified_images.append(
                    {
                        "index": idx,
                        "original_url": photo_url,
                        "status": "failed",
                        "error": str(e),
                    }
                )
                await _add_room_job_error(job_id, "image_processing", str(e), photo_url=photo_url, index=idx)
            await _update_room_job(job_id, modified_images=modified_images)

        image_cost = sum(1 for img in modified_images if img.get("status") == "complete") * 0.08
        await _update_room_job(job_id, status="image_complete", cost_estimate=image_cost)

        await _update_room_job(job_id, status="plan_generating")
        job = await _load_room_job(job_id)
        await _generate_plan_for_job(job)
        await _update_room_job(job_id, cost_estimate=image_cost + 0.02)

        await _update_room_job(job_id, status="pdf_generating")
        job = await _load_room_job(job_id)
        await _generate_pdf_for_job(job)

        await _update_room_job(job_id, status="video_generating", video_status="processing")
        job = await _load_room_job(job_id)
        try:
            await _generate_video_for_job(job)
        except Exception as e:
            logging.warning("Video generation failed for job %s: %s", job_id, e)
            await _update_room_job(job_id, video_status="failed")
            await _add_room_job_error(job_id, "video_generating", str(e))

        await _update_room_job(job_id, status="complete")
        job = await _load_room_job(job_id)
        await _send_completion_email(job)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Room job failed")
        await _update_room_job(job_id, status="failed")
        await _add_room_job_error(job_id, "job", str(e))
    finally:
        ROOM_JOB_ACTIVE.discard(job_id)


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
    return {"message": "FlowSpace API", "status": "ok"}


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


# ------------------------- Uploads (GridFS) -------------------------
@api_router.post("/uploads/photo")
async def upload_photo(file: UploadFile = File(...)):
    ct = (file.content_type or "").lower()
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    file_id = await fs_bucket.upload_from_stream(
        file.filename or "upload",
        contents,
        metadata={"content_type": ct, "uploaded_at": _iso(datetime.now(timezone.utc))},
    )
    return {"id": str(file_id), "url": f"/api/uploads/photo/{file_id}"}


@api_router.get("/uploads/photo/{photo_id}")
async def get_photo(photo_id: str):
    try:
        oid = ObjectId(photo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    try:
        stream = await fs_bucket.open_download_stream(oid)
    except NoFile:
        raise HTTPException(status_code=404, detail="Not found")
    data = await stream.read()
    media = "image/jpeg"
    if stream.metadata and stream.metadata.get("content_type"):
        media = stream.metadata["content_type"]
    return Response(
        content=data,
        media_type=media,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ------------------------- Room Automation Jobs -------------------------
@api_router.post("/process-room")
async def create_room_job(payload: RoomJobCreate, background_tasks: BackgroundTasks):
    if len(payload.photos) < 2 or len(payload.photos) > 4:
        raise HTTPException(status_code=400, detail="Upload 2 to 4 room photos")
    if payload.package_id and payload.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail="Invalid package_id")
    job = RoomJob(**payload.model_dump())
    await db.room_jobs.insert_one(_doc(job))
    background_tasks.add_task(process_room_job, job.id)
    return _hydrate_room_job(_doc(job))


@api_router.get("/jobs/{job_id}")
async def get_room_job(job_id: str):
    return await _load_room_job(job_id)


@api_router.post("/generate-images")
async def generate_images(payload: JobActionRequest, background_tasks: BackgroundTasks, _: bool = Depends(require_admin)):
    await _load_room_job(payload.job_id)
    background_tasks.add_task(process_room_job, payload.job_id)
    return {"job_id": payload.job_id, "queued": True, "stage": "image_processing"}


@api_router.post("/generate-plan")
async def generate_plan(payload: JobActionRequest, _: bool = Depends(require_admin)):
    job = await _load_room_job(payload.job_id)
    await _update_room_job(payload.job_id, status="plan_generating")
    plan = await _generate_plan_for_job(job)
    await _update_room_job(payload.job_id, status="image_complete")
    return {"job_id": payload.job_id, "plan": plan}


@api_router.post("/generate-pdf")
async def generate_pdf(payload: JobActionRequest, _: bool = Depends(require_admin)):
    job = await _load_room_job(payload.job_id)
    await _update_room_job(payload.job_id, status="pdf_generating")
    pdf_url = await _generate_pdf_for_job(job)
    await _update_room_job(payload.job_id, status="complete")
    return {"job_id": payload.job_id, "pdf_url": pdf_url}


@api_router.post("/generate-video")
async def generate_video(payload: JobActionRequest, _: bool = Depends(require_admin)):
    job = await _load_room_job(payload.job_id)
    await _update_room_job(payload.job_id, status="video_generating", video_status="processing")
    try:
        video_url = await _generate_video_for_job(job)
    except Exception as e:
        await _update_room_job(payload.job_id, video_status="failed")
        await _add_room_job_error(payload.job_id, "video_generating", str(e))
        raise HTTPException(status_code=502, detail=f"Video generation failed: {e}")
    await _update_room_job(payload.job_id, status="complete")
    return {"job_id": payload.job_id, "video_url": video_url}


@api_router.get("/admin/jobs")
async def admin_room_jobs(_: bool = Depends(require_admin)):
    items = await db.room_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return [_hydrate_room_job(it) for it in items]


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


# ------------------------- Deliverable / PDF -------------------------
async def _resolve_image_bytes(url: Optional[str], request: Request) -> Optional[bytes]:
    """Fetch image bytes from a URL (relative /api/uploads/... or absolute http)."""
    if not url:
        return None
    try:
        if url.startswith("/api/uploads/photo/"):
            photo_id = url.rsplit("/", 1)[-1]
            try:
                oid = ObjectId(photo_id)
            except Exception:
                return None
            try:
                stream = await fs_bucket.open_download_stream(oid)
            except NoFile:
                return None
            return await stream.read()
        if url.startswith("http://") or url.startswith("https://"):
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as ac:
                r = await ac.get(url)
                r.raise_for_status()
                return r.content
    except Exception as e:
        logging.warning(f"image fetch failed for {url}: {e}")
        return None
    return None


@api_router.get("/admin/leads/{lead_id}/deliverable")
async def get_deliverable(lead_id: str, _: bool = Depends(require_admin)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0})
    if d:
        d = _hydrate(d, ["updated_at"])
    return {"lead": _hydrate(lead, ["created_at"]), "deliverable": d}


@api_router.put("/admin/leads/{lead_id}/deliverable", response_model=Deliverable)
async def upsert_deliverable(
    lead_id: str, payload: Deliverable, _: bool = Depends(require_admin)
):
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    payload.lead_id = lead_id
    payload.updated_at = datetime.now(timezone.utc)
    doc = _doc(payload)
    await db.deliverables.update_one(
        {"lead_id": lead_id}, {"$set": doc}, upsert=True
    )
    return payload


@api_router.post("/admin/leads/{lead_id}/deliverable/draft")
async def ai_draft_deliverable(lead_id: str, _: bool = Depends(require_admin)):
    """Use the LLM to draft a deliverable from the lead's questionnaire."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    try:
        plan = await draft_deliverable(lead)
    except Exception as e:
        logging.exception("AI draft failed")
        raise HTTPException(status_code=502, detail=f"AI draft failed: {e}")
    return {"draft": plan}


@api_router.post("/admin/leads/{lead_id}/deliverable/generate-image")
async def ai_generate_image(
    lead_id: str,
    slot: str = "front_view",
    _: bool = Depends(require_admin),
):
    """Generate an AI rendering for a deliverable image slot using Nano Banana.

    Currently supports slot='front_view' — a 3D front-view rendering based
    on the customer's questionnaire answers and (when available) their
    uploaded reference photos. The generated PNG is persisted to GridFS
    and the deliverable doc is updated so the URL survives reloads.
    """
    valid_slots = {"front_view", "view_1", "view_2", "view_3", "floor_plan"}
    if slot not in valid_slots:
        raise HTTPException(status_code=400, detail=f"Invalid slot. Use one of {sorted(valid_slots)}")

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    deliverable = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {}

    try:
        png_bytes, mime = await generate_front_view(
            lead=lead, deliverable=deliverable, fs_bucket=fs_bucket
        )
    except Exception as e:
        logging.exception("AI image generation failed")
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}")

    ext = "jpg" if "jpeg" in (mime or "") else "png"
    file_id = await fs_bucket.upload_from_stream(
        f"ai_{slot}_{lead_id}.{ext}",
        png_bytes,
        metadata={
            "content_type": mime or "image/png",
            "uploaded_at": _iso(datetime.now(timezone.utc)),
            "source": "ai_generated",
            "lead_id": lead_id,
            "slot": slot,
        },
    )
    url = f"/api/uploads/photo/{file_id}"

    slot_field = f"{slot}_url"
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {
            "$set": {
                slot_field: url,
                "lead_id": lead_id,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
        upsert=True,
    )

    return {"slot": slot, "url": url}


@api_router.get("/admin/leads/{lead_id}/deliverable/pdf")
async def render_deliverable_pdf(
    lead_id: str, request: Request, _: bool = Depends(require_admin)
):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    d = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or {
        "lead_id": lead_id
    }

    # Resolve image bytes in parallel-ish (sequentially via async for clarity)
    images: Dict[str, Any] = {
        "front_view": await _resolve_image_bytes(d.get("front_view_url"), request),
        "floor_plan": await _resolve_image_bytes(d.get("floor_plan_url"), request),
        "view_1": await _resolve_image_bytes(d.get("view_1_url"), request),
        "view_2": await _resolve_image_bytes(d.get("view_2_url"), request),
        "view_3": await _resolve_image_bytes(d.get("view_3_url"), request),
    }
    customer_photos: List[Optional[bytes]] = []
    if d.get("include_customer_photos", True):
        for p in (lead.get("photos") or [])[:8]:
            b = await _resolve_image_bytes(p, request)
            if b:
                customer_photos.append(b)
    images["customer_photos"] = customer_photos

    pdf_bytes = build_pdf(lead=lead, deliverable=d, images=images)

    safe_name = (lead.get("name") or "client").replace(" ", "_")
    space = (lead.get("space_type") or "space").capitalize()
    filename = f"FlowSpace_{space}_Plan_{safe_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


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
        "source": "flowspace_web",
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
    status_resp = None
    try:
        status_resp = await stripe.get_checkout_status(session_id)
        new_payment_status = status_resp.payment_status
        new_status = status_resp.status
        amount_total = status_resp.amount_total
        currency = status_resp.currency
        metadata = status_resp.metadata
    except Exception as e:
        # Fallback: emergentintegrations currently has a pydantic validation bug
        # with StripeObject metadata. Query Stripe directly.
        logging.warning(f"emergentintegrations status failed, falling back: {e}")
        try:
            stripe_sdk.api_key = STRIPE_API_KEY
            sess = await stripe_sdk.checkout.Session.retrieve_async(session_id)
            new_payment_status = getattr(sess, "payment_status", "unknown")
            new_status = getattr(sess, "status", "unknown")
            amount_total = getattr(sess, "amount_total", None) or 0
            currency = getattr(sess, "currency", existing.get("currency", "usd"))
            raw_meta = getattr(sess, "metadata", {}) or {}
            try:
                metadata = dict(raw_meta)
            except Exception:
                metadata = {}
        except Exception as inner:
            logging.exception("Stripe direct fallback also failed")
            raise HTTPException(status_code=502, detail=f"Stripe error: {inner}")

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "payment_status": new_payment_status,
                "status": new_status,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
    )

    return {
        "payment_status": new_payment_status,
        "status": new_status,
        "amount_total": amount_total,
        "currency": currency,
        "metadata": metadata,
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
    resumable = await db.room_jobs.find(
        {
            "status": {
                "$in": [
                    "pending",
                    "uploaded",
                    "image_processing",
                    "image_complete",
                    "plan_generating",
                    "pdf_generating",
                    "video_generating",
                ]
            }
        },
        {"_id": 0, "id": 1},
    ).to_list(50)
    for job in resumable:
        asyncio.create_task(process_room_job(job["id"]))


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
