from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any

# Create the integration using the config.json
google_tasks = Integration.load()

# Base URL for Google Tasks API
GOOGLE_TASKS_API_BASE_URL = "https://tasks.googleapis.com/tasks/v1"


# ---- Helper Functions ----

# Google Tasks uses OAuth 2.0 (platform auth), so context.fetch() handles auth automatically
# No custom headers needed - access token is injected by the SDK


# ---- Action Handlers ----

# ---- Tasklist Handlers ----


@google_tasks.action("list_tasklists")
class ListTasklistsAction(ActionHandler):
    """List all task lists for the authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if inputs.get("maxResults") is not None:
                params["maxResults"] = inputs.get("maxResults")
            if inputs.get("pageToken") is not None:
                params["pageToken"] = inputs.get("pageToken")

            response = (
                await context.fetch(
                    f"{GOOGLE_TASKS_API_BASE_URL}/users/@me/lists", method="GET", params=params if params else None
                )
            ).data

            tasklists = response.get("items", [])
            data = {"tasklists": tasklists, "result": True}

            if "nextPageToken" in response:
                data["nextPageToken"] = response["nextPageToken"]

            return ActionResult(data=data, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"tasklists": [], "result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("get_tasklist")
class GetTasklistAction(ActionHandler):
    """Get details of a specific task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]

            tasklist = (
                await context.fetch(f"{GOOGLE_TASKS_API_BASE_URL}/users/@me/lists/{tasklist_id}", method="GET")
            ).data

            return ActionResult(data={"tasklist": tasklist, "result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"tasklist": {}, "result": False, "error": str(e)}, cost_usd=0)


# ---- Task Handlers ----


@google_tasks.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a new task in a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]

            # Build task body
            body = {"title": inputs["title"]}

            if inputs.get("notes"):
                body["notes"] = inputs.get("notes")
            if inputs.get("due"):
                body["due"] = inputs.get("due")
            if inputs.get("status"):
                body["status"] = inputs.get("status")

            # Build query params for positioning
            params = {}
            if inputs.get("parent"):
                params["parent"] = inputs.get("parent")
            if inputs.get("previous"):
                params["previous"] = inputs.get("previous")

            task = (
                await context.fetch(
                    f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks",
                    method="POST",
                    params=params if params else None,
                    json=body,
                )
            ).data

            return ActionResult(data={"task": task, "result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"task": {}, "result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List all tasks in a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]

            params = {}
            if inputs.get("maxResults") is not None:
                params["maxResults"] = inputs.get("maxResults")
            if inputs.get("pageToken") is not None:
                params["pageToken"] = inputs.get("pageToken")
            if inputs.get("showCompleted") is not None:
                params["showCompleted"] = str(inputs.get("showCompleted")).lower()
            if inputs.get("showHidden") is not None:
                params["showHidden"] = str(inputs.get("showHidden")).lower()
            if inputs.get("dueMin") is not None:
                params["dueMin"] = inputs.get("dueMin")
            if inputs.get("dueMax") is not None:
                params["dueMax"] = inputs.get("dueMax")

            response = (
                await context.fetch(
                    f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks", method="GET", params=params
                )
            ).data

            tasks = response.get("items", [])
            data = {"tasks": tasks, "result": True}

            if "nextPageToken" in response:
                data["nextPageToken"] = response["nextPageToken"]

            return ActionResult(data=data, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"tasks": [], "result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]
            task_id = inputs["task"]

            task = (
                await context.fetch(f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}", method="GET")
            ).data

            return ActionResult(data={"task": task, "result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"task": {}, "result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]
            task_id = inputs["task"]

            # First, fetch the existing task to preserve unmodified fields
            existing_task = (
                await context.fetch(f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}", method="GET")
            ).data

            # Build update body starting with existing task data
            # NOTE: Google Tasks API requires 'id' in the body even though it's in the URL
            body = {
                "id": task_id,
                "title": existing_task.get("title", ""),
                "notes": existing_task.get("notes", ""),
                "status": existing_task.get("status", "needsAction"),
            }

            # Preserve 'due' field if it exists
            if "due" in existing_task:
                body["due"] = existing_task["due"]

            # Override with any provided fields
            if inputs.get("title"):
                body["title"] = inputs.get("title")
            if inputs.get("notes") is not None:
                body["notes"] = inputs.get("notes")
            if "due" in inputs:
                body["due"] = inputs.get("due")
            if inputs.get("status"):
                body["status"] = inputs.get("status")

            task = (
                await context.fetch(
                    f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}", method="PUT", json=body
                )
            ).data

            return ActionResult(data={"task": task, "result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"task": {}, "result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task from a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]
            task_id = inputs["task"]

            await context.fetch(f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}", method="DELETE")

            return ActionResult(data={"result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0)


@google_tasks.action("move_task")
class MoveTaskAction(ActionHandler):
    """Move a task to another position or make it a subtask."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs["tasklist"]
            task_id = inputs["task"]

            # Build query params
            params = {}
            if inputs.get("parent"):
                params["parent"] = inputs.get("parent")
            if inputs.get("previous"):
                params["previous"] = inputs.get("previous")

            task = (
                await context.fetch(
                    f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}/move",
                    method="POST",
                    params=params if params else None,
                )
            ).data

            return ActionResult(data={"task": task, "result": True}, cost_usd=0)

        except Exception as e:
            return ActionResult(data={"task": {}, "result": False, "error": str(e)}, cost_usd=0)
