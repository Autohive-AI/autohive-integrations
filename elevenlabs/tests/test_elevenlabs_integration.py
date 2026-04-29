"""
Integration tests for the ElevenLabs integration (read-only actions).

Requires ELEVENLABS_API_KEY set in environment or .env file.

Run with:
    pytest elevenlabs/tests/test_elevenlabs_integration.py -m integration
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_spec = importlib.util.spec_from_file_location("elevenlabs_mod", os.path.join(_parent, "elevenlabs.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

elevenlabs = _mod.elevenlabs

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("ELEVENLABS_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                data = await resp.json()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": API_KEY}}
    return ctx


class TestGetUserSubscription:
    async def test_returns_subscription(self, live_context):
        result = await elevenlabs.execute_action("get_user_subscription", {}, live_context)

        data = result.result.data
        assert "subscription" in data


class TestListVoices:
    async def test_returns_voices(self, live_context):
        result = await elevenlabs.execute_action("list_voices", {"page_size": 5}, live_context)

        data = result.result.data
        assert "voices" in data
        assert isinstance(data["voices"], list)

    async def test_voice_has_required_fields(self, live_context):
        result = await elevenlabs.execute_action("list_voices", {"page_size": 1}, live_context)

        voices = result.result.data["voices"]
        if not voices:
            pytest.skip("No voices in account")

        voice = voices[0]
        assert "voice_id" in voice
        assert "name" in voice


class TestListHistory:
    async def test_returns_history(self, live_context):
        result = await elevenlabs.execute_action("list_history", {"page_size": 5}, live_context)

        data = result.result.data
        assert "history" in data
        assert isinstance(data["history"], list)
