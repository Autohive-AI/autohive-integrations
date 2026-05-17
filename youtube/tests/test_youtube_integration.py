"""
End-to-end integration tests for the YouTube integration.

These tests call the real YouTube Data API v3 and require a valid OAuth access
token set in the YOUTUBE_ACCESS_TOKEN environment variable (via .env or export).

Required env vars:
    YOUTUBE_ACCESS_TOKEN          OAuth2 access token with youtube + youtube.force-ssl scopes

Optional env vars (skip the corresponding tests when missing):
    YOUTUBE_TEST_VIDEO_ID         A video ID the authenticated user can read/update
    YOUTUBE_TEST_CHANNEL_ID       A public channel ID to fetch
    YOUTUBE_TEST_PLAYLIST_ID      An existing playlist ID for list_playlist_items
    YOUTUBE_TEST_COMMENT_ID       A comment ID for list_comment_replies
    YOUTUBE_TEST_THUMBNAIL_PATH   Local path to a JPEG/PNG used by upload_thumbnail
    YOUTUBE_TEST_OWNED_VIDEO_ID   A video the user owns (for moderate_comment ownership)

Run read-only tests (safe):
    pytest youtube/tests/test_youtube_integration.py -m "integration and not destructive"

Run destructive tests (creates/updates/deletes on the real account — review first):
    pytest youtube/tests/test_youtube_integration.py -m "integration and destructive"

Never runs in CI — the default pytest filter (-m unit) excludes these, and the
file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse

from youtube import youtube

pytestmark = pytest.mark.integration


ACCESS_TOKEN = os.environ.get("YOUTUBE_ACCESS_TOKEN", "")
TEST_VIDEO_ID = os.environ.get("YOUTUBE_TEST_VIDEO_ID", "")
TEST_CHANNEL_ID = os.environ.get("YOUTUBE_TEST_CHANNEL_ID", "")
TEST_PLAYLIST_ID = os.environ.get("YOUTUBE_TEST_PLAYLIST_ID", "")
TEST_COMMENT_ID = os.environ.get("YOUTUBE_TEST_COMMENT_ID", "")
TEST_THUMBNAIL_PATH = os.environ.get("YOUTUBE_TEST_THUMBNAIL_PATH", "")
TEST_OWNED_VIDEO_ID = os.environ.get("YOUTUBE_TEST_OWNED_VIDEO_ID", "")


def require_video_id():
    if not TEST_VIDEO_ID:
        pytest.skip("YOUTUBE_TEST_VIDEO_ID not set")


def require_channel_id():
    if not TEST_CHANNEL_ID:
        pytest.skip("YOUTUBE_TEST_CHANNEL_ID not set")


def require_playlist_id():
    if not TEST_PLAYLIST_ID:
        pytest.skip("YOUTUBE_TEST_PLAYLIST_ID not set")


def require_comment_id():
    if not TEST_COMMENT_ID:
        pytest.skip("YOUTUBE_TEST_COMMENT_ID not set")


def require_thumbnail_path():
    if not TEST_THUMBNAIL_PATH:
        pytest.skip("YOUTUBE_TEST_THUMBNAIL_PATH not set")
    if not os.path.isfile(TEST_THUMBNAIL_PATH):
        pytest.skip(f"YOUTUBE_TEST_THUMBNAIL_PATH does not point to a real file: {TEST_THUMBNAIL_PATH}")


def require_owned_video_id():
    if not TEST_OWNED_VIDEO_ID:
        pytest.skip("YOUTUBE_TEST_OWNED_VIDEO_ID not set — required for moderate_comment (user must own the channel)")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("YOUTUBE_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, data=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                headers=merged_headers,
                params=params,
                data=data,
            ) as resp:
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# =============================================================================
# SEARCH (read-only)
# =============================================================================


class TestSearch:
    async def test_returns_items(self, live_context):
        result = await youtube.execute_action(
            "search", {"query": "python tutorial", "max_results": 3, "type": "video"}, live_context
        )
        data = result.result.data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) <= 3

    async def test_item_has_expected_fields(self, live_context):
        result = await youtube.execute_action("search", {"query": "music", "max_results": 1}, live_context)
        items = result.result.data["items"]
        if not items:
            pytest.skip("No search results returned")
        item = items[0]
        assert "id" in item
        assert "title" in item
        assert "thumbnail" in item
        assert "channel_title" in item


# =============================================================================
# VIDEO (read-only)
# =============================================================================


class TestGetVideo:
    async def test_returns_video(self, live_context):
        require_video_id()
        result = await youtube.execute_action("get_video", {"video_id": TEST_VIDEO_ID}, live_context)
        data = result.result.data
        assert "video" in data
        assert data["video"]["id"] == TEST_VIDEO_ID
        assert "title" in data["video"]


# =============================================================================
# CHANNEL (read-only)
# =============================================================================


class TestGetChannel:
    async def test_my_channel(self, live_context):
        result = await youtube.execute_action("get_channel", {"mine": True}, live_context)
        data = result.result.data
        assert "channel" in data
        assert isinstance(data["channel"]["id"], str)
        assert len(data["channel"]["id"]) > 0

    async def test_by_channel_id(self, live_context):
        require_channel_id()
        result = await youtube.execute_action("get_channel", {"channel_id": TEST_CHANNEL_ID}, live_context)
        data = result.result.data
        assert data["channel"]["id"] == TEST_CHANNEL_ID


# =============================================================================
# PLAYLISTS (read-only)
# =============================================================================


class TestListPlaylists:
    async def test_my_playlists(self, live_context):
        result = await youtube.execute_action("list_playlists", {"mine": True, "max_results": 5}, live_context)
        data = result.result.data
        assert "playlists" in data
        assert isinstance(data["playlists"], list)
        assert len(data["playlists"]) <= 5

    async def test_limit_respected(self, live_context):
        result = await youtube.execute_action("list_playlists", {"mine": True, "max_results": 2}, live_context)
        assert len(result.result.data["playlists"]) <= 2


class TestListPlaylistItems:
    async def test_returns_items(self, live_context):
        require_playlist_id()
        result = await youtube.execute_action(
            "list_playlist_items",
            {"playlist_id": TEST_PLAYLIST_ID, "max_results": 5},
            live_context,
        )
        data = result.result.data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) <= 5

    async def test_items_have_video_ids(self, live_context):
        require_playlist_id()
        result = await youtube.execute_action(
            "list_playlist_items",
            {"playlist_id": TEST_PLAYLIST_ID, "max_results": 1},
            live_context,
        )
        items = result.result.data["items"]
        if not items:
            pytest.skip("Playlist is empty")
        assert "video_id" in items[0]
        assert "title" in items[0]


# =============================================================================
# COMMENTS (read-only)
# =============================================================================


class TestListComments:
    async def test_returns_comments(self, live_context):
        require_video_id()
        result = await youtube.execute_action(
            "list_comments",
            {"video_id": TEST_VIDEO_ID, "max_results": 5},
            live_context,
        )
        data = result.result.data
        assert "comments" in data
        assert isinstance(data["comments"], list)

    async def test_comment_structure(self, live_context):
        require_video_id()
        result = await youtube.execute_action(
            "list_comments",
            {"video_id": TEST_VIDEO_ID, "max_results": 1},
            live_context,
        )
        comments = result.result.data["comments"]
        if not comments:
            pytest.skip("Video has no comments")
        c = comments[0]
        assert "id" in c
        assert "text" in c
        assert "author_display_name" in c


class TestListCommentReplies:
    async def test_returns_replies(self, live_context):
        require_comment_id()
        result = await youtube.execute_action(
            "list_comment_replies",
            {"parent_comment_id": TEST_COMMENT_ID, "max_results": 5},
            live_context,
        )
        data = result.result.data
        assert "replies" in data
        assert isinstance(data["replies"], list)


# =============================================================================
# DESTRUCTIVE — playlist + comment lifecycles
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestPlaylistLifecycle:
    """Create → update → list items → delete a playlist on the authenticated account."""

    async def test_full_lifecycle(self, live_context):
        # Create
        create_result = await youtube.execute_action(
            "create_playlist",
            {
                "title": f"Integration Test Playlist {os.getpid()}",
                "description": "Created by automated integration test — will be deleted",
                "privacy_status": "private",
            },
            live_context,
        )
        playlist_id = create_result.result.data["playlist"]["id"]
        assert playlist_id

        try:
            # Update
            update_result = await youtube.execute_action(
                "update_playlist",
                {"playlist_id": playlist_id, "title": f"Updated Test Playlist {os.getpid()}"},
                live_context,
            )
            assert update_result.result.data["playlist"]["id"] == playlist_id

            # List items (should be empty for a new playlist)
            list_result = await youtube.execute_action(
                "list_playlist_items", {"playlist_id": playlist_id}, live_context
            )
            assert list_result.result.data["items"] == []

            # Optional: add then remove a video if a test video is provided
            if TEST_VIDEO_ID:
                add_result = await youtube.execute_action(
                    "add_video_to_playlist",
                    {"playlist_id": playlist_id, "video_id": TEST_VIDEO_ID},
                    live_context,
                )
                item_id = add_result.result.data["playlist_item"]["id"]
                assert item_id

                remove_result = await youtube.execute_action(
                    "remove_video_from_playlist",
                    {"playlist_item_id": item_id},
                    live_context,
                )
                assert remove_result.result.data["success"] is True
        finally:
            # Cleanup
            delete_result = await youtube.execute_action("delete_playlist", {"playlist_id": playlist_id}, live_context)
            assert delete_result.result.data["success"] is True


@pytest.mark.destructive
class TestCommentLifecycle:
    """Post → update → delete a comment on a test video."""

    async def test_full_lifecycle(self, live_context):
        require_video_id()

        # Post
        post_result = await youtube.execute_action(
            "post_comment",
            {
                "video_id": TEST_VIDEO_ID,
                "text": f"Integration test comment {os.getpid()} — will be deleted",
            },
            live_context,
        )
        comment_id = post_result.result.data["comment"]["id"]
        assert comment_id

        try:
            # Update
            update_result = await youtube.execute_action(
                "update_comment",
                {"comment_id": comment_id, "text": f"Updated test comment {os.getpid()}"},
                live_context,
            )
            assert "comment" in update_result.result.data
        finally:
            # Cleanup
            delete_result = await youtube.execute_action("delete_comment", {"comment_id": comment_id}, live_context)
            assert delete_result.result.data["success"] is True


@pytest.mark.destructive
class TestUpdateVideo:
    """Mutates a real video's title/description, then reverts to the original values."""

    async def test_update_and_revert(self, live_context):
        require_video_id()

        # Read current state so we can revert
        get_result = await youtube.execute_action("get_video", {"video_id": TEST_VIDEO_ID}, live_context)
        original = get_result.result.data["video"]
        original_title = original["title"]
        original_description = original["description"]

        new_title = f"{original_title} [integration test {os.getpid()}]"
        new_description = f"{original_description}\n\n[integration test marker {os.getpid()}]"

        try:
            update_result = await youtube.execute_action(
                "update_video",
                {"video_id": TEST_VIDEO_ID, "title": new_title, "description": new_description},
                live_context,
            )
            assert update_result.result.data["video"]["id"] == TEST_VIDEO_ID
            assert update_result.result.data["video"]["title"] == new_title
        finally:
            # Revert
            await youtube.execute_action(
                "update_video",
                {"video_id": TEST_VIDEO_ID, "title": original_title, "description": original_description},
                live_context,
            )


