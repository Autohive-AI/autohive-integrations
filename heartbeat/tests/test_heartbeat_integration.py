"""
Live integration tests for the Heartbeat integration.

Requires HEARTBEAT_API_KEY set in the environment or project .env.

Safe read-only run:
    pytest heartbeat/tests/test_heartbeat_integration.py -m "integration and not destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse

from heartbeat import heartbeat

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("HEARTBEAT_API_KEY")
    if not api_key:
        pytest.skip("HEARTBEAT_API_KEY not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = make_context(auth={"api_key": api_key})
    ctx.fetch = AsyncMock(side_effect=real_fetch)
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
