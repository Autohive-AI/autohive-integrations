import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))

# The 'supadata/' integration folder has an __init__.py that shadows the 'supadata'
# PyPI package. Pre-load the real package from site-packages before exec_module runs,
# so sys.modules['supadata'] already refers to the installed library.
import site  # noqa: E402

for _site_dir in site.getsitepackages():
    _real_supadata = os.path.join(_site_dir, "supadata")
    if os.path.isdir(_real_supadata) and os.path.abspath(_real_supadata) != _parent:
        _supadata_spec = importlib.util.spec_from_file_location(
            "supadata",
            os.path.join(_real_supadata, "__init__.py"),
            submodule_search_locations=[_real_supadata],
        )
        _supadata_mod = importlib.util.module_from_spec(_supadata_spec)
        sys.modules["supadata"] = _supadata_mod
        _supadata_spec.loader.exec_module(_supadata_mod)
        break

if _deps not in sys.path:
    sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("supadata_transcribe", os.path.join(_parent, "supadata_transcribe.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["supadata_transcribe"] = _mod
_spec.loader.exec_module(_mod)

supadata_transcribe = _mod.supadata_transcribe

pytestmark = pytest.mark.unit

# ---- Sample Data ----

SAMPLE_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def make_chunk(text, offset, duration):
    chunk = MagicMock()
    chunk.text = text
    chunk.offset = offset
    chunk.duration = duration
    return chunk


def make_transcript_response(content, lang="en", available_langs=None):
    resp = MagicMock()
    resp.content = content
    resp.lang = lang
    resp.available_langs = available_langs or ["en"]
    return resp


# ---- Fixtures ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    # custom auth: flat object matching config.json fields
    ctx.auth = {
        "credentials": {
            "api_key": "test_api_key",  # nosec B105
        }
    }
    return ctx


# ---- Tests ----


class TestGetTranscript:
    @pytest.mark.asyncio
    async def test_happy_path_with_chunks(self, mock_context):
        chunks = [
            make_chunk("Hello world", 0, 2000),
            make_chunk("This is a test", 2000, 3000),
        ]
        transcript_resp = make_transcript_response(chunks, lang="en", available_langs=["en", "fr"])

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert result.type == ResultType.ACTION
        assert "transcript" in result.result.data
        assert result.result.data["language"] == "en"
        assert "en" in result.result.data["available_languages"]
        assert "fr" in result.result.data["available_languages"]

    @pytest.mark.asyncio
    async def test_transcript_text_format(self, mock_context):
        chunks = [make_chunk("Hello", 0, 1000)]
        transcript_resp = make_transcript_response(chunks)

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        transcript = result.result.data["transcript"]
        assert "00:00:00,000 --> 00:00:01,000" in transcript
        assert "Hello" in transcript

    @pytest.mark.asyncio
    async def test_api_key_passed_to_sdk(self, mock_context):
        transcript_resp = make_transcript_response("plain text transcript")

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            await supadata_transcribe.execute_action("get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context)

            MockSupadata.assert_called_once_with(api_key="test_api_key")  # nosec B105  # noqa: S106

    @pytest.mark.asyncio
    async def test_sdk_called_with_correct_params(self, mock_context):
        transcript_resp = make_transcript_response("text")

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            await supadata_transcribe.execute_action("get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context)

            MockSupadata.return_value.transcript.assert_called_once_with(
                url=SAMPLE_VIDEO_URL,
                text=False,
                mode="auto",
            )

    @pytest.mark.asyncio
    async def test_supadata_error_returns_action_error(self, mock_context):
        from supadata import SupadataError

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.side_effect = SupadataError(
                error="not_found",
                message="Video not found",
                details="The video could not be found",
            )

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Supadata API error" in result.result.message
        assert "Video not found" in result.result.message

    @pytest.mark.asyncio
    async def test_generic_exception_returns_action_error(self, mock_context):
        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.side_effect = Exception("Connection refused")

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Error getting transcript" in result.result.message
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_string_content_returned_as_is(self, mock_context):
        transcript_resp = make_transcript_response("Plain text transcript content")

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert result.result.data["transcript"] == "Plain text transcript content"

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_string(self, mock_context):
        transcript_resp = make_transcript_response([])

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert result.result.data["transcript"] == ""

    @pytest.mark.asyncio
    async def test_invalid_chunk_format_returns_error_string(self, mock_context):
        transcript_resp = make_transcript_response({"not": "a list or string"})

        with patch("supadata_transcribe.Supadata") as MockSupadata:
            MockSupadata.return_value.transcript.return_value = transcript_resp

            result = await supadata_transcribe.execute_action(
                "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
            )

        assert "invalid format" in result.result.data["transcript"]

    @pytest.mark.asyncio
    async def test_missing_video_url_returns_validation_error(self, mock_context):
        result = await supadata_transcribe.execute_action("get_transcript", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR


class TestMsToTimestamp:
    """Tests for the _ms_to_timestamp helper method."""

    def _get_handler(self):
        # Instantiate the handler class directly
        handler_cls = _mod.GetTranscriptAction
        return handler_cls.__new__(handler_cls)

    def test_zero_ms(self):
        handler = self._get_handler()
        assert handler._ms_to_timestamp(0) == "00:00:00,000"

    def test_one_second(self):
        handler = self._get_handler()
        assert handler._ms_to_timestamp(1000) == "00:00:01,000"

    def test_one_minute(self):
        handler = self._get_handler()
        assert handler._ms_to_timestamp(60000) == "00:01:00,000"

    def test_one_hour(self):
        handler = self._get_handler()
        assert handler._ms_to_timestamp(3600000) == "01:00:00,000"

    def test_complex_timestamp(self):
        handler = self._get_handler()
        # 1h 23m 45s 678ms
        ms = (1 * 3600000) + (23 * 60000) + (45 * 1000) + 678
        assert handler._ms_to_timestamp(ms) == "01:23:45,678"
