from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Dict, Any
import base64
import io
import aiohttp

# Create the integration using the config.json
clickup = Integration.load()

# Base URL for ClickUp API
CLICKUP_API_BASE_URL = "https://api.clickup.com/api/v2"


# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


# ---- Task Handlers ----


@clickup.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a new task in a list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]

            # Build request body
            data = {"name": inputs["name"]}

            # Add optional fields
            if inputs.get("description"):
                data["description"] = inputs.get("description")
            if inputs.get("assignees"):
                data["assignees"] = inputs.get("assignees")
            if inputs.get("status"):
                data["status"] = inputs.get("status")
            if inputs.get("priority") is not None:
                data["priority"] = inputs.get("priority")
            if inputs.get("due_date"):
                data["due_date"] = inputs.get("due_date")
            if inputs.get("due_date_time") is not None:
                data["due_date_time"] = inputs.get("due_date_time")
            if inputs.get("start_date"):
                data["start_date"] = inputs.get("start_date")
            if inputs.get("tags"):
                data["tags"] = inputs.get("tags")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}/task", method="POST", json=data
            )).data

            return ActionResult(data={"task": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]

            # Build query params
            params = {}
            if inputs.get("include_subtasks"):
                params["include_subtasks"] = "true"

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}",
                method="GET",
                params=params if params else None,
            )).data

            return ActionResult(data={"task": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]
            data = {}

            # Add only provided fields
            if inputs.get("name"):
                data["name"] = inputs.get("name")
            if inputs.get("description"):
                data["description"] = inputs.get("description")
            if inputs.get("status"):
                data["status"] = inputs.get("status")
            if inputs.get("priority") is not None:
                data["priority"] = inputs.get("priority")
            if inputs.get("assignees"):
                data["assignees"] = inputs.get("assignees")
            if inputs.get("due_date"):
                data["due_date"] = inputs.get("due_date")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}", method="PUT", json=data
            )).data

            return ActionResult(data={"task": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}", method="DELETE"
            )

            return ActionResult(data={"result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@clickup.action("get_tasks")
class GetTasksAction(ActionHandler):
    """Get tasks from a list with optional filtering."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]

            # Build query params
            params = {}
            if inputs.get("archived") is not None:
                params["archived"] = "true" if inputs.get("archived") else "false"
            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")
            if inputs.get("order_by"):
                params["order_by"] = inputs.get("order_by")
            if inputs.get("reverse") is not None:
                params["reverse"] = "true" if inputs.get("reverse") else "false"
            if inputs.get("subtasks") is not None:
                params["subtasks"] = "true" if inputs.get("subtasks") else "false"
            if inputs.get("statuses"):
                params["statuses[]"] = inputs.get("statuses")
            if inputs.get("assignees"):
                params["assignees[]"] = inputs.get("assignees")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}/task",
                method="GET",
                params=params if params else None,
            )).data

            tasks = response.get("tasks", [])
            return ActionResult(data={"tasks": tasks, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"tasks": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("create_task_attachment")
class CreateTaskAttachmentAction(ActionHandler):
    """Upload a file attachment to a task using the v3 Attachments API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Required path parameters for the v3 endpoint. workspace_id must match the
            # workspace that owns the task — a mismatch causes ClickUp to return 404.
            workspace_id = inputs["workspace_id"]
            task_id = inputs["task_id"]

            # The Autohive platform delivers file attachments from chat as an object
            # with `name`, `content` (base64), and `contentType` fields.
            file_obj = inputs["file"]

            # Optional `filename` input overrides the filename used in the upload; falls
            # back to the uploaded file's own name.
            default_filename = file_obj.get("name", "attachment")
            filename = inputs.get("filename") or default_filename
            content_b64 = file_obj.get("content", "")
            content_type = file_obj.get("contentType", "application/octet-stream")

            if not content_b64:
                return ActionResult(
                    data={
                        "attachment": {},
                        "result": False,
                        "error": f"File '{filename}' has no content provided",
                    },
                    cost_usd=0.0,
                )

            # Strip whitespace/newlines and re-pad — base64 coming through transport
            # layers is sometimes reformatted and loses padding, which trips the strict
            # decoder below.
            content_b64_cleaned = (
                content_b64.strip()
                .replace("\n", "")
                .replace("\r", "")
                .replace(" ", "")
                .replace("\t", "")
            )
            padding_needed = len(content_b64_cleaned) % 4
            if padding_needed != 0:
                content_b64_cleaned += "=" * (4 - padding_needed)

            try:
                file_bytes = base64.b64decode(content_b64_cleaned, validate=True)
            except Exception as e:
                return ActionResult(
                    data={
                        "attachment": {},
                        "result": False,
                        "error": f"Failed to decode file '{filename}': {str(e)}. Content must be valid base64.",
                    },
                    cost_usd=0.0,
                )

            if not file_bytes:
                return ActionResult(
                    data={
                        "attachment": {},
                        "result": False,
                        "error": f"File '{filename}' decoded to empty content",
                    },
                    cost_usd=0.0,
                )

            # context.fetch serialises request bodies as JSON and can't build multipart
            # form-data, so we pull the OAuth token from context and send the request via
            # raw aiohttp. See the same pattern in front/front.py and box/box.py.
            auth_token = None
            if context.auth and "credentials" in context.auth:
                auth_token = context.auth["credentials"].get("access_token")

            if not auth_token:
                return ActionResult(
                    data={
                        "attachment": {},
                        "result": False,
                        "error": "No authentication token available",
                    },
                    cost_usd=0.0,
                )

            # ClickUp v3 Attachments endpoint. The path nests under /tasks/{task_id} —
            # the ClickUp docs describe the path template as
            # /workspaces/{workspace_id}/{entity_type}/{entity_id}/attachments with
            # entity_type = "tasks" for tasks (or "custom_fields" for file-type custom
            # fields, which this action doesn't expose).
            url = f"https://api.clickup.com/api/v3/workspaces/{workspace_id}/tasks/{task_id}/attachments"

            # Build multipart/form-data body. ClickUp v2 used the field name "attachment"
            # for the file part; v3 docs don't explicitly state the field name, so we
            # inherit the v2 convention. If a 400 comes back complaining about the file
            # field, try "file" instead.
            form = aiohttp.FormData()
            bio = io.BytesIO(file_bytes)
            bio.seek(0)
            form.add_field(
                "attachment", bio, filename=filename, content_type=content_type
            )
            # v3 supports an optional body field that overrides the stored filename
            # independently of the multipart part's filename.
            if inputs.get("filename"):
                form.add_field("filename", inputs.get("filename"))

            headers = {"Authorization": f"Bearer {auth_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form, headers=headers) as resp:
                    if resp.status >= 400:
                        # ClickUp 404 "Not Found or Authorized" usually means workspace_id
                        # and task_id don't match, or the OAuth user lacks access.
                        error_text = await resp.text()
                        return ActionResult(
                            data={
                                "attachment": {},
                                "result": False,
                                "error": f"HTTP {resp.status}: {error_text} (url={url})",
                            },
                            cost_usd=0.0,
                        )
                    response_data = await resp.json()

            return ActionResult(
                data={"attachment": response_data, "result": True}, cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"attachment": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


# ---- List Handlers ----


@clickup.action("create_list")
class CreateListAction(ActionHandler):
    """Create a new list in a folder or space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Determine parent (folder or space)
            parent_type = None
            parent_id = None

            if inputs.get("folder_id"):
                parent_type = "folder"
                parent_id = inputs.get("folder_id")
            elif inputs.get("space_id"):
                parent_type = "space"
                parent_id = inputs.get("space_id")
            else:
                return ActionResult(
                    data={
                        "list": {},
                        "result": False,
                        "error": "Either folder_id or space_id is required",
                    },
                    cost_usd=0.0,
                )

            data = {"name": inputs["name"]}

            # Add optional fields
            if inputs.get("content"):
                data["content"] = inputs.get("content")
            if inputs.get("due_date"):
                data["due_date"] = inputs.get("due_date")
            if inputs.get("priority") is not None:
                data["priority"] = inputs.get("priority")
            if inputs.get("status"):
                data["status"] = inputs.get("status")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/{parent_type}/{parent_id}/list",
                method="POST",
                json=data,
            )).data

            return ActionResult(data={"list": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("get_list")
class GetListAction(ActionHandler):
    """Get details of a specific list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}", method="GET"
            )).data

            return ActionResult(data={"list": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("update_list")
class UpdateListAction(ActionHandler):
    """Update an existing list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]
            data = {}

            if inputs.get("name"):
                data["name"] = inputs.get("name")
            if inputs.get("content"):
                data["content"] = inputs.get("content")
            if inputs.get("due_date"):
                data["due_date"] = inputs.get("due_date")
            if inputs.get("priority") is not None:
                data["priority"] = inputs.get("priority")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}", method="PUT", json=data
            )).data

            return ActionResult(data={"list": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("delete_list")
class DeleteListAction(ActionHandler):
    """Delete a list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs["list_id"]

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}", method="DELETE"
            )

            return ActionResult(data={"result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@clickup.action("get_lists")
class GetListsAction(ActionHandler):
    """Get all lists in a folder or space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Determine parent (folder or space)
            parent_type = None
            parent_id = None

            if inputs.get("folder_id"):
                parent_type = "folder"
                parent_id = inputs.get("folder_id")
            elif inputs.get("space_id"):
                parent_type = "space"
                parent_id = inputs.get("space_id")
            else:
                return ActionResult(
                    data={
                        "lists": [],
                        "result": False,
                        "error": "Either folder_id or space_id is required",
                    },
                    cost_usd=0.0,
                )

            params = {}
            if inputs.get("archived") is not None:
                params["archived"] = "true" if inputs.get("archived") else "false"

            response = (
                await context.fetch(
                    f"{CLICKUP_API_BASE_URL}/{parent_type}/{parent_id}/list",
                    method="GET",
                    params=params if params else None,
                )
            ).data

            lists = response.get("lists", [])
            return ActionResult(data={"lists": lists, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"lists": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


# ---- Folder Handlers ----


@clickup.action("create_folder")
class CreateFolderAction(ActionHandler):
    """Create a new folder in a space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs["space_id"]
            data = {"name": inputs["name"]}

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/space/{space_id}/folder",
                method="POST",
                json=data,
            )).data

            return ActionResult(data={"folder": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("get_folder")
class GetFolderAction(ActionHandler):
    """Get details of a specific folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}", method="GET"
            )).data

            return ActionResult(data={"folder": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("update_folder")
class UpdateFolderAction(ActionHandler):
    """Update an existing folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]
            data = {"name": inputs["name"]}

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}", method="PUT", json=data
            )).data

            return ActionResult(data={"folder": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("delete_folder")
class DeleteFolderAction(ActionHandler):
    """Delete a folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs["folder_id"]

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}", method="DELETE"
            )

            return ActionResult(data={"result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@clickup.action("get_folders")
class GetFoldersAction(ActionHandler):
    """Get all folders in a space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs["space_id"]

            params = {}
            if inputs.get("archived") is not None:
                params["archived"] = "true" if inputs.get("archived") else "false"

            response = (
                await context.fetch(
                    f"{CLICKUP_API_BASE_URL}/space/{space_id}/folder",
                    method="GET",
                    params=params if params else None,
                )
            ).data

            folders = response.get("folders", [])
            return ActionResult(data={"folders": folders, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"folders": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


# ---- Space Handlers ----


@clickup.action("get_space")
class GetSpaceAction(ActionHandler):
    """Get details of a specific space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs["space_id"]

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/space/{space_id}", method="GET"
            )).data

            return ActionResult(data={"space": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"space": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("get_spaces")
class GetSpacesAction(ActionHandler):
    """Get all spaces in a team/workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            team_id = inputs["team_id"]

            params = {}
            if inputs.get("archived") is not None:
                params["archived"] = "true" if inputs.get("archived") else "false"

            response = (
                await context.fetch(
                    f"{CLICKUP_API_BASE_URL}/team/{team_id}/space",
                    method="GET",
                    params=params if params else None,
                )
            ).data

            spaces = response.get("spaces", [])
            return ActionResult(data={"spaces": spaces, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"spaces": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


# ---- Team/Workspace Handlers ----


@clickup.action("get_authorized_teams")
class GetAuthorizedTeamsAction(ActionHandler):
    """Get all teams/workspaces the authenticated user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = (await context.fetch(f"{CLICKUP_API_BASE_URL}/team", method="GET")).data

            teams = response.get("teams", [])
            return ActionResult(data={"teams": teams, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"teams": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


# ---- Comment Handlers ----


@clickup.action("create_task_comment")
class CreateTaskCommentAction(ActionHandler):
    """Add a comment to a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]
            data = {"comment_text": inputs["comment_text"]}

            # Add optional fields
            if inputs.get("assignee"):
                data["assignee"] = inputs.get("assignee")
            if inputs.get("notify_all") is not None:
                data["notify_all"] = inputs.get("notify_all")

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}/comment",
                method="POST",
                json=data,
            )).data

            return ActionResult(
                data={"comment": response, "result": True}, cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comment": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("get_task_comments")
class GetTaskCommentsAction(ActionHandler):
    """Get all comments for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]

            response = (
                await context.fetch(f"{CLICKUP_API_BASE_URL}/task/{task_id}/comment", method="GET")
            ).data

            comments = response.get("comments", [])
            return ActionResult(
                data={"comments": comments, "result": True}, cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comments": [], "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("update_comment")
class UpdateCommentAction(ActionHandler):
    """Update an existing comment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_id = inputs["comment_id"]
            data = {"comment_text": inputs["comment_text"]}

            response = (await context.fetch(
                f"{CLICKUP_API_BASE_URL}/comment/{comment_id}", method="PUT", json=data
            )).data

            return ActionResult(
                data={"comment": response, "result": True}, cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comment": {}, "result": False, "error": str(e)}, cost_usd=0.0
            )


@clickup.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    """Delete a comment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_id = inputs["comment_id"]

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/comment/{comment_id}", method="DELETE"
            )

            return ActionResult(data={"result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
