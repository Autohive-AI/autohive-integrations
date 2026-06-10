from autohive_integrations_sdk import ActionError, ActionResult, Integration, ActionHandler, ExecutionContext
from typing import Dict, Any

asana = Integration.load()

ASANA_API_BASE_URL = "https://app.asana.com/api/1.0"


# ---- Task Handlers ----


@asana.action("create_task")
class CreateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"name": inputs["name"]}

            if inputs.get("workspace"):
                data["workspace"] = inputs["workspace"]
            if inputs.get("projects"):
                data["projects"] = inputs["projects"]
            if inputs.get("assignee"):
                data["assignee"] = inputs["assignee"]
            if inputs.get("notes"):
                data["notes"] = inputs["notes"]
            if inputs.get("due_on"):
                data["due_on"] = inputs["due_on"]
            if inputs.get("due_at"):
                data["due_at"] = inputs["due_at"]
            if inputs.get("completed") is not None:
                data["completed"] = inputs["completed"]

            response = await context.fetch(f"{ASANA_API_BASE_URL}/tasks", method="POST", json={"data": data})
            return ActionResult(data={"task": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("get_task")
class GetTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs["task_gid"]

            params = {}
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}", method="GET", params=params if params else None
            )
            return ActionResult(data={"task": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("update_task")
class UpdateTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs["task_gid"]
            data = {}

            if inputs.get("name"):
                data["name"] = inputs["name"]
            if inputs.get("notes"):
                data["notes"] = inputs["notes"]
            if "assignee" in inputs:
                data["assignee"] = inputs["assignee"]
            if "due_on" in inputs:
                data["due_on"] = inputs["due_on"]
            if "due_at" in inputs:
                data["due_at"] = inputs["due_at"]
            if inputs.get("completed") is not None:
                data["completed"] = inputs["completed"]

            response = await context.fetch(f"{ASANA_API_BASE_URL}/tasks/{task_gid}", method="PUT", json={"data": data})
            return ActionResult(data={"task": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("list_tasks")
class ListTasksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("project"):
                params["project"] = inputs["project"]
            if inputs.get("section"):
                params["section"] = inputs["section"]
            if inputs.get("assignee"):
                params["assignee"] = inputs["assignee"]
            if inputs.get("workspace"):
                params["workspace"] = inputs["workspace"]
            if inputs.get("completed_since"):
                params["completed_since"] = inputs["completed_since"]
            if "limit" in inputs:
                params["limit"] = inputs["limit"]
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(f"{ASANA_API_BASE_URL}/tasks", method="GET", params=params)
            return ActionResult(data={"tasks": response.data.get("data", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("delete_task")
class DeleteTaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs["task_gid"]
            await context.fetch(f"{ASANA_API_BASE_URL}/tasks/{task_gid}", method="DELETE")
            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Project Handlers ----


@asana.action("list_projects")
class ListProjectsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("workspace"):
                params["workspace"] = inputs["workspace"]
            if inputs.get("team"):
                params["team"] = inputs["team"]
            if inputs.get("archived") is not None:
                params["archived"] = str(inputs["archived"]).lower()
            if "limit" in inputs:
                params["limit"] = inputs["limit"]

            response = await context.fetch(f"{ASANA_API_BASE_URL}/projects", method="GET", params=params)
            return ActionResult(data={"projects": response.data.get("data", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("get_project")
class GetProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs["project_gid"]

            params = {}
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}", method="GET", params=params if params else None
            )
            return ActionResult(data={"project": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("create_project")
class CreateProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"name": inputs["name"], "workspace": inputs["workspace"]}

            if inputs.get("team"):
                data["team"] = inputs["team"]
            if inputs.get("notes"):
                data["notes"] = inputs["notes"]
            if inputs.get("color"):
                data["color"] = inputs["color"]
            if inputs.get("public") is not None:
                data["public"] = inputs["public"]

            response = await context.fetch(f"{ASANA_API_BASE_URL}/projects", method="POST", json={"data": data})
            return ActionResult(data={"project": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("update_project")
class UpdateProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs["project_gid"]
            data = {}

            if inputs.get("name"):
                data["name"] = inputs["name"]
            if inputs.get("notes"):
                data["notes"] = inputs["notes"]
            if inputs.get("color"):
                data["color"] = inputs["color"]
            if inputs.get("public") is not None:
                data["public"] = inputs["public"]
            if inputs.get("archived") is not None:
                data["archived"] = inputs["archived"]

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}", method="PUT", json={"data": data}
            )
            return ActionResult(data={"project": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("delete_project")
class DeleteProjectAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs["project_gid"]
            await context.fetch(f"{ASANA_API_BASE_URL}/projects/{project_gid}", method="DELETE")
            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("get_project_by_name")
class GetProjectByNameAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            target_name = inputs["name"]
            offset = None

            while True:
                params = {
                    "limit": 100,
                    "opt_fields": "name,gid,workspace,workspace.name,team,team.name,archived,color,notes",
                }

                if inputs.get("workspace"):
                    params["workspace"] = inputs["workspace"]
                if inputs.get("team"):
                    params["team"] = inputs["team"]
                if inputs.get("archived") is not None:
                    params["archived"] = str(inputs["archived"]).lower()
                if offset:
                    params["offset"] = offset

                response = await context.fetch(f"{ASANA_API_BASE_URL}/projects", method="GET", params=params)
                body = response.data
                projects = body.get("data", [])

                for project in projects:
                    if project.get("name") == target_name:
                        return ActionResult(
                            data={
                                "gid": project.get("gid"),
                                "name": project.get("name"),
                                "workspace": project.get("workspace"),
                                "team": project.get("team"),
                                "archived": project.get("archived", False),
                                "color": project.get("color"),
                                "notes": project.get("notes"),
                                "not_found": False,
                            },
                            cost_usd=0.0,
                        )

                next_page = body.get("next_page")
                if next_page and next_page.get("offset"):
                    offset = next_page["offset"]
                else:
                    break

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
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


# ---- Section Handlers ----


@asana.action("list_sections")
class ListSectionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs["project_gid"]

            params = {}
            if "limit" in inputs:
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}/sections", method="GET", params=params if params else None
            )
            return ActionResult(data={"sections": response.data.get("data", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("create_section")
class CreateSectionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_gid = inputs["project_gid"]
            data = {"name": inputs["name"]}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/projects/{project_gid}/sections", method="POST", json={"data": data}
            )
            return ActionResult(data={"section": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("update_section")
class UpdateSectionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            section_gid = inputs["section_gid"]
            data = {"name": inputs["name"]}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/sections/{section_gid}", method="PUT", json={"data": data}
            )
            return ActionResult(data={"section": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("add_task_to_section")
class AddTaskToSectionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            section_gid = inputs["section_gid"]
            data = {"task": inputs["task_gid"]}

            await context.fetch(
                f"{ASANA_API_BASE_URL}/sections/{section_gid}/addTask", method="POST", json={"data": data}
            )
            return ActionResult(data={"added": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Story/Comment Handlers ----


@asana.action("create_story")
class CreateStoryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs["task_gid"]
            data = {"text": inputs["text"]}

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}/stories", method="POST", json={"data": data}
            )
            return ActionResult(data={"story": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("list_stories")
class ListStoriesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_gid = inputs["task_gid"]

            params = {}
            if "limit" in inputs:
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{task_gid}/stories", method="GET", params=params if params else None
            )
            return ActionResult(data={"stories": response.data.get("data", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Subtask Handler ----


@asana.action("create_subtask")
class CreateSubtaskAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            parent_task_gid = inputs["parent_task_gid"]
            data = {"name": inputs["name"]}

            if inputs.get("assignee"):
                data["assignee"] = inputs["assignee"]
            if inputs.get("notes"):
                data["notes"] = inputs["notes"]
            if inputs.get("due_on"):
                data["due_on"] = inputs["due_on"]

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/tasks/{parent_task_gid}/subtasks", method="POST", json={"data": data}
            )
            return ActionResult(data={"subtask": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Workspace Handlers ----


@asana.action("list_workspaces")
class ListWorkspacesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            if "limit" in inputs:
                params["limit"] = inputs["limit"]
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/workspaces", method="GET", params=params if params else None
            )
            return ActionResult(data={"workspaces": response.data.get("data", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@asana.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_gid = inputs["workspace_gid"]

            params = {}
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/workspaces/{workspace_gid}", method="GET", params=params if params else None
            )
            return ActionResult(data={"workspace": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- User Handlers ----


@asana.action("get_user")
class GetUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_gid = inputs.get("user_gid", "me")

            params = {}
            if inputs.get("opt_fields"):
                params["opt_fields"] = ",".join(inputs["opt_fields"])

            response = await context.fetch(
                f"{ASANA_API_BASE_URL}/users/{user_gid}", method="GET", params=params if params else None
            )
            return ActionResult(data={"user": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
