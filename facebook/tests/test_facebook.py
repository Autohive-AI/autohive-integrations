"""
Tests for Facebook Pages Integration

Tests all 12 actions with mocked API responses to verify correct behavior
without making actual Facebook API calls.
"""

import time
from typing import Any

import pytest

from context import facebook

pytestmark = pytest.mark.asyncio


class MockExecutionContext:
    """
    Mock execution context that simulates Facebook Graph API responses.
    
    Routes requests based on URL patterns and HTTP methods to return
    pre-configured responses for testing.
    """
    
    def __init__(self, responses: dict[str, Any]):
        self.auth = {}
        self._responses = responses
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data
        })
        
        if "/me/accounts" in url and method == "GET":
            return self._responses.get("GET /me/accounts", {"data": []})
        
        # Handle GET /{page_id}?fields=access_token for page token retrieval
        if method == "GET" and params and params.get("fields") == "access_token":
            return self._responses.get("GET /page_token", {"access_token": "page_token_123"})
        

        
        if "/feed" in url and method == "POST":
            return self._responses.get("POST /feed", {"id": ""})
        
        if "/posts" in url and method == "GET":
            return self._responses.get("GET /posts", {"data": []})
        
        if "/photos" in url and method == "POST":
            return self._responses.get("POST /photos", {"id": ""})
        
        if "/videos" in url and method == "POST":
            return self._responses.get("POST /videos", {"id": ""})
        
        if "/comments" in url and method == "GET":
            return self._responses.get("GET /comments", {"data": [], "summary": {"total_count": 0}})
        
        if "/comments" in url and method == "POST":
            return self._responses.get("POST /comments", {"id": ""})
        
        if "/insights" in url and method == "GET":
            return self._responses.get("GET /insights", {"data": []})
        
        if "/events" in url and method == "GET":
            return self._responses.get("GET /events", {"data": []})
        
        if "/events" in url and method == "POST":
            return self._responses.get("POST /events", {"id": ""})
        
        if method == "DELETE":
            return self._responses.get("DELETE", {"success": True})
        
        if method == "POST" and "is_hidden" in str(data):
            return self._responses.get("POST /hide", {"success": True})
        
        single_post = self._responses.get("GET /post")
        if single_post and method == "GET":
            return single_post
        
        return {}


# =============================================================================
# LIST PAGES TESTS
# =============================================================================

async def test_list_pages_success():
    """Test listing pages returns correct structure."""
    responses = {
        "GET /me/accounts": {
            "data": [
                {
                    "id": "123456789",
                    "name": "My Business Page",
                    "category": "Business",
                    "followers_count": 5000
                },
                {
                    "id": "987654321",
                    "name": "My Personal Brand",
                    "category": "Personal Blog",
                    "followers_count": 1200
                }
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("list_pages", {}, context)
    data = result.result.data

    assert "pages" in data
    assert len(data["pages"]) == 2
    assert data["pages"][0]["id"] == "123456789"
    assert data["pages"][0]["name"] == "My Business Page"
    assert data["pages"][0]["category"] == "Business"
    assert data["pages"][0]["followers_count"] == 5000


async def test_list_pages_empty():
    """Test listing pages when user has no pages."""
    responses = {
        "GET /me/accounts": {"data": []}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("list_pages", {}, context)
    data = result.result.data

    assert "pages" in data
    assert len(data["pages"]) == 0


# =============================================================================
# GET POSTS TESTS
# =============================================================================

async def test_get_posts_list():
    """Test listing multiple posts from a page."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /posts": {
            "data": [
                {
                    "id": "123456789_111",
                    "message": "First post",
                    "created_time": "2024-01-01T10:00:00+0000",
                    "permalink_url": "https://facebook.com/123456789_111"
                },
                {
                    "id": "123456789_222",
                    "message": "Second post",
                    "created_time": "2024-01-02T10:00:00+0000",
                    "permalink_url": "https://facebook.com/123456789_222"
                }
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_posts", {
        "page_id": "123456789"
    }, context)
    data = result.result.data

    assert "posts" in data
    assert len(data["posts"]) == 2
    assert data["posts"][0]["id"] == "123456789_111"
    assert data["posts"][0]["message"] == "First post"


async def test_get_posts_single():
    """Test fetching a single post by ID."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /post": {
            "id": "123456789_111",
            "message": "Specific post",
            "created_time": "2024-01-01T10:00:00+0000",
            "permalink_url": "https://facebook.com/123456789_111"
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_posts", {
        "page_id": "123456789",
        "post_id": "123456789_111"
    }, context)
    data = result.result.data

    assert "posts" in data
    assert len(data["posts"]) == 1
    assert data["posts"][0]["id"] == "123456789_111"


# =============================================================================
# CREATE POST TESTS
# =============================================================================

async def test_create_post_text():
    """Test creating a simple text post."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /feed": {"id": "123456789_111222333"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "Hello, this is a test post!"
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_111222333"
    assert "facebook.com" in data["permalink_url"]
    assert data["is_scheduled"] == False


async def test_create_post_with_link():
    """Test creating a post with a link."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /feed": {"id": "123456789_444555666"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "Check out our website!",
        "media_type": "link",
        "media_url": "https://example.com"
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_444555666"
    assert data["is_scheduled"] == False


async def test_create_post_photo():
    """Test creating a photo post."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /photos": {"id": "123456789_photo123"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "Check out this image!",
        "media_type": "photo",
        "media_url": "https://example.com/image.jpg"
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_photo123"


async def test_create_post_video():
    """Test creating a video post."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /videos": {"id": "123456789_video123"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "Watch this video!",
        "media_type": "video",
        "media_url": "https://example.com/video.mp4"
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_video123"


async def test_create_post_scheduled_unix_timestamp():
    """Test scheduling a post with Unix timestamp as string."""
    future_time = int(time.time()) + 3600  # 1 hour from now
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /feed": {"id": "123456789_777888999"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "This post will be published later!",
        "scheduled_time": str(future_time)
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_777888999"
    assert data["is_scheduled"] == True
    assert data["scheduled_time"] == future_time


async def test_create_post_scheduled_iso_format():
    """Test scheduling a post with ISO 8601 format."""
    from datetime import datetime, timezone, timedelta
    future_dt = datetime.now(timezone.utc) + timedelta(hours=2)
    future_iso = future_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /feed": {"id": "123456789_888999000"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("create_post", {
        "page_id": "123456789",
        "message": "Scheduled with ISO format!",
        "scheduled_time": future_iso
    }, context)
    data = result.result.data

    assert data["post_id"] == "123456789_888999000"
    assert data["is_scheduled"] == True


async def test_create_post_scheduled_too_soon():
    """Test error when scheduling less than 10 minutes in future."""
    too_soon = int(time.time()) + 60  # 1 minute from now
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Too soon!",
            "scheduled_time": str(too_soon)
        }, context)
        assert False, "Should have raised exception"
    except ValueError as e:
        assert "at least 10 minutes" in str(e)


async def test_create_post_scheduled_too_far():
    """Test error when scheduling more than 75 days in future."""
    too_far = int(time.time()) + (76 * 24 * 60 * 60)  # 76 days from now
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Too far in future!",
            "scheduled_time": str(too_far)
        }, context)
        assert False, "Should have raised exception"
    except ValueError as e:
        assert "within 75 days" in str(e)


