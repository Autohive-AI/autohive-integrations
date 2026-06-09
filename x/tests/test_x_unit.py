"""
Unit tests for the X (formerly Twitter) integration using mocked fetch.

All tests mock ``context.fetch`` to return ``FetchResponse`` objects (SDK 2.0.0)
and never touch the network. Error paths return ``ActionError`` and surface as
``ResultType.ACTION_ERROR``.
"""

import base64
import importlib.util
import os
import sys

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

# The integration folder ships an __init__.py that turns `x` into a package
# exposing only the integration object, so `import x` is ambiguous with x.py.
# Load the action source directly by file path to get the handlers/helpers too.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("x_integration_mod", os.path.join(_parent, "x.py"))
x_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(x_mod)

x_integration = x_mod.x
XConnectedAccountHandler = x_mod.XConnectedAccountHandler
_upload_media = x_mod._upload_media

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {}
    return ctx


def make_ctx_multi(responses: list):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {}
    return ctx


def make_ctx_error(exc: Exception):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc)
    ctx.auth = {}
    return ctx


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("utf-8")


# Sample media payloads
IMAGE_FILE = {"content": b64(b"fake-image-bytes"), "name": "pic.png", "contentType": "image/png"}
VIDEO_FILE = {"content": b64(b"fake-video-bytes"), "name": "clip.mp4", "contentType": "video/mp4"}


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


class TestConnectedAccount:
    @pytest.mark.asyncio
    async def test_full_name_split(self):
        ctx = make_ctx(
            {
                "data": {
                    "id": "111",
                    "username": "jack",
                    "name": "Jack Dorsey",
                    "profile_image_url": "https://img.example/jack.jpg",
                }
            }
        )
        result = await XConnectedAccountHandler().get_account_info(ctx)
        assert result.username == "jack"
        assert result.first_name == "Jack"
        assert result.last_name == "Dorsey"
        assert result.user_id == "111"
        assert result.avatar_url == "https://img.example/jack.jpg"

    @pytest.mark.asyncio
    async def test_single_name(self):
        ctx = make_ctx({"data": {"id": "1", "username": "cher", "name": "Cher"}})
        result = await XConnectedAccountHandler().get_account_info(ctx)
        assert result.first_name == "Cher"
        assert result.last_name is None

    @pytest.mark.asyncio
    async def test_no_name(self):
        ctx = make_ctx({"data": {"id": "1", "username": "noname", "name": ""}})
        result = await XConnectedAccountHandler().get_account_info(ctx)
        assert result.first_name is None
        assert result.last_name is None

    @pytest.mark.asyncio
    async def test_requests_expected_fields(self):
        ctx = make_ctx({"data": {"id": "1", "username": "u", "name": "U"}})
        await XConnectedAccountHandler().get_account_info(ctx)
        params = ctx.fetch.call_args.kwargs.get("params", {})
        assert "username" in params["user.fields"]
        assert "profile_image_url" in params["user.fields"]


# =============================================================================
# MEDIA UPLOAD HELPER (_upload_media)
# =============================================================================


class TestUploadMedia:
    @pytest.mark.asyncio
    async def test_image_happy_path(self):
        ctx = make_ctx_multi(
            [
                {"data": {"id": "media_1"}},  # initialize
                {},  # append
                {},  # finalize
            ]
        )
        result = await _upload_media(ctx, IMAGE_FILE)
        assert result["media_id"] == "media_1"
        assert result["media_type"] == "image/png"
        assert result["size"] == len(b"fake-image-bytes")
        assert ctx.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_media_id_string_fallback(self):
        ctx = make_ctx_multi([{"media_id_string": "555"}, {}, {}])
        result = await _upload_media(ctx, IMAGE_FILE)
        assert result["media_id"] == "555"

    @pytest.mark.asyncio
    async def test_initialize_error(self):
        ctx = make_ctx_multi([{"errors": [{"message": "bad init"}]}])
        result = await _upload_media(ctx, IMAGE_FILE)
        assert result["error"] == "Initialize failed: bad init"
        assert ctx.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_no_media_id_returned(self):
        ctx = make_ctx_multi([{"data": {}}])
        result = await _upload_media(ctx, IMAGE_FILE)
        assert "No media_id returned" in result["error"]

    @pytest.mark.asyncio
    async def test_append_error(self):
        ctx = make_ctx_multi([{"data": {"id": "m1"}}, {"errors": [{"message": "bad append"}]}])
        result = await _upload_media(ctx, IMAGE_FILE)
        assert result["error"] == "Append chunk 0 failed: bad append"

    @pytest.mark.asyncio
    async def test_finalize_error(self):
        ctx = make_ctx_multi([{"data": {"id": "m1"}}, {}, {"errors": [{"message": "bad final"}]}])
        result = await _upload_media(ctx, IMAGE_FILE)
        assert result["error"] == "Finalize failed: bad final"

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_video_polls_until_succeeded(self, _sleep):
        ctx = make_ctx_multi(
            [
                {"data": {"id": "v1"}},  # initialize
                {},  # append
                {"data": {"processing_info": {"state": "pending", "check_after_secs": 0}}},  # finalize
                {"data": {"processing_info": {"state": "succeeded"}}},  # status poll
            ]
        )
        result = await _upload_media(ctx, VIDEO_FILE)
        assert result["media_id"] == "v1"
        assert ctx.fetch.call_count == 4

    @pytest.mark.asyncio
    async def test_video_processing_failed(self):
        ctx = make_ctx_multi(
            [
                {"data": {"id": "v1"}},
                {},
                {"data": {"processing_info": {"state": "failed", "error": {"message": "encode failed"}}}},
            ]
        )
        result = await _upload_media(ctx, VIDEO_FILE)
        assert result["error"] == "encode failed"


