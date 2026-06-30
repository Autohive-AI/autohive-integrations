"""
End-to-end integration tests for the Projectworks integration.

These tests call the real Projectworks API and require valid API-account
credentials set in the environment (via .env or export):

    PROJECTWORKS_CONSUMER_KEY
    PROJECTWORKS_CONSUMER_SECRET

Optional pre-existing resource IDs (tests chain list -> get when unset):

    PROJECTWORKS_TEST_USER_ID
    PROJECTWORKS_TEST_PROJECT_ID
    PROJECTWORKS_TEST_CLIENT_ID

Run (read-only — safe default):
    pytest projectworks/tests/test_projectworks_integration.py -m "integration and not destructive"

Run destructive write tests (each self-cleans: create -> update -> delete):
    pytest projectworks/tests/test_projectworks_integration.py -m "integration and destructive"

Destructive coverage: timesheet lifecycle, client lifecycle (POST/PATCH/DELETE),
and a nested module + task lifecycle under an existing project.

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


class TestGetModule:
    async def test_get_module_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_modules", {"page_size": 1}, live_context))
        if not listed["modules"]:
            pytest.skip("No modules in account to test with")
        module_id = listed["modules"][0].get("ModuleID")
        data = ok_data(await projectworks.execute_action("get_module", {"module_id": module_id}, live_context))
        assert isinstance(data["module"], dict)


# ---- Tasks ----


class TestListTasks:
    async def test_returns_tasks(self, live_context):
        result = await projectworks.execute_action("list_tasks", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["tasks"], list)


class TestGetTask:
    async def test_get_task_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_tasks", {"page_size": 1}, live_context))
        if not listed["tasks"]:
            pytest.skip("No tasks in account to test with")
        task_id = listed["tasks"][0].get("TaskID")
        data = ok_data(await projectworks.execute_action("get_task", {"task_id": task_id}, live_context))
        assert isinstance(data["task"], dict)


# ---- Resources ----


class TestListResources:
    async def test_returns_resources(self, live_context):
        result = await projectworks.execute_action("list_resources", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["resources"], list)


class TestGetResource:
    async def test_get_resource_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_resources", {"page_size": 100}, live_context))
        # Capacity/penciled bookings have a null ResourceID and are not individually fetchable.
        with_id = [r for r in listed["resources"] if r.get("ResourceID") is not None]
        if not with_id:
            pytest.skip("No individually-addressable resourcing bookings (non-null ResourceID) to test with")
        resource_id = with_id[0]["ResourceID"]
        data = ok_data(await projectworks.execute_action("get_resource", {"resource_id": resource_id}, live_context))
        assert isinstance(data["resource"], dict)


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


class TestGetLeave:
    async def test_get_leave_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_leaves", {"page_size": 1}, live_context))
        if not listed["leaves"]:
            pytest.skip("No leave requests in account to test with")
        leave_id = listed["leaves"][0].get("LeaveID")
        data = ok_data(await projectworks.execute_action("get_leave", {"leave_id": leave_id}, live_context))
        assert isinstance(data["leave"], dict)


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


class TestGetInvoice:
    async def test_get_invoice_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_invoices", {"page_size": 1}, live_context))
        if not listed["invoices"]:
            pytest.skip("No invoices in account to test with")
        invoice_id = listed["invoices"][0].get("InvoiceID")
        data = ok_data(await projectworks.execute_action("get_invoice", {"invoice_id": invoice_id}, live_context))
        assert isinstance(data["invoice"], dict)


# ---- Expense Claims ----


class TestListExpenseClaims:
    async def test_returns_expense_claims(self, live_context):
        result = await projectworks.execute_action("list_expense_claims", {"page_size": 5}, live_context)
        data = ok_data(result)
        assert isinstance(data["expense_claims"], list)


class TestGetExpenseClaim:
    async def test_get_expense_claim_chained(self, live_context):
        listed = ok_data(await projectworks.execute_action("list_expense_claims", {"page_size": 1}, live_context))
        if not listed["expense_claims"]:
            pytest.skip("No expense claims in account to test with")
        expense_claim_id = listed["expense_claims"][0].get("ExpenseClaimID")
        data = ok_data(
            await projectworks.execute_action("get_expense_claim", {"expense_claim_id": expense_claim_id}, live_context)
        )
        assert isinstance(data["expense_claim"], dict)


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
        # Projectworks only accepts time from a user assigned to the task's timecode.
        # A task's Users array does not reliably reflect that assignment, so derive a
        # known-valid (user, task) pair from an existing timesheet entry instead.
        existing = ok_data(await projectworks.execute_action("list_timesheets", {"page_size": 1}, live_context))[
            "timesheets"
        ]
        if not existing:
            pytest.skip("No existing timesheet entry to derive a valid user/task assignment from")

        user_id = existing[0]["UserID"]
        task_id = existing[0]["TaskID"]

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


@pytest.mark.destructive
class TestClientLifecycle:
    """End-to-end entity write pattern: create (POST) -> update (PATCH) -> delete.

    Discovers a real account manager + office by chaining list actions, then
    creates a clearly-named throwaway client and removes it again, so the test
    is self-contained and leaves no residue on success.
    """

    async def test_full_lifecycle(self, live_context):
        users = ok_data(await projectworks.execute_action("list_users", {"page_size": 1}, live_context))["users"]
        offices = ok_data(await projectworks.execute_action("list_offices", {"page_size": 1}, live_context))["offices"]
        if not users or not offices:
            pytest.skip("Need at least one user and one office to run the client lifecycle")

        account_manager_id = users[0].get("UserID")
        office_id = offices[0].get("OfficeID")

        # Create
        created = ok_data(
            await projectworks.execute_action(
                "create_client",
                {
                    "client_name": f"ZZ Autohive Test Client {os.getpid()}",
                    "account_manager_id": account_manager_id,
                    "office_id": office_id,
                },
                live_context,
            )
        )["client"]
        client_id = created.get("ClientID")
        assert client_id is not None

        # Update (partial PATCH)
        new_name = f"ZZ Autohive Test Client {os.getpid()} (updated)"
        updated = ok_data(
            await projectworks.execute_action(
                "update_client", {"client_id": client_id, "client_name": new_name}, live_context
            )
        )["client"]
        assert updated.get("ClientName") == new_name

        # Delete (cleanup)
        deleted = ok_data(await projectworks.execute_action("delete_client", {"client_id": client_id}, live_context))
        assert deleted["deleted"] is True
        assert deleted["client_id"] == client_id


@pytest.mark.destructive
class TestModuleTaskLifecycle:
    """End-to-end nested write pattern under a real project: create a services
    module, create a task within it, update the task, then tear both down.

    Modules/tasks are created with a clear 'ZZ Autohive Test' prefix and removed
    in reverse order, so the test cleans up after itself on success.
    """

    async def test_full_lifecycle(self, live_context):
        projects = ok_data(await projectworks.execute_action("list_projects", {"page_size": 1}, live_context))[
            "projects"
        ]
        if not projects:
            pytest.skip("Need at least one project to run the module/task lifecycle")
        project_id = projects[0].get("ProjectID")

        # A task requires a taskTypeID; there is no list_task_types action, so
        # discover a valid type from an existing task.
        existing = ok_data(await projectworks.execute_action("list_tasks", {"page_size": 50}, live_context))["tasks"]
        task_type_ids = [t.get("TaskTypeID") for t in existing if t.get("TaskTypeID") is not None]
        if not task_type_ids:
            pytest.skip("No existing task with a TaskTypeID to derive a valid task type from")
        task_type_id = task_type_ids[0]

        # Create a services module (tasks/timecodes can only be added to services modules).
        module = ok_data(
            await projectworks.execute_action(
                "create_module",
                {
                    "project_id": project_id,
                    "module_name": f"ZZ Autohive Test Module {os.getpid()}",
                    "is_services": True,
                },
                live_context,
            )
        )["module"]
        module_id = module.get("ModuleID")
        assert module_id is not None

        task_id = None
        try:
            # Create a task within the module
            task = ok_data(
                await projectworks.execute_action(
                    "create_task",
                    {
                        "module_id": module_id,
                        "task_name": f"ZZ Autohive Test Task {os.getpid()}",
                        "task_type_id": task_type_id,
                    },
                    live_context,
                )
            )["task"]
            task_id = task.get("TaskID")
            assert task_id is not None

            # Update (partial PATCH)
            new_name = f"ZZ Autohive Test Task {os.getpid()} (updated)"
            updated = ok_data(
                await projectworks.execute_action(
                    "update_task", {"task_id": task_id, "task_name": new_name}, live_context
                )
            )["task"]
            assert updated.get("TaskName") == new_name
        finally:
            # Tear down in reverse order so the project is left clean even on failure.
            if task_id is not None:
                deleted_task = ok_data(
                    await projectworks.execute_action("delete_task", {"task_id": task_id}, live_context)
                )
                assert deleted_task["deleted"] is True
            deleted_module = ok_data(
                await projectworks.execute_action("delete_module", {"module_id": module_id}, live_context)
            )
            assert deleted_module["deleted"] is True
