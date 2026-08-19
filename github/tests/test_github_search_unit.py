import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit


def _envelope(items, total_count=None, incomplete_results=False):
    """Build a Search API response envelope around ``items``."""
    return {
        "total_count": len(items) if total_count is None else total_count,
        "incomplete_results": incomplete_results,
        "items": items,
    }


SAMPLE_REPO_ITEM = {
    "id": 1296269,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "owner": {"login": "octocat", "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4"},
    "description": "My first repository on GitHub!",
    "language": "Python",
    "stargazers_count": 80,
    "forks_count": 9,
    "open_issues_count": 3,
    "topics": ["octocat", "example"],
    "private": False,
    "updated_at": "2024-01-02T00:00:00Z",
    "html_url": "https://github.com/octocat/Hello-World",
}

SAMPLE_ISSUE_ITEM = {
    "number": 132,
    "title": "Widget fails to render",
    "state": "open",
    "user": {"login": "octocat", "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4"},
    "repository_url": "https://api.github.com/repos/octocat/Hello-World",
    "labels": [{"name": "bug"}, {"name": "help wanted"}],
    "comments": 4,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "html_url": "https://github.com/octocat/Hello-World/issues/132",
}

SAMPLE_PR_ITEM = {
    "number": 347,
    "title": "Fix the widget renderer",
    "state": "closed",
    "user": {"login": "hubot", "avatar_url": "https://avatars.githubusercontent.com/u/583232?v=4"},
    "repository_url": "https://api.github.com/repos/octocat/Hello-World",
    "labels": [],
    "comments": 1,
    "created_at": "2024-02-01T00:00:00Z",
    "updated_at": "2024-02-03T00:00:00Z",
    "html_url": "https://github.com/octocat/Hello-World/pull/347",
    "draft": False,
    "pull_request": {
        "url": "https://api.github.com/repos/octocat/Hello-World/pulls/347",
        "html_url": "https://github.com/octocat/Hello-World/pull/347",
        "merged_at": "2024-02-03T10:00:00Z",
    },
}

SAMPLE_CODE_ITEM = {
    "name": "helpers.py",
    "path": "src/helpers.py",
    "sha": "8b1ddb6c0ffee1234567890abcdef1234567890a",
    "repository": {"full_name": "octocat/Hello-World"},
    "html_url": "https://github.com/octocat/Hello-World/blob/main/src/helpers.py",
}

SAMPLE_COMMIT_ITEM = {
    "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
    "html_url": "https://github.com/octocat/Hello-World/commit/6dcb09b",
    "commit": {
        "message": "Fix all the bugs",
        "author": {"name": "Monalisa Octocat", "email": "octo@github.com", "date": "2024-03-01T00:00:00Z"},
        "committer": {"name": "Monalisa Octocat", "email": "octo@github.com", "date": "2024-03-01T00:00:00Z"},
    },
    "repository": {"full_name": "octocat/Hello-World"},
}

SAMPLE_USER_ITEM = {
    "login": "octocat",
    "id": 583231,
    "type": "User",
    "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
    "html_url": "https://github.com/octocat",
}

SAMPLE_ORG_ITEM = {
    "login": "github",
    "id": 9919,
    "type": "Organization",
    "avatar_url": "https://avatars.githubusercontent.com/u/9919?v=4",
    "html_url": "https://github.com/github",
}


# ---- Repository search ----


