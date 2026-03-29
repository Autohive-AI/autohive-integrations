"""
Shotstack Video Editing Integration for Autohive

Provides video editing capabilities including file upload, rendering with
timeline control, text/logo overlays, audio tracks, captions, and more.
"""

from autohive_integrations_sdk import Integration, ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any
import aiohttp
import base64
import mimetypes

from helpers import (
    EDIT_API_BASE,
    INGEST_API_BASE,
    get_environment,
    get_headers,
    poll_render_until_complete,
    poll_source_until_ready,
    download_file_as_base64,
    get_media_info,
    position_to_offset,
    build_timeline_from_clips,
)

shotstack = Integration.load()


# ============================================================================
# File Actions
# ============================================================================


@shotstack.action("upload_file")
class UploadFileAction(ActionHandler):
    """Upload a file to Shotstack and get a URL for use in edits."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            wait_for_ready = inputs.get("wait_for_ready", False)

            file_obj = inputs.get("file")
            if file_obj:
                content_base64 = file_obj.get("content")
                filename = file_obj.get("name")
                content_type = file_obj.get("contentType")
                file_url = file_obj.get("url")
                if file_url and not content_base64:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as response:
                            file_bytes = await response.read()
                            content_base64 = base64.b64encode(file_bytes).decode("utf-8")
            else:
                content_base64 = inputs.get("content")
                filename = inputs.get("filename")
                content_type = inputs.get("content_type")

            if not content_base64 or not filename:
                return ActionResult(
                    data={"result": False, "error": "Missing required file content or filename"},
                    cost_usd=0.0,
                )

            file_bytes = base64.b64decode(content_base64)
            if not content_type:
                guessed_type, _ = mimetypes.guess_type(filename)
                content_type = guessed_type or "application/octet-stream"

            response = await context.fetch(
                f"{INGEST_API_BASE}/{env}/upload",
                method="POST",
                headers=get_headers(context),
            )
            upload_data = response.get("data", {})
            attributes = upload_data.get("attributes", {})
            presigned_url = attributes.get("url")
            source_id = upload_data.get("id")
            upload_headers = attributes.get("headers", {})

            if not presigned_url:
                return ActionResult(
                    data={"result": False, "error": "Failed to get presigned upload URL"},
                    cost_usd=0.0,
                )

            async with aiohttp.ClientSession() as session:
                put_headers = upload_headers if upload_headers else {}
                async with session.put(
                    presigned_url,
                    data=file_bytes,
                    headers=put_headers,
                    skip_auto_headers=["Content-Type"],
                ) as upload_response:
                    if upload_response.status not in (200, 201):
                        error_text = await upload_response.text()
                        return ActionResult(
                            data={"result": False, "error": f"Failed to upload file: {upload_response.status} - {error_text}"},
                            cost_usd=0.0,
                        )

            if wait_for_ready:
                poll_result = await poll_source_until_ready(context, source_id)
                if poll_result["status"] == "ready":
                    return ActionResult(
                        data={"source_id": source_id, "source_url": poll_result["source_url"], "status": "ready", "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"source_id": source_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )

            return ActionResult(
                data={"source_id": source_id, "status": "processing", "result": True},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("check_source_status")
class CheckSourceStatusAction(ActionHandler):
    """Check the status of an uploaded file."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            source_id = inputs["source_id"]
            response = await context.fetch(
                f"{INGEST_API_BASE}/{env}/sources/{source_id}",
                method="GET",
                headers=get_headers(context),
            )
            source_data = response.get("data", {})
            attributes = source_data.get("attributes", {})
            status = attributes.get("status")
            result_data: Dict[str, Any] = {"source_id": source_id, "status": status, "result": True}
            if status == "ready":
                result_data["source_url"] = attributes.get("source")
                result_data["message"] = "File is ready to use in edits!"
            elif status == "failed":
                result_data["error"] = source_data.get("error", "Source processing failed")
                result_data["result"] = False
            else:
                result_data["message"] = f"File is {status}. Check again in a few seconds."
            return ActionResult(data=result_data, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("get_upload_url")
class GetUploadUrlAction(ActionHandler):
    """Get a presigned URL for direct file upload."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            response = await context.fetch(
                f"{INGEST_API_BASE}/{env}/upload",
                method="POST",
                headers=get_headers(context),
            )
            upload_data = response.get("data", {})
            attributes = upload_data.get("attributes", {})
            return ActionResult(
                data={
                    "upload_url": attributes.get("url"),
                    "source_id": upload_data.get("id"),
                    "expires": attributes.get("expires"),
                    "result": True,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"upload_url": None, "source_id": None, "result": False, "error": str(e)}, cost_usd=0.0)


# ============================================================================
# Rendering Actions
# ============================================================================


@shotstack.action("submit_render")
class SubmitRenderAction(ActionHandler):
    """Submit a render job and return immediately with render_id."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            return ActionResult(
                data={"render_id": render_id, "status": "queued", "message": "Render job submitted. Use check_render_status to poll for completion.", "result": True},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("check_render_status")
class CheckRenderStatusAction(ActionHandler):
    """Check the status of a render job."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            render_id = inputs["render_id"]
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render/{render_id}",
                method="GET",
                headers=get_headers(context),
            )
            render_data = response.get("response", {})
            status = render_data.get("status")
            result_data: Dict[str, Any] = {"render_id": render_id, "status": status, "result": True}
            if status == "done":
                result_data["url"] = render_data.get("url")
                result_data["duration"] = render_data.get("duration")
                result_data["message"] = "Render complete!"
            elif status == "failed":
                result_data["error"] = render_data.get("error", "Render failed")
                result_data["result"] = False
            else:
                result_data["message"] = f"Render is {status}. Check again in a few seconds."
            return ActionResult(data=result_data, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("render_and_wait")
class RenderAndWaitAction(ActionHandler):
    """Submit a render job and wait for completion."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            max_wait = inputs.get("max_wait_seconds", 300)
            poll_interval = inputs.get("poll_interval_seconds", 5)
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            poll_result = await poll_render_until_complete(context, render_id, max_wait, poll_interval)
            if poll_result["status"] == "done":
                render_data = poll_result.get("render", {})
                return ActionResult(
                    data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                    cost_usd=0.0,
                )
            return ActionResult(
                data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("download_render")
class DownloadRenderAction(ActionHandler):
    """Download a rendered video/image and return as base64."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            render_id = inputs.get("render_id")
            url = inputs.get("url")
            if render_id and not url:
                response = await context.fetch(
                    f"{EDIT_API_BASE}/{env}/render/{render_id}",
                    method="GET",
                    headers=get_headers(context),
                )
                render_data = response.get("response", {})
                status = render_data.get("status")
                if status != "done":
                    return ActionResult(data={"result": False, "error": f"Render is not complete. Status: {status}"}, cost_usd=0.0)
                url = render_data.get("url")
            if not url:
                return ActionResult(data={"result": False, "error": "No URL available. Provide render_id or url."}, cost_usd=0.0)
            download_result = await download_file_as_base64(context, url)
            return ActionResult(
                data={
                    "content": download_result["content"],
                    "content_type": download_result["content_type"],
                    "filename": download_result["filename"],
                    "size": download_result["size"],
                    "result": True,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ============================================================================
# Editing Actions
# ============================================================================


@shotstack.action("custom_edit")
class CustomEditAction(ActionHandler):
    """Create a fully customizable video edit using Shotstack's timeline structure."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            wait_for_completion = inputs.get("wait_for_completion", True)
            max_wait = inputs.get("max_wait_seconds", 300)
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id, max_wait)
                if poll_result["status"] == "done":
                    render_data = poll_result.get("render", {})
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("compose_video")
class ComposeVideoAction(ActionHandler):
    """Combine multiple video/image clips with transitions."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            clips = inputs["clips"]
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            background_color = inputs.get("background_color", "#000000")
            wait_for_completion = inputs.get("wait_for_completion", True)
            timeline = build_timeline_from_clips(clips, background_color)
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    render_data = poll_result.get("render", {})
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_text_overlay")
class AddTextOverlayAction(ActionHandler):
    """Add text/titles to a video at specified time and position."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            video_url = inputs["video_url"]
            text = inputs["text"]
            style = inputs.get("style", "minimal")
            position = inputs.get("position", "center")
            start_time = inputs.get("start_time", 0)
            duration = inputs.get("duration")
            font_size = inputs.get("font_size", "medium")
            color = inputs.get("color", "#ffffff")
            background_color = inputs.get("background_color")
            effect = inputs.get("effect")
            transition = inputs.get("transition")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)

            if not duration:
                try:
                    media_info = await get_media_info(context, video_url)
                    video_duration = media_info.get("metadata", {}).get("streams", [{}])[0].get("duration", 10)
                    duration = video_duration - start_time
                except Exception:
                    duration = 10

            text_asset: Dict[str, Any] = {
                "type": "html",
                "html": f"<p>{text}</p>",
                "css": f"p {{ font-size: {font_size}; color: {color}; }}",
                "width": 600,
                "height": 200,
                "position": "center",
            }
            if background_color:
                text_asset["background"] = background_color

            text_clip: Dict[str, Any] = {
                "asset": text_asset,
                "start": start_time,
                "length": duration,
                "position": position,
            }
            if effect:
                text_clip["effect"] = effect
            if transition:
                text_clip["transition"] = transition

            video_clip = {"asset": {"type": "video", "src": video_url}, "start": 0}
            timeline = {"tracks": [{"clips": [text_clip]}, {"clips": [video_clip]}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_logo_overlay")
class AddLogoOverlayAction(ActionHandler):
    """Add logo/watermark to a video."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            video_url = inputs["video_url"]
            logo_url = inputs["logo_url"]
            position = inputs.get("position", "bottomRight")
            scale = inputs.get("scale", 0.15)
            opacity = inputs.get("opacity", 1)
            offset_x = inputs.get("offset_x")
            offset_y = inputs.get("offset_y")
            start_time = inputs.get("start_time", 0)
            duration = inputs.get("duration")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)

            if not duration:
                try:
                    media_info = await get_media_info(context, video_url)
                    video_duration = media_info.get("metadata", {}).get("streams", [{}])[0].get("duration", 10)
                    duration = video_duration - start_time
                except Exception:
                    duration = 10

            logo_clip: Dict[str, Any] = {
                "asset": {"type": "image", "src": logo_url},
                "start": start_time,
                "length": duration,
                "scale": scale,
                "position": position,
                "opacity": opacity,
            }
            if offset_x is not None or offset_y is not None:
                offset = position_to_offset(position)
                if offset_x is not None:
                    offset["x"] = offset_x
                if offset_y is not None:
                    offset["y"] = offset_y
                logo_clip["offset"] = offset

            video_clip = {"asset": {"type": "video", "src": video_url}, "start": 0}
            timeline = {"tracks": [{"clips": [logo_clip]}, {"clips": [video_clip]}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_audio_track")
class AddAudioTrackAction(ActionHandler):
    """Add background music or voiceover to a video."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            video_url = inputs["video_url"]
            audio_url = inputs["audio_url"]
            volume = inputs.get("volume", 1)
            start_time = inputs.get("start_time", 0)
            trim_from = inputs.get("trim_from", 0)
            trim_duration = inputs.get("trim_duration")
            fade_in = inputs.get("fade_in")
            fade_out = inputs.get("fade_out")
            mix_mode = inputs.get("mix_mode", "mix")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)

            video_asset: Dict[str, Any] = {"type": "video", "src": video_url}
            if mix_mode == "replace":
                video_asset["volume"] = 0

            audio_asset: Dict[str, Any] = {"type": "audio", "src": audio_url, "volume": volume}
            if trim_from:
                audio_asset["trim"] = trim_from
            if fade_in and fade_out:
                audio_asset["effect"] = "fadeInFadeOut"
            elif fade_in:
                audio_asset["effect"] = "fadeIn"
            elif fade_out:
                audio_asset["effect"] = "fadeOut"

            audio_clip: Dict[str, Any] = {"asset": audio_asset, "start": start_time}
            if trim_duration:
                audio_clip["length"] = trim_duration

            timeline = {"tracks": [{"clips": [{"asset": video_asset, "start": 0}]}, {"clips": [audio_clip]}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("trim_video")
class TrimVideoAction(ActionHandler):
    """Extract a segment from a video."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            video_url = inputs["video_url"]
            start_time = inputs["start_time"]
            end_time = inputs.get("end_time")
            duration = inputs.get("duration")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)

            if end_time is not None:
                length = end_time - start_time
            elif duration is not None:
                length = duration
            else:
                return ActionResult(data={"result": False, "error": "Either end_time or duration is required"}, cost_usd=0.0)

            video_clip = {"asset": {"type": "video", "src": video_url, "trim": start_time}, "start": 0, "length": length}
            timeline = {"tracks": [{"clips": [video_clip]}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    render_data = poll_result.get("render", {})
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("concatenate_videos")
class ConcatenateVideosAction(ActionHandler):
    """Join multiple videos sequentially."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            videos = inputs["videos"]
            transition = inputs.get("transition")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)

            clips = []
            for i, video_url in enumerate(videos):
                video_clip: Dict[str, Any] = {"asset": {"type": "video", "src": video_url}, "start": 0}
                if transition and transition != "none":
                    trans: Dict[str, str] = {}
                    if i > 0:
                        trans["in"] = transition
                    if i < len(videos) - 1:
                        trans["out"] = transition
                    if trans:
                        video_clip["transition"] = trans
                clips.append(video_clip)

            timeline = {"tracks": [{"clips": clips}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id)
                if poll_result["status"] == "done":
                    render_data = poll_result.get("render", {})
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_captions")
class AddCaptionsAction(ActionHandler):
    """Add auto-generated or manual captions/subtitles to a video."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            env = get_environment(context)
            video_url = inputs["video_url"]
            subtitle_url = inputs.get("subtitle_url")
            auto_generate = inputs.get("auto_generate", True)
            font_family = inputs.get("font_family")
            font_size = inputs.get("font_size", 16)
            font_color = inputs.get("font_color", "#ffffff")
            line_height = inputs.get("line_height")
            stroke_color = inputs.get("stroke_color")
            stroke_width = inputs.get("stroke_width")
            background_color = inputs.get("background_color")
            background_opacity = inputs.get("background_opacity", 0.8)
            background_padding = inputs.get("background_padding", 10)
            background_border_radius = inputs.get("background_border_radius", 4)
            position = inputs.get("position", "bottom")
            margin_top = inputs.get("margin_top")
            margin_bottom = inputs.get("margin_bottom", 0.1)
            margin_left = inputs.get("margin_left")
            margin_right = inputs.get("margin_right")
            caption_width = inputs.get("width")
            caption_height = inputs.get("height")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait_for_completion = inputs.get("wait_for_completion", True)
            max_wait = inputs.get("max_wait_seconds", 300)

            video_clip: Dict[str, Any] = {"asset": {"type": "video", "src": video_url}, "start": 0, "length": "auto"}
            if auto_generate and not subtitle_url:
                video_clip["alias"] = "main_video"

            caption_asset: Dict[str, Any] = {"type": "caption"}
            if subtitle_url:
                caption_asset["src"] = subtitle_url
            elif auto_generate:
                caption_asset["src"] = "alias://main_video"
            else:
                return ActionResult(data={"result": False, "error": "Either subtitle_url or auto_generate=True is required"}, cost_usd=0.0)

            font: Dict[str, Any] = {}
            if font_family:
                font["family"] = font_family
            if font_size:
                font["size"] = font_size
            if font_color:
                font["color"] = font_color
            if line_height:
                font["lineHeight"] = line_height
            if stroke_color:
                font["stroke"] = stroke_color
            if stroke_width:
                font["strokeWidth"] = stroke_width
            if font:
                caption_asset["font"] = font

            if background_color:
                caption_asset["background"] = {
                    "color": background_color,
                    "opacity": background_opacity,
                    "padding": background_padding,
                    "borderRadius": background_border_radius,
                }

            if position:
                caption_asset["position"] = position

            margin: Dict[str, Any] = {}
            if margin_top is not None:
                margin["top"] = margin_top
            if margin_bottom is not None:
                margin["bottom"] = margin_bottom
            if margin_left is not None:
                margin["left"] = margin_left
            if margin_right is not None:
                margin["right"] = margin_right
            if margin:
                caption_asset["margin"] = margin

            if caption_width:
                caption_asset["width"] = caption_width
            if caption_height:
                caption_asset["height"] = caption_height

            caption_clip = {"asset": caption_asset, "start": 0, "length": "end"}
            timeline = {"tracks": [{"clips": [caption_clip]}, {"clips": [video_clip]}]}
            payload = {"timeline": timeline, "output": output}
            response = await context.fetch(
                f"{EDIT_API_BASE}/{env}/render",
                method="POST",
                headers=get_headers(context),
                json=payload,
            )
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            if wait_for_completion:
                poll_result = await poll_render_until_complete(context, render_id, max_wait)
                if poll_result["status"] == "done":
                    render_data = poll_result.get("render", {})
                    return ActionResult(
                        data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True},
                        cost_usd=0.0,
                    )
                return ActionResult(
                    data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False},
                    cost_usd=0.0,
                )
            return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
