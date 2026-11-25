import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

COMMIT = {
    "sha": "abc123",
    "html_url": "https://github.com/example/project/commit/abc123",
    "author": {"login": "octocat"},
    "committer": None,
    "commit": {"message": "Add daily summaries", "author": None, "committer": None},
    "repository": {"full_name": "example/project"},
}


def response(data, status=200, headers=None):
    return FetchResponse(status=status, headers=headers or {}, data=data)


def search_page(items, total=None, incomplete=False):
    return response(
        {"items": items, "total_count": len(items) if total is None else total, "incomplete_results": incomplete}
    )


class TestSearchCommits:
    @pytest.mark.parametrize(
        "until,expected",
        [
            ("2026-11-23t12:00:00Z", "2026-11-23T12:00:00Z"),
            ("2026-11-23T12:00:00Z", "2026-11-23T12:00:00Z"),
            ("2026-11-23 12:00:00Z", "2026-11-23T12:00:00Z"),
            ("2026-11-23", "2026-11-23T23:59:59Z"),
        ],
    )
    async def test_until_expands_only_date_inputs(self, mock_context, until, expected):
        mock_context.fetch.return_value = search_page([COMMIT])
        result = await github.execute_action("search_commits", {"username": "octocat", "until": until}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["commits"][0]["sha"] == COMMIT["sha"]
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == f"author:octocat author-date:<={expected}"

    async def test_connected_user_and_compact_commits(self, mock_context):
        mock_context.fetch.side_effect = [response({"login": "octocat"}), search_page([COMMIT])]
        result = await github.execute_action("search_commits", {}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["username"] == "octocat"
        assert data["commits"][0]["repository"] == "example/project"
        assert data["commits"][0]["author_login"] == "octocat"
        assert data["commits"][0]["committer_login"] is None
        assert data["commits"][0]["author"]["date"] is None
        assert data["next_page"] is None
        assert not data["truncated"]
        assert mock_context.fetch.call_args_list[0].args[0] == "https://api.github.com/user"

    async def test_filters_are_sent_as_encoded_query_params(self, mock_context):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_commits",
            {
                "username": "octocat",
                "since": "2026-11-23T00:00:00+13:00",
                "until": "2026-11-23",
                "organization": "example",
                "repository": "example/project",
                "include_merges": False,
                "date_field": "committer-date",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.github.com/search/commits"
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "q": "author:octocat org:example repo:example/project "
            "committer-date:2026-11-22T11:00:00Z..2026-11-23T23:59:59Z merge:false",
            "sort": "committer-date",
            "order": "desc",
            "per_page": 100,
            "page": 1,
        }

    @pytest.mark.parametrize("date_field", ["author-date", "committer-date"])
    @pytest.mark.parametrize(
        "bounds,expected",
        [
            ({"since": "2026-11-23T12:00:00.500Z"}, ">=2026-11-23T12:00:01Z"),
            ({"until": "2026-11-23T12:00:00.500Z"}, "<=2026-11-23T12:00:00Z"),
            (
                {"since": "2026-11-23T12:00:00.500Z", "until": "2026-11-23T12:00:01.500Z"},
                "2026-11-23T12:00:01Z..2026-11-23T12:00:01Z",
            ),
            ({"since": "2026-11-23T23:59:59.999Z"}, ">=2026-11-24T00:00:00Z"),
        ],
    )
    async def test_second_precision_bounds(self, mock_context, date_field, bounds, expected):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_commits", {"username": "octocat", "date_field": date_field, **bounds}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == f"author:octocat {date_field}:{expected}"

    async def test_subsecond_interval_without_indexed_seconds(self, mock_context):
        result = await github.execute_action(
            "search_commits",
            {"username": "octocat", "since": "2026-11-23T12:00:00.100Z", "until": "2026-11-23T12:00:00.900Z"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["commits"] == []
        assert result.result.data["pages_fetched"] == 0
        mock_context.fetch.assert_not_awaited()

    async def test_pagination_and_incomplete_results_accumulate(self, mock_context):
        mock_context.fetch.side_effect = [search_page([COMMIT] * 100, 101, True), search_page([COMMIT], 101)]
        result = await github.execute_action("search_commits", {"username": "octocat", "max_pages": 2}, mock_context)
        data = result.result.data
        assert len(data["commits"]) == 101
        assert data["incomplete_results"]
        assert not data["truncated"]
        assert data["pages_fetched"] == 2
        assert [call.kwargs["params"]["page"] for call in mock_context.fetch.call_args_list] == [1, 2]

    async def test_page_budget_returns_continuation(self, mock_context):
        mock_context.fetch.return_value = search_page([COMMIT] * 100, 201)
        result = await github.execute_action("search_commits", {"username": "octocat"}, mock_context)
        assert result.result.data["next_page"] == 2
        assert result.result.data["truncated"]
        assert mock_context.fetch.await_count == 1

    async def test_search_cap_does_not_request_page_eleven(self, mock_context):
        mock_context.fetch.return_value = search_page([COMMIT] * 100, 1500)
        result = await github.execute_action("search_commits", {"username": "octocat", "page": 10}, mock_context)
        assert result.result.data["next_page"] is None
        assert result.result.data["truncated"]
        assert mock_context.fetch.await_count == 1


@pytest.mark.parametrize("action", ["search_commits"])
class TestCommitSearchErrors:
    @pytest.mark.parametrize(
        "bounds", [{"since": "invalid"}, {"until": "2026-13-01"}, {"since": "2026-11-24", "until": "2026-11-23"}]
    )
    async def test_bad_dates_fail_before_network(self, mock_context, action, bounds):
        result = await github.execute_action(action, {"username": "octocat", **bounds}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
    async def test_http_errors_are_not_empty_successes(self, mock_context, action, status):
        mock_context.fetch.return_value = response({"message": "Request rejected"}, status)
        result = await github.execute_action(action, {"username": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert str(status) in result.result.message

    async def test_transport_error(self, mock_context, action):
        mock_context.fetch.side_effect = RuntimeError("Connection failed")
        result = await github.execute_action(action, {"username": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    async def test_missing_credentials(self, mock_context, action):
        mock_context.auth["credentials"] = {}
        result = await github.execute_action(action, {"username": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.parametrize(
        "inputs", [{"max_pages": 0}, {"username": "octocat org:other"}, {"repository": "../bad/path"}]
    )
    async def test_invalid_inputs_are_rejected(self, mock_context, action, inputs):
        result = await github.execute_action(action, inputs, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()
