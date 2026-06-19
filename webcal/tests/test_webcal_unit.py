"""
Unit tests for the Webcal integration using a mocked ``context.fetch``.

The integration fetches an iCal/webcal feed and parses it locally with the
``icalendar`` library, so these tests build deterministic ICS payloads in
memory and assert on the parsed/normalised output. No network access.
"""

import os
import sys
from datetime import datetime, timedelta

import pytest
import pytz
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import webcal as webcal_mod  # noqa: E402

webcal_integration = webcal_mod.webcal

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers — build ICS payloads and mock contexts
# =============================================================================

_ICS_DT_FMT = "%Y%m%dT%H%M%SZ"
_ICS_DATE_FMT = "%Y%m%d"


def _utc_now():
    return datetime.now(pytz.utc)


def make_ics(events):
    """Build a minimal VCALENDAR string from a list of event dicts.

    Each event dict supports: uid, summary, description, location, start, end,
    all_day, organizer, attendees (list), url, rrule.
    """
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Autohive//Webcal Test//EN"]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append("UID:" + ev["uid"])
        lines.append("SUMMARY:" + ev.get("summary", ""))
        if ev.get("description"):
            lines.append("DESCRIPTION:" + ev["description"])
        if ev.get("location"):
            lines.append("LOCATION:" + ev["location"])
        if ev.get("all_day"):
            lines.append("DTSTART;VALUE=DATE:" + ev["start"].strftime(_ICS_DATE_FMT))
            if ev.get("end"):
                lines.append("DTEND;VALUE=DATE:" + ev["end"].strftime(_ICS_DATE_FMT))
        else:
            lines.append("DTSTART:" + ev["start"].strftime(_ICS_DT_FMT))
            if ev.get("end"):
                lines.append("DTEND:" + ev["end"].strftime(_ICS_DT_FMT))
        if ev.get("organizer"):
            lines.append("ORGANIZER:" + ev["organizer"])
        for att in ev.get("attendees", []):
            lines.append("ATTENDEE:" + att)
        if ev.get("url"):
            lines.append("URL:" + ev["url"])
        if ev.get("rrule"):
            lines.append("RRULE:" + ev["rrule"])
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def make_ctx(ics_text, status=200):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=FetchResponse(status=status, headers={}, data=ics_text))
    ctx.auth = {"credentials": {}}
    return ctx


# =============================================================================
# FETCH EVENTS
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_events_basic():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Team Meeting",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    data = result.result.data
    assert data["result"] is True
    assert data["timezone"] == "UTC"
    assert len(data["events"]) == 1
    event = data["events"][0]
    assert event["summary"] == "Team Meeting"
    assert event["all_day"] is False
    assert event["recurring"] is False


@pytest.mark.asyncio
async def test_fetch_events_defaults_to_utc_and_7_days():
    now = _utc_now()
    ics = make_ics(
        [{"uid": "1", "summary": "Soon", "start": now + timedelta(days=1), "end": now + timedelta(days=1, hours=1)}]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action("fetch_events", {"webcal_url": "https://example.com/cal.ics"}, ctx)
    data = result.result.data
    assert data["timezone"] == "UTC"
    assert len(data["events"]) == 1


@pytest.mark.asyncio
async def test_fetch_events_excludes_out_of_range():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "near",
                "summary": "Near",
                "start": now + timedelta(days=1),
                "end": now + timedelta(days=1, hours=1),
            },
            {
                "uid": "far",
                "summary": "Far",
                "start": now + timedelta(days=100),
                "end": now + timedelta(days=100, hours=1),
            },
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    summaries = [e["summary"] for e in result.result.data["events"]]
    assert summaries == ["Near"]


@pytest.mark.asyncio
async def test_fetch_events_includes_ongoing_event():
    now = _utc_now()
    ics = make_ics(
        [{"uid": "ong", "summary": "Ongoing Sprint", "start": now - timedelta(days=2), "end": now + timedelta(days=2)}]
    )
    ctx = make_ctx(ics)
    # look_ahead of 1 day: the event started in the past, but is still ongoing.
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 1}, ctx
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["summary"] == "Ongoing Sprint"


@pytest.mark.asyncio
async def test_fetch_events_all_day():
    now = _utc_now()
    ics = make_ics([{"uid": "hol", "summary": "Holiday", "start": now + timedelta(days=3), "all_day": True}])
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["all_day"] is True


@pytest.mark.asyncio
async def test_fetch_events_recurring_flag():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "r",
                "summary": "Daily Standup",
                "start": now + timedelta(days=1),
                "end": now + timedelta(days=1, minutes=15),
                "rrule": "FREQ=DAILY;COUNT=5",
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    assert result.result.data["events"][0]["recurring"] is True


@pytest.mark.asyncio
async def test_fetch_events_extracts_metadata():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "m",
                "summary": "Workshop",
                "description": "Bring laptop",
                "location": "Room 5",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=2),
                "organizer": "mailto:host@example.com",
                "attendees": ["mailto:a@example.com", "mailto:b@example.com"],
                "url": "https://example.com/event",
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    event = result.result.data["events"][0]
    assert event["description"] == "Bring laptop"
    assert event["location"] == "Room 5"
    assert event["organizer"] == "mailto:host@example.com"
    assert len(event["attendees"]) == 2
    assert event["url"] == "https://example.com/event"


