"""Unit tests for the Projectworks integration using a mocked fetch."""

import base64

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from projectworks.projectworks import (
    projectworks,
    _as_list,
    _clean,
    _get_headers,
    _matches_query,
    _project,
    BASE_URL,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SEARCH_SCAN,
)

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


class TestGetHeaders:
    def test_basic_auth_header_from_flat_auth(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {"consumer_key": "key123", "consumer_secret": "secret456"}  # nosec B105
        headers = _get_headers(ctx)
        expected = base64.b64encode(b"key123:secret456").decode()
        assert headers["Authorization"] == f"Basic {expected}"
        assert headers["Accept"] == "application/json"

    def test_basic_auth_header_from_nested_credentials(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {"credentials": {"consumer_key": "k", "consumer_secret": "s"}}  # nosec B105
        headers = _get_headers(ctx)
        expected = base64.b64encode(b"k:s").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_missing_credentials_raise(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {}
        with pytest.raises(ValueError, match="Consumer Key and Consumer Secret are required"):
            _get_headers(ctx)

    def test_blank_credentials_raise(self):
        ctx = type("Ctx", (), {})()
        ctx.auth = {"consumer_key": "key123", "consumer_secret": ""}  # nosec B105
        with pytest.raises(ValueError, match="Consumer Key and Consumer Secret are required"):
            _get_headers(ctx)

    @pytest.mark.asyncio
    async def test_action_surfaces_missing_credential_error(self, mock_context):
        # The runtime guard should reach the caller as a clear ActionError,
        # not an unauthenticated request.
        mock_context.auth = {}
        result = await projectworks.execute_action("list_users", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Consumer Key and Consumer Secret are required" in result.result.message
        mock_context.fetch.assert_not_called()


class TestAsList:
    def test_bare_list_passthrough(self):
        assert _as_list([{"id": 1}]) == [{"id": 1}]

    def test_empty_list(self):
        assert _as_list([]) == []

    def test_wrapped_data_key(self):
        assert _as_list({"data": [{"id": 1}]}) == [{"id": 1}]

    def test_wrapped_items_key(self):
        assert _as_list({"items": [{"id": 2}]}) == [{"id": 2}]

    def test_unknown_shape_returns_empty(self):
        assert _as_list({"unexpected": "value"}) == []

    def test_none_returns_empty(self):
        assert _as_list(None) == []


class TestClean:
    def test_drops_none(self):
        assert _clean({"UserID": 5, "Email": None, "Name": "Jane"}) == {"UserID": 5, "Name": "Jane"}

    def test_keeps_falsey_non_none(self):
        # 0 and False are valid values and must not be dropped.
        assert _clean({"IsBillable": False, "page": 0}) == {"IsBillable": False, "page": 0}

    def test_empty(self):
        assert _clean({"x": None}) == {}


# =============================================================================
# USERS
# =============================================================================


class TestListUsers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"userID": 1, "email": "a@b.com"}])
        result = await projectworks.execute_action("list_users", {}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["users"][0]["userID"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_users", {}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_filters_mapped_to_query_params(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action(
            "list_users",
            {"email": "a@b.com", "modified_since_date": "2026-01-01T00:00:00Z", "page": 2, "page_size": 50},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["Email"] == "a@b.com"
        assert params["ModifiedSinceDate"] == "2026-01-01T00:00:00Z"
        assert params["page"] == 2
        assert params["pageSize"] == 50

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_context):
        mock_context.fetch.return_value = ok([])
        result = await projectworks.execute_action("list_users", {}, mock_context)
        assert result.result.data["users"] == []

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")
        result = await projectworks.execute_action("list_users", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_non_2xx_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=401, headers={}, data={"message": "Unauthorized"})
        result = await projectworks.execute_action("list_users", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "401" in result.result.message
        assert "Unauthorized" in result.result.message


class TestGetUser:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"userID": 7, "email": "x@y.com"})
        result = await projectworks.execute_action("get_user", {"user_id": 7}, mock_context)
        assert result.result.data["user"]["userID"] == 7

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok({})
        await projectworks.execute_action("get_user", {"user_id": 7}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Users/7"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await projectworks.execute_action("get_user", {"user_id": 7}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListRoles:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"userRoleID": 3, "code": "DEV", "description": "Developer"}])
        result = await projectworks.execute_action("list_roles", {}, mock_context)
        assert result.result.data["roles"][0]["userRoleID"] == 3
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Users/Roles"

    @pytest.mark.asyncio
    async def test_role_code_filter(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_roles", {"role_code": "DEV"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["roleCode"] == "DEV"


# =============================================================================
# CLIENTS
# =============================================================================


class TestListClients:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"clientID": 3}])
        result = await projectworks.execute_action("list_clients", {"office_id": 1}, mock_context)
        assert result.result.data["clients"][0]["clientID"] == 3
        assert mock_context.fetch.call_args.kwargs["params"]["OfficeID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_clients", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Clients"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_clients", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetClient:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"clientID": 9})
        result = await projectworks.execute_action("get_client", {"client_id": 9}, mock_context)
        assert result.result.data["client"]["clientID"] == 9
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Clients/9"


