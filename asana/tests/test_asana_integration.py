"""
End-to-end integration tests for the Asana integration.

These tests call the real Asana API and require a valid OAuth access token
set in the ASANA_ACCESS_TOKEN environment variable (via .env or export).
A workspace GID is also required for most project/task actions â€” set ASANA_TEST_WORKSPACE_GID.

Run read-only tests (safe):
    pytest asana/tests/test_asana_integration.py -m "integration and not destructive"

Run destructive tests (creates/deletes real data):
    pytest asana/tests/test_asana_integration.py -m "integration and destructive"

Never runs in CI â€” pyproject.toml excludes test_*_integration.py files and filters to -m unit.
"""

import os
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from asana.asana import asana

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("ASANA_ACCESS_TOKEN", "")
TEST_WORKSPACE_GID = os.environ.get("ASANA_TEST_WORKSPACE_GID", "")
TEST_PROJECT_GID = os.environ.get("ASANA_TEST_PROJECT_GID", "")
TEST_TASK_GID = os.environ.get("ASANA_TEST_TASK_GID", "")


def require_workspace():
    if not TEST_WORKSPACE_GID:
        pytest.skip("ASANA_TEST_WORKSPACE_GID not set")


def require_project():
    if not TEST_PROJECT_GID:
        pytest.skip("ASANA_TEST_PROJECT_GID not set")


def require_task():
    if not TEST_TASK_GID:
        pytest.skip("ASANA_TEST_TASK_GID not set")


@pytest.fixture
def live_context(make_context):
    token = os.environ.get("ASANA_ACCESS_TOKEN", "")
    if not token:
        pytest.skip("ASANA_ACCESS_TOKEN not set â€” skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        payload = kwargs.get("data", body)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=payload,
                headers={"Authorization": f"Bearer {token}", **(dict(headers or {}))},
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"auth_type": "PlatformOauth2", "credentials": {"access_token": token}})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


class TestListWorkspacesLive:
    async def test_returns_workspaces(self, live_context):
        result = await asana.execute_action("list_workspaces", {}, live_context)
        assert result.type == ResultType.ACTION
        assert "workspaces" in result.result.data
        assert isinstance(result.result.data["workspaces"], list)

    async def test_workspace_has_gid_and_name(self, live_context):
        result = await asana.execute_action("list_workspaces", {}, live_context)
        workspaces = result.result.data["workspaces"]
        if workspaces:
            assert "gid" in workspaces[0]
            assert "name" in workspaces[0]


