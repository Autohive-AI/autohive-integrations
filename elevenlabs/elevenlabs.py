from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
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

    return {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }


# ---- Action Handlers ----

@elevenlabs.action("list_voices")
class ListVoicesAction(ActionHandler):
    """List all available voices. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'page_size' in inputs and inputs['page_size']:
                params['page_size'] = inputs['page_size']
            if 'category' in inputs and inputs['category']:
                params['category'] = inputs['category']
            if 'use_cases' in inputs and inputs['use_cases']:
                params['use_cases'] = inputs['use_cases']
            if 'search' in inputs and inputs['search']:
                params['search'] = inputs['search']

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices",
                method="GET",
                headers=headers,
                params=params if params else None
            )

            voices = response.get('voices', [])
            return {"voices": voices, "result": True}

        except Exception as e:
            return {"voices": [], "result": False, "error": str(e)}


@elevenlabs.action("get_voice")
class GetVoiceAction(ActionHandler):
    """Get details of a specific voice. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs['voice_id']

            params = {}
            if 'with_settings' in inputs and inputs['with_settings']:
                params['with_settings'] = str(inputs['with_settings']).lower()

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices/{voice_id}",
                method="GET",
                headers=headers,
                params=params if params else None
            )

            return {"voice": response, "result": True}

        except Exception as e:
            return {"voice": {}, "result": False, "error": str(e)}


@elevenlabs.action("get_voice_settings")
class GetVoiceSettingsAction(ActionHandler):
    """Get voice settings for a specific voice. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs['voice_id']

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/voices/{voice_id}/settings",
                method="GET",
                headers=headers
            )

            return {"settings": response, "result": True}

        except Exception as e:
            return {"settings": {}, "result": False, "error": str(e)}


@elevenlabs.action("list_history")
class ListHistoryAction(ActionHandler):
    """List generation history. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'page_size' in inputs and inputs['page_size']:
                params['page_size'] = inputs['page_size']
            if 'voice_id' in inputs and inputs['voice_id']:
                params['voice_id'] = inputs['voice_id']

            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/history",
                method="GET",
                headers=headers,
                params=params if params else None
            )

            history = response.get('history', [])
            return {"history": history, "result": True}

        except Exception as e:
            return {"history": [], "result": False, "error": str(e)}


@elevenlabs.action("download_history_audio")
class DownloadHistoryAudioAction(ActionHandler):
    """Download audio from history item. FREE - no new credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            history_item_id = inputs['history_item_id']

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
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                        return {
                            "file": {
                                "content": audio_base64,
                                "name": "downloaded_audio.mp3",
                                "contentType": "audio/mpeg"
                            },
                            "result": True
                        }
                    else:
                        error_text = await resp.text()
                        return {"audio": {}, "result": False, "error": f"HTTP {resp.status}: {error_text}"}

        except Exception as e:
            return {"audio": {}, "result": False, "error": str(e)}


@elevenlabs.action("get_user_subscription")
class GetUserSubscriptionAction(ActionHandler):
    """Get user subscription info. FREE - no credits used."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)

            response = await context.fetch(
                f"{ELEVENLABS_API_BASE_URL}/user/subscription",
                method="GET",
                headers=headers
            )

            return {"subscription": response, "result": True}

        except Exception as e:
            return {"subscription": {}, "result": False, "error": str(e)}


@elevenlabs.action("text_to_speech")
class TextToSpeechAction(ActionHandler):
    """Convert text to speech. COSTS CREDITS: 1 per character (standard) or 0.5 (Turbo)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            voice_id = inputs['voice_id']
            text = inputs['text']

            credentials = context.auth.get("credentials", {})
            api_key = credentials.get("api_key", "")

            # Build request body
            body = {"text": text}

            if 'model_id' in inputs and inputs['model_id']:
                body['model_id'] = inputs['model_id']
            if 'voice_settings' in inputs and inputs['voice_settings']:
                body['voice_settings'] = inputs['voice_settings']

            # Build URL with optional output_format
            url = f"{ELEVENLABS_API_BASE_URL}/text-to-speech/{voice_id}"
            if 'output_format' in inputs and inputs['output_format']:
                url += f"?output_format={inputs['output_format']}"

            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

            # Generate audio using aiohttp to handle binary response
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as resp:
                    if resp.status == 200:
                        audio_bytes = await resp.read()
                        # Encode as base64 following Autohive pattern (see Slider integration)
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                        return {
                            "file": {
                                "content": audio_base64,
                                "name": "generated_audio.mp3",
                                "contentType": "audio/mpeg"
                            },
                            "result": True
                        }
                    else:
                        error_text = await resp.text()
                        return {"audio": {}, "result": False, "error": f"HTTP {resp.status}: {error_text}"}

        except Exception as e:
            return {"audio": {}, "result": False, "error": str(e)}
