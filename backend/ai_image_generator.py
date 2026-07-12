"""
AI image generation using Replicate (FLUX) for FlowSpace room renderings.

Given a lead's questionnaire answers (style/color prefs, storage needs, space type)
generates a photorealistic interior rendering via FLUX on Replicate.

Returns raw image bytes + mime type.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
import replicate

logger = logging.getLogger(__name__)

# FLUX Pro via Replicate — best photorealistic interior quality
REPLICATE_MODEL = "black-forest-labs/flux-1.1-pro"

from ai_drafter import BOTHERS, COLORS, FEELING, STORAGE, STYLE, _humanize


def _build_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
    has_reference: bool = False,
) -> str:
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "living room").lower()

    style_str = ", ".join(_humanize(lead.get("style_prefs") or [], STYLE)) or "modern minimalist"
    color_str = ", ".join(_humanize(lead.get("color_prefs") or [], COLORS)) or "warm neutrals with soft sage accents"
    feeling_str = ", ".join(_humanize(lead.get("desired_feeling") or [], FEELING)) or "calm and functional"
    storage_str = ", ".join(_humanize(lead.get("storage_needs") or [], STORAGE)) or "general storage"

    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    wall_phrase = ""
    if wall_name or wall_hex:
        bits = []
        if wall_name:
            bits.append(wall_name)
        if wall_hex:
            bits.append(f"hex {wall_hex}")
        wall_phrase = f" Wall color: {' / '.join(bits)}."

    must_stay = (lead.get("must_stay") or "").strip()
    must_phrase = f" Keep visible: {must_stay}." if must_stay else ""

    zones = deliverable.get("zones") or []
    zone_titles = [
        (z.get("title") or "").strip()
        for z in zones
        if isinstance(z, dict) and (z.get("title") or "").strip()
    ]
    zone_phrase = f" Distinct zones: {', '.join(zone_titles)}." if zone_titles else ""

    return (
        f"Photorealistic interior design photograph of a beautifully organized residential {space}. "
        f"Aesthetic style: {style_str}. "
        f"Color palette: {color_str}. "
        f"Atmosphere: {feeling_str}, mentally calming. "
        f"Smart storage solutions for {storage_str} — modular shelving, labeled bins, baskets, hooks."
        f"{wall_phrase}{zone_phrase}{must_phrase} "
        "Eye-level front view, wide angle showing full room. "
        "Bright natural lighting, no people, no text or watermarks. "
        "Professional interior photography, magazine quality, ultra detailed, 4K."
    )


async def generate_front_view(
    *,
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]],
    fs_bucket,
) -> Tuple[bytes, str]:
    """Generate a room rendering via Replicate FLUX. Returns (image_bytes, mime_type)."""
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured")

    os.environ["REPLICATE_API_TOKEN"] = api_token
    client = replicate.Client(api_token=api_token)

    prompt = _build_prompt(lead, deliverable)
    logger.info("Replicate FLUX prompt: %s", prompt[:200])

    output = client.run(
        REPLICATE_MODEL,
        input={
            "prompt": prompt,
            "aspect_ratio": "4:3",
            "output_format": "jpg",
            "output_quality": 90,
            "safety_tolerance": 2,
            "prompt_upsampling": True,
        },
    )

    # output is a URL or FileOutput object
    if hasattr(output, "url"):
        image_url = str(output.url)
    elif hasattr(output, "read"):
        data = output.read()
        return data, "image/jpeg"
    else:
        image_url = str(output)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as ac:
        r = await ac.get(image_url)
        r.raise_for_status()
        image_bytes = r.content

    mime = "image/jpeg"
    if image_url.endswith(".png"):
        mime = "image/png"

    logger.info("Replicate image downloaded: %d bytes", len(image_bytes))
    return image_bytes, mime
