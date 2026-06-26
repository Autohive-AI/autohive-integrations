import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.unit

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SAMPLE_USER = {
    "id": "user-id-123",
    "displayName": "John Doe",
    "mail": "john.doe@example.com",
    "userPrincipalName": "john.doe@example.com",
    "jobTitle": "Software Engineer",
}

SAMPLE_GROUP = {
    "id": "group-id-1",
    "displayName": "Marketing Team",
    "description": "Marketing group",
    "groupTypes": ["Unified"],
}

SAMPLE_TASK = {
    "id": "task-id-1",
    "title": "My Task",
    "planId": "plan-id-1",
    "bucketId": "bucket-id-1",
    "percentComplete": 0,
}

SAMPLE_PLAN = {
    "id": "plan-id-1",
    "title": "My Plan",
    "owner": "group-id-1",
}


# ---- Group Tests ----


class TestListGroups:
    @pytest.mark.asyncio
    async def test_returns_groups(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_GROUP]})

        result = await microsoft_planner.execute_action("list_groups", {}, mock_context)

        assert result.result.data["groups"] == [SAMPLE_GROUP]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_groups", {"limit": 50}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/me/memberOf/microsoft.graph.group" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"]["$top"] == 50
        assert "Unified" in call_args.kwargs["params"]["$filter"]

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_groups", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 100

    @pytest.mark.asyncio
    async def test_empty_groups(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("list_groups", {}, mock_context)

        assert result.result.data["groups"] == []
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await microsoft_planner.execute_action("list_groups", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- Get User By Email Tests ----


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_user_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_USER]})

        result = await microsoft_planner.execute_action(
            "get_user_by_email", {"email": "john.doe@example.com"}, mock_context
        )

        assert result.result.data["user_id"] == "user-id-123"
        assert result.result.data["display_name"] == "John Doe"
        assert result.result.data["email"] == "john.doe@example.com"
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_USER]})

        await microsoft_planner.execute_action("get_user_by_email", {"email": "john.doe@example.com"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert f"{GRAPH_BASE}/users" == call_args.args[0]
        assert "john.doe@example.com" in call_args.kwargs["params"]["$filter"]

    @pytest.mark.asyncio
    async def test_user_not_found_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action(
            "get_user_by_email", {"email": "nobody@example.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message

    @pytest.mark.asyncio
    async def test_upn_fallback_for_email(self, mock_context):
        user_with_upn = {**SAMPLE_USER, "mail": None, "userPrincipalName": "upn@example.com"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [user_with_upn]})

        result = await microsoft_planner.execute_action("get_user_by_email", {"email": "upn@example.com"}, mock_context)

        assert result.result.data["email"] == "upn@example.com"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await microsoft_planner.execute_action(
            "get_user_by_email", {"email": "test@example.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


# ---- Search Users Tests ----


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_returns_formatted_users(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_USER]})

        result = await microsoft_planner.execute_action("search_users", {"query": "John"}, mock_context)

        assert len(result.result.data["users"]) == 1
        user = result.result.data["users"][0]
        assert user["user_id"] == "user-id-123"
        assert user["display_name"] == "John Doe"
        assert user["email"] == "john.doe@example.com"
        assert user["job_title"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_request_has_search_and_consistency_header(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("search_users", {"query": "Doe", "limit": 5}, mock_context)

        call_args = mock_context.fetch.call_args
        assert f"{GRAPH_BASE}/users" == call_args.args[0]
        assert "$search" in call_args.kwargs["params"]
        assert call_args.kwargs["params"]["$top"] == 5
        assert call_args.kwargs["headers"]["ConsistencyLevel"] == "eventual"

    @pytest.mark.asyncio
    async def test_default_limit_10(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("search_users", {"query": "test"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 10

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await microsoft_planner.execute_action("search_users", {"query": "nobody"}, mock_context)

        assert result.result.data["users"] == []
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Service unavailable")

        result = await microsoft_planner.execute_action("search_users", {"query": "test"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Service unavailable" in result.result.message


# ---- Get Current User Tests ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user_info(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        result = await microsoft_planner.execute_action("get_current_user", {}, mock_context)

        assert result.result.data["user_id"] == "user-id-123"
        assert result.result.data["display_name"] == "John Doe"
        assert result.result.data["email"] == "john.doe@example.com"
        assert result.result.data["user"] == SAMPLE_USER
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_hits_me_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        await microsoft_planner.execute_action("get_current_user", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{GRAPH_BASE}/me"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_upn_fallback_for_email(self, mock_context):
        user = {**SAMPLE_USER, "mail": None, "userPrincipalName": "upn@tenant.com"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=user)

        result = await microsoft_planner.execute_action("get_current_user", {}, mock_context)

        assert result.result.data["email"] == "upn@tenant.com"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Token expired")

        result = await microsoft_planner.execute_action("get_current_user", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Token expired" in result.result.message


# ---- List User Tasks Tests ----


class TestListUserTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_TASK]})

        result = await microsoft_planner.execute_action("list_user_tasks", {}, mock_context)

        assert result.result.data["tasks"] == [SAMPLE_TASK]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_defaults_to_me_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_user_tasks", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/users/me/planner/tasks" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_uses_provided_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_user_tasks", {"user_id": "user-id-999"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/users/user-id-999/planner/tasks" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await microsoft_planner.execute_action("list_user_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- List User Plans Tests ----


class TestListUserPlans:
    @pytest.mark.asyncio
    async def test_returns_plans(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": [SAMPLE_PLAN]})

        result = await microsoft_planner.execute_action("list_user_plans", {}, mock_context)

        assert result.result.data["plans"] == [SAMPLE_PLAN]
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_defaults_to_me_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_user_plans", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/users/me/planner/plans" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_uses_provided_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await microsoft_planner.execute_action("list_user_plans", {"user_id": "user-abc"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/users/user-abc/planner/plans" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Rate limited")

        result = await microsoft_planner.execute_action("list_user_plans", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Rate limited" in result.result.message
