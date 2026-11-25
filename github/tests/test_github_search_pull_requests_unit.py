import json
from pathlib import Path

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType
from jsonschema import validate

from github import github

pytestmark = pytest.mark.unit

PULL_REQUEST = {
    "number": 42,
    "title": "Add daily summaries",
    "html_url": "https://github.com/example/project/pull/42",
    "repository_url": "https://api.github.com/repos/example/project",
    "user": {"login": "octocat"},
    "state": "open",
    "draft": True,
    "created_at": "2026-11-23T11:00:00Z",
    "updated_at": "2026-11-23T12:00:00Z",
    "closed_at": None,
    "pull_request": {"url": "https://api.github.com/repos/example/project/pulls/42"},
    "body": "Long content that should not appear in the summary",
}


def search_page(items, total=None, incomplete=False):
    return FetchResponse(
        status=200,
        headers={},
        data={"items": items, "total_count": len(items) if total is None else total, "incomplete_results": incomplete},
    )


class TestSearchPullRequests:
    async def test_defaults_to_connected_author_and_returns_compact_schema(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"login": "octocat"}),
            search_page([PULL_REQUEST]),
        ]
        result = await github.execute_action("search_pull_requests", {}, mock_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["author"] == "octocat"
        assert data["query"] == "is:pr author:octocat"
        assert data["pull_requests"][0]["repository"] == "example/project"
        assert data["pull_requests"][0]["draft"] is True
        assert data["pull_requests"][0]["closed_at"] is None
        assert "body" not in data["pull_requests"][0]
        assert data["warnings"]
        assert not data["truncated"]
        assert data["next_page"] is None
        assert mock_context.fetch.call_args_list[0].args[0] == "https://api.github.com/user"
        config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8"))
        validate(data, config["actions"]["search_pull_requests"]["output_schema"])

    async def test_author_scope_dates_state_and_sort_are_sent_to_search(self, mock_context):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_pull_requests",
            {
                "author": "octocat",
                "organization": "example",
                "repositories": ["example/project", "example/other"],
                "state": "merged",
                "since": "2026-11-23T00:00:00+13:00",
                "until": "2026-11-23",
                "date_field": "merged",
                "sort": "created",
                "order": "asc",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.github.com/search/issues"
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "q": "is:pr author:octocat repo:example/project repo:example/other "
            "is:merged merged:2026-11-22T11:00:00Z..2026-11-23T23:59:59Z",
            "sort": "created",
            "order": "asc",
            "per_page": 100,
            "page": 1,
        }
        assert mock_context.fetch.await_count == 1

    async def test_organization_scope_without_selected_repositories(self, mock_context):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_pull_requests", {"author": "octocat", "organization": "example", "repositories": []}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["query"] == "is:pr author:octocat org:example"

    @pytest.mark.parametrize("state,qualifier", [("all", ""), ("open", " state:open"), ("closed", " state:closed")])
    async def test_state_filter(self, mock_context, state, qualifier):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_pull_requests", {"author": "octocat", "state": state}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["query"] == f"is:pr author:octocat{qualifier}"

    @pytest.mark.parametrize("date_field", ["created", "updated", "closed", "merged"])
    @pytest.mark.parametrize(
        "bounds,expected",
        [
            ({"since": "2026-11-23T12:00:00.500Z"}, ">=2026-11-23T12:00:01Z"),
            ({"until": "2026-11-23T12:00:00.500Z"}, "<=2026-11-23T12:00:00Z"),
            ({"since": "2026-11-23", "until": "2026-11-23"}, "2026-11-23T00:00:00Z..2026-11-23T23:59:59Z"),
            ({"until": "2026-11-23t12:00:00Z"}, "<=2026-11-23T12:00:00Z"),
        ],
    )
    async def test_date_filters_use_inclusive_second_precision(self, mock_context, date_field, bounds, expected):
        mock_context.fetch.return_value = search_page([])
        result = await github.execute_action(
            "search_pull_requests", {"author": "octocat", "date_field": date_field, **bounds}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["query"] == f"is:pr author:octocat {date_field}:{expected}"

    async def test_subsecond_interval_without_searchable_second_avoids_request(self, mock_context):
        result = await github.execute_action(
            "search_pull_requests",
            {"author": "octocat", "since": "2026-11-23T12:00:00.100Z", "until": "2026-11-23T12:00:00.900Z"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["pull_requests"] == []
        assert result.result.data["pages_fetched"] == 0
        mock_context.fetch.assert_not_awaited()

    async def test_pagination_accumulates_repositories_and_incomplete_flag(self, mock_context):
        other = {**PULL_REQUEST, "repository_url": "https://api.github.com/repos/example/other"}
        mock_context.fetch.side_effect = [search_page([PULL_REQUEST] * 100, 101, True), search_page([other], 101)]
        result = await github.execute_action(
            "search_pull_requests", {"author": "octocat", "max_pages": 2}, mock_context
        )
        data = result.result.data
        assert len(data["pull_requests"]) == 101
        assert data["pull_requests"][-1]["repository"] == "example/other"
        assert data["pages_fetched"] == 2
        assert data["incomplete_results"]
        assert not data["truncated"]
        assert any("incomplete" in warning for warning in data["warnings"])
        assert [call.kwargs["params"]["page"] for call in mock_context.fetch.call_args_list] == [1, 2]

    async def test_budget_returns_continuation(self, mock_context):
        mock_context.fetch.return_value = search_page([PULL_REQUEST] * 100, 201)
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.result.data["next_page"] == 2
        assert result.result.data["truncated"]
        assert mock_context.fetch.await_count == 1

    async def test_search_cap_has_no_page_eleven(self, mock_context):
        mock_context.fetch.return_value = search_page([PULL_REQUEST] * 100, 1500)
        result = await github.execute_action(
            "search_pull_requests", {"author": "octocat", "page": 10, "max_pages": 10}, mock_context
        )
        assert result.result.data["next_page"] is None
        assert result.result.data["truncated"]
        assert mock_context.fetch.await_count == 1

    async def test_deleted_author_is_nullable(self, mock_context):
        mock_context.fetch.return_value = search_page([{**PULL_REQUEST, "user": None}])
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["pull_requests"][0]["author"] is None

    async def test_org_repository_mismatch_is_not_silently_broadened(self, mock_context):
        result = await github.execute_action(
            "search_pull_requests",
            {"author": "octocat", "organization": "example", "repositories": ["other/project"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()

    async def test_issue_result_is_not_returned_as_a_pull_request(self, mock_context):
        issue = {key: value for key, value in PULL_REQUEST.items() if key != "pull_request"}
        mock_context.fetch.return_value = search_page([issue])
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.parametrize("bounds", [{"since": "invalid"}, {"since": "2026-11-24", "until": "2026-11-23"}])
    async def test_invalid_dates_fail_before_network(self, mock_context, bounds):
        result = await github.execute_action("search_pull_requests", {"author": "octocat", **bounds}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.parametrize("status", [401, 403, 404, 422, 500, 503])
    async def test_http_errors_are_not_empty_successes(self, mock_context, status):
        mock_context.fetch.return_value = FetchResponse(status=status, headers={}, data={"message": "Request rejected"})
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert str(status) in result.result.message

    async def test_transport_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Connection failed")
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    async def test_missing_credentials(self, mock_context):
        mock_context.auth["credentials"] = {}
        result = await github.execute_action("search_pull_requests", {"author": "octocat"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.parametrize(
        "inputs",
        [
            {"author": "octocat org:other"},
            {"organization": "example repo:other/project"},
            {"repositories": ["../bad/path"]},
            {"repositories": ["example/project", "example/project"]},
            {"repositories": [f"example/repo-{i}" for i in range(11)]},
            {"state": "invalid"},
            {"date_field": "pushed"},
            {"sort": "merged"},
            {"order": "invalid"},
            {"page": 11},
            {"max_pages": 0},
        ],
    )
    async def test_invalid_inputs_are_rejected(self, mock_context, inputs):
        result = await github.execute_action("search_pull_requests", inputs, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()
