"""
End-to-end integration tests for the Zoom integration.

These tests call the real Zoom API v2 and require a valid OAuth access token in
the ZOOM_ACCESS_TOKEN environment variable.

Run read-only tests:
    pytest zoom/tests/test_zoom_integration.py -m "integration and not destructive"

Run destructive tests (creates, updates, and deletes a real meeting):
    pytest zoom/tests/test_zoom_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

from zoom.zoom import zoom as zoom_integration, ZoomConnectedAccountHandler  # noqa: E402

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("ZOOM_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("ZOOM_ACCESS_TOKEN not set — skipping integration tests")

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


async def _me(live_context):
    """Return the authenticated user's record (also asserts auth works)."""
    result = await zoom_integration.execute_action("get_user", {"user_id": "me"}, live_context)
    assert result.type != ResultType.ACTION_ERROR, getattr(result.result, "message", "")
    return result.result.data


# =============================================================================
# CONNECTED ACCOUNT
# =============================================================================


class TestConnectedAccount:
    async def test_get_account_info(self, live_context):
        handler = ZoomConnectedAccountHandler()
        info = await handler.get_account_info(live_context)
        assert info.email
        assert info.user_id


# =============================================================================
# USER
# =============================================================================


class TestUser:
    async def test_get_current_user(self, live_context):
        user = await _me(live_context)
        assert user["email"]
        assert user["id"]

    async def test_get_user_permissions(self, live_context):
        result = await zoom_integration.execute_action("get_user_permissions", {"user_id": "me"}, live_context)
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Permissions endpoint unavailable: {result.result.message}")
        assert isinstance(result.result.data["permissions"], list)


# =============================================================================
# MEETINGS (read-only)
# =============================================================================


class TestMeetings:
    async def test_list_meetings(self, live_context):
        result = await zoom_integration.execute_action(
            "list_meetings", {"user_id": "me", "type": "scheduled", "page_size": 10}, live_context
        )
        assert result.type != ResultType.ACTION_ERROR, getattr(result.result, "message", "")
        assert isinstance(result.result.data["meetings"], list)

    async def test_get_meeting_not_found_is_action_error(self, live_context):
        # A non-existent meeting id should surface a clean ActionError, not a crash.
        result = await zoom_integration.execute_action("get_meeting", {"meeting_id": "0"}, live_context)
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message


# =============================================================================
# CONTACTS — may be unavailable depending on plan / scopes
# =============================================================================


class TestContacts:
    async def test_list_contacts(self, live_context):
        result = await zoom_integration.execute_action("list_contacts", {"type": "company"}, live_context)
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"Contacts unavailable on this plan/scope: {result.result.message}")
        assert isinstance(result.result.data["contacts"], list)


# =============================================================================
# DESTRUCTIVE — create, update, then delete a real meeting
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestMeetingLifecycle:
    async def test_create_update_delete(self, live_context):
        create = await zoom_integration.execute_action(
            "create_meeting",
            {"topic": "Autohive Integration Test", "type": 2, "duration": 30, "agenda": "Automated test meeting"},
            live_context,
        )
        assert create.type != ResultType.ACTION_ERROR, getattr(create.result, "message", "")
        meeting_id = create.result.data["id"]
        assert meeting_id

        # Guarantee cleanup even if a later assertion or API call fails.
        try:
            got = await zoom_integration.execute_action("get_meeting", {"meeting_id": str(meeting_id)}, live_context)
            assert got.result.data["topic"] == "Autohive Integration Test"

            updated = await zoom_integration.execute_action(
                "update_meeting",
                {"meeting_id": str(meeting_id), "topic": "Autohive Integration Test (updated)"},
                live_context,
            )
            assert updated.result.data["meeting_id"] == str(meeting_id)
        finally:
            deleted = await zoom_integration.execute_action(
                "delete_meeting", {"meeting_id": str(meeting_id)}, live_context
            )
            assert deleted.result.data["meeting_id"] == str(meeting_id)
