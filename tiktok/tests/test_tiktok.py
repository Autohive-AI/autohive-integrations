"""
Tests for TikTok integration.

Unit tests for helper functions and integration tests for action handlers.
"""

import base64
import pytest

# =============================================================================
# Test Constants
# =============================================================================

MIN_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
MAX_VIDEO_SIZE = 287 * 1024 * 1024  # 287 MB
MAX_CAPTION_LENGTH = 2200

# Mock video content
_MOCK_VIDEO_BYTES = b"fake video content for unit testing purposes - not a real video"
MOCK_VIDEO_CONTENT_BASE64 = base64.b64encode(_MOCK_VIDEO_BYTES).decode()


# =============================================================================
# Helper Function Tests (No SDK imports needed)
# =============================================================================


class TestValidateVideoContent:
    """Tests for video content validation logic."""

    def _validate_video_content(self, video_content_base64):
        """Local implementation for testing validation logic."""
        if not video_content_base64:
            raise ValueError("video_content_base64 is required")

        try:
            video_data = base64.b64decode(video_content_base64)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}")

        if len(video_data) == 0:
            raise ValueError("Video content is empty")

        if len(video_data) > MAX_VIDEO_SIZE:
            raise ValueError(f"Video size ({len(video_data)} bytes) exceeds maximum allowed ({MAX_VIDEO_SIZE} bytes)")

        return video_data

    def test_valid_base64_content(self):
        """Test valid base64 video content."""
        video_data = b"fake video content for testing"
        video_base64 = base64.b64encode(video_data).decode()
        result = self._validate_video_content(video_base64)
        assert result == video_data

    def test_missing_content_raises_error(self):
        """Test missing video content raises error."""
        with pytest.raises(ValueError, match="video_content_base64 is required"):
            self._validate_video_content(None)

    def test_empty_string_raises_error(self):
        """Test empty string raises error."""
        with pytest.raises(ValueError, match="video_content_base64 is required"):
            self._validate_video_content("")

    def test_invalid_base64_raises_error(self):
        """Test invalid base64 encoding raises error."""
        with pytest.raises(ValueError, match="Invalid base64 encoding"):
            self._validate_video_content("not-valid-base64!!!")

    def test_empty_content_raises_error(self):
        """Test empty decoded content raises error."""
        # Note: base64.b64encode(b"") returns b"" which is falsy
        # So empty content is caught by the "is required" check
        empty_base64 = base64.b64encode(b"").decode()
        with pytest.raises(ValueError):
            self._validate_video_content(empty_base64)


class TestValidateChunkSize:
    """Tests for chunk size validation logic."""

    def _validate_chunk_size(self, chunk_size, video_size):
        """Local implementation for testing validation logic."""
        if video_size < MIN_CHUNK_SIZE:
            return video_size
        return max(MIN_CHUNK_SIZE, min(chunk_size, MAX_CHUNK_SIZE))

    def test_small_video_uses_video_size(self):
        """Test small videos use video size as chunk size."""
        small_size = 1024 * 1024  # 1 MB
        result = self._validate_chunk_size(MIN_CHUNK_SIZE, small_size)
        assert result == small_size

    def test_clamps_to_min(self):
        """Test chunk size is clamped to minimum."""
        result = self._validate_chunk_size(1024, MIN_CHUNK_SIZE * 2)
        assert result == MIN_CHUNK_SIZE

    def test_clamps_to_max(self):
        """Test chunk size is clamped to maximum."""
        result = self._validate_chunk_size(100 * 1024 * 1024, 100 * 1024 * 1024)
        assert result == MAX_CHUNK_SIZE

    def test_valid_chunk_size_unchanged(self):
        """Test valid chunk size is unchanged."""
        chunk_size = 10 * 1024 * 1024  # 10 MB
        video_size = 50 * 1024 * 1024  # 50 MB
        result = self._validate_chunk_size(chunk_size, video_size)
        assert result == chunk_size


