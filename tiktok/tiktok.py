"""
TikTok Integration for Autohive

Enables video posting, user profile management, and content analytics
via the official TikTok Content Posting API.
"""

import base64
from typing import Any, Dict, Optional

import aiohttp

from autohive_integrations_sdk import (
    ActionHandler,
    ActionResult,
    ConnectedAccountHandler,
    ConnectedAccountInfo,
    ExecutionContext,
    Integration,
)

# =============================================================================
# Constants
# =============================================================================

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"

# Endpoints
USER_INFO_ENDPOINT = f"{TIKTOK_API_BASE}/user/info/"
CREATOR_INFO_ENDPOINT = f"{TIKTOK_API_BASE}/post/publish/creator_info/query/"
VIDEO_INIT_ENDPOINT = f"{TIKTOK_API_BASE}/post/publish/video/init/"
INBOX_VIDEO_INIT_ENDPOINT = f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/"
PHOTO_INIT_ENDPOINT = f"{TIKTOK_API_BASE}/post/publish/content/init/"
STATUS_FETCH_ENDPOINT = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
VIDEO_LIST_ENDPOINT = f"{TIKTOK_API_BASE}/video/list/"

# User info fields
ALL_USER_INFO_FIELDS = [
    "open_id", "union_id", "avatar_url", "avatar_url_100", "avatar_large_url",
    "display_name", "bio_description", "profile_deep_link", "is_verified",
    "username", "follower_count", "following_count", "likes_count", "video_count"
]

# Video list fields
VIDEO_FIELDS = [
    "id", "title", "cover_image_url", "share_url", "create_time",
    "duration", "width", "height", "like_count", "comment_count",
    "share_count", "view_count"
]

# Chunk size limits (bytes)
MIN_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB

# Validation
MAX_VIDEO_SIZE = 287 * 1024 * 1024  # 287 MB (TikTok limit)
MAX_CAPTION_LENGTH = 2200


# =============================================================================
# Exceptions
# =============================================================================

