"""
Unit tests for the Substack integration using mocked fetch.
"""

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from substack import substack as substack_integration
from substack.substack import _normalise_url

pytestmark = pytest.mark.unit

# ============================================================
# Sample data
# ============================================================

MOCK_POST = {
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

MOCK_FULL_POST = {
    **MOCK_POST,
    "body_html": "<p>Content here</p>",
    "audio_url": None,
}

MOCK_SEARCH_PUBS_RESPONSE = {
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

MOCK_COMMENTS_RESPONSE = {
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


# ============================================================
# HELPERS — _normalise_url (pure function, tested directly)
# ============================================================


def test_normalise_strips_trailing_slash():
    assert _normalise_url("https://example.substack.com/") == "https://example.substack.com"


def test_normalise_upgrades_http():
    assert _normalise_url("http://example.substack.com") == "https://example.substack.com"


def test_normalise_strips_path():
    assert _normalise_url("https://example.substack.com/p/some-post") == "https://example.substack.com"


def test_normalise_custom_domain_unchanged():
    assert _normalise_url("https://newsletter.example.com") == "https://newsletter.example.com"


def test_normalise_bare_hostname_no_scheme():
    assert _normalise_url("example.substack.com") == "https://example.substack.com"


# ============================================================
# GET PUBLICATION POSTS
# ============================================================


class TestGetPublicationPosts:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[MOCK_POST])
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["count"] == 1
        assert result.result.data["posts"][0]["slug"] == "hello-world"

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            mock_context,
        )
        assert result.result.data["posts"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com", "offset": 12, "limit": 6},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["offset"] == 12
        assert params["limit"] == 6

    @pytest.mark.asyncio
    async def test_sort_param_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com", "sort": "top"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["sort"] == "top"

    @pytest.mark.asyncio
    async def test_search_param_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com", "search": "python"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params.get("search") == "python"

    @pytest.mark.asyncio
    async def test_url_normalised(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "http://example.substack.com/"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert url.startswith("https://example.substack.com")

    @pytest.mark.asyncio
    async def test_no_cookie_header(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            mock_context,
        )
        headers = mock_context.fetch.call_args.kwargs.get("headers", {})
        assert "Cookie" not in headers

    @pytest.mark.asyncio
    async def test_null_cover_image_dropped(self, mock_context):
        """cover_image=None is excluded from each post by _drop_none."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[MOCK_POST])
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {"publication_url": "https://example.substack.com"},
            mock_context,
        )
        assert "cover_image" not in result.result.data["posts"][0]


# ============================================================
# GET POST
# ============================================================


class TestGetPost:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_FULL_POST)
        result = await substack_integration.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["slug"] == "hello-world"
        assert result.result.data["body_html"] == "<p>Content here</p>"
        assert result.result.data["like_count"] == 10

    @pytest.mark.asyncio
    async def test_url_contains_slug(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_FULL_POST)
        await substack_integration.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "/api/v1/posts/hello-world" in url

    @pytest.mark.asyncio
    async def test_none_fields_dropped(self, mock_context):
        """audio_url and cover_image are None — _drop_none must exclude them."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_FULL_POST)
        result = await substack_integration.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            mock_context,
        )
        assert "audio_url" not in result.result.data
        assert "cover_image" not in result.result.data

    @pytest.mark.asyncio
    async def test_audio_url_present_when_set(self, mock_context):
        post_with_audio = {**MOCK_FULL_POST, "audio_url": "https://example.com/audio.mp3"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=post_with_audio)
        result = await substack_integration.execute_action(
            "get_post",
            {"publication_url": "https://example.substack.com", "slug": "hello-world"},
            mock_context,
        )
        assert result.result.data["audio_url"] == "https://example.com/audio.mp3"

    @pytest.mark.asyncio
    async def test_url_normalised(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_FULL_POST)
        await substack_integration.execute_action(
            "get_post",
            {"publication_url": "http://example.substack.com/", "slug": "hello-world"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert url.startswith("https://example.substack.com")


# ============================================================
# SEARCH PUBLICATIONS
# ============================================================


class TestSearchPublications:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_SEARCH_PUBS_RESPONSE)
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "tech"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["publications"]) == 1
        assert result.result.data["more"] is False

    @pytest.mark.asyncio
    async def test_uses_global_base_url(self, mock_context):
        """search_publications uses the global SUBSTACK_BASE, not a publication-specific URL."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_SEARCH_PUBS_RESPONSE)
        await substack_integration.execute_action(
            "search_publications",
            {"query": "tech"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "substack.com/api/v1/publication/search" in url

    @pytest.mark.asyncio
    async def test_query_param_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_SEARCH_PUBS_RESPONSE)
        await substack_integration.execute_action(
            "search_publications",
            {"query": "finance"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["query"] == "finance"

    @pytest.mark.asyncio
    async def test_page_and_limit_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_SEARCH_PUBS_RESPONSE)
        await substack_integration.execute_action(
            "search_publications",
            {"query": "tech", "page": 2, "limit": 20},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["page"] == 2
        assert params["limit"] == 20

    @pytest.mark.asyncio
    async def test_none_fields_dropped(self, mock_context):
        """custom_domain and logo_url are None — dropped by _drop_none."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_SEARCH_PUBS_RESPONSE)
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "tech"},
            mock_context,
        )
        pub = result.result.data["publications"][0]
        assert "custom_domain" not in pub
        assert "logo_url" not in pub

    @pytest.mark.asyncio
    async def test_more_flag_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={**MOCK_SEARCH_PUBS_RESPONSE, "more": True}
        )
        result = await substack_integration.execute_action(
            "search_publications",
            {"query": "tech"},
            mock_context,
        )
        assert result.result.data["more"] is True


