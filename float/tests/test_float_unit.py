import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

float_integration = _mod.float

pytestmark = pytest.mark.unit

# ---- Sample data ----

# list_people output_schema has active: integer; get_person output_schema has active: boolean
SAMPLE_PERSON_LIST_ITEM = {
    "people_id": 1,
    "name": "Alice Smith",
    "email": "alice@example.com",
    "active": 1,
}

SAMPLE_PERSON = {
    "people_id": 1,
    "name": "Alice Smith",
    "email": "alice@example.com",
    "active": True,
    "job_title": "Engineer",
    "department_id": None,
    "role_id": None,
}

# list_projects output_schema has active: integer; get_project has active: boolean
SAMPLE_PROJECT_LIST_ITEM = {
    "project_id": 10,
    "name": "Website Redesign",
    "client_id": 5,
    "active": 1,
}

SAMPLE_PROJECT = {
    "project_id": 10,
    "name": "Website Redesign",
    "client_id": 5,
    "active": True,
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
}

SAMPLE_TASK = {
    "task_id": 100,
    "people_id": 1,
    "project_id": 10,
    "start_date": "2025-01-01",
    "end_date": "2025-01-05",
    "hours": 8.0,
}

SAMPLE_TIME_OFF = {
    "timeoff_id": 200,
    "people_id": 1,
    "timeoff_type_id": 3,
    "start_date": "2025-02-01",
    "end_date": "2025-02-03",
    "hours": 8.0,
}

SAMPLE_LOGGED_TIME = {
    "logged_time_id": "abc123",
    "people_id": 1,
    "project_id": 10,
    "date": "2025-01-10",
    "hours": 7.5,
}

SAMPLE_CLIENT_LIST_ITEM = {
    "client_id": 5,
    "name": "Acme Corp",
    "active": 1,
}

SAMPLE_CLIENT = {
    "client_id": 5,
    "name": "Acme Corp",
    "active": True,
}


# ---- Fixture ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "api_key": "test_api_key",  # nosec B105
            "application_name": "Test App",
            "contact_email": "test@example.com",
        }
    }
    return ctx


# ---- People ----


