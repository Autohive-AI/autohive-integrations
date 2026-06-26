import base64
from typing import Any, Dict, List

import aiohttp
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

projectworks = Integration.load()

BASE_URL = "https://api.projectworksapp.com/api/v1"

# Time-cap for direct file downloads so a stalled download fails cleanly.
_FILE_DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=25)


async def _resolve_file_bytes(file_obj: Dict[str, Any]) -> bytes:
    """Resolve raw bytes from an Autohive file object.

    The platform attaches files as an object carrying either base64 ``content``
    or a pre-signed ``url``. We return the raw bytes so the caller can re-encode
    them in whatever form the target API expects.
    """
    content_b64 = file_obj.get("content")
    if content_b64:
        try:
            return base64.b64decode(content_b64)
        except Exception:
            raise ValueError("file 'content' is not valid base64-encoded data")

    url = file_obj.get("url")
    if url:
        async with aiohttp.ClientSession(timeout=_FILE_DOWNLOAD_TIMEOUT) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to download file from url: HTTP {resp.status}")
                return await resp.read()

    raise ValueError("file object missing 'content' (base64) or 'url' — attach a receipt file to the expense claim")


async def _apply_expense_file(inputs: Dict[str, Any], body: Dict[str, Any]) -> None:
    """If a ``file`` object is supplied, download/decode it and set the
    ProjectWorks inline attachment fields (``fileName`` + base64 ``fileContent``)."""
    file_obj = inputs.get("file")
    if not file_obj:
        return
    file_bytes = await _resolve_file_bytes(file_obj)
    body["fileContent"] = base64.b64encode(file_bytes).decode("utf-8")
    if not body.get("fileName"):
        body["fileName"] = file_obj.get("name") or "receipt"


def _get_headers(context: ExecutionContext) -> Dict[str, str]:
    creds = context.auth.get("credentials", context.auth)
    consumer_key = creds.get("consumer_key", "")
    consumer_secret = creds.get("consumer_secret", "")
    token = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _check_response(response: Any) -> None:
    if response.status < 200 or response.status >= 300:
        data = response.data
        msg: str
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error") or data.get("title") or str(data)
        else:
            msg = str(data)
        raise RuntimeError(f"ProjectWorks error {response.status}: {msg}")


def _as_list(data: Any) -> List[Any]:
    """ProjectWorks list endpoints return a bare JSON array."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Defensive: some deployments may wrap results.
        for key in ("data", "items", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _as_object(data: Any) -> Dict[str, Any]:
    """Normalise a single-record response to an object.

    Some ProjectWorks single-record endpoints return a one-element array
    (or, on an empty result, a null/empty body) rather than a bare object.
    """
    if isinstance(data, list):
        first = data[0] if data else None
        return first if isinstance(first, dict) else {}
    if isinstance(data, dict):
        return data
    return {}


# Maps an input field name -> ProjectWorks query parameter name.
def _build_params(inputs: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for input_key, param_key in mapping.items():
        value = inputs.get(input_key)
        if value is not None:
            params[param_key] = value
    return params


_PAGINATION = {"page": "page", "page_size": "pageSize"}


async def _list(
    context: ExecutionContext,
    path: str,
    inputs: Dict[str, Any],
    mapping: Dict[str, str],
    result_key: str,
) -> ActionResult:
    params = _build_params(inputs, {**mapping, **_PAGINATION})
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method="GET",
        headers=_get_headers(context),
        params=params,
    )
    _check_response(response)
    return ActionResult(data={result_key: _as_list(response.data)}, cost_usd=0.0)


async def _get(
    context: ExecutionContext,
    path: str,
    result_key: str,
    params: Dict[str, Any] | None = None,
) -> ActionResult:
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method="GET",
        headers=_get_headers(context),
        params=params or {},
    )
    _check_response(response)
    return ActionResult(data={result_key: response.data}, cost_usd=0.0)


async def _write(
    context: ExecutionContext,
    method: str,
    path: str,
    inputs: Dict[str, Any],
    mapping: Dict[str, str],
    result_key: str,
    extra_body: Dict[str, Any] | None = None,
) -> ActionResult:
    """POST/PUT/PATCH a mapped body and return the API's response object."""
    body = _build_params(inputs, mapping)
    if extra_body:
        body.update(extra_body)
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method=method,
        headers=_get_headers(context),
        json=body,
    )
    _check_response(response)
    return ActionResult(data={result_key: response.data}, cost_usd=0.0)


