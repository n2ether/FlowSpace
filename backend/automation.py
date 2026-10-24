"""
FlowSpace Automation Pipeline

Triggered after Stripe payment is confirmed.
Full flow:
  1. AI draft the design plan (Claude), using the first room photo
  2. OpenAI Images edit on each required room photo (same camera)
  3. Build the image board, companion PDF, and a review contact sheet
  4. Email the customer board + PDF only when the package is final
  5. Update lead status in MongoDB

A lead with room photos stops at ``review`` until an admin sends the final
package. If any required source fails QA or generation, the package is
``incomplete`` and is not emailed as final. Leads with no room photo keep the
single text-to-image path and may still email that result.
"""
from __future__ import annotations

import asyncio
import logging
import os
import weakref
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from gridfs.errors import NoFile

from ai_drafter import draft_deliverable
from ai_image_generator import (
    BASKET_RETRY_CONSTRAINT,
    CONSISTENCY_REFERENCE_CONSTRAINT,
    SAME_CAMERA_CONSTRAINT,
    WALL_RETRY_CONSTRAINT,
    generate_front_view,
    generate_supporting_views,
    requested_wall_color,
)
from contact_sheet import build_contact_sheet
from email_service import send_blueprint  # kept so tests can patch it; this pipeline does not send
from image_orientation import (
    UnreadableImage,
    normalize_photo_bytes,
    rotate_photo_bytes,
    upright_bytes,
)
from image_board import build_image_board
from pdf_generator import build_pdf
from package_items import (
    consistency_report,
    fixed_retry_constraint,
    room_inventory,
    view_check_inputs,
)
from pdf_images import assemble_pdf_images, choose_hero
from photo_access import gridfs_key, store_photo
from render_qa import RenderQAResult, review_cross_view, review_organized_render, review_same_shot
from render_recovery import heartbeat_loop, touch_render_heartbeat
from source_photos import (
    classify_upload,
    photo_filename,
    photo_id_from_url,
    photo_url,
)

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def _fetch_gridfs(fs_bucket, url: Optional[str]) -> tuple[Optional[bytes], str]:
    """Read a GridFS photo and its stored filename."""
    if not url or "/api/uploads/photo/" not in str(url):
        return None, ""
    try:
        key = gridfs_key(photo_id_from_url(url))
        if key is None:
            logger.warning("[automation] Invalid GridFS photo id in %s", url)
            return None, ""
        stream = await fs_bucket.open_download_stream(key)
        data = await stream.read()
        filename = str(getattr(stream, "filename", "") or "")
        return (data or None), filename
    except NoFile:
        logger.warning("[automation] GridFS file missing for %s", url)
        return None, ""
    except Exception as exc:
        logger.warning("[automation] Could not fetch image %s: %s", url, exc)
        return None, ""


async def _fetch_gridfs_bytes(fs_bucket, url: Optional[str]) -> Optional[bytes]:
    """Read a GridFS photo from a relative ``/api/uploads/photo/{id}`` URL."""
    data, _filename = await _fetch_gridfs(fs_bucket, url)
    return data


def _replace_photo_url(photo: Any, new_url: str) -> Any:
    if isinstance(photo, dict):
        return {**photo, "url": new_url}
    return new_url


async def _persist_upright_original(
    *,
    lead: Dict[str, Any],
    db,
    fs_bucket,
    raw_bytes: bytes,
    index: int = 0,
) -> tuple[bytes, Optional[str]]:
    """Gravity-correct one stored original so retries share the same upright source."""
    try:
        upright, info = await asyncio.to_thread(normalize_photo_bytes, raw_bytes)
    except UnreadableImage as exc:
        logger.warning("[automation] Could not normalize original photo: %s", exc)
        return raw_bytes, None

    if not info.get("applied"):
        return raw_bytes, None

    lead_id = lead.get("id", "unknown")
    try:
        new_url = await store_photo(
            fs_bucket,
            filename=f"original_upright_{lead_id}_{index}.jpg",
            data=upright,
            metadata={
                "content_type": "image/jpeg",
                "uploaded_at": _iso(datetime.now(timezone.utc)),
                "source": "orientation_normalize",
                "lead_id": lead_id,
                "exif_orientation": info.get("exif_orientation"),
                "orientation_normalized": True,
                **({"member_id": lead["member_id"]} if lead.get("member_id") else {}),
            },
        )
        photos = list(lead.get("photos") or [])
        if 0 <= index < len(photos):
            photos[index] = _replace_photo_url(photos[index], new_url)
        elif photos:
            photos[0] = _replace_photo_url(photos[0], new_url)
        else:
            photos = [new_url]
        await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"photos": photos, "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        lead["photos"] = photos
        logger.info(
            "[automation] Persisted EXIF-corrected original for lead %s photo %s (orientation=%s)",
            lead_id,
            index,
            info.get("exif_orientation"),
        )
        return upright, new_url
    except Exception as exc:
        logger.warning("[automation] Could not persist upright original: %s", exc)
        return upright, None


