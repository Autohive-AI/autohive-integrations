from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

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
            list_id = inputs['list_id']

            # Build request body
            data = {
                "name": inputs['name']
            }

            # Add optional fields
            if 'description' in inputs and inputs['description']:
                data['description'] = inputs['description']
            if 'assignees' in inputs and inputs['assignees']:
                data['assignees'] = inputs['assignees']
            if 'status' in inputs and inputs['status']:
                data['status'] = inputs['status']
            if 'priority' in inputs and inputs['priority'] is not None:
                data['priority'] = inputs['priority']
            if 'due_date' in inputs and inputs['due_date']:
                data['due_date'] = inputs['due_date']
            if 'due_date_time' in inputs and inputs['due_date_time'] is not None:
                data['due_date_time'] = inputs['due_date_time']
            if 'start_date' in inputs and inputs['start_date']:
                data['start_date'] = inputs['start_date']
            if 'tags' in inputs and inputs['tags']:
                data['tags'] = inputs['tags']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}/task",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"task": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Build query params
            params = {}
            if 'include_subtasks' in inputs and inputs['include_subtasks']:
                params['include_subtasks'] = 'true'

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"task": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']
            data = {}

            # Add only provided fields
            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'description' in inputs and inputs['description']:
                data['description'] = inputs['description']
            if 'status' in inputs and inputs['status']:
                data['status'] = inputs['status']
            if 'priority' in inputs and inputs['priority'] is not None:
                data['priority'] = inputs['priority']
            if 'assignees' in inputs and inputs['assignees']:
                data['assignees'] = inputs['assignees']
            if 'due_date' in inputs and inputs['due_date']:
                data['due_date'] = inputs['due_date']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"task": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_tasks")
