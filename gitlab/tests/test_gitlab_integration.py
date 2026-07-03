"""
End-to-end integration tests for the GitLab integration (read-only actions).

These tests call the real GitLab API (gitlab.com) and require a valid OAuth
access token set in the GITLAB_ACCESS_TOKEN environment variable (via .env
or export), plus a project the token can access set in GITLAB_PROJECT_ID
(numeric ID or URL-encoded "namespace/project" path).

All GitLab actions in this integration are read-only, so no destructive
gating is required.

Run with:
    pytest gitlab/tests/test_gitlab_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock

from autohive_integrations_sdk import FetchResponse, ResultType
from gitlab.gitlab import gitlab

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("GITLAB_ACCESS_TOKEN", "")
PROJECT_ID = os.environ.get("GITLAB_PROJECT_ID", "")

skip_if_no_creds = pytest.mark.skipif(not ACCESS_TOKEN, reason="GITLAB_ACCESS_TOKEN required")
skip_if_no_project = pytest.mark.skipif(
    not (ACCESS_TOKEN and PROJECT_ID), reason="GITLAB_ACCESS_TOKEN and GITLAB_PROJECT_ID required"
)


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with a GitLab OAuth token.

    The GitLab integration relies on context.fetch to auto-inject the OAuth
    token (auth.type = "platform"). In tests we bypass the SDK auth layer and
    manually add the Authorization header to every request.
    """

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, body=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, data=body, headers=merged_headers, params=params
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---- User ----


class TestGetCurrentUser:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_user_info(self, live_context):
        result = await gitlab.execute_action("get_current_user", {}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert "username" in result.result.data["user"]


# ---- Projects ----


class TestListProjects:
    @skip_if_no_creds
    @pytest.mark.asyncio
    async def test_returns_projects(self, live_context):
        result = await gitlab.execute_action("list_projects", {"membership": True, "per_page": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["projects"], list)


class TestGetProject:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_project(self, live_context):
        result = await gitlab.execute_action("get_project", {"project_id": PROJECT_ID}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert "id" in result.result.data["project"]


# ---- Issues ----


class TestListIssues:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_issues(self, live_context):
        result = await gitlab.execute_action("list_issues", {"project_id": PROJECT_ID, "per_page": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["issues"], list)


# ---- Merge Requests ----


class TestListMergeRequests:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_merge_requests(self, live_context):
        result = await gitlab.execute_action(
            "list_merge_requests", {"project_id": PROJECT_ID, "per_page": 5}, live_context
        )

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["merge_requests"], list)


# ---- Branches ----


class TestListBranches:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_branches(self, live_context):
        result = await gitlab.execute_action("list_branches", {"project_id": PROJECT_ID, "per_page": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["branches"], list)


# ---- Commits ----


class TestListCommits:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_commits(self, live_context):
        result = await gitlab.execute_action("list_commits", {"project_id": PROJECT_ID, "per_page": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["commits"], list)


# ---- Pipelines ----


class TestListPipelines:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_pipelines(self, live_context):
        result = await gitlab.execute_action("list_pipelines", {"project_id": PROJECT_ID, "per_page": 5}, live_context)

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["pipelines"], list)


# ---- Repository ----


class TestListRepositoryTree:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_tree(self, live_context):
        result = await gitlab.execute_action(
            "list_repository_tree", {"project_id": PROJECT_ID, "per_page": 5}, live_context
        )

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["tree"], list)


# ---- Container Registry ----


class TestListContainerRegistryRepositories:
    @skip_if_no_project
    @pytest.mark.asyncio
    async def test_returns_repositories(self, live_context):
        result = await gitlab.execute_action(
            "list_container_registry_repositories", {"project_id": PROJECT_ID}, live_context
        )

        assert result.type != ResultType.ACTION_ERROR, result.result.message
        assert isinstance(result.result.data["repositories"], list)