class TestListPeople:
    @pytest.mark.asyncio
    async def test_list_people_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PERSON_LIST_ITEM])

        result = await float_integration.execute_action("list_people", {}, mock_context)

        assert result.result.data == [SAMPLE_PERSON_LIST_ITEM]

    @pytest.mark.asyncio
    async def test_list_people_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "https://api.float.com/v3/people" in call_args.kwargs["url"]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_list_people_with_active_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {"active": True}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["active"] == 1

    @pytest.mark.asyncio
    async def test_list_people_active_false_sends_zero(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {"active": False}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["active"] == 0

    @pytest.mark.asyncio
    async def test_list_people_exception_propagates(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Failed to list people"):
            await float_integration.execute_action("list_people", {}, mock_context)


class TestGetPerson:
    @pytest.mark.asyncio
    async def test_get_person_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        result = await float_integration.execute_action("get_person", {"people_id": 1}, mock_context)

        assert result.result.data["people_id"] == 1
        assert result.result.data["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_get_person_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action("get_person", {"people_id": 42}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/people/42"

    @pytest.mark.asyncio
    async def test_get_person_exception_propagates(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        with pytest.raises(Exception, match="Failed to get person 1"):
            await float_integration.execute_action("get_person", {"people_id": 1}, mock_context)


class TestCreatePerson:
    @pytest.mark.asyncio
    async def test_create_person_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PERSON)

        result = await float_integration.execute_action("create_person", {"name": "Alice Smith"}, mock_context)

        assert result.result.data["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_create_person_request_method_and_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action(
            "create_person",
            {"name": "Bob Jones", "email": "bob@example.com"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["url"] == "https://api.float.com/v3/people"
        assert call_args.kwargs["json"]["name"] == "Bob Jones"
        assert call_args.kwargs["json"]["email"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_create_person_exception_propagates(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad request")

        with pytest.raises(Exception, match="Failed to create person"):
            await float_integration.execute_action("create_person", {"name": "Test"}, mock_context)


class TestUpdatePerson:
    @pytest.mark.asyncio
    async def test_update_person_happy_path(self, mock_context):
        updated = {**SAMPLE_PERSON, "job_title": "Senior Engineer"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await float_integration.execute_action(
            "update_person", {"people_id": 1, "job_title": "Senior Engineer"}, mock_context
        )

        assert result.result.data["job_title"] == "Senior Engineer"

    @pytest.mark.asyncio
    async def test_update_person_request_method_and_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PERSON)

        await float_integration.execute_action("update_person", {"people_id": 7, "name": "New Name"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "PATCH"
        assert call_args.kwargs["url"] == "https://api.float.com/v3/people/7"
        assert call_args.kwargs["json"]["name"] == "New Name"


class TestDeletePerson:
    @pytest.mark.asyncio
    async def test_delete_person_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_person", {"people_id": 1}, mock_context)

        assert result.result.data["success"] is True
        assert "1" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_delete_person_request_method_and_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await float_integration.execute_action("delete_person", {"people_id": 99}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "DELETE"
        assert call_args.kwargs["url"] == "https://api.float.com/v3/people/99"


# ---- Projects ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_projects_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_PROJECT_LIST_ITEM])

        result = await float_integration.execute_action("list_projects", {}, mock_context)

        assert result.result.data == [SAMPLE_PROJECT_LIST_ITEM]

    @pytest.mark.asyncio
    async def test_list_projects_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_projects", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/projects"

    @pytest.mark.asyncio
    async def test_list_projects_per_page_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_projects", {"per_page": 100}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["per-page"] == 100

    @pytest.mark.asyncio
    async def test_list_projects_active_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_projects", {"active": True}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["active"] == 1


class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_project_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        result = await float_integration.execute_action("get_project", {"project_id": 10}, mock_context)

        assert result.result.data["project_id"] == 10

    @pytest.mark.asyncio
    async def test_get_project_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        await float_integration.execute_action("get_project", {"project_id": 10}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/projects/10"


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_project_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PROJECT)

        result = await float_integration.execute_action("create_project", {"name": "Website Redesign"}, mock_context)

        assert result.result.data["project_id"] == 10

    @pytest.mark.asyncio
    async def test_create_project_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PROJECT)

        await float_integration.execute_action("create_project", {"name": "My Project", "client_id": 5}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "My Project"
        assert body["client_id"] == 5


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_delete_project_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_project", {"project_id": 10}, mock_context)

        assert result.result.data["success"] is True


# ---- Tasks ----


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_tasks_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TASK])

        result = await float_integration.execute_action("list_tasks", {}, mock_context)

        assert result.result.data == [SAMPLE_TASK]

    @pytest.mark.asyncio
    async def test_list_tasks_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_tasks", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/tasks"

    @pytest.mark.asyncio
    async def test_list_tasks_with_people_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_tasks", {"people_id": 1}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["people_id"] == 1


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        result = await float_integration.execute_action(
            "create_task",
            {"people_id": 1, "project_id": 10, "start_date": "2025-01-01", "end_date": "2025-01-05", "hours": 8.0},
            mock_context,
        )

        assert result.result.data["task_id"] == 100

    @pytest.mark.asyncio
    async def test_create_task_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await float_integration.execute_action(
            "create_task",
            {"people_id": 1, "project_id": 10, "start_date": "2025-01-01", "end_date": "2025-01-05", "hours": 8.0},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["people_id"] == 1
        assert body["project_id"] == 10
        assert body["hours"] == 8.0

    @pytest.mark.asyncio
    async def test_create_task_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TASK)

        await float_integration.execute_action(
            "create_task",
            {"people_id": 1, "project_id": 10, "start_date": "2025-01-01", "end_date": "2025-01-05", "hours": 8.0},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_task_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_task", {"task_id": 100}, mock_context)

        assert result.result.data["success"] is True
        assert "100" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_delete_task_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await float_integration.execute_action("delete_task", {"task_id": 55}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/tasks/55"


# ---- Time Off ----


class TestListTimeOff:
    @pytest.mark.asyncio
    async def test_list_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TIME_OFF])

        result = await float_integration.execute_action("list_time_off", {}, mock_context)

        assert result.result.data == [SAMPLE_TIME_OFF]

    @pytest.mark.asyncio
    async def test_list_time_off_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_time_off", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/timeoffs"


class TestCreateTimeOff:
    @pytest.mark.asyncio
    async def test_create_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_OFF)

        result = await float_integration.execute_action(
            "create_time_off",
            {
                "people_id": 1,
                "timeoff_type_id": 3,
                "start_date": "2025-02-01",
                "end_date": "2025-02-03",
                "hours": 8.0,
            },
            mock_context,
        )

        assert result.result.data["timeoff_id"] == 200

    @pytest.mark.asyncio
    async def test_create_time_off_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIME_OFF)

        await float_integration.execute_action(
            "create_time_off",
            {
                "people_id": 1,
                "timeoff_type_id": 3,
                "start_date": "2025-02-01",
                "end_date": "2025-02-03",
                "hours": 8.0,
                "full_day": True,
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["people_id"] == 1
        assert body["full_day"] is True


class TestDeleteTimeOff:
    @pytest.mark.asyncio
    async def test_delete_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_time_off", {"timeoff_id": 200}, mock_context)

        assert result.result.data["success"] is True


# ---- Logged Time ----


class TestListLoggedTime:
    @pytest.mark.asyncio
    async def test_list_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_LOGGED_TIME])

        result = await float_integration.execute_action("list_logged_time", {}, mock_context)

        assert result.result.data == [SAMPLE_LOGGED_TIME]

    @pytest.mark.asyncio
    async def test_list_logged_time_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_logged_time", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/logged-time"


class TestCreateLoggedTime:
    @pytest.mark.asyncio
    async def test_create_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LOGGED_TIME)

        result = await float_integration.execute_action(
            "create_logged_time",
            {"people_id": 1, "project_id": 10, "date": "2025-01-10", "hours": 7.5},
            mock_context,
        )

        assert result.result.data["logged_time_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_create_logged_time_optional_billable(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_LOGGED_TIME)

        await float_integration.execute_action(
            "create_logged_time",
            {"people_id": 1, "project_id": 10, "date": "2025-01-10", "hours": 7.5, "billable": True},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["billable"] is True


class TestDeleteLoggedTime:
    @pytest.mark.asyncio
    async def test_delete_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action(
            "delete_logged_time", {"logged_time_id": "abc123"}, mock_context
        )

        assert result.result.data["success"] is True


# ---- Clients ----


class TestListClients:
    @pytest.mark.asyncio
    async def test_list_clients_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_CLIENT_LIST_ITEM])

        result = await float_integration.execute_action("list_clients", {}, mock_context)

        assert result.result.data == [SAMPLE_CLIENT_LIST_ITEM]

    @pytest.mark.asyncio
    async def test_list_clients_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_clients", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/clients"


class TestGetClient:
    @pytest.mark.asyncio
    async def test_get_client_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CLIENT)

        result = await float_integration.execute_action("get_client", {"client_id": 5}, mock_context)

        assert result.result.data["client_id"] == 5


class TestCreateClient:
    @pytest.mark.asyncio
    async def test_create_client_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CLIENT)

        result = await float_integration.execute_action("create_client", {"name": "Acme Corp"}, mock_context)

        assert result.result.data["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_create_client_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CLIENT)

        await float_integration.execute_action(
            "create_client", {"name": "Acme Corp", "notes": "Big client"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "Acme Corp"
        assert body["notes"] == "Big client"


class TestDeleteClient:
    @pytest.mark.asyncio
    async def test_delete_client_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_client", {"client_id": 5}, mock_context)

        assert result.result.data["success"] is True


# ---- Departments / Roles ----


class TestListDepartments:
    @pytest.mark.asyncio
    async def test_list_departments_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"department_id": 1, "name": "Engineering"}]
        )

        result = await float_integration.execute_action("list_departments", {}, mock_context)

        assert result.result.data[0]["name"] == "Engineering"

    @pytest.mark.asyncio
    async def test_list_departments_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_departments", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/departments"


class TestListRoles:
    @pytest.mark.asyncio
    async def test_list_roles_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"role_id": 1, "name": "Developer"}]
        )

        result = await float_integration.execute_action("list_roles", {}, mock_context)

        assert result.result.data[0]["role_id"] == 1

    @pytest.mark.asyncio
    async def test_list_roles_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_roles", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/roles"


