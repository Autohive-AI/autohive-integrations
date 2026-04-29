from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any
import base64
import aiohttp

# Create the integration using the config.json
elevenlabs = Integration.load()

# Base URL for ElevenLabs API
ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io/v1"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for ElevenLabs API requests.
    ElevenLabs uses a custom header 'xi-api-key' for authentication.

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with xi-api-key header
    """
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")

    return {"xi-api-key": api_key, "Content-Type": "application/json"}


# ---- Action Handlers ----


@elevenlabs.action("list_voices")
class ListVoicesAction(ActionHandler):
    """List all available voices. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("page_size"):
                params["page_size"] = inputs["page_size"]
            if inputs.get("category"):
                params["category"] = inputs["category"]
            if inputs.get("use_cases"):
                params["use_cases"] = inputs["use_cases"]
            if inputs.get("search"):
                params["search"] = inputs["search"]

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices",
                method="GET",
                headers=headers,
                params=params if params else None,
            )

            voices = response.data.get("voices", [])
            return ActionResult(data={"voices": voices}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("get_voice")
class GetVoiceAction(ActionHandler):
    """Get details of a specific voice. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs["voice_id"]

            params = {}
            if inputs.get("with_settings"):
                params["with_settings"] = str(inputs["with_settings"]).lower()

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices/{voice_id}",
                method="GET",
                headers=headers,
                params=params if params else None,
            )

            return ActionResult(data={"voice": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("get_voice_settings")
class GetVoiceSettingsAction(ActionHandler):
    """Get voice settings for a specific voice. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs["voice_id"]

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices/{voice_id}/settings",
                method="GET",
                headers=headers,
            )

            return ActionResult(data={"settings": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("list_history")
class ListHistoryAction(ActionHandler):
    """List generation history. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("page_size"):
                params["page_size"] = inputs["page_size"]
            if inputs.get("voice_id"):
                params["voice_id"] = inputs["voice_id"]

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/history",
                method="GET",
                headers=headers,
                params=params if params else None,
            )

            history = response.data.get("history", [])
            return ActionResult(data={"history": history}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("download_history_audio")
class DownloadHistoryAudioAction(ActionHandler):
    """Download audio from history item. FREE - no new credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            history_item_id = inputs["history_item_id"]

            credentials = context.auth.get("credentials", {})
            api_key = credentials.get("api_key", "")

            # Download binary audio using aiohttp
            url = f"{ELEVENLABS_API_BASE_URL}/history/{history_item_id}/audio"
            headers = {"xi-api-key": api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        audio_bytes = await resp.read()
                        # Encode as base64 following Autohive pattern (see Slider integration)
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

                        return ActionResult(
                            data={
                                "file": {
                                    "content": audio_base64,
                                    "name": "downloaded_audio.mp3",
                                    "contentType": "audio/mpeg",
                                },
                            },
                            cost_usd=0.0,
                        )
                    else:
                        error_text = await resp.text()
                        return ActionError(message=f"HTTP {resp.status}: {error_text}")

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("get_user_subscription")
class GetUserSubscriptionAction(ActionHandler):
    """Get user subscription info. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/user/subscription",
                method="GET",
                headers=headers,
            )

            return ActionResult(data={"subscription": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("speech_to_text_convert")
class SpeechToTextConvertAction(ActionHandler):
    """Transcribe audio/video file using ElevenLabs Scribe."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            file_url = inputs["file_url"]
            model_id = inputs.get("model_id", "scribe_v1")

            credentials = context.auth.get("credentials", {})
            api_key = credentials.get("api_key", "")

            # Pass the URL directly to ElevenLabs — they fetch the file on their end
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("model_id", model_id)
                form.add_field("file_url", file_url)
                if inputs.get("language_code"):
                    form.add_field("language_code", inputs["language_code"])
                if inputs.get("timestamps_granularity"):
                    form.add_field("timestamps_granularity", inputs["timestamps_granularity"])
                if inputs.get("diarize") is not None:
                    form.add_field("diarize", str(inputs["diarize"]).lower())

                async with session.post(
                    f"{ELEVENLABS_API_BASE_URL}/speech-to-text",
                    headers={"xi-api-key": api_key},
                    data=form,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return ActionResult(data=data, cost_usd=0.0)
                    else:
                        error_text = await resp.text()
                        return ActionError(message=f"HTTP {resp.status}: {error_text}")

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("speech_to_text_get")
class SpeechToTextGetAction(ActionHandler):
    """Retrieve a transcript by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            transcription_id = inputs["transcription_id"]
            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/speech-to-text/transcripts/{transcription_id}",
                method="GET",
                headers=headers,
            )

            return ActionResult(data=response.data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("speech_to_text_delete")
class SpeechToTextDeleteAction(ActionHandler):
    """Delete a transcript by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            transcription_id = inputs["transcription_id"]
            headers = get_auth_headers(context)

            await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/speech-to-text/transcripts/{transcription_id}",
                method="DELETE",
                headers=headers,
            )

            return ActionResult(data={"result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@elevenlabs.action("text_to_speech")
class TextToSpeechAction(ActionHandler):
    """Convert text to speech. COSTS CREDITS: 1 per character (standard) or 0.5 (Turbo)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs["voice_id"]
            text = inputs["text"]

            credentials = context.auth.get("credentials", {})
            api_key = credentials.get("api_key", "")

            # Build request body
            body = {"text": text}

            if inputs.get("model_id"):
                body["model_id"] = inputs["model_id"]
            if inputs.get("voice_settings"):
                body["voice_settings"] = inputs["voice_settings"]

            # Build URL with optional output_format
            url = f"{ELEVENLABS_API_BASE_URL}/text-to-speech/{voice_id}"
            if inputs.get("output_format"):
                url += f"?output_format={inputs['output_format']}"

            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

            # Generate audio using aiohttp to handle binary response
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as resp:
                    if resp.status == 200:
                        audio_bytes = await resp.read()
                        # Encode as base64 following Autohive pattern (see Slider integration)
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

                        return ActionResult(
                            data={
                                "file": {
                                    "content": audio_base64,
                                    "name": "generated_audio.mp3",
                                    "contentType": "audio/mpeg",
                                },
                            },
                            cost_usd=0.0,
                        )
                    else:
                        error_text = await resp.text()
                        return ActionError(message=f"HTTP {resp.status}: {error_text}")

        except Exception as e:
            return ActionError(message=str(e))
