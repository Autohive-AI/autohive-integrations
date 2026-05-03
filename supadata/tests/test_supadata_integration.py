"""Integration tests for the Supadata integration.

Requires SUPADATA_API_KEY in the environment (the repo-root conftest auto-loads
the project `.env`). Live tests are skipped when the key is missing.

Run with:
    pytest supadata/tests/test_supadata_integration.py -m integration
"""

from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk.integration import ResultType

from supadata_transcribe import supadata_transcribe

pytestmark = pytest.mark.integration


SAMPLE_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def live_context(env_credentials, make_context):
    """ExecutionContext wired to the real Supadata API key."""
    api_key = env_credentials("SUPADATA_API_KEY")
    if not api_key:
        pytest.skip("SUPADATA_API_KEY not set — skipping live integration tests")
    return make_context(auth={"credentials": {"api_key": api_key}})


@pytest.mark.asyncio
async def test_get_transcript_live(live_context):
    """Calls the real Supadata API end-to-end and asserts on the response shape."""
    result = await supadata_transcribe.execute_action("get_transcript", {"video_url": SAMPLE_VIDEO_URL}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "transcript" in data
    assert "language" in data
    assert "available_languages" in data


@pytest.mark.asyncio
async def test_get_transcript_mocked(mock_context):
    """Sanity check that mirrors the live test path with a mocked Supadata client."""
    chunk = MagicMock()
    chunk.text = "Hello world"
    chunk.offset = 0
    chunk.duration = 2000

    transcript_resp = MagicMock()
    transcript_resp.content = [chunk]
    transcript_resp.lang = "en"
    transcript_resp.available_langs = ["en"]

    with patch("supadata_transcribe.Supadata") as MockSupadata:
        MockSupadata.return_value.transcript.return_value = transcript_resp

        result = await supadata_transcribe.execute_action(
            "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
        )

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "transcript" in data
    assert data["language"] == "en"
