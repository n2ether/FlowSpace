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


def final_email_block_reason(deliverable: Optional[Dict[str, Any]]) -> Optional[str]:
    """Why the customer board and PDF must not go out as final.

    ``None`` means a final send is allowed. Legacy deliverables with no
    per-source record stay sendable. An incomplete package, or any required
    source without an approved after URL, is blocked.
    """
    doc = deliverable or {}
    status = str(doc.get("package_status") or "").strip().lower()
    if status == "incomplete":
        return "Package is incomplete. A required source after failed generation or QA."
    entries = doc.get("source_afters") or []
    if not isinstance(entries, list) or not entries:
        return None
    missing: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            missing.append("source")
            continue
        label = str(entry.get("label") or entry.get("source_photo_id") or "source")
        if entry.get("status") != "approved" or not entry.get("after_url"):
            missing.append(label)
    if missing:
        return "Package is incomplete. Missing afters: " + ", ".join(missing)
    return None