async def test_create_post_scheduled_invalid_format():
    """Test error when scheduled_time has invalid format."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Invalid format!",
            "scheduled_time": "not-a-valid-time"
        }, context)
        assert False, "Should have raised exception"
    except ValueError as e:
        assert "Invalid scheduled_time format" in str(e)


async def test_create_post_page_not_found():
    """Test error when page doesn't exist or user lacks permission."""
    responses = {
        "GET /page_token": {}  # No access_token returned = no permission
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "nonexistent_page",
            "message": "This should fail"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "failed to retrieve" in str(e).lower() or "permission" in str(e).lower()


async def test_create_post_photo_missing_url():
    """Test error when photo post missing media_url."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Missing photo URL",
            "media_type": "photo"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "media_url is required" in str(e)


async def test_create_post_video_missing_url():
    """Test error when video post missing media_url."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Missing video URL",
            "media_type": "video"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "media_url is required" in str(e)


async def test_create_post_link_missing_url():
    """Test error when link post missing media_url."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("create_post", {
            "page_id": "123456789",
            "message": "Missing link URL",
            "media_type": "link"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "media_url is required" in str(e)


# =============================================================================
# DELETE POST TESTS
# =============================================================================

async def test_delete_post_success():
    """Test successfully deleting a post."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "DELETE": {"success": True}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("delete_post", {
        "page_id": "123456789",
        "post_id": "123456789_111"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["deleted_post_id"] == "123456789_111"


# =============================================================================
# GET COMMENTS TESTS
# =============================================================================

async def test_get_comments_success():
    """Test fetching comments on a post."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /comments": {
            "data": [
                {
                    "id": "123456789_111_c1",
                    "message": "Great post!",
                    "from": {"id": "user1", "name": "John Doe"},
                    "created_time": "2024-01-01T12:00:00+0000",
                    "is_hidden": False,
                    "comment_count": 2
                },
                {
                    "id": "123456789_111_c2",
                    "message": "Thanks for sharing",
                    "from": {"id": "user2", "name": "Jane Smith"},
                    "created_time": "2024-01-01T13:00:00+0000",
                    "is_hidden": False,
                    "comment_count": 0
                }
            ],
            "summary": {"total_count": 2}
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_comments", {
        "post_id": "123456789_111"
    }, context)
    data = result.result.data

    assert "comments" in data
    assert len(data["comments"]) == 2
    assert data["comments"][0]["message"] == "Great post!"
    assert data["comments"][0]["from_name"] == "John Doe"
    assert data["comments"][0]["reply_count"] == 2
    assert data["total_count"] == 2


async def test_get_comments_include_hidden():
    """Test fetching comments including hidden ones."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /comments": {
            "data": [
                {
                    "id": "123456789_111_c1",
                    "message": "Visible comment",
                    "from": {"id": "user1", "name": "John Doe"},
                    "created_time": "2024-01-01T12:00:00+0000",
                    "is_hidden": False,
                    "comment_count": 0
                },
                {
                    "id": "123456789_111_c2",
                    "message": "Hidden comment",
                    "from": {"id": "user2", "name": "Spammer"},
                    "created_time": "2024-01-01T13:00:00+0000",
                    "is_hidden": True,
                    "comment_count": 0
                }
            ],
            "summary": {"total_count": 2}
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_comments", {
        "post_id": "123456789_111",
        "include_hidden": True
    }, context)
    data = result.result.data

    assert len(data["comments"]) == 2
    assert data["comments"][1]["is_hidden"] == True