# =============================================================================
# CREATE TWEET
# =============================================================================


class TestCreateTweet:
    @pytest.mark.asyncio
    async def test_text_only(self):
        ctx = make_ctx({"data": {"id": "t1", "text": "hello"}})
        result = await x_integration.execute_action("create_tweet", {"text": "hello"}, ctx)
        assert result.result.data["post"]["id"] == "t1"
        assert "media_id" not in result.result.data

    @pytest.mark.asyncio
    async def test_posts_to_tweets_endpoint(self):
        ctx = make_ctx({"data": {"id": "t1"}})
        await x_integration.execute_action("create_tweet", {"text": "hi"}, ctx)
        call = ctx.fetch.call_args
        assert call.args[0].endswith("/tweets")
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["text"] == "hi"

    @pytest.mark.asyncio
    async def test_poll_and_reply_payload(self):
        ctx = make_ctx({"data": {"id": "t1"}})
        await x_integration.execute_action(
            "create_tweet",
            {
                "text": "vote",
                "reply_to": "r1",
                "quote_tweet_id": "q1",
                "poll_options": ["a", "b"],
                "poll_duration_minutes": 60,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["reply"]["in_reply_to_tweet_id"] == "r1"
        assert payload["quote_tweet_id"] == "q1"
        assert payload["poll"]["options"] == ["a", "b"]
        assert payload["poll"]["duration_minutes"] == 60

    @pytest.mark.asyncio
    async def test_with_media(self):
        ctx = make_ctx_multi(
            [
                {"data": {"id": "media_9"}},  # initialize
                {},  # append
                {},  # finalize
                {"data": {"id": "t1"}},  # create tweet
            ]
        )
        result = await x_integration.execute_action("create_tweet", {"text": "with pic", "file": IMAGE_FILE}, ctx)
        assert result.result.data["media_id"] == "media_9"
        tweet_payload = ctx.fetch.call_args.kwargs["json"]
        assert tweet_payload["media"]["media_ids"] == ["media_9"]

    @pytest.mark.asyncio
    async def test_media_upload_failure_returns_action_error(self):
        ctx = make_ctx_multi([{"errors": [{"message": "bad init"}]}])
        result = await x_integration.execute_action("create_tweet", {"text": "with pic", "file": IMAGE_FILE}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Initialize failed" in result.result.message

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"errors": [{"message": "duplicate content"}]})
        result = await x_integration.execute_action("create_tweet", {"text": "dup"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "duplicate content" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("boom"))
        result = await x_integration.execute_action("create_tweet", {"text": "x"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_text_is_validation_error(self):
        ctx = make_ctx({"data": {"id": "t1"}})
        result = await x_integration.execute_action("create_tweet", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()


# =============================================================================
# GET TWEET
# =============================================================================


class TestGetTweet:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"id": "t1", "text": "hello"}, "includes": {"users": [{"id": "u1"}]}})
        result = await x_integration.execute_action("get_tweet", {"post_id": "t1"}, ctx)
        assert result.result.data["post"]["id"] == "t1"
        assert result.result.data["includes"]["users"][0]["id"] == "u1"

    @pytest.mark.asyncio
    async def test_include_user_adds_expansions(self):
        ctx = make_ctx({"data": {}})
        await x_integration.execute_action(
            "get_tweet", {"post_id": "t1", "include_user": True, "include_metrics": True}, ctx
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["expansions"] == "author_id"
        assert "user.fields" in params
        assert "non_public_metrics" in params["tweet.fields"]

    @pytest.mark.asyncio
    async def test_url_contains_post_id(self):
        ctx = make_ctx({"data": {}})
        await x_integration.execute_action("get_tweet", {"post_id": "999"}, ctx)
        assert ctx.fetch.call_args.args[0].endswith("/tweets/999")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("network down"))
        result = await x_integration.execute_action("get_tweet", {"post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "network down" in result.result.message


# =============================================================================
# DELETE TWEET
# =============================================================================


class TestDeleteTweet:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"deleted": True}})
        result = await x_integration.execute_action("delete_tweet", {"post_id": "t1"}, ctx)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self):
        ctx = make_ctx({"data": {"deleted": True}})
        await x_integration.execute_action("delete_tweet", {"post_id": "abc"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "DELETE"
        assert call.args[0].endswith("/tweets/abc")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("fail"))
        result = await x_integration.execute_action("delete_tweet", {"post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# SEARCH TWEETS
# =============================================================================


class TestSearchTweets:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": [{"id": "t1"}, {"id": "t2"}], "includes": {"users": []}, "meta": {"result_count": 2}})
        result = await x_integration.execute_action("search_tweets", {"query": "#ai"}, ctx)
        data = result.result.data
        assert len(data["posts"]) == 2
        assert data["meta"]["result_count"] == 2

    @pytest.mark.asyncio
    async def test_max_results_clamped_to_100(self):
        ctx = make_ctx({"data": []})
        await x_integration.execute_action("search_tweets", {"query": "x", "max_results": 500}, ctx)
        assert ctx.fetch.call_args.kwargs["params"]["max_results"] == 100

    @pytest.mark.asyncio
    async def test_optional_params_forwarded(self):
        ctx = make_ctx({"data": []})
        await x_integration.execute_action(
            "search_tweets",
            {"query": "x", "start_time": "2024-01-01T00:00:00Z", "next_token": "tok"},  # nosec B105
            ctx,
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["start_time"] == "2024-01-01T00:00:00Z"
        assert params["next_token"] == "tok"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        ctx = make_ctx({"data": []})
        result = await x_integration.execute_action("search_tweets", {"query": "nothing"}, ctx)
        assert result.result.data["posts"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("rate limited"))
        result = await x_integration.execute_action("search_tweets", {"query": "x"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "rate limited" in result.result.message


# =============================================================================
# GET USER TWEETS
# =============================================================================


class TestGetUserTweets:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": [{"id": "t1"}], "meta": {"newest_id": "t1"}})
        result = await x_integration.execute_action("get_user_tweets", {"user_id": "u1"}, ctx)
        assert result.result.data["posts"][0]["id"] == "t1"
        assert result.result.data["meta"]["newest_id"] == "t1"

    @pytest.mark.asyncio
    async def test_default_max_results(self):
        ctx = make_ctx({"data": []})
        await x_integration.execute_action("get_user_tweets", {"user_id": "u1"}, ctx)
        assert ctx.fetch.call_args.kwargs["params"]["max_results"] == 10

    @pytest.mark.asyncio
    async def test_exclude_replies_and_retweets(self):
        ctx = make_ctx({"data": []})
        await x_integration.execute_action(
            "get_user_tweets",
            {"user_id": "u1", "exclude_replies": True, "exclude_retweets": True},
            ctx,
        )
        assert ctx.fetch.call_args.kwargs["params"]["exclude"] == "replies,retweets"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("nope"))
        result = await x_integration.execute_action("get_user_tweets", {"user_id": "u1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET LIKED TWEETS
# =============================================================================


class TestGetLikedTweets:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": [{"id": "t1"}], "includes": {}, "meta": {}})
        result = await x_integration.execute_action("get_liked_tweets", {"user_id": "u1"}, ctx)
        assert result.result.data["posts"][0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_pagination_token_forwarded(self):
        ctx = make_ctx({"data": []})
        inputs = {"user_id": "u1", "pagination_token": "pg"}  # nosec B105
        await x_integration.execute_action("get_liked_tweets", inputs, ctx)
        assert ctx.fetch.call_args.kwargs["params"]["pagination_token"] == "pg"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("get_liked_tweets", {"user_id": "u1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET BOOKMARKS
# =============================================================================


class TestGetBookmarks:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": [{"id": "t1"}], "includes": {}, "meta": {}})
        result = await x_integration.execute_action("get_bookmarks", {"user_id": "u1"}, ctx)
        assert result.result.data["posts"][0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"errors": [{"message": "forbidden"}]})
        result = await x_integration.execute_action("get_bookmarks", {"user_id": "u1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "forbidden" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("get_bookmarks", {"user_id": "u1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# BOOKMARK / REMOVE BOOKMARK
# =============================================================================


class TestBookmarkTweet:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"bookmarked": True}})
        result = await x_integration.execute_action("bookmark_tweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.result.data["bookmarked"] is True

    @pytest.mark.asyncio
    async def test_request_payload(self):
        ctx = make_ctx({"data": {"bookmarked": True}})
        await x_integration.execute_action("bookmark_tweet", {"user_id": "u1", "post_id": "t9"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["tweet_id"] == "t9"

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"errors": [{"message": "limit reached"}]})
        result = await x_integration.execute_action("bookmark_tweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "limit reached" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("bookmark_tweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


class TestRemoveBookmark:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"bookmarked": False}})
        result = await x_integration.execute_action("remove_bookmark", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.result.data["removed"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self):
        ctx = make_ctx({"data": {"bookmarked": False}})
        await x_integration.execute_action("remove_bookmark", {"user_id": "u1", "post_id": "t7"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "DELETE"
        assert call.args[0].endswith("/bookmarks/t7")

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"errors": [{"message": "not found"}]})
        result = await x_integration.execute_action("remove_bookmark", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("remove_bookmark", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# RETWEET / UNRETWEET
# =============================================================================


class TestRetweet:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"retweeted": True}})
        result = await x_integration.execute_action("retweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.result.data["reposted"] is True

    @pytest.mark.asyncio
    async def test_request_payload(self):
        ctx = make_ctx({"data": {"retweeted": True}})
        await x_integration.execute_action("retweet", {"user_id": "u1", "post_id": "t3"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["tweet_id"] == "t3"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("retweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


class TestUnretweet:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"retweeted": False}})
        result = await x_integration.execute_action("unretweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.result.data["unreposted"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self):
        ctx = make_ctx({"data": {"retweeted": False}})
        await x_integration.execute_action("unretweet", {"user_id": "u1", "post_id": "t5"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "DELETE"
        assert call.args[0].endswith("/retweets/t5")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("unretweet", {"user_id": "u1", "post_id": "t1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET USER / GET ME
# =============================================================================


class TestGetUser:
    @pytest.mark.asyncio
    async def test_by_user_id(self):
        ctx = make_ctx({"data": {"id": "u1", "username": "alice"}})
        result = await x_integration.execute_action("get_user", {"user_id": "u1"}, ctx)
        assert result.result.data["user"]["username"] == "alice"
        assert ctx.fetch.call_args.args[0].endswith("/users/u1")

    @pytest.mark.asyncio
    async def test_by_username(self):
        ctx = make_ctx({"data": {"id": "u1", "username": "bob"}})
        await x_integration.execute_action("get_user", {"username": "bob"}, ctx)
        assert ctx.fetch.call_args.args[0].endswith("/users/by/username/bob")

    @pytest.mark.asyncio
    async def test_missing_identifier_returns_action_error(self):
        ctx = make_ctx({"data": {}})
        result = await x_integration.execute_action("get_user", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "user_id or username" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("get_user", {"user_id": "u1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR


class TestGetMe:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"id": "me", "username": "myself"}})
        result = await x_integration.execute_action("get_me", {}, ctx)
        assert result.result.data["user"]["username"] == "myself"
        assert ctx.fetch.call_args.args[0].endswith("/users/me")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action("get_me", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# FOLLOW / UNFOLLOW
# =============================================================================


class TestFollowUser:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"following": True}})
        result = await x_integration.execute_action(
            "follow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx
        )
        assert result.result.data["followed"] is True

    @pytest.mark.asyncio
    async def test_request_payload(self):
        ctx = make_ctx({"data": {"following": True}})
        await x_integration.execute_action("follow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["target_user_id"] == "u2"
        assert call.args[0].endswith("/users/u1/following")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action(
            "follow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx
        )
        assert result.type == ResultType.ACTION_ERROR


class TestUnfollowUser:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        ctx = make_ctx({"data": {"following": False}})
        result = await x_integration.execute_action(
            "unfollow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx
        )
        assert result.result.data["unfollowed"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self):
        ctx = make_ctx({"data": {"following": False}})
        await x_integration.execute_action("unfollow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx)
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "DELETE"
        assert call.args[0].endswith("/users/u1/following/u2")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx_error(Exception("err"))
        result = await x_integration.execute_action(
            "unfollow_user", {"source_user_id": "u1", "target_user_id": "u2"}, ctx
        )
        assert result.type == ResultType.ACTION_ERROR
