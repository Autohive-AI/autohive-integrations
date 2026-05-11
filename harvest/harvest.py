from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any

# Create the integration using the config.json
harvest = Integration.load()

# Harvest API base URL
HARVEST_API_BASE = "https://api.harvestapp.com/v2"


@harvest.action("create_time_entry")
class CreateTimeEntry(ActionHandler):
    """Create a new time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build the time entry payload
            payload = {
                "project_id": inputs["project_id"],
                "task_id": inputs["task_id"],
                "spent_date": inputs["spent_date"],
            }

            # Add optional fields
            if inputs.get("notes") is not None:
                payload["notes"] = inputs.get("notes")

            if inputs.get("hours") is not None:
                payload["hours"] = inputs.get("hours")

            if inputs.get("started_time") is not None and inputs.get("ended_time") is not None:
                payload["started_time"] = inputs.get("started_time")
                payload["ended_time"] = inputs.get("ended_time")

            if inputs.get("is_running") is not None:
                payload["is_running"] = inputs.get("is_running")

            if inputs.get("user_id") is not None:
                payload["user_id"] = inputs.get("user_id")

            if inputs.get("external_reference") is not None:
                payload["external_reference"] = inputs.get("external_reference")

            response = await context.fetch(f"{HARVEST_API_BASE}/time_entries", method="POST", json=payload)

            return ActionResult(data={"time_entry": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("stop_time_entry")
class StopTimeEntry(ActionHandler):
    """Stop a running time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            response = await context.fetch(f"{HARVEST_API_BASE}/time_entries/{time_entry_id}/stop", method="PATCH")

            return ActionResult(data={"time_entry": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("list_time_entries")
class ListTimeEntries(ActionHandler):
    """List time entries with optional filters"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("client_id") is not None:
                params["client_id"] = inputs.get("client_id")

            if inputs.get("project_id") is not None:
                params["project_id"] = inputs.get("project_id")

            if inputs.get("task_id") is not None:
                params["task_id"] = inputs.get("task_id")

            if inputs.get("is_billed") is not None:
                params["is_billed"] = inputs.get("is_billed")

            if inputs.get("is_running") is not None:
                params["is_running"] = inputs.get("is_running")

            if inputs.get("updated_since") is not None:
                params["updated_since"] = inputs.get("updated_since")

            if inputs.get("from") is not None:
                params["from"] = inputs.get("from")

            if inputs.get("to") is not None:
                params["to"] = inputs.get("to")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")

            response = await context.fetch(f"{HARVEST_API_BASE}/time_entries", method="GET", params=params)
            body = response.data

            return ActionResult(
                data={
                    "time_entries": body.get("time_entries", []),
                    "per_page": body.get("per_page"),
                    "total_pages": body.get("total_pages"),
                    "total_entries": body.get("total_entries"),
                    "next_page": body.get("next_page"),
                    "previous_page": body.get("previous_page"),
                    "page": body.get("page"),
                    "links": body.get("links"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("update_time_entry")
class UpdateTimeEntry(ActionHandler):
    """Update an existing time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            # Build the update payload
            payload = {}

            if inputs.get("project_id") is not None:
                payload["project_id"] = inputs.get("project_id")

            if inputs.get("task_id") is not None:
                payload["task_id"] = inputs.get("task_id")

            if inputs.get("spent_date") is not None:
                payload["spent_date"] = inputs.get("spent_date")

            if inputs.get("notes") is not None:
                payload["notes"] = inputs.get("notes")

            if inputs.get("hours") is not None:
                payload["hours"] = inputs.get("hours")

            if inputs.get("started_time") is not None:
                payload["started_time"] = inputs.get("started_time")

            if inputs.get("ended_time") is not None:
                payload["ended_time"] = inputs.get("ended_time")

            if inputs.get("external_reference") is not None:
                payload["external_reference"] = inputs.get("external_reference")

            response = await context.fetch(
                f"{HARVEST_API_BASE}/time_entries/{time_entry_id}",
                method="PATCH",
                json=payload,
            )

            return ActionResult(data={"time_entry": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("delete_time_entry")
class DeleteTimeEntry(ActionHandler):
    """Delete a time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            await context.fetch(f"{HARVEST_API_BASE}/time_entries/{time_entry_id}", method="DELETE")

            return ActionResult(
                data={
                    "message": f"Time entry {time_entry_id} deleted successfully",
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("list_projects")
class ListProjects(ActionHandler):
    """List all projects"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("is_active") is not None:
                params["is_active"] = inputs.get("is_active")

            if inputs.get("client_id") is not None:
                params["client_id"] = inputs.get("client_id")

            if inputs.get("updated_since") is not None:
                params["updated_since"] = inputs.get("updated_since")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")

            response = await context.fetch(f"{HARVEST_API_BASE}/projects", method="GET", params=params)
            body = response.data

            return ActionResult(
                data={
                    "projects": body.get("projects", []),
                    "per_page": body.get("per_page"),
                    "total_pages": body.get("total_pages"),
                    "total_entries": body.get("total_entries"),
                    "next_page": body.get("next_page"),
                    "previous_page": body.get("previous_page"),
                    "page": body.get("page"),
                    "links": body.get("links"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("get_project")
class GetProject(ActionHandler):
    """Get a specific project by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            response = await context.fetch(f"{HARVEST_API_BASE}/projects/{project_id}", method="GET")

            return ActionResult(data={"project": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("list_clients")
class ListClients(ActionHandler):
    """List all clients"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("is_active") is not None:
                params["is_active"] = inputs.get("is_active")

            if inputs.get("updated_since") is not None:
                params["updated_since"] = inputs.get("updated_since")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")

            response = await context.fetch(f"{HARVEST_API_BASE}/clients", method="GET", params=params)
            body = response.data

            return ActionResult(
                data={
                    "clients": body.get("clients", []),
                    "per_page": body.get("per_page"),
                    "total_pages": body.get("total_pages"),
                    "total_entries": body.get("total_entries"),
                    "next_page": body.get("next_page"),
                    "previous_page": body.get("previous_page"),
                    "page": body.get("page"),
                    "links": body.get("links"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("list_tasks")
class ListTasks(ActionHandler):
    """List all tasks"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("is_active") is not None:
                params["is_active"] = inputs.get("is_active")

            if inputs.get("updated_since") is not None:
                params["updated_since"] = inputs.get("updated_since")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")

            response = await context.fetch(f"{HARVEST_API_BASE}/tasks", method="GET", params=params)
            body = response.data

            return ActionResult(
                data={
                    "tasks": body.get("tasks", []),
                    "per_page": body.get("per_page"),
                    "total_pages": body.get("total_pages"),
                    "total_entries": body.get("total_entries"),
                    "next_page": body.get("next_page"),
                    "previous_page": body.get("previous_page"),
                    "page": body.get("page"),
                    "links": body.get("links"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@harvest.action("list_users")
class ListUsers(ActionHandler):
    """List all users (team members)"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("is_active") is not None:
                params["is_active"] = inputs.get("is_active")

            if inputs.get("updated_since") is not None:
                params["updated_since"] = inputs.get("updated_since")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("per_page") is not None:
                params["per_page"] = inputs.get("per_page")

            response = await context.fetch(f"{HARVEST_API_BASE}/users", method="GET", params=params)
            body = response.data

            return ActionResult(
                data={
                    "users": body.get("users", []),
                    "per_page": body.get("per_page"),
                    "total_pages": body.get("total_pages"),
                    "total_entries": body.get("total_entries"),
                    "next_page": body.get("next_page"),
                    "previous_page": body.get("previous_page"),
                    "page": body.get("page"),
                    "links": body.get("links"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))
