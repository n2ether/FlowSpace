"""Virtual walkthrough video provider adapters for FlowSpace room jobs."""
from __future__ import annotations

import base64
import os
import uuid
from typing import List, Tuple


def _data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


def _first_url(value):
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, list):
        for item in value:
            found = _first_url(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("url", "video", "output", "asset", "downloadUrl"):
            found = _first_url(value.get(key))
            if found:
                return found
    return None


async def _download(url: str) -> Tuple[bytes, str]:
    import httpx

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "video/mp4")


async def _runway_generate(source_frames: List[bytes], prompt: str) -> Tuple[bytes, str, str]:
    import asyncio
    import httpx

    api_key = os.environ.get("RUNWAY_API_KEY")
    if not api_key:
        raise RuntimeError("RUNWAY_API_KEY is not configured")

    payload = {
        "model": os.environ.get("RUNWAY_VIDEO_MODEL", "gen4_turbo"),
        "promptText": prompt,
        "promptImage": _data_url(source_frames[0]),
        "ratio": "1280:720",
        "duration": int(os.environ.get("RUNWAY_VIDEO_DURATION", "5")),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": os.environ.get("RUNWAY_API_VERSION", "2024-11-06"),
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        create = await client.post("https://api.dev.runwayml.com/v1/image_to_video", headers=headers, json=payload)
        create.raise_for_status()
        task = create.json()
        task_id = task.get("id")
        if not task_id:
            raise RuntimeError("Runway did not return a task id")
        for _ in range(120):
            poll = await client.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
            poll.raise_for_status()
            task = poll.json()
            status = (task.get("status") or "").upper()
            if status in {"SUCCEEDED", "SUCCESS"}:
                output_url = _first_url(task.get("output"))
                if not output_url:
                    raise RuntimeError("Runway succeeded without a video URL")
                video_bytes, mime = await _download(output_url)
                return video_bytes, mime, "runway"
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                raise RuntimeError(task.get("failure") or "Runway video generation failed")
            await asyncio.sleep(3)
    raise RuntimeError("Runway video generation timed out")


async def _luma_generate(source_frames: List[bytes], prompt: str) -> Tuple[bytes, str, str]:
    import asyncio
    import httpx

    api_key = os.environ.get("LUMA_API_KEY")
    if not api_key:
        raise RuntimeError("LUMA_API_KEY is not configured")
    payload = {
        "prompt": prompt,
        "keyframes": {"frame0": {"type": "image", "url": _data_url(source_frames[0])}},
        "model": os.environ.get("LUMA_VIDEO_MODEL", "ray-2"),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        create = await client.post("https://api.lumalabs.ai/dream-machine/v1/generations", headers=headers, json=payload)
        create.raise_for_status()
        generation = create.json()
        generation_id = generation.get("id")
        if not generation_id:
            raise RuntimeError("Luma did not return a generation id")
        for _ in range(120):
            poll = await client.get(
                f"https://api.lumalabs.ai/dream-machine/v1/generations/{generation_id}",
                headers=headers,
            )
            poll.raise_for_status()
            generation = poll.json()
            state = (generation.get("state") or "").lower()
            if state == "completed":
                output_url = _first_url(generation.get("assets") or generation.get("video"))
                if not output_url:
                    raise RuntimeError("Luma completed without a video URL")
                video_bytes, mime = await _download(output_url)
                return video_bytes, mime, "luma"
            if state in {"failed", "dreaming_failed"}:
                raise RuntimeError(generation.get("failure_reason") or "Luma video generation failed")
            await asyncio.sleep(3)
    raise RuntimeError("Luma video generation timed out")


async def generate_walkthrough_video(source_frames: List[bytes]) -> Tuple[bytes, str, str]:
    """Generate a calm walkthrough video from organized source frames."""
    if not source_frames:
        raise RuntimeError("No organized source frames available for video generation")

    prompt = (
        "Create a calm, slow virtual walkthrough of this organized room. Keep the "
        "room structure stable: do not distort walls, floors, windows, doors, "
        "ceiling fixtures, camera perspective, built-ins, or room dimensions. "
        "Use gentle movement, natural light, and a peaceful premium home "
        "organization feel."
    )
    provider = (os.environ.get("VIDEO_PROVIDER") or "").strip().lower()
    if provider == "runway":
        return await _runway_generate(source_frames, prompt)
    if provider == "luma":
        return await _luma_generate(source_frames, prompt)
    if os.environ.get("RUNWAY_API_KEY"):
        return await _runway_generate(source_frames, prompt)
    if os.environ.get("LUMA_API_KEY"):
        return await _luma_generate(source_frames, prompt)
    raise RuntimeError("No video provider configured. Set VIDEO_PROVIDER plus RUNWAY_API_KEY or LUMA_API_KEY.")
