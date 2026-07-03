import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType
from gitlab.gitlab import gitlab

pytestmark = pytest.mark.unit

GITLAB_API_BASE_URL = "https://gitlab.com/api/v4"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# ---- User ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1, "username": "alice"})

        result = await gitlab.execute_action("get_current_user", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["user"] == {"id": 1, "username": "alice"}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("unauthorized")

        result = await gitlab.execute_action("get_current_user", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unauthorized" in result.result.message


# ---- Projects ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1, "name": "proj"}])

        result = await gitlab.execute_action("list_projects", {"owned": True}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["projects"] == [{"id": 1, "name": "proj"}]

    @pytest.mark.asyncio
    async def test_non_list_response_defaults_empty(self, mock_context):
        mock_context.fetch.return_value = ok({"unexpected": "shape"})

        result = await gitlab.execute_action("list_projects", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["projects"] == []

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


class TestGetProject:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1, "name": "proj"})

        result = await gitlab.execute_action("get_project", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["project"]["name"] == "proj"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("not found")

        result = await gitlab.execute_action("get_project", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message


# ---- Issues ----


class TestListIssues:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"iid": 1, "title": "bug"}])

        result = await gitlab.execute_action("list_issues", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["issues"] == [{"iid": 1, "title": "bug"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_issues", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetIssue:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"iid": 1, "title": "bug"})

        result = await gitlab.execute_action("get_issue", {"project_id": "1", "issue_iid": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["issue"]["title"] == "bug"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("get_issue", {"project_id": "1", "issue_iid": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Merge Requests ----


class TestListMergeRequests:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"iid": 1, "title": "mr"}])

        result = await gitlab.execute_action("list_merge_requests", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["merge_requests"] == [{"iid": 1, "title": "mr"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_merge_requests", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetMergeRequest:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"iid": 1, "title": "mr"})

        result = await gitlab.execute_action(
            "get_merge_request", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["merge_request"]["title"] == "mr"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_merge_request", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetMergeRequestChanges:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"changes": [{"old_path": "a.py"}]})

        result = await gitlab.execute_action(
            "get_merge_request_changes", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["changes"] == [{"old_path": "a.py"}]

    @pytest.mark.asyncio
    async def test_non_dict_response_defaults_empty(self, mock_context):
        mock_context.fetch.return_value = ok([])

        result = await gitlab.execute_action(
            "get_merge_request_changes", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["changes"] == []

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_merge_request_changes", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListMergeRequestCommits:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": "abc123"}])

        result = await gitlab.execute_action(
            "list_merge_request_commits", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["commits"] == [{"id": "abc123"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "list_merge_request_commits", {"project_id": "1", "merge_request_iid": 1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Branches ----


class TestListBranches:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"name": "main"}])

        result = await gitlab.execute_action("list_branches", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["branches"] == [{"name": "main"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_branches", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetBranch:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"name": "main", "protected": True})

        result = await gitlab.execute_action("get_branch", {"project_id": "1", "branch": "main"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["branch"]["protected"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("get_branch", {"project_id": "1", "branch": "main"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Commits ----


class TestListCommits:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": "abc123"}])

        result = await gitlab.execute_action("list_commits", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["commits"] == [{"id": "abc123"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_commits", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetCommit:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "abc123", "message": "fix"})

        result = await gitlab.execute_action("get_commit", {"project_id": "1", "sha": "abc123"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["commit"]["message"] == "fix"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("get_commit", {"project_id": "1", "sha": "abc123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetCommitDiff:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"old_path": "a.py"}])

        result = await gitlab.execute_action("get_commit_diff", {"project_id": "1", "sha": "abc123"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["diffs"] == [{"old_path": "a.py"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("get_commit_diff", {"project_id": "1", "sha": "abc123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Pipelines ----


class TestListPipelines:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1, "status": "success"}])

        result = await gitlab.execute_action("list_pipelines", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["pipelines"] == [{"id": 1, "status": "success"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_pipelines", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetPipeline:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1, "status": "success"})

        result = await gitlab.execute_action("get_pipeline", {"project_id": "1", "pipeline_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["pipeline"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("get_pipeline", {"project_id": "1", "pipeline_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListPipelineJobs:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1, "name": "build"}])

        result = await gitlab.execute_action("list_pipeline_jobs", {"project_id": "1", "pipeline_id": 1}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["jobs"] == [{"id": 1, "name": "build"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_pipeline_jobs", {"project_id": "1", "pipeline_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Repository ----


class TestListRepositoryTree:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"name": "README.md", "type": "blob"}])

        result = await gitlab.execute_action("list_repository_tree", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["tree"] == [{"name": "README.md", "type": "blob"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_repository_tree", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetFile:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"file_name": "README.md", "content": "aGVsbG8="})

        result = await gitlab.execute_action(
            "get_file", {"project_id": "1", "file_path": "README.md", "ref": "main"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["file"]["file_name"] == "README.md"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_file", {"project_id": "1", "file_path": "README.md", "ref": "main"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetFileRaw:
    @pytest.mark.asyncio
    async def test_success_string(self, mock_context):
        mock_context.fetch.return_value = ok("hello world")

        result = await gitlab.execute_action(
            "get_file_raw", {"project_id": "1", "file_path": "README.md", "ref": "main"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_success_bytes(self, mock_context):
        mock_context.fetch.return_value = ok(b"hello world")

        result = await gitlab.execute_action(
            "get_file_raw", {"project_id": "1", "file_path": "README.md", "ref": "main"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_file_raw", {"project_id": "1", "file_path": "README.md", "ref": "main"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestCompareBranches:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"commits": [], "diffs": []})

        result = await gitlab.execute_action(
            "compare_branches", {"project_id": "1", "from": "main", "to": "feature"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["comparison"] == {"commits": [], "diffs": []}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "compare_branches", {"project_id": "1", "from": "main", "to": "feature"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Container Registry ----


class TestListContainerRegistryRepositories:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1, "name": "repo"}])

        result = await gitlab.execute_action("list_container_registry_repositories", {"project_id": "1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["repositories"] == [{"id": 1, "name": "repo"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action("list_container_registry_repositories", {"project_id": "1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetContainerRegistryRepository:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1, "name": "repo"})

        result = await gitlab.execute_action(
            "get_container_registry_repository",
            {"project_id": "1", "repository_id": 1},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["repository"]["name"] == "repo"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_container_registry_repository",
            {"project_id": "1", "repository_id": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListContainerRegistryTags:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok([{"name": "latest"}])

        result = await gitlab.execute_action(
            "list_container_registry_tags",
            {"project_id": "1", "repository_id": 1},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["tags"] == [{"name": "latest"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "list_container_registry_tags",
            {"project_id": "1", "repository_id": 1},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetContainerRegistryTag:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"name": "latest", "digest": "sha256:abc"})

        result = await gitlab.execute_action(
            "get_container_registry_tag",
            {"project_id": "1", "repository_id": 1, "tag_name": "latest"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["tag"]["digest"] == "sha256:abc"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await gitlab.execute_action(
            "get_container_registry_tag",
            {"project_id": "1", "repository_id": 1, "tag_name": "latest"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
