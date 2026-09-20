"""Cheap post-FLUX vision QA for organized 'after' renders.

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
  "walls_repainted": true if AFTER walls are a clearly different paint color than BEFORE (e.g. light blue / blue-gray became taupe, beige, cream, or warm earth). Ignore small lighting or white-balance shifts. Fail on an obvious wall-color makeover,
  "reasons": ["short facts"],
  "suggested_rotate_degrees": 0, 90, 180, or 270
}

suggested_rotate_degrees is clockwise rotation to apply to the SOURCE photo
before a retry when gravity looks wrong; otherwise 0.

Mark ok=false if windows_covered OR gravity_wrong OR walls_repainted.
Do not fail for clutter style or minor furniture taste.
Be conservative: only fail on clear window-covering, gravity/fixture errors, or an obvious wall repaint.
"""


@dataclass
class RenderQAResult:
    ok: bool = True
    windows_covered: bool = False
    gravity_wrong: bool = False
    walls_repainted: bool = False
    reasons: List[str] = field(default_factory=list)
    suggested_rotate_degrees: int = 0
    skipped: bool = False
    error: Optional[str] = None
    attempt: int = 1

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

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


def _from_payload(data: Dict[str, Any], *, skipped: bool = False, error: Optional[str] = None) -> RenderQAResult:
    windows_covered = bool(data.get("windows_covered"))
    gravity_wrong = bool(data.get("gravity_wrong"))
    walls_repainted = bool(data.get("walls_repainted"))
    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    reasons = [str(r).strip() for r in reasons if str(r).strip()]
    ok = data.get("ok")
    if ok is None:
        ok = not (windows_covered or gravity_wrong or walls_repainted)
    return RenderQAResult(
        ok=bool(ok) and not windows_covered and not gravity_wrong and not walls_repainted,
        windows_covered=windows_covered,
        gravity_wrong=gravity_wrong,
        walls_repainted=walls_repainted,
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
) -> RenderQAResult:
    """Synchronous cheap vision check. Never raises — skip/ok on infra failure."""
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
        content.append({"type": "text", "text": "AFTER (organized render).\n\n" + QA_PROMPT})

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=QA_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text if message.content else ""
        parsed = _from_payload(_parse_qa_json(raw))
        parsed.attempt = attempt
        logger.info(
            "[render_qa] attempt=%s ok=%s windows_covered=%s gravity_wrong=%s walls_repainted=%s rotate=%s reasons=%s",
            attempt,
            parsed.ok,
            parsed.windows_covered,
            parsed.gravity_wrong,
            parsed.walls_repainted,
            parsed.suggested_rotate_degrees,
            parsed.reasons,
        )
        return parsed
    except Exception as exc:
        logger.warning("[render_qa] skipped after error: %s", exc)
        return RenderQAResult(ok=True, skipped=True, error=str(exc), attempt=attempt)
