"""
Unit tests for the shared helpers in helpers.py.

These cover the plumbing that action modules depend on but that no single action
fully exercises: Search API envelope handling and its 1000-result cap, the
GraphQL error contract, and the Accept-header override used for non-JSON
responses such as PR diffs.
"""

import pytest
from autohive_integrations_sdk import FetchResponse

from helpers import GitHubAPI

pytestmark = pytest.mark.unit


def _search_page(items, total_count=None, incomplete=False):
    """Build a Search API envelope response."""
    return FetchResponse(
        status=200,
        headers={},
        data={
            "total_count": total_count if total_count is not None else len(items),
            "incomplete_results": incomplete,
            "items": items,
        },
    )


class TestGetHeaders:
    def test_default_accept_is_json(self, mock_context):
        headers = GitHubAPI.get_headers(mock_context)

        assert headers["Accept"] == "application/vnd.github.v3+json"
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_accept_override(self, mock_context):
        """Non-JSON endpoints (PR diffs) need a different media type."""
        headers = GitHubAPI.get_headers(mock_context, accept="application/vnd.github.diff")

        assert headers["Accept"] == "application/vnd.github.diff"
        assert headers["Authorization"] == "Bearer test_token"

    def test_missing_token_does_not_raise(self, mock_context):
        """get_headers is called before the auth guard in some paths."""
        mock_context.auth = {"credentials": {}}

        assert GitHubAPI.get_headers(mock_context)["Authorization"] == "Bearer "


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_envelope_fields(self, mock_context):
        mock_context.fetch.return_value = _search_page([{"id": 1}], total_count=1)

        result = await GitHubAPI.search(mock_context, "repositories", "autohive")

        assert result["items"] == [{"id": 1}]
        assert result["total_count"] == 1
        assert result["incomplete_results"] is False
        assert result["capped"] is False

    @pytest.mark.asyncio
    async def test_query_and_endpoint_are_passed_through(self, mock_context):
        mock_context.fetch.return_value = _search_page([])

        await GitHubAPI.search(mock_context, "code", "addClass repo:jquery/jquery")

        url = mock_context.fetch.call_args.args[0]
        params = mock_context.fetch.call_args.kwargs["params"]
        assert url == "https://api.github.com/search/code"
        assert params["q"] == "addClass repo:jquery/jquery"

    @pytest.mark.asyncio
    async def test_sort_and_order_only_sent_when_given(self, mock_context):
        mock_context.fetch.return_value = _search_page([])

        await GitHubAPI.search(mock_context, "repositories", "python")

        params = mock_context.fetch.call_args.kwargs["params"]
        assert "sort" not in params
        assert "order" not in params

    @pytest.mark.asyncio
    async def test_sort_and_order_forwarded(self, mock_context):
        mock_context.fetch.return_value = _search_page([])

        await GitHubAPI.search(mock_context, "repositories", "python", sort="stars", order="desc")

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["sort"] == "stars"
        assert params["order"] == "desc"

    @pytest.mark.asyncio
    async def test_paginates_until_partial_page(self, mock_context):
        mock_context.fetch.side_effect = [
            _search_page([{"id": i} for i in range(100)], total_count=150),
            _search_page([{"id": i} for i in range(50)], total_count=150),
        ]

        result = await GitHubAPI.search(mock_context, "issues", "bug")

        assert len(result["items"]) == 150
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_limit_truncates_and_stops_early(self, mock_context):
        mock_context.fetch.return_value = _search_page([{"id": i} for i in range(10)], total_count=500)

        result = await GitHubAPI.search(mock_context, "issues", "bug", limit=10)

        assert len(result["items"]) == 10
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = _search_page([], total_count=0)

        result = await GitHubAPI.search(mock_context, "users", "nonexistentuser999")

        assert result["items"] == []
        assert result["total_count"] == 0
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_capped_flag_when_total_exceeds_api_limit(self, mock_context):
        """GitHub caps every query at 1000 results however far you paginate."""
        mock_context.fetch.return_value = _search_page([{"id": 1}], total_count=50000)

        result = await GitHubAPI.search(mock_context, "issues", "is:issue")

        assert result["capped"] is True
        assert result["total_count"] == 50000

    @pytest.mark.asyncio
    async def test_max_pages_stops_without_raising(self, mock_context):
        """Unlike paginated_fetch, search stops quietly - the cap is GitHub's, not ours."""
        mock_context.fetch.return_value = _search_page([{"id": i} for i in range(100)], total_count=100000)

        result = await GitHubAPI.search(mock_context, "issues", "bug", max_pages=2)

        assert mock_context.fetch.call_count == 2
        assert len(result["items"]) == 200

    @pytest.mark.asyncio
    async def test_incomplete_results_is_sticky_across_pages(self, mock_context):
        """A timeout on any page means the whole result set is incomplete."""
        mock_context.fetch.side_effect = [
            _search_page([{"id": i} for i in range(100)], total_count=150, incomplete=True),
            _search_page([{"id": i} for i in range(50)], total_count=150, incomplete=False),
        ]

        result = await GitHubAPI.search(mock_context, "code", "foo")

        assert result["incomplete_results"] is True

    @pytest.mark.asyncio
    async def test_extra_params_forwarded(self, mock_context):
        mock_context.fetch.return_value = _search_page([])

        await GitHubAPI.search(mock_context, "issues", "bug", extra_params={"advanced_search": "true"})

        assert mock_context.fetch.call_args.kwargs["params"]["advanced_search"] == "true"


class TestGraphQL:
    @pytest.mark.asyncio
    async def test_returns_data_object(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"data": {"viewer": {"login": "octocat"}}}
        )

        result = await GitHubAPI.graphql(mock_context, "query { viewer { login } }")

        assert result == {"viewer": {"login": "octocat"}}

    @pytest.mark.asyncio
    async def test_posts_to_graphql_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": {}})

        await GitHubAPI.graphql(mock_context, "query { viewer { login } }")

        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/graphql"
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_variables_included_when_given(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": {}})

        await GitHubAPI.graphql(mock_context, "query($id: ID!) { node(id: $id) { id } }", {"id": "abc"})

        assert mock_context.fetch.call_args.kwargs["json"]["variables"] == {"id": "abc"}

    @pytest.mark.asyncio
    async def test_variables_omitted_when_absent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": {}})

        await GitHubAPI.graphql(mock_context, "query { viewer { login } }")

        assert "variables" not in mock_context.fetch.call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_errors_array_raises(self, mock_context):
        """GraphQL answers 200 even when the operation failed - don't treat that as success."""
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"data": None, "errors": [{"message": "Could not resolve to a node"}]},
        )

        with pytest.raises(ValueError, match="Could not resolve to a node"):
            await GitHubAPI.graphql(mock_context, 'query { node(id: "bad") { id } }')

    @pytest.mark.asyncio
    async def test_multiple_errors_are_all_reported(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"errors": [{"message": "first problem"}, {"message": "second problem"}]},
        )

        with pytest.raises(ValueError) as exc:
            await GitHubAPI.graphql(mock_context, "query { x }")

        assert "first problem" in str(exc.value)
        assert "second problem" in str(exc.value)

    @pytest.mark.asyncio
    async def test_missing_data_key_returns_empty_dict(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        assert await GitHubAPI.graphql(mock_context, "query { viewer { login } }") == {}
