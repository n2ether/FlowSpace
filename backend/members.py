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

# Preview logs put full runs between about 3.5 and 7.5 minutes; the estimate a
# customer sees is the ceiling, and past it the status says so.
GENERATION_ESTIMATE_MINUTES = 10
DELAYED_NOTE = (
    "This is taking a little longer than usual. Your Design Plan is still being prepared, "
    "and we'll email you when it's ready. There's no need to keep this page open."
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


SPACE_TITLES = {
    "closet": "Closet",
    "garage": "Garage",
    "laundry_room": "Laundry room",
    "laundry": "Laundry room",
    "pantry": "Pantry",
    "mudroom": "Mudroom",
    "storage": "Storage area",
    "kids_room": "Kids' room",
    "nursery": "Nursery",
    "home_office": "Home office",
    "living_room": "Living room",
    "bedroom": "Bedroom",
}

# Customer-facing status. Raw lead statuses (including legacy "error") and
# automation errors are admin-only.
IN_PROGRESS = ("in_progress", "In progress", "We're preparing your Design Plan.")
IN_REVIEW = (
    "in_review",
    "In review",
    "Our beta team reviews every plan before it's sent.",
)
DELIVERED = ("delivered", "Delivered", "Design Plan emailed to you.")
AWAITING_PAYMENT = (
    "awaiting_payment",
    "Awaiting payment",
    "Finish checkout to start your Design Plan.",
)
PAYMENT_NOT_COMPLETED = (
    "payment_not_completed",
    "Payment not completed",
    "Your payment didn't go through. Start checkout again to continue.",
)
CHECKOUT_EXPIRED = (
    "checkout_expired",
    "Checkout expired",
    "Your checkout timed out before payment. Start checkout again to continue.",
)
# Lead statuses that still wait on Stripe for a paid package.
PRE_PAYMENT_STATUSES = frozenset({"new"})
CUSTOMER_STATUS = {
    "new": IN_PROGRESS,
    "paid": IN_PROGRESS,
    "processing": IN_PROGRESS,
    "review": IN_REVIEW,
    "incomplete": IN_REVIEW,
    "pdf_ready": IN_REVIEW,
    "error": IN_REVIEW,
    "delivered": DELIVERED,
}


def space_title(lead: Dict[str, Any]) -> str:
    """The space's name as the customer chose it: room type label or their 'Other' name."""
    intake = lead.get("intake") if isinstance(lead.get("intake"), dict) else {}
    space_type = str(intake.get("space_type") or lead.get("space_type") or "").strip().lower()
    if space_type == "other":
        fact_space = (lead.get("fact_sheet") or {}).get("space") if isinstance(lead.get("fact_sheet"), dict) else None
        custom = str(intake.get("other_label") or (fact_space or {}).get("label") or "").strip()
        return custom or "Other space"
    if space_type in SPACE_TITLES:
        return SPACE_TITLES[space_type]
    return space_type.replace("_", " ").capitalize() or "Your space"


def payment_state(transaction: Optional[Dict[str, Any]]) -> str:
    """Collapse a payment_transactions row into paid / failed / expired / awaiting."""
    if not transaction:
        return "awaiting"
    payment = str(transaction.get("payment_status") or "").strip().lower()
    stripe_status = str(transaction.get("status") or "").strip().lower()
    if payment in {"paid", "no_payment_required"}:
        return "paid"
    if payment == "expired" or stripe_status == "expired":
        return "expired"
    if payment in {"failed", "canceled", "cancelled", "declined"}:
        return "failed"
    return "awaiting"


def customer_status(
    status: Optional[str],
    *,
    paid_package: bool = False,
    transaction: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Customer-facing label. Only paid or processing work reads "In progress"."""
    raw = str(status or "new").strip().lower()
    entry = CUSTOMER_STATUS.get(raw, IN_REVIEW)
    if paid_package and raw in PRE_PAYMENT_STATUSES:
        state = payment_state(transaction)
        entry = {
            "paid": IN_PROGRESS,
            "expired": CHECKOUT_EXPIRED,
            "failed": PAYMENT_NOT_COMPLETED,
        }.get(state, AWAITING_PAYMENT)
    code, label, note = entry
    return {"status": code, "status_label": label, "status_note": note}


def latest_transactions(transactions: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Newest payment row per lead_id; a paid row always wins over a later retry."""
    by_lead: Dict[str, Dict[str, Any]] = {}
    for tx in transactions or []:
        lead_id = tx.get("lead_id")
        if not lead_id:
            continue
        current = by_lead.get(lead_id)
        if current is None:
            by_lead[lead_id] = tx
            continue
        if payment_state(current) == "paid":
            continue
        if payment_state(tx) == "paid" or str(tx.get("created_at") or "") >= str(current.get("created_at") or ""):
            by_lead[lead_id] = tx
    return by_lead


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_delayed(
    lead: Dict[str, Any],
    status_code: str,
    now: Optional[datetime] = None,
) -> bool:
    """True once in-progress work runs past the estimate the customer was shown."""
    if status_code != "in_progress":
        return False
    started = _parse_iso(lead.get("processing_started_at") or lead.get("created_at"))
    if not started:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - started).total_seconds() > GENERATION_ESTIMATE_MINUTES * 60


def public_space(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
    *,
    transaction: Optional[Dict[str, Any]] = None,
    packages: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    out = {k: lead.get(k) for k in SPACE_PUBLIC_FIELDS}
    out["title"] = space_title(lead)
    out.update(
        customer_status(
            lead.get("status"),
            paid_package=not is_free_package(lead.get("package_id"), packages),
            transaction=transaction,
        )
    )
    out["processing_started_at"] = lead.get("processing_started_at")
    out["estimate_minutes"] = GENERATION_ESTIMATE_MINUTES
    out["delayed"] = is_delayed(lead, out["status"], now)
    if out["delayed"]:
        out["status_note"] = DELAYED_NOTE
    if deliverable:
        out["deliverable"] = {
            "has_plan": True,
            "front_view_url": deliverable.get("front_view_url"),
            "updated_at": deliverable.get("updated_at"),
        }
    else:
        out["deliverable"] = {"has_plan": False, "front_view_url": None, "updated_at": None}
    return out


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if isinstance(v, str) and v.strip()]


def public_plan(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only plan a member sees for their own space.

    Built from an allowlist so admin fields (automation_error, notes,
    render_qa, contact_sheet_*) never reach the customer.
    """
    zones = []
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict) and str(zone.get("title") or "").strip():
            zones.append({"title": str(zone["title"]).strip(), "desc": str(zone.get("desc") or "").strip()})
    shopping = []
    for item in deliverable.get("shopping_list") or []:
        if isinstance(item, dict) and str(item.get("name") or "").strip():
            shopping.append(
                {
                    "name": str(item["name"]).strip(),
                    "qty": item.get("qty") if isinstance(item.get("qty"), (int, float)) else 1,
                    "price": item.get("price") if isinstance(item.get("price"), (int, float)) else 0,
                }
            )
    afters = []
    for entry in deliverable.get("source_afters") or []:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("after_url") or "").strip()
        if url and str(entry.get("status") or "").strip().lower() == "approved":
            afters.append({"after_url": url})
    summary = deliverable.get("summary")
    return {
        "lead_id": lead.get("id"),
        "title": space_title(lead),
        **customer_status(lead.get("status"), paid_package=not is_free_package(lead.get("package_id"))),
        "approved": bool(deliverable.get("design_plan_approved")),
        "summary": summary.strip() if isinstance(summary, str) and summary.strip() else None,
        "strategy": _clean_list(deliverable.get("strategy")),
        "zones": zones,
        "shopping_list": shopping,
        "afters": afters,
        "updated_at": deliverable.get("updated_at"),
    }


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
            "You've used your free Design Plan. Upgrade to Plus or Premium "
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
