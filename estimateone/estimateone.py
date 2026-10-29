"""E1 Supplier API: customer-authorized Speci-finder opportunity retrieval."""

from pathlib import Path
from typing import Any

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext, HTTPError, Integration

estimateone = Integration.load(str(Path(__file__).with_name("config.json")))
AUTH_URL = "https://auth.api.estimateone.com/oauth2/token"
API_URL = "https://api.estimateone.com/api/tender/supplier/v1/companies"


async def get_token(context: ExecutionContext) -> str:
    credentials = context.auth["credentials"]
    response = await context.fetch(
        AUTH_URL,
        method="POST",
        content_type="application/x-www-form-urlencoded",
        data={
            "grant_type": "client_credentials",
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        },
    )
    if not isinstance(response.data, dict) or not isinstance(response.data.get("access_token"), str):
        raise ValueError("E1 authentication returned no access token.")
    if not response.data["access_token"]:
        raise ValueError("E1 authentication returned an empty access token.")
    return response.data["access_token"]


@estimateone.action("list_matched_projects")
class ListMatchedProjectsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        company_id = inputs["company_id"]
        if not company_id.isascii() or not company_id.isdigit():
            raise ValueError("company_id must be the numeric E1 account number.")
        params = {"limit": inputs.get("limit", 25)}
        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]
        if inputs.get("created_since"):
            params["createdSince"] = inputs["created_since"]

        # Tokens stay local to this execution; credentials and tokens never enter action outputs.
        token = await get_token(context)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-e1-client-id": context.auth["credentials"]["client_id"],
            "Accept": "application/json",
        }
        try:
            response = await context.fetch(
                f"{API_URL}/{company_id}/speci-finder/results", headers=headers, params=params
            )
        except HTTPError as error:
            if error.status != 401:
                raise
            # E1 uses 401 for both expiry and missing permissions. Refresh only once.
            headers["Authorization"] = f"Bearer {await get_token(context)}"
            response = await context.fetch(
                f"{API_URL}/{company_id}/speci-finder/results", headers=headers, params=params
            )

        body = response.data
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise ValueError("E1 returned an invalid project list.")
        metadata = body.get("_metadata")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("hasNextPage"), bool):
            raise ValueError("E1 returned invalid pagination metadata.")
        cursor = metadata.get("nextCursor")
        if cursor is not None and not isinstance(cursor, str):
            raise ValueError("E1 returned an invalid pagination cursor.")
        if metadata["hasNextPage"] and not cursor:
            raise ValueError("E1 reported another page without a cursor.")
        return ActionResult(
            data={
                "projects": body["data"],
                "next_cursor": cursor,
                "has_next_page": metadata["hasNextPage"],
            }
        )
