"""
Shotstack integration helper functions.

Shared utility functions used across action handlers.
"""

from autohive_integrations_sdk import ExecutionContext
from typing import Dict, Any
from urllib.parse import quote
import base64
import asyncio
import mimetypes

EDIT_API_BASE = "https://api.shotstack.io/edit"
INGEST_API_BASE = "https://api.shotstack.io/ingest"


def get_api_key(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {})
    return credentials.get("api_key", "")


def get_environment(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {})
    return credentials.get("environment", "stage")


def get_headers(context: ExecutionContext) -> Dict[str, str]:
    return {
        "x-api-key": get_api_key(context),
        "Content-Type": "application/json",
    }


async def poll_render_until_complete(
    context: ExecutionContext,
    render_id: str,
    max_wait: int = 300,
    poll_interval: int = 5,
) -> Dict[str, Any]:
    """Poll render status until done/failed or timeout."""
    env = get_environment(context)
    elapsed = 0
    while elapsed < max_wait:
        response = await context.fetch(
            f"{EDIT_API_BASE}/{env}/render/{render_id}",
            method="GET",
            headers=get_headers(context),
        )
        render_data = response.get("response", {})
        status = render_data.get("status")
        if status == "done":
            return {"status": "done", "url": render_data.get("url"), "render": render_data}
        elif status == "failed":
            return {"status": "failed", "error": render_data.get("error", "Render failed"), "render": render_data}
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"status": "timeout", "error": f"Render did not complete within {max_wait} seconds", "render_id": render_id}


async def poll_source_until_ready(
    context: ExecutionContext,
    source_id: str,
    max_wait: int = 120,
    poll_interval: int = 3,
) -> Dict[str, Any]:
    """Poll source status until ready or timeout."""
    env = get_environment(context)
    elapsed = 0
    while elapsed < max_wait:
        response = await context.fetch(
            f"{INGEST_API_BASE}/{env}/sources/{source_id}",
            method="GET",
            headers=get_headers(context),
        )
        source_data = response.get("data", {})
        attributes = source_data.get("attributes", {})
        status = attributes.get("status")
        if status == "ready":
            return {"status": "ready", "source_url": attributes.get("source"), "source": source_data}
        elif status == "failed":
            return {"status": "failed", "error": source_data.get("error", "Source processing failed"), "source": source_data}
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"status": "timeout", "error": f"Source did not become ready within {max_wait} seconds", "source_id": source_id}


async def download_file_as_base64(context: ExecutionContext, url: str) -> Dict[str, Any]:
    """Download a file and return as base64-encoded string."""
    response = await context.fetch(url, method="GET", headers={"Accept": "*/*"}, raw_response=True)
    content_type = response.get("content_type", "application/octet-stream")
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(url)
        if guessed_type:
            content_type = guessed_type
    filename = url.split("/")[-1].split("?")[0] or f"downloaded_file{mimetypes.guess_extension(content_type) or ''}"
    content_bytes = response.get("body", b"")
    if isinstance(content_bytes, str):
        content_bytes = content_bytes.encode("utf-8")
    return {
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "content_type": content_type,
        "filename": filename,
        "size": len(content_bytes),
    }


async def get_media_info(context: ExecutionContext, url: str) -> Dict[str, Any]:
    """Get media metadata using Shotstack probe endpoint."""
    env = get_environment(context)
    response = await context.fetch(
        f"{EDIT_API_BASE}/{env}/probe/{quote(url, safe='')}",
        method="GET",
        headers=get_headers(context),
    )
    return response.get("response", {})


def position_to_offset(position: str) -> Dict[str, float]:
    offsets = {
        "center": {"x": 0, "y": 0},
        "top": {"x": 0, "y": 0.4},
        "topRight": {"x": 0.4, "y": 0.4},
        "right": {"x": 0.4, "y": 0},
        "bottomRight": {"x": 0.4, "y": -0.4},
        "bottom": {"x": 0, "y": -0.4},
        "bottomLeft": {"x": -0.4, "y": -0.4},
        "left": {"x": -0.4, "y": 0},
        "topLeft": {"x": -0.4, "y": 0.4},
    }
    return offsets.get(position, {"x": 0, "y": 0})


def build_timeline_from_clips(clips: list, background_color: str = "#000000") -> Dict[str, Any]:
    """Convert simplified clip list to Shotstack timeline structure."""
    timeline_clips = []
    current_time = 0.0
    for clip in clips:
        url = clip.get("url")
        duration = clip.get("duration")
        start_from = clip.get("start_from", 0)
        length = clip.get("length")
        fit = clip.get("fit", "crop")
        effect = clip.get("effect")
        transition = clip.get("transition", {})
        is_image = any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"])
        if is_image:
            asset: Dict[str, Any] = {"type": "image", "src": url}
            clip_length = duration or 5
        else:
            asset = {"type": "video", "src": url}
            if start_from:
                asset["trim"] = start_from
            clip_length = length or duration
        timeline_clip: Dict[str, Any] = {"asset": asset, "start": current_time, "fit": fit}
        if clip_length:
            timeline_clip["length"] = clip_length
        if effect:
            timeline_clip["effect"] = effect
        if transition:
            timeline_clip["transition"] = transition
        timeline_clips.append(timeline_clip)
        current_time += clip_length if clip_length else 5
    return {"background": background_color, "tracks": [{"clips": timeline_clips}]}
