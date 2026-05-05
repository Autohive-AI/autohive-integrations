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

_spec = importlib.util.spec_from_file_location("hubspot_mod", os.path.join(_parent, "hubspot.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

hubspot = _mod.hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


TASKS_API_URL = "https://api.hubapi.com/crm/v3/objects/tasks"

SAMPLE_TASK_RESPONSE = {
    "id": "23456",
    "properties": {
        "hs_task_body": "Test task content",
        "hs_timestamp": "1700000000000",
        "hs_createdate": "2025-01-15T10:00:00.000Z",
    },
}


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_with_contact_association(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        result = await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Follow up tomorrow",
                "hs_timestamp": 1700000000000,
                "contact_id": "501",
            },
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["task"] == SAMPLE_TASK_RESPONSE

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == TASKS_API_URL
        assert call_kwargs.kwargs["method"] == "POST"
        payload = call_kwargs.kwargs["json"]
        assert payload["properties"]["hs_task_body"] == "Follow up tomorrow"
        assert payload["associations"][0]["to"]["id"] == "501"

    @pytest.mark.asyncio
    async def test_create_task_multiple_associations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Multi-assoc task",
                "hs_timestamp": 1700000000000,
                "contact_id": "100",
                "company_id": "200",
                "deal_id": "300",
            },
            mock_context,
        )

        associations = mock_context.fetch.call_args.kwargs["json"]["associations"]
        assert len(associations) == 3
        assert [a["types"][0]["associationTypeId"] for a in associations] == [
            204,
            192,
            216,
        ]

    @pytest.mark.asyncio
    async def test_create_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Will fail",
                "hs_timestamp": 1700000000000,
                "contact_id": "501",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to create task" in result.result.message

    @pytest.mark.asyncio
    async def test_create_task_with_direct_associations_object(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Task with direct associations",
                "hs_timestamp": 1700000000000,
                "associations": [
                    {
                        "to": {"id": "501"},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 204,
                            }
                        ],
                    }
                ],
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["associations"][0]["to"]["id"] == "501"
        assert payload["associations"][0]["types"][0]["associationTypeId"] == 204

    @pytest.mark.asyncio
    async def test_create_task_without_timestamp_returns_validation_error(self, mock_context):
        result = await hubspot.execute_action("create_task", {"hs_task_body": "No timestamp"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "hs_timestamp" in result.result["message"]
        mock_context.fetch.assert_not_called()


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_task_body(self, mock_context):
        updated_response = {
            "id": "23456",
            "properties": {"hs_task_body": "Updated content"},
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated_response)

        result = await hubspot.execute_action(
            "update_task",
            {"hs_object_id": "23456", "hs_task_body": "Updated content"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["task"] == updated_response
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_update_task_additional_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        result = await hubspot.execute_action(
            "update_task",
            {
                "hs_object_id": "23456",
                "hs_task_body": "Body",
                "additional_properties": {"hs_task_priority": "HIGH"},
            },
            mock_context,
        )

        props = mock_context.fetch.call_args.kwargs["json"]["properties"]
        assert props["hs_task_body"] == "Body"
        assert props["hs_task_priority"] == "HIGH"
        assert result.result.data["updated_properties"]["hs_task_priority"] == "HIGH"

    @pytest.mark.asyncio
    async def test_update_task_no_properties_returns_action_error(self, mock_context):
        result = await hubspot.execute_action("update_task", {"hs_object_id": "23456"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "No properties provided to update"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action(
            "update_task",
            {"hs_object_id": "23456", "hs_task_body": "Will fail"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to update task" in result.result.message


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await hubspot.execute_action("delete_task", {"hs_object_id": "23456"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["hs_object_id"] == "23456"
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_delete_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action("delete_task", {"hs_object_id": "99999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to delete task" in result.result.message


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_task_success(self, mock_context):
        response_data = {
            "id": "23456",
            "properties": {
                "hs_task_body": "Task body",
                "hs_timestamp": "1700000000000",
                "hs_createdate": "1700000000000",
                "hs_lastmodifieddate": "1700000100000",
            },
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await hubspot.execute_action("get_task", {"hs_object_id": "23456"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["task"]["id"] == "23456"
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        params = mock_context.fetch.call_args.kwargs["params"]
        assert "properties" in params
        # Default property set matches create_task / update_task fields
        assert "hs_task_type" in params["properties"]
        assert "hubspot_owner_id" in params["properties"]
        assert "hs_task_reminders" in params["properties"]

    @pytest.mark.asyncio
    async def test_get_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action("get_task", {"hs_object_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve task" in result.result.message


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_context):
        response_data = {
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "hs_task_body": "Task 1",
                        "hs_timestamp": "1700000000000",
                    },
                },
                {
                    "id": "2",
                    "properties": {
                        "hs_task_body": "Task 2",
                        "hs_timestamp": "1700000100000",
                    },
                },
            ],
            "paging": {"next": {"after": "abc123"}},
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await hubspot.execute_action("list_tasks", {"limit": 2}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["total"] == 2
        assert len(result.result.data["tasks"]) == 2
        assert result.result.data["paging"]["next"]["after"] == "abc123"
        assert mock_context.fetch.call_args.args[0] == TASKS_API_URL
        list_params = mock_context.fetch.call_args.kwargs["params"]
        assert list_params["limit"] == 2
        assert "hs_task_type" in list_params["properties"]
        assert "hubspot_owner_id" in list_params["properties"]
        assert "hs_task_reminders" in list_params["properties"]

    @pytest.mark.asyncio
    async def test_list_tasks_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("list_tasks", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_list_tasks_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve tasks" in result.result.message
