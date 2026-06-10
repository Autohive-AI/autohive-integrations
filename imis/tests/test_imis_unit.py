import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ResultType
from imis.imis import imis  # noqa: E402

pytestmark = pytest.mark.unit

TOKEN_RESPONSE = MagicMock(data={"access_token": "test-token"})  # nosec B105


def _resp(data):
    return MagicMock(data=data)


# ---- Contacts ----


@pytest.mark.asyncio
async def test_get_contact(mock_context):
    contact = {"Id": "12345", "FirstName": "Alice", "LastName": "Smith"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(contact)])
    result = await imis.execute_action("get_contact", {"party_id": "12345"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["contact"]["Id"] == "12345"


@pytest.mark.asyncio
async def test_get_contact_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await imis.execute_action("get_contact", {"party_id": "bad"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "not found" in result.result.message


@pytest.mark.asyncio
async def test_update_contact(mock_context):
    existing = {"Id": "12345", "FirstName": "Alice", "LastName": "Smith", "PrimaryEmail": "old@example.com"}
    updated = {**existing, "PrimaryEmail": "new@example.com"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(existing), TOKEN_RESPONSE, _resp(updated)])
    result = await imis.execute_action(
        "update_contact",
        {"party_id": "12345", "email": "new@example.com"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["contact"]["PrimaryEmail"] == "new@example.com"


@pytest.mark.asyncio
async def test_update_contact_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("update failed"))
    result = await imis.execute_action("update_contact", {"party_id": "12345", "email": "x@x.com"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- Events ----


@pytest.mark.asyncio
async def test_list_events(mock_context):
    events_resp = {"Items": [{"Id": "EVT1", "Title": "Annual Conference"}], "Count": 1}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(events_resp)])
    result = await imis.execute_action("list_events", {"limit": 10}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["events"]) == 1
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_list_events_with_date_filter(mock_context):
    events_resp = {"Items": [], "Count": 0}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(events_resp)])
    result = await imis.execute_action(
        "list_events",
        {"from_date": "2025-01-01", "to_date": "2025-12-31"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["events"] == []


@pytest.mark.asyncio
async def test_get_event(mock_context):
    event = {"Id": "EVT1", "Title": "Annual Conference", "StartDate": "2025-09-01"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(event)])
    result = await imis.execute_action("get_event", {"event_id": "EVT1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["event"]["Title"] == "Annual Conference"


@pytest.mark.asyncio
async def test_get_event_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("event not found"))
    result = await imis.execute_action("get_event", {"event_id": "BAD"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_create_event(mock_context):
    created = {"Id": "EVT2", "Title": "New Event", "StartDate": "2025-10-01T09:00:00"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(created)])
    result = await imis.execute_action(
        "create_event",
        {"title": "New Event", "start_date": "2025-10-01T09:00:00", "location": "Auckland"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["event"]["Id"] == "EVT2"


@pytest.mark.asyncio
async def test_update_event(mock_context):
    existing = {"Id": "EVT1", "Title": "Old Title", "StartDate": "2025-09-01"}
    updated = {**existing, "Title": "New Title"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(existing), TOKEN_RESPONSE, _resp(updated)])
    result = await imis.execute_action(
        "update_event",
        {"event_id": "EVT1", "title": "New Title"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["event"]["Title"] == "New Title"


@pytest.mark.asyncio
async def test_update_event_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("update failed"))
    result = await imis.execute_action("update_event", {"event_id": "EVT1", "title": "x"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- Registrations ----


@pytest.mark.asyncio
async def test_list_registrations(mock_context):
    regs_resp = {"Items": [{"Id": "REG1", "EventId": "EVT1", "PartyId": "12345"}], "Count": 1}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(regs_resp)])
    result = await imis.execute_action("list_registrations", {"event_id": "EVT1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_create_registration(mock_context):
    created = {"Id": "REG2", "EventId": "EVT1", "PartyId": "12345"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(created)])
    result = await imis.execute_action(
        "create_registration",
        {"event_id": "EVT1", "party_id": "12345"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["registration"]["Id"] == "REG2"


@pytest.mark.asyncio
async def test_create_registration_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("already registered"))
    result = await imis.execute_action(
        "create_registration",
        {"event_id": "EVT1", "party_id": "12345"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- Media Assets ----


@pytest.mark.asyncio
async def test_list_media_assets(mock_context):
    assets_resp = {"Items": [{"Id": "ASSET1", "Name": "hero-image.jpg"}], "Count": 1}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(assets_resp)])
    result = await imis.execute_action("list_media_assets", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["assets"]) == 1


@pytest.mark.asyncio
async def test_list_media_assets_with_search(mock_context):
    assets_resp = {"Items": [], "Count": 0}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(assets_resp)])
    result = await imis.execute_action("list_media_assets", {"search": "banner"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["assets"] == []


@pytest.mark.asyncio
async def test_get_media_asset(mock_context):
    asset = {"Id": "ASSET1", "Name": "hero.jpg", "Url": "https://example.com/hero.jpg"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(asset)])
    result = await imis.execute_action("get_media_asset", {"asset_id": "ASSET1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["asset"]["Id"] == "ASSET1"


@pytest.mark.asyncio
async def test_get_media_asset_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await imis.execute_action("get_media_asset", {"asset_id": "BAD"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- Contacts (extended) ----


@pytest.mark.asyncio
async def test_create_contact(mock_context):
    created = {"Id": "99999", "FirstName": "Bob", "LastName": "Jones", "PrimaryEmail": "bob@example.com"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(created)])
    result = await imis.execute_action(
        "create_contact",
        {"last_name": "Jones", "first_name": "Bob", "email": "bob@example.com"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["contact"]["Id"] == "99999"


@pytest.mark.asyncio
async def test_create_contact_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("create failed"))
    result = await imis.execute_action("create_contact", {"last_name": "Jones"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- Groups ----


@pytest.mark.asyncio
async def test_list_groups(mock_context):
    groups_resp = {"Items": [{"Id": "GRP1", "Name": "Members"}], "Count": 1}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(groups_resp)])
    result = await imis.execute_action("list_groups", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_get_group(mock_context):
    group = {"Id": "GRP1", "Name": "Members"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(group)])
    result = await imis.execute_action("get_group", {"group_id": "GRP1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["group"]["Name"] == "Members"


@pytest.mark.asyncio
async def test_get_group_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await imis.execute_action("get_group", {"group_id": "BAD"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_add_group_member(mock_context):
    member = {"GroupId": "GRP1", "PartyId": "12345"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(member)])
    result = await imis.execute_action("add_group_member", {"group_id": "GRP1", "party_id": "12345"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["member"]["PartyId"] == "12345"


@pytest.mark.asyncio
async def test_remove_group_member(mock_context):
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(None)])
    result = await imis.execute_action("remove_group_member", {"group_id": "GRP1", "party_id": "12345"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["deleted"] is True


# ---- Registrations (extended) ----


@pytest.mark.asyncio
async def test_delete_registration(mock_context):
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(None)])
    result = await imis.execute_action("delete_registration", {"registration_id": "REG1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_delete_registration_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await imis.execute_action("delete_registration", {"registration_id": "BAD"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- Tags ----


@pytest.mark.asyncio
async def test_list_tags(mock_context):
    tags_resp = {"Items": [{"Tag": "vip"}, {"Tag": "member"}], "Count": 2}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(tags_resp)])
    result = await imis.execute_action("list_tags", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["count"] == 2


@pytest.mark.asyncio
async def test_add_tag(mock_context):
    tag_resp = {"PartyId": "12345", "Tag": "vip"}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(tag_resp)])
    result = await imis.execute_action("add_tag", {"party_id": "12345", "tag": "vip"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["tag"]["Tag"] == "vip"


@pytest.mark.asyncio
async def test_add_tag_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("tag failed"))
    result = await imis.execute_action("add_tag", {"party_id": "12345", "tag": "vip"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- IQA Queries ----


@pytest.mark.asyncio
async def test_run_query(mock_context):
    query_resp = {"Items": [{"Name": "Alice"}, {"Name": "Bob"}], "Count": 2}
    mock_context.fetch = AsyncMock(side_effect=[TOKEN_RESPONSE, _resp(query_resp)])
    result = await imis.execute_action("run_query", {"query_name": "$/Contact/AllContacts"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["count"] == 2
    assert len(result.result.data["results"]) == 2


@pytest.mark.asyncio
async def test_run_query_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("query not found"))
    result = await imis.execute_action("run_query", {"query_name": "$/Bad/Query"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