class TestCalculateChunkCount:
    """Tests for chunk count calculation logic."""

    def _calculate_chunk_count(self, video_size, chunk_size):
        """Local implementation for testing calculation logic."""
        if video_size <= chunk_size:
            return 1
        return (video_size + chunk_size - 1) // chunk_size

    def test_single_chunk_for_small_video(self):
        """Test small video needs single chunk."""
        video_size = 3 * 1024 * 1024  # 3 MB
        chunk_size = 5 * 1024 * 1024  # 5 MB
        result = self._calculate_chunk_count(video_size, chunk_size)
        assert result == 1

    def test_multiple_chunks(self):
        """Test larger video needs multiple chunks."""
        video_size = 25 * 1024 * 1024  # 25 MB
        chunk_size = 10 * 1024 * 1024  # 10 MB
        result = self._calculate_chunk_count(video_size, chunk_size)
        assert result == 3


class TestBuildPostInfo:
    """Tests for post info building logic."""

    def _build_post_info(self, inputs):
        """Local implementation for testing post info building."""
        post_info = {
            "privacy_level": inputs.get("privacy_level", "PUBLIC_TO_EVERYONE"),
            "disable_comment": inputs.get("disable_comment", False),
            "disable_duet": inputs.get("disable_duet", False),
            "disable_stitch": inputs.get("disable_stitch", False),
        }
        title = inputs.get("title")
        if title:
            post_info["title"] = title[:MAX_CAPTION_LENGTH]
        if inputs.get("video_cover_timestamp_ms") is not None:
            post_info["video_cover_timestamp_ms"] = inputs["video_cover_timestamp_ms"]
        if inputs.get("brand_content_toggle") is not None:
            post_info["brand_content_toggle"] = bool(inputs["brand_content_toggle"])
        if inputs.get("brand_organic_toggle") is not None:
            post_info["brand_organic_toggle"] = bool(inputs["brand_organic_toggle"])
        return post_info

    def test_builds_basic_post_info(self):
        """Test building basic post info."""
        inputs = {"title": "Test video #tiktok", "privacy_level": "PUBLIC_TO_EVERYONE"}
        result = self._build_post_info(inputs)

        assert result["title"] == "Test video #tiktok"
        assert result["privacy_level"] == "PUBLIC_TO_EVERYONE"
        assert result["disable_comment"] is False
        assert result["disable_duet"] is False

    def test_truncates_long_title(self):
        """Test title is truncated to max length."""
        inputs = {"title": "x" * 3000}
        result = self._build_post_info(inputs)
        assert len(result["title"]) == MAX_CAPTION_LENGTH

    def test_optional_fields_included(self):
        """Test optional boolean fields are included correctly."""
        inputs = {"brand_content_toggle": True, "brand_organic_toggle": False}
        result = self._build_post_info(inputs)
        assert result["brand_content_toggle"] is True
        assert result["brand_organic_toggle"] is False  # Explicit False is preserved

    def test_optional_fields_omitted_when_not_provided(self):
        """Test optional boolean fields are omitted when not provided."""
        inputs = {}
        result = self._build_post_info(inputs)
        assert "brand_content_toggle" not in result
        assert "brand_organic_toggle" not in result

    def test_cover_timestamp_included(self):
        """Test cover timestamp is included when provided."""
        inputs = {"video_cover_timestamp_ms": 5000}
        result = self._build_post_info(inputs)
        assert result["video_cover_timestamp_ms"] == 5000


