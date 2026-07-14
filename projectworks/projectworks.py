import base64
from typing import Any, Dict, List

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

projectworks = Integration.load()

BASE_URL = "https://api.projectworksapp.com/api/v1"

# Cap an unparameterised list call so it cannot dump hundreds of full records
# into a consuming LLM's context window. Callers can still page explicitly.
DEFAULT_PAGE_SIZE = 50

# search_* actions scan a single page client-side; this is how many records that
# page holds (larger than DEFAULT_PAGE_SIZE so a free-text scan has more to match
# against) and how many matches are returned by default.
DEFAULT_SEARCH_SCAN = 200
DEFAULT_SEARCH_LIMIT = 10


def _resolve_file_bytes(file_obj: Dict[str, Any]) -> bytes:
    """Resolve raw bytes from a standard Autohive file object.

    Files are attached as an object carrying base64 ``content``. We deliberately
    do not fetch arbitrary caller-supplied URLs here: downloading from the
    integration runtime would expose an SSRF vector and let unbounded responses
    be buffered and base64-expanded in memory.
    """
    content_b64 = file_obj.get("content")
    if not content_b64:
        raise ValueError("file object missing 'content' (base64) — attach a receipt file to the expense claim")
    try:
        return base64.b64decode(content_b64)
    except Exception:
        raise ValueError("file 'content' is not valid base64-encoded data")


def _get_headers(context: ExecutionContext) -> Dict[str, str]:
    creds = context.auth.get("credentials", context.auth)
    consumer_key = creds.get("consumer_key", "")
    consumer_secret = creds.get("consumer_secret", "")
    # Guard at runtime rather than via auth.fields.required: the config stays
    # compatible with whatever shape the platform passes, while a missing/blank
    # credential fails with a clear message instead of an unauthenticated request.
    if not consumer_key or not consumer_secret:
        raise ValueError("Projectworks Consumer Key and Consumer Secret are required")
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
        raise RuntimeError(f"Projectworks error {response.status}: {msg}")


def _as_list(data: Any) -> List[Any]:
    """Projectworks list endpoints return a bare JSON array."""
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

    Some Projectworks single-record endpoints return a one-element array
    (or, on an empty result, a null/empty body) rather than a bare object.
    """
    if isinstance(data, list):
        first = data[0] if data else None
        return first if isinstance(first, dict) else {}
    if isinstance(data, dict):
        return data
    return {}


def _clean(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys whose value is None so unset inputs are not sent to the API.

    Falsy-but-meaningful values (``False``, ``0``, ``""``) are preserved.
    """
    return {k: v for k, v in d.items() if v is not None}


def _project(records: List[Any], fields: Any) -> List[Any]:
    """Trim each record down to the requested field names.

    ``fields`` is an optional list of API response keys (PascalCase, e.g.
    ``["UserID", "FirstName", "Email"]``). When omitted, records pass through
    unchanged. This lets a caller keep list payloads small for a consuming LLM's
    context window and fall back to the matching ``get_*`` action for the full
    record once a row of interest is identified. Unknown keys are simply absent.
    """
    if not fields:
        return records
    wanted = set(fields)
    return [{k: v for k, v in r.items() if k in wanted} if isinstance(r, dict) else r for r in records]


async def _list(
    context: ExecutionContext,
    path: str,
    result_key: str,
    params: Dict[str, Any],
    fields: Any = None,
) -> ActionResult:
    # Apply a conservative default page size so a filter-less call stays small.
    if params.get("pageSize") is None:
        params["pageSize"] = DEFAULT_PAGE_SIZE
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method="GET",
        headers=_get_headers(context),
        params=_clean(params),
    )
    _check_response(response)
    return ActionResult(data={result_key: _project(_as_list(response.data), fields)}, cost_usd=0.0)


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
    context: ExecutionContext, method: str, path: str, result_key: str, body: Dict[str, Any]
) -> ActionResult:
    """POST/PUT/PATCH a body (None values dropped) and return the API's response object."""
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method=method,
        headers=_get_headers(context),
        json=_clean(body),
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


