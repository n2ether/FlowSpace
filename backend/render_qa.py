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
from typing import Any, Dict, List, Optional

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
  "fixed_items_changed": true if any FIXED PIECE below that is visible in BEFORE has a different structure in AFTER — doors turned into open cubbies, baskets, or bins; glass doors became solid or open; drawers or shelves added or removed; or the piece was swapped for a different one,
  "baskets_misplaced": true if any basket, bin, or box in AFTER sits on a seat (sofa, sectional, chaise, chair, bench seat), on or in a bed or crib, or on or under a shoe bench where shoes are kept{basket_exception},
  "visible_additions": [names from PLANNED ADDITIONS below that you can clearly see in AFTER, copied exactly],
  "unlisted_additions": [short names of new decor or storage items visible in AFTER that are not in BEFORE and not in PLANNED ADDITIONS; ignore small accessories]
Mark ok=false if fixed_items_changed OR baskets_misplaced.
FIXED PIECES: {fixed}
PLANNED ADDITIONS: {additions}
"""


def qa_prompt(
    paint_request: str = "",
    *,
    fixed_items: Optional[List[str]] = None,
    additions: Optional[List[str]] = None,
    basket_exception: str = "",
) -> str:
    prompt = QA_PROMPT
    if paint_request:
        prompt += "\n" + PAINT_REQUEST_QA_NOTE.format(color=paint_request) + "\n"
    if fixed_items is not None or additions is not None:
        prompt += ITEMS_QA_NOTE.format(
            fixed="; ".join(fixed_items or []) or "none listed (judge the furniture visible in BEFORE)",
            additions="; ".join(additions or []) or "none",
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

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if self.visible_additions is None:
            out.pop("visible_additions")
        if self.unlisted_additions is None:
            out.pop("unlisted_additions")
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


def _from_payload(data: Dict[str, Any], *, skipped: bool = False, error: Optional[str] = None) -> RenderQAResult:
    windows_covered = bool(data.get("windows_covered"))
    gravity_wrong = bool(data.get("gravity_wrong"))
    walls_repainted = bool(data.get("walls_repainted"))
    fixed_changed = bool(data.get("fixed_items_changed"))
    baskets = bool(data.get("baskets_misplaced"))
    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    reasons = [str(r).strip() for r in reasons if str(r).strip()]
    ok = data.get("ok")
    hard = windows_covered or gravity_wrong or walls_repainted or fixed_changed or baskets
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
) -> RenderQAResult:
    """Synchronous cheap vision check. Never raises — skip/ok on infra failure.

    ``paint_request`` is the wall color the customer asked for; when set, a wall
    change toward that color is not a QA failure. ``fixed_items`` and
    ``additions`` (the shared item list) turn on the furniture-structure,
    basket-placement, and planned-item checks.
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
        prompt = qa_prompt(paint_request, fixed_items=fixed_items, additions=additions, basket_exception=basket_exception)
        content.append({"type": "text", "text": "AFTER (organized render).\n\n" + prompt})

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=QA_MODEL,
            max_tokens=600 if (fixed_items is not None or additions is not None) else 300,
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
