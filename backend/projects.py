"""Project (room transformation) routes + background AI pipeline."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
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
    photo: str  # base64 data URL
    language: str = "en"


def _public(p: dict) -> dict:
    p = {k: v for k, v in p.items() if k != "_id"}
    # never expose raw storage paths beyond what the client needs
    return p


async def _process(project_id: str, user_id: str, plan: str, room_type: str, style: str, data_uri: str, language: str):
    try:
        prompt = room_service.build_prompt(room_type, style)
        gen_bytes = await replicate_service.generate_organized_image(prompt, data_uri)

        cfg = plan_cfg(plan)
        display_bytes = room_service.add_watermark(gen_bytes) if cfg["watermark"] else gen_bytes

        gen_path = f"{APP_NAME}/generated-room-images/{user_id}/{uuid.uuid4().hex}.jpg"
        await storage_service.put_object_async(gen_path, display_bytes, "image/jpeg")

        plan_data = await room_service.generate_room_plan(room_type, style, language)

        pdf_path = None
        email_sent = False
        if cfg["pdf"]:
            udoc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1, "email": 1})
            uname = (udoc or {}).get("name", "there")
            uemail = (udoc or {}).get("email", "")
            _, before_raw = room_service.strip_data_url(data_uri)
            pdf_bytes = await asyncio.to_thread(
                room_service.build_room_pdf,
                user_name=uname, room_type=room_type, style=style, plan=plan_data,
                before_bytes=before_raw, after_bytes=gen_bytes, with_affiliate=cfg["affiliate"],
            )
            pdf_path = f"{APP_NAME}/project-pdfs/{user_id}/{uuid.uuid4().hex}.pdf"
            await storage_service.put_object_async(pdf_path, pdf_bytes, "application/pdf")
            email_sent = await email_service.send_plan_email(
                uemail, uname, ROOM_LABELS.get(room_type, room_type), pdf_bytes
            )

        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "generated_storage_path": gen_path,
                "organization_plan": plan_data,
                "shopping_list": plan_data.get("shopping_list", []),
                "organization_score": plan_data.get("organization_score"),
                "estimated_cost": plan_data.get("estimated_cost"),
                "estimated_time": plan_data.get("estimated_time"),
                "difficulty": plan_data.get("difficulty"),
                "pdf_storage_path": pdf_path,
                "email_sent": email_sent,
                "watermarked": cfg["watermark"],
                "status": "complete",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:
        logger.exception(f"Project {project_id} processing failed: {e}")
        # Refund the credit consumed up-front since generation failed.
        await db.users.update_one(
            {"user_id": user_id, "monthly_generations_used": {"$gt": 0}},
            {"$inc": {"monthly_generations_used": -1}},
        )
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"status": "failed", "error": str(e)[:300],
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )


@projects_router.post("")
async def create_project(payload: ProjectCreate, background: BackgroundTasks, request: Request):
    user = await get_current_user(request)
    if payload.room_type not in ROOM_TYPES:
        raise HTTPException(status_code=400, detail="Invalid room_type")
    if payload.style not in STYLES:
        raise HTTPException(status_code=400, detail="Invalid style")

    cfg = plan_cfg(user.get("subscription_plan", "free"))
    used = user.get("monthly_generations_used", 0)
    if used >= cfg["limit"]:
        raise HTTPException(status_code=402, detail="credit_limit_reached")

    try:
        _, raw = room_service.strip_data_url(payload.photo)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image")
    data_uri = room_service.downscale_to_data_uri(raw)

    user_id = user["user_id"]
    orig_path = f"{APP_NAME}/original-room-images/{user_id}/{uuid.uuid4().hex}.jpg"
    await storage_service.put_object_async(orig_path, raw, "image/jpeg")

    now = datetime.now(timezone.utc).isoformat()
    project = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "room_type": payload.room_type,
        "style": payload.style,
        "original_storage_path": orig_path,
        "generated_storage_path": None,
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

    # consume one credit immediately (idempotent per project)
    await db.users.update_one({"user_id": user_id}, {"$inc": {"monthly_generations_used": 1}})

    background.add_task(_process, project["id"], user_id, user.get("subscription_plan", "free"),
                        payload.room_type, payload.style, data_uri, payload.language)
    return _public(project)


@projects_router.get("")
async def list_projects(request: Request):
    user = await get_current_user(request)
    items = await db.projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@projects_router.get("/{project_id}")
async def get_project(project_id: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@projects_router.get("/{project_id}/image/{which}")
async def project_image(project_id: str, which: str, request: Request):
    user = await get_current_user(request)
    p = await db.projects.find_one({"id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    path = p.get("original_storage_path") if which == "original" else p.get("generated_storage_path")
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
