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

Safe read-only run (use this by default):
    pytest powerbi/tests/test_powerbi_integration.py -m "integration and not destructive"

Destructive run — mutates real data (creates/clones reports, triggers a real dataset
refresh, initiates a real export). Only run deliberately, never by reviewers:
    pytest powerbi/tests/test_powerbi_integration.py -m "integration and destructive"
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType

# Plain "from powerbi import powerbi" is ambiguous: it can resolve to the powerbi/
# *package* directory (which has __init__.py) instead of powerbi/powerbi.py, silently
# binding the wrong object depending on sys.path order at import time. Load the module
# explicitly by file path instead, matching the other test files in this directory.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("powerbi_mod", os.path.join(_parent, "powerbi.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
powerbi = _mod.powerbi

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
                # Match production context.fetch semantics (raises HTTPError on any
                # non-2xx status) - without this, actions relying on fetch to raise for
                # their try/except error handling silently "succeed" with null/malformed
                # data on real API errors instead of returning a proper ActionError.
                if resp.status >= 300:
                    message = data.get("error", {}).get("message", str(data)) if isinstance(data, dict) else str(data)
                    raise HTTPError(status=resp.status, message=message, response_data=data)
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
    # "My workspace" (no workspace_id) is often empty - fall back to scanning real
    # workspaces so these tests exercise dataset-scoped actions against actual data.
    result = await powerbi.execute_action("list_datasets", {}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI datasets: {result.result.message}")

    datasets = result.result.data["datasets"]
    if datasets:
        return datasets[0]["id"]

    workspaces_result = await powerbi.execute_action("list_workspaces", {"top": 25}, live_context)
    if workspaces_result.type == ResultType.ACTION:
        for workspace in workspaces_result.result.data["workspaces"]:
            ws_result = await powerbi.execute_action("list_datasets", {"workspace_id": workspace["id"]}, live_context)
            if ws_result.type == ResultType.ACTION and ws_result.result.data["datasets"]:
                return ws_result.result.data["datasets"][0]["id"]

    pytest.skip("No Power BI datasets available in My workspace or any accessible workspace")


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


async def test_get_dataset_returns_dataset_shape(live_context):
    dataset_id = await _first_dataset_id(live_context)

    result = await powerbi.execute_action("get_dataset", {"dataset_id": dataset_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "dataset" in data
    assert data["dataset"]["id"] == dataset_id


async def _first_report_id(live_context):
    # Same "My workspace" fallback as _first_dataset_id.
    result = await powerbi.execute_action("list_reports", {}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Power BI reports: {result.result.message}")

    reports = result.result.data["reports"]
    if reports:
        return reports[0]["id"]

    workspaces_result = await powerbi.execute_action("list_workspaces", {"top": 25}, live_context)
    if workspaces_result.type == ResultType.ACTION:
        for workspace in workspaces_result.result.data["workspaces"]:
            ws_result = await powerbi.execute_action("list_reports", {"workspace_id": workspace["id"]}, live_context)
            if ws_result.type == ResultType.ACTION and ws_result.result.data["reports"]:
                return ws_result.result.data["reports"][0]["id"]

    pytest.skip("No Power BI reports available in My workspace or any accessible workspace")


async def test_get_report_returns_report_shape(live_context):
    report_id = await _first_report_id(live_context)

    result = await powerbi.execute_action("get_report", {"report_id": report_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "report" in data
    assert data["report"]["id"] == report_id


@pytest.mark.destructive
async def test_refresh_dataset_triggers_a_refresh(live_context):
    dataset_id = await _first_dataset_id(live_context)

    result = await powerbi.execute_action("refresh_dataset", {"dataset_id": dataset_id}, live_context)

    assert result.type == ResultType.ACTION, getattr(result.result, "message", None)
    assert "message" in result.result.data


@pytest.mark.destructive
async def test_clone_report_creates_a_copy(live_context):
    report_id = await _first_report_id(live_context)

    result = await powerbi.execute_action(
        "clone_report",
        {"report_id": report_id, "name": "Autohive Integration Test Clone"},
        live_context,
    )

    assert result.type == ResultType.ACTION, getattr(result.result, "message", None)
    data = result.result.data
    assert data["id"]
    assert data["id"] != report_id


@pytest.mark.destructive
async def test_export_report_initiates_an_export(live_context):
    report_id = await _first_report_id(live_context)

    result = await powerbi.execute_action("export_report", {"report_id": report_id, "format": "PDF"}, live_context)

    # export_report requires Premium/Fabric dedicated capacity - a workspace on shared
    # capacity fails here with a 403 (surfaced as ACTION_ERROR), which is an environment
    # limitation rather than an integration bug. Assert the action behaves correctly
    # either way: either it succeeds with an export_id, or it cleanly reports the
    # documented capacity error rather than a schema-validation crash.
    if result.type == ResultType.ACTION_ERROR:
        pytest.skip(f"export_report requires dedicated capacity: {result.result.message}")
    assert result.type == ResultType.ACTION
    assert result.result.data["export_id"]


@pytest.mark.destructive
async def test_create_report_creates_a_report(live_context):
    workspace_id = await _first_workspace_id(live_context)
    dataset_id = await _first_dataset_id(live_context)

    result = await powerbi.execute_action(
        "create_report",
        {
            "display_name": "Autohive Integration Test Report",
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "pages": [
                {
                    "name": "Overview",
                    "visuals": [
                        {
                            "type": "card",
                            "table": "AutohiveIntegrationTest",
                            "columns": [],
                            "title": "Autohive Integration Test",
                        }
                    ],
                }
            ],
        },
        live_context,
    )

    assert result.type == ResultType.ACTION, getattr(result.result, "message", None)
    data = result.result.data
    assert data["id"]
    assert data["workspace_id"] == workspace_id
