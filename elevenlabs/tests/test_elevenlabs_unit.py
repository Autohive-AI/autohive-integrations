import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402
from elevenlabs.elevenlabs import elevenlabs  # noqa: E402

pytestmark = pytest.mark.unit

API_BASE = "https://api.elevenlabs.io/v1"
TEST_AUTH = {"credentials": {"api_key": "test_key"}}  # nosec B105


@pytest.fixture
def ctx(make_context):
    return make_context(auth=TEST_AUTH)


def _aiohttp_session_mock(*, status: int, body: bytes = b"", text: str = ""):
    """Build a MagicMock that mimics aiohttp.ClientSession() as an async context manager.

    The integration uses:
        async with aiohttp.ClientSession() as session:
            async with session.get(...) as resp:
                resp.status; await resp.read(); await resp.text()
    """
    resp = MagicMock()
    resp.status = status
    resp.read = AsyncMock(return_value=body)
    resp.text = AsyncMock(return_value=text)

    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=resp)
    request_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=request_cm)
    session.post = MagicMock(return_value=request_cm)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    session_cls = MagicMock(return_value=session_cm)
    return session_cls, session, resp


# ---- list_voices ----


class TestListVoices:
    async def test_returns_voices(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"voices": [{"voice_id": "v1", "name": "Alice"}]},
        )

        result = await elevenlabs.execute_action("list_voices", {}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["voices"] == [{"voice_id": "v1", "name": "Alice"}]
        ctx.fetch.assert_called_once()
        call = ctx.fetch.call_args
        assert call.args[0] == f"{API_BASE}/voices"
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] is None

    async def test_passes_filter_params(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"voices": []})
        inputs = {"page_size": 50, "category": "premade", "search": "narrator"}

        await elevenlabs.execute_action("list_voices", inputs, ctx)

        params = ctx.fetch.call_args.kwargs["params"]
        assert params == {"page_size": 50, "category": "premade", "search": "narrator"}

    async def test_missing_voices_key(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await elevenlabs.execute_action("list_voices", {}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["voices"] == []

    async def test_fetch_error(self, ctx):
        ctx.fetch.side_effect = Exception("Network down")

        result = await elevenlabs.execute_action("list_voices", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network down" in result.result.message


# ---- get_voice ----


class TestGetVoice:
    async def test_returns_voice(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"voice_id": "v1", "name": "Alice", "category": "premade"},
        )
        inputs = {"voice_id": "v1"}

        result = await elevenlabs.execute_action("get_voice", inputs, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["voice"]["voice_id"] == "v1"
        assert ctx.fetch.call_args.args[0] == f"{API_BASE}/voices/v1"

    async def test_with_settings_param(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"voice_id": "v1"})
        inputs = {"voice_id": "v1", "with_settings": True}

        await elevenlabs.execute_action("get_voice", inputs, ctx)

        params = ctx.fetch.call_args.kwargs["params"]
        assert params == {"with_settings": "true"}

    async def test_error(self, ctx):
        ctx.fetch.side_effect = Exception("404 Not Found")

        result = await elevenlabs.execute_action("get_voice", {"voice_id": "missing"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


# ---- get_voice_settings ----


class TestGetVoiceSettings:
    async def test_returns_settings(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        )

        result = await elevenlabs.execute_action("get_voice_settings", {"voice_id": "v1"}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["settings"]["stability"] == 0.5
        assert ctx.fetch.call_args.args[0] == f"{API_BASE}/voices/v1/settings"

    async def test_error(self, ctx):
        ctx.fetch.side_effect = Exception("Unauthorized")

        result = await elevenlabs.execute_action("get_voice_settings", {"voice_id": "v1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


# ---- list_history ----


class TestListHistory:
    async def test_returns_history(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"history": [{"history_item_id": "h1", "text": "hello"}]},
        )

        result = await elevenlabs.execute_action("list_history", {}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["history"]) == 1
        assert result.result.data["history"][0]["history_item_id"] == "h1"

    async def test_passes_filter_params(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"history": []})
        inputs = {"page_size": 25, "voice_id": "v1"}

        await elevenlabs.execute_action("list_history", inputs, ctx)

        params = ctx.fetch.call_args.kwargs["params"]
        assert params == {"page_size": 25, "voice_id": "v1"}

    async def test_missing_history_key(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await elevenlabs.execute_action("list_history", {}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["history"] == []

    async def test_error(self, ctx):
        ctx.fetch.side_effect = Exception("Timeout")

        result = await elevenlabs.execute_action("list_history", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message


# ---- get_user_subscription ----


class TestGetUserSubscription:
    async def test_returns_subscription(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"tier": "free", "character_count": 100, "character_limit": 10000},
        )

        result = await elevenlabs.execute_action("get_user_subscription", {}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["subscription"]["tier"] == "free"
        assert ctx.fetch.call_args.args[0] == f"{API_BASE}/user/subscription"

    async def test_error(self, ctx):
        ctx.fetch.side_effect = Exception("Forbidden")

        result = await elevenlabs.execute_action("get_user_subscription", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- download_history_audio (uses aiohttp directly) ----


class TestDownloadHistoryAudio:
    async def test_returns_base64_file(self, ctx):
        audio_bytes = b"FAKE_AUDIO_DATA"
        session_cls, _session, _resp = _aiohttp_session_mock(status=200, body=audio_bytes)

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("download_history_audio", {"history_item_id": "h1"}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        file_obj = result.result.data["file"]
        assert file_obj["name"] == "downloaded_audio.mp3"
        assert file_obj["contentType"] == "audio/mpeg"
        assert file_obj["content"] == base64.b64encode(audio_bytes).decode("utf-8")

    async def test_http_error(self, ctx):
        session_cls, _session, _resp = _aiohttp_session_mock(status=404, text="not found")

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("download_history_audio", {"history_item_id": "missing"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message
        assert "not found" in result.result.message

    async def test_exception(self, ctx):
        with patch(
            "elevenlabs.elevenlabs.aiohttp.ClientSession",
            side_effect=Exception("connection refused"),
        ):
            result = await elevenlabs.execute_action("download_history_audio", {"history_item_id": "h1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "connection refused" in result.result.message


# ---- speech_to_text_convert ----


class TestSpeechToTextConvert:
    def _make_session_mock(
        self,
        *,
        file_status=200,
        file_body=b"AUDIO",
        file_content_type="audio/mpeg",
        post_status=200,
        post_json=None,
        post_text="",
    ):
        """Build a mock aiohttp session that handles GET (file download) then POST (transcribe)."""
        if post_json is None:
            post_json = {
                "transcription_id": "tid1",
                "text": "hello",
                "language_code": "en",
                "language_probability": 0.99,
                "words": [],
            }

        file_resp = MagicMock()
        file_resp.status = file_status
        file_resp.read = AsyncMock(return_value=file_body)
        file_resp.headers = {"Content-Type": file_content_type}

        file_cm = MagicMock()
        file_cm.__aenter__ = AsyncMock(return_value=file_resp)
        file_cm.__aexit__ = AsyncMock(return_value=False)

        post_resp = MagicMock()
        post_resp.status = post_status
        post_resp.json = AsyncMock(return_value=post_json)
        post_resp.text = AsyncMock(return_value=post_text)

        post_cm = MagicMock()
        post_cm.__aenter__ = AsyncMock(return_value=post_resp)
        post_cm.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=file_cm)
        session.post = MagicMock(return_value=post_cm)

        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        return MagicMock(return_value=session_cm), session

    async def test_returns_transcript(self, ctx):
        session_cls, session = self._make_session_mock()
        inputs = {"file_url": "https://example.com/audio.mp3"}

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("speech_to_text_convert", inputs, ctx)

        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["transcription_id"] == "tid1"
        assert data["text"] == "hello"
        assert data["language_code"] == "en"

    async def test_file_download_failure(self, ctx):
        session_cls, _ = self._make_session_mock(file_status=403)
        inputs = {"file_url": "https://example.com/secret.mp3"}

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("speech_to_text_convert", inputs, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to download file" in result.result.message

    async def test_api_error(self, ctx):
        session_cls, _ = self._make_session_mock(post_status=422, post_text="invalid model")
        inputs = {"file_url": "https://example.com/audio.mp3"}

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("speech_to_text_convert", inputs, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 422" in result.result.message

    async def test_exception(self, ctx):
        with patch(
            "elevenlabs.elevenlabs.aiohttp.ClientSession",
            side_effect=Exception("DNS error"),
        ):
            result = await elevenlabs.execute_action("speech_to_text_convert", {"file_url": "https://x.com/a.mp3"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "DNS error" in result.result.message


# ---- speech_to_text_get ----


class TestSpeechToTextGet:
    async def test_returns_transcript(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "transcription_id": "tid1",
                "text": "hello",
                "language_code": "en",
                "language_probability": 0.99,
                "words": [],
            },
        )

        result = await elevenlabs.execute_action("speech_to_text_get", {"transcription_id": "tid1"}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["transcription_id"] == "tid1"
        assert data["text"] == "hello"
        assert ctx.fetch.call_args.args[0] == f"{API_BASE}/speech-to-text/transcripts/tid1"
        assert ctx.fetch.call_args.kwargs["method"] == "GET"

    async def test_not_found(self, ctx):
        ctx.fetch.side_effect = Exception("404 Not Found")

        result = await elevenlabs.execute_action("speech_to_text_get", {"transcription_id": "missing"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message

    async def test_auth_error(self, ctx):
        ctx.fetch.side_effect = Exception("Unauthorized")

        result = await elevenlabs.execute_action("speech_to_text_get", {"transcription_id": "tid1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


# ---- speech_to_text_delete ----


class TestSpeechToTextDelete:
    async def test_deletes_transcript(self, ctx):
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await elevenlabs.execute_action("speech_to_text_delete", {"transcription_id": "tid1"}, ctx)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["result"] is True
        assert ctx.fetch.call_args.args[0] == f"{API_BASE}/speech-to-text/transcripts/tid1"
        assert ctx.fetch.call_args.kwargs["method"] == "DELETE"

    async def test_not_found(self, ctx):
        ctx.fetch.side_effect = Exception("404 Not Found")

        result = await elevenlabs.execute_action("speech_to_text_delete", {"transcription_id": "missing"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message

    async def test_exception(self, ctx):
        ctx.fetch.side_effect = Exception("Network error")

        result = await elevenlabs.execute_action("speech_to_text_delete", {"transcription_id": "tid1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- text_to_speech (uses aiohttp directly) ----


class TestTextToSpeech:
    async def test_generates_audio(self, ctx):
        audio_bytes = b"GENERATED_MP3"
        session_cls, session, _resp = _aiohttp_session_mock(status=200, body=audio_bytes)

        inputs = {"voice_id": "v1", "text": "hello world"}
        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("text_to_speech", inputs, ctx)

        assert result.type != ResultType.ACTION_ERROR
        file_obj = result.result.data["file"]
        assert file_obj["name"] == "generated_audio.mp3"
        assert file_obj["contentType"] == "audio/mpeg"
        assert file_obj["content"] == base64.b64encode(audio_bytes).decode("utf-8")

        post_url = session.post.call_args.args[0]
        post_body = session.post.call_args.kwargs["json"]
        assert post_url == f"{API_BASE}/text-to-speech/v1"
        assert post_body == {"text": "hello world"}

    async def test_appends_output_format_query(self, ctx):
        session_cls, session, _resp = _aiohttp_session_mock(status=200, body=b"x")
        inputs = {
            "voice_id": "v1",
            "text": "hi",
            "output_format": "mp3_44100_128",
            "model_id": "eleven_turbo_v2_5",
        }

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            await elevenlabs.execute_action("text_to_speech", inputs, ctx)

        post_url = session.post.call_args.args[0]
        post_body = session.post.call_args.kwargs["json"]
        assert post_url == f"{API_BASE}/text-to-speech/v1?output_format=mp3_44100_128"
        assert post_body == {"text": "hi", "model_id": "eleven_turbo_v2_5"}

    async def test_passes_voice_settings(self, ctx):
        session_cls, session, _resp = _aiohttp_session_mock(status=200, body=b"x")
        voice_settings = {"stability": 0.4, "similarity_boost": 0.8}
        inputs = {"voice_id": "v1", "text": "hi", "voice_settings": voice_settings}

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            await elevenlabs.execute_action("text_to_speech", inputs, ctx)

        post_body = session.post.call_args.kwargs["json"]
        assert post_body["voice_settings"] == voice_settings

    async def test_http_error(self, ctx):
        session_cls, _session, _resp = _aiohttp_session_mock(status=401, text="invalid api key")

        with patch("elevenlabs.elevenlabs.aiohttp.ClientSession", session_cls):
            result = await elevenlabs.execute_action("text_to_speech", {"voice_id": "v1", "text": "hi"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 401" in result.result.message
        assert "invalid api key" in result.result.message

    async def test_exception(self, ctx):
        with patch(
            "elevenlabs.elevenlabs.aiohttp.ClientSession",
            side_effect=Exception("DNS error"),
        ):
            result = await elevenlabs.execute_action("text_to_speech", {"voice_id": "v1", "text": "hi"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "DNS error" in result.result.message
