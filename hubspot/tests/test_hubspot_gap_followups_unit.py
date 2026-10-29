"""Regression coverage for the remaining customer workflow gaps."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType
from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


@pytest.fixture
def ctx():
    context = MagicMock()
    context.fetch = AsyncMock()
    context.metadata = {}
    context.config = {"max_retries": 3}
    return context


async def test_connected_user_resolves_metadata_email_without_reading_tokens(ctx):
    ctx.metadata = {"connected_user": "rep@example.com", "hub_id": 42}
    owner = {"id": "7", "email": "rep@example.com", "userId": 81}
    ctx.fetch.return_value = ok({"results": [owner]})
    result = await hubspot.execute_action("get_current_user", {}, ctx)
    assert result.result.data == {"email": "rep@example.com", "owner": owner, "portal_id": 42}
    assert ctx.fetch.call_args.kwargs["params"]["email"] == "rep@example.com"


async def test_connected_user_missing_metadata_requires_reconnect(ctx):
    result = await hubspot.execute_action("get_current_user", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Reconnect" in result.result.message
    ctx.fetch.assert_not_called()


async def test_connected_user_without_owner_is_still_identified(ctx):
    ctx.metadata = {"connected_user": "rep@example.com"}
    ctx.fetch.return_value = ok({"results": []})
    result = await hubspot.execute_action("get_current_user", {}, ctx)
    assert result.result.data["email"] == "rep@example.com"
    assert result.result.data["owner"] is None


async def test_custom_schema_discovery(ctx):
    schemas = [{"objectTypeId": "2-123", "name": "projects"}]
    ctx.fetch.return_value = ok({"results": schemas})
    result = await hubspot.execute_action("get_object_schemas", {}, ctx)
    assert result.result.data == {"schemas": schemas}
    assert ctx.fetch.call_args.args[0].endswith("/crm-object-schemas/2026-09/schemas")


async def test_create_ticket_uses_internal_stage_and_disables_transport_retries(ctx):
    ctx.fetch.return_value = ok({"id": "12", "properties": {"subject": "Help"}}, 201)
    result = await hubspot.execute_action(
        "create_ticket",
        {"subject": "Help", "hs_pipeline_stage": "1", "hs_pipeline": "0", "properties": {"hs_ticket_priority": "HIGH"}},
        ctx,
    )
    assert result.result.data["ticket"]["id"] == "12"
    call = ctx.fetch.call_args
    assert call.args[0].endswith("/crm/objects/2026-09/tickets")
    assert call.kwargs["method"] == "POST"
    assert call.kwargs["retry_count"] == 3
    assert call.kwargs["json"]["properties"] == {
        "subject": "Help",
        "hs_pipeline_stage": "1",
        "hs_pipeline": "0",
        "hs_ticket_priority": "HIGH",
    }


async def test_update_ticket_preserves_empty_string_to_clear_property(ctx):
    ctx.fetch.return_value = ok({"id": "12", "properties": {"content": ""}})
    result = await hubspot.execute_action("update_ticket", {"ticket_id": "12", "properties": {"content": ""}}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.kwargs["method"] == "PATCH"
    assert ctx.fetch.call_args.kwargs["json"] == {"properties": {"content": ""}}


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("create_ticket", {"subject": "Help"}),
        ("update_ticket", {"ticket_id": "../12", "properties": {"subject": "Help"}}),
        ("update_ticket", {"ticket_id": "12", "properties": {}}),
    ],
)
async def test_invalid_ticket_inputs_make_no_request(ctx, action, inputs):
    result = await hubspot.execute_action(action, inputs, ctx)
    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("create_ticket", {"subject": "Help", "hs_pipeline_stage": "1"}),
        ("update_ticket", {"ticket_id": "12", "properties": {"subject": "Help"}}),
        ("get_object_schemas", {}),
        ("search_conversations", {}),
    ],
)
async def test_provider_permission_errors_are_reported(ctx, action, inputs):
    ctx.fetch.side_effect = HTTPError(403, "Missing scope")
    result = await hubspot.execute_action(action, inputs, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "403" in result.result.message


async def test_conversation_filters_and_next_cursor(ctx):
    ctx.fetch.return_value = ok({"results": [{"id": "9"}], "paging": {"next": {"after": "10"}}})
    result = await hubspot.execute_action(
        "search_conversations",
        {
            "inbox_id": "1",
            "contact_id": "2",
            "ticket_id": "3",
            "status": "OPEN",
            "archived": False,
            "limit": 20,
            "after": "8",
        },
        ctx,
    )
    assert ctx.fetch.call_args.kwargs["params"] == {
        "inboxId": "1",
        "associatedContactId": "2",
        "associatedTicketId": "3",
        "threadStatus": "OPEN",
        "archived": "false",
        "limit": 20,
        "after": "8",
        "sort": "id",
        "association": "TICKET",
    }
    assert result.result.data["has_more"] is True
    assert result.result.data["after"] == "10"


async def test_preserve_existing_labels_across_association_pages(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"category": "USER_DEFINED", "typeId": 42, "label": "Architect"}]}),
        ok({"results": [{"from": {"id": "5"}, "to": [], "paging": {"next": {"after": "next"}}}]}),
        ok(
            {
                "results": [
                    {
                        "from": {"id": "5"},
                        "to": [
                            {
                                "toObjectId": 1,
                                "associationTypes": [
                                    {"category": "USER_DEFINED", "typeId": 41, "label": "Decision maker"}
                                ],
                            },
                            {
                                "toObjectId": 2,
                                "associationTypes": [{"category": "USER_DEFINED", "typeId": 99, "label": "Other"}],
                            },
                        ],
                    }
                ]
            }
        ),
        ok({}),
    ]
    result = await hubspot.execute_action(
        "create_association",
        {
            "from_object_type": "deals",
            "from_object_id": "5",
            "to_object_type": "contacts",
            "to_object_id": "1",
            "label": "Architect",
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.kwargs["json"] == [
        {"associationCategory": "USER_DEFINED", "associationTypeId": 41},
        {"associationCategory": "USER_DEFINED", "associationTypeId": 42},
    ]


async def test_dont_replace_labels_when_existing_labels_cannot_be_read(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"category": "USER_DEFINED", "typeId": 42, "label": "Architect"}]}),
        HTTPError(403, "Forbidden"),
    ]
    result = await hubspot.execute_action(
        "create_association",
        {
            "from_object_type": "deals",
            "from_object_id": "5",
            "to_object_type": "contacts",
            "to_object_id": "1",
            "label": "Architect",
        },
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert all(call.kwargs.get("method") != "PUT" for call in ctx.fetch.call_args_list)


async def test_custom_lookup_property_is_retained_with_reordered_results(ctx):
    records = [
        {"id": "9", "properties": {"external_id": "b", "amount": "2"}},
        {"id": "8", "properties": {"external_id": "a", "amount": "1"}},
    ]
    ctx.fetch.return_value = ok({"results": records})
    properties = ["amount"]
    result = await hubspot.execute_action(
        "get_crm_objects",
        {"object_type": "deals", "ids": ["a", "b"], "id_property": "external_id", "properties": properties},
        ctx,
    )
    assert ctx.fetch.call_args.kwargs["json"]["properties"] == ["amount", "external_id"]
    assert properties == ["amount"]
    assert {record["properties"]["external_id"]: record["id"] for record in result.result.data["results"]} == {
        "a": "8",
        "b": "9",
    }


async def test_pipeline_backed_stage_options(ctx):
    ctx.fetch.side_effect = [
        ok(
            {
                "results": [
                    {
                        "name": "dealstage",
                        "label": "Deal Stage",
                        "type": "enumeration",
                        "externalOptions": True,
                        "options": [],
                    }
                ]
            }
        ),
        ok({"results": [{"id": "default", "label": "Sales", "stages": [{"id": "won", "label": "Won"}]}]}),
    ]
    result = await hubspot.execute_action(
        "get_object_properties", {"object_type": "deals", "include_details": True}, ctx
    )
    assert result.result.data["properties"][0]["options"] == [
        {"label": "Won", "value": "won", "pipeline_id": "default"}
    ]
    assert ctx.fetch.call_args.args[0].endswith("/crm/pipelines/2026-09/deals")


async def test_ticket_timeout_warns_of_unknown_outcome_without_retry(ctx):
    import asyncio

    ctx.fetch.side_effect = asyncio.TimeoutError()
    result = await hubspot.execute_action("create_ticket", {"subject": "Help", "hs_pipeline_stage": "1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "unknown" in result.result.message
    ctx.fetch.assert_awaited_once()


async def test_custom_object_links_use_association_api(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"id": "5", "properties": {}}]}),
        ok({"results": [{"from": {"id": "5"}, "to": [{"toObjectId": 8, "associationTypes": []}]}]}),
    ]
    result = await hubspot.execute_action(
        "get_crm_objects", {"object_type": "deals", "ids": ["5"], "associations": ["2-123"]}, ctx
    )
    assert result.result.data["results"][0]["associations"]["2-123"][0]["toObjectId"] == 8
    assert ctx.fetch.call_args.args[0].endswith("/deals/2-123/batch/read")


async def test_label_creation_stops_when_existing_links_are_truncated(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"category": "USER_DEFINED", "typeId": 42, "label": "Architect"}]}),
        *[ok({"results": [{"from": {"id": "5"}, "to": [], "paging": {"next": {"after": "more"}}}]})] * 20,
    ]
    result = await hubspot.execute_action(
        "create_association",
        {
            "from_object_type": "deals",
            "from_object_id": "5",
            "to_object_type": "contacts",
            "to_object_id": "1",
            "label": "Architect",
        },
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "incomplete" in result.result.message
    assert all(call.kwargs.get("method") != "PUT" for call in ctx.fetch.call_args_list)


async def test_links_custom_object_type(ctx):
    ctx.fetch.return_value = ok({})
    result = await hubspot.execute_action(
        "create_association",
        {"from_object_type": "2-123", "from_object_id": "1", "to_object_type": "contacts", "to_object_id": "2"},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert "/2-123/1/associations/default/contacts/2" in ctx.fetch.call_args.args[0]


async def test_pipeline_options_failure_is_reported(ctx):
    ctx.fetch.side_effect = [
        ok(
            {
                "results": [
                    {"name": "hs_pipeline_stage", "label": "Stage", "type": "enumeration", "externalOptions": True}
                ]
            }
        ),
        HTTPError(403, "Forbidden"),
    ]
    result = await hubspot.execute_action(
        "get_object_properties", {"object_type": "tickets", "include_details": True}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "pipeline options" in result.result.message