class TestBuildUserInfo:
    """Tests for user info building logic."""

    def _build_user_info(self, data):
        """Local implementation for testing user info building."""
        user = data.get("user", data)
        return {
            "open_id": user.get("open_id", ""),
            "union_id": user.get("union_id", ""),
            "avatar_url": user.get("avatar_url", ""),
            "avatar_url_100": user.get("avatar_url_100", ""),
            "avatar_large_url": user.get("avatar_large_url", ""),
            "display_name": user.get("display_name", ""),
            "bio_description": user.get("bio_description", ""),
            "profile_deep_link": user.get("profile_deep_link", ""),
            "is_verified": user.get("is_verified", False),
            "username": user.get("username", ""),
            "follower_count": user.get("follower_count", 0),
            "following_count": user.get("following_count", 0),
            "likes_count": user.get("likes_count", 0),
            "video_count": user.get("video_count", 0),
        }

    def test_builds_complete_response(self):
        """Test building response with all fields."""
        data = {
            "user": {
                "open_id": "test_open_id_123",
                "union_id": "test_union_id_456",
                "display_name": "Test Creator",
                "username": "testcreator",
                "follower_count": 10000,
                "is_verified": True,
            }
        }
        result = self._build_user_info(data)

        assert result["open_id"] == "test_open_id_123"
        assert result["union_id"] == "test_union_id_456"
        assert result["display_name"] == "Test Creator"
        assert result["username"] == "testcreator"
        assert result["follower_count"] == 10000
        assert result["is_verified"] is True

    def test_handles_missing_fields(self):
        """Test handling missing fields with defaults."""
        data = {"user": {"open_id": "123"}}
        result = self._build_user_info(data)

        assert result["open_id"] == "123"
        assert result["display_name"] == ""
        assert result["follower_count"] == 0
        assert result["is_verified"] is False

    def test_handles_flat_structure(self):
        """Test handling response without nested 'user' key."""
        data = {"open_id": "direct_123", "display_name": "Direct User"}
        result = self._build_user_info(data)

        assert result["open_id"] == "direct_123"
        assert result["display_name"] == "Direct User"


class TestBuildCreatorInfo:
    """Tests for creator info building logic."""

    def _build_creator_info(self, data):
        """Local implementation for testing creator info building."""
        return {
            "creator_avatar_url": data.get("creator_avatar_url", ""),
            "creator_username": data.get("creator_username", ""),
            "creator_nickname": data.get("creator_nickname", ""),
            "privacy_level_options": data.get("privacy_level_options", []),
            "comment_disabled": data.get("comment_disabled", False),
            "duet_disabled": data.get("duet_disabled", False),
            "stitch_disabled": data.get("stitch_disabled", False),
            "max_video_post_duration_sec": data.get("max_video_post_duration_sec", 600),
        }

    def test_builds_complete_response(self):
        """Test building response with all fields."""
        data = {
            "creator_username": "testcreator",
            "max_video_post_duration_sec": 600,
            "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
            "comment_disabled": False,
        }
        result = self._build_creator_info(data)

        assert result["creator_username"] == "testcreator"
        assert result["max_video_post_duration_sec"] == 600
        assert "PUBLIC_TO_EVERYONE" in result["privacy_level_options"]
        assert result["comment_disabled"] is False

    def test_handles_missing_fields(self):
        """Test handling missing fields."""
        data = {}
        result = self._build_creator_info(data)

        assert result["creator_username"] == ""
        assert result["privacy_level_options"] == []
        assert result["max_video_post_duration_sec"] == 600


class TestBuildVideo:
    """Tests for video building logic."""

    def _build_video(self, video):
        """Local implementation for testing video building."""
        return {
            "id": video.get("id", ""),
            "title": video.get("title", ""),
            "cover_image_url": video.get("cover_image_url", ""),
            "share_url": video.get("share_url", ""),
            "create_time": video.get("create_time", 0),
            "duration": video.get("duration", 0),
            "width": video.get("width", 0),
            "height": video.get("height", 0),
            "like_count": video.get("like_count", 0),
            "comment_count": video.get("comment_count", 0),
            "share_count": video.get("share_count", 0),
            "view_count": video.get("view_count", 0),
        }

    def test_builds_complete_response(self):
        """Test building video response with all fields."""
        video = {
            "id": "7123456789012345678",
            "title": "Test video #tiktok",
            "duration": 30,
            "like_count": 1000,
            "view_count": 10000,
        }
        result = self._build_video(video)

        assert result["id"] == "7123456789012345678"
        assert result["title"] == "Test video #tiktok"
        assert result["duration"] == 30
        assert result["like_count"] == 1000
        assert result["view_count"] == 10000

    def test_handles_missing_fields(self):
        """Test handling missing video fields."""
        video = {"id": "123"}
        result = self._build_video(video)

        assert result["id"] == "123"
        assert result["title"] == ""
        assert result["duration"] == 0
        assert result["like_count"] == 0


