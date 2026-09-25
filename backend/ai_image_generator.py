"""
AI image generation for FlowSpace room renderings.

Uses the OpenAI Images edit API when the customer has uploaded a photo of
their actual space — this preserves the room's real architecture, windows,
proportions, and camera angle while restyling furniture, storage, and decor.

Falls back to OpenAI text-to-image (same model) only when no reference photo
exists, since a text-only render can never match a specific room.

Model: ``gpt-image-2.5-sunburst``. OpenAI's image guide recommends Sunburst
when editing precision matters (wall paint, windows, room geometry). ``gpt-image-1``
is scheduled to shut down on 2026-10-23, so new work should not target it.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI

from ai_drafter import COLORS, FEELING, STORAGE, STYLE, _humanize
from image_orientation import upright_bytes

logger = logging.getLogger(__name__)

# Edit + text-to-image. Sunburst is the docs-recommended model when the edit
# must keep the source photo's structure. Do not pass input_fidelity: GPT Image
# 2 and 2.5 always process image inputs at high fidelity.
IMAGE_MODEL = "gpt-image-2.5-sunburst"

# JPEG matches the PDF/GridFS path (mime contains "jpeg" → .jpg).
IMAGE_OUTPUT_FORMAT = "jpeg"
IMAGE_OUTPUT_COMPRESSION = 90
IMAGE_QUALITY = "high"
# Match the upright source photo's aspect ratio.
EDIT_SIZE = "auto"
# 4:3, same framing the old text-to-image path requested. Edges are multiples
# of 16 and the pixel count is inside the GPT Image 2.5 size limits.
TEXT_TO_IMAGE_SIZE = "1536x1152"
IMAGE_TIMEOUT_SECONDS = 180.0

# Color prefs are for soft goods only. A warm fallback here used to leak onto walls.
SOFT_GOODS_COLOR_FALLBACK = "neutral textiles that complement the existing wall color"

# Shared rails for image edit, text-to-image, and QA retries.
WALL_PRESERVE_RAILS = (
    "CRITICAL EDIT LOCK — WALL PAINT MUST MATCH THE REFERENCE PHOTO EXACTLY. "
    "Copy the existing wall paint 1:1: same hue, same lightness — light blue / "
    "cool gray-blue / light gray-blue if that is what the photo shows. "
    "FORBIDDEN: warm taupe, beige, cream, sand, greige, terracotta, or earth-tone "
    "wall makeovers. Do not repaint, re-tint, color-grade, white-balance, or restyle "
    "the walls. Color preferences apply ONLY to textiles, pillows, baskets, rugs, "
    "throws, and accessories — never to wall paint. "
)

ORGANIZE_RAILS = (
    "HARD CONSTRAINT: Windows and room dimensions must stay ~95% accurate to the "
    "source photo — same window count, size, and placement, same wall lengths, "
    "same camera angle, same architecture. Do not add, remove, move, or invent "
    "walls, windows, doors, or dimensions. "
    "Never place shelves, racks, cabinets, bins, or any storage in front of, "
    "over, or across a window or door — openings stay fully visible and in the "
    "same location. "
    "Keep ceiling fans, lights, vents, smoke detectors, and other fixtures on the "
    "ceiling — never mounted on a wall. "
    "Gravity must be correct: floor at the bottom of the frame, ceiling at the top. "
    "Do not rotate the room or treat a wall as the ceiling. "
    + WALL_PRESERVE_RAILS
)

RETRY_RAILS = (
    "PREVIOUS RENDER FAILED QA. The last attempt covered a window/door, put a "
    "ceiling fixture on a wall / used wrong gravity, or changed the wall paint. "
    "Re-edit the source photo: keep every window fully visible, keep fans and lights "
    "on the ceiling, floor at the bottom, and match the original light wall color "
    "from the photo — light blue / cool gray-blue, not warm taupe or beige. "
    "Do not repeat the failed layout."
)

WALL_RETRY_CONSTRAINT = (
    "FAILED QA: walls were repainted. Keep the original light wall color from the "
    "photo exactly — light blue / cool gray-blue, not warm taupe or beige. "
    "Do not color-grade or restyle the walls. Color preferences are textiles only."
)


def _soft_goods_colors(lead: Dict[str, Any]) -> str:
    """color_prefs describe textiles/accessories only — never wall paint."""
    prefs = _humanize(lead.get("color_prefs") or [], COLORS)
    return ", ".join(prefs) if prefs else SOFT_GOODS_COLOR_FALLBACK


def _build_kontext_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
    *,
    stronger_rails: bool = False,
    extra_constraint: str = "",
) -> str:
    """Prompt for image editing — keep windows/dimensions ~95% accurate.

    Match existing wall paint. Only change furniture/storage/loose items.
    The function name is historical; the text is what we send to the OpenAI
    Images edit API.
    """
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "room").lower().replace("_", " ")

    style_str = ", ".join(_humanize(lead.get("style_prefs") or [], STYLE)) or "modern minimalist"
    color_str = _soft_goods_colors(lead)
    storage_str = ", ".join(_humanize(lead.get("storage_needs") or [], STORAGE)) or "everyday items"

    rails = ORGANIZE_RAILS
    if stronger_rails:
        rails = rails + RETRY_RAILS
    extra = (extra_constraint or "").strip()
    if extra and not extra.endswith((".", " ")):
        extra = extra + " "

    return (
        f"Edit this existing {space} photo while keeping the original composition. "
        "WALL PAINT LOCK: match the reference photo's exact wall paint — light blue / "
        "cool gray-blue / light gray-blue stays that color. Do not warm, taupe, beige, "
        "or earth-tone the walls. "
        f"Change only furniture, storage, and loose items into a tidy {style_str} layout. "
        f"Soft-goods colors only (textiles, baskets, pillows — NEVER walls): {color_str}. "
        f"Add tidy storage for {storage_str}: matching baskets, "
        f"labeled bins, streamlined shelving. Clear clutter from the floor and surfaces. "
        f"{rails}{extra}"
        "Do not change wall paint. The walls must look like the same painted surface as "
        "the input photo. Photorealistic, natural lighting, "
        "no people, no text or watermarks."
    )


# Public alias for callers that think in "edit" rather than the old model name.
_build_edit_prompt = _build_kontext_prompt


def _build_text_to_image_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
    *,
    stronger_rails: bool = False,
    extra_constraint: str = "",
) -> str:
    """Fallback prompt when there's no customer photo to edit."""
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "closet").lower().replace("_", " ")

    style_str = ", ".join(_humanize(lead.get("style_prefs") or [], STYLE)) or "modern minimalist"
    color_str = _soft_goods_colors(lead)
    feeling_str = ", ".join(_humanize(lead.get("desired_feeling") or [], FEELING)) or "calm and functional"
    storage_str = ", ".join(_humanize(lead.get("storage_needs") or [], STORAGE)) or "general storage"

    rails = (
        "Do not invent unusual windows or exaggerated room dimensions. "
        "Never place shelves or storage over windows or doors. "
        "Keep ceiling fans, lights, and fixtures on the ceiling, never on a wall. "
        "Gravity correct: floor at the bottom, ceiling at the top. "
        "Do not feature a painted-wall makeover — keep existing wall color. "
        "Match existing wall paint exactly — light blue / cool gray-blue if that is "
        "the room; apply color preferences only to textiles and accessories, never walls. "
        "FORBIDDEN: warm taupe or beige wall makeovers. "
    )
    if stronger_rails:
        rails = rails + RETRY_RAILS
    extra = (extra_constraint or "").strip()
    if extra and not extra.endswith((".", " ")):
        extra = extra + " "

    return (
        f"Photorealistic photograph of a beautifully organized residential {space}. "
        f"Aesthetic style: {style_str}. "
        f"Textile and accessory colors only (never wall paint): {color_str}. "
        f"Atmosphere: {feeling_str}, mentally calming. "
        f"Smart storage for {storage_str} — modular shelving, labeled bins, baskets, hooks. "
        f"{rails}{extra}"
        "Eye-level front view, wide angle showing the full space. "
        "Bright natural lighting, no people, no text or watermarks. "
        "Professional interior photography, magazine quality, ultra detailed, 4K."
    )


