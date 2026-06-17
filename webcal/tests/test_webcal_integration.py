"""
End-to-end integration tests for the Webcal integration.

Webcal requires no authentication — it fetches public iCal/webcal feeds. These
tests hit a real public calendar feed over the network. Override the feed with
the WEBCAL_TEST_URL environment variable if the default becomes unavailable.

Run:
    pytest webcal/tests/test_webcal_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import webcal as webcal_mod  # noqa: E402

webcal_integration = webcal_mod.webcal

pytestmark = pytest.mark.integration

# Public US Holidays iCal feed — no auth required.
PUBLIC_ICS_URL = os.environ.get("WEBCAL_TEST_URL", "https://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics")
PUBLIC_WEBCAL_URL = PUBLIC_ICS_URL.replace("https://", "webcal://")


@pytest.fixture
def live_context():
    async def real_fetch(url, *, method="GET", params=None, data=None, headers=None, json=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json or data, headers=headers or {}) as resp:
                # iCal feeds return text/calendar — read the body as text, not JSON.
                body = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {}}
    return ctx


# =============================================================================
# FETCH EVENTS
# =============================================================================


class TestFetchEvents:
    async def test_returns_event_structure(self, live_context):
        result = await webcal_integration.execute_action(
            "fetch_events", {"webcal_url": PUBLIC_ICS_URL, "look_ahead_days": 365}, live_context
        )
        data = result.result.data
        assert data["result"] is True
        assert data["timezone"] == "UTC"
        assert isinstance(data["events"], list)

    async def test_webcal_protocol_url(self, live_context):
        result = await webcal_integration.execute_action(
            "fetch_events", {"webcal_url": PUBLIC_WEBCAL_URL, "look_ahead_days": 365}, live_context
        )
        assert result.result.data["result"] is True
        assert isinstance(result.result.data["events"], list)

    async def test_respects_timezone(self, live_context):
        result = await webcal_integration.execute_action(
            "fetch_events",
            {"webcal_url": PUBLIC_ICS_URL, "timezone": "Pacific/Auckland", "look_ahead_days": 365},
            live_context,
        )
        assert result.result.data["timezone"] == "Pacific/Auckland"

    async def test_event_fields_present(self, live_context):
        result = await webcal_integration.execute_action(
            "fetch_events", {"webcal_url": PUBLIC_ICS_URL, "look_ahead_days": 365}, live_context
        )
        events = result.result.data["events"]
        if not events:
            pytest.skip("No events in the feed for the look-ahead window")
        event = events[0]
        for field in ("summary", "start_time", "end_time", "all_day", "recurring"):
            assert field in event


# =============================================================================
# SEARCH EVENTS
# =============================================================================


class TestSearchEvents:
    async def test_search_returns_structure(self, live_context):
        result = await webcal_integration.execute_action(
            "search_events",
            {"webcal_url": PUBLIC_ICS_URL, "search_term": "Day", "look_ahead_days": 365},
            live_context,
        )
        data = result.result.data
        assert data["result"] is True
        assert data["search_term"] == "Day"
        assert isinstance(data["events"], list)
        for event in data["events"]:
            assert event["match_field"] in ("summary", "description", "location")

    async def test_search_no_results_for_gibberish(self, live_context):
        result = await webcal_integration.execute_action(
            "search_events",
            {"webcal_url": PUBLIC_ICS_URL, "search_term": "zzznonexistentxyz123", "look_ahead_days": 365},
            live_context,
        )
        assert result.result.data["result"] is True
        assert result.result.data["events"] == []

    async def test_case_sensitivity(self, live_context):
        insensitive = await webcal_integration.execute_action(
            "search_events",
            {"webcal_url": PUBLIC_ICS_URL, "search_term": "day", "case_sensitive": False, "look_ahead_days": 365},
            live_context,
        )
        sensitive = await webcal_integration.execute_action(
            "search_events",
            {"webcal_url": PUBLIC_ICS_URL, "search_term": "day", "case_sensitive": True, "look_ahead_days": 365},
            live_context,
        )
        # A case-sensitive search for the lowercase term cannot match more than
        # the case-insensitive one.
        assert len(sensitive.result.data["events"]) <= len(insensitive.result.data["events"])
