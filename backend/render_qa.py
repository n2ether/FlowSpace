"""Cheap post-generation vision QA for organized 'after' renders.

If windows are covered by storage, or gravity/fixtures look wrong (fan on a
wall, upside-down room), the caller retries generation once with stronger
rails and/or a corrected source orientation. A second failure is logged and
the broken after is discarded — the PDF falls back to the labeled original.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import anthropic

from image_orientation import jpeg_for_vision

logger = logging.getLogger(__name__)

QA_MODEL = os.environ.get("ANTHROPIC_QA_MODEL", "claude-haiku-4-5")

QA_PROMPT = """You are a cheap QA check for FlowSpace organized-space renders.
Compare the BEFORE photo (customer's real space) to the AFTER render when both
are attached. If only AFTER is attached, judge that image alone.

Return ONLY JSON (no markdown):
{
  "ok": true or false,
  "windows_covered": true if shelves, cabinets, racks, or storage cover, block, or sit over a window or door that should stay visible,
  "gravity_wrong": true if the room is sideways/upside-down OR a ceiling fan, light, vent, or fixture is on a wall instead of the ceiling,
  "walls_repainted": true if AFTER walls are a clearly different paint color than BEFORE, in either direction (warm became cool, cool became warm, or a new hue). Warm, cool, neutral, and colored walls are all correct when they match BEFORE. Ignore small lighting or white-balance shifts. Fail on an obvious wall-color makeover,
  "reasons": ["short facts"],
  "suggested_rotate_degrees": 0, 90, 180, or 270
}

suggested_rotate_degrees is clockwise rotation to apply to the SOURCE photo
before a retry when gravity looks wrong; otherwise 0.

Mark ok=false if windows_covered OR gravity_wrong OR walls_repainted.
Do not fail for clutter style or minor furniture taste.
Be conservative: only fail on clear window-covering, gravity/fixture errors, or an obvious wall repaint.
"""


PAINT_REQUEST_QA_NOTE = (
    "The customer explicitly asked for new wall paint: {color}. A wall color change "
    "toward that requested color is expected and correct. Set walls_repainted=true only "
    "if the AFTER walls are a clearly different color from what the customer requested."
)


ITEMS_QA_NOTE = """
Also check the furniture and the planned items. Add these keys to the same JSON:
  "fixed_items_check": [one entry per FIXED PIECE below: {{"name": copied exactly, "in_before": true if clearly visible in BEFORE, "in_after": true if clearly visible in AFTER, "same": true if AFTER keeps its structure (doors and glass, drawer and shelf count), color, material, size, and place}}],
  "fixed_items_changed": true if any FIXED PIECE visible in BEFORE is missing from AFTER or has a different structure in AFTER — doors turned into open cubbies, baskets, or bins; glass doors became solid or open; drawers or shelves added or removed; or the piece was swapped for a different one,
  "baskets_misplaced": true if any basket, bin, or box in AFTER sits on a seat (sofa, sectional, chaise, chair, bench seat), on or in a bed or crib, or on or under a shoe bench where shoes are kept{basket_exception},
  "avoid_seen": [entries from NEVER SHOW below that AFTER shows, copied exactly],
  "visible_additions": [names from PLANNED ADDITIONS below that you can clearly see in AFTER, copied exactly],
  "unlisted_additions": [short names of new decor or storage items visible in AFTER that are not in BEFORE and not in PLANNED ADDITIONS; ignore small accessories]
Mark ok=false if fixed_items_changed OR baskets_misplaced OR avoid_seen is not empty.
A fixed piece that is out of frame in BEFORE does not count. Ignore small lighting and angle differences.
FIXED PIECES: {fixed}
PLANNED ADDITIONS: {additions}
NEVER SHOW: {avoid}
"""


def qa_prompt(
    paint_request: str = "",
    *,
    fixed_items: Optional[List[str]] = None,
    additions: Optional[List[str]] = None,
    basket_exception: str = "",
    avoid: Optional[List[str]] = None,
) -> str:
    prompt = QA_PROMPT
    if paint_request:
        prompt += "\n" + PAINT_REQUEST_QA_NOTE.format(color=paint_request) + "\n"
    if fixed_items is not None or additions is not None:
        prompt += ITEMS_QA_NOTE.format(
            fixed="; ".join(fixed_items or []) or "none listed (judge the furniture visible in BEFORE)",
            additions="; ".join(additions or []) or "none",
            avoid="; ".join(avoid or []) or "none",
            basket_exception=f" (allowed only where the customer asked: \"{basket_exception}\")" if basket_exception else "",
        )
    return prompt


@dataclass
class RenderQAResult:
    ok: bool = True
    windows_covered: bool = False
    gravity_wrong: bool = False
    walls_repainted: bool = False
    fixed_items_changed: bool = False
    baskets_misplaced: bool = False
    reasons: List[str] = field(default_factory=list)
    suggested_rotate_degrees: int = 0
    skipped: bool = False
    error: Optional[str] = None
    attempt: int = 1
    # Only present when the item check ran; the consistency report reads them.
    visible_additions: Optional[List[str]] = None
    unlisted_additions: Optional[List[str]] = None
    fixed_items_altered: Optional[List[str]] = None
    fixed_items_missing: Optional[List[str]] = None
    avoid_seen: Optional[List[str]] = None

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        for key in ("visible_additions", "unlisted_additions", "fixed_items_altered", "fixed_items_missing", "avoid_seen"):
            if out.get(key) is None:
                out.pop(key)
        return out

    @property
    def failed(self) -> bool:
        return (not self.skipped) and (not self.ok)


def _parse_qa_json(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("QA JSON was not an object")
    return data


def _degrees(value: Any) -> int:
    try:
        deg = int(value)
    except (TypeError, ValueError):
        return 0
    deg = deg % 360
    if deg in (0, 90, 180, 270):
        return deg
    return 0


def _image_block(jpeg_bytes: bytes) -> Dict[str, Any]:
    import base64

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(jpeg_bytes).decode("ascii"),
        },
    }


def _names(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [" ".join(str(v).split()) for v in value if str(v).strip()]


def _fixed_check(value: Any) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """(altered, missing) piece names from ``fixed_items_check``; ``None`` when QA did not return it."""
    if not isinstance(value, list):
        return None, None
    altered: List[str] = []
    missing: List[str] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        name = " ".join(str(row.get("name") or "").split())
        if not name or not row.get("in_before"):
            continue
        if not row.get("in_after"):
            missing.append(name)
        elif row.get("same") is False:
            altered.append(name)
    return altered, missing


def _from_payload(data: Dict[str, Any], *, skipped: bool = False, error: Optional[str] = None) -> RenderQAResult:
    windows_covered = bool(data.get("windows_covered"))
    gravity_wrong = bool(data.get("gravity_wrong"))
    walls_repainted = bool(data.get("walls_repainted"))
    altered, missing = _fixed_check(data.get("fixed_items_check"))
    fixed_changed = bool(data.get("fixed_items_changed")) or bool(altered) or bool(missing)
    baskets = bool(data.get("baskets_misplaced"))
    avoid_seen = _names(data.get("avoid_seen"))
    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    reasons = [str(r).strip() for r in reasons if str(r).strip()]
    ok = data.get("ok")
    hard = windows_covered or gravity_wrong or walls_repainted or fixed_changed or baskets or bool(avoid_seen)
    if ok is None:
        ok = not hard
    return RenderQAResult(
        ok=bool(ok) and not hard,
        windows_covered=windows_covered,
        gravity_wrong=gravity_wrong,
        walls_repainted=walls_repainted,
        fixed_items_changed=fixed_changed,
        baskets_misplaced=baskets,
        visible_additions=_names(data.get("visible_additions")),
        unlisted_additions=_names(data.get("unlisted_additions")),
        fixed_items_altered=altered,
        fixed_items_missing=missing,
        avoid_seen=avoid_seen,
        reasons=reasons,
        suggested_rotate_degrees=_degrees(data.get("suggested_rotate_degrees")),
        skipped=skipped,
        error=error,
    )


def review_organized_render(
    *,
    after_bytes: bytes,
    before_bytes: Optional[bytes] = None,
    attempt: int = 1,
    paint_request: str = "",
    fixed_items: Optional[List[str]] = None,
    additions: Optional[List[str]] = None,
    basket_exception: str = "",
    avoid: Optional[List[str]] = None,
) -> RenderQAResult:
    """Synchronous cheap vision check. Never raises — skip/ok on infra failure.

    ``paint_request`` is the wall color the customer asked for; when set, a wall
    change toward that color is not a QA failure. ``fixed_items`` and
    ``additions`` (the shared item list) turn on the furniture-structure,
    basket-placement, and planned-item checks; ``avoid`` lists what no view may
    show. A skipped check is recorded as ``skipped``; the consistency report
    treats that view as unverified, never as passed.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("[render_qa] skipped — ANTHROPIC_API_KEY not configured")
        return RenderQAResult(ok=True, skipped=True, error="no_api_key", attempt=attempt)
    if not after_bytes:
        return RenderQAResult(ok=False, reasons=["missing after render"], attempt=attempt)

    try:
        after_jpeg = jpeg_for_vision(after_bytes, max_side=768)
        content: List[Dict[str, Any]] = []
        if before_bytes:
            content.append(_image_block(jpeg_for_vision(before_bytes, max_side=768)))
            content.append({"type": "text", "text": "BEFORE (customer photo, gravity-corrected)."})
        content.append(_image_block(after_jpeg))
        prompt = qa_prompt(
            paint_request, fixed_items=fixed_items, additions=additions, basket_exception=basket_exception, avoid=avoid
        )
        content.append({"type": "text", "text": "AFTER (organized render).\n\n" + prompt})

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=QA_MODEL,
            max_tokens=900 if (fixed_items is not None or additions is not None) else 300,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text if message.content else ""
        parsed = _from_payload(_parse_qa_json(raw))
        parsed.attempt = attempt
        logger.info(
            "[render_qa] attempt=%s ok=%s windows_covered=%s gravity_wrong=%s walls_repainted=%s fixed_changed=%s baskets=%s rotate=%s reasons=%s",
            attempt,
            parsed.ok,
            parsed.windows_covered,
            parsed.gravity_wrong,
            parsed.walls_repainted,
            parsed.fixed_items_changed,
            parsed.baskets_misplaced,
            parsed.suggested_rotate_degrees,
            parsed.reasons,
        )
        return parsed
    except Exception as exc:
        logger.warning("[render_qa] skipped after error: %s", exc)
        return RenderQAResult(ok=True, skipped=True, error=str(exc), attempt=attempt)


# ──────────────────────────── Cross-view check ─────────────────────────────

# Comparing several views at once needs the stronger vision model the drafter uses.
CROSS_VIEW_MODEL = os.environ.get("ANTHROPIC_CROSS_VIEW_MODEL", "claude-sonnet-4-5")

CROSS_VIEW_PROMPT = """You check that several organized AFTER views of ONE room agree with each other.
Each image is labeled. They are different camera angles of the same room after the same plan.

Return ONLY JSON (no markdown):
{{
  "items": [one entry per piece listed below: {{"name": copied exactly, "views": [labels where the piece is clearly visible], "consistent": true or false, "difference": "short fact when not consistent, else empty"}}],
  "ok": true or false
}}

consistent=false when the piece looks different between views where it is visible: structure (glass doors
vs solid doors, open shelves, cubbies, or baskets; drawer or shelf count), color, material, size, pattern,
or it is replaced by a different piece. A piece that is out of frame in a view is not a difference.
Ignore camera angle, lighting, and partial occlusion. Mark ok=false if any item is not consistent.

FIXED PIECES (must be identical in every view): {fixed}
PLANNED ADDITIONS (must be the same item wherever shown): {additions}
"""


@dataclass
class CrossViewResult:
    ok: bool = True
    skipped: bool = False
    error: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    mismatches: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def cross_view_from_payload(data: Dict[str, Any], labels: Sequence[str]) -> CrossViewResult:
    known = set(labels)
    items: List[Dict[str, Any]] = []
    mismatches: List[Dict[str, Any]] = []
    for row in data.get("items") or []:
        if not isinstance(row, dict) or not str(row.get("name") or "").strip():
            continue
        views = [str(v) for v in row.get("views") or [] if str(v) in known]
        entry = {
            "name": " ".join(str(row["name"]).split()),
            "views": views,
            "consistent": row.get("consistent") is not False,
            "difference": " ".join(str(row.get("difference") or "").split()),
        }
        items.append(entry)
        if not entry["consistent"] and len(views) >= 2:
            mismatches.append(entry)
    return CrossViewResult(ok=not mismatches, items=items, mismatches=mismatches)


def review_cross_view(
    *,
    views: Sequence[Tuple[str, bytes]],
    fixed_items: List[str],
    additions: List[str],
) -> CrossViewResult:
    """Compare every approved after of one room for the shared fixed pieces and planned additions.

    Never raises. A missing key or an API error returns ``skipped``; the
    consistency report blocks a final send until the comparison has run.
    """
    if len(views) < 2:
        return CrossViewResult(ok=True)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return CrossViewResult(ok=True, skipped=True, error="no_api_key")
    try:
        content: List[Dict[str, Any]] = []
        for label, data in views[:6]:
            content.append(_image_block(jpeg_for_vision(data, max_side=640)))
            content.append({"type": "text", "text": f"VIEW {label}"})
        content.append(
            {
                "type": "text",
                "text": CROSS_VIEW_PROMPT.format(
                    fixed="; ".join(fixed_items) or "none listed (judge the furniture that appears in more than one view)",
                    additions="; ".join(additions) or "none",
                ),
            }
        )
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=CROSS_VIEW_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text if message.content else ""
        result = cross_view_from_payload(_parse_qa_json(raw), [label for label, _ in views])
        logger.info("[render_qa] cross-view ok=%s mismatches=%s", result.ok, [m["name"] for m in result.mismatches])
        return result
    except Exception as exc:
        logger.warning("[render_qa] cross-view check skipped after error: %s", exc)
        return CrossViewResult(ok=True, skipped=True, error=str(exc))