class TestGetWorkspaceLive:
    async def test_returns_workspace(self, live_context):
        require_workspace()
        result = await asana.execute_action("get_workspace", {"workspace_gid": TEST_WORKSPACE_GID}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["workspace"]["gid"] == TEST_WORKSPACE_GID


class TestGetUserLive:
    async def test_returns_current_user(self, live_context):
        result = await asana.execute_action("get_user", {"user_gid": "me"}, live_context)
        assert result.type == ResultType.ACTION
        assert "user" in result.result.data
        assert "gid" in result.result.data["user"]

    async def test_user_has_name(self, live_context):
        result = await asana.execute_action("get_user", {"user_gid": "me"}, live_context)
        assert result.result.data["user"].get("name")


class TestListProjectsLive:
    async def test_returns_projects(self, live_context):
        require_workspace()
        result = await asana.execute_action(
            "list_projects", {"workspace": TEST_WORKSPACE_GID, "limit": 5}, live_context
        )
        assert result.type == ResultType.ACTION
        assert "projects" in result.result.data
        assert isinstance(result.result.data["projects"], list)

    async def test_limit_respected(self, live_context):
        require_workspace()
        result = await asana.execute_action(
            "list_projects", {"workspace": TEST_WORKSPACE_GID, "limit": 2}, live_context
        )
        assert len(result.result.data["projects"]) <= 2


class TestGetProjectLive:
    async def test_returns_project(self, live_context):
        require_project()
        result = await asana.execute_action("get_project", {"project_gid": TEST_PROJECT_GID}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["project"]["gid"] == TEST_PROJECT_GID


class TestGetProjectByNameLive:
    async def test_not_found_for_nonsense_name(self, live_context):
        require_workspace()
        result = await asana.execute_action(
            "get_project_by_name",
            {"name": "ZZZZNONEXISTENT_PROJECT_XYZ_999", "workspace": TEST_WORKSPACE_GID},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["not_found"] is True


class TestListTasksLive:
    async def test_returns_tasks(self, live_context):
        require_project()
        result = await asana.execute_action("list_tasks", {"project": TEST_PROJECT_GID, "limit": 5}, live_context)
        assert result.type == ResultType.ACTION
        assert "tasks" in result.result.data

    async def test_limit_respected(self, live_context):
        require_project()
        result = await asana.execute_action("list_tasks", {"project": TEST_PROJECT_GID, "limit": 2}, live_context)
        assert len(result.result.data["tasks"]) <= 2


class TestGetTaskLive:
    async def test_returns_task(self, live_context):
        require_task()
        result = await asana.execute_action("get_task", {"task_gid": TEST_TASK_GID}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["task"]["gid"] == TEST_TASK_GID


class TestListSectionsLive:
    async def test_returns_sections(self, live_context):
        require_project()
        result = await asana.execute_action("list_sections", {"project_gid": TEST_PROJECT_GID}, live_context)
        assert result.type == ResultType.ACTION
        assert "sections" in result.result.data

    async def test_sections_have_gid(self, live_context):
        require_project()
        result = await asana.execute_action("list_sections", {"project_gid": TEST_PROJECT_GID}, live_context)
        sections = result.result.data["sections"]
        if sections:
            assert "gid" in sections[0]


class TestListStoriesLive:
    async def test_returns_stories(self, live_context):
        require_task()
        result = await asana.execute_action("list_stories", {"task_gid": TEST_TASK_GID}, live_context)
        assert result.type == ResultType.ACTION
        assert "stories" in result.result.data


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestTaskLifecycle:
    """Full task lifecycle: create â†’ get â†’ update â†’ add comment â†’ create subtask â†’ delete."""

    async def test_full_lifecycle(self, live_context):
        require_workspace()

        # Create
        create_result = await asana.execute_action(
            "create_task",
            {"name": f"Integration Test Task {os.getpid()}", "workspace": TEST_WORKSPACE_GID, "assignee": "me"},
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        task_gid = create_result.result.data["task"]["gid"]
        assert task_gid

        # Get
        get_result = await asana.execute_action("get_task", {"task_gid": task_gid}, live_context)
        assert get_result.result.data["task"]["gid"] == task_gid

        # Update
        update_result = await asana.execute_action(
            "update_task", {"task_gid": task_gid, "name": f"Updated {os.getpid()}"}, live_context
        )
        assert update_result.type == ResultType.ACTION

        # Add comment
        story_result = await asana.execute_action(
            "create_story", {"task_gid": task_gid, "text": "Integration test comment"}, live_context
        )
        assert story_result.type == ResultType.ACTION
        assert "story" in story_result.result.data

        # Create subtask
        subtask_result = await asana.execute_action(
            "create_subtask", {"parent_task_gid": task_gid, "name": f"Subtask {os.getpid()}"}, live_context
        )
        assert subtask_result.type == ResultType.ACTION

        # Delete (cleanup)
        delete_result = await asana.execute_action("delete_task", {"task_gid": task_gid}, live_context)
        assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
class TestProjectLifecycle:
    """Full project lifecycle: create â†’ get â†’ update â†’ create section â†’ update section â†’ delete."""

    async def test_full_lifecycle(self, live_context):
        require_workspace()

        # Create
        create_result = await asana.execute_action(
            "create_project",
            {"name": f"Integration Test Project {os.getpid()}", "workspace": TEST_WORKSPACE_GID},
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        project_gid = create_result.result.data["project"]["gid"]
        assert project_gid

        # Get
        get_result = await asana.execute_action("get_project", {"project_gid": project_gid}, live_context)
        assert get_result.result.data["project"]["gid"] == project_gid

        # Update
        update_result = await asana.execute_action(
            "update_project", {"project_gid": project_gid, "name": f"Renamed {os.getpid()}"}, live_context
        )
        assert update_result.type == ResultType.ACTION

        # Create section
        section_result = await asana.execute_action(
            "create_section", {"project_gid": project_gid, "name": "To Do"}, live_context
        )
        assert section_result.type == ResultType.ACTION
        section_gid = section_result.result.data["section"]["gid"]

        # Update section
        update_section_result = await asana.execute_action(
            "update_section", {"section_gid": section_gid, "name": "In Progress"}, live_context
        )
        assert update_section_result.type == ResultType.ACTION

        # Delete (cleanup)
        delete_result = await asana.execute_action("delete_project", {"project_gid": project_gid}, live_context)
        assert delete_result.result.data["deleted"] is True