class TikTokAPIError(Exception):
    """Exception raised for TikTok API errors."""

    def __init__(self, message: str, error_code: str = "", response: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.response = response


# =============================================================================
# Response Helpers
# =============================================================================

def _check_api_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Check API response for errors and extract data."""
    if "error" in response and response["error"]:
        error = response["error"]
        if isinstance(error, dict):
            code = error.get("code", "unknown_error")
            message = error.get("message", "Unknown error occurred")
            if code == "access_token_invalid":
                raise TikTokAPIError("Access token is invalid or expired.", error_code=code, response=response)
            elif code == "rate_limit_exceeded":
                raise TikTokAPIError("Rate limit exceeded.", error_code=code, response=response)
            elif code == "scope_not_authorized":
                raise TikTokAPIError("Required scope not authorized.", error_code=code, response=response)
            else:
                raise TikTokAPIError(f"TikTok API error: {message}", error_code=code, response=response)
        else:
            raise TikTokAPIError(f"TikTok API error: {error}", response=response)
    return response.get("data", response)


def _build_user_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize user info API response."""
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


def _build_creator_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize creator info API response."""
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


def _build_video(video: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize video object from API response."""
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


def _build_post_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize post status API response."""
    return {
        "status": data.get("status", ""),
        "fail_reason": data.get("fail_reason", ""),
        "publicaly_available_post_id": data.get("publicaly_available_post_id", []),
        "uploaded_bytes": data.get("uploaded_bytes", 0),
        "error_code": data.get("error_code", ""),
    }


# =============================================================================
# Validation Helpers
# =============================================================================

def _validate_video_content(video_content_base64: Optional[str]) -> bytes:
    """Validate and decode base64 video content."""
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


def _validate_chunk_size(chunk_size: int, video_size: int) -> int:
    """Validate and adjust chunk size for video uploads."""
    if video_size < MIN_CHUNK_SIZE:
        return video_size
    return max(MIN_CHUNK_SIZE, min(chunk_size, MAX_CHUNK_SIZE))


def _calculate_chunk_count(video_size: int, chunk_size: int) -> int:
    """Calculate the number of chunks needed for video upload."""
    if video_size <= chunk_size:
        return 1
    return (video_size + chunk_size - 1) // chunk_size


async def _upload_video_chunks(
    upload_url: str,
    video_data: bytes,
    chunk_size: int,
    access_token: str,
) -> None:
    """
    Upload video data in chunks to TikTok's upload URL.

    Args:
        upload_url: TikTok's presigned upload URL
        video_data: Raw video bytes
        chunk_size: Size of each chunk in bytes
        access_token: OAuth access token

    Raises:
        TikTokAPIError: If upload fails
    """
    video_size = len(video_data)
    total_chunks = _calculate_chunk_count(video_size, chunk_size)

    async with aiohttp.ClientSession() as session:
        for chunk_index in range(total_chunks):
            start = chunk_index * chunk_size
            end = min(start + chunk_size, video_size)
            chunk_data = video_data[start:end]

            # Content-Range header format: bytes start-end/total
            content_range = f"bytes {start}-{end - 1}/{video_size}"

            headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(chunk_data)),
                "Content-Range": content_range,
            }

            async with session.put(
                upload_url,
                data=chunk_data,
                headers=headers,
            ) as response:
                if response.status not in (200, 201, 206):
                    error_text = await response.text()
                    raise TikTokAPIError(
                        f"Failed to upload chunk {chunk_index + 1}/{total_chunks}: {error_text}",
                        error_code="upload_failed",
                    )


def _build_post_info(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build post_info object for video publishing."""
    post_info: Dict[str, Any] = {
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
    if inputs.get("brand_content_toggle"):
        post_info["brand_content_toggle"] = True
    if inputs.get("brand_organic_toggle"):
        post_info["brand_organic_toggle"] = True
    return post_info


# =============================================================================
# Integration Setup
# =============================================================================

tiktok = Integration.load()


# =============================================================================
# Connected Account Handler
# =============================================================================

@tiktok.connected_account()
class TikTokConnectedAccountHandler(ConnectedAccountHandler):
    """Handler for TikTok connected account information."""

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """Fetch and return the connected TikTok account information."""
        response = await context.fetch(
            USER_INFO_ENDPOINT,
            method="GET",
            params={"fields": "open_id,union_id,avatar_url,display_name,username"},
        )
        data = _check_api_response(response)
        user = data.get("user", data)
        return ConnectedAccountInfo(
            user_id=user.get("open_id", ""),
            username=user.get("username", user.get("display_name", "")),
            first_name=user.get("display_name", ""),
            last_name="",
            avatar_url=user.get("avatar_url", ""),
        )


# =============================================================================
# Action Handlers
# =============================================================================

@tiktok.action("get_user_info")
class GetUserInfoHandler(ActionHandler):
    """Get TikTok user profile information."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        response = await context.fetch(
            USER_INFO_ENDPOINT,
            method="GET",
            params={"fields": ",".join(ALL_USER_INFO_FIELDS)},
        )
        data = _check_api_response(response)
        return ActionResult(data=_build_user_info(data))


@tiktok.action("get_creator_info")
class GetCreatorInfoHandler(ActionHandler):
    """Get creator's posting capabilities."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        response = await context.fetch(CREATOR_INFO_ENDPOINT, method="POST", json={})
        data = _check_api_response(response)
        return ActionResult(data=_build_creator_info(data))


@tiktok.action("create_video_post")
class CreateVideoPostHandler(ActionHandler):
    """Post a video directly to TikTok."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        video_content_base64 = inputs.get("video_content_base64")

        # Validate and decode the video content
        video_data = _validate_video_content(video_content_base64)
        video_size = len(video_data)

        # Calculate chunk size
        chunk_size = _validate_chunk_size(
            inputs.get("chunk_size", DEFAULT_CHUNK_SIZE),
            video_size
        )

        # Initialize the upload with TikTok
        request_body: dict = {
            "post_info": _build_post_info(inputs),
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": _calculate_chunk_count(video_size, chunk_size),
            },
        }

        response = await context.fetch(VIDEO_INIT_ENDPOINT, method="POST", json=request_body)
        data = _check_api_response(response)

        publish_id = data.get("publish_id", "")
        upload_url = data.get("upload_url", "")

        if not upload_url:
            raise TikTokAPIError("No upload URL returned from TikTok", error_code="missing_upload_url")

        # Upload the video chunks
        access_token = context.auth.get("access_token", "")
        await _upload_video_chunks(upload_url, video_data, chunk_size, access_token)

        return ActionResult(data={
            "publish_id": publish_id,
            "status": "PROCESSING_UPLOAD",
        })


@tiktok.action("upload_video_draft")
class UploadVideoDraftHandler(ActionHandler):
    """Upload a video as a draft to TikTok inbox."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        video_content_base64 = inputs.get("video_content_base64")

        # Validate and decode the video content
        video_data = _validate_video_content(video_content_base64)
        video_size = len(video_data)

        # Calculate chunk size
        chunk_size = _validate_chunk_size(
            inputs.get("chunk_size", DEFAULT_CHUNK_SIZE),
            video_size
        )

        # Initialize the upload with TikTok
        request_body: dict = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": _calculate_chunk_count(video_size, chunk_size),
            },
        }

        response = await context.fetch(INBOX_VIDEO_INIT_ENDPOINT, method="POST", json=request_body)
        data = _check_api_response(response)

        publish_id = data.get("publish_id", "")
        upload_url = data.get("upload_url", "")

        if not upload_url:
            raise TikTokAPIError("No upload URL returned from TikTok", error_code="missing_upload_url")

        # Upload the video chunks
        access_token = context.auth.get("access_token", "")
        await _upload_video_chunks(upload_url, video_data, chunk_size, access_token)

        return ActionResult(data={
            "publish_id": publish_id,
            "status": "PROCESSING_UPLOAD",
        })


