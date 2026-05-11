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

SAMPLE_COMMIT = {
    "sha": "abc123def456",
    "commit": {
        "author": {"name": "Octocat", "email": "octocat@github.com", "date": "2021-01-01T00:00:00Z"},
        "committer": {"name": "Octocat", "email": "octocat@github.com", "date": "2021-01-01T00:00:00Z"},
        "message": "Initial commit",
    },
    "html_url": "https://github.com/octocat/Hello-World/commit/abc123",
    "stats": {"additions": 10, "deletions": 2, "total": 12},
    "files": [],
}

SAMPLE_BRANCH = {
    "name": "main",
    "protected": True,
    "commit": {"sha": "abc123", "url": "https://api.github.com/repos/octocat/Hello-World/commits/abc123"},
    "protection": {},
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


# ---- Commit Actions ----


class TestGetCommit:
    @pytest.mark.asyncio
    async def test_returns_commit_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMIT)

        result = await github.execute_action(
            "get_commit", {"owner": "octocat", "repo": "Hello-World", "sha": "abc123def456"}, mock_context
        )

        assert result.result.data["sha"] == "abc123def456"
        assert result.result.data["message"] == "Initial commit"
        assert result.result.data["author"]["name"] == "Octocat"

    @pytest.mark.asyncio
    async def test_url_includes_sha(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMIT)

        await github.execute_action(
            "get_commit", {"owner": "octocat", "repo": "Hello-World", "sha": "abc123def456"}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "commits/abc123def456" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Commit not found")

        result = await github.execute_action(
            "get_commit", {"owner": "octocat", "repo": "Hello-World", "sha": "bad_sha"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListCommits:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_COMMIT])

        result = await github.execute_action("list_commits", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["sha"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_filters_applied_to_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action(
            "list_commits",
            {"owner": "octocat", "repo": "Hello-World", "sha": "main", "since": "2021-01-01T00:00:00Z"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["sha"] == "main"
        assert params["since"] == "2021-01-01T00:00:00Z"


# ---- Branch Actions ----


class TestGetBranch:
    @pytest.mark.asyncio
    async def test_returns_branch_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BRANCH)

        result = await github.execute_action(
            "get_branch", {"owner": "octocat", "repo": "Hello-World", "branch": "main"}, mock_context
        )

        assert result.result.data["name"] == "main"
        assert result.result.data["protected"] is True

    @pytest.mark.asyncio
    async def test_url_includes_branch_name(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BRANCH)

        await github.execute_action(
            "get_branch", {"owner": "octocat", "repo": "Hello-World", "branch": "main"}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "branches/main" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Branch not found")

        result = await github.execute_action(
            "get_branch", {"owner": "octocat", "repo": "Hello-World", "branch": "nonexistent"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListBranches:
    @pytest.mark.asyncio
    async def test_returns_branches(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_BRANCH])

        result = await github.execute_action("list_branches", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["name"] == "main"


class TestCreateBranch:
    @pytest.mark.asyncio
    async def test_creates_branch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "ref": "refs/heads/new-branch",
                "url": "https://api.github.com/repos/octocat/Hello-World/git/refs/heads/new-branch",
                "object": {"sha": "abc123", "type": "commit", "url": "https://..."},
            },
        )

        result = await github.execute_action(
            "create_branch",
            {"owner": "octocat", "repo": "Hello-World", "branch_name": "new-branch", "sha": "abc123"},
            mock_context,
        )

        assert result.result.data["ref"] == "refs/heads/new-branch"
        assert result.result.data["object"]["sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_payload_contains_ref_and_sha(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={"ref": "refs/heads/nb", "url": "", "object": {"sha": "abc", "type": "commit", "url": ""}},
        )

        await github.execute_action(
            "create_branch",
            {"owner": "octocat", "repo": "Hello-World", "branch_name": "nb", "sha": "abc"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["ref"] == "refs/heads/nb"
        assert payload["sha"] == "abc"


class TestDeleteBranch:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action(
            "delete_branch", {"owner": "octocat", "repo": "Hello-World", "branch": "old-branch"}, mock_context
        )

        assert result.result.data["deleted"] is True
        assert result.result.data["branch"] == "old-branch"


class TestGetBranchProtection:
    @pytest.mark.asyncio
    async def test_returns_protection_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "required_status_checks": {"contexts": ["ci/test"]},
                "enforce_admins": {"enabled": True},
                "required_pull_request_reviews": {
                    "required_approving_review_count": 1,
                    "dismiss_stale_reviews": False,
                    "require_code_owner_reviews": False,
                },
                "restrictions": None,
            },
        )

        result = await github.execute_action(
            "get_branch_protection", {"owner": "octocat", "repo": "Hello-World", "branch": "main"}, mock_context
        )

        assert result.result.data["enabled"] is True
        assert result.result.data["enforce_admins"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Branch has no protection rules")

        result = await github.execute_action(
            "get_branch_protection", {"owner": "octocat", "repo": "Hello-World", "branch": "main"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Branch protection not available" in result.result.message


class TestDiffBranchToBranch:
    @pytest.mark.asyncio
    async def test_returns_diff_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "status": "ahead",
                "ahead_by": 3,
                "behind_by": 0,
                "total_commits": 3,
                "commits": [],
                "files": [],
            },
        )

        result = await github.execute_action(
            "diff_branch_to_branch",
            {"owner": "octocat", "repo": "Hello-World", "base_branch": "main", "head_branch": "feature"},
            mock_context,
        )

        assert result.result.data["status"] == "ahead"
        assert result.result.data["ahead_by"] == 3

    @pytest.mark.asyncio
    async def test_url_contains_compare(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"status": "identical", "ahead_by": 0, "behind_by": 0, "total_commits": 0, "commits": [], "files": []},
        )

        await github.execute_action(
            "diff_branch_to_branch",
            {"owner": "octocat", "repo": "Hello-World", "base_branch": "main", "head_branch": "feature"},
            mock_context,
        )

        url = mock_context.fetch.call_args.args[0]
        assert "compare/main...feature" in url
