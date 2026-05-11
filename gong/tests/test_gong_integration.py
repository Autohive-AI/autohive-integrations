"""
Live integration tests for the Gong integration.

Requires GONG_ACCESS_TOKEN set in the environment or project .env. Set
GONG_API_BASE_URL when the OAuth token response includes a customer-specific
api_base_url_for_customer value; otherwise the tests default to
https://api.gong.io.

Token/base-url extraction recipe:
1. Create a Gong OAuth app from Admin center > Settings > Ecosystem > API.
2. Select the scopes configured in gong/config.json:
   api:calls:read:basic, api:calls:read:extensive,
   api:calls:read:transcript, and api:users:read.
3. Complete Gong's authorization-code flow as a tech admin and exchange the
   authorization code with /oauth2/generate-customer-token.
4. Copy the returned access_token to GONG_ACCESS_TOKEN.
5. If the response includes api_base_url_for_customer, copy it to
   GONG_API_BASE_URL. Gong OAuth responses can return a customer-specific API
   base URL, and requests should use that value when present.

Safe read-only run:
    pytest gong/tests/test_gong_integration.py -m "integration and not destructive"
"""

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
    access_token = env_credentials("GONG_ACCESS_TOKEN")
    api_base_url = env_credentials("GONG_API_BASE_URL") or BASE_URL
    if not access_token:
        pytest.skip("GONG_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = {"Authorization": f"Bearer {access_token}"}
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
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.metadata = {"api_base_url": api_base_url}
    return ctx


async def _first_call_id(live_context):
    result = await gong.execute_action("list_calls", {"limit": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Gong calls: {result.result.message}")

    calls = result.result.data["calls"]
    if not calls:
        pytest.skip("No non-private Gong calls available to test call-specific actions")
    return calls[0]["id"]


class TestListCallsIntegration:
    async def test_list_calls_returns_calls(self, live_context):
        result = await gong.execute_action("list_calls", {"limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "calls" in data
        assert isinstance(data["calls"], list)
        assert "has_more" in data
        assert "next_cursor" in data


class TestGetCallDetailsIntegration:
    async def test_get_call_details_returns_call_shape(self, live_context):
        call_id = await _first_call_id(live_context)

        result = await gong.execute_action("get_call_details", {"call_id": call_id}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["id"] == call_id
        assert "title" in data
        assert "started" in data
        assert "duration" in data
        assert "participants" in data
        assert "outcome" in data
        assert "crm_data" in data


class TestGetCallTranscriptIntegration:
    async def test_get_call_transcript_returns_transcript_shape(self, live_context):
        call_id = await _first_call_id(live_context)

        result = await gong.execute_action("get_call_transcript", {"call_id": call_id}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["call_id"] == call_id
        assert "transcript" in data
        assert isinstance(data["transcript"], list)


class TestSearchCallsIntegration:
    async def test_search_calls_returns_results_shape(self, live_context):
        result = await gong.execute_action("search_calls", {"query": "a", "limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "results" in data
        assert isinstance(data["results"], list)
        assert "total_count" in data


class TestListUsersIntegration:
    async def test_list_users_returns_users(self, live_context):
        result = await gong.execute_action("list_users", {"limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "users" in data
        assert isinstance(data["users"], list)
        assert "has_more" in data
        assert "next_cursor" in data
