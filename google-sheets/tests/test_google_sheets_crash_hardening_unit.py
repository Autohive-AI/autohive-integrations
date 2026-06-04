import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from autohive_integrations_sdk.integration import ResultType

import google_sheets as gs_module
from google_sheets import google_sheets, build_sheets_service, build_drive_service, HTTP_TIMEOUT_SECONDS

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


# ---- HTTP timeout cap ----


class TestHttpTimeout:
    def test_timeout_is_below_lambda_timeout(self):
        # httplib2's default timeout is None (block indefinitely); the
        # integration Lambda is killed after 30s, so a stalled Google API
        # call must fail before that instead of crashing with "Unhandled".
        assert HTTP_TIMEOUT_SECONDS < 30

    @patch("google_sheets.build")
    def test_sheets_service_uses_timeout_capped_http(self, mock_build, mock_context):
        build_sheets_service(mock_context)

        http_arg = mock_build.call_args.kwargs["http"]
        assert http_arg.http.timeout == HTTP_TIMEOUT_SECONDS

    @patch("google_sheets.build")
    def test_drive_service_uses_timeout_capped_http(self, mock_build, mock_context):
        build_drive_service(mock_context)

        http_arg = mock_build.call_args.kwargs["http"]
        assert http_arg.http.timeout == HTTP_TIMEOUT_SECONDS


# ---- Cancellation handling ----


class TestCancellation:
    @pytest.mark.asyncio
    @patch("google_sheets.build")
    async def test_cancelled_action_returns_action_error(self, mock_build, mock_context):
        # asyncio.CancelledError is a BaseException, so the actions'
        # `except Exception` blocks let it slip through and the Lambda
        # returned "Unhandled". The handle_cancellation decorator must
        # convert it to a clean ActionError.
        mock_build.side_effect = asyncio.CancelledError()

        result = await google_sheets.execute_action(
            "sheets_read_range",
            {"spreadsheet_id": "sid", "range": "A1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "cancelled" in result.result.message.lower()

    @pytest.mark.asyncio
    @patch("google_sheets.build")
    async def test_cancelled_write_returns_action_error(self, mock_build, mock_context):
        mock_build.side_effect = asyncio.CancelledError()

        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": "sid", "range": "A1", "values": [["x"]]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "cancelled" in result.result.message.lower()

    @pytest.mark.asyncio
    @patch("google_sheets.build")
    async def test_normal_error_still_returns_action_error(self, mock_build, mock_context):
        # Regression guard: the decorator must not swallow or alter the
        # existing Exception -> ActionError behavior.
        mock_build.side_effect = Exception("boom")

        result = await google_sheets.execute_action(
            "sheets_read_range",
            {"spreadsheet_id": "sid", "range": "A1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


# ---- include_grid_data observability ----


class TestGridDataWarning:
    @pytest.mark.asyncio
    @patch("google_sheets.build")
    async def test_include_grid_data_logs_warning(self, mock_build, mock_context, caplog):
        service = MagicMock()
        mock_build.return_value = service
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid"}

        with caplog.at_level("WARNING", logger=gs_module.logger.name):
            result = await google_sheets.execute_action(
                "sheets_get_spreadsheet",
                {"spreadsheet_id": "sid", "include_grid_data": True},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        assert any("include_grid_data" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    @patch("google_sheets.build")
    async def test_no_warning_without_grid_data(self, mock_build, mock_context, caplog):
        service = MagicMock()
        mock_build.return_value = service
        service.spreadsheets().get().execute.return_value = {"spreadsheetId": "sid"}

        with caplog.at_level("WARNING", logger=gs_module.logger.name):
            await google_sheets.execute_action(
                "sheets_get_spreadsheet",
                {"spreadsheet_id": "sid"},
                mock_context,
            )

        assert not any("include_grid_data" in rec.message for rec in caplog.records)
