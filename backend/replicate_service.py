"""Replicate image-to-image generation (flux-kontext-pro)."""
import asyncio
import logging
import os

import replicate
import requests

logger = logging.getLogger(__name__)

MODEL = os.environ.get("REPLICATE_MODEL", "black-forest-labs/flux-kontext-pro")
# replicate client reads REPLICATE_API_TOKEN from the environment automatically.


def _extract_bytes(out) -> bytes:
    """flux-kontext-pro returns a single image (FileOutput or URL)."""
    if isinstance(out, (list, tuple)):
        out = out[0] if out else None
    if out is None:
        raise RuntimeError("Replicate returned no output")
    if hasattr(out, "read"):
        return out.read()
    url = str(out)
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return r.content


def _run(prompt: str, data_uri: str) -> bytes:
    base_input = {
        "prompt": prompt,
        "input_image": data_uri,
        "output_format": "jpg",
        "safety_tolerance": 2,
    }
    try:
        out = replicate.run(MODEL, input={**base_input, "aspect_ratio": "match_input_image"})
    except Exception as e:
        logger.warning(f"Replicate match_input_image failed ({e}); retrying with default ratio")
        out = replicate.run(MODEL, input=base_input)
    return _extract_bytes(out)


async def generate_organized_image(prompt: str, data_uri: str) -> bytes:
    """Run the Replicate model off the event loop and return image bytes."""
    return await asyncio.to_thread(_run, prompt, data_uri)
