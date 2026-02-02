"""
Tests for LinkedIn Integration

Tests all actions with mocked API responses to verify correct behavior
without making actual LinkedIn API calls.
"""

from typing import Any
from unittest.mock import patch, AsyncMock
from urllib.parse import quote

import pytest

from context import linkedin, linkedin_module

pytestmark = pytest.mark.asyncio


class MockExecutionContext:
    """
    Mock execution context that simulates LinkedIn API responses.

    Routes requests based on URL patterns and HTTP methods to return
    pre-configured responses for testing.
    """

    def __init__(self, responses: dict[str, Any] = None):
        self.auth = {}
        self._responses = responses or {}
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data,
            "json": json,
            "headers": headers
        })

        # Userinfo endpoint
        if "/userinfo" in url and method == "GET":
            return self._responses.get("GET /userinfo", {
                "sub": "abc123",
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User",
                "picture": "https://media.licdn.com/pic.jpg",
                "locale": {"country": "US", "language": "en"},
                "email": "test@example.com",
                "email_verified": True
            })

        # Posts endpoint - CREATE
        if "/rest/posts" in url and method == "POST" and "X-RestLi-Method" not in (headers or {}):
            return self._responses.get("POST /posts", {
                "id": "urn:li:share:123456789",
                "author": "urn:li:person:abc123",
                "lifecycleState": "PUBLISHED",
                "visibility": "PUBLIC",
                "commentary": "Test post",
                "createdAt": 1705849200000,
                "publishedAt": 1705849200000
            })

        # Posts endpoint - GET single
        if "/rest/posts/" in url and method == "GET":
            return self._responses.get("GET /posts/{urn}", {
                "id": "urn:li:share:123456789",
                "author": "urn:li:person:abc123",
                "lifecycleState": "PUBLISHED",
                "visibility": "PUBLIC",
                "commentary": "Test post content",
                "createdAt": 1705849200000,
                "publishedAt": 1705849200000,
                "lastModifiedAt": 1705849200000
            })

        # Posts endpoint - GET list (finder)
        if "/rest/posts?" in url and method == "GET":
            return self._responses.get("GET /posts", {
                "elements": [
                    {
                        "id": "urn:li:share:111",
                        "author": "urn:li:person:abc123",
                        "commentary": "Post 1",
                        "visibility": "PUBLIC",
                        "lifecycleState": "PUBLISHED"
                    },
                    {
                        "id": "urn:li:share:222",
                        "author": "urn:li:person:abc123",
                        "commentary": "Post 2",
                        "visibility": "PUBLIC",
                        "lifecycleState": "PUBLISHED"
                    }
                ],
                "paging": {"start": 0, "count": 10}
            })

        # Posts endpoint - UPDATE
        if "/rest/posts/" in url and method == "POST" and headers and headers.get("X-RestLi-Method") == "PARTIAL_UPDATE":
            return self._responses.get("PATCH /posts", {})

        # Posts endpoint - DELETE
        if "/rest/posts/" in url and method == "DELETE":
            return self._responses.get("DELETE /posts", {})

        # Comments endpoint - GET
        if "/socialActions/" in url and "/comments" in url and method == "GET":
            return self._responses.get("GET /comments", {
                "elements": [
                    {
                        "id": "comment123",
                        "actor": "urn:li:person:commenter1",
                        "message": {"text": "Great post!"},
                        "created": {"time": 1705849200000}
                    }
                ],
                "paging": {"start": 0, "count": 10}
            })

        # Comments endpoint - CREATE
        if "/socialActions/" in url and "/comments" in url and method == "POST":
            return self._responses.get("POST /comments", {
                "id": "comment456",
                "actor": "urn:li:person:abc123",
                "message": {"text": "Test comment"},
                "object": "urn:li:activity:123456"
            })

        # Comments endpoint - DELETE
        if "/socialActions/" in url and "/comments/" in url and method == "DELETE":
            return self._responses.get("DELETE /comments", {})

        # Reactions endpoint - GET
        if "/rest/reactions/(entity:" in url and method == "GET":
            return self._responses.get("GET /reactions", {
                "elements": [
                    {
                        "id": "urn:li:reaction:(urn:li:person:user1,urn:li:activity:123)",
                        "reactionType": "LIKE",
                        "created": {"time": 1705849200000}
                    }
                ],
                "paging": {"start": 0, "count": 10, "total": 1}
            })

        # Reactions endpoint - CREATE
        if "/rest/reactions?" in url and method == "POST":
            return self._responses.get("POST /reactions", {
                "id": "urn:li:reaction:(urn:li:person:abc123,urn:li:activity:123)",
                "reactionType": "LIKE",
                "created": {"time": 1705849200000}
            })

        # Reactions endpoint - DELETE
        if "/rest/reactions/(actor:" in url and method == "DELETE":
            return self._responses.get("DELETE /reactions", {})

        # Images endpoint - Initialize upload
        if "/rest/images?action=initializeUpload" in url and method == "POST":
            # Generate a unique image URN based on the number of image init calls
            image_count = len([r for r in self._requests if "initializeUpload" in r["url"]])
            return self._responses.get("POST /images/initializeUpload", {
                "value": {
                    "uploadUrl": f"https://api.linkedin.com/upload/image{image_count}",
                    "image": f"urn:li:image:{image_count}"
                }
            })

        # Images endpoint - Binary upload
        if "api.linkedin.com/upload/" in url and method == "PUT":
            return self._responses.get("PUT /images/upload", {})

        return {}


