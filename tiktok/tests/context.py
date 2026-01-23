"""
Mock ExecutionContext for TikTok integration tests.
"""

from typing import Any, Dict, List, Optional


class MockExecutionContext:
    """Mock ExecutionContext that returns predefined responses for API calls."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        """
        Initialize mock context.

        Args:
            responses: Dictionary mapping request patterns to responses
        """
        self.auth = {"access_token": "mock_access_token"}
        self._responses = responses or {}
        self._requests: List[Dict[str, Any]] = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        timeout: Optional[int] = None,
        retry_count: int = 0,
    ) -> Any:
        """
        Mock fetch that records requests and returns predefined responses.

        Args:
            url: Request URL
            method: HTTP method
            params: Query parameters
            data: Form data
            json: JSON body
            headers: Request headers
            content_type: Content type
            timeout: Request timeout
            retry_count: Retry count

        Returns:
            Predefined response for the request pattern
        """
        # Record the request
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data,
            "json": json,
            "headers": headers,
        })

        # Find matching response
        request_key = f"{method} {url}"

        # Try exact match first
        if request_key in self._responses:
            return self._responses[request_key]

        # Try URL pattern matching
        for pattern, response in self._responses.items():
            pattern_method, pattern_url = pattern.split(" ", 1)
            if pattern_method == method and pattern_url in url:
                return response

        # Default empty response
        return {"data": {}}

    def get_requests(self) -> List[Dict[str, Any]]:
        """Get list of recorded requests."""
        return self._requests

    def get_last_request(self) -> Optional[Dict[str, Any]]:
        """Get the last recorded request."""
        return self._requests[-1] if self._requests else None

    def clear_requests(self) -> None:
        """Clear recorded requests."""
        self._requests.clear()


# Common mock responses for tests
MOCK_USER_INFO_RESPONSE = {
    "data": {
        "user": {
            "open_id": "test_open_id_123",
            "union_id": "test_union_id_456",
            "avatar_url": "https://example.com/avatar.jpg",
            "avatar_url_100": "https://example.com/avatar_100.jpg",
            "avatar_large_url": "https://example.com/avatar_large.jpg",
            "display_name": "Test Creator",
            "bio_description": "Test bio description",
            "profile_deep_link": "https://www.tiktok.com/@testcreator",
            "is_verified": True,
            "username": "testcreator",
            "follower_count": 10000,
            "following_count": 500,
            "likes_count": 50000,
            "video_count": 100,
        }
    }
}

MOCK_CREATOR_INFO_RESPONSE = {
    "data": {
        "creator_avatar_url": "https://example.com/avatar.jpg",
        "creator_username": "testcreator",
        "creator_nickname": "Test Creator",
        "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
        "comment_disabled": False,
        "duet_disabled": False,
        "stitch_disabled": False,
        "max_video_post_duration_sec": 600,
    }
}

MOCK_VIDEO_INIT_RESPONSE = {
    "data": {
        "publish_id": "v_pub_123456789",
    }
}

MOCK_VIDEO_INIT_FILE_UPLOAD_RESPONSE = {
    "data": {
        "publish_id": "v_pub_123456789",
        "upload_url": "https://upload.tiktokapis.com/video/?upload_id=abc123",
    }
}

MOCK_POST_STATUS_PROCESSING_RESPONSE = {
    "data": {
        "status": "PROCESSING_DOWNLOAD",
        "uploaded_bytes": 0,
    }
}

MOCK_POST_STATUS_COMPLETE_RESPONSE = {
    "data": {
        "status": "PUBLISH_COMPLETE",
        "publicaly_available_post_id": ["7123456789012345678"],
    }
}

MOCK_POST_STATUS_FAILED_RESPONSE = {
    "data": {
        "status": "FAILED",
        "fail_reason": "Video format not supported",
        "error_code": "video_format_invalid",
    }
}

MOCK_VIDEOS_LIST_RESPONSE = {
    "data": {
        "videos": [
            {
                "id": "7123456789012345678",
                "title": "Test video #tiktok",
                "cover_image_url": "https://example.com/cover1.jpg",
                "share_url": "https://www.tiktok.com/@testcreator/video/7123456789012345678",
                "create_time": 1706000000,
                "duration": 30,
                "width": 1080,
                "height": 1920,
                "like_count": 1000,
                "comment_count": 50,
                "share_count": 25,
                "view_count": 10000,
            },
            {
                "id": "7123456789012345679",
                "title": "Another test video",
                "cover_image_url": "https://example.com/cover2.jpg",
                "share_url": "https://www.tiktok.com/@testcreator/video/7123456789012345679",
                "create_time": 1705900000,
                "duration": 45,
                "width": 1080,
                "height": 1920,
                "like_count": 500,
                "comment_count": 20,
                "share_count": 10,
                "view_count": 5000,
            },
        ],
        "cursor": 1705900000,
        "has_more": True,
    }
}

MOCK_PHOTO_POST_RESPONSE = {
    "data": {
        "publish_id": "p_pub_987654321",
    }
}

# Error responses
MOCK_ERROR_RESPONSE_INVALID_TOKEN = {
    "error": {
        "code": "access_token_invalid",
        "message": "The access token is invalid or has expired.",
    }
}

MOCK_ERROR_RESPONSE_RATE_LIMIT = {
    "error": {
        "code": "rate_limit_exceeded",
        "message": "You have exceeded the rate limit.",
    }
}

MOCK_ERROR_RESPONSE_SCOPE_NOT_AUTHORIZED = {
    "error": {
        "code": "scope_not_authorized",
        "message": "The required scope is not authorized.",
    }
}

MOCK_ERROR_RESPONSE_GENERIC = {
    "error": {
        "code": "spam_risk_too_many_posts",
        "message": "Too many posts in a short period.",
    }
}
