"""Gravity-correct uploaded photos before any downstream consumer sees them.

Phone JPEGs often store landscape pixel buffers plus EXIF Orientation=6/8.
Browsers apply that tag when displaying; OpenAI image edit, ReportLab, and raw
vision APIs typically do not. The result is a sideways room: ceiling fan on
a wall, shelves drawn over a window that was actually on the side.

Every upload is transposed, re-encoded as a plain RGB JPEG (EXIF stripped),
and persisted so retries reuse the same upright source.
"""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

EXIF_ORIENTATION_TAG = 274
DEFAULT_JPEG_QUALITY = 90


class UnreadableImage(ValueError):
    """Bytes were not a decodable still image."""


def read_exif_orientation(img: Image.Image) -> int:
    try:
        exif = img.getexif()
        if not exif:
            return 1
        value = exif.get(EXIF_ORIENTATION_TAG)
        if value is None:
            return 1
        return int(value)
    except Exception:
        return 1


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _encode_jpeg(img: Image.Image, *, quality: int = DEFAULT_JPEG_QUALITY) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def normalize_photo_bytes(
    data: Optional[bytes],
    *,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> Tuple[bytes, Dict[str, Any]]:
    """Apply EXIF orientation and return upright JPEG bytes plus metadata.

    ``changed`` is True only when pixels were transposed (or flipped). A
    re-encode of an already-upright JPEG does not count as a change, so
    callers can persist only when gravity actually needed a fix.
    """
    if not data:
        raise UnreadableImage("empty image")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnreadableImage(str(exc) or "unreadable image") from exc

    raw_orientation = read_exif_orientation(img)
    raw_size = img.size
    transposed = ImageOps.exif_transpose(img)
    if transposed is None:
        transposed = img
    upright = _to_rgb(transposed)
    applied = raw_orientation not in (0, 1) or upright.size != raw_size
    encoded = _encode_jpeg(upright, quality=quality)
    width, height = upright.size
    info: Dict[str, Any] = {
        "exif_orientation": raw_orientation,
        "applied": bool(applied),
        "changed": bool(applied),
        "width": width,
        "height": height,
        "is_landscape": width > height,
        "is_portrait": height > width,
        "content_type": "image/jpeg",
    }
    if applied:
        logger.info(
            "Applied EXIF orientation %s (%sx%s → %sx%s)",
            raw_orientation,
            raw_size[0],
            raw_size[1],
            width,
            height,
        )
    return encoded, info


def upright_bytes(data: Optional[bytes]) -> Optional[bytes]:
    """Best-effort gravity correction. Returns the original bytes if undecodable."""
    if not data:
        return None
    try:
        normalized, info = normalize_photo_bytes(data)
        return normalized if info.get("applied") else data
    except UnreadableImage:
        logger.warning("Leaving photo bytes unchanged — could not decode for orientation")
        return data


def upright_jpeg_bytes(
    data: Optional[bytes],
    *,
    quality: int = 88,
    max_edge: Optional[int] = None,
) -> Optional[bytes]:
    """Gravity-correct and re-encode as JPEG with EXIF stripped. None if undecodable.

    Full resolution unless ``max_edge`` is set and the long edge exceeds it.
    The ICC profile is kept so colors match the original.
    """
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    icc = img.info.get("icc_profile")
    rgb = _to_rgb(ImageOps.exif_transpose(img) or img)
    if max_edge and max(rgb.size) > max_edge:
        rgb = rgb.copy()
        rgb.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    options: Dict[str, Any] = {"format": "JPEG", "quality": quality, "optimize": True, "progressive": True}
    if icc:
        options["icc_profile"] = icc
    rgb.save(buf, **options)
    return buf.getvalue()


def rotate_photo_bytes(data: bytes, degrees: int) -> bytes:
    """Rotate clockwise by 0/90/180/270 and return a JPEG."""
    turns = int(degrees) % 360
    if turns not in (0, 90, 180, 270):
        turns = 0
    img = Image.open(io.BytesIO(data))
    img.load()
    upright = ImageOps.exif_transpose(img) or img
    rgb = _to_rgb(upright)
    if turns:
        rgb = rgb.rotate(-turns, expand=True)
    return _encode_jpeg(rgb)


def jpeg_for_vision(
    data: bytes,
    *,
    max_side: int = 1024,
    quality: int = 80,
) -> bytes:
    """Downscale for a cheap vision call. Already gravity-correct if ``data`` is."""
    img = Image.open(io.BytesIO(data))
    img.load()
    rgb = _to_rgb(ImageOps.exif_transpose(img) or img)
    width, height = rgb.size
    longest = max(width, height)
    if longest > max_side and longest > 0:
        scale = max_side / float(longest)
        rgb = rgb.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    return _encode_jpeg(rgb, quality=quality)
