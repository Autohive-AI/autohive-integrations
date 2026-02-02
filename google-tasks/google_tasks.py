from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional

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
            if 'maxResults' in inputs:
                params['maxResults'] = inputs['maxResults']
            if 'pageToken' in inputs:
                params['pageToken'] = inputs['pageToken']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/users/@me/lists",
                method="GET",
                params=params if params else None
            )

            tasklists = response.get('items', [])
            result = {"tasklists": tasklists, "result": True}

            if 'nextPageToken' in response:
                result['nextPageToken'] = response['nextPageToken']

            return result

        except Exception as e:
            return {"tasklists": [], "result": False, "error": str(e)}


@google_tasks.action("get_tasklist")
class GetTasklistAction(ActionHandler):
    """Get details of a specific task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/users/@me/lists/{tasklist_id}",
                method="GET"
            )

            return {"tasklist": response, "result": True}

        except Exception as e:
            return {"tasklist": {}, "result": False, "error": str(e)}


# ---- Task Handlers ----

@google_tasks.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a new task in a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']

            # Build task body
            body = {"title": inputs['title']}

            if 'notes' in inputs and inputs['notes']:
                body['notes'] = inputs['notes']
            if 'due' in inputs and inputs['due']:
                body['due'] = inputs['due']
            if 'status' in inputs and inputs['status']:
                body['status'] = inputs['status']

            # Build query params for positioning
            params = {}
            if 'parent' in inputs and inputs['parent']:
                params['parent'] = inputs['parent']
            if 'previous' in inputs and inputs['previous']:
                params['previous'] = inputs['previous']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks",
                method="POST",
                params=params if params else None,
                json=body
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@google_tasks.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List all tasks in a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']

            params = {}
            if 'maxResults' in inputs:
                params['maxResults'] = inputs['maxResults']
            if 'pageToken' in inputs:
                params['pageToken'] = inputs['pageToken']
            if 'showCompleted' in inputs and inputs['showCompleted'] is not None:
                params['showCompleted'] = str(inputs['showCompleted']).lower()
            if 'showHidden' in inputs and inputs['showHidden'] is not None:
                params['showHidden'] = str(inputs['showHidden']).lower()
            if 'dueMin' in inputs:
                params['dueMin'] = inputs['dueMin']
            if 'dueMax' in inputs:
                params['dueMax'] = inputs['dueMax']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks",
                method="GET",
                params=params
            )

            tasks = response.get('items', [])
            result = {"tasks": tasks, "result": True}

            if 'nextPageToken' in response:
                result['nextPageToken'] = response['nextPageToken']

            return result

        except Exception as e:
            return {"tasks": [], "result": False, "error": str(e)}


@google_tasks.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']
            task_id = inputs['task']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}",
                method="GET"
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@google_tasks.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']
            task_id = inputs['task']

            # First, fetch the existing task to preserve unmodified fields
            existing_task = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}",
                method="GET"
            )

            # Build update body starting with existing task data
            # NOTE: Google Tasks API requires 'id' in the body even though it's in the URL
            body = {
                'id': task_id,
                'title': existing_task.get('title', ''),
                'notes': existing_task.get('notes', ''),
                'status': existing_task.get('status', 'needsAction')
            }

            # Preserve 'due' field if it exists
            if 'due' in existing_task:
                body['due'] = existing_task['due']

            # Override with any provided fields
            if 'title' in inputs and inputs['title']:
                body['title'] = inputs['title']
            if 'notes' in inputs and inputs['notes'] is not None:
                body['notes'] = inputs['notes']
            if 'due' in inputs:
                body['due'] = inputs['due']
            if 'status' in inputs and inputs['status']:
                body['status'] = inputs['status']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}",
                method="PUT",
                json=body
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@google_tasks.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task from a task list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']
            task_id = inputs['task']

            await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}",
                method="DELETE"
            )

            return {"result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


@google_tasks.action("move_task")
class MoveTaskAction(ActionHandler):
    """Move a task to another position or make it a subtask."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tasklist_id = inputs['tasklist']
            task_id = inputs['task']

            # Build query params
            params = {}
            if 'parent' in inputs and inputs['parent']:
                params['parent'] = inputs['parent']
            if 'previous' in inputs and inputs['previous']:
                params['previous'] = inputs['previous']

            response = await context.fetch(
                f"{GOOGLE_TASKS_API_BASE_URL}/lists/{tasklist_id}/tasks/{task_id}/move",
                method="POST",
                params=params if params else None
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


