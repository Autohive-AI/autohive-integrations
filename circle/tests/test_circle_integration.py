"""
End-to-end integration tests for the Circle integration.

These tests call the real Circle Admin API (v2) and require a valid admin API
token set in the CIRCLE_API_TOKEN environment variable.

Run read-only tests (excludes destructive — the post lifecycle carries both the
integration and destructive markers, so a bare `-m integration` would select it):
    pytest circle/tests/test_circle_integration.py -m "integration and not destructive"

Run destructive tests (creates/updates real data on the community):
    pytest circle/tests/test_circle_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import circle as circle_mod  # noqa: E402

circle_integration = circle_mod.circle

pytestmark = pytest.mark.integration

API_TOKEN = os.environ.get("CIRCLE_API_TOKEN", "")


@pytest.fixture
def live_context():
    if not API_TOKEN:
        pytest.skip("CIRCLE_API_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers or {},
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_token": API_TOKEN}}
    return ctx


# =============================================================================
# COMMUNITY
# =============================================================================


class TestCommunity:
    async def test_get_community_info(self, live_context):
        result = await circle_integration.execute_action("get_community_info", {}, live_context)
        community = result.result.data["community"]
        assert isinstance(community, dict)
        assert community.get("id") is not None


# =============================================================================
# SPACES
# =============================================================================


class TestSpaces:
    async def test_search_spaces_returns_list(self, live_context):
        result = await circle_integration.execute_action("search_spaces", {"per_page": 10}, live_context)
        data = result.result.data
        assert isinstance(data["spaces"], list)
        assert isinstance(data["count"], int)

    async def test_get_space_by_id(self, live_context):
        spaces_result = await circle_integration.execute_action("search_spaces", {"per_page": 1}, live_context)
        spaces = spaces_result.result.data["spaces"]
        if not spaces:
            pytest.skip("No spaces in this community")

        space_id = spaces[0]["id"]
        result = await circle_integration.execute_action("get_space", {"space_id": str(space_id)}, live_context)
        assert str(result.result.data["space"]["id"]) == str(space_id)


# =============================================================================
# POSTS
# =============================================================================


class TestPosts:
    async def test_search_posts_returns_list(self, live_context):
        result = await circle_integration.execute_action("search_posts", {"per_page": 10}, live_context)
        data = result.result.data
        assert isinstance(data["posts"], list)
        assert isinstance(data["count"], int)

    async def test_get_post_by_id(self, live_context):
        posts_result = await circle_integration.execute_action("search_posts", {"per_page": 1}, live_context)
        posts = posts_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts in this community")

        post_id = posts[0]["id"]
        result = await circle_integration.execute_action("get_post", {"post_id": str(post_id)}, live_context)
        assert str(result.result.data["post"]["id"]) == str(post_id)

    async def test_get_post_comments(self, live_context):
        posts_result = await circle_integration.execute_action("search_posts", {"per_page": 5}, live_context)
        posts = posts_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts in this community")

        result = await circle_integration.execute_action(
            "get_post_comments", {"post_id": str(posts[0]["id"]), "per_page": 10}, live_context
        )
        data = result.result.data
        assert isinstance(data["comments"], list)
        assert isinstance(data["count"], int)


# =============================================================================
# MEMBERS
# =============================================================================


class TestMembers:
    async def test_list_members_returns_list(self, live_context):
        result = await circle_integration.execute_action("list_members", {"per_page": 10}, live_context)
        data = result.result.data
        assert isinstance(data["members"], list)
        assert isinstance(data["count"], int)

    async def test_get_member_by_id(self, live_context):
        members_result = await circle_integration.execute_action("list_members", {"per_page": 1}, live_context)
        members = members_result.result.data["members"]
        if not members:
            pytest.skip("No members in this community")

        member_id = members[0]["id"]
        result = await circle_integration.execute_action("get_member", {"member_id": str(member_id)}, live_context)
        assert str(result.result.data["member"]["id"]) == str(member_id)

    async def test_search_member_by_email(self, live_context):
        members_result = await circle_integration.execute_action("list_members", {"per_page": 10}, live_context)
        members = members_result.result.data["members"]
        email = next((m.get("email") for m in members if m.get("email")), None)
        if not email:
            pytest.skip("No member with a visible email in this community")

        result = await circle_integration.execute_action("search_member_by_email", {"email": email}, live_context)
        assert isinstance(result.result.data["member"], dict)


# =============================================================================
# EVENTS
# =============================================================================


class TestEvents:
    async def test_search_events_returns_list(self, live_context):
        result = await circle_integration.execute_action(
            "search_events", {"time_filter": "all", "per_page": 10}, live_context
        )
        data = result.result.data
        assert isinstance(data["events"], list)
        assert isinstance(data["count"], int)

    async def test_get_event_by_id(self, live_context):
        events_result = await circle_integration.execute_action(
            "search_events", {"time_filter": "all", "per_page": 1}, live_context
        )
        events = events_result.result.data["events"]
        if not events:
            pytest.skip("No events in this community")

        event_id = events[0]["id"]
        result = await circle_integration.execute_action("get_event", {"event_id": str(event_id)}, live_context)
        assert str(result.result.data["event"]["id"]) == str(event_id)


# =============================================================================
# TAGS / GROUPS (read-only listings)
# =============================================================================


class TestListings:
    async def test_list_tags(self, live_context):
        result = await circle_integration.execute_action("list_tags", {}, live_context)
        assert isinstance(result.result.data["tags"], list)

    async def test_list_space_groups(self, live_context):
        result = await circle_integration.execute_action("list_space_groups", {}, live_context)
        assert isinstance(result.result.data["space_groups"], list)

    async def test_list_access_groups(self, live_context):
        result = await circle_integration.execute_action("list_access_groups", {}, live_context)
        assert isinstance(result.result.data["access_groups"], list)


# =============================================================================
# DESTRUCTIVE — create/update (writes to the real community)
# Only run with: pytest -m "integration and destructive"
# Requires CIRCLE_TEST_SPACE_ID for the post lifecycle test.
# =============================================================================


@pytest.mark.destructive
class TestPostLifecycle:
    async def test_create_then_update_post(self, live_context):
        space_id = os.environ.get("CIRCLE_TEST_SPACE_ID")
        if not space_id:
            pytest.skip("CIRCLE_TEST_SPACE_ID not set")

        create_result = await circle_integration.execute_action(
            "create_post",
            {
                "space_id": int(space_id),
                "name": "Autohive integration test post",
                "body": "# Test\n\nCreated by an automated integration test. Safe to delete.",
                "status": "draft",
            },
            live_context,
        )
        post = create_result.result.data["post"]
        post_id = post["id"]
        assert post_id is not None

        update_result = await circle_integration.execute_action(
            "update_post",
            {"post_id": str(post_id), "name": "Autohive integration test post (updated)"},
            live_context,
        )
        assert update_result.result.data["post"] is not None
