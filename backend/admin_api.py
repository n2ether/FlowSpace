"""Admin dashboard API (password-token protected)."""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from db import db
from plans import plan_cfg, PLAN_LIMITS

admin_router = APIRouter(prefix="/api/admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "garage2025")


async def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> bool:
    if not x_admin_token or x_admin_token != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


class AdminLoginRequest(BaseModel):
    password: str


class AffiliateProduct(BaseModel):
    category: str
    product_name: str
    product_description: str = ""
    affiliate_url: str
    image_url: str = ""
    price_range: str = ""
    room_type: str = ""


class CreditAdjust(BaseModel):
    user_id: str
    monthly_generations_used: int


@admin_router.post("/login")
async def admin_login(payload: AdminLoginRequest):
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": ADMIN_PASSWORD}


@admin_router.get("/users")
async def admin_users(_: bool = Depends(require_admin)):
    return await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@admin_router.get("/projects")
async def admin_projects(_: bool = Depends(require_admin)):
    return await db.projects.find(
        {}, {"_id": 0, "original_storage_path": 0, "generated_storage_path": 0, "pdf_storage_path": 0}
    ).sort("created_at", -1).to_list(2000)


@admin_router.get("/subscriptions")
async def admin_subscriptions(_: bool = Depends(require_admin)):
    return await db.subscriptions.find({}, {"_id": 0}).sort("updated_at", -1).to_list(2000)


@admin_router.get("/transactions")
async def admin_transactions(_: bool = Depends(require_admin)):
    return await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@admin_router.get("/stats")
async def admin_stats(_: bool = Depends(require_admin)):
    users = await db.users.count_documents({})
    projects = await db.projects.count_documents({})
    completed = await db.projects.count_documents({"status": "complete"})
    failed = await db.projects.count_documents({"status": "failed"})
    paid_users = await db.users.count_documents({"subscription_plan": {"$in": ["pro", "premium"]}})
    paid_tx = await db.payment_transactions.find({"payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(5000)
    mrr = sum(float(t.get("amount", 0)) for t in paid_tx)
    by_plan = {}
    for plan in PLAN_LIMITS:
        by_plan[plan] = await db.users.count_documents({"subscription_plan": plan})
    return {
        "users": users, "projects": projects, "completed": completed, "failed": failed,
        "paid_users": paid_users, "revenue": round(mrr, 2), "by_plan": by_plan,
    }


@admin_router.post("/credits")
async def admin_credits(payload: CreditAdjust, _: bool = Depends(require_admin)):
    res = await db.users.update_one(
        {"user_id": payload.user_id},
        {"$set": {"monthly_generations_used": max(0, payload.monthly_generations_used)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


# ---- affiliate products CRUD ----
@admin_router.get("/affiliate")
async def list_affiliate(_: bool = Depends(require_admin)):
    return await db.affiliate_products.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@admin_router.post("/affiliate")
async def add_affiliate(payload: AffiliateProduct, _: bool = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **payload.model_dump(),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.affiliate_products.insert_one(dict(doc))
    return doc


@admin_router.delete("/affiliate/{item_id}")
async def delete_affiliate(item_id: str, _: bool = Depends(require_admin)):
    res = await db.affiliate_products.delete_one({"id": item_id})
    return {"deleted": res.deleted_count}
