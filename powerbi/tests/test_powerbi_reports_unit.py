import base64
import json
import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("powerbi_mod", os.path.join(_parent, "powerbi.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

powerbi = _mod.powerbi
CreateReportAction = _mod.CreateReportAction

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


FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"

SAMPLE_PAGES = [
    {
        "name": "Overview",
        "visuals": [
            {"type": "table", "table": "Sales", "columns": ["Region", "Amount"], "title": "Sales by Region"},
        ],
    }
]


class TestCreateReport:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "id": "rpt-new",
                "displayName": "New Report",
                "workspaceId": "ws-1",
                "webUrl": "https://app.fabric.microsoft.com/rpt-new",
            },
        )

        result = await powerbi.execute_action(
            "create_report",
            {
                "display_name": "New Report",
                "workspace_id": "ws-1",
                "dataset_id": "ds-1",
                "pages": SAMPLE_PAGES,
            },
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["id"] == "rpt-new"
        assert result.result.data["display_name"] == "New Report"
        assert result.result.data["workspace_id"] == "ws-1"
        assert result.result.data["web_url"] == "https://app.fabric.microsoft.com/rpt-new"

    @pytest.mark.asyncio
    async def test_missing_webUrl_displayName_workspaceId_falls_back_to_inputs(self, mock_context):
        # Regression test: live testing showed the Fabric create/result payload only
        # reliably includes "id" - webUrl/displayName/workspaceId can come back missing
        # even though the report was created successfully, which previously failed
        # output schema validation (required string, got None).
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"id": "rpt-new"})

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["id"] == "rpt-new"
        assert result.result.data["display_name"] == "New Report"
        assert result.result.data["workspace_id"] == "ws-1"
        assert result.result.data["web_url"] == "https://app.powerbi.com/groups/ws-1/reports/rpt-new"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={})

        await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0] == f"{FABRIC_API_BASE}/workspaces/ws-1/reports"
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_payload_binds_dataset_and_display_name(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={})

        await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["displayName"] == "New Report"
        parts = payload["definition"]["parts"]
        paths = [p["path"] for p in parts]
        # Confirmed via get_report_definition against a real, working report in this
        # tenant: only these 3 files exist. The newer decomposed PBIR layout
        # (version.json, pages/*.json, visuals/*.json) is not what this tenant expects.
        assert paths == [".platform", "definition.pbir", "report.json"]

    @pytest.mark.asyncio
    async def test_report_json_has_one_section_per_page_and_stringified_config(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={})

        two_page_spec = [
            {"name": "Page 1", "visuals": [{"type": "table", "table": "Sales", "columns": ["Region"]}]},
            {"name": "Page 2", "visuals": [{"type": "bar", "table": "Sales", "columns": ["Region", "Amount"]}]},
        ]
        await powerbi.execute_action(
            "create_report",
            {"display_name": "Multi-page", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": two_page_spec},
            mock_context,
        )

        parts = mock_context.fetch.call_args.kwargs["json"]["definition"]["parts"]
        report_part = next(p for p in parts if p["path"] == "report.json")
        report_json = json.loads(base64.b64decode(report_part["payload"]).decode("utf-8"))

        assert len(report_json["sections"]) == 2
        assert report_json["sections"][0]["displayName"] == "Page 1"
        assert report_json["sections"][1]["displayName"] == "Page 2"
        assert len(report_json["sections"][1]["visualContainers"]) == 1

        # config/filters must be JSON-stringified, not inline objects, matching the
        # real report's shape - this is what broke the earlier decomposed-PBIR attempt.
        assert isinstance(report_json["config"], str)
        assert isinstance(report_json["filters"], str)
        assert isinstance(report_json["sections"][0]["config"], str)
        visual = report_json["sections"][1]["visualContainers"][0]
        assert isinstance(visual["config"], str)
        assert isinstance(visual["filters"], str)
        visual_config = json.loads(visual["config"])
        assert visual_config["singleVisual"]["visualType"] == "barChart"

    @pytest.mark.asyncio
    async def test_no_pages_returns_success_with_empty_sections(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"id": "rpt-empty"})

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "Empty", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": []},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        parts = mock_context.fetch.call_args.kwargs["json"]["definition"]["parts"]
        report_part = next(p for p in parts if p["path"] == "report.json")
        report_json = json.loads(base64.b64decode(report_part["payload"]).decode("utf-8"))
        assert report_json["sections"] == []

    @pytest.mark.asyncio
    async def test_empty_columns_on_a_visual_rejected_by_schema(self, mock_context):
        pages_with_empty_columns = [
            {
                "name": "Overview",
                "visuals": [{"type": "card", "table": "Sales", "columns": [], "title": "Broken"}],
            }
        ]
        result = await powerbi.execute_action(
            "create_report",
            {
                "display_name": "New Report",
                "workspace_id": "ws-1",
                "dataset_id": "ds-1",
                "pages": pages_with_empty_columns,
            },
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_columns_on_a_visual_rejected_by_code_guard(self, mock_context):
        # Belt-and-suspenders: the action itself also rejects empty columns, in case
        # it's ever invoked directly (bypassing config.json schema validation). Live
        # testing showed an empty columns list silently produces a blank visual with no
        # data bound to it - the report imports "successfully" but has nothing on it.
        pages_with_empty_columns = [
            {
                "name": "Overview",
                "visuals": [{"type": "card", "table": "Sales", "columns": [], "title": "Broken"}],
            }
        ]
        result = await CreateReportAction().execute(
            {
                "display_name": "New Report",
                "workspace_id": "ws-1",
                "dataset_id": "ds-1",
                "pages": pages_with_empty_columns,
            },
            mock_context,
        )

        expected_message = (
            "Visual on page 'Overview' has no columns - an empty columns list silently "
            "produces a blank visual with no data bound to it. Use get_dataset_schema to "
            "discover real column names first."
        )
        assert result.message == expected_message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message

    @pytest.mark.asyncio
    async def test_202_response_with_none_data_does_not_crash(self, mock_context):
        # Regression test: a 202 Accepted with no body used to crash with
        # AttributeError: 'NoneType' object has no attribute 'get'.
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=202, headers={"Location": "https://api.fabric.microsoft.com/v1/operations/op-1"}, data=None
            ),
            FetchResponse(status=200, headers={}, data={"status": "Succeeded"}),
            FetchResponse(
                status=200,
                headers={},
                data={"id": "rpt-new", "displayName": "New Report", "workspaceId": "ws-1", "webUrl": "https://x"},
            ),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await powerbi.execute_action(
                "create_report",
                {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
                mock_context,
            )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["id"] == "rpt-new"

    @pytest.mark.asyncio
    async def test_202_polls_operation_and_fetches_result(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=202, headers={"Location": "https://api.fabric.microsoft.com/v1/operations/op-1"}, data={}
            ),
            FetchResponse(status=200, headers={}, data={"status": "Running"}),
            FetchResponse(status=200, headers={}, data={"status": "Succeeded"}),
            FetchResponse(
                status=200,
                headers={},
                data={"id": "rpt-new", "displayName": "New Report", "workspaceId": "ws-1", "webUrl": "https://x"},
            ),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await powerbi.execute_action(
                "create_report",
                {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
                mock_context,
            )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["id"] == "rpt-new"
        assert (
            mock_context.fetch.call_args_list[-1].args[0]
            == "https://api.fabric.microsoft.com/v1/operations/op-1/result"
        )

    @pytest.mark.asyncio
    async def test_202_operation_failed_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=202, headers={"Location": "https://api.fabric.microsoft.com/v1/operations/op-1"}, data={}
            ),
            FetchResponse(
                status=200, headers={}, data={"status": "Failed", "error": {"message": "Invalid definition"}}
            ),
        ]

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid definition" in result.result.message

    @pytest.mark.asyncio
    async def test_202_without_location_header_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Location header" in result.result.message

    @pytest.mark.asyncio
    async def test_201_with_none_data_does_not_crash(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=None)

        result = await powerbi.execute_action(
            "create_report",
            {"display_name": "New Report", "workspace_id": "ws-1", "dataset_id": "ds-1", "pages": SAMPLE_PAGES},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "no report ID" in result.result.message


class TestGetReportDefinition:
    @pytest.mark.asyncio
    async def test_happy_path_decodes_parts(self, mock_context):
        payload = base64.b64encode(b'{"version": "2.0.0"}').decode("utf-8")
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"definition": {"parts": [{"path": "definition/version.json", "payload": payload}]}},
        )

        result = await powerbi.execute_action(
            "get_report_definition", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["parts"] == [{"path": "definition/version.json", "content": '{"version": "2.0.0"}'}]

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"definition": {"parts": []}})

        await powerbi.execute_action(
            "get_report_definition", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0] == f"{FABRIC_API_BASE}/workspaces/ws-1/reports/rpt-1/getDefinition"
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_202_polls_and_fetches_result(self, mock_context):
        payload = base64.b64encode(b'{"version": "2.0.0"}').decode("utf-8")
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=202, headers={"Location": "https://api.fabric.microsoft.com/v1/operations/op-1"}, data={}
            ),
            FetchResponse(status=200, headers={}, data={"status": "Succeeded"}),
            FetchResponse(
                status=200,
                headers={},
                data={"definition": {"parts": [{"path": "definition/version.json", "payload": payload}]}},
            ),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await powerbi.execute_action(
                "get_report_definition", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
            )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["parts"][0]["path"] == "definition/version.json"

    @pytest.mark.asyncio
    async def test_undecodable_payload_returns_null_content(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"definition": {"parts": [{"path": "icon.png", "payload": "not-valid-base64-utf8-\xff"}]}},
        )

        result = await powerbi.execute_action(
            "get_report_definition", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["parts"][0]["content"] is None

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await powerbi.execute_action(
            "get_report_definition", {"report_id": "rpt-1", "workspace_id": "ws-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message
