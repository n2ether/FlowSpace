"""Re-check stored afters against the current room inventory, without generating anything.

Used after the brief or plan changes, after a targeted refine, and on demand
from the admin. Every approved after gets a fresh per-view check (fixed pieces,
baskets, avoid rules, planned additions) stamped with the inventory hash and the
exact image URL it covered, and the afters are compared with each other. A
failing check leaves the image in place and records the failure, so the
consistency report blocks the customer send instead of the image silently
shipping.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ai_image_generator import requested_wall_color
from package_items import room_inventory, view_check_inputs
from render_qa import RenderQAResult, review_cross_view, review_organized_render
from source_photos import mapping_is_own_source

LoadFn = Callable[[Optional[str]], Awaitable[Optional[bytes]]]


async def verify_views(*, lead: Dict[str, Any], deliverable: Dict[str, Any], load: LoadFn) -> Dict[str, Any]:
    """Fresh per-view and cross-view results for a stored package. Returns the fields to store."""
    inventory = room_inventory(lead, deliverable)
    inputs = view_check_inputs(inventory)
    paint = requested_wall_color(lead, deliverable)
    entries = [dict(e) if isinstance(e, dict) else e for e in deliverable.get("source_afters") or []]
    checked: List[Tuple[str, str, bytes]] = []
    for entry in entries:
        if not mapping_is_own_source(entry):
            continue
        after_url = str(entry.get("after_url") or "")
        source = await load(entry.get("source_url"))
        after = await load(after_url)
        if not after:
            qa = RenderQAResult(ok=False, skipped=True, error="after image could not be read")
        else:
            qa = await asyncio.to_thread(
                review_organized_render,
                after_bytes=after,
                before_bytes=source,
                attempt=1,
                paint_request=paint,
                **inputs,
            )
            checked.append((str(entry.get("after_label") or entry.get("label") or "view"), after_url, after))
        entry["qa"] = {**qa.as_dict(), "inventory_hash": inventory["hash"], "checked_after_url": after_url}
    cross: Optional[Dict[str, Any]] = None
    if len(checked) >= 2:
        result = await asyncio.to_thread(
            review_cross_view,
            views=[(label, data) for label, _url, data in checked],
            fixed_items=inputs["fixed_items"],
            additions=inputs["additions"],
        )
        cross = {
            **result.as_dict(),
            "inventory_hash": inventory["hash"],
            "after_urls": [url for _label, url, _data in checked],
            "repaired": [],
        }
    return {"source_afters": entries, "cross_view": cross, "room_inventory": inventory}