def edit_api_params(prompt: str) -> Dict[str, Any]:
    """Images edit settings. ``image`` is attached by the caller.

    ``input_fidelity`` is intentionally omitted. GPT Image 2.5 always reads
    reference photos at high fidelity, and the API rejects the old knob.
    """
    return {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "size": EDIT_SIZE,
        "quality": IMAGE_QUALITY,
        "output_format": IMAGE_OUTPUT_FORMAT,
        "output_compression": IMAGE_OUTPUT_COMPRESSION,
    }


def generate_api_params(prompt: str) -> Dict[str, Any]:
    """Text-to-image settings used only when there is no customer photo."""
    return {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "size": TEXT_TO_IMAGE_SIZE,
        "quality": IMAGE_QUALITY,
        "output_format": IMAGE_OUTPUT_FORMAT,
        "output_compression": IMAGE_OUTPUT_COMPRESSION,
    }


def _require_openai_key() -> str:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return api_key


def _openai_client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, timeout=IMAGE_TIMEOUT_SECONDS, max_retries=2)


def _image_upload(data: bytes) -> Tuple[str, bytes, str]:
    """Filename, bytes, and content type for the Images edit multipart file."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "room.png", data, "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "room.webp", data, "image/webp"
    return "room.jpg", data, "image/jpeg"


def _mime_from_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _bytes_from_response(result: Any) -> Tuple[bytes, str]:
    """Decode an Images API response into the (bytes, mime) automation expects."""
    data = getattr(result, "data", None) or []
    if not data:
        raise RuntimeError("OpenAI image response did not include image data")
    first = data[0]
    b64 = getattr(first, "b64_json", None)
    if not b64:
        raise RuntimeError("OpenAI image response did not include image bytes")
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:
        raise RuntimeError("OpenAI image response bytes could not be decoded") from exc
    if not raw:
        raise RuntimeError("OpenAI image response was empty")
    return raw, _mime_from_bytes(raw)


async def generate_front_view(
    *,
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]],
    fs_bucket,
    reference_photo_bytes: Optional[bytes] = None,
    stronger_rails: bool = False,
    extra_constraint: str = "",
) -> Tuple[bytes, str]:
    """
    Generate a room rendering.

    If ``reference_photo_bytes`` is provided (the customer's actual uploaded photo),
    uses the OpenAI Images edit API on that exact photo — preserving the real room.
    Otherwise falls back to OpenAI text-to-image.

    Reference bytes are gravity-corrected again here so retries and admin
    regenerations cannot feed a sideways buffer into the edit.

    Returns ``(image_bytes, mime)``. Missing ``OPENAI_API_KEY`` and API failures
    raise ``RuntimeError`` so the automation QA loop can soft-fail the same way
    it did for the previous image provider.
    """
    api_key = _require_openai_key()
    client = _openai_client(api_key)

    try:
        if reference_photo_bytes:
            reference_photo_bytes = upright_bytes(reference_photo_bytes) or reference_photo_bytes
            prompt = _build_edit_prompt(
                lead,
                deliverable,
                stronger_rails=stronger_rails,
                extra_constraint=extra_constraint,
            )
            logger.info("OpenAI image edit prompt: %s", prompt[:200])
            upload = _image_upload(reference_photo_bytes)
            result = await client.images.edit(
                image=[upload],
                **edit_api_params(prompt),
            )
        else:
            prompt = _build_text_to_image_prompt(
                lead,
                deliverable,
                stronger_rails=stronger_rails,
                extra_constraint=extra_constraint,
            )
            logger.info("OpenAI text-to-image (no reference photo) prompt: %s", prompt[:200])
            result = await client.images.generate(**generate_api_params(prompt))
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("OpenAI image generation failed: %s", exc)
        raise RuntimeError(f"OpenAI image generation failed: {exc}") from exc

    image_bytes, mime = _bytes_from_response(result)
    logger.info("Room render generated: %d bytes (%s)", len(image_bytes), mime)
    return image_bytes, mime