@pytest.mark.destructive
class TestUploadThumbnail:
    """Uploads a real thumbnail to a test video.

    NOTE: YouTube does not provide an API to revert a custom thumbnail to the
    auto-generated one. After this test runs the test video will keep the
    uploaded thumbnail unless changed manually.
    """

    async def test_uploads_via_file_input(self, live_context):
        require_video_id()
        require_thumbnail_path()

        import base64

        with open(TEST_THUMBNAIL_PATH, "rb") as fh:
            img_bytes = fh.read()
        b64 = base64.b64encode(img_bytes).decode()

        result = await youtube.execute_action(
            "upload_thumbnail",
            {"video_id": TEST_VIDEO_ID, "file": {"content": b64, "filename": os.path.basename(TEST_THUMBNAIL_PATH)}},
            live_context,
        )
        data = result.result.data
        assert "thumbnail" in data


@pytest.mark.destructive
class TestReplyToCommentLifecycle:
    """Post parent → reply → delete reply → delete parent."""

    async def test_full_lifecycle(self, live_context):
        require_video_id()

        # Create parent comment
        parent_result = await youtube.execute_action(
            "post_comment",
            {
                "video_id": TEST_VIDEO_ID,
                "text": f"Integration test parent {os.getpid()} — will be deleted",
            },
            live_context,
        )
        parent_id = parent_result.result.data["comment"]["id"]
        assert parent_id

        reply_id = None
        try:
            # Reply
            reply_result = await youtube.execute_action(
                "reply_to_comment",
                {
                    "parent_comment_id": parent_id,
                    "text": f"Integration test reply {os.getpid()} — will be deleted",
                },
                live_context,
            )
            reply_id = reply_result.result.data["comment"]["id"]
            assert reply_id
            assert reply_result.result.data["comment"]["text"]
        finally:
            # Cleanup: delete reply first (if created), then parent
            if reply_id:
                reply_delete = await youtube.execute_action("delete_comment", {"comment_id": reply_id}, live_context)
                assert reply_delete.result.data["success"] is True
            parent_delete = await youtube.execute_action("delete_comment", {"comment_id": parent_id}, live_context)
            assert parent_delete.result.data["success"] is True


