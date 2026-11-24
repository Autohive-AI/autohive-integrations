from copy import deepcopy

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
PUSH = {
    "id": "123",
    "type": "PushEvent",
    "created_at": "2026-11-23T12:00:00Z",
    "repo": {"name": "example/project"},
    "actor": {"login": "octocat"},
    "public": False,
    "payload": {"ref": "refs/heads/feature", "before": "a" * 40, "head": "b" * 40},
}


def response(data, status=200, headers=None):
    return FetchResponse(status=status, headers=headers or {}, data=data)


def search_page(items, total=None, incomplete=False):
    return response(
        {"items": items, "total_count": len(items) if total is None else total, "incomplete_results": incomplete}
    )


def comparison(commits, total=None, status="ahead"):
    return response({"commits": commits, "total_commits": len(commits) if total is None else total, "status": status})


class TestSearchCommits:
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


class TestListUserActivity:
    async def test_filters_dates_repository_and_event_type_before_expansion(self, mock_context):
        old = {**PUSH, "created_at": "2026-11-22T10:00:00Z"}
        future = {**PUSH, "created_at": "2026-11-24T10:00:00Z"}
        other_repo = {**PUSH, "repo": {"name": "other/project"}}
        issue = {**PUSH, "type": "IssuesEvent"}
        mock_context.fetch.return_value = response([future, other_repo, PUSH, issue, old])
        result = await github.execute_action(
            "list_user_activity",
            {
                "username": "octocat",
                "since": "2026-11-23",
                "until": "2026-11-23",
                "organization": "EXAMPLE",
                "repository": "EXAMPLE/PROJECT",
                "event_types": ["PushEvent"],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert len(data["events"]) == 1
        assert data["events_scanned"] == 5
        assert data["events"][0]["payload"]["ref"] == "refs/heads/feature"
        assert data["events"][0]["commits_status"] == "not_requested"
        assert not data["truncated"]
        assert mock_context.fetch.await_count == 1
        assert mock_context.fetch.call_args.args[0] == "https://api.github.com/users/octocat/events"

    async def test_empty_connected_user_activity(self, mock_context):
        mock_context.fetch.side_effect = [response({"login": "octocat"}), response([])]
        result = await github.execute_action("list_user_activity", {}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["events"] == []
        assert result.result.data["oldest_scanned_at"] is None
        assert result.result.data["warnings"]

    async def test_filtered_full_page_still_fetches_next_page(self, mock_context):
        issue = {**PUSH, "type": "IssuesEvent"}
        mock_context.fetch.side_effect = [response([issue] * 100), response([PUSH])]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "event_types": ["PushEvent"]}, mock_context
        )
        assert len(result.result.data["events"]) == 1
        assert result.result.data["events_scanned"] == 101
        assert mock_context.fetch.await_count == 2

    async def test_page_budget_can_be_resumed(self, mock_context):
        mock_context.fetch.return_value = response([PUSH] * 100)
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "max_pages": 1}, mock_context
        )
        assert result.result.data["truncated"]
        assert result.result.data["next_page"] == 2

    async def test_provider_cap_is_partial_without_a_next_page(self, mock_context):
        mock_context.fetch.return_value = response([PUSH] * 100)
        result = await github.execute_action("list_user_activity", {"username": "octocat"}, mock_context)
        assert result.result.data["truncated"]
        assert result.result.data["next_page"] is None
        assert result.result.data["events_scanned"] == 300
        assert mock_context.fetch.await_count == 3

    @pytest.mark.parametrize("header_name", ["link", "Link"])
    @pytest.mark.parametrize("max_pages", [1, 2])
    async def test_short_page_honors_provider_continuation(self, mock_context, header_name, max_pages):
        mock_context.fetch.side_effect = [
            response(
                [PUSH] * 99, headers={header_name: '<https://api.github.com/users/octocat/events?page=2>; rel="next"'}
            ),
            response([PUSH]),
        ]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "max_pages": max_pages}, mock_context
        )
        data = result.result.data
        assert data["events_scanned"] == (99 if max_pages == 1 else 100)
        assert data["next_page"] == (2 if max_pages == 1 else None)
        assert data["truncated"] == (max_pages == 1)
        assert mock_context.fetch.await_count == max_pages

    async def test_scans_later_pages_after_older_events(self, mock_context):
        old = {**PUSH, "created_at": "2026-11-22T23:59:59Z"}
        mock_context.fetch.side_effect = [response([PUSH] * 99 + [old]), response([PUSH])]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "since": "2026-11-23"}, mock_context
        )
        assert len(result.result.data["events"]) == 100
        assert not result.result.data["truncated"]
        assert mock_context.fetch.await_count == 2

    async def test_expands_feature_branch_push_and_preserves_author_identity(self, mock_context):
        commit = {**COMMIT, "author": {"login": "someone-else"}}
        mock_context.fetch.side_effect = [response([PUSH]), comparison([commit])]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "include_commits": True}, mock_context
        )
        event = result.result.data["events"][0]
        assert event["commits_status"] == "complete"
        assert event["actor"] == "octocat"
        assert event["commits"][0]["author_login"] == "someone-else"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"https://api.github.com/repos/example/project/compare/{'a' * 40}...{'b' * 40}"
        assert call.kwargs["params"] == {"per_page": 100, "page": 1}

    async def test_expansion_budget_preserves_unexpanded_events(self, mock_context):
        mock_context.fetch.side_effect = [response([PUSH, {**PUSH, "id": "124"}]), comparison([COMMIT])]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "include_commits": True, "max_pushes": 1}, mock_context
        )
        assert [event["commits_status"] for event in result.result.data["events"]] == ["complete", "budget_exceeded"]
        assert mock_context.fetch.await_count == 2

    @pytest.mark.parametrize("max_pages, expected", [(1, "truncated"), (2, "complete")])
    async def test_comparison_pagination(self, mock_context, max_pages, expected):
        mock_context.fetch.side_effect = [response([PUSH]), comparison([COMMIT] * 100, 101), comparison([COMMIT], 101)]
        result = await github.execute_action(
            "list_user_activity",
            {"username": "octocat", "include_commits": True, "max_commit_pages": max_pages},
            mock_context,
        )
        event = result.result.data["events"][0]
        assert event["commits_status"] == expected
        assert len(event["commits"]) == (100 if max_pages == 1 else 101)

    @pytest.mark.parametrize("before", [None, "0" * 40])
    async def test_missing_push_range_does_not_fetch_unrelated_history(self, mock_context, before):
        push = deepcopy(PUSH)
        push["payload"]["before"] = before
        mock_context.fetch.return_value = response([push])
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "include_commits": True}, mock_context
        )
        assert result.result.data["events"][0]["commits_status"] == "unavailable"
        assert mock_context.fetch.await_count == 1

    @pytest.mark.parametrize("failure", [response({"message": "Not Found"}, 404), RuntimeError("Objects unavailable")])
    async def test_failed_expansion_preserves_other_events(self, mock_context, failure):
        mock_context.fetch.side_effect = [response([PUSH, {**PUSH, "type": "IssuesEvent"}]), failure]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "include_commits": True}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["events"]) == 2
        assert result.result.data["events"][0]["commits_status"] == "unavailable"
        assert result.result.data["events"][0]["commits_warning"]

    async def test_diverged_history_is_flagged(self, mock_context):
        mock_context.fetch.side_effect = [response([PUSH]), comparison([COMMIT], status="diverged")]
        result = await github.execute_action(
            "list_user_activity", {"username": "octocat", "include_commits": True}, mock_context
        )
        event = result.result.data["events"][0]
        assert event["commits_status"] == "unavailable"
        assert "diverged" in event["commits_warning"]

    async def test_pr_payload_is_compact(self, mock_context):
        event = {
            **PUSH,
            "type": "PullRequestEvent",
            "payload": {
                "action": "opened",
                "pull_request": {
                    "number": 42,
                    "title": "Daily updates",
                    "body": "x" * 2000,
                    "html_url": "https://github.com/example/project/pull/42",
                    "base": {"large": "object"},
                },
            },
        }
        mock_context.fetch.return_value = response([event])
        result = await github.execute_action("list_user_activity", {"username": "octocat"}, mock_context)
        pr = result.result.data["events"][0]["payload"]["pull_request"]
        assert pr["number"] == 42
        assert len(pr["body"]) == 1000
        assert "base" not in pr


@pytest.mark.parametrize("action", ["search_commits", "list_user_activity"])
class TestActivityErrors:
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
