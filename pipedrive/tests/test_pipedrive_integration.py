"""
End-to-end integration tests for the Pipedrive integration.

Read-only tests require a valid OAuth access token in PIPEDRIVE_ACCESS_TOKEN
(via .env or export).

Destructive tests (create/update/delete deal, person, organization, activity,
note) are gated behind PIPEDRIVE_RUN_DESTRUCTIVE_TESTS=1 since they create
and mutate real data in the Pipedrive account.

Run with:
    pytest pipedrive/tests/test_pipedrive_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock

from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from pipedrive.pipedrive import pipedrive

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("PIPEDRIVE_ACCESS_TOKEN", "")
RUN_DESTRUCTIVE = os.environ.get("PIPEDRIVE_RUN_DESTRUCTIVE_TESTS", "") == "1"

skip_if_no_creds = pytest.mark.skipif(not ACCESS_TOKEN, reason="PIPEDRIVE_ACCESS_TOKEN required")
skip_if_not_destructive = pytest.mark.skipif(not RUN_DESTRUCTIVE, reason="PIPEDRIVE_RUN_DESTRUCTIVE_TESTS=1 required")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with a Pipedrive OAuth token.

    The Pipedrive integration relies on context.fetch to auto-inject the OAuth
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

                # Mimic ExecutionContext.fetch() error semantics so actions reach
                # their except blocks and return ActionError as they would in prod.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(data), data)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(data), data)

                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---- Read-only ----


class TestListDeals:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_deals(self, live_context):
        result = await pipedrive.execute_action("list_deals", {"limit": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["deals"], list)


class TestListPersons:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_persons(self, live_context):
        result = await pipedrive.execute_action("list_persons", {"limit": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["persons"], list)


class TestListOrganizations:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_organizations(self, live_context):
        result = await pipedrive.execute_action("list_organizations", {"limit": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["organizations"], list)


class TestListActivities:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_activities(self, live_context):
        result = await pipedrive.execute_action("list_activities", {"limit": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["activities"], list)


class TestListPipelines:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_pipelines(self, live_context):
        result = await pipedrive.execute_action("list_pipelines", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["pipelines"], list)


class TestListStages:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_stages(self, live_context):
        result = await pipedrive.execute_action("list_stages", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["stages"], list)


class TestSearch:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_items(self, live_context):
        result = await pipedrive.execute_action("search", {"term": "a"}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["items"], list)


# ---- Destructive lifecycle ----


class TestDealLifecycle:
    @skip_if_not_destructive
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_01_create_update_delete_deal(self, live_context):
        create_result = await pipedrive.execute_action(
            "create_deal", {"title": "Autohive Integration Test Deal"}, live_context
        )
        assert create_result.type != ResultType.ACTION_ERROR, create_result.result.message
        deal_id = create_result.result.data["deal"]["id"]

        update_result = await pipedrive.execute_action(
            "update_deal", {"deal_id": deal_id, "title": "Updated by integration test"}, live_context
        )
        assert update_result.type != ResultType.ACTION_ERROR, update_result.result.message

        delete_result = await pipedrive.execute_action("delete_deal", {"deal_id": deal_id}, live_context)
        assert delete_result.type != ResultType.ACTION_ERROR, delete_result.result.message
        assert delete_result.result.data["deleted"] is True


class TestPersonLifecycle:
    @skip_if_not_destructive
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_01_create_update_delete_person(self, live_context):
        create_result = await pipedrive.execute_action("create_person", {"name": "Autohive Test Contact"}, live_context)
        assert create_result.type != ResultType.ACTION_ERROR, create_result.result.message
        person_id = create_result.result.data["person"]["id"]

        update_result = await pipedrive.execute_action(
            "update_person", {"person_id": person_id, "name": "Updated Test Contact"}, live_context
        )
        assert update_result.type != ResultType.ACTION_ERROR, update_result.result.message

        delete_result = await pipedrive.execute_action("delete_person", {"person_id": person_id}, live_context)
        assert delete_result.type != ResultType.ACTION_ERROR, delete_result.result.message
        assert delete_result.result.data["deleted"] is True
