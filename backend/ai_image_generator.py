"""
AI image generation for FlowSpace room renderings.

Uses FLUX Kontext (image-to-image) when the customer has uploaded a photo of
their actual space — this preserves the room's real architecture, windows,
proportions, and camera angle while restyling furniture, storage, and decor.

Falls back to text-to-image (FLUX 1.1 Pro) only when no reference photo
exists, since a text-only render can never match a specific room.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx
import replicate

logger = logging.getLogger(__name__)

# Image-to-image: edits the customer's actual photo, preserving room structure.
KONTEXT_MODEL = "black-forest-labs/flux-kontext-pro"
# Text-to-image fallback: used only when no customer photo is available.
TEXT_TO_IMAGE_MODEL = "black-forest-labs/flux-1.1-pro"

from ai_drafter import BOTHERS, COLORS, FEELING, STORAGE, STYLE, _humanize
from image_orientation import upright_bytes

# Replicate flux-kontext-pro has no prompt_strength / guidance_scale.
# Keep prompt_upsampling off so the wall-paint lock is not rewritten.
# https://replicate.com/black-forest-labs/flux-kontext-pro
KONTEXT_PROMPT_UPSAMPLING = False

# Color prefs are for soft goods only. A warm fallback here used to leak onto walls.
SOFT_GOODS_COLOR_FALLBACK = "neutral textiles that complement the existing wall color"

# Shared rails for Kontext, text-to-image, and QA retries.
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
    """Prompt for image-EDITING — keep windows/dimensions ~95% accurate.
    Match existing wall paint. Only change furniture/storage/loose items."""
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


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as ac:
        r = await ac.get(url)
        r.raise_for_status()
        return r.content


def _output_to_url_or_bytes(output) -> Tuple[Optional[str], Optional[bytes]]:
    if hasattr(output, "url"):
        return str(output.url), None
    if hasattr(output, "read"):
        return None, output.read()
    if isinstance(output, list) and output:
        first = output[0]
        if hasattr(first, "url"):
            return str(first.url), None
        return str(first), None
    return str(output), None


def _kontext_model_input(prompt: str, data_uri: str) -> Dict[str, Any]:
    """Replicate Kontext inputs. No guidance/prompt_strength exists on this API.

    prompt_upsampling stays False so the wall-paint lock is not rewritten.
    """
    return {
        "prompt": prompt,
        "input_image": data_uri,
        "aspect_ratio": "match_input_image",
        "output_format": "jpg",
        "safety_tolerance": 2,
        "prompt_upsampling": KONTEXT_PROMPT_UPSAMPLING,
    }


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

    If `reference_photo_bytes` is provided (the customer's actual uploaded photo),
    uses FLUX Kontext to edit that exact photo — preserving the real room.
    Otherwise falls back to text-to-image generation.

    Reference bytes are gravity-corrected again here so retries and admin
    regenerations cannot feed a sideways buffer into Kontext.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured")

    os.environ["REPLICATE_API_TOKEN"] = api_token
    client = replicate.Client(api_token=api_token)

    if reference_photo_bytes:
        reference_photo_bytes = upright_bytes(reference_photo_bytes) or reference_photo_bytes
        prompt = _build_kontext_prompt(
            lead,
            deliverable,
            stronger_rails=stronger_rails,
            extra_constraint=extra_constraint,
        )
        logger.info("FLUX Kontext (image-to-image) prompt: %s", prompt[:200])
        b64 = base64.b64encode(reference_photo_bytes).decode("ascii")
        data_uri = f"data:image/jpeg;base64,{b64}"
        output = client.run(
            KONTEXT_MODEL,
            input=_kontext_model_input(prompt, data_uri),
        )
    else:
        prompt = _build_text_to_image_prompt(
            lead,
            deliverable,
            stronger_rails=stronger_rails,
            extra_constraint=extra_constraint,
        )
        logger.info("FLUX text-to-image (no reference photo) prompt: %s", prompt[:200])
        output = client.run(
            TEXT_TO_IMAGE_MODEL,
            input={
                "prompt": prompt,
                "aspect_ratio": "4:3",
                "output_format": "jpg",
                "output_quality": 90,
                "safety_tolerance": 2,
                "prompt_upsampling": True,
            },
        )

    image_url, image_bytes = _output_to_url_or_bytes(output)
    if image_bytes is None:
        image_bytes = await _download(image_url)

    mime = "image/png" if (image_url or "").endswith(".png") else "image/jpeg"
    logger.info("Room render generated: %d bytes (%s)", len(image_bytes), mime)
    return image_bytes, mime
