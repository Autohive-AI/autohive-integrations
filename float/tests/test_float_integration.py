"""
End-to-end integration tests for the Float integration.

These tests call the real Float API and require a valid API key
set in the FLOAT_API_KEY environment variable (via .env or export).

Run with:
    pytest float/tests/test_float_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib.util
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["float_mod"] = _mod

float_integration = _mod.float

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("FLOAT_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("FLOAT_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "credentials": {
            "api_key": API_KEY,
            "application_name": os.environ.get("FLOAT_APP_NAME", "Autohive Float Integration"),
            "contact_email": os.environ.get("FLOAT_CONTACT_EMAIL", ""),
        }
    }
    return ctx


# ---- Read-Only Tests ----


class TestListPeople:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_people", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)

    async def test_limit_respected(self, live_context):
        result = await float_integration.execute_action("list_people", {"per_page": 2}, live_context)
        data = result.result.data
        assert isinstance(data, list)
        assert len(data) <= 2


class TestGetPerson:
    async def test_returns_person(self, live_context):
        list_result = await float_integration.execute_action("list_people", {"per_page": 1}, live_context)
        people = list_result.result.data

        if not people:
            pytest.skip("No people in account to test with")

        person_id = people[0]["people_id"]
        result = await float_integration.execute_action("get_person", {"people_id": person_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert data["people_id"] == person_id


class TestListProjects:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_projects", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)

    async def test_limit_respected(self, live_context):
        result = await float_integration.execute_action("list_projects", {"per_page": 2}, live_context)
        data = result.result.data
        assert isinstance(data, list)
        assert len(data) <= 2


class TestGetProject:
    async def test_returns_project(self, live_context):
        list_result = await float_integration.execute_action("list_projects", {"per_page": 1}, live_context)
        projects = list_result.result.data

        if not projects:
            pytest.skip("No projects in account to test with")

        project_id = projects[0]["project_id"]
        result = await float_integration.execute_action("get_project", {"project_id": project_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert data["project_id"] == project_id


class TestListTasks:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_tasks", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetTask:
    async def test_returns_task(self, live_context):
        list_result = await float_integration.execute_action("list_tasks", {"per_page": 1}, live_context)
        tasks = list_result.result.data

        if not tasks:
            pytest.skip("No tasks in account to test with")

        task_id = tasks[0]["task_id"]
        result = await float_integration.execute_action("get_task", {"task_id": task_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "task_id" in data


class TestListClients:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_clients", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetClient:
    async def test_returns_client(self, live_context):
        list_result = await float_integration.execute_action("list_clients", {"per_page": 1}, live_context)
        clients = list_result.result.data

        if not clients:
            pytest.skip("No clients in account to test with")

        client_id = clients[0]["client_id"]
        result = await float_integration.execute_action("get_client", {"client_id": client_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "client_id" in data


class TestListTimeOff:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_time_off", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestListLoggedTime:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_logged_time", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestListDepartments:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_departments", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetDepartment:
    async def test_returns_department(self, live_context):
        list_result = await float_integration.execute_action("list_departments", {"per_page": 1}, live_context)
        departments = list_result.result.data

        if not departments:
            pytest.skip("No departments in account to test with")

        dept_id = departments[0]["department_id"]
        result = await float_integration.execute_action("get_department", {"department_id": dept_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "department_id" in data


class TestListRoles:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_roles", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetRole:
    async def test_returns_role(self, live_context):
        list_result = await float_integration.execute_action("list_roles", {"per_page": 1}, live_context)
        roles = list_result.result.data

        if not roles:
            pytest.skip("No roles in account to test with")

        role_id = roles[0]["role_id"]
        result = await float_integration.execute_action("get_role", {"role_id": role_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "role_id" in data


class TestListTimeOffTypes:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_time_off_types", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetTimeOffType:
    async def test_returns_time_off_type(self, live_context):
        list_result = await float_integration.execute_action("list_time_off_types", {"per_page": 1}, live_context)
        types = list_result.result.data

        if not types:
            pytest.skip("No time off types in account to test with")

        type_id = types[0]["timeoff_type_id"]
        result = await float_integration.execute_action("get_time_off_type", {"timeoff_type_id": type_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "timeoff_type_id" in data


class TestListAccounts:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_accounts", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetAccount:
    async def test_returns_account(self, live_context):
        list_result = await float_integration.execute_action("list_accounts", {"per_page": 1}, live_context)
        accounts = list_result.result.data

        if not accounts:
            pytest.skip("No accounts in account to test with")

        account_id = accounts[0]["account_id"]
        result = await float_integration.execute_action("get_account", {"account_id": account_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "account_id" in data


class TestListStatuses:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_statuses", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetStatus:
    async def test_returns_status(self, live_context):
        list_result = await float_integration.execute_action("list_statuses", {"per_page": 1}, live_context)
        statuses = list_result.result.data

        if not statuses:
            pytest.skip("No statuses in account to test with")

        status_id = statuses[0]["status_id"]
        result = await float_integration.execute_action("get_status", {"status_id": status_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "status_id" in data


class TestListPublicHolidays:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_public_holidays", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetPublicHoliday:
    async def test_returns_holiday(self, live_context):
        list_result = await float_integration.execute_action("list_public_holidays", {"per_page": 1}, live_context)
        holidays = list_result.result.data

        if not holidays:
            pytest.skip("No public holidays in account to test with")

        holiday_id = holidays[0].get("public_holiday_id") or holidays[0].get("id")
        result = await float_integration.execute_action(
            "get_public_holiday", {"public_holiday_id": holiday_id}, live_context
        )

        data = result.result.data
        assert isinstance(data, dict)


class TestListTeamHolidays:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_team_holidays", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetTeamHoliday:
    async def test_returns_holiday(self, live_context):
        list_result = await float_integration.execute_action("list_team_holidays", {"per_page": 1}, live_context)
        holidays = list_result.result.data

        if not holidays:
            pytest.skip("No team holidays in account to test with")

        holiday_id = holidays[0]["holiday_id"]
        result = await float_integration.execute_action("get_team_holiday", {"holiday_id": holiday_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "holiday_id" in data


class TestListProjectStages:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_project_stages", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetProjectStage:
    async def test_returns_stage(self, live_context):
        list_result = await float_integration.execute_action("list_project_stages", {"per_page": 1}, live_context)
        stages = list_result.result.data

        if not stages:
            pytest.skip("No project stages in account to test with")

        stage_id = stages[0].get("project_stage_id") or stages[0].get("id")
        result = await float_integration.execute_action(
            "get_project_stage", {"project_stage_id": stage_id}, live_context
        )

        data = result.result.data
        assert isinstance(data, dict)


class TestListProjectExpenses:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_project_expenses", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetProjectExpense:
    async def test_returns_expense(self, live_context):
        list_result = await float_integration.execute_action("list_project_expenses", {"per_page": 1}, live_context)
        expenses = list_result.result.data

        if not expenses:
            pytest.skip("No project expenses in account to test with")

        expense_id = expenses[0]["project_expense_id"]
        result = await float_integration.execute_action(
            "get_project_expense", {"project_expense_id": expense_id}, live_context
        )

        data = result.result.data
        assert isinstance(data, dict)
        assert "project_expense_id" in data


class TestListPhases:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_phases", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetPhase:
    async def test_returns_phase(self, live_context):
        list_result = await float_integration.execute_action("list_phases", {"per_page": 1}, live_context)
        phases = list_result.result.data

        if not phases:
            pytest.skip("No phases in account to test with")

        phase_id = phases[0]["phase_id"]
        result = await float_integration.execute_action("get_phase", {"phase_id": phase_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "phase_id" in data


class TestListProjectTasks:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_project_tasks", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetProjectTask:
    async def test_returns_task(self, live_context):
        list_result = await float_integration.execute_action("list_project_tasks", {"per_page": 1}, live_context)
        tasks = list_result.result.data

        if not tasks:
            pytest.skip("No project tasks in account to test with")

        task_id = tasks[0].get("project_task_id") or tasks[0].get("task_meta_id")
        result = await float_integration.execute_action("get_project_task", {"project_task_id": task_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)


class TestListMilestones:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_milestones", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)


class TestGetMilestone:
    async def test_returns_milestone(self, live_context):
        list_result = await float_integration.execute_action("list_milestones", {"per_page": 1}, live_context)
        milestones = list_result.result.data

        if not milestones:
            pytest.skip("No milestones in account to test with")

        milestone_id = milestones[0]["milestone_id"]
        result = await float_integration.execute_action("get_milestone", {"milestone_id": milestone_id}, live_context)

        data = result.result.data
        assert isinstance(data, dict)
        assert "milestone_id" in data


class TestReports:
    async def test_get_people_report(self, live_context):
        result = await float_integration.execute_action(
            "get_people_report", {"start_date": "2025-01-01", "end_date": "2025-01-31"}, live_context
        )
        data = result.result.data
        assert isinstance(data, dict)

    async def test_get_projects_report(self, live_context):
        result = await float_integration.execute_action(
            "get_projects_report", {"start_date": "2025-01-01", "end_date": "2025-01-31"}, live_context
        )
        data = result.result.data
        assert isinstance(data, dict)


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestClientLifecycle:
    """End-to-end workflow: create client → update → delete."""

    async def test_full_lifecycle(self, live_context):
        client_name = f"Integration Test Client {os.getpid()}"

        create_result = await float_integration.execute_action("create_client", {"name": client_name}, live_context)
        data = create_result.result.data
        assert isinstance(data, dict)
        client_id = data["client_id"]
        assert client_id is not None

        update_result = await float_integration.execute_action(
            "update_client", {"client_id": client_id, "name": f"{client_name} Updated"}, live_context
        )
        assert isinstance(update_result.result.data, dict)

        delete_result = await float_integration.execute_action("delete_client", {"client_id": client_id}, live_context)
        assert delete_result.result.data is not None


@pytest.mark.destructive
class TestPersonLifecycle:
    """End-to-end workflow: create person → update → delete."""

    async def test_full_lifecycle(self, live_context):
        person_name = f"Integration Test {os.getpid()}"

        create_result = await float_integration.execute_action("create_person", {"name": person_name}, live_context)
        data = create_result.result.data
        assert isinstance(data, dict)
        person_id = data["people_id"]
        assert person_id is not None

        update_result = await float_integration.execute_action(
            "update_person", {"people_id": person_id, "name": f"{person_name} Updated"}, live_context
        )
        assert isinstance(update_result.result.data, dict)

        delete_result = await float_integration.execute_action("delete_person", {"people_id": person_id}, live_context)
        assert delete_result.result.data is not None


@pytest.mark.destructive
class TestProjectLifecycle:
    """End-to-end workflow: create project → update → delete."""

    async def test_full_lifecycle(self, live_context):
        project_name = f"Integration Test Project {os.getpid()}"

        create_result = await float_integration.execute_action("create_project", {"name": project_name}, live_context)
        data = create_result.result.data
        assert isinstance(data, dict)
        project_id = data["project_id"]
        assert project_id is not None

        update_result = await float_integration.execute_action(
            "update_project", {"project_id": project_id, "name": f"{project_name} Updated"}, live_context
        )
        assert isinstance(update_result.result.data, dict)

        delete_result = await float_integration.execute_action(
            "delete_project", {"project_id": project_id}, live_context
        )
        assert delete_result.result.data is not None


@pytest.mark.destructive
class TestTaskLifecycle:
    """End-to-end workflow: create task → update → delete."""

    async def test_full_lifecycle(self, live_context):
        people_result = await float_integration.execute_action("list_people", {"per_page": 1}, live_context)
        people = people_result.result.data

        projects_result = await float_integration.execute_action("list_projects", {"per_page": 1}, live_context)
        projects = projects_result.result.data

        if not people or not projects:
            pytest.skip("Need at least one person and project to test task lifecycle")

        person_id = people[0]["people_id"]
        project_id = projects[0]["project_id"]

        create_result = await float_integration.execute_action(
            "create_task",
            {
                "people_id": person_id,
                "project_id": project_id,
                "start_date": "2025-06-01",
                "end_date": "2025-06-07",
                "hours": 8,
            },
            live_context,
        )
        data = create_result.result.data
        assert isinstance(data, dict)
        task_id = data["task_id"]
        assert task_id is not None

        update_result = await float_integration.execute_action(
            "update_task", {"task_id": task_id, "hours": 16}, live_context
        )
        assert isinstance(update_result.result.data, dict)

        delete_result = await float_integration.execute_action("delete_task", {"task_id": task_id}, live_context)
        assert delete_result.result.data is not None


@pytest.mark.destructive
class TestMergeProjectTasks:
    async def test_merge_project_tasks(self, live_context):
        list_result = await float_integration.execute_action("list_project_tasks", {"per_page": 3}, live_context)
        tasks = list_result.result.data

        if len(tasks) < 2:
            pytest.skip("Need at least 2 project tasks to test merge")

        source_ids = [tasks[0].get("project_task_id") or tasks[0].get("task_meta_id")]
        target_id = tasks[1].get("project_task_id") or tasks[1].get("task_meta_id")

        result = await float_integration.execute_action(
            "merge_project_tasks", {"source_ids": source_ids, "target_id": target_id}, live_context
        )
        assert result.result.data is not None