async def _load_lead_photos(lead: Dict[str, Any], db, fs_bucket) -> List[Dict[str, Any]]:
    """Upright every upload and mark which ones are required room photos."""
    loaded: List[Dict[str, Any]] = []
    for index, photo in enumerate(list(lead.get("photos") or [])):
        url = photo_url(photo)
        raw, stored_name = await _fetch_gridfs(fs_bucket, url)
        filename = stored_name or photo_filename(photo)
        upright = raw
        if raw:
            upright, new_url = await _persist_upright_original(
                lead=lead,
                db=db,
                fs_bucket=fs_bucket,
                raw_bytes=raw,
                index=index,
            )
            if new_url:
                url = new_url
                photo = _replace_photo_url(photo, new_url)
        kind, reason = await asyncio.to_thread(
            classify_upload, photo, upright, filename=filename
        )
        loaded.append(
            {
                "index": index,
                "url": url,
                "photo_id": photo_id_from_url(url),
                "filename": filename,
                "bytes": upright,
                "kind": kind,
                "reason": reason,
            }
        )
        logger.info(
            "[automation] Upload %s classified %s (%s) id=%s",
            index,
            kind,
            reason,
            photo_id_from_url(url),
        )
    return loaded


def _qa_retry_reference(original_bytes: Optional[bytes], qa: RenderQAResult) -> Optional[bytes]:
    if not original_bytes:
        return None
    degrees = qa.suggested_rotate_degrees if qa.gravity_wrong else 0
    if degrees:
        try:
            logger.info("[automation] Retrying OpenAI image edit with source rotated %s°", degrees)
            return rotate_photo_bytes(original_bytes, degrees)
        except Exception as exc:
            logger.warning("[automation] Could not rotate source for QA retry: %s", exc)
    return original_bytes


def _qa_retry_extra(qa: RenderQAResult, paint_request: str = "") -> str:
    bits: list[str] = []
    if qa.walls_repainted and not paint_request:
        bits.append(WALL_RETRY_CONSTRAINT)
    if qa.camera_changed:
        bits.append(CAMERA_RETRY_CONSTRAINT)
    if qa.fixed_items_changed:
        bits.append(fixed_retry_constraint(qa.fixed_items_altered or [], qa.fixed_items_missing or []))
    if qa.baskets_misplaced:
        bits.append(BASKET_RETRY_CONSTRAINT)
    if qa.avoid_seen:
        bits.append("FAILED QA: the view showed what the brief rules out: " + "; ".join(qa.avoid_seen) + ". Remove it.")
    bits.extend(qa.reasons[:3])
    return " ".join(bits)


CAMERA_RETRY_CONSTRAINT = (
    "FAILED QA: the last render showed a different camera view than the source photo. Keep this photo's "
    "exact framing and subject; if it is a close-up, the organized view is the same close-up, not the whole room."
)

CROSS_VIEW_RETRY_CONSTRAINT = (
    "FAILED CROSS-VIEW CHECK: this view shows a piece differently from the reference view of the same room. "
    "Make each listed piece identical to the reference (structure, doors and glass, drawers, color, material, "
    "size) while keeping this photo's own camera: "
)


