"""
Live integration tests for the Front integration.

Requires FRONT_API_TOKEN set in the environment or project .env.

Safe read-only run:
    pytest front/tests/test_front_integration.py -m "integration and not destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from front import front

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("FRONT_API_TOKEN")
    if not access_token:
        pytest.skip("FRONT_API_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"

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
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    return ctx


async def test_list_inboxes_integration(live_context):
    result = await front.execute_action("list_inboxes", {"limit": 5}, live_context)

    assert result.type == ResultType.ACTION
    assert "inboxes" in result.result.data
    assert isinstance(result.result.data["inboxes"], list)


async def test_list_teammates_integration(live_context):
    result = await front.execute_action("list_teammates", {"limit": 5}, live_context)

    assert result.type == ResultType.ACTION
    assert "teammates" in result.result.data
    assert isinstance(result.result.data["teammates"], list)


async def test_list_channels_integration(live_context):
    result = await front.execute_action("list_channels", {"limit": 5}, live_context)

    assert result.type == ResultType.ACTION
    assert "channels" in result.result.data
    assert isinstance(result.result.data["channels"], list)
