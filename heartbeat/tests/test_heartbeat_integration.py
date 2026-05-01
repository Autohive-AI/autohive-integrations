"""Integration tests for the Heartbeat integration.

These tests make real HTTP calls to the Heartbeat API and require a valid API key.
They are skipped automatically when the HEARTBEAT_API_KEY environment variable is not set.

Run with:
    HEARTBEAT_API_KEY=<key> pytest heartbeat/tests/test_heartbeat_integration.py -m integration -v
"""

import importlib.util
import os
import sys

import pytest

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(_parent)
sys.path.insert(0, _parent)

pytestmark = pytest.mark.integration

HEARTBEAT_API_KEY = os.environ.get("HEARTBEAT_API_KEY", "")

if not HEARTBEAT_API_KEY:
    pytest.skip(
        "HEARTBEAT_API_KEY not set — skipping integration tests",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Load heartbeat module via importlib (same pattern as unit tests)
# ---------------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location("heartbeat_mod", os.path.join(_parent, "heartbeat.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["heartbeat_mod"] = _mod

heartbeat = _mod.heartbeat  # the Integration instance

# ---------------------------------------------------------------------------
# Real aiohttp fetch helper
# ---------------------------------------------------------------------------
import aiohttp  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402


async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
    """Make a real HTTP request using aiohttp and return a FetchResponse."""
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = await resp.text()
            return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)


@pytest.fixture
def real_context():
    """Execution context that uses real aiohttp for HTTP calls."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = real_fetch
    ctx.auth = {"credentials": {"api_key": HEARTBEAT_API_KEY}}  # nosec B105
    return ctx


# ---------------------------------------------------------------------------
# Integration tests (read-only actions only)
# ---------------------------------------------------------------------------


class TestGetChannelsIntegration:
    @pytest.mark.asyncio
    async def test_returns_channels(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_channels", {}, real_context)
        assert result is not None
        assert hasattr(result, "result")
        assert "channels" in result.result.data
        assert isinstance(result.result.data["channels"], list)

    @pytest.mark.asyncio
    async def test_channels_have_required_fields(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_channels", {}, real_context)
        channels = result.result.data["channels"]
        if channels:
            channel = channels[0]
            assert "id" in channel
            assert "name" in channel


class TestGetUsersIntegration:
    @pytest.mark.asyncio
    async def test_returns_users(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_users", {}, real_context)
        assert result is not None
        assert "users" in result.result.data
        assert isinstance(result.result.data["users"], list)

    @pytest.mark.asyncio
    async def test_users_have_required_fields(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_users", {}, real_context)
        users = result.result.data["users"]
        if users:
            user = users[0]
            assert "id" in user
            assert "email" in user
            assert "name" in user


class TestGetEventsIntegration:
    @pytest.mark.asyncio
    async def test_returns_events(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_events", {}, real_context)
        assert result is not None
        assert "events" in result.result.data
        assert isinstance(result.result.data["events"], list)

    @pytest.mark.asyncio
    async def test_events_have_required_fields(self, real_context):
        result = await heartbeat.execute_action("get_heartbeat_events", {}, real_context)
        events = result.result.data["events"]
        if events:
            event = events[0]
            assert "id" in event
            assert "title" in event
            assert "startTime" in event
