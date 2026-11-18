"""Figma REST API integration: files, images, comments and libraries."""

from pathlib import Path
from typing import Any
from urllib.parse import quote

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

figma = Integration.load(str(Path(__file__).with_name("config.json")))
BASE_URL = "https://api.figma.com/v1"


def _http_error(status: int, headers: dict[str, str]) -> ActionError:
    """Expose actionable status information without including credentials or response bodies."""
    hints = {
        401: " Check that the token is valid and has not expired.",
        403: " Check token scopes and the user's access to this resource.",
        404: " Check the resource ID and that the token owner can access it.",
    }
    message = f"Figma request failed (HTTP {status})." + hints.get(status, "")
    retry_after = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
    if status == 429 and retry_after:
        message += f" Retry after {retry_after} seconds."
    return ActionError(message=message)


async def _request(
    context: ExecutionContext,
    path: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> ActionResult | ActionError:
    """Send authenticated requests through the SDK, preserving Figma response fields."""
    token = context.auth.get("credentials", {}).get("access_token", "")
    if not token or not token.strip():
        return ActionError(message="Connect a Figma account before running this action.")
    kwargs: dict[str, Any] = {
        "method": method,
        "headers": {"Accept": "application/json"},
    }
    if params:
        kwargs["params"] = params
    if body is not None:
        kwargs["json"] = body
    try:
        response = await context.fetch(f"{BASE_URL}{path}", **kwargs)
    except HTTPError as exc:
        return _http_error(exc.status, exc.headers)
    if response.status >= 400:
        return _http_error(response.status, response.headers)
    data = response.data
    if isinstance(data, dict) and (
        data.get("error") is True or data.get("err") or (isinstance(data.get("status"), int) and data["status"] >= 400)
    ):
        return ActionError(message="Figma reported an API error. Check token scopes and resource access.")
    if method == "DELETE":
        return ActionResult(data={"deleted": True})
    if not isinstance(data, dict):
        return ActionError(message="Figma returned an unexpected response format.")
    return ActionResult(data=data)


@figma.action("get_me")
class GetMeAction(ActionHandler):
    """Get the authenticated Figma user."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        return await _request(context, "/me")


@figma.action("get_file")
class GetFileAction(ActionHandler):
    """Read a file document and its metadata."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        params = {}
        if "version" in inputs:
            params["version"] = inputs.get("version")
        if "depth" in inputs:
            params["depth"] = inputs.get("depth")
        if "geometry" in inputs:
            params["geometry"] = inputs.get("geometry")
        if "plugin_data" in inputs:
            params["plugin_data"] = inputs.get("plugin_data")
        if "ids" in inputs:
            params["ids"] = ",".join(inputs.get("ids"))
        if "branch_data" in inputs:
            params["branch_data"] = str(inputs.get("branch_data")).lower()
        return await _request(context, f"/files/{file_key}", params=params)


@figma.action("get_file_nodes")
class GetFileNodesAction(ActionHandler):
    """Read selected nodes; missing nodes may have null values."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        params = {}
        if "ids" in inputs:
            params["ids"] = ",".join(inputs["ids"])
        if "version" in inputs:
            params["version"] = inputs.get("version")
        if "depth" in inputs:
            params["depth"] = inputs.get("depth")
        if "geometry" in inputs:
            params["geometry"] = inputs.get("geometry")
        if "plugin_data" in inputs:
            params["plugin_data"] = inputs.get("plugin_data")
        return await _request(context, f"/files/{file_key}/nodes", params=params)


@figma.action("get_file_metadata")
class GetFileMetadataAction(ActionHandler):
    """Read file metadata without the full document."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        return await _request(context, f"/files/{file_key}/meta")


@figma.action("export_images")
class ExportImagesAction(ActionHandler):
    """Render nodes as temporary image URLs; no binary download."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        params = {}
        if "ids" in inputs:
            params["ids"] = ",".join(inputs["ids"])
        if "version" in inputs:
            params["version"] = inputs.get("version")
        if "format" in inputs:
            params["format"] = inputs.get("format")
        if "scale" in inputs:
            params["scale"] = inputs.get("scale")
        if "svg_outline_text" in inputs:
            params["svg_outline_text"] = str(inputs.get("svg_outline_text")).lower()
        if "svg_include_id" in inputs:
            params["svg_include_id"] = str(inputs.get("svg_include_id")).lower()
        if "svg_include_node_id" in inputs:
            params["svg_include_node_id"] = str(inputs.get("svg_include_node_id")).lower()
        if "svg_simplify_stroke" in inputs:
            params["svg_simplify_stroke"] = str(inputs.get("svg_simplify_stroke")).lower()
        if "contents_only" in inputs:
            params["contents_only"] = str(inputs.get("contents_only")).lower()
        if "use_absolute_bounds" in inputs:
            params["use_absolute_bounds"] = str(inputs.get("use_absolute_bounds")).lower()
        return await _request(context, f"/images/{file_key}", params=params)


@figma.action("get_image_fills")
class GetImageFillsAction(ActionHandler):
    """Get temporary URLs for image fills used in a file."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        return await _request(context, f"/files/{file_key}/images")


@figma.action("list_comments")
class ListCommentsAction(ActionHandler):
    """List file comments and replies."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        params = {}
        if "as_md" in inputs:
            params["as_md"] = str(inputs.get("as_md")).lower()
        return await _request(context, f"/files/{file_key}/comments", params=params)


@figma.action("create_comment")
class CreateCommentAction(ActionHandler):
    """Post a comment or reply to a root comment."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        body = {}
        if "message" in inputs:
            body["message"] = inputs["message"]
        if "comment_id" in inputs:
            body["comment_id"] = inputs.get("comment_id")
        if "client_meta" in inputs:
            body["client_meta"] = inputs.get("client_meta")
        return await _request(context, f"/files/{file_key}/comments", method="POST", body=body)


@figma.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    """Delete a comment authored by the token owner."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        comment_id = quote(inputs["comment_id"], safe="")
        return await _request(context, f"/files/{file_key}/comments/{comment_id}", method="DELETE")


@figma.action("list_file_versions")
class ListFileVersionsAction(ActionHandler):
    """List one page of file versions; pagination links are preserved."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        params = {}
        if "page_size" in inputs:
            params["page_size"] = inputs.get("page_size")
        if "before" in inputs:
            params["before"] = inputs.get("before")
        if "after" in inputs:
            params["after"] = inputs.get("after")
        return await _request(context, f"/files/{file_key}/versions", params=params)


@figma.action("list_file_components")
class ListFileComponentsAction(ActionHandler):
    """List published components in a file."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        return await _request(context, f"/files/{file_key}/components")


@figma.action("list_team_components")
class ListTeamComponentsAction(ActionHandler):
    """List published components in a team (one page)."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        team_id = quote(inputs["team_id"], safe="")
        params = {}
        if "page_size" in inputs:
            params["page_size"] = inputs.get("page_size")
        if "before" in inputs:
            params["before"] = inputs.get("before")
        if "after" in inputs:
            params["after"] = inputs.get("after")
        return await _request(context, f"/teams/{team_id}/components", params=params)


@figma.action("get_component")
class GetComponentAction(ActionHandler):
    """Get a published component by its asset key."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        key = quote(inputs["key"], safe="")
        return await _request(context, f"/components/{key}")


@figma.action("list_file_component_sets")
class ListFileComponentSetsAction(ActionHandler):
    """List published component sets in a file."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        return await _request(context, f"/files/{file_key}/component_sets")


@figma.action("list_team_component_sets")
class ListTeamComponentSetsAction(ActionHandler):
    """List published component sets in a team (one page)."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        team_id = quote(inputs["team_id"], safe="")
        params = {}
        if "page_size" in inputs:
            params["page_size"] = inputs.get("page_size")
        if "before" in inputs:
            params["before"] = inputs.get("before")
        if "after" in inputs:
            params["after"] = inputs.get("after")
        return await _request(context, f"/teams/{team_id}/component_sets", params=params)


@figma.action("get_component_set")
class GetComponentSetAction(ActionHandler):
    """Get a published component set by its asset key."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        key = quote(inputs["key"], safe="")
        return await _request(context, f"/component_sets/{key}")


@figma.action("list_file_styles")
class ListFileStylesAction(ActionHandler):
    """List published styles in a file."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        file_key = quote(inputs["file_key"], safe="")
        return await _request(context, f"/files/{file_key}/styles")


@figma.action("list_team_styles")
class ListTeamStylesAction(ActionHandler):
    """List published styles in a team (one page)."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        team_id = quote(inputs["team_id"], safe="")
        params = {}
        if "page_size" in inputs:
            params["page_size"] = inputs.get("page_size")
        if "before" in inputs:
            params["before"] = inputs.get("before")
        if "after" in inputs:
            params["after"] = inputs.get("after")
        return await _request(context, f"/teams/{team_id}/styles", params=params)


@figma.action("get_style")
class GetStyleAction(ActionHandler):
    """Get a published style by its asset key."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        key = quote(inputs["key"], safe="")
        return await _request(context, f"/styles/{key}")