# =============================================================================
# GET USER INFO TESTS
# =============================================================================

async def test_get_user_info_success():
    """Test getting user info returns correct structure."""
    responses = {
        "GET /userinfo": {
            "sub": "user123",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://media.licdn.com/profile.jpg",
            "locale": {"country": "US", "language": "en"},
            "email": "john.doe@example.com",
            "email_verified": True
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_user_info", {}, context)
    data = result.result.data

    assert data["result"] == "User information retrieved successfully."
    assert data["user_info"]["sub"] == "user123"
    assert data["user_info"]["name"] == "John Doe"
    assert data["user_info"]["given_name"] == "John"
    assert data["user_info"]["family_name"] == "Doe"
    assert data["user_info"]["email"] == "john.doe@example.com"
    assert data["user_info"]["email_verified"] == True


async def test_get_user_info_without_email():
    """Test getting user info when email scope not granted."""
    responses = {
        "GET /userinfo": {
            "sub": "user456",
            "name": "Jane Smith",
            "given_name": "Jane",
            "family_name": "Smith",
            "picture": "https://media.licdn.com/jane.jpg",
            "locale": {"country": "GB", "language": "en"}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_user_info", {}, context)
    data = result.result.data

    assert data["result"] == "User information retrieved successfully."
    assert data["user_info"]["sub"] == "user456"
    assert data["user_info"]["name"] == "Jane Smith"
    assert "email" not in data["user_info"]


async def test_get_user_info_error():
    """Test handling error response from userinfo endpoint."""
    responses = {
        "GET /userinfo": {
            "error": "invalid_token",
            "error_description": "The access token is invalid"
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_user_info", {}, context)
    data = result.result.data

    assert data["result"] == "Failed to retrieve user information."
    assert data["user_info"] is None


# =============================================================================
# SHARE CONTENT TESTS
# =============================================================================

# =============================================================================
# SHARE ARTICLE TESTS
# =============================================================================

@patch.object(linkedin_module, 'post_to_linkedin')
async def test_share_article_success(mock_post):
    """Test sharing an article successfully."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:article123"}, None)

    responses = {
        "GET /userinfo": {"sub": "article_user", "name": "Article User"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("share_article", {
        "article_url": "https://example.com/article",
        "article_title": "Test Article",
        "article_description": "Article description",
        "commentary": "Check out this article!"
    }, context)
    data = result.result.data

    assert data["result"] == "Article shared successfully."
    assert data["post_id"] == "urn:li:share:article123"
    assert data["post_url"] == "https://www.linkedin.com/feed/update/urn:li:share:article123"

    # Verify article content in payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["content"]["article"]["source"] == "https://example.com/article"
    assert payload["content"]["article"]["title"] == "Test Article"
    assert payload["commentary"] == "Check out this article!"


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_share_article_minimal(mock_post):
    """Test sharing article with only required fields."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:min_article"}, None)

    responses = {
        "GET /userinfo": {"sub": "min_user", "name": "Min User"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("share_article", {
        "article_url": "https://example.com/min",
        "article_title": "Minimal Article"
    }, context)
    data = result.result.data

    assert data["result"] == "Article shared successfully."

    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["commentary"] == ""  # Default empty
    assert payload["content"]["article"]["description"] == ""  # Default empty


# =============================================================================
# RESHARE POST TESTS
# =============================================================================

@patch.object(linkedin_module, 'post_to_linkedin')
async def test_reshare_post_success(mock_post):
    """Test resharing a post successfully."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:reshare123"}, None)

    responses = {
        "GET /userinfo": {"sub": "reshare_user", "name": "Reshare User"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("reshare_post", {
        "original_post_urn": "urn:li:share:original123",
        "commentary": "Great post!"
    }, context)
    data = result.result.data

    assert data["result"] == "Post reshared successfully."
    assert data["post_id"] == "urn:li:share:reshare123"
    assert data["post_url"] == "https://www.linkedin.com/feed/update/urn:li:share:reshare123"

    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["reshareContext"]["parent"] == "urn:li:share:original123"
    assert payload["commentary"] == "Great post!"


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_reshare_post_no_commentary(mock_post):
    """Test resharing without commentary."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:reshare456"}, None)

    responses = {
        "GET /userinfo": {"sub": "reshare_user2", "name": "Reshare User 2"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("reshare_post", {
        "original_post_urn": "urn:li:share:original456"
    }, context)
    data = result.result.data

    assert data["result"] == "Post reshared successfully."

    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["commentary"] == ""  # Default empty


# =============================================================================
# GET POST TESTS
# =============================================================================

async def test_get_post_success():
    """Test retrieving a single post."""
    responses = {
        "GET /posts/{urn}": {
            "id": "urn:li:share:get123",
            "author": "urn:li:person:author123",
            "commentary": "Retrieved post content",
            "visibility": "PUBLIC",
            "lifecycleState": "PUBLISHED",
            "createdAt": 1705849200000
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_post", {
        "post_urn": "urn:li:share:get123"
    }, context)
    data = result.result.data

    assert data["result"] == "Post retrieved successfully."
    assert data["post"]["id"] == "urn:li:share:get123"
    assert data["post"]["commentary"] == "Retrieved post content"


async def test_get_post_url_encoding():
    """Test that post URN is properly URL-encoded."""
    responses = {"GET /posts/{urn}": {"id": "urn:li:ugcPost:123"}}
    context = MockExecutionContext(responses)
    await linkedin.execute_action("get_post", {
        "post_urn": "urn:li:ugcPost:123"
    }, context)

    get_calls = [r for r in context._requests if "/rest/posts/" in r["url"] and r["method"] == "GET"]
    assert len(get_calls) == 1
    # URN should be encoded in the URL
    assert quote("urn:li:ugcPost:123", safe="") in get_calls[0]["url"]


# =============================================================================
# GET POSTS TESTS
# =============================================================================

async def test_get_posts_success():
    """Test retrieving posts by author."""
    responses = {
        "GET /userinfo": {"sub": "posts_user", "name": "Posts User"},
        "GET /posts": {
            "elements": [
                {"id": "urn:li:share:p1", "commentary": "Post 1"},
                {"id": "urn:li:share:p2", "commentary": "Post 2"}
            ],
            "paging": {"start": 0, "count": 10}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_posts", {}, context)
    data = result.result.data

    assert data["result"] == "Posts retrieved successfully."
    assert len(data["posts"]) == 2
    assert data["posts"][0]["id"] == "urn:li:share:p1"
    assert data["paging"]["start"] == 0


async def test_get_posts_with_pagination():
    """Test retrieving posts with pagination parameters."""
    responses = {
        "GET /userinfo": {"sub": "page_user", "name": "Page User"},
        "GET /posts": {
            "elements": [{"id": "urn:li:share:p3"}],
            "paging": {"start": 10, "count": 5}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_posts", {
        "count": 5,
        "start": 10,
        "sort_by": "CREATED"
    }, context)
    data = result.result.data

    assert data["result"] == "Posts retrieved successfully."

    # Verify query parameters
    get_calls = [r for r in context._requests if "/rest/posts?" in r["url"]]
    assert "count=5" in get_calls[0]["url"]
    assert "start=10" in get_calls[0]["url"]
    assert "sortBy=CREATED" in get_calls[0]["url"]


async def test_get_posts_with_author_id():
    """Test retrieving posts for specific author."""
    responses = {
        "GET /posts": {
            "elements": [{"id": "urn:li:share:author_post"}],
            "paging": {"start": 0, "count": 10}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_posts", {
        "author_id": "specific_author"
    }, context)
    data = result.result.data

    assert data["result"] == "Posts retrieved successfully."

    # Verify no userinfo call was made
    userinfo_calls = [r for r in context._requests if "/userinfo" in r["url"]]
    assert len(userinfo_calls) == 0

    # Verify author in URL
    get_calls = [r for r in context._requests if "/rest/posts?" in r["url"]]
    assert "urn%3Ali%3Aperson%3Aspecific_author" in get_calls[0]["url"]


# =============================================================================
# UPDATE POST TESTS
# =============================================================================

async def test_update_post_success():
    """Test updating a post's commentary."""
    responses = {"PATCH /posts": {}}
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("update_post", {
        "post_urn": "urn:li:share:update123",
        "commentary": "Updated content"
    }, context)
    data = result.result.data

    assert data["result"] == "Post updated successfully."
    assert data["post_urn"] == "urn:li:share:update123"

    # Verify PARTIAL_UPDATE header
    post_calls = [r for r in context._requests if "/rest/posts/" in r["url"] and r["method"] == "POST"]
    assert post_calls[0]["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"

    # Verify patch payload
    payload = post_calls[0]["json"]
    assert payload["patch"]["$set"]["commentary"] == "Updated content"


# =============================================================================
# DELETE POST TESTS
# =============================================================================

async def test_delete_post_success():
    """Test deleting a post."""
    responses = {"DELETE /posts": {}}
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("delete_post", {
        "post_urn": "urn:li:share:delete123"
    }, context)
    data = result.result.data

    assert data["result"] == "Post deleted successfully."
    assert data["post_urn"] == "urn:li:share:delete123"

    # Verify DELETE method and header
    delete_calls = [r for r in context._requests if r["method"] == "DELETE"]
    assert len(delete_calls) == 1
    assert delete_calls[0]["headers"]["X-RestLi-Method"] == "DELETE"


# =============================================================================
# GET COMMENTS TESTS
# =============================================================================

async def test_get_comments_success():
    """Test retrieving comments on a post."""
    responses = {
        "GET /comments": {
            "elements": [
                {
                    "id": "comment1",
                    "actor": "urn:li:person:commenter1",
                    "message": {"text": "First comment"}
                },
                {
                    "id": "comment2",
                    "actor": "urn:li:person:commenter2",
                    "message": {"text": "Second comment"}
                }
            ],
            "paging": {"start": 0, "count": 10}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_comments", {
        "post_urn": "urn:li:activity:123456"
    }, context)
    data = result.result.data

    assert data["result"] == "Comments retrieved successfully."
    assert len(data["comments"]) == 2
    assert data["comments"][0]["message"]["text"] == "First comment"


async def test_get_comments_url_structure():
    """Test that comments URL is correctly formed."""
    responses = {"GET /comments": {"elements": [], "paging": {}}}
    context = MockExecutionContext(responses)
    await linkedin.execute_action("get_comments", {
        "post_urn": "urn:li:activity:789"
    }, context)

    get_calls = [r for r in context._requests if "/socialActions/" in r["url"]]
    assert len(get_calls) == 1
    assert "/comments" in get_calls[0]["url"]
    assert quote("urn:li:activity:789", safe="") in get_calls[0]["url"]


# =============================================================================
# CREATE COMMENT TESTS
# =============================================================================

async def test_create_comment_success():
    """Test creating a comment on a post."""
    responses = {
        "GET /userinfo": {"sub": "commenter123", "name": "Commenter"},
        "POST /comments": {
            "id": "new_comment_id",
            "actor": "urn:li:person:commenter123",
            "message": {"text": "My comment"},
            "object": "urn:li:activity:target123"
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_comment", {
        "post_urn": "urn:li:activity:target123",
        "message": "My comment"
    }, context)
    data = result.result.data

    assert data["result"] == "Comment created successfully."
    assert data["comment_id"] == "new_comment_id"
    assert data["comment"]["message"]["text"] == "My comment"


async def test_create_comment_with_author_id():
    """Test creating a comment with explicit author_id."""
    responses = {
        "POST /comments": {
            "id": "explicit_comment",
            "actor": "urn:li:person:explicit_commenter"
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_comment", {
        "post_urn": "urn:li:activity:target456",
        "message": "Comment from explicit author",
        "author_id": "explicit_commenter"
    }, context)
    data = result.result.data

    assert data["result"] == "Comment created successfully."

    # Verify no userinfo call
    userinfo_calls = [r for r in context._requests if "/userinfo" in r["url"]]
    assert len(userinfo_calls) == 0

    # Verify actor in payload
    post_calls = [r for r in context._requests if "/comments" in r["url"] and r["method"] == "POST"]
    assert post_calls[0]["json"]["actor"] == "urn:li:person:explicit_commenter"


async def test_create_comment_payload_structure():
    """Test that comment payload has correct structure."""
    responses = {
        "GET /userinfo": {"sub": "struct_commenter", "name": "Struct"},
        "POST /comments": {"id": "struct_comment"}
    }
    context = MockExecutionContext(responses)
    await linkedin.execute_action("create_comment", {
        "post_urn": "urn:li:activity:struct_target",
        "message": "Structured comment"
    }, context)

    post_calls = [r for r in context._requests if "/comments" in r["url"] and r["method"] == "POST"]
    payload = post_calls[0]["json"]

    assert payload["actor"] == "urn:li:person:struct_commenter"
    assert payload["object"] == "urn:li:activity:struct_target"
    assert payload["message"]["text"] == "Structured comment"


# =============================================================================
# DELETE COMMENT TESTS
# =============================================================================

async def test_delete_comment_success():
    """Test deleting a comment."""
    responses = {
        "GET /userinfo": {"sub": "deleter123", "name": "Deleter"},
        "DELETE /comments": {}
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("delete_comment", {
        "post_urn": "urn:li:activity:post123",
        "comment_id": "comment_to_delete"
    }, context)
    data = result.result.data

    assert data["result"] == "Comment deleted successfully."
    assert data["comment_id"] == "comment_to_delete"


async def test_delete_comment_url_structure():
    """Test that delete comment URL is correctly formed with encoded IDs."""
    responses = {
        "GET /userinfo": {"sub": "url_deleter", "name": "URL Deleter"},
        "DELETE /comments": {}
    }
    context = MockExecutionContext(responses)
    await linkedin.execute_action("delete_comment", {
        "post_urn": "urn:li:activity:url_post",
        "comment_id": "12345"
    }, context)

    delete_calls = [r for r in context._requests if r["method"] == "DELETE"]
    assert len(delete_calls) == 1
    url = delete_calls[0]["url"]
    # Verify URL contains encoded post URN and comment ID
    assert "/socialActions/" in url
    assert "/comments/" in url
    assert "actor=" in url


async def test_delete_comment_with_author_id():
    """Test deleting a comment with explicit author_id."""
    responses = {"DELETE /comments": {}}
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("delete_comment", {
        "post_urn": "urn:li:activity:auth_post",
        "comment_id": "auth_comment",
        "author_id": "explicit_deleter"
    }, context)
    data = result.result.data

    assert data["result"] == "Comment deleted successfully."

    # Verify no userinfo call
    userinfo_calls = [r for r in context._requests if "/userinfo" in r["url"]]
    assert len(userinfo_calls) == 0


# =============================================================================
# GET REACTIONS TESTS
# =============================================================================

async def test_get_reactions_success():
    """Test retrieving reactions on a post."""
    responses = {
        "GET /reactions": {
            "elements": [
                {"id": "reaction1", "reactionType": "LIKE"},
                {"id": "reaction2", "reactionType": "PRAISE"}
            ],
            "paging": {"start": 0, "count": 10, "total": 2}
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("get_reactions", {
        "post_urn": "urn:li:activity:react123"
    }, context)
    data = result.result.data

    assert data["result"] == "Reactions retrieved successfully."
    assert len(data["reactions"]) == 2
    assert data["reactions"][0]["reactionType"] == "LIKE"
    assert data["reactions"][1]["reactionType"] == "PRAISE"


async def test_get_reactions_with_sort():
    """Test retrieving reactions with custom sort order."""
    responses = {"GET /reactions": {"elements": [], "paging": {}}}
    context = MockExecutionContext(responses)
    await linkedin.execute_action("get_reactions", {
        "post_urn": "urn:li:activity:sort_test",
        "sort": "CHRONOLOGICAL"
    }, context)

    get_calls = [r for r in context._requests if "/reactions" in r["url"]]
    assert "sort=(value:CHRONOLOGICAL)" in get_calls[0]["url"]


async def test_get_reactions_default_sort():
    """Test that default sort is REVERSE_CHRONOLOGICAL."""
    responses = {"GET /reactions": {"elements": [], "paging": {}}}
    context = MockExecutionContext(responses)
    await linkedin.execute_action("get_reactions", {
        "post_urn": "urn:li:activity:default_sort"
    }, context)

    get_calls = [r for r in context._requests if "/reactions" in r["url"]]
    assert "sort=(value:REVERSE_CHRONOLOGICAL)" in get_calls[0]["url"]


# =============================================================================
# CREATE REACTION TESTS
# =============================================================================

async def test_create_reaction_success():
    """Test creating a reaction (like)."""
    responses = {
        "GET /userinfo": {"sub": "reactor123", "name": "Reactor"},
        "POST /reactions": {
            "id": "urn:li:reaction:(urn:li:person:reactor123,urn:li:activity:target)",
            "reactionType": "LIKE"
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_reaction", {
        "target_urn": "urn:li:activity:target"
    }, context)
    data = result.result.data

    assert data["result"] == "Reaction created successfully."
    assert data["reaction"]["reactionType"] == "LIKE"


async def test_create_reaction_different_types():
    """Test creating different reaction types."""
    reaction_types = ["LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION", "ENTERTAINMENT"]

    for reaction_type in reaction_types:
        responses = {
            "GET /userinfo": {"sub": "reactor", "name": "Reactor"},
            "POST /reactions": {"reactionType": reaction_type}
        }
        context = MockExecutionContext(responses)
        result = await linkedin.execute_action("create_reaction", {
            "target_urn": "urn:li:activity:multi_react",
            "reaction_type": reaction_type
        }, context)
        data = result.result.data

        assert data["result"] == "Reaction created successfully."

        post_calls = [r for r in context._requests if "/reactions" in r["url"] and r["method"] == "POST"]
        assert post_calls[0]["json"]["reactionType"] == reaction_type


async def test_create_reaction_with_author_id():
    """Test creating a reaction with explicit author_id."""
    responses = {
        "POST /reactions": {
            "id": "urn:li:reaction:(urn:li:person:explicit_reactor,urn:li:activity:target)",
            "reactionType": "PRAISE"
        }
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_reaction", {
        "target_urn": "urn:li:activity:explicit_target",
        "reaction_type": "PRAISE",
        "author_id": "explicit_reactor"
    }, context)
    data = result.result.data

    assert data["result"] == "Reaction created successfully."

    # Verify actor in URL query param
    post_calls = [r for r in context._requests if "/reactions" in r["url"] and r["method"] == "POST"]
    assert "actor=" in post_calls[0]["url"]
    assert "explicit_reactor" in post_calls[0]["url"]


async def test_create_reaction_payload_structure():
    """Test that reaction payload has correct structure."""
    responses = {
        "GET /userinfo": {"sub": "struct_reactor", "name": "Struct"},
        "POST /reactions": {"reactionType": "INTEREST"}
    }
    context = MockExecutionContext(responses)
    await linkedin.execute_action("create_reaction", {
        "target_urn": "urn:li:activity:struct_target",
        "reaction_type": "INTEREST"
    }, context)

    post_calls = [r for r in context._requests if "/reactions" in r["url"] and r["method"] == "POST"]
    payload = post_calls[0]["json"]

    assert payload["root"] == "urn:li:activity:struct_target"
    assert payload["reactionType"] == "INTEREST"


# =============================================================================
# DELETE REACTION TESTS
# =============================================================================

async def test_delete_reaction_success():
    """Test removing a reaction."""
    responses = {
        "GET /userinfo": {"sub": "unreactor123", "name": "Unreactor"},
        "DELETE /reactions": {}
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("delete_reaction", {
        "target_urn": "urn:li:activity:unreact_target"
    }, context)
    data = result.result.data

    assert data["result"] == "Reaction removed successfully."
    assert data["target_urn"] == "urn:li:activity:unreact_target"


async def test_delete_reaction_url_structure():
    """Test that delete reaction URL is correctly formed."""
    responses = {
        "GET /userinfo": {"sub": "url_unreactor", "name": "URL Unreactor"},
        "DELETE /reactions": {}
    }
    context = MockExecutionContext(responses)
    await linkedin.execute_action("delete_reaction", {
        "target_urn": "urn:li:activity:url_unreact"
    }, context)

    delete_calls = [r for r in context._requests if r["method"] == "DELETE"]
    assert len(delete_calls) == 1
    url = delete_calls[0]["url"]
    # URL should contain (actor:...,entity:...)
    assert "(actor:" in url
    assert ",entity:" in url


async def test_delete_reaction_with_author_id():
    """Test removing a reaction with explicit author_id."""
    responses = {"DELETE /reactions": {}}
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("delete_reaction", {
        "target_urn": "urn:li:activity:auth_unreact",
        "author_id": "explicit_unreactor"
    }, context)
    data = result.result.data

    assert data["result"] == "Reaction removed successfully."

    # Verify no userinfo call
    userinfo_calls = [r for r in context._requests if "/userinfo" in r["url"]]
    assert len(userinfo_calls) == 0


# =============================================================================
# CREATE POST TESTS (with image support)
# =============================================================================

# Sample base64-encoded 1x1 pixel images for testing
SAMPLE_JPEG_BASE64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQCEAwEPwAB//9k="
SAMPLE_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_text_only(mock_post):
    """Test creating a text-only post with no images."""
    # Mock post_to_linkedin to return success with post ID in headers
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:text123"}, None)

    responses = {
        "GET /userinfo": {"sub": "text_user", "name": "Text User"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Hello from create_post!"
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."
    assert data["post_id"] == "urn:li:share:text123"
    assert data["post_url"] == "https://www.linkedin.com/feed/update/urn:li:share:text123"
    assert data["images_uploaded"] == 0

    # Verify no image upload calls were made
    image_calls = [r for r in context._requests if "initializeUpload" in r["url"]]
    assert len(image_calls) == 0

    # Verify post_to_linkedin was called with correct payload (no content field)
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    payload = call_args[0][1]  # Second positional arg is payload
    assert "content" not in payload
    assert payload["commentary"] == "Hello from create_post!"


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_single_image(mock_post):
    """Test creating a post with a single image."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:img123"}, None)

    responses = {
        "GET /userinfo": {"sub": "img_user", "name": "Image User"},
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/image1",
                "image": "urn:li:image:single123"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Check out this image!",
        "files": [
            {
                "content": SAMPLE_JPEG_BASE64,
                "name": "photo.jpg",
                "contentType": "image/jpeg"
            }
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."
    assert data["post_id"] == "urn:li:share:img123"
    assert data["images_uploaded"] == 1

    # Verify image upload was called
    init_calls = [r for r in context._requests if "initializeUpload" in r["url"]]
    assert len(init_calls) == 1

    # Verify post payload has content.media for single image
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert "content" in payload
    assert "media" in payload["content"]
    assert "id" in payload["content"]["media"]


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_multi_image(mock_post):
    """Test creating a post with multiple images."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:multi123"}, None)

    responses = {
        "GET /userinfo": {"sub": "multi_user", "name": "Multi User"},
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/img",
                "image": "urn:li:image:multi"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Multiple images!",
        "files": [
            {"content": SAMPLE_JPEG_BASE64, "name": "image1.jpg", "contentType": "image/jpeg"},
            {"content": SAMPLE_PNG_BASE64, "name": "image2.png", "contentType": "image/png"},
            {"content": SAMPLE_JPEG_BASE64, "name": "image3.jpg", "contentType": "image/jpeg"}
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."
    assert data["images_uploaded"] == 3

    # Verify 3 image uploads were initiated
    init_calls = [r for r in context._requests if "initializeUpload" in r["url"]]
    assert len(init_calls) == 3

    # Verify post payload has content.multiImage structure
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert "content" in payload
    assert "multiImage" in payload["content"]
    assert "images" in payload["content"]["multiImage"]
    assert len(payload["content"]["multiImage"]["images"]) == 3


async def test_create_post_too_many_images():
    """Test that >20 images are rejected before any API calls."""
    context = MockExecutionContext({})

    # Create 21 files
    files = [{"content": SAMPLE_JPEG_BASE64, "name": f"image{i}.jpg", "contentType": "image/jpeg"} for i in range(21)]

    result = await linkedin.execute_action("create_post", {
        "text": "Too many images",
        "files": files
    }, context)
    data = result.result.data

    assert "Too many images" in data["result"]
    assert data["post_id"] is None
    assert data["images_uploaded"] == 0

    # Verify no API calls were made
    assert len(context._requests) == 0


async def test_create_post_invalid_image_type():
    """Test that unsupported image types are rejected."""
    context = MockExecutionContext({})

    result = await linkedin.execute_action("create_post", {
        "text": "Invalid image type",
        "files": [
            {"content": "base64data", "name": "image.bmp", "contentType": "image/bmp"}
        ]
    }, context)
    data = result.result.data

    assert "Invalid file" in data["result"]
    assert "Unsupported image type" in data["result"]
    assert data["post_id"] is None

    # Verify no API calls were made
    assert len(context._requests) == 0


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_image_with_alt_text(mock_post):
    """Test that alt text (derived from filename) is included in the post payload."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:alt123"}, None)

    responses = {
        "GET /userinfo": {"sub": "alt_user", "name": "Alt User"},
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/alt",
                "image": "urn:li:image:alt123"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Image with alt text",
        "files": [
            {
                "content": SAMPLE_JPEG_BASE64,
                "name": "A beautiful sunset over the mountains.jpg",
                "contentType": "image/jpeg"
            }
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."

    # Verify alt text (derived from filename) is in the payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["content"]["media"]["altText"] == "A beautiful sunset over the mountains"


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_visibility_options(mock_post):
    """Test that visibility options are correctly applied."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:vis123"}, None)

    responses = {
        "GET /userinfo": {"sub": "vis_user", "name": "Visibility User"},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Connections only post",
        "visibility": "CONNECTIONS"
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."

    # Verify visibility in payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["visibility"] == "CONNECTIONS"


async def test_create_post_no_content():
    """Test that a post with neither text nor files is rejected."""
    context = MockExecutionContext({})

    result = await linkedin.execute_action("create_post", {}, context)
    data = result.result.data

    assert "must have either text or at least one file" in data["result"]
    assert data["post_id"] is None


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_image_only(mock_post):
    """Test creating a post with only an image and no text."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:imgonly123"}, None)

    responses = {
        "GET /userinfo": {"sub": "imgonly_user", "name": "Image Only User"},
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/imgonly",
                "image": "urn:li:image:only123"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "files": [
            {"content": SAMPLE_PNG_BASE64, "name": "photo.png", "contentType": "image/png"}
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."
    assert data["images_uploaded"] == 1

    # Verify commentary is empty string
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["commentary"] == ""


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_with_author_id(mock_post):
    """Test creating a post with explicit author_id."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:auth123"}, None)

    responses = {
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/auth",
                "image": "urn:li:image:auth123"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Post with explicit author",
        "author_id": "explicit_author",
        "files": [
            {"content": SAMPLE_JPEG_BASE64, "name": "photo.jpg", "contentType": "image/jpeg"}
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."

    # Verify no userinfo call was made
    userinfo_calls = [r for r in context._requests if "/userinfo" in r["url"]]
    assert len(userinfo_calls) == 0

    # Verify author in image init payload
    init_calls = [r for r in context._requests if "initializeUpload" in r["url"]]
    assert init_calls[0]["json"]["initializeUploadRequest"]["owner"] == "urn:li:person:explicit_author"

    # Verify author in post payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    assert payload["author"] == "urn:li:person:explicit_author"


async def test_create_post_missing_file_content():
    """Test that file without content is rejected."""
    context = MockExecutionContext({})

    result = await linkedin.execute_action("create_post", {
        "text": "Missing file content",
        "files": [
            {"name": "photo.jpg", "contentType": "image/jpeg"}
        ]
    }, context)
    data = result.result.data

    assert "Invalid file" in data["result"]
    assert "content" in data["result"].lower()


async def test_create_post_missing_file_content_type():
    """Test that file without contentType is rejected."""
    context = MockExecutionContext({})

    result = await linkedin.execute_action("create_post", {
        "text": "Missing content type",
        "files": [
            {"content": SAMPLE_JPEG_BASE64, "name": "photo.jpg"}
        ]
    }, context)
    data = result.result.data

    assert "Invalid file" in data["result"]
    assert "contentType" in data["result"]


@patch.object(linkedin_module, 'post_to_linkedin')
async def test_create_post_multi_image_with_alt_texts(mock_post):
    """Test that alt texts (derived from filenames) are included for all images in multi-image post."""
    mock_post.return_value = (201, {"x-restli-id": "urn:li:share:multialt123"}, None)

    responses = {
        "GET /userinfo": {"sub": "multi_alt_user", "name": "Multi Alt User"},
        "POST /images/initializeUpload": {
            "value": {
                "uploadUrl": "https://api.linkedin.com/upload/multialt",
                "image": "urn:li:image:multialt"
            }
        },
        "PUT /images/upload": {},
    }
    context = MockExecutionContext(responses)
    result = await linkedin.execute_action("create_post", {
        "text": "Multiple images with alt texts",
        "files": [
            {"content": SAMPLE_JPEG_BASE64, "name": "First image.jpg", "contentType": "image/jpeg"},
            {"content": SAMPLE_PNG_BASE64, "name": "Second image.png", "contentType": "image/png"}
        ]
    }, context)
    data = result.result.data

    assert data["result"] == "Post created successfully."
    assert data["images_uploaded"] == 2

    # Verify alt texts (derived from filenames) in multiImage payload
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][1]
    images = payload["content"]["multiImage"]["images"]
    assert images[0]["altText"] == "First image"
    assert images[1]["altText"] == "Second image"
