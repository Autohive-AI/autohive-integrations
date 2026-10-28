"""Sales Hub Leads are separate from contacts and require optional plan-specific scopes."""

import asyncio
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
    context.config = {"max_retries": 3}
    return context


async def test_create_lead_links_contact_atomically_without_transport_retries(ctx):
    ctx.fetch.return_value = ok({"id": "10", "properties": {"hs_lead_name": "Monkeytoe project"}}, 201)
    result = await hubspot.execute_action(
        "create_lead",
        {"hs_lead_name": "Monkeytoe project", "contact_id": "20", "properties": {"hs_lead_label": "WARM"}},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["lead"]["id"] == "10"
    call = ctx.fetch.call_args
    assert call.args[0].endswith("/crm/objects/2026-09/leads")
    assert call.kwargs["method"] == "POST"
    assert call.kwargs["retry_count"] == 3
    assert call.kwargs["json"] == {
        "properties": {"hs_lead_name": "Monkeytoe project", "hs_lead_label": "WARM"},
        "associations": [
            {"to": {"id": "20"}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 578}]}
        ],
    }


async def test_update_lead_retains_empty_strings_for_clearing(ctx):
    ctx.fetch.return_value = ok({"id": "10", "properties": {"hs_lead_label": ""}})
    result = await hubspot.execute_action("update_lead", {"lead_id": "10", "properties": {"hs_lead_label": ""}}, ctx)
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.args[0].endswith("/leads/10")
    assert ctx.fetch.call_args.kwargs["method"] == "PATCH"
    assert ctx.fetch.call_args.kwargs["json"] == {"properties": {"hs_lead_label": ""}}


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("create_lead", {"hs_lead_name": "Missing contact"}),
        ("create_lead", {"contact_id": "20", "hs_lead_name": ""}),
        ("create_lead", {"contact_id": "../20", "hs_lead_name": "Lead"}),
        ("update_lead", {"lead_id": "10", "properties": {}}),
        ("update_lead", {"lead_id": "../10", "properties": {"hs_lead_name": "Lead"}}),
    ],
)
async def test_invalid_lead_inputs_do_not_make_requests(ctx, action, inputs):
    result = await hubspot.execute_action(action, inputs, ctx)
    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("create_lead", {"hs_lead_name": "Lead", "contact_id": "20"}),
        ("update_lead", {"lead_id": "10", "properties": {"hs_lead_name": "Lead"}}),
    ],
)
async def test_missing_leads_grant_returns_actionable_error(ctx, action, inputs):
    ctx.fetch.side_effect = HTTPError(403, "Missing scope")
    result = await hubspot.execute_action(action, inputs, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Sales Hub Professional/Enterprise" in result.result.message
    assert "crm.objects.leads.write" in result.result.message


async def test_lead_creation_timeout_is_not_retried(ctx):
    ctx.fetch.side_effect = asyncio.TimeoutError()
    result = await hubspot.execute_action("create_lead", {"hs_lead_name": "Lead", "contact_id": "20"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "outcome is unknown" in result.result.message
    ctx.fetch.assert_awaited_once()


async def test_generic_lead_search_filters_and_paging(ctx):
    ctx.fetch.return_value = ok(
        {"results": [{"id": "10", "properties": {}}], "total": 2, "paging": {"next": {"after": "11"}}}
    )
    result = await hubspot.execute_action(
        "search_crm_objects",
        {
            "object_type": "leads",
            "filters": [{"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "7"}],
            "associated_with": {"object_type": "contacts", "id": "20"},
            "limit": 1,
            "after": "9",
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.args[0].endswith("/leads/search")
    payload = ctx.fetch.call_args.kwargs["json"]
    assert payload["after"] == "9"
    assert payload["filterGroups"][0]["filters"] == [
        {"propertyName": "associations.contact", "operator": "EQ", "value": "20"},
        {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "7"},
    ]
    assert result.result.data["after"] == "11"


async def test_generic_lead_read_preserves_provider_url_and_associations(ctx):
    record = {"id": "10", "properties": {}, "url": "https://app.hubspot.com/contacts/42/record/0-136/10"}
    ctx.fetch.side_effect = [
        ok({"results": [record]}),
        ok({"results": [{"from": {"id": "10"}, "to": [{"toObjectId": 20, "associationTypes": []}]}]}),
    ]
    result = await hubspot.execute_action(
        "get_crm_objects",
        {"object_type": "leads", "ids": ["10"], "associations": ["contacts"], "include_urls": True},
        ctx,
    )
    assert result.type == ResultType.ACTION
    lead = result.result.data["results"][0]
    assert lead["url"] == record["url"]
    assert lead["associations"]["contacts"][0]["toObjectId"] == 20
    assert ctx.fetch.call_count == 2


async def test_lead_url_fallback_uses_lead_type_id(ctx):
    ctx.fetch.side_effect = [
        ok({"results": [{"id": "10", "properties": {}}]}),
        ok({"portalId": 42, "uiDomain": "app-eu1.hubspot.com"}),
    ]
    result = await hubspot.execute_action(
        "get_crm_objects", {"object_type": "leads", "ids": ["10"], "include_urls": True}, ctx
    )
    assert result.result.data["results"][0]["url"] == "https://app-eu1.hubspot.com/contacts/42/record/0-136/10"


async def test_lead_properties_discovery(ctx):
    ctx.fetch.return_value = ok(
        {
            "results": [
                {
                    "name": "hs_lead_label",
                    "label": "Label",
                    "type": "enumeration",
                    "options": [{"label": "Warm", "value": "WARM"}],
                }
            ]
        }
    )
    result = await hubspot.execute_action(
        "get_object_properties", {"object_type": "leads", "include_details": True}, ctx
    )
    assert ctx.fetch.call_args.args[0].endswith("/crm/properties/2026-09/leads")
    assert result.result.data["properties"][0]["options"] == [{"label": "Warm", "value": "WARM"}]


async def test_contacts_can_read_lead_associations(ctx):
    ctx.fetch.return_value = ok(
        {"results": [{"from": {"id": "20"}, "to": [{"toObjectId": 10, "associationTypes": []}]}]}
    )
    result = await hubspot.execute_action(
        "get_contact_associations", {"contact_id": "20", "association_types": ["leads"]}, ctx
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.args[0].endswith("/contacts/leads/batch/read")


async def test_link_records_accepts_leads(ctx):
    ctx.fetch.return_value = ok({})
    result = await hubspot.execute_action(
        "create_association",
        {"from_object_type": "leads", "from_object_id": "10", "to_object_type": "contacts", "to_object_id": "20"},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert ctx.fetch.call_args.args[0].endswith("/leads/10/associations/default/contacts/20")
