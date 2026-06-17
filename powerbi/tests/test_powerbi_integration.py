"""
End-to-end integration tests for the Power BI integration.

These tests call the real Power BI REST API and require a valid OAuth2 access token
set in the POWERBI_ACCESS_TOKEN environment variable (via .env or export).

Optional environment variables used by some tests:
    POWERBI_TEST_WORKSPACE_ID  — workspace ID for workspace-scoped tests
    POWERBI_TEST_DATASET_ID    — dataset ID for dataset/refresh tests
    POWERBI_TEST_REPORT_ID     — report ID for report tests
    POWERBI_TEST_DASHBOARD_ID  — dashboard ID for dashboard tests

Run read-only tests (safe — use this by default):
    pytest powerbi/tests/test_powerbi_integration.py -m "integration and not destructive"

Run destructive tests (triggers real refreshes against the live account):
    pytest powerbi/tests/test_powerbi_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from powerbi import powerbi

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.getenv("POWERBI_ACCESS_TOKEN", "")
TEST_WORKSPACE_ID = os.getenv("POWERBI_TEST_WORKSPACE_ID", "")
TEST_DATASET_ID = os.getenv("POWERBI_TEST_DATASET_ID", "")
TEST_REPORT_ID = os.getenv("POWERBI_TEST_REPORT_ID", "")
TEST_DASHBOARD_ID = os.getenv("POWERBI_TEST_DASHBOARD_ID", "")

POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("POWERBI_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=merged_headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# ---- Workspaces ----


@pytest.mark.asyncio
async def test_list_workspaces_live(live_context):
    result = await powerbi.execute_action("list_workspaces", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("workspaces") is not None


@pytest.mark.asyncio
async def test_get_workspace_live(live_context):
    if not TEST_WORKSPACE_ID:
        pytest.skip("POWERBI_TEST_WORKSPACE_ID not set")
    result = await powerbi.execute_action("get_workspace", {"workspace_id": TEST_WORKSPACE_ID}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("workspace") is not None


# ---- Datasets ----


@pytest.mark.asyncio
async def test_list_datasets_live(live_context):
    inputs = {"workspace_id": TEST_WORKSPACE_ID} if TEST_WORKSPACE_ID else {}
    result = await powerbi.execute_action("list_datasets", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("datasets") is not None


@pytest.mark.asyncio
async def test_get_refresh_history_live(live_context):
    if not TEST_DATASET_ID:
        pytest.skip("POWERBI_TEST_DATASET_ID not set")
    inputs = {"dataset_id": TEST_DATASET_ID, "top": 5}
    if TEST_WORKSPACE_ID:
        inputs["workspace_id"] = TEST_WORKSPACE_ID
    result = await powerbi.execute_action("get_refresh_history", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("refreshes") is not None


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_refresh_dataset_live(live_context):
    if not TEST_DATASET_ID:
        pytest.skip("POWERBI_TEST_DATASET_ID not set")
    inputs = {"dataset_id": TEST_DATASET_ID, "notify_option": "NoNotification"}
    if TEST_WORKSPACE_ID:
        inputs["workspace_id"] = TEST_WORKSPACE_ID
    result = await powerbi.execute_action("refresh_dataset", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("message") is not None


# ---- Reports ----


@pytest.mark.asyncio
async def test_list_reports_live(live_context):
    inputs = {"workspace_id": TEST_WORKSPACE_ID} if TEST_WORKSPACE_ID else {}
    result = await powerbi.execute_action("list_reports", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("reports") is not None


@pytest.mark.asyncio
async def test_get_report_live(live_context):
    if not TEST_REPORT_ID:
        pytest.skip("POWERBI_TEST_REPORT_ID not set")
    inputs = {"report_id": TEST_REPORT_ID}
    if TEST_WORKSPACE_ID:
        inputs["workspace_id"] = TEST_WORKSPACE_ID
    result = await powerbi.execute_action("get_report", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("report") is not None


# ---- Dashboards ----


@pytest.mark.asyncio
async def test_list_dashboards_live(live_context):
    inputs = {"workspace_id": TEST_WORKSPACE_ID} if TEST_WORKSPACE_ID else {}
    result = await powerbi.execute_action("list_dashboards", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("dashboards") is not None


@pytest.mark.asyncio
async def test_get_dashboard_live(live_context):
    if not TEST_DASHBOARD_ID:
        pytest.skip("POWERBI_TEST_DASHBOARD_ID not set")
    inputs = {"dashboard_id": TEST_DASHBOARD_ID}
    if TEST_WORKSPACE_ID:
        inputs["workspace_id"] = TEST_WORKSPACE_ID
    result = await powerbi.execute_action("get_dashboard", inputs, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("dashboard") is not None
