import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("salesforce_mod", os.path.join(_parent, "salesforce.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

salesforce = _mod.salesforce
_build_task_query = _mod._build_task_query
_build_event_query = _mod._build_event_query
_summarise_task = _mod._summarise_task
_summarise_event = _mod._summarise_event
_validate_sf_id = _mod._validate_sf_id

pytestmark = pytest.mark.unit

import json  # noqa: E402

CONFIG_PATH = os.path.join(_parent, "config.json")

TEST_TOKEN = "test_access_token"  # nosec B105
TEST_INSTANCE = "https://test.salesforce.com"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": TEST_TOKEN},  # nosec B105
    }
    ctx.metadata = {"instance_url": TEST_INSTANCE}
    return ctx


# ---- ID Validation ----


class TestValidateSfId:
    def test_accepts_15_char_id(self):
        assert _validate_sf_id("003000000000001", "x") == "003000000000001"

    def test_accepts_18_char_id(self):
        assert _validate_sf_id("003000000000001AAA", "x") == "003000000000001AAA"

    def test_rejects_short_id(self):
        with pytest.raises(ValueError, match="Invalid Salesforce ID"):
            _validate_sf_id("short", "record_id")

    def test_rejects_id_with_special_chars(self):
        with pytest.raises(ValueError, match="Invalid Salesforce ID"):
            _validate_sf_id("003abc' OR '1'='1", "record_id")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Invalid Salesforce ID"):
            _validate_sf_id("", "task_id")

    async def test_get_record_rejects_bad_id(self, mock_context):
        result = await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": "bad-id!"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid Salesforce ID" in result.result.message

    async def test_get_task_summary_rejects_bad_id(self, mock_context):
        result = await salesforce.execute_action("get_task_summary", {"task_id": "bad-id!"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid Salesforce ID" in result.result.message

    async def test_get_event_summary_rejects_bad_id(self, mock_context):
        result = await salesforce.execute_action("get_event_summary", {"event_id": "bad-id!"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid Salesforce ID" in result.result.message


# ---- Config Validation ----


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        defined = set(config.get("actions", {}).keys())
        registered = set(salesforce._action_handlers.keys())
        assert not (defined - registered), f"Missing handlers: {defined - registered}"
        assert not (registered - defined), f"Extra handlers: {registered - defined}"

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


# ---- Helper: _build_task_query ----


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


# ---- Helper: _build_event_query ----


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


# ---- Helper: _summarise_task ----


class TestSummariseTask:
    def test_full_task(self):
        task = {
            "Subject": "Follow up call",
            "Status": "Not Started",
            "Priority": "High",
            "ActivityDate": "2026-05-01",
            "Description": "Call the client.",
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


# ---- Helper: _summarise_event ----


class TestSummariseEvent:
    def test_full_event(self):
        event = {
            "Subject": "Quarterly review",
            "StartDateTime": "2026-05-01T09:00:00Z",
            "EndDateTime": "2026-05-01T10:00:00Z",
            "Location": "Board Room",
            "Description": "Q1 results.",
            "IsAllDayEvent": False,
        }
        summary = _summarise_event(event)
        assert "Quarterly review" in summary
        assert "Board Room" in summary
        assert "(All day)" not in summary

    def test_all_day_event_label(self):
        summary = _summarise_event({"Subject": "Holiday", "IsAllDayEvent": True})
        assert "(All day)" in summary

    def test_missing_fields_use_defaults(self):
        summary = _summarise_event({})
        assert "No subject" in summary
        assert "No location" in summary
        assert "No description" in summary


# ---- search_records ----


class TestSearchRecords:
    async def test_returns_records(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"records": [{"Id": "003000000000001", "Name": "Jane Doe"}], "totalSize": 1, "done": True},
        )
        result = await salesforce.execute_action(
            "search_records", {"soql": "SELECT Id, Name FROM Contact LIMIT 1"}, mock_context
        )
        assert result.result.data["result"] is True
        assert len(result.result.data["records"]) == 1
        assert result.result.data["total_size"] == 1

    async def test_passes_soql_as_query_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [], "totalSize": 0, "done": True}
        )
        soql = "SELECT Id FROM Lead LIMIT 5"
        await salesforce.execute_action("search_records", {"soql": soql}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == soql

    async def test_uses_bearer_auth_header(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [], "totalSize": 0, "done": True}
        )
        await salesforce.execute_action("search_records", {"soql": "SELECT Id FROM Contact"}, mock_context)
        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {TEST_TOKEN}"

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await salesforce.execute_action("search_records", {"soql": "SELECT Id FROM Contact"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message

    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [], "totalSize": 0, "done": True}
        )
        result = await salesforce.execute_action(
            "search_records", {"soql": "SELECT Id FROM Contact WHERE Name = 'Nobody'"}, mock_context
        )
        assert result.result.data["result"] is True
        assert result.result.data["records"] == []


# ---- get_record ----


class TestGetRecord:
    async def test_returns_record(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"Id": "003000000000001", "Name": "Jane Doe", "Email": "jane@example.com"}
        )
        result = await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": "003000000000001"}, mock_context
        )
        assert result.result.data["result"] is True
        assert result.result.data["record"]["Name"] == "Jane Doe"

    async def test_url_contains_object_type_and_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"Id": "003000000000001"})
        await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": "003000000000001"}, mock_context
        )
        assert "/sobjects/Contact/003000000000001" in mock_context.fetch.call_args.args[0]

    async def test_fields_param_passed_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"Id": "003000000000001", "Name": "Jane"}
        )
        await salesforce.execute_action(
            "get_record",
            {"object_type": "Contact", "record_id": "003000000000001", "fields": "Id,Name"},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["params"]["fields"] == "Id,Name"

    async def test_no_fields_param_when_not_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"Id": "003000000000001"})
        await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": "003000000000001"}, mock_context
        )
        assert "fields" not in mock_context.fetch.call_args.kwargs.get("params", {})

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        result = await salesforce.execute_action(
            "get_record", {"object_type": "Contact", "record_id": "003000000000001"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


# ---- update_record ----


class TestUpdateRecord:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)
        result = await salesforce.execute_action(
            "update_record",
            {"object_type": "Contact", "record_id": "003000000000001", "fields": {"Phone": "0400000000"}},
            mock_context,
        )
        assert result.result.data["result"] is True
        assert result.result.data["record_id"] == "003000000000001"
        assert result.result.data["object_type"] == "Contact"

    async def test_uses_patch_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)
        await salesforce.execute_action(
            "update_record",
            {"object_type": "Lead", "record_id": "00Q000000000001", "fields": {"Title": "Manager"}},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    async def test_fields_sent_as_json_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)
        fields = {"Phone": "0400000000", "Title": "Director"}
        await salesforce.execute_action(
            "update_record", {"object_type": "Contact", "record_id": "003000000000001", "fields": fields}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == fields

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")
        result = await salesforce.execute_action(
            "update_record",
            {"object_type": "Contact", "record_id": "003000000000001", "fields": {"Name": "X"}},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# ---- list_tasks ----


class TestListTasks:
    async def test_returns_tasks(self, mock_context):
        tasks = [{"Id": "00T000000000001", "Subject": "Call client", "Status": "Not Started"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": tasks, "totalSize": 1})
        result = await salesforce.execute_action("list_tasks", {}, mock_context)
        assert result.result.data["result"] is True
        assert len(result.result.data["tasks"]) == 1
        assert result.result.data["total_size"] == 1

    async def test_status_filter_in_soql(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("list_tasks", {"status": "Completed"}, mock_context)
        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "Status = 'Completed'" in soql

    async def test_date_filter_in_soql(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action(
            "list_tasks", {"due_date_from": "2026-01-01", "due_date_to": "2026-06-30"}, mock_context
        )
        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "ActivityDate >= 2026-01-01" in soql
        assert "ActivityDate <= 2026-06-30" in soql

    async def test_default_limit_25(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("list_tasks", {}, mock_context)
        assert "LIMIT 25" in mock_context.fetch.call_args.kwargs["params"]["q"]

    async def test_custom_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("list_tasks", {"limit": 50}, mock_context)
        assert "LIMIT 50" in mock_context.fetch.call_args.kwargs["params"]["q"]

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")
        result = await salesforce.execute_action("list_tasks", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- list_events ----


class TestListEvents:
    async def test_returns_events(self, mock_context):
        events = [{"Id": "00U000000000001", "Subject": "Client meeting"}]
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": events, "totalSize": 1}
        )
        result = await salesforce.execute_action("list_events", {}, mock_context)
        assert result.result.data["result"] is True
        assert len(result.result.data["events"]) == 1

    async def test_date_filter_in_soql(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action(
            "list_events", {"start_date_from": "2026-05-01", "start_date_to": "2026-05-31"}, mock_context
        )
        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "StartDateTime >= 2026-05-01T00:00:00Z" in soql
        assert "StartDateTime <= 2026-05-31T23:59:59Z" in soql

    async def test_default_limit_25(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("list_events", {}, mock_context)
        assert "LIMIT 25" in mock_context.fetch.call_args.kwargs["params"]["q"]

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("network error")
        result = await salesforce.execute_action("list_events", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- get_task_summary ----


class TestGetTaskSummary:
    async def test_returns_summary(self, mock_context):
        task = {
            "Id": "00T000000000001",
            "Subject": "Follow up",
            "Status": "In Progress",
            "Priority": "High",
            "ActivityDate": "2026-05-10",
            "Description": "Check contract.",
        }
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [task], "totalSize": 1}
        )
        result = await salesforce.execute_action("get_task_summary", {"task_id": "00T000000000001"}, mock_context)
        assert result.result.data["result"] is True
        assert "Follow up" in result.result.data["summary"]
        assert "In Progress" in result.result.data["summary"]
        assert result.result.data["task"]["Id"] == "00T000000000001"

    async def test_task_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        result = await salesforce.execute_action("get_task_summary", {"task_id": "00T000000000001"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message.lower()

    async def test_soql_filters_by_task_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("get_task_summary", {"task_id": "00T000000000001"}, mock_context)
        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "00T000000000001" in soql
        assert "FROM Task" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await salesforce.execute_action("get_task_summary", {"task_id": "00T000000000001"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- get_event_summary ----


class TestGetEventSummary:
    async def test_returns_summary(self, mock_context):
        event = {
            "Id": "00U000000000001",
            "Subject": "Board meeting",
            "StartDateTime": "2026-06-01T09:00:00Z",
            "EndDateTime": "2026-06-01T11:00:00Z",
            "Location": "HQ",
            "Description": "Annual review.",
            "IsAllDayEvent": False,
        }
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [event], "totalSize": 1}
        )
        result = await salesforce.execute_action("get_event_summary", {"event_id": "00U000000000001"}, mock_context)
        assert result.result.data["result"] is True
        assert "Board meeting" in result.result.data["summary"]
        assert "HQ" in result.result.data["summary"]
        assert result.result.data["event"]["Id"] == "00U000000000001"

    async def test_event_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        result = await salesforce.execute_action("get_event_summary", {"event_id": "00U000000000001"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message.lower()

    async def test_all_day_event_in_summary(self, mock_context):
        event = {"Id": "00U000000000001", "Subject": "Public Holiday", "IsAllDayEvent": True}
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"records": [event], "totalSize": 1}
        )
        result = await salesforce.execute_action("get_event_summary", {"event_id": "00U000000000001"}, mock_context)
        assert "(All day)" in result.result.data["summary"]

    async def test_soql_filters_by_event_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"records": [], "totalSize": 0})
        await salesforce.execute_action("get_event_summary", {"event_id": "00U000000000001"}, mock_context)
        soql = mock_context.fetch.call_args.kwargs["params"]["q"]
        assert "00U000000000001" in soql
        assert "FROM Event" in soql

    async def test_error_returns_false(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")
        result = await salesforce.execute_action("get_event_summary", {"event_id": "00U000000000001"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