class TestSearchRepositories:
    @pytest.mark.asyncio
    async def test_returns_shaped_repositories(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_REPO_ITEM]))

        result = await github.execute_action("search_repositories", {"query": "autohive"}, mock_context)

        item = result.result.data["items"][0]
        assert item["full_name"] == "octocat/Hello-World"
        assert item["stars"] == 80
        assert item["forks"] == 9
        assert item["language"] == "Python"
        assert item["url"] == "https://github.com/octocat/Hello-World"
        assert item["owner"]["login"] == "octocat"

    @pytest.mark.asyncio
    async def test_hits_repositories_endpoint_with_sort_and_order(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_REPO_ITEM]))

        await github.execute_action(
            "search_repositories",
            {"query": "autohive", "sort": "stars", "order": "desc"},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0].endswith("/search/repositories")
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["q"] == "autohive"
        assert params["sort"] == "stars"
        assert params["order"] == "desc"

    @pytest.mark.asyncio
    async def test_surfaces_total_count_and_flags(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=_envelope([SAMPLE_REPO_ITEM], total_count=42, incomplete_results=True)
        )

        result = await github.execute_action("search_repositories", {"query": "autohive"}, mock_context)

        assert result.result.data["total_count"] == 42
        assert result.result.data["incomplete_results"] is True
        assert result.result.data["capped"] is False

    @pytest.mark.asyncio
    async def test_capped_when_total_exceeds_search_ceiling(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=_envelope([SAMPLE_REPO_ITEM], total_count=50_000)
        )

        result = await github.execute_action("search_repositories", {"query": "stars:>1"}, mock_context)

        assert result.result.data["total_count"] == 50_000
        assert result.result.data["capped"] is True
        assert len(result.result.data["items"]) == 1

    @pytest.mark.asyncio
    async def test_follows_pagination_across_two_pages(self, mock_context):
        page_one = [dict(SAMPLE_REPO_ITEM, id=index, full_name=f"octocat/repo-{index}") for index in range(100)]
        page_two = [dict(SAMPLE_REPO_ITEM, id=100, full_name="octocat/repo-100")]
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=_envelope(page_one, total_count=101)),
            FetchResponse(status=200, headers={}, data=_envelope(page_two, total_count=101)),
        ]

        result = await github.execute_action("search_repositories", {"query": "autohive"}, mock_context)

        assert mock_context.fetch.await_count == 2
        assert len(result.result.data["items"]) == 101
        assert result.result.data["items"][-1]["full_name"] == "octocat/repo-100"

    @pytest.mark.asyncio
    async def test_limit_truncates_items(self, mock_context):
        items = [dict(SAMPLE_REPO_ITEM, full_name=f"octocat/repo-{index}") for index in range(5)]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope(items))

        result = await github.execute_action("search_repositories", {"query": "autohive", "limit": 2}, mock_context)

        assert len(result.result.data["items"]) == 2

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("search_repositories", {"query": "autohive"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


# ---- Code search ----


class TestSearchCode:
    @pytest.mark.asyncio
    async def test_returns_shaped_code_hits(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_CODE_ITEM]))

        result = await github.execute_action(
            "search_code", {"query": "addClass repo:octocat/Hello-World"}, mock_context
        )

        item = result.result.data["items"][0]
        assert item["path"] == "src/helpers.py"
        assert item["repository"] == "octocat/Hello-World"
        assert item["url"] == "https://github.com/octocat/Hello-World/blob/main/src/helpers.py"

    @pytest.mark.asyncio
    async def test_hits_code_endpoint_without_injecting_qualifiers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_CODE_ITEM]))

        await github.execute_action("search_code", {"query": "addClass org:autohive-ai"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/search/code")
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "addClass org:autohive-ai"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("rate limit exceeded")

        result = await github.execute_action("search_code", {"query": "addClass"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit exceeded" in result.result.message


# ---- Commit search ----


class TestSearchCommits:
    @pytest.mark.asyncio
    async def test_returns_shaped_commits(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_COMMIT_ITEM]))

        result = await github.execute_action("search_commits", {"query": "repo:octocat/Hello-World bug"}, mock_context)

        item = result.result.data["items"][0]
        assert item["sha"] == "6dcb09b5b57875f334f61aebed695e2e4193db5e"
        assert item["message"] == "Fix all the bugs"
        assert item["author"]["name"] == "Monalisa Octocat"
        assert item["repository"] == "octocat/Hello-World"
        assert item["url"] == "https://github.com/octocat/Hello-World/commit/6dcb09b"

    @pytest.mark.asyncio
    async def test_hits_commits_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_COMMIT_ITEM]))

        await github.execute_action(
            "search_commits",
            {"query": "repo:octocat/Hello-World bug", "sort": "author-date"},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0].endswith("/search/commits")
        assert mock_context.fetch.call_args.kwargs["params"]["sort"] == "author-date"


# ---- Issue search ----


