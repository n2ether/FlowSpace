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


ROOM_TRANSFORMATION_PROMPT_TEMPLATE = (
    "Transform this uploaded room photo into a clean, organized, peaceful "
    "version of the exact same room. Preserve the original architecture, room "
    "dimensions, camera angle, perspective, wall color, floor color, window "
    "placement, door placement, trim, ceiling fixtures, lighting positions, "
    "outlets, vents, and built-in features. Do not change the layout of the "
    "room. Do not add new windows or doors. Do not remove existing windows or "
    "doors. Do not change the floor material or wall color unless specifically "
    "requested. Only organize clutter and add realistic storage solutions such "
    "as shelves, bins, baskets, cabinets, hooks, labels, closet organizers, "
    "pantry organizers, garage shelving, laundry storage, or under-bed storage. "
    "Make the room feel calm, functional, bright, and mentally peaceful. "
    "Photorealistic result."
)


def build_room_transformation_prompt(intake: Dict[str, Any]) -> str:
    """Build the strict image-editing prompt required for room preservation."""
    details = [
        ROOM_TRANSFORMATION_PROMPT_TEMPLATE,
        f"Room type: {intake.get('room_type') or intake.get('space_type') or 'room'}.",
        f"Pain point: {intake.get('pain_point') or 'clutter and disorganization'}.",
        f"Budget: {intake.get('budget') or 'customer selected budget'}."
        f" Style preference: {intake.get('style_preference') or 'calm, practical, organized'}.",
        f"Preferred stores: {', '.join(intake.get('preferred_stores') or []) or 'Walmart, Target, IKEA'}.",
        f"Rent/own: {intake.get('rent_or_own') or 'not specified'}.",
        (
            "Drilling or wall mounting is allowed."
            if intake.get("mounting_allowed")
            else "Avoid drilling and permanent mounting; use renter-friendly storage where possible."
        ),
        "Critical constraints: preserve architecture, preserve walls, preserve floors, "
        "preserve windows, preserve doors, preserve ceiling fixtures, preserve camera "
        "perspective, do not change room dimensions, do not change wall color unless "
        "requested, do not change flooring, do not hallucinate windows or doors, and "
        "only modify organization/storage elements.",
    ]
    return "\n".join(details)


def _data_url(image_bytes: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


async def _download_image(url: str) -> tuple[bytes, str]:
    import httpx

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "image/png")


def _first_output_url(output: Any) -> Optional[str]:
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list):
        for item in output:
            found = _first_output_url(item)
            if found:
                return found
    if isinstance(output, dict):
        for key in ("url", "image", "output", "generated_image"):
            found = _first_output_url(output.get(key))
            if found:
                return found
    return None


async def _replicate_generate(
    *, image_bytes: bytes, mime_type: str, prompt: str
) -> tuple[bytes, str, str]:
    import httpx

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured")
    model = os.environ.get("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-kontext-pro")
    if "/" not in model:
        raise RuntimeError("REPLICATE_IMAGE_MODEL must use owner/model format")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "input": {
            "prompt": prompt,
            "input_image": _data_url(image_bytes, mime_type),
            "output_format": "png",
        }
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        create = await client.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers=headers,
            json=body,
        )
        create.raise_for_status()
        prediction = create.json()
        get_url = prediction.get("urls", {}).get("get")
        if not get_url:
            raise RuntimeError("Replicate did not return a polling URL")
        for _ in range(90):
            poll = await client.get(get_url, headers=headers)
            poll.raise_for_status()
            prediction = poll.json()
            status = prediction.get("status")
            if status == "succeeded":
                output_url = _first_output_url(prediction.get("output"))
                if not output_url:
                    raise RuntimeError("Replicate succeeded without an image URL")
                out_bytes, out_mime = await _download_image(output_url)
                return out_bytes, out_mime, "replicate"
            if status in {"failed", "canceled"}:
                raise RuntimeError(prediction.get("error") or f"Replicate {status}")
            import asyncio

            await asyncio.sleep(2)
    raise RuntimeError("Replicate image generation timed out")


async def _stability_generate(
    *, image_bytes: bytes, mime_type: str, prompt: str
) -> tuple[bytes, str, str]:
    import httpx

    api_key = os.environ.get("STABILITY_API_KEY")
    if not api_key:
        raise RuntimeError("STABILITY_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "image/*"}
    files = {"image": ("room.png", image_bytes, mime_type)}
    data = {"prompt": prompt, "output_format": "png"}
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            "https://api.stability.ai/v2beta/stable-image/edit/ultra",
            headers=headers,
            files=files,
            data=data,
        )
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "image/png"), "stability"


async def _runware_generate(
    *, image_bytes: bytes, mime_type: str, prompt: str
) -> tuple[bytes, str, str]:
    import httpx

    api_key = os.environ.get("RUNWARE_API_KEY")
    if not api_key:
        raise RuntimeError("RUNWARE_API_KEY is not configured")
    payload = [
        {
            "taskType": "imageInference",
            "taskUUID": str(uuid.uuid4()),
            "positivePrompt": prompt,
            "referenceImages": [_data_url(image_bytes, mime_type)],
            "model": os.environ.get("RUNWARE_IMAGE_MODEL", "runware:100@1"),
            "numberResults": 1,
            "outputFormat": "PNG",
        }
    ]
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            "https://api.runware.ai/v1",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        output_url = _first_output_url(data)
        if not output_url:
            raise RuntimeError("Runware returned no generated image URL")
        out_bytes, out_mime = await _download_image(output_url)
        return out_bytes, out_mime, "runware"


async def generate_room_transformation(
    *,
    image_bytes: bytes,
    mime_type: str,
    intake: Dict[str, Any],
) -> tuple[bytes, str, str, str]:
    """Generate an organized version of one customer photo via selected provider.

    Returns (image_bytes, mime_type, provider_name, prompt). If no image provider
    is configured, a local preview fallback returns the original photo bytes so
    the rest of the customer PDF workflow can still be exercised end-to-end.
    """
    prompt = build_room_transformation_prompt(intake)
    configured_provider = os.environ.get("IMAGE_PROVIDER")
    provider = (
        configured_provider
        or ("replicate" if os.environ.get("REPLICATE_API_TOKEN") else "local-preview")
    ).strip().lower()
    if provider == "replicate":
        out_bytes, out_mime, provider_name = await _replicate_generate(
            image_bytes=image_bytes, mime_type=mime_type, prompt=prompt
        )
    elif provider in {"stability", "stability_ai", "stability-ai"}:
        out_bytes, out_mime, provider_name = await _stability_generate(
            image_bytes=image_bytes, mime_type=mime_type, prompt=prompt
        )
    elif provider == "runware":
        out_bytes, out_mime, provider_name = await _runware_generate(
            image_bytes=image_bytes, mime_type=mime_type, prompt=prompt
        )
    elif provider in {"local", "local-preview", "mock"}:
        logger.warning("IMAGE_PROVIDER is not configured; returning source image as local preview")
        out_bytes, out_mime, provider_name = image_bytes, mime_type, "local-preview"
    else:
        raise RuntimeError(
            "Unsupported IMAGE_PROVIDER. Use replicate, stability, runware, or local-preview."
        )
    return out_bytes, out_mime or "image/png", provider_name, prompt