def _matches_query(
    record: Dict[str, Any],
    query: str,
    search_fields: List[str],
    composed_fields: List[List[str]] | None = None,
) -> bool:
    q = query.casefold()
    for field in search_fields:
        value = record.get(field)
        if isinstance(value, str) and q in value.casefold():
            return True
    # composed_fields lets a multi-word query (e.g. "Jane Doe") match against
    # several fields joined together (e.g. FirstName + LastName), which no single
    # field would satisfy on its own.
    for group in composed_fields or []:
        joined = " ".join(v for v in (record.get(f) for f in group) if isinstance(v, str))
        if joined and q in joined.casefold():
            return True
    return False


async def _search(
    context: ExecutionContext,
    path: str,
    result_key: str,
    query: str,
    search_fields: List[str],
    limit: Any = None,
    page: Any = None,
    page_size: Any = None,
    fields: Any = None,
    composed_fields: List[List[str]] | None = None,
) -> ActionResult:
    """Free-text convenience search over a list endpoint.

    Projectworks exposes only structured (exact) list filters, so this scans one
    page of records and matches ``query`` case-insensitively as a substring
    against ``search_fields`` (and any ``composed_fields`` groups joined with a
    space), returning at most ``limit`` lean results. It is a convenience layer
    over ``list_*`` for "find the X called ..." flows — for exhaustive
    enumeration use the matching ``list_*`` action with explicit filters and
    pagination.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be blank")
    params = {
        "page": page,
        "pageSize": page_size or DEFAULT_SEARCH_SCAN,
    }
    response = await context.fetch(
        f"{BASE_URL}/{path}",
        method="GET",
        headers=_get_headers(context),
        params=_clean(params),
    )
    _check_response(response)
    cap = limit or DEFAULT_SEARCH_LIMIT
    matched = [
        r
        for r in _as_list(response.data)
        if isinstance(r, dict) and _matches_query(r, query, search_fields, composed_fields)
    ]
    return ActionResult(data={result_key: _project(matched[:cap], fields)}, cost_usd=0.0)


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
                "users",
                {
                    "UserID": inputs.get("user_id"),
                    "Email": inputs.get("email"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "roles",
                {
                    "roleCode": inputs.get("role_code"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "clients",
                {
                    "OfficeID": inputs.get("office_id"),
                    "ClientID": inputs.get("client_id"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "projects",
                {
                    "ClientID": inputs.get("client_id"),
                    "ProjectID": inputs.get("project_id"),
                    "UserID": inputs.get("user_id"),
                    "ProjectNumber": inputs.get("project_number"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "modules",
                {
                    "ProjectID": inputs.get("project_id"),
                    "ModuleID": inputs.get("module_id"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "tasks",
                {
                    "ProjectID": inputs.get("project_id"),
                    "ModuleID": inputs.get("module_id"),
                    "TaskID": inputs.get("task_id"),
                    "UserID": inputs.get("user_id"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "resources",
                {
                    "AfterResourceID": inputs.get("after_resource_id"),
                    "ProjectID": inputs.get("project_id"),
                    "ModuleID": inputs.get("module_id"),
                    "ResourceTypeID": inputs.get("resource_type_id"),
                    "UserID": inputs.get("user_id"),
                    "StartDate": inputs.get("start_date"),
                    "EndDate": inputs.get("end_date"),
                    "ModeID": inputs.get("mode_id"),
                    "LevelID": inputs.get("level_id"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "timesheets",
                {
                    "ID": inputs.get("timesheet_id"),
                    "UserID": inputs.get("user_id"),
                    "TaskID": inputs.get("task_id"),
                    "Date": inputs.get("date"),
                    "Comment": inputs.get("comment"),
                    "UserExternalReference": inputs.get("user_external_reference"),
                    "TaskExternalReference": inputs.get("task_external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "leaves",
                {
                    "LeaveID": inputs.get("leave_id"),
                    "UserID": inputs.get("user_id"),
                    "TypeID": inputs.get("type_id"),
                    "StatusID": inputs.get("status_id"),
                    "StartDate": inputs.get("start_date"),
                    "EndDate": inputs.get("end_date"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "leave_types",
                {
                    "TypeID": inputs.get("type_id"),
                    "Name": inputs.get("name"),
                    "IsActive": inputs.get("is_active"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "invoices",
                {
                    "InvoiceID": inputs.get("invoice_id"),
                    "InvoiceNumber": inputs.get("invoice_number"),
                    "ClientID": inputs.get("client_id"),
                    "ProjectID": inputs.get("project_id"),
                    "BillingContactID": inputs.get("billing_contact_id"),
                    "StatusID": inputs.get("status_id"),
                    "StartDate": inputs.get("start_date"),
                    "EndDate": inputs.get("end_date"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "expense_claims",
                {
                    "AfterExpenseClaimID": inputs.get("after_expense_claim_id"),
                    "UserID": inputs.get("user_id"),
                    "ClientID": inputs.get("client_id"),
                    "ProjectID": inputs.get("project_id"),
                    "ModuleID": inputs.get("module_id"),
                    "ExpenseClaimTypeID": inputs.get("expense_claim_type_id"),
                    "ExpenseClaimStatusID": inputs.get("expense_claim_status_id"),
                    "IsReimbursable": inputs.get("is_reimbursable"),
                    "IsBillable": inputs.get("is_billable"),
                    "StartDate": inputs.get("start_date"),
                    "EndDate": inputs.get("end_date"),
                    "InvoiceID": inputs.get("invoice_id"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "IncludeCustomFields": inputs.get("include_custom_fields"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
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
                "offices",
                {
                    "OfficeID": inputs.get("office_id"),
                    "Name": inputs.get("name"),
                    "ExternalReference": inputs.get("external_reference"),
                    "ModifiedSinceDate": inputs.get("modified_since_date"),
                    "page": inputs.get("page"),
                    "pageSize": inputs.get("page_size"),
                },
                fields=inputs.get("fields"),
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# SEARCH (free-text convenience over list endpoints)
# =============================================================================


@projectworks.action("search_users")
class SearchUsersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _search(
                context,
                "Users",
                "users",
                inputs["query"],
                ["FirstName", "LastName", "Name", "Email"],
                limit=inputs.get("limit"),
                page=inputs.get("page"),
                page_size=inputs.get("page_size"),
                fields=inputs.get("fields"),
                composed_fields=[["FirstName", "LastName"]],
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("search_clients")
class SearchClientsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _search(
                context,
                "Clients",
                "clients",
                inputs["query"],
                ["Name", "ClientName"],
                limit=inputs.get("limit"),
                page=inputs.get("page"),
                page_size=inputs.get("page_size"),
                fields=inputs.get("fields"),
            )
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("search_projects")
class SearchProjectsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _search(
                context,
                "Projects",
                "projects",
                inputs["query"],
                ["Name", "ProjectName", "ProjectNumber"],
                limit=inputs.get("limit"),
                page=inputs.get("page"),
                page_size=inputs.get("page_size"),
                fields=inputs.get("fields"),
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# CLIENTS — write
# =============================================================================


@projectworks.action("create_client")
class CreateClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "clientName": inputs["client_name"],
                "accountManagerID": inputs["account_manager_id"],
                "officeID": inputs["office_id"],
                "currencyID": inputs.get("currency_id"),
                "clientTypeID": inputs.get("client_type_id"),
                "defaultRateCardID": inputs.get("default_rate_card_id"),
                "defaultTaxTypeID": inputs.get("default_tax_type_id"),
                "financeEmail": inputs.get("finance_email"),
                "financePhone": inputs.get("finance_phone"),
                "financeNotes": inputs.get("finance_notes"),
                "isActive": inputs.get("is_active"),
                "companyTaxNumber": inputs.get("company_tax_number"),
                "address": inputs.get("address"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Clients", "client", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_client")
class UpdateClientAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "clientName": inputs.get("client_name"),
                "accountManagerID": inputs.get("account_manager_id"),
                "officeID": inputs.get("office_id"),
                "currencyID": inputs.get("currency_id"),
                "clientTypeID": inputs.get("client_type_id"),
                "defaultRateCardID": inputs.get("default_rate_card_id"),
                "defaultTaxTypeID": inputs.get("default_tax_type_id"),
                "financeEmail": inputs.get("finance_email"),
                "financePhone": inputs.get("finance_phone"),
                "financeNotes": inputs.get("finance_notes"),
                "isActive": inputs.get("is_active"),
                "companyTaxNumber": inputs.get("company_tax_number"),
                "address": inputs.get("address"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PATCH", f"Clients/{inputs['client_id']}", "client", body)
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
            body = {
                "projectName": inputs["project_name"],
                "officeID": inputs["office_id"],
                "clientID": inputs["client_id"],
                "projectTypeID": inputs["project_type_id"],
                "projectStatusID": inputs["project_status_id"],
                "currencyID": inputs["currency_id"],
                "projectManagerID": inputs["project_manager_id"],
                "accountManagerID": inputs["account_manager_id"],
                "taskSelfServiceModeID": inputs["task_self_service_mode_id"],
                "projectBudgetTypeID": inputs.get("project_budget_type_id"),
                "projectNumber": inputs.get("project_number"),
                "defaultRateCardID": inputs.get("default_rate_card_id"),
                "startDate": inputs.get("start_date"),
                "endDate": inputs.get("end_date"),
                "isActive": inputs.get("is_active"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Projects", "project", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_project")
class UpdateProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "projectName": inputs.get("project_name"),
                "officeID": inputs.get("office_id"),
                "clientID": inputs.get("client_id"),
                "projectTypeID": inputs.get("project_type_id"),
                "projectStatusID": inputs.get("project_status_id"),
                "currencyID": inputs.get("currency_id"),
                "projectManagerID": inputs.get("project_manager_id"),
                "accountManagerID": inputs.get("account_manager_id"),
                "taskSelfServiceModeID": inputs.get("task_self_service_mode_id"),
                "projectBudgetTypeID": inputs.get("project_budget_type_id"),
                "projectNumber": inputs.get("project_number"),
                "defaultRateCardID": inputs.get("default_rate_card_id"),
                "startDate": inputs.get("start_date"),
                "endDate": inputs.get("end_date"),
                "isActive": inputs.get("is_active"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PATCH", f"Projects/{inputs['project_id']}", "project", body)
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
            body = {
                "projectID": inputs["project_id"],
                "moduleName": inputs["module_name"],
                "budget": inputs.get("budget"),
                "isServices": inputs.get("is_services"),
                "glCodeID": inputs.get("gl_code_id"),
                "isActive": inputs.get("is_active"),
                "feeTypeID": inputs.get("fee_type_id"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Modules", "module", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_module")
class UpdateModuleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "projectID": inputs.get("project_id"),
                "moduleName": inputs.get("module_name"),
                "budget": inputs.get("budget"),
                "isServices": inputs.get("is_services"),
                "glCodeID": inputs.get("gl_code_id"),
                "isActive": inputs.get("is_active"),
                "feeTypeID": inputs.get("fee_type_id"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PATCH", f"Modules/{inputs['module_id']}", "module", body)
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
            body = {
                "moduleID": inputs["module_id"],
                "taskName": inputs["task_name"],
                "taskTypeID": inputs.get("task_type_id"),
                "startDate": inputs.get("start_date"),
                "endDate": inputs.get("end_date"),
                "isOnTimesheet": inputs.get("is_on_timesheet"),
                "isBillable": inputs.get("is_billable"),
                "statusID": inputs.get("status_id"),
                "percentComplete": inputs.get("percent_complete"),
                "feeTypeID": inputs.get("fee_type_id"),
                "fee": inputs.get("fee"),
                "defaultRate": inputs.get("default_rate"),
                "useDefaultRate": inputs.get("use_default_rate"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Tasks", "task", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task")
class UpdateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "moduleID": inputs.get("module_id"),
                "taskName": inputs.get("task_name"),
                "taskTypeID": inputs.get("task_type_id"),
                "startDate": inputs.get("start_date"),
                "endDate": inputs.get("end_date"),
                "isOnTimesheet": inputs.get("is_on_timesheet"),
                "isBillable": inputs.get("is_billable"),
                "statusID": inputs.get("status_id"),
                "percentComplete": inputs.get("percent_complete"),
                "feeTypeID": inputs.get("fee_type_id"),
                "fee": inputs.get("fee"),
                "defaultRate": inputs.get("default_rate"),
                "useDefaultRate": inputs.get("use_default_rate"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PATCH", f"Tasks/{inputs['task_id']}", "task", body)
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
            body = {
                "email": inputs["email"],
                "firstName": inputs["first_name"],
                "lastName": inputs["last_name"],
                "alternateEmail": inputs.get("alternate_email"),
                "birthDate": inputs.get("birth_date"),
                "gender": inputs.get("gender"),
                "employeeStartDate": inputs.get("employee_start_date"),
                "employeeEndDate": inputs.get("employee_end_date"),
                "isActive": inputs.get("is_active"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Users", "user", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_user")
class UpdateUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "email": inputs.get("email"),
                "alternateEmail": inputs.get("alternate_email"),
                "firstName": inputs.get("first_name"),
                "lastName": inputs.get("last_name"),
                "birthDate": inputs.get("birth_date"),
                "gender": inputs.get("gender"),
                "employeeStartDate": inputs.get("employee_start_date"),
                "employeeEndDate": inputs.get("employee_end_date"),
                "isActive": inputs.get("is_active"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PATCH", f"Users/{inputs['user_id']}", "user", body)
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
            body = {
                "userID": inputs["user_id"],
                "statusID": inputs["status_id"],
                "days": inputs["days"],
                "requestComment": inputs.get("request_comment"),
                "responseComment": inputs.get("response_comment"),
                "isReviewRequired": inputs.get("is_review_required"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "POST", "Leaves", "leave", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_leave")
class UpdateLeaveAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "userID": inputs["user_id"],
                "statusID": inputs["status_id"],
                "days": inputs["days"],
                "requestComment": inputs.get("request_comment"),
                "responseComment": inputs.get("response_comment"),
                "isReviewRequired": inputs.get("is_review_required"),
                "externalReference": inputs.get("external_reference"),
            }
            return await _write(context, "PUT", f"Leaves/{inputs['leave_id']}", "leave", body)
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


async def _send_expense_claim(
    context: ExecutionContext, method: str, path: str, body: Dict[str, Any], file_obj: Dict[str, Any] | None
) -> ActionResult:
    """Attach the receipt file (if supplied) inline as base64, then send the claim."""
    if file_obj:
        file_bytes = _resolve_file_bytes(file_obj)
        body["fileContent"] = base64.b64encode(file_bytes).decode("utf-8")
        body["fileName"] = file_obj.get("name") or "receipt"
    return await _write(context, method, path, "expense_claim", body)


@projectworks.action("create_expense_claim")
class CreateExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "userID": inputs["user_id"],
                "projectID": inputs["project_id"],
                "moduleID": inputs["module_id"],
                "expenseClaimTypeID": inputs["expense_claim_type_id"],
                "isReimbursable": inputs["is_reimbursable"],
                "isProcessed": inputs["is_processed"],
                "date": inputs["date"],
                "amount": inputs["amount"],
                "currencyID": inputs["currency_id"],
                "taxTypeID": inputs["tax_type_id"],
                "expenseClaimStatusID": inputs.get("expense_claim_status_id"),
                "expenseClaimNumber": inputs.get("expense_claim_number"),
                "isBillable": inputs.get("is_billable"),
                "notes": inputs.get("notes"),
                "invoiceDescription": inputs.get("invoice_description"),
                "quantity": inputs.get("quantity"),
            }
            return await _send_expense_claim(context, "POST", "ExpenseClaims", body, inputs.get("file"))
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_expense_claim")
class UpdateExpenseClaimAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "userID": inputs["user_id"],
                "projectID": inputs["project_id"],
                "moduleID": inputs["module_id"],
                "expenseClaimTypeID": inputs["expense_claim_type_id"],
                "isReimbursable": inputs["is_reimbursable"],
                "isProcessed": inputs["is_processed"],
                "date": inputs["date"],
                "amount": inputs["amount"],
                "currencyID": inputs["currency_id"],
                "taxTypeID": inputs["tax_type_id"],
                "expenseClaimStatusID": inputs.get("expense_claim_status_id"),
                "expenseClaimNumber": inputs.get("expense_claim_number"),
                "isBillable": inputs.get("is_billable"),
                "notes": inputs.get("notes"),
                "invoiceDescription": inputs.get("invoice_description"),
                "quantity": inputs.get("quantity"),
            }
            path = f"ExpenseClaims/{inputs['expense_claim_id']}"
            return await _send_expense_claim(context, "PUT", path, body, inputs.get("file"))
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
            body = {
                "userID": inputs["user_id"],
                "taskID": inputs["task_id"],
                "date": inputs["date"],
                "minutes": inputs["minutes"],
                "comment": inputs.get("comment"),
                "isReviewed": inputs.get("is_reviewed"),
            }
            return await _write(context, "POST", "Timesheets", "timesheet", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_timesheet")
class UpdateTimesheetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "id": inputs["timesheet_id"],
                "minutes": inputs["minutes"],
                "userID": inputs.get("user_id"),
                "taskID": inputs.get("task_id"),
                "date": inputs.get("date"),
                "comment": inputs.get("comment"),
                "isReviewed": inputs.get("is_reviewed"),
            }
            return await _write(context, "PUT", "Timesheets", "timesheet", body)
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
            body = {
                "userID": inputs["user_id"],
                "rateCardID": inputs.get("rate_card_id"),
                "rate": inputs.get("rate"),
                "costRateCardID": inputs.get("cost_rate_card_id"),
            }
            return await _write(context, "PUT", f"Projects/{inputs['project_id']}/Users", "project_user", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task_user")
class UpdateTaskUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "userID": inputs["user_id"],
                "hours": inputs.get("hours"),
                "rateCardID": inputs.get("rate_card_id"),
                "rate": inputs.get("rate"),
                "costRateCardID": inputs.get("cost_rate_card_id"),
                "isActive": inputs.get("is_active"),
                "isPinned": inputs.get("is_pinned"),
            }
            return await _write(context, "PUT", f"Tasks/{inputs['task_id']}/Users", "task_user", body)
        except Exception as e:
            return ActionError(message=str(e))


@projectworks.action("update_task_placeholder")
class UpdateTaskPlaceholderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "roleID": inputs["role_id"],
                "placeholderID": inputs.get("placeholder_id"),
                "hours": inputs.get("hours"),
                "rateCardID": inputs.get("rate_card_id"),
                "rate": inputs.get("rate"),
                "isActive": inputs.get("is_active"),
                "isPinned": inputs.get("is_pinned"),
            }
            return await _write(context, "PUT", f"Tasks/{inputs['task_id']}/Placeholders", "placeholder", body)
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
            body = {
                "startDate": inputs["start_date"],
                "isBillable": inputs["is_billable"],
                "recoverable": inputs["recoverable"],
                "rate": inputs["rate"],
                "officeID": inputs["office_id"],
                "locationID": inputs["location_id"],
                "teamID": inputs["team_id"],
                "positionID": inputs["position_id"],
                "agreementTypeID": inputs["agreement_type_id"],
                "currencyID": inputs["currency_id"],
                "endDate": inputs.get("end_date"),
                "rankID": inputs.get("rank_id"),
                "holidayCalendarID": inputs.get("holiday_calendar_id"),
                "managerID": inputs.get("manager_id"),
                "capacityDays": inputs.get("capacity_days"),
            }
            return await _write(context, "PUT", f"Users/{inputs['user_id']}/Postings", "posting", body)
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
