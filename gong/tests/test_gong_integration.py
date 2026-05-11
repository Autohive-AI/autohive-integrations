"""
Live integration tests for the Gong integration.

Requires GONG_ACCESS_KEY and GONG_ACCESS_KEY_SECRET set in the environment or
project .env.

Safe read-only run:
    pytest gong/tests/test_gong_integration.py -m "integration and not destructive"
"""

import base64
from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from gong import gong

pytestmark = pytest.mark.integration

BASE_URL = "https://api.gong.io"


@pytest.fixture
def live_context(env_credentials, make_context):
    access_key = env_credentials("GONG_ACCESS_KEY")
    access_key_secret = env_credentials("GONG_ACCESS_KEY_SECRET")
    if not access_key:
        pytest.skip("GONG_ACCESS_KEY not set — skipping integration tests")
    if not access_key_secret:
        pytest.skip("GONG_ACCESS_KEY_SECRET not set — skipping integration tests")

    token = base64.b64encode(f"{access_key}:{access_key_secret}".encode()).decode()

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = {"Authorization": f"Basic {token}"}
        if headers:
            merged_headers.update(headers)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                headers=merged_headers,
                params=params,
                **kwargs,
            ) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_key},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.metadata = {"api_base_url": BASE_URL}
    return ctx


class TestListCallsIntegration:
    async def test_list_calls_returns_calls(self, live_context):
        result = await gong.execute_action("list_calls", {"limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "calls" in data
        assert isinstance(data["calls"], list)
        assert "has_more" in data
        assert "next_cursor" in data


class TestListUsersIntegration:
    async def test_list_users_returns_users(self, live_context):
        result = await gong.execute_action("list_users", {"limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "users" in data
        assert isinstance(data["users"], list)
        assert "has_more" in data
        assert "next_cursor" in data
