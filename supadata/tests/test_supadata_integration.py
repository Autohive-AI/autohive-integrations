"""
Integration tests for the Supadata integration.

Requires SUPADATA_API_KEY set in environment or .env file.

Run with:
    pytest supadata/tests/test_supadata_integration.py -m integration
"""

import importlib
import importlib.util
import os
import site
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Pre-load the real `supadata` SDK to avoid shadowing by the integration folder __init__.py
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

_spec = importlib.util.spec_from_file_location("supadata_transcribe", os.path.join(_parent, "supadata_transcribe.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["supadata_transcribe"] = _mod
_spec.loader.exec_module(_mod)

supadata_transcribe = _mod.supadata_transcribe

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")

SAMPLE_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def live_context():
    if not SUPADATA_API_KEY:
        pytest.skip("SUPADATA_API_KEY not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": SUPADATA_API_KEY}}  # nosec B105
    return ctx


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test_key"}}  # nosec B105
    return ctx


@pytest.mark.asyncio
@pytest.mark.skipif(not SUPADATA_API_KEY, reason="SUPADATA_API_KEY env var not set")
async def test_get_transcript_live(live_context):
    """Integration test: calls the real Supadata API to get a transcript."""
    result = await supadata_transcribe.execute_action("get_transcript", {"video_url": SAMPLE_VIDEO_URL}, live_context)
    assert result is not None
    data = result.result.data
    assert "transcript" in data
    assert "language" in data
    assert "available_languages" in data


@pytest.mark.asyncio
async def test_get_transcript_mocked(mock_context):
    """Integration-style test with mocked Supadata SDK."""

    def make_chunk(text, offset, duration):
        chunk = MagicMock()
        chunk.text = text
        chunk.offset = offset
        chunk.duration = duration
        return chunk

    transcript_resp = MagicMock()
    transcript_resp.content = [make_chunk("Hello world", 0, 2000)]
    transcript_resp.lang = "en"
    transcript_resp.available_langs = ["en"]

    with patch("supadata_transcribe.Supadata") as MockSupadata:
        MockSupadata.return_value.transcript.return_value = transcript_resp

        result = await supadata_transcribe.execute_action(
            "get_transcript", {"video_url": SAMPLE_VIDEO_URL}, mock_context
        )

    assert result is not None
    data = result.result.data
    assert "transcript" in data
    assert "language" in data
    assert data["language"] == "en"
