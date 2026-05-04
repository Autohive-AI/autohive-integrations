import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

float_integration = _mod.float

pytestmark = pytest.mark.unit


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


# ---- Logged Time ----


class TestListLoggedTime:
    @pytest.mark.asyncio
    async def test_list_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[{"logged_time_id": "abc123", "hours": 8.0, "people_id": 1, "project_id": 1, "date": "2025-01-15"}],
        )

        result = await float_integration.execute_action("list_logged_time", {}, mock_context)

        assert result.result.data[0]["logged_time_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_list_logged_time_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_logged_time", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert "logged-time" in url

    @pytest.mark.asyncio
    async def test_list_logged_time_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await float_integration.execute_action("list_logged_time", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetLoggedTime:
    @pytest.mark.asyncio
    async def test_get_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"logged_time_id": "abc123", "hours": 4.0, "people_id": 1, "project_id": 1, "date": "2025-01-15"},
        )

        result = await float_integration.execute_action("get_logged_time", {"logged_time_id": "abc123"}, mock_context)

        assert result.result.data["logged_time_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_get_logged_time_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_logged_time", {"logged_time_id": "bad_id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateLoggedTime:
    @pytest.mark.asyncio
    async def test_create_logged_time_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={"logged_time_id": "abc10", "hours": 8.0, "people_id": 1, "project_id": 1, "date": "2025-01-15"},
        )

        result = await float_integration.execute_action(
            "create_logged_time",
            {"people_id": 1, "project_id": 1, "date": "2025-01-15", "hours": 8.0},
            mock_context,
        )

        assert result.result.data["logged_time_id"] == "abc10"

    @pytest.mark.asyncio
    async def test_create_logged_time_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create failed")

        result = await float_integration.execute_action(
            "create_logged_time",
            {"people_id": 1, "project_id": 1, "date": "2025-01-15", "hours": 8.0},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Clients ----


class TestListClients:
    @pytest.mark.asyncio
    async def test_list_clients_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[{"client_id": 5, "name": "Acme"}])

        result = await float_integration.execute_action("list_clients", {}, mock_context)

        assert result.result.data[0]["client_id"] == 5

    @pytest.mark.asyncio
    async def test_list_clients_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_clients", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetClient:
    @pytest.mark.asyncio
    async def test_get_client_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"client_id": 5, "name": "Acme"})

        result = await float_integration.execute_action("get_client", {"client_id": 5}, mock_context)

        assert result.result.data["client_id"] == 5

    @pytest.mark.asyncio
    async def test_get_client_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_client", {"client_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateClient:
    @pytest.mark.asyncio
    async def test_create_client_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={"client_id": 20, "name": "New"})

        result = await float_integration.execute_action("create_client", {"name": "New Client"}, mock_context)

        assert result.result.data["client_id"] == 20

    @pytest.mark.asyncio
    async def test_create_client_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create error")

        result = await float_integration.execute_action("create_client", {"name": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteClient:
    @pytest.mark.asyncio
    async def test_delete_client_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_client", {"client_id": 5}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_client_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete failed")

        result = await float_integration.execute_action("delete_client", {"client_id": 5}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Departments ----


class TestListDepartments:
    @pytest.mark.asyncio
    async def test_list_departments_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"department_id": 1, "name": "Engineering"}]
        )

        result = await float_integration.execute_action("list_departments", {}, mock_context)

        assert result.result.data[0]["department_id"] == 1

    @pytest.mark.asyncio
    async def test_list_departments_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_departments", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDepartment:
    @pytest.mark.asyncio
    async def test_get_department_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"department_id": 1, "name": "Engineering"}
        )

        result = await float_integration.execute_action("get_department", {"department_id": 1}, mock_context)

        assert result.result.data["department_id"] == 1

    @pytest.mark.asyncio
    async def test_get_department_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_department", {"department_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Roles ----


class TestListRoles:
    @pytest.mark.asyncio
    async def test_list_roles_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"role_id": 1, "name": "Developer"}]
        )

        result = await float_integration.execute_action("list_roles", {}, mock_context)

        assert result.result.data[0]["role_id"] == 1

    @pytest.mark.asyncio
    async def test_list_roles_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_roles", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetRole:
    @pytest.mark.asyncio
    async def test_get_role_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"role_id": 1, "name": "Developer"}
        )

        result = await float_integration.execute_action("get_role", {"role_id": 1}, mock_context)

        assert result.result.data["role_id"] == 1

    @pytest.mark.asyncio
    async def test_get_role_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_role", {"role_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Accounts ----


