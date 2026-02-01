from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

# Create the integration
typeform = Integration.load()

# Base URL for Typeform API
TYPEFORM_API_BASE_URL = "https://api.typeform.com"

# Read-only fields that cannot be sent back to the API on form updates
# These are returned by GET but must be removed before PUT
FORM_READONLY_FIELDS = {"id", "_links", "created_at", "last_updated_at", "published_at", "self"}

# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.
#
# This integration uses the following scopes:
# - accounts:read, forms:read/write, responses:read/write
# - workspaces:read/write, themes:read/write, images:read/write
# - webhooks:read/write, offline
#
# Rate Limiting: Typeform API has rate limits that vary by plan.


# ---- User/Account Handlers ----

@typeform.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Get information about the authenticated user account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/me",
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


# ---- Form Handlers ----

@typeform.action("list_forms")
class ListFormsAction(ActionHandler):
    """List all forms in your account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("workspace_id"):
                params["workspace_id"] = inputs["workspace_id"]
            if inputs.get("search"):
                params["search"] = inputs["search"]
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size") is not None:
                params["page_size"] = inputs["page_size"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms",
                method="GET",
                params=params if params else None
            )

            forms = response.get("items", []) if isinstance(response, dict) else []
            total_items = response.get("total_items", len(forms)) if isinstance(response, dict) else len(forms)

            return ActionResult(
                data={"forms": forms, "total_items": total_items, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"forms": [], "total_items": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("get_form")
class GetFormAction(ActionHandler):
    """Get detailed information about a specific form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}",
                method="GET"
            )

            return ActionResult(
                data={"form": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"form": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("create_form")
class CreateFormAction(ActionHandler):
    """Create a new form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"title": inputs["title"]}

            if inputs.get("workspace_id"):
                body["workspace"] = {"href": f"{TYPEFORM_API_BASE_URL}/workspaces/{inputs['workspace_id']}"}
            if inputs.get("fields"):
                body["fields"] = inputs["fields"]
            if inputs.get("settings"):
                body["settings"] = inputs["settings"]
            if inputs.get("theme_id"):
                body["theme"] = {"href": f"{TYPEFORM_API_BASE_URL}/themes/{inputs['theme_id']}"}
            if inputs.get("welcome_screens"):
                body["welcome_screens"] = inputs["welcome_screens"]
            if inputs.get("thankyou_screens"):
                body["thankyou_screens"] = inputs["thankyou_screens"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms",
                method="POST",
                json=body
            )

            return ActionResult(
                data={"form": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"form": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("update_form")
class UpdateFormAction(ActionHandler):
    """Update an existing form. Uses PUT which replaces the entire form.

    Note: Typeform API only supports limited PATCH operations (title, settings,
    workspace, theme). To update fields/questions, PUT with full form definition
    is required. This action fetches the existing form first to preserve all
    properties and prevent data loss.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]

            # First get the existing form - PUT requires full form definition
            existing_form = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}",
                method="GET"
            )

            # Start with full existing form and remove only read-only fields
            # This prevents data loss when updating specific fields
            body = {k: v for k, v in existing_form.items() if k not in FORM_READONLY_FIELDS}

            # Apply updates from inputs (only if provided)
            if inputs.get("title"):
                body["title"] = inputs["title"]
            if inputs.get("fields"):
                body["fields"] = inputs["fields"]
            if inputs.get("settings"):
                body["settings"] = inputs["settings"]
            if inputs.get("theme_id"):
                body["theme"] = {"href": f"{TYPEFORM_API_BASE_URL}/themes/{inputs['theme_id']}"}
            if inputs.get("welcome_screens"):
                body["welcome_screens"] = inputs["welcome_screens"]
            if inputs.get("thankyou_screens"):
                body["thankyou_screens"] = inputs["thankyou_screens"]

            # Use PUT to replace the entire form
            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}",
                method="PUT",
                json=body
            )

            return ActionResult(
                data={"form": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"form": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_form")
class DeleteFormAction(ActionHandler):
    """Delete a form permanently."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Response Handlers ----

@typeform.action("list_responses")
class ListResponsesAction(ActionHandler):
    """Retrieve responses for a form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]
            params = {}

            param_keys = ["page_size", "since", "until", "after", "before", "sort", "query", "fields"]
            for key in param_keys:
                if inputs.get(key):
                    params[key] = inputs[key]

            if inputs.get("completed") is not None:
                params["completed"] = str(inputs["completed"]).lower()

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/responses",
                method="GET",
                params=params if params else None
            )

            responses = response.get("items", []) if isinstance(response, dict) else []
            total_items = response.get("total_items", 0) if isinstance(response, dict) else 0
            page_count = response.get("page_count", 1) if isinstance(response, dict) else 1

            return ActionResult(
                data={
                    "responses": responses,
                    "total_items": total_items,
                    "page_count": page_count,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"responses": [], "total_items": 0, "page_count": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_responses")
class DeleteResponsesAction(ActionHandler):
    """Delete responses from a form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]
            included_response_ids = inputs["included_response_ids"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/responses",
                method="DELETE",
                params={"included_response_ids": included_response_ids}
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Workspace Handlers ----

@typeform.action("list_workspaces")
class ListWorkspacesAction(ActionHandler):
    """List all workspaces in your account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("search"):
                params["search"] = inputs["search"]
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size") is not None:
                params["page_size"] = inputs["page_size"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces",
                method="GET",
                params=params if params else None
            )

            workspaces = response.get("items", []) if isinstance(response, dict) else []
            total_items = response.get("total_items", len(workspaces)) if isinstance(response, dict) else len(workspaces)

            return ActionResult(
                data={"workspaces": workspaces, "total_items": total_items, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspaces": [], "total_items": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    """Get details of a specific workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs["workspace_id"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces/{workspace_id}",
                method="GET"
            )

            return ActionResult(
                data={"workspace": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspace": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("create_workspace")
class CreateWorkspaceAction(ActionHandler):
    """Create a new workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"name": inputs["name"]}

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces",
                method="POST",
                json=body
            )

            return ActionResult(
                data={"workspace": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspace": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("update_workspace")
class UpdateWorkspaceAction(ActionHandler):
    """Update a workspace's name using JSON Patch format."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs["workspace_id"]

            # Typeform uses JSON Patch format for workspace updates
            # Format: array of operations with op, path, value
            body = [
                {
                    "op": "replace",
                    "path": "/name",
                    "value": inputs["name"]
                }
            ]

            # PATCH returns 204 No Content on success
            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces/{workspace_id}",
                method="PATCH",
                json=body
            )

            # Fetch the updated workspace to return
            updated_workspace = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces/{workspace_id}",
                method="GET"
            )

            return ActionResult(
                data={"workspace": updated_workspace, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspace": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_workspace")
class DeleteWorkspaceAction(ActionHandler):
    """Delete a workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs["workspace_id"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/workspaces/{workspace_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Theme Handlers ----

@typeform.action("list_themes")
class ListThemesAction(ActionHandler):
    """List all themes in your account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size") is not None:
                params["page_size"] = inputs["page_size"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/themes",
                method="GET",
                params=params if params else None
            )

            themes = response.get("items", []) if isinstance(response, dict) else []
            total_items = response.get("total_items", len(themes)) if isinstance(response, dict) else len(themes)

            return ActionResult(
                data={"themes": themes, "total_items": total_items, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"themes": [], "total_items": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("get_theme")
class GetThemeAction(ActionHandler):
    """Get details of a specific theme."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            theme_id = inputs["theme_id"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/themes/{theme_id}",
                method="GET"
            )

            return ActionResult(
                data={"theme": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"theme": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("create_theme")
class CreateThemeAction(ActionHandler):
    """Create a new theme."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"name": inputs["name"]}

            if inputs.get("colors"):
                body["colors"] = inputs["colors"]
            if inputs.get("font"):
                body["font"] = inputs["font"]
            if inputs.get("has_transparent_button") is not None:
                body["has_transparent_button"] = inputs["has_transparent_button"]
            if inputs.get("background"):
                body["background"] = inputs["background"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/themes",
                method="POST",
                json=body
            )

            return ActionResult(
                data={"theme": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"theme": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_theme")
class DeleteThemeAction(ActionHandler):
    """Delete a theme."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            theme_id = inputs["theme_id"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/themes/{theme_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Image Handlers ----

@typeform.action("list_images")
class ListImagesAction(ActionHandler):
    """List all images in your account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("page") is not None:
                params["page"] = inputs["page"]
            if inputs.get("page_size") is not None:
                params["page_size"] = inputs["page_size"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/images",
                method="GET",
                params=params if params else None
            )

            images = response.get("items", []) if isinstance(response, dict) else []
            total_items = response.get("total_items", len(images)) if isinstance(response, dict) else len(images)

            return ActionResult(
                data={"images": images, "total_items": total_items, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"images": [], "total_items": 0, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("get_image")
class GetImageAction(ActionHandler):
    """Get details of a specific image."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            image_id = inputs["image_id"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/images/{image_id}",
                method="GET"
            )

            return ActionResult(
                data={"image": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"image": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_image")
class DeleteImageAction(ActionHandler):
    """Delete an image from your account."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            image_id = inputs["image_id"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/images/{image_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Webhook Handlers ----

@typeform.action("list_webhooks")
class ListWebhooksAction(ActionHandler):
    """List all webhooks for a form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/webhooks",
                method="GET"
            )

            webhooks = response.get("items", []) if isinstance(response, dict) else []

            return ActionResult(
                data={"webhooks": webhooks, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhooks": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("get_webhook")
class GetWebhookAction(ActionHandler):
    """Get details of a specific webhook."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]
            tag = inputs["tag"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/webhooks/{tag}",
                method="GET"
            )

            return ActionResult(
                data={"webhook": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhook": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("create_webhook")
class CreateWebhookAction(ActionHandler):
    """Create or update a webhook for a form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]
            tag = inputs["tag"]

            body = {"url": inputs["url"]}

            if inputs.get("enabled") is not None:
                body["enabled"] = inputs["enabled"]
            if inputs.get("secret"):
                body["secret"] = inputs["secret"]

            response = await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/webhooks/{tag}",
                method="PUT",
                json=body
            )

            return ActionResult(
                data={"webhook": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhook": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@typeform.action("delete_webhook")
class DeleteWebhookAction(ActionHandler):
    """Delete a webhook from a form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            form_id = inputs["form_id"]
            tag = inputs["tag"]

            await context.fetch(
                f"{TYPEFORM_API_BASE_URL}/forms/{form_id}/webhooks/{tag}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )
