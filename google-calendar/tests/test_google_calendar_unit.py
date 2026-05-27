import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, MagicMock
from google_calendar import google_calendar
from autohive_integrations_sdk import ActionResult, ActionError

pytestmark = pytest.mark.unit


def make_fetch_response(data, status=200):
    resp = MagicMock()
    resp.status = status
    resp.data = data
    return resp


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.auth = {"credentials": {"access_token": "test_token"}}
    ctx.fetch = AsyncMock()
    return ctx


# ---- list_calendars ----


class TestListCalendars:
    @pytest.mark.asyncio
    async def test_returns_calendars(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {"items": [{"id": "cal1", "summary": "Work"}, {"id": "primary", "summary": "Personal", "primary": True}]}
        )
        result = await google_calendar.execute_action("list_calendars", {}, mock_context)
        assert isinstance(result.result, ActionResult)
        calendars = result.result.data["calendars"]
        assert len(calendars) == 2
        assert calendars[0]["id"] == "cal1"
        assert calendars[1]["primary"] is True

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"items": []})
        result = await google_calendar.execute_action("list_calendars", {}, mock_context)
        assert isinstance(result.result, ActionResult)
        assert result.result.data["calendars"] == []

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Invalid Credentials"}, status=401)
        result = await google_calendar.execute_action("list_calendars", {}, mock_context)
        assert isinstance(result.result, ActionError)
        assert "Invalid Credentials" in result.result.message

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("network error")
        result = await google_calendar.execute_action("list_calendars", {}, mock_context)
        assert isinstance(result.result, ActionError)


# ---- list_events ----


class TestListEvents:
    @pytest.mark.asyncio
    async def test_returns_events(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {
                "items": [
                    {"id": "evt1", "summary": "Team standup", "start": {"dateTime": "2026-06-03T09:00:00+12:00"}},
                    {"id": "evt2", "summary": "All-day event", "start": {"date": "2026-06-03"}},
                ]
            }
        )
        result = await google_calendar.execute_action("list_events", {"calendar_id": "primary"}, mock_context)
        assert isinstance(result.result, ActionResult)
        events = result.result.data["events"]
        assert len(events) == 2
        assert events[0]["id"] == "evt1"

    @pytest.mark.asyncio
    async def test_sends_single_events_true(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"items": []})
        await google_calendar.execute_action("list_events", {"calendar_id": "primary"}, mock_context)
        call_kwargs = mock_context.fetch.call_args
        params = call_kwargs[1].get("params") or call_kwargs.kwargs.get("params", {})
        assert params.get("singleEvents") == "true"
        assert params.get("orderBy") == "startTime"

    @pytest.mark.asyncio
    async def test_passes_time_min_max(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"items": []})
        await google_calendar.execute_action(
            "list_events",
            {"calendar_id": "primary", "time_min": "2026-06-01T00:00:00Z", "time_max": "2026-06-30T23:59:59Z"},
            mock_context,
        )
        params = mock_context.fetch.call_args[1]["params"]
        assert params["timeMin"] == "2026-06-01T00:00:00Z"
        assert params["timeMax"] == "2026-06-30T23:59:59Z"

    @pytest.mark.asyncio
    async def test_passes_query_param(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"items": []})
        await google_calendar.execute_action(
            "list_events",
            {"calendar_id": "primary", "query": "Onboarding"},
            mock_context,
        )
        params = mock_context.fetch.call_args[1]["params"]
        assert params["q"] == "Onboarding"

    @pytest.mark.asyncio
    async def test_next_page_token_included(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {"items": [{"id": "e1", "summary": "E1"}], "nextPageToken": "tok123"}
        )
        result = await google_calendar.execute_action("list_events", {"calendar_id": "primary"}, mock_context)
        assert result.result.data["nextPageToken"] == "tok123"

    @pytest.mark.asyncio
    async def test_no_next_page_token_when_last_page(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"items": []})
        result = await google_calendar.execute_action("list_events", {"calendar_id": "primary"}, mock_context)
        assert "nextPageToken" not in result.result.data

    @pytest.mark.asyncio
    async def test_recurring_event_instance_has_recurring_event_id(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {
                "items": [
                    {
                        "id": "instance_abc",
                        "summary": "Weekly sync",
                        "recurringEventId": "base_event_id",
                        "start": {"dateTime": "2026-06-04T10:00:00+12:00"},
                    }
                ]
            }
        )
        result = await google_calendar.execute_action("list_events", {"calendar_id": "primary"}, mock_context)
        event = result.result.data["events"][0]
        assert event["recurringEventId"] == "base_event_id"

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Not Found"}, status=404)
        result = await google_calendar.execute_action("list_events", {"calendar_id": "bad_id"}, mock_context)
        assert isinstance(result.result, ActionError)


# ---- get_event ----


