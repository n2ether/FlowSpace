"""Member account + free-tier quota helpers.

Leads stay the source of truth for spaces/plans. A member owns a lead via
`member_id`; signup/login also claims leftover guest leads that share the
same email so the pre-account free path is not lost.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import uuid

from auth import hash_password, normalize_email

FREE_GENERATION_LIMIT = 1
FREE_PACKAGE_IDS = frozenset({"free", ""})

MEMBER_PUBLIC_FIELDS = ("id", "name", "email", "created_at")
SPACE_PUBLIC_FIELDS = (
    "id",
    "name",
    "email",
    "space_type",
    "package_id",
    "status",
    "photos",
    "created_at",
    "style_prefs",
    "color_prefs",
    "biggest_challenge",
    "goals",
    "email_sent",
)


def is_free_package(package_id: Optional[str], packages: Optional[Dict[str, Any]] = None) -> bool:
    if not package_id:
        return True
    if package_id in FREE_PACKAGE_IDS:
        return True
    if packages and package_id in packages:
        return float(packages[package_id].get("price") or 0) == 0.0
    return False


def public_member(doc: Dict[str, Any], usage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {k: doc.get(k) for k in MEMBER_PUBLIC_FIELDS}
    if usage is not None:
        out["usage"] = usage
    return out


def public_space(lead: Dict[str, Any], deliverable: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {k: lead.get(k) for k in SPACE_PUBLIC_FIELDS}
    if deliverable:
        out["deliverable"] = {
            "has_plan": True,
            "front_view_url": deliverable.get("front_view_url"),
            "updated_at": deliverable.get("updated_at"),
        }
    else:
        out["deliverable"] = {"has_plan": False, "front_view_url": None, "updated_at": None}
    return out


def usage_payload(free_used: int, paid_count: int = 0) -> Dict[str, Any]:
    used = int(free_used)
    return {
        "free_generations_used": used,
        "free_generations_limit": FREE_GENERATION_LIMIT,
        "can_generate_free": used < FREE_GENERATION_LIMIT,
        "paid_generations": int(paid_count),
    }


def free_limit_error(used: int) -> Dict[str, Any]:
    return {
        "code": "FREE_TIER_LIMIT",
        "message": (
            "You've used your free Blueprint. Upgrade to Plus or Premium "
            "to organize another space."
        ),
        "used": int(used),
        "limit": FREE_GENERATION_LIMIT,
        "upgrade_path": "/#packages",
    }


def new_member_doc(name: str, email: str, password: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": (name or "").strip() or "Member",
        "email": normalize_email(email),
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _lead_is_free(lead: Dict[str, Any], packages: Optional[Dict[str, Any]] = None) -> bool:
    return is_free_package(lead.get("package_id"), packages)


def count_generations(
    leads: Iterable[Dict[str, Any]],
    *,
    packages: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    free_used = 0
    paid_count = 0
    for lead in leads:
        if _lead_is_free(lead, packages):
            free_used += 1
        else:
            paid_count += 1
    return {"free_used": free_used, "paid_count": paid_count}


async def fetch_member_leads(db, member_id: str) -> List[Dict[str, Any]]:
    return await db.leads.find({"member_id": member_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


async def usage_for_member(db, member_id: str, packages: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    leads = await fetch_member_leads(db, member_id)
    counts = count_generations(leads, packages=packages)
    return usage_payload(counts["free_used"], counts["paid_count"])


async def claim_leads_for_email(db, member_id: str, email: str) -> int:
    """Attach leftover guest leads (no member_id) that match this email."""
    email_n = normalize_email(email)
    if not email_n or not member_id:
        return 0
    result = await db.leads.update_many(
        {
            "email": {"$regex": f"^{_escape_regex(email_n)}$", "$options": "i"},
            "$or": [{"member_id": None}, {"member_id": {"$exists": False}}, {"member_id": ""}],
        },
        {"$set": {"member_id": member_id}},
    )
    return int(getattr(result, "modified_count", 0) or 0)


def _escape_regex(value: str) -> str:
    specials = r"\.^$*+?{}[]()|"
    return "".join("\\" + ch if ch in specials else ch for ch in value)


async def ensure_member_indexes(db) -> None:
    try:
        await db.members.create_index("email", unique=True)
        await db.members.create_index("id", unique=True)
        await db.leads.create_index("member_id")
    except Exception:
        # Index creation is best-effort (local FakeDB / restricted Atlas users).
        return
