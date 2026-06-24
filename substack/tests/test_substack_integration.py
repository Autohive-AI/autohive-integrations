"""
End-to-end integration tests for the Substack integration.

Substack's public API requires no authentication — tests run against the live
API using a configurable public newsletter.

Environment variables (all optional):
    SUBSTACK_TEST_PUBLICATION_URL — base URL of a Substack publication to test
                                    (default: https://www.astralcodexten.com)
    SUBSTACK_TEST_POST_SLUG       — slug of a specific post to use in get_post
                                    tests; falls back to the first archive post

Run (safe — all tests are read-only):
    pytest substack/tests/test_substack_integration.py -m integration -v

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from unittest.mock import MagicMock, AsyncMock

from substack import substack as substack_integration

pytestmark = pytest.mark.integration

TEST_PUBLICATION_URL = os.environ.get("SUBSTACK_TEST_PUBLICATION_URL", "https://www.astralcodexten.com")
TEST_POST_SLUG = os.environ.get("SUBSTACK_TEST_POST_SLUG", "")


@pytest.fixture
def live_context():
    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, data=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, headers=headers or {}) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(resp_data), resp_data)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(resp_data), resp_data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {}
    return ctx


# ============================================================
# GET PUBLICATION POSTS
# ============================================================


class TestGetPublicationPosts:
    async def test_returns_posts_list(self, live_context):
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "posts" in result.result.data
        assert isinstance(result.result.data["posts"], list)
        assert "count" in result.result.data

    async def test_limit_respected(self, live_context):
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 3},
            live_context,
        )
        assert len(result.result.data["posts"]) <= 3

    async def test_post_item_has_expected_fields(self, live_context):
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 1},
            live_context,
        )
        posts = result.result.data["posts"]
        if not posts:
            pytest.skip("No posts returned from this publication")
        post = posts[0]
        assert "slug" in post
        assert "title" in post
        assert "post_date" in post

    async def test_sort_top(self, live_context):
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "sort": "top", "limit": 5},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["posts"], list)

    async def test_pagination_returns_different_posts(self, live_context):
        first = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 2, "offset": 0},
            live_context,
        )
        second = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 2, "offset": 2},
            live_context,
        )
        posts_first = first.result.data["posts"]
        posts_second = second.result.data["posts"]
        if posts_first and posts_second:
            assert posts_first[0]["slug"] != posts_second[0]["slug"]


# ============================================================
# GET POST
# ============================================================


class TestGetPost:
    async def test_returns_post_content(self, live_context):
        list_result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 1},
            live_context,
        )
        posts = list_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts available to fetch")
        slug = TEST_POST_SLUG or posts[0]["slug"]

        result = await substack_integration.execute_action(
            "get_post",
            {"publication_url": TEST_PUBLICATION_URL, "slug": slug},
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "slug" in data
        assert "title" in data
        assert "body_html" in data

    async def test_slug_matches(self, live_context):
        list_result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 1},
            live_context,
        )
        posts = list_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts available")
        slug = posts[0]["slug"]

        result = await substack_integration.execute_action(
            "get_post",
            {"publication_url": TEST_PUBLICATION_URL, "slug": slug},
            live_context,
        )
        assert result.result.data["slug"] == slug

    async def test_nonexistent_slug_raises_http_error(self, live_context):
        """A bad slug 404s — context.fetch raises HTTPError (SDK v2 raises on
        non-ok), which execute_action does not catch, so it propagates."""
        with pytest.raises(HTTPError):
            await substack_integration.execute_action(
                "get_post",
                {
                    "publication_url": TEST_PUBLICATION_URL,
                    "slug": "this-slug-definitely-does-not-exist-xyz123",
                },
                live_context,
            )


# ============================================================
# SEARCH PUBLICATIONS
# ============================================================


class TestSearchPublications:
    async def test_returns_publications(self, live_context):
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "technology"},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "publications" in result.result.data
        assert isinstance(result.result.data["publications"], list)
        assert "more" in result.result.data

    async def test_publication_has_expected_fields(self, live_context):
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "newsletter"},
            live_context,
        )
        pubs = result.result.data["publications"]
        if not pubs:
            pytest.skip("No publications returned for query")
        pub = pubs[0]
        assert "name" in pub
        assert "subdomain" in pub

    async def test_limit_respected(self, live_context):
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "technology", "limit": 3},
            live_context,
        )
        assert len(result.result.data["publications"]) <= 3


# ============================================================
# SEARCH POSTS
# ============================================================


class TestSearchPosts:
    async def test_returns_posts(self, live_context):
        result = await substack_integration.execute_action(
            "search_posts",
            {"publication_url": TEST_PUBLICATION_URL, "query": "a"},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "posts" in result.result.data
        assert isinstance(result.result.data["posts"], list)
        assert "count" in result.result.data

    async def test_posts_have_expected_fields(self, live_context):
        result = await substack_integration.execute_action(
            "search_posts",
            {"publication_url": TEST_PUBLICATION_URL, "query": "a", "limit": 1},
            live_context,
        )
        posts = result.result.data["posts"]
        if not posts:
            pytest.skip("No posts matched search query")
        assert "slug" in posts[0]
        assert "title" in posts[0]


# ============================================================
# GET POST COMMENTS
# ============================================================


class TestGetPostComments:
    async def test_returns_comments_structure(self, live_context):
        list_result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 5},
            live_context,
        )
        posts = list_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts available")

        post_id = posts[0].get("id")
        if not post_id:
            pytest.skip("Post has no numeric id")

        result = await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": TEST_PUBLICATION_URL, "post_id": post_id},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "comments" in result.result.data
        assert isinstance(result.result.data["comments"], list)
        assert "count" in result.result.data

    async def test_count_matches_comments_length(self, live_context):
        list_result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": TEST_PUBLICATION_URL, "limit": 3},
            live_context,
        )
        posts = list_result.result.data["posts"]
        if not posts:
            pytest.skip("No posts available")

        for post in posts:
            post_id = post.get("id")
            if not post_id:
                continue
            result = await substack_integration.execute_action(
                "get_post_comments",
                {"publication_url": TEST_PUBLICATION_URL, "post_id": post_id},
                live_context,
            )
            data = result.result.data
            assert data["count"] == len(data["comments"])
            return

        pytest.skip("No posts with numeric id found")
