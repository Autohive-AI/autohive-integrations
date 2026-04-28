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


# ---- Workspaces ----


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "value": [
                    {
                        "id": "ws-1",
                        "name": "My Workspace",
                        "isReadOnly": False,
                        "isOnDedicatedCapacity": False,
                        "type": "Workspace",
                    }
                ]
            },
        )

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.result.data["workspaces"][0]["id"] == "ws-1"
        assert result.result.data["workspaces"][0]["name"] == "My Workspace"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{POWERBI_API_BASE}/groups"

    @pytest.mark.asyncio
    async def test_filter_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {"filter": "type eq 'Workspace'"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["params"]["$filter"] == "type eq 'Workspace'"

    @pytest.mark.asyncio
    async def test_top_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {"top": 50}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["params"]["$top"] == 50

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.result.data["workspaces"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        ws = {"id": "ws-1", "name": "Sales", "isReadOnly": False}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ws)

        result = await powerbi.execute_action("get_workspace", {"workspace_id": "ws-1"}, mock_context)

        assert result.result.data["workspace"]["id"] == "ws-1"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_workspace", {"workspace_id": "ws-abc"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-abc"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_workspace", {"workspace_id": "ws-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Datasets ----


class TestListDatasets:
    @pytest.mark.asyncio
    async def test_happy_path_no_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "value": [{"id": "ds-1", "name": "Sales DS", "configuredBy": "user@test.com", "isRefreshable": True}]
            },
        )

        result = await powerbi.execute_action("list_datasets", {}, mock_context)

        assert result.result.data["datasets"][0]["id"] == "ds-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_datasets", {"workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_datasets", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/datasets"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await powerbi.execute_action("list_datasets", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDataset:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        ds = {"id": "ds-1", "name": "Sales"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ds)

        result = await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["dataset"]["id"] == "ds-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/datasets/ds-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestRefreshDataset:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["message"] == "Dataset refresh initiated successfully"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_default_notify_option(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["notifyOption"] == "NoNotification"

    @pytest.mark.asyncio
    async def test_notify_option_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action(
            "refresh_dataset", {"dataset_id": "ds-1", "notify_option": "MailOnFailure"}, mock_context
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["notifyOption"] == "MailOnFailure"

    @pytest.mark.asyncio
    async def test_request_id_from_headers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={"x-ms-request-id": "req-123"}, data=None)

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["request_id"] == "req-123"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/refreshes"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetRefreshHistory:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"refreshType": "Full", "status": "Completed", "startTime": "2024-01-01T00:00:00Z"}]},
        )

        result = await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["refreshes"][0]["refreshType"] == "Full"

    @pytest.mark.asyncio
    async def test_top_param_sent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1", "top": 5}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 5

    @pytest.mark.asyncio
    async def test_default_top_is_10(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 10

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Reports ----


class TestListReports:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"id": "rpt-1", "name": "Sales Report", "datasetId": "ds-1"}]},
        )

        result = await powerbi.execute_action("list_reports", {}, mock_context)

        assert result.result.data["reports"][0]["id"] == "rpt-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_reports", {"workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/reports"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_reports", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/reports"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection error")

        result = await powerbi.execute_action("list_reports", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        rpt = {"id": "rpt-1", "name": "Sales Report", "datasetId": "ds-1"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=rpt)

        result = await powerbi.execute_action("get_report", {"report_id": "rpt-1"}, mock_context)

        assert result.result.data["report"]["id"] == "rpt-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_report", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/reports/rpt-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_report", {"report_id": "rpt-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetReportDatasources:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"datasourceType": "Sql", "datasourceId": "dsc-1", "name": "DB Source"}]},
        )

        result = await powerbi.execute_action("get_report_datasources", {"report_id": "rpt-1"}, mock_context)

        assert result.result.data["datasources"][0]["datasourceType"] == "Sql"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action(
            "get_report_datasources", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/reports/rpt-1/datasources"

    @pytest.mark.asyncio
    async def test_connection_details_included(self, mock_context):
        conn_details = {"server": "myserver", "database": "mydb"}
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"datasourceType": "Sql", "connectionDetails": conn_details}]},
        )

        result = await powerbi.execute_action("get_report_datasources", {"report_id": "rpt-1"}, mock_context)

        assert result.result.data["datasources"][0]["connectionDetails"]["server"] == "myserver"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await powerbi.execute_action("get_report_datasources", {"report_id": "rpt-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestRefreshReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"id": "rpt-1", "name": "Sales", "datasetId": "ds-1"}),
            FetchResponse(status=202, headers={}, data=None),
        ]

        result = await powerbi.execute_action("refresh_report", {"report_id": "rpt-1"}, mock_context)

        assert result.result.data["dataset_id"] == "ds-1"
        assert "Sales" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_missing_dataset_returns_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "rpt-1", "name": "Report"})

        result = await powerbi.execute_action("refresh_report", {"report_id": "rpt-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "associated dataset" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await powerbi.execute_action("refresh_report", {"report_id": "rpt-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCloneReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": "rpt-2",
                "name": "Sales Copy",
                "webUrl": "https://app.powerbi.com/rpt-2",
                "embedUrl": "https://embed/rpt-2",
            },
        )

        result = await powerbi.execute_action(
            "clone_report", {"report_id": "rpt-1", "name": "Sales Copy"}, mock_context
        )

        assert result.result.data["id"] == "rpt-2"
        assert result.result.data["name"] == "Sales Copy"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "rpt-2"})

        await powerbi.execute_action("clone_report", {"report_id": "rpt-1", "name": "Clone"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_clone_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "rpt-2"})

        await powerbi.execute_action(
            "clone_report",
            {"report_id": "rpt-1", "name": "Clone", "target_workspace_id": "ws-2", "target_dataset_id": "ds-2"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["name"] == "Clone"
        assert payload["targetWorkspaceId"] == "ws-2"
        assert payload["targetModelId"] == "ds-2"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await powerbi.execute_action("clone_report", {"report_id": "rpt-1", "name": "Clone"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestExportReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data={"id": "exp-1"})

        result = await powerbi.execute_action("export_report", {"report_id": "rpt-1"}, mock_context)

        assert result.result.data["export_id"] == "exp-1"
        assert result.result.data["message"] == "Export initiated successfully"

    @pytest.mark.asyncio
    async def test_default_format_is_pdf(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data={"id": "exp-1"})

        await powerbi.execute_action("export_report", {"report_id": "rpt-1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["format"] == "PDF"

    @pytest.mark.asyncio
    async def test_custom_format(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data={"id": "exp-1"})

        await powerbi.execute_action("export_report", {"report_id": "rpt-1", "format": "PPTX"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["format"] == "PPTX"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Service unavailable")

        result = await powerbi.execute_action("export_report", {"report_id": "rpt-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetExportStatus:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"status": "Running", "percentComplete": 45}
        )

        result = await powerbi.execute_action(
            "get_export_status", {"report_id": "rpt-1", "export_id": "exp-1"}, mock_context
        )

        assert result.result.data["status"] == "Running"
        assert result.result.data["percentComplete"] == 45

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"status": "Succeeded", "percentComplete": 100}
        )

        await powerbi.execute_action(
            "get_export_status", {"report_id": "rpt-1", "export_id": "exp-1", "workspace_id": "ws-1"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/reports/rpt-1/exports/exp-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action(
            "get_export_status", {"report_id": "rpt-1", "export_id": "exp-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


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
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await powerbi.execute_action("get_dashboard_tiles", {"dashboard_id": "db-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Queries ----


class TestExecuteQueries:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": [{"tables": [{"rows": [{"Revenue": 1000}]}]}]},
        )

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert len(result.result.data["results"]) == 1

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        queries = [{"query": "EVALUATE VALUES(Sales)"}]
        await powerbi.execute_action("execute_queries", {"dataset_id": "ds-1", "queries": queries}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["queries"] == queries
        assert payload["serializerSettings"]["includeNulls"] is True

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "workspace_id": "ws-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/executeQueries"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert result.result.data["results"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Query failed")

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Query failed" in result.result.message
