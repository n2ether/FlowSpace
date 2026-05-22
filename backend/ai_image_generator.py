"""
AI image generation for FlowSpace deliverable renderings.

Uses Gemini Nano Banana (gemini-3.1-flash-image-preview) via the Emergent
LLM key. Given a lead's questionnaire answers (style/color prefs, storage
needs, must-keep items, space type) and optionally one or more customer
photos of the actual space, we generate a clean photorealistic 3D front
view of the redesigned space.

The output is raw PNG bytes — the caller persists them however it wants
(GridFS in our case).
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from emergentintegrations.llm.chat import (
    ImageContent,
    LlmChat,
    UserMessage,
)

from ai_drafter import (
    BOTHERS,
    COLORS,
    FEELING,
    STORAGE,
    STYLE,
    _humanize,
)

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "gemini"
MODEL_NAME = "gemini-3.1-flash-image-preview"

SYSTEM_PROMPT = (
    "You are a professional interior design visualizer for FlowSpace, a "
    "home-organization studio. When asked to generate an image, return a "
    "single photorealistic 3D interior rendering of the described space. "
    "Clean lines, calm lighting, no people, no text or watermarks, no "
    "logos. Composition: eye-level front view, slightly wide angle, the "
    "full back wall visible with storage organized along it. Keep the "
    "style cohesive with the requested aesthetic."
)


def _build_prompt(
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]] = None,
    has_reference: bool = False,
) -> str:
    deliverable = deliverable or {}
    space = (lead.get("space_type") or "garage").lower()

    style_list = _humanize(lead.get("style_prefs") or [], STYLE)
    color_list = _humanize(lead.get("color_prefs") or [], COLORS)
    feeling_list = _humanize(lead.get("desired_feeling") or [], FEELING)
    storage_list = _humanize(lead.get("storage_needs") or [], STORAGE)
    bothers_list = _humanize(lead.get("bothers_about") or [], BOTHERS)

    style_str = ", ".join(style_list) or "modern minimalist"
    color_str = ", ".join(color_list) or "warm neutrals with soft sage accents"
    feeling_str = ", ".join(feeling_list) or "calm and functional"
    storage_str = ", ".join(storage_list) or "general storage"

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
    must_phrase = (
        f" The redesign must keep these existing items visible: {must_stay}."
        if must_stay
        else ""
    )

    zones = deliverable.get("zones") or []
    zone_titles = [
        (z.get("title") or "").strip()
        for z in zones
        if isinstance(z, dict) and (z.get("title") or "").strip()
    ]
    zone_phrase = (
        f" Show distinct functional zones: {', '.join(zone_titles)}."
        if zone_titles
        else ""
    )

    pain_phrase = (
        f" Solve these pain points: {', '.join(bothers_list)}."
        if bothers_list
        else ""
    )

    reference_phrase = (
        " Use the attached photo(s) as a reference for the actual room "
        "dimensions, door/window placement, and ceiling — preserve the "
        "footprint but reimagine the contents as described above."
        if has_reference
        else ""
    )

    return (
        f"Generate a photorealistic 3D rendering of a redesigned residential "
        f"{space}, eye-level front view. "
        f"Aesthetic: {style_str}. "
        f"Color palette: {color_str}. "
        f"Atmosphere: {feeling_str}. "
        f"Storage focus: well-organized {storage_str} along the back/side "
        f"walls — slatwall, modular cabinets, labeled bins, hooks and "
        f"shelving as appropriate."
        f"{wall_phrase}"
        f"{zone_phrase}"
        f"{must_phrase}"
        f"{pain_phrase}"
        f"{reference_phrase}"
        " Render at high quality, bright even lighting, no people, no text, "
        "no logos, no watermarks. Clean floor, professional interior "
        "photography composition."
    )


async def _fetch_reference_images(
    lead: Dict[str, Any],
    fs_bucket,
    max_images: int = 2,
) -> List[ImageContent]:
    """Pull up to N customer-uploaded photos from GridFS as ImageContent."""
    from bson import ObjectId
    from gridfs.errors import NoFile

    out: List[ImageContent] = []
    photos = lead.get("photos") or []
    for p in photos[:max_images]:
        if not isinstance(p, str) or "/api/uploads/photo/" not in p:
            continue
        photo_id = p.rsplit("/", 1)[-1]
        try:
            oid = ObjectId(photo_id)
        except Exception:
            continue
        try:
            stream = await fs_bucket.open_download_stream(oid)
        except NoFile:
            continue
        data = await stream.read()
        if not data:
            continue
        out.append(ImageContent(base64.b64encode(data).decode("utf-8")))
    return out


async def generate_front_view(
    *,
    lead: Dict[str, Any],
    deliverable: Optional[Dict[str, Any]],
    fs_bucket,
) -> tuple[bytes, str]:
    """Generate a 3D front view rendering.

    Returns: (image_bytes, mime_type) — usually image/png or image/jpeg.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    references = await _fetch_reference_images(lead, fs_bucket, max_images=2)
    prompt = _build_prompt(lead, deliverable, has_reference=bool(references))

    chat = (
        LlmChat(
            api_key=api_key,
            session_id=f"front-view-{lead.get('id', uuid.uuid4())}-{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_PROMPT,
        )
        .with_model(MODEL_PROVIDER, MODEL_NAME)
        .with_params(modalities=["image", "text"])
    )

    msg = UserMessage(text=prompt, file_contents=references or None)
    text, images = await chat.send_message_multimodal_response(msg)
    logger.info(
        "Nano Banana returned %d image(s) for lead %s (text len=%d)",
        len(images or []),
        lead.get("id"),
        len(text or ""),
    )

    if not images:
        raise RuntimeError("Image generation returned no images")

    first = images[0]
    data_b64 = first.get("data") if isinstance(first, dict) else None
    mime = (first.get("mime_type") if isinstance(first, dict) else None) or "image/png"
    if not data_b64:
        raise RuntimeError("Image generation returned no image data")
    return base64.b64decode(data_b64), mime