@tiktok.action("get_post_status")
class GetPostStatusHandler(ActionHandler):
    """Check video post status."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        publish_id = inputs.get("publish_id")
        if not publish_id:
            raise ValueError("publish_id is required")

        response = await context.fetch(STATUS_FETCH_ENDPOINT, method="POST", json={"publish_id": publish_id})
        data = _check_api_response(response)
        return ActionResult(data=_build_post_status(data))


@tiktok.action("get_videos")
class GetVideosHandler(ActionHandler):
    """List user's videos."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        max_count = min(inputs.get("max_count", 20), 20)
        request_body: dict = {"max_count": max_count, "fields": VIDEO_FIELDS}
        if inputs.get("cursor") is not None:
            request_body["cursor"] = inputs["cursor"]

        response = await context.fetch(VIDEO_LIST_ENDPOINT, method="POST", json=request_body)
        data = _check_api_response(response)

        return ActionResult(data={
            "videos": [_build_video(v) for v in data.get("videos", [])],
            "cursor": data.get("cursor"),
            "has_more": data.get("has_more", False),
        })


@tiktok.action("create_photo_post")
class CreatePhotoPostHandler(ActionHandler):
    """Post photos to TikTok."""

    async def execute(self, inputs: dict, context: ExecutionContext) -> ActionResult:
        photo_urls = inputs.get("photo_urls", [])
        if not photo_urls:
            raise ValueError("photo_urls is required and must contain at least one URL")
        if len(photo_urls) > 35:
            raise ValueError("Maximum 35 photos allowed per post")

        post_info: Dict[str, Any] = {
            "privacy_level": inputs.get("privacy_level", "PUBLIC_TO_EVERYONE"),
            "disable_comment": inputs.get("disable_comment", False),
        }
        if inputs.get("title"):
            post_info["title"] = inputs["title"][:MAX_CAPTION_LENGTH]
        if inputs.get("auto_add_music"):
            post_info["auto_add_music"] = True

        request_body = {
            "post_info": post_info,
            "source_info": {"source": "PULL_FROM_URL", "photo_images": photo_urls},
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO",
        }

        response = await context.fetch(PHOTO_INIT_ENDPOINT, method="POST", json=request_body)
        data = _check_api_response(response)

        return ActionResult(data={"publish_id": data.get("publish_id", ""), "status": "PROCESSING_DOWNLOAD"})
