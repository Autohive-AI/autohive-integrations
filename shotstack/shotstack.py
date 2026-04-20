from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Any, Dict
from urllib.parse import quote
import asyncio
import base64
import mimetypes
import os


config_path = os.path.join(os.path.dirname(__file__), "config.json")
shotstack = Integration.load(config_path)

EDIT_API_BASE = "https://api.shotstack.io/edit"
INGEST_API_BASE = "https://api.shotstack.io/ingest"


def _get_api_key(context: ExecutionContext) -> str:
    return context.auth.get("credentials", {}).get("api_key", "")


def _get_env(context: ExecutionContext) -> str:
    return context.auth.get("credentials", {}).get("environment", "stage")


def _get_headers(context: ExecutionContext) -> Dict[str, str]:
    return {"x-api-key": _get_api_key(context), "Content-Type": "application/json"}


async def _poll_render(context: ExecutionContext, render_id: str, max_wait: int = 300, poll_interval: int = 5) -> Dict[str, Any]:
    env = _get_env(context)
    elapsed = 0
    while elapsed < max_wait:
        response = await context.fetch(f"{EDIT_API_BASE}/{env}/render/{render_id}", method="GET", headers=_get_headers(context))
        render_data = response.get("response", {})
        status = render_data.get("status")
        if status == "done":
            return {"status": "done", "url": render_data.get("url"), "render": render_data}
        elif status == "failed":
            return {"status": "failed", "error": render_data.get("error", "Render failed"), "render": render_data}
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"status": "timeout", "error": f"Render did not complete within {max_wait} seconds"}


async def _poll_source(context: ExecutionContext, source_id: str, max_wait: int = 120, poll_interval: int = 3) -> Dict[str, Any]:
    env = _get_env(context)
    elapsed = 0
    while elapsed < max_wait:
        response = await context.fetch(f"{INGEST_API_BASE}/{env}/sources/{source_id}", method="GET", headers=_get_headers(context))
        source_data = response.get("data", {})
        attributes = source_data.get("attributes", {})
        status = attributes.get("status")
        if status == "ready":
            return {"status": "ready", "source_url": attributes.get("source"), "source": source_data}
        elif status == "failed":
            return {"status": "failed", "error": source_data.get("error", "Source processing failed")}
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"status": "timeout", "error": f"Source did not become ready within {max_wait} seconds"}


async def _download_base64(context: ExecutionContext, url: str) -> Dict[str, Any]:
    response = await context.fetch(url, method="GET", headers={"Accept": "*/*"}, raw_response=True)
    content_type = response.get("content_type", "application/octet-stream")
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(url)
        if guessed_type:
            content_type = guessed_type
    filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
    content_bytes = response.get("body", b"")
    if isinstance(content_bytes, str):
        content_bytes = content_bytes.encode("utf-8")
    return {"content": base64.b64encode(content_bytes).decode("utf-8"), "content_type": content_type, "filename": filename, "size": len(content_bytes)}


async def _get_media_info(context: ExecutionContext, url: str) -> Dict[str, Any]:
    env = _get_env(context)
    encoded_url = quote(url, safe="")
    response = await context.fetch(f"{EDIT_API_BASE}/{env}/probe/{encoded_url}", method="GET", headers=_get_headers(context))
    return response.get("response", {})


def _position_to_offset(position: str) -> Dict[str, float]:
    offsets = {
        "center": {"x": 0, "y": 0}, "top": {"x": 0, "y": 0.4}, "topRight": {"x": 0.4, "y": 0.4},
        "right": {"x": 0.4, "y": 0}, "bottomRight": {"x": 0.4, "y": -0.4}, "bottom": {"x": 0, "y": -0.4},
        "bottomLeft": {"x": -0.4, "y": -0.4}, "left": {"x": -0.4, "y": 0}, "topLeft": {"x": -0.4, "y": 0.4},
    }
    return offsets.get(position, {"x": 0, "y": 0})


def _build_timeline_from_clips(clips: list, background_color: str = "#000000") -> Dict[str, Any]:
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
            asset = {"type": "image", "src": url}
            clip_length = duration or 5
        else:
            asset = {"type": "video", "src": url}
            if start_from:
                asset["trim"] = start_from
            clip_length = length or duration
        timeline_clip = {"asset": asset, "start": current_time, "fit": fit}
        if clip_length:
            timeline_clip["length"] = clip_length
        if effect:
            timeline_clip["effect"] = effect
        if transition:
            timeline_clip["transition"] = transition
        timeline_clips.append(timeline_clip)
        current_time += clip_length if clip_length else 5
    return {"background": background_color, "tracks": [{"clips": timeline_clips}]}


