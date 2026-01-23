"""
Unit tests for TikTok integration.
"""

import pytest

from ..tiktok import (
    TikTokAPIError,
    _build_user_info,
    _build_creator_info,
    _build_video,
    _build_post_status,
    _build_post_info,
    _check_api_response,
    _validate_video_source,
    _validate_chunk_size,
    _calculate_chunk_count,
    MIN_CHUNK_SIZE,
    MAX_CHUNK_SIZE,
    MAX_CAPTION_LENGTH,
)
from .context import (
    MockExecutionContext,
    MOCK_USER_INFO_RESPONSE,
    MOCK_CREATOR_INFO_RESPONSE,
    MOCK_VIDEO_INIT_RESPONSE,
    MOCK_VIDEO_INIT_FILE_UPLOAD_RESPONSE,
    MOCK_POST_STATUS_COMPLETE_RESPONSE,
    MOCK_POST_STATUS_FAILED_RESPONSE,
    MOCK_VIDEOS_LIST_RESPONSE,
    MOCK_PHOTO_POST_RESPONSE,
    MOCK_ERROR_RESPONSE_INVALID_TOKEN,
    MOCK_ERROR_RESPONSE_RATE_LIMIT,
    MOCK_ERROR_RESPONSE_SCOPE_NOT_AUTHORIZED,
    MOCK_ERROR_RESPONSE_GENERIC,
)

pytestmark = pytest.mark.asyncio


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestBuildUserInfo:
    """Tests for _build_user_info helper."""

    def test_builds_complete_response(self):
        """Test building response with all fields."""
        data = MOCK_USER_INFO_RESPONSE["data"]
        result = _build_user_info(data)

        assert result["open_id"] == "test_open_id_123"
        assert result["union_id"] == "test_union_id_456"
        assert result["display_name"] == "Test Creator"
        assert result["username"] == "testcreator"
        assert result["follower_count"] == 10000
        assert result["is_verified"] is True

    def test_handles_missing_fields(self):
        """Test handling missing fields with defaults."""
        data = {"user": {"open_id": "123"}}
        result = _build_user_info(data)

        assert result["open_id"] == "123"
        assert result["display_name"] == ""
        assert result["follower_count"] == 0
        assert result["is_verified"] is False

    def test_handles_flat_structure(self):
        """Test handling response without nested 'user' key."""
        data = {"open_id": "direct_123", "display_name": "Direct User"}
        result = _build_user_info(data)

        assert result["open_id"] == "direct_123"
        assert result["display_name"] == "Direct User"


class TestBuildCreatorInfo:
    """Tests for _build_creator_info helper."""

    def test_builds_complete_response(self):
        """Test building response with all fields."""
        data = MOCK_CREATOR_INFO_RESPONSE["data"]
        result = _build_creator_info(data)

        assert result["creator_username"] == "testcreator"
        assert result["max_video_post_duration_sec"] == 600
        assert "PUBLIC_TO_EVERYONE" in result["privacy_level_options"]
        assert result["comment_disabled"] is False

    def test_handles_missing_fields(self):
        """Test handling missing fields."""
        data = {}
        result = _build_creator_info(data)

        assert result["creator_username"] == ""
        assert result["privacy_level_options"] == []
        assert result["max_video_post_duration_sec"] == 600


class TestBuildVideo:
    """Tests for _build_video helper."""

    def test_builds_complete_response(self):
        """Test building video response with all fields."""
        video = MOCK_VIDEOS_LIST_RESPONSE["data"]["videos"][0]
        result = _build_video(video)

        assert result["id"] == "7123456789012345678"
        assert result["title"] == "Test video #tiktok"
        assert result["duration"] == 30
        assert result["like_count"] == 1000
        assert result["view_count"] == 10000

    def test_handles_missing_fields(self):
        """Test handling missing video fields."""
        video = {"id": "123"}
        result = _build_video(video)

        assert result["id"] == "123"
        assert result["title"] == ""
        assert result["duration"] == 0
        assert result["like_count"] == 0


class TestBuildPostStatus:
    """Tests for _build_post_status helper."""

    def test_builds_complete_response(self):
        """Test building complete status response."""
        data = MOCK_POST_STATUS_COMPLETE_RESPONSE["data"]
        result = _build_post_status(data)

        assert result["status"] == "PUBLISH_COMPLETE"
        assert "7123456789012345678" in result["publicaly_available_post_id"]

    def test_builds_failed_response(self):
        """Test building failed status response."""
        data = MOCK_POST_STATUS_FAILED_RESPONSE["data"]
        result = _build_post_status(data)

        assert result["status"] == "FAILED"
        assert result["fail_reason"] == "Video format not supported"
        assert result["error_code"] == "video_format_invalid"


