"""
Unit tests for the Zoom integration using mocked fetch.

All tests are CI-safe: fetch is mocked, no credentials required. Covers every
action's success path, its ActionError path (fetch raises), and validation
errors for missing required inputs, plus the connected-account handler and the
module's helper functions.
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

from zoom.zoom import (  # noqa: E402
    zoom as zoom_integration,
    ZoomConnectedAccountHandler,
    ZoomAPIClient,
    encode_meeting_id,
    get_headers,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data, status=200):
    """Context whose fetch returns a single FetchResponse."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data, status))
    ctx.auth = {}
    return ctx


def make_ctx_multi(responses):
    """Context whose fetch returns a sequence of FetchResponses."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {}
    return ctx


def make_ctx_error(exc=None):
    """Context whose fetch raises — exercises the ActionError path."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc or Exception("API request failed"))
    ctx.auth = {}
    return ctx


def called_url(ctx):
    """Return the URL passed to the most recent fetch call."""
    call = ctx.fetch.call_args
    return call.args[0] if call.args else call.kwargs["url"]


def called_kwargs(ctx):
    return ctx.fetch.call_args.kwargs


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def test_get_headers():
    assert get_headers() == {"Content-Type": "application/json"}


def test_encode_meeting_id_plain():
    # Normal numeric / non-slash IDs are returned unchanged.
    assert encode_meeting_id("123456789") == "123456789"


def test_encode_meeting_id_double_encodes_uuid_with_slash():
    # UUIDs starting with '/' or containing '//' are double URL-encoded.
    assert encode_meeting_id("/abc==") == "%252Fabc%253D%253D"
    assert encode_meeting_id("ab//cd") == "ab%252F%252Fcd"


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


@pytest.mark.asyncio
async def test_connected_account_full_name():
    ctx = make_ctx(
        {
            "id": "abc123",
            "email": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "display_name": "Jane Doe",
            "pic_url": "https://example.com/pic.jpg",
            "company": "Acme",
        }
    )
    handler = ZoomConnectedAccountHandler()
    info = await handler.get_account_info(ctx)
    assert info.email == "jane@example.com"
    assert info.username == "Jane Doe"
    assert info.first_name == "Jane"
    assert info.last_name == "Doe"
    assert info.avatar_url == "https://example.com/pic.jpg"
    assert info.organization == "Acme"
    assert info.user_id == "abc123"
    assert called_url(ctx).endswith("/users/me")


@pytest.mark.asyncio
async def test_connected_account_builds_username_from_names():
    ctx = make_ctx({"id": "1", "email": "a@b.com", "first_name": "Sam", "last_name": "Smith"})
    handler = ZoomConnectedAccountHandler()
    info = await handler.get_account_info(ctx)
    # No display_name → username falls back to "first last".
    assert info.username == "Sam Smith"


@pytest.mark.asyncio
async def test_connected_account_empty_names_are_none():
    ctx = make_ctx({"id": "1", "email": "a@b.com", "first_name": "", "last_name": "", "dept": "Eng"})
    handler = ZoomConnectedAccountHandler()
    info = await handler.get_account_info(ctx)
    assert info.first_name is None
    assert info.last_name is None
    assert info.organization == "Eng"


# =============================================================================
# API CLIENT — _make_request behaviour
# =============================================================================


@pytest.mark.asyncio
async def test_make_request_returns_body_data():
    ctx = make_ctx({"hello": "world"})
    client = ZoomAPIClient(ctx)
    body = await client._make_request("users/me")
    assert body == {"hello": "world"}


@pytest.mark.asyncio
async def test_make_request_delete_empty_response():
    # DELETE with an empty body yields the synthetic success marker.
    ctx = make_ctx(None, status=204)
    client = ZoomAPIClient(ctx)
    body = await client._make_request("meetings/123", method="DELETE")
    assert body == {"success": True}


@pytest.mark.asyncio
async def test_make_request_rejects_unknown_method():
    ctx = make_ctx({})
    client = ZoomAPIClient(ctx)
    with pytest.raises(ValueError):
        await client._make_request("x", method="PUT")


# =============================================================================
# LIST MEETINGS
# =============================================================================