# =============================================================================
# MANAGE COMMENT TESTS
# =============================================================================

async def test_manage_comment_reply():
    """Test replying to a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /comments": {"id": "123456789_111_c1_reply1"}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("manage_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1",
        "action": "reply",
        "message": "Thank you for your comment!"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["action_taken"] == "reply"
    assert data["reply_id"] == "123456789_111_c1_reply1"


async def test_manage_comment_hide():
    """Test hiding a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /hide": {"success": True}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("manage_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1",
        "action": "hide"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["action_taken"] == "hide"
    assert data["is_hidden"] == True


async def test_manage_comment_unhide():
    """Test unhiding a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "POST /hide": {"success": True}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("manage_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1",
        "action": "unhide"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["action_taken"] == "unhide"
    assert data["is_hidden"] == False


async def test_manage_comment_like():
    """Test liking a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("manage_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1",
        "action": "like"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["action_taken"] == "like"


async def test_manage_comment_unlike():
    """Test unliking a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("manage_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1",
        "action": "unlike"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["action_taken"] == "unlike"


async def test_manage_comment_reply_missing_message():
    """Test error when reply action missing message."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("manage_comment", {
            "page_id": "123456789",
            "comment_id": "123456789_111_c1",
            "action": "reply"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "message is required" in str(e)


async def test_manage_comment_invalid_action():
    """Test error when using invalid action."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        }
    }
    context = MockExecutionContext(responses)
    
    try:
        await facebook.execute_action("manage_comment", {
            "page_id": "123456789",
            "comment_id": "123456789_111_c1",
            "action": "invalid_action"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "is not one of" in str(e) or "Unknown action" in str(e)


# =============================================================================
# DELETE COMMENT TESTS
# =============================================================================

async def test_delete_comment_success():
    """Test successfully deleting a comment."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "DELETE": {"success": True}
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("delete_comment", {
        "page_id": "123456789",
        "comment_id": "123456789_111_c1"
    }, context)
    data = result.result.data

    assert data["success"] == True
    assert data["deleted_comment_id"] == "123456789_111_c1"


# =============================================================================
# GET INSIGHTS TESTS
# =============================================================================

async def test_get_insights_page():
    """Test fetching page-level insights."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /insights": {
            "data": [
                {"name": "page_impressions", "values": [{"value": 15000}]},
                {"name": "page_engaged_users", "values": [{"value": 500}]},
                {"name": "page_fans", "values": [{"value": 10000}]}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_insights", {
        "target_type": "page",
        "target_id": "123456789"
    }, context)
    data = result.result.data

    assert data["target_type"] == "page"
    assert data["target_id"] == "123456789"
    assert data["metrics"]["page_impressions"] == 15000
    assert data["metrics"]["page_engaged_users"] == 500
    assert data["metrics"]["page_fans"] == 10000


async def test_get_insights_post():
    """Test fetching post-level insights."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /insights": {
            "data": [
                {"name": "post_impressions", "values": [{"value": 5000}]},
                {"name": "post_engaged_users", "values": [{"value": 200}]}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_insights", {
        "target_type": "post",
        "target_id": "123456789_111"
    }, context)
    data = result.result.data

    assert data["target_type"] == "post"
    assert data["target_id"] == "123456789_111"
    assert data["metrics"]["post_impressions"] == 5000
    assert data["metrics"]["post_engaged_users"] == 200


async def test_get_insights_custom_metrics():
    """Test fetching insights with custom metrics."""
    responses = {
        "GET /me/accounts": {
            "data": [{"id": "123456789", "access_token": "page_token_123"}]
        },
        "GET /insights": {
            "data": [
                {"name": "page_views_total", "values": [{"value": 25000}]},
                {"name": "page_fan_adds", "values": [{"value": 150}]}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await facebook.execute_action("get_insights", {
        "target_type": "page",
        "target_id": "123456789",
        "metrics": ["page_views_total", "page_fan_adds"]
    }, context)
    data = result.result.data

    assert data["metrics"]["page_views_total"] == 25000
    assert data["metrics"]["page_fan_adds"] == 150