class TestValidateVideoSource:
    """Tests for _validate_video_source helper."""

    def test_valid_pull_from_url(self):
        """Test valid PULL_FROM_URL source."""
        _validate_video_source("PULL_FROM_URL", "https://example.com/video.mp4", None)

    def test_valid_file_upload(self):
        """Test valid FILE_UPLOAD source."""
        _validate_video_source("FILE_UPLOAD", None, 1024 * 1024)

    def test_invalid_pull_from_url_missing_url(self):
        """Test PULL_FROM_URL without video_url raises error."""
        with pytest.raises(ValueError, match="video_url is required"):
            _validate_video_source("PULL_FROM_URL", None, None)

    def test_invalid_file_upload_missing_size(self):
        """Test FILE_UPLOAD without video_size raises error."""
        with pytest.raises(ValueError, match="video_size is required"):
            _validate_video_source("FILE_UPLOAD", None, None)

    def test_invalid_source_value(self):
        """Test invalid source value raises error."""
        with pytest.raises(ValueError, match="Invalid source"):
            _validate_video_source("INVALID_SOURCE", None, None)

    def test_invalid_source_empty_string(self):
        """Test empty source string raises error."""
        with pytest.raises(ValueError, match="Invalid source"):
            _validate_video_source("", None, None)


class TestCheckApiResponse:
    """Tests for _check_api_response helper."""

    def test_returns_data_on_success(self):
        """Test successful response returns data."""
        response = {"data": {"publish_id": "123"}}
        result = _check_api_response(response)
        assert result == {"publish_id": "123"}

    def test_returns_response_when_no_data_key(self):
        """Test response without data key returns entire response."""
        response = {"publish_id": "123"}
        result = _check_api_response(response)
        assert result == {"publish_id": "123"}

    def test_raises_on_invalid_token(self):
        """Test invalid token error raises TikTokAPIError."""
        with pytest.raises(TikTokAPIError) as exc_info:
            _check_api_response(MOCK_ERROR_RESPONSE_INVALID_TOKEN)
        assert exc_info.value.error_code == "access_token_invalid"

    def test_raises_on_rate_limit(self):
        """Test rate limit error raises TikTokAPIError."""
        with pytest.raises(TikTokAPIError) as exc_info:
            _check_api_response(MOCK_ERROR_RESPONSE_RATE_LIMIT)
        assert exc_info.value.error_code == "rate_limit_exceeded"

    def test_raises_on_scope_not_authorized(self):
        """Test scope not authorized error raises TikTokAPIError."""
        with pytest.raises(TikTokAPIError) as exc_info:
            _check_api_response(MOCK_ERROR_RESPONSE_SCOPE_NOT_AUTHORIZED)
        assert exc_info.value.error_code == "scope_not_authorized"

    def test_raises_on_generic_error(self):
        """Test generic error raises TikTokAPIError."""
        with pytest.raises(TikTokAPIError) as exc_info:
            _check_api_response(MOCK_ERROR_RESPONSE_GENERIC)
        assert exc_info.value.error_code == "spam_risk_too_many_posts"

    def test_handles_string_error(self):
        """Test string error message is handled."""
        response = {"error": "Something went wrong"}
        with pytest.raises(TikTokAPIError) as exc_info:
            _check_api_response(response)
        assert "Something went wrong" in str(exc_info.value)

    def test_ignores_empty_error(self):
        """Test empty error field is ignored."""
        response = {"error": None, "data": {"id": "123"}}
        result = _check_api_response(response)
        assert result == {"id": "123"}

    def test_ignores_empty_string_error(self):
        """Test empty string error field is ignored."""
        response = {"error": "", "data": {"id": "123"}}
        result = _check_api_response(response)
        assert result == {"id": "123"}


