"""Unit tests for the Power BI integration — all actions, all branches, no real HTTP."""

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse
from powerbi import powerbi


# ---- Workspaces ----


@pytest.mark.asyncio
async def test_list_workspaces_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "id": "workspace1",
                    "name": "Test Workspace",
                    "isReadOnly": False,
                    "isOnDedicatedCapacity": False,
                    "type": "Workspace",
                }
            ]
        },
    )
    result = await powerbi.ListWorkspacesAction().execute({}, mock_context)
    assert len(result["workspaces"]) == 1
    assert result["workspaces"][0]["name"] == "Test Workspace"
    mock_context.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_list_workspaces_with_filter(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})
    result = await powerbi.ListWorkspacesAction().execute({"filter": "name eq 'Test'", "top": 10}, mock_context)
    assert "workspaces" in result
    call_args = mock_context.fetch.call_args
    assert call_args[1]["params"]["$filter"] == "name eq 'Test'"
    assert call_args[1]["params"]["$top"] == 10


@pytest.mark.asyncio
async def test_get_workspace_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"id": "workspace1", "name": "Test Workspace", "isReadOnly": False},
    )
    result = await powerbi.GetWorkspaceAction().execute({"workspace_id": "workspace1"}, mock_context)
    assert result["workspace"]["name"] == "Test Workspace"


# ---- Datasets ----


@pytest.mark.asyncio
async def test_list_datasets_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "id": "dataset1",
                    "name": "Sales Dataset",
                    "configuredBy": "user@example.com",
                    "isRefreshable": True,
                    "isEffectiveIdentityRequired": False,
                    "isEffectiveIdentityRolesRequired": False,
                    "isOnPremGatewayRequired": False,
                }
            ]
        },
    )
    result = await powerbi.ListDatasetsAction().execute({"workspace_id": "workspace1"}, mock_context)
    assert len(result["datasets"]) == 1
    assert result["datasets"][0]["name"] == "Sales Dataset"
    assert result["datasets"][0]["isRefreshable"] is True


@pytest.mark.asyncio
async def test_list_datasets_without_workspace(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})
    result = await powerbi.ListDatasetsAction().execute({}, mock_context)
    assert "datasets" in result
    url = mock_context.fetch.call_args[0][0]
    assert "/datasets" in url
    assert "/groups/" not in url


@pytest.mark.asyncio
async def test_refresh_dataset_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)
    result = await powerbi.RefreshDatasetAction().execute(
        {"dataset_id": "dataset1", "workspace_id": "workspace1", "notify_option": "MailOnFailure"}, mock_context
    )
    assert "message" in result
    call_args = mock_context.fetch.call_args
    assert "refreshes" in call_args[0][0]
    assert call_args[1]["method"] == "POST"
    assert call_args[1]["json"]["notifyOption"] == "MailOnFailure"


@pytest.mark.asyncio
async def test_refresh_dataset_with_enhanced_parameters(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)
    result = await powerbi.RefreshDatasetAction().execute(
        {
            "dataset_id": "dataset1",
            "type": "Full",
            "commit_mode": "Transactional",
            "max_parallelism": 4,
            "retry_count": 3,
        },
        mock_context,
    )
    assert "message" in result
    json_data = mock_context.fetch.call_args[1]["json"]
    assert json_data["type"] == "Full"
    assert json_data["commitMode"] == "Transactional"
    assert json_data["maxParallelism"] == 4
    assert json_data["retryCount"] == 3


@pytest.mark.asyncio
async def test_get_refresh_history_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "refreshType": "ViaApi",
                    "startTime": "2024-08-01T10:00:00Z",
                    "endTime": "2024-08-01T10:05:00Z",
                    "status": "Completed",
                    "requestId": "req123",
                }
            ]
        },
    )
    result = await powerbi.GetRefreshHistoryAction().execute(
        {"dataset_id": "dataset1", "workspace_id": "workspace1", "top": 5}, mock_context
    )
    assert len(result["refreshes"]) == 1
    assert result["refreshes"][0]["status"] == "Completed"
    assert result["refreshes"][0]["refreshType"] == "ViaApi"


# ---- Reports ----


@pytest.mark.asyncio
async def test_list_reports_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "id": "report1",
                    "name": "Sales Report",
                    "webUrl": "https://app.powerbi.com/reports/report1",
                    "embedUrl": "https://app.powerbi.com/reportEmbed?reportId=report1",
                    "datasetId": "dataset1",
                }
            ]
        },
    )
    result = await powerbi.ListReportsAction().execute({"workspace_id": "workspace1"}, mock_context)
    assert len(result["reports"]) == 1
    assert result["reports"][0]["name"] == "Sales Report"


@pytest.mark.asyncio
async def test_get_report_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"id": "report1", "name": "Sales Report", "datasetId": "dataset1"},
    )
    result = await powerbi.GetReportAction().execute(
        {"report_id": "report1", "workspace_id": "workspace1"}, mock_context
    )
    assert result["report"]["name"] == "Sales Report"


