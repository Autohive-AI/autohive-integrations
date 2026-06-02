"""
Read-only live integration tests for the GitHub integration.

These tests call the real GitHub API and require a valid OAuth access token in
the GITHUB_ACCESS_TOKEN environment variable (via .env or export). They never
run in CI by default: pytest only auto-discovers test_*_unit.py files and the
default marker filter is -m unit.

Run manually with:
    pytest github/tests/test_github_integration.py -m integration
"""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.integration

PUBLIC_OWNER = "octocat"
PUBLIC_REPO = "Hello-World"


@pytest.fixture
def live_context(env_credentials):
    access_token = env_credentials("GITHUB_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("GITHUB_ACCESS_TOKEN not set — skipping GitHub integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params, **kwargs) as resp:
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": access_token},
    }
    return ctx


class TestGitHubReadOnlyActions:
    async def test_get_repository_returns_public_repo(self, live_context):
        result = await github.execute_action(
            "get_repository", {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO}, live_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["name"] == PUBLIC_REPO
        assert result.result.data["full_name"] == f"{PUBLIC_OWNER}/{PUBLIC_REPO}"

    async def test_list_commits_returns_commits(self, live_context):
        result = await github.execute_action(
            "list_commits",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "per_page": 5, "max_pages": 1},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data, list)
        assert result.result.data
        assert "sha" in result.result.data[0]

    async def test_list_issues_returns_issues(self, live_context):
        result = await github.execute_action(
            "list_issues", {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "state": "all"}, live_context
        )

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data, list)

    async def test_list_pull_requests_uses_rest_endpoint_successfully(self, live_context):
        result = await github.execute_action(
            "list_pull_requests",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "state": "all", "limit": 5, "max_pages": 1},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data, list)

    async def test_diff_branch_to_branch_returns_comparison(self, live_context):
        result = await github.execute_action(
            "diff_branch_to_branch",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "base_branch": "master", "head_branch": "master"},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["status"] == "identical"
        assert result.result.data["ahead_by"] == 0
        assert result.result.data["behind_by"] == 0
