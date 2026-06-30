import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.unit

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SAMPLE_PLAN = {
    "id": "plan-id-1",
    "title": "Marketing Plan Q1",
    "owner": "group-id-1",
    "@odata.etag": 'W/"etag-plan-123"',
    "createdDateTime": "2024-01-15T10:00:00Z",
}

SAMPLE_PLAN_DETAILS = {
    "id": "plan-id-1",
    "@odata.etag": 'W/"etag-details-456"',
    "categoryDescriptions": {"category1": "Bug", "category2": "Feature"},
    "sharedWith": {},
}


# ---- List Plans Tests ----


class TestListPlans:
    @pytest.mark.asyncio
    async def test_returns_plans(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_PLAN]})

        result = await microsoft_planner.execute_action("list_plans", {"group_id": "group-id-1"}, mock_context)

        assert result.result.data["plans"] == [SAMPLE_PLAN]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_group_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_plans", {"group_id": "group-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/groups/group-id-1/planner/plans" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_empty_plans(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("list_plans", {"group_id": "group-id-1"}, mock_context)

        assert result.result.data["plans"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Group not found")

        result = await microsoft_planner.execute_action("list_plans", {"group_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Group not found" in result.result.message


# ---- Get Plan Tests ----


class TestGetPlan:
    @pytest.mark.asyncio
    async def test_returns_plan(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PLAN)

        result = await microsoft_planner.execute_action("get_plan", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["plan"] == SAMPLE_PLAN
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_contains_plan_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PLAN)

        await microsoft_planner.execute_action("get_plan", {"plan_id": "plan-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/plans/plan-id-1" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await microsoft_planner.execute_action("get_plan", {"plan_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Create Plan Tests ----


class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_creates_plan_with_group_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PLAN)

        result = await microsoft_planner.execute_action(
            "create_plan", {"title": "New Plan", "group_id": "group-id-1"}, mock_context
        )

        assert result.result.data["plan"] == SAMPLE_PLAN
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_body_with_group_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PLAN)

        await microsoft_planner.execute_action(
            "create_plan", {"title": "New Plan", "group_id": "group-id-1"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "POST"
        body = call_args.kwargs["json"]
        assert body["title"] == "New Plan"
        assert body["container"]["containerId"] == "group-id-1"
        assert body["container"]["type"] == "group"

    @pytest.mark.asyncio
    async def test_creates_plan_with_container_object(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PLAN)
        container = {"containerId": "group-id-2", "type": "group"}

        await microsoft_planner.execute_action("create_plan", {"title": "Plan", "container": container}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["container"] == container

    @pytest.mark.asyncio
    async def test_missing_container_and_group_id_returns_action_error(self, mock_context):
        result = await microsoft_planner.execute_action("create_plan", {"title": "Orphan Plan"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "container" in result.result.message or "group_id" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Permission denied")

        result = await microsoft_planner.execute_action(
            "create_plan", {"title": "Plan", "group_id": "group-id-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Permission denied" in result.result.message


# ---- Update Plan Tests ----


class TestUpdatePlan:
    @pytest.mark.asyncio
    async def test_updates_plan_title(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),  # ETag fetch
            FetchResponse(status=204, headers={}, data=None),  # PATCH response
        ]

        result = await microsoft_planner.execute_action(
            "update_plan", {"plan_id": "plan-id-1", "title": "Updated Title"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["plan"] == {}  # 204 No Content

    @pytest.mark.asyncio
    async def test_patch_includes_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_plan", {"plan_id": "plan-id-1", "title": "New Title"}, mock_context
        )

        patch_call = mock_context.fetch.call_args_list[1]
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-plan-123"'
        assert patch_call.kwargs["method"] == "PATCH"
        assert patch_call.kwargs["json"]["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action(
            "update_plan", {"plan_id": "plan-id-1", "title": "Title"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),
            Exception("Server error"),
        ]

        result = await microsoft_planner.execute_action(
            "update_plan", {"plan_id": "plan-id-1", "title": "Title"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- Delete Plan Tests ----


class TestDeletePlan:
    @pytest.mark.asyncio
    async def test_deletes_plan(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),  # ETag fetch
            FetchResponse(status=204, headers={}, data=None),  # DELETE response
        ]

        result = await microsoft_planner.execute_action("delete_plan", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_delete_includes_if_match_header(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action("delete_plan", {"plan_id": "plan-id-1"}, mock_context)

        delete_call = mock_context.fetch.call_args_list[1]
        assert delete_call.kwargs["headers"]["If-Match"] == 'W/"etag-plan-123"'
        assert delete_call.kwargs["method"] == "DELETE"
        assert "/planner/plans/plan-id-1" in delete_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action("delete_plan", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN),
            Exception("Not found"),
        ]

        result = await microsoft_planner.execute_action("delete_plan", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Get Plan Details Tests ----


class TestGetPlanDetails:
    @pytest.mark.asyncio
    async def test_returns_plan_details(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PLAN_DETAILS)

        result = await microsoft_planner.execute_action("get_plan_details", {"plan_id": "plan-id-1"}, mock_context)

        assert result.result.data["plan_details"] == SAMPLE_PLAN_DETAILS
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PLAN_DETAILS)

        await microsoft_planner.execute_action("get_plan_details", {"plan_id": "plan-id-1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/planner/plans/plan-id-1/details" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Access denied")

        result = await microsoft_planner.execute_action("get_plan_details", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Access denied" in result.result.message


# ---- Update Plan Details Tests ----


class TestUpdatePlanDetails:
    @pytest.mark.asyncio
    async def test_updates_category_descriptions(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN_DETAILS),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await microsoft_planner.execute_action(
            "update_plan_details",
            {"plan_id": "plan-id-1", "category_descriptions": {"category1": "Bug Fix"}},
            mock_context,
        )

        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_patch_body_maps_category_descriptions(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN_DETAILS),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await microsoft_planner.execute_action(
            "update_plan_details",
            {"plan_id": "plan-id-1", "category_descriptions": {"category1": "Bug"}},
            mock_context,
        )

        patch_call = mock_context.fetch.call_args_list[1]
        body = patch_call.kwargs["json"]
        assert body["categoryDescriptions"] == {"category1": "Bug"}
        assert patch_call.kwargs["headers"]["If-Match"] == 'W/"etag-details-456"'

    @pytest.mark.asyncio
    async def test_missing_etag_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await microsoft_planner.execute_action("update_plan_details", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "ETag" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_PLAN_DETAILS),
            Exception("Conflict"),
        ]

        result = await microsoft_planner.execute_action("update_plan_details", {"plan_id": "plan-id-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Conflict" in result.result.message