# ---- Reference Data ----


class TestListTimeOffTypes:
    @pytest.mark.asyncio
    async def test_list_time_off_types_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"timeoff_type_id": 1, "name": "Annual Leave"}]
        )

        result = await float_integration.execute_action("list_time_off_types", {}, mock_context)

        assert result.result.data[0]["name"] == "Annual Leave"

    @pytest.mark.asyncio
    async def test_list_time_off_types_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_time_off_types", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/timeoff-types"


class TestListAccounts:
    @pytest.mark.asyncio
    async def test_list_accounts_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"account_id": 1, "name": "Main"}]
        )

        result = await float_integration.execute_action("list_accounts", {}, mock_context)

        assert result.result.data[0]["account_id"] == 1

    @pytest.mark.asyncio
    async def test_list_accounts_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_accounts", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/accounts"


class TestListStatuses:
    @pytest.mark.asyncio
    async def test_list_statuses_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_statuses", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/status"


# ---- Holidays ----


class TestListPublicHolidays:
    @pytest.mark.asyncio
    async def test_list_public_holidays_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_public_holidays", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/public-holidays"


class TestListTeamHolidays:
    @pytest.mark.asyncio
    async def test_list_team_holidays_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_team_holidays", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/holidays"


# ---- Project Extras ----


class TestListPhases:
    @pytest.mark.asyncio
    async def test_list_phases_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_phases", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/phases"

    @pytest.mark.asyncio
    async def test_list_phases_with_project_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_phases", {"project_id": 10}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["project_id"] == 10


