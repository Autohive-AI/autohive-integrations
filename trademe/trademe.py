"""Read Trade Me account data and seller listings with OAuth 1.0a."""

from pathlib import Path
from urllib.parse import quote

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

trademe = Integration.load(str(Path(__file__).with_name("config.json")))

API_HOSTS = {
    "sandbox": "https://api.tmsandbox.co.nz",
    "production": "https://api.trademe.co.nz",
}


def oauth_header(consumer_key, consumer_secret, token=None, token_secret=None, **parameters):
    """Encode the OAuth PLAINTEXT signing key, then each header value (RFC 5849)."""
    signature = f"{quote(consumer_secret, safe='~')}&{quote(token_secret or '', safe='~')}"
    values = {
        "oauth_consumer_key": consumer_key,
        "oauth_signature_method": "PLAINTEXT",
        "oauth_signature": signature,
        **parameters,
    }
    if token:
        values["oauth_token"] = token
    return "OAuth " + ", ".join(f'{key}="{quote(value, safe="~")}"' for key, value in values.items())


def api_error(status):
    """Return a useful error without exposing provider bodies or request headers."""
    if status in (401, 403):
        return ActionError(
            message="Trade Me denied access. Check the environment, credentials, and MyTradeMeRead permission."
        )
    if status == 429:
        return ActionError(message="Trade Me rate limit reached. Try again after the hourly limit resets.")
    if status == 400:
        return ActionError(message="Trade Me rejected the request. Check the inputs and listing ownership.")
    if status == 404:
        return ActionError(message="Trade Me could not find the requested resource.")
    return ActionError(message=f"Trade Me request failed (HTTP {status}).")


async def get(context: ExecutionContext, path: str, params=None):
    credentials = context.auth["credentials"]
    host = API_HOSTS[credentials.get("environment", "sandbox")]
    headers = {
        "Authorization": oauth_header(
            credentials["consumer_key"],
            credentials["consumer_secret"],
            credentials["access_token"],
            credentials["access_token_secret"],
        ),
        "Accept": "application/json",
    }
    try:
        response = await context.fetch(f"{host}/v1/{path}.json", method="GET", headers=headers, params=params or {})
    except HTTPError as error:
        return api_error(error.status)
    if response.status >= 400:
        return api_error(response.status)
    if not isinstance(response.data, dict):
        return ActionError(message="Trade Me returned an invalid response. Expected a JSON object.")
    return response.data


async def list_items(context, inputs, resource, default_filter):
    data = await get(
        context,
        f"MyTradeMe/{resource}/{inputs.get('filter', default_filter)}",
        {"page": inputs.get("page", 1), "rows": inputs.get("rows", 50)},
    )
    if isinstance(data, ActionError):
        return data
    return ActionResult(
        data={
            "items": data.get("List") or [],
            "total_count": data["TotalCount"],
            "page": data["Page"],
            "page_size": data["PageSize"],
        }
    )


@trademe.action("get_profile")
class GetProfileAction(ActionHandler):
    async def execute(self, inputs, context):
        data = await get(context, "MyTradeMe/Summary")
        if isinstance(data, ActionError):
            return data
        return ActionResult(data={"profile": data})


@trademe.action("list_selling_items")
class ListSellingItemsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_items(context, inputs, "SellingItems", "All")


@trademe.action("list_sold_items")
class ListSoldItemsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_items(context, inputs, "SoldItems", "Last45Days")


@trademe.action("list_unsold_items")
class ListUnsoldItemsAction(ActionHandler):
    async def execute(self, inputs, context):
        return await list_items(context, inputs, "UnsoldItems", "Last45Days")


@trademe.action("get_selling_listing")
class GetSellingListingAction(ActionHandler):
    async def execute(self, inputs, context):
        data = await get(context, f"Selling/Listings/{inputs['listing_id']}")
        if isinstance(data, ActionError):
            return data
        return ActionResult(data={"listing": data})
