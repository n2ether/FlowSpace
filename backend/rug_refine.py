"""Targeted rug-consistency pass on approved AFTER images.

Reviewer feedback: the organized afters showed the room's one round rug
differently from view to view. This pass edits each existing approved after
(not the source photo) with a prompt that locks the rug to one explicit
description and preserves everything else. Each refined image runs the same
vision QA as generation, plus a rug check, and replaces its after only when
both pass. SOURCE_n → AFTER_n mappings, labels, and package status do not
change, and nothing is emailed.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from render_qa import RenderQAResult, _image_block, _parse_qa_json, review_organized_render
from space_rails import (
    CRIB_INTERIOR_RAILS,
    is_nursery_space,
    is_space_theme,
    rug_description,
    rug_spec,
)

logger = logging.getLogger(__name__)

RUG_DESCRIBE_MODEL = os.environ.get("ANTHROPIC_QA_MODEL", "claude-haiku-4-5")

DEFAULT_ROUND_RUG = {
    "shape": "round",
    "diameter_ft": 5,
    "diameter_m": 1.5,
}

RUG_DESCRIBE_PROMPT = """You describe one rug for an image-edit prompt.
The BEFORE photos are the customer's real room. The REFERENCE AFTER is the first organized view.
Describe the single area rug on the floor as it appears in the BEFORE photos (use the REFERENCE AFTER
only to resolve details the BEFORE photos do not show). Return ONLY JSON (no markdown):
{
  "color": "main and secondary colors, plain words (e.g. 'warm cream with soft gray')",
  "texture": "pile and surface (e.g. 'low flat pile, soft cotton weave')",
  "pattern": "pattern or 'solid, no pattern' (e.g. 'thin concentric gray rings near the edge')",
  "edge": "edge finish (e.g. 'plain bound edge, no fringe')"
}
Use short concrete phrases. Do not mention furniture."""

RUG_CHECK_PROMPT = """You check a targeted rug edit of an organized room photo.
PREVIOUS is the approved organized view. REFINED is the edited version. The only allowed change is the rug.
The rug must be: {rug}.
Return ONLY JSON (no markdown):
{{
  "ok": true or false,
  "rug_matches": true if REFINED shows exactly one rug matching that description (shape, approximate size, color, pattern),
  "other_changes": true if anything other than the rug clearly changed: furniture added/removed/moved, dresser drawers changed or replaced, crib contents changed (anything other than a fitted sheet / sleep sack), rocker or basket changed, walls or wall color, windows, door, wall decor or space-themed art, camera angle, crop, or orientation,
  "reasons": ["short facts"]
}}
Mark ok=false if rug_matches is false or other_changes is true. Ignore tiny lighting or compression differences."""


@dataclass
class RugCheckResult:
    ok: bool = True
    rug_matches: bool = True
    other_changes: bool = False
    reasons: List[str] = field(default_factory=list)
    skipped: bool = False
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "rug_matches": self.rug_matches,
            "other_changes": self.other_changes,
            "reasons": list(self.reasons),
            "skipped": self.skipped,
            "error": self.error,
        }


def _anthropic_client():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _vision_block(data: bytes) -> Dict[str, Any]:
    from image_orientation import jpeg_for_vision

    return _image_block(jpeg_for_vision(data, max_side=768))


def describe_rug(
    sources: List[bytes],
    reference_after: Optional[bytes],
    base: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill color, texture, pattern, and edge from the source photos and AFTER_01.

    Keeps shape, size, and placement from ``base``. Never raises; on any
    failure the spec keeps whatever it already had.
    """
    spec = {**DEFAULT_ROUND_RUG, **(base or {})}
    if all(spec.get(key) for key in ("color", "texture", "pattern")):
        return spec
    client = _anthropic_client()
    if client is None or not (sources or reference_after):
        return spec
    try:
        content: List[Dict[str, Any]] = []
        for data in sources[:4]:
            content.append(_vision_block(data))
            content.append({"type": "text", "text": "BEFORE (customer photo)."})
        if reference_after:
            content.append(_vision_block(reference_after))
            content.append({"type": "text", "text": "REFERENCE AFTER (first organized view)."})
        content.append({"type": "text", "text": RUG_DESCRIBE_PROMPT})
        message = client.messages.create(
            model=RUG_DESCRIBE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text if message.content else ""
        found = _parse_qa_json(raw)
        for key in ("color", "texture", "pattern", "edge"):
            value = " ".join(str(found.get(key) or "").split())
            if value and not spec.get(key):
                spec[key] = value
        spec["described_by"] = "vision"
    except Exception as exc:
        logger.warning("[rug_refine] rug description skipped: %s", exc)
    return spec


def review_rug_edit(
    *,
    refined: bytes,
    previous: bytes,
    rug: Dict[str, Any],
) -> RugCheckResult:
    """Rug-only vision check of a refined after against the after it would replace."""
    client = _anthropic_client()
    if client is None:
        return RugCheckResult(ok=True, skipped=True, error="no_api_key")
    try:
        content = [
            _vision_block(previous),
            {"type": "text", "text": "PREVIOUS (approved organized view)."},
            _vision_block(refined),
            {"type": "text", "text": "REFINED (rug edit).\n\n" + RUG_CHECK_PROMPT.format(rug=rug_description(rug))},
        ]
        message = client.messages.create(
            model=RUG_DESCRIBE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": content}],
        )
        data = _parse_qa_json(message.content[0].text if message.content else "")
        rug_matches = bool(data.get("rug_matches", True))
        other = bool(data.get("other_changes", False))
        reasons = data.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        return RugCheckResult(
            ok=bool(data.get("ok", True)) and rug_matches and not other,
            rug_matches=rug_matches,
            other_changes=other,
            reasons=[str(r).strip() for r in reasons if str(r).strip()],
        )
    except Exception as exc:
        logger.warning("[rug_refine] rug check skipped after error: %s", exc)
        return RugCheckResult(ok=True, skipped=True, error=str(exc))


def preserve_everything_else(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    parts = [
        "PRESERVE EVERYTHING ELSE EXACTLY AS IN THIS IMAGE: same camera, framing, crop, perspective, and "
        "orientation; same walls and wall color; same windows, window treatments, and door; same wall "
        "switches and outlets; same furniture in the same places.",
    ]
    if is_nursery_space(lead):
        parts.append(
            "The six-drawer dresser keeps all six drawers exactly as shown — no baskets, no open cubbies. "
            "The crib keeps a fitted sheet only, nothing else inside it. The rocker and the storage basket "
            "stay exactly as shown."
        )
        parts.append(CRIB_INTERIOR_RAILS)
    if is_space_theme(lead, deliverable):
        parts.append("Keep every piece of space-themed decor (planets, moon, rockets, astronauts) exactly as shown.")
    return " ".join(parts)


def build_refine_prompt(
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    rug: Dict[str, Any],
    *,
    has_reference: bool = False,
    retry_note: str = "",
) -> str:
    """Rug-only edit of an approved organized view. Image 1 is the view to edit."""
    described = rug_description(rug)
    reference = (
        "Image 2 is a reference for the rug ONLY — match that rug's color, texture, and pattern; "
        "do not copy anything else from image 2. "
        if has_reference
        else ""
    )
    retry = f"PREVIOUS ATTEMPT FAILED REVIEW: {retry_note} " if retry_note else ""
    return (
        "TARGETED EDIT — RUG ONLY. Edit image 1, an organized photo of this room. "
        f"The room has exactly one rug: {described}. "
        "Make the rug on the floor match that description exactly: correct its shape, size, color, "
        "texture, and pattern so it is the same rug seen in every other view of this room. "
        "Where furniture overlaps it, the rug continues naturally underneath. "
        "If the rug is hidden by furniture from this camera, show only the visible part. "
        "Do not add a second rug, a runner, or a play mat. "
        f"{reference}"
        f"{preserve_everything_else(lead, deliverable)} "
        f"{retry}"
        "Photorealistic, natural lighting, no people, no text or watermarks."
    )


EditFn = Callable[[str, bytes, Optional[bytes]], Awaitable[bytes]]
QAFn = Callable[..., RenderQAResult]
RugCheckFn = Callable[..., RugCheckResult]


@dataclass
class RefineOutcome:
    label: str
    after_label: str
    replaced: bool
    after_bytes: Optional[bytes]
    attempts: int
    qa: Dict[str, Any]
    rug_check: Dict[str, Any]
    reasons: List[str]

    def report(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "after_label": self.after_label,
            "replaced": self.replaced,
            "attempts": self.attempts,
            "qa": self.qa,
            "rug_check": self.rug_check,
            "reasons": self.reasons,
        }


def _passed(result: Any) -> bool:
    return bool(result) and not getattr(result, "skipped", False) and bool(getattr(result, "ok", False))


async def refine_one(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    rug: Dict[str, Any],
    label: str,
    after_label: str,
    source: Optional[bytes],
    after: bytes,
    reference: Optional[bytes],
    edit: EditFn,
    qa: Optional[QAFn] = None,
    rug_check: Optional[RugCheckFn] = None,
    attempts: int = 2,
) -> RefineOutcome:
    """Edit one approved after; keep it only when generation QA and the rug check both pass.

    A skipped check is not a pass: without a working vision review the
    existing after stays.
    """
    qa = qa or review_organized_render
    rug_check = rug_check or review_rug_edit
    retry_note = ""
    last_qa: Dict[str, Any] = {}
    last_rug: Dict[str, Any] = {}
    reasons: List[str] = []
    for attempt in range(1, attempts + 1):
        prompt = build_refine_prompt(
            lead, deliverable, rug, has_reference=reference is not None, retry_note=retry_note
        )
        try:
            refined = await edit(prompt, after, reference)
        except Exception as exc:
            reasons.append(f"edit failed: {exc}")
            logger.warning("[rug_refine] %s edit failed: %s", after_label, exc)
            break
        render = qa(after_bytes=refined, before_bytes=source or after, attempt=attempt)
        last_qa = render.as_dict()
        if not _passed(render):
            reasons = list(render.reasons) or [render.error or "render QA did not pass"]
            retry_note = "; ".join(reasons[:3])
            continue
        check = rug_check(refined=refined, previous=after, rug=rug)
        last_rug = check.as_dict()
        if not _passed(check):
            reasons = list(check.reasons) or [check.error or "rug check did not pass"]
            retry_note = "; ".join(reasons[:3])
            continue
        return RefineOutcome(label, after_label, True, refined, attempt, last_qa, last_rug, [])
    return RefineOutcome(label, after_label, False, None, attempt, last_qa, last_rug, reasons)


def resolve_refine_rug(
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shape and size from the plan, then an admin override on top."""
    spec = {**DEFAULT_ROUND_RUG, **rug_spec(lead, deliverable)}
    spec.pop("keep_existing", None)
    for key, value in (override or {}).items():
        if value not in (None, ""):
            spec[key] = value
    return spec
