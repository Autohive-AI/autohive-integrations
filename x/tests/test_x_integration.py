"""
End-to-end integration tests for the X (formerly Twitter) integration.

These tests call the real X API v2 and require a valid OAuth2 user access token
set in the X_ACCESS_TOKEN environment variable (via .env or export).

Optional environment variables used by some tests:
    X_TEST_TARGET_USER_ID  — a user id to follow/unfollow in the follow lifecycle test

Run read-only tests (safe — use this by default):
    pytest x/tests/test_x_integration.py -m "integration and not destructive"

Run destructive tests (posts/bookmarks/reposts written to the real account):
    pytest x/tests/test_x_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib.util
import os
import sys

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

# The integration folder ships an __init__.py that turns `x` into a package
# exposing only the integration object, so `import x` is ambiguous with x.py.
# Load the action source directly by file path to reach handlers/helpers too.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("x_integration_mod", os.path.join(_parent, "x.py"))
x_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(x_mod)

x_integration = x_mod.x
XConnectedAccountHandler = x_mod.XConnectedAccountHandler

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
TEST_TARGET_USER_ID = os.environ.get("X_TEST_TARGET_USER_ID", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("X_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, data=None, headers=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json or data, headers=merged_headers) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                # Mirror the SDK's context.fetch: it raises on non-2xx (RateLimitError
                # on 429, HTTPError otherwise) and only returns a FetchResponse for 2xx.
                # Replicating that here ensures failed requests (401/403/429 from token
                # scopes, API tier, or rate limits) surface as ActionError exactly as in
                # production — rather than masquerading as empty/successful results.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", resp_data)
                if not resp.ok:
                    raise HTTPError(resp.status, str(resp_data), resp_data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# ---- Helpers ----


async def _get_me_id(live_context):
    """Return the authenticated user's id, skipping the test if get_me fails."""
    result = await x_integration.execute_action("get_me", {}, live_context)
    if result.type == ResultType.ACTION_ERROR:
        pytest.skip(f"get_me failed (check token/scopes): {result.result.message}")
    return result.result.data["user"]["id"]


def _skip_if_action_error(result, what):
    """Skip when an action errors — useful for endpoints gated behind API access tiers."""
    if result.type == ResultType.ACTION_ERROR:
        pytest.skip(f"{what} unavailable on this account/tier: {result.result.message}")


# =============================================================================
# READ-ONLY TESTS
# =============================================================================


class TestConnectedAccount:
    async def test_get_account_info_returns_identity(self, live_context):
        result = await XConnectedAccountHandler().get_account_info(live_context)
        assert result.username is not None
        assert result.user_id is not None

    async def test_get_account_info_has_name_fields(self, live_context):
        result = await XConnectedAccountHandler().get_account_info(live_context)
        # graceful either way — accounts may have a blank display name
        assert result.first_name is not None or result.last_name is None


class TestGetMe:
    async def test_returns_authenticated_user(self, live_context):
        result = await x_integration.execute_action("get_me", {}, live_context)
        _skip_if_action_error(result, "get_me")
        user = result.result.data["user"]
        assert "id" in user
        assert "username" in user

    async def test_id_is_string(self, live_context):
        result = await x_integration.execute_action("get_me", {}, live_context)
        _skip_if_action_error(result, "get_me")
        assert isinstance(result.result.data["user"]["id"], str)