class GetTasksAction(ActionHandler):
    """Get tasks from a list with optional filtering."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']

            # Build query params
            params = {}
            if 'archived' in inputs and inputs['archived'] is not None:
                params['archived'] = 'true' if inputs['archived'] else 'false'
            if 'page' in inputs:
                params['page'] = inputs['page']
            if 'order_by' in inputs and inputs['order_by']:
                params['order_by'] = inputs['order_by']
            if 'reverse' in inputs and inputs['reverse'] is not None:
                params['reverse'] = 'true' if inputs['reverse'] else 'false'
            if 'subtasks' in inputs and inputs['subtasks'] is not None:
                params['subtasks'] = 'true' if inputs['subtasks'] else 'false'
            if 'statuses' in inputs and inputs['statuses']:
                params['statuses[]'] = inputs['statuses']
            if 'assignees' in inputs and inputs['assignees']:
                params['assignees[]'] = inputs['assignees']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}/task",
                method="GET",
                params=params if params else None
            )

            tasks = response.get('tasks', [])
            return ActionResult(
                data={"tasks": tasks, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"tasks": [], "result": False, "error": str(e)},
                cost_usd=0.0
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

            if 'folder_id' in inputs and inputs['folder_id']:
                parent_type = 'folder'
                parent_id = inputs['folder_id']
            elif 'space_id' in inputs and inputs['space_id']:
                parent_type = 'space'
                parent_id = inputs['space_id']
            else:
                return ActionResult(
                    data={"list": {}, "result": False, "error": "Either folder_id or space_id is required"},
                    cost_usd=0.0
                )

            data = {
                "name": inputs['name']
            }

            # Add optional fields
            if 'content' in inputs and inputs['content']:
                data['content'] = inputs['content']
            if 'due_date' in inputs and inputs['due_date']:
                data['due_date'] = inputs['due_date']
            if 'priority' in inputs and inputs['priority'] is not None:
                data['priority'] = inputs['priority']
            if 'status' in inputs and inputs['status']:
                data['status'] = inputs['status']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/{parent_type}/{parent_id}/list",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_list")
class GetListAction(ActionHandler):
    """Get details of a specific list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}",
                method="GET"
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("update_list")
class UpdateListAction(ActionHandler):
    """Update an existing list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']
            data = {}

            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'content' in inputs and inputs['content']:
                data['content'] = inputs['content']
            if 'due_date' in inputs and inputs['due_date']:
                data['due_date'] = inputs['due_date']
            if 'priority' in inputs and inputs['priority'] is not None:
                data['priority'] = inputs['priority']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"list": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"list": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("delete_list")
class DeleteListAction(ActionHandler):
    """Delete a list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            list_id = inputs['list_id']

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/list/{list_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_lists")
class GetListsAction(ActionHandler):
    """Get all lists in a folder or space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Determine parent (folder or space)
            parent_type = None
            parent_id = None

            if 'folder_id' in inputs and inputs['folder_id']:
                parent_type = 'folder'
                parent_id = inputs['folder_id']
            elif 'space_id' in inputs and inputs['space_id']:
                parent_type = 'space'
                parent_id = inputs['space_id']
            else:
                return ActionResult(
                    data={"lists": [], "result": False, "error": "Either folder_id or space_id is required"},
                    cost_usd=0.0
                )

            params = {}
            if 'archived' in inputs and inputs['archived'] is not None:
                params['archived'] = 'true' if inputs['archived'] else 'false'

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/{parent_type}/{parent_id}/list",
                method="GET",
                params=params if params else None
            )

            lists = response.get('lists', [])
            return ActionResult(
                data={"lists": lists, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"lists": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Folder Handlers ----

@clickup.action("create_folder")
class CreateFolderAction(ActionHandler):
    """Create a new folder in a space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs['space_id']
            data = {"name": inputs['name']}

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/space/{space_id}/folder",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"folder": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_folder")
class GetFolderAction(ActionHandler):
    """Get details of a specific folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs['folder_id']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}",
                method="GET"
            )

            return ActionResult(
                data={"folder": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("update_folder")
class UpdateFolderAction(ActionHandler):
    """Update an existing folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs['folder_id']
            data = {"name": inputs['name']}

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"folder": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"folder": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("delete_folder")
class DeleteFolderAction(ActionHandler):
    """Delete a folder."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            folder_id = inputs['folder_id']

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/folder/{folder_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_folders")
class GetFoldersAction(ActionHandler):
    """Get all folders in a space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs['space_id']

            params = {}
            if 'archived' in inputs and inputs['archived'] is not None:
                params['archived'] = 'true' if inputs['archived'] else 'false'

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/space/{space_id}/folder",
                method="GET",
                params=params if params else None
            )

            folders = response.get('folders', [])
            return ActionResult(
                data={"folders": folders, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"folders": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Space Handlers ----

@clickup.action("get_space")
class GetSpaceAction(ActionHandler):
    """Get details of a specific space."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            space_id = inputs['space_id']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/space/{space_id}",
                method="GET"
            )

            return ActionResult(
                data={"space": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"space": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_spaces")
class GetSpacesAction(ActionHandler):
    """Get all spaces in a team/workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            team_id = inputs['team_id']

            params = {}
            if 'archived' in inputs and inputs['archived'] is not None:
                params['archived'] = 'true' if inputs['archived'] else 'false'

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/team/{team_id}/space",
                method="GET",
                params=params if params else None
            )

            spaces = response.get('spaces', [])
            return ActionResult(
                data={"spaces": spaces, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"spaces": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Team/Workspace Handlers ----

@clickup.action("get_authorized_teams")
class GetAuthorizedTeamsAction(ActionHandler):
    """Get all teams/workspaces the authenticated user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/team",
                method="GET"
            )

            teams = response.get('teams', [])
            return ActionResult(
                data={"teams": teams, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"teams": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Comment Handlers ----

@clickup.action("create_task_comment")
class CreateTaskCommentAction(ActionHandler):
    """Add a comment to a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']
            data = {"comment_text": inputs['comment_text']}

            # Add optional fields
            if 'assignee' in inputs and inputs['assignee']:
                data['assignee'] = inputs['assignee']
            if 'notify_all' in inputs and inputs['notify_all'] is not None:
                data['notify_all'] = inputs['notify_all']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}/comment",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"comment": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comment": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("get_task_comments")
class GetTaskCommentsAction(ActionHandler):
    """Get all comments for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/task/{task_id}/comment",
                method="GET"
            )

            comments = response.get('comments', [])
            return ActionResult(
                data={"comments": comments, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comments": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("update_comment")
class UpdateCommentAction(ActionHandler):
    """Update an existing comment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_id = inputs['comment_id']
            data = {"comment_text": inputs['comment_text']}

            response = await context.fetch(
                f"{CLICKUP_API_BASE_URL}/comment/{comment_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"comment": response, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"comment": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@clickup.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    """Delete a comment."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_id = inputs['comment_id']

            await context.fetch(
                f"{CLICKUP_API_BASE_URL}/comment/{comment_id}",
                method="DELETE"
            )

            return ActionResult(
                data={"result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"result": False, "error": str(e)},
                cost_usd=0.0
            )