class TestGetEvent:
    @pytest.mark.asyncio
    async def test_returns_event(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {"id": "evt1", "summary": "Meeting", "location": "Conference Room A"}
        )
        result = await google_calendar.execute_action(
            "get_event", {"calendar_id": "primary", "event_id": "evt1"}, mock_context
        )
        assert isinstance(result.result, ActionResult)
        event = result.result.data["event"]
        assert event["id"] == "evt1"
        assert event["location"] == "Conference Room A"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Not Found"}, status=404)
        result = await google_calendar.execute_action(
            "get_event", {"calendar_id": "primary", "event_id": "nonexistent"}, mock_context
        )
        assert isinstance(result.result, ActionError)


# ---- create_event ----


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_creates_event(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(
            {"id": "new_evt", "summary": "New Event", "htmlLink": "https://calendar.google.com/..."}
        )
        result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": "primary",
                "summary": "New Event",
                "start_datetime": "2026-06-10T10:00:00",
                "end_datetime": "2026-06-10T11:00:00",
            },
            mock_context,
        )
        assert isinstance(result.result, ActionResult)
        assert result.result.data["event"]["id"] == "new_evt"

    @pytest.mark.asyncio
    async def test_includes_timezone_in_request(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"id": "e1", "summary": "TZ Event"})
        await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": "primary",
                "summary": "TZ Event",
                "start_datetime": "2026-06-10T10:00:00",
                "end_datetime": "2026-06-10T11:00:00",
                "timezone": "Pacific/Auckland",
            },
            mock_context,
        )
        body = mock_context.fetch.call_args[1]["json"]
        assert body["start"]["timeZone"] == "Pacific/Auckland"
        assert body["end"]["timeZone"] == "Pacific/Auckland"

    @pytest.mark.asyncio
    async def test_all_day_event(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"id": "e1", "summary": "All Day"})
        await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": "primary",
                "summary": "All Day",
                "start_date": "2026-06-15",
                "end_date": "2026-06-15",
            },
            mock_context,
        )
        body = mock_context.fetch.call_args[1]["json"]
        assert body["start"] == {"date": "2026-06-15"}
        assert body["end"] == {"date": "2026-06-15"}

    @pytest.mark.asyncio
    async def test_adds_attendees(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"id": "e1", "summary": "Meeting"})
        await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": "primary",
                "summary": "Meeting",
                "attendees": ["alice@example.com", "bob@example.com"],
            },
            mock_context,
        )
        body = mock_context.fetch.call_args[1]["json"]
        assert body["attendees"] == [{"email": "alice@example.com"}, {"email": "bob@example.com"}]

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Forbidden"}, status=403)
        result = await google_calendar.execute_action(
            "create_event", {"calendar_id": "primary", "summary": "X"}, mock_context
        )
        assert isinstance(result.result, ActionError)


# ---- update_event ----


class TestUpdateEvent:
    @pytest.mark.asyncio
    async def test_updates_event(self, mock_context):
        existing = {
            "id": "evt1",
            "summary": "Old Title",
            "start": {"dateTime": "2026-06-10T10:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-06-10T11:00:00Z", "timeZone": "UTC"},
        }
        updated = {"id": "evt1", "summary": "New Title"}
        mock_context.fetch.side_effect = [make_fetch_response(existing), make_fetch_response(updated)]
        result = await google_calendar.execute_action(
            "update_event",
            {"calendar_id": "primary", "event_id": "evt1", "summary": "New Title"},
            mock_context,
        )
        assert isinstance(result.result, ActionResult)
        assert result.result.data["event"]["summary"] == "New Title"

    @pytest.mark.asyncio
    async def test_clear_attendees_when_empty_list(self, mock_context):
        existing = {"id": "evt1", "summary": "Meeting", "attendees": [{"email": "a@b.com"}]}
        mock_context.fetch.side_effect = [
            make_fetch_response(existing),
            make_fetch_response({"id": "evt1", "summary": "Meeting"}),
        ]
        await google_calendar.execute_action(
            "update_event",
            {"calendar_id": "primary", "event_id": "evt1", "attendees": []},
            mock_context,
        )
        put_body = mock_context.fetch.call_args[1]["json"]
        assert "attendees" not in put_body

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Not Found"}, status=404)
        result = await google_calendar.execute_action(
            "update_event", {"calendar_id": "primary", "event_id": "bad"}, mock_context
        )
        assert isinstance(result.result, ActionError)


# ---- delete_event ----


class TestDeleteEvent:
    @pytest.mark.asyncio
    async def test_deletes_event(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response(None, status=204)
        result = await google_calendar.execute_action(
            "delete_event", {"calendar_id": "primary", "event_id": "evt1"}, mock_context
        )
        assert isinstance(result.result, ActionResult)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = make_fetch_response({"message": "Not Found"}, status=404)
        result = await google_calendar.execute_action(
            "delete_event", {"calendar_id": "primary", "event_id": "bad"}, mock_context
        )
        assert isinstance(result.result, ActionError)
