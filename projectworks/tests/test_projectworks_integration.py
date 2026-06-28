"""
End-to-end integration tests for the ProjectWorks integration.

These tests call the real ProjectWorks API and require valid API-account
credentials set in the environment (via .env or export):

    PROJECTWORKS_CONSUMER_KEY
    PROJECTWORKS_CONSUMER_SECRET

Optional pre-existing resource IDs (tests chain list -> get when unset):

    PROJECTWORKS_TEST_USER_ID
    PROJECTWORKS_TEST_PROJECT_ID
    PROJECTWORKS_TEST_CLIENT_ID

Run (read-only — safe default):
    pytest projectworks/tests/test_projectworks_integration.py -m "integration and not destructive"

Run destructive write tests (creates/updates/deletes a real timesheet entry):
    pytest projectworks/tests/test_projectworks_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType
from unittest.mock import AsyncMock, MagicMock

from projectworks.projectworks import projectworks

pytestmark = pytest.mark.integration

TEST_USER_ID = os.environ.get("PROJECTWORKS_TEST_USER_ID", "")
TEST_PROJECT_ID = os.environ.get("PROJECTWORKS_TEST_PROJECT_ID", "")
TEST_CLIENT_ID = os.environ.get("PROJECTWORKS_TEST_CLIENT_ID", "")


@pytest.fixture
def live_context(env_credentials):
    consumer_key = env_credentials("PROJECTWORKS_CONSUMER_KEY")
    consumer_secret = env_credentials("PROJECTWORKS_CONSUMER_SECRET")
    if not consumer_key or not consumer_secret:
        pytest.skip("PROJECTWORKS_CONSUMER_KEY / PROJECTWORKS_CONSUMER_SECRET not set")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    # Custom auth — the action handler builds the Basic auth header from this.
    ctx.auth = {"consumer_key": consumer_key, "consumer_secret": consumer_secret}
    return ctx


def ok_data(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result)
    return result.result.data


# ---- Users ----


class TestListUsers:
    async def test_returns_users(self, live_context):
        result = await projectworks.execute_action("list_users", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["users"], list)
        assert len(data["users"]) <= 5


class TestGetUser:
    async def test_get_user_chained(self, live_context):
        user_id = TEST_USER_ID
        if not user_id:
            listed = ok_data(await projectworks.execute_action("list_users", {"page_size": 1}, live_context))
            if not listed["users"]:
                pytest.skip("No users in account to test with")
            user_id = listed["users"][0].get("UserID")

        result = await projectworks.execute_action("get_user", {"user_id": user_id}, live_context)
        data = ok_data(result)
        assert isinstance(data["user"], dict)


class TestListRoles:
    async def test_returns_roles(self, live_context):
        result = await projectworks.execute_action("list_roles", {}, live_context)
        data = ok_data(result)
        assert isinstance(data["roles"], list)


# ---- Clients ----


class TestListClients:
    async def test_returns_clients(self, live_context):
        result = await projectworks.execute_action("list_clients", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["clients"], list)


class TestGetClient:
    async def test_get_client_chained(self, live_context):
        client_id = TEST_CLIENT_ID
        if not client_id:
            listed = ok_data(await projectworks.execute_action("list_clients", {"page_size": 1}, live_context))
            if not listed["clients"]:
                pytest.skip("No clients in account to test with")
            client_id = listed["clients"][0].get("ClientID")

        result = await projectworks.execute_action("get_client", {"client_id": client_id}, live_context)
        data = ok_data(result)
        assert isinstance(data["client"], dict)


# ---- Projects ----


class TestListProjects:
    async def test_returns_projects(self, live_context):
        result = await projectworks.execute_action("list_projects", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["projects"], list)


class TestGetProject:
    async def test_get_project_chained(self, live_context):
        project_id = TEST_PROJECT_ID
        if not project_id:
            listed = ok_data(await projectworks.execute_action("list_projects", {"page_size": 1}, live_context))
            if not listed["projects"]:
                pytest.skip("No projects in account to test with")
            project_id = listed["projects"][0].get("ProjectID")

        result = await projectworks.execute_action("get_project", {"project_id": project_id}, live_context)
        data = ok_data(result)
        assert isinstance(data["project"], dict)


# ---- Modules ----


class TestListModules:
    async def test_returns_modules(self, live_context):
        result = await projectworks.execute_action("list_modules", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["modules"], list)


# ---- Tasks ----


class TestListTasks:
    async def test_returns_tasks(self, live_context):
        result = await projectworks.execute_action("list_tasks", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["tasks"], list)


# ---- Resources ----


class TestListResources:
    async def test_returns_resources(self, live_context):
        result = await projectworks.execute_action("list_resources", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["resources"], list)


# ---- Timesheets ----


class TestListTimesheets:
    async def test_returns_timesheets(self, live_context):
        result = await projectworks.execute_action("list_timesheets", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["timesheets"], list)


# ---- Leave ----


class TestListLeaves:
    async def test_returns_leaves(self, live_context):
        result = await projectworks.execute_action("list_leaves", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["leaves"], list)


class TestListLeaveTypes:
    async def test_returns_leave_types(self, live_context):
        result = await projectworks.execute_action("list_leave_types", {}, live_context)
        data = ok_data(result)
        assert isinstance(data["leave_types"], list)


# ---- Invoices ----


class TestListInvoices:
    async def test_returns_invoices(self, live_context):
        result = await projectworks.execute_action("list_invoices", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["invoices"], list)


# ---- Expense Claims ----


class TestListExpenseClaims:
    async def test_returns_expense_claims(self, live_context):
        result = await projectworks.execute_action("list_expense_claims", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["expense_claims"], list)


# ---- Offices ----


class TestListOffices:
    async def test_returns_offices(self, live_context):
        result = await projectworks.execute_action("list_offices", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["offices"], list)


# ---- Destructive Tests (Write Operations) ----
# These create, update, and delete real data on the connected account.
# Only run deliberately with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestTimesheetLifecycle:
    """End-to-end timesheet workflow: create -> update -> delete.

    Discovers a real user + task by chaining list actions, so it is
    self-contained and cleans up the entry it creates.
    """

    async def test_full_lifecycle(self, live_context):
        users = ok_data(await projectworks.execute_action("list_users", {"page_size": 1}, live_context))["users"]
        # list_tasks has no server-side IsOnTimesheet filter, so page through and
        # pick a timesheet-eligible task client-side.
        tasks = ok_data(await projectworks.execute_action("list_tasks", {"page_size": 100}, live_context))["tasks"]
        timesheet_tasks = [t for t in tasks if t.get("IsOnTimesheet")]
        if not users or not timesheet_tasks:
            pytest.skip("Need at least one user and one timesheet-eligible task to run the lifecycle")

        user_id = users[0].get("UserID")
        task_id = timesheet_tasks[0].get("TaskID")

        # Create
        created = ok_data(
            await projectworks.execute_action(
                "create_timesheet",
                {
                    "user_id": user_id,
                    "task_id": task_id,
                    "date": "2026-06-01",
                    "minutes": 60,
                    "comment": f"Autohive integration test {os.getpid()}",
                },
                live_context,
            )
        )
        entry = created["timesheet"]
        entry_id = (entry.get("ID") or entry.get("id")) if isinstance(entry, dict) else None
        assert entry_id is not None

        # Update
        updated = ok_data(
            await projectworks.execute_action(
                "update_timesheet", {"timesheet_id": entry_id, "minutes": 90}, live_context
            )
        )
        assert "timesheet" in updated

        # Delete (cleanup)
        deleted = ok_data(
            await projectworks.execute_action("delete_timesheet", {"timesheet_id": entry_id}, live_context)
        )
        assert deleted["deleted"] is True
        assert deleted["timesheet_id"] == entry_id