# =============================================================================
# PROJECTS
# =============================================================================


class TestListProjects:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"projectID": 11}])
        result = await projectworks.execute_action(
            "list_projects", {"client_id": 2, "project_number": "P-100"}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["ClientID"] == 2
        assert params["ProjectNumber"] == "P-100"
        assert result.result.data["projects"][0]["projectID"] == 11

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_projects", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Projects"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_projects", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetProject:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"projectID": 4})
        result = await projectworks.execute_action("get_project", {"project_id": 4}, mock_context)
        assert result.result.data["project"]["projectID"] == 4
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Projects/4"


# =============================================================================
# MODULES
# =============================================================================


class TestListModules:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"moduleID": 1}])
        result = await projectworks.execute_action("list_modules", {"project_id": 5}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["ProjectID"] == 5
        assert result.result.data["modules"][0]["moduleID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_modules", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Modules"


class TestGetModule:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"moduleID": 6})
        result = await projectworks.execute_action("get_module", {"module_id": 6}, mock_context)
        assert result.result.data["module"]["moduleID"] == 6
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Modules/6"


# =============================================================================
# TASKS
# =============================================================================


class TestListTasks:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"taskID": 1}])
        result = await projectworks.execute_action("list_tasks", {"project_id": 5, "module_id": 8}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["ProjectID"] == 5
        assert params["ModuleID"] == 8
        assert result.result.data["tasks"][0]["taskID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_tasks", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Tasks"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_tasks", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetTask:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"taskID": 2})
        result = await projectworks.execute_action("get_task", {"task_id": 2}, mock_context)
        assert result.result.data["task"]["taskID"] == 2
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Tasks/2"


# =============================================================================
# RESOURCES
# =============================================================================


class TestListResources:
    @pytest.mark.asyncio
    async def test_happy_path_with_date_range(self, mock_context):
        mock_context.fetch.return_value = ok([{"resourceID": 1}])
        result = await projectworks.execute_action(
            "list_resources",
            {"project_id": 5, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            mock_context,
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["ProjectID"] == 5
        assert params["StartDate"] == "2026-01-01"
        assert params["EndDate"] == "2026-01-31"
        assert result.result.data["resources"][0]["resourceID"] == 1

    @pytest.mark.asyncio
    async def test_after_resource_id_cursor(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_resources", {"after_resource_id": 100}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["AfterResourceID"] == 100

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_resources", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Resources"


class TestGetResource:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"resourceID": 12})
        result = await projectworks.execute_action("get_resource", {"resource_id": 12}, mock_context)
        assert result.result.data["resource"]["resourceID"] == 12
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Resources/12"


# =============================================================================
# TIMESHEETS
# =============================================================================


class TestListTimesheets:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1}])
        result = await projectworks.execute_action(
            "list_timesheets", {"user_id": 3, "date": "2026-06-01"}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["UserID"] == 3
        assert params["Date"] == "2026-06-01"
        assert result.result.data["timesheets"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_timesheet_id_maps_to_ID(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_timesheets", {"timesheet_id": 55}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["ID"] == 55

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_timesheets", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Timesheets"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_timesheets", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LEAVE
# =============================================================================


class TestListLeaves:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"leaveID": 1}])
        result = await projectworks.execute_action("list_leaves", {"user_id": 3, "status_id": 2}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["UserID"] == 3
        assert params["StatusID"] == 2
        assert result.result.data["leaves"][0]["leaveID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_leaves", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Leaves"


class TestGetLeave:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"leaveID": 21})
        result = await projectworks.execute_action("get_leave", {"leave_id": 21}, mock_context)
        assert result.result.data["leave"]["leaveID"] == 21
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Leaves/21"


