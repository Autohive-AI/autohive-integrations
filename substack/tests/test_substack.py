import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

from substack import substack  # noqa: E402


def make_context(fetch_side_effect=None, fetch_return_value=None):
    """Create a mock ExecutionContext."""
    context = MagicMock()
    context.auth = {}
    if fetch_side_effect is not None:
        context.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        context.fetch = AsyncMock(return_value=fetch_return_value)
    return context


def run(coro):
    return asyncio.run(coro)


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestNormaliseUrl(unittest.TestCase):
    def _normalise(self, url):
        from substack.substack import _normalise_url

        return _normalise_url(url)

    def test_strips_trailing_slash(self):
        assert self._normalise("https://example.substack.com/") == "https://example.substack.com"

    def test_upgrades_http_to_https(self):
        assert self._normalise("http://example.substack.com") == "https://example.substack.com"

    def test_strips_path(self):
        assert self._normalise("https://example.substack.com/p/some-post") == "https://example.substack.com"

    def test_custom_domain_unchanged(self):
        assert self._normalise("https://newsletter.example.com") == "https://newsletter.example.com"

    def test_no_change_needed(self):
        assert self._normalise("https://example.substack.com") == "https://example.substack.com"

    def test_bare_hostname_no_scheme(self):
        assert self._normalise("example.substack.com") == "https://example.substack.com"


# ── get_publication_posts ─────────────────────────────────────────────────────


class TestGetPublicationPosts(unittest.TestCase):
    MOCK_RESPONSE = [
        {
            "id": 123,
            "slug": "hello-world",
            "title": "Hello World",
            "subtitle": "A subtitle",
            "post_date": "2024-01-01T00:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/hello-world",
            "audience": "everyone",
            "paywall": False,
            "reading_time_minutes": 3,
            "cover_image": None,
            "like_count": 10,
            "comment_count": 2,
            "type": "newsletter",
        }
    ]

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "get_publication_posts",
                {"publication_url": "https://example.substack.com"},
                context,
            )
        )
        data = result.result.data
        assert len(data["posts"]) == 1
        assert data["posts"][0]["slug"] == "hello-world"
        assert data["count"] == 1

    def test_passes_pagination_params(self):
        context = make_context(fetch_return_value=[])
        run(
            substack.execute_action(
                "get_publication_posts",
                {
                    "publication_url": "https://example.substack.com",
                    "offset": 12,
                    "limit": 6,
                },
                context,
            )
        )
        params = context.fetch.call_args[1].get("params", {})
        assert params.get("offset") == 12
        assert params.get("limit") == 6

    def test_url_normalisation(self):
        context = make_context(fetch_return_value=[])
        run(
            substack.execute_action(
                "get_publication_posts",
                {"publication_url": "http://example.substack.com/"},
                context,
            )
        )
        url_called = context.fetch.call_args[0][0]
        assert url_called.startswith("https://example.substack.com")

    def test_no_cookie_header(self):
        context = make_context(fetch_return_value=[])
        run(
            substack.execute_action(
                "get_publication_posts",
                {"publication_url": "https://example.substack.com"},
                context,
            )
        )
        headers = context.fetch.call_args[1].get("headers", {})
        assert "Cookie" not in headers


# ── get_post ──────────────────────────────────────────────────────────────────