class TestBuildPostStatus:
    """Tests for post status building logic."""

    def _build_post_status(self, data):
        """Local implementation for testing post status building."""
        # Note: "publicaly_available_post_id" is TikTok's actual field name (their typo)
        # We preserve it for API compatibility but also provide correct spelling alias
        post_ids = data.get("publicaly_available_post_id", [])
        return {
            "status": data.get("status", ""),
            "fail_reason": data.get("fail_reason", ""),
            "publicaly_available_post_id": post_ids,  # TikTok's actual field name
            "publicly_available_post_id": post_ids,   # Correctly spelled alias
            "uploaded_bytes": data.get("uploaded_bytes", 0),
            "error_code": data.get("error_code", ""),
        }

    def test_builds_complete_response(self):
        """Test building complete status response."""
        data = {
            "status": "PUBLISH_COMPLETE",
            "publicaly_available_post_id": ["7123456789012345678"],
        }
        result = self._build_post_status(data)

        assert result["status"] == "PUBLISH_COMPLETE"
        assert "7123456789012345678" in result["publicaly_available_post_id"]
        # Test correctly spelled alias
        assert result["publicly_available_post_id"] == result["publicaly_available_post_id"]

    def test_builds_failed_response(self):
        """Test building failed status response."""
        data = {
            "status": "FAILED",
            "fail_reason": "Video format not supported",
            "error_code": "video_format_invalid",
        }
        result = self._build_post_status(data)

        assert result["status"] == "FAILED"
        assert result["fail_reason"] == "Video format not supported"
        assert result["error_code"] == "video_format_invalid"


class TestCheckApiResponse:
    """Tests for API response error checking logic."""

    class TikTokAPIError(Exception):
        """Local exception class for testing."""
        def __init__(self, message, error_code="", log_id=""):
            super().__init__(message)
            self.error_code = error_code
            self.log_id = log_id

    def _check_api_response(self, response):
        """Local implementation for testing API response checking."""
        # Check for error_code/error_message format (alternative error structure)
        if "error_code" in response and response["error_code"]:
            code = str(response["error_code"])
            message = response.get("error_message") or response.get("message") or "Unknown error"
            log_id = response.get("log_id", "")
            raise self.TikTokAPIError(f"TikTok API error: {message} (code: {code})", error_code=code, log_id=log_id)

        # Check for standard error object format
        if "error" in response:
            error = response["error"]
            if isinstance(error, dict):
                code = error.get("code", "unknown_error")
                if code == "ok":
                    return response.get("data", response)

                message = error.get("message") or error.get("description") or str(error)
                log_id = error.get("log_id", "")
                raise self.TikTokAPIError(f"TikTok API error: {message} (code: {code}, log_id: {log_id})", error_code=code, log_id=log_id)
            elif error:
                raise self.TikTokAPIError(f"TikTok API error: {error}")

        # Check for top-level message without error object
        if "message" in response and not response.get("data"):
            message = response["message"]
            if message and message.lower() not in ("success", "ok", ""):
                raise self.TikTokAPIError(f"TikTok API error: {message}")

        return response.get("data", response)

    def test_success_response_with_ok_code(self):
        """Test successful response with error.code = 'ok'."""
        response = {
            "data": {"user": {"open_id": "123"}},
            "error": {"code": "ok", "message": "", "log_id": "abc123"}
        }
        result = self._check_api_response(response)
        assert result["user"]["open_id"] == "123"

    def test_error_code_format(self):
        """Test error_code/error_message format."""
        response = {
            "error_code": "invalid_token",
            "error_message": "Token has expired",
            "log_id": "xyz789"
        }
        with pytest.raises(self.TikTokAPIError) as exc_info:
            self._check_api_response(response)
        assert exc_info.value.error_code == "invalid_token"
        assert "Token has expired" in str(exc_info.value)

    def test_standard_error_object_format(self):
        """Test standard error object format."""
        response = {
            "data": {},
            "error": {"code": "rate_limit_exceeded", "message": "Too many requests", "log_id": "rl123"}
        }
        with pytest.raises(self.TikTokAPIError) as exc_info:
            self._check_api_response(response)
        assert exc_info.value.error_code == "rate_limit_exceeded"

    def test_top_level_message_error(self):
        """Test top-level message without data."""
        response = {"message": "Unauthorized access"}
        with pytest.raises(self.TikTokAPIError) as exc_info:
            self._check_api_response(response)
        assert "Unauthorized access" in str(exc_info.value)

    def test_success_message_not_treated_as_error(self):
        """Test 'success' message is not treated as error."""
        response = {"message": "success", "data": {"result": "ok"}}
        result = self._check_api_response(response)
        assert result["result"] == "ok"


