from typing import Any, Dict

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

# Create the integration using the config.json
freshsales = Integration.load()

# Maps user-facing entity names to Freshsales API path segments.
ENTITY_PATHS = {"contacts": "contacts", "accounts": "sales_accounts", "deals": "deals"}


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Freshsales API requests.
    Freshsales uses token auth: 'Authorization: Token token=API_KEY'.
    """
    api_key = context.auth["credentials"].get("api_key", "")
    return {"Authorization": f"Token token={api_key}", "Content-Type": "application/json"}


def get_base_url(context: ExecutionContext) -> str:
    """
    Construct the base URL for Freshsales API requests from the bundle alias.

    Tolerates a pasted full domain ('https://acme.myfreshworks.com/') by
    stripping the protocol, path, and domain suffix down to the bare alias.
    """
    alias = context.auth["credentials"].get("bundle_alias", "").strip()
    alias = alias.removeprefix("https://").removeprefix("http://")
    alias = alias.split("/")[0].split(".")[0]
    return f"https://{alias}.myfreshworks.com/crm/sales/api"


async def resolve_view_id(context: ExecutionContext, resource: str) -> int:
    """
    Return the id of the default 'All ...' view for a resource.

    Freshsales has no plain list endpoint — records are listed through views.
    Falls back to the first available view when no 'All ...' view exists.
    """
    headers = get_auth_headers(context)
    base_url = get_base_url(context)
    response = await context.fetch(f"{base_url}/{resource}/filters", method="GET", headers=headers)
    views = response.data.get("filters", [])
    if not views:
        raise ValueError(f"No list views available for {resource}")
    for view in views:
        if view.get("name", "").lower().startswith("all "):
            return view["id"]
    return views[0]["id"]


# ---- Action Handlers ----


@freshsales.action("list_views")
class ListViewsAction(ActionHandler):
    """List the available list views (filters) for contacts, accounts, or deals."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            resource = ENTITY_PATHS[inputs["entity"]]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/{resource}/filters", method="GET", headers=headers)
            views = response.data.get("filters", [])
            return ActionResult(data={"views": views, "total": len(views)})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_contact")
class CreateContactAction(ActionHandler):
    """Create a new contact. Requires first_name or last_name plus email or mobile_number."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "first_name": inputs.get("first_name"),
                    "last_name": inputs.get("last_name"),
                    "email": inputs.get("email"),
                    "mobile_number": inputs.get("mobile_number"),
                    "work_number": inputs.get("work_number"),
                    "job_title": inputs.get("job_title"),
                    "address": inputs.get("address"),
                    "city": inputs.get("city"),
                    "state": inputs.get("state"),
                    "zipcode": inputs.get("zipcode"),
                    "country": inputs.get("country"),
                    "owner_id": inputs.get("owner_id"),
                    "sales_account_id": inputs.get("sales_account_id"),
                    "territory_id": inputs.get("territory_id"),
                    "lead_source_id": inputs.get("lead_source_id"),
                    "medium": inputs.get("medium"),
                    "keyword": inputs.get("keyword"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts", method="POST", headers=headers, json={"contact": body}
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_contact")
class GetContactAction(ActionHandler):
    """Retrieve a contact by ID, optionally embedding related records via `include`."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_contact")
