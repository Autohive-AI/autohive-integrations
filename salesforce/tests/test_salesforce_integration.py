"""
End-to-end integration tests for the Salesforce integration.

These tests call the real Salesforce API and require a valid access token
and instance URL set via environment variables (via .env or export).

Run with:
    pytest salesforce/tests/test_salesforce_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("salesforce_mod", os.path.join(_parent, "salesforce.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

salesforce = _mod.salesforce

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("SALESFORCE_TOKEN", "")
INSTANCE_URL = os.environ.get("SALESFORCE_INSTANCE_URL", "")
RECORD_ID = os.environ.get("SALESFORCE_RECORD_ID", "")
TASK_ID = os.environ.get("SALESFORCE_TASK_ID", "")
EVENT_ID = os.environ.get("SALESFORCE_EVENT_ID", "")


def require_record_id():
    if not RECORD_ID:
        pytest.skip("SALESFORCE_RECORD_ID not set")


def require_task_id():
    if not TASK_ID:
        pytest.skip("SALESFORCE_TASK_ID not set")


def require_event_id():
    if not EVENT_ID:
        pytest.skip("SALESFORCE_EVENT_ID not set")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("SALESFORCE_TOKEN not set — skipping integration tests")
    if not INSTANCE_URL:
        pytest.skip("SALESFORCE_INSTANCE_URL not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},  # nosec B105
    }
    ctx.metadata = {"instance_url": INSTANCE_URL}
    return ctx


# ---- Read-Only Tests ----


class TestSearchRecords:
    async def test_search_contacts(self, live_context):
        result = await salesforce.execute_action(
            "search_records", {"soql": "SELECT Id, Name FROM Contact LIMIT 5"}, live_context
        )
        data = result.result.data
        assert data["result"] is True
        assert "records" in data
        assert isinstance(data["records"], list)

    async def test_search_returns_total_size(self, live_context):
        result = await salesforce.execute_action(
            "search_records", {"soql": "SELECT Id FROM Contact LIMIT 1"}, live_context
        )
        assert "total_size" in result.result.data
        assert isinstance(result.result.data["total_size"], int)


class TestGetRecord:
    async def test_get_contact_by_id(self, live_context):
        require_record_id()
        result = await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": RECORD_ID}, live_context
        )
        data = result.result.data
        assert data["result"] is True
        assert "record" in data
        assert data["record"]["Id"] == RECORD_ID

    async def test_get_record_with_fields(self, live_context):
        require_record_id()
        result = await salesforce.execute_action(
            "get_record",
            {"object_type": "Contact", "record_id": RECORD_ID, "fields": "Id,Name"},
            live_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert "Id" in data["record"]


class TestListTasks:
    async def test_list_tasks_no_filters(self, live_context):
        result = await salesforce.execute_action("list_tasks", {"limit": 5}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "tasks" in data
        assert len(data["tasks"]) <= 5

    async def test_list_tasks_with_status_filter(self, live_context):
        result = await salesforce.execute_action("list_tasks", {"status": "Not Started", "limit": 5}, live_context)
        data = result.result.data
        assert data["result"] is True
        for task in data["tasks"]:
            assert task["Status"] == "Not Started"


class TestListEvents:
    async def test_list_events_no_filters(self, live_context):
        result = await salesforce.execute_action("list_events", {"limit": 5}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "events" in data
        assert len(data["events"]) <= 5


class TestGetTaskSummary:
    async def test_get_task_summary(self, live_context):
        require_task_id()
        result = await salesforce.execute_action("get_task_summary", {"task_id": TASK_ID}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "summary" in data
        assert "task" in data
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0


class TestGetEventSummary:
    async def test_get_event_summary(self, live_context):
        require_event_id()
        result = await salesforce.execute_action("get_event_summary", {"event_id": EVENT_ID}, live_context)
        data = result.result.data
        assert data["result"] is True
        assert "summary" in data
        assert "event" in data
        assert isinstance(data["summary"], str)


# ---- Destructive Tests (Write Operations) ----
# These update real data. Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestUpdateRecord:
    async def test_update_contact_field(self, live_context):
        require_record_id()
        result = await salesforce.execute_action(
            "update_record",
            {"object_type": "Contact", "record_id": RECORD_ID, "fields": {"Description": "Updated by Autohive test"}},
            live_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["record_id"] == RECORD_ID