class TestValidateChunkSize:
    """Tests for _validate_chunk_size helper."""

    def test_small_video_uses_video_size(self):
        """Test small videos use video size as chunk size."""
        small_size = 1024 * 1024  # 1 MB
        result = _validate_chunk_size(MIN_CHUNK_SIZE, small_size)
        assert result == small_size

    def test_clamps_to_min(self):
        """Test chunk size is clamped to minimum."""
        result = _validate_chunk_size(1024, MIN_CHUNK_SIZE * 2)
        assert result == MIN_CHUNK_SIZE

    def test_clamps_to_max(self):
        """Test chunk size is clamped to maximum."""
        result = _validate_chunk_size(100 * 1024 * 1024, 100 * 1024 * 1024)
        assert result == MAX_CHUNK_SIZE

    def test_valid_chunk_size_unchanged(self):
        """Test valid chunk size is unchanged."""
        chunk_size = 10 * 1024 * 1024  # 10 MB
        video_size = 50 * 1024 * 1024  # 50 MB
        result = _validate_chunk_size(chunk_size, video_size)
        assert result == chunk_size


class TestCalculateChunkCount:
    """Tests for _calculate_chunk_count helper."""

    def test_single_chunk_for_small_video(self):
        """Test small video needs single chunk."""
        video_size = 3 * 1024 * 1024  # 3 MB
        chunk_size = 5 * 1024 * 1024  # 5 MB
        result = _calculate_chunk_count(video_size, chunk_size)
        assert result == 1

    def test_multiple_chunks(self):
        """Test larger video needs multiple chunks."""
        video_size = 25 * 1024 * 1024  # 25 MB
        chunk_size = 10 * 1024 * 1024  # 10 MB
        result = _calculate_chunk_count(video_size, chunk_size)
        assert result == 3


class TestBuildPostInfo:
    """Tests for _build_post_info helper."""

    def test_builds_basic_post_info(self):
        """Test building basic post info."""
        inputs = {"title": "Test video #tiktok", "privacy_level": "PUBLIC_TO_EVERYONE"}
        result = _build_post_info(inputs)

        assert result["title"] == "Test video #tiktok"
        assert result["privacy_level"] == "PUBLIC_TO_EVERYONE"
        assert result["disable_comment"] is False
        assert result["disable_duet"] is False

    def test_truncates_long_title(self):
        """Test title is truncated to max length."""
        inputs = {"title": "x" * 3000}
        result = _build_post_info(inputs)
        assert len(result["title"]) == MAX_CAPTION_LENGTH

    def test_optional_fields_included(self):
        """Test optional boolean fields are included correctly."""
        inputs = {"brand_content_toggle": True, "brand_organic_toggle": False}
        result = _build_post_info(inputs)
        assert result["brand_content_toggle"] is True
        assert "brand_organic_toggle" not in result

    def test_cover_timestamp_included(self):
        """Test cover timestamp is included when provided."""
        inputs = {"video_cover_timestamp_ms": 5000}
        result = _build_post_info(inputs)
        assert result["video_cover_timestamp_ms"] == 5000


# =============================================================================
# Action Handler Tests
# =============================================================================


class TestGetUserInfoHandler:
    """Tests for get_user_info action."""

    async def test_returns_user_info(self):
        """Test get_user_info returns profile data."""
        from ..tiktok import GetUserInfoHandler

        context = MockExecutionContext({
            "GET https://open.tiktokapis.com/v2/user/info/": MOCK_USER_INFO_RESPONSE,
        })

        handler = GetUserInfoHandler()
        result = await handler.execute({}, context)

        assert result.data["open_id"] == "test_open_id_123"
        assert result.data["display_name"] == "Test Creator"
        assert result.data["follower_count"] == 10000

    async def test_sends_correct_fields(self):
        """Test request includes correct fields parameter."""
        from ..tiktok import GetUserInfoHandler

        context = MockExecutionContext({
            "GET https://open.tiktokapis.com/v2/user/info/": MOCK_USER_INFO_RESPONSE,
        })

        handler = GetUserInfoHandler()
        await handler.execute({}, context)

        request = context.get_last_request()
        assert request is not None
        assert "open_id" in request["params"]["fields"]
        assert "follower_count" in request["params"]["fields"]


class TestGetCreatorInfoHandler:
    """Tests for get_creator_info action."""

    async def test_returns_creator_info(self):
        """Test get_creator_info returns capabilities."""
        from ..tiktok import GetCreatorInfoHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/creator_info/query/": MOCK_CREATOR_INFO_RESPONSE,
        })

        handler = GetCreatorInfoHandler()
        result = await handler.execute({}, context)

        assert result.data["creator_username"] == "testcreator"
        assert "PUBLIC_TO_EVERYONE" in result.data["privacy_level_options"]


