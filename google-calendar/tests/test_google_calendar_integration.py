"""
Live integration tests for the Google Calendar integration.

Requires a valid Google OAuth2 access token in the environment:
    GOOGLE_CALENDAR_ACCESS_TOKEN=<token>

Run:
    pytest google-calendar/tests/test_google_calendar_integration.py -m integration -v
"""

from __future__ import annotations

import os
import sys

import pytest
from autohive_integrations_sdk import ActionResult, ExecutionContext, IntegrationResult
from autohive_integrations_sdk.integration import ResultType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google_calendar import google_calendar  # noqa: E402

pytestmark = pytest.mark.integration

CALENDAR_ID = "primary"


def _assert_ok(result):
    """Unwrap IntegrationResult and assert no error."""
    if isinstance(result, IntegrationResult):
        assert result.type != ResultType.ACTION_ERROR, (
            f"Expected success but got ActionError: {getattr(result.result, 'message', result)!r}"
        )
        assert result.type != ResultType.VALIDATION_ERROR, f"Validation error: {result.result}"
        return result.result.data
    assert isinstance(result, ActionResult), f"Expected ActionResult, got {type(result)}"
    return result.data


@pytest.fixture(scope="session")
def gcal_auth():
    token = os.environ.get("GOOGLE_CALENDAR_ACCESS_TOKEN")
    if not token:
        pytest.skip("GOOGLE_CALENDAR_ACCESS_TOKEN not set")
    return {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": token},
    }


# ---- Read-only tests ----


@pytest.mark.asyncio
async def test_list_calendars(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action("list_calendars", {}, ctx)
    data = _assert_ok(result)
    assert isinstance(data["calendars"], list)
    assert len(data["calendars"]) > 0


@pytest.mark.asyncio
async def test_list_events_returns_results(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "list_events",
            {"calendar_id": CALENDAR_ID, "max_results": 10},
            ctx,
        )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_list_events_with_time_range(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "list_events",
            {
                "calendar_id": CALENDAR_ID,
                "time_min": "2026-06-01T00:00:00Z",
                "time_max": "2026-07-31T23:59:59Z",
                "max_results": 50,
            },
            ctx,
        )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_list_events_recurring_instances_expanded(gcal_auth):
    """Verify recurring events are returned as individual instances (singleEvents=true fix)."""
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "list_events",
            {"calendar_id": CALENDAR_ID, "max_results": 100},
            ctx,
        )
    data = _assert_ok(result)
    events = data["events"]
    # Any recurring instances should have a unique id different from their parent
    for evt in events:
        if "recurringEventId" in evt:
            assert evt["id"] != evt["recurringEventId"]


@pytest.mark.asyncio
async def test_list_events_with_query(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "list_events",
            {"calendar_id": CALENDAR_ID, "query": "Autohive"},
            ctx,
        )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


# ---- Destructive tests (create / get / update / delete) ----


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_event(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] Create Test",
                "description": "Created by integration tests",
                "start_datetime": "2026-07-15T14:00:00",
                "end_datetime": "2026-07-15T14:30:00",
                "timezone": "Pacific/Auckland",
            },
            ctx,
        )
        data = _assert_ok(result)
        event_id = data["event"]["id"]
        assert event_id
        assert data["event"]["summary"] == "[Autohive Test] Create Test"

        # Clean up
        await google_calendar.execute_action("delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx)


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_all_day_event(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] All Day",
                "start_date": "2026-07-20",
                "end_date": "2026-07-21",
            },
            ctx,
        )
        data = _assert_ok(result)
        event_id = data["event"]["id"]
        assert event_id

        # Clean up
        await google_calendar.execute_action("delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx)


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_get_event(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        create_result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] Get Test",
                "start_datetime": "2026-07-16T09:00:00",
                "end_datetime": "2026-07-16T09:30:00",
                "timezone": "UTC",
            },
            ctx,
        )
        event_id = _assert_ok(create_result)["event"]["id"]

        try:
            result = await google_calendar.execute_action(
                "get_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx
            )
            data = _assert_ok(result)
            assert data["event"]["id"] == event_id
            assert data["event"]["summary"] == "[Autohive Test] Get Test"
        finally:
            await google_calendar.execute_action(
                "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx
            )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_update_event(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        create_result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] Before Update",
                "start_datetime": "2026-07-17T10:00:00",
                "end_datetime": "2026-07-17T10:30:00",
                "timezone": "UTC",
            },
            ctx,
        )
        event_id = _assert_ok(create_result)["event"]["id"]

        try:
            result = await google_calendar.execute_action(
                "update_event",
                {
                    "calendar_id": CALENDAR_ID,
                    "event_id": event_id,
                    "summary": "[Autohive Test] After Update",
                    "description": "Updated by integration test",
                },
                ctx,
            )
            data = _assert_ok(result)
            assert data["event"]["id"] == event_id
            assert data["event"]["summary"] == "[Autohive Test] After Update"
        finally:
            await google_calendar.execute_action(
                "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx
            )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_delete_event(gcal_auth):
    async with ExecutionContext(auth=gcal_auth) as ctx:
        create_result = await google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] Delete Me",
                "start_datetime": "2026-07-18T11:00:00",
                "end_datetime": "2026-07-18T11:30:00",
                "timezone": "UTC",
            },
            ctx,
        )
        event_id = _assert_ok(create_result)["event"]["id"]

        result = await google_calendar.execute_action(
            "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, ctx
        )
        data = _assert_ok(result)
        assert data["deleted"] is True
