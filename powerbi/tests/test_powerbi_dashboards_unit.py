import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("powerbi_mod", os.path.join(_parent, "powerbi.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

powerbi = _mod.powerbi

pytestmark = pytest.mark.unit

POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Dashboards ----


class TestListDashboards:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"id": "db-1", "displayName": "Sales Dashboard", "isReadOnly": False}]},
        )

        result = await powerbi.execute_action("list_dashboards", {}, mock_context)

        assert result.result.data["dashboards"][0]["id"] == "db-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_dashboards", {"workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/dashboards"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_dashboards", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/dashboards"

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("list_dashboards", {}, mock_context)

        assert result.result.data["dashboards"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await powerbi.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        db = {"id": "db-1", "displayName": "Sales Dashboard"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=db)

        result = await powerbi.execute_action("get_dashboard", {"dashboard_id": "db-1"}, mock_context)

        assert result.result.data["dashboard"]["id"] == "db-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dashboard", {"dashboard_id": "db-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/dashboards/db-1"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dashboard", {"dashboard_id": "db-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/dashboards/db-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_dashboard", {"dashboard_id": "db-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDashboardTiles:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"id": "tile-1", "title": "Revenue", "datasetId": "ds-1", "reportId": "rpt-1"}]},
        )

        result = await powerbi.execute_action("get_dashboard_tiles", {"dashboard_id": "db-1"}, mock_context)

        assert result.result.data["tiles"][0]["id"] == "tile-1"
        assert result.result.data["tiles"][0]["title"] == "Revenue"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action(
            "get_dashboard_tiles", {"dashboard_id": "db-1", "workspace_id": "ws-1"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/dashboards/db-1/tiles"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("get_dashboard_tiles", {"dashboard_id": "db-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/dashboards/db-1/tiles"

    @pytest.mark.asyncio
    async def test_empty_tiles(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("get_dashboard_tiles", {"dashboard_id": "db-1"}, mock_context)

        assert result.result.data["tiles"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await powerbi.execute_action("get_dashboard_tiles", {"dashboard_id": "db-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