async def _delete(
    context: ExecutionContext,
    path: str,
    deleted_key: str,
    deleted_value: Any,
    params: Dict[str, Any] | None = None,
) -> ActionResult:
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method="DELETE",
        headers=_get_headers(context),
        params=params or {},
    )
    _check_response(response)
    return ActionResult(data={deleted_key: deleted_value, "deleted": True}, cost_usd=0.0)


# =============================================================================
# USERS / EMPLOYEES
# =============================================================================


@projectworks.action("list_users")
class ListUsersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Users",
                inputs,
                {
                    "user_id": "UserID",
                    "email": "Email",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "users",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_user")
class GetUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Users/{inputs['user_id']}", "user")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("list_roles")
class ListRolesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Users/Roles",
                inputs,
                {
                    "role_code": "roleCode",
                },
                "roles",
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# CLIENTS / COMPANIES
# =============================================================================


@projectworks.action("list_clients")
class ListClientsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Clients",
                inputs,
                {
                    "office_id": "OfficeID",
                    "client_id": "ClientID",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "clients",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_client")
class GetClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Clients/{inputs['client_id']}", "client")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# PROJECTS
# =============================================================================


@projectworks.action("list_projects")
class ListProjectsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Projects",
                inputs,
                {
                    "client_id": "ClientID",
                    "project_id": "ProjectID",
                    "user_id": "UserID",
                    "project_number": "ProjectNumber",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "projects",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_project")
class GetProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Projects/{inputs['project_id']}", "project")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# MODULES (project sub-divisions)
# =============================================================================


@projectworks.action("list_modules")
class ListModulesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Modules",
                inputs,
                {
                    "project_id": "ProjectID",
                    "module_id": "ModuleID",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "modules",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_module")
class GetModuleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Modules/{inputs['module_id']}", "module")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# TASKS
# =============================================================================


@projectworks.action("list_tasks")
class ListTasksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Tasks",
                inputs,
                {
                    "project_id": "ProjectID",
                    "module_id": "ModuleID",
                    "task_id": "TaskID",
                    "user_id": "UserID",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "tasks",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_task")
class GetTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Tasks/{inputs['task_id']}", "task")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# RESOURCES / BOOKINGS (resourcing)
# =============================================================================


@projectworks.action("list_resources")
class ListResourcesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Resources",
                inputs,
                {
                    "after_resource_id": "AfterResourceID",
                    "project_id": "ProjectID",
                    "module_id": "ModuleID",
                    "resource_type_id": "ResourceTypeID",
                    "user_id": "UserID",
                    "start_date": "StartDate",
                    "end_date": "EndDate",
                    "mode_id": "ModeID",
                    "level_id": "LevelID",
                    "modified_since_date": "ModifiedSinceDate",
                },
                "resources",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_resource")
class GetResourceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Resources/{inputs['resource_id']}", "resource")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# TIMESHEETS / TIME ENTRIES
# =============================================================================


@projectworks.action("list_timesheets")
class ListTimesheetsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Timesheets",
                inputs,
                {
                    "timesheet_id": "ID",
                    "user_id": "UserID",
                    "task_id": "TaskID",
                    "date": "Date",
                    "comment": "Comment",
                    "user_external_reference": "UserExternalReference",
                    "task_external_reference": "TaskExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "timesheets",
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# LEAVE
# =============================================================================


@projectworks.action("list_leaves")
class ListLeavesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Leaves",
                inputs,
                {
                    "leave_id": "LeaveID",
                    "user_id": "UserID",
                    "type_id": "TypeID",
                    "status_id": "StatusID",
                    "start_date": "StartDate",
                    "end_date": "EndDate",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                },
                "leaves",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_leave")
class GetLeaveAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Leaves/{inputs['leave_id']}", "leave")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("list_leave_types")
class ListLeaveTypesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Leaves/Types",
                inputs,
                {
                    "type_id": "TypeID",
                    "name": "Name",
                    "is_active": "IsActive",
                },
                "leave_types",
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# INVOICES
# =============================================================================


@projectworks.action("list_invoices")
class ListInvoicesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Invoices",
                inputs,
                {
                    "invoice_id": "InvoiceID",
                    "invoice_number": "InvoiceNumber",
                    "client_id": "ClientID",
                    "project_id": "ProjectID",
                    "billing_contact_id": "BillingContactID",
                    "status_id": "StatusID",
                    "start_date": "StartDate",
                    "end_date": "EndDate",
                    "modified_since_date": "ModifiedSinceDate",
                },
                "invoices",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_invoice")
class GetInvoiceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _get(context, f"Invoices/{inputs['invoice_id']}", "invoice")
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# EXPENSE CLAIMS
# =============================================================================


@projectworks.action("list_expense_claims")
class ListExpenseClaimsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "ExpenseClaims",
                inputs,
                {
                    "after_expense_claim_id": "AfterExpenseClaimID",
                    "user_id": "UserID",
                    "client_id": "ClientID",
                    "project_id": "ProjectID",
                    "module_id": "ModuleID",
                    "expense_claim_type_id": "ExpenseClaimTypeID",
                    "expense_claim_status_id": "ExpenseClaimStatusID",
                    "is_reimbursable": "IsReimbursable",
                    "is_billable": "IsBillable",
                    "start_date": "StartDate",
                    "end_date": "EndDate",
                    "invoice_id": "InvoiceID",
                    "modified_since_date": "ModifiedSinceDate",
                    "include_custom_fields": "IncludeCustomFields",
                },
                "expense_claims",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("get_expense_claim")
class GetExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params = {}
            if inputs.get("include_custom_fields") is not None:
                params["includeCustomFields"] = inputs["include_custom_fields"]
            response = await context.fetch(
                f"{BASE_URL}/ExpenseClaims/{inputs['expense_claim_id']}",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
            # The endpoint may return a single-element array rather than a bare object.
            return ActionResult(data={"expense_claim": _as_object(response.data)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# OFFICES
# =============================================================================


@projectworks.action("list_offices")
class ListOfficesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _list(
                context,
                "Offices",
                inputs,
                {
                    "office_id": "OfficeID",
                    "name": "Name",
                    "external_reference": "ExternalReference",
                    "modified_since_date": "ModifiedSinceDate",
                },
                "offices",
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# WRITE ACTIONS — field mappings (snake_case input -> ProjectWorks camelCase)
# =============================================================================

_CLIENT_FIELDS = {
    "client_name": "clientName",
    "account_manager_id": "accountManagerID",
    "office_id": "officeID",
    "currency_id": "currencyID",
    "client_type_id": "clientTypeID",
    "default_rate_card_id": "defaultRateCardID",
    "default_tax_type_id": "defaultTaxTypeID",
    "finance_email": "financeEmail",
    "finance_phone": "financePhone",
    "finance_notes": "financeNotes",
    "is_active": "isActive",
    "company_tax_number": "companyTaxNumber",
    "address": "address",
    "external_reference": "externalReference",
}

_PROJECT_FIELDS = {
    "project_name": "projectName",
    "office_id": "officeID",
    "client_id": "clientID",
    "project_type_id": "projectTypeID",
    "project_status_id": "projectStatusID",
    "currency_id": "currencyID",
    "project_manager_id": "projectManagerID",
    "account_manager_id": "accountManagerID",
    "task_self_service_mode_id": "taskSelfServiceModeID",
    "project_budget_type_id": "projectBudgetTypeID",
    "project_number": "projectNumber",
    "default_rate_card_id": "defaultRateCardID",
    "start_date": "startDate",
    "end_date": "endDate",
    "is_active": "isActive",
    "external_reference": "externalReference",
}

_MODULE_FIELDS = {
    "project_id": "projectID",
    "module_name": "moduleName",
    "budget": "budget",
    "is_services": "isServices",
    "gl_code_id": "glCodeID",
    "is_active": "isActive",
    "fee_type_id": "feeTypeID",
    "external_reference": "externalReference",
}

_TASK_FIELDS = {
    "module_id": "moduleID",
    "task_name": "taskName",
    "task_type_id": "taskTypeID",
    "start_date": "startDate",
    "end_date": "endDate",
    "is_on_timesheet": "isOnTimesheet",
    "is_billable": "isBillable",
    "status_id": "statusID",
    "percent_complete": "percentComplete",
    "fee_type_id": "feeTypeID",
    "fee": "fee",
    "default_rate": "defaultRate",
    "use_default_rate": "useDefaultRate",
    "external_reference": "externalReference",
}

_USER_FIELDS = {
    "email": "email",
    "alternate_email": "alternateEmail",
    "first_name": "firstName",
    "last_name": "lastName",
    "birth_date": "birthDate",
    "gender": "gender",
    "employee_start_date": "employeeStartDate",
    "employee_end_date": "employeeEndDate",
    "is_active": "isActive",
    "external_reference": "externalReference",
}

_LEAVE_FIELDS = {
    "user_id": "userID",
    "status_id": "statusID",
    "days": "days",
    "request_comment": "requestComment",
    "response_comment": "responseComment",
    "is_review_required": "isReviewRequired",
    "external_reference": "externalReference",
}

_EXPENSE_CLAIM_FIELDS = {
    "user_id": "userID",
    "project_id": "projectID",
    "module_id": "moduleID",
    "expense_claim_type_id": "expenseClaimTypeID",
    "expense_claim_status_id": "expenseClaimStatusID",
    "expense_claim_number": "expenseClaimNumber",
    "is_reimbursable": "isReimbursable",
    "is_processed": "isProcessed",
    "date": "date",
    "amount": "amount",
    "currency_id": "currencyID",
    "tax_type_id": "taxTypeID",
    "is_billable": "isBillable",
    "notes": "notes",
    "invoice_description": "invoiceDescription",
    "quantity": "quantity",
}

_TIMESHEET_CREATE_FIELDS = {
    "user_id": "userID",
    "task_id": "taskID",
    "date": "date",
    "minutes": "minutes",
    "comment": "comment",
    "is_reviewed": "isReviewed",
}

_TIMESHEET_UPDATE_FIELDS = {
    "timesheet_id": "id",
    "user_id": "userID",
    "task_id": "taskID",
    "date": "date",
    "minutes": "minutes",
    "comment": "comment",
    "is_reviewed": "isReviewed",
}


# =============================================================================
# CLIENTS — write
# =============================================================================


@projectworks.action("create_client")
class CreateClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Clients", inputs, _CLIENT_FIELDS, "client")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_client")
class UpdateClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PATCH", f"Clients/{inputs['client_id']}", inputs, _CLIENT_FIELDS, "client")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_client")
class DeleteClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Clients/{inputs['client_id']}", "client_id", inputs["client_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# PROJECTS — write
# =============================================================================


@projectworks.action("create_project")
class CreateProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Projects", inputs, _PROJECT_FIELDS, "project")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_project")
class UpdateProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(
                context, "PATCH", f"Projects/{inputs['project_id']}", inputs, _PROJECT_FIELDS, "project"
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_project")
class DeleteProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Projects/{inputs['project_id']}", "project_id", inputs["project_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# MODULES — write
# =============================================================================


@projectworks.action("create_module")
class CreateModuleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Modules", inputs, _MODULE_FIELDS, "module")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_module")
class UpdateModuleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PATCH", f"Modules/{inputs['module_id']}", inputs, _MODULE_FIELDS, "module")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_module")
class DeleteModuleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Modules/{inputs['module_id']}", "module_id", inputs["module_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# TASKS — write
# =============================================================================


@projectworks.action("create_task")
class CreateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Tasks", inputs, _TASK_FIELDS, "task")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task")
class UpdateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PATCH", f"Tasks/{inputs['task_id']}", inputs, _TASK_FIELDS, "task")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_task")
class DeleteTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Tasks/{inputs['task_id']}", "task_id", inputs["task_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# USERS — write
# =============================================================================


@projectworks.action("create_user")
class CreateUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Users", inputs, _USER_FIELDS, "user")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_user")
class UpdateUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PATCH", f"Users/{inputs['user_id']}", inputs, _USER_FIELDS, "user")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_user")
class DeleteUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Users/{inputs['user_id']}", "user_id", inputs["user_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# LEAVE — write (PUT replaces the full record)
# =============================================================================


@projectworks.action("create_leave")
class CreateLeaveAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Leaves", inputs, _LEAVE_FIELDS, "leave")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_leave")
class UpdateLeaveAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PUT", f"Leaves/{inputs['leave_id']}", inputs, _LEAVE_FIELDS, "leave")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_leave")
class DeleteLeaveAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(context, f"Leaves/{inputs['leave_id']}", "leave_id", inputs["leave_id"])
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# EXPENSE CLAIMS — write (PUT replaces the full record)
# =============================================================================


