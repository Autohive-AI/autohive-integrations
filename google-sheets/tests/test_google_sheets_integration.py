"""
End-to-end integration tests for the Google Sheets integration.

These tests call the real Google Sheets/Drive API and require a valid OAuth access token
set in the GOOGLE_SHEETS_ACCESS_TOKEN environment variable (via .env or export).

Run with:
    pytest google-sheets/tests/test_google_sheets_integration.py -m integration

Never runs in CI -- the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_sheets_mod", os.path.join(_parent, "google_sheets.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_sheets = _mod.google_sheets

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("GOOGLE_SHEETS_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("GOOGLE_SHEETS_ACCESS_TOKEN not set - skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


def get_first_spreadsheet_id(live_context):
    """Helper to get a real spreadsheet ID by running list action inline."""
    import asyncio

    async def _get():
        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = result.result.data.get("files", [])
        if not files:
            pytest.skip("No spreadsheets found in account")
        return files[0]["id"]

    return asyncio.get_event_loop().run_until_complete(_get())


# ---- Read-Only Tests ----


class TestListSpreadsheets:
    async def test_returns_files(self, live_context):
        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        data = result.result.data
        assert "files" in data
        assert isinstance(data["files"], list)

    async def test_response_structure(self, live_context):
        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = result.result.data["files"]
        if files:
            assert "id" in files[0]
            assert "name" in files[0]


class TestGetSpreadsheet:
    async def test_returns_spreadsheet(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_get_spreadsheet", {"spreadsheet_id": spreadsheet_id}, live_context
        )

        data = result.result.data
        assert "spreadsheet" in data
        assert data["spreadsheet"]["spreadsheetId"] == spreadsheet_id

    async def test_spreadsheet_has_sheets(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_get_spreadsheet", {"spreadsheet_id": spreadsheet_id}, live_context
        )

        assert "sheets" in result.result.data["spreadsheet"]


class TestListSheets:
    async def test_returns_sheets(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_list_sheets", {"spreadsheet_id": spreadsheet_id}, live_context
        )

        data = result.result.data
        assert "sheets" in data
        assert isinstance(data["sheets"], list)
        assert len(data["sheets"]) > 0

    async def test_sheet_has_expected_fields(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_list_sheets", {"spreadsheet_id": spreadsheet_id}, live_context
        )

        sheet = result.result.data["sheets"][0]
        assert "sheetId" in sheet
        assert "title" in sheet


class TestReadRange:
    async def test_reads_range(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": spreadsheet_id, "range": "A1:C10"}, live_context
        )

        data = result.result.data
        assert "range" in data
        assert "values" in data

    async def test_response_structure(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_read_range", {"spreadsheet_id": spreadsheet_id, "range": "A1"}, live_context
        )

        assert isinstance(result.result.data["values"], list)


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestWriteRange:
    async def test_writes_range(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_write_range",
            {"spreadsheet_id": spreadsheet_id, "range": "A1", "values": [["integration_test"]]},
            live_context,
        )

        data = result.result.data
        assert "updatedRange" in data
        assert data["updatedCells"] >= 1


@pytest.mark.destructive
class TestAppendRows:
    async def test_appends_rows(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_append_rows",
            {"spreadsheet_id": spreadsheet_id, "range": "A1", "rows": [["append_test_row"]]},
            live_context,
        )

        data = result.result.data
        assert "updates" in data


@pytest.mark.destructive
class TestFormatRange:
    async def test_formats_range(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        sheets_result = await google_sheets.execute_action(
            "sheets_list_sheets", {"spreadsheet_id": spreadsheet_id}, live_context
        )
        sheet_id = sheets_result.result.data["sheets"][0]["sheetId"]

        result = await google_sheets.execute_action(
            "sheets_format_range",
            {
                "spreadsheet_id": spreadsheet_id,
                "sheetId": sheet_id,
                "gridRange": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                },
                "style": {"textFormat": {"bold": True}},
            },
            live_context,
        )

        assert result.result is not None


@pytest.mark.destructive
class TestFreeze:
    async def test_freezes_rows(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        sheets_result = await google_sheets.execute_action(
            "sheets_list_sheets", {"spreadsheet_id": spreadsheet_id}, live_context
        )
        sheet_id = sheets_result.result.data["sheets"][0]["sheetId"]

        result = await google_sheets.execute_action(
            "sheets_freeze",
            {"spreadsheet_id": spreadsheet_id, "sheetId": sheet_id, "rows": 1},
            live_context,
        )

        assert result.result is not None


@pytest.mark.destructive
class TestBatchUpdate:
    async def test_batch_update(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        spreadsheet_id = files[0]["id"]
        sheets_result = await google_sheets.execute_action(
            "sheets_list_sheets", {"spreadsheet_id": spreadsheet_id}, live_context
        )
        sheet_id = sheets_result.result.data["sheets"][0]["sheetId"]

        requests = [
            {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "title": "Sheet1"}, "fields": "title"}}
        ]
        result = await google_sheets.execute_action(
            "sheets_batch_update",
            {"spreadsheet_id": spreadsheet_id, "requests": requests},
            live_context,
        )

        assert result.result is not None


@pytest.mark.destructive
class TestDuplicateSpreadsheet:
    async def test_duplicates_spreadsheet(self, live_context):
        list_result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, live_context)
        files = list_result.result.data["files"]
        if not files:
            pytest.skip("No spreadsheets in account")

        source_id = files[0]["id"]
        result = await google_sheets.execute_action(
            "sheets_duplicate_spreadsheet",
            {"source_spreadsheet_id": source_id, "new_title": "Integration Test Copy"},
            live_context,
        )

        from autohive_integrations_sdk.integration import ResultType

        if result.type == ResultType.ACTION_ERROR:
            # 403 appNotAuthorizedToFile is a permissions issue with the token, not a code bug
            assert (
                "403" in result.result.message
                or "appNotAuthorizedToFile" in result.result.message
                or "forbidden" in result.result.message.lower()
            )
            pytest.skip(f"Token lacks copy permission: {result.result.message}")

        data = result.result.data
        assert "file_metadata" in data
        assert "id" in data["file_metadata"]