@pytest.mark.asyncio
async def test_fetch_events_no_dtend_uses_start():
    now = _utc_now()
    ics = make_ics([{"uid": "noend", "summary": "Point In Time", "start": now + timedelta(days=2)}])
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    event = result.result.data["events"][0]
    assert event["start_time"] == event["end_time"]


@pytest.mark.asyncio
async def test_fetch_events_empty_calendar():
    ctx = make_ctx(make_ics([]))
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    assert result.result.data["events"] == []
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_fetch_events_respects_timezone():
    now = _utc_now()
    ics = make_ics(
        [{"uid": "tz", "summary": "Call", "start": now + timedelta(days=2), "end": now + timedelta(days=2, hours=1)}]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events",
        {"webcal_url": "https://example.com/cal.ics", "timezone": "America/New_York", "look_ahead_days": 7},
        ctx,
    )
    assert result.result.data["timezone"] == "America/New_York"
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_fetch_events_converts_webcal_protocol_to_https():
    ctx = make_ctx(make_ics([]))
    await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "webcal://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    called_url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert called_url == "https://example.com/cal.ics"


@pytest.mark.asyncio
async def test_fetch_events_missing_url_validation_error():
    ctx = make_ctx(make_ics([]))
    result = await webcal_integration.execute_action("fetch_events", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# SEARCH EVENTS
# =============================================================================


@pytest.mark.asyncio
async def test_search_events_match_summary():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Project Kickoff",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "Kickoff", "look_ahead_days": 30},
        ctx,
    )
    data = result.result.data
    assert data["result"] is True
    assert data["search_term"] == "Kickoff"
    assert len(data["events"]) == 1
    assert data["events"][0]["match_field"] == "summary"


@pytest.mark.asyncio
async def test_search_events_match_description():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Generic Event",
                "description": "Annual budget review session",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "budget", "look_ahead_days": 30},
        ctx,
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["match_field"] == "description"


@pytest.mark.asyncio
async def test_search_events_match_location():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Generic Event",
                "description": "Nothing special",
                "location": "Boardroom A",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "Boardroom", "look_ahead_days": 30},
        ctx,
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["match_field"] == "location"


@pytest.mark.asyncio
async def test_search_events_case_insensitive_default():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Team Sync",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "team sync", "look_ahead_days": 30},
        ctx,
    )
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_search_events_case_sensitive_no_match():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Team Sync",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {
            "webcal_url": "https://example.com/cal.ics",
            "search_term": "team sync",
            "case_sensitive": True,
            "look_ahead_days": 30,
        },
        ctx,
    )
    assert result.result.data["events"] == []


@pytest.mark.asyncio
async def test_search_events_case_sensitive_match():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Team Sync",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {
            "webcal_url": "https://example.com/cal.ics",
            "search_term": "Team",
            "case_sensitive": True,
            "look_ahead_days": 30,
        },
        ctx,
    )
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_search_events_no_results():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Team Sync",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "zzznotfound", "look_ahead_days": 30},
        ctx,
    )
    assert result.result.data["result"] is True
    assert result.result.data["events"] == []


@pytest.mark.asyncio
async def test_search_events_excludes_out_of_range():
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "far",
                "summary": "Faraway Kickoff",
                "start": now + timedelta(days=100),
                "end": now + timedelta(days=100, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "Kickoff", "look_ahead_days": 7},
        ctx,
    )
    assert result.result.data["events"] == []


@pytest.mark.asyncio
async def test_search_events_missing_search_term_validation_error():
    ctx = make_ctx(make_ics([]))
    result = await webcal_integration.execute_action(
        "search_events", {"webcal_url": "https://example.com/cal.ics"}, ctx
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_search_events_match_field_prefers_summary():
    # When the term appears in summary, description, and location, the matcher
    # must report "summary" — it checks summary first and short-circuits.
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "1",
                "summary": "Budget Planning",
                "description": "budget details inside",
                "location": "Budget Room",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "search_events",
        {"webcal_url": "https://example.com/cal.ics", "search_term": "budget", "look_ahead_days": 30},
        ctx,
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["match_field"] == "summary"


# =============================================================================
# EVENT DATA EXTRACTION — edge branches
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_events_single_attendee():
    # A single ATTENDEE parses to one object, not a list — exercises the
    # non-list branch in extract_event_data.
    now = _utc_now()
    ics = make_ics(
        [
            {
                "uid": "solo",
                "summary": "One-on-one",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=2, hours=1),
                "attendees": ["mailto:solo@example.com"],
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    event = result.result.data["events"][0]
    assert len(event["attendees"]) == 1
    assert "solo@example.com" in event["attendees"][0]


@pytest.mark.asyncio
async def test_fetch_events_all_day_with_end_date():
    # All-day event with an explicit DTEND date — exercises the all-day end
    # branch (date, not datetime) in both the range filter and extraction.
    now = _utc_now()
    start = now + timedelta(days=3)
    ics = make_ics(
        [
            {
                "uid": "multi",
                "summary": "Conference",
                "start": start,
                "end": start + timedelta(days=2),
                "all_day": True,
            }
        ]
    )
    ctx = make_ctx(ics)
    result = await webcal_integration.execute_action(
        "fetch_events", {"webcal_url": "https://example.com/cal.ics", "look_ahead_days": 7}, ctx
    )
    events = result.result.data["events"]
    assert len(events) == 1
    assert events[0]["all_day"] is True
    # End is two days after start, so it must differ from the start timestamp.
    assert events[0]["end_time"] != events[0]["start_time"]
