import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.unit

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SAMPLE_BUCKET = {
    "id": "bucket-id-1",
    "name": "To Do",
    "planId": "plan-id-1",
    "orderHint": "8585269235419339378",
    "@odata.etag": 'W/"etag-bucket-abc"',
}

SAMPLE_TASK = {
    "id": "task-id-1",
    "title": "Write tests",
    "planId": "plan-id-1",
    "bucketId": "bucket-id-1",
}


# ---- List Buckets Tests ----


class TestListBuckets:
    @pytest.mark.asyncio
    async def test_returns_buckets(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_BUCKET]})

        result = await microsoft_planner.execute_action("list_buckets", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["buckets"] == [SAMPLE_BUCKET]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_includes_planid_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_buckets", {"plan_id": "plan-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/buckets" in call_args.args[0]
        assert "plan-id-1" in call_args.kwargs["params"]["$filter"]

    @pytest.mark.asyncio
    async def test_empty_buckets(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("list_buckets", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["buckets"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action("list_buckets", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Get Bucket Tests ----


class TestGetBucket:
    @pytest.mark.asyncio
    async def test_returns_bucket(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET)

        result = await microsoft_planner.execute_action("get_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.result.data["bucket"] == SAMPLE_BUCKET
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_bucket_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET)

        await microsoft_planner.execute_action("get_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/buckets/bucket-id-1" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bucket not found")

        result = await microsoft_planner.execute_action("get_bucket", {"bucket_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Bucket not found" in result.result.message


# ---- Create Bucket Tests ----


class TestCreateBucket:
    @pytest.mark.asyncio
    async def test_creates_bucket(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_BUCKET)

        result = await microsoft_planner.execute_action(
            "create_bucket", {"name": "To Do", "plan_id": "plan-id-1"}, mock_context
        )

        assert result.result.data["bucket"] == SAMPLE_BUCKET
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_body_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_BUCKET)

        await microsoft_planner.execute_action(
            "create_bucket", {"name": "Backlog", "plan_id": "plan-id-1"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "POST"
        body = call_args.kwargs["json"]
        assert body["name"] == "Backlog"
        assert body["planId"] == "plan-id-1"

    @pytest.mark.asyncio
    async def test_default_order_hint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_BUCKET)

        await microsoft_planner.execute_action("create_bucket", {"name": "Done", "plan_id": "plan-id-1"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["orderHint"] == " !"

    @pytest.mark.asyncio
    async def test_custom_order_hint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_BUCKET)

        await microsoft_planner.execute_action(
            "create_bucket", {"name": "Done", "plan_id": "plan-id-1", "order_hint": "8585!"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["orderHint"] == "8585!"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Conflict")

        result = await microsoft_planner.execute_action(
            "create_bucket", {"name": "Bucket", "plan_id": "plan-id-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message


# ---- Update Bucket Tests ----


class TestUpdateBucket:
    @pytest.mark.asyncio
    async def test_updates_bucket_name(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),  # ETag fetch
            FetchResponse(status=204, headers={}, data=None),  # PATCH response
        ]

        result = await microsoft_planner.execute_action(
            "update_bucket", {"bucket_id": "bucket-id-1", "name": "Backlog"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["bucket"] == {}

    @pytest.mark.asyncio
    async def test_patch_includes_if_match_and_name(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_bucket", {"bucket_id": "bucket-id-1", "name": "New Name"}, mock_context
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-bucket-abc"'
        assert patch_call.kwargs["method"] == "PATCH"
        assert patch_call.kwargs["json"]["name"] == "New Name"
        assert "/planner/buckets/bucket-id-1" in patch_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_bucket", {"bucket_id": "bucket-id-1", "name": "New"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),
            Exception("Conflict"),
        ]

        result = await microsoft_planner.execute_action(
            "update_bucket", {"bucket_id": "bucket-id-1", "name": "New"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message


# ---- Delete Bucket Tests ----


class TestDeleteBucket:
    @pytest.mark.asyncio
    async def test_deletes_bucket(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action("delete_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_delete_includes_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action("delete_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        delete_call = mock_context.fetch.call_args_list[1]
        assert delete_call.kwargs["headers"]["If-Match"] == 'W/"etag-bucket-abc"'
        assert delete_call.kwargs["method"] == "DELETE"
        assert "/planner/buckets/bucket-id-1" in delete_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action("delete_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_BUCKET),
            Exception("Not found"),
        ]

        result = await microsoft_planner.execute_action("delete_bucket", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- List Bucket Tasks Tests ----


class TestListBucketTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_TASK]})

        result = await microsoft_planner.execute_action("list_bucket_tasks", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.result.data["tasks"] == [SAMPLE_TASK]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_bucket_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_bucket_tasks", {"bucket_id": "bucket-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/buckets/bucket-id-1/tasks" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_empty_tasks(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("list_bucket_tasks", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.result.data["tasks"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await microsoft_planner.execute_action("list_bucket_tasks", {"bucket_id": "bucket-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message