class TestSearchIssues:
    @pytest.mark.asyncio
    async def test_returns_shaped_issues(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ISSUE_ITEM]))

        result = await github.execute_action(
            "search_issues", {"query": "repo:octocat/Hello-World widget"}, mock_context
        )

        item = result.result.data["items"][0]
        assert item["number"] == 132
        assert item["title"] == "Widget fails to render"
        assert item["state"] == "open"
        assert item["author"]["login"] == "octocat"
        assert item["repository"] == "octocat/Hello-World"
        assert item["labels"] == ["bug", "help wanted"]
        assert item["url"] == "https://github.com/octocat/Hello-World/issues/132"

    @pytest.mark.asyncio
    async def test_injects_is_issue_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ISSUE_ITEM]))

        await github.execute_action("search_issues", {"query": "widget"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/search/issues")
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "widget is:issue"

    @pytest.mark.asyncio
    async def test_does_not_duplicate_caller_supplied_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ISSUE_ITEM]))

        await github.execute_action("search_issues", {"query": "widget type:issue"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "widget type:issue"

    @pytest.mark.asyncio
    async def test_respects_caller_choosing_pull_requests(self, mock_context):
        """A caller who wrote is:pr must not get a contradictory is:issue bolted on."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_PR_ITEM]))

        await github.execute_action("search_issues", {"query": "widget is:pr"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "widget is:pr"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Validation Failed")

        result = await github.execute_action("search_issues", {"query": "widget"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Validation Failed" in result.result.message


# ---- Pull request search ----


class TestSearchPullRequests:
    @pytest.mark.asyncio
    async def test_returns_shaped_pull_requests(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_PR_ITEM]))

        result = await github.execute_action(
            "search_pull_requests", {"query": "repo:octocat/Hello-World widget"}, mock_context
        )

        item = result.result.data["items"][0]
        assert item["number"] == 347
        assert item["state"] == "closed"
        assert item["author"]["login"] == "hubot"
        assert item["repository"] == "octocat/Hello-World"
        assert item["draft"] is False
        assert item["merged_at"] == "2024-02-03T10:00:00Z"
        assert item["url"] == "https://github.com/octocat/Hello-World/pull/347"

    @pytest.mark.asyncio
    async def test_uses_issues_endpoint_with_pull_request_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_PR_ITEM]))

        await github.execute_action("search_pull_requests", {"query": "widget"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/search/issues")
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "widget is:pr"

    @pytest.mark.asyncio
    async def test_does_not_duplicate_caller_supplied_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_PR_ITEM]))

        await github.execute_action("search_pull_requests", {"query": "widget is:pr"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "widget is:pr"


# ---- User and organization search ----


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_returns_shaped_users(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_USER_ITEM]))

        result = await github.execute_action("search_users", {"query": "octocat"}, mock_context)

        item = result.result.data["items"][0]
        assert item["login"] == "octocat"
        assert item["type"] == "User"
        assert item["url"] == "https://github.com/octocat"

    @pytest.mark.asyncio
    async def test_injects_type_user_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_USER_ITEM]))

        await github.execute_action("search_users", {"query": "octocat"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/search/users")
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "octocat type:user"

    @pytest.mark.asyncio
    async def test_does_not_duplicate_caller_supplied_qualifier(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ORG_ITEM]))

        await github.execute_action("search_users", {"query": "github type:org"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "github type:org"


class TestSearchOrgs:
    @pytest.mark.asyncio
    async def test_returns_shaped_organizations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ORG_ITEM]))

        result = await github.execute_action("search_orgs", {"query": "github"}, mock_context)

        item = result.result.data["items"][0]
        assert item["login"] == "github"
        assert item["type"] == "Organization"
        assert item["url"] == "https://github.com/github"

    @pytest.mark.asyncio
    async def test_uses_users_endpoint_with_type_org(self, mock_context):
        """There is no /search/orgs endpoint — organizations come from /search/users."""
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_envelope([SAMPLE_ORG_ITEM]))

        await github.execute_action("search_orgs", {"query": "github"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url.endswith("/search/users")
        assert "/search/orgs" not in url
        assert mock_context.fetch.call_args.kwargs["params"]["q"] == "github type:org"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("search_orgs", {"query": "github"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message