class TestAPIErrorHandling:
    """Tests for API error handling across handlers."""

    async def test_get_user_info_handles_api_error(self):
        """Test get_user_info raises on API error."""
        from ..tiktok import GetUserInfoHandler

        context = MockExecutionContext({
            "GET https://open.tiktokapis.com/v2/user/info/": MOCK_ERROR_RESPONSE_INVALID_TOKEN,
        })

        handler = GetUserInfoHandler()
        with pytest.raises(TikTokAPIError) as exc_info:
            await handler.execute({}, context)
        assert exc_info.value.error_code == "access_token_invalid"

    async def test_create_video_post_handles_rate_limit(self):
        """Test create_video_post raises on rate limit."""
        from ..tiktok import CreateVideoPostHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/video/init/": MOCK_ERROR_RESPONSE_RATE_LIMIT,
        })

        handler = CreateVideoPostHandler()
        with pytest.raises(TikTokAPIError) as exc_info:
            await handler.execute({
                "source": "PULL_FROM_URL",
                "video_url": "https://example.com/video.mp4",
            }, context)
        assert exc_info.value.error_code == "rate_limit_exceeded"

    async def test_get_videos_handles_scope_error(self):
        """Test get_videos raises on scope not authorized."""
        from ..tiktok import GetVideosHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/video/list/": MOCK_ERROR_RESPONSE_SCOPE_NOT_AUTHORIZED,
        })

        handler = GetVideosHandler()
        with pytest.raises(TikTokAPIError) as exc_info:
            await handler.execute({}, context)
        assert exc_info.value.error_code == "scope_not_authorized"


class TestCreateVideoPostHandler:
    """Tests for create_video_post action."""

    async def test_creates_post_from_url(self):
        """Test creating video post from URL."""
        from ..tiktok import CreateVideoPostHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/video/init/": MOCK_VIDEO_INIT_RESPONSE,
        })

        handler = CreateVideoPostHandler()
        result = await handler.execute({
            "source": "PULL_FROM_URL",
            "video_url": "https://example.com/video.mp4",
            "title": "Test video #tiktok",
            "privacy_level": "PUBLIC_TO_EVERYONE",
        }, context)

        assert result.data["publish_id"] == "v_pub_123456789"
        assert result.data["status"] == "PROCESSING_DOWNLOAD"

    async def test_creates_post_file_upload(self):
        """Test creating video post with file upload."""
        from ..tiktok import CreateVideoPostHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/video/init/": MOCK_VIDEO_INIT_FILE_UPLOAD_RESPONSE,
        })

        handler = CreateVideoPostHandler()
        result = await handler.execute({
            "source": "FILE_UPLOAD",
            "video_size": 10 * 1024 * 1024,
        }, context)

        assert result.data["publish_id"] == "v_pub_123456789"
        assert result.data["upload_url"] is not None
        assert result.data["status"] == "PROCESSING_UPLOAD"

    async def test_validates_source_pull_from_url(self):
        """Test validation for PULL_FROM_URL without video_url."""
        from ..tiktok import CreateVideoPostHandler

        context = MockExecutionContext({})
        handler = CreateVideoPostHandler()

        with pytest.raises(ValueError, match="video_url is required"):
            await handler.execute({"source": "PULL_FROM_URL"}, context)

    async def test_sends_post_info(self):
        """Test request includes post_info with settings."""
        from ..tiktok import CreateVideoPostHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/video/init/": MOCK_VIDEO_INIT_RESPONSE,
        })

        handler = CreateVideoPostHandler()
        await handler.execute({
            "source": "PULL_FROM_URL",
            "video_url": "https://example.com/video.mp4",
            "title": "Test",
            "privacy_level": "SELF_ONLY",
            "disable_comment": True,
        }, context)

        request = context.get_last_request()
        assert request["json"]["post_info"]["privacy_level"] == "SELF_ONLY"
        assert request["json"]["post_info"]["disable_comment"] is True


class TestUploadVideoDraftHandler:
    """Tests for upload_video_draft action."""

    async def test_uploads_draft_from_url(self):
        """Test uploading draft from URL."""
        from ..tiktok import UploadVideoDraftHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/": MOCK_VIDEO_INIT_RESPONSE,
        })

        handler = UploadVideoDraftHandler()
        result = await handler.execute({
            "source": "PULL_FROM_URL",
            "video_url": "https://example.com/video.mp4",
        }, context)

        assert result.data["publish_id"] == "v_pub_123456789"


