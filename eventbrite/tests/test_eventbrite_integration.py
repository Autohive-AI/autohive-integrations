"""
End-to-end integration tests for the Eventbrite integration.

Read-only tests require a valid OAuth access token in EVENTBRITE_ACCESS_TOKEN
(via .env or export), plus an organization the token can access set in
EVENTBRITE_ORGANIZATION_ID.

Destructive tests (create/update/delete event, venue, ticket class) are
gated behind EVENTBRITE_RUN_DESTRUCTIVE_TESTS=1 since they create and
mutate real data in the Eventbrite account.

Run with:
    pytest eventbrite/tests/test_eventbrite_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock

from autohive_integrations_sdk import FetchResponse, ResultType
from eventbrite.eventbrite import eventbrite

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("EVENTBRITE_ACCESS_TOKEN", "")
ORGANIZATION_ID = os.environ.get("EVENTBRITE_ORGANIZATION_ID", "")
RUN_DESTRUCTIVE = os.environ.get("EVENTBRITE_RUN_DESTRUCTIVE_TESTS", "") == "1"

skip_if_no_creds = pytest.mark.skipif(not ACCESS_TOKEN, reason="EVENTBRITE_ACCESS_TOKEN required")
skip_if_no_org = pytest.mark.skipif(
    not (ACCESS_TOKEN and ORGANIZATION_ID),
    reason="EVENTBRITE_ACCESS_TOKEN and EVENTBRITE_ORGANIZATION_ID required",
)
skip_if_not_destructive = pytest.mark.skipif(not RUN_DESTRUCTIVE, reason="EVENTBRITE_RUN_DESTRUCTIVE_TESTS=1 required")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with an Eventbrite OAuth token.

    The Eventbrite integration relies on context.fetch to auto-inject the OAuth
    token (auth.type = "platform"). In tests we bypass the SDK auth layer and
    manually add the Authorization header to every request.
    """

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, body=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, data=body, headers=merged_headers, params=params
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---- User ----


class TestGetCurrentUser:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_user_info(self, live_context):
        result = await eventbrite.execute_action("get_current_user", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert "id" in result.result.data["user"]


class TestListOrganizations:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_organizations(self, live_context):
        result = await eventbrite.execute_action("list_organizations", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["organizations"], list)


# ---- Events ----


class TestListEvents:
    @skip_if_no_org
    @pytest.mark.asyncio
    async def test_returns_events(self, live_context):
        result = await eventbrite.execute_action(
            "list_events", {"organization_id": ORGANIZATION_ID, "page_size": 5}, live_context
        )

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["events"], list)


class TestListCategories:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_categories(self, live_context):
        result = await eventbrite.execute_action("list_categories", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["categories"], list)


# ---- Destructive event lifecycle ----


class TestEventLifecycle:
    @skip_if_not_destructive
    @skip_if_no_org
    @pytest.mark.asyncio
    async def test_01_create_update_delete_event(self, live_context):
        create_result = await eventbrite.execute_action(
            "create_event",
            {
                "organization_id": ORGANIZATION_ID,
                "name": "Autohive Integration Test Event",
                "start_utc": "2030-01-01T18:00:00Z",
                "end_utc": "2030-01-01T20:00:00Z",
                "timezone": "UTC",
                "currency": "USD",
            },
            live_context,
        )
        assert create_result.type != ResultType.ACTION_ERROR, create_result.result.message
        event_id = create_result.result.data["event"]["id"]

        update_result = await eventbrite.execute_action(
            "update_event", {"event_id": event_id, "summary": "Updated by integration test"}, live_context
        )
        assert update_result.type != ResultType.ACTION_ERROR, update_result.result.message

        delete_result = await eventbrite.execute_action("delete_event", {"event_id": event_id}, live_context)
        assert delete_result.type != ResultType.ACTION_ERROR, delete_result.result.message
        assert delete_result.result.data["deleted"] is True