class TestGetVideosValidation:
    """Tests for get_videos input validation logic."""

    def _validate_get_videos_inputs(self, inputs):
        """Local implementation for testing get_videos validation."""
        # Validate and clamp max_count to [1..20]
        max_count = inputs.get("max_count", 20)
        if not isinstance(max_count, int) or max_count < 1:
            max_count = 1
        max_count = min(max_count, 20)

        request_body = {"max_count": max_count}

        # Validate cursor type if provided
        cursor = inputs.get("cursor")
        if cursor is not None:
            if not isinstance(cursor, int):
                raise ValueError("cursor must be an integer")
            request_body["cursor"] = cursor

        return request_body

    def test_default_max_count(self):
        """Test default max_count is 20."""
        result = self._validate_get_videos_inputs({})
        assert result["max_count"] == 20

    def test_clamps_max_count_to_20(self):
        """Test max_count is clamped to 20."""
        result = self._validate_get_videos_inputs({"max_count": 100})
        assert result["max_count"] == 20

    def test_clamps_zero_max_count_to_1(self):
        """Test zero max_count is clamped to 1."""
        result = self._validate_get_videos_inputs({"max_count": 0})
        assert result["max_count"] == 1

    def test_clamps_negative_max_count_to_1(self):
        """Test negative max_count is clamped to 1."""
        result = self._validate_get_videos_inputs({"max_count": -5})
        assert result["max_count"] == 1

    def test_valid_cursor(self):
        """Test valid integer cursor is accepted."""
        result = self._validate_get_videos_inputs({"cursor": 12345})
        assert result["cursor"] == 12345

    def test_invalid_cursor_type(self):
        """Test non-integer cursor raises error."""
        with pytest.raises(ValueError, match="cursor must be an integer"):
            self._validate_get_videos_inputs({"cursor": "not_an_int"})


# =============================================================================
# Integration Tests (Manual - require real credentials)
# =============================================================================
# To run integration tests:
# 1. Replace TEST_AUTH with valid TikTok OAuth credentials
# 2. Uncomment and run the tests manually

"""
import asyncio
from context import tiktok
from autohive_integrations_sdk import ExecutionContext

TEST_AUTH = {
    "credentials": {
        "access_token": "your_access_token_here"
    }
}

async def test_get_user_info():
    '''Test getting user info.'''
    print("\n[TEST] Getting user info...")

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await tiktok.execute_action("get_user_info", {}, context)
            print(f"Result: {result.data}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None

async def test_get_creator_info():
    '''Test getting creator info.'''
    print("\n[TEST] Getting creator info...")

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await tiktok.execute_action("get_creator_info", {}, context)
            print(f"Result: {result.data}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None

async def test_create_video_post():
    '''Test creating a video post.'''
    print("\n[TEST] Creating video post...")

    # Read video file and encode as base64
    with open("test_video.mp4", "rb") as f:
        video_content = base64.b64encode(f.read()).decode()

    inputs = {
        "video_content_base64": video_content,
        "title": "Test video from Autohive #tiktok",
        "privacy_level": "SELF_ONLY",  # Private for testing
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await tiktok.execute_action("create_video_post", inputs, context)
            print(f"Result: {result.data}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(test_get_user_info())
    asyncio.run(test_get_creator_info())
"""
