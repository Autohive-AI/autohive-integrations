from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
asana = Integration.load()

# Base URL for Asana API
ASANA_API_BASE_URL = "https://app.asana.com/api/1.0"


# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


# ---- Action Handlers ----

# ---- Task Handlers ----

@asana.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a new task in Asana."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body - Asana requires data wrapped in "data" object
            data = {
                "name": inputs['name']
            }

            # Add optional fields
            if 'workspace' in inputs and inputs['workspace']:
                data['workspace'] = inputs['workspace']
            if 'projects' in inputs and inputs['projects']:
                data['projects'] = inputs['projects']
            if 'assignee' in inputs and inputs['assignee']:
                data['assignee'] = inputs['assignee']
            if 'notes' in inputs and inputs['notes']:
                data['notes'] = inputs['notes']
            if 'due_on' in inputs and inputs['due_on']:
                data['due_on'] = inputs['due_on']
            if 'due_at' in inputs and inputs['due_at']:
                data['due_at'] = inputs['due_at']
            if 'completed' in inputs and inputs['completed'] is not None:
                data['completed'] = inputs['completed']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks",
                method="POST",
                json={"data": data}
            )

            return ActionResult(
                data={"task": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs['task_gid']

            # Build query params
            params = {}
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"task": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs['task_gid']
            data = {}

            # Add only provided fields
            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'notes' in inputs and inputs['notes']:
                data['notes'] = inputs['notes']
            if 'assignee' in inputs:
                data['assignee'] = inputs['assignee']  # Can be null to unassign
            if 'due_on' in inputs:
                data['due_on'] = inputs['due_on']
            if 'due_at' in inputs:
                data['due_at'] = inputs['due_at']
            if 'completed' in inputs and inputs['completed'] is not None:
                data['completed'] = inputs['completed']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}",
                method="PUT",
                json={"data": data}
            )

            return ActionResult(
                data={"task": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"task": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List tasks with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query params - at least one filter is required by Asana
            params = {}

            if 'project' in inputs and inputs['project']:
                params['project'] = inputs['project']
            if 'section' in inputs and inputs['section']:
                params['section'] = inputs['section']
            if 'assignee' in inputs and inputs['assignee']:
                params['assignee'] = inputs['assignee']
            if 'workspace' in inputs and inputs['workspace']:
                params['workspace'] = inputs['workspace']
            if 'completed_since' in inputs and inputs['completed_since']:
                params['completed_since'] = inputs['completed_since']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks",
                method="GET",
                params=params
            )

            tasks = response.get('data', [])
            return ActionResult(
                data={"tasks": tasks, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"tasks": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs['task_gid']

            await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}",
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


# ---- Project Handlers ----

@asana.action("list_projects")
class ListProjectsAction(ActionHandler):
    """List projects in a workspace or team."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'workspace' in inputs and inputs['workspace']:
                params['workspace'] = inputs['workspace']
            if 'team' in inputs and inputs['team']:
                params['team'] = inputs['team']
            if 'archived' in inputs and inputs['archived'] is not None:
                params['archived'] = str(inputs['archived']).lower()
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects",
                method="GET",
                params=params
            )

            projects = response.get('data', [])
            return ActionResult(
                data={"projects": projects, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"projects": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("get_project")
class GetProjectAction(ActionHandler):
    """Get details of a specific project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs['project_gid']

            params = {}
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"project": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"project": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("create_project")
class CreateProjectAction(ActionHandler):
    """Create a new project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "name": inputs['name'],
                "workspace": inputs['workspace']
            }

            if 'team' in inputs and inputs['team']:
                data['team'] = inputs['team']
            if 'notes' in inputs and inputs['notes']:
                data['notes'] = inputs['notes']
            if 'color' in inputs and inputs['color']:
                data['color'] = inputs['color']
            if 'public' in inputs and inputs['public'] is not None:
                data['public'] = inputs['public']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects",
                method="POST",
                json={"data": data}
            )

            return ActionResult(
                data={"project": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"project": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("update_project")
class UpdateProjectAction(ActionHandler):
    """Update an existing project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs['project_gid']
            data = {}

            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'notes' in inputs and inputs['notes']:
                data['notes'] = inputs['notes']
            if 'color' in inputs and inputs['color']:
                data['color'] = inputs['color']
            if 'public' in inputs and inputs['public'] is not None:
                data['public'] = inputs['public']
            if 'archived' in inputs and inputs['archived'] is not None:
                data['archived'] = inputs['archived']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}",
                method="PUT",
                json={"data": data}
            )

            return ActionResult(
                data={"project": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"project": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("delete_project")
class DeleteProjectAction(ActionHandler):
    """Delete a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs['project_gid']

            await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}",
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


@asana.action("get_project_by_name")
class GetProjectByNameAction(ActionHandler):
    """Get a project by its exact name."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            target_name = inputs['name']
            projects_checked = 0
            offset = None

            while True:
                params = {
                    "limit": 100,  # Maximum allowed by Asana API
                    "opt_fields": "name,gid,workspace,workspace.name,team,team.name,archived,color,notes"
                }

                # Add optional filter parameters for better performance
                if 'workspace' in inputs and inputs['workspace']:
                    params['workspace'] = inputs['workspace']
                if 'team' in inputs and inputs['team']:
                    params['team'] = inputs['team']
                if 'archived' in inputs and inputs['archived'] is not None:
                    params['archived'] = str(inputs['archived']).lower()

                if offset:
                    params['offset'] = offset

                response = await context.fetch(
                    f"{ASANA_API_BASE_URL}/projects",
                    method="GET",
                    params=params
                )

                # Check if response is successful
                data = response.get('data', [])

                for project in data:
                    projects_checked += 1
                    if project.get('name') == target_name:
                        return ActionResult(
                            data={
                                "gid": project.get('gid'),
                                "name": project.get('name'),
                                "workspace": project.get('workspace'),
                                "team": project.get('team'),
                                "archived": project.get('archived', False),
                                "color": project.get('color'),
                                "notes": project.get('notes'),
                                "not_found": False,
                                "result": True
                            },
                            cost_usd=0.0
                        )

                # Check for next page
                next_page = response.get('next_page')
                if next_page and next_page.get('offset'):
                    offset = next_page['offset']
                else:
                    break

            # Project not found after checking all pages
            return ActionResult(
                data={
                    "gid": None,
                    "name": None,
                    "workspace": None,
                    "team": None,
                    "archived": None,
                    "color": None,
                    "notes": None,
                    "not_found": True,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={
                    "gid": None,
                    "name": None,
                    "workspace": None,
                    "team": None,
                    "archived": None,
                    "color": None,
                    "notes": None,
                    "not_found": True,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Section Handlers ----

@asana.action("list_sections")
class ListSectionsAction(ActionHandler):
    """List sections in a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs['project_gid']

            params = {}
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}/sections",
                method="GET",
                params=params if params else None
            )

            sections = response.get('data', [])
            return ActionResult(
                data={"sections": sections, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"sections": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("create_section")
class CreateSectionAction(ActionHandler):
    """Create a new section in a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs['project_gid']
            data = {"name": inputs['name']}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}/sections",
                method="POST",
                json={"data": data}
            )

            return ActionResult(
                data={"section": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"section": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("update_section")
class UpdateSectionAction(ActionHandler):
    """Update a section."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            section_gid = inputs['section_gid']
            data = {"name": inputs['name']}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/sections/{section_gid}",
                method="PUT",
                json={"data": data}
            )

            return ActionResult(
                data={"section": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"section": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("add_task_to_section")
class AddTaskToSectionAction(ActionHandler):
    """Add a task to a section."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            section_gid = inputs['section_gid']
            data = {"task": inputs['task_gid']}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/sections/{section_gid}/addTask",
                method="POST",
                json={"data": data}
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


# ---- Story/Comment Handlers ----

@asana.action("create_story")
class CreateStoryAction(ActionHandler):
    """Add a comment to a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs['task_gid']
            data = {"text": inputs['text']}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}/stories",
                method="POST",
                json={"data": data}
            )

            return ActionResult(
                data={"story": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"story": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("list_stories")
class ListStoriesAction(ActionHandler):
    """Get all stories/comments for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs['task_gid']

            params = {}
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}/stories",
                method="GET",
                params=params if params else None
            )

            stories = response.get('data', [])
            return ActionResult(
                data={"stories": stories, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"stories": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Subtask Handler ----

@asana.action("create_subtask")
class CreateSubtaskAction(ActionHandler):
    """Create a subtask under a parent task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            parent_task_gid = inputs['parent_task_gid']
            data = {"name": inputs['name']}

            if 'assignee' in inputs and inputs['assignee']:
                data['assignee'] = inputs['assignee']
            if 'notes' in inputs and inputs['notes']:
                data['notes'] = inputs['notes']
            if 'due_on' in inputs and inputs['due_on']:
                data['due_on'] = inputs['due_on']

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{parent_task_gid}/subtasks",
                method="POST",
                json={"data": data}
            )

            return ActionResult(
                data={"subtask": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"subtask": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Workspace Handlers ----

@asana.action("list_workspaces")
class ListWorkspacesAction(ActionHandler):
    """List all workspaces the authenticated user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if 'limit' in inputs:
                params['limit'] = inputs['limit']
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/workspaces",
                method="GET",
                params=params if params else None
            )

            workspaces = response.get('data', [])
            return ActionResult(
                data={"workspaces": workspaces, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspaces": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@asana.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    """Get details of a specific workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_gid = inputs['workspace_gid']

            params = {}
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/workspaces/{workspace_gid}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"workspace": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"workspace": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- User Handlers ----

@asana.action("get_user")
class GetUserAction(ActionHandler):
    """Get details of a user. Use 'me' to get current authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_gid = inputs.get('user_gid', 'me')

            params = {}
            if 'opt_fields' in inputs and inputs['opt_fields']:
                params['opt_fields'] = ','.join(inputs['opt_fields'])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/users/{user_gid}",
                method="GET",
                params=params if params else None
            )

            return ActionResult(
                data={"user": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},

        except Exception as e:
            return ActionResult(
                data={"subtask": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


