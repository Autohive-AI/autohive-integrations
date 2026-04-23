"""
Unit tests for ClickUp integration.

Uses pytest + mock context pattern (mock_context fixture from root conftest.py).
Covers all 23 actions with mocked context.fetch calls.
"""

import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "clickup_mod", os.path.join(_parent, "clickup.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

clickup = _mod.clickup

pytestmark = pytest.mark.unit

CLICKUP_API_BASE_URL = "https://api.clickup.com/api/v2"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        defined_actions = set(config.get("actions", {}).keys())
        registered_actions = set(clickup._action_handlers.keys())

        missing_handlers = defined_actions - registered_actions
        extra_handlers = registered_actions - defined_actions

        assert not missing_handlers, f"Missing handlers for actions: {missing_handlers}"
        assert not extra_handlers, f"Extra handlers without config: {extra_handlers}"


# ---------------------------------------------------------------------------
# Team/Workspace actions
# ---------------------------------------------------------------------------


class TestGetAuthorizedTeams:
    @pytest.mark.asyncio
    async def test_returns_teams(self, mock_context):
        mock_context.fetch.return_value = {
            "teams": [{"id": "t1", "name": "Workspace 1"}]
        }

        result = await clickup.execute_action("get_authorized_teams", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["teams"] == [{"id": "t1", "name": "Workspace 1"}]
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/team", method="GET"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await clickup.execute_action("get_authorized_teams", {}, mock_context)

        assert result.result.data["result"] is False
        assert "Network error" in result.result.data["error"]
        assert result.result.data["teams"] == []


# ---------------------------------------------------------------------------
# Space actions
# ---------------------------------------------------------------------------


class TestGetSpaces:
    @pytest.mark.asyncio
    async def test_returns_spaces(self, mock_context):
        mock_context.fetch.return_value = {"spaces": [{"id": "s1", "name": "Space 1"}]}

        result = await clickup.execute_action(
            "get_spaces", {"team_id": "t1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["spaces"] == [{"id": "s1", "name": "Space 1"}]
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/team/t1/space", method="GET", params=None
        )

    @pytest.mark.asyncio
    async def test_with_archived(self, mock_context):
        mock_context.fetch.return_value = {"spaces": []}

        await clickup.execute_action(
            "get_spaces", {"team_id": "t1", "archived": True}, mock_context
        )

        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/team/t1/space",
            method="GET",
            params={"archived": "true"},
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await clickup.execute_action(
            "get_spaces", {"team_id": "t1"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["spaces"] == []


class TestGetSpace:
    @pytest.mark.asyncio
    async def test_returns_space(self, mock_context):
        mock_context.fetch.return_value = {"id": "s1", "name": "My Space"}

        result = await clickup.execute_action(
            "get_space", {"space_id": "s1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["space"] == {"id": "s1", "name": "My Space"}
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/space/s1", method="GET"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await clickup.execute_action(
            "get_space", {"space_id": "s1"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["space"] == {}


# ---------------------------------------------------------------------------
# Folder actions
# ---------------------------------------------------------------------------


class TestCreateFolder:
    @pytest.mark.asyncio
    async def test_creates_folder(self, mock_context):
        mock_context.fetch.return_value = {"id": "f1", "name": "New Folder"}

        result = await clickup.execute_action(
            "create_folder", {"space_id": "s1", "name": "New Folder"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["folder"] == {"id": "f1", "name": "New Folder"}
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/space/s1/folder",
            method="POST",
            json={"name": "New Folder"},
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await clickup.execute_action(
            "create_folder", {"space_id": "s1", "name": "Fail"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["folder"] == {}


class TestGetFolder:
    @pytest.mark.asyncio
    async def test_returns_folder(self, mock_context):
        mock_context.fetch.return_value = {"id": "f1", "name": "Folder 1"}

        result = await clickup.execute_action(
            "get_folder", {"folder_id": "f1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["folder"]["id"] == "f1"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/folder/f1", method="GET"
        )


class TestUpdateFolder:
    @pytest.mark.asyncio
    async def test_updates_folder(self, mock_context):
        mock_context.fetch.return_value = {"id": "f1", "name": "Renamed"}

        result = await clickup.execute_action(
            "update_folder", {"folder_id": "f1", "name": "Renamed"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["folder"]["name"] == "Renamed"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/folder/f1", method="PUT", json={"name": "Renamed"}
        )


class TestDeleteFolder:
    @pytest.mark.asyncio
    async def test_deletes_folder(self, mock_context):
        mock_context.fetch.return_value = None

        result = await clickup.execute_action(
            "delete_folder", {"folder_id": "f1"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/folder/f1", method="DELETE"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await clickup.execute_action(
            "delete_folder", {"folder_id": "f1"}, mock_context
        )

        assert result.result.data["result"] is False


class TestGetFolders:
    @pytest.mark.asyncio
    async def test_returns_folders(self, mock_context):
        mock_context.fetch.return_value = {"folders": [{"id": "f1"}, {"id": "f2"}]}

        result = await clickup.execute_action(
            "get_folders", {"space_id": "s1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert len(result.result.data["folders"]) == 2

    @pytest.mark.asyncio
    async def test_with_archived(self, mock_context):
        mock_context.fetch.return_value = {"folders": []}

        await clickup.execute_action(
            "get_folders", {"space_id": "s1", "archived": False}, mock_context
        )

        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/space/s1/folder",
            method="GET",
            params={"archived": "false"},
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await clickup.execute_action(
            "get_folders", {"space_id": "s1"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["folders"] == []


# ---------------------------------------------------------------------------
# List actions
# ---------------------------------------------------------------------------


class TestCreateList:
    @pytest.mark.asyncio
    async def test_creates_list_in_folder(self, mock_context):
        mock_context.fetch.return_value = {"id": "l1", "name": "My List"}

        result = await clickup.execute_action(
            "create_list", {"folder_id": "f1", "name": "My List"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["list"]["name"] == "My List"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/folder/f1/list",
            method="POST",
            json={"name": "My List"},
        )

    @pytest.mark.asyncio
    async def test_creates_list_in_space(self, mock_context):
        mock_context.fetch.return_value = {"id": "l2", "name": "Space List"}

        result = await clickup.execute_action(
            "create_list", {"space_id": "s1", "name": "Space List"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/space/s1/list",
            method="POST",
            json={"name": "Space List"},
        )

    @pytest.mark.asyncio
    async def test_missing_parent_returns_error(self, mock_context):
        result = await clickup.execute_action(
            "create_list", {"name": "Orphan"}, mock_context
        )

        assert result.result.data["result"] is False
        assert "folder_id or space_id" in result.result.data["error"]

    @pytest.mark.asyncio
    async def test_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = {"id": "l3"}

        await clickup.execute_action(
            "create_list",
            {
                "folder_id": "f1",
                "name": "Detailed",
                "content": "Description",
                "priority": 2,
            },
            mock_context,
        )

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["name"] == "Detailed"
        assert call_json["content"] == "Description"
        assert call_json["priority"] == 2


class TestGetList:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = {"id": "l1", "name": "List 1"}

        result = await clickup.execute_action(
            "get_list", {"list_id": "l1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["list"]["id"] == "l1"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/list/l1", method="GET"
        )


class TestUpdateList:
    @pytest.mark.asyncio
    async def test_updates_list(self, mock_context):
        mock_context.fetch.return_value = {"id": "l1", "name": "Updated"}

        result = await clickup.execute_action(
            "update_list", {"list_id": "l1", "name": "Updated"}, mock_context
        )

        assert result.result.data["result"] is True
        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["name"] == "Updated"


class TestDeleteList:
    @pytest.mark.asyncio
    async def test_deletes_list(self, mock_context):
        mock_context.fetch.return_value = None

        result = await clickup.execute_action(
            "delete_list", {"list_id": "l1"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/list/l1", method="DELETE"
        )


class TestGetLists:
    @pytest.mark.asyncio
    async def test_returns_lists_from_folder(self, mock_context):
        mock_context.fetch.return_value = {"lists": [{"id": "l1"}, {"id": "l2"}]}

        result = await clickup.execute_action(
            "get_lists", {"folder_id": "f1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert len(result.result.data["lists"]) == 2
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/folder/f1/list", method="GET", params=None
        )

    @pytest.mark.asyncio
    async def test_returns_lists_from_space(self, mock_context):
        mock_context.fetch.return_value = {"lists": []}

        result = await clickup.execute_action(
            "get_lists", {"space_id": "s1"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/space/s1/list", method="GET", params=None
        )

    @pytest.mark.asyncio
    async def test_missing_parent_returns_error(self, mock_context):
        result = await clickup.execute_action("get_lists", {}, mock_context)

        assert result.result.data["result"] is False
        assert result.result.data["lists"] == []


# ---------------------------------------------------------------------------
# Task actions
# ---------------------------------------------------------------------------


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_creates_task(self, mock_context):
        mock_context.fetch.return_value = {"id": "task1", "name": "New Task"}

        result = await clickup.execute_action(
            "create_task", {"list_id": "l1", "name": "New Task"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["task"]["name"] == "New Task"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/list/l1/task",
            method="POST",
            json={"name": "New Task"},
        )

    @pytest.mark.asyncio
    async def test_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = {"id": "task2"}

        await clickup.execute_action(
            "create_task",
            {
                "list_id": "l1",
                "name": "Detailed Task",
                "description": "A description",
                "priority": 1,
                "status": "In Progress",
                "tags": ["urgent"],
            },
            mock_context,
        )

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["name"] == "Detailed Task"
        assert call_json["description"] == "A description"
        assert call_json["priority"] == 1
        assert call_json["status"] == "In Progress"
        assert call_json["tags"] == ["urgent"]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await clickup.execute_action(
            "create_task", {"list_id": "l1", "name": "Fail"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["task"] == {}


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_task(self, mock_context):
        mock_context.fetch.return_value = {"id": "task1", "name": "My Task"}

        result = await clickup.execute_action(
            "get_task", {"task_id": "task1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["task"]["id"] == "task1"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1", method="GET", params=None
        )

    @pytest.mark.asyncio
    async def test_with_subtasks(self, mock_context):
        mock_context.fetch.return_value = {"id": "task1", "subtasks": []}

        await clickup.execute_action(
            "get_task", {"task_id": "task1", "include_subtasks": True}, mock_context
        )

        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1",
            method="GET",
            params={"include_subtasks": "true"},
        )


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_updates_task(self, mock_context):
        mock_context.fetch.return_value = {"id": "task1", "name": "Updated"}

        result = await clickup.execute_action(
            "update_task",
            {"task_id": "task1", "name": "Updated", "status": "Complete"},
            mock_context,
        )

        assert result.result.data["result"] is True
        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["name"] == "Updated"
        assert call_json["status"] == "Complete"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1", method="PUT", json=call_json
        )


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_deletes_task(self, mock_context):
        mock_context.fetch.return_value = None

        result = await clickup.execute_action(
            "delete_task", {"task_id": "task1"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1", method="DELETE"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await clickup.execute_action(
            "delete_task", {"task_id": "task1"}, mock_context
        )

        assert result.result.data["result"] is False


class TestGetTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks(self, mock_context):
        mock_context.fetch.return_value = {"tasks": [{"id": "t1"}, {"id": "t2"}]}

        result = await clickup.execute_action(
            "get_tasks", {"list_id": "l1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert len(result.result.data["tasks"]) == 2

    @pytest.mark.asyncio
    async def test_with_filters(self, mock_context):
        mock_context.fetch.return_value = {"tasks": []}

        await clickup.execute_action(
            "get_tasks",
            {
                "list_id": "l1",
                "archived": True,
                "page": 2,
                "order_by": "created",
                "reverse": True,
            },
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["archived"] == "true"
        assert params["page"] == 2
        assert params["order_by"] == "created"
        assert params["reverse"] == "true"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await clickup.execute_action(
            "get_tasks", {"list_id": "l1"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["tasks"] == []


# ---------------------------------------------------------------------------
# Attachment action
# ---------------------------------------------------------------------------


class TestCreateTaskAttachment:
    @pytest.fixture
    def mock_context_with_auth(self, mock_context):
        mock_context.auth = {
            "credentials": {"access_token": "test_token"},  # nosec B105
        }
        return mock_context

    @pytest.mark.asyncio
    async def test_missing_file_content(self, mock_context_with_auth):
        inputs = {
            "workspace_id": "w1",
            "task_id": "task1",
            "file": {"name": "empty.txt", "content": "", "contentType": "text/plain"},
        }

        result = await clickup.execute_action(
            "create_task_attachment", inputs, mock_context_with_auth
        )

        assert result.result.data["result"] is False
        assert "no content" in result.result.data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_base64(self, mock_context_with_auth):
        inputs = {
            "workspace_id": "w1",
            "task_id": "task1",
            "file": {
                "name": "bad.txt",
                "content": "!!!invalid!!!",
                "contentType": "text/plain",
            },
        }

        result = await clickup.execute_action(
            "create_task_attachment", inputs, mock_context_with_auth
        )

        assert result.result.data["result"] is False
        assert (
            "decode" in result.result.data["error"].lower()
            or "base64" in result.result.data["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_no_auth_token(self, mock_context):
        mock_context.auth = {}

        inputs = {
            "workspace_id": "w1",
            "task_id": "task1",
            "file": {
                "name": "test.txt",
                "content": "dGVzdA==",
                "contentType": "text/plain",
            },
        }

        result = await clickup.execute_action(
            "create_task_attachment", inputs, mock_context
        )

        assert result.result.data["result"] is False
        assert (
            "authentication" in result.result.data["error"].lower()
            or "token" in result.result.data["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_successful_upload(self, mock_context_with_auth):
        inputs = {
            "workspace_id": "w1",
            "task_id": "task1",
            "file": {
                "name": "test.txt",
                "content": "dGVzdA==",
                "contentType": "text/plain",
            },
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"id": "att1", "url": "https://example.com/att1"}
        )
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await clickup.execute_action(
                "create_task_attachment", inputs, mock_context_with_auth
            )

        assert result.result.data["result"] is True
        assert result.result.data["attachment"] == {
            "id": "att1",
            "url": "https://example.com/att1",
        }

    @pytest.mark.asyncio
    async def test_http_error_response(self, mock_context_with_auth):
        inputs = {
            "workspace_id": "w1",
            "task_id": "task1",
            "file": {
                "name": "test.txt",
                "content": "dGVzdA==",
                "contentType": "text/plain",
            },
        }

        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.text = AsyncMock(return_value="Not Found or Authorized")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await clickup.execute_action(
                "create_task_attachment", inputs, mock_context_with_auth
            )

        assert result.result.data["result"] is False
        assert "404" in result.result.data["error"]


# ---------------------------------------------------------------------------
# Comment actions
# ---------------------------------------------------------------------------


class TestCreateTaskComment:
    @pytest.mark.asyncio
    async def test_creates_comment(self, mock_context):
        mock_context.fetch.return_value = {"id": "c1", "comment_text": "Hello"}

        result = await clickup.execute_action(
            "create_task_comment",
            {"task_id": "task1", "comment_text": "Hello"},
            mock_context,
        )

        assert result.result.data["result"] is True
        assert result.result.data["comment"]["id"] == "c1"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1/comment",
            method="POST",
            json={"comment_text": "Hello"},
        )

    @pytest.mark.asyncio
    async def test_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = {"id": "c2"}

        await clickup.execute_action(
            "create_task_comment",
            {
                "task_id": "task1",
                "comment_text": "Note",
                "assignee": 123,
                "notify_all": True,
            },
            mock_context,
        )

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["assignee"] == 123
        assert call_json["notify_all"] is True

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await clickup.execute_action(
            "create_task_comment",
            {"task_id": "task1", "comment_text": "Fail"},
            mock_context,
        )

        assert result.result.data["result"] is False
        assert result.result.data["comment"] == {}


class TestGetTaskComments:
    @pytest.mark.asyncio
    async def test_returns_comments(self, mock_context):
        mock_context.fetch.return_value = {"comments": [{"id": "c1"}, {"id": "c2"}]}

        result = await clickup.execute_action(
            "get_task_comments", {"task_id": "task1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert len(result.result.data["comments"]) == 2
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/task/task1/comment", method="GET"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await clickup.execute_action(
            "get_task_comments", {"task_id": "task1"}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["comments"] == []


class TestUpdateComment:
    @pytest.mark.asyncio
    async def test_updates_comment(self, mock_context):
        mock_context.fetch.return_value = {"id": "c1", "comment_text": "Updated"}

        result = await clickup.execute_action(
            "update_comment",
            {"comment_id": "c1", "comment_text": "Updated"},
            mock_context,
        )

        assert result.result.data["result"] is True
        assert result.result.data["comment"]["comment_text"] == "Updated"
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/comment/c1",
            method="PUT",
            json={"comment_text": "Updated"},
        )


class TestDeleteComment:
    @pytest.mark.asyncio
    async def test_deletes_comment(self, mock_context):
        mock_context.fetch.return_value = None

        result = await clickup.execute_action(
            "delete_comment", {"comment_id": "c1"}, mock_context
        )

        assert result.result.data["result"] is True
        mock_context.fetch.assert_called_once_with(
            f"{CLICKUP_API_BASE_URL}/comment/c1", method="DELETE"
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await clickup.execute_action(
            "delete_comment", {"comment_id": "c1"}, mock_context
        )

        assert result.result.data["result"] is False
