import asyncio

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit


async def test_create_call_logs_and_associates_contact(make_context):
    context = make_context()
    context.fetch.return_value = FetchResponse(status=201, headers={}, data={"id": "10"})
    result = await hubspot.execute_action(
        "create_call", {"title": "Follow-up", "contact_id": "20", "duration_ms": 0}, context
    )
    assert result.result.data["call"]["id"] == "10"
    request = context.fetch.call_args
    assert request.args[0] == "https://api.hubapi.com/crm/v3/objects/calls"
    assert request.kwargs["method"] == "POST"
    payload = request.kwargs["json"]
    assert payload["properties"]["hs_timestamp"].isdigit()
    assert payload["properties"]["hs_call_duration"] == "0"
    assert payload["associations"] == [
        {"to": {"id": "20"}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 194}]}
    ]


async def test_update_meeting_patches_only_supplied_fields(make_context):
    context = make_context()
    context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "10"})
    start = "2026-11-10T12:00:00Z"
    result = await hubspot.execute_action(
        "update_meeting", {"meeting_id": "10", "body": "", "start_time": start}, context
    )
    assert result.result.data["meeting"]["id"] == "10"
    request = context.fetch.call_args
    assert request.args[0] == "https://api.hubapi.com/crm/v3/objects/meetings/10"
    assert request.kwargs["method"] == "PATCH"
    assert request.kwargs["json"] == {
        "properties": {"hs_meeting_body": "", "hs_meeting_start_time": start, "hs_timestamp": start}
    }


async def test_update_meeting_rejects_empty_patch(make_context):
    context = make_context()
    result = await hubspot.execute_action("update_meeting", {"meeting_id": "10"}, context)
    assert result.type == ResultType.ACTION_ERROR
    context.fetch.assert_not_called()


@pytest.mark.parametrize("unconfirmed", [asyncio.TimeoutError(), FetchResponse(status=201, headers={}, data={})])
async def test_create_call_reports_uncertain_write_without_resending(make_context, unconfirmed):
    context = make_context()
    context.config = {"max_retries": 3}
    context.fetch.side_effect = [unconfirmed]
    result = await hubspot.execute_action("create_call", {"title": "Follow-up"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "before retrying" in result.result.message
    context.fetch.assert_awaited_once()
    assert context.fetch.call_args.kwargs["retry_count"] == 3