async def _submit_and_maybe_wait(context: ExecutionContext, payload: Dict[str, Any], wait: bool, max_wait: int = 300) -> ActionResult:
    env = _get_env(context)
    response = await context.fetch(f"{EDIT_API_BASE}/{env}/render", method="POST", headers=_get_headers(context), json=payload)
    render_id = response.get("response", {}).get("id")
    if not render_id:
        return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
    if wait:
        poll_result = await _poll_render(context, render_id, max_wait)
        if poll_result["status"] == "done":
            render_data = poll_result.get("render", {})
            return ActionResult(data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": render_data.get("duration"), "result": True}, cost_usd=0.0)
        return ActionResult(data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False}, cost_usd=0.0)
    return ActionResult(data={"render_id": render_id, "status": "queued", "result": True}, cost_usd=0.0)


@shotstack.action("upload_file")
class UploadFileAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            wait_for_ready = inputs.get("wait_for_ready", False)
            file_obj = inputs.get("file")
            if file_obj:
                content_base64 = file_obj.get("content")
                filename = file_obj.get("name")
                content_type = file_obj.get("contentType")
                file_url = file_obj.get("url")
                if file_url and not content_base64:
                    resp = await context.fetch(file_url, method="GET", raw_response=True)
                    content_base64 = base64.b64encode(resp.get("body", b"")).decode("utf-8")
            else:
                content_base64 = inputs.get("content")
                filename = inputs.get("filename")
                content_type = inputs.get("content_type")
            if not content_base64 or not filename:
                return ActionResult(data={"result": False, "error": "Missing required file content or filename"}, cost_usd=0.0)
            file_bytes = base64.b64decode(content_base64)
            if not content_type:
                guessed_type, _ = mimetypes.guess_type(filename)
                content_type = guessed_type or "application/octet-stream"
            response = await context.fetch(f"{INGEST_API_BASE}/{env}/upload", method="POST", headers=_get_headers(context))
            upload_data = response.get("data", {})
            attributes = upload_data.get("attributes", {})
            presigned_url = attributes.get("url")
            source_id = upload_data.get("id")
            upload_headers = attributes.get("headers", {})
            if not presigned_url:
                return ActionResult(data={"result": False, "error": "Failed to get presigned upload URL"}, cost_usd=0.0)
            put_headers = upload_headers if upload_headers else {}
            await context.fetch(presigned_url, method="PUT", data=file_bytes, headers=put_headers)
            if wait_for_ready:
                poll_result = await _poll_source(context, source_id)
                if poll_result["status"] == "ready":
                    return ActionResult(data={"source_id": source_id, "source_url": poll_result["source_url"], "status": "ready", "result": True}, cost_usd=0.0)
                return ActionResult(data={"source_id": source_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False}, cost_usd=0.0)
            return ActionResult(data={"source_id": source_id, "status": "processing", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("check_source_status")
class CheckSourceStatusAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            source_id = inputs["source_id"]
            response = await context.fetch(f"{INGEST_API_BASE}/{env}/sources/{source_id}", method="GET", headers=_get_headers(context))
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            response = await context.fetch(f"{INGEST_API_BASE}/{env}/upload", method="POST", headers=_get_headers(context))
            upload_data = response.get("data", {})
            attributes = upload_data.get("attributes", {})
            return ActionResult(data={"upload_url": attributes.get("url"), "source_id": upload_data.get("id"), "expires": attributes.get("expires"), "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"upload_url": None, "source_id": None, "result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("submit_render")
class SubmitRenderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            response = await context.fetch(f"{EDIT_API_BASE}/{env}/render", method="POST", headers=_get_headers(context), json=payload)
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            return ActionResult(data={"render_id": render_id, "status": "queued", "message": "Render job submitted. Use check_render_status to poll for completion.", "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("check_render_status")
class CheckRenderStatusAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            render_id = inputs["render_id"]
            response = await context.fetch(f"{EDIT_API_BASE}/{env}/render/{render_id}", method="GET", headers=_get_headers(context))
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            max_wait = inputs.get("max_wait_seconds", 300)
            poll_interval = inputs.get("poll_interval_seconds", 5)
            env = _get_env(context)
            response = await context.fetch(f"{EDIT_API_BASE}/{env}/render", method="POST", headers=_get_headers(context), json=payload)
            render_id = response.get("response", {}).get("id")
            if not render_id:
                return ActionResult(data={"result": False, "error": "Failed to submit render job"}, cost_usd=0.0)
            poll_result = await _poll_render(context, render_id, max_wait, poll_interval)
            if poll_result["status"] == "done":
                return ActionResult(data={"render_id": render_id, "status": "done", "url": poll_result["url"], "duration": poll_result.get("render", {}).get("duration"), "result": True}, cost_usd=0.0)
            return ActionResult(data={"render_id": render_id, "status": poll_result["status"], "error": poll_result.get("error"), "result": False}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("download_render")
class DownloadRenderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            env = _get_env(context)
            render_id = inputs.get("render_id")
            url = inputs.get("url")
            if render_id and not url:
                response = await context.fetch(f"{EDIT_API_BASE}/{env}/render/{render_id}", method="GET", headers=_get_headers(context))
                render_data = response.get("response", {})
                status = render_data.get("status")
                if status != "done":
                    return ActionResult(data={"result": False, "error": f"Render is not complete. Status: {status}"}, cost_usd=0.0)
                url = render_data.get("url")
            if not url:
                return ActionResult(data={"result": False, "error": "No URL available. Provide render_id or url."}, cost_usd=0.0)
            dl = await _download_base64(context, url)
            return ActionResult(data={"content": dl["content"], "content_type": dl["content_type"], "filename": dl["filename"], "size": dl["size"], "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("custom_edit")
class CustomEditAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            wait = inputs.get("wait_for_completion", True)
            max_wait = inputs.get("max_wait_seconds", 300)
            payload = {"timeline": inputs["timeline"], "output": inputs["output"]}
            return await _submit_and_maybe_wait(context, payload, wait, max_wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("compose_video")
class ComposeVideoAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            clips = inputs["clips"]
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            background_color = inputs.get("background_color", "#000000")
            wait = inputs.get("wait_for_completion", True)
            timeline = _build_timeline_from_clips(clips, background_color)
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_text_overlay")
class AddTextOverlayAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
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
            wait = inputs.get("wait_for_completion", True)
            if not duration:
                try:
                    media_info = await _get_media_info(context, video_url)
                    video_duration = media_info.get("metadata", {}).get("streams", [{}])[0].get("duration", 10)
                    duration = video_duration - start_time
                except Exception:
                    duration = 10
            title_asset: Dict[str, Any] = {"type": "title", "text": text, "style": style, "color": color, "size": font_size, "position": position}
            if background_color:
                title_asset["background"] = background_color
            text_clip: Dict[str, Any] = {"asset": title_asset, "start": start_time, "length": duration}
            if effect:
                text_clip["effect"] = effect
            if transition:
                text_clip["transition"] = transition
            timeline = {"tracks": [{"clips": [text_clip]}, {"clips": [{"asset": {"type": "video", "src": video_url}, "start": 0}]}]}
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_logo_overlay")
class AddLogoOverlayAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
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
            wait = inputs.get("wait_for_completion", True)
            if not duration:
                try:
                    media_info = await _get_media_info(context, video_url)
                    video_duration = media_info.get("metadata", {}).get("streams", [{}])[0].get("duration", 10)
                    duration = video_duration - start_time
                except Exception:
                    duration = 10
            logo_clip: Dict[str, Any] = {"asset": {"type": "image", "src": logo_url}, "start": start_time, "length": duration, "scale": scale, "position": position, "opacity": opacity}
            if offset_x is not None or offset_y is not None:
                offset = _position_to_offset(position)
                if offset_x is not None:
                    offset["x"] = offset_x
                if offset_y is not None:
                    offset["y"] = offset_y
                logo_clip["offset"] = offset
            timeline = {"tracks": [{"clips": [logo_clip]}, {"clips": [{"asset": {"type": "video", "src": video_url}, "start": 0}]}]}
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_audio_track")
class AddAudioTrackAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
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
            wait = inputs.get("wait_for_completion", True)
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
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("trim_video")
class TrimVideoAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            video_url = inputs["video_url"]
            start_time = inputs["start_time"]
            end_time = inputs.get("end_time")
            duration = inputs.get("duration")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait = inputs.get("wait_for_completion", True)
            if end_time is not None:
                length = end_time - start_time
            elif duration is not None:
                length = duration
            else:
                return ActionResult(data={"result": False, "error": "Either end_time or duration is required"}, cost_usd=0.0)
            timeline = {"tracks": [{"clips": [{"asset": {"type": "video", "src": video_url, "trim": start_time}, "start": 0, "length": length}]}]}
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("concatenate_videos")
class ConcatenateVideosAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            videos = inputs["videos"]
            transition = inputs.get("transition")
            output = inputs.get("output", {"format": "mp4", "resolution": "hd"})
            wait = inputs.get("wait_for_completion", True)
            clips = []
            for i, video_url in enumerate(videos):
                clip: Dict[str, Any] = {"asset": {"type": "video", "src": video_url}, "start": 0}
                if transition and transition != "none":
                    trans = {}
                    if i > 0:
                        trans["in"] = transition
                    if i < len(videos) - 1:
                        trans["out"] = transition
                    if trans:
                        clip["transition"] = trans
                clips.append(clip)
            timeline = {"tracks": [{"clips": clips}]}
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@shotstack.action("add_captions")
class AddCaptionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
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
            wait = inputs.get("wait_for_completion", True)
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
                bg: Dict[str, Any] = {"color": background_color}
                if background_opacity is not None:
                    bg["opacity"] = background_opacity
                if background_padding is not None:
                    bg["padding"] = background_padding
                if background_border_radius is not None:
                    bg["borderRadius"] = background_border_radius
                caption_asset["background"] = bg
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
            return await _submit_and_maybe_wait(context, {"timeline": timeline, "output": output}, wait, max_wait)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
