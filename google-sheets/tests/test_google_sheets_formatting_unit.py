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

_spec = importlib.util.spec_from_file_location("google_sheets_fmt_mod", os.path.join(_parent, "google_sheets.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["google_sheets_fmt_mod"] = _mod
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


# ---- Format Range ----


class TestFormatRange:
    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_happy_path_returns_replies(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": [{}]}

        result = await google_sheets.execute_action(
            "sheets_format_range",
            {
                "spreadsheet_id": "sid",
                "sheetId": 0,
                "gridRange": {
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 3,
                },
                "style": {"backgroundColor": {"red": 1.0}},
            },
            mock_context,
        )

        assert "replies" in result.result.data

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_request_contains_repeat_cell(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": []}

        await google_sheets.execute_action(
            "sheets_format_range",
            {
                "spreadsheet_id": "sid",
                "sheetId": 0,
                "gridRange": {"startRowIndex": 0, "endRowIndex": 1},
                "style": {"bold": True},
            },
            mock_context,
        )

        call_kwargs = service.spreadsheets().batchUpdate.call_args.kwargs
        body = call_kwargs["body"]
        assert "repeatCell" in body["requests"][0]
        assert body["requests"][0]["repeatCell"]["cell"]["userEnteredFormat"] == {"bold": True}

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.reason = "Bad Request"
        service.spreadsheets().batchUpdate().execute.side_effect = HttpError(mock_resp, b"Bad Request")

        result = await google_sheets.execute_action(
            "sheets_format_range",
            {
                "spreadsheet_id": "sid",
                "sheetId": 0,
                "gridRange": {},
                "style": {},
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.side_effect = Exception("Format failed")

        result = await google_sheets.execute_action(
            "sheets_format_range",
            {
                "spreadsheet_id": "sid",
                "sheetId": 0,
                "gridRange": {},
                "style": {},
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Format failed" in result.result.message


# ---- Freeze Panes ----


class TestFreezePanes:
    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_happy_path_freeze_rows(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": [{}]}

        result = await google_sheets.execute_action(
            "sheets_freeze",
            {"spreadsheet_id": "sid", "sheetId": 0, "rows": 1},
            mock_context,
        )

        assert "replies" in result.result.data

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_freeze_rows_field_set_correctly(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": []}

        await google_sheets.execute_action(
            "sheets_freeze",
            {"spreadsheet_id": "sid", "sheetId": 0, "rows": 2},
            mock_context,
        )

        call_kwargs = service.spreadsheets().batchUpdate.call_args.kwargs
        req = call_kwargs["body"]["requests"][0]["updateSheetProperties"]
        assert req["properties"]["gridProperties"]["frozenRowCount"] == 2
        assert "gridProperties.frozenRowCount" in req["fields"]

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_freeze_columns_field_set_correctly(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": []}

        await google_sheets.execute_action(
            "sheets_freeze",
            {"spreadsheet_id": "sid", "sheetId": 0, "columns": 1},
            mock_context,
        )

        call_kwargs = service.spreadsheets().batchUpdate.call_args.kwargs
        req = call_kwargs["body"]["requests"][0]["updateSheetProperties"]
        assert req["properties"]["gridProperties"]["frozenColumnCount"] == 1
        assert "gridProperties.frozenColumnCount" in req["fields"]

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_resp.reason = "Forbidden"
        service.spreadsheets().batchUpdate().execute.side_effect = HttpError(mock_resp, b"Forbidden")

        result = await google_sheets.execute_action(
            "sheets_freeze",
            {"spreadsheet_id": "sid", "sheetId": 0, "rows": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.side_effect = Exception("Freeze failed")

        result = await google_sheets.execute_action(
            "sheets_freeze", {"spreadsheet_id": "sid", "sheetId": 0}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Freeze failed" in result.result.message


# ---- Batch Update ----


class TestBatchUpdate:
    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_happy_path_returns_replies(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.return_value = {"replies": [{}, {}]}

        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {
                "spreadsheet_id": "sid",
                "requests": [{"addSheet": {}}, {"deleteSheet": {"sheetId": 1}}],
            },
            mock_context,
        )

        assert result.result.data["dryRun"] is False
        assert len(result.result.data["replies"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_requests_not_a_list_returns_validation_error(self, mock_context):
        # SDK validates inputs against schema before handler runs
        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": "sid", "requests": "not_a_list"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_invalid_requests_list_of_non_dicts_returns_validation_error(self, mock_context):
        # SDK validates items are objects before handler runs
        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": "sid", "requests": ["not", "dicts"]},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_dry_run_validates_without_updating(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid"}

        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": "sid", "requests": [{"addSheet": {}}], "dry_run": True},
            mock_context,
        )

        assert result.result.data["dryRun"] is True
        assert result.result.data["replies"] == []
        service.spreadsheets().batchUpdate.assert_not_called()

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_http_error_returns_action_error(self, mock_build, mock_context):
        from googleapiclient.errors import HttpError

        service = make_sheets_service(mock_build)
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.reason = "Bad Request"
        service.spreadsheets().batchUpdate().execute.side_effect = HttpError(mock_resp, b"Bad Request")

        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": "sid", "requests": [{"bad": "request"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Google Sheets API error" in result.result.message

    @pytest.mark.asyncio
    @patch("google_sheets_fmt_mod.build")
    async def test_generic_exception_returns_action_error(self, mock_build, mock_context):
        service = make_sheets_service(mock_build)
        service.spreadsheets().batchUpdate().execute.side_effect = Exception("Batch failed")

        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": "sid", "requests": [{"addSheet": {}}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Batch failed" in result.result.message
