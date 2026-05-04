"""
End-to-end integration tests for the Humanitix integration.

These tests call the real Humanitix API and require a valid API key
set in the HUMANITIX_API_KEY environment variable (via .env or export).

Run with:
    pytest humanitix/tests/test_humanitix_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

os.chdir(_parent)
_spec = importlib.util.spec_from_file_location("humanitix_mod_integration", os.path.join(_parent, "humanitix.py"))
_mod = importlib.util.module_from_spec(_spec)
# Register as "humanitix" so that actions/*.py can `from humanitix import humanitix`
sys.modules.setdefault("humanitix", _mod)
_spec.loader.exec_module(_mod)

humanitix = _mod.humanitix

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("HUMANITIX_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("HUMANITIX_API_KEY not set — skipping integration tests")

    from curl_cffi.requests import AsyncSession

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with AsyncSession(impersonate="chrome") as session:
            resp = await session.request(method, url, json=json, headers=headers or {}, params=params)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return FetchResponse(status=resp.status_code, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": API_KEY}}  # nosec B105
    return ctx


class TestGetEvents:
    async def test_returns_events_list(self, live_context):
        result = await humanitix.execute_action("get_events", {"page_size": 5}, live_context)

        data = result.result.data
        assert "result" in data
        assert "events" in data
        assert isinstance(data["events"], list)

    async def test_has_pagination_fields(self, live_context):
        result = await humanitix.execute_action("get_events", {"page_size": 5}, live_context)

        data = result.result.data
        if data.get("result") is True:
            assert "total" in data
            assert "page" in data
            assert "pageSize" in data


class TestGetTags:
    async def test_returns_tags_list(self, live_context):
        result = await humanitix.execute_action("get_tags", {"page_size": 5}, live_context)

        data = result.result.data
        assert "result" in data
        assert "tags" in data
        assert isinstance(data["tags"], list)

    async def test_tags_structure(self, live_context):
        result = await humanitix.execute_action("get_tags", {"page_size": 5}, live_context)

        data = result.result.data
        if data.get("result") is True and data["tags"]:
            tag = data["tags"][0]
            assert "_id" in tag
            assert "name" in tag

    async def test_pagination_params_respected(self, live_context):
        result = await humanitix.execute_action("get_tags", {"page_size": 2, "page": 1}, live_context)

        data = result.result.data
        if data.get("result") is True:
            assert len(data["tags"]) <= 2


class TestGetOrders:
    async def test_returns_orders_list(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        result = await humanitix.execute_action("get_orders", {"event_id": event_id, "page_size": 5}, live_context)

        data = result.result.data
        assert "orders" in data
        assert isinstance(data["orders"], list)

    async def test_has_pagination_fields(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        result = await humanitix.execute_action("get_orders", {"event_id": event_id, "page_size": 5}, live_context)

        data = result.result.data
        if data.get("result") is True:
            assert "total" in data
            assert "page" in data
            assert "pageSize" in data


class TestGetTickets:
    async def test_returns_tickets_list(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        result = await humanitix.execute_action("get_tickets", {"event_id": event_id, "page_size": 5}, live_context)

        data = result.result.data
        assert "tickets" in data
        assert isinstance(data["tickets"], list)

    async def test_has_pagination_fields(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        result = await humanitix.execute_action("get_tickets", {"event_id": event_id, "page_size": 5}, live_context)

        data = result.result.data
        if data.get("result") is True:
            assert "total" in data
            assert "page" in data
            assert "pageSize" in data

    async def test_status_filter(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        result = await humanitix.execute_action(
            "get_tickets", {"event_id": event_id, "page_size": 5, "status": "complete"}, live_context
        )

        data = result.result.data
        assert "tickets" in data


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCheckInOut:
    async def test_check_in_and_out(self, live_context):
        events_result = await humanitix.execute_action("get_events", {"page_size": 1}, live_context)
        events = events_result.result.data.get("events", [])

        if not events:
            pytest.skip("No events in account to test with")

        event_id = events[0]["_id"]
        tickets_result = await humanitix.execute_action(
            "get_tickets", {"event_id": event_id, "page_size": 1}, live_context
        )
        tickets = tickets_result.result.data.get("tickets", [])

        if not tickets:
            pytest.skip("No tickets in event to test with")

        ticket_id = tickets[0]["_id"]

        check_in_result = await humanitix.execute_action(
            "check_in", {"event_id": event_id, "ticket_id": ticket_id}, live_context
        )
        assert "result" in check_in_result.result.data

        check_out_result = await humanitix.execute_action(
            "check_out", {"event_id": event_id, "ticket_id": ticket_id}, live_context
        )
        assert "result" in check_out_result.result.data
