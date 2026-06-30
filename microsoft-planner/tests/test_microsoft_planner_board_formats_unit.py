import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.unit

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SAMPLE_ASSIGNED_TO_FORMAT = {
    "id": "task-id-1",
    "@odata.etag": 'W/"etag-assigned-abc"',
    "unassignedOrderHint": "8585!",
    "orderHintsByAssignee": {"user-id-1": "hint-1"},
}

SAMPLE_BUCKET_FORMAT = {
    "id": "task-id-1",
    "@odata.etag": 'W/"etag-bucket-format-abc"',
    "orderHint": "8585!",
}

SAMPLE_PROGRESS_FORMAT = {
    "id": "task-id-1",
    "@odata.etag": 'W/"etag-progress-abc"',
    "orderHint": "8585!",
}


# ---- Get Task Assigned-To Board Format Tests ----


class TestGetTaskAssignedToBoardFormat:
    @pytest.mark.asyncio
    async def test_returns_board_format(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ASSIGNED_TO_FORMAT)

        result = await microsoft_planner.execute_action(
            "get_task_assigned_to_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.result.data["board_format"] == SAMPLE_ASSIGNED_TO_FORMAT
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ASSIGNED_TO_FORMAT)

        await microsoft_planner.execute_action(
            "get_task_assigned_to_board_format", {"task_id": "task-id-1"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert "/planner/tasks/task-id-1/assignedToTaskBoardFormat" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action(
            "get_task_assigned_to_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Update Task Assigned-To Board Format Tests ----


class TestUpdateTaskAssignedToBoardFormat:
    @pytest.mark.asyncio
    async def test_updates_format(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_ASSIGNED_TO_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_assigned_to_board_format",
            {"task_id": "task-id-1", "unassigned_order_hint": "new-hint!"},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_body_and_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_ASSIGNED_TO_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task_assigned_to_board_format",
            {
                "task_id": "task-id-1",
                "unassigned_order_hint": "new-hint!",
                "order_hints_by_assignee": {"user-id-1": "hint-2"},
            },
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-assigned-abc"'
        body = patch_call.kwargs["json"]
        assert body["unassignedOrderHint"] == "new-hint!"
        assert body["orderHintsByAssignee"] == {"user-id-1": "hint-2"}

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_task_assigned_to_board_format",
            {"task_id": "task-id-1", "unassigned_order_hint": "hint"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_ASSIGNED_TO_FORMAT),
            Exception("Server error"),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_assigned_to_board_format",
            {"task_id": "task-id-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- Get Task Bucket Board Format Tests ----


class TestGetTaskBucketBoardFormat:
    @pytest.mark.asyncio
    async def test_returns_board_format(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET_FORMAT)

        result = await microsoft_planner.execute_action(
            "get_task_bucket_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.result.data["board_format"] == SAMPLE_BUCKET_FORMAT
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET_FORMAT)

        await microsoft_planner.execute_action("get_task_bucket_board_format", {"task_id": "task-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/tasks/task-id-1/bucketTaskBoardFormat" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action(
            "get_task_bucket_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Update Task Bucket Board Format Tests ----


class TestUpdateTaskBucketBoardFormat:
    @pytest.mark.asyncio
    async def test_updates_order_hint(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_bucket_board_format",
            {"task_id": "task-id-1", "order_hint": "new-hint!"},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_includes_if_match_and_order_hint(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task_bucket_board_format",
            {"task_id": "task-id-1", "order_hint": "new-hint!"},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-bucket-format-abc"'
        assert patch_call.kwargs["json"]["orderHint"] == "new-hint!"

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_task_bucket_board_format",
            {"task_id": "task-id-1", "order_hint": "hint"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET_FORMAT),
            Exception("Conflict"),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_bucket_board_format",
            {"task_id": "task-id-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message


# ---- Get Task Progress Board Format Tests ----


class TestGetTaskProgressBoardFormat:
    @pytest.mark.asyncio
    async def test_returns_board_format(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROGRESS_FORMAT)

        result = await microsoft_planner.execute_action(
            "get_task_progress_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.result.data["board_format"] == SAMPLE_PROGRESS_FORMAT
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROGRESS_FORMAT)

        await microsoft_planner.execute_action("get_task_progress_board_format", {"task_id": "task-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/tasks/task-id-1/progressTaskBoardFormat" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action(
            "get_task_progress_board_format", {"task_id": "task-id-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Update Task Progress Board Format Tests ----


class TestUpdateTaskProgressBoardFormat:
    @pytest.mark.asyncio
    async def test_updates_order_hint(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PROGRESS_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_progress_board_format",
            {"task_id": "task-id-1", "order_hint": "new-hint!"},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_includes_if_match_and_order_hint(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PROGRESS_FORMAT),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_task_progress_board_format",
            {"task_id": "task-id-1", "order_hint": "new-hint!"},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-progress-abc"'
        assert patch_call.kwargs["json"]["orderHint"] == "new-hint!"

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_task_progress_board_format",
            {"task_id": "task-id-1", "order_hint": "hint"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PROGRESS_FORMAT),
            Exception("Server error"),
        ]

        result = await microsoft_planner.execute_action(
            "update_task_progress_board_format",
            {"task_id": "task-id-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message
