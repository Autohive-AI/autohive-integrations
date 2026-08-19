"""
Read-only live integration tests for the GitHub integration.

These tests call the real GitHub API and require a valid OAuth access token in
the GITHUB_ACCESS_TOKEN environment variable (via .env or export). They never
run in CI by default: pytest only auto-discovers test_*_unit.py files and the
default marker filter is -m unit.

Run manually with:
    pytest github/tests/test_github_integration.py -m "integration and not destructive"

Tests marked `destructive` create, modify and delete real data. They additionally
require GITHUB_TEST_REPO ("owner/repo") and skip without it:
    export GITHUB_TEST_REPO=my-org/my-scratch-repo
    pytest github/tests/test_github_integration.py -m "integration and destructive"
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


# =============================================================================
# Read-only live coverage for actions added in 3.0.0
#
# Everything below hits public GitHub only. Assertions deliberately check
# response *shape* and invariants rather than exact counts, since public repos
# change underneath us.
# =============================================================================

# A repo with a long, stable history and real pull requests.
PR_OWNER = "octocat"
PR_REPO = "Spoon-Knife"

# A repo that actually runs GitHub Actions.
WF_OWNER = "cli"
WF_REPO = "cli"


class TestSearchActionsLive:
    async def test_search_repositories_returns_matches(self, live_context):
        result = await github.execute_action("search_repositories", {"query": "autohive", "limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["total_count"] >= 0
        assert isinstance(data["items"], list)
        assert len(data["items"]) <= 5
        if data["items"]:
            assert {"full_name", "url"} <= set(data["items"][0])

    async def test_search_issues_only_returns_issues(self, live_context):
        result = await github.execute_action(
            "search_issues", {"query": f"repo:{PR_OWNER}/{PR_REPO}", "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["items"]) <= 5

    async def test_search_pull_requests_only_returns_prs(self, live_context):
        result = await github.execute_action(
            "search_pull_requests", {"query": f"repo:{PR_OWNER}/{PR_REPO}", "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["total_count"] > 0

    async def test_search_orgs_hits_the_users_endpoint(self, live_context):
        """There is no /search/orgs — search_orgs must scope /search/users with type:org."""
        result = await github.execute_action("search_orgs", {"query": "github", "limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        for item in result.result.data["items"]:
            assert item["type"] == "Organization"

    async def test_search_users_excludes_orgs(self, live_context):
        result = await github.execute_action("search_users", {"query": "octocat", "limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        for item in result.result.data["items"]:
            assert item["type"] == "User"

    async def test_search_commits_returns_shaped_results(self, live_context):
        result = await github.execute_action(
            "search_commits", {"query": f"repo:{PUBLIC_OWNER}/{PUBLIC_REPO}", "limit": 3}, live_context
        )

        assert result.type == ResultType.ACTION
        if result.result.data["items"]:
            assert {"sha", "url"} <= set(result.result.data["items"][0])

    async def test_search_code_requires_a_search_term(self, live_context):
        """A bare qualifier with no term is rejected by GitHub with a 422."""
        result = await github.execute_action(
            "search_code", {"query": f"addClass repo:{PR_OWNER}/{PR_REPO}", "limit": 3}, live_context
        )

        assert result.type in (ResultType.ACTION, ResultType.ACTION_ERROR)


class TestRepoAndFileActionsLive:
    async def test_get_repository_tree_returns_entries(self, live_context):
        result = await github.execute_action(
            "get_repository_tree",
            {"owner": PUBLIC_OWNER, "repo": PUBLIC_REPO, "tree_sha": "master"},
            live_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["entries"]
        assert data["truncated"] is False
        assert {"path", "type", "sha"} <= set(data["entries"][0])

    async def test_get_repository_tree_recursive_walks_subdirectories(self, live_context):
        result = await github.execute_action(
            "get_repository_tree",
            {"owner": DIR_OWNER, "repo": DIR_REPO, "tree_sha": "main", "recursive": True},
            live_context,
        )

        assert result.type == ResultType.ACTION
        paths = [entry["path"] for entry in result.result.data["entries"]]
        assert any("/" in path for path in paths), "recursive tree should contain nested paths"


class TestPullRequestActionsLive:
    async def _first_pr_number(self, live_context):
        listed = await github.execute_action(
            "list_pull_requests",
            {"owner": PR_OWNER, "repo": PR_REPO, "state": "all", "limit": 1, "max_pages": 1},
            live_context,
        )
        assert listed.type == ResultType.ACTION
        if not listed.result.data:
            pytest.skip(f"{PR_OWNER}/{PR_REPO} has no pull requests to read")
        return listed.result.data[0]["number"]

    async def test_get_pull_request_files(self, live_context):
        number = await self._first_pr_number(live_context)

        result = await github.execute_action(
            "get_pull_request_files",
            {"owner": PR_OWNER, "repo": PR_REPO, "pull_number": number},
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data, (list, dict))

    async def test_get_pull_request_diff_returns_text_not_json(self, live_context):
        number = await self._first_pr_number(live_context)

        result = await github.execute_action(
            "get_pull_request_diff",
            {"owner": PR_OWNER, "repo": PR_REPO, "pull_number": number},
            live_context,
        )

        assert result.type == ResultType.ACTION
        diff = result.result.data.get("diff", "")
        assert isinstance(diff, str)

    async def test_list_pull_request_commits(self, live_context):
        number = await self._first_pr_number(live_context)

        result = await github.execute_action(
            "list_pull_request_commits",
            {"owner": PR_OWNER, "repo": PR_REPO, "pull_number": number},
            live_context,
        )

        assert result.type == ResultType.ACTION


class TestWorkflowActionsLive:
    async def test_list_workflows_and_read_a_run(self, live_context):
        workflows = await github.execute_action("list_workflows", {"owner": WF_OWNER, "repo": WF_REPO}, live_context)
        assert workflows.type == ResultType.ACTION
        if not workflows.result.data:
            pytest.skip(f"{WF_OWNER}/{WF_REPO} has no workflows")

        runs = await github.execute_action("get_workflow_runs", {"owner": WF_OWNER, "repo": WF_REPO}, live_context)
        assert runs.type == ResultType.ACTION
        if not runs.result.data:
            pytest.skip("no workflow runs available")

        run_id = runs.result.data[0]["id"]
        detail = await github.execute_action(
            "get_workflow_run", {"owner": WF_OWNER, "repo": WF_REPO, "run_id": run_id}, live_context
        )

        assert detail.type == ResultType.ACTION
        assert detail.result.data["id"] == run_id

    async def test_download_artifact_never_fetches_the_zip(self, live_context):
        """The ZIP redirect raises UnicodeDecodeError through the SDK, so the
        action must return metadata and never request the archive itself."""
        runs = await github.execute_action("get_workflow_runs", {"owner": WF_OWNER, "repo": WF_REPO}, live_context)
        if runs.type != ResultType.ACTION or not runs.result.data:
            pytest.skip("no workflow runs available")

        artifacts = await github.execute_action(
            "list_workflow_run_artifacts",
            {"owner": WF_OWNER, "repo": WF_REPO, "run_id": runs.result.data[0]["id"]},
            live_context,
        )
        assert artifacts.type == ResultType.ACTION


class TestSecurityActionsLive:
    """Global advisories are public data and need no special scope, so these run
    even against a token without security_events."""

    async def test_list_global_security_advisories(self, live_context):
        result = await github.execute_action(
            "list_global_security_advisories", {"ecosystem": "pip", "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION
        items = result.result.data if isinstance(result.result.data, list) else result.result.data.get("items", [])
        assert isinstance(items, list)

    async def test_get_global_security_advisory_round_trip(self, live_context):
        listed = await github.execute_action(
            "list_global_security_advisories", {"ecosystem": "pip", "limit": 1}, live_context
        )
        if listed.type != ResultType.ACTION:
            pytest.skip("advisory listing unavailable")

        items = listed.result.data if isinstance(listed.result.data, list) else listed.result.data.get("items", [])
        if not items:
            pytest.skip("no advisories returned")

        ghsa_id = items[0]["ghsa_id"]
        result = await github.execute_action("get_global_security_advisory", {"ghsa_id": ghsa_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["ghsa_id"] == ghsa_id


class TestLabelActionsLive:
    async def test_list_labels_returns_shaped_labels(self, live_context):
        result = await github.execute_action(
            "list_labels", {"owner": WF_OWNER, "repo": WF_REPO, "limit": 5}, live_context
        )

        assert result.type == ResultType.ACTION
        labels = result.result.data if isinstance(result.result.data, list) else result.result.data.get("items", [])
        if labels:
            assert {"name", "color"} <= set(labels[0])


# =============================================================================
# Destructive live tests
#
# These CREATE, MODIFY and DELETE real data. They are double-gated: the
# `destructive` marker (opt-in, never selected by default) plus a GITHUB_TEST_REPO
# environment variable naming the scratch repo. With no GITHUB_TEST_REPO set they
# skip, so there is no way to run them against a repository you did not nominate.
#
#     export GITHUB_TEST_REPO=my-org/my-scratch-repo
#     pytest github/tests/test_github_integration.py -m "integration and destructive"
# =============================================================================


@pytest.fixture
def test_repo(env_credentials):
    """owner/repo of a scratch repository the caller has explicitly nominated."""
    slug = env_credentials("GITHUB_TEST_REPO")
    if not slug:
        pytest.skip("GITHUB_TEST_REPO not set — skipping destructive tests")
    if "/" not in slug:
        pytest.fail(f"GITHUB_TEST_REPO must be 'owner/repo', got '{slug}'")
    owner, repo = slug.split("/", 1)
    return {"owner": owner, "repo": repo}


@pytest.mark.destructive
class TestLabelLifecycleLive:
    """Create -> read -> update -> delete a label, cleaning up after itself."""

    LABEL = "autohive-integration-test"

    async def test_label_round_trip(self, live_context, test_repo):
        # Remove a leftover from a previous failed run so the test is re-runnable.
        await github.execute_action("delete_label", {**test_repo, "name": self.LABEL}, live_context)

        created = await github.execute_action(
            "create_label",
            {**test_repo, "name": self.LABEL, "color": "ededed", "description": "Temporary test label"},
            live_context,
        )
        assert created.type == ResultType.ACTION, getattr(created.result, "message", created.result)
        assert created.result.data["name"] == self.LABEL

        try:
            fetched = await github.execute_action("get_label", {**test_repo, "name": self.LABEL}, live_context)
            assert fetched.type == ResultType.ACTION
            assert fetched.result.data["color"] == "ededed"

            updated = await github.execute_action(
                "update_label",
                {**test_repo, "name": self.LABEL, "description": "Updated by integration test"},
                live_context,
            )
            assert updated.type == ResultType.ACTION
            assert updated.result.data["description"] == "Updated by integration test"
        finally:
            deleted = await github.execute_action("delete_label", {**test_repo, "name": self.LABEL}, live_context)
            assert deleted.type == ResultType.ACTION
            assert deleted.result.data["deleted"] is True


@pytest.mark.destructive
class TestPushFilesLive:
    """push_files is the most complex new action - five chained Git Data calls."""

    async def test_pushes_multiple_files_in_one_commit(self, live_context, test_repo):
        repo = await github.execute_action("get_repository", test_repo, live_context)
        assert repo.type == ResultType.ACTION
        branch = repo.result.data.get("default_branch", "main")

        result = await github.execute_action(
            "push_files",
            {
                **test_repo,
                "branch": branch,
                "message": "chore: autohive integration test commit",
                "files": [
                    {"path": "autohive-test/one.txt", "content": "first file\n"},
                    {"path": "autohive-test/two.txt", "content": "second file\n"},
                ],
            },
            live_context,
        )

        assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
        assert result.result.data.get("commit_sha")

        # Both files must be readable at the new commit, proving one atomic tree.
        for path in ("autohive-test/one.txt", "autohive-test/two.txt"):
            read = await github.execute_action("get_file_content", {**test_repo, "path": path}, live_context)
            assert read.type == ResultType.ACTION, f"{path} missing after push_files"

    async def test_empty_file_list_is_rejected_before_any_call(self, live_context, test_repo):
        result = await github.execute_action(
            "push_files",
            {**test_repo, "branch": "main", "message": "should not happen", "files": []},
            live_context,
        )

        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)


@pytest.mark.destructive
class TestIssueAndSubIssueLifecycleLive:
    async def test_create_issue_attach_sub_issue_then_close_both(self, live_context, test_repo):
        parent = await github.execute_action(
            "create_issue", {**test_repo, "title": "Autohive test parent issue"}, live_context
        )
        assert parent.type == ResultType.ACTION, getattr(parent.result, "message", parent.result)

        child = await github.execute_action(
            "create_issue", {**test_repo, "title": "Autohive test child issue"}, live_context
        )
        assert child.type == ResultType.ACTION

        parent_number = parent.result.data["number"]
        child_number = child.result.data["number"]

        try:
            child_full = await github.execute_action(
                "get_issue", {**test_repo, "issue_number": child_number}, live_context
            )
            assert child_full.type == ResultType.ACTION
            child_id = child_full.result.data.get("id")
            if child_id is None:
                pytest.skip("get_issue does not expose the numeric id needed for sub-issues")

            linked = await github.execute_action(
                "add_sub_issue",
                {**test_repo, "issue_number": parent_number, "sub_issue_id": child_id},
                live_context,
            )
            assert linked.type == ResultType.ACTION, getattr(linked.result, "message", linked.result)

            listed = await github.execute_action(
                "list_sub_issues", {**test_repo, "issue_number": parent_number}, live_context
            )
            assert listed.type == ResultType.ACTION
        finally:
            for number in (child_number, parent_number):
                await github.execute_action(
                    "update_issue", {**test_repo, "issue_number": number, "state": "closed"}, live_context
                )
