"""
Unit tests for the Zoho CRM integration using mocked fetch.

All tests are CI-safe: fetch is mocked, no credentials required. Covers every
action's success path, its ActionError path (fetch raises), validation errors
for missing required inputs, and the Zoho-specific soft-error paths — a 200
response carrying a non-SUCCESS code, or an empty data envelope, must surface
as an ActionError rather than a silent success.
"""

import importlib.util
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

# The integration folder ships an __init__.py that turns `zoho` into a package
# exposing nothing, so `import zoho` is ambiguous with zoho.py. Load the action
# source directly by file path to get the integration object plus its helpers.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("zoho_integration_mod", os.path.join(_parent, "zoho.py"))
zoho_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zoho_mod)

zoho = zoho_mod.zoho
build_contact_data = zoho_mod.build_contact_data
build_account_data = zoho_mod.build_account_data
build_deal_data = zoho_mod.build_deal_data
build_lead_data = zoho_mod.build_lead_data
build_task_data = zoho_mod.build_task_data
build_event_data = zoho_mod.build_event_data
build_call_data = zoho_mod.build_call_data
build_query_params = zoho_mod.build_query_params
build_search_params = zoho_mod.build_search_params
build_notes_query_params = zoho_mod.build_notes_query_params
get_default_fields_for_module = zoho_mod.get_default_fields_for_module
get_zoho_api_url = zoho_mod.get_zoho_api_url
build_zoho_headers = zoho_mod.build_zoho_headers

pytestmark = pytest.mark.unit

AUTH = {"credentials": {"access_token": "test-token", "api_domain": "https://www.zohoapis.com"}}  # nosec B105


# =============================================================================
# Context / response helpers
# =============================================================================


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    """Context whose fetch returns a single FetchResponse."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = AUTH
    return ctx


def make_ctx_multi(responses):
    """Context whose fetch returns a sequence of FetchResponses."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = AUTH
    return ctx


def make_ctx_error(exc=None):
    """Context whose fetch raises — exercises the ActionError path."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc or Exception("API request failed"))
    ctx.auth = AUTH
    return ctx


def crud_success(record_id="100"):
    """A Zoho write-envelope reporting SUCCESS."""
    return {"data": [{"code": "SUCCESS", "details": {"id": record_id}}]}


def crud_failure(message="Required field missing", code="MANDATORY_NOT_FOUND"):
    """A 200 response whose record reports a non-SUCCESS code."""
    return {"data": [{"code": code, "message": message}]}


def empty_envelope():
    return {"data": []}


# Maps each write-style action to a representative valid input payload.
RECORD_INPUTS = {
    "contact": {"Last_Name": "Doe", "First_Name": "Jane", "Email": "jane@example.com"},
    "account": {"Account_Name": "Acme Inc"},
    "deal": {"Deal_Name": "Big Deal", "Stage": "Qualification"},
    "lead": {"Last_Name": "Prospect", "Company": "Lead Co"},
    "task": {"Subject": "Follow up"},
    "event": {
        "Event_Title": "Demo",
        "Start_DateTime": "2026-01-01T10:00:00+00:00",
        "End_DateTime": "2026-01-01T11:00:00+00:00",
    },
    "call": {"Subject": "Intro call", "Call_Type": "Outbound", "Call_Start_Time": "2026-01-01T10:00:00+00:00"},
}


# =============================================================================
# Pure helpers
# =============================================================================


class TestHelpers:
    def test_build_contact_data_filters_empty(self):
        data = build_contact_data({"Last_Name": "Doe", "First_Name": "", "Phone": None, "Email": "x@y.com"})
        assert data == {"Last_Name": "Doe", "Email": "x@y.com"}

    def test_build_account_data_maps_employee_field(self):
        data = build_account_data({"Account_Name": "Acme", "No_of_Employees": 50})
        assert data["Account_Name"] == "Acme"
        assert data["Employees"] == 50

    def test_build_deal_data(self):
        data = build_deal_data({"Deal_Name": "D", "Stage": "S", "Amount": 0})
        # Amount 0 is falsy -> filtered out, matching the integration's existing behaviour
        assert data == {"Deal_Name": "D", "Stage": "S"}

    def test_build_lead_data_maps_employee_field(self):
        data = build_lead_data({"Last_Name": "L", "No_of_Employees": 10})
        assert data["Employees"] == 10

    def test_build_task_data(self):
        data = build_task_data({"Subject": "S", "Priority": "High", "Unknown": "x"})
        assert data == {"Subject": "S", "Priority": "High"}

    def test_build_event_data_keeps_explicit_false(self):
        # build_event_data uses "is not None" so a False All_day must be kept
        data = build_event_data({"Event_Title": "E", "All_day": False})
        assert data["All_day"] is False

    def test_build_call_data(self):
        data = build_call_data({"Subject": "S", "Call_Type": "Inbound"})
        assert data == {"Subject": "S", "Call_Type": "Inbound"}

    def test_build_query_params_defaults_fields(self):
        params = build_query_params({"page": 2, "per_page": 50})
        assert params["page"] == "2"
        assert params["per_page"] == "50"
        assert "First_Name" in params["fields"]

    def test_build_query_params_explicit_fields(self):
        params = build_query_params({"fields": ["Email", "Phone"]})
        assert params["fields"] == "Email,Phone"

    def test_build_search_params_criteria(self):
        params = build_search_params(
            {
                "search_type": "criteria",
                "criteria": [{"api_name": "Last_Name", "comparator": "equals", "value": "Doe"}],
            }
        )
        assert params["criteria"] == "(Last_Name:equals:Doe)"

    def test_build_search_params_criteria_list_value(self):
        params = build_search_params(
            {
                "search_type": "criteria",
                "criteria": [{"api_name": "Stage", "comparator": "in", "value": ["A", "B"]}],
            }
        )
        assert params["criteria"] == "(Stage:in:A,B)"

    def test_build_search_params_email(self):
        params = build_search_params({"search_type": "email", "email": "x@y.com"})
        assert params["email"] == "x@y.com"

    def test_build_notes_query_params_caps_per_page(self):
        params = build_notes_query_params({"per_page": 9999})
        assert params["per_page"] == "200"

    def test_build_notes_query_params_defaults_fields(self):
        # Zoho's Notes list endpoint rejects requests without a fields param,
        # so the builder must supply a default when none is specified.
        params = build_notes_query_params({})
        assert "Note_Content" in params["fields"]
        assert "Note_Title" in params["fields"]

    def test_build_notes_query_params_explicit_fields(self):
        params = build_notes_query_params({"fields": ["Note_Title", "Owner"]})
        assert params["fields"] == "Note_Title,Owner"

    def test_get_default_fields_known_and_unknown(self):
        assert "Deal_Name" in get_default_fields_for_module("Deals")
        assert get_default_fields_for_module("Mystery") == ["id"]

    def test_get_zoho_api_url_uses_region_domain(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"access_token": "t", "api_domain": "https://www.zohoapis.eu/"}}  # nosec B105
        url = get_zoho_api_url(ctx, "/Contacts")
        assert url == "https://www.zohoapis.eu/crm/v8/Contacts"

    def test_get_zoho_api_url_defaults_domain(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"access_token": "t"}}  # nosec B105
        assert get_zoho_api_url(ctx, "/Deals").startswith("https://www.zohoapis.com/crm/v8/Deals")

    def test_build_zoho_headers(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"access_token": "abc"}}  # nosec B105
        headers = build_zoho_headers(ctx)
        assert headers["Authorization"] == "Zoho-oauthtoken abc"
        assert headers["Content-Type"] == "application/json"


# =============================================================================
# CREATE actions (contact / account / deal / lead / task / event / call)
# =============================================================================


CREATE_ACTIONS = [
    ("create_contact", "contact"),
    ("create_account", "account"),
    ("create_deal", "deal"),
    ("create_lead", "lead"),
    ("create_task", "task"),
    ("create_event", "event"),
    ("create_call", "call"),
]
RECORD_KEY = {
    "create_contact": "contact",
    "create_account": "account",
    "create_deal": "deal",
    "create_lead": "lead",
    "create_task": "task",
    "create_event": "event",
    "create_call": "call",
}


class TestCreateActions:
    @pytest.mark.parametrize("action,kind", CREATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, kind):
        ctx = make_ctx(crud_success("555"))
        result = await zoho.execute_action(action, RECORD_INPUTS[kind], ctx)
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data[RECORD_KEY[action]]["id"] == "555"
        assert ctx.fetch.call_args.kwargs.get("method") == "POST"

    @pytest.mark.parametrize("action,kind", CREATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_non_success_code_is_action_error(self, action, kind):
        ctx = make_ctx(crud_failure("duplicate data"))
        result = await zoho.execute_action(action, RECORD_INPUTS[kind], ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "duplicate data" in result.result.message

    @pytest.mark.parametrize("action,kind", CREATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_empty_envelope_is_action_error(self, action, kind):
        ctx = make_ctx(empty_envelope())
        result = await zoho.execute_action(action, RECORD_INPUTS[kind], ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "No response data received" in result.result.message

    @pytest.mark.parametrize("action,kind", CREATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, kind):
        ctx = make_ctx_error(Exception("503 Service Unavailable"))
        result = await zoho.execute_action(action, RECORD_INPUTS[kind], ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "503 Service Unavailable" in result.result.message

    @pytest.mark.asyncio
    async def test_create_contact_requires_last_name(self):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action("create_contact", {"First_Name": "Jane"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_create_deal_requires_name_and_stage(self):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action("create_deal", {"Deal_Name": "X"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_create_event_requires_times(self):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action("create_event", {"Event_Title": "X"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# GET actions
# =============================================================================


GET_ACTIONS = [
    ("get_contact", "contact_id", "contact"),
    ("get_account", "account_id", "account"),
    ("get_deal", "deal_id", "deal"),
    ("get_lead", "lead_id", "lead"),
    ("get_task", "task_id", "task"),
    ("get_event", "event_id", "event"),
    ("get_call", "call_id", "call"),
    ("get_note", "note_id", "note"),
]


class TestGetActions:
    @pytest.mark.parametrize("action,id_field,key", GET_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, id_field, key):
        ctx = make_ctx({"data": [{"id": "42", "Name": "Sample"}]})
        result = await zoho.execute_action(action, {id_field: "42"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data[key]["id"] == "42"
        assert ctx.fetch.call_args.kwargs.get("method") == "GET"

    @pytest.mark.parametrize("action,id_field,key", GET_ACTIONS)
    @pytest.mark.asyncio
    async def test_not_found_is_action_error(self, action, id_field, key):
        ctx = make_ctx(empty_envelope())
        result = await zoho.execute_action(action, {id_field: "42"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.parametrize("action,id_field,key", GET_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, id_field, key):
        ctx = make_ctx_error(Exception("404 Not Found"))
        result = await zoho.execute_action(action, {id_field: "42"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "404 Not Found" in result.result.message

    @pytest.mark.parametrize("action,id_field,key", GET_ACTIONS)
    @pytest.mark.asyncio
    async def test_missing_id_is_validation_error(self, action, id_field, key):
        ctx = make_ctx({"data": [{"id": "42"}]})
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# UPDATE actions
# =============================================================================


UPDATE_ACTIONS = [
    ("update_contact", "contact_id", "contact"),
    ("update_account", "account_id", "account"),
    ("update_deal", "deal_id", "deal"),
    ("update_lead", "lead_id", "lead"),
    ("update_task", "task_id", "task"),
    ("update_event", "event_id", "event"),
    ("update_call", "call_id", "call"),
]


class TestUpdateActions:
    @pytest.mark.parametrize("action,id_field,key", UPDATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, id_field, key):
        ctx = make_ctx(crud_success("77"))
        result = await zoho.execute_action(action, {id_field: "77", "Description": "updated"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data[key]["id"] == "77"
        assert ctx.fetch.call_args.kwargs.get("method") == "PUT"

    @pytest.mark.parametrize("action,id_field,key", UPDATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_non_success_code_is_action_error(self, action, id_field, key):
        ctx = make_ctx(crud_failure("invalid data"))
        result = await zoho.execute_action(action, {id_field: "77"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "invalid data" in result.result.message

    @pytest.mark.parametrize("action,id_field,key", UPDATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, id_field, key):
        ctx = make_ctx_error()
        result = await zoho.execute_action(action, {id_field: "77"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.parametrize("action,id_field,key", UPDATE_ACTIONS)
    @pytest.mark.asyncio
    async def test_missing_id_is_validation_error(self, action, id_field, key):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action(action, {"Description": "x"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# DELETE actions
# =============================================================================


DELETE_ACTIONS = [
    ("delete_contact", "contact_id"),
    ("delete_account", "account_id"),
    ("delete_deal", "deal_id"),
    ("delete_lead", "lead_id"),
    ("delete_task", "task_id"),
    ("delete_event", "event_id"),
    ("delete_call", "call_id"),
    ("delete_note", "note_id"),
]


class TestDeleteActions:
    @pytest.mark.parametrize("action,id_field", DELETE_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, id_field):
        ctx = make_ctx(crud_success("9"))
        result = await zoho.execute_action(action, {id_field: "9"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"

    @pytest.mark.parametrize("action,id_field", DELETE_ACTIONS)
    @pytest.mark.asyncio
    async def test_non_success_code_is_action_error(self, action, id_field):
        ctx = make_ctx(crud_failure("record locked"))
        result = await zoho.execute_action(action, {id_field: "9"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "record locked" in result.result.message

    @pytest.mark.parametrize("action,id_field", DELETE_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, id_field):
        ctx = make_ctx_error()
        result = await zoho.execute_action(action, {id_field: "9"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.parametrize("action,id_field", DELETE_ACTIONS)
    @pytest.mark.asyncio
    async def test_missing_id_is_validation_error(self, action, id_field):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_delete_contact_returns_id(self):
        ctx = make_ctx(crud_success("9"))
        result = await zoho.execute_action("delete_contact", {"contact_id": "9"}, ctx)
        assert result.result.data["details"]["id"] == "9"


# =============================================================================
# LIST actions
# =============================================================================


LIST_ACTIONS = [
    ("list_contacts", "contacts"),
    ("list_accounts", "accounts"),
    ("list_deals", "deals"),
    ("list_leads", "leads"),
    ("list_tasks", "tasks"),
    ("list_events", "events"),
    ("list_calls", "calls"),
]


class TestListActions:
    @pytest.mark.parametrize("action,key", LIST_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, key):
        ctx = make_ctx({"data": [{"id": "1"}, {"id": "2"}], "info": {"more_records": False}})
        result = await zoho.execute_action(action, {"page": 1, "per_page": 10}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data[key]) == 2
        assert result.result.data["info"]["more_records"] is False

    @pytest.mark.parametrize("action,key", LIST_ACTIONS)
    @pytest.mark.asyncio
    async def test_empty_list_is_success(self, action, key):
        # An empty result set is a legitimate success, not an error.
        ctx = make_ctx({"data": [], "info": {}})
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data[key] == []

    @pytest.mark.parametrize("action,key", LIST_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, key):
        ctx = make_ctx_error()
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# SEARCH actions
# =============================================================================


SEARCH_ACTIONS = [
    ("search_contacts", "contacts"),
    ("search_accounts", "accounts"),
    ("search_deals", "deals"),
    ("search_leads", "leads"),
    ("search_tasks", "tasks"),
    ("search_events", "events"),
    ("search_calls", "calls"),
]


class TestSearchActions:
    @pytest.mark.parametrize("action,key", SEARCH_ACTIONS)
    @pytest.mark.asyncio
    async def test_success(self, action, key):
        ctx = make_ctx({"data": [{"id": "1"}], "info": {"count": 1}})
        # "word" search is supported by every module (events/calls don't allow email/phone)
        result = await zoho.execute_action(action, {"search_type": "word", "word": "acme"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data[key]) == 1

    @pytest.mark.parametrize("action,key", SEARCH_ACTIONS)
    @pytest.mark.asyncio
    async def test_missing_search_type_is_validation_error(self, action, key):
        ctx = make_ctx({"data": []})
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.parametrize("action,key", SEARCH_ACTIONS)
    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self, action, key):
        ctx = make_ctx_error()
        result = await zoho.execute_action(action, {"search_type": "word", "word": "x"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# 204 / empty body — response.data is None (regression for Codex P2)
# =============================================================================


class TestNoneResponseBody:
    """Zoho returns HTTP 204 with no body for empty modules and missing records;
    SDK 2 surfaces that as ``response.data is None``. List/search reads must
    return an empty result set, and single-record reads must fall through to a
    graceful not-found ActionError instead of an AttributeError leaking through
    the broad ``except`` as a misleading generic failure."""

    @pytest.mark.parametrize("action,key", LIST_ACTIONS)
    @pytest.mark.asyncio
    async def test_list_none_body_is_empty_success(self, action, key):
        ctx = make_ctx(None)
        result = await zoho.execute_action(action, {}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data[key] == []
        assert result.result.data["info"] == {}

    @pytest.mark.parametrize("action,key", SEARCH_ACTIONS)
    @pytest.mark.asyncio
    async def test_search_none_body_is_empty_success(self, action, key):
        ctx = make_ctx(None)
        result = await zoho.execute_action(action, {"search_type": "word", "word": "x"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data[key] == []

    @pytest.mark.parametrize("action,id_field,key", GET_ACTIONS)
    @pytest.mark.asyncio
    async def test_get_none_body_is_graceful_not_found(self, action, id_field, key):
        ctx = make_ctx(None)
        result = await zoho.execute_action(action, {id_field: "42"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "AttributeError" not in (result.result.message or "")

    @pytest.mark.asyncio
    async def test_related_records_none_body_is_empty_success(self):
        ctx = make_ctx(None)
        result = await zoho.execute_action(
            "get_related_records",
            {"module": "Accounts", "record_id": "1", "related_module": "Contacts"},
            ctx,
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["related_records"] == []

    @pytest.mark.asyncio
    async def test_coql_none_body_is_empty_success(self):
        ctx = make_ctx(None)
        result = await zoho.execute_action("execute_coql_query", {"select_query": "select id from Contacts"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"] == []


# =============================================================================
# CONVERT LEAD
# =============================================================================


class TestConvertLead:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx(
            {"data": [{"code": "SUCCESS", "Accounts": {"id": "a1"}, "Contacts": {"id": "c1"}, "Deals": {"id": "d1"}}]}
        )
        result = await zoho.execute_action("convert_lead", {"lead_id": "L1"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        conv = result.result.data["conversion"]
        assert conv["account"]["id"] == "a1"
        assert conv["contact"]["id"] == "c1"
        assert conv["deal"]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_with_deal_creation_builds_payload(self):
        ctx = make_ctx(
            {"data": [{"code": "SUCCESS", "Accounts": {"id": "a1"}, "Contacts": {"id": "c1"}, "Deals": {"id": "d1"}}]}
        )
        await zoho.execute_action(
            "convert_lead",
            {
                "lead_id": "L1",
                "create_deal": True,
                "deal_name": "New Deal",
                "deal_stage": "Closed Won",
                "deal_amount": 1000,
            },
            ctx,
        )
        body = ctx.fetch.call_args.kwargs.get("json", {})
        assert body["data"][0]["Deals"]["Deal_Name"] == "New Deal"
        assert body["data"][0]["Deals"]["Stage"] == "Closed Won"

    @pytest.mark.asyncio
    async def test_non_success_is_action_error(self):
        ctx = make_ctx(crud_failure("conversion not allowed"))
        result = await zoho.execute_action("convert_lead", {"lead_id": "L1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "conversion not allowed" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_lead_id_is_validation_error(self):
        ctx = make_ctx({"data": []})
        result = await zoho.execute_action("convert_lead", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action("convert_lead", {"lead_id": "L1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# COQL QUERY
# =============================================================================


class TestExecuteCOQL:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"data": [{"Last_Name": "Doe"}], "info": {"count": 1}})
        result = await zoho.execute_action(
            "execute_coql_query", {"select_query": "SELECT Last_Name FROM Contacts LIMIT 1"}, ctx
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"][0]["Last_Name"] == "Doe"
        assert ctx.fetch.call_args.kwargs.get("json") == {"select_query": "SELECT Last_Name FROM Contacts LIMIT 1"}

    @pytest.mark.asyncio
    async def test_missing_query_is_validation_error(self):
        ctx = make_ctx({"data": []})
        result = await zoho.execute_action("execute_coql_query", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_fetch_raises_is_action_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action("execute_coql_query", {"select_query": "SELECT id FROM Leads"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# RELATED RECORDS / NOTES
# =============================================================================


class TestRelatedRecords:
    @pytest.mark.asyncio
    async def test_get_related_records_success(self):
        ctx = make_ctx({"data": [{"id": "d1", "Deal_Name": "X"}], "info": {"count": 1}})
        result = await zoho.execute_action(
            "get_related_records",
            {"module": "Accounts", "record_id": "a1", "related_module": "Deals"},
            ctx,
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["related_records"][0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_get_related_records_missing_field_validation_error(self):
        ctx = make_ctx({"data": []})
        result = await zoho.execute_action("get_related_records", {"module": "Accounts"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_get_related_records_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action(
            "get_related_records",
            {"module": "Accounts", "record_id": "a1", "related_module": "Deals"},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_update_related_records_success(self):
        ctx = make_ctx(crud_success("rr1"))
        result = await zoho.execute_action(
            "update_related_records",
            {
                "module": "Accounts",
                "record_id": "a1",
                "related_module": "Contacts",
                "related_record_id": "c1",
                "update_data": {"Description": "linked"},
            },
            ctx,
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["updated_record"]["id"] == "rr1"

    @pytest.mark.asyncio
    async def test_update_related_records_non_success_is_action_error(self):
        ctx = make_ctx(crud_failure("not related"))
        result = await zoho.execute_action(
            "update_related_records",
            {
                "module": "Accounts",
                "record_id": "a1",
                "related_module": "Contacts",
                "related_record_id": "c1",
                "update_data": {"Description": "x"},
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_create_note_success(self):
        ctx = make_ctx(crud_success("n1"))
        result = await zoho.execute_action(
            "create_note",
            {"module": "Contacts", "record_id": "c1", "Note_Content": "Important"},
            ctx,
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["note"]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_create_note_missing_content_validation_error(self):
        ctx = make_ctx(crud_success())
        result = await zoho.execute_action("create_note", {"module": "Contacts", "record_id": "c1"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_get_contact_notes_success(self):
        ctx = make_ctx({"data": [{"id": "n1", "Note_Content": "hi"}], "info": {"count": 1}})
        result = await zoho.execute_action("get_contact_notes", {"module": "Contacts", "record_id": "c1"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["notes"][0]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_update_note_success(self):
        ctx = make_ctx(crud_success("n1"))
        result = await zoho.execute_action("update_note", {"note_id": "n1", "Note_Content": "edited"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["note"]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_delete_note_success_message(self):
        ctx = make_ctx(crud_success("n1"))
        result = await zoho.execute_action("delete_note", {"note_id": "n1"}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["message"] == "Note deleted successfully"


# =============================================================================
# AGGREGATE / MULTI-FETCH actions
# =============================================================================


class TestAggregateActions:
    @pytest.mark.asyncio
    async def test_account_hierarchy_success(self):
        # 1 fetch for the account + 1 per requested module
        ctx = make_ctx_multi(
            [
                {"data": [{"id": "a1", "Account_Name": "Acme"}]},
                {"data": [{"id": "c1"}, {"id": "c2"}]},
            ]
        )
        result = await zoho.execute_action(
            "get_account_hierarchy", {"account_id": "a1", "include_modules": ["Contacts"]}, ctx
        )
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["account"]["id"] == "a1"
        assert len(data["contacts"]) == 2

    @pytest.mark.asyncio
    async def test_account_hierarchy_module_fetch_failure_is_tolerated(self):
        # account fetch succeeds, the related-module fetch raises -> that module is empty,
        # but the action still returns success (per-module errors are swallowed by design).
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if url.endswith("/Accounts/a1"):
                return ok({"data": [{"id": "a1"}]})
            raise Exception("module fetch failed")

        ctx = MagicMock(name="ExecutionContext")
        ctx.fetch = AsyncMock(side_effect=side_effect)
        ctx.auth = AUTH
        result = await zoho.execute_action(
            "get_account_hierarchy", {"account_id": "a1", "include_modules": ["Contacts"]}, ctx
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["contacts"] == []

    @pytest.mark.asyncio
    async def test_account_hierarchy_top_level_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action("get_account_hierarchy", {"account_id": "a1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_contact_activities_success_and_summary(self):
        ctx = make_ctx_multi(
            [
                {"data": [{"id": "c1", "First_Name": "Jane"}]},
                {"data": [{"id": "t1"}, {"id": "t2"}]},
            ]
        )
        result = await zoho.execute_action(
            "get_contact_activities", {"contact_id": "c1", "include_modules": ["Tasks"]}, ctx
        )
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["contact"]["id"] == "c1"
        assert data["activity_summary"]["total_tasks"] == 2

    @pytest.mark.asyncio
    async def test_contact_activities_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action("get_contact_activities", {"contact_id": "c1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_deal_relationships_minimal(self):
        # deal has no Account_Name/Contact_Name dicts and activities are disabled,
        # so only the initial deal fetch occurs.
        ctx = make_ctx({"data": [{"id": "d1", "Deal_Name": "Big"}]})
        result = await zoho.execute_action(
            "get_deal_relationships", {"deal_id": "d1", "include_activities": False}, ctx
        )
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["deal"]["id"] == "d1"
        assert data["relationship_summary"]["has_account"] is False

    @pytest.mark.asyncio
    async def test_deal_relationships_with_account_and_activities(self):
        ctx = make_ctx_multi(
            [
                {"data": [{"id": "d1", "Account_Name": {"id": "a1"}}]},
                {"data": [{"id": "a1", "Account_Name": "Acme"}]},  # account lookup
                {"data": [{"id": "t1"}]},  # Tasks
                {"data": []},  # Events
                {"data": [{"id": "ca1"}]},  # Calls
            ]
        )
        result = await zoho.execute_action("get_deal_relationships", {"deal_id": "d1", "include_activities": True}, ctx)
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["relationship_summary"]["has_account"] is True
        assert data["relationship_summary"]["total_activities"] == 2

    @pytest.mark.asyncio
    async def test_deal_relationships_error(self):
        ctx = make_ctx_error()
        result = await zoho.execute_action("get_deal_relationships", {"deal_id": "d1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
