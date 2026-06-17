import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from asana.asana import asana

pytestmark = pytest.mark.unit

SAMPLE_TASK = {"gid": "123456789", "name": "Test Task", "completed": False, "notes": ""}
SAMPLE_PROJECT = {"gid": "987654321", "name": "Test Project", "archived": False}
SAMPLE_SECTION = {"gid": "111111111", "name": "To Do"}
SAMPLE_STORY = {"gid": "222222222", "text": "A comment", "type": "comment"}
SAMPLE_WORKSPACE = {"gid": "333333333", "name": "My Workspace"}
SAMPLE_USER = {"gid": "444444444", "name": "Jane Doe", "email": "jane@example.com"}


# ---- Task Actions ----


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_creates_task(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_TASK})
        result = await asana.execute_action("create_task", {"name": "Test Task", "workspace": "333"}, mock_context)
        assert result.result.data["task"]["gid"] == "123456789"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action("create_task", {"name": "Test Task"}, mock_context)
        call_args = mock_context.fetch.call_args
        assert call_args.args[0].endswith("/tasks")
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_optional_fields_included(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action(
            "create_task",
            {"name": "Test Task", "workspace": "333", "assignee": "me", "due_on": "2025-12-31"},
            mock_context,
        )
        payload = mock_context.fetch.call_args.kwargs["json"]["data"]
        assert payload["assignee"] == "me"
        assert payload["due_on"] == "2025-12-31"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection error")
        result = await asana.execute_action("create_task", {"name": "Test Task"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection error" in result.result.message


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_task(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_TASK})
        result = await asana.execute_action("get_task", {"task_gid": "123456789"}, mock_context)
        assert result.result.data["task"]["gid"] == "123456789"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action("get_task", {"task_gid": "123456789"}, mock_context)
        assert "123456789" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_opt_fields_joined(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action("get_task", {"task_gid": "123", "opt_fields": ["name", "due_on"]}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["opt_fields"] == "name,due_on"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        result = await asana.execute_action("get_task", {"task_gid": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_updates_task(self, mock_context):
        updated = {**SAMPLE_TASK, "name": "Updated Task"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": updated})
        result = await asana.execute_action("update_task", {"task_gid": "123", "name": "Updated Task"}, mock_context)
        assert result.result.data["task"]["name"] == "Updated Task"

    @pytest.mark.asyncio
    async def test_request_method_is_put(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action("update_task", {"task_gid": "123", "completed": True}, mock_context)
        assert mock_context.fetch.call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await asana.execute_action("update_task", {"task_gid": "123"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [SAMPLE_TASK]})
        result = await asana.execute_action("list_tasks", {"project": "999"}, mock_context)
        assert isinstance(result.result.data["tasks"], list)
        assert result.result.data["tasks"][0]["gid"] == "123456789"

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})
        result = await asana.execute_action("list_tasks", {"project": "999"}, mock_context)
        assert result.result.data["tasks"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Rate limit")
        result = await asana.execute_action("list_tasks", {"project": "999"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_deletes_task(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        result = await asana.execute_action("delete_task", {"task_gid": "123"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_method_is_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        await asana.execute_action("delete_task", {"task_gid": "123"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")
        result = await asana.execute_action("delete_task", {"task_gid": "123"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- Project Actions ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_returns_projects(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [SAMPLE_PROJECT]})
        result = await asana.execute_action("list_projects", {"workspace": "333"}, mock_context)
        assert len(result.result.data["projects"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")
        result = await asana.execute_action("list_projects", {"workspace": "333"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetProject:
    @pytest.mark.asyncio
    async def test_returns_project(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_PROJECT})
        result = await asana.execute_action("get_project", {"project_gid": "987"}, mock_context)
        assert result.result.data["project"]["gid"] == "987654321"

    @pytest.mark.asyncio
    async def test_request_url_contains_gid(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_PROJECT})
        await asana.execute_action("get_project", {"project_gid": "987654321"}, mock_context)
        assert "987654321" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        result = await asana.execute_action("get_project", {"project_gid": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_creates_project(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_PROJECT})
        result = await asana.execute_action(
            "create_project", {"name": "Test Project", "workspace": "333"}, mock_context
        )
        assert result.result.data["project"]["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_workspace_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_PROJECT})
        await asana.execute_action("create_project", {"name": "Test", "workspace": "333"}, mock_context)
        payload = mock_context.fetch.call_args.kwargs["json"]["data"]
        assert payload["workspace"] == "333"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")
        result = await asana.execute_action("create_project", {"name": "X", "workspace": "333"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_updates_project(self, mock_context):
        updated = {**SAMPLE_PROJECT, "name": "Renamed"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": updated})
        result = await asana.execute_action("update_project", {"project_gid": "987", "name": "Renamed"}, mock_context)
        assert result.result.data["project"]["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await asana.execute_action("update_project", {"project_gid": "987"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_deletes_project(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        result = await asana.execute_action("delete_project", {"project_gid": "987"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")
        result = await asana.execute_action("delete_project", {"project_gid": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetProjectByName:
    @pytest.mark.asyncio
    async def test_finds_project(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"data": [SAMPLE_PROJECT], "next_page": None}
        )
        result = await asana.execute_action(
            "get_project_by_name", {"name": "Test Project", "workspace": "333"}, mock_context
        )
        assert result.result.data["not_found"] is False
        assert result.result.data["gid"] == "987654321"

    @pytest.mark.asyncio
    async def test_project_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [], "next_page": None})
        result = await asana.execute_action("get_project_by_name", {"name": "Nonexistent"}, mock_context)
        assert result.result.data["not_found"] is True
        assert result.result.data["gid"] is None

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")
        result = await asana.execute_action("get_project_by_name", {"name": "Test"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- Section Actions ----


class TestListSections:
    @pytest.mark.asyncio
    async def test_returns_sections(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [SAMPLE_SECTION]})
        result = await asana.execute_action("list_sections", {"project_gid": "987"}, mock_context)
        assert len(result.result.data["sections"]) == 1

    @pytest.mark.asyncio
    async def test_request_url_contains_project_gid(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})
        await asana.execute_action("list_sections", {"project_gid": "987654321"}, mock_context)
        assert "987654321" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("list_sections", {"project_gid": "987"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateSection:
    @pytest.mark.asyncio
    async def test_creates_section(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_SECTION})
        result = await asana.execute_action("create_section", {"project_gid": "987", "name": "To Do"}, mock_context)
        assert result.result.data["section"]["name"] == "To Do"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("create_section", {"project_gid": "987", "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateSection:
    @pytest.mark.asyncio
    async def test_updates_section(self, mock_context):
        updated = {**SAMPLE_SECTION, "name": "In Progress"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": updated})
        result = await asana.execute_action(
            "update_section", {"section_gid": "111", "name": "In Progress"}, mock_context
        )
        assert result.result.data["section"]["name"] == "In Progress"

    @pytest.mark.asyncio
    async def test_request_method_is_put(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_SECTION})
        await asana.execute_action("update_section", {"section_gid": "111", "name": "X"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("update_section", {"section_gid": "111", "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestAddTaskToSection:
    @pytest.mark.asyncio
    async def test_adds_task(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        result = await asana.execute_action(
            "add_task_to_section", {"section_gid": "111", "task_gid": "123"}, mock_context
        )
        assert result.result.data["added"] is True

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        await asana.execute_action("add_task_to_section", {"section_gid": "111", "task_gid": "123"}, mock_context)
        payload = mock_context.fetch.call_args.kwargs["json"]["data"]
        assert payload["task"] == "123"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action(
            "add_task_to_section", {"section_gid": "111", "task_gid": "123"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


# ---- Story Actions ----


class TestCreateStory:
    @pytest.mark.asyncio
    async def test_creates_story(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_STORY})
        result = await asana.execute_action("create_story", {"task_gid": "123", "text": "A comment"}, mock_context)
        assert result.result.data["story"]["text"] == "A comment"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_STORY})
        await asana.execute_action("create_story", {"task_gid": "123456789", "text": "Hi"}, mock_context)
        call_args = mock_context.fetch.call_args
        assert "123456789" in call_args.args[0]
        assert "stories" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("create_story", {"task_gid": "123", "text": "Hi"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListStories:
    @pytest.mark.asyncio
    async def test_returns_stories(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [SAMPLE_STORY]})
        result = await asana.execute_action("list_stories", {"task_gid": "123"}, mock_context)
        assert len(result.result.data["stories"]) == 1

    @pytest.mark.asyncio
    async def test_empty_stories(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})
        result = await asana.execute_action("list_stories", {"task_gid": "123"}, mock_context)
        assert result.result.data["stories"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("list_stories", {"task_gid": "123"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- Subtask Action ----


class TestCreateSubtask:
    @pytest.mark.asyncio
    async def test_creates_subtask(self, mock_context):
        subtask = {**SAMPLE_TASK, "gid": "555555555", "name": "Subtask 1"}
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": subtask})
        result = await asana.execute_action(
            "create_subtask", {"parent_task_gid": "123", "name": "Subtask 1"}, mock_context
        )
        assert result.result.data["subtask"]["name"] == "Subtask 1"

    @pytest.mark.asyncio
    async def test_request_url_contains_parent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"data": SAMPLE_TASK})
        await asana.execute_action("create_subtask", {"parent_task_gid": "123456789", "name": "Sub"}, mock_context)
        assert "123456789" in mock_context.fetch.call_args.args[0]
        assert "subtasks" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("create_subtask", {"parent_task_gid": "123", "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- Workspace Actions ----


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_returns_workspaces(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": [SAMPLE_WORKSPACE]})
        result = await asana.execute_action("list_workspaces", {}, mock_context)
        assert len(result.result.data["workspaces"]) == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})
        await asana.execute_action("list_workspaces", {}, mock_context)
        assert mock_context.fetch.call_args.args[0].endswith("/workspaces")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("list_workspaces", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_returns_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_WORKSPACE})
        result = await asana.execute_action("get_workspace", {"workspace_gid": "333"}, mock_context)
        assert result.result.data["workspace"]["gid"] == "333333333"

    @pytest.mark.asyncio
    async def test_request_url_contains_gid(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_WORKSPACE})
        await asana.execute_action("get_workspace", {"workspace_gid": "333333333"}, mock_context)
        assert "333333333" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")
        result = await asana.execute_action("get_workspace", {"workspace_gid": "bad"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ---- User Action ----


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_USER})
        result = await asana.execute_action("get_user", {"user_gid": "me"}, mock_context)
        assert result.result.data["user"]["name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_defaults_to_me(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_USER})
        await asana.execute_action("get_user", {}, mock_context)
        assert "/users/me" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_opt_fields_joined(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": SAMPLE_USER})
        await asana.execute_action("get_user", {"user_gid": "me", "opt_fields": ["email", "name"]}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["opt_fields"] == "email,name"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")
        result = await asana.execute_action("get_user", {"user_gid": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