# ============================================================
# SEARCH POSTS
# ============================================================


class TestSearchPosts:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[
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
            ],
        )
        result = await substack_integration.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "keyword"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["posts"][0]["slug"] == "matching-post"
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_uses_archive_endpoint_with_search_param(self, mock_context):
        """/api/v1/posts/search 404s — must use /api/v1/archive?search= instead."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "keyword"},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert "/api/v1/archive" in url
        assert params.get("search") == "keyword"

    @pytest.mark.asyncio
    async def test_offset_param_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "x", "offset": 10},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["offset"] == 10

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        result = await substack_integration.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "noresults"},
            mock_context,
        )
        assert result.result.data["posts"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_max_limit_forwarded(self, mock_context):
        """limit=50 (schema maximum) is passed through to the API."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])
        await substack_integration.execute_action(
            "search_posts",
            {"publication_url": "https://example.substack.com", "query": "x", "limit": 50},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["limit"] == 50


# ============================================================
# GET POST COMMENTS
# ============================================================


class TestGetPostComments:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_COMMENTS_RESPONSE)
        result = await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["comments"][0]["author_name"] == "Alice"
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_url_uses_singular_post_path(self, mock_context):
        """URL must be /api/v1/post/ (singular), not /api/v1/posts/."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_COMMENTS_RESPONSE)
        await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            mock_context,
        )
        url = mock_context.fetch.call_args.args[0]
        assert "/api/v1/post/123/comments" in url
        assert "/api/v1/posts/" not in url

    @pytest.mark.asyncio
    async def test_all_comments_true_sent_as_string(self, mock_context):
        """Substack expects the string 'true', not a boolean."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_COMMENTS_RESPONSE)
        await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["all_comments"] == "true"

    @pytest.mark.asyncio
    async def test_all_comments_false_sent_as_string(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_COMMENTS_RESPONSE)
        await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123, "all_comments": False},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["all_comments"] == "false"

    @pytest.mark.asyncio
    async def test_sort_param_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=MOCK_COMMENTS_RESPONSE)
        await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123, "sort": "newest"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params["sort"] == "newest"

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        result = await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            mock_context,
        )
        assert result.result.data["comments"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_null_comment_fields_pass_output_validation(self, mock_context):
        """Deleted/anonymous comments return null body, author_name, etc.

        Comments are passed through raw (not via _drop_none), so the output
        schema must allow null for these fields — otherwise SDK v2 output
        validation raises VALIDATION_ERROR on a successful 200. Confirmed
        against the live API: deleted comments have ``"body": null``.
        """
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "comments": [
                    {
                        "id": 2002,
                        "body": None,
                        "date": None,
                        "author_name": None,
                        "author_id": None,
                        "like_count": None,
                        "children": [],
                    }
                ]
            },
        )
        result = await substack_integration.execute_action(
            "get_post_comments",
            {"publication_url": "https://example.substack.com", "post_id": 123},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["count"] == 1
        assert result.result.data["comments"][0]["body"] is None


# ============================================================
# VALIDATION
# ============================================================


class TestValidation:
    @pytest.mark.asyncio
    async def test_missing_required_input(self, mock_context):
        result = await substack_integration.execute_action(
            "get_publication_posts",
            {},  # publication_url is required
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_unknown_action(self, mock_context):
        result = await substack_integration.execute_action("nonexistent_action", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