class TestListMilestones:
    @pytest.mark.asyncio
    async def test_list_milestones_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_milestones", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/milestones"


class TestMergeProjectTasks:
    @pytest.mark.asyncio
    async def test_merge_project_tasks_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"success": True})

        result = await float_integration.execute_action(
            "merge_project_tasks", {"source_ids": [1, 2], "target_id": 3}, mock_context
        )

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_merge_project_tasks_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action(
            "merge_project_tasks", {"source_ids": [1, 2], "target_id": 3}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["source_ids"] == [1, 2]
        assert body["target_id"] == 3
        assert mock_context.fetch.call_args.kwargs["url"] == "https://api.float.com/v3/project-tasks/merge"


# ---- Reports ----


class TestGetPeopleReport:
    @pytest.mark.asyncio
    async def test_get_people_report_happy_path(self, mock_context):
        report_data = {"people": [{"people_id": 1, "name": "Alice", "scheduled_hours": 40.0}]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=report_data)

        result = await float_integration.execute_action("get_people_report", {}, mock_context)

        assert result.result.data["people"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_people_report_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action("get_people_report", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/reports/people"

    @pytest.mark.asyncio
    async def test_get_people_report_with_date_filters(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action(
            "get_people_report",
            {"start_date": "2025-01-01", "end_date": "2025-01-31"},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["start_date"] == "2025-01-01"
        assert params["end_date"] == "2025-01-31"


class TestGetProjectsReport:
    @pytest.mark.asyncio
    async def test_get_projects_report_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action("get_projects_report", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs["url"]
        assert url == "https://api.float.com/v3/reports/projects"

    @pytest.mark.asyncio
    async def test_get_projects_report_with_project_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action("get_projects_report", {"project_id": 10}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["project_id"] == 10


# ---- Auth headers ----


class TestAuthHeaders:
    @pytest.mark.asyncio
    async def test_auth_header_includes_bearer_token(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test_api_key"  # nosec B105

    @pytest.mark.asyncio
    async def test_user_agent_header_included(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_people", {}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert "Test App" in headers["User-Agent"]
        assert "test@example.com" in headers["User-Agent"]
