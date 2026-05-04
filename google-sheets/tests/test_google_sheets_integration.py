import os
import sys
import importlib.util

import pytest

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

from autohive_integrations_sdk import ExecutionContext  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_sheets_mod", os.path.join(_parent, "google_sheets.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_sheets = _mod.google_sheets  # the Integration instance

pytestmark = pytest.mark.integration

# Skip all integration tests if env var is not set
ACCESS_TOKEN = os.environ.get("GOOGLE_SHEETS_ACCESS_TOKEN", "")
TEST_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_TEST_SPREADSHEET_ID", "")

skip_if_no_creds = pytest.mark.skipif(
    not ACCESS_TOKEN,
    reason="GOOGLE_SHEETS_ACCESS_TOKEN env var required for integration tests",
)


@pytest.fixture
def live_context():
    """Real ExecutionContext using env var credentials."""
    auth = {"credentials": {"access_token": ACCESS_TOKEN}}  # nosec B105
    return auth


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_spreadsheets_integration(live_context):
    """Integration test: list spreadsheets from live Google Sheets account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await google_sheets.execute_action("sheets_list_spreadsheets", {}, context)
        assert result.result is not None
        assert "files" in result.result.data


@skip_if_no_creds
@pytest.mark.skipif(
    not TEST_SPREADSHEET_ID,
    reason="GOOGLE_SHEETS_TEST_SPREADSHEET_ID env var required",
)
@pytest.mark.asyncio
async def test_get_spreadsheet_integration(live_context):
    """Integration test: get a specific spreadsheet from live Google Sheets."""
    async with ExecutionContext(auth=live_context) as context:
        result = await google_sheets.execute_action(
            "sheets_get_spreadsheet",
            {"spreadsheet_id": TEST_SPREADSHEET_ID},
            context,
        )
        assert result.result is not None
        assert "spreadsheet" in result.result.data


@skip_if_no_creds
@pytest.mark.skipif(
    not TEST_SPREADSHEET_ID,
    reason="GOOGLE_SHEETS_TEST_SPREADSHEET_ID env var required",
)
@pytest.mark.asyncio
async def test_list_sheets_integration(live_context):
    """Integration test: list sheets in a spreadsheet from live Google Sheets."""
    async with ExecutionContext(auth=live_context) as context:
        result = await google_sheets.execute_action(
            "sheets_list_sheets",
            {"spreadsheet_id": TEST_SPREADSHEET_ID},
            context,
        )
        assert result.result is not None
        assert "sheets" in result.result.data