class UpdateContactAction(ActionHandler):
    """Update fields on an existing contact. Only provided fields are changed."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "first_name": inputs.get("first_name"),
                    "last_name": inputs.get("last_name"),
                    "email": inputs.get("email"),
                    "mobile_number": inputs.get("mobile_number"),
                    "work_number": inputs.get("work_number"),
                    "job_title": inputs.get("job_title"),
                    "address": inputs.get("address"),
                    "city": inputs.get("city"),
                    "state": inputs.get("state"),
                    "zipcode": inputs.get("zipcode"),
                    "country": inputs.get("country"),
                    "owner_id": inputs.get("owner_id"),
                    "sales_account_id": inputs.get("sales_account_id"),
                    "territory_id": inputs.get("territory_id"),
                    "lead_source_id": inputs.get("lead_source_id"),
                    "medium": inputs.get("medium"),
                    "keyword": inputs.get("keyword"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="PUT", headers=headers, json={"contact": body}
            )
            return ActionResult(data={"contact": response.data.get("contact", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_contact")
class DeleteContactAction(ActionHandler):
    """Delete a contact by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/{inputs['contact_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "contact_id": inputs["contact_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_contacts")
class ListContactsAction(ActionHandler):
    """List contacts from a view, auto-resolving the 'All Contacts' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id")
            if view_id is None:
                view_id = await resolve_view_id(context, "contacts")
            params = {"page": inputs.get("page", 1)}
            for param, value in {
                "sort": inputs.get("sort"),
                "sort_type": inputs.get("sort_type"),
                "include": inputs.get("include"),
            }.items():
                if value:
                    params[param] = value
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/contacts/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(
                data={"contacts": response.data.get("contacts", []), "meta": response.data.get("meta", {})}
            )
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_account")
class CreateAccountAction(ActionHandler):
    """Create a new sales account (organization)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "name": inputs["name"],
                    "website": inputs.get("website"),
                    "phone": inputs.get("phone"),
                    "address": inputs.get("address"),
                    "city": inputs.get("city"),
                    "state": inputs.get("state"),
                    "zipcode": inputs.get("zipcode"),
                    "country": inputs.get("country"),
                    "industry_type_id": inputs.get("industry_type_id"),
                    "business_type_id": inputs.get("business_type_id"),
                    "number_of_employees": inputs.get("number_of_employees"),
                    "annual_revenue": inputs.get("annual_revenue"),
                    "owner_id": inputs.get("owner_id"),
                    "territory_id": inputs.get("territory_id"),
                    "parent_sales_account_id": inputs.get("parent_sales_account_id"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts", method="POST", headers=headers, json={"sales_account": body}
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_account")
class GetAccountAction(ActionHandler):
    """Retrieve a sales account by ID, optionally embedding related records."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_account")
class UpdateAccountAction(ActionHandler):
    """Update fields on an existing sales account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "name": inputs.get("name"),
                    "website": inputs.get("website"),
                    "phone": inputs.get("phone"),
                    "address": inputs.get("address"),
                    "city": inputs.get("city"),
                    "state": inputs.get("state"),
                    "zipcode": inputs.get("zipcode"),
                    "country": inputs.get("country"),
                    "industry_type_id": inputs.get("industry_type_id"),
                    "business_type_id": inputs.get("business_type_id"),
                    "number_of_employees": inputs.get("number_of_employees"),
                    "annual_revenue": inputs.get("annual_revenue"),
                    "owner_id": inputs.get("owner_id"),
                    "territory_id": inputs.get("territory_id"),
                    "parent_sales_account_id": inputs.get("parent_sales_account_id"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}",
                method="PUT",
                headers=headers,
                json={"sales_account": body},
            )
            return ActionResult(data={"account": response.data.get("sales_account", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_account")
class DeleteAccountAction(ActionHandler):
    """Delete a sales account by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/{inputs['account_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "account_id": inputs["account_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_accounts")
class ListAccountsAction(ActionHandler):
    """List sales accounts from a view, auto-resolving the 'All Accounts' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id")
            if view_id is None:
                view_id = await resolve_view_id(context, "sales_accounts")
            params = {"page": inputs.get("page", 1)}
            for param, value in {
                "sort": inputs.get("sort"),
                "sort_type": inputs.get("sort_type"),
                "include": inputs.get("include"),
            }.items():
                if value:
                    params[param] = value
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/sales_accounts/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(
                data={"accounts": response.data.get("sales_accounts", []), "meta": response.data.get("meta", {})}
            )
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_deal")
class CreateDealAction(ActionHandler):
    """Create a new deal. Name and amount are required."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "name": inputs["name"],
                    "amount": inputs["amount"],
                    "sales_account_id": inputs.get("sales_account_id"),
                    "deal_stage_id": inputs.get("deal_stage_id"),
                    "deal_pipeline_id": inputs.get("deal_pipeline_id"),
                    "deal_type_id": inputs.get("deal_type_id"),
                    "lead_source_id": inputs.get("lead_source_id"),
                    "owner_id": inputs.get("owner_id"),
                    "expected_close": inputs.get("expected_close"),
                    "probability": inputs.get("probability"),
                    "currency_id": inputs.get("currency_id"),
                    "territory_id": inputs.get("territory_id"),
                    "campaign_id": inputs.get("campaign_id"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/deals", method="POST", headers=headers, json={"deal": body})
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_deal")
class GetDealAction(ActionHandler):
    """Retrieve a deal by ID, optionally embedding related records."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/{inputs['deal_id']}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_deal")
class UpdateDealAction(ActionHandler):
    """Update fields on an existing deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "name": inputs.get("name"),
                    "amount": inputs.get("amount"),
                    "sales_account_id": inputs.get("sales_account_id"),
                    "deal_stage_id": inputs.get("deal_stage_id"),
                    "deal_pipeline_id": inputs.get("deal_pipeline_id"),
                    "deal_type_id": inputs.get("deal_type_id"),
                    "lead_source_id": inputs.get("lead_source_id"),
                    "owner_id": inputs.get("owner_id"),
                    "expected_close": inputs.get("expected_close"),
                    "probability": inputs.get("probability"),
                    "currency_id": inputs.get("currency_id"),
                    "territory_id": inputs.get("territory_id"),
                    "campaign_id": inputs.get("campaign_id"),
                    "custom_field": inputs.get("custom_field"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/{inputs['deal_id']}", method="PUT", headers=headers, json={"deal": body}
            )
            return ActionResult(data={"deal": response.data.get("deal", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_deal")
class DeleteDealAction(ActionHandler):
    """Delete a deal by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/deals/{inputs['deal_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "deal_id": inputs["deal_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_deals")
class ListDealsAction(ActionHandler):
    """List deals from a view, auto-resolving the 'All Deals' view when none is given."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            view_id = inputs.get("view_id")
            if view_id is None:
                view_id = await resolve_view_id(context, "deals")
            params = {"page": inputs.get("page", 1)}
            for param, value in {
                "sort": inputs.get("sort"),
                "sort_type": inputs.get("sort_type"),
                "include": inputs.get("include"),
            }.items():
                if value:
                    params[param] = value
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/deals/view/{view_id}", method="GET", headers=headers, params=params
            )
            return ActionResult(data={"deals": response.data.get("deals", []), "meta": response.data.get("meta", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a task attached to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "title": inputs["title"],
                    "description": inputs.get("description"),
                    "due_date": inputs["due_date"],
                    "owner_id": inputs.get("owner_id"),
                    "targetable_type": inputs["targetable_type"],
                    "targetable_id": inputs["targetable_id"],
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks", method="POST", headers=headers, json={"task": body})
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_task")
class GetTaskAction(ActionHandler):
    """Retrieve a task by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks/{inputs['task_id']}", method="GET", headers=headers)
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update fields on an existing task; set status=1 to mark it done."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "title": inputs.get("title"),
                    "description": inputs.get("description"),
                    "due_date": inputs.get("due_date"),
                    "owner_id": inputs.get("owner_id"),
                    "targetable_type": inputs.get("targetable_type"),
                    "targetable_id": inputs.get("targetable_id"),
                    "status": inputs.get("status"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/tasks/{inputs['task_id']}", method="PUT", headers=headers, json={"task": body}
            )
            return ActionResult(data={"task": response.data.get("task", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks/{inputs['task_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "task_id": inputs["task_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List tasks by status filter (open, due_today, due_tomorrow, overdue, completed)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"filter": inputs.get("filter", "open")}
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/tasks", method="GET", headers=headers, params=params)
            return ActionResult(data={"tasks": response.data.get("tasks", [])})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_appointment")
class CreateAppointmentAction(ActionHandler):
    """Schedule an appointment attached to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "title": inputs["title"],
                    "description": inputs.get("description"),
                    "from_date": inputs["from_date"],
                    "end_date": inputs["end_date"],
                    "time_zone": inputs.get("time_zone"),
                    "location": inputs.get("location"),
                    "is_allday": inputs.get("is_allday"),
                    "targetable_type": inputs["targetable_type"],
                    "targetable_id": inputs["targetable_id"],
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments", method="POST", headers=headers, json={"appointment": body}
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("get_appointment")
class GetAppointmentAction(ActionHandler):
    """Retrieve an appointment by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}", method="GET", headers=headers
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_appointment")
class UpdateAppointmentAction(ActionHandler):
    """Update fields on an existing appointment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "title": inputs.get("title"),
                    "description": inputs.get("description"),
                    "from_date": inputs.get("from_date"),
                    "end_date": inputs.get("end_date"),
                    "time_zone": inputs.get("time_zone"),
                    "location": inputs.get("location"),
                    "is_allday": inputs.get("is_allday"),
                    "targetable_type": inputs.get("targetable_type"),
                    "targetable_id": inputs.get("targetable_id"),
                }.items()
                if value is not None
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}",
                method="PUT",
                headers=headers,
                json={"appointment": body},
            )
            return ActionResult(data={"appointment": response.data.get("appointment", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_appointment")
class DeleteAppointmentAction(ActionHandler):
    """Delete an appointment by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/appointments/{inputs['appointment_id']}", method="DELETE", headers=headers
            )
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(
                data={"success": bool(data.get("success", True)), "appointment_id": inputs["appointment_id"]}
            )
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("list_appointments")
class ListAppointmentsAction(ActionHandler):
    """List appointments, optionally filtered to past or upcoming."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("filter"):
                params["filter"] = inputs["filter"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/appointments", method="GET", headers=headers, params=params)
            return ActionResult(data={"appointments": response.data.get("appointments", [])})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("create_note")
class CreateNoteAction(ActionHandler):
    """Attach a note to a contact, sales account, or deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "description": inputs["description"],
                "targetable_type": inputs["targetable_type"],
                "targetable_id": inputs["targetable_id"],
            }
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/notes", method="POST", headers=headers, json={"note": body})
            return ActionResult(data={"note": response.data.get("note", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("update_note")
class UpdateNoteAction(ActionHandler):
    """Update the content of an existing note."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"description": inputs["description"]}
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(
                f"{base_url}/notes/{inputs['note_id']}", method="PUT", headers=headers, json={"note": body}
            )
            return ActionResult(data={"note": response.data.get("note", {})})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("delete_note")
class DeleteNoteAction(ActionHandler):
    """Delete a note by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/notes/{inputs['note_id']}", method="DELETE", headers=headers)
            data = response.data if isinstance(response.data, dict) else {}
            return ActionResult(data={"success": bool(data.get("success", True)), "note_id": inputs["note_id"]})
        except Exception as e:
            return ActionError(message=str(e))


@freshsales.action("search")
class SearchAction(ActionHandler):
    """Search across contacts, sales accounts, and deals."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"q": inputs["query"], "include": inputs.get("include", "contact,sales_account,deal")}
            if inputs.get("per_page"):
                params["per_page"] = inputs["per_page"]
            headers = get_auth_headers(context)
            base_url = get_base_url(context)
            response = await context.fetch(f"{base_url}/search", method="GET", headers=headers, params=params)
            results = response.data if isinstance(response.data, list) else []
            return ActionResult(data={"results": results, "total": len(results)})
        except Exception as e:
            return ActionError(message=str(e))
