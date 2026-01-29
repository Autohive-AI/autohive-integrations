"""
Unit tests for Microsoft Excel integration.
These tests focus on testing the integration logic by mocking all external dependencies.
"""
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Any, Dict


class MockExecutionContext:
    def __init__(self, access_token: str = "test_token"):
        self.auth = {
            'credentials': {
                'access_token': access_token
            }
        }
        self.fetch = AsyncMock()


class MockActionHandler:
    async def execute(self, inputs: Dict[str, Any], context: MockExecutionContext):
        pass


class MockIntegration:
    def __init__(self):
        self._actions = {}

    @classmethod
    def load(cls):
        return cls()

    def action(self, action_name):
        def decorator(handler_class):
            self._actions[action_name] = handler_class
            return handler_class
        return decorator


class MockActionResult:
    def __init__(self, data: Dict[str, Any], cost_usd: float = 0.0):
        self.data = data
        self.cost_usd = cost_usd


sdk_mock = Mock()
sdk_mock.Integration = MockIntegration
sdk_mock.ExecutionContext = MockExecutionContext
sdk_mock.ActionHandler = MockActionHandler
sdk_mock.ActionResult = MockActionResult
sys.modules['autohive_integrations_sdk'] = sdk_mock

integration_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, integration_root)

from microsoft_excel import (
    ListWorkbooks,
    GetWorkbook,
    ListWorksheets,
    ReadRange,
    WriteRange,
    ListTables,
    GetTableData,
    AddTableRow,
    CreateWorksheet,
    DeleteWorksheet,
    CreateTable,
    UpdateTableRow,
    DeleteTableRow,
    SortRange,
    ApplyFilter,
    ClearFilter,
    GetUsedRange,
    FormatRange,
)


def create_mock_response(status_code: int, json_data: dict):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    return mock_resp