class TestListLeaveTypes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"typeID": 5, "name": "Annual"}])
        result = await projectworks.execute_action("list_leave_types", {"is_active": True}, mock_context)
        assert result.result.data["leave_types"][0]["typeID"] == 5
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Leaves/Types"
        assert mock_context.fetch.call_args.kwargs["params"]["IsActive"] is True

    @pytest.mark.asyncio
    async def test_filters_mapped(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_leave_types", {"type_id": 5, "name": "Annual"}, mock_context)
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["TypeID"] == 5
        assert params["Name"] == "Annual"


# =============================================================================
# INVOICES
# =============================================================================


class TestListInvoices:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"invoiceID": 1}])
        result = await projectworks.execute_action(
            "list_invoices", {"client_id": 2, "invoice_number": "INV-1"}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["ClientID"] == 2
        assert params["InvoiceNumber"] == "INV-1"
        assert result.result.data["invoices"][0]["invoiceID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_invoices", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Invoices"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_invoices", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetInvoice:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"invoiceID": 33})
        result = await projectworks.execute_action("get_invoice", {"invoice_id": 33}, mock_context)
        assert result.result.data["invoice"]["invoiceID"] == 33
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Invoices/33"


# =============================================================================
# EXPENSE CLAIMS
# =============================================================================


