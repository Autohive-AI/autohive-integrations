"""
End-to-end integration tests for the Microsoft Planner integration.

These tests call the real Microsoft Graph API and require a valid OAuth access token
set in the MICROSOFT_PLANNER_ACCESS_TOKEN environment variable (via .env or export).

Optional env vars for skipping chain lookups:
    MICROSOFT_PLANNER_TEST_GROUP_ID    — an existing group ID to use in list_plans / plan lifecycle
    MICROSOFT_PLANNER_TEST_PLAN_ID     — an existing plan ID to use in task/bucket tests
    MICROSOFT_PLANNER_TEST_BUCKET_ID   — an existing bucket ID to use in task tests
    MICROSOFT_PLANNER_TEST_TASK_ID     — an existing task ID to use in detail/update/board-format tests
    MICROSOFT_PLANNER_TEST_USER_EMAIL  — a known user email to use in get_user_by_email/search_users tests

Run read-only tests (safe — use this by default):
    pytest microsoft-planner/tests/test_microsoft_planner_integration.py -m "integration and not destructive"

Run destructive tests (creates/updates/deletes real data — use a test account):
    pytest microsoft-planner/tests/test_microsoft_planner_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from microsoft_planner import microsoft_planner

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("MICROSOFT_PLANNER_ACCESS_TOKEN", "")
TEST_GROUP_ID = os.environ.get("MICROSOFT_PLANNER_TEST_GROUP_ID", "")
TEST_PLAN_ID = os.environ.get("MICROSOFT_PLANNER_TEST_PLAN_ID", "")
TEST_BUCKET_ID = os.environ.get("MICROSOFT_PLANNER_TEST_BUCKET_ID", "")
TEST_TASK_ID = os.environ.get("MICROSOFT_PLANNER_TEST_TASK_ID", "")
TEST_USER_EMAIL = os.environ.get("MICROSOFT_PLANNER_TEST_USER_EMAIL", "")


def require_group_id():
    if not TEST_GROUP_ID:
        pytest.skip("MICROSOFT_PLANNER_TEST_GROUP_ID not set")


def require_plan_id():
    if not TEST_PLAN_ID:
        pytest.skip("MICROSOFT_PLANNER_TEST_PLAN_ID not set")


def require_bucket_id():
    if not TEST_BUCKET_ID:
        pytest.skip("MICROSOFT_PLANNER_TEST_BUCKET_ID not set")


def require_task_id():
    if not TEST_TASK_ID:
        pytest.skip("MICROSOFT_PLANNER_TEST_TASK_ID not set")


def require_user_email():
    if not TEST_USER_EMAIL:
        pytest.skip("MICROSOFT_PLANNER_TEST_USER_EMAIL not set")


@pytest.fixture
def live_context(env_credentials):
    token = env_credentials("MICROSOFT_PLANNER_ACCESS_TOKEN")
    if not token:
        pytest.skip("MICROSOFT_PLANNER_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                if resp.status == 204 or resp.content_length == 0:
                    return FetchResponse(status=resp.status, headers=dict(resp.headers), data=None)
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", str(data))
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": token},  # nosec B105
    }
    return ctx


# ---- Read-Only Tests ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_current_user(self, live_context):
        result = await microsoft_planner.execute_action("get_current_user", {}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "user_id" in data
        assert data["user_id"] is not None
        assert "display_name" in data
        assert "result" in data
        assert data["result"] is True

    @pytest.mark.asyncio
    async def test_user_object_has_expected_structure(self, live_context):
        result = await microsoft_planner.execute_action("get_current_user", {}, live_context)

        user = result.result.data["user"]
        assert "id" in user
        assert "displayName" in user


class TestListGroups:
    @pytest.mark.asyncio
    async def test_returns_groups_list(self, live_context):
        result = await microsoft_planner.execute_action("list_groups", {"limit": 5}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "groups" in data
        assert isinstance(data["groups"], list)

    @pytest.mark.asyncio
    async def test_limit_respected(self, live_context):
        result = await microsoft_planner.execute_action("list_groups", {"limit": 2}, live_context)

        assert result.type == ResultType.SUCCESS
        assert len(result.result.data["groups"]) <= 2


class TestListUserPlans:
    @pytest.mark.asyncio
    async def test_returns_plans_for_current_user(self, live_context):
        result = await microsoft_planner.execute_action("list_user_plans", {}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "plans" in data
        assert isinstance(data["plans"], list)


class TestListUserTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_for_current_user(self, live_context):
        result = await microsoft_planner.execute_action("list_user_tasks", {}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)


class TestListPlans:
    @pytest.mark.asyncio
    async def test_returns_plans_for_group(self, live_context):
        require_group_id()

        result = await microsoft_planner.execute_action("list_plans", {"group_id": TEST_GROUP_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        assert "plans" in result.result.data
        assert isinstance(result.result.data["plans"], list)


class TestGetPlan:
    @pytest.mark.asyncio
    async def test_returns_plan(self, live_context):
        require_plan_id()

        result = await microsoft_planner.execute_action("get_plan", {"plan_id": TEST_PLAN_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "plan" in data
        assert data["plan"]["id"] == TEST_PLAN_ID

    @pytest.mark.asyncio
    async def test_plan_has_expected_fields(self, live_context):
        require_plan_id()

        result = await microsoft_planner.execute_action("get_plan", {"plan_id": TEST_PLAN_ID}, live_context)

        plan = result.result.data["plan"]
        assert "id" in plan
        assert "title" in plan


class TestGetPlanDetails:
    @pytest.mark.asyncio
    async def test_returns_plan_details(self, live_context):
        require_plan_id()

        result = await microsoft_planner.execute_action("get_plan_details", {"plan_id": TEST_PLAN_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "plan_details" in data
        assert data["plan_details"] is not None


class TestListBuckets:
    @pytest.mark.asyncio
    async def test_returns_buckets_for_plan(self, live_context):
        require_plan_id()

        result = await microsoft_planner.execute_action("list_buckets", {"plan_id": TEST_PLAN_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "buckets" in data
        assert isinstance(data["buckets"], list)


class TestGetBucket:
    @pytest.mark.asyncio
    async def test_returns_bucket(self, live_context):
        require_bucket_id()

        result = await microsoft_planner.execute_action("get_bucket", {"bucket_id": TEST_BUCKET_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "bucket" in data
        assert data["bucket"]["id"] == TEST_BUCKET_ID


class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_for_plan(self, live_context):
        require_plan_id()

        result = await microsoft_planner.execute_action("list_tasks", {"plan_id": TEST_PLAN_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_task(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action("get_task", {"task_id": TEST_TASK_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "task" in data
        assert data["task"]["id"] == TEST_TASK_ID

    @pytest.mark.asyncio
    async def test_task_has_expected_fields(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action("get_task", {"task_id": TEST_TASK_ID}, live_context)

        task = result.result.data["task"]
        assert "id" in task
        assert "title" in task
        assert "planId" in task
        assert "bucketId" in task


class TestGetTaskDetails:
    @pytest.mark.asyncio
    async def test_returns_task_details(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action("get_task_details", {"task_id": TEST_TASK_ID}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "task_details" in data
        assert data["task_details"] is not None


class TestGetTaskBoardFormats:
    @pytest.mark.asyncio
    async def test_get_assigned_to_board_format(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action(
            "get_task_assigned_to_board_format", {"task_id": TEST_TASK_ID}, live_context
        )

        assert result.type == ResultType.SUCCESS
        assert "board_format" in result.result.data

    @pytest.mark.asyncio
    async def test_get_bucket_board_format(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action(
            "get_task_bucket_board_format", {"task_id": TEST_TASK_ID}, live_context
        )

        assert result.type == ResultType.SUCCESS
        assert "board_format" in result.result.data

    @pytest.mark.asyncio
    async def test_get_progress_board_format(self, live_context):
        require_task_id()

        result = await microsoft_planner.execute_action(
            "get_task_progress_board_format", {"task_id": TEST_TASK_ID}, live_context
        )

        assert result.type == ResultType.SUCCESS
        assert "board_format" in result.result.data


class TestListBucketTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_for_bucket(self, live_context):
        require_bucket_id()

        result = await microsoft_planner.execute_action(
            "list_bucket_tasks", {"bucket_id": TEST_BUCKET_ID}, live_context
        )

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)


class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_returns_user(self, live_context):
        require_user_email()

        result = await microsoft_planner.execute_action("get_user_by_email", {"email": TEST_USER_EMAIL}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "user_id" in data
        assert data["user_id"] is not None
        assert data["result"] is True

    @pytest.mark.asyncio
    async def test_returned_email_matches_query(self, live_context):
        require_user_email()

        result = await microsoft_planner.execute_action("get_user_by_email", {"email": TEST_USER_EMAIL}, live_context)

        assert result.type == ResultType.SUCCESS
        assert result.result.data["email"].lower() == TEST_USER_EMAIL.lower()


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_returns_users_for_query(self, live_context):
        require_user_email()

        query = TEST_USER_EMAIL.split("@")[0]
        result = await microsoft_planner.execute_action("search_users", {"query": query, "limit": 5}, live_context)

        assert result.type == ResultType.SUCCESS
        data = result.result.data
        assert "users" in data
        assert isinstance(data["users"], list)

    @pytest.mark.asyncio
    async def test_search_results_have_expected_fields(self, live_context):
        require_user_email()

        query = TEST_USER_EMAIL.split("@")[0]
        result = await microsoft_planner.execute_action("search_users", {"query": query, "limit": 3}, live_context)

        assert result.type == ResultType.SUCCESS
        if result.result.data["users"]:
            user = result.result.data["users"][0]
            assert "user_id" in user
            assert "display_name" in user


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestBucketLifecycle:
    """End-to-end workflow: create bucket → update → delete."""

    @pytest.mark.asyncio
    async def test_full_bucket_lifecycle(self, live_context):
        require_plan_id()

        # Step 1: Create
        create_result = await microsoft_planner.execute_action(
            "create_bucket",
            {"name": f"Integration Test Bucket {os.getpid()}", "plan_id": TEST_PLAN_ID},
            live_context,
        )
        assert create_result.type == ResultType.SUCCESS
        bucket_id = create_result.result.data["bucket"]["id"]
        assert bucket_id is not None

        # Step 2: Update
        update_result = await microsoft_planner.execute_action(
            "update_bucket",
            {"bucket_id": bucket_id, "name": "Updated Integration Test Bucket"},
            live_context,
        )
        assert update_result.type == ResultType.SUCCESS

        # Step 3: Delete (cleanup)
        delete_result = await microsoft_planner.execute_action("delete_bucket", {"bucket_id": bucket_id}, live_context)
        assert delete_result.type == ResultType.SUCCESS
        assert delete_result.result.data["result"] is True


@pytest.mark.destructive
class TestTaskLifecycle:
    """End-to-end workflow: create task → update → get details → delete."""

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, live_context):
        require_plan_id()
        require_bucket_id()

        # Step 1: Create task
        create_result = await microsoft_planner.execute_action(
            "create_task",
            {
                "plan_id": TEST_PLAN_ID,
                "bucket_id": TEST_BUCKET_ID,
                "title": f"Integration Test Task {os.getpid()}",
            },
            live_context,
        )
        assert create_result.type == ResultType.SUCCESS
        task_id = create_result.result.data["task"]["id"]
        assert task_id is not None

        # Step 2: Update task
        update_result = await microsoft_planner.execute_action(
            "update_task",
            {"task_id": task_id, "percent_complete": 50},
            live_context,
        )
        assert update_result.type == ResultType.SUCCESS

        # Step 3: Get task details
        details_result = await microsoft_planner.execute_action("get_task_details", {"task_id": task_id}, live_context)
        assert details_result.type == ResultType.SUCCESS
        assert "task_details" in details_result.result.data

        # Step 4: Update task details (description)
        update_details_result = await microsoft_planner.execute_action(
            "update_task_details",
            {"task_id": task_id, "description": f"Integration test description {os.getpid()}"},
            live_context,
        )
        assert update_details_result.type == ResultType.SUCCESS

        # Step 5: Delete (cleanup)
        delete_result = await microsoft_planner.execute_action("delete_task", {"task_id": task_id}, live_context)
        assert delete_result.type == ResultType.SUCCESS
        assert delete_result.result.data["result"] is True


@pytest.mark.destructive
class TestChecklistLifecycle:
    """Create task, add checklist item, update it, remove it, delete task."""

    @pytest.mark.asyncio
    async def test_checklist_lifecycle(self, live_context):
        require_plan_id()
        require_bucket_id()

        # Step 1: Create task
        create_result = await microsoft_planner.execute_action(
            "create_task",
            {
                "plan_id": TEST_PLAN_ID,
                "bucket_id": TEST_BUCKET_ID,
                "title": f"Checklist Test Task {os.getpid()}",
            },
            live_context,
        )
        assert create_result.type == ResultType.SUCCESS
        task_id = create_result.result.data["task"]["id"]

        # Step 2: Add checklist item
        add_result = await microsoft_planner.execute_action(
            "add_checklist_item",
            {"task_id": task_id, "title": "Test checklist step"},
            live_context,
        )
        assert add_result.type == ResultType.SUCCESS
        item_id = add_result.result.data["item_id"]
        assert item_id is not None

        # Step 3: Update checklist item
        update_result = await microsoft_planner.execute_action(
            "update_checklist_item",
            {"task_id": task_id, "item_id": item_id, "is_checked": True},
            live_context,
        )
        assert update_result.type == ResultType.SUCCESS

        # Step 4: Remove checklist item
        remove_result = await microsoft_planner.execute_action(
            "remove_checklist_item",
            {"task_id": task_id, "item_id": item_id},
            live_context,
        )
        assert remove_result.type == ResultType.SUCCESS

        # Step 5: Cleanup - delete task
        delete_result = await microsoft_planner.execute_action("delete_task", {"task_id": task_id}, live_context)
        assert delete_result.type == ResultType.SUCCESS


@pytest.mark.destructive
class TestPlanLifecycle:
    """End-to-end workflow: create plan → update title → update details → delete."""

    @pytest.mark.asyncio
    async def test_full_plan_lifecycle(self, live_context):
        require_group_id()

        # Step 1: Create plan
        create_result = await microsoft_planner.execute_action(
            "create_plan",
            {"title": f"Integration Test Plan {os.getpid()}", "group_id": TEST_GROUP_ID},
            live_context,
        )
        assert create_result.type == ResultType.SUCCESS
        plan_id = create_result.result.data["plan"]["id"]
        assert plan_id is not None

        # Step 2: Update plan title
        update_result = await microsoft_planner.execute_action(
            "update_plan",
            {"plan_id": plan_id, "title": "Updated Integration Test Plan"},
            live_context,
        )
        assert update_result.type == ResultType.SUCCESS

        # Step 3: Update plan details (category descriptions)
        update_details_result = await microsoft_planner.execute_action(
            "update_plan_details",
            {"plan_id": plan_id, "category_descriptions": {"category1": "Integration Test"}},
            live_context,
        )
        assert update_details_result.type == ResultType.SUCCESS

        # Step 4: Delete (cleanup)
        delete_result = await microsoft_planner.execute_action("delete_plan", {"plan_id": plan_id}, live_context)
        assert delete_result.type == ResultType.SUCCESS
        assert delete_result.result.data["result"] is True


@pytest.mark.destructive
class TestBoardFormatLifecycle:
    """Reads each board format ETag then patches it back with the same hint (idempotent)."""

    @pytest.mark.asyncio
    async def test_update_assigned_to_board_format(self, live_context):
        require_task_id()

        get_result = await microsoft_planner.execute_action(
            "get_task_assigned_to_board_format", {"task_id": TEST_TASK_ID}, live_context
        )
        assert get_result.type == ResultType.SUCCESS
        current_hint = get_result.result.data["board_format"].get("unassignedOrderHint", "8585!")

        result = await microsoft_planner.execute_action(
            "update_task_assigned_to_board_format",
            {"task_id": TEST_TASK_ID, "unassigned_order_hint": current_hint},
            live_context,
        )
        assert result.type == ResultType.SUCCESS
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_update_bucket_board_format(self, live_context):
        require_task_id()

        get_result = await microsoft_planner.execute_action(
            "get_task_bucket_board_format", {"task_id": TEST_TASK_ID}, live_context
        )
        assert get_result.type == ResultType.SUCCESS
        current_hint = get_result.result.data["board_format"].get("orderHint", "8585!")

        result = await microsoft_planner.execute_action(
            "update_task_bucket_board_format",
            {"task_id": TEST_TASK_ID, "order_hint": current_hint},
            live_context,
        )
        assert result.type == ResultType.SUCCESS
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_update_progress_board_format(self, live_context):
        require_task_id()

        get_result = await microsoft_planner.execute_action(
            "get_task_progress_board_format", {"task_id": TEST_TASK_ID}, live_context
        )
        assert get_result.type == ResultType.SUCCESS
        current_hint = get_result.result.data["board_format"].get("orderHint", "8585!")

        result = await microsoft_planner.execute_action(
            "update_task_progress_board_format",
            {"task_id": TEST_TASK_ID, "order_hint": current_hint},
            live_context,
        )
        assert result.type == ResultType.SUCCESS
        assert result.result.data["result"] is True
