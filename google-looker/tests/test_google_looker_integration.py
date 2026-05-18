"""
End-to-end integration tests for the Google Looker integration.

These tests call the real Looker API and require valid credentials
set in environment variables (via .env or export).

Run with:
    pytest google-looker/tests/test_google_looker_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

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


def require_dashboard_id():
    if not LOOKER_TEST_DASHBOARD_ID:
        pytest.skip("LOOKER_TEST_DASHBOARD_ID not set")


def require_model_name():
    if not LOOKER_TEST_MODEL_NAME:
        pytest.skip("LOOKER_TEST_MODEL_NAME not set")


@pytest.fixture
def live_context():
    if not all([LOOKER_BASE_URL, LOOKER_CLIENT_ID, LOOKER_CLIENT_SECRET]):
        pytest.skip("LOOKER_BASE_URL, LOOKER_CLIENT_ID, LOOKER_CLIENT_SECRET not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, data=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, data=data, headers=headers, params=params) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "credentials": {
            "base_url": LOOKER_BASE_URL,
            "client_id": LOOKER_CLIENT_ID,
            "client_secret": LOOKER_CLIENT_SECRET,
        }
    }
    return ctx


# ---- Read-Only Tests ----


class TestListDashboards:
    @pytest.mark.asyncio
    async def test_returns_dashboard_list(self, live_context):
        result = await google_looker.execute_action("list_dashboards", {}, live_context)

        assert "dashboards" in result.result.data
        assert isinstance(result.result.data["dashboards"], list)

    @pytest.mark.asyncio
    async def test_fields_param_filters_response(self, live_context):
        result = await google_looker.execute_action("list_dashboards", {"fields": "id,title"}, live_context)

        assert "dashboards" in result.result.data


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_dashboard(self, live_context):
        require_dashboard_id()
        result = await google_looker.execute_action(
            "get_dashboard", {"dashboard_id": LOOKER_TEST_DASHBOARD_ID}, live_context
        )

        assert "dashboard" in result.result.data
        assert result.result.data["dashboard"]["id"] == LOOKER_TEST_DASHBOARD_ID


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_model_list(self, live_context):
        result = await google_looker.execute_action("list_models", {}, live_context)

        assert "models" in result.result.data
        assert isinstance(result.result.data["models"], list)


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_model(self, live_context):
        require_model_name()
        result = await google_looker.execute_action("get_model", {"model_name": LOOKER_TEST_MODEL_NAME}, live_context)

        assert "model" in result.result.data
        assert result.result.data["model"]["name"] == LOOKER_TEST_MODEL_NAME


class TestListConnections:
    @pytest.mark.asyncio
    async def test_returns_connections(self, live_context):
        result = await google_looker.execute_action("list_connections", {}, live_context)

        assert "connections" in result.result.data
        assert isinstance(result.result.data["connections"], list)
