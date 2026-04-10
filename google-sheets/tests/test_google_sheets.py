"""
Standalone unit tests for Google Sheets integration that don't rely on external dependencies.
These tests focus on testing the integration logic by mocking all external dependencies.
"""
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict

# Mock all Google API dependencies before any imports
sys.modules['googleapiclient'] = Mock()
sys.modules['googleapiclient.discovery'] = Mock()
sys.modules['googleapiclient.http'] = Mock()
sys.modules['googleapiclient.errors'] = Mock()
sys.modules['google'] = Mock()
sys.modules['google.oauth2'] = Mock()
sys.modules['google.oauth2.credentials'] = Mock()

# Create mock HttpError class
class MockHttpError(Exception):
    def __init__(self, resp, content=None):
        self.resp = resp
        self.content = content
        super().__init__(str(resp))

sys.modules['googleapiclient.errors'].HttpError = MockHttpError

# Mock the autohive integration SDK
class MockExecutionContext:
    def __init__(self, access_token: str = "test_token"):
        self.auth = {
            'credentials': {
                'access_token': access_token
            }
        }

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
            # Store the handler class for testing
            self._actions[action_name] = handler_class
            return handler_class
        return decorator

    async def execute_action(self, action_name: str, inputs: Dict[str, Any], context: MockExecutionContext):
        if action_name in self._actions:
            handler = self._actions[action_name]()
            return await handler.execute(inputs, context)
        else:
            raise ValueError(f"Action {action_name} not found")

# Mock the SDK modules
sys.modules['autohive_integrations_sdk'] = Mock()
sys.modules['autohive_integrations_sdk'].Integration = MockIntegration
sys.modules['autohive_integrations_sdk'].ExecutionContext = MockExecutionContext
sys.modules['autohive_integrations_sdk'].ActionHandler = MockActionHandler

# Change to the integration directory and add to path
integration_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, integration_root)

# Import the google_sheets module now that everything is mocked
import google_sheets

# Replace the google_sheets instance with our mock after import
google_sheets.google_sheets = MockIntegration()