class TestListAccounts:
    @pytest.mark.asyncio
    async def test_list_accounts_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"account_id": 1, "name": "Main"}]
        )

        result = await float_integration.execute_action("list_accounts", {}, mock_context)

        assert result.result.data[0]["account_id"] == 1

    @pytest.mark.asyncio
    async def test_list_accounts_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_accounts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_get_account_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"account_id": 1})

        result = await float_integration.execute_action("get_account", {"account_id": 1}, mock_context)

        assert result.result.data["account_id"] == 1

    @pytest.mark.asyncio
    async def test_get_account_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("get_account", {"account_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Statuses ----


class TestListStatuses:
    @pytest.mark.asyncio
    async def test_list_statuses_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"status_id": 1, "name": "Active"}]
        )

        result = await float_integration.execute_action("list_statuses", {}, mock_context)

        assert result.result.data[0]["status_id"] == 1

    @pytest.mark.asyncio
    async def test_list_statuses_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_statuses", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Public Holidays ----


class TestListPublicHolidays:
    @pytest.mark.asyncio
    async def test_list_public_holidays_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"public_holiday_id": 1, "name": "New Year"}]
        )

        result = await float_integration.execute_action("list_public_holidays", {}, mock_context)

        assert result.result.data[0]["public_holiday_id"] == 1

    @pytest.mark.asyncio
    async def test_list_public_holidays_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_public_holidays", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Team Holidays ----


class TestListTeamHolidays:
    @pytest.mark.asyncio
    async def test_list_team_holidays_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"team_holiday_id": 1, "name": "Company Day"}]
        )

        result = await float_integration.execute_action("list_team_holidays", {}, mock_context)

        assert result.result.data[0]["team_holiday_id"] == 1

    @pytest.mark.asyncio
    async def test_list_team_holidays_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_team_holidays", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Time Off Types ----


class TestListTimeOffTypes:
    @pytest.mark.asyncio
    async def test_list_time_off_types_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"timeoff_type_id": 1, "name": "Vacation"}]
        )

        result = await float_integration.execute_action("list_time_off_types", {}, mock_context)

        assert result.result.data[0]["timeoff_type_id"] == 1

    @pytest.mark.asyncio
    async def test_list_time_off_types_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_time_off_types", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetTimeOffType:
    @pytest.mark.asyncio
    async def test_get_time_off_type_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"timeoff_type_id": 1, "name": "Vacation"}
        )

        result = await float_integration.execute_action("get_time_off_type", {"timeoff_type_id": 1}, mock_context)

        assert result.result.data["timeoff_type_id"] == 1

    @pytest.mark.asyncio
    async def test_get_time_off_type_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("get_time_off_type", {"timeoff_type_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Reports ----


class TestGetPeopleReport:
    @pytest.mark.asyncio
    async def test_get_people_report_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})

        result = await float_integration.execute_action(
            "get_people_report", {"start_date": "2025-01-01", "end_date": "2025-01-31"}, mock_context
        )

        assert result.result.data is not None

    @pytest.mark.asyncio
    async def test_get_people_report_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await float_integration.execute_action(
            "get_people_report", {"start_date": "2025-01-01", "end_date": "2025-01-31"}, mock_context
        )

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert "reports/people" in url

    @pytest.mark.asyncio
    async def test_get_people_report_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Report error")

        result = await float_integration.execute_action("get_people_report", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetProjectsReport:
    @pytest.mark.asyncio
    async def test_get_projects_report_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": []})

        result = await float_integration.execute_action(
            "get_projects_report", {"start_date": "2025-01-01", "end_date": "2025-01-31"}, mock_context
        )

        assert result.result.data is not None

    @pytest.mark.asyncio
    async def test_get_projects_report_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Report error")

        result = await float_integration.execute_action("get_projects_report", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Milestones ----


class TestListMilestones:
    @pytest.mark.asyncio
    async def test_list_milestones_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[{"milestone_id": 1, "name": "Launch"}]
        )

        result = await float_integration.execute_action("list_milestones", {}, mock_context)

        assert result.result.data[0]["milestone_id"] == 1

    @pytest.mark.asyncio
    async def test_list_milestones_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("list_milestones", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetMilestone:
    @pytest.mark.asyncio
    async def test_get_milestone_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"milestone_id": 1, "name": "Launch"}
        )

        result = await float_integration.execute_action("get_milestone", {"milestone_id": 1}, mock_context)

        assert result.result.data["milestone_id"] == 1

    @pytest.mark.asyncio
    async def test_get_milestone_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await float_integration.execute_action("get_milestone", {"milestone_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