@pytest.mark.asyncio
async def test_clone_report_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "id": "report2",
            "name": "Sales Report Copy",
            "webUrl": "https://app.powerbi.com/reports/report2",
            "embedUrl": "https://app.powerbi.com/reportEmbed?reportId=report2",
        },
    )
    result = await powerbi.CloneReportAction().execute(
        {
            "report_id": "report1",
            "name": "Sales Report Copy",
            "workspace_id": "workspace1",
            "target_workspace_id": "workspace2",
        },
        mock_context,
    )
    assert result["name"] == "Sales Report Copy"
    assert "webUrl" in result
    call_args = mock_context.fetch.call_args
    assert "Clone" in call_args[0][0]
    assert call_args[1]["method"] == "POST"
    assert call_args[1]["json"]["name"] == "Sales Report Copy"


@pytest.mark.asyncio
async def test_export_report_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data={"id": "export123"})
    result = await powerbi.ExportReportAction().execute(
        {"report_id": "report1", "workspace_id": "workspace1", "format": "PDF"}, mock_context
    )
    assert result["export_id"] == "export123"
    assert mock_context.fetch.call_args[1]["json"]["format"] == "PDF"


@pytest.mark.asyncio
async def test_get_export_status_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200, headers={}, data={"status": "Succeeded", "percentComplete": 100}
    )
    result = await powerbi.GetExportStatusAction().execute(
        {"report_id": "report1", "export_id": "export123", "workspace_id": "workspace1"}, mock_context
    )
    assert result["status"] == "Succeeded"
    assert result["percentComplete"] == 100


@pytest.mark.asyncio
async def test_refresh_report_success(mock_context):
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"id": "report1", "name": "Sales Report", "datasetId": "dataset1"}),
        FetchResponse(status=202, headers={}, data=None),
    ]
    result = await powerbi.RefreshReportAction().execute(
        {"report_id": "report1", "workspace_id": "workspace1", "notify_option": "MailOnFailure"}, mock_context
    )
    assert result["dataset_id"] == "dataset1"
    assert "message" in result
    assert mock_context.fetch.call_count == 2


@pytest.mark.asyncio
async def test_refresh_report_no_dataset(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200, headers={}, data={"id": "report1", "name": "Sales Report"}
    )
    result = await powerbi.RefreshReportAction().execute(
        {"report_id": "report1", "workspace_id": "workspace1"}, mock_context
    )
    assert isinstance(result, ActionError)
    assert "dataset" in result.message.lower()


@pytest.mark.asyncio
async def test_get_report_datasources_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "datasourceType": "Sql",
                    "datasourceId": "datasource1",
                    "gatewayId": "gateway1",
                    "name": "SQL Server",
                    "connectionString": "Server=localhost;Database=Sales",
                    "connectionDetails": {"server": "localhost", "database": "Sales"},
                }
            ]
        },
    )
    result = await powerbi.GetReportDatasourcesAction().execute(
        {"report_id": "report1", "workspace_id": "workspace1"}, mock_context
    )
    assert len(result["datasources"]) == 1
    assert result["datasources"][0]["datasourceType"] == "Sql"
    assert "connectionDetails" in result["datasources"][0]


# ---- Dashboards ----


@pytest.mark.asyncio
async def test_list_dashboards_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "id": "dashboard1",
                    "displayName": "Sales Dashboard",
                    "isReadOnly": False,
                    "embedUrl": "https://app.powerbi.com/dashboardEmbed?dashboardId=dashboard1",
                }
            ]
        },
    )
    result = await powerbi.ListDashboardsAction().execute({"workspace_id": "workspace1"}, mock_context)
    assert len(result["dashboards"]) == 1
    assert result["dashboards"][0]["displayName"] == "Sales Dashboard"


@pytest.mark.asyncio
async def test_get_dashboard_tiles_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "value": [
                {
                    "id": "tile1",
                    "title": "Revenue Chart",
                    "embedUrl": "https://app.powerbi.com/tileEmbed?tileId=tile1",
                    "datasetId": "dataset1",
                    "reportId": "report1",
                }
            ]
        },
    )
    result = await powerbi.GetDashboardTilesAction().execute(
        {"dashboard_id": "dashboard1", "workspace_id": "workspace1"}, mock_context
    )
    assert len(result["tiles"]) == 1
    assert result["tiles"][0]["title"] == "Revenue Chart"


# ---- Queries ----


@pytest.mark.asyncio
async def test_execute_queries_success(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={"results": [{"tables": [{"rows": [{"Column1": "Value1", "Column2": 100}]}]}]},
    )
    result = await powerbi.ExecuteQueriesAction().execute(
        {
            "dataset_id": "dataset1",
            "workspace_id": "workspace1",
            "queries": [{"query": "EVALUATE VALUES('Table'[Column])"}],
        },
        mock_context,
    )
    assert len(result["results"]) == 1
    call_args = mock_context.fetch.call_args
    assert "executeQueries" in call_args[0][0]
    assert call_args[1]["method"] == "POST"


# ---- Error handling ----


@pytest.mark.asyncio
async def test_error_handling(mock_context):
    mock_context.fetch.side_effect = Exception("API Error")
    result = await powerbi.ListWorkspacesAction().execute({}, mock_context)
    assert isinstance(result, ActionError)
    assert result.message == "API Error"
