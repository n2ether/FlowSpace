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


def _build_kontext_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
) -> str:
    """Prompt for image-EDITING — must instruct the model to keep the room's
    real structure and only change furniture/storage/decor/color."""
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "room").lower().replace("_", " ")

    style_str = ", ".join(_humanize(lead.get("style_prefs") or [], STYLE)) or "modern minimalist"
    color_str = ", ".join(_humanize(lead.get("color_prefs") or [], COLORS)) or "warm neutrals with soft sage accents"
    storage_str = ", ".join(_humanize(lead.get("storage_needs") or [], STORAGE)) or "everyday items"

    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    wall_phrase = ""
    if wall_name or wall_hex:
        bits = [b for b in [wall_name, (f"hex {wall_hex}" if wall_hex else "")] if b]
        wall_phrase = f" Repaint the walls {' / '.join(bits)}."

    return (
        f"Transform this {space} into a beautifully organized, {style_str} space "
        f"with a {color_str} color palette. "
        f"Add smart, tidy storage for {storage_str} — matching baskets, labeled bins, "
        f"streamlined shelving. Remove clutter from the floor and surfaces."
        f"{wall_phrase} "
        "IMPORTANT: Keep the exact same room — same walls, same windows, same doors, "
        "same camera angle, same architecture and proportions. Only change the "
        "furniture, storage, decor, and surface colors. This must look like the same "
        "physical room, just organized and restyled. Photorealistic, natural lighting, "
        "no people, no text or watermarks."
    )


def _build_text_to_image_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
) -> str:
    """Fallback prompt when there's no customer photo to edit."""
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "living room").lower().replace("_", " ")

    style_str = ", ".join(_humanize(lead.get("style_prefs") or [], STYLE)) or "modern minimalist"
    color_str = ", ".join(_humanize(lead.get("color_prefs") or [], COLORS)) or "warm neutrals with soft sage accents"
    feeling_str = ", ".join(_humanize(lead.get("desired_feeling") or [], FEELING)) or "calm and functional"
    storage_str = ", ".join(_humanize(lead.get("storage_needs") or [], STORAGE)) or "general storage"

    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    wall_phrase = ""
    if wall_name or wall_hex:
        bits = [b for b in [wall_name, (f"hex {wall_hex}" if wall_hex else "")] if b]
        wall_phrase = f" Wall color: {' / '.join(bits)}."

    return (
        f"Photorealistic interior design photograph of a beautifully organized residential {space}. "
        f"Aesthetic style: {style_str}. Color palette: {color_str}. "
        f"Atmosphere: {feeling_str}, mentally calming. "
        f"Smart storage solutions for {storage_str} — modular shelving, labeled bins, baskets, hooks."
        f"{wall_phrase} Eye-level front view, wide angle showing full room. "
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


async def generate_front_view(
    *,
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]],
    fs_bucket,
    reference_photo_bytes: Optional[bytes] = None,
) -> Tuple[bytes, str]:
    """
    Generate a room rendering.

    If `reference_photo_bytes` is provided (the customer's actual uploaded photo),
    uses FLUX Kontext to edit that exact photo — preserving the real room.
    Otherwise falls back to text-to-image generation.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured")

    os.environ["REPLICATE_API_TOKEN"] = api_token
    client = replicate.Client(api_token=api_token)

    if reference_photo_bytes:
        prompt = _build_kontext_prompt(lead, deliverable)
        logger.info("FLUX Kontext (image-to-image) prompt: %s", prompt[:200])
        b64 = base64.b64encode(reference_photo_bytes).decode("ascii")
        data_uri = f"data:image/jpeg;base64,{b64}"
        output = client.run(
            KONTEXT_MODEL,
            input={
                "prompt": prompt,
                "input_image": data_uri,
                "aspect_ratio": "match_input_image",
                "output_format": "jpg",
                "safety_tolerance": 2,
            },
        )
    else:
        prompt = _build_text_to_image_prompt(lead, deliverable)
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