class TestGetPostStatusHandler:
    """Tests for get_post_status action."""

    async def test_returns_complete_status(self):
        """Test getting complete status."""
        from ..tiktok import GetPostStatusHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/status/fetch/": MOCK_POST_STATUS_COMPLETE_RESPONSE,
        })

        handler = GetPostStatusHandler()
        result = await handler.execute({"publish_id": "v_pub_123"}, context)

        assert result.data["status"] == "PUBLISH_COMPLETE"
        assert len(result.data["publicaly_available_post_id"]) > 0

    async def test_returns_failed_status(self):
        """Test getting failed status."""
        from ..tiktok import GetPostStatusHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/status/fetch/": MOCK_POST_STATUS_FAILED_RESPONSE,
        })

        handler = GetPostStatusHandler()
        result = await handler.execute({"publish_id": "v_pub_123"}, context)

        assert result.data["status"] == "FAILED"
        assert result.data["fail_reason"] == "Video format not supported"

    async def test_validates_publish_id(self):
        """Test validation for missing publish_id."""
        from ..tiktok import GetPostStatusHandler

        context = MockExecutionContext({})
        handler = GetPostStatusHandler()

        with pytest.raises(ValueError, match="publish_id is required"):
            await handler.execute({}, context)


class TestGetVideosHandler:
    """Tests for get_videos action."""

    async def test_returns_videos_list(self):
        """Test getting list of videos."""
        from ..tiktok import GetVideosHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/video/list/": MOCK_VIDEOS_LIST_RESPONSE,
        })

        handler = GetVideosHandler()
        result = await handler.execute({}, context)

        assert len(result.data["videos"]) == 2
        assert result.data["videos"][0]["id"] == "7123456789012345678"
        assert result.data["has_more"] is True
        assert result.data["cursor"] is not None

    async def test_respects_max_count(self):
        """Test max_count is capped at 20."""
        from ..tiktok import GetVideosHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/video/list/": MOCK_VIDEOS_LIST_RESPONSE,
        })

        handler = GetVideosHandler()
        await handler.execute({"max_count": 100}, context)

        request = context.get_last_request()
        assert request["json"]["max_count"] == 20


class TestCreatePhotoPostHandler:
    """Tests for create_photo_post action."""

    async def test_creates_photo_post(self):
        """Test creating photo post."""
        from ..tiktok import CreatePhotoPostHandler

        context = MockExecutionContext({
            "POST https://open.tiktokapis.com/v2/post/publish/content/init/": MOCK_PHOTO_POST_RESPONSE,
        })

        handler = CreatePhotoPostHandler()
        result = await handler.execute({
            "photo_urls": ["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"],
            "title": "Test photos",
        }, context)

        assert result.data["publish_id"] == "p_pub_987654321"

    async def test_validates_photo_urls_required(self):
        """Test validation for missing photo_urls."""
        from ..tiktok import CreatePhotoPostHandler

        context = MockExecutionContext({})
        handler = CreatePhotoPostHandler()

        with pytest.raises(ValueError, match="photo_urls is required"):
            await handler.execute({}, context)

    async def test_validates_max_photos(self):
        """Test validation for too many photos."""
        from ..tiktok import CreatePhotoPostHandler

        context = MockExecutionContext({})
        handler = CreatePhotoPostHandler()

        with pytest.raises(ValueError, match="Maximum 35 photos"):
            await handler.execute({
                "photo_urls": [f"https://example.com/photo{i}.jpg" for i in range(40)]
            }, context)


# =============================================================================
# Connected Account Handler Tests
# =============================================================================


class TestTikTokConnectedAccountHandler:
    """Tests for TikTok connected account handler."""

    async def test_returns_account_info(self):
        """Test connected account returns user info."""
        from ..tiktok import TikTokConnectedAccountHandler

        context = MockExecutionContext({
            "GET https://open.tiktokapis.com/v2/user/info/": MOCK_USER_INFO_RESPONSE,
        })

        handler = TikTokConnectedAccountHandler()
        result = await handler.get_account_info(context)

        assert result.user_id == "test_open_id_123"
        assert result.username == "testcreator"
        assert result.first_name == "Test Creator"
        assert result.avatar_url == "https://example.com/avatar.jpg"
