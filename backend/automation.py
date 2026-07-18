"""
FlowSpace Automation Pipeline

Triggered after Stripe payment is confirmed.
Full flow:
  1. AI draft the design plan (Claude)
  2. Generate room rendering (Replicate FLUX)
  3. Build the PDF (ReportLab)
  4. Email it to the customer (Resend)
  5. Update lead status in MongoDB
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ai_drafter import draft_deliverable
from ai_image_generator import generate_front_view
from email_service import send_blueprint
from pdf_generator import build_pdf

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def run_automation(
    *,
    lead: Dict[str, Any],
    db,
    fs_bucket,
) -> bool:
    """
    Run the full automation pipeline for a lead.

    Returns True if the pipeline completed and email was sent, False on failure.
    """
    lead_id = lead.get("id", "unknown")
    customer_name = lead.get("name", "there")
    customer_email = lead.get("email", "")
    space_type = lead.get("space_type", "space")

    logger.info("[automation] Starting pipeline for lead %s (%s)", lead_id, customer_email)

    # Mark as processing
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"status": "processing", "updated_at": _iso(datetime.now(timezone.utc))}},
    )

    try:
        # ── Step 1: AI Draft ─────────────────────────────────────────────
        logger.info("[automation] Step 1: AI drafting plan...")
        plan = await draft_deliverable(lead)

        # Save draft to deliverables collection
        plan["lead_id"] = lead_id
        plan["updated_at"] = _iso(datetime.now(timezone.utc))
        await db.deliverables.update_one(
            {"lead_id": lead_id},
            {"$set": plan},
            upsert=True,
        )
        logger.info("[automation] Plan drafted and saved")

        # ── Step 2: AI Image Generation ──────────────────────────────────
        logger.info("[automation] Step 2: Generating room rendering via Replicate...")
        image_bytes: Optional[bytes] = None
        image_mime: str = "image/jpeg"
        try:
            # Fetch the customer's own uploaded photo (if any) so the AI
            # transforms their ACTUAL room instead of inventing one from scratch.
            reference_photo_bytes: Optional[bytes] = None
            first_photo = (lead.get("photos") or [None])[0]
            if first_photo:
                photo_url = first_photo if isinstance(first_photo, str) else first_photo.get("url")
                if photo_url and "/api/uploads/photo/" in photo_url:
                    try:
                        from bson import ObjectId
                        photo_id = photo_url.rsplit("/", 1)[-1]
                        stream = await fs_bucket.open_download_stream(ObjectId(photo_id))
                        reference_photo_bytes = await stream.read()
                        logger.info("[automation] Using customer's uploaded photo as render reference")
                    except Exception as fetch_err:
                        logger.warning("[automation] Could not fetch customer photo: %s", fetch_err)

            image_bytes, image_mime = await generate_front_view(
                lead=lead,
                deliverable=plan,
                fs_bucket=fs_bucket,
                reference_photo_bytes=reference_photo_bytes,
            )
            ext = "jpg" if "jpeg" in image_mime else "png"
            file_id = await fs_bucket.upload_from_stream(
                f"ai_front_view_{lead_id}.{ext}",
                image_bytes,
                metadata={
                    "content_type": image_mime,
                    "uploaded_at": _iso(datetime.now(timezone.utc)),
                    "source": "automation",
                    "lead_id": lead_id,
                },
            )
            front_view_url = f"/api/uploads/photo/{file_id}"
            await db.deliverables.update_one(
                {"lead_id": lead_id},
                {"$set": {"front_view_url": front_view_url}},
            )
            logger.info("[automation] Rendering saved: %s", front_view_url)
        except Exception as img_err:
            logger.warning("[automation] Image generation failed (continuing without): %s", img_err)
            image_bytes = None
            front_view_url = None

        # ── Step 3: Build PDF ────────────────────────────────────────────
        logger.info("[automation] Step 3: Building PDF...")
        deliverable_doc = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or plan

        # Resolve customer photos from GridFS
        from bson import ObjectId
        from gridfs.errors import NoFile

        async def _fetch_bytes(url: Optional[str]) -> Optional[bytes]:
            if not url:
                return None
            try:
                if "/api/uploads/photo/" in url:
                    photo_id = url.rsplit("/", 1)[-1]
                    oid = ObjectId(photo_id)
                    stream = await fs_bucket.open_download_stream(oid)
                    return await stream.read()
            except Exception:
                return None
            return None

        images = {
            "front_view": await _fetch_bytes(deliverable_doc.get("front_view_url")),
            "floor_plan": await _fetch_bytes(deliverable_doc.get("floor_plan_url")),
            "view_1": await _fetch_bytes(deliverable_doc.get("view_1_url")),
            "view_2": await _fetch_bytes(deliverable_doc.get("view_2_url")),
            "view_3": await _fetch_bytes(deliverable_doc.get("view_3_url")),
        }
        customer_photos = []
        for p in (lead.get("photos") or [])[:6]:
            url = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
            b = await _fetch_bytes(url)
            if b:
                customer_photos.append(b)
        images["customer_photos"] = customer_photos

        pdf_bytes = build_pdf(lead=lead, deliverable=deliverable_doc, images=images)
        logger.info("[automation] PDF built: %d bytes", len(pdf_bytes))

        # ── Step 4: Send Email ───────────────────────────────────────────
        logger.info("[automation] Step 4: Sending email to %s...", customer_email)
        sent = await send_blueprint(
            customer_name=customer_name,
            customer_email=customer_email,
            space_type=space_type,
            lead_id=lead_id,
            pdf_bytes=pdf_bytes,
        )

        # ── Step 5: Update status ────────────────────────────────────────
        final_status = "delivered" if sent else "pdf_ready"
        await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"status": final_status, "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        logger.info("[automation] Pipeline complete for lead %s — status: %s", lead_id, final_status)
        return sent

    except Exception as e:
        logger.exception("[automation] Pipeline failed for lead %s: %s", lead_id, e)
        await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"status": "error", "automation_error": str(e), "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        return False
