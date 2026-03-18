import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
)

from substack import substack  # noqa: E402


def make_context(auth=None, fetch_side_effect=None, fetch_return_value=None):
    """Create a mock ExecutionContext."""
    context = MagicMock()
    context.auth = auth or {}
    if fetch_side_effect is not None:
        context.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        context.fetch = AsyncMock(return_value=fetch_return_value)
    return context


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Helpers ──────────────────────────────────────────────────────────────────


class TestNormaliseUrl(unittest.TestCase):
    def _normalise(self, url):
        from substack.substack import _normalise_url

        return _normalise_url(url)

    def test_strips_trailing_slash(self):
        assert (
            self._normalise("https://example.substack.com/")
            == "https://example.substack.com"
        )

    def test_upgrades_http_to_https(self):
        assert (
            self._normalise("http://example.substack.com")
            == "https://example.substack.com"
        )

    def test_strips_path(self):
        assert (
            self._normalise("https://example.substack.com/p/some-post")
            == "https://example.substack.com"
        )

    def test_custom_domain_unchanged(self):
        assert (
            self._normalise("https://newsletter.example.com")
            == "https://newsletter.example.com"
        )

    def test_no_change_needed(self):
        assert (
            self._normalise("https://example.substack.com")
            == "https://example.substack.com"
        )


class TestBuildHeaders(unittest.TestCase):
    def _headers(self, auth):
        from substack.substack import _build_headers

        return _build_headers(auth)

    def test_no_auth_no_cookie_header(self):
        headers = self._headers({})
        assert "Cookie" not in headers

    def test_with_both_cookies(self):
        headers = self._headers({"connect_sid": "abc", "substack_sid": "xyz"})
        assert headers["Cookie"] == "connect.sid=abc; substack.sid=xyz"

    def test_with_only_connect_sid(self):
        headers = self._headers({"connect_sid": "abc"})
        assert "connect.sid=abc" in headers["Cookie"]
        assert "substack.sid" not in headers["Cookie"]

    def test_empty_strings_excluded(self):
        headers = self._headers({"connect_sid": "", "substack_sid": ""})
        assert "Cookie" not in headers


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
        assert len(result["posts"]) == 1
        assert result["posts"][0]["slug"] == "hello-world"
        assert result["count"] == 1

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
        call_kwargs = context.fetch.call_args
        params = call_kwargs[1].get("params") or (
            call_kwargs[0][2] if len(call_kwargs[0]) > 2 else {}
        )
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

    def test_no_auth_no_cookie_header(self):
        context = make_context(auth={}, fetch_return_value=[])
        run(
            substack.execute_action(
                "get_publication_posts",
                {"publication_url": "https://example.substack.com"},
                context,
            )
        )
        headers = context.fetch.call_args[1].get("headers", {})
        assert "Cookie" not in headers

    def test_auth_sets_cookie_header(self):
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_return_value=[],
        )
        run(
            substack.execute_action(
                "get_publication_posts",
                {"publication_url": "https://example.substack.com"},
                context,
            )
        )
        headers = context.fetch.call_args[1].get("headers", {})
        assert "Cookie" in headers


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
        assert result["slug"] == "hello-world"
        assert result["body_html"] == "<p>Content here</p>"

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


# ── get_publication_info ──────────────────────────────────────────────────────


class TestGetPublicationInfo(unittest.TestCase):
    MOCK_RESPONSE = {
        "id": 1,
        "name": "Example Newsletter",
        "subdomain": "example",
        "custom_domain": None,
        "logo_url": "https://example.com/logo.png",
        "cover_photo_url": None,
        "hero_text": "A great newsletter",
        "subscriber_count": 1000,
        "author_id": 42,
        "email_from_name": "Author Name",
        "type": "newsletter",
    }

    def test_success(self):
        context = make_context(fetch_return_value=self.MOCK_RESPONSE)
        result = run(
            substack.execute_action(
                "get_publication_info",
                {"publication_url": "https://example.substack.com"},
                context,
            )
        )
        assert result["name"] == "Example Newsletter"
        assert result["subscriber_count"] == 1000


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
        assert len(result["publications"]) == 1
        assert result["more"] is False

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
        assert len(result["posts"]) == 1
        assert result["posts"][0]["slug"] == "matching-post"

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
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author_name"] == "Alice"

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


# ── get_subscriptions ─────────────────────────────────────────────────────────


class TestGetSubscriptions(unittest.TestCase):
    PROFILE_RESPONSE = {"id": 999, "name": "Test User"}
    PROFILE_DATA_RESPONSE = {
        "subscriptions": [
            {
                "name": "Cool Newsletter",
                "subdomain": "cool",
                "custom_domain": None,
                "author_name": "Bob",
                "is_paid": False,
                "subscriber_count": 200,
                "logo_url": None,
            }
        ]
    }

    def test_success(self):
        responses = [self.PROFILE_RESPONSE, self.PROFILE_DATA_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        result = run(substack.execute_action("get_subscriptions", {}, context))
        assert len(result["subscriptions"]) == 1
        assert result["subscriptions"][0]["name"] == "Cool Newsletter"

    def test_preflight_401_raises_auth_error(self):
        from autohive_integrations_sdk import AuthError

        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=AuthError("Unauthorized"),
        )
        with self.assertRaises(AuthError):
            run(substack.execute_action("get_subscriptions", {}, context))

    def test_makes_two_fetch_calls(self):
        responses = [self.PROFILE_RESPONSE, self.PROFILE_DATA_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        run(substack.execute_action("get_subscriptions", {}, context))
        assert context.fetch.call_count == 2


# ── get_reader_feed ───────────────────────────────────────────────────────────


class TestGetReaderFeed(unittest.TestCase):
    PROFILE_RESPONSE = {"id": 999}
    FEED_RESPONSE = {
        "items": [
            {
                "id": "item-1",
                "type": "like",
                "date": "2024-02-01T00:00:00.000Z",
                "post_title": "A Post I Liked",
                "post_url": "https://example.substack.com/p/a-post",
                "publication_name": "Example Newsletter",
                "publication_url": "https://example.substack.com",
            }
        ]
    }

    def test_success(self):
        responses = [self.PROFILE_RESPONSE, self.FEED_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        result = run(substack.execute_action("get_reader_feed", {}, context))
        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "like"

    def test_preflight_401_raises_auth_error(self):
        from autohive_integrations_sdk import AuthError

        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=AuthError("Unauthorized"),
        )
        with self.assertRaises(AuthError):
            run(substack.execute_action("get_reader_feed", {}, context))

    def test_types_filter_passed_as_params(self):
        responses = [self.PROFILE_RESPONSE, self.FEED_RESPONSE]
        context = make_context(
            auth={"connect_sid": "abc", "substack_sid": "xyz"},
            fetch_side_effect=responses,
        )
        run(
            substack.execute_action(
                "get_reader_feed",
                {"types": ["like"]},
                context,
            )
        )
        # Second call is the feed call — check its params
        feed_call = context.fetch.call_args_list[1]
        params = feed_call[1].get("params", {})
        assert "like" in str(params)


if __name__ == "__main__":
    unittest.main()
