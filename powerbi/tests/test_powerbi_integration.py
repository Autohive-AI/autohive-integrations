"""
Live integration tests for the Power BI integration.

Requires POWERBI_ACCESS_TOKEN set in the environment or project .env.

Token extraction recipe:
1. Authorize the Power BI platform OAuth app for a sandbox/test tenant.
2. Request the scopes configured in powerbi/config.json, including workspace,
   dataset, report, dashboard, and query permissions.
3. Copy the resulting short-lived OAuth access token to POWERBI_ACCESS_TOKEN.
4. Add the value to the project .env file or export it in your shell before
   running these tests.

Safe read-only run:
    pytest powerbi/tests/test_powerbi_integration.py -m "integration and not destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from powerbi import powerbi

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("POWERBI_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("POWERBI_ACCESS_TOKEN not set — skipping integration tests")

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
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    return ctx


async def _first_workspace_id(live_context):
    result = await powerbi.execute_action("list_workspaces", {"top": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI workspaces: {result.result.message}")

    workspaces = result.result.data["workspaces"]
    if not workspaces:
        pytest.skip("No Power BI workspaces available for workspace-scoped live tests")
    return workspaces[0]["id"]


async def _first_dataset_id(live_context):
    result = await powerbi.execute_action("list_datasets", {}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI datasets: {result.result.message}")

    datasets = result.result.data["datasets"]
    if not datasets:
        pytest.skip("No Power BI datasets available for dataset/query live tests")
    return datasets[0]["id"]


async def test_list_workspaces_returns_workspaces(live_context):
    result = await powerbi.execute_action("list_workspaces", {"top": 5}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "workspaces" in data
    assert isinstance(data["workspaces"], list)


async def test_list_datasets_returns_datasets(live_context):
    result = await powerbi.execute_action("list_datasets", {}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "datasets" in data
    assert isinstance(data["datasets"], list)


async def test_list_reports_returns_reports(live_context):
    result = await powerbi.execute_action("list_reports", {}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "reports" in data
    assert isinstance(data["reports"], list)


async def test_list_dashboards_returns_dashboards(live_context):
    result = await powerbi.execute_action("list_dashboards", {}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "dashboards" in data
    assert isinstance(data["dashboards"], list)


async def test_execute_queries_returns_results(live_context):
    dataset_id = await _first_dataset_id(live_context)

    result = await powerbi.execute_action(
        "execute_queries",
        {"dataset_id": dataset_id, "queries": [{"query": 'EVALUATE ROW("AutohiveIntegrationTest", 1)'}]},
        live_context,
    )

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "results" in data
    assert isinstance(data["results"], list)


async def test_get_workspace_returns_workspace_shape(live_context):
    workspace_id = await _first_workspace_id(live_context)

    result = await powerbi.execute_action("get_workspace", {"workspace_id": workspace_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "workspace" in data
    assert data["workspace"]["id"] == workspace_id
