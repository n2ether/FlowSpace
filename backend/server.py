"""FlowSpace Solutions — FastAPI entrypoint."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from db import client, db
from auth import auth_router
from projects import projects_router
from billing import billing_router
from admin_api import admin_router, require_admin
import storage_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FlowSpace API")
public_router = APIRouter(prefix="/api")


# ---------------- Gallery (powers the homepage before/after slider) ----------------
STARTER_GALLERY = [
    {"title": "Garage — Workshop reset", "category": "garage",
     "before_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/e8nmvr9k_cluttered_garage.png",
     "after_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/9sy0qc1i_organized_garage.png"},
    {"title": "Walk-in closet — Daily clarity", "category": "closet",
     "before_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/69dy858e_cluttered_closet.png",
     "after_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/l8r8pdii_tidy_closet.png"},
    {"title": "Laundry room — Wash, dry, fold, repeat", "category": "laundry",
     "before_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/a8ic5ch6_cluttered_laundry_room.png",
     "after_url": "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/dlxnx33a_tidy_laundry_room.png"},
]


class GalleryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: str
    before_url: str
    after_url: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GalleryCreate(BaseModel):
    title: str
    category: str
    before_url: str
    after_url: str


async def seed_gallery_if_empty():
    if await db.gallery.count_documents({}) == 0:
        for item in STARTER_GALLERY:
            await db.gallery.insert_one({"id": str(uuid.uuid4()),
                                         "created_at": datetime.now(timezone.utc).isoformat(), **item})


@public_router.get("/")
async def root():
    return {"message": "FlowSpace API", "status": "ok"}


@public_router.get("/gallery", response_model=List[GalleryItem])
async def list_gallery():
    await seed_gallery_if_empty()
    return await db.gallery.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@public_router.get("/affiliate/{room_type}")
async def affiliate_for_room(room_type: str):
    return await db.affiliate_products.find(
        {"$or": [{"room_type": room_type}, {"room_type": ""}]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)


# Gallery admin (kept here, used by existing admin gallery tab)
@public_router.post("/admin/gallery", response_model=GalleryItem)
async def admin_add_gallery(payload: GalleryCreate, _: bool = Depends(require_admin)):
    item = GalleryItem(**payload.model_dump())
    await db.gallery.insert_one(item.model_dump())
    return item


@public_router.delete("/admin/gallery/{item_id}")
async def admin_delete_gallery(item_id: str, _: bool = Depends(require_admin)):
    res = await db.gallery.delete_one({"id": item_id})
    return {"deleted": res.deleted_count}


# ---------------- wiring ----------------
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(billing_router)
app.include_router(admin_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    await seed_gallery_if_empty()
    try:
        storage_service.init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def _shutdown():
    client.close()