@pytest.mark.destructive
class TestModerateComment:
    """Post a comment on a video the user owns → moderate it → delete it.

    moderate_comment requires the authenticated user to own the channel that
    hosts the video. Set YOUTUBE_TEST_OWNED_VIDEO_ID to a video on the user's
    own channel — otherwise YouTube returns a 403 and we cannot exercise this
    action against a live API.
    """

    async def test_set_moderation_status(self, live_context):
        require_owned_video_id()

        # Post a comment we can moderate
        post_result = await youtube.execute_action(
            "post_comment",
            {
                "video_id": TEST_OWNED_VIDEO_ID,
                "text": f"Integration test moderation target {os.getpid()} — will be deleted",
            },
            live_context,
        )
        comment_id = post_result.result.data["comment"]["id"]
        assert comment_id

        try:
            # Moderate — set to heldForReview
            mod_result = await youtube.execute_action(
                "moderate_comment",
                {"comment_id": comment_id, "moderation_status": "heldForReview"},
                live_context,
            )
            assert mod_result.result.data["success"] is True

            # Restore to published
            restore_result = await youtube.execute_action(
                "moderate_comment",
                {"comment_id": comment_id, "moderation_status": "published"},
                live_context,
            )
            assert restore_result.result.data["success"] is True
        finally:
            # Cleanup
            delete_result = await youtube.execute_action("delete_comment", {"comment_id": comment_id}, live_context)
            assert delete_result.result.data["success"] is True
