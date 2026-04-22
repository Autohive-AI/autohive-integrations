"""
End-to-end integration tests for the ClickUp integration (read-only actions).

These tests call the real ClickUp API and require a valid OAuth access token
set in the CLICKUP_ACCESS_TOKEN environment variable (via .env or export).

Write actions (create_task, update_task, delete_task, create_folder, etc.) are
intentionally excluded — they create/modify real data in the ClickUp workspace.

Some tests depend on data existing in the workspace. These will skip gracefully
if none are found:
    - TestGetSpace (needs at least one space)
    - TestGetFolder (needs at least one folder)
    - TestGetList (needs at least one list)
    - TestGetTask / TestGetTasks (needs at least one list with tasks)
    - TestGetTaskComments (needs at least one task)

Run with:
    pytest clickup/tests/test_clickup_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402

_spec = importlib.util.spec_from_file_location("clickup_mod", os.path.join(_parent, "clickup.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

clickup = _mod.clickup

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("CLICKUP_ACCESS_TOKEN", "")

CLICKUP_API_BASE_URL = "https://api.clickup.com/api/v2"


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with ClickUp OAuth token.

    The ClickUp integration relies on context.fetch to auto-inject the OAuth
    token (auth.type = "platform"). In tests we bypass the SDK auth layer and
    manually add the Authorization header to every request.
    """
    if not ACCESS_TOKEN:
        pytest.skip("CLICKUP_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = ACCESS_TOKEN
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                return await resp.json()

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_first_team_id(live_context):
    """Return the first team/workspace ID, or skip if none."""
    result = await clickup.execute_action("get_authorized_teams", {}, live_context)
    teams = result.result.data.get("teams", [])
    if not teams:
        pytest.skip("No teams/workspaces found in ClickUp account")
    return teams[0]["id"]


async def _get_first_space_id(live_context):
    """Return the first space ID, or skip if none."""
    team_id = await _get_first_team_id(live_context)
    result = await clickup.execute_action("get_spaces", {"team_id": team_id}, live_context)
    spaces = result.result.data.get("spaces", [])
    if not spaces:
        pytest.skip("No spaces found in ClickUp workspace")
    return spaces[0]["id"]


async def _get_first_folder_id(live_context):
    """Return the first folder ID, or skip if none."""
    space_id = await _get_first_space_id(live_context)
    result = await clickup.execute_action("get_folders", {"space_id": space_id}, live_context)
    folders = result.result.data.get("folders", [])
    if not folders:
        pytest.skip("No folders found in ClickUp space")
    return folders[0]["id"]


async def _get_first_list_id(live_context):
    """Return the first list ID (from a folder), or skip if none."""
    folder_id = await _get_first_folder_id(live_context)
    result = await clickup.execute_action("get_lists", {"folder_id": folder_id}, live_context)
    lists = result.result.data.get("lists", [])
    if not lists:
        pytest.skip("No lists found in ClickUp folder")
    return lists[0]["id"]


# ---------------------------------------------------------------------------
# Team/Workspace actions
# ---------------------------------------------------------------------------


class TestGetAuthorizedTeams:
    @pytest.mark.asyncio
    async def test_returns_teams(self, live_context):
        result = await clickup.execute_action("get_authorized_teams", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "teams" in data
        assert len(data["teams"]) > 0

    @pytest.mark.asyncio
    async def test_team_structure(self, live_context):
        result = await clickup.execute_action("get_authorized_teams", {}, live_context)

        team = result.result.data["teams"][0]
        assert "id" in team
        assert "name" in team


# ---------------------------------------------------------------------------
# Space actions
# ---------------------------------------------------------------------------


class TestGetSpaces:
    @pytest.mark.asyncio
    async def test_returns_spaces(self, live_context):
        team_id = await _get_first_team_id(live_context)

        result = await clickup.execute_action("get_spaces", {"team_id": team_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "spaces" in data
        assert len(data["spaces"]) > 0

    @pytest.mark.asyncio
    async def test_space_structure(self, live_context):
        team_id = await _get_first_team_id(live_context)

        result = await clickup.execute_action("get_spaces", {"team_id": team_id}, live_context)

        space = result.result.data["spaces"][0]
        assert "id" in space
        assert "name" in space


class TestGetSpace:
    @pytest.mark.asyncio
    async def test_returns_space(self, live_context):
        space_id = await _get_first_space_id(live_context)

        result = await clickup.execute_action("get_space", {"space_id": space_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert data["space"]["id"] == space_id


# ---------------------------------------------------------------------------
# Folder actions
# ---------------------------------------------------------------------------


class TestGetFolders:
    @pytest.mark.asyncio
    async def test_returns_folders(self, live_context):
        space_id = await _get_first_space_id(live_context)

        result = await clickup.execute_action("get_folders", {"space_id": space_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "folders" in data


class TestGetFolder:
    @pytest.mark.asyncio
    async def test_returns_folder(self, live_context):
        folder_id = await _get_first_folder_id(live_context)

        result = await clickup.execute_action("get_folder", {"folder_id": folder_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert data["folder"]["id"] == folder_id


# ---------------------------------------------------------------------------
# List actions
# ---------------------------------------------------------------------------


class TestGetLists:
    @pytest.mark.asyncio
    async def test_returns_lists(self, live_context):
        folder_id = await _get_first_folder_id(live_context)

        result = await clickup.execute_action("get_lists", {"folder_id": folder_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "lists" in data


class TestGetList:
    @pytest.mark.asyncio
    async def test_returns_list(self, live_context):
        list_id = await _get_first_list_id(live_context)

        result = await clickup.execute_action("get_list", {"list_id": list_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert data["list"]["id"] == list_id


# ---------------------------------------------------------------------------
# Task actions (read-only)
# ---------------------------------------------------------------------------


class TestGetTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks(self, live_context):
        list_id = await _get_first_list_id(live_context)

        result = await clickup.execute_action("get_tasks", {"list_id": list_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "tasks" in data


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_task(self, live_context):
        list_id = await _get_first_list_id(live_context)

        tasks_result = await clickup.execute_action("get_tasks", {"list_id": list_id}, live_context)
        tasks = tasks_result.result.data.get("tasks", [])

        if not tasks:
            pytest.skip("No tasks found in ClickUp list")

        task_id = tasks[0]["id"]
        result = await clickup.execute_action("get_task", {"task_id": task_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert data["task"]["id"] == task_id


# ---------------------------------------------------------------------------
# Comment actions (read-only)
# ---------------------------------------------------------------------------


class TestGetTaskComments:
    @pytest.mark.asyncio
    async def test_returns_comments(self, live_context):
        list_id = await _get_first_list_id(live_context)

        tasks_result = await clickup.execute_action("get_tasks", {"list_id": list_id}, live_context)
        tasks = tasks_result.result.data.get("tasks", [])

        if not tasks:
            pytest.skip("No tasks found in ClickUp list")

        task_id = tasks[0]["id"]
        result = await clickup.execute_action("get_task_comments", {"task_id": task_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "comments" in data
