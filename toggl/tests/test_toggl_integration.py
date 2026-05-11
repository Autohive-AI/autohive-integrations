"""
Live integration tests for the Toggl Track integration.

Requires TOGGL_API_TOKEN set in the environment or project .env.
Also requires TOGGL_WORKSPACE_ID (numeric workspace ID).

Find your API token at: https://track.toggl.com/profile
Find your workspace ID at: https://track.toggl.com/

Run with:
    pytest toggl/tests/test_toggl_integration.py -m "integration"
"""

import json as _json
from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from toggl.toggl import toggl

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_token = env_credentials("TOGGL_API_TOKEN")
    if not api_token:
        pytest.skip("TOGGL_API_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params, **kwargs) as resp:
                text = await resp.text()
                data = _json.loads(text) if text.strip() else {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"credentials": {"api_token": api_token}})
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    return ctx


@pytest.fixture
def workspace_id(env_credentials):
    wid = env_credentials("TOGGL_WORKSPACE_ID")
    if not wid:
        pytest.skip("TOGGL_WORKSPACE_ID not set — skipping integration tests")
    return int(wid)


@pytest.mark.destructive
async def test_create_time_entry(live_context, workspace_id):
    result = await toggl.execute_action(
        "create_time_entry",
        {
            "workspace_id": workspace_id,
            "start": "2026-01-01T10:00:00Z",
            "stop": "2026-01-01T11:00:00Z",
            "duration": 3600,
            "description": "Autohive integration test — safe to delete",
        },
        live_context,
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "id" in data
    assert data["workspace_id"] == workspace_id
