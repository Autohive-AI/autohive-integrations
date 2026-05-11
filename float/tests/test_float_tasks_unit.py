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

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

float_integration = _mod.float

pytestmark = pytest.mark.unit

SAMPLE_TASK = {
    "task_id": 50,
    "people_id": 123,
    "project_id": 10,
    "start_date": "2025-01-06",
    "end_date": "2025-01-10",
    "hours": 8.0,
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "api_key": "test_api_key",  # nosec B105
            "application_name": "Test App",
            "contact_email": "test@example.com",
        }
    }
    return ctx


# ---- List Tasks ----


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_tasks_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TASK])

        result = await float_integration.execute_action("list_tasks", {}, mock_context)

        assert result.result.data[0]["task_id"] == 50

    @pytest.mark.asyncio
    async def test_list_tasks_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_tasks", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/tasks")

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action(
            "list_tasks", {"people_id": 123, "project_id": 10, "start_date": "2025-01-01"}, mock_context
        )

        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params.get("people_id") == 123
        assert params.get("project_id") == 10
        assert params.get("start_date") == "2025-01-01"

    @pytest.mark.asyncio
    async def test_list_tasks_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Fetch error")

        result = await float_integration.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Fetch error" in result.result.message


# ---- Get Task ----


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_task_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        result = await float_integration.execute_action("get_task", {"task_id": 50}, mock_context)

        assert result.result.data["task_id"] == 50

    @pytest.mark.asyncio
    async def test_get_task_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        await float_integration.execute_action("get_task", {"task_id": 50}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/tasks/50")

    @pytest.mark.asyncio
    async def test_get_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_task", {"task_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Create Task ----


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={**SAMPLE_TASK, "task_id": 99})

        result = await float_integration.execute_action(
            "create_task",
            {"people_id": 123, "project_id": 10, "start_date": "2025-01-06", "end_date": "2025-01-10", "hours": 8.0},
            mock_context,
        )

        assert result.result.data["task_id"] == 99

    @pytest.mark.asyncio
    async def test_create_task_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await float_integration.execute_action(
            "create_task",
            {"people_id": 123, "project_id": 10, "start_date": "2025-01-06", "end_date": "2025-01-10", "hours": 4.0},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs.get("json", {})
        assert body["people_id"] == 123
        assert body["project_id"] == 10
        assert body["hours"] == 4.0

    @pytest.mark.asyncio
    async def test_create_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Conflict")

        result = await float_integration.execute_action(
            "create_task",
            {"people_id": 1, "project_id": 1, "start_date": "2025-01-01", "end_date": "2025-01-02", "hours": 8},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Update Task ----


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_task_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        await float_integration.execute_action("update_task", {"task_id": 50, "hours": 6.0}, mock_context)

        assert mock_context.fetch.call_args.kwargs.get("method") == "PATCH"

    @pytest.mark.asyncio
    async def test_update_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update error")

        result = await float_integration.execute_action("update_task", {"task_id": 50}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Delete Task ----


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_task_success_message(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_task", {"task_id": 50}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete error")

        result = await float_integration.execute_action("delete_task", {"task_id": 50}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