class TestMicrosoftExcelIntegration:
    """Test cases for Microsoft Excel integration functionality"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.context = MockExecutionContext()

    async def test_list_workbooks_success(self):
        """Test successful listing of workbooks"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [
                {"id": "workbook1", "name": "Report.xlsx", "webUrl": "https://...", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}},
                {"id": "workbook2", "name": "Data.xlsx", "webUrl": "https://...", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}}
            ]
        })

        action = ListWorkbooks()
        result = await action.execute({}, self.context)

        assert result.data["result"] is True
        assert len(result.data["workbooks"]) == 2
        assert result.data["workbooks"][0]["name"] == "Report.xlsx"

    async def test_list_workbooks_with_filter(self):
        """Test listing workbooks with name filter"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [
                {"id": "workbook1", "name": "Sales Report.xlsx", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}}
            ]
        })

        action = ListWorkbooks()
        result = await action.execute({"name_contains": "Sales"}, self.context)

        assert result.data["result"] is True
        assert len(result.data["workbooks"]) == 1

    async def test_list_workbooks_api_error(self):
        """Test error handling for API errors"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_resp.json.return_value = {"error": {"message": "Unauthorized"}}
        self.context.fetch.return_value = mock_resp

        action = ListWorkbooks()
        result = await action.execute({}, self.context)

        assert result.data["result"] is False
        assert "401" in result.data["error"]

    async def test_list_workbooks_with_pagination(self):
        """Test listing workbooks with pagination"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [{"id": "wb1", "name": "Test.xlsx", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/..."
        })

        action = ListWorkbooks()
        result = await action.execute({"page_size": 10}, self.context)

        assert result.data["result"] is True
        assert "next_page_token" in result.data

    async def test_get_workbook_success(self):
        """Test getting workbook metadata"""
        self.context.fetch.side_effect = [
            create_mock_response(200, {
                "id": "workbook123",
                "name": "Test.xlsx",
                "webUrl": "https://...",
                "lastModifiedDateTime": "2024-01-01T00:00:00Z"
            }),
            create_mock_response(200, {
                "value": [
                    {"id": "ws1", "name": "Sheet1", "position": 0, "visibility": "Visible"}
                ]
            }),
            create_mock_response(200, {
                "value": [
                    {"id": "1", "name": "Table1", "showHeaders": True}
                ]
            }),
            create_mock_response(200, {
                "value": [
                    {"name": "MyRange", "value": "A1:B10"}
                ]
            })
        ]

        action = GetWorkbook()
        result = await action.execute({"workbook_id": "workbook123"}, self.context)

        assert result.data["result"] is True
        assert len(result.data["worksheets"]) == 1
        assert len(result.data["tables"]) == 1
        assert len(result.data["named_ranges"]) == 1

    async def test_list_worksheets_success(self):
        """Test listing worksheets"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [
                {"id": "ws1", "name": "Sheet1", "position": 0, "visibility": "Visible"},
                {"id": "ws2", "name": "Sheet2", "position": 1, "visibility": "Visible"}
            ]
        })

        action = ListWorksheets()
        result = await action.execute({"workbook_id": "workbook123"}, self.context)

        assert result.data["result"] is True
        assert len(result.data["worksheets"]) == 2

    async def test_read_range_success(self):
        """Test reading a range of cells"""
        self.context.fetch.return_value = create_mock_response(200, {
            "address": "Sheet1!A1:B2",
            "values": [["Name", "Value"], ["Test", 123]],
            "rowCount": 2,
            "columnCount": 2
        })

        action = ReadRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:B2"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["values"] == [["Name", "Value"], ["Test", 123]]
        assert result.data["row_count"] == 2
        assert result.data["column_count"] == 2

    async def test_read_range_not_found(self):
        """Test error when worksheet not found"""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Worksheet not found"
        mock_resp.json.return_value = {"error": {"message": "Worksheet not found"}}
        self.context.fetch.return_value = mock_resp

        action = ReadRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "NonExistent",
            "range": "A1:B2"
        }, self.context)

        assert result.data["result"] is False
        assert "404" in result.data["error"]

    async def test_write_range_success(self):
        """Test writing values to a range"""
        self.context.fetch.return_value = create_mock_response(200, {
            "address": "Sheet1!A1:B2"
        })

        action = WriteRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:B2",
            "values": [["Name", "Value"], ["Test", 123]]
        }, self.context)

        assert result.data["result"] is True
        assert result.data["updated_rows"] == 2
        assert result.data["updated_columns"] == 2
        assert result.data["updated_cells"] == 4

    async def test_list_tables_success(self):
        """Test listing tables in a workbook"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [
                {"id": "1", "name": "Table1", "showHeaders": True, "showTotals": False}
            ]
        })

        action = ListTables()
        result = await action.execute({"workbook_id": "workbook123"}, self.context)

        assert result.data["result"] is True
        assert len(result.data["tables"]) == 1
        assert result.data["tables"][0]["name"] == "Table1"

    async def test_list_tables_by_worksheet(self):
        """Test listing tables filtered by worksheet"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [{"id": "1", "name": "Table1"}]
        })

        action = ListTables()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1"
        }, self.context)

        assert result.data["result"] is True
        call_url = self.context.fetch.call_args[0][0]
        assert "worksheets" in call_url

    async def test_get_table_data_success(self):
        """Test getting table data with headers"""
        self.context.fetch.side_effect = [
            create_mock_response(200, {
                "values": [["Name", "Email", "Status"]]
            }),
            create_mock_response(200, {
                "values": [
                    ["John", "john@example.com", "Active"],
                    ["Jane", "jane@example.com", "Pending"]
                ]
            })
        ]

        action = GetTableData()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["headers"] == ["Name", "Email", "Status"]
        assert len(result.data["rows"]) == 2
        assert result.data["rows"][0]["Name"] == "John"

    async def test_get_table_data_with_select_columns(self):
        """Test getting table data with column selection"""
        self.context.fetch.side_effect = [
            create_mock_response(200, {
                "values": [["Name", "Email", "Status"]]
            }),
            create_mock_response(200, {
                "values": [
                    ["John", "john@example.com", "Active"]
                ]
            })
        ]

        action = GetTableData()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "select_columns": ["Name", "Status"]
        }, self.context)

        assert result.data["result"] is True
        assert "Name" in result.data["rows"][0]
        assert "Status" in result.data["rows"][0]
        assert "Email" not in result.data["rows"][0]

    async def test_add_table_row_success(self):
        """Test adding rows to a table"""
        self.context.fetch.side_effect = [
            create_mock_response(201, {}),
            create_mock_response(200, {"address": "Table1!A1:C5"})
        ]

        action = AddTableRow()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "rows": [["New", "new@example.com", "Active"]]
        }, self.context)

        assert result.data["result"] is True
        assert result.data["added_rows"] == 1

    async def test_add_table_row_with_index(self):
        """Test adding rows at specific index"""
        self.context.fetch.side_effect = [
            create_mock_response(201, {}),
            create_mock_response(200, {"address": "A1:C10"})
        ]

        action = AddTableRow()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "rows": [["New Row"]],
            "index": 0
        }, self.context)

        assert result.data["result"] is True
        assert result.data["added_rows"] == 1

    async def test_create_worksheet_success(self):
        """Test creating a new worksheet"""
        self.context.fetch.return_value = create_mock_response(201, {
            "id": "ws_new",
            "name": "NewSheet",
            "position": 2,
            "visibility": "Visible"
        })

        action = CreateWorksheet()
        result = await action.execute({
            "workbook_id": "workbook123",
            "name": "NewSheet"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["worksheet"]["name"] == "NewSheet"

    async def test_delete_worksheet_success(self):
        """Test deleting a worksheet"""
        self.context.fetch.return_value = create_mock_response(204, {})

        action = DeleteWorksheet()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet2"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["deleted"] is True

    async def test_create_table_success(self):
        """Test creating a table from a range"""
        self.context.fetch.return_value = create_mock_response(201, {
            "id": "1",
            "name": "Table1",
            "showHeaders": True
        })

        action = CreateTable()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:C5",
            "has_headers": True
        }, self.context)

        assert result.data["result"] is True
        assert result.data["table"]["name"] == "Table1"

    async def test_update_table_row_success(self):
        """Test updating a table row"""
        self.context.fetch.return_value = create_mock_response(200, {
            "values": [["Updated", "updated@example.com", "Inactive"]]
        })

        action = UpdateTableRow()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "row_index": 0,
            "values": ["Updated", "updated@example.com", "Inactive"]
        }, self.context)

        assert result.data["result"] is True

    async def test_delete_table_row_success(self):
        """Test deleting a table row"""
        self.context.fetch.return_value = create_mock_response(204, {})

        action = DeleteTableRow()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "row_index": 0
        }, self.context)

        assert result.data["result"] is True
        assert result.data["deleted"] is True

    async def test_sort_range_success(self):
        """Test sorting a range"""
        self.context.fetch.return_value = create_mock_response(200, {})

        action = SortRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:C10",
            "sort_fields": [{"column_index": 0, "ascending": True}]
        }, self.context)

        assert result.data["result"] is True
        assert result.data["sorted"] is True

    async def test_sort_range_multiple_columns(self):
        """Test sorting by multiple columns"""
        self.context.fetch.return_value = create_mock_response(200, {})

        action = SortRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:C10",
            "sort_fields": [
                {"column_index": 0, "ascending": True},
                {"column_index": 1, "ascending": False}
            ]
        }, self.context)

        assert result.data["result"] is True
        call_body = self.context.fetch.call_args[1]["json"]
        assert len(call_body["fields"]) == 2

    async def test_apply_filter_success(self):
        """Test applying a filter to a table"""
        self.context.fetch.side_effect = [
            create_mock_response(200, {
                "value": [
                    {"id": "col1", "name": "Status"},
                    {"id": "col2", "name": "Name"}
                ]
            }),
            create_mock_response(200, {})
        ]

        action = ApplyFilter()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "column_index": 0,
            "filter_criteria": {"filterOn": "Values", "values": ["Active"]}
        }, self.context)

        assert result.data["result"] is True
        assert result.data["filtered"] is True

    async def test_apply_filter_column_out_of_range(self):
        """Test applying filter with invalid column index"""
        self.context.fetch.return_value = create_mock_response(200, {
            "value": [{"id": "col1", "name": "Status"}]
        })

        action = ApplyFilter()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1",
            "column_index": 5,
            "filter_criteria": {"filterOn": "Values", "values": ["Active"]}
        }, self.context)

        assert result.data["result"] is False
        assert "out of range" in result.data["error"]

    async def test_clear_filter_success(self):
        """Test clearing filters from a table"""
        self.context.fetch.return_value = create_mock_response(200, {})

        action = ClearFilter()
        result = await action.execute({
            "workbook_id": "workbook123",
            "table_name": "Table1"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["cleared"] is True

    async def test_get_used_range_success(self):
        """Test getting the used range of a worksheet"""
        self.context.fetch.return_value = create_mock_response(200, {
            "address": "Sheet1!A1:D10",
            "rowCount": 10,
            "columnCount": 4,
            "values": [["A", "B", "C", "D"]]
        })

        action = GetUsedRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1"
        }, self.context)

        assert result.data["result"] is True
        assert result.data["range"] == "Sheet1!A1:D10"
        assert result.data["row_count"] == 10
        assert result.data["column_count"] == 4

    async def test_get_used_range_values_only(self):
        """Test getting used range with values only"""
        self.context.fetch.return_value = create_mock_response(200, {
            "address": "Sheet1!A1:B5",
            "rowCount": 5,
            "columnCount": 2
        })

        action = GetUsedRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "values_only": True
        }, self.context)

        assert result.data["result"] is True
        call_url = self.context.fetch.call_args[0][0]
        assert "valuesOnly=true" in call_url

    async def test_format_range_success(self):
        """Test formatting a range"""
        self.context.fetch.return_value = create_mock_response(200, {})

        action = FormatRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "A1:D1",
            "format": {
                "font": {"bold": True, "color": "#FFFFFF"},
                "fill": {"color": "#4472C4"},
                "horizontalAlignment": "Center"
            }
        }, self.context)

        assert result.data["result"] is True
        assert result.data["formatted"] is True

    async def test_format_range_with_number_format(self):
        """Test formatting with number format"""
        self.context.fetch.return_value = create_mock_response(200, {})

        action = FormatRange()
        result = await action.execute({
            "workbook_id": "workbook123",
            "worksheet_name": "Sheet1",
            "range": "B2:B10",
            "format": {
                "numberFormat": "#,##0.00"
            }
        }, self.context)

        assert result.data["result"] is True
        assert result.data["formatted"] is True

    async def test_exception_handling(self):
        """Test handling of unexpected exceptions"""
        self.context.fetch.side_effect = Exception("Network error")

        action = ListWorkbooks()
        result = await action.execute({}, self.context)

        assert result.data["result"] is False
        assert "Network error" in result.data["error"]


async def run_all_tests():
    """Run all test methods and report results"""
    test_instance = TestMicrosoftExcelIntegration()

    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]

    print("Running Microsoft Excel integration tests...")
    print("=" * 50)

    passed = 0
    failed = 0

    for method_name in test_methods:
        test_method = getattr(test_instance, method_name)
        try:
            test_instance.setup_method()
            if asyncio.iscoroutinefunction(test_method):
                await test_method()
            else:
                test_method()
            passed += 1
            print(f"PASS {method_name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {method_name}: {str(e)}")

    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("All tests passed!")
        return True
    else:
        print(f"{failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    if not success:
        exit(1)
    print("\nMicrosoft Excel integration unit tests completed successfully!")