def _qa_item_kwargs(lead: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """The room inventory's fixed pieces, additions, and avoid rules that every view's QA checks."""
    return view_check_inputs(room_inventory(lead, plan))


def _stamp_qa(qa: Dict[str, Any], inventory_hash: str, after_url: Optional[str]) -> Dict[str, Any]:
    """Record which inventory and which stored image this check covered."""
    return {**qa, "inventory_hash": inventory_hash, "checked_after_url": after_url or ""}


def _with_view_reference(extra: str, has_reference: bool) -> str:
    if not has_reference:
        return extra
    return f"{extra} {CONSISTENCY_REFERENCE_CONSTRAINT}".strip()


def _same_camera_extra(extra: str) -> str:
    """Keep each source edit on that photo's camera. QA text is appended."""
    extra = (extra or "").strip()
    if SAME_CAMERA_CONSTRAINT in extra:
        return extra
    return f"{SAME_CAMERA_CONSTRAINT} {extra}".strip()


async def _check_same_shot(qa: RenderQAResult, before: Optional[bytes], after: Optional[bytes]) -> RenderQAResult:
    """Fail a view that passed QA but is not an edit of its source photo's shot."""
    if qa.failed or not before or not after:
        return qa
    same, reason = await asyncio.to_thread(review_same_shot, before_bytes=before, after_bytes=after)
    if same is False:
        qa.camera_changed = True
        qa.ok = False
        qa.reasons = list(qa.reasons) + [f"Different shot from the source photo: {reason}".strip()]
    return qa


async def _generate_organized_with_qa(
    *,
    lead: Dict[str, Any],
    plan: Dict[str, Any],
    fs_bucket,
    original_bytes: Optional[bytes],
    view_reference: Optional[bytes] = None,
    extra_constraint: str = "",
) -> tuple[Optional[bytes], str, RenderQAResult]:
    """OpenAI image once, cheap vision QA, one retry with stronger rails, then give up.

    ``view_reference`` is an already approved after of the same room. It rides
    along as a second image so fixed furniture and planned items match it.
    ``extra_constraint`` is added to both attempts (a cross-view repair note).
    """
    organized_bytes: Optional[bytes] = None
    image_mime = "image/jpeg"
    qa = RenderQAResult(ok=True, skipped=True, error="not_run")
    paint_request = requested_wall_color(lead, plan)
    item_qa = _qa_item_kwargs(lead, plan)
    has_reference = bool(view_reference and original_bytes)
    reference_kw = {"consistency_reference": view_reference} if has_reference else {}
    first_extra = f"{_same_camera_extra('')} {extra_constraint}".strip() if original_bytes else extra_constraint

    try:
        organized_bytes, image_mime = await generate_front_view(
            lead=lead,
            deliverable=plan,
            fs_bucket=fs_bucket,
            reference_photo_bytes=original_bytes,
            extra_constraint=_with_view_reference(first_extra, has_reference) if original_bytes else first_extra,
            **reference_kw,
        )
        logger.info(
            "[automation] OpenAI organized render ready: %d bytes (%s)",
            len(organized_bytes or b""),
            image_mime,
        )
    except Exception as img_err:
        logger.warning(
            "[automation] OpenAI image generation failed (soft-fail, PDF continues): %s",
            img_err,
        )
        return None, image_mime, RenderQAResult(ok=False, reasons=[str(img_err)], error="generate_failed")

    qa = await asyncio.to_thread(
        review_organized_render,
        after_bytes=organized_bytes,
        before_bytes=original_bytes,
        attempt=1,
        paint_request=paint_request,
        **item_qa,
    )
    qa = await _check_same_shot(qa, original_bytes, organized_bytes)
    if not qa.failed:
        return organized_bytes, image_mime, qa

    logger.warning(
        "[automation] Organized render failed QA (attempt 1): windows_covered=%s gravity_wrong=%s walls_repainted=%s camera_changed=%s reasons=%s",
        qa.windows_covered,
        qa.gravity_wrong,
        qa.walls_repainted,
        qa.camera_changed,
        qa.reasons,
    )
    retry_ref = _qa_retry_reference(original_bytes, qa)
    extra = f"{extra_constraint} {_qa_retry_extra(qa, paint_request)}".strip()
    try:
        organized_bytes, image_mime = await generate_front_view(
            lead=lead,
            deliverable=plan,
            fs_bucket=fs_bucket,
            reference_photo_bytes=retry_ref,
            stronger_rails=True,
            extra_constraint=_with_view_reference(_same_camera_extra(extra), has_reference) if original_bytes else extra,
            **reference_kw,
        )
    except Exception as img_err:
        logger.warning("[automation] OpenAI image QA retry failed: %s", img_err)
        return None, image_mime, RenderQAResult(
            ok=False,
            windows_covered=qa.windows_covered,
            gravity_wrong=qa.gravity_wrong,
            walls_repainted=qa.walls_repainted,
            camera_changed=qa.camera_changed,
            reasons=list(qa.reasons) + [f"retry generate failed: {img_err}"],
            attempt=2,
            error="retry_generate_failed",
        )

    qa2 = await asyncio.to_thread(
        review_organized_render,
        after_bytes=organized_bytes,
        before_bytes=retry_ref or original_bytes,
        attempt=2,
        paint_request=paint_request,
        **item_qa,
    )
    qa2 = await _check_same_shot(qa2, retry_ref or original_bytes, organized_bytes)
    if qa2.failed:
        logger.error(
            "[automation] Organized render still failed QA after retry — discarding after "
            "(will not embed a broken organized image). reasons=%s",
            qa2.reasons,
        )
        return None, image_mime, qa2
    if qa2.skipped:
        logger.warning(
            "[automation] QA skipped on retry; keeping stronger-rails render. error=%s",
            qa2.error,
        )
    return organized_bytes, image_mime, qa2


async def _cross_view_round(inventory: Dict[str, Any], approved: List[Dict[str, Any]]):
    inputs = view_check_inputs(inventory)
    return await asyncio.to_thread(
        review_cross_view,
        views=[(item["after_label"], item["after_bytes"]) for item in approved],
        fixed_items=inputs["fixed_items"],
        additions=inputs["additions"],
    )


async def _cross_view_check(
    *,
    lead: Dict[str, Any],
    plan: Dict[str, Any],
    inventory: Dict[str, Any],
    outcomes: List[Dict[str, Any]],
    fs_bucket,
    lead_id: str,
) -> Optional[Dict[str, Any]]:
    """Compare every approved after for the shared pieces; re-edit mismatched views once.

    The first approved after is the reference. A view that shows a piece
    differently is re-edited from its own source photo with the reference
    attached and the mismatch named. Its replacement must pass the per-view
    check; otherwise the earlier after stays and the mismatch is recorded, so
    the consistency report blocks the final send. ``None`` for fewer than two views.
    """
    approved = [item for item in outcomes if item.get("after_bytes")]
    if len(approved) < 2:
        return None
    result = await _cross_view_round(inventory, approved)
    repaired: List[str] = []
    if result.mismatches and not result.skipped:
        reference = approved[0]
        for item in approved[1:]:
            notes = [
                f"{row['name']}" + (f" ({row['difference']})" if row.get("difference") else "")
                for row in result.mismatches
                if item["after_label"] in row.get("views", [])
            ]
            if not notes:
                continue
            after_bytes, mime, qa = await _generate_organized_with_qa(
                lead=lead,
                plan=plan,
                fs_bucket=fs_bucket,
                original_bytes=item.get("before_bytes"),
                view_reference=reference["after_bytes"],
                extra_constraint=CROSS_VIEW_RETRY_CONSTRAINT + "; ".join(notes) + ".",
            )
            if not after_bytes:
                logger.warning("[automation] %s cross-view repair did not pass QA; keeping the earlier after", item["after_label"])
                continue
            ext = "jpg" if "jpeg" in (mime or "") else "png"
            url = await _store_bytes(
                fs_bucket,
                filename=f"ai_{item['label'].lower()}_xview_{lead_id}.{ext}",
                data=after_bytes,
                mime=mime or "image/jpeg",
                lead_id=lead_id,
                slot=item["label"].lower(),
                source_photo_id=item.get("source_photo_id") or "",
            )
            if not url:
                continue
            item.update(
                {
                    "after_bytes": after_bytes,
                    "after_url": url,
                    "qa": _stamp_qa(qa.as_dict(), inventory["hash"], url),
                }
            )
            repaired.append(item["after_label"])
        if repaired:
            result = await _cross_view_round(inventory, approved)
    logger.info(
        "[automation] Cross-view check: ok=%s skipped=%s mismatches=%s repaired=%s",
        result.ok,
        result.skipped,
        [row["name"] for row in result.mismatches],
        repaired,
    )
    return {
        **result.as_dict(),
        "inventory_hash": inventory["hash"],
        "after_urls": [item.get("after_url") or "" for item in approved],
        "repaired": repaired,
    }


async def _clear_stale_render_slots(db, lead_id: str) -> None:
    """Drop previous afters and extra views so this run cannot mix them in."""
    await db.deliverables.update_one(
        {"lead_id": lead_id},
        {
            "$set": {
                "front_view_url": None,
                "view_1_url": None,
                "view_2_url": None,
                "view_3_url": None,
                "front_view_kind": None,
                "source_afters": [],
                "cross_view": None,
                "non_room_uploads": [],
                "contact_sheet_url": None,
                "package_status": None,
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
        upsert=True,
    )


async def _store_bytes(
    fs_bucket,
    *,
    filename: str,
    data: bytes,
    mime: str,
    lead_id: str,
    **meta: Any,
) -> Optional[str]:
    try:
        return await store_photo(
            fs_bucket,
            filename=filename,
            data=data,
            metadata={
                "content_type": mime,
                "uploaded_at": _iso(datetime.now(timezone.utc)),
                "source": "automation",
                "lead_id": lead_id,
                **meta,
            },
        )
    except Exception as exc:
        logger.warning("[automation] GridFS upload failed for %s: %s", filename, exc)
        return None


def _public_source_after(outcome: Dict[str, Any]) -> Dict[str, Any]:
    """Durable SOURCE_n → AFTER_n mapping. Image bytes stay in GridFS.

    ``edit_kind`` is ``own_source`` only when this after was edited from that
    same photo. A crop or a view taken from a different source must not be
    stored under this flag.
    """
    source_id = outcome.get("source_photo_id") or ""
    approved = outcome.get("status") == "approved" and bool(outcome.get("after_url"))
    return {
        "source_photo_id": source_id,
        "source_url": outcome.get("source_url"),
        "label": outcome.get("label"),
        "after_label": outcome.get("after_label"),
        "after_url": outcome.get("after_url"),
        "status": outcome.get("status"),
        "kind": "room",
        "edit_kind": "own_source" if approved else "missing",
        "derived_from_photo_id": source_id if approved else "",
        "qa": outcome.get("qa") or {},
    }


async def _store_supporting_views(
    *,
    supporting: Dict[str, bytes],
    db,
    fs_bucket,
    lead_id: str,
) -> None:
    for slot, blob in supporting.items():
        ext = "jpg" if blob[:2] == b"\xff\xd8" else "png"
        mime = "image/jpeg" if ext == "jpg" else "image/png"
        url = await _store_bytes(
            fs_bucket,
            filename=f"ai_{slot}_{lead_id}.{ext}",
            data=blob,
            mime=mime,
            lead_id=lead_id,
            slot=slot,
        )
        if url:
            await db.deliverables.update_one(
                {"lead_id": lead_id},
                {"$set": {f"{slot}_url": url}},
            )


_RENDER_SEMAPHORES: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


def render_concurrency() -> int:
    """Max concurrent run_automation renders (env RENDER_CONCURRENCY, default 3)."""
    try:
        return max(1, int(os.environ.get("RENDER_CONCURRENCY", "3")))
    except ValueError:
        return 3


def _render_semaphore() -> asyncio.Semaphore:
    # One semaphore per event loop (a semaphore is bound to the loop that uses it).
    loop = asyncio.get_running_loop()
    sem = _RENDER_SEMAPHORES.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(render_concurrency())
        _RENDER_SEMAPHORES[loop] = sem
    return sem


async def run_automation(
    *,
    lead: Dict[str, Any],
    db,
    fs_bucket,
) -> bool:
    """Run the pipeline, capping concurrent renders at RENDER_CONCURRENCY.

    The heartbeat runs while the lead waits for a slot too, so a long queue is
    not mistaken for a render orphaned by a restart.
    """
    ticker = asyncio.create_task(heartbeat_loop(db, lead.get("id")))
    try:
        async with _render_semaphore():
            return await _run_automation(lead=lead, db=db, fs_bucket=fs_bucket)
    finally:
        ticker.cancel()
        try:
            await ticker
        except (asyncio.CancelledError, Exception):
            pass


async def _run_automation(
    *,
    lead: Dict[str, Any],
    db,
    fs_bucket,
) -> bool:
    """
    Run the full automation pipeline for a lead.

    Returns True when the package is held for review (a finished photo package,
    or a conceptual plan with no room photo). Nothing here emails the customer.
    Returns False when a required source failed, or the pipeline raised.
    """
    lead_id = lead.get("id", "unknown")
    customer_name = lead.get("name", "there")
    customer_email = lead.get("email", "")

    logger.info("[automation] Starting pipeline for lead %s (%s)", lead_id, customer_email)

    await db.leads.update_one(
        {"id": lead_id},
        {
            "$set": {
                "status": "processing",
                "automation_failed": False,
                "render_heartbeat_at": _iso(datetime.now(timezone.utc)),
                "updated_at": _iso(datetime.now(timezone.utc)),
            }
        },
    )

    try:
        # ── Step 0: Upright uploads and separate room photos from screenshots ─
        loaded = await _load_lead_photos(lead, db, fs_bucket)
        room = [photo for photo in loaded if photo.get("kind") == "room"]
        non_room = [photo for photo in loaded if photo.get("kind") != "room"]
        draft_bytes = next((photo.get("bytes") for photo in room if photo.get("bytes")), None)
        await touch_render_heartbeat(db, lead_id)
        if room:
            logger.info(
                "[automation] %d required room photo(s), %d non-room upload(s)",
                len(room),
                len(non_room),
            )
        elif loaded:
            logger.info("[automation] No room photos among %d upload(s); skipping per-source edits", len(loaded))

        # ── Step 1: AI Draft (Claude + layers, with the first room photo) ──
        logger.info("[automation] Step 1: AI drafting plan...")
        extra_photos = [photo.get("bytes") for photo in room if photo.get("bytes")][1:]
        plan = await draft_deliverable(
            lead,
            reference_photo_bytes=draft_bytes,
            **({"extra_photo_bytes": extra_photos} if extra_photos else {}),
        )
        plan["lead_id"] = lead_id
        if lead.get("fact_sheet"):
            plan["fact_sheet"] = lead["fact_sheet"]
        inventory = room_inventory(lead, plan)
        plan["room_inventory"] = inventory
        plan["updated_at"] = _iso(datetime.now(timezone.utc))
        stored = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0, "package_version": 1})
        if not (stored or {}).get("package_version"):
            plan["package_version"] = 1
        await db.deliverables.update_one(
            {"lead_id": lead_id},
            {"$set": plan},
            upsert=True,
        )
        logger.info("[automation] Plan drafted and saved")
        await touch_render_heartbeat(db, lead_id)

        # Old view_* / after URLs must not survive into this run.
        await _clear_stale_render_slots(db, lead_id)

        supporting: Dict[str, bytes] = {}
        outcomes: List[Dict[str, Any]] = []
        organized_bytes: Optional[bytes] = None
        original_bytes: Optional[bytes] = draft_bytes
        multi = len(room) >= 2

        if room:
            logger.info("[automation] Step 2: Editing %d room photo(s) via OpenAI...", len(room))
            for number, src in enumerate(room, start=1):
                label = f"SOURCE_{number:02d}"
                after_label = f"AFTER_{number:02d}"
                if not src.get("bytes"):
                    outcomes.append(
                        {
                            "source_photo_id": src.get("photo_id") or "",
                            "source_url": src.get("url"),
                            "label": label,
                            "after_label": after_label,
                            "after_url": None,
                            "status": "failed",
                            "qa": RenderQAResult(
                                ok=False,
                                reasons=["source photo could not be read"],
                                error="missing_source",
                            ).as_dict(),
                            "after_bytes": None,
                            "before_bytes": None,
                        }
                    )
                    logger.warning("[automation] %s has no readable photo; source failed", label)
                    continue
                view_reference = next(
                    (item.get("after_bytes") for item in outcomes if item.get("after_bytes")), None
                )
                after_bytes, mime, qa = await _generate_organized_with_qa(
                    lead=lead,
                    plan=plan,
                    fs_bucket=fs_bucket,
                    original_bytes=src.get("bytes"),
                    view_reference=view_reference,
                )
                after_url = None
                if after_bytes:
                    ext = "jpg" if "jpeg" in (mime or "") else "png"
                    after_url = await _store_bytes(
                        fs_bucket,
                        filename=f"ai_{label.lower()}_{lead_id}.{ext}",
                        data=after_bytes,
                        mime=mime or "image/jpeg",
                        lead_id=lead_id,
                        slot=label.lower(),
                        source_photo_id=src.get("photo_id") or "",
                    )
                approved = bool(after_bytes and after_url)
                await touch_render_heartbeat(db, lead_id)
                if after_bytes and not after_url:
                    logger.warning(
                        "[automation] %s render could not be stored; source stays incomplete",
                        label,
                    )
                outcomes.append(
                    {
                        "source_photo_id": src.get("photo_id") or "",
                        "source_url": src.get("url"),
                        "label": label,
                        "after_label": after_label,
                        "after_url": after_url,
                        "status": "approved" if approved else "failed",
                        "qa": _stamp_qa(qa.as_dict(), inventory["hash"], after_url),
                        "after_bytes": after_bytes if approved else None,
                        "before_bytes": src.get("bytes"),
                    }
                )
                logger.info(
                    "[automation] %s → %s status=%s photo=%s",
                    label,
                    after_label,
                    "approved" if approved else "failed",
                    src.get("photo_id"),
                )

            cross_view = await _cross_view_check(
                lead=lead,
                plan=plan,
                inventory=inventory,
                outcomes=outcomes,
                fs_bucket=fs_bucket,
                lead_id=lead_id,
            )
            await touch_render_heartbeat(db, lead_id)

            failed = [item for item in outcomes if item["status"] != "approved"]
            render_qa_source = failed[0] if failed else outcomes[-1]
            summary_qa = dict(render_qa_source.get("qa") or {})
            approved_afters = [item for item in outcomes if item.get("after_bytes")]
            organized_bytes = approved_afters[0]["after_bytes"] if approved_afters else None
            incomplete = bool(failed)

            # Hero-derived extras are optional details for a single source.
            # Several room photos already are the angles — do not invent more.
            if len(room) == 1 and organized_bytes and not incomplete:
                try:
                    supporting = await generate_supporting_views(
                        lead=lead,
                        deliverable=plan,
                        reference_photo_bytes=original_bytes,
                        organized_bytes=organized_bytes,
                    )
                except Exception as view_err:
                    logger.warning(
                        "[automation] Optional detail views failed (soft-fail): %s",
                        view_err,
                    )
                    supporting = {}
                await _store_supporting_views(
                    supporting=supporting,
                    db=db,
                    fs_bucket=fs_bucket,
                    lead_id=lead_id,
                )
            elif multi:
                logger.info(
                    "[automation] Not inventing supporting angles from the hero (%d source photos)",
                    len(room),
                )
                supporting = {}

            source_pairs = [
                {
                    "label": item["label"],
                    "after_label": item["after_label"],
                    "source_photo_id": item["source_photo_id"],
                    "status": item["status"],
                    "before": item.get("before_bytes"),
                    "after": item.get("after_bytes"),
                    "visible_additions": list((item.get("qa") or {}).get("visible_additions") or []),
                }
                for item in outcomes
            ]
            if organized_bytes:
                hero_bytes, hero_kind = organized_bytes, "organized"
            elif original_bytes:
                hero_bytes, hero_kind = original_bytes, "original"
            else:
                hero_bytes, hero_kind = None, "placeholder"

            customer_photos = [item["before_bytes"] for item in outcomes if item.get("before_bytes")]
            images = assemble_pdf_images(
                hero_bytes=hero_bytes,
                hero_kind=hero_kind,
                before=original_bytes,
                after=organized_bytes,
                view_1=None if multi else supporting.get("view_1"),
                view_2=None if multi else supporting.get("view_2"),
                view_3=None if multi else supporting.get("view_3"),
                customer_photos=customer_photos,
                source_pairs=source_pairs,
                fetched={},
            )
            package_status = "incomplete" if incomplete else "review"
            contact_bytes = await asyncio.to_thread(
                build_contact_sheet,
                source_pairs,
                customer_name=customer_name,
                incomplete=incomplete,
            )
            contact_sheet_url = await _store_bytes(
                fs_bucket,
                filename=f"contact_sheet_{lead_id}.png",
                data=contact_bytes,
                mime="image/png",
                lead_id=lead_id,
                slot="contact_sheet",
            )
            front_view_url = approved_afters[0]["after_url"] if approved_afters else None
            await db.deliverables.update_one(
                {"lead_id": lead_id},
                {
                    "$set": {
                        "render_qa": summary_qa,
                        "source_afters": [_public_source_after(item) for item in outcomes],
                        "cross_view": cross_view,
                        "room_inventory": inventory,
                        "required_source_ids": [
                            str(photo.get("photo_id") or "")
                            for photo in room
                            if str(photo.get("photo_id") or "")
                        ],
                        "non_room_uploads": [
                            {
                                "photo_id": photo.get("photo_id") or "",
                                "url": photo.get("url"),
                                "filename": photo.get("filename") or "",
                                "reason": photo.get("reason") or "",
                            }
                            for photo in non_room
                        ],
                        "package_status": package_status,
                        "contact_sheet_url": contact_sheet_url,
                        "front_view_url": front_view_url,
                        "front_view_kind": hero_kind,
                        "updated_at": _iso(datetime.now(timezone.utc)),
                    }
                },
            )
        else:
            logger.info("[automation] Step 2: No room photo — text-to-image fallback...")
            organized_bytes, _image_mime, render_qa = await _generate_organized_with_qa(
                lead=lead,
                plan=plan,
                fs_bucket=fs_bucket,
                original_bytes=None,
            )
            summary_qa = render_qa.as_dict()
            if organized_bytes:
                ext = "jpg" if organized_bytes[:2] == b"\xff\xd8" else "png"
                mime = "image/jpeg" if ext == "jpg" else "image/png"
                front_view_url = await _store_bytes(
                    fs_bucket,
                    filename=f"ai_front_view_{lead_id}.{ext}",
                    data=organized_bytes,
                    mime=mime,
                    lead_id=lead_id,
                    slot="front_view",
                )
                if front_view_url:
                    await db.deliverables.update_one(
                        {"lead_id": lead_id},
                        {"$set": {"front_view_url": front_view_url, "front_view_kind": "organized"}},
                    )
                try:
                    supporting = await generate_supporting_views(
                        lead=lead,
                        deliverable=plan,
                        reference_photo_bytes=None,
                        organized_bytes=organized_bytes,
                    )
                except Exception as view_err:
                    logger.warning(
                        "[automation] Supporting views failed (soft-fail, board keeps hero crops): %s",
                        view_err,
                    )
                    supporting = {}
                await _store_supporting_views(
                    supporting=supporting,
                    db=db,
                    fs_bucket=fs_bucket,
                    lead_id=lead_id,
                )
            else:
                await db.deliverables.update_one(
                    {"lead_id": lead_id},
                    {
                        "$set": {
                            "front_view_url": None,
                            "view_1_url": None,
                            "view_2_url": None,
                            "view_3_url": None,
                            "front_view_kind": "placeholder",
                            "updated_at": _iso(datetime.now(timezone.utc)),
                        }
                    },
                )
            await db.deliverables.update_one(
                {"lead_id": lead_id},
                {"$set": {"render_qa": summary_qa, "updated_at": _iso(datetime.now(timezone.utc))}},
            )
            hero_bytes, hero_kind = choose_hero(
                organized_bytes=organized_bytes,
                original_bytes=None,
            )
            images = assemble_pdf_images(
                hero_bytes=hero_bytes,
                hero_kind=hero_kind,
                before=None,
                after=organized_bytes,
                view_1=supporting.get("view_1"),
                view_2=supporting.get("view_2"),
                view_3=supporting.get("view_3"),
                customer_photos=[],
                fetched={},
            )

        logger.info(
            "[automation] PDF images: hero=%s before=%s after=%s pairs=%d views=%s/%s/%s",
            images.get("front_view_kind"),
            "y" if images.get("before") else "n",
            "y" if images.get("after") else "n",
            len(images.get("source_pairs") or []),
            "y" if images.get("view_1") else "n",
            "y" if images.get("view_2") else "n",
            "y" if images.get("view_3") else "n",
        )

        await touch_render_heartbeat(db, lead_id)
        deliverable_doc = await db.deliverables.find_one({"lead_id": lead_id}, {"_id": 0}) or plan
        try:
            report = await asyncio.to_thread(consistency_report, lead, deliverable_doc)
        except Exception as report_err:
            logger.warning("[automation] Consistency check failed to run: %s", report_err)
            report = {"ok": False, "issues": [{"code": "check_error", "severity": "warn", "message": str(report_err)}], "blocking": 0}
        await db.deliverables.update_one(
            {"lead_id": lead_id},
            {"$set": {"consistency": report, "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        deliverable_doc["consistency"] = report
        logger.info(
            "[automation] Consistency check: ok=%s blocking=%s issues=%d",
            report.get("ok"),
            report.get("blocking"),
            len(report.get("issues") or []),
        )
        pdf_bytes = await asyncio.to_thread(
            build_pdf, lead=lead, deliverable=deliverable_doc, images=images
        )
        board_bytes = await asyncio.to_thread(
            build_image_board, lead=lead, deliverable=deliverable_doc, images=images
        )
        logger.info(
            "[automation] Companion PDF %d bytes, image board %d bytes",
            len(pdf_bytes),
            len(board_bytes),
        )

        if room:
            # Review sheet is ready. The customer board and PDF stay unsent
            # until an admin marks the package final. Incomplete never emails.
            note = (
                "DRAFT. Review version. Not yet approved. Customer release held. A required room photo is still missing."
                if package_status == "incomplete"
                else "DRAFT. Review version. Not yet approved. Customer release held."
            )
            await db.leads.update_one(
                {"id": lead_id},
                {
                    "$set": {
                        "status": package_status,
                        "package_status": package_status,
                        "email_sent": False,
                        "email_error": None,
                        "automation_error": None if package_status == "review" else note,
                        "automation_note": note,
                        "updated_at": _iso(datetime.now(timezone.utc)),
                    }
                },
            )
            logger.info("[automation] Lead %s package_status=%s (no final email)", lead_id, package_status)
            return package_status == "review"

        # No room photo: hold the package. Regeneration and automation never email.
        note = "DRAFT. Review version. Not yet approved. Customer release held."
        if lead.get("intake"):
            note += " Conceptual plan (no photos)."
        await db.deliverables.update_one(
            {"lead_id": lead_id},
            {"$set": {"package_status": "review", "updated_at": _iso(datetime.now(timezone.utc))}},
        )
        await db.leads.update_one(
            {"id": lead_id},
            {
                "$set": {
                    "status": "review",
                    "package_status": "review",
                    "email_sent": False,
                    "email_error": None,
                    "automation_error": None,
                    "automation_note": note,
                    "updated_at": _iso(datetime.now(timezone.utc)),
                }
            },
        )
        logger.info("[automation] Lead %s package held for review (no email)", lead_id)
        return True

    except Exception as e:
        logger.exception("[automation] Pipeline failed for lead %s: %s", lead_id, e)
        # Held for admin review/retry. automation_error and automation_failed_at
        # are admin-only; customers only ever see "In review".
        now = _iso(datetime.now(timezone.utc))
        await db.leads.update_one(
            {"id": lead_id},
            {
                "$set": {
                    "status": "review",
                    "package_status": "review",
                    "email_sent": False,
                    "automation_failed": True,
                    "automation_error": str(e) or e.__class__.__name__,
                    "automation_failed_at": now,
                    "automation_note": "Generation failed. Held for review. Retry automation from the admin.",
                    "updated_at": now,
                }
            },
        )
        return False