async def _write_expense_claim(
    context: ExecutionContext, method: str, path: str, inputs: Dict[str, Any]
) -> ActionResult:
    """Build the expense-claim body, attach the receipt file if supplied, and send it."""
    body = _build_params(inputs, _EXPENSE_CLAIM_FIELDS)
    await _apply_expense_file(inputs, body)
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method=method,
        headers=_get_headers(context),
        json=body,
    )
    _check_response(response)
    return ActionResult(data={"expense_claim": response.data}, cost_usd=0.0)


@projectworks.action("create_expense_claim")
class CreateExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write_expense_claim(context, "POST", "ExpenseClaims", inputs)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_expense_claim")
class UpdateExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write_expense_claim(context, "PUT", f"ExpenseClaims/{inputs['expense_claim_id']}", inputs)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_expense_claim")
class DeleteExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(
                context,
                f"ExpenseClaims/{inputs['expense_claim_id']}",
                "expense_claim_id",
                inputs["expense_claim_id"],
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# TIMESHEETS — write (collection-level id, no path segment)
# =============================================================================


@projectworks.action("create_timesheet")
class CreateTimesheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "POST", "Timesheets", inputs, _TIMESHEET_CREATE_FIELDS, "timesheet")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_timesheet")
class UpdateTimesheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(context, "PUT", "Timesheets", inputs, _TIMESHEET_UPDATE_FIELDS, "timesheet")
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("delete_timesheet")
class DeleteTimesheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _delete(
                context, "Timesheets", "timesheet_id", inputs["timesheet_id"], params={"id": inputs["timesheet_id"]}
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# WRITE — SUB-RESOURCES (project/task assignments, roles, balances, postings)
# =============================================================================

_PROJECT_USER_FIELDS = {
    "user_id": "userID",
    "rate_card_id": "rateCardID",
    "rate": "rate",
    "cost_rate_card_id": "costRateCardID",
}

_TASK_USER_FIELDS = {
    "user_id": "userID",
    "hours": "hours",
    "rate_card_id": "rateCardID",
    "rate": "rate",
    "cost_rate_card_id": "costRateCardID",
    "is_active": "isActive",
    "is_pinned": "isPinned",
}

_TASK_PLACEHOLDER_FIELDS = {
    "placeholder_id": "placeholderID",
    "role_id": "roleID",
    "hours": "hours",
    "rate_card_id": "rateCardID",
    "rate": "rate",
    "is_active": "isActive",
    "is_pinned": "isPinned",
}

_USER_POSTING_FIELDS = {
    "start_date": "startDate",
    "end_date": "endDate",
    "is_billable": "isBillable",
    "recoverable": "recoverable",
    "rate": "rate",
    "office_id": "officeID",
    "location_id": "locationID",
    "team_id": "teamID",
    "position_id": "positionID",
    "rank_id": "rankID",
    "agreement_type_id": "agreementTypeID",
    "holiday_calendar_id": "holidayCalendarID",
    "manager_id": "managerID",
    "currency_id": "currencyID",
    "capacity_days": "capacityDays",
}

# entity_type input -> URL path segment for the custom-fields endpoints.
_FIELDS_ENTITY_PATHS = {
    "client": "Clients",
    "project": "Projects",
    "module": "Modules",
    "task": "Tasks",
    "user": "Users",
}


@projectworks.action("update_project_user")
class UpdateProjectUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(
                context,
                "PUT",
                f"Projects/{inputs['project_id']}/Users",
                inputs,
                _PROJECT_USER_FIELDS,
                "project_user",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task_user")
class UpdateTaskUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(
                context, "PUT", f"Tasks/{inputs['task_id']}/Users", inputs, _TASK_USER_FIELDS, "task_user"
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task_placeholder")
class UpdateTaskPlaceholderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(
                context,
                "PUT",
                f"Tasks/{inputs['task_id']}/Placeholders",
                inputs,
                _TASK_PLACEHOLDER_FIELDS,
                "placeholder",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_user_roles")
class UpdateUserRolesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            user_id = inputs["user_id"]
            role_ids = inputs["user_role_ids"]
            response = await context.fetch(
                f"{BASE_URL}/Users/{user_id}/Roles",
                method="PUT",
                headers=_get_headers(context),
                json={"userRoleIDs": role_ids},
            )
            _check_response(response)
            # The endpoint returns an empty 200 body, so echo the applied state.
            return ActionResult(data={"user_id": user_id, "user_role_ids": role_ids, "updated": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_user_leave_balances")
class UpdateUserLeaveBalancesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            user_id = inputs["user_id"]
            balances = inputs["balances"]
            response = await context.fetch(
                f"{BASE_URL}/Users/{user_id}/LeaveBalances",
                method="PUT",
                headers=_get_headers(context),
                json={"balances": balances},
            )
            _check_response(response)
            # The endpoint returns an empty 200 body, so echo the applied state.
            return ActionResult(data={"user_id": user_id, "balances": balances, "updated": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_user_postings")
class UpdateUserPostingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _write(
                context,
                "PUT",
                f"Users/{inputs['user_id']}/Postings",
                inputs,
                _USER_POSTING_FIELDS,
                "posting",
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("set_custom_fields")
class SetCustomFieldsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            segment = _FIELDS_ENTITY_PATHS.get(inputs["entity_type"])
            if segment is None:
                return ActionError(message=f"Unknown entity_type: {inputs['entity_type']}")
            entity_id = inputs["entity_id"]
            response = await context.fetch(
                f"{BASE_URL}/{segment}/{entity_id}/Fields",
                method="PUT",
                headers=_get_headers(context),
                json=inputs["fields"],
            )
            _check_response(response)
            return ActionResult(data={"entity_id": entity_id, "updated": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
