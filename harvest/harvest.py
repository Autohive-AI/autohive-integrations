from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional

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
                "spent_date": inputs["spent_date"]
            }

            # Add optional fields
            if "notes" in inputs:
                payload["notes"] = inputs["notes"]

            if "hours" in inputs:
                payload["hours"] = inputs["hours"]

            if "started_time" in inputs and "ended_time" in inputs:
                payload["started_time"] = inputs["started_time"]
                payload["ended_time"] = inputs["ended_time"]

            if "is_running" in inputs:
                payload["is_running"] = inputs["is_running"]

            if "user_id" in inputs:
                payload["user_id"] = inputs["user_id"]

            if "external_reference" in inputs:
                payload["external_reference"] = inputs["external_reference"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/time_entries",
                method="POST",
                json=payload
            )

            return {
                "success": True,
                "time_entry": response
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("stop_time_entry")
class StopTimeEntry(ActionHandler):
    """Stop a running time entry"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/time_entries/{time_entry_id}/stop",
                method="PATCH"
            )

            return {
                "success": True,
                "time_entry": response
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("list_time_entries")
class ListTimeEntries(ActionHandler):
    """List time entries with optional filters"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if "user_id" in inputs:
                params["user_id"] = inputs["user_id"]

            if "client_id" in inputs:
                params["client_id"] = inputs["client_id"]

            if "project_id" in inputs:
                params["project_id"] = inputs["project_id"]

            if "task_id" in inputs:
                params["task_id"] = inputs["task_id"]

            if "is_billed" in inputs:
                params["is_billed"] = inputs["is_billed"]

            if "is_running" in inputs:
                params["is_running"] = inputs["is_running"]

            if "updated_since" in inputs:
                params["updated_since"] = inputs["updated_since"]

            if "from" in inputs:
                params["from"] = inputs["from"]

            if "to" in inputs:
                params["to"] = inputs["to"]

            if "page" in inputs:
                params["page"] = inputs["page"]

            if "per_page" in inputs:
                params["per_page"] = inputs["per_page"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/time_entries",
                method="GET",
                params=params
            )

            return {
                "success": True,
                "time_entries": response.get("time_entries", []),
                "per_page": response.get("per_page"),
                "total_pages": response.get("total_pages"),
                "total_entries": response.get("total_entries"),
                "next_page": response.get("next_page"),
                "previous_page": response.get("previous_page"),
                "page": response.get("page"),
                "links": response.get("links")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("update_time_entry")
class UpdateTimeEntry(ActionHandler):
    """Update an existing time entry"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            # Build the update payload
            payload = {}

            if "project_id" in inputs:
                payload["project_id"] = inputs["project_id"]

            if "task_id" in inputs:
                payload["task_id"] = inputs["task_id"]

            if "spent_date" in inputs:
                payload["spent_date"] = inputs["spent_date"]

            if "notes" in inputs:
                payload["notes"] = inputs["notes"]

            if "hours" in inputs:
                payload["hours"] = inputs["hours"]

            if "started_time" in inputs:
                payload["started_time"] = inputs["started_time"]

            if "ended_time" in inputs:
                payload["ended_time"] = inputs["ended_time"]

            if "external_reference" in inputs:
                payload["external_reference"] = inputs["external_reference"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/time_entries/{time_entry_id}",
                method="PATCH",
                json=payload
            )

            return {
                "success": True,
                "time_entry": response
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("delete_time_entry")
class DeleteTimeEntry(ActionHandler):
    """Delete a time entry"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            time_entry_id = inputs["time_entry_id"]

            await context.fetch(
                f"{HARVEST_API_BASE}/time_entries/{time_entry_id}",
                method="DELETE"
            )

            return {
                "success": True,
                "message": f"Time entry {time_entry_id} deleted successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("list_projects")
class ListProjects(ActionHandler):
    """List all projects"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if "is_active" in inputs:
                params["is_active"] = inputs["is_active"]

            if "client_id" in inputs:
                params["client_id"] = inputs["client_id"]

            if "updated_since" in inputs:
                params["updated_since"] = inputs["updated_since"]

            if "page" in inputs:
                params["page"] = inputs["page"]

            if "per_page" in inputs:
                params["per_page"] = inputs["per_page"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/projects",
                method="GET",
                params=params
            )

            return {
                "success": True,
                "projects": response.get("projects", []),
                "per_page": response.get("per_page"),
                "total_pages": response.get("total_pages"),
                "total_entries": response.get("total_entries"),
                "next_page": response.get("next_page"),
                "previous_page": response.get("previous_page"),
                "page": response.get("page"),
                "links": response.get("links")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("get_project")
class GetProject(ActionHandler):
    """Get a specific project by ID"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/projects/{project_id}",
                method="GET"
            )

            return {
                "success": True,
                "project": response
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("list_clients")
class ListClients(ActionHandler):
    """List all clients"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if "is_active" in inputs:
                params["is_active"] = inputs["is_active"]

            if "updated_since" in inputs:
                params["updated_since"] = inputs["updated_since"]

            if "page" in inputs:
                params["page"] = inputs["page"]

            if "per_page" in inputs:
                params["per_page"] = inputs["per_page"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/clients",
                method="GET",
                params=params
            )

            return {
                "success": True,
                "clients": response.get("clients", []),
                "per_page": response.get("per_page"),
                "total_pages": response.get("total_pages"),
                "total_entries": response.get("total_entries"),
                "next_page": response.get("next_page"),
                "previous_page": response.get("previous_page"),
                "page": response.get("page"),
                "links": response.get("links")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("list_tasks")
class ListTasks(ActionHandler):
    """List all tasks"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if "is_active" in inputs:
                params["is_active"] = inputs["is_active"]

            if "updated_since" in inputs:
                params["updated_since"] = inputs["updated_since"]

            if "page" in inputs:
                params["page"] = inputs["page"]

            if "per_page" in inputs:
                params["per_page"] = inputs["per_page"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/tasks",
                method="GET",
                params=params
            )

            return {
                "success": True,
                "tasks": response.get("tasks", []),
                "per_page": response.get("per_page"),
                "total_pages": response.get("total_pages"),
                "total_entries": response.get("total_entries"),
                "next_page": response.get("next_page"),
                "previous_page": response.get("previous_page"),
                "page": response.get("page"),
                "links": response.get("links")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

@harvest.action("list_users")
class ListUsers(ActionHandler):
    """List all users (team members)"""
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if "is_active" in inputs:
                params["is_active"] = inputs["is_active"]

            if "updated_since" in inputs:
                params["updated_since"] = inputs["updated_since"]

            if "page" in inputs:
                params["page"] = inputs["page"]

            if "per_page" in inputs:
                params["per_page"] = inputs["per_page"]

            response = await context.fetch(
                f"{HARVEST_API_BASE}/users",
                method="GET",
                params=params
            )

            return {
                "success": True,
                "users": response.get("users", []),
                "per_page": response.get("per_page"),
                "total_pages": response.get("total_pages"),
                "total_entries": response.get("total_entries"),
                "next_page": response.get("next_page"),
                "previous_page": response.get("previous_page"),
                "page": response.get("page"),
                "links": response.get("links")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
