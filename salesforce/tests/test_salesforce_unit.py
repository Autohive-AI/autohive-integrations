"""
Unit tests for Salesforce integration.

All tests are fully mocked — no real API credentials required.
Covers all 7 action handlers plus helper functions.
"""

import json
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from autohive_integrations_sdk import FetchResponse  # noqa: E402

from salesforce.salesforce import (  # noqa: E402
    SearchRecordsAction,
    GetRecordAction,
    UpdateRecordAction,
    ListTasksAction,
    ListEventsAction,
    GetTaskSummaryAction,
    GetEventSummaryAction,
    _build_task_query,
    _build_event_query,
    _summarise_task,
    _summarise_event,
    salesforce as salesforce_integration,
)

pytestmark = pytest.mark.unit

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

TEST_TOKEN = "test_access_token"  # nosec B105
TEST_INSTANCE = "https://test.salesforce.com"
TEST_AUTH = {"credentials": {"access_token": TEST_TOKEN, "instance_url": TEST_INSTANCE}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fetch_response(data: dict) -> MagicMock:
    resp = MagicMock(spec=FetchResponse)
    resp.data = data
    return resp


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = TEST_AUTH
    return ctx


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        defined = set(config.get("actions", {}).keys())
        registered = set(salesforce_integration._action_handlers.keys())

        missing = defined - registered
        extra = registered - defined

        assert not missing, f"Missing handlers: {missing}"
        assert not extra, f"Extra handlers without config: {extra}"

    def test_auth_type_is_platform(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        assert config["auth"]["type"] == "platform"
        assert config["auth"]["provider"] == "salesforce"

    def test_all_actions_have_output_schema(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        for name, action in config["actions"].items():
            assert "output_schema" in action, f"Action '{name}' missing output_schema"

    def test_all_actions_have_result_in_output(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        for name, action in config["actions"].items():
            props = action.get("output_schema", {}).get("properties", {})
            assert "result" in props, f"Action '{name}' output_schema missing 'result' field"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestBuildTaskQuery:
    def test_no_filters(self):
        q = _build_task_query()
        assert "FROM Task" in q
        assert "WHERE" not in q
        assert "LIMIT 25" in q

    def test_status_filter(self):
        q = _build_task_query(status="Completed")
        assert "Status = 'Completed'" in q
        assert "WHERE" in q

    def test_status_escapes_single_quote(self):
        q = _build_task_query(status="Won't do")
        assert "Won\\'t do" in q

    def test_assigned_to_filter(self):
        q = _build_task_query(assigned_to_id="005XXXX")
        assert "OwnerId = '005XXXX'" in q

    def test_due_date_range(self):
        q = _build_task_query(due_date_from="2026-01-01", due_date_to="2026-12-31")
        assert "ActivityDate >= 2026-01-01" in q
        assert "ActivityDate <= 2026-12-31" in q

    def test_limit_capped_at_200(self):
        q = _build_task_query(limit=999)
        assert "LIMIT 200" in q

    def test_custom_limit(self):
        q = _build_task_query(limit=10)
        assert "LIMIT 10" in q

    def test_multiple_conditions_use_and(self):
        q = _build_task_query(status="Open", assigned_to_id="005XXX")
        assert " AND " in q

    def test_required_fields_in_select(self):
        q = _build_task_query()
        for field in ["Id", "Subject", "Status", "Priority", "ActivityDate", "Description"]:
            assert field in q


class TestBuildEventQuery:
    def test_no_filters(self):
        q = _build_event_query()
        assert "FROM Event" in q
        assert "WHERE" not in q
        assert "LIMIT 25" in q

    def test_start_date_range(self):
        q = _build_event_query(start_date_from="2026-01-01", start_date_to="2026-01-31")
        assert "StartDateTime >= 2026-01-01T00:00:00Z" in q
        assert "StartDateTime <= 2026-01-31T23:59:59Z" in q

    def test_assigned_to_filter(self):
        q = _build_event_query(assigned_to_id="005XXX")
        assert "OwnerId = '005XXX'" in q

    def test_limit_capped_at_200(self):
        q = _build_event_query(limit=500)
        assert "LIMIT 200" in q

    def test_required_fields_in_select(self):
        q = _build_event_query()
        for field in ["Id", "Subject", "StartDateTime", "EndDateTime", "Location", "Description"]:
            assert field in q


class TestSummariseTask:
    def test_full_task(self):
        task = {
            "Subject": "Follow up call",
            "Status": "Not Started",
            "Priority": "High",
            "ActivityDate": "2026-05-01",
            "Description": "Call the client to follow up on the proposal.",
        }
        summary = _summarise_task(task)
        assert "Follow up call" in summary
        assert "Not Started" in summary
        assert "High" in summary
        assert "2026-05-01" in summary
        assert "Call the client" in summary

    def test_missing_fields_use_defaults(self):
        summary = _summarise_task({})
        assert "No subject" in summary
        assert "Unknown" in summary
        assert "No due date" in summary
        assert "No description" in summary


class TestSummariseEvent:
    def test_full_event(self):
        event = {
            "Subject": "Quarterly review",
            "StartDateTime": "2026-05-01T09:00:00Z",
            "EndDateTime": "2026-05-01T10:00:00Z",
            "Location": "Board Room",
            "Description": "Q1 results discussion.",
            "IsAllDayEvent": False,
        }
        summary = _summarise_event(event)
        assert "Quarterly review" in summary
        assert "2026-05-01T09:00:00Z" in summary
        assert "Board Room" in summary
        assert "Q1 results" in summary
        assert "(All day)" not in summary

    def test_all_day_event_label(self):
        event = {"Subject": "Holiday", "IsAllDayEvent": True}
        summary = _summarise_event(event)
        assert "(All day)" in summary

    def test_missing_fields_use_defaults(self):
        summary = _summarise_event({})
        assert "No subject" in summary
        assert "No location" in summary
        assert "No description" in summary


# ---------------------------------------------------------------------------
# Action handler tests
# ---------------------------------------------------------------------------


class TestSearchRecordsAction:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {"records": [{"Id": "003XX", "Name": "Jane Doe"}], "totalSize": 1, "done": True}
        )
        handler = SearchRecordsAction()
        result = await handler.execute({"soql": "SELECT Id, Name FROM Contact LIMIT 1"}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["records"]) == 1
        assert result.data["records"][0]["Name"] == "Jane Doe"
        assert result.data["total_size"] == 1
        assert result.data["done"] is True

    async def test_passes_soql_as_query_param(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0, "done": True})
        handler = SearchRecordsAction()
        soql = "SELECT Id FROM Lead LIMIT 5"
        await handler.execute({"soql": soql}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["params"]["q"] == soql

    async def test_uses_bearer_auth_header(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0, "done": True})
        handler = SearchRecordsAction()
        await handler.execute({"soql": "SELECT Id FROM Contact"}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {TEST_TOKEN}"

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        handler = SearchRecordsAction()
        result = await handler.execute({"soql": "SELECT Id FROM Contact"}, mock_context)

        assert result.data["result"] is False
        assert "API error" in result.data["error"]

    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0, "done": True})
        handler = SearchRecordsAction()
        result = await handler.execute({"soql": "SELECT Id FROM Contact WHERE Name = 'Nobody'"}, mock_context)

        assert result.data["result"] is True
        assert result.data["records"] == []
        assert result.data["total_size"] == 0


class TestGetRecordAction:
    async def test_success(self, mock_context):
        record = {"Id": "003XX", "Name": "Jane Doe", "Email": "jane@example.com"}
        mock_context.fetch.return_value = make_fetch_response(record)
        handler = GetRecordAction()
        result = await handler.execute({"object_type": "Contact", "record_id": "003XX"}, mock_context)

        assert result.data["result"] is True
        assert result.data["record"]["Name"] == "Jane Doe"

    async def test_url_contains_object_type_and_id(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"Id": "003XX"})
        handler = GetRecordAction()
        await handler.execute({"object_type": "Contact", "record_id": "003XX"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "/sobjects/Contact/003XX" in url

    async def test_fields_param_passed_when_provided(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"Id": "003XX", "Name": "Jane"})
        handler = GetRecordAction()
        await handler.execute({"object_type": "Contact", "record_id": "003XX", "fields": "Id,Name"}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["fields"] == "Id,Name"

    async def test_no_fields_param_when_not_provided(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"Id": "003XX"})
        handler = GetRecordAction()
        await handler.execute({"object_type": "Contact", "record_id": "003XX"}, mock_context)

        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert "fields" not in params

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        handler = GetRecordAction()
        result = await handler.execute({"object_type": "Contact", "record_id": "BAD"}, mock_context)

        assert result.data["result"] is False
        assert "Not found" in result.data["error"]


class TestUpdateRecordAction:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({})
        handler = UpdateRecordAction()
        result = await handler.execute(
            {"object_type": "Contact", "record_id": "003XX", "fields": {"Phone": "0400000000"}},
            mock_context,
        )

        assert result.data["result"] is True
        assert result.data["record_id"] == "003XX"
        assert result.data["object_type"] == "Contact"

    async def test_uses_patch_method(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({})
        handler = UpdateRecordAction()
        await handler.execute(
            {"object_type": "Lead", "record_id": "00QXX", "fields": {"Title": "Manager"}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    async def test_fields_sent_as_json_body(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({})
        handler = UpdateRecordAction()
        fields = {"Phone": "0400000000", "Title": "Director"}
        await handler.execute({"object_type": "Contact", "record_id": "003XX", "fields": fields}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"] == fields

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")
        handler = UpdateRecordAction()
        result = await handler.execute(
            {"object_type": "Contact", "record_id": "003XX", "fields": {"Name": "X"}}, mock_context
        )

        assert result.data["result"] is False


class TestListTasksAction:
    async def test_success_no_filters(self, mock_context):
        tasks = [{"Id": "00TXX", "Subject": "Call client", "Status": "Not Started"}]
        mock_context.fetch.return_value = make_fetch_response({"records": tasks, "totalSize": 1})
        handler = ListTasksAction()
        result = await handler.execute({}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["tasks"]) == 1
        assert result.data["total_size"] == 1

    async def test_status_filter_applied(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListTasksAction()
        await handler.execute({"status": "Completed"}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "Status = 'Completed'" in soql

    async def test_date_filter_applied(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListTasksAction()
        await handler.execute({"due_date_from": "2026-01-01", "due_date_to": "2026-06-30"}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "ActivityDate >= 2026-01-01" in soql
        assert "ActivityDate <= 2026-06-30" in soql

    async def test_default_limit_is_25(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListTasksAction()
        await handler.execute({}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "LIMIT 25" in soql

    async def test_custom_limit(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListTasksAction()
        await handler.execute({"limit": 50}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "LIMIT 50" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")
        handler = ListTasksAction()
        result = await handler.execute({}, mock_context)

        assert result.data["result"] is False


class TestListEventsAction:
    async def test_success_no_filters(self, mock_context):
        events = [{"Id": "00UXX", "Subject": "Client meeting", "StartDateTime": "2026-05-01T09:00:00Z"}]
        mock_context.fetch.return_value = make_fetch_response({"records": events, "totalSize": 1})
        handler = ListEventsAction()
        result = await handler.execute({}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["events"]) == 1
        assert result.data["total_size"] == 1

    async def test_date_filter_applied(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListEventsAction()
        await handler.execute({"start_date_from": "2026-05-01", "start_date_to": "2026-05-31"}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "StartDateTime >= 2026-05-01T00:00:00Z" in soql
        assert "StartDateTime <= 2026-05-31T23:59:59Z" in soql

    async def test_default_limit_is_25(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = ListEventsAction()
        await handler.execute({}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "LIMIT 25" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("network error")
        handler = ListEventsAction()
        result = await handler.execute({}, mock_context)

        assert result.data["result"] is False


class TestGetTaskSummaryAction:
    async def test_success(self, mock_context):
        task = {
            "Id": "00TXX",
            "Subject": "Follow up",
            "Status": "In Progress",
            "Priority": "High",
            "ActivityDate": "2026-05-10",
            "Description": "Check on contract status.",
        }
        mock_context.fetch.return_value = make_fetch_response({"records": [task], "totalSize": 1})
        handler = GetTaskSummaryAction()
        result = await handler.execute({"task_id": "00TXX"}, mock_context)

        assert result.data["result"] is True
        assert "Follow up" in result.data["summary"]
        assert "In Progress" in result.data["summary"]
        assert result.data["task"]["Id"] == "00TXX"

    async def test_task_not_found(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = GetTaskSummaryAction()
        result = await handler.execute({"task_id": "00TBAD"}, mock_context)

        assert result.data["result"] is False
        assert "not found" in result.data["error"].lower()

    async def test_soql_filters_by_task_id(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = GetTaskSummaryAction()
        await handler.execute({"task_id": "00TXX123"}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "00TXX123" in soql
        assert "FROM Task" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        handler = GetTaskSummaryAction()
        result = await handler.execute({"task_id": "00TXX"}, mock_context)

        assert result.data["result"] is False


class TestGetEventSummaryAction:
    async def test_success(self, mock_context):
        event = {
            "Id": "00UXX",
            "Subject": "Board meeting",
            "StartDateTime": "2026-06-01T09:00:00Z",
            "EndDateTime": "2026-06-01T11:00:00Z",
            "Location": "HQ",
            "Description": "Annual board review.",
            "IsAllDayEvent": False,
        }
        mock_context.fetch.return_value = make_fetch_response({"records": [event], "totalSize": 1})
        handler = GetEventSummaryAction()
        result = await handler.execute({"event_id": "00UXX"}, mock_context)

        assert result.data["result"] is True
        assert "Board meeting" in result.data["summary"]
        assert "HQ" in result.data["summary"]
        assert result.data["event"]["Id"] == "00UXX"

    async def test_event_not_found(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = GetEventSummaryAction()
        result = await handler.execute({"event_id": "00UBAD"}, mock_context)

        assert result.data["result"] is False
        assert "not found" in result.data["error"].lower()

    async def test_all_day_event_in_summary(self, mock_context):
        event = {"Id": "00UXX", "Subject": "Public Holiday", "IsAllDayEvent": True}
        mock_context.fetch.return_value = make_fetch_response({"records": [event], "totalSize": 1})
        handler = GetEventSummaryAction()
        result = await handler.execute({"event_id": "00UXX"}, mock_context)

        assert "(All day)" in result.data["summary"]

    async def test_soql_filters_by_event_id(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"records": [], "totalSize": 0})
        handler = GetEventSummaryAction()
        await handler.execute({"event_id": "00UABC"}, mock_context)

        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "00UABC" in soql
        assert "FROM Event" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")
        handler = GetEventSummaryAction()
        result = await handler.execute({"event_id": "00UXX"}, mock_context)

        assert result.data["result"] is False