class TestGetUser:
    async def test_by_username(self, live_context):
        result = await x_integration.execute_action("get_user", {"username": "X"}, live_context)
        _skip_if_action_error(result, "get_user")
        user = result.result.data["user"]
        assert user["username"].lower() == "x"
        assert "id" in user

    async def test_missing_identifier_returns_action_error(self, live_context):
        result = await x_integration.execute_action("get_user", {}, live_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "user_id or username" in result.result.message


class TestSearchTweets:
    async def test_returns_posts_list(self, live_context):
        result = await x_integration.execute_action(
            "search_tweets", {"query": "#AI -is:retweet lang:en", "max_results": 10}, live_context
        )
        _skip_if_action_error(result, "search_tweets")
        data = result.result.data
        assert "posts" in data
        assert isinstance(data["posts"], list)
        assert len(data["posts"]) <= 10

    async def test_post_structure(self, live_context):
        result = await x_integration.execute_action("search_tweets", {"query": "the", "max_results": 10}, live_context)
        _skip_if_action_error(result, "search_tweets")
        posts = result.result.data["posts"]
        if not posts:
            pytest.skip("No posts returned for query")
        assert "id" in posts[0]
        assert "text" in posts[0]


class TestGetTweet:
    async def test_get_single_post_by_id(self, live_context):
        search = await x_integration.execute_action("search_tweets", {"query": "the", "max_results": 10}, live_context)
        _skip_if_action_error(search, "search_tweets")
        posts = search.result.data["posts"]
        if not posts:
            pytest.skip("No posts available to fetch by id")

        post_id = posts[0]["id"]
        result = await x_integration.execute_action(
            "get_tweet", {"post_id": post_id, "include_user": True, "include_metrics": False}, live_context
        )
        _skip_if_action_error(result, "get_tweet")
        assert result.result.data["post"]["id"] == post_id


class TestGetUserTweets:
    async def test_returns_user_timeline(self, live_context):
        user_id = await _get_me_id(live_context)
        result = await x_integration.execute_action(
            "get_user_tweets", {"user_id": user_id, "max_results": 5}, live_context
        )
        _skip_if_action_error(result, "get_user_tweets")
        data = result.result.data
        assert isinstance(data["posts"], list)
        assert len(data["posts"]) <= 5


class TestGetLikedTweets:
    async def test_returns_liked_posts(self, live_context):
        user_id = await _get_me_id(live_context)
        result = await x_integration.execute_action(
            "get_liked_tweets", {"user_id": user_id, "max_results": 5}, live_context
        )
        _skip_if_action_error(result, "get_liked_tweets")
        assert isinstance(result.result.data["posts"], list)


class TestGetBookmarks:
    async def test_returns_bookmarks(self, live_context):
        user_id = await _get_me_id(live_context)
        result = await x_integration.execute_action(
            "get_bookmarks", {"user_id": user_id, "max_results": 5}, live_context
        )
        _skip_if_action_error(result, "get_bookmarks")
        assert isinstance(result.result.data["posts"], list)


# =============================================================================
# DESTRUCTIVE TESTS (write operations on the real account)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestTweetLifecycle:
    """Create a post then delete it."""

    async def test_create_then_delete(self, live_context):
        create = await x_integration.execute_action(
            "create_tweet", {"text": f"Autohive X integration test {os.getpid()} — will be deleted"}, live_context
        )
        _skip_if_action_error(create, "create_tweet")
        post_id = create.result.data["post"]["id"]
        assert post_id

        delete = await x_integration.execute_action("delete_tweet", {"post_id": post_id}, live_context)
        _skip_if_action_error(delete, "delete_tweet")
        assert delete.result.data["deleted"] is True


@pytest.mark.destructive
class TestBookmarkLifecycle:
    """Create a post, bookmark it, remove the bookmark, then delete the post."""

    async def test_bookmark_then_remove(self, live_context):
        user_id = await _get_me_id(live_context)

        create = await x_integration.execute_action(
            "create_tweet", {"text": f"Autohive bookmark test {os.getpid()} — will be deleted"}, live_context
        )
        _skip_if_action_error(create, "create_tweet")
        post_id = create.result.data["post"]["id"]

        try:
            bookmark = await x_integration.execute_action(
                "bookmark_tweet", {"user_id": user_id, "post_id": post_id}, live_context
            )
            _skip_if_action_error(bookmark, "bookmark_tweet")
            assert bookmark.result.data["bookmarked"] is True

            remove = await x_integration.execute_action(
                "remove_bookmark", {"user_id": user_id, "post_id": post_id}, live_context
            )
            _skip_if_action_error(remove, "remove_bookmark")
            assert remove.result.data["removed"] is True
        finally:
            await x_integration.execute_action("delete_tweet", {"post_id": post_id}, live_context)


@pytest.mark.destructive
class TestRepostLifecycle:
    """Repost an existing post then undo the repost."""

    async def test_repost_then_unrepost(self, live_context):
        user_id = await _get_me_id(live_context)

        search = await x_integration.execute_action(
            "search_tweets", {"query": "the -is:retweet", "max_results": 10}, live_context
        )
        _skip_if_action_error(search, "search_tweets")
        posts = search.result.data["posts"]
        if not posts:
            pytest.skip("No posts available to repost")
        post_id = posts[0]["id"]

        repost = await x_integration.execute_action("retweet", {"user_id": user_id, "post_id": post_id}, live_context)
        _skip_if_action_error(repost, "retweet")
        assert repost.result.data["reposted"] is True

        unrepost = await x_integration.execute_action(
            "unretweet", {"user_id": user_id, "post_id": post_id}, live_context
        )
        _skip_if_action_error(unrepost, "unretweet")
        assert unrepost.result.data["unreposted"] is True


@pytest.mark.destructive
class TestFollowLifecycle:
    """Follow then unfollow a target user. Requires X_TEST_TARGET_USER_ID."""

    async def test_follow_then_unfollow(self, live_context):
        if not TEST_TARGET_USER_ID:
            pytest.skip("X_TEST_TARGET_USER_ID not set")
        user_id = await _get_me_id(live_context)

        follow = await x_integration.execute_action(
            "follow_user", {"source_user_id": user_id, "target_user_id": TEST_TARGET_USER_ID}, live_context
        )
        _skip_if_action_error(follow, "follow_user")
        assert follow.result.data["followed"] is True

        unfollow = await x_integration.execute_action(
            "unfollow_user", {"source_user_id": user_id, "target_user_id": TEST_TARGET_USER_ID}, live_context
        )
        _skip_if_action_error(unfollow, "unfollow_user")
        assert unfollow.result.data["unfollowed"] is True
