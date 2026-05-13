"""
Unit tests for the Instagram integration using mocked fetch.
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import instagram as instagram_mod  # noqa: E402
from instagram import InstagramConnectedAccountHandler  # noqa: E402
from helpers import get_instagram_account_id, wait_for_media_container  # noqa: E402

instagram_integration = instagram_mod.instagram

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


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


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


@pytest.mark.asyncio
async def test_connected_account_full_name():
    ctx = make_ctx(
        {
            "id": "17841400000000000",
            "username": "mybusiness",
            "name": "Jane Doe",
            "profile_picture_url": "https://example.com/pic.jpg",
        }
    )
    handler = InstagramConnectedAccountHandler()
    result = await handler.get_account_info(ctx)
    assert result.username == "mybusiness"
    assert result.first_name == "Jane"
    assert result.last_name == "Doe"
    assert result.avatar_url == "https://example.com/pic.jpg"
    assert result.user_id == "17841400000000000"


@pytest.mark.asyncio
async def test_connected_account_single_name():
    ctx = make_ctx(
        {"id": "123", "username": "solo", "name": "Cher", "profile_picture_url": None}
    )
    handler = InstagramConnectedAccountHandler()
    result = await handler.get_account_info(ctx)
    assert result.first_name == "Cher"
    assert result.last_name is None


@pytest.mark.asyncio
async def test_connected_account_no_name():
    ctx = make_ctx(
        {"id": "123", "username": "noname", "name": "", "profile_picture_url": None}
    )
    handler = InstagramConnectedAccountHandler()
    result = await handler.get_account_info(ctx)
    assert result.first_name is None
    assert result.last_name is None


@pytest.mark.asyncio
async def test_connected_account_fetches_correct_fields():
    ctx = make_ctx({"id": "123", "username": "u", "name": "U"})
    handler = InstagramConnectedAccountHandler()
    await handler.get_account_info(ctx)
    call_kwargs = ctx.fetch.call_args
    params = call_kwargs.kwargs.get("params", {})
    assert "username" in params["fields"]
    assert "name" in params["fields"]
    assert "profile_picture_url" in params["fields"]


# =============================================================================
# HELPERS — get_instagram_account_id
# =============================================================================


@pytest.mark.asyncio
async def test_get_account_id_success():
    ctx = make_ctx({"id": "17841400000000000", "username": "testuser"})
    account_id = await get_instagram_account_id(ctx)
    assert account_id == "17841400000000000"


@pytest.mark.asyncio
async def test_get_account_id_missing_raises():
    ctx = make_ctx({"username": "testuser"})  # no "id"
    with pytest.raises(Exception, match="Failed to retrieve Instagram account ID"):
        await get_instagram_account_id(ctx)


# =============================================================================
# HELPERS — wait_for_media_container
# =============================================================================


@pytest.mark.asyncio
async def test_wait_for_container_finished():
    ctx = make_ctx({"status_code": "FINISHED"})
    result = await wait_for_media_container(
        ctx, "container_123", max_attempts=3, delay=0
    )
    assert result["status_code"] == "FINISHED"


@pytest.mark.asyncio
async def test_wait_for_container_error_raises():
    ctx = make_ctx({"status_code": "ERROR", "status": "Processing failed"})
    with pytest.raises(Exception, match="Media container processing failed"):
        await wait_for_media_container(ctx, "container_123", max_attempts=3, delay=0)


@pytest.mark.asyncio
async def test_wait_for_container_expired_raises():
    ctx = make_ctx({"status_code": "EXPIRED"})
    with pytest.raises(Exception, match="expired"):
        await wait_for_media_container(ctx, "container_123", max_attempts=3, delay=0)


@pytest.mark.asyncio
async def test_wait_for_container_failed_raises():
    ctx = make_ctx({"status_code": "FAILED"})
    with pytest.raises(Exception, match="failed"):
        await wait_for_media_container(ctx, "container_123", max_attempts=3, delay=0)


@pytest.mark.asyncio
async def test_wait_for_container_timeout_raises():
    ctx = make_ctx({"status_code": "IN_PROGRESS"})  # never finishes
    with pytest.raises(Exception, match="timed out"):
        await wait_for_media_container(ctx, "container_123", max_attempts=2, delay=0)


@pytest.mark.asyncio
async def test_wait_for_container_polls_until_ready():
    ctx = make_ctx_multi(
        [
            {"status_code": "IN_PROGRESS"},
            {"status_code": "IN_PROGRESS"},
            {"status_code": "FINISHED"},
        ]
    )
    result = await wait_for_media_container(
        ctx, "container_123", max_attempts=5, delay=0
    )
    assert result["status_code"] == "FINISHED"
    assert ctx.fetch.call_count == 3


# =============================================================================
# GET ACCOUNT
# =============================================================================


@pytest.mark.asyncio
async def test_get_account_success():
    ctx = make_ctx(
        {
            "id": "17841400000000000",
            "username": "mybusiness",
            "name": "My Business",
            "biography": "We sell products",
            "followers_count": 10000,
            "follows_count": 500,
            "media_count": 150,
            "profile_picture_url": "https://example.com/pic.jpg",
            "website": "https://mybusiness.com",
        }
    )
    result = await instagram_integration.execute_action("get_account", {}, ctx)
    data = result.result.data
    assert data["id"] == "17841400000000000"
    assert data["username"] == "mybusiness"
    assert data["followers_count"] == 10000
    assert data["following_count"] == 500  # mapped from follows_count
    assert data["media_count"] == 150
    assert data["biography"] == "We sell products"
    assert data["website"] == "https://mybusiness.com"
    ctx.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_account_missing_fields_default_to_empty():
    ctx = make_ctx({"id": "123", "username": "sparse"})
    result = await instagram_integration.execute_action("get_account", {}, ctx)
    data = result.result.data
    assert data["biography"] == ""
    assert data["followers_count"] == 0
    assert data["website"] == ""


@pytest.mark.asyncio
async def test_get_account_fetches_me_endpoint():
    ctx = make_ctx({"id": "123", "username": "u"})
    await instagram_integration.execute_action("get_account", {}, ctx)
    url = (
        ctx.fetch.call_args.args[0]
        if ctx.fetch.call_args.args
        else ctx.fetch.call_args.kwargs["url"]
    )
    assert "/me" in url


# =============================================================================
# GET POSTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_posts_list():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000", "username": "testbusiness"},
            {
                "data": [
                    {
                        "id": "post1",
                        "media_type": "IMAGE",
                        "caption": "Hello",
                        "like_count": 10,
                        "comments_count": 2,
                    },
                    {
                        "id": "post2",
                        "media_type": "VIDEO",
                        "caption": "World",
                        "like_count": 20,
                        "comments_count": 5,
                    },
                ]
            },
        ]
    )
    result = await instagram_integration.execute_action("get_posts", {}, ctx)
    data = result.result.data
    assert len(data["media"]) == 2
    assert data["media"][0]["id"] == "post1"
    assert data["media"][1]["like_count"] == 20


@pytest.mark.asyncio
async def test_get_posts_empty():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000", "username": "testbusiness"},
            {"data": []},
        ]
    )
    result = await instagram_integration.execute_action("get_posts", {}, ctx)
    assert result.result.data["media"] == []


@pytest.mark.asyncio
async def test_get_posts_single_by_id():
    ctx = make_ctx(
        {
            "id": "post1",
            "media_type": "IMAGE",
            "caption": "Solo",
            "like_count": 5,
            "comments_count": 1,
        }
    )
    result = await instagram_integration.execute_action(
        "get_posts", {"media_id": "post1"}, ctx
    )
    data = result.result.data
    assert len(data["media"]) == 1
    assert data["media"][0]["id"] == "post1"


@pytest.mark.asyncio
async def test_get_posts_pagination_next_cursor():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {
                "data": [{"id": "post1", "media_type": "IMAGE"}],
                "paging": {
                    "cursors": {"after": "cursor_abc"},
                    "next": "https://graph.instagram.com/next",
                },
            },
        ]
    )
    result = await instagram_integration.execute_action("get_posts", {}, ctx)
    assert result.result.data["next_cursor"] == "cursor_abc"


@pytest.mark.asyncio
async def test_get_posts_no_next_cursor_when_last_page():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {
                "data": [{"id": "post1", "media_type": "IMAGE"}],
                "paging": {"cursors": {"after": "cursor_abc"}},  # no "next" key
            },
        ]
    )
    result = await instagram_integration.execute_action("get_posts", {}, ctx)
    assert result.result.data["next_cursor"] is None


@pytest.mark.asyncio
async def test_get_posts_limit_capped_at_100():
    ctx = make_ctx_multi([{"id": "17841400000000000"}, {"data": []}])
    await instagram_integration.execute_action("get_posts", {"limit": 500}, ctx)
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert params["limit"] == 100


@pytest.mark.asyncio
async def test_get_posts_after_cursor_forwarded():
    ctx = make_ctx_multi([{"id": "17841400000000000"}, {"data": []}])
    await instagram_integration.execute_action(
        "get_posts", {"after_cursor": "cursor_xyz"}, ctx
    )
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert params["after"] == "cursor_xyz"


# =============================================================================
# CREATE POST
# =============================================================================


@pytest.mark.asyncio
async def test_create_post_image():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "container_123"},
            {"status_code": "FINISHED"},
            {"id": "published_456"},
            {"permalink": "https://www.instagram.com/p/ABC/"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_post",
        {
            "media_type": "IMAGE",
            "media_url": "https://example.com/img.jpg",
            "caption": "Test",
        },
        ctx,
    )
    data = result.result.data
    assert data["media_id"] == "published_456"
    assert "instagram.com" in data["permalink"]


@pytest.mark.asyncio
async def test_create_post_image_with_alt_text():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "container_123"},
            {"status_code": "FINISHED"},
            {"id": "published_456"},
            {"permalink": "https://www.instagram.com/p/ABC/"},
        ]
    )
    await instagram_integration.execute_action(
        "create_post",
        {
            "media_type": "IMAGE",
            "media_url": "https://example.com/img.jpg",
            "alt_text": "A sunset",
        },
        ctx,
    )
    create_call_data = ctx.fetch.call_args_list[1].kwargs.get("data", {})
    assert create_call_data.get("alt_text") == "A sunset"


@pytest.mark.asyncio
async def test_create_post_video():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "container_vid"},
            {"status_code": "FINISHED"},
            {"id": "published_vid"},
            {"permalink": "https://www.instagram.com/p/VID/"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_post",
        {
            "media_type": "VIDEO",
            "media_url": "https://example.com/video.mp4",
            "caption": "Vid",
        },
        ctx,
    )
    assert result.result.data["media_id"] == "published_vid"


@pytest.mark.asyncio
async def test_create_post_video_missing_url_raises():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])
    with pytest.raises(Exception, match="media_url is required for VIDEO"):
        await instagram_integration.execute_action(
            "create_post", {"media_type": "VIDEO"}, ctx
        )


@pytest.mark.asyncio
async def test_create_post_reels():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "container_reel"},
            {"status_code": "FINISHED"},
            {"id": "reel_789"},
            {"permalink": "https://www.instagram.com/reel/XYZ/"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_post",
        {
            "media_type": "REELS",
            "media_url": "https://example.com/video.mp4",
            "caption": "Reel!",
        },
        ctx,
    )
    assert result.result.data["media_id"] == "reel_789"


@pytest.mark.asyncio
async def test_create_post_reels_missing_url_raises():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])
    with pytest.raises(Exception, match="media_url is required for REELS"):
        await instagram_integration.execute_action(
            "create_post", {"media_type": "REELS"}, ctx
        )


@pytest.mark.asyncio
async def test_create_post_image_missing_url_raises():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])
    with pytest.raises(Exception, match="media_url is required"):
        await instagram_integration.execute_action(
            "create_post", {"media_type": "IMAGE"}, ctx
        )


@pytest.mark.asyncio
async def test_create_post_carousel_success():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},  # account id
            {"id": "child_c1"},  # child container 1
            {"id": "child_c2"},  # child container 2
            {"status_code": "FINISHED"},  # poll child 1
            {"status_code": "FINISHED"},  # poll child 2
            {"id": "carousel_container"},  # carousel container
            {"status_code": "FINISHED"},  # poll carousel
            {"id": "carousel_published"},  # publish
            {"permalink": "https://www.instagram.com/p/CAR/"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_post",
        {
            "media_type": "CAROUSEL",
            "caption": "Multi",
            "children": [
                "https://example.com/img1.jpg",
                "https://example.com/img2.jpg",
            ],
        },
        ctx,
    )
    assert result.result.data["media_id"] == "carousel_published"


@pytest.mark.asyncio
async def test_create_post_carousel_too_few_raises():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])
    with pytest.raises(Exception, match="at least 2"):
        await instagram_integration.execute_action(
            "create_post",
            {"media_type": "CAROUSEL", "children": ["https://example.com/img.jpg"]},
            ctx,
        )


@pytest.mark.asyncio
async def test_create_post_carousel_too_many_raises():
    ctx = make_ctx_multi([{"id": "17841400000000000"}])
    with pytest.raises(Exception, match="maximum 10"):
        await instagram_integration.execute_action(
            "create_post",
            {
                "media_type": "CAROUSEL",
                "children": [f"https://example.com/img{i}.jpg" for i in range(11)],
            },
            ctx,
        )


# =============================================================================
# CREATE STORY
# =============================================================================


@pytest.mark.asyncio
async def test_create_story_image():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "story_container"},
            {"status_code": "FINISHED"},
            {"id": "story_999"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_story",
        {"media_type": "IMAGE", "media_url": "https://example.com/story.jpg"},
        ctx,
    )
    assert result.result.data["media_id"] == "story_999"


@pytest.mark.asyncio
async def test_create_story_video():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "story_vid_container"},
            {"status_code": "FINISHED"},
            {"id": "story_vid_published"},
        ]
    )
    result = await instagram_integration.execute_action(
        "create_story",
        {"media_type": "VIDEO", "media_url": "https://example.com/story.mp4"},
        ctx,
    )
    assert result.result.data["media_id"] == "story_vid_published"
    create_call_data = ctx.fetch.call_args_list[1].kwargs.get("data", {})
    assert "video_url" in create_call_data


@pytest.mark.asyncio
async def test_create_story_image_uses_image_url_field():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {"id": "s_container"},
            {"status_code": "FINISHED"},
            {"id": "s_published"},
        ]
    )
    await instagram_integration.execute_action(
        "create_story",
        {"media_type": "IMAGE", "media_url": "https://example.com/s.jpg"},
        ctx,
    )
    create_call_data = ctx.fetch.call_args_list[1].kwargs.get("data", {})
    assert create_call_data.get("image_url") == "https://example.com/s.jpg"
    assert create_call_data.get("media_type") == "STORIES"


# =============================================================================
# GET COMMENTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_comments_success():
    ctx = make_ctx(
        {
            "data": [
                {
                    "id": "c1",
                    "text": "Great post!",
                    "username": "fan1",
                    "timestamp": "2024-01-01T12:00:00+0000",
                    "like_count": 3,
                    "replies": {"data": []},
                },
                {
                    "id": "c2",
                    "text": "Love it!",
                    "username": "fan2",
                    "timestamp": "2024-01-01T13:00:00+0000",
                    "like_count": 1,
                    "replies": {
                        "data": [
                            {
                                "id": "r1",
                                "text": "Thanks!",
                                "username": "me",
                                "timestamp": "2024-01-01T14:00:00+0000",
                            }
                        ]
                    },
                },
            ]
        }
    )
    result = await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1"}, ctx
    )
    data = result.result.data
    assert len(data["comments"]) == 2
    assert data["comments"][0]["text"] == "Great post!"
    assert data["total_count"] == 2
    assert len(data["comments"][1]["replies"]) == 1
    assert data["comments"][1]["replies"][0]["text"] == "Thanks!"


@pytest.mark.asyncio
async def test_get_comments_empty():
    ctx = make_ctx({"data": []})
    result = await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1"}, ctx
    )
    assert result.result.data["comments"] == []
    assert result.result.data["total_count"] == 0


@pytest.mark.asyncio
async def test_get_comments_username_from_from_field():
    ctx = make_ctx(
        {
            "data": [
                {
                    "id": "c1",
                    "text": "Hi",
                    "from": {"id": "u1", "username": "fromuser"},
                    "like_count": 0,
                    "replies": {"data": []},
                }
            ]
        }
    )
    result = await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1"}, ctx
    )
    assert result.result.data["comments"][0]["username"] == "fromuser"
    assert result.result.data["comments"][0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_get_comments_pagination_cursor():
    ctx = make_ctx(
        {
            "data": [
                {"id": "c1", "text": "Hi", "like_count": 0, "replies": {"data": []}}
            ],
            "paging": {
                "cursors": {"after": "next_cursor_123"},
                "next": "https://graph.instagram.com/next",
            },
        }
    )
    result = await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1"}, ctx
    )
    assert result.result.data["next_cursor"] == "next_cursor_123"


@pytest.mark.asyncio
async def test_get_comments_limit_forwarded():
    ctx = make_ctx({"data": []})
    await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1", "limit": 10}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["limit"] == 10


@pytest.mark.asyncio
async def test_get_comments_limit_capped_at_100():
    ctx = make_ctx({"data": []})
    await instagram_integration.execute_action(
        "get_comments", {"media_id": "post1", "limit": 999}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["limit"] == 100


# =============================================================================
# MANAGE COMMENT
# =============================================================================


@pytest.mark.asyncio
async def test_manage_comment_reply():
    ctx = make_ctx({"id": "reply_new_123"})
    result = await instagram_integration.execute_action(
        "manage_comment",
        {"comment_id": "c1", "action": "reply", "message": "Thank you!"},
        ctx,
    )
    data = result.result.data
    assert data["success"] is True
    assert data["action_taken"] == "reply"
    assert data["reply_id"] == "reply_new_123"


@pytest.mark.asyncio
async def test_manage_comment_reply_posts_to_replies_endpoint():
    ctx = make_ctx({"id": "r1"})
    await instagram_integration.execute_action(
        "manage_comment",
        {"comment_id": "c1", "action": "reply", "message": "Nice!"},
        ctx,
    )
    url = (
        ctx.fetch.call_args.args[0]
        if ctx.fetch.call_args.args
        else ctx.fetch.call_args.kwargs.get("url", "")
    )
    assert "/replies" in url
    assert ctx.fetch.call_args.kwargs.get("data", {}).get("message") == "Nice!"


@pytest.mark.asyncio
async def test_manage_comment_hide():
    ctx = make_ctx({"success": True})
    result = await instagram_integration.execute_action(
        "manage_comment", {"comment_id": "c1", "action": "hide"}, ctx
    )
    assert result.result.data["is_hidden"] is True
    assert ctx.fetch.call_args.kwargs.get("data", {}).get("hide") == "true"


@pytest.mark.asyncio
async def test_manage_comment_unhide():
    ctx = make_ctx({"success": True})
    result = await instagram_integration.execute_action(
        "manage_comment", {"comment_id": "c1", "action": "unhide"}, ctx
    )
    assert result.result.data["is_hidden"] is False
    assert ctx.fetch.call_args.kwargs.get("data", {}).get("hide") == "false"


@pytest.mark.asyncio
async def test_manage_comment_reply_missing_message_raises():
    ctx = make_ctx({})
    with pytest.raises(Exception, match="message is required"):
        await instagram_integration.execute_action(
            "manage_comment", {"comment_id": "c1", "action": "reply"}, ctx
        )


@pytest.mark.asyncio
async def test_manage_comment_invalid_action_returns_error():
    ctx = make_ctx({})
    result = await instagram_integration.execute_action(
        "manage_comment", {"comment_id": "c1", "action": "nuke"}, ctx
    )
    assert result.result is not None
    result_str = str(result.result)
    assert "Unknown action" in result_str or "nuke" in result_str


# =============================================================================
# DELETE COMMENT
# =============================================================================


@pytest.mark.asyncio
async def test_delete_comment_success():
    ctx = make_ctx({})
    result = await instagram_integration.execute_action(
        "delete_comment", {"comment_id": "c1"}, ctx
    )
    data = result.result.data
    assert data["success"] is True
    assert data["deleted_comment_id"] == "c1"


@pytest.mark.asyncio
async def test_delete_comment_uses_delete_method():
    ctx = make_ctx({})
    await instagram_integration.execute_action(
        "delete_comment", {"comment_id": "c99"}, ctx
    )
    assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"
    url = (
        ctx.fetch.call_args.args[0]
        if ctx.fetch.call_args.args
        else ctx.fetch.call_args.kwargs.get("url", "")
    )
    assert "c99" in url


# =============================================================================
# GET INSIGHTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_insights_account():
    ctx = make_ctx_multi(
        [
            {"id": "17841400000000000"},
            {
                "data": [
                    {"name": "reach", "total_value": {"value": 50000}},
                    {"name": "profile_views", "total_value": {"value": 1500}},
                ]
            },
        ]
    )
    result = await instagram_integration.execute_action(
        "get_insights", {"target_type": "account"}, ctx
    )
    data = result.result.data
    assert data["target_type"] == "account"
    assert data["target_id"] == "account"
    assert data["metrics"]["reach"] == 50000
    assert data["metrics"]["profile_views"] == 1500


@pytest.mark.asyncio
async def test_get_insights_account_default_period():
    ctx = make_ctx_multi([{"id": "17841400000000000"}, {"data": []}])
    result = await instagram_integration.execute_action(
        "get_insights", {"target_type": "account"}, ctx
    )
    assert result.result.data["period"] == "days_28"
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert params["period"] == "days_28"


@pytest.mark.asyncio
async def test_get_insights_account_custom_period():
    ctx = make_ctx_multi([{"id": "17841400000000000"}, {"data": []}])
    await instagram_integration.execute_action(
        "get_insights", {"target_type": "account", "period": "week"}, ctx
    )
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert params["period"] == "week"


@pytest.mark.asyncio
async def test_get_insights_account_custom_metrics():
    ctx = make_ctx_multi([{"id": "17841400000000000"}, {"data": []}])
    await instagram_integration.execute_action(
        "get_insights", {"target_type": "account", "metrics": ["reach", "likes"]}, ctx
    )
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert params["metric"] == "reach,likes"


@pytest.mark.asyncio
async def test_get_insights_media_feed():
    ctx = make_ctx_multi(
        [
            {"media_product_type": "FEED"},
            {
                "data": [
                    {"name": "reach", "values": [{"value": 5000}]},
                    {"name": "likes", "values": [{"value": 200}]},
                ]
            },
        ]
    )
    result = await instagram_integration.execute_action(
        "get_insights", {"target_type": "media", "target_id": "post1"}, ctx
    )
    data = result.result.data
    assert data["target_type"] == "media"
    assert data["target_id"] == "post1"
    assert data["period"] == "lifetime"
    assert data["metrics"]["reach"] == 5000
    assert data["metrics"]["likes"] == 200


@pytest.mark.asyncio
async def test_get_insights_media_reels_uses_reels_metrics():
    ctx = make_ctx_multi(
        [
            {"media_product_type": "REELS"},
            {
                "data": [
                    {"name": "ig_reels_avg_watch_time", "total_value": {"value": 12}}
                ]
            },
        ]
    )
    await instagram_integration.execute_action(
        "get_insights", {"target_type": "media", "target_id": "reel1"}, ctx
    )
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert "ig_reels_avg_watch_time" in params["metric"]


@pytest.mark.asyncio
async def test_get_insights_media_story_uses_story_metrics():
    ctx = make_ctx_multi(
        [
            {"media_product_type": "STORY"},
            {"data": [{"name": "navigation", "total_value": {"value": 5}}]},
        ]
    )
    await instagram_integration.execute_action(
        "get_insights", {"target_type": "media", "target_id": "story1"}, ctx
    )
    params = ctx.fetch.call_args_list[1].kwargs.get("params", {})
    assert "navigation" in params["metric"]


@pytest.mark.asyncio
async def test_get_insights_media_missing_target_id_raises():
    ctx = make_ctx({})
    with pytest.raises(Exception, match="target_id is required"):
        await instagram_integration.execute_action(
            "get_insights", {"target_type": "media"}, ctx
        )
