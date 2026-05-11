import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("harvest_mod", os.path.join(_parent, "harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

harvest = _mod.harvest

pytestmark = pytest.mark.unit

SAMPLE_TIME_ENTRY = {
    "id": 1001,
    "project_id": 5,
    "task_id": 10,
    "spent_date": "2025-01-15",
    "hours": 2.5,
    "notes": "Working on feature",
    "is_running": False,
}

SAMPLE_PROJECT = {
    "id": 5,
    "name": "My Project",
    "is_active": True,
    "client": {"id": 3, "name": "Acme Corp"},
}

SAMPLE_CLIENT = {"id": 3, "name": "Acme Corp", "is_active": True}

SAMPLE_TASK = {"id": 10, "name": "Development", "is_active": True}

SAMPLE_USER = {"id": 1, "first_name": "Jane", "last_name": "Doe", "is_active": True}

LIST_RESPONSE = {
    "per_page": 100,
    "total_pages": 1,
    "total_entries": 1,
    "next_page": None,
    "previous_page": None,
    "page": 1,
    "links": {"first": "https://api.harvestapp.com/v2/time_entries?page=1"},
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


# ---- Time Entry Actions ----


class TestCreateTimeEntry:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_ENTRY)

        result = await harvest.execute_action(
            "create_time_entry",
            {"project_id": 5, "task_id": 10, "spent_date": "2025-01-15"},
            mock_context,
        )

        assert result.result.data["time_entry"]["id"] == 1001

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action(
            "create_time_entry",
            {"project_id": 5, "task_id": 10, "spent_date": "2025-01-15"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/time_entries"
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_required_fields_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action(
            "create_time_entry",
            {"project_id": 5, "task_id": 10, "spent_date": "2025-01-15"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["project_id"] == 5
        assert payload["task_id"] == 10
        assert payload["spent_date"] == "2025-01-15"

    @pytest.mark.asyncio
    async def test_optional_hours_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action(
            "create_time_entry",
            {"project_id": 5, "task_id": 10, "spent_date": "2025-01-15", "hours": 3.0},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["hours"] == 3.0

    @pytest.mark.asyncio
    async def test_start_end_times_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action(
            "create_time_entry",
            {
                "project_id": 5,
                "task_id": 10,
                "spent_date": "2025-01-15",
                "started_time": "09:00",
                "ended_time": "17:00",
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["started_time"] == "09:00"
        assert payload["ended_time"] == "17:00"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection error")

        result = await harvest.execute_action(
            "create_time_entry",
            {"project_id": 5, "task_id": 10, "spent_date": "2025-01-15"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection error" in result.result.message


class TestStopTimeEntry:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        stopped_entry = {**SAMPLE_TIME_ENTRY, "is_running": False}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=stopped_entry)

        result = await harvest.execute_action("stop_time_entry", {"time_entry_id": 1001}, mock_context)

        assert result.result.data["time_entry"]["id"] == 1001
        assert result.result.data["time_entry"]["is_running"] is False

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action("stop_time_entry", {"time_entry_id": 1001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/time_entries/1001/stop"
        assert call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await harvest.execute_action("stop_time_entry", {"time_entry_id": 9999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


class TestListTimeEntries:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        body = {**LIST_RESPONSE, "time_entries": [SAMPLE_TIME_ENTRY]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_time_entries", {}, mock_context)

        assert len(result.result.data["time_entries"]) == 1
        assert result.result.data["total_entries"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        body = {**LIST_RESPONSE, "time_entries": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_time_entries", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/time_entries"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_filters_passed_as_params(self, mock_context):
        body = {**LIST_RESPONSE, "time_entries": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action(
            "list_time_entries",
            {"project_id": 5, "from": "2025-01-01", "to": "2025-01-31"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["project_id"] == 5
        assert params["from"] == "2025-01-01"
        assert params["to"] == "2025-01-31"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        body = {**LIST_RESPONSE, "time_entries": [], "total_entries": 0}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_time_entries", {}, mock_context)

        assert result.result.data["time_entries"] == []
        assert result.result.data["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Service unavailable")

        result = await harvest.execute_action("list_time_entries", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Service unavailable" in result.result.message

    @pytest.mark.asyncio
    async def test_pagination_fields_in_response(self, mock_context):
        body = {**LIST_RESPONSE, "time_entries": [], "next_page": 2, "total_pages": 3}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_time_entries", {}, mock_context)

        assert result.result.data["next_page"] == 2
        assert result.result.data["total_pages"] == 3


class TestUpdateTimeEntry:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        updated = {**SAMPLE_TIME_ENTRY, "notes": "Updated notes"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await harvest.execute_action(
            "update_time_entry",
            {"time_entry_id": 1001, "notes": "Updated notes"},
            mock_context,
        )

        assert result.result.data["time_entry"]["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action("update_time_entry", {"time_entry_id": 1001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/time_entries/1001"
        assert call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_payload_contains_only_provided_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await harvest.execute_action(
            "update_time_entry",
            {"time_entry_id": 1001, "hours": 4.0},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["hours"] == 4.0
        assert "notes" not in payload

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update failed")

        result = await harvest.execute_action("update_time_entry", {"time_entry_id": 1001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Update failed" in result.result.message


class TestDeleteTimeEntry:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await harvest.execute_action("delete_time_entry", {"time_entry_id": 1001}, mock_context)

        assert "1001" in result.result.data["message"]
        assert "deleted" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await harvest.execute_action("delete_time_entry", {"time_entry_id": 1001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/time_entries/1001"
        assert call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await harvest.execute_action("delete_time_entry", {"time_entry_id": 1001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- Project Actions ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        body = {**LIST_RESPONSE, "projects": [SAMPLE_PROJECT]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_projects", {}, mock_context)

        assert len(result.result.data["projects"]) == 1
        assert result.result.data["projects"][0]["id"] == 5

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        body = {**LIST_RESPONSE, "projects": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_projects", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/projects"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_active_filter_passed(self, mock_context):
        body = {**LIST_RESPONSE, "projects": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_projects", {"is_active": True}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["is_active"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await harvest.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


class TestGetProject:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        result = await harvest.execute_action("get_project", {"project_id": 5}, mock_context)

        assert result.result.data["project"]["id"] == 5
        assert result.result.data["project"]["name"] == "My Project"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        await harvest.execute_action("get_project", {"project_id": 5}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/projects/5"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Project not found")

        result = await harvest.execute_action("get_project", {"project_id": 9999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Project not found" in result.result.message


# ---- Client Actions ----


class TestListClients:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        body = {**LIST_RESPONSE, "clients": [SAMPLE_CLIENT]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_clients", {}, mock_context)

        assert len(result.result.data["clients"]) == 1
        assert result.result.data["clients"][0]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        body = {**LIST_RESPONSE, "clients": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_clients", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/clients"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_pagination_params_passed(self, mock_context):
        body = {**LIST_RESPONSE, "clients": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_clients", {"page": 2, "per_page": 50}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["page"] == 2
        assert params["per_page"] == 50

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Rate limited")

        result = await harvest.execute_action("list_clients", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Rate limited" in result.result.message


# ---- Task Actions ----


class TestListTasks:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        body = {**LIST_RESPONSE, "tasks": [SAMPLE_TASK]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_tasks", {}, mock_context)

        assert len(result.result.data["tasks"]) == 1
        assert result.result.data["tasks"][0]["name"] == "Development"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        body = {**LIST_RESPONSE, "tasks": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_tasks", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/tasks"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_inactive_filter(self, mock_context):
        body = {**LIST_RESPONSE, "tasks": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_tasks", {"is_active": False}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["is_active"] is False

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await harvest.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- User Actions ----


class TestListUsers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        body = {**LIST_RESPONSE, "users": [SAMPLE_USER]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_users", {}, mock_context)

        assert len(result.result.data["users"]) == 1
        assert result.result.data["users"][0]["first_name"] == "Jane"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        body = {**LIST_RESPONSE, "users": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_users", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.harvestapp.com/v2/users"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_active_filter_passed(self, mock_context):
        body = {**LIST_RESPONSE, "users": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        await harvest.execute_action("list_users", {"is_active": True}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["is_active"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await harvest.execute_action("list_users", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message

    @pytest.mark.asyncio
    async def test_response_has_pagination_fields(self, mock_context):
        body = {**LIST_RESPONSE, "users": [SAMPLE_USER]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=body)

        result = await harvest.execute_action("list_users", {}, mock_context)

        assert "per_page" in result.result.data
        assert "total_pages" in result.result.data
        assert "page" in result.result.data
