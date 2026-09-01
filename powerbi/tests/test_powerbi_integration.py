"""Read-only live integration tests for Power BI.

Requires POWERBI_ACCESS_TOKEN in the repository-root .env file or environment.

Run explicitly because integration tests are excluded from default discovery:
    pytest powerbi/tests/test_powerbi_integration.py -m integration -v
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from powerbi.powerbi import powerbi

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("POWERBI_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("POWERBI_ACCESS_TOKEN not set; skipping Power BI integration tests")

    async def real_fetch(url, *, method="GET", json=None, data=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method,
                url,
                json=json,
                data=data,
                headers=merged_headers,
                params=params,
                **kwargs,
            ) as response,
        ):
            try:
                response_data = await response.json(content_type=None)
            except Exception:
                response_data = await response.text()
            return FetchResponse(
                status=response.status,
                headers=dict(response.headers),
                data=response_data,
            )

    context = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


async def _first_workspace_id(live_context):
    result = await powerbi.execute_action("list_workspaces", {"top": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI workspaces: {result.result.message}")

    workspaces = result.result.data["workspaces"]
    if not workspaces:
        pytest.skip("No Power BI workspaces available for workspace-scoped tests")
    return workspaces[0]["id"]


async def _first_dataset_id(live_context):
    result = await powerbi.execute_action("list_datasets", {}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI datasets: {result.result.message}")

    datasets = result.result.data["datasets"]
    if not datasets:
        pytest.skip("No Power BI datasets available for query tests")
    return datasets[0]["id"]


async def test_list_workspaces_returns_workspaces(live_context):
    result = await powerbi.execute_action("list_workspaces", {"top": 5}, live_context)

    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["workspaces"], list)


async def test_list_datasets_returns_datasets(live_context):
    result = await powerbi.execute_action("list_datasets", {}, live_context)

    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["datasets"], list)


async def test_list_reports_returns_reports(live_context):
    result = await powerbi.execute_action("list_reports", {}, live_context)

    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["reports"], list)


async def test_list_dashboards_returns_dashboards(live_context):
    result = await powerbi.execute_action("list_dashboards", {}, live_context)

    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["dashboards"], list)


async def test_execute_queries_returns_results(live_context):
    dataset_id = await _first_dataset_id(live_context)

    result = await powerbi.execute_action(
        "execute_queries",
        {"dataset_id": dataset_id, "queries": [{"query": 'EVALUATE ROW("AutohiveIntegrationTest", 1)'}]},
        live_context,
    )

    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["results"], list)


async def test_get_workspace_returns_workspace_shape(live_context):
    workspace_id = await _first_workspace_id(live_context)

    result = await powerbi.execute_action("get_workspace", {"workspace_id": workspace_id}, live_context)

    assert result.type == ResultType.ACTION
    assert result.result.data["workspace"]["id"] == workspace_id
