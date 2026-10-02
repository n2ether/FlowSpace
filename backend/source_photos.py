"""Classify lead uploads and decide when a package may be emailed as final.

Only room photos are required sources. Intake screenshots (forms, UI captures)
are not camera angles, so they are not edited and they do not count as missing
angles.

Classification is deterministic from the filename and the pixels. It does not
call a vision API: a screenshot is a flat UI field (near-white panels, a few
quantized colors, long rows of one color), and a photograph is continuous tone.
Solid-color fixtures stay room photos so a bright wall is not dropped. An
upload can force ``kind`` to ``room`` or ``non_room``.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

_NON_ROOM_NAME = re.compile(
    r"(screenshot|screen[\s_-]?shot|screencap|intake|form[\s_-]?capture)",
    re.I,
)

# Flat UI: many rows are one color, the frame is mostly near-white, and the
# palette is tiny. A real photo, even a pale wall, keeps more color buckets
# after a coarse quantize. A single flat color (test swatches, blown frames)
# is not a screenshot — those stay room photos.
_UI_WHITE_MIN = 0.38
_UI_FLAT_ROW_MIN = 0.50
_UI_BUCKET_MAX = 40
_SOLID_BUCKET_MAX = 3


def photo_url(photo: Any) -> Optional[str]:
    if isinstance(photo, str):
        text = photo.strip()
        return text or None
    if isinstance(photo, dict):
        for key in ("url", "photo_url", "src"):
            value = photo.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def photo_id_from_url(url: Optional[str]) -> str:
    if not url or "/api/uploads/photo/" not in str(url):
        return ""
    return str(url).rstrip("/").rsplit("/", 1)[-1]


def photo_filename(photo: Any) -> str:
    if isinstance(photo, dict):
        for key in ("filename", "name", "original_filename"):
            value = photo.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def forced_kind(photo: Any) -> Optional[str]:
    """Explicit room / non-room override stored on the upload."""
    if not isinstance(photo, dict):
        return None
    kind = str(photo.get("kind") or photo.get("role") or "").strip().lower()
    if kind in {"room", "non_room"}:
        return kind
    if kind in {"intake", "screenshot", "form"}:
        return "non_room"
    return None


def _ui_stats(data: bytes) -> Optional[Dict[str, float]]:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        small = img.convert("RGB").resize((80, 120), Image.Resampling.BOX)
    except Exception:
        return None
    raw_pixels = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    pixels = list(raw_pixels)
    if pixels and isinstance(pixels[0], int):
        pixels = list(zip(pixels[0::3], pixels[1::3], pixels[2::3]))
    if not pixels:
        return None
    width, height = small.size
    white = 0
    buckets = set()
    for r, g, b in pixels:
        if r >= 245 and g >= 245 and b >= 245:
            white += 1
        buckets.add((r // 32, g // 32, b // 32))
    flat_rows = 0
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        quantized = [(r // 32, g // 32, b // 32) for r, g, b in row]
        mode_count = Counter(quantized).most_common(1)[0][1]
        if mode_count / width >= 0.72:
            flat_rows += 1
    return {
        "white": white / len(pixels),
        "buckets": float(len(buckets)),
        "flat": flat_rows / height,
    }


def classify_image_bytes(data: Optional[bytes], *, filename: str = "") -> Tuple[str, str]:
    """Return ``(kind, reason)`` where kind is ``room`` or ``non_room``.

    Defaults to room. A file is non-room only with a screenshot-like name or
    a positive UI-screenshot pixel signature.
    """
    if _NON_ROOM_NAME.search(filename or ""):
        return "non_room", "filename"
    # Missing or unreadable bytes stay required room sources so the package
    # is marked incomplete instead of inventing an after from no photo.
    if not data:
        return "room", "missing"
    stats = _ui_stats(data)
    if stats is None:
        return "room", "unreadable"
    if stats["buckets"] <= _SOLID_BUCKET_MAX:
        return "room", "solid_or_simple"
    if (
        stats["white"] >= _UI_WHITE_MIN
        and stats["flat"] >= _UI_FLAT_ROW_MIN
        and stats["buckets"] <= _UI_BUCKET_MAX
    ):
        return "non_room", "ui_screenshot"
    return "room", "continuous_tone"


def classify_upload(photo: Any, data: Optional[bytes] = None, *, filename: str = "") -> Tuple[str, str]:
    """Classify one lead upload. An explicit kind wins over pixels."""
    override = forced_kind(photo)
    if override:
        return override, "override"
    name = filename or photo_filename(photo)
    return classify_image_bytes(data, filename=name)


# An after counts only when the persisted row says it was edited from that same source.
# Crops, invented angles, and views derived from a different photo do not count.
OWN_SOURCE_EDIT = "own_source"
_DISQUALIFIED_EDITS = {
    "crop",
    "hero_crop",
    "after_crop",
    "invented",
    "invented_angle",
    "other_source",
    "cross_source",
    "supporting_view",
}


def mapping_is_own_source(entry: Any) -> bool:
    """True only for an explicit SOURCE_n → AFTER_n edit of that same photo.

    The row must be approved, point at an after URL, and record
    ``edit_kind == own_source``. A crop, an invented angle, or an after whose
    ``derived_from_photo_id`` is a different photo does not count.
    """
    if not isinstance(entry, dict):
        return False
    if str(entry.get("edit_kind") or "").strip().lower() != OWN_SOURCE_EDIT:
        return False
    if str(entry.get("status") or "").strip().lower() != "approved":
        return False
    if not str(entry.get("after_url") or "").strip():
        return False
    if entry.get("crop") or entry.get("invented_angle"):
        return False
    source_id = str(entry.get("source_photo_id") or "").strip()
    derived = str(entry.get("derived_from_photo_id") or "").strip()
    if derived and source_id and derived != source_id:
        return False
    if derived and not source_id:
        return False
    return True


def final_email_block_reason(deliverable: Optional[Dict[str, Any]]) -> Optional[str]:
    """Why the customer package must not go out as final.

    ``None`` means a final send is allowed. A lead with no room-photo record
    (no ``source_afters`` and no ``required_source_ids``) stays sendable.
    Any failed, missing, cropped, invented, or cross-source mapping blocks
    the customer final. Contact sheets and draft sends must not claim final.
    """
    doc = deliverable or {}
    status = str(doc.get("package_status") or "").strip().lower()
    raw_entries = doc.get("source_afters") or []
    entries = raw_entries if isinstance(raw_entries, list) else []
    required = [
        str(item).strip()
        for item in (doc.get("required_source_ids") or [])
        if str(item).strip()
    ]

    problems: List[str] = []
    covered = set()
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("source")
            continue
        label = str(entry.get("label") or entry.get("source_photo_id") or "source")
        if mapping_is_own_source(entry):
            source_id = str(entry.get("source_photo_id") or "").strip()
            if source_id:
                covered.add(source_id)
            continue
        problems.append(label)
    for source_id in required:
        if source_id not in covered and source_id not in problems:
            problems.append(source_id)

    if problems:
        return "Package is incomplete. Own-source edits missing: " + ", ".join(problems)
    if status == "incomplete":
        return "Package is incomplete. A required source after failed generation or QA."
    return None


def draft_send_block_reason(deliverable: Optional[Dict[str, Any]]) -> Optional[str]:
    """Review send. Never a customer final.

    Follows the incomplete gate: a failed or missing after cannot go out.
    An explicit crop, invented angle, or cross-source after cannot go out.
    A legacy approved row that has not yet recorded ``edit_kind`` can still
    be reviewed. It still cannot pass ``final_email_block_reason``.
    """
    doc = deliverable or {}
    status = str(doc.get("package_status") or "").strip().lower()
    if status == "incomplete":
        return "Package is incomplete. A required source after failed generation or QA."
    raw_entries = doc.get("source_afters") or []
    entries = raw_entries if isinstance(raw_entries, list) else []
    if not entries:
        return None
    problems: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("source")
            continue
        label = str(entry.get("label") or entry.get("source_photo_id") or "source")
        kind = str(entry.get("edit_kind") or "").strip().lower()
        source_id = str(entry.get("source_photo_id") or "").strip()
        derived = str(entry.get("derived_from_photo_id") or "").strip()
        disqualified = kind in _DISQUALIFIED_EDITS or bool(entry.get("crop") or entry.get("invented_angle"))
        cross = bool(derived and source_id and derived != source_id)
        if disqualified or cross or str(entry.get("status") or "").strip().lower() != "approved" or not entry.get("after_url"):
            problems.append(label)
    if problems:
        return "Package is incomplete. Own-source edits missing: " + ", ".join(problems)
    return None
