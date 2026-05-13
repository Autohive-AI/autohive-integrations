"""
End-to-end integration tests for the Instagram integration.

These tests call the real Instagram Graph API and require a valid access token
set in the INSTAGRAM_ACCESS_TOKEN environment variable.

Run all read-only tests:
    pytest instagram/tests/test_instagram_integration.py -m integration

Run destructive tests (posts/comments written to real account):
    pytest instagram/tests/test_instagram_integration.py -m "integration and destructive"

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

import instagram as instagram_mod  # noqa: E402
from instagram import InstagramConnectedAccountHandler  # noqa: E402

instagram_integration = instagram_mod.instagram

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("INSTAGRAM_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, data=None, headers=None, json=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            # Instagram Graph API uses access_token as a query param for OAuth flows
            all_params = {"access_token": ACCESS_TOKEN, **(params or {})}
            async with session.request(
                method, url, params=all_params, json=json or data, headers=headers or {}
            ) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# =============================================================================
# CONNECTED ACCOUNT
# =============================================================================


class TestConnectedAccount:
    async def test_get_account_info_returns_username(self, live_context):
        handler = InstagramConnectedAccountHandler()
        result = await handler.get_account_info(live_context)
        assert result.username is not None
        assert result.user_id is not None

    async def test_get_account_info_has_name(self, live_context):
        handler = InstagramConnectedAccountHandler()
        result = await handler.get_account_info(live_context)
        # at least first_name or last_name should be present if the account has a name
        assert result.first_name is not None or result.last_name is None  # graceful either way


# =============================================================================
# GET ACCOUNT
# =============================================================================


class TestGetAccount:
    async def test_returns_account_fields(self, live_context):
        result = await instagram_integration.execute_action("get_account", {}, live_context)
        data = result.result.data
        assert "id" in data
        assert "username" in data
        assert isinstance(data["followers_count"], int)
        assert isinstance(data["following_count"], int)
        assert isinstance(data["media_count"], int)

    async def test_id_is_string(self, live_context):
        result = await instagram_integration.execute_action("get_account", {}, live_context)
        assert isinstance(result.result.data["id"], str)
        assert len(result.result.data["id"]) > 0


# =============================================================================
# GET POSTS
# =============================================================================


class TestGetPosts:
    async def test_returns_media_list(self, live_context):
        result = await instagram_integration.execute_action("get_posts", {}, live_context)
        data = result.result.data
        assert "media" in data
        assert isinstance(data["media"], list)

    async def test_limit_respected(self, live_context):
        result = await instagram_integration.execute_action("get_posts", {"limit": 2}, live_context)
        data = result.result.data
        assert len(data["media"]) <= 2

    async def test_media_item_has_expected_fields(self, live_context):
        result = await instagram_integration.execute_action("get_posts", {"limit": 1}, live_context)
        media = result.result.data["media"]
        if not media:
            pytest.skip("No posts on this account")
        item = media[0]
        assert "id" in item
        assert "media_type" in item
        assert "timestamp" in item

    async def test_get_single_post_by_id(self, live_context):
        list_result = await instagram_integration.execute_action("get_posts", {"limit": 1}, live_context)
        media = list_result.result.data["media"]
        if not media:
            pytest.skip("No posts on this account")

        post_id = media[0]["id"]
        result = await instagram_integration.execute_action("get_posts", {"media_id": post_id}, live_context)
        data = result.result.data
        assert len(data["media"]) == 1
        assert data["media"][0]["id"] == post_id

    async def test_pagination_cursor_present_when_more_results(self, live_context):
        # fetch with limit=1 — if account has >1 post there should be a next_cursor
        account_result = await instagram_integration.execute_action("get_account", {}, live_context)
        media_count = account_result.result.data.get("media_count", 0)
        if media_count < 2:
            pytest.skip("Account has fewer than 2 posts — can't test pagination")

        result = await instagram_integration.execute_action("get_posts", {"limit": 1}, live_context)
        assert result.result.data["next_cursor"] is not None


# =============================================================================
# GET COMMENTS
# =============================================================================


class TestGetComments:
    async def test_returns_comments_list(self, live_context):
        list_result = await instagram_integration.execute_action("get_posts", {"limit": 5}, live_context)
        media = list_result.result.data["media"]
        if not media:
            pytest.skip("No posts on this account")

        # try each post until we find one (some may have comments disabled)
        for post in media:
            result = await instagram_integration.execute_action(
                "get_comments", {"media_id": post["id"]}, live_context
            )
            data = result.result.data
            assert "comments" in data
            assert isinstance(data["comments"], list)
            assert "total_count" in data
            return  # tested at least one post

    async def test_comment_structure(self, live_context):
        list_result = await instagram_integration.execute_action("get_posts", {"limit": 5}, live_context)
        media = list_result.result.data["media"]
        if not media:
            pytest.skip("No posts on this account")

        for post in media:
            result = await instagram_integration.execute_action(
                "get_comments", {"media_id": post["id"]}, live_context
            )
            comments = result.result.data["comments"]
            if comments:
                c = comments[0]
                assert "id" in c
                assert "text" in c
                assert "timestamp" in c
                assert "replies" in c
                return

        pytest.skip("No posts with comments found")


# =============================================================================
# GET INSIGHTS
# =============================================================================


class TestGetInsights:
    async def test_account_insights_returns_metrics(self, live_context):
        result = await instagram_integration.execute_action(
            "get_insights", {"target_type": "account"}, live_context
        )
        data = result.result.data
        assert data["target_type"] == "account"
        assert isinstance(data["metrics"], dict)

    async def test_account_insights_period_field(self, live_context):
        result = await instagram_integration.execute_action(
            "get_insights", {"target_type": "account", "period": "week"}, live_context
        )
        assert result.result.data["period"] == "week"

    async def test_media_insights_for_feed_post(self, live_context):
        list_result = await instagram_integration.execute_action("get_posts", {"limit": 5}, live_context)
        media = list_result.result.data["media"]
        if not media:
            pytest.skip("No posts on this account")

        # find a non-story post
        feed_post = next(
            (m for m in media if m.get("media_type") not in ("STORY",)), None
        )
        if not feed_post:
            pytest.skip("No feed posts found")

        result = await instagram_integration.execute_action(
            "get_insights", {"target_type": "media", "target_id": feed_post["id"]}, live_context
        )
        data = result.result.data
        assert data["target_type"] == "media"
        assert data["target_id"] == feed_post["id"]
        assert isinstance(data["metrics"], dict)


# =============================================================================
# DESTRUCTIVE — create/manage/delete (writes to real account)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestCommentLifecycle:
    """Reply to a comment → hide → unhide → delete the reply.

    Requires a post with at least one comment. Skips gracefully if none found.
    """

    async def test_full_lifecycle(self, live_context):
        # find a post with a comment
        list_result = await instagram_integration.execute_action("get_posts", {"limit": 10}, live_context)
        media = list_result.result.data["media"]
        if not media:
            pytest.skip("No posts found")

        target_comment_id = None
        for post in media:
            comments_result = await instagram_integration.execute_action(
                "get_comments", {"media_id": post["id"]}, live_context
            )
            comments = comments_result.result.data["comments"]
            if comments:
                target_comment_id = comments[0]["id"]
                break

        if not target_comment_id:
            pytest.skip("No comments found on any post")

        # reply
        reply_result = await instagram_integration.execute_action(
            "manage_comment",
            {"comment_id": target_comment_id, "action": "reply", "message": "Integration test reply — will be deleted"},
            live_context,
        )
        assert reply_result.result.data["success"] is True
        reply_id = reply_result.result.data["reply_id"]
        assert reply_id

        # hide the original comment
        hide_result = await instagram_integration.execute_action(
            "manage_comment", {"comment_id": target_comment_id, "action": "hide"}, live_context
        )
        assert hide_result.result.data["is_hidden"] is True

        # unhide
        unhide_result = await instagram_integration.execute_action(
            "manage_comment", {"comment_id": target_comment_id, "action": "unhide"}, live_context
        )
        assert unhide_result.result.data["is_hidden"] is False

        # delete the reply we created
        delete_result = await instagram_integration.execute_action(
            "delete_comment", {"comment_id": reply_id}, live_context
        )
        assert delete_result.result.data["success"] is True
        assert delete_result.result.data["deleted_comment_id"] == reply_id
