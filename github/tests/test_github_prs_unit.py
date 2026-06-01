import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("github_mod", os.path.join(_parent, "github.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

github = _mod.github

pytestmark = pytest.mark.unit

SAMPLE_USER = {"login": "octocat", "id": 1, "avatar_url": "https://github.com/octocat.png"}

SAMPLE_REPO_REF = {"name": "Hello-World", "full_name": "octocat/Hello-World", "id": 1}

SAMPLE_PR = {
    "id": 100,
    "node_id": "PR_001",
    "number": 7,
    "title": "Fix the bug",
    "body": "This PR fixes the bug",
    "state": "open",
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-02T00:00:00Z",
    "closed_at": None,
    "merged_at": None,
    "draft": False,
    "merged": False,
    "mergeable": True,
    "mergeable_state": "clean",
    "merge_commit_sha": None,
    "html_url": "https://github.com/octocat/Hello-World/pull/7",
    "url": "https://api.github.com/repos/octocat/Hello-World/pulls/7",
    "diff_url": "https://github.com/octocat/Hello-World/pull/7.diff",
    "patch_url": "https://github.com/octocat/Hello-World/pull/7.patch",
    "user": SAMPLE_USER,
    "assignee": None,
    "assignees": [],
    "requested_reviewers": [],
    "requested_teams": [],
    "labels": [],
    "milestone": None,
    "author_association": "OWNER",
    "comments": 0,
    "review_comments": 0,
    "commits": 1,
    "additions": 10,
    "deletions": 2,
    "changed_files": 1,
    "head": {"ref": "feature-branch", "sha": "abc123", "repo": SAMPLE_REPO_REF},
    "base": {"ref": "main", "sha": "def456", "repo": SAMPLE_REPO_REF},
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


class TestGetPullRequest:
    @pytest.mark.asyncio
    async def test_returns_pr_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PR)

        result = await github.execute_action(
            "get_pull_request", {"owner": "octocat", "repo": "Hello-World", "pull_number": 7}, mock_context
        )

        assert result.result.data["number"] == 7
        assert result.result.data["title"] == "Fix the bug"
        assert result.result.data["head"]["ref"] == "feature-branch"

    @pytest.mark.asyncio
    async def test_url_includes_pull_number(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PR)

        await github.execute_action(
            "get_pull_request", {"owner": "octocat", "repo": "Hello-World", "pull_number": 7}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "pulls/7" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("PR not found")

        result = await github.execute_action(
            "get_pull_request", {"owner": "octocat", "repo": "Hello-World", "pull_number": 7}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "PR not found" in result.result.message


class TestListPullRequests:
    @pytest.mark.asyncio
    async def test_returns_prs_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PR])

        result = await github.execute_action(
            "list_pull_requests", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["number"] == 7

    @pytest.mark.asyncio
    async def test_uses_rest_pulls_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action("list_pull_requests", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "repos/octocat/Hello-World/pulls" in url
        assert "search/issues" not in url

    @pytest.mark.asyncio
    async def test_passes_state_sort_direction_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "state": "open", "sort": "created", "direction": "asc"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["state"] == "open"
        assert params["sort"] == "created"
        assert params["direction"] == "asc"

    @pytest.mark.asyncio
    async def test_filters_by_author_client_side(self, mock_context):
        other_pr = {**SAMPLE_PR, "number": 8, "user": {**SAMPLE_USER, "login": "someone-else"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PR, other_pr])

        result = await github.execute_action(
            "list_pull_requests", {"owner": "octocat", "repo": "Hello-World", "author": "octocat"}, mock_context
        )

        assert [pr["number"] for pr in result.result.data] == [7]

    @pytest.mark.asyncio
    async def test_limit_caps_returned_list(self, mock_context):
        pr2 = {**SAMPLE_PR, "number": 8}
        pr3 = {**SAMPLE_PR, "number": 9}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PR, pr2, pr3])

        result = await github.execute_action(
            "list_pull_requests", {"owner": "octocat", "repo": "Hello-World", "limit": 2}, mock_context
        )

        assert len(result.result.data) == 2

    @pytest.mark.asyncio
    async def test_limit_returns_first_n_without_exhausting_pages(self, mock_context):
        # A plain limit on a huge repo must return the first N PRs, not raise the
        # max_pages TimeoutError. Every page is full (100 items) so without early
        # exit pagination would run to the cap and error.
        full_page = [{**SAMPLE_PR, "number": i} for i in range(100)]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=full_page)

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "limit": 10, "max_pages": 2},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data) == 10
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_author_filter_with_limit_stops_early(self, mock_context):
        # A client-side filter must not defeat the limit early-exit: if page 1
        # already has enough matching PRs, pagination must stop there instead of
        # scanning to max_pages and raising a spurious TimeoutError.
        full_page = [{**SAMPLE_PR, "number": i, "user": SAMPLE_USER} for i in range(100)]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=full_page)

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "author": "octocat", "limit": 10, "max_pages": 2},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data) == 10
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_author_filter_thins_pages_then_paginates(self, mock_context):
        # When a full page is entirely filtered out, pagination must still detect
        # it as a full page and advance, rather than mistaking the thinned result
        # for a last (short) page and stopping early.
        others = [{**SAMPLE_PR, "number": i, "user": {**SAMPLE_USER, "login": "someone-else"}} for i in range(100)]
        match_page = [{**SAMPLE_PR, "number": 999, "user": SAMPLE_USER}]
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=others),
            FetchResponse(status=200, headers={}, data=match_page),
        ]

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "author": "octocat", "max_pages": 5},
            mock_context,
        )

        assert [pr["number"] for pr in result.result.data] == [999]
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_before_date_is_inclusive_of_whole_day(self, mock_context):
        # before="2024-01-01" must include a PR created during that day
        # (matching the old Search API created:<= semantics), not exclude it on
        # a raw string comparison.
        same_day = {**SAMPLE_PR, "number": 1, "created_at": "2024-01-01T09:00:00Z"}
        next_day = {**SAMPLE_PR, "number": 2, "created_at": "2024-01-02T00:00:00Z"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[same_day, next_day])

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "before": "2024-01-01"},
            mock_context,
        )

        assert [pr["number"] for pr in result.result.data] == [1]

    @pytest.mark.asyncio
    async def test_after_date_is_inclusive_of_whole_day(self, mock_context):
        before_day = {**SAMPLE_PR, "number": 1, "created_at": "2024-01-01T09:00:00Z"}
        on_day = {**SAMPLE_PR, "number": 2, "created_at": "2024-01-02T09:00:00Z"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[before_day, on_day])

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "after": "2024-01-02"},
            mock_context,
        )

        assert [pr["number"] for pr in result.result.data] == [2]

    @pytest.mark.asyncio
    async def test_max_pages_cap_stops_unbounded_pagination(self, mock_context):
        # Each page returns a full 100 items so paginated_fetch would keep going
        # forever; the max_pages cap must stop it and surface a TimeoutError
        # which the decorator turns into an ActionError.
        full_page = [SAMPLE_PR] * 100
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=full_page)

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World", "max_pages": 2},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "2 pages" in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_default_max_pages_is_ten(self, mock_context):
        # When the caller omits max_pages, the default cap of 10 must apply.
        full_page = [SAMPLE_PR] * 100
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=full_page)

        result = await github.execute_action(
            "list_pull_requests",
            {"owner": "octocat", "repo": "Hello-World"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 10


class TestCreatePullRequest:
    @pytest.mark.asyncio
    async def test_creates_pr(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PR)

        result = await github.execute_action(
            "create_pull_request",
            {
                "owner": "octocat",
                "repo": "Hello-World",
                "title": "Fix the bug",
                "head": "feature-branch",
                "base": "main",
            },
            mock_context,
        )

        assert result.result.data["number"] == 7
        assert result.result.data["title"] == "Fix the bug"

    @pytest.mark.asyncio
    async def test_request_uses_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PR)

        await github.execute_action(
            "create_pull_request",
            {"owner": "octocat", "repo": "Hello-World", "title": "Fix", "head": "feature", "base": "main"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_contains_required_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PR)

        await github.execute_action(
            "create_pull_request",
            {"owner": "octocat", "repo": "Hello-World", "title": "Fix", "head": "feature", "base": "main"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["title"] == "Fix"
        assert payload["head"] == "feature"
        assert payload["base"] == "main"


class TestMergePullRequest:
    @pytest.mark.asyncio
    async def test_merge_returns_merged_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"sha": "abc123", "merged": True, "message": "Pull Request successfully merged"},
        )

        result = await github.execute_action(
            "merge_pull_request",
            {"owner": "octocat", "repo": "Hello-World", "pull_number": 7},
            mock_context,
        )

        assert result.result.data["merged"] is True
        assert result.result.data["sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_request_uses_put(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"sha": "abc"})

        await github.execute_action(
            "merge_pull_request",
            {"owner": "octocat", "repo": "Hello-World", "pull_number": 7},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PUT"
        assert "pulls/7/merge" in mock_context.fetch.call_args.args[0]


class TestAddPullRequestReviewers:
    @pytest.mark.asyncio
    async def test_adds_reviewers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={"requested_reviewers": [{"login": "reviewer1", "id": 2}], "requested_teams": []},
        )

        result = await github.execute_action(
            "add_pull_request_reviewers",
            {"owner": "octocat", "repo": "Hello-World", "pull_number": 7, "reviewers": ["reviewer1"]},
            mock_context,
        )

        assert len(result.result.data["requested_reviewers"]) == 1
        assert result.result.data["requested_reviewers"][0]["login"] == "reviewer1"


class TestListPullRequestReviewers:
    @pytest.mark.asyncio
    async def test_returns_reviewers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"users": [{"login": "reviewer1", "id": 2, "avatar_url": "https://..."}], "teams": []},
        )

        result = await github.execute_action(
            "list_pull_request_reviewers",
            {"owner": "octocat", "repo": "Hello-World", "pull_number": 7},
            mock_context,
        )

        assert len(result.result.data["users"]) == 1
        assert result.result.data["users"][0]["login"] == "reviewer1"


class TestCreatePullRequestReview:
    @pytest.mark.asyncio
    async def test_creates_review(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": 99,
                "body": "LGTM",
                "state": "APPROVED",
                "submitted_at": "2021-01-01T00:00:00Z",
                "user": {"login": "reviewer1", "avatar_url": "https://..."},
                "html_url": "https://github.com/octocat/Hello-World/pull/7#pullrequestreview-99",
            },
        )

        result = await github.execute_action(
            "create_pull_request_review",
            {"owner": "octocat", "repo": "Hello-World", "pull_number": 7, "body": "LGTM", "event": "APPROVE"},
            mock_context,
        )

        assert result.result.data["id"] == 99
        assert result.result.data["state"] == "APPROVED"
