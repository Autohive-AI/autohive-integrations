"""Unit tests for the Supadata integration.

Mocked end-to-end: every test patches `supadata_transcribe.Supadata` so no
real HTTP traffic is generated, and uses the `mock_context` fixture from
the local conftest (pre-populated with a fake API key).
"""

from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk.integration import ResultType
from supadata import SupadataError

from supadata_transcribe import GetTranscriptAction, supadata_transcribe

pytestmark = pytest.mark.unit


# ---- Sample Data ----

SAMPLE_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def make_chunk(text: str, offset: int, duration: int) -> MagicMock:
    chunk = MagicMock()
    chunk.text = text
    chunk.offset = offset
    chunk.duration = duration
    return chunk


def make_transcript_response(content, lang: str = "en", available_langs=None) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.lang = lang
    resp.available_langs = available_langs or ["en"]
    return resp


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

            MockSupadata.assert_called_once_with(api_key="test_api_key")  # nosec B106

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

    def _get_handler(self) -> GetTranscriptAction:
        return GetTranscriptAction.__new__(GetTranscriptAction)

    def test_zero_ms(self):
        assert self._get_handler()._ms_to_timestamp(0) == "00:00:00,000"

    def test_one_second(self):
        assert self._get_handler()._ms_to_timestamp(1000) == "00:00:01,000"

    def test_one_minute(self):
        assert self._get_handler()._ms_to_timestamp(60000) == "00:01:00,000"

    def test_one_hour(self):
        assert self._get_handler()._ms_to_timestamp(3600000) == "01:00:00,000"

    def test_complex_timestamp(self):
        # 1h 23m 45s 678ms
        ms = (1 * 3600000) + (23 * 60000) + (45 * 1000) + 678
        assert self._get_handler()._ms_to_timestamp(ms) == "01:23:45,678"
