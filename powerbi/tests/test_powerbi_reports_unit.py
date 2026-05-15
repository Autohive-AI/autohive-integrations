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
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("list_reports", {}, mock_context)

        assert result.result.data["reports"] == []

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
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_report", {"report_id": "rpt-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/reports/rpt-1"

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
    async def test_makes_two_requests(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"id": "rpt-1", "name": "Sales", "datasetId": "ds-1"}),
            FetchResponse(status=202, headers={}, data=None),
        ]

        await powerbi.execute_action("refresh_report", {"report_id": "rpt-1"}, mock_context)

        assert mock_context.fetch.call_count == 2

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
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"status": "Succeeded", "percentComplete": 100}
        )

        await powerbi.execute_action("get_export_status", {"report_id": "rpt-1", "export_id": "exp-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/reports/rpt-1/exports/exp-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action(
            "get_export_status", {"report_id": "rpt-1", "export_id": "exp-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
