"""
Power BI Integration Test Suite

This module contains comprehensive unit tests for the Power BI integration,
covering all action handlers and their various edge cases.

Test Categories:
- Workspace Management: List, Get
- Dataset Operations: List, Get, Refresh, Refresh History
- Report Management: List, Get, Clone, Export, Export Status, Refresh, Datasources
- Dashboard Operations: List, Get, Get Tiles
- Query Execution: Execute DAX/MDX queries
- Error Handling: General exception handling

Each test uses mocked API responses to verify action handler behavior
without making actual API calls to Power BI.
"""

import unittest
from unittest.mock import AsyncMock, Mock, patch
import json
from context import powerbi


class TestPowerBIIntegration(unittest.TestCase):
    """
    Test suite for Power BI integration action handlers.

    This test class validates all Power BI integration actions using mocked
    ExecutionContext to simulate API responses without external dependencies.
    """

    def setUp(self):
        """
        Set up test fixtures before each test method.

        Creates a mock ExecutionContext with an AsyncMock fetch method
        to simulate Power BI REST API calls.
        """
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()

    # ========================================================================
    # WORKSPACE TESTS
    # ========================================================================

    async def test_list_workspaces_success(self):
        """
        Test successful workspace listing without filters.

        Verifies that the ListWorkspacesAction correctly processes and returns
        workspace data from the Power BI API.
        """
        # Mock successful API response
        mock_response = {
            "value": [
                {
                    "id": "workspace1",
                    "name": "Test Workspace",
                    "isReadOnly": False,
                    "isOnDedicatedCapacity": False,
                    "type": "Workspace"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        # Create action handler
        handler = powerbi.ListWorkspacesAction()

        # Test inputs
        inputs = {}

        # Execute action
        result = await handler.execute(inputs, self.mock_context)

        # Verify result
        self.assertTrue(result["result"])
        self.assertEqual(len(result["workspaces"]), 1)
        self.assertEqual(result["workspaces"][0]["name"], "Test Workspace")

        # Verify API call
        self.mock_context.fetch.assert_called_once()

    async def test_list_workspaces_with_filter(self):
        """
        Test workspace listing with OData filter and top parameters.

        Verifies that filter and pagination parameters are correctly passed
        to the Power BI API when listing workspaces.
        """
        mock_response = {"value": []}
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ListWorkspacesAction()
        inputs = {
            "filter": "name eq 'Test'",
            "top": 10
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        # Verify params were passed
        call_args = self.mock_context.fetch.call_args
        self.assertIn("params", call_args[1])
        self.assertEqual(call_args[1]["params"]["$filter"], "name eq 'Test'")
        self.assertEqual(call_args[1]["params"]["$top"], 10)

    async def test_get_workspace_success(self):
        """
        Test retrieval of a single workspace by ID.

        Verifies that workspace details are correctly fetched and returned.
        """
        mock_response = {
            "id": "workspace1",
            "name": "Test Workspace",
            "isReadOnly": False
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetWorkspaceAction()
        inputs = {"workspace_id": "workspace1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["workspace"]["name"], "Test Workspace")

    # ========================================================================
    # DATASET TESTS
    # ========================================================================

    async def test_list_datasets_success(self):
        """
        Test successful dataset listing within a workspace.

        Verifies that dataset information including refresh capabilities
        and configuration is correctly returned.
        """
        mock_response = {
            "value": [
                {
                    "id": "dataset1",
                    "name": "Sales Dataset",
                    "configuredBy": "user@example.com",
                    "isRefreshable": True,
                    "isEffectiveIdentityRequired": False,
                    "isEffectiveIdentityRolesRequired": False,
                    "isOnPremGatewayRequired": False
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ListDatasetsAction()
        inputs = {"workspace_id": "workspace1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["datasets"]), 1)
        self.assertEqual(result["datasets"][0]["name"], "Sales Dataset")
        self.assertTrue(result["datasets"][0]["isRefreshable"])

    async def test_list_datasets_without_workspace(self):
        """
        Test dataset listing without specifying a workspace.

        Verifies that datasets can be listed from the user's scope
        without targeting a specific workspace.
        """
        mock_response = {"value": []}
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ListDatasetsAction()
        inputs = {}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        # Verify the URL doesn't include workspace/groups
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/datasets", call_args[0][0])
        self.assertNotIn("/groups/", call_args[0][0])

    async def test_refresh_dataset_success(self):
        """
        Test triggering a dataset refresh with notification options.

        Verifies that refresh requests are properly formatted and submitted
        with the correct notify_option parameter.
        """
        self.mock_context.fetch.return_value = None

        handler = powerbi.RefreshDatasetAction()
        inputs = {
            "dataset_id": "dataset1",
            "workspace_id": "workspace1",
            "notify_option": "MailOnFailure"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertIn("message", result)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("refreshes", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
        self.assertEqual(call_args[1]["json"]["notifyOption"], "MailOnFailure")

    async def test_refresh_dataset_with_enhanced_parameters(self):
        """
        Test dataset refresh with advanced parameters.

        Verifies that enhanced refresh options like refresh type, commit mode,
        parallelism, and retry count are correctly passed to the API.
        """
        self.mock_context.fetch.return_value = None

        handler = powerbi.RefreshDatasetAction()
        inputs = {
            "dataset_id": "dataset1",
            "type": "Full",
            "commit_mode": "Transactional",
            "max_parallelism": 4,
            "retry_count": 3
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])

        # Verify enhanced parameters were passed
        call_args = self.mock_context.fetch.call_args
        json_data = call_args[1]["json"]
        self.assertEqual(json_data["type"], "Full")
        self.assertEqual(json_data["commitMode"], "Transactional")
        self.assertEqual(json_data["maxParallelism"], 4)
        self.assertEqual(json_data["retryCount"], 3)

    async def test_get_refresh_history_success(self):
        """
        Test retrieving dataset refresh history.

        Verifies that refresh history including status, timestamps, and request IDs
        is correctly fetched and formatted.
        """
        mock_response = {
            "value": [
                {
                    "refreshType": "ViaApi",
                    "startTime": "2024-08-01T10:00:00Z",
                    "endTime": "2024-08-01T10:05:00Z",
                    "status": "Completed",
                    "requestId": "req123"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetRefreshHistoryAction()
        inputs = {
            "dataset_id": "dataset1",
            "workspace_id": "workspace1",
            "top": 5
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["refreshes"]), 1)
        self.assertEqual(result["refreshes"][0]["status"], "Completed")
        self.assertEqual(result["refreshes"][0]["refreshType"], "ViaApi")

    # ========================================================================
    # REPORT TESTS
    # ========================================================================

    async def test_list_reports_success(self):
        """
        Test successful report listing.

        Verifies that report metadata including web URLs, embed URLs,
        and associated dataset IDs are correctly retrieved.
        """
        mock_response = {
            "value": [
                {
                    "id": "report1",
                    "name": "Sales Report",
                    "webUrl": "https://app.powerbi.com/reports/report1",
                    "embedUrl": "https://app.powerbi.com/reportEmbed?reportId=report1",
                    "datasetId": "dataset1"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ListReportsAction()
        inputs = {"workspace_id": "workspace1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["reports"]), 1)
        self.assertEqual(result["reports"][0]["name"], "Sales Report")

    async def test_get_report_success(self):
        """
        Test retrieving a single report by ID.

        Verifies that report details including associated dataset ID
        are correctly fetched and returned.
        """
        mock_response = {
            "id": "report1",
            "name": "Sales Report",
            "datasetId": "dataset1"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetReportAction()
        inputs = {
            "report_id": "report1",
            "workspace_id": "workspace1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["report"]["name"], "Sales Report")

    async def test_clone_report_success(self):
        """
        Test cloning a report to another workspace or with a different dataset.

        Verifies that report cloning requests include the correct name,
        target workspace ID, and target dataset ID parameters.
        """
        mock_response = {
            "id": "report2",
            "name": "Sales Report Copy",
            "webUrl": "https://app.powerbi.com/reports/report2",
            "embedUrl": "https://app.powerbi.com/reportEmbed?reportId=report2"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.CloneReportAction()
        inputs = {
            "report_id": "report1",
            "name": "Sales Report Copy",
            "workspace_id": "workspace1",
            "target_workspace_id": "workspace2"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["name"], "Sales Report Copy")
        self.assertIn("webUrl", result)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("Clone", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")
        self.assertEqual(call_args[1]["json"]["name"], "Sales Report Copy")

    async def test_export_report_success(self):
        """
        Test initiating a report export to PDF or other formats.

        Verifies that export requests are properly formatted with the
        desired format and return an export ID for status tracking.
        """
        mock_response = {"id": "export123"}
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ExportReportAction()
        inputs = {
            "report_id": "report1",
            "workspace_id": "workspace1",
            "format": "PDF"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["export_id"], "export123")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertEqual(call_args[1]["json"]["format"], "PDF")

    async def test_get_export_status_success(self):
        """
        Test checking the status of an ongoing report export.

        Verifies that export status including completion percentage
        and current state are correctly retrieved.
        """
        mock_response = {
            "status": "Succeeded",
            "percentComplete": 100
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetExportStatusAction()
        inputs = {
            "report_id": "report1",
            "export_id": "export123",
            "workspace_id": "workspace1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["status"], "Succeeded")
        self.assertEqual(result["percentComplete"], 100)

    # ========================================================================
    # DASHBOARD TESTS
    # ========================================================================

    async def test_list_dashboards_success(self):
        """
        Test successful dashboard listing.

        Verifies that dashboard metadata including display names,
        read-only status, and embed URLs are correctly retrieved.
        """
        mock_response = {
            "value": [
                {
                    "id": "dashboard1",
                    "displayName": "Sales Dashboard",
                    "isReadOnly": False,
                    "embedUrl": "https://app.powerbi.com/dashboardEmbed?dashboardId=dashboard1"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ListDashboardsAction()
        inputs = {"workspace_id": "workspace1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["dashboards"]), 1)
        self.assertEqual(result["dashboards"][0]["displayName"], "Sales Dashboard")

    async def test_get_dashboard_tiles_success(self):
        """
        Test retrieving tiles from a dashboard.

        Verifies that dashboard tile information including embed URLs,
        dataset IDs, and report IDs are correctly fetched.
        """
        mock_response = {
            "value": [
                {
                    "id": "tile1",
                    "title": "Revenue Chart",
                    "embedUrl": "https://app.powerbi.com/tileEmbed?tileId=tile1",
                    "datasetId": "dataset1",
                    "reportId": "report1"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetDashboardTilesAction()
        inputs = {
            "dashboard_id": "dashboard1",
            "workspace_id": "workspace1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["tiles"]), 1)
        self.assertEqual(result["tiles"][0]["title"], "Revenue Chart")

    # ========================================================================
    # QUERY EXECUTION TESTS
    # ========================================================================

    async def test_execute_queries_success(self):
        """
        Test executing DAX/MDX queries on a dataset.

        Verifies that query requests are correctly formatted and query results
        are properly returned from the Power BI dataset.
        """
        mock_response = {
            "results": [
                {
                    "tables": [
                        {
                            "rows": [
                                {"Column1": "Value1", "Column2": 100}
                            ]
                        }
                    ]
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.ExecuteQueriesAction()
        inputs = {
            "dataset_id": "dataset1",
            "workspace_id": "workspace1",
            "queries": [
                {
                    "query": "EVALUATE VALUES('Table'[Column])"
                }
            ]
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["results"]), 1)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("executeQueries", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

    # ========================================================================
    # ADVANCED REPORT TESTS
    # ========================================================================

    async def test_refresh_report_success(self):
        """
        Test refreshing a report by refreshing its underlying dataset.

        Verifies that the action correctly fetches the report's dataset ID
        and triggers a refresh operation on that dataset.
        """
        # Mock report response
        mock_report_response = {
            "id": "report1",
            "name": "Sales Report",
            "datasetId": "dataset1"
        }

        # Setup mock to return different values for different calls
        self.mock_context.fetch.side_effect = [
            mock_report_response,  # First call gets the report
            None  # Second call triggers the refresh
        ]

        handler = powerbi.RefreshReportAction()
        inputs = {
            "report_id": "report1",
            "workspace_id": "workspace1",
            "notify_option": "MailOnFailure"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["dataset_id"], "dataset1")
        self.assertIn("message", result)

        # Verify both API calls were made
        self.assertEqual(self.mock_context.fetch.call_count, 2)

    async def test_refresh_report_no_dataset(self):
        """
        Test error handling when a report has no associated dataset.

        Verifies that the action properly handles and returns an error
        when attempting to refresh a report without a linked dataset.
        """
        # Mock report response without dataset
        mock_report_response = {
            "id": "report1",
            "name": "Sales Report"
        }
        self.mock_context.fetch.return_value = mock_report_response

        handler = powerbi.RefreshReportAction()
        inputs = {
            "report_id": "report1",
            "workspace_id": "workspace1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("error", result)
        self.assertIn("dataset", result["error"].lower())

    async def test_get_report_datasources_success(self):
        """
        Test retrieving datasources connected to a report.

        Verifies that datasource information including type, connection strings,
        gateway IDs, and connection details are correctly retrieved.
        """
        mock_response = {
            "value": [
                {
                    "datasourceType": "Sql",
                    "datasourceId": "datasource1",
                    "gatewayId": "gateway1",
                    "name": "SQL Server",
                    "connectionString": "Server=localhost;Database=Sales",
                    "connectionDetails": {
                        "server": "localhost",
                        "database": "Sales"
                    }
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = powerbi.GetReportDatasourcesAction()
        inputs = {
            "report_id": "report1",
            "workspace_id": "workspace1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["datasources"]), 1)
        self.assertEqual(result["datasources"][0]["datasourceType"], "Sql")
        self.assertIn("connectionDetails", result["datasources"][0])

    # ========================================================================
    # ERROR HANDLING TESTS
    # ========================================================================

    async def test_error_handling(self):
        """
        Test general error handling across all actions.

        Verifies that exceptions from the Power BI API are properly caught,
        formatted, and returned with appropriate error messages.
        """
        # Mock API error
        self.mock_context.fetch.side_effect = Exception("API Error")

        handler = powerbi.ListWorkspacesAction()
        inputs = {}

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("error", result)
        self.assertEqual(result["error"], "API Error")

if __name__ == '__main__':
    unittest.main()
