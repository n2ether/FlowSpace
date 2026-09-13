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

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from gridfs.errors import NoFile

from ai_drafter import draft_deliverable
from ai_image_generator import generate_front_view
from email_service import send_blueprint
from pdf_generator import build_pdf
from pdf_images import as_gridfs_source, assemble_pdf_images, choose_hero

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def _fetch_gridfs_bytes(fs_bucket, url: Optional[str]) -> Optional[bytes]:
    """Read a GridFS photo from a relative ``/api/uploads/photo/{id}`` URL."""
    if not url or "/api/uploads/photo/" not in str(url):
        return None
    try:
        photo_id = str(url).rsplit("/", 1)[-1]
        try:
            oid = ObjectId(photo_id)
        except Exception:
            logger.warning("[automation] Invalid GridFS photo id in %s", url)
            return None
        stream = await fs_bucket.open_download_stream(oid)
        data = await stream.read()
        return data or None
    except NoFile:
        logger.warning("[automation] GridFS file missing for %s", url)
        return None
    except Exception as exc:
        logger.warning("[automation] Could not fetch image %s: %s", url, exc)
        return None


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
        organized_bytes: Optional[bytes] = None
        original_bytes: Optional[bytes] = None
        image_mime: str = "image/jpeg"

        # Fetch the customer's own uploaded photo (if any) so FLUX Kontext
        # transforms their ACTUAL room — and so we can use it as a labeled
        # interim hero if generation fails.
        first_photo = (lead.get("photos") or [None])[0]
        if first_photo:
            photo_url = first_photo if isinstance(first_photo, str) else first_photo.get("url")
            original_bytes = await _fetch_gridfs_bytes(fs_bucket, photo_url)
            if original_bytes:
                logger.info("[automation] Using customer's uploaded photo as render reference")

        try:
            organized_bytes, image_mime = await generate_front_view(
                lead=lead,
                deliverable=plan,
                fs_bucket=fs_bucket,
                reference_photo_bytes=original_bytes,
            )
            logger.info(
                "[automation] FLUX organized render ready: %d bytes (%s)",
                len(organized_bytes or b""),
                image_mime,
            )
        except Exception as img_err:
            logger.warning(
                "[automation] FLUX generation failed (soft-fail, PDF continues): %s",
                img_err,
            )
            organized_bytes = None

        # Persist the organized render when we have one. Upload failure must
        # NOT discard in-memory bytes — those still go into build_pdf().
        if organized_bytes:
            try:
                ext = "jpg" if "jpeg" in image_mime else "png"
                file_id = await fs_bucket.upload_from_stream(
                    f"ai_front_view_{lead_id}.{ext}",
                    as_gridfs_source(organized_bytes),
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
                    {"$set": {"front_view_url": front_view_url, "front_view_kind": "organized"}},
                )
                logger.info("[automation] Rendering saved: %s", front_view_url)
            except Exception as upload_err:
                logger.warning(
                    "[automation] GridFS upload failed; keeping in-memory FLUX bytes: %s",
                    upload_err,
                )

        # ── Step 3: Build PDF ────────────────────────────────────────────
        logger.info("[automation] Step 3: Building PDF...")
        deliverable_doc = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or plan

        fetched = {
            "front_view": await _fetch_gridfs_bytes(fs_bucket, deliverable_doc.get("front_view_url")),
            "floor_plan": await _fetch_gridfs_bytes(fs_bucket, deliverable_doc.get("floor_plan_url")),
            "view_1": await _fetch_gridfs_bytes(fs_bucket, deliverable_doc.get("view_1_url")),
            "view_2": await _fetch_gridfs_bytes(fs_bucket, deliverable_doc.get("view_2_url")),
            "view_3": await _fetch_gridfs_bytes(fs_bucket, deliverable_doc.get("view_3_url")),
        }
        customer_photos = []
        for p in (lead.get("photos") or [])[:6]:
            url = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
            b = await _fetch_gridfs_bytes(fs_bucket, url)
            if b:
                customer_photos.append(b)

        # Prefer this-run FLUX bytes, then a previously stored organized render,
        # then the labeled original photo — never drop a real image for a mint panel.
        hero_bytes, hero_kind = choose_hero(
            organized_bytes=organized_bytes or fetched.get("front_view"),
            original_bytes=original_bytes,
        )
        if hero_kind == "original":
            logger.warning(
                "[automation] FLUX unavailable — using labeled customer original as interim hero (%d bytes)",
                len(hero_bytes or b""),
            )
        elif hero_kind == "placeholder":
            logger.warning("[automation] No FLUX render and no original photo — branded placeholder hero")
        else:
            logger.info("[automation] Hero source=organized (%d bytes)", len(hero_bytes or b""))

        images = assemble_pdf_images(
            hero_bytes=hero_bytes,
            hero_kind=hero_kind,
            before=original_bytes,
            after=organized_bytes,
            customer_photos=customer_photos,
            fetched=fetched,
        )
        logger.info(
            "[automation] PDF images: hero=%s (%s bytes) before=%s after=%s views=%s/%s/%s floor_plan=%s photos=%d",
            images.get("front_view_kind"),
            len(images.get("front_view") or b""),
            "y" if images.get("before") else "n",
            "y" if images.get("after") else "n",
            "y" if images.get("view_1") else "n",
            "y" if images.get("view_2") else "n",
            "y" if images.get("view_3") else "n",
            "y" if images.get("floor_plan") else "n",
            len(customer_photos),
        )

        pdf_bytes = build_pdf(lead=lead, deliverable=deliverable_doc, images=images)
        logger.info("[automation] PDF built: %d bytes", len(pdf_bytes))

        # ── Step 4: Send Email ───────────────────────────────────────────
        logger.info("[automation] Step 4: Sending email to %s...", customer_email)
        sent, email_error = await send_blueprint(
            customer_name=customer_name,
            customer_email=customer_email,
            space_type=space_type,
            lead_id=lead_id,
            pdf_bytes=pdf_bytes,
        )

        # ── Step 5: Update status ────────────────────────────────────────
        final_status = "delivered" if sent else "pdf_ready"
        update = {
            "status": final_status,
            "email_sent": bool(sent),
            "updated_at": _iso(datetime.now(timezone.utc)),
        }
        if sent:
            update["email_error"] = None
            update["automation_error"] = None
        else:
            update["email_error"] = email_error or "Email was not sent"
            logger.error("[automation] PDF built but email not sent for %s: %s", lead_id, email_error)
        await db.leads.update_one({"id": lead_id}, {"$set": update})
        logger.info("[automation] Pipeline complete for lead %s — status: %s", lead_id, final_status)
        return sent

    except Exception as e:
        logger.exception("[automation] Pipeline failed for lead %s: %s", lead_id, e)
        await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"status": "error", "automation_error": str(e), "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        return False
