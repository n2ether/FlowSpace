"""Recover renders orphaned by a restart or deploy.

Renders run as in-process background tasks. If the process dies mid-render the
lead stays ``processing`` forever. While a render is queued or running it
touches ``render_heartbeat_at``; a sweep on startup and every few minutes finds
``processing`` leads whose heartbeat (or ``updated_at`` for older leads) is
stale, claims each one with an atomic conditional update, and re-queues it.
After ``RENDER_MAX_RECOVERIES`` reclaims the lead is held as failed with an
admin-visible reason.

The claim is a single ``update_one`` whose filter repeats the staleness test
and the attempt count that was read, so two instances sweeping at once cannot
both win the same lead: the first write refreshes the heartbeat and bumps the
count, and the second filter no longer matches.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)
SWEEP_INTERVAL_SECONDS = 5 * 60
HEARTBEAT_INTERVAL_SECONDS = 60
LEASE_DURATION = timedelta(minutes=20)

INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def max_recoveries() -> int:
    try:
        return max(0, int(os.environ.get("RENDER_MAX_RECOVERIES", "2")))
    except ValueError:
        return 2


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def touch_render_heartbeat(db, lead_id: Optional[str]) -> None:
    """Mark a queued or running render as alive. Never raises."""
    if not lead_id:
        return
    now = _iso(datetime.now(timezone.utc))
    try:
        await db.leads.update_one(
            {"id": lead_id, "status": "processing"},
            {"$set": {"render_heartbeat_at": now, "updated_at": now}},
        )
    except Exception as exc:
        logger.warning("[recovery] Heartbeat failed for lead %s: %s", lead_id, exc)


async def heartbeat_loop(db, lead_id: Optional[str], interval: float = HEARTBEAT_INTERVAL_SECONDS) -> None:
    """Touch the heartbeat until cancelled. Covers time spent waiting on the semaphore."""
    while True:
        await asyncio.sleep(interval)
        await touch_render_heartbeat(db, lead_id)


def stale_filter(now: datetime, stale_after: timedelta = STALE_AFTER) -> Dict[str, Any]:
    cutoff = _iso(now - stale_after)
    return {
        "status": "processing",
        "$and": [
            {
                "$or": [
                    {"render_heartbeat_at": {"$lt": cutoff}},
                    {"render_heartbeat_at": {"$exists": False}, "updated_at": {"$lt": cutoff}},
                    {"render_heartbeat_at": None, "updated_at": {"$lt": cutoff}},
                ]
            },
            {
                "$or": [
                    {"render_lease_until": {"$exists": False}},
                    {"render_lease_until": None},
                    {"render_lease_until": {"$lt": _iso(now)}},
                ]
            },
        ],
    }


async def claim_stale_lead(
    db,
    lead: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    owner: str = INSTANCE_ID,
) -> str:
    """Atomically claim one stale lead. Returns "requeue", "failed", or "" if another instance won."""
    now = now or datetime.now(timezone.utc)
    lead_id = lead.get("id")
    if not lead_id:
        return ""
    seen = int(lead.get("render_recoveries") or 0)
    query = {
        "id": lead_id,
        "render_recoveries": {"$in": [seen, None]} if seen == 0 else seen,
        **stale_filter(now),
    }
    stamp = _iso(now)
    if seen >= max_recoveries():
        reason = (
            f"Render did not finish after {seen} automatic restart(s); the heartbeat went stale "
            f"(last seen {lead.get('render_heartbeat_at') or lead.get('updated_at') or 'unknown'}). "
            "Retry automation from the admin."
        )
        result = await db.leads.update_one(
            query,
            {
                "$set": {
                    "status": "review",
                    "package_status": "review",
                    "email_sent": False,
                    "automation_failed": True,
                    "automation_failed_at": stamp,
                    "automation_error": reason,
                    "automation_note": "Generation failed. Held for review. Retry automation from the admin.",
                    "render_recovery_status": "gave_up",
                    "render_lease_owner": None,
                    "render_lease_until": None,
                    "updated_at": stamp,
                }
            },
        )
        if getattr(result, "matched_count", 0):
            logger.error("[recovery] Lead %s marked failed: %s", lead_id, reason)
            return "failed"
        return ""
    result = await db.leads.update_one(
        query,
        {
            "$set": {
                "render_recoveries": seen + 1,
                "render_lease_owner": owner,
                "render_lease_until": _iso(now + LEASE_DURATION),
                "render_heartbeat_at": stamp,
                "render_recovered_at": stamp,
                "render_recovery_status": "requeued",
                "updated_at": stamp,
            }
        },
    )
    if getattr(result, "matched_count", 0):
        logger.warning("[recovery] Reclaimed stale render for lead %s (restart %s/%s)", lead_id, seen + 1, max_recoveries())
        return "requeue"
    return ""


async def sweep_stale_renders(
    db,
    requeue: Callable[[Dict[str, Any]], Awaitable[Any]],
    *,
    now: Optional[datetime] = None,
    owner: str = INSTANCE_ID,
) -> Dict[str, List[str]]:
    """One pass: claim stale processing leads, re-queue or fail each."""
    now = now or datetime.now(timezone.utc)
    report: Dict[str, List[str]] = {"requeued": [], "failed": []}
    candidates = await db.leads.find(stale_filter(now), {"_id": 0}).to_list(200)
    for lead in candidates:
        outcome = await claim_stale_lead(db, lead, now=now, owner=owner)
        if outcome == "requeue":
            fresh = await db.leads.find_one({"id": lead["id"]}, {"_id": 0}) or lead
            try:
                await requeue(fresh)
                report["requeued"].append(lead["id"])
            except Exception:
                logger.exception("[recovery] Could not re-queue lead %s", lead.get("id"))
        elif outcome == "failed":
            report["failed"].append(lead["id"])
    if report["requeued"] or report["failed"]:
        logger.warning("[recovery] Sweep requeued=%s failed=%s", report["requeued"], report["failed"])
    return report


async def sweep_forever(
    db,
    requeue: Callable[[Dict[str, Any]], Awaitable[Any]],
    interval: float = SWEEP_INTERVAL_SECONDS,
) -> None:
    """Sweep now (startup), then every ``interval`` seconds until cancelled."""
    while True:
        try:
            await sweep_stale_renders(db, requeue)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[recovery] Stale-render sweep failed")
        await asyncio.sleep(interval)
