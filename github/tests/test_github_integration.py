"""
Read-only live integration tests for the GitHub integration.

These tests call the real GitHub API and require a valid OAuth access token in
the GITHUB_ACCESS_TOKEN environment variable (via .env or export).
Default pytest discovery excludes these tests; TeamCity runs the read-only
live suite with configured credentials and fixtures.

Run manually with:
    pytest github/tests/test_github_integration.py -m integration
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.integration

PUBLIC_OWNER = "octocat"
PUBLIC_REPO = "Hello-World"

# octocat/Hello-World is flat, so directory-listing coverage uses a public repo
# with a stable tree.
DIR_OWNER = "github"
DIR_REPO = "gitignore"
DIR_PATH = "Global"


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


@pytest.fixture
def search_repositories_fixture(live_context, env_credentials):
    variables = {
        "username": "GITHUB_TEST_SEARCH_USERNAME",
        "repo_a": "GITHUB_TEST_SEARCH_REPO_A",
        "repo_b": "GITHUB_TEST_SEARCH_REPO_B",
    }
    values = {key: env_credentials(name) for key, name in variables.items()}
    missing = [name for key, name in variables.items() if not values[key]]
    assert not missing, f"Configure GitHub search fixtures (see github/README.md): {', '.join(missing)}"
    assert values["repo_a"].lower() != values["repo_b"].lower(), "Search fixtures must use two distinct repositories"
    return values


@pytest.fixture
def commit_search_fixture(search_repositories_fixture, env_credentials):
    values = dict(search_repositories_fixture)
    for key, name in {"sha_a": "GITHUB_TEST_SEARCH_SHA_A", "sha_b": "GITHUB_TEST_SEARCH_SHA_B"}.items():
        values[key] = env_credentials(name)
        assert values[key], f"Configure {name} (see github/README.md)"
    return values


@pytest.fixture
def pull_request_search_fixture(search_repositories_fixture, env_credentials):
    values = dict(search_repositories_fixture)
    for key, name in {"pr_a": "GITHUB_TEST_SEARCH_PR_A", "pr_b": "GITHUB_TEST_SEARCH_PR_B"}.items():
        value = env_credentials(name)
        assert value and value.isdigit() and int(value) > 0, f"Configure {name} as a positive PR number"
        values[key] = int(value)
    return values


class TestGitHubReadOnlyActions:
    async def test_search_commits_across_repositories(self, live_context, commit_search_fixture):
        fixture = commit_search_fixture
        result = await github.execute_action(
            "search_commits", {"username": fixture["username"], "max_pages": 1}, live_context
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert isinstance(data["commits"], list)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["incomplete_results"], bool)
        assert data["pages_fetched"] == 1
        assert data["total_count"] >= 2
        assert not data["incomplete_results"], "GitHub search was incomplete; retry the fixture test"
        expected = {
            (fixture["repo_a"].lower(), fixture["sha_a"]),
            (fixture["repo_b"].lower(), fixture["sha_b"]),
        }
        found = {(commit["repository"].lower(), commit["sha"]) for commit in data["commits"]}
        assert expected <= found, f"Known cross-repository commits missing: {expected - found}"
        for commit in data["commits"]:
            assert commit["author_login"].lower() == fixture["username"].lower()
            assert commit["sha"]
            assert commit["url"].startswith("https://github.com/")

    async def test_search_pull_requests_across_private_repositories(self, live_context, pull_request_search_fixture):
        fixture = pull_request_search_fixture
        result = await github.execute_action(
            "search_pull_requests",
            {"repositories": [fixture["repo_a"], fixture["repo_b"]], "state": "open", "max_pages": 1},
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["author"].lower() == fixture["username"].lower()
        assert not data["incomplete_results"]
        expected = {(fixture["repo_a"].lower(), fixture["pr_a"]), (fixture["repo_b"].lower(), fixture["pr_b"])}
        found = {(pr["repository"].lower(), pr["number"]) for pr in data["pull_requests"]}
        assert expected <= found, f"Known cross-repository PRs missing: {expected - found}"
        assert data["pages_fetched"] == 1
        for pr in data["pull_requests"]:
            assert pr["repository"].lower() in {fixture["repo_a"].lower(), fixture["repo_b"].lower()}
            assert pr["author"].lower() == fixture["username"].lower()
            assert pr["state"] == "open"
            assert pr["url"].startswith("https://github.com/")

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

    async def test_list_commits_filters_by_author(self, live_context, env_credentials):
        repository = env_credentials("GITHUB_TEST_SEARCH_REPO_A")
        expected_sha = env_credentials("GITHUB_TEST_SEARCH_SHA_A")
        assert repository and expected_sha, "Configure the repository A fixtures in README.md"
        owner, repo = repository.split("/", 1)

        known_commit = await github.execute_action(
            "get_commit", {"owner": owner, "repo": repo, "sha": expected_sha}, live_context
        )
        assert known_commit.type == ResultType.ACTION
        author_email = known_commit.result.data["author"]["email"]
        assert author_email, "The known fixture commit must have an author email"

        result = await github.execute_action(
            "list_commits",
            {"owner": owner, "repo": repo, "sha": expected_sha, "author": author_email, "max_pages": 1},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert expected_sha in {commit["sha"] for commit in result.result.data}
        assert all(commit["author"]["email"] == author_email for commit in result.result.data)

        unmatched = await github.execute_action(
            "list_commits",
            {
                "owner": owner,
                "repo": repo,
                "sha": expected_sha,
                "author": "no-matching-author@example.invalid",
                "max_pages": 1,
            },
            live_context,
        )
        assert unmatched.type == ResultType.ACTION
        assert unmatched.result.data == []

    async def test_list_issues_returns_issues(self, live_context):
        # Keep this smoke test below the pagination cap as the public repository grows.
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = await github.execute_action(
            "list_issues",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "state": "all", "since": since},
            live_context,
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

    async def test_get_file_content_returns_decoded_file(self, live_context):
        result = await github.execute_action(
            "get_file_content",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "path": "README"},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["type"] == "file"
        assert result.result.data["name"] == "README"
        assert result.result.data["content"]
        assert result.result.data["sha"]
        assert result.result.data["entries"] == []

    async def test_get_file_content_lists_directory_entries(self, live_context):
        result = await github.execute_action(
            "get_file_content",
            {"owner": DIR_OWNER, "repo": DIR_REPO, "path": DIR_PATH},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["type"] == "dir"
        assert result.result.data["content"] == ""
        assert result.result.data["name"] == DIR_PATH
        assert result.result.data["path"] == DIR_PATH

        entries = result.result.data["entries"]
        assert entries
        assert {"name", "path", "type", "sha", "size", "download_url"} <= set(entries[0])
        assert all(entry["type"] in ("file", "dir") for entry in entries)

        by_name = {entry["name"]: entry for entry in entries}
        assert "macOS.gitignore" in by_name
        assert by_name["macOS.gitignore"]["type"] == "file"
        assert by_name["macOS.gitignore"]["path"] == "Global/macOS.gitignore"
        assert by_name["macOS.gitignore"]["size"] > 0
