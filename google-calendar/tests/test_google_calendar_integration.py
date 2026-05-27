"""
Live integration tests for the Google Calendar integration.

Requires a valid Google OAuth2 access token in the environment:
    GOOGLE_CALENDAR_ACCESS_TOKEN=<token>

Run:
    pytest google-calendar/tests/test_google_calendar_integration.py -m integration -v
"""

import pytest
from autohive_integrations_sdk import ActionResult, ActionError
from autohive_integrations_sdk.integration import ResultType
from google_calendar import google_calendar

pytestmark = pytest.mark.integration

CALENDAR_ID = "primary"


def _assert_ok(result):
    """Unwrap IntegrationResult and assert no error."""
    assert result.type != ResultType.ACTION_ERROR, f"Action failed: {result.result}"
    assert result.type != ResultType.VALIDATION_ERROR, f"Validation error: {result.result}"
    assert isinstance(result.result, ActionResult), f"Expected ActionResult, got {type(result.result)}"
    return result.result.data


@pytest.fixture(scope="session")
def live_context(env_credentials, make_context):
    token = env_credentials("GOOGLE_CALENDAR_ACCESS_TOKEN")
    if not token:
        pytest.skip("GOOGLE_CALENDAR_ACCESS_TOKEN not set")
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": token},
        }
    )


@pytest.fixture(scope="session")
def created_event_id(live_context):
    """Create a test event once for the session; delete it at teardown."""
    result = pytest.run_coroutine(  # type: ignore[attr-defined]
        google_calendar.execute_action(
            "create_event",
            {
                "calendar_id": CALENDAR_ID,
                "summary": "[Autohive Test] Integration Test Event",
                "description": "Created by google-calendar integration tests — safe to delete",
                "start_datetime": "2026-07-01T10:00:00",
                "end_datetime": "2026-07-01T11:00:00",
                "timezone": "Pacific/Auckland",
            },
            live_context,
        )
    )
    data = _assert_ok(result)
    event_id = data["event"]["id"]
    yield event_id
    # Teardown — delete the test event
    import asyncio

    asyncio.get_event_loop().run_until_complete(
        google_calendar.execute_action("delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, live_context)
    )


# ---- Tests ----


@pytest.mark.asyncio
async def test_list_calendars(live_context):
    result = await google_calendar.execute_action("list_calendars", {}, live_context)
    data = _assert_ok(result)
    assert isinstance(data["calendars"], list)
    assert len(data["calendars"]) > 0
    cal_ids = [c["id"] for c in data["calendars"]]
    assert any("primary" in cid or "@" in cid for cid in cal_ids)


@pytest.mark.asyncio
async def test_list_events_returns_results(live_context):
    result = await google_calendar.execute_action(
        "list_events",
        {"calendar_id": CALENDAR_ID, "max_results": 10},
        live_context,
    )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_list_events_with_time_range(live_context):
    result = await google_calendar.execute_action(
        "list_events",
        {
            "calendar_id": CALENDAR_ID,
            "time_min": "2026-06-01T00:00:00Z",
            "time_max": "2026-07-31T23:59:59Z",
            "max_results": 50,
        },
        live_context,
    )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_list_events_recurring_instances_expanded(live_context):
    """Verify recurring events are returned as individual instances (singleEvents=true)."""
    result = await google_calendar.execute_action(
        "list_events",
        {"calendar_id": CALENDAR_ID, "max_results": 100},
        live_context,
    )
    data = _assert_ok(result)
    events = data["events"]
    # If any recurring events are present, they should have recurringEventId
    recurring = [e for e in events if "recurringEventId" in e]
    # Just verify parsing is correct — each recurring instance has a unique id
    for evt in recurring:
        assert evt["id"] != evt["recurringEventId"]


@pytest.mark.asyncio
async def test_list_events_with_query(live_context):
    result = await google_calendar.execute_action(
        "list_events",
        {"calendar_id": CALENDAR_ID, "query": "Integration Test"},
        live_context,
    )
    data = _assert_ok(result)
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_event(live_context):
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
        live_context,
    )
    data = _assert_ok(result)
    assert data["event"]["id"]
    assert data["event"]["summary"] == "[Autohive Test] Create Test"

    # Clean up
    await google_calendar.execute_action(
        "delete_event",
        {"calendar_id": CALENDAR_ID, "event_id": data["event"]["id"]},
        live_context,
    )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_all_day_event(live_context):
    result = await google_calendar.execute_action(
        "create_event",
        {
            "calendar_id": CALENDAR_ID,
            "summary": "[Autohive Test] All Day",
            "start_date": "2026-07-20",
            "end_date": "2026-07-20",
        },
        live_context,
    )
    data = _assert_ok(result)
    assert data["event"]["id"]

    # Clean up
    await google_calendar.execute_action(
        "delete_event",
        {"calendar_id": CALENDAR_ID, "event_id": data["event"]["id"]},
        live_context,
    )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_get_event(live_context):
    # Create an event to retrieve
    create_result = await google_calendar.execute_action(
        "create_event",
        {
            "calendar_id": CALENDAR_ID,
            "summary": "[Autohive Test] Get Test",
            "start_datetime": "2026-07-16T09:00:00",
            "end_datetime": "2026-07-16T09:30:00",
            "timezone": "UTC",
        },
        live_context,
    )
    event_id = _assert_ok(create_result)["event"]["id"]

    try:
        result = await google_calendar.execute_action(
            "get_event",
            {"calendar_id": CALENDAR_ID, "event_id": event_id},
            live_context,
        )
        data = _assert_ok(result)
        assert data["event"]["id"] == event_id
        assert data["event"]["summary"] == "[Autohive Test] Get Test"
    finally:
        await google_calendar.execute_action(
            "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, live_context
        )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_update_event(live_context):
    # Create an event to update
    create_result = await google_calendar.execute_action(
        "create_event",
        {
            "calendar_id": CALENDAR_ID,
            "summary": "[Autohive Test] Before Update",
            "start_datetime": "2026-07-17T10:00:00",
            "end_datetime": "2026-07-17T10:30:00",
            "timezone": "UTC",
        },
        live_context,
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
            live_context,
        )
        data = _assert_ok(result)
        assert data["event"]["id"] == event_id
        assert data["event"]["summary"] == "[Autohive Test] After Update"
    finally:
        await google_calendar.execute_action(
            "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, live_context
        )


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_delete_event(live_context):
    # Create an event to delete
    create_result = await google_calendar.execute_action(
        "create_event",
        {
            "calendar_id": CALENDAR_ID,
            "summary": "[Autohive Test] Delete Me",
            "start_datetime": "2026-07-18T11:00:00",
            "end_datetime": "2026-07-18T11:30:00",
            "timezone": "UTC",
        },
        live_context,
    )
    event_id = _assert_ok(create_result)["event"]["id"]

    result = await google_calendar.execute_action(
        "delete_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, live_context
    )
    data = _assert_ok(result)
    assert data["deleted"] is True

    # Verify it's gone
    get_result = await google_calendar.execute_action(
        "get_event", {"calendar_id": CALENDAR_ID, "event_id": event_id}, live_context
    )
    assert isinstance(get_result.result, ActionError)
