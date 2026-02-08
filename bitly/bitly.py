from autohive_integrations_sdk import (
    Integration, ActionHandler, ActionResult
)
from typing import Dict, Any
from urllib.parse import quote, urlparse

# Create the integration
bitly = Integration.load()

# Base URL for Bitly API
BITLY_API_BASE_URL = "https://api-ssl.bitly.com/v4"

# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


def normalize_bitlink(bitlink: str) -> str:
    """Normalize a bitlink to domain/path format (e.g., 'bit.ly/abc123')."""
    # If it's a full URL, parse it properly
    if bitlink.startswith(("http://", "https://")):
        parsed = urlparse(bitlink)
        # Return domain + path (e.g., "bit.ly/abc123")
        return f"{parsed.netloc}{parsed.path}"

    # If it already contains a slash, assume it's in domain/path format
    if "/" in bitlink:
        return bitlink

    # Otherwise, it's just a hash - prepend default domain
    return f"bit.ly/{bitlink}"


def encode_bitlink_for_url(bitlink: str) -> str:
    """URL-encode a bitlink for use in API paths (e.g., bit.ly/abc -> bit.ly%2Fabc)."""
    return quote(bitlink, safe="")


# ---- User Handlers ----

@bitly.action("get_user")
class GetUserAction(ActionHandler):
    """Get information about the currently authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/user",
                method="GET"
            )

            return ActionResult(
                data={"user": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Bitlink Handlers ----

@bitly.action("shorten_url")
class ShortenUrlAction(ActionHandler):
    """Shorten a long URL to a Bitly link."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            body = {
                "long_url": inputs["long_url"]
            }

            if inputs.get("domain"):
                body["domain"] = inputs["domain"]
            if inputs.get("group_guid"):
                body["group_guid"] = inputs["group_guid"]

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/shorten",
                method="POST",
                json=body
            )

            return ActionResult(
                data={"bitlink": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bitlink": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("create_bitlink")
class CreateBitlinkAction(ActionHandler):
    """Create a bitlink with advanced options."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            body = {
                "long_url": inputs["long_url"]
            }

            if inputs.get("domain"):
                body["domain"] = inputs["domain"]
            if inputs.get("group_guid"):
                body["group_guid"] = inputs["group_guid"]
            if inputs.get("title"):
                body["title"] = inputs["title"]
            if inputs.get("tags"):
                body["tags"] = inputs["tags"]
            if inputs.get("custom_back_half"):
                body["custom_back_half"] = inputs["custom_back_half"]

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/bitlinks",
                method="POST",
                json=body
            )

            return ActionResult(
                data={"bitlink": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bitlink": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("get_bitlink")
class GetBitlinkAction(ActionHandler):
    """Get information about a specific bitlink."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            bitlink = normalize_bitlink(inputs["bitlink"])
            encoded_bitlink = encode_bitlink_for_url(bitlink)

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/bitlinks/{encoded_bitlink}",
                method="GET"
            )

            return ActionResult(
                data={"bitlink": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bitlink": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("update_bitlink")
class UpdateBitlinkAction(ActionHandler):
    """Update an existing bitlink."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            bitlink = normalize_bitlink(inputs["bitlink"])
            encoded_bitlink = encode_bitlink_for_url(bitlink)

            body = {}
            if inputs.get("title") is not None:
                body["title"] = inputs["title"]
            if inputs.get("tags") is not None:
                body["tags"] = inputs["tags"]
            if inputs.get("archived") is not None:
                body["archived"] = inputs["archived"]

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/bitlinks/{encoded_bitlink}",
                method="PATCH",
                json=body
            )

            return ActionResult(
                data={"bitlink": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bitlink": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("expand_bitlink")
class ExpandBitlinkAction(ActionHandler):
    """Get the original long URL from a bitlink."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            bitlink = normalize_bitlink(inputs["bitlink"])

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/expand",
                method="POST",
                json={"bitlink_id": bitlink}
            )

            return ActionResult(
                data={
                    "long_url": response.get("long_url", ""),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"long_url": "", "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Click Analytics Handlers ----

@bitly.action("get_clicks")
class GetClicksAction(ActionHandler):
    """Get click counts for a bitlink by time unit."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            bitlink = normalize_bitlink(inputs["bitlink"])
            encoded_bitlink = encode_bitlink_for_url(bitlink)

            params = {
                "unit": inputs.get("unit", "day"),
                "units": inputs["units"] if inputs.get("units") is not None else -1
            }

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/bitlinks/{encoded_bitlink}/clicks",
                method="GET",
                params=params
            )

            clicks = response.get("link_clicks", [])

            return ActionResult(
                data={"clicks": clicks, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"clicks": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("get_clicks_summary")
class GetClicksSummaryAction(ActionHandler):
    """Get a summary of total clicks for a bitlink."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            bitlink = normalize_bitlink(inputs["bitlink"])
            encoded_bitlink = encode_bitlink_for_url(bitlink)

            params = {
                "unit": inputs.get("unit", "day"),
                "units": inputs["units"] if inputs.get("units") is not None else -1
            }

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/bitlinks/{encoded_bitlink}/clicks/summary",
                method="GET",
                params=params
            )

            return ActionResult(
                data={
                    "total_clicks": response.get("total_clicks", 0),
                    "unit": response.get("unit", ""),
                    "units": response.get("units", 0),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "total_clicks": 0,
                    "unit": "",
                    "units": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@bitly.action("list_bitlinks")
class ListBitlinksAction(ActionHandler):
    """List bitlinks for a group."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            # Get group_guid from input or fetch default group
            group_guid = inputs.get("group_guid")
            if not group_guid:
                # Get user's default group
                user_response = await context.fetch(
                    f"{BITLY_API_BASE_URL}/user",
                    method="GET"
                )
                group_guid = user_response.get("default_group_guid")
                if not group_guid:
                    return ActionResult(
                        data={"bitlinks": [], "result": False, "error": "No default_group_guid found for user"},
                        cost_usd=0.0
                    )

            # URL encode group_guid for safe path insertion
            encoded_group_guid = quote(group_guid, safe="")

            params = {}
            if inputs.get("size") is not None:
                params["size"] = inputs["size"]
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("keyword"):
                params["keyword"] = inputs["keyword"]
            if inputs.get("archived"):
                params["archived"] = inputs["archived"]

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/groups/{encoded_group_guid}/bitlinks",
                method="GET",
                params=params if params else None
            )

            bitlinks = response.get("links", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={
                    "bitlinks": bitlinks,
                    "total": pagination.get("total"),
                    "page": pagination.get("page"),
                    "size": pagination.get("size"),
                    "next": pagination.get("next"),
                    "prev": pagination.get("prev"),
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"bitlinks": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Group Handlers ----

@bitly.action("list_groups")
class ListGroupsAction(ActionHandler):
    """List all groups the user belongs to."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/groups",
                method="GET"
            )

            groups = response.get("groups", [])

            return ActionResult(
                data={"groups": groups, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"groups": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bitly.action("get_group")
class GetGroupAction(ActionHandler):
    """Get information about a specific group."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            group_guid = quote(inputs["group_guid"], safe="")

            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/groups/{group_guid}",
                method="GET"
            )

            return ActionResult(
                data={"group": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"group": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Organization Handlers ----

@bitly.action("list_organizations")
class ListOrganizationsAction(ActionHandler):
    """List all organizations the user belongs to."""

    async def execute(self, inputs: Dict[str, Any], context):
        try:
            response = await context.fetch(
                f"{BITLY_API_BASE_URL}/organizations",
                method="GET"
            )

            organizations = response.get("organizations", [])

            return ActionResult(
                data={"organizations": organizations, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"organizations": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )
