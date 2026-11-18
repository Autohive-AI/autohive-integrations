from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit

LEADS_URL = "https://api.hubapi.com/crm/objects/2026-09/leads"
NEW_LEAD = {"name": "Jane Doe", "contact_id": "12345"}
NEW_LEAD_PAYLOAD = {
    "properties": {"hs_lead_name": "Jane Doe"},
    "associations": [
        {"to": {"id": "12345"}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 578}]}
    ],
}
LEAD = {"id": "12", "properties": {"hs_lead_name": "Jane Doe"}}
CHANGES = {"hs_lead_label": "WARM"}
UPDATE = {"lead_id": "12", "properties": CHANGES}
BATCH_RESULT = {"status": "COMPLETE", "results": [LEAD], "errors": [{"message": "Invalid record"}]}


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.fetch = AsyncMock()
    ctx.config = {"max_retries": 3}
    return ctx


@pytest.mark.parametrize("cursor", ["next-page", None])
async def test_list_reads_cursor_and_serializes_properties(context, cursor):
    payload = {"results": [LEAD]}
    if cursor:
        payload["paging"] = {"next": {"after": cursor}}
    context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)
    result = await hubspot.execute_action(
        "list_leads", {"limit": 20, "after": "current", "properties": ["hs_lead_name", "hs_lead_label"]}, context
    )
    assert result.result.data == {"leads": [LEAD], "after": cursor}
    assert context.fetch.call_args.args == (LEADS_URL,)
    assert context.fetch.call_args.kwargs["params"] == {
        "limit": 20,
        "after": "current",
        "properties": "hs_lead_name,hs_lead_label",
    }


@pytest.mark.parametrize(
    "action, inputs, method, path, request_body, status, payload, expected",
    [
        ("get_lead", {"lead_id": "12"}, "GET", "/12", None, 200, LEAD, {"lead": LEAD}),
        ("create_lead", NEW_LEAD, "POST", "", NEW_LEAD_PAYLOAD, 201, LEAD, {"lead": LEAD}),
        ("update_lead", UPDATE, "PATCH", "/12", {"properties": CHANGES}, 200, LEAD, {"lead": LEAD}),
        ("archive_lead", {"lead_id": "12"}, "DELETE", "/12", None, 204, None, {"archived": True}),
        (
            "merge_leads",
            {"primary_lead_id": "12", "lead_id_to_merge": "34"},
            "POST",
            "/merge",
            {"primaryObjectId": "12", "objectIdToMerge": "34"},
            200,
            {"id": "56"},
            {"lead": {"id": "56"}},
        ),
        (
            "batch_create_leads",
            {"leads": [NEW_LEAD]},
            "POST",
            "/batch/create",
            {"inputs": [{**NEW_LEAD_PAYLOAD, "objectWriteTraceId": "0"}]},
            207,
            BATCH_RESULT,
            BATCH_RESULT,
        ),
        (
            "batch_update_leads",
            {"leads": [UPDATE]},
            "POST",
            "/batch/update",
            {"inputs": [{"id": "12", "properties": CHANGES, "objectWriteTraceId": "0"}]},
            207,
            BATCH_RESULT,
            BATCH_RESULT,
        ),
        (
            "batch_archive_leads",
            {"lead_ids": ["12", "34"]},
            "POST",
            "/batch/archive",
            {"inputs": [{"id": "12"}, {"id": "34"}]},
            204,
            None,
            {"archived": True},
        ),
        (
            "remove_lead_association",
            {"lead_id": "12", "to_object_type": "contacts", "to_object_id": "12345", "association_type_id": 578},
            "DELETE",
            "/12/associations/contacts/12345/578",
            None,
            204,
            None,
            {"removed": True},
        ),
    ],
)
async def test_lead_actions(context, action, inputs, method, path, request_body, status, payload, expected):
    context.fetch.return_value = FetchResponse(status=status, headers={}, data=payload)
    result = await hubspot.execute_action(action, inputs, context)
    assert result.result.data == expected
    assert context.fetch.call_args.args == (LEADS_URL + path,)
    assert context.fetch.call_args.kwargs.get("method", "GET") == method
    assert context.fetch.call_args.kwargs.get("json") == request_body


async def test_create_does_not_retry_when_hubspot_may_have_already_created_the_lead(context):
    context.fetch.side_effect = TimeoutError()
    result = await hubspot.execute_action("create_lead", NEW_LEAD, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Check HubSpot before retrying" in result.result.message
    assert context.fetch.call_args.kwargs["retry_count"] == 3
    context.fetch.assert_awaited_once()


async def test_missing_scope_is_an_action_error(context):
    context.fetch.side_effect = HTTPError(403, "MISSING_SCOPES", {})
    result = await hubspot.execute_action("list_leads", {}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "MISSING_SCOPES" in result.result.message
