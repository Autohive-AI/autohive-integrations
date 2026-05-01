"""
End-to-end integration tests for the Heartbeat integration.

These tests call the real Heartbeat API and require a valid API key.

Run with:
    HEARTBEAT_API_KEY=<key> pytest heartbeat/tests/test_heartbeat_integration.py -m integration

Skipped automatically when HEARTBEAT_API_KEY is not set.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk.integration import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("heartbeat_mod", os.path.join(_parent, "heartbeat.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

heartbeat = _mod.heartbeat

pytestmark = pytest.mark.integration

HEARTBEAT_API_KEY = os.environ.get("HEARTBEAT_API_KEY", "")

if not HEARTBEAT_API_KEY:
    pytest.skip("HEARTBEAT_API_KEY environment variable not set", allow_module_level=True)


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client via aiohttp."""
    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": HEARTBEAT_API_KEY}}  # nosec B105
    return ctx


# ---- Channels ----


class TestGetChannelsIntegration:
    async def test_returns_channels(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_channels", {}, live_context)

        data = result.result.data
        assert "channels" in data
        assert isinstance(data["channels"], list)

    async def test_channel_structure(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_channels", {}, live_context)

        channels = result.result.data["channels"]
        if channels:
            channel = channels[0]
            assert "id" in channel
            assert "name" in channel

    async def test_cost_is_zero(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_channels", {}, live_context)

        assert result.result.cost_usd == 0.0


# ---- Users ----


class TestGetUsersIntegration:
    async def test_returns_users(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_users", {}, live_context)

        data = result.result.data
        assert "users" in data
        assert isinstance(data["users"], list)

    async def test_user_structure(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_users", {}, live_context)

        users = result.result.data["users"]
        if users:
            user = users[0]
            assert "id" in user
            assert "email" in user
            assert "name" in user


# ---- Events ----


class TestGetEventsIntegration:
    async def test_returns_events(self, live_context):
        result = await heartbeat.execute_action("get_heartbeat_events", {}, live_context)

        data = result.result.data
        assert "events" in data
        assert isinstance(data["events"], list)