class TestGetPost(unittest.TestCase):
    MOCK_RESPONSE = {
        "id": 123,
        "slug": "hello-world",
        "title": "Hello World",
        "subtitle": "A subtitle",
        "body_html": "<p>Content here</p>",
        "post_date": "2024-01-01T00:00:00.000Z",
        "canonical_url": "https://example.substack.com/p/hello-world",
        "audience": "everyone",
        "paywall": False,
        "reading_time_minutes": 3,
        "cover_image": None,
        "like_count": 10,
        "comment_count": 2,
        "type": "newsletter",
        "audio_url": None,
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "get_post",
                {
                    "publication_url": "https://example.substack.com",
                    "slug": "hello-world",
                },
                context,
            )
        )
        data = result.result.data
        assert data["slug"] == "hello-world"
        assert data["body_html"] == "<p>Content here</p>"

    def test_url_contains_slug(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(
            substack.execute_action(
                "get_post",
                {
                    "publication_url": "https://example.substack.com",
                    "slug": "hello-world",
                },
                context,
            )
        )
        url_called = context.fetch.call_args[0][0]
        assert "hello-world" in url_called


# ── search_publications ───────────────────────────────────────────────────────


class TestSearchPublications(unittest.TestCase):
    MOCK_RESPONSE = {
        "publications": [
            {
                "id": 1,
                "name": "Example Newsletter",
                "subdomain": "example",
                "custom_domain": None,
                "logo_url": None,
                "description": "A newsletter about things",
                "subscriber_count": 500,
            }
        ],
        "more": False,
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "search_publications",
                {"query": "tech"},
                context,
            )
        )
        data = result.result.data
        assert len(data["publications"]) == 1
        assert data["more"] is False

    def test_passes_query_param(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(
            substack.execute_action(
                "search_publications",
                {"query": "finance"},
                context,
            )
        )
        call_kwargs = context.fetch.call_args
        params = call_kwargs[1].get("params", {})
        assert params.get("query") == "finance"


# ── search_posts ──────────────────────────────────────────────────────────────


class TestSearchPosts(unittest.TestCase):
    MOCK_RESPONSE = [
        {
            "id": 99,
            "slug": "matching-post",
            "title": "Matching Post",
            "subtitle": "",
            "post_date": "2024-06-01T00:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/matching-post",
            "audience": "everyone",
            "paywall": False,
            "reading_time_minutes": 2,
            "cover_image": None,
            "like_count": 5,
            "comment_count": 1,
            "type": "newsletter",
        }
    ]

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "search_posts",
                {"publication_url": "https://example.substack.com", "query": "keyword"},
                context,
            )
        )
        data = result.result.data
        assert len(data["posts"]) == 1
        assert data["posts"][0]["slug"] == "matching-post"

    def test_uses_archive_endpoint_with_search_param(self):
        """search_posts must use /api/v1/archive?search= not /api/v1/posts/search (404)."""
        context = make_context(fetch_return_value=[])
        run(
            substack.execute_action(
                "search_posts",
                {"publication_url": "https://example.substack.com", "query": "keyword"},
                context,
            )
        )
        url_called = context.fetch.call_args[0][0]
        params = context.fetch.call_args[1].get("params", {})
        assert "/api/v1/archive" in url_called
        assert params.get("search") == "keyword"

    def test_limit_maximum_passed(self):
        context = make_context(fetch_return_value=[])
        run(
            substack.execute_action(
                "search_posts",
                {
                    "publication_url": "https://example.substack.com",
                    "query": "x",
                    "limit": 50,
                },
                context,
            )
        )
        params = context.fetch.call_args[1].get("params", {})
        assert params.get("limit") == 50


# ── get_post_comments ─────────────────────────────────────────────────────────


class TestGetPostComments(unittest.TestCase):
    MOCK_RESPONSE = {
        "comments": [
            {
                "id": 1001,
                "body": "Great post!",
                "date": "2024-01-02T00:00:00.000Z",
                "author_name": "Alice",
                "author_id": 55,
                "like_count": 3,
                "children": [],
            }
        ]
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "get_post_comments",
                {"publication_url": "https://example.substack.com", "post_id": 123},
                context,
            )
        )
        data = result.result.data
        assert len(data["comments"]) == 1
        assert data["comments"][0]["author_name"] == "Alice"

    def test_url_uses_singular_post_path(self):
        """URL must use /api/v1/post/ (singular), not /api/v1/posts/."""
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(
            substack.execute_action(
                "get_post_comments",
                {"publication_url": "https://example.substack.com", "post_id": 123},
                context,
            )
        )
        url_called = context.fetch.call_args[0][0]
        assert "/api/v1/post/123/comments" in url_called
        assert "/api/v1/posts/123/comments" not in url_called

    def test_all_comments_sent_as_string(self):
        """Substack expects 'true'/'false' strings for the all_comments param."""
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        run(
            substack.execute_action(
                "get_post_comments",
                {
                    "publication_url": "https://example.substack.com",
                    "post_id": 123,
                    "all_comments": False,
                },
                context,
            )
        )
        params = context.fetch.call_args[1].get("params", {})
        assert params.get("all_comments") == "false"


if __name__ == "__main__":
    unittest.main()