class TestGoogleSheetsIntegration:
    """Test cases for Google Sheets integration functionality"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.context = MockExecutionContext()
        self.integration = google_sheets.google_sheets

    @patch('google_sheets.build')
    async def test_list_spreadsheets_success(self, mock_build):
        """Test successful listing of spreadsheets"""
        # Set up mocks
        mock_drive_service = Mock()
        mock_files = Mock()
        mock_list = Mock()

        mock_build.return_value = mock_drive_service
        mock_drive_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {'id': 'sheet1', 'name': 'Test Spreadsheet 1'},
                {'id': 'sheet2', 'name': 'Test Spreadsheet 2'}
            ],
            'nextPageToken': 'next_token'
        }

        # Execute action
        result = await google_sheets.ListSpreadsheets().execute({}, self.context)

        # Verify results
        assert result['result'] is True
        assert len(result['files']) == 2
        assert result['files'][0]['id'] == 'sheet1'
        assert result['nextPageToken'] == 'next_token'

        # Verify API calls
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_build.call_args[1]['credentials'])

    @patch('google_sheets.build')
    async def test_list_spreadsheets_with_filters(self, mock_build):
        """Test listing spreadsheets with filters applied"""
        # Set up mocks
        mock_drive_service = Mock()
        mock_files = Mock()
        mock_list = Mock()

        mock_build.return_value = mock_drive_service
        mock_drive_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {'files': []}

        inputs = {
            'name_contains': 'Test',
            'owner': 'me',
            'pageSize': 10,
            'pageToken': 'token123'
        }

        # Execute action
        await google_sheets.ListSpreadsheets().execute(inputs, self.context)

        # Verify query parameters
        call_args = mock_files.list.call_args[1]
        assert "name contains 'Test'" in call_args['q']
        assert "'me' in owners" in call_args['q']
        assert call_args['pageSize'] == 10
        assert call_args['pageToken'] == 'token123'

    @patch('google_sheets.build')
    async def test_list_spreadsheets_quote_escaping(self, mock_build):
        """Test that quotes in search strings are properly escaped"""
        mock_drive_service = Mock()
        mock_files = Mock()
        mock_list = Mock()

        mock_build.return_value = mock_drive_service
        mock_drive_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {'files': []}

        inputs = {'name_contains': "Test's Sheet"}

        await google_sheets.ListSpreadsheets().execute(inputs, self.context)

        call_args = mock_files.list.call_args[1]
        assert "name contains 'Test\\'s Sheet'" in call_args['q']

    @patch('google_sheets.build')
    async def test_list_spreadsheets_http_error(self, mock_build):
        """Test error handling for HTTP errors"""
        mock_drive_service = Mock()
        mock_files = Mock()
        mock_list = Mock()

        mock_build.return_value = mock_drive_service
        mock_drive_service.files.return_value = mock_files
        mock_files.list.return_value = mock_list
        mock_list.execute.side_effect = MockHttpError(Mock(status=403))

        result = await google_sheets.ListSpreadsheets().execute({}, self.context)

        assert result['result'] is False
        assert 'Google Drive API error' in result['error']
        assert result['files'] == []

    @patch('google_sheets.build')
    async def test_read_range_success(self, mock_build):
        """Test successful reading of a spreadsheet range"""
        mock_sheets_service = Mock()
        mock_spreadsheets = Mock()
        mock_values = Mock()
        mock_get = Mock()

        mock_build.return_value = mock_sheets_service
        mock_sheets_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.values.return_value = mock_values
        mock_values.get.return_value = mock_get
        mock_get.execute.return_value = {
            'range': 'Sheet1!A1:B2',
            'values': [['Name', 'Age'], ['John', '30']]
        }

        inputs = {
            'spreadsheet_id': 'test_id',
            'range': 'Sheet1!A1:B2',
            'valueRenderOption': 'FORMATTED_VALUE'
        }

        result = await google_sheets.ReadRange().execute(inputs, self.context)

        assert result['result'] is True
        assert result['range'] == 'Sheet1!A1:B2'
        assert len(result['values']) == 2
        assert result['values'][0] == ['Name', 'Age']

    @patch('google_sheets.build')
    async def test_write_range_success(self, mock_build):
        """Test successful writing to a spreadsheet range"""
        mock_sheets_service = Mock()
        mock_spreadsheets = Mock()
        mock_values = Mock()
        mock_update = Mock()

        mock_build.return_value = mock_sheets_service
        mock_sheets_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value = mock_update
        mock_update.execute.return_value = {
            'updatedRange': 'Sheet1!A1:B2',
            'updatedRows': 2,
            'updatedColumns': 2,
            'updatedCells': 4
        }

        inputs = {
            'spreadsheet_id': 'test_id',
            'range': 'Sheet1!A1:B2',
            'values': [['Name', 'Age'], ['John', '30']],
            'inputOption': 'USER_ENTERED'
        }

        result = await google_sheets.WriteRange().execute(inputs, self.context)

        assert result['result'] is True
        assert result['updatedRange'] == 'Sheet1!A1:B2'
        assert result['updatedRows'] == 2
        assert result['updatedCells'] == 4
        assert result['dryRun'] is False

    @patch('google_sheets.build')
    async def test_write_range_dry_run(self, mock_build):
        """Test dry run mode for write operations"""
        mock_sheets_service = Mock()
        mock_spreadsheets = Mock()
        mock_get = Mock()

        mock_build.return_value = mock_sheets_service
        mock_sheets_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.get.return_value = mock_get
        mock_get.execute.return_value = {'spreadsheetId': 'test_id'}

        inputs = {
            'spreadsheet_id': 'test_id',
            'range': 'Sheet1!A1:B2',
            'values': [['Name', 'Age'], ['John', '30']],
            'dry_run': True
        }

        result = await google_sheets.WriteRange().execute(inputs, self.context)

        assert result['result'] is True
        assert result['dryRun'] is True
        assert result['updatedRows'] == 2
        assert result['updatedColumns'] == 2
        assert result['updatedCells'] == 4

    async def test_batch_update_invalid_requests(self):
        """Test validation of batch update requests"""
        inputs = {
            'spreadsheet_id': 'test_id',
            'requests': 'not_a_list'  # Should be a list
        }

        result = await google_sheets.SheetsBatchUpdate().execute(inputs, self.context)

        assert result['result'] is False
        assert 'requests must be an array of objects' in result['error']

    @patch('google_sheets.Credentials')
    def test_build_credentials(self, mock_credentials):
        """Test credential building from execution context"""
        # Set up mock
        mock_creds_instance = Mock()
        mock_credentials.return_value = mock_creds_instance

        context = MockExecutionContext("test_access_token")
        result = google_sheets.build_credentials(context)

        # Verify Credentials was called with correct parameters
        mock_credentials.assert_called_once_with(
            token="test_access_token",
            token_uri="https://oauth2.googleapis.com/token"
        )
        assert result == mock_creds_instance

    @patch('google_sheets.build')
    async def test_error_handling_generic_exception(self, mock_build):
        """Test handling of generic exceptions"""
        mock_sheets_service = Mock()
        mock_spreadsheets = Mock()
        mock_get = Mock()

        mock_build.return_value = mock_sheets_service
        mock_sheets_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.get.return_value = mock_get
        mock_get.execute.side_effect = Exception("Network error")

        inputs = {'spreadsheet_id': 'test_id'}
        result = await google_sheets.GetSpreadsheet().execute(inputs, self.context)

        assert result['result'] is False
        assert result['error'] == "Network error"
        assert result['spreadsheet'] == {}


async def run_all_tests():
    """Run all test methods and report results"""
    test_instance = TestGoogleSheetsIntegration()

    # List all test methods
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]

    print("Running Google Sheets integration tests...")
    print("=" * 50)

    passed = 0
    failed = 0

    for method_name in test_methods:
        test_method = getattr(test_instance, method_name)
        try:
            test_instance.setup_method()  # Set up before each test
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
    print("\nGoogle Sheets integration unit tests completed successfully!")