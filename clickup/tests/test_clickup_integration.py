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
from autohive_integrations_sdk import FetchResponse  # noqa: E402

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
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        print(f"\n[HTTP] {method} {url}")
        if params:
            print(f"[HTTP]   params: {params}")
        if json:
            print(f"[HTTP]   body:   {json}")
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                data = await resp.json(content_type=None)
                print(f"[HTTP]   status: {resp.status}")
                print(f"[HTTP]   data:   {data}")
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

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


# ---------------------------------------------------------------------------
# Destructive tests (write operations)
# These create, update, or delete real data in the connected ClickUp workspace.
# Each test cleans up after itself when possible (e.g. deletes what it creates).
#
# Run with:
#     pytest tests/test_clickup_integration.py -m "integration and destructive"
# ---------------------------------------------------------------------------


@pytest.mark.destructive
class TestFolderLifecycle:
    """Create → update → delete a folder."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        space_id = await _get_first_space_id(live_context)

        # Create
        create = await clickup.execute_action(
            "create_folder",
            {"space_id": space_id, "name": f"Integration test folder {os.getpid()}"},
            live_context,
        )
        assert create.result.data["result"] is True
        folder_id = create.result.data["folder"]["id"]
        assert folder_id

        try:
            # Update
            update = await clickup.execute_action(
                "update_folder",
                {"folder_id": folder_id, "name": f"Renamed folder {os.getpid()}"},
                live_context,
            )
            assert update.result.data["result"] is True
        finally:
            # Delete (always runs — cleanup even if update asserts fail)
            delete = await clickup.execute_action("delete_folder", {"folder_id": folder_id}, live_context)
            assert delete.result.data["result"] is True


@pytest.mark.destructive
class TestListLifecycle:
    """Create → update → delete a list inside the first folder."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        folder_id = await _get_first_folder_id(live_context)

        create = await clickup.execute_action(
            "create_list",
            {"folder_id": folder_id, "name": f"Integration test list {os.getpid()}"},
            live_context,
        )
        assert create.result.data["result"] is True
        list_id = create.result.data["list"]["id"]

        try:
            update = await clickup.execute_action(
                "update_list",
                {"list_id": list_id, "name": f"Renamed list {os.getpid()}"},
                live_context,
            )
            assert update.result.data["result"] is True
        finally:
            delete = await clickup.execute_action("delete_list", {"list_id": list_id}, live_context)
            assert delete.result.data["result"] is True


@pytest.mark.destructive
class TestTaskLifecycle:
    """Create → update → delete a task in the first list."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        list_id = await _get_first_list_id(live_context)

        create = await clickup.execute_action(
            "create_task",
            {
                "list_id": list_id,
                "name": f"Integration test task {os.getpid()}",
                "description": "Created by automated integration test",
                "priority": 3,
            },
            live_context,
        )
        assert create.result.data["result"] is True
        task_id = create.result.data["task"]["id"]

        try:
            update = await clickup.execute_action(
                "update_task",
                {
                    "task_id": task_id,
                    "description": "Updated by automated integration test",
                },
                live_context,
            )
            assert update.result.data["result"] is True
        finally:
            delete = await clickup.execute_action("delete_task", {"task_id": task_id}, live_context)
            assert delete.result.data["result"] is True


@pytest.mark.destructive
class TestCommentLifecycle:
    """Create a task, add a comment, update it, delete the comment and task."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        list_id = await _get_first_list_id(live_context)

        # Need a task to attach comments to
        task_create = await clickup.execute_action(
            "create_task",
            {"list_id": list_id, "name": f"Comment host task {os.getpid()}"},
            live_context,
        )
        task_id = task_create.result.data["task"]["id"]

        try:
            comment_create = await clickup.execute_action(
                "create_task_comment",
                {"task_id": task_id, "comment_text": "Integration test comment"},
                live_context,
            )
            assert comment_create.result.data["result"] is True
            # ClickUp returns the new comment's ID at response["id"]
            comment_id = str(comment_create.result.data["comment"]["id"])

            try:
                update = await clickup.execute_action(
                    "update_comment",
                    {
                        "comment_id": comment_id,
                        "comment_text": "Updated integration test comment",
                    },
                    live_context,
                )
                assert update.result.data["result"] is True
            finally:
                delete_comment = await clickup.execute_action(
                    "delete_comment", {"comment_id": comment_id}, live_context
                )
                assert delete_comment.result.data["result"] is True
        finally:
            await clickup.execute_action("delete_task", {"task_id": task_id}, live_context)


@pytest.mark.destructive
class TestTaskAttachment:
    """Create a task, upload a 1x1 PNG via the v3 attachments endpoint, delete the task."""

    @pytest.mark.asyncio
    async def test_upload_attachment(self, live_context):
        team_id = await _get_first_team_id(live_context)
        list_id = await _get_first_list_id(live_context)

        task_create = await clickup.execute_action(
            "create_task",
            {"list_id": list_id, "name": f"Attachment host task {os.getpid()}"},
            live_context,
        )
        task_id = task_create.result.data["task"]["id"]

        try:
            # 1x1 transparent PNG as base64
            png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            result = await clickup.execute_action(
                "create_task_attachment",
                {
                    "workspace_id": team_id,
                    "task_id": task_id,
                    "file": {
                        "name": "pixel.png",
                        "content": png_b64,
                        "contentType": "image/png",
                    },
                },
                live_context,
            )
            assert result.result.data["result"] is True, f"Attachment upload failed: {result.result.data.get('error')}"
            assert "attachment" in result.result.data
        finally:
            await clickup.execute_action("delete_task", {"task_id": task_id}, live_context)