@pytest.mark.asyncio
async def test_list_meetings_success():
    ctx = make_ctx(
        {
            "meetings": [{"id": 1, "type": 2, "topic": "Standup", "join_url": "https://zoom.us/j/1"}],
            "next_page_token": "tok",  # nosec B105
            "page_count": 1,
            "page_size": 30,
            "total_records": 1,
        }
    )
    result = await zoom_integration.execute_action("list_meetings", {"user_id": "me"}, ctx)
    data = result.result.data
    assert len(data["meetings"]) == 1
    assert data["meetings"][0]["topic"] == "Standup"
    assert data["next_page_token"] == "tok"
    assert data["total_records"] == 1
    assert "result" not in data
    assert called_url(ctx).endswith("/users/me/meetings")


@pytest.mark.asyncio
async def test_list_meetings_page_size_over_max_validation_error():
    # The input schema caps page_size at 300; exceeding it is rejected before fetch.
    ctx = make_ctx({"meetings": []})
    result = await zoom_integration.execute_action("list_meetings", {"page_size": 9999}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_list_meetings_error():
    ctx = make_ctx_error(Exception("401 Unauthorized"))
    result = await zoom_integration.execute_action("list_meetings", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "401 Unauthorized" in result.result.message


# =============================================================================
# GET MEETING
# =============================================================================


@pytest.mark.asyncio
async def test_get_meeting_success():
    ctx = make_ctx({"id": 99, "type": 2, "topic": "Sync", "status": "waiting", "settings": {"waiting_room": True}})
    result = await zoom_integration.execute_action("get_meeting", {"meeting_id": "99"}, ctx)
    data = result.result.data
    assert data["id"] == 99
    assert data["topic"] == "Sync"
    assert data["settings"] == {"waiting_room": True}
    assert called_url(ctx).endswith("/meetings/99")


@pytest.mark.asyncio
async def test_get_meeting_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_meeting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_meeting_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_meeting", {"meeting_id": "99"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "404 Not Found" in result.result.message


# =============================================================================
# CREATE MEETING
# =============================================================================


@pytest.mark.asyncio
async def test_create_meeting_success():
    ctx = make_ctx({"id": 555, "topic": "Kickoff", "join_url": "https://zoom.us/j/555", "password": "p"})  # nosec B105
    result = await zoom_integration.execute_action(
        "create_meeting",
        {"topic": "Kickoff", "duration": 30, "waiting_room": True, "auto_recording": "cloud"},
        ctx,
    )
    data = result.result.data
    assert data["id"] == 555
    assert data["join_url"] == "https://zoom.us/j/555"
    body = called_kwargs(ctx)["json"]
    assert body["topic"] == "Kickoff"
    assert body["duration"] == 30
    assert body["settings"]["waiting_room"] is True
    assert body["settings"]["auto_recording"] == "cloud"


@pytest.mark.asyncio
async def test_create_meeting_missing_topic_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("create_meeting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_meeting_error():
    ctx = make_ctx_error(Exception("400 Bad Request"))
    result = await zoom_integration.execute_action("create_meeting", {"topic": "X"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "400 Bad Request" in result.result.message


# =============================================================================
# UPDATE MEETING
# =============================================================================


@pytest.mark.asyncio
async def test_update_meeting_success():
    ctx = make_ctx(None, status=204)
    result = await zoom_integration.execute_action(
        "update_meeting", {"meeting_id": "77", "topic": "Renamed", "join_before_host": True}, ctx
    )
    assert result.result.data == {"meeting_id": "77"}
    assert called_kwargs(ctx)["method"] == "PATCH"
    body = called_kwargs(ctx)["json"]
    assert body["topic"] == "Renamed"
    assert body["settings"]["join_before_host"] is True


@pytest.mark.asyncio
async def test_update_meeting_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("update_meeting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_update_meeting_error():
    ctx = make_ctx_error(Exception("409 Conflict"))
    result = await zoom_integration.execute_action("update_meeting", {"meeting_id": "77"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "409 Conflict" in result.result.message


# =============================================================================
# DELETE MEETING
# =============================================================================


@pytest.mark.asyncio
async def test_delete_meeting_success():
    ctx = make_ctx(None, status=204)
    result = await zoom_integration.execute_action("delete_meeting", {"meeting_id": "88", "occurrence_id": "occ1"}, ctx)
    assert result.result.data == {"meeting_id": "88"}
    assert called_kwargs(ctx)["method"] == "DELETE"
    assert called_kwargs(ctx)["params"]["occurrence_id"] == "occ1"


@pytest.mark.asyncio
async def test_delete_meeting_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("delete_meeting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_delete_meeting_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("delete_meeting", {"meeting_id": "88"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "404 Not Found" in result.result.message


# =============================================================================
# GET USER
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_success():
    ctx = make_ctx({"id": "u1", "email": "u@e.com", "first_name": "Uma", "type": 2, "pmi": 1234567890, "use_pmi": True})
    result = await zoom_integration.execute_action("get_user", {"user_id": "u1"}, ctx)
    data = result.result.data
    assert data["id"] == "u1"
    assert data["email"] == "u@e.com"
    assert data["use_pmi"] is True
    assert called_url(ctx).endswith("/users/u1")


@pytest.mark.asyncio
async def test_get_user_defaults_to_me():
    ctx = make_ctx({"id": "me-id", "email": "me@e.com"})
    await zoom_integration.execute_action("get_user", {}, ctx)
    assert called_url(ctx).endswith("/users/me")


@pytest.mark.asyncio
async def test_get_user_error():
    ctx = make_ctx_error(Exception("403 Forbidden"))
    result = await zoom_integration.execute_action("get_user", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "403 Forbidden" in result.result.message


# =============================================================================
# GET MEETING PARTICIPANTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_meeting_participants_success():
    ctx = make_ctx(
        {
            "participants": [{"id": "p1", "name": "Pat", "duration": 600}],
            "next_page_token": "n",  # nosec B105
            "page_count": 1,
            "page_size": 30,
            "total_records": 1,
        }
    )
    result = await zoom_integration.execute_action("get_meeting_participants", {"meeting_id": "12"}, ctx)
    data = result.result.data
    assert data["participants"][0]["name"] == "Pat"
    assert data["total_records"] == 1
    assert called_url(ctx).endswith("/past_meetings/12/participants")


@pytest.mark.asyncio
async def test_get_meeting_participants_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_meeting_participants", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_meeting_participants_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_meeting_participants", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# ADD MEETING REGISTRANT
# =============================================================================


@pytest.mark.asyncio
async def test_add_meeting_registrant_success():
    ctx = make_ctx({"registrant_id": "r1", "id": 12, "join_url": "https://zoom.us/w/12"})
    result = await zoom_integration.execute_action(
        "add_meeting_registrant",
        {"meeting_id": "12", "email": "g@e.com", "first_name": "Guest", "last_name": "User"},
        ctx,
    )
    data = result.result.data
    assert data["registrant_id"] == "r1"
    body = called_kwargs(ctx)["json"]
    assert body["email"] == "g@e.com"
    assert body["last_name"] == "User"


@pytest.mark.asyncio
async def test_add_meeting_registrant_missing_fields_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("add_meeting_registrant", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_add_meeting_registrant_error():
    ctx = make_ctx_error(Exception("429 Too Many Requests"))
    result = await zoom_integration.execute_action(
        "add_meeting_registrant", {"meeting_id": "12", "email": "g@e.com", "first_name": "G"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE CALENDAR EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_create_calendar_event_success():
    ctx = make_ctx({"id": "ev1", "summary": "Lunch", "htmlLink": "https://cal/ev1"})
    result = await zoom_integration.execute_action(
        "create_calendar_event",
        {
            "summary": "Lunch",
            "start": {"dateTime": "2026-01-01T12:00:00Z"},
            "end": {"dateTime": "2026-01-01T13:00:00Z"},
        },
        ctx,
    )
    data = result.result.data
    assert data["id"] == "ev1"
    assert data["html_link"] == "https://cal/ev1"
    assert called_url(ctx).endswith("/calendars/primary/events")


@pytest.mark.asyncio
async def test_create_calendar_event_missing_required_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("create_calendar_event", {"summary": "X"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_calendar_event_error():
    ctx = make_ctx_error(Exception("500 Server Error"))
    result = await zoom_integration.execute_action(
        "create_calendar_event", {"summary": "X", "start": {}, "end": {}}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# DELETE CALENDAR EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_delete_calendar_event_success():
    ctx = make_ctx(None, status=204)
    result = await zoom_integration.execute_action(
        "delete_calendar_event", {"calendar_id": "cal1", "event_id": "ev9"}, ctx
    )
    assert result.result.data == {"event_id": "ev9"}
    assert called_url(ctx).endswith("/calendars/cal1/events/ev9")
    assert called_kwargs(ctx)["method"] == "DELETE"


@pytest.mark.asyncio
async def test_delete_calendar_event_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("delete_calendar_event", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_delete_calendar_event_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("delete_calendar_event", {"event_id": "ev9"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# QUICK CREATE CALENDAR EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_quick_create_calendar_event_success():
    ctx = make_ctx({"id": "qev", "summary": "Coffee tomorrow 9am", "htmlLink": "https://cal/qev"})
    result = await zoom_integration.execute_action("quick_create_calendar_event", {"text": "Coffee tomorrow 9am"}, ctx)
    data = result.result.data
    assert data["id"] == "qev"
    assert called_kwargs(ctx)["json"] == {"text": "Coffee tomorrow 9am"}
    assert called_url(ctx).endswith("/calendars/primary/events/quickAdd")


@pytest.mark.asyncio
async def test_quick_create_calendar_event_missing_text_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("quick_create_calendar_event", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_quick_create_calendar_event_error():
    ctx = make_ctx_error(Exception("400 Bad Request"))
    result = await zoom_integration.execute_action("quick_create_calendar_event", {"text": "x"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# UPDATE CALENDAR METADATA
# =============================================================================


@pytest.mark.asyncio
async def test_update_calendar_metadata_success():
    ctx = make_ctx({"id": "cal1", "summary": "Team", "description": "d", "timezone": "UTC"})
    result = await zoom_integration.execute_action(
        "update_calendar_metadata", {"calendar_id": "cal1", "summary": "Team"}, ctx
    )
    data = result.result.data
    assert data["id"] == "cal1"
    assert data["summary"] == "Team"
    assert called_kwargs(ctx)["method"] == "PATCH"


@pytest.mark.asyncio
async def test_update_calendar_metadata_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("update_calendar_metadata", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_update_calendar_metadata_error():
    ctx = make_ctx_error(Exception("403 Forbidden"))
    result = await zoom_integration.execute_action("update_calendar_metadata", {"calendar_id": "cal1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# UPDATE CALENDAR SETTING
# =============================================================================


@pytest.mark.asyncio
async def test_update_calendar_setting_success():
    ctx = make_ctx({"id": "s1", "value": "on"})
    result = await zoom_integration.execute_action("update_calendar_setting", {"setting_id": "s1", "value": "on"}, ctx)
    data = result.result.data
    assert data["id"] == "s1"
    assert data["value"] == "on"
    assert called_url(ctx).endswith("/calendars/settings/s1")


@pytest.mark.asyncio
async def test_update_calendar_setting_missing_value_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("update_calendar_setting", {"setting_id": "s1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_update_calendar_setting_error():
    ctx = make_ctx_error(Exception("400 Bad Request"))
    result = await zoom_integration.execute_action("update_calendar_setting", {"setting_id": "s1", "value": "on"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET CALENDAR METADATA
# =============================================================================


@pytest.mark.asyncio
async def test_get_calendar_metadata_success():
    ctx = make_ctx({"id": "primary", "summary": "Me", "accessRole": "owner", "primary": True})
    result = await zoom_integration.execute_action("get_calendar_metadata", {}, ctx)
    data = result.result.data
    assert data["access_role"] == "owner"
    assert data["primary"] is True
    assert called_url(ctx).endswith("/calendars/primary")


@pytest.mark.asyncio
async def test_get_calendar_metadata_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_calendar_metadata", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET CALENDAR SETTING
# =============================================================================


@pytest.mark.asyncio
async def test_get_calendar_setting_success():
    ctx = make_ctx({"id": "s2", "value": "v", "etag": "e"})
    result = await zoom_integration.execute_action("get_calendar_setting", {"setting_id": "s2"}, ctx)
    data = result.result.data
    assert data["id"] == "s2"
    assert data["etag"] == "e"


@pytest.mark.asyncio
async def test_get_calendar_setting_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_calendar_setting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_calendar_setting_error():
    ctx = make_ctx_error(Exception("403 Forbidden"))
    result = await zoom_integration.execute_action("get_calendar_setting", {"setting_id": "s2"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET CALENDAR EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_get_calendar_event_success():
    ctx = make_ctx(
        {"id": "ev3", "summary": "Review", "attendees": [{"email": "a@b.com"}], "htmlLink": "https://cal/ev3"}
    )
    result = await zoom_integration.execute_action(
        "get_calendar_event", {"calendar_id": "cal2", "event_id": "ev3"}, ctx
    )
    data = result.result.data
    assert data["summary"] == "Review"
    assert data["attendees"] == [{"email": "a@b.com"}]
    assert called_url(ctx).endswith("/calendars/cal2/events/ev3")


@pytest.mark.asyncio
async def test_get_calendar_event_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_calendar_event", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_calendar_event_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_calendar_event", {"event_id": "ev3"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST CALENDAR EVENTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_calendar_events_success():
    ctx = make_ctx(
        {
            "items": [{"id": "e1", "summary": "A"}, {"id": "e2", "summary": "B"}],
            "nextPageToken": "np",
            "timeZone": "UTC",
        }
    )
    result = await zoom_integration.execute_action(
        "list_calendar_events", {"time_min": "2026-01-01T00:00:00Z", "max_results": 10}, ctx
    )
    data = result.result.data
    assert len(data["events"]) == 2
    assert data["next_page_token"] == "np"
    assert data["time_zone"] == "UTC"
    assert called_kwargs(ctx)["params"]["timeMin"] == "2026-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_list_calendar_events_max_results_over_max_validation_error():
    # max_results is capped at 2500 by the input schema.
    ctx = make_ctx({"items": []})
    result = await zoom_integration.execute_action("list_calendar_events", {"max_results": 99999}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_list_calendar_events_error():
    ctx = make_ctx_error(Exception("500 Server Error"))
    result = await zoom_integration.execute_action("list_calendar_events", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST CALENDAR SETTINGS
# =============================================================================


@pytest.mark.asyncio
async def test_list_calendar_settings_success():
    ctx = make_ctx({"items": [{"id": "s1", "value": "v", "etag": "e"}], "nextPageToken": None})
    result = await zoom_integration.execute_action("list_calendar_settings", {}, ctx)
    data = result.result.data
    assert data["settings"][0]["id"] == "s1"
    assert called_url(ctx).endswith("/calendars/settings")


@pytest.mark.asyncio
async def test_list_calendar_settings_error():
    ctx = make_ctx_error(Exception("403 Forbidden"))
    result = await zoom_integration.execute_action("list_calendar_settings", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST CONTACTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_contacts_success():
    ctx = make_ctx(
        {
            "contacts": [{"id": "c1", "email": "c@e.com", "first_name": "Cara"}],
            "next_page_token": "cp",  # nosec B105
            "total_records": 1,
        }
    )
    result = await zoom_integration.execute_action("list_contacts", {"search_key": "Cara"}, ctx)
    data = result.result.data
    assert data["contacts"][0]["email"] == "c@e.com"
    assert data["total_records"] == 1
    assert called_kwargs(ctx)["params"]["search_key"] == "Cara"


@pytest.mark.asyncio
async def test_list_contacts_page_size_over_max_validation_error():
    # page_size is capped at 1000 by the input schema.
    ctx = make_ctx({"contacts": []})
    result = await zoom_integration.execute_action("list_contacts", {"page_size": 99999}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_list_contacts_error():
    ctx = make_ctx_error(Exception("429 Too Many Requests"))
    result = await zoom_integration.execute_action("list_contacts", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE MEETING TEMPLATE
# =============================================================================


@pytest.mark.asyncio
async def test_create_meeting_template_success():
    ctx = make_ctx({"id": "tpl1", "name": "Weekly"})
    result = await zoom_integration.execute_action(
        "create_meeting_template", {"meeting_id": "12", "name": "Weekly", "save_recurrence": True}, ctx
    )
    data = result.result.data
    assert data["id"] == "tpl1"
    assert data["name"] == "Weekly"
    body = called_kwargs(ctx)["json"]
    assert body["name"] == "Weekly"
    assert body["save_recurrence"] is True


@pytest.mark.asyncio
async def test_create_meeting_template_missing_fields_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("create_meeting_template", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_meeting_template_error():
    ctx = make_ctx_error(Exception("400 Bad Request"))
    result = await zoom_integration.execute_action(
        "create_meeting_template", {"meeting_id": "12", "name": "Weekly"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE MEETING INVITE LINKS
# =============================================================================


@pytest.mark.asyncio
async def test_create_meeting_invite_links_success():
    ctx = make_ctx({"attendees": [{"name": "Ann", "join_url": "https://zoom.us/j/1?tk=a"}]})
    result = await zoom_integration.execute_action(
        "create_meeting_invite_links",
        {"meeting_id": "12", "attendees": [{"name": "Ann"}], "ttl": 7200},
        ctx,
    )
    data = result.result.data
    assert data["attendees"][0]["name"] == "Ann"
    body = called_kwargs(ctx)["json"]
    assert body["ttl"] == 7200


@pytest.mark.asyncio
async def test_create_meeting_invite_links_missing_fields_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("create_meeting_invite_links", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_meeting_invite_links_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action(
        "create_meeting_invite_links", {"meeting_id": "12", "attendees": [{"name": "Ann"}]}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET MEETING PARTICIPANT
# =============================================================================


@pytest.mark.asyncio
async def test_get_meeting_participant_success():
    ctx = make_ctx({"id": "p9", "name": "Pat", "user_email": "p@e.com", "status": "in_meeting"})
    result = await zoom_integration.execute_action(
        "get_meeting_participant", {"meeting_id": "12", "participant_id": "p9"}, ctx
    )
    data = result.result.data
    assert data["id"] == "p9"
    assert data["status"] == "in_meeting"
    assert called_url(ctx).endswith("/meetings/12/participants/p9")


@pytest.mark.asyncio
async def test_get_meeting_participant_missing_fields_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_meeting_participant", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_meeting_participant_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action(
        "get_meeting_participant", {"meeting_id": "12", "participant_id": "p9"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET PAST MEETING
# =============================================================================


@pytest.mark.asyncio
async def test_get_past_meeting_success():
    ctx = make_ctx({"id": 12, "type": 8, "topic": "Retro", "participants_count": 5, "total_minutes": 250})
    result = await zoom_integration.execute_action("get_past_meeting", {"meeting_id": "12"}, ctx)
    data = result.result.data
    assert data["topic"] == "Retro"
    assert data["participants_count"] == 5
    assert called_url(ctx).endswith("/past_meetings/12")


@pytest.mark.asyncio
async def test_get_past_meeting_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_past_meeting", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_past_meeting_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_past_meeting", {"meeting_id": "12"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET MEETING TEMPLATE DETAIL
# =============================================================================


@pytest.mark.asyncio
async def test_get_meeting_template_detail_success():
    ctx = make_ctx({"id": "tpl1", "name": "Weekly", "type": 2, "topic": "Sync", "settings": {"host_video": True}})
    result = await zoom_integration.execute_action("get_meeting_template_detail", {"template_id": "tpl1"}, ctx)
    data = result.result.data
    assert data["name"] == "Weekly"
    assert data["settings"] == {"host_video": True}
    assert called_url(ctx).endswith("/users/me/meeting_templates/tpl1")


@pytest.mark.asyncio
async def test_get_meeting_template_detail_missing_id_validation_error():
    ctx = make_ctx({})
    result = await zoom_integration.execute_action("get_meeting_template_detail", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_meeting_template_detail_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await zoom_integration.execute_action("get_meeting_template_detail", {"template_id": "tpl1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET USER PERMISSIONS
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_permissions_success():
    ctx = make_ctx({"permissions": ["meeting:read", "meeting:write"]})
    result = await zoom_integration.execute_action("get_user_permissions", {}, ctx)
    data = result.result.data
    assert data["permissions"] == ["meeting:read", "meeting:write"]
    assert called_url(ctx).endswith("/users/me/permissions")


@pytest.mark.asyncio
async def test_get_user_permissions_error():
    ctx = make_ctx_error(Exception("403 Forbidden"))
    result = await zoom_integration.execute_action("get_user_permissions", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "403 Forbidden" in result.result.message
