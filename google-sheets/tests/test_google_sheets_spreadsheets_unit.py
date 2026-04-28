import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_sheets_mod", os.path.join(_parent, "google_sheets.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["google_sheets_mod"] = _mod
_spec.loader.exec_module(_mod)

google_sheets = _mod.google_sheets

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def make_drive_service(mock_build):
    """Helper: configure mock_build to return a drive service mock."""
    drive = MagicMock()
    mock_build.return_value = drive
    return drive


def make_sheets_service(mock_build):
    """Helper: configure mock_build to return a sheets service mock."""
    service = MagicMock()
    mock_build.return_value = service
    return service


# ---- List Spreadsheets ----


class TestListSpreadsheets:
    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_happy_path_returns_files(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {
            "files": [{"id": "abc", "name": "My Sheet"}],
        }

        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, mock_context)

        assert result.result.data["files"][0]["id"] == "abc"
        assert "nextPageToken" not in result.result.data

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_next_page_token_included_when_present(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {
            "files": [],
            "nextPageToken": "tok123",
        }

        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, mock_context)

        assert result.result.data["nextPageToken"] == "tok123"

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_name_contains_filter_applied(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {"files": []}

        await google_sheets.execute_action("sheets_list_spreadsheets", {"name_contains": "Budget"}, mock_context)

        call_kwargs = drive.files().list.call_args.kwargs
        assert "name contains 'Budget'" in call_kwargs["q"]

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_owner_me_filter(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {"files": []}

        await google_sheets.execute_action("sheets_list_spreadsheets", {"owner": "me"}, mock_context)

        call_kwargs = drive.files().list.call_args.kwargs
        assert "'me' in owners" in call_kwargs["q"]

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_owner_email_filter(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {"files": []}

        await google_sheets.execute_action("sheets_list_spreadsheets", {"owner": "user@example.com"}, mock_context)

        call_kwargs = drive.files().list.call_args.kwargs
        assert "'user@example.com' in owners" in call_kwargs["q"]

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_quote_escaping_in_name_contains(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.return_value = {"files": []}

        await google_sheets.execute_action("sheets_list_spreadsheets", {"name_contains": "Test's Sheet"}, mock_context)

        call_kwargs = drive.files().list.call_args.kwargs
        assert "name contains 'Test\\'s Sheet'" in call_kwargs["q"]

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        drive = make_drive_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_resp.reason = "Forbidden"
        drive.files().list().execute.side_effect = HttpError(mock_resp, b"Forbidden")

        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Drive API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().list().execute.side_effect = Exception("Network timeout")

        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network timeout" in result.result.message


# ---- Get Spreadsheet ----


class TestGetSpreadsheet:
    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_happy_path_returns_spreadsheet(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid1", "title": "My Sheet"}

        result = await google_sheets.execute_action("sheets_get_spreadsheet", {"spreadsheet_id": "sid1"}, mock_context)

        assert result.result.data["spreadsheet"]["spreadsheetId"] == "sid1"

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_include_grid_data_passed_correctly(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid1"}

        await google_sheets.execute_action(
            "sheets_get_spreadsheet", {"spreadsheet_id": "sid1", "include_grid_data": True}, mock_context
        )

        service.spreadsheets().get.assert_called_with(spreadsheetId="sid1", includeGridData=True)

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.reason = "Not Found"
        service.spreadsheets().get().execute.side_effect = HttpError(mock_resp, b"Not Found")

        result = await google_sheets.execute_action(
            "sheets_get_spreadsheet", {"spreadsheet_id": "bad_id"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.side_effect = Exception("Connection refused")

        result = await google_sheets.execute_action("sheets_get_spreadsheet", {"spreadsheet_id": "sid1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message


# ---- List Sheets ----


class TestListSheets:
    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_happy_path_returns_sheet_list(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Sheet1", "index": 0}},
                {"properties": {"sheetId": 1, "title": "Sheet2", "index": 1}},
            ]
        }

        result = await google_sheets.execute_action("sheets_list_sheets", {"spreadsheet_id": "sid1"}, mock_context)

        assert len(result.result.data["sheets"]) == 2
        assert result.result.data["sheets"][0]["title"] == "Sheet1"

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_empty_spreadsheet_returns_empty_list(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {"sheets": []}

        result = await google_sheets.execute_action("sheets_list_sheets", {"spreadsheet_id": "sid1"}, mock_context)

        assert result.result.data["sheets"] == []

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_resp.reason = "Forbidden"
        service.spreadsheets().get().execute.side_effect = HttpError(mock_resp, b"Forbidden")

        result = await google_sheets.execute_action("sheets_list_sheets", {"spreadsheet_id": "sid1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.side_effect = Exception("API down")

        result = await google_sheets.execute_action("sheets_list_sheets", {"spreadsheet_id": "sid1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API down" in result.result.message


# ---- Duplicate Spreadsheet ----


class TestDuplicateSpreadsheet:
    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_happy_path_returns_file_metadata(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().copy().execute.return_value = {
            "id": "new_id",
            "name": "Copy of Sheet",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": ["root"],
            "webViewLink": "https://docs.google.com/spreadsheets/d/new_id",
        }

        result = await google_sheets.execute_action(
            "sheets_duplicate_spreadsheet",
            {"source_spreadsheet_id": "src_id", "new_title": "Copy of Sheet"},
            mock_context,
        )

        assert result.result.data["file_metadata"]["id"] == "new_id"
        assert result.result.data["file_metadata"]["name"] == "Copy of Sheet"

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_parent_folder_id_included_when_provided(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().copy().execute.return_value = {"id": "new_id", "name": "Copy"}

        await google_sheets.execute_action(
            "sheets_duplicate_spreadsheet",
            {"source_spreadsheet_id": "src", "new_title": "Copy", "parent_folder_id": "folder123"},
            mock_context,
        )

        call_kwargs = drive.files().copy.call_args.kwargs
        assert call_kwargs["body"]["parents"] == ["folder123"]

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        drive = make_drive_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.reason = "Not Found"
        drive.files().copy().execute.side_effect = HttpError(mock_resp, b"Not Found")

        result = await google_sheets.execute_action(
            "sheets_duplicate_spreadsheet",
            {"source_spreadsheet_id": "bad", "new_title": "Copy"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Drive API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        drive = make_drive_service(mock_build)
        drive.files().copy().execute.side_effect = Exception("Quota exceeded")

        result = await google_sheets.execute_action(
            "sheets_duplicate_spreadsheet",
            {"source_spreadsheet_id": "src", "new_title": "Copy"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Quota exceeded" in result.result.message
