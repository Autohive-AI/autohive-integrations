"""
End-to-end integration tests for the Google Looker integration.

These tests call the real Looker API and require valid credentials
set in environment variables (via .env or export).

Run with:
    pytest google-looker/tests/test_google_looker_integration.py -m "integration and not destructive"

Run the opt-in SQL Runner test with:
    pytest google-looker/tests/test_google_looker_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib
import json as json_module
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse, HTTPError  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_looker_mod", os.path.join(_parent, "google_looker.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_looker = _mod.google_looker

pytestmark = pytest.mark.integration

LOOKER_BASE_URL = os.environ.get("LOOKER_BASE_URL", "")
LOOKER_CLIENT_ID = os.environ.get("LOOKER_CLIENT_ID", "")
LOOKER_CLIENT_SECRET = os.environ.get("LOOKER_CLIENT_SECRET", "")  # nosec B105
LOOKER_TEST_DASHBOARD_ID = os.environ.get("LOOKER_TEST_DASHBOARD_ID", "")
LOOKER_TEST_MODEL_NAME = os.environ.get("LOOKER_TEST_MODEL_NAME", "")
LOOKER_TEST_EXPLORE_NAME = os.environ.get("LOOKER_TEST_EXPLORE_NAME", "")
LOOKER_TEST_QUERY_FIELD = os.environ.get("LOOKER_TEST_QUERY_FIELD", "")
LOOKER_RUN_SQL_TESTS = os.environ.get("LOOKER_RUN_SQL_TESTS", "").lower() == "true"


def require_dashboard_id():
    if not LOOKER_TEST_DASHBOARD_ID:
        pytest.skip("LOOKER_TEST_DASHBOARD_ID not set")


def require_model_name():
    if not LOOKER_TEST_MODEL_NAME:
        pytest.skip("LOOKER_TEST_MODEL_NAME not set")


def require_query_config():
    missing = [
        name
        for name, value in {
            "LOOKER_TEST_MODEL_NAME": LOOKER_TEST_MODEL_NAME,
            "LOOKER_TEST_EXPLORE_NAME": LOOKER_TEST_EXPLORE_NAME,
            "LOOKER_TEST_QUERY_FIELD": LOOKER_TEST_QUERY_FIELD,
        }.items()
        if not value
    ]
    if missing:
        pytest.skip(f"{', '.join(missing)} not set")


def assert_action_success(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)


@pytest.fixture
def live_context():
    if not all([LOOKER_BASE_URL, LOOKER_CLIENT_ID, LOOKER_CLIENT_SECRET]):
        pytest.skip("LOOKER_BASE_URL, LOOKER_CLIENT_ID, LOOKER_CLIENT_SECRET not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, data=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, data=data, headers=headers, params=params) as resp:
                response_text = await resp.text()
                try:
                    resp_data = json_module.loads(response_text)
                except (TypeError, ValueError):
                    resp_data = response_text
                if not 200 <= resp.status < 300:
                    raise HTTPError(resp.status, response_text, resp_data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": LOOKER_BASE_URL,
            "client_id": LOOKER_CLIENT_ID,
            "client_secret": LOOKER_CLIENT_SECRET,
        },
    }
    return ctx


# ---- Read-Only Tests ----


class TestListDashboards:
    @pytest.mark.asyncio
    async def test_returns_dashboard_list(self, live_context):
        result = await google_looker.execute_action("list_dashboards", {}, live_context)

        assert_action_success(result)
        assert "dashboards" in result.result.data
        assert isinstance(result.result.data["dashboards"], list)

    @pytest.mark.asyncio
    async def test_fields_param_filters_response(self, live_context):
        result = await google_looker.execute_action("list_dashboards", {"fields": "id,title"}, live_context)

        assert_action_success(result)
        assert "dashboards" in result.result.data
        assert all(set(dashboard).issubset({"id", "title"}) for dashboard in result.result.data["dashboards"])


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_dashboard(self, live_context):
        require_dashboard_id()
        result = await google_looker.execute_action(
            "get_dashboard", {"dashboard_id": LOOKER_TEST_DASHBOARD_ID}, live_context
        )

        assert_action_success(result)
        assert "dashboard" in result.result.data
        assert result.result.data["dashboard"]["id"] == LOOKER_TEST_DASHBOARD_ID


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_model_list(self, live_context):
        result = await google_looker.execute_action("list_models", {}, live_context)

        assert_action_success(result)
        assert "models" in result.result.data
        assert isinstance(result.result.data["models"], list)


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_model(self, live_context):
        require_model_name()
        result = await google_looker.execute_action("get_model", {"model_name": LOOKER_TEST_MODEL_NAME}, live_context)

        assert_action_success(result)
        assert "model" in result.result.data
        assert result.result.data["model"]["name"] == LOOKER_TEST_MODEL_NAME


class TestListConnections:
    @pytest.mark.asyncio
    async def test_returns_connections(self, live_context):
        result = await google_looker.execute_action("list_connections", {}, live_context)

        assert_action_success(result)
        assert "connections" in result.result.data
        assert isinstance(result.result.data["connections"], list)


class TestExecuteLookMLQuery:
    @pytest.mark.asyncio
    async def test_executes_bounded_read_only_query(self, live_context):
        require_query_config()

        result = await google_looker.execute_action(
            "execute_lookml_query",
            {
                "model": LOOKER_TEST_MODEL_NAME,
                "explore": LOOKER_TEST_EXPLORE_NAME,
                "dimensions": [LOOKER_TEST_QUERY_FIELD],
                "limit": 1,
                "result_format": "json",
            },
            live_context,
        )

        assert_action_success(result)
        rows = json_module.loads(result.result.data["query_results"])
        assert isinstance(rows, list)
        assert len(rows) <= 1


class TestExecuteSQLQuery:
    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_executes_read_only_sql_statement(self, live_context):
        if not LOOKER_RUN_SQL_TESTS:
            pytest.skip("Set LOOKER_RUN_SQL_TESTS=true to explicitly enable the SQL Runner test")
        require_model_name()

        result = await google_looker.execute_action(
            "execute_sql_query",
            {
                "sql": "SELECT 1 AS autohive_test",
                "model_name": LOOKER_TEST_MODEL_NAME,
                "result_format": "json",
                "download": "false",
            },
            live_context,
        )

        assert_action_success(result)
        assert result.result.data["slug"]
        assert result.result.data["query_results"]