class TestListExpenseClaims:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"id": 1}])
        result = await projectworks.execute_action(
            "list_expense_claims", {"user_id": 3, "is_billable": True}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["UserID"] == 3
        assert params["IsBillable"] is True
        assert result.result.data["expense_claims"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_is_billable_false_is_sent(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_expense_claims", {"is_billable": False}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["IsBillable"] is False

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_expense_claims", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/ExpenseClaims"


class TestGetExpenseClaim:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 44})
        result = await projectworks.execute_action("get_expense_claim", {"expense_claim_id": 44}, mock_context)
        assert result.result.data["expense_claim"]["id"] == 44
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/ExpenseClaims/44"

    @pytest.mark.asyncio
    async def test_include_custom_fields_param(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 44})
        await projectworks.execute_action(
            "get_expense_claim", {"expense_claim_id": 44, "include_custom_fields": True}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["params"]["includeCustomFields"] is True

    @pytest.mark.asyncio
    async def test_no_optional_param_omitted(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 44})
        await projectworks.execute_action("get_expense_claim", {"expense_claim_id": 44}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"] == {}

    @pytest.mark.asyncio
    async def test_single_element_array_is_unwrapped(self, mock_context):
        # The endpoint can return a one-element array rather than a bare object.
        mock_context.fetch.return_value = ok([{"id": 44}])
        result = await projectworks.execute_action("get_expense_claim", {"expense_claim_id": 44}, mock_context)
        assert result.result.data["expense_claim"] == {"id": 44}

    @pytest.mark.asyncio
    async def test_empty_body_yields_empty_object(self, mock_context):
        mock_context.fetch.return_value = ok(None)
        result = await projectworks.execute_action("get_expense_claim", {"expense_claim_id": 44}, mock_context)
        assert result.result.data["expense_claim"] == {}


# =============================================================================
# OFFICES
# =============================================================================


class TestListOffices:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok([{"officeID": 1, "name": "HQ"}])
        result = await projectworks.execute_action("list_offices", {"name": "HQ"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["Name"] == "HQ"
        assert result.result.data["offices"][0]["officeID"] == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_offices", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Offices"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("list_offices", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# WRITE — CLIENTS
# =============================================================================


class TestCreateClient:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"clientID": 100, "clientName": "Acme"})
        result = await projectworks.execute_action(
            "create_client",
            {"client_name": "Acme", "account_manager_id": 1, "office_id": 2},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["client"]["clientID"] == 100

    @pytest.mark.asyncio
    async def test_request_method_url_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"clientID": 100})
        await projectworks.execute_action(
            "create_client",
            {"client_name": "Acme", "account_manager_id": 1, "office_id": 2, "finance_email": "f@a.com"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Clients"
        assert call.kwargs["method"] == "POST"
        body = call.kwargs["json"]
        assert body["clientName"] == "Acme"
        assert body["accountManagerID"] == 1
        assert body["officeID"] == 2
        assert body["financeEmail"] == "f@a.com"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await projectworks.execute_action(
            "create_client", {"client_name": "Acme", "account_manager_id": 1, "office_id": 2}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateClient:
    @pytest.mark.asyncio
    async def test_patch_partial_body(self, mock_context):
        mock_context.fetch.return_value = ok({"clientID": 5, "clientName": "New"})
        await projectworks.execute_action("update_client", {"client_id": 5, "client_name": "New"}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Clients/5"
        assert call.kwargs["method"] == "PATCH"
        # Delta — only the provided field is sent (client_id is path-only).
        assert call.kwargs["json"] == {"clientName": "New"}

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("update_client", {"client_id": 5}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteClient:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_client", {"client_id": 5}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Clients/5"
        assert call.kwargs["method"] == "DELETE"
        assert result.result.data == {"client_id": 5, "deleted": True}

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("delete_client", {"client_id": 5}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# WRITE — PROJECTS
# =============================================================================


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"projectID": 9})
        await projectworks.execute_action(
            "create_project",
            {
                "project_name": "P1",
                "office_id": 1,
                "client_id": 2,
                "project_type_id": 3,
                "project_status_id": 4,
                "currency_id": 5,
                "project_manager_id": 6,
                "account_manager_id": 7,
                "task_self_service_mode_id": 8,
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Projects"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["projectName"] == "P1"
        assert call.kwargs["json"]["clientID"] == 2


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_patch_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"projectID": 9})
        await projectworks.execute_action("update_project", {"project_id": 9, "is_active": False}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Projects/9"
        assert call.kwargs["method"] == "PATCH"
        assert call.kwargs["json"] == {"isActive": False}


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_project", {"project_id": 9}, mock_context)
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"
        assert result.result.data == {"project_id": 9, "deleted": True}


# =============================================================================
# WRITE — MODULES
# =============================================================================


class TestCreateModule:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"moduleID": 3})
        await projectworks.execute_action("create_module", {"project_id": 1, "module_name": "M1"}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Modules"
        assert call.kwargs["json"] == {"projectID": 1, "moduleName": "M1"}


class TestUpdateModule:
    @pytest.mark.asyncio
    async def test_patch(self, mock_context):
        mock_context.fetch.return_value = ok({"moduleID": 3})
        await projectworks.execute_action("update_module", {"module_id": 3, "budget": 1000}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Modules/3"
        assert call.kwargs["method"] == "PATCH"
        assert call.kwargs["json"] == {"budget": 1000}


class TestDeleteModule:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_module", {"module_id": 3}, mock_context)
        assert result.result.data == {"module_id": 3, "deleted": True}


# =============================================================================
# WRITE — TASKS
# =============================================================================


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"taskID": 7})
        await projectworks.execute_action(
            "create_task", {"module_id": 2, "task_name": "T1", "is_billable": True}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Tasks"
        assert call.kwargs["json"]["moduleID"] == 2
        assert call.kwargs["json"]["taskName"] == "T1"
        assert call.kwargs["json"]["isBillable"] is True


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_patch(self, mock_context):
        mock_context.fetch.return_value = ok({"taskID": 7})
        await projectworks.execute_action("update_task", {"task_id": 7, "percent_complete": 50}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Tasks/7"
        assert call.kwargs["method"] == "PATCH"
        assert call.kwargs["json"] == {"percentComplete": 50}


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_task", {"task_id": 7}, mock_context)
        assert result.result.data == {"task_id": 7, "deleted": True}


# =============================================================================
# WRITE — USERS
# =============================================================================


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"userID": 50})
        await projectworks.execute_action(
            "create_user",
            {"email": "a@b.com", "first_name": "Jane", "last_name": "Doe"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users"
        assert call.kwargs["json"] == {"email": "a@b.com", "firstName": "Jane", "lastName": "Doe"}


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_patch(self, mock_context):
        mock_context.fetch.return_value = ok({"userID": 50})
        await projectworks.execute_action("update_user", {"user_id": 50, "is_active": False}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users/50"
        assert call.kwargs["method"] == "PATCH"
        assert call.kwargs["json"] == {"isActive": False}


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_user", {"user_id": 50}, mock_context)
        assert result.result.data == {"user_id": 50, "deleted": True}


# =============================================================================
# WRITE — LEAVE
# =============================================================================


class TestCreateLeave:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"leaveID": 5})
        days = [{"date": "2026-07-01", "typeID": 1, "hours": 8}]
        await projectworks.execute_action("create_leave", {"user_id": 3, "status_id": 1, "days": days}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Leaves"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"userID": 3, "statusID": 1, "days": days}


class TestUpdateLeave:
    @pytest.mark.asyncio
    async def test_put(self, mock_context):
        mock_context.fetch.return_value = ok({"leaveID": 5})
        days = [{"date": "2026-07-01", "typeID": 1, "hours": 8}]
        await projectworks.execute_action(
            "update_leave", {"leave_id": 5, "user_id": 3, "status_id": 2, "days": days}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Leaves/5"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"]["statusID"] == 2


class TestDeleteLeave:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_leave", {"leave_id": 5}, mock_context)
        assert result.result.data == {"leave_id": 5, "deleted": True}


# =============================================================================
# WRITE — EXPENSE CLAIMS
# =============================================================================


def _expense_inputs(**over):
    base = {
        "user_id": 1,
        "project_id": 2,
        "module_id": 3,
        "expense_claim_type_id": 4,
        "is_reimbursable": True,
        "is_processed": False,
        "date": "2026-06-01",
        "amount": 42.5,
        "currency_id": 1,
        "tax_type_id": 1,
    }
    base.update(over)
    return base


class TestCreateExpenseClaim:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 11})
        await projectworks.execute_action("create_expense_claim", _expense_inputs(), mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/ExpenseClaims"
        assert call.kwargs["method"] == "POST"
        body = call.kwargs["json"]
        assert body["amount"] == 42.5
        assert body["isReimbursable"] is True
        assert body["isProcessed"] is False

    @pytest.mark.asyncio
    async def test_file_object_with_base64_content(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 11})
        raw = b"%PDF-1.4 receipt"
        content_b64 = base64.b64encode(raw).decode()
        await projectworks.execute_action(
            "create_expense_claim",
            _expense_inputs(file={"name": "receipt.pdf", "content": content_b64}),
            mock_context,
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["fileName"] == "receipt.pdf"
        # Round-trips through bytes, so the body still carries valid base64 of the file.
        assert base64.b64decode(body["fileContent"]) == raw

    @pytest.mark.asyncio
    async def test_file_object_without_content_errors(self, mock_context):
        # A 'url' is intentionally not downloaded (SSRF risk); only base64 'content' is accepted.
        mock_context.fetch.return_value = ok({"id": 11})
        result = await projectworks.execute_action(
            "create_expense_claim",
            _expense_inputs(file={"name": "receipt.pdf", "url": "https://files.example.com/receipt.pdf"}),
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_invalid_base64_content_errors(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 11})
        result = await projectworks.execute_action(
            "create_expense_claim",
            _expense_inputs(file={"name": "x.pdf", "content": "not!base64!"}),
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateExpenseClaim:
    @pytest.mark.asyncio
    async def test_put(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 11})
        await projectworks.execute_action(
            "update_expense_claim", _expense_inputs(expense_claim_id=11, amount=99), mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/ExpenseClaims/11"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"]["amount"] == 99


class TestDeleteExpenseClaim:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_expense_claim", {"expense_claim_id": 11}, mock_context)
        assert result.result.data == {"expense_claim_id": 11, "deleted": True}


# =============================================================================
# WRITE — TIMESHEETS
# =============================================================================


class TestCreateTimesheet:
    @pytest.mark.asyncio
    async def test_happy_path_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1})
        await projectworks.execute_action(
            "create_timesheet",
            {"user_id": 3, "task_id": 4, "date": "2026-06-01", "minutes": 120, "comment": "work"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Timesheets"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "userID": 3,
            "taskID": 4,
            "date": "2026-06-01",
            "minutes": 120,
            "comment": "work",
        }


class TestUpdateTimesheet:
    @pytest.mark.asyncio
    async def test_put_collection_with_id_in_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": 1})
        await projectworks.execute_action("update_timesheet", {"timesheet_id": 1, "minutes": 90}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Timesheets"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"id": 1, "minutes": 90}


class TestDeleteTimesheet:
    @pytest.mark.asyncio
    async def test_delete_uses_query_id(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await projectworks.execute_action("delete_timesheet", {"timesheet_id": 1}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Timesheets"
        assert call.kwargs["method"] == "DELETE"
        assert call.kwargs["params"] == {"id": 1}
        assert result.result.data == {"timesheet_id": 1, "deleted": True}


# =============================================================================
# WRITE — SUB-RESOURCES
# =============================================================================


class TestUpdateProjectUser:
    @pytest.mark.asyncio
    async def test_put_url_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"userID": 3})
        await projectworks.execute_action(
            "update_project_user", {"project_id": 9, "user_id": 3, "rate": 150}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Projects/9/Users"
        assert call.kwargs["method"] == "PUT"
        # project_id is path-only; only body fields are sent.
        assert call.kwargs["json"] == {"userID": 3, "rate": 150}

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action("update_project_user", {"project_id": 9, "user_id": 3}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateTaskUser:
    @pytest.mark.asyncio
    async def test_put_url_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"userID": 3})
        await projectworks.execute_action(
            "update_task_user", {"task_id": 7, "user_id": 3, "hours": 10, "is_active": True}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Tasks/7/Users"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"userID": 3, "hours": 10, "isActive": True}


class TestUpdateTaskPlaceholder:
    @pytest.mark.asyncio
    async def test_put_url_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"placeholderID": 2})
        await projectworks.execute_action(
            "update_task_placeholder", {"task_id": 7, "role_id": 5, "hours": 8}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Tasks/7/Placeholders"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"roleID": 5, "hours": 8}


class TestUpdateUserRoles:
    @pytest.mark.asyncio
    async def test_put_wraps_role_ids(self, mock_context):
        mock_context.fetch.return_value = ok({})
        await projectworks.execute_action(
            "update_user_roles", {"user_id": 50, "user_role_ids": [1, 2, 3]}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users/50/Roles"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"userRoleIDs": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_empty_body_echoes_applied_state(self, mock_context):
        # The endpoint returns an empty 200 body (often null) — output must
        # still satisfy the schema rather than passing through None.
        mock_context.fetch.return_value = ok(None)
        result = await projectworks.execute_action(
            "update_user_roles", {"user_id": 50, "user_role_ids": [1, 2, 3]}, mock_context
        )
        assert result.result.data == {"user_id": 50, "user_role_ids": [1, 2, 3], "updated": True}


class TestUpdateUserLeaveBalances:
    @pytest.mark.asyncio
    async def test_put_passes_balances(self, mock_context):
        mock_context.fetch.return_value = ok({})
        balances = [{"leaveTypeID": 1, "balance": 40, "unit": "Hours"}]
        await projectworks.execute_action(
            "update_user_leave_balances", {"user_id": 50, "balances": balances}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users/50/LeaveBalances"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"balances": balances}

    @pytest.mark.asyncio
    async def test_empty_body_echoes_applied_state(self, mock_context):
        mock_context.fetch.return_value = ok(None)
        balances = [{"leaveTypeID": 1, "balance": 40, "unit": "Hours"}]
        result = await projectworks.execute_action(
            "update_user_leave_balances", {"user_id": 50, "balances": balances}, mock_context
        )
        assert result.result.data == {"user_id": 50, "balances": balances, "updated": True}


class TestUpdateUserPostings:
    @pytest.mark.asyncio
    async def test_put_url_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({})
        inputs = {
            "user_id": 50,
            "start_date": "2026-01-01",
            "is_billable": True,
            "recoverable": 1,
            "rate": 120.0,
            "office_id": 1,
            "location_id": 2,
            "team_id": 3,
            "position_id": 4,
            "agreement_type_id": 5,
            "currency_id": 6,
        }
        await projectworks.execute_action("update_user_postings", inputs, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Users/50/Postings"
        assert call.kwargs["method"] == "PUT"
        body = call.kwargs["json"]
        assert body["startDate"] == "2026-01-01"
        assert body["officeID"] == 1
        assert body["isBillable"] is True
        assert "userID" not in body  # user_id is path-only


class TestSetCustomFields:
    @pytest.mark.asyncio
    async def test_put_bare_array_body_for_project(self, mock_context):
        mock_context.fetch.return_value = ok({})
        fields = [{"fieldID": 10, "value": "Hello"}]
        result = await projectworks.execute_action(
            "set_custom_fields", {"entity_type": "project", "entity_id": 9, "fields": fields}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE_URL}/Projects/9/Fields"
        assert call.kwargs["method"] == "PUT"
        # Body is the bare array, not wrapped in a key.
        assert call.kwargs["json"] == fields
        assert result.result.data == {"entity_id": 9, "updated": True}

    @pytest.mark.asyncio
    async def test_entity_type_maps_to_segment(self, mock_context):
        mock_context.fetch.return_value = ok({})
        for entity_type, segment in [
            ("client", "Clients"),
            ("module", "Modules"),
            ("task", "Tasks"),
            ("user", "Users"),
        ]:
            await projectworks.execute_action(
                "set_custom_fields", {"entity_type": entity_type, "entity_id": 1, "fields": []}, mock_context
            )
            assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/{segment}/1/Fields"

    @pytest.mark.asyncio
    async def test_error_path(self, mock_context):
        mock_context.fetch.side_effect = Exception("err")
        result = await projectworks.execute_action(
            "set_custom_fields", {"entity_type": "user", "entity_id": 1, "fields": []}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CONTEXT-WINDOW HELPERS: default page size + field projection
# =============================================================================


class TestProject:
    def test_none_fields_passes_records_through(self):
        records = [{"UserID": 1, "Name": "Jane"}]
        assert _project(records, None) == records

    def test_empty_fields_passes_records_through(self):
        records = [{"UserID": 1, "Name": "Jane"}]
        assert _project(records, []) == records

    def test_trims_to_requested_fields(self):
        records = [{"UserID": 1, "Name": "Jane", "Email": "j@x.com"}]
        assert _project(records, ["UserID", "Name"]) == [{"UserID": 1, "Name": "Jane"}]

    def test_unknown_field_simply_absent(self):
        records = [{"UserID": 1}]
        assert _project(records, ["UserID", "Missing"]) == [{"UserID": 1}]

    def test_non_dict_records_passthrough(self):
        assert _project([1, "x"], ["UserID"]) == [1, "x"]


class TestListPageSizeAndProjection:
    @pytest.mark.asyncio
    async def test_default_page_size_applied_when_unset(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_users", {}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["pageSize"] == DEFAULT_PAGE_SIZE

    @pytest.mark.asyncio
    async def test_explicit_page_size_overrides_default(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("list_users", {"page_size": 5}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["pageSize"] == 5

    @pytest.mark.asyncio
    async def test_fields_projects_list_records(self, mock_context):
        mock_context.fetch.return_value = ok(
            [{"UserID": 1, "FirstName": "Jane", "Email": "j@x.com", "Department": "Eng"}]
        )
        result = await projectworks.execute_action("list_users", {"fields": ["UserID", "Email"]}, mock_context)
        assert result.result.data["users"] == [{"UserID": 1, "Email": "j@x.com"}]


# =============================================================================
# SEARCH (free-text convenience over list endpoints)
# =============================================================================


class TestMatchesQuery:
    def test_case_insensitive_substring(self):
        assert _matches_query({"Name": "Acme Corp"}, "acme", ["Name"])

    def test_no_match(self):
        assert not _matches_query({"Name": "Acme Corp"}, "globex", ["Name"])

    def test_ignores_non_string_and_missing_fields(self):
        assert not _matches_query({"Name": 123, "Other": None}, "1", ["Name", "Other", "Absent"])

    def test_composed_fields_match_multi_word_query(self):
        # "jane doe" matches neither FirstName nor LastName alone, but does match
        # the two joined together.
        record = {"FirstName": "Jane", "LastName": "Doe"}
        assert not _matches_query(record, "jane doe", ["FirstName", "LastName"])
        assert _matches_query(record, "jane doe", ["FirstName", "LastName"], [["FirstName", "LastName"]])


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_filters_client_side_by_name_or_email(self, mock_context):
        mock_context.fetch.return_value = ok(
            [
                {"UserID": 1, "FirstName": "Jane", "LastName": "Doe", "Email": "jane@x.com"},
                {"UserID": 2, "FirstName": "John", "LastName": "Smith", "Email": "john@x.com"},
                {"UserID": 3, "FirstName": "Janet", "LastName": "Roe", "Email": "janet@x.com"},
            ]
        )
        result = await projectworks.execute_action("search_users", {"query": "jan"}, mock_context)
        ids = [u["UserID"] for u in result.result.data["users"]]
        assert ids == [1, 3]

    @pytest.mark.asyncio
    async def test_matches_full_name_across_first_and_last(self, mock_context):
        mock_context.fetch.return_value = ok(
            [
                {"UserID": 1, "FirstName": "Jane", "LastName": "Doe", "Email": "jane@x.com"},
                {"UserID": 2, "FirstName": "John", "LastName": "Smith", "Email": "john@x.com"},
            ]
        )
        result = await projectworks.execute_action("search_users", {"query": "Jane Doe"}, mock_context)
        assert [u["UserID"] for u in result.result.data["users"]] == [1]

    @pytest.mark.asyncio
    async def test_default_scan_page_size(self, mock_context):
        mock_context.fetch.return_value = ok([])
        await projectworks.execute_action("search_users", {"query": "x"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["pageSize"] == DEFAULT_SEARCH_SCAN

    @pytest.mark.asyncio
    async def test_limit_caps_results(self, mock_context):
        mock_context.fetch.return_value = ok([{"UserID": i, "Name": "match"} for i in range(20)])
        result = await projectworks.execute_action("search_users", {"query": "match", "limit": 3}, mock_context)
        assert len(result.result.data["users"]) == 3

    @pytest.mark.asyncio
    async def test_fields_projection_applied(self, mock_context):
        mock_context.fetch.return_value = ok([{"UserID": 1, "Name": "Acme", "Email": "a@x.com"}])
        result = await projectworks.execute_action(
            "search_users", {"query": "acme", "fields": ["UserID"]}, mock_context
        )
        assert result.result.data["users"] == [{"UserID": 1}]

    @pytest.mark.asyncio
    async def test_missing_query_is_validation_error(self, mock_context):
        # `query` is required in the schema, so the framework rejects the call
        # before the handler runs and never hits the API.
        mock_context.fetch.return_value = ok([])
        result = await projectworks.execute_action("search_users", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


class TestSearchClientsAndProjects:
    @pytest.mark.asyncio
    async def test_search_clients_matches_name(self, mock_context):
        mock_context.fetch.return_value = ok([{"ClientID": 1, "Name": "Acme"}, {"ClientID": 2, "Name": "Globex"}])
        result = await projectworks.execute_action("search_clients", {"query": "glob"}, mock_context)
        assert [c["ClientID"] for c in result.result.data["clients"]] == [2]
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Clients"

    @pytest.mark.asyncio
    async def test_search_projects_matches_number(self, mock_context):
        mock_context.fetch.return_value = ok(
            [{"ProjectID": 1, "Name": "Site", "ProjectNumber": "P-100"}, {"ProjectID": 2, "Name": "App"}]
        )
        result = await projectworks.execute_action("search_projects", {"query": "p-100"}, mock_context)
        assert [p["ProjectID"] for p in result.result.data["projects"]] == [1]
        assert mock_context.fetch.call_args.args[0] == f"{BASE_URL}/Projects"
