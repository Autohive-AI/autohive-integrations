"""
End-to-end integration tests for the Calendly integration.

These tests call the real Calendly API v2 and require a valid OAuth/personal
access token in the CALENDLY_ACCESS_TOKEN environment variable.

Run all read-only tests:
    pytest calendly/tests/test_calendly_integration.py -m integration

Run destructive tests (creates/deletes a real webhook subscription, requires a
paid Calendly plan):
    pytest calendly/tests/test_calendly_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import calendly as calendly_mod  # noqa: E402

calendly_integration = calendly_mod.calendly

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("CALENDLY_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("CALENDLY_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        request_headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=request_headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                # Mirror the SDK contract: context.fetch() raises on non-2xx so the
                # action's try/except surfaces an ActionError. Returning a FetchResponse
                # for an error status would let an error body masquerade as success data.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


def _uuid_from_uri(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


async def _current_user(live_context):
    result = await calendly_integration.execute_action("get_current_user", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, getattr(result.result, "message", "")
    return result.result.data["user"]


# =============================================================================
# CURRENT USER / GET USER
# =============================================================================


class TestCurrentUser:
    async def test_returns_user_uri_and_org(self, live_context):
        user = await _current_user(live_context)
        assert user.get("uri", "").startswith("https://api.calendly.com/users/")
        assert "current_organization" in user

    async def test_get_user_by_uuid(self, live_context):
        user = await _current_user(live_context)
        uuid = _uuid_from_uri(user["uri"])
        result = await calendly_integration.execute_action("get_user", {"user_uuid": uuid}, live_context)
        assert result.result.data["user"]["uri"] == user["uri"]


# =============================================================================
# EVENT TYPES
# =============================================================================


class TestEventTypes:
    async def test_list_event_types(self, live_context):
        user = await _current_user(live_context)
        result = await calendly_integration.execute_action(
            "list_event_types", {"user": user["uri"], "count": 10}, live_context
        )
        data = result.result.data
        assert isinstance(data["event_types"], list)
        assert isinstance(data["pagination"], dict)

    async def test_get_event_type_detail(self, live_context):
        user = await _current_user(live_context)
        listed = await calendly_integration.execute_action(
            "list_event_types", {"user": user["uri"], "count": 10}, live_context
        )
        event_types = listed.result.data["event_types"]
        if not event_types:
            pytest.skip("No event types on this account")

        uuid = _uuid_from_uri(event_types[0]["uri"])
        result = await calendly_integration.execute_action("get_event_type", {"event_type_uuid": uuid}, live_context)
        assert result.result.data["event_type"]["uri"] == event_types[0]["uri"]


# =============================================================================
# SCHEDULED EVENTS / INVITEES
# =============================================================================


class TestScheduledEvents:
    async def test_list_scheduled_events(self, live_context):
        user = await _current_user(live_context)
        result = await calendly_integration.execute_action(
            "list_scheduled_events", {"user": user["uri"], "count": 10}, live_context
        )
        assert isinstance(result.result.data["events"], list)

    async def test_get_event_and_invitees(self, live_context):
        user = await _current_user(live_context)
        listed = await calendly_integration.execute_action(
            "list_scheduled_events", {"user": user["uri"], "count": 10}, live_context
        )
        events = listed.result.data["events"]
        if not events:
            pytest.skip("No scheduled events on this account")

        uuid = _uuid_from_uri(events[0]["uri"])
        detail = await calendly_integration.execute_action("get_scheduled_event", {"event_uuid": uuid}, live_context)
        assert detail.result.data["event"]["uri"] == events[0]["uri"]

        invitees = await calendly_integration.execute_action(
            "list_event_invitees", {"event_uuid": uuid, "count": 10}, live_context
        )
        assert isinstance(invitees.result.data["invitees"], list)


# =============================================================================
# AVAILABILITY
# =============================================================================


class TestAvailability:
    async def test_user_busy_times(self, live_context):
        user = await _current_user(live_context)
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=6)
        result = await calendly_integration.execute_action(
            "get_user_busy_times",
            {
                "user": user["uri"],
                "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            live_context,
        )
        assert isinstance(result.result.data["busy_times"], list)

    async def test_list_availability_schedules(self, live_context):
        user = await _current_user(live_context)
        result = await calendly_integration.execute_action(
            "list_user_availability_schedules", {"user": user["uri"]}, live_context
        )
        assert isinstance(result.result.data["availability_schedules"], list)

    async def test_event_type_available_times(self, live_context):
        user = await _current_user(live_context)
        listed = await calendly_integration.execute_action(
            "list_event_types", {"user": user["uri"], "active": True, "count": 10}, live_context
        )
        event_types = [et for et in listed.result.data["event_types"] if et.get("active")]
        if not event_types:
            pytest.skip("No active event types to query availability for")

        start = datetime.now(timezone.utc) + timedelta(hours=1)
        end = start + timedelta(days=6)
        result = await calendly_integration.execute_action(
            "get_event_type_available_times",
            {
                "event_type": event_types[0]["uri"],
                "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            live_context,
        )
        assert isinstance(result.result.data["available_times"], list)


# =============================================================================
# ORGANIZATION
# =============================================================================


class TestOrganization:
    async def test_list_memberships(self, live_context):
        user = await _current_user(live_context)
        org = user.get("current_organization")
        if not org:
            pytest.skip("User has no current_organization")
        result = await calendly_integration.execute_action(
            "list_organization_memberships", {"organization": org, "count": 10}, live_context
        )
        assert isinstance(result.result.data["memberships"], list)


# =============================================================================
# WEBHOOKS (read-only) — may require a paid plan
# =============================================================================


class TestWebhooks:
    async def test_list_webhooks(self, live_context):
        user = await _current_user(live_context)
        org = user.get("current_organization")
        if not org:
            pytest.skip("User has no current_organization")
        result = await calendly_integration.execute_action(
            "list_webhooks", {"organization": org, "scope": "organization"}, live_context
        )
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Webhooks unavailable (likely free plan): {result.result.message}")
        assert isinstance(result.result.data["webhooks"], list)


# =============================================================================
# ROUTING FORMS — may be unavailable on some plans
# =============================================================================


class TestRoutingForms:
    async def test_list_routing_forms(self, live_context):
        user = await _current_user(live_context)
        org = user.get("current_organization")
        if not org:
            pytest.skip("User has no current_organization")
        result = await calendly_integration.execute_action(
            "list_routing_forms", {"organization": org, "count": 10}, live_context
        )
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Routing forms unavailable on this plan: {result.result.message}")
        assert isinstance(result.result.data["routing_forms"], list)


# =============================================================================
# DESTRUCTIVE — create then delete a real webhook (requires a paid plan)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestWebhookLifecycle:
    async def test_create_then_delete(self, live_context):
        user = await _current_user(live_context)
        org = user.get("current_organization")
        if not org:
            pytest.skip("User has no current_organization")

        create = await calendly_integration.execute_action(
            "create_webhook",
            {
                "url": "https://example.com/calendly-integration-test",
                "events": ["invitee.created", "invitee.canceled"],
                "organization": org,
                "scope": "organization",
            },
            live_context,
        )
        if create.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Webhook creation unavailable (likely free plan): {create.result.message}")

        webhook = create.result.data["webhook"]
        assert webhook.get("uri")

        uuid = _uuid_from_uri(webhook["uri"])
        delete = await calendly_integration.execute_action("delete_webhook", {"webhook_uuid": uuid}, live_context)
        assert delete.result.data["deleted"] is True
