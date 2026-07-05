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
