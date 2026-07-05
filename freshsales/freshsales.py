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


def build_body(inputs: Dict[str, Any], fields: tuple) -> Dict[str, Any]:
    """Collect the provided (non-None) input fields into a request body dict."""
    return {field: inputs[field] for field in fields if inputs.get(field) is not None}


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


CONTACT_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "mobile_number",
    "work_number",
    "job_title",
    "address",
    "city",
    "state",
    "zipcode",
    "country",
    "owner_id",
    "sales_account_id",
    "territory_id",
    "lead_source_id",
    "medium",
    "keyword",
    "custom_field",
)


@freshsales.action("create_contact")
class CreateContactAction(ActionHandler):
    """Create a new contact. Requires first_name or last_name plus email or mobile_number."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = build_body(inputs, CONTACT_FIELDS)
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
            body = build_body(inputs, CONTACT_FIELDS)
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
            view_id = inputs.get("view_id") or await resolve_view_id(context, "contacts")
            params = {"page": inputs.get("page", 1)}
            for param in ("sort", "sort_type", "include"):
                if inputs.get(param):
                    params[param] = inputs[param]
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
