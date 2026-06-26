import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.unit

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SAMPLE_TASK = {
    "id": "task-id-1",
    "title": "Create marketing materials",
    "planId": "plan-id-1",
    "bucketId": "bucket-id-1",
    "percentComplete": 50,
    "priority": 5,
    "@odata.etag": 'W/"etag-task-xyz"',
    "assignments": {
        "user-id-1": {
            "@odata.type": "#microsoft.graph.plannerAssignment",
            "assignedDateTime": "2024-01-15T10:00:00Z",
        }
    },
}

SAMPLE_TASK_DETAILS = {
    "id": "task-id-1",
    "@odata.etag": 'W/"etag-details-abc"',
    "description": "Task description",
    "checklist": {
        "item-id-1": {
            "@odata.type": "#microsoft.graph.plannerChecklistItem",
            "title": "Step 1",
            "isChecked": False,
            "orderHint": "8585!",
        }
    },
    "references": {},
}


# ---- List Tasks Tests ----


class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_TASK]})

        result = await microsoft_planner.execute_action("list_tasks", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["tasks"] == [SAMPLE_TASK]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_plan_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_tasks", {"plan_id": "plan-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/plans/plan-id-1/tasks" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_empty_tasks(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("list_tasks", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["tasks"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action("list_tasks", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Get Task Tests ----


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_task(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        result = await microsoft_planner.execute_action("get_task", {"task_id": "task-id-1"}, mock_context)

        assert result.result.data["task"] == SAMPLE_TASK
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_task_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        await microsoft_planner.execute_action("get_task", {"task_id": "task-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/tasks/task-id-1" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Task not found")

        result = await microsoft_planner.execute_action("get_task", {"task_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Task not found" in result.result.message


# ---- Create Task Tests ----


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_creates_task_with_required_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        result = await microsoft_planner.execute_action(
            "create_task",
            {"plan_id": "plan-id-1", "bucket_id": "bucket-id-1", "title": "New Task"},
            mock_context,
        )

        assert result.result.data["task"] == SAMPLE_TASK
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_body_required_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await microsoft_planner.execute_action(
            "create_task",
            {"plan_id": "plan-id-1", "bucket_id": "bucket-id-1", "title": "New Task"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "POST"
        body = call_args.kwargs["json"]
        assert body["planId"] == "plan-id-1"
        assert body["bucketId"] == "bucket-id-1"
        assert body["title"] == "New Task"

    @pytest.mark.asyncio
    async def test_creates_task_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await microsoft_planner.execute_action(
            "create_task",
            {
                "plan_id": "plan-id-1",
                "bucket_id": "bucket-id-1",
                "title": "Task With Options",
                "priority": 3,
                "percent_complete": 0,
                "due_date_time": "2024-12-31T17:00:00Z",
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["priority"] == 3
        assert body["percentComplete"] == 0
        assert body["dueDateTime"] == "2024-12-31T17:00:00Z"

    @pytest.mark.asyncio
    async def test_assignment_gets_odata_type_added(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await microsoft_planner.execute_action(
            "create_task",
            {
                "plan_id": "plan-id-1",
                "bucket_id": "bucket-id-1",
                "title": "Task",
                "assignments": {"user-id-1": {}},
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["assignments"]["user-id-1"]["@odata.type"] == "#microsoft.graph.plannerAssignment"

    @pytest.mark.asyncio
    async def test_null_assignment_removes_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await microsoft_planner.execute_action(
            "create_task",
            {
                "plan_id": "plan-id-1",
                "bucket_id": "bucket-id-1",
                "title": "Task",
                "assignments": {"user-id-1": None},
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["assignments"]["user-id-1"] is None

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Permission denied")

        result = await microsoft_planner.execute_action(
            "create_task",
            {"plan_id": "plan-id-1", "bucket_id": "bucket-id-1", "title": "Task"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Permission denied" in result.result.message


# ---- Update Task Tests ----


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_updates_task_title(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_task", {"task_id": "task-id-1", "title": "Updated Title"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["task"] == {}

    @pytest.mark.asyncio
    async def test_patch_includes_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task", {"task_id": "task-id-1", "title": "New Title"}, mock_context
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-task-xyz"'
        assert patch_call.kwargs["method"] == "PATCH"
        assert patch_call.kwargs["json"]["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_updates_percent_complete_and_priority(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task",
            {"task_id": "task-id-1", "percent_complete": 75, "priority": 1},
            mock_context,
        )

        body = mock_context.fetch.call_args_list[1].kwargs["json"]
        assert body["percentComplete"] == 75
        assert body["priority"] == 1

    @pytest.mark.asyncio
    async def test_no_fields_to_update_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK)

        result = await microsoft_planner.execute_action("update_task", {"task_id": "task-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "No fields" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_task", {"task_id": "task-id-1", "title": "Title"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            Exception("Conflict"),
        ]

        result = await microsoft_planner.execute_action(
            "update_task", {"task_id": "task-id-1", "title": "Title"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message


# ---- Delete Task Tests ----


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_deletes_task(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action("delete_task", {"task_id": "task-id-1"}, mock_context)

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_delete_includes_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action("delete_task", {"task_id": "task-id-1"}, mock_context)

        delete_call = mock_context.fetch.call_args_list[1]
        assert delete_call.kwargs["headers"]["If-Match"] == 'W/"etag-task-xyz"'
        assert delete_call.kwargs["method"] == "DELETE"
        assert "/planner/tasks/task-id-1" in delete_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action("delete_task", {"task_id": "task-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK),
            Exception("Not found"),
        ]

        result = await microsoft_planner.execute_action("delete_task", {"task_id": "task-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Get Task Details Tests ----


class TestGetTaskDetails:
    @pytest.mark.asyncio
    async def test_returns_task_details(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS)

        result = await microsoft_planner.execute_action("get_task_details", {"task_id": "task-id-1"}, mock_context)

        assert result.result.data["task_details"] == SAMPLE_TASK_DETAILS
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS)

        await microsoft_planner.execute_action("get_task_details", {"task_id": "task-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/tasks/task-id-1/details" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action("get_task_details", {"task_id": "task-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Update Task Details Tests ----


class TestUpdateTaskDetails:
    @pytest.mark.asyncio
    async def test_updates_description(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_details",
            {"task_id": "task-id-1", "description": "New description"},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_body_and_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task_details",
            {"task_id": "task-id-1", "description": "Updated desc", "preview_type": "description"},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-details-abc"'
        body = patch_call.kwargs["json"]
        assert body["description"] == "Updated desc"
        assert body["previewType"] == "description"

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_task_details", {"task_id": "task-id-1", "description": "desc"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            Exception("Conflict"),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_details", {"task_id": "task-id-1", "description": "desc"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message


# ---- Add Checklist Item Tests ----


class TestAddChecklistItem:
    @pytest.mark.asyncio
    async def test_adds_item_to_checklist(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={**SAMPLE_TASK_DETAILS}),
        ]

        result = await microsoft_planner.execute_action(
            "add_checklist_item",
            {"task_id": "task-id-1", "title": "New step"},
            mock_context,
        )

        assert result.result.data["result"] is True
        assert "item_id" in result.result.data
        assert result.result.data["item_id"] is not None

    @pytest.mark.asyncio
    async def test_patch_body_includes_existing_and_new_item(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={}),
        ]

        await microsoft_planner.execute_action(
            "add_checklist_item",
            {"task_id": "task-id-1", "title": "New step", "is_checked": False},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-details-abc"'
        checklist = patch_call.kwargs["json"]["checklist"]
        # Original item + new item
        assert len(checklist) == 2
        # New item has the title we passed
        titles = [v["title"] for v in checklist.values() if v is not None]
        assert "New step" in titles

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "add_checklist_item", {"task_id": "task-id-1", "title": "Step"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await microsoft_planner.execute_action(
            "add_checklist_item", {"task_id": "task-id-1", "title": "Step"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- Update Checklist Item Tests ----


class TestUpdateChecklistItem:
    @pytest.mark.asyncio
    async def test_updates_checklist_item(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={}),
        ]

        result = await microsoft_planner.execute_action(
            "update_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1", "title": "Updated step", "is_checked": True},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_body_has_updated_item(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={}),
        ]

        await microsoft_planner.execute_action(
            "update_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1", "title": "Done", "is_checked": True},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        checklist = patch_call.kwargs["json"]["checklist"]
        assert checklist["item-id-1"]["title"] == "Done"
        assert checklist["item-id-1"]["isChecked"] is True

    @pytest.mark.asyncio
    async def test_item_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS)

        result = await microsoft_planner.execute_action(
            "update_checklist_item",
            {"task_id": "task-id-1", "item_id": "nonexistent-item", "title": "X"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await microsoft_planner.execute_action(
            "update_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1", "title": "X"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- Remove Checklist Item Tests ----


class TestRemoveChecklistItem:
    @pytest.mark.asyncio
    async def test_removes_checklist_item(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={}),
        ]

        result = await microsoft_planner.execute_action(
            "remove_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1"},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_removed_item_is_set_to_null(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS),
            FetchResponse(status=200, headers={}, data={}),
        ]

        await microsoft_planner.execute_action(
            "remove_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1"},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        checklist = patch_call.kwargs["json"]["checklist"]
        assert checklist["item-id-1"] is None

    @pytest.mark.asyncio
    async def test_item_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_DETAILS)

        result = await microsoft_planner.execute_action(
            "remove_checklist_item",
            {"task_id": "task-id-1", "item_id": "nonexistent"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await microsoft_planner.execute_action(
            "remove_checklist_item",
            {"task_id": "task-id-1", "item_id": "item-id-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message
