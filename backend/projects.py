"""Project (room transformation) routes + background AI pipeline (multi-photo)."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel

from db import db
from auth import get_current_user
from plans import plan_cfg, ROOM_TYPES, STYLES, ROOM_LABELS
import email_service
import replicate_service
import room_service
import storage_service

logger = logging.getLogger(__name__)
projects_router = APIRouter(prefix="/api/projects")
APP_NAME = storage_service.APP_NAME


class ProjectCreate(BaseModel):
    room_type: str
    style: str
    photos: List[str]  # 1..max base64 data URLs (different angles of the same space)
    language: str = "en"


def _public(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "_id"}


async def _process(project_id, user_id, plan, room_type, style, items_payload, language):
    """items_payload: list of {id, data_uri, original_storage_path}."""
    cfg = plan_cfg(plan)
    results = {}            # item_id -> (generated_path|None, status)
    succeeded_pairs = []    # (before_bytes, after_bytes)

    prompt = room_service.build_prompt(room_type, style)
    for it in items_payload:
        try:
            gen_bytes = await replicate_service.generate_organized_image(prompt, it["data_uri"])
            display_bytes = room_service.add_watermark(gen_bytes) if cfg["watermark"] else gen_bytes
            gen_path = f"{APP_NAME}/generated-room-images/{user_id}/{uuid.uuid4().hex}.jpg"
            await storage_service.put_object_async(gen_path, display_bytes, "image/jpeg")
            results[it["id"]] = (gen_path, "complete")
            _, before_raw = room_service.strip_data_url(it["data_uri"])
            succeeded_pairs.append((before_raw, gen_bytes))
        except Exception as e:
            logger.exception(f"Photo {it['id']} of project {project_id} failed: {e}")
            results[it["id"]] = (None, "failed")

    # Rebuild the items list with generated paths + per-photo status.
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "items": 1})
    new_items = []
    for it in (project or {}).get("items", []):
        gp, st = results.get(it["id"], (None, "failed"))
        new_items.append({**it, "generated_storage_path": gp, "status": st})

    succeeded = len(succeeded_pairs)
    failed = len(items_payload) - succeeded
    if failed > 0:
        # Refund credits for the photos that didn't generate.
        await db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"monthly_generations_used": -failed}},
        )
        await db.users.update_one(
            {"user_id": user_id, "monthly_generations_used": {"$lt": 0}},
            {"$set": {"monthly_generations_used": 0}},
        )

    if succeeded == 0:
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"items": new_items, "status": "failed", "error": "All photos failed to generate",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return

    plan_data = await room_service.generate_room_plan(room_type, style, language)

    pdf_path = None
    email_sent = False
    if cfg["pdf"]:
        udoc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1, "email": 1})
        uname = (udoc or {}).get("name", "there")
        uemail = (udoc or {}).get("email", "")
        pdf_bytes = await asyncio.to_thread(
            room_service.build_room_pdf,
            user_name=uname, room_type=room_type, style=style, plan=plan_data,
            pairs=succeeded_pairs, with_affiliate=cfg["affiliate"],
        )
        pdf_path = f"{APP_NAME}/project-pdfs/{user_id}/{uuid.uuid4().hex}.pdf"
        await storage_service.put_object_async(pdf_path, pdf_bytes, "application/pdf")
        email_sent = await email_service.send_plan_email(
            uemail, uname, ROOM_LABELS.get(room_type, room_type), pdf_bytes
        )

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "items": new_items,
            "organization_plan": plan_data,
            "shopping_list": plan_data.get("shopping_list", []),
            "organization_score": plan_data.get("organization_score"),
            "estimated_cost": plan_data.get("estimated_cost"),
            "estimated_time": plan_data.get("estimated_time"),
            "difficulty": plan_data.get("difficulty"),
            "pdf_storage_path": pdf_path,
            "email_sent": email_sent,
            "watermarked": cfg["watermark"],
            "status": "complete" if failed == 0 else "partial",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


@projects_router.post("")
async def create_project(payload: ProjectCreate, background: BackgroundTasks, request: Request):
    user = await get_current_user(request)
    if payload.room_type not in ROOM_TYPES:
        raise HTTPException(status_code=400, detail="Invalid room_type")
    if payload.style not in STYLES:
        raise HTTPException(status_code=400, detail="Invalid style")

    n = len(payload.photos)
    cfg = plan_cfg(user.get("subscription_plan", "free"))
    if n < 1:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if n > cfg["max_photos"]:
        raise HTTPException(status_code=400, detail=f"too_many_photos:{cfg['max_photos']}")

    used = user.get("monthly_generations_used", 0)
    if used + n > cfg["limit"]:
        raise HTTPException(status_code=402, detail="credit_limit_reached")

    user_id = user["user_id"]
    items = []
    items_payload = []
    for ph in payload.photos:
        try:
            _, raw = room_service.strip_data_url(ph)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image")
        data_uri = room_service.downscale_to_data_uri(raw)
        orig_path = f"{APP_NAME}/original-room-images/{user_id}/{uuid.uuid4().hex}.jpg"
        await storage_service.put_object_async(orig_path, raw, "image/jpeg")
        iid = uuid.uuid4().hex[:10]
        items.append({"id": iid, "original_storage_path": orig_path,
                      "generated_storage_path": None, "status": "processing"})
        items_payload.append({"id": iid, "data_uri": data_uri, "original_storage_path": orig_path})

    now = datetime.now(timezone.utc).isoformat()
    project = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "room_type": payload.room_type,
        "style": payload.style,
        "items": items,
        "photo_count": n,
        "organization_plan": None,
        "shopping_list": [],
        "pdf_storage_path": None,
        "status": "processing",
        "watermarked": cfg["watermark"],
        "language": payload.language,
        "created_at": now,
        "updated_at": now,
    }
    await db.projects.insert_one(dict(project))

    # Consume one credit per photo up-front (refunded per-photo on failure).
    await db.users.update_one({"user_id": user_id}, {"$inc": {"monthly_generations_used": n}})

    background.add_task(_process, project["id"], user_id, user.get("subscription_plan", "free"),
                        payload.room_type, payload.style, items_payload, payload.language)
    return _public(project)


@projects_router.get("")
async def list_projects(request: Request):
    user = await get_current_user(request)
    return await db.projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


@projects_router.get("/{project_id}")
async def get_project(project_id: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@projects_router.get("/{project_id}/photo/{idx}/{which}")
async def project_photo(project_id: str, idx: int, which: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    items = p.get("items", [])
    if idx < 0 or idx >= len(items):
        raise HTTPException(status_code=404, detail="Photo not found")
    item = items[idx]
    path = item.get("original_storage_path") if which == "original" else item.get("generated_storage_path")
    if not path:
        raise HTTPException(status_code=404, detail="Image not ready")
    data, ctype = await storage_service.get_object_async(path)
    return Response(content=data, media_type=ctype)


@projects_router.get("/{project_id}/pdf")
async def project_pdf(project_id: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    path = p.get("pdf_storage_path")
    if not path:
        raise HTTPException(status_code=403, detail="PDF not available on your plan")
    data, _ = await storage_service.get_object_async(path)
    return Response(
        content=data, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="FlowSpace_{project_id[:8]}.pdf"'},
    )


@projects_router.post("/{project_id}/email")
async def email_project_pdf(project_id: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    path = p.get("pdf_storage_path")
    if not path:
        raise HTTPException(status_code=403, detail="PDF not available on your plan")
    pdf_bytes, _ = await storage_service.get_object_async(path)
    ok = await email_service.send_plan_email(
        user["email"], user.get("name", "there"),
        ROOM_LABELS.get(p.get("room_type"), p.get("room_type", "space")), pdf_bytes,
    )
    if not ok:
        raise HTTPException(status_code=502, detail="email_unavailable")
    await db.projects.update_one({"id": project_id}, {"$set": {"email_sent": True}})
    return {"ok": True, "email": user["email"]}
