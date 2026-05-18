"""
Unit tests for the YouTube integration using mocked fetch.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from youtube import youtube, YouTubeParser

pytestmark = pytest.mark.unit


# ---- Helpers ----


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test_token"}}  # nosec B105
    return ctx


def make_ctx_multi(responses: list):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test_token"}}  # nosec B105
    return ctx


# =============================================================================
# YouTubeParser — pure helpers
# =============================================================================


class TestParseSearchResult:
    def test_video_item(self):
        item = {
            "id": {"kind": "youtube#video", "videoId": "abc123"},
            "snippet": {
                "title": "Test Video",
                "description": "A test",
                "publishedAt": "2024-01-01T00:00:00Z",
                "channelId": "ch1",
                "channelTitle": "Test Channel",
                "thumbnails": {
                    "high": {"url": "https://img/hi.jpg"},
                    "medium": {"url": "https://img/med.jpg"},
                    "default": {"url": "https://img/def.jpg"},
                },
            },
        }
        parsed = YouTubeParser.parse_search_result(item)
        assert parsed["id"] == {"kind": "youtube#video", "videoId": "abc123"}
        assert parsed["title"] == "Test Video"
        assert parsed["thumbnail"] == "https://img/hi.jpg"  # prefers high
        assert parsed["channel_id"] == "ch1"

    def test_falls_back_to_medium_thumbnail(self):
        item = {
            "id": {"videoId": "x"},
            "snippet": {
                "title": "t",
                "thumbnails": {"medium": {"url": "https://img/med.jpg"}, "default": {"url": "https://img/def.jpg"}},
            },
        }
        parsed = YouTubeParser.parse_search_result(item)
        assert parsed["thumbnail"] == "https://img/med.jpg"

    def test_falls_back_to_default_thumbnail(self):
        item = {"id": {}, "snippet": {"thumbnails": {"default": {"url": "https://img/def.jpg"}}}}
        parsed = YouTubeParser.parse_search_result(item)
        assert parsed["thumbnail"] == "https://img/def.jpg"

    def test_missing_snippet_safe_defaults(self):
        parsed = YouTubeParser.parse_search_result({"id": {}})
        assert parsed["title"] == ""
        assert parsed["thumbnail"] == ""
        assert parsed["channel_id"] == ""


class TestParseVideo:
    def test_full_video(self):
        item = {
            "id": "vid1",
            "snippet": {
                "title": "T",
                "description": "D",
                "channelId": "c",
                "channelTitle": "C",
                "publishedAt": "2024-01-01",
                "thumbnails": {"high": {"url": "u"}},
                "tags": ["one", "two"],
            },
            "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "5"},
            "contentDetails": {"duration": "PT5M"},
        }
        parsed = YouTubeParser.parse_video(item)
        assert parsed["id"] == "vid1"
        assert parsed["duration"] == "PT5M"
        assert parsed["view_count"] == "100"
        assert parsed["like_count"] == "10"
        assert parsed["comment_count"] == "5"
        assert parsed["tags"] == ["one", "two"]

    def test_video_without_statistics(self):
        item = {"id": "v", "snippet": {"title": "t"}}
        parsed = YouTubeParser.parse_video(item)
        assert parsed["id"] == "v"
        assert "view_count" not in parsed
        assert "duration" not in parsed
        assert "tags" not in parsed


class TestParseChannel:
    def test_full_channel(self):
        item = {
            "id": "ch1",
            "snippet": {
                "title": "My Channel",
                "description": "desc",
                "customUrl": "@mychannel",
                "publishedAt": "2020-01-01",
                "thumbnails": {},
            },
            "statistics": {"subscriberCount": "1000", "videoCount": "50", "viewCount": "100000"},
        }
        parsed = YouTubeParser.parse_channel(item)
        assert parsed["id"] == "ch1"
        assert parsed["custom_url"] == "@mychannel"
        assert parsed["subscriber_count"] == "1000"
        assert parsed["video_count"] == "50"
        assert parsed["view_count"] == "100000"

    def test_channel_missing_stats(self):
        parsed = YouTubeParser.parse_channel({"id": "c", "snippet": {"title": "t"}})
        assert "subscriber_count" not in parsed


class TestParsePlaylist:
    def test_full_playlist(self):
        item = {
            "id": "pl1",
            "snippet": {"title": "My PL", "channelId": "c", "channelTitle": "C"},
            "contentDetails": {"itemCount": 42},
        }
        parsed = YouTubeParser.parse_playlist(item)
        assert parsed["id"] == "pl1"
        assert parsed["item_count"] == 42

    def test_playlist_without_item_count(self):
        parsed = YouTubeParser.parse_playlist({"id": "p", "snippet": {}})
        assert "item_count" not in parsed


class TestParseComment:
    def test_comment_thread_format(self):
        # commentThreads.list returns thread items with topLevelComment
        item = {
            "id": "thread1",
            "snippet": {
                "topLevelComment": {
                    "id": "c1",
                    "snippet": {
                        "textDisplay": "Hello",
                        "textOriginal": "Hello",
                        "authorDisplayName": "Alice",
                        "authorChannelId": {"value": "ch_alice"},
                        "likeCount": 3,
                        "publishedAt": "2024-01-01",
                        "updatedAt": "2024-01-01",
                    },
                },
                "totalReplyCount": 2,
            },
        }
        parsed = YouTubeParser.parse_comment(item)
        assert parsed["id"] == "thread1"
        assert parsed["text"] == "Hello"
        assert parsed["author_display_name"] == "Alice"
        assert parsed["author_channel_id"] == "ch_alice"
        assert parsed["like_count"] == 3
        assert parsed["total_reply_count"] == 2

    def test_plain_comment_format(self):
        # comments.insert returns the bare comment with snippet at top
        item = {
            "id": "c1",
            "snippet": {
                "textDisplay": "Bare",
                "textOriginal": "Bare",
                "authorDisplayName": "Bob",
                "authorChannelId": {"value": "ch_bob"},
                "likeCount": 0,
            },
        }
        parsed = YouTubeParser.parse_comment(item)
        assert parsed["id"] == "c1"
        assert parsed["text"] == "Bare"
        assert parsed["author_display_name"] == "Bob"


# =============================================================================
# SEARCH
# =============================================================================


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_parsed_items(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": {"kind": "youtube#video", "videoId": "v1"},
                        "snippet": {
                            "title": "Vid 1",
                            "channelTitle": "Ch",
                            "thumbnails": {"high": {"url": "u"}},
                        },
                    }
                ],
                "pageInfo": {"totalResults": 1},
                "nextPageToken": "tok_next",
            }
        )
        result = await youtube.execute_action("search", {"query": "python"}, ctx)
        data = result.result.data
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Vid 1"
        assert data["total_results"] == 1
        assert data["next_page_token"] == "tok_next"

    @pytest.mark.asyncio
    async def test_default_max_results_is_5(self):
        ctx = make_ctx({"items": [], "pageInfo": {"totalResults": 0}})
        await youtube.execute_action("search", {"query": "python"}, ctx)
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["maxResults"] == 5
        assert params["q"] == "python"
        assert params["part"] == "snippet"

    @pytest.mark.asyncio
    async def test_optional_params_forwarded(self):
        ctx = make_ctx({"items": [], "pageInfo": {}})
        await youtube.execute_action(
            "search",
            {
                "query": "q",
                "type": "video",
                "max_results": 25,
                "order": "date",
                "published_after": "2024-01-01T00:00:00Z",
                "published_before": "2024-12-31T00:00:00Z",
                "channel_id": "UC123",
                "region_code": "US",
                "page_token": "ptok",  # nosec B105
            },
            ctx,
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["type"] == "video"
        assert params["maxResults"] == 25
        assert params["order"] == "date"
        assert params["publishedAfter"] == "2024-01-01T00:00:00Z"
        assert params["publishedBefore"] == "2024-12-31T00:00:00Z"
        assert params["channelId"] == "UC123"
        assert params["regionCode"] == "US"
        assert params["pageToken"] == "ptok"

    @pytest.mark.asyncio
    async def test_no_next_page_token_when_absent(self):
        ctx = make_ctx({"items": [], "pageInfo": {"totalResults": 0}})
        result = await youtube.execute_action("search", {"query": "q"}, ctx)
        assert "next_page_token" not in result.result.data

    @pytest.mark.asyncio
    async def test_url_correct(self):
        ctx = make_ctx({"items": [], "pageInfo": {}})
        await youtube.execute_action("search", {"query": "q"}, ctx)
        assert ctx.fetch.call_args.args[0] == "https://www.googleapis.com/youtube/v3/search"
        assert ctx.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = MagicMock(name="ExecutionContext")
        ctx.fetch = AsyncMock(side_effect=Exception("network down"))
        ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "t"}}  # nosec B105
        result = await youtube.execute_action("search", {"query": "q"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "network down" in result.result.message


# =============================================================================
# GET VIDEO
# =============================================================================


class TestGetVideo:
    @pytest.mark.asyncio
    async def test_returns_video(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": "v1",
                        "snippet": {"title": "T", "channelId": "c", "channelTitle": "C"},
                        "statistics": {"viewCount": "10"},
                        "contentDetails": {"duration": "PT1M"},
                    }
                ]
            }
        )
        result = await youtube.execute_action("get_video", {"video_id": "v1"}, ctx)
        data = result.result.data
        assert data["video"]["id"] == "v1"
        assert data["video"]["view_count"] == "10"
        assert data["video"]["duration"] == "PT1M"

    @pytest.mark.asyncio
    async def test_not_found_returns_action_error(self):
        ctx = make_ctx({"items": []})
        result = await youtube.execute_action("get_video", {"video_id": "missing"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Video not found" in result.result.message

    @pytest.mark.asyncio
    async def test_request_params(self):
        ctx = make_ctx({"items": [{"id": "v1", "snippet": {}}]})
        await youtube.execute_action("get_video", {"video_id": "v1"}, ctx)
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["id"] == "v1"
        assert params["part"] == "snippet,statistics,contentDetails"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = MagicMock()
        ctx.fetch = AsyncMock(side_effect=Exception("boom"))
        ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "t"}}  # nosec B105
        result = await youtube.execute_action("get_video", {"video_id": "v1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


# =============================================================================
# UPDATE VIDEO
# =============================================================================


class TestUpdateVideo:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        ctx = make_ctx_multi(
            [
                {"items": [{"id": "v1", "snippet": {"title": "old"}, "status": {"privacyStatus": "private"}}]},
                {"id": "v1", "snippet": {"title": "new", "channelId": "c"}, "statistics": {}, "contentDetails": {}},
            ]
        )
        result = await youtube.execute_action(
            "update_video",
            {
                "video_id": "v1",
                "title": "new",
                "description": "desc",
                "tags": ["a", "b"],
                "privacy_status": "public",
                "category_id": "22",
                "made_for_kids": False,
            },
            ctx,
        )
        data = result.result.data
        assert data["video"]["id"] == "v1"

        # verify PUT call body
        put_call = ctx.fetch.call_args_list[1]
        body = put_call.kwargs["json"]
        assert body["id"] == "v1"
        assert body["snippet"]["title"] == "new"
        assert body["snippet"]["description"] == "desc"
        assert body["snippet"]["tags"] == ["a", "b"]
        assert body["snippet"]["categoryId"] == "22"
        assert body["status"]["privacyStatus"] == "public"
        assert body["status"]["selfDeclaredMadeForKids"] is False

    @pytest.mark.asyncio
    async def test_video_not_found(self):
        ctx = make_ctx({"items": []})
        result = await youtube.execute_action("update_video", {"video_id": "missing", "title": "x"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Video not found" in result.result.message

    @pytest.mark.asyncio
    async def test_only_provided_fields_change(self):
        ctx = make_ctx_multi(
            [
                {
                    "items": [
                        {
                            "id": "v1",
                            "snippet": {"title": "orig", "description": "orig desc"},
                            "status": {"privacyStatus": "private"},
                        }
                    ]
                },
                {"id": "v1", "snippet": {"title": "new"}, "statistics": {}, "contentDetails": {}},
            ]
        )
        await youtube.execute_action("update_video", {"video_id": "v1", "title": "new"}, ctx)
        body = ctx.fetch.call_args_list[1].kwargs["json"]
        assert body["snippet"]["title"] == "new"
        assert body["snippet"]["description"] == "orig desc"  # untouched
        assert body["status"]["privacyStatus"] == "private"  # untouched


# =============================================================================
# UPLOAD THUMBNAIL
# =============================================================================


class TestUploadThumbnail:
    @pytest.mark.asyncio
    async def test_uploads_small_jpeg_from_url(self):
        jpeg_bytes = b"\xff\xd8" + b"\x00" * 100  # JPEG magic + tiny payload
        ctx = make_ctx_multi([jpeg_bytes, {"items": [{"default": {"url": "thumb"}}]}])
        # First fetch (image_url) returns bytes; wrap manually because make_ctx_multi assumes dict
        ctx.fetch = AsyncMock(
            side_effect=[
                FetchResponse(status=200, headers={}, data=jpeg_bytes),
                FetchResponse(status=200, headers={}, data={"items": [{"default": {"url": "thumb"}}]}),
            ]
        )

        result = await youtube.execute_action(
            "upload_thumbnail",
            {"video_id": "v1", "image_url": "https://example.com/img.jpg"},
            ctx,
        )
        data = result.result.data
        assert "thumbnail" in data
        # Upload call uses POST with image/jpeg content type
        upload_call = ctx.fetch.call_args_list[1]
        assert upload_call.kwargs["method"] == "POST"
        assert upload_call.kwargs["headers"]["Content-Type"] == "image/jpeg"
        assert upload_call.kwargs["params"]["videoId"] == "v1"

    @pytest.mark.asyncio
    async def test_no_image_input_returns_error(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("upload_thumbnail", {"video_id": "v1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "image_url" in result.result.message

    @pytest.mark.asyncio
    async def test_file_object_missing_content(self):
        ctx = make_ctx({})
        result = await youtube.execute_action(
            "upload_thumbnail",
            {"video_id": "v1", "file": {"filename": "x.jpg"}},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "content" in result.result.message

    @pytest.mark.asyncio
    async def test_chat_uploaded_file(self):
        import base64

        png_bytes = b"\x89PNG" + b"\x00" * 100
        b64 = base64.b64encode(png_bytes).decode()

        ctx = MagicMock()
        ctx.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data={"items": []}))
        ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "t"}}  # nosec B105

        result = await youtube.execute_action(
            "upload_thumbnail",
            {"video_id": "v1", "file": {"content": b64}},
            ctx,
        )
        assert result.type != ResultType.ACTION_ERROR
        # only one fetch call (the upload itself; no URL fetch)
        assert ctx.fetch.call_count == 1
        assert ctx.fetch.call_args.kwargs["headers"]["Content-Type"] == "image/png"


# =============================================================================
# GET CHANNEL
# =============================================================================


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_get_my_channel(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": "ch1",
                        "snippet": {"title": "Mine"},
                        "statistics": {"subscriberCount": "100"},
                    }
                ]
            }
        )
        result = await youtube.execute_action("get_channel", {"mine": True}, ctx)
        data = result.result.data
        assert data["channel"]["id"] == "ch1"
        assert data["channel"]["subscriber_count"] == "100"
        assert ctx.fetch.call_args.kwargs["params"]["mine"] == "true"

    @pytest.mark.asyncio
    async def test_get_by_channel_id(self):
        ctx = make_ctx({"items": [{"id": "ch1", "snippet": {}, "statistics": {}}]})
        await youtube.execute_action("get_channel", {"channel_id": "ch1"}, ctx)
        assert ctx.fetch.call_args.kwargs["params"]["id"] == "ch1"

    @pytest.mark.asyncio
    async def test_get_by_handle(self):
        ctx = make_ctx({"items": [{"id": "ch1", "snippet": {}, "statistics": {}}]})
        await youtube.execute_action("get_channel", {"channel_handle": "@me"}, ctx)
        assert ctx.fetch.call_args.kwargs["params"]["forHandle"] == "@me"

    @pytest.mark.asyncio
    async def test_no_filter_returns_error(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("get_channel", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "channel_id" in result.result.message

    @pytest.mark.asyncio
    async def test_channel_not_found(self):
        ctx = make_ctx({"items": []})
        result = await youtube.execute_action("get_channel", {"channel_id": "missing"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Channel not found" in result.result.message


# =============================================================================
# PLAYLISTS
# =============================================================================


class TestListPlaylists:
    @pytest.mark.asyncio
    async def test_list_my_playlists(self):
        ctx = make_ctx(
            {
                "items": [
                    {"id": "pl1", "snippet": {"title": "P1"}, "contentDetails": {"itemCount": 5}},
                    {"id": "pl2", "snippet": {"title": "P2"}, "contentDetails": {"itemCount": 10}},
                ],
                "nextPageToken": "tok",
            }
        )
        result = await youtube.execute_action("list_playlists", {"mine": True}, ctx)
        data = result.result.data
        assert len(data["playlists"]) == 2
        assert data["playlists"][0]["item_count"] == 5
        assert data["next_page_token"] == "tok"
        assert ctx.fetch.call_args.kwargs["params"]["mine"] == "true"

    @pytest.mark.asyncio
    async def test_list_by_channel(self):
        ctx = make_ctx({"items": []})
        await youtube.execute_action(
            "list_playlists",
            {"channel_id": "UC1", "max_results": 25, "page_token": "ptok"},  # nosec B105
            ctx,
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["channelId"] == "UC1"
        assert params["maxResults"] == 25
        assert params["pageToken"] == "ptok"

    @pytest.mark.asyncio
    async def test_no_filter_returns_error(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("list_playlists", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "channel_id" in result.result.message


class TestCreatePlaylist:
    @pytest.mark.asyncio
    async def test_creates_with_required(self):
        ctx = make_ctx({"id": "pl_new", "snippet": {"title": "T"}, "contentDetails": {}})
        result = await youtube.execute_action(
            "create_playlist",
            {"title": "T", "privacy_status": "private"},
            ctx,
        )
        data = result.result.data
        assert data["playlist"]["id"] == "pl_new"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["title"] == "T"
        assert body["status"]["privacyStatus"] == "private"
        assert "description" not in body["snippet"]

    @pytest.mark.asyncio
    async def test_creates_with_description(self):
        ctx = make_ctx({"id": "pl_new", "snippet": {}, "contentDetails": {}})
        await youtube.execute_action(
            "create_playlist",
            {"title": "T", "privacy_status": "public", "description": "D"},
            ctx,
        )
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["description"] == "D"


class TestUpdatePlaylist:
    @pytest.mark.asyncio
    async def test_updates_title_and_privacy(self):
        ctx = make_ctx_multi(
            [
                {
                    "items": [
                        {
                            "id": "pl1",
                            "snippet": {"title": "old"},
                            "status": {"privacyStatus": "private"},
                        }
                    ]
                },
                {"id": "pl1", "snippet": {"title": "new"}, "contentDetails": {}},
            ]
        )
        result = await youtube.execute_action(
            "update_playlist",
            {"playlist_id": "pl1", "title": "new", "privacy_status": "public", "description": "D"},
            ctx,
        )
        assert result.result.data["playlist"]["id"] == "pl1"
        body = ctx.fetch.call_args_list[1].kwargs["json"]
        assert body["snippet"]["title"] == "new"
        assert body["snippet"]["description"] == "D"
        assert body["status"]["privacyStatus"] == "public"

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self):
        ctx = make_ctx({"items": []})
        result = await youtube.execute_action("update_playlist", {"playlist_id": "x", "title": "y"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Playlist not found" in result.result.message


class TestDeletePlaylist:
    @pytest.mark.asyncio
    async def test_deletes(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("delete_playlist", {"playlist_id": "pl1"}, ctx)
        assert result.result.data == {"success": True}
        assert ctx.fetch.call_args.kwargs["method"] == "DELETE"
        assert ctx.fetch.call_args.kwargs["params"]["id"] == "pl1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = MagicMock()
        ctx.fetch = AsyncMock(side_effect=Exception("403"))
        ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "t"}}  # nosec B105
        result = await youtube.execute_action("delete_playlist", {"playlist_id": "pl1"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "403" in result.result.message


class TestListPlaylistItems:
    @pytest.mark.asyncio
    async def test_returns_items(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": "i1",
                        "snippet": {"title": "V1", "position": 0, "publishedAt": "2024", "thumbnails": {}},
                        "contentDetails": {"videoId": "v1"},
                    }
                ],
                "nextPageToken": "tok",
            }
        )
        result = await youtube.execute_action(
            "list_playlist_items",
            {"playlist_id": "pl1", "max_results": 10, "page_token": "p"},  # nosec B105
            ctx,
        )
        data = result.result.data
        assert len(data["items"]) == 1
        assert data["items"][0]["video_id"] == "v1"
        assert data["items"][0]["position"] == 0
        assert data["next_page_token"] == "tok"
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["playlistId"] == "pl1"
        assert params["maxResults"] == 10
        assert params["pageToken"] == "p"


class TestAddVideoToPlaylist:
    @pytest.mark.asyncio
    async def test_adds_video(self):
        ctx = make_ctx({"id": "item_new"})
        result = await youtube.execute_action(
            "add_video_to_playlist",
            {"playlist_id": "pl1", "video_id": "v1"},
            ctx,
        )
        assert result.result.data["playlist_item"]["id"] == "item_new"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["playlistId"] == "pl1"
        assert body["snippet"]["resourceId"]["videoId"] == "v1"
        assert body["snippet"]["resourceId"]["kind"] == "youtube#video"

    @pytest.mark.asyncio
    async def test_position_forwarded(self):
        ctx = make_ctx({"id": "item_new"})
        await youtube.execute_action(
            "add_video_to_playlist",
            {"playlist_id": "pl1", "video_id": "v1", "position": 3},
            ctx,
        )
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["position"] == 3


class TestRemoveVideoFromPlaylist:
    @pytest.mark.asyncio
    async def test_removes(self):
        ctx = make_ctx({})
        result = await youtube.execute_action(
            "remove_video_from_playlist",
            {"playlist_item_id": "item1"},
            ctx,
        )
        assert result.result.data == {"success": True}
        assert ctx.fetch.call_args.kwargs["method"] == "DELETE"
        assert ctx.fetch.call_args.kwargs["params"]["id"] == "item1"


# =============================================================================
# COMMENTS
# =============================================================================


class TestListComments:
    @pytest.mark.asyncio
    async def test_returns_comments(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": "thread1",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "textDisplay": "Great",
                                    "authorDisplayName": "Alice",
                                    "likeCount": 5,
                                },
                            },
                            "totalReplyCount": 0,
                        },
                    }
                ],
                "nextPageToken": "tok",
            }
        )
        result = await youtube.execute_action("list_comments", {"video_id": "v1"}, ctx)
        data = result.result.data
        assert len(data["comments"]) == 1
        assert data["comments"][0]["text"] == "Great"
        assert data["next_page_token"] == "tok"

    @pytest.mark.asyncio
    async def test_default_max_results_20(self):
        ctx = make_ctx({"items": []})
        await youtube.execute_action("list_comments", {"video_id": "v1"}, ctx)
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["maxResults"] == 20
        assert params["videoId"] == "v1"
        assert params["textFormat"] == "plainText"

    @pytest.mark.asyncio
    async def test_order_and_page_token_forwarded(self):
        ctx = make_ctx({"items": []})
        await youtube.execute_action(
            "list_comments",
            {"video_id": "v1", "order": "relevance", "page_token": "ptok", "max_results": 50},  # nosec B105
            ctx,
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["order"] == "relevance"
        assert params["pageToken"] == "ptok"
        assert params["maxResults"] == 50


class TestListCommentReplies:
    @pytest.mark.asyncio
    async def test_returns_replies(self):
        ctx = make_ctx(
            {
                "items": [
                    {
                        "id": "r1",
                        "snippet": {
                            "textDisplay": "Thanks!",
                            "authorDisplayName": "Author",
                            "likeCount": 1,
                            "publishedAt": "2024",
                        },
                    }
                ]
            }
        )
        result = await youtube.execute_action("list_comment_replies", {"parent_comment_id": "c1"}, ctx)
        data = result.result.data
        assert len(data["replies"]) == 1
        assert data["replies"][0]["text"] == "Thanks!"
        assert ctx.fetch.call_args.kwargs["params"]["parentId"] == "c1"


class TestPostComment:
    @pytest.mark.asyncio
    async def test_posts_comment(self):
        ctx = make_ctx(
            {
                "id": "thread_new",
                "snippet": {
                    "topLevelComment": {
                        "id": "c_new",
                        "snippet": {
                            "textDisplay": "Hello",
                            "textOriginal": "Hello",
                            "authorDisplayName": "Me",
                        },
                    },
                    "totalReplyCount": 0,
                },
            }
        )
        result = await youtube.execute_action("post_comment", {"video_id": "v1", "text": "Hello"}, ctx)
        data = result.result.data
        assert data["comment"]["text"] == "Hello"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["videoId"] == "v1"
        assert body["snippet"]["topLevelComment"]["snippet"]["textOriginal"] == "Hello"


class TestReplyToComment:
    @pytest.mark.asyncio
    async def test_replies(self):
        ctx = make_ctx(
            {
                "id": "r_new",
                "snippet": {"textDisplay": "Reply", "authorDisplayName": "Me"},
            }
        )
        result = await youtube.execute_action(
            "reply_to_comment",
            {"parent_comment_id": "c1", "text": "Reply"},
            ctx,
        )
        data = result.result.data
        assert data["comment"]["id"] == "r_new"
        assert data["comment"]["text"] == "Reply"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["snippet"]["parentId"] == "c1"
        assert body["snippet"]["textOriginal"] == "Reply"


class TestUpdateComment:
    @pytest.mark.asyncio
    async def test_updates(self):
        ctx = make_ctx_multi(
            [
                {"items": [{"id": "c1", "snippet": {"textOriginal": "old"}}]},
                {
                    "id": "c1",
                    "snippet": {
                        "textDisplay": "new",
                        "textOriginal": "new",
                        "authorDisplayName": "Tester",
                    },
                },
            ]
        )
        result = await youtube.execute_action("update_comment", {"comment_id": "c1", "text": "new"}, ctx)
        data = result.result.data
        assert data["comment"]["id"] == "c1"
        assert data["comment"]["text"] == "new"
        assert data["comment"]["text_original"] == "new"
        assert data["comment"]["author_display_name"] == "Tester"
        body = ctx.fetch.call_args_list[1].kwargs["json"]
        assert body["id"] == "c1"
        assert body["snippet"]["textOriginal"] == "new"

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self):
        ctx = make_ctx({"items": []})
        result = await youtube.execute_action("update_comment", {"comment_id": "missing", "text": "x"}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "Comment not found" in result.result.message


class TestDeleteComment:
    @pytest.mark.asyncio
    async def test_deletes(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("delete_comment", {"comment_id": "c1"}, ctx)
        assert result.result.data == {"success": True}
        assert ctx.fetch.call_args.kwargs["method"] == "DELETE"
        assert ctx.fetch.call_args.kwargs["params"]["id"] == "c1"


class TestModerateComment:
    @pytest.mark.asyncio
    async def test_sets_moderation_status(self):
        ctx = make_ctx({})
        result = await youtube.execute_action(
            "moderate_comment",
            {"comment_id": "c1", "moderation_status": "heldForReview"},
            ctx,
        )
        assert result.result.data == {"success": True}
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["id"] == "c1"
        assert params["moderationStatus"] == "heldForReview"
        assert "banAuthor" not in params

    @pytest.mark.asyncio
    async def test_ban_author_flag(self):
        ctx = make_ctx({})
        await youtube.execute_action(
            "moderate_comment",
            {"comment_id": "c1", "moderation_status": "rejected", "ban_author": True},
            ctx,
        )
        params = ctx.fetch.call_args.kwargs["params"]
        assert params["banAuthor"] == "true"

    @pytest.mark.asyncio
    async def test_url_uses_set_moderation_status_endpoint(self):
        ctx = make_ctx({})
        await youtube.execute_action(
            "moderate_comment",
            {"comment_id": "c1", "moderation_status": "published"},
            ctx,
        )
        assert ctx.fetch.call_args.args[0] == ("https://www.googleapis.com/youtube/v3/comments/setModerationStatus")


# =============================================================================
# Input validation (SDK-level)
# =============================================================================


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_search_missing_query_validation_error(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("search", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_create_playlist_missing_required(self):
        ctx = make_ctx({})
        result = await youtube.execute_action("create_playlist", {"title": "T"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
