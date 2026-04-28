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

_spec = importlib.util.spec_from_file_location("google_sheets_data_mod", os.path.join(_parent, "google_sheets.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["google_sheets_data_mod"] = _mod
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


def make_sheets_service(mock_build):
    service = MagicMock()
    mock_build.return_value = service
    return service


# ---- Read Range ----


class TestReadRange:
    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_happy_path_returns_values(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:B2",
            "values": [["Name", "Age"], ["Alice", "30"]],
        }

        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": "sid", "range": "Sheet1!A1:B2"}, mock_context
        )

        assert result.result.data["range"] == "Sheet1!A1:B2"
        assert result.result.data["values"] == [["Name", "Age"], ["Alice", "30"]]

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_empty_range_returns_empty_values(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().get().execute.return_value = {"range": "Sheet1!A1"}

        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": "sid", "range": "Sheet1!A1"}, mock_context
        )

        assert result.result.data["values"] == []

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_value_render_option_passed(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().get().execute.return_value = {"range": "A1", "values": []}

        await google_sheets.execute_action(
            "sheets_read_range",
            {"spreadsheet_id": "sid", "range": "A1", "valueRenderOption": "FORMULA"},
            mock_context,
        )

        call_kwargs = service.spreadsheets().values().get.call_args.kwargs
        assert call_kwargs["valueRenderOption"] == "FORMULA"

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_datetime_render_option_passed(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().get().execute.return_value = {"range": "A1", "values": []}

        await google_sheets.execute_action(
            "sheets_read_range",
            {"spreadsheet_id": "sid", "range": "A1", "dateTimeRenderOption": "FORMATTED_STRING"},
            mock_context,
        )

        call_kwargs = service.spreadsheets().values().get.call_args.kwargs
        assert call_kwargs["dateTimeRenderOption"] == "FORMATTED_STRING"

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.reason = "Bad Request"
        service.spreadsheets().values().get().execute.side_effect = HttpError(mock_resp, b"Bad Request")

        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": "sid", "range": "Bad!Range"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().get().execute.side_effect = Exception("Timeout")

        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": "sid", "range": "A1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message


# ---- Write Range ----


class TestWriteRange:
    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_happy_path_returns_update_info(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().update().execute.return_value = {
            "updatedRange": "Sheet1!A1:B2",
            "updatedRows": 2,
            "updatedColumns": 2,
            "updatedCells": 4,
        }

        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "Sheet1!A1:B2", "values": [["Name", "Age"], ["Alice", "30"]]},
            mock_context,
        )

        assert result.result.data["updatedRange"] == "Sheet1!A1:B2"
        assert result.result.data["updatedRows"] == 2
        assert result.result.data["dryRun"] is False

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_dry_run_returns_estimate_without_write(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid"}

        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "A1", "values": [["a", "b"], ["c", "d"]], "dry_run": True},
            mock_context,
        )

        assert result.result.data["dryRun"] is True
        assert result.result.data["updatedRows"] == 2
        assert result.result.data["updatedColumns"] == 2
        assert result.result.data["updatedCells"] == 4
        # values().update should NOT have been called
        service.spreadsheets().values().update.assert_not_called()

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_input_option_raw_by_default(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().update().execute.return_value = {}

        await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "A1", "values": [["x"]]},
            mock_context,
        )

        call_kwargs = service.spreadsheets().values().update.call_args.kwargs
        assert call_kwargs["valueInputOption"] == "RAW"

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_resp.reason = "Forbidden"
        service.spreadsheets().values().update().execute.side_effect = HttpError(mock_resp, b"Forbidden")

        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "A1", "values": [["x"]]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().update().execute.side_effect = Exception("Write failed")

        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "A1", "values": [["x"]]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Write failed" in result.result.message


# ---- Append Rows ----


class TestAppendRows:
    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_happy_path_returns_updates(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().append().execute.return_value = {
            "updates": {"updatedRows": 3, "updatedCells": 6}
        }

        result = await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": "sid", "range": "Sheet1", "rows": [["a", "b"], ["c", "d"], ["e", "f"]]},
            mock_context,
        )

        assert result.result.data["updates"]["updatedRows"] == 3

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_insert_rows_option_always_set(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().append().execute.return_value = {"updates": {}}

        await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": "sid", "range": "Sheet1", "rows": [["x"]]},
            mock_context,
        )

        call_kwargs = service.spreadsheets().values().append.call_args.kwargs
        assert call_kwargs["insertDataOption"] == "INSERT_ROWS"

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_input_option_raw_by_default(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().append().execute.return_value = {"updates": {}}

        await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": "sid", "range": "Sheet1", "rows": [["x"]]},
            mock_context,
        )

        call_kwargs = service.spreadsheets().values().append.call_args.kwargs
        assert call_kwargs["valueInputOption"] == "RAW"

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 429
        mock_resp.reason = "Too Many Requests"
        service.spreadsheets().values().append().execute.side_effect = HttpError(mock_resp, b"Rate limited")

        result = await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": "sid", "range": "Sheet1", "rows": [["x"]]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_data_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().values().append().execute.side_effect = Exception("Append failed")

        result = await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": "sid", "range": "Sheet1", "rows": [["x"]]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Append failed" in result.result.message
