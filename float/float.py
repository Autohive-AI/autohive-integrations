from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult,
    ConnectedAccountHandler, ConnectedAccountInfo
)
from typing import Dict, Any

# Create the integration using the config.json
float = Integration.load()

# Base URL for Float API
FLOAT_API_BASE_URL = "https://api.float.com/v3"

# Rate limiting constants
# Primary endpoints: 200 GET/min, 100 non-GET/min, 10 GET/sec burst, 4 non-GET/sec burst
# Reports endpoints: 30 GET/min
GET_REQUESTS_PER_MINUTE = 200
NON_GET_REQUESTS_PER_MINUTE = 100
GET_BURST_PER_SECOND = 10
NON_GET_BURST_PER_SECOND = 4
REPORTS_REQUESTS_PER_MINUTE = 30


# ---- Helper Functions ----

def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Float API requests.
    Float uses Bearer token authentication with a required User-Agent header.

    Float API requires a User-Agent header that identifies your application
    and provides a contact email in the format: "App Name (email@example.com)"

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with Authorization and User-Agent headers
    """
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")
    application_name = credentials.get("application_name", "Autohive Float Integration")
    contact_email = credentials.get("contact_email", "support@autohive.com")

    # Build User-Agent in Float's required format: "Application Name (contact@email.com)"
    user_agent = f"{application_name} ({contact_email})"

    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": user_agent,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def handle_pagination_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract pagination information from response headers and add to response data.

    Args:
        response: API response containing data and potentially pagination headers

    Returns:
        Dictionary with data and pagination information
    """
    # Float API returns pagination info in headers, but the SDK's fetch
    # method should handle this. We'll structure the response consistently.
    return response


# ---- Connected Account Handler ----

@float.connected_account()
class FloatConnectedAccountHandler(ConnectedAccountHandler):
    """Handler for retrieving connected account information from Float"""

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch Float account information for the connected user.

        This method is called once when a user authorizes the integration.
        The returned information is cached in the database.

        Args:
            context: ExecutionContext containing auth credentials and metadata

        Returns:
            ConnectedAccountInfo with user/account information
        """
        headers = get_auth_headers(context)

        try:
            # Float API provides account information through the /account endpoint
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/account",
                method="GET",
                headers=headers
            )

            # Extract account information
            # Float typically returns account details including company name
            account_data = response if isinstance(response, dict) else {}

            # Try to get the current user's information from the account endpoint
            # Float API typically returns the account owner's information
            user_email = account_data.get("owner_email") or account_data.get("email")
            user_name = account_data.get("owner_name") or account_data.get("name")

            # Get company/organization name from account
            organization = account_data.get("name") or account_data.get("company_name")

            # Parse name into first/last if available
            first_name = None
            last_name = None
            if user_name:
                name_parts = user_name.split(maxsplit=1)
                first_name = name_parts[0] if len(name_parts) > 0 else None
                last_name = name_parts[1] if len(name_parts) > 1 else None

            return ConnectedAccountInfo(
                email=user_email,
                username=user_email.split('@')[0] if user_email else None,
                first_name=first_name,
                last_name=last_name,
                organization=organization,
                user_id=str(account_data.get("account_id", "")) if account_data.get("account_id") else None
            )

        except Exception as e:
            # Log the error but don't fail - return minimal info
            print(f"Warning: Could not fetch Float account info: {str(e)}")
            return ConnectedAccountInfo(
                organization="Float Account"
            )


# ---- People Resource Actions ----

@float.action("list_people")
class ListPeopleHandler(ActionHandler):
    """Handler for listing all people in the Float account"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all people with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters (active, department_id, modified_since, page, per_page, fields, sort)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of people and pagination info
        """
        params = {}

        # Add optional filters
        if "active" in inputs and inputs["active"] is not None:
            params["active"] = 1 if inputs["active"] else 0

        if "department_id" in inputs and inputs["department_id"]:
            params["department_id"] = inputs["department_id"]

        if "modified_since" in inputs and inputs["modified_since"]:
            params["modified_since"] = inputs["modified_since"]

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        if "fields" in inputs and inputs["fields"]:
            params["fields"] = inputs["fields"]

        if "sort" in inputs and inputs["sort"]:
            params["sort"] = inputs["sort"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/people",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list people: {str(e)}")


@float.action("get_person")
class GetPersonHandler(ActionHandler):
    """Handler for retrieving a specific person by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific person.

        Args:
            inputs: Dictionary containing 'people_id' and optional 'expand' parameter
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing person details
        """
        people_id = inputs["people_id"]
        params = {}

        if "expand" in inputs and inputs["expand"]:
            params["expand"] = inputs["expand"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/people/{people_id}",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get person {people_id}: {str(e)}")


@float.action("create_person")
class CreatePersonHandler(ActionHandler):
    """Handler for creating a new person"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new person in Float.

        Args:
            inputs: Dictionary containing 'name' (required) and optional fields
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created person details
        """
        request_body = {
            "name": inputs["name"]
        }

        # Add optional fields
        optional_fields = [
            "email", "job_title", "department_id", "role_id", "people_type_id",
            "active", "employee_type", "work_days_hours", "start_date", "end_date",
            "notes", "tags", "avatar_file", "cost_rate", "default_hourly_rate"
        ]

        for field in optional_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/people",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create person: {str(e)}")


@float.action("update_person")
class UpdatePersonHandler(ActionHandler):
    """Handler for updating an existing person"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing person's information.

        Args:
            inputs: Dictionary containing 'people_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated person details
        """
        people_id = inputs["people_id"]
        request_body = {}

        # Add updatable fields
        updatable_fields = [
            "name", "email", "job_title", "department_id", "role_id", "people_type_id",
            "active", "employee_type", "work_days_hours", "start_date", "end_date",
            "notes", "tags", "avatar_file", "cost_rate", "default_hourly_rate", "effective_date"
        ]

        for field in updatable_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        params = {}
        if "expand" in inputs and inputs["expand"]:
            params["expand"] = inputs["expand"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/people/{people_id}",
                method="PATCH",
                headers=headers,
                json=request_body,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update person {people_id}: {str(e)}")


@float.action("delete_person")
class DeletePersonHandler(ActionHandler):
    """Handler for deleting a person"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a person from Float.

        Args:
            inputs: Dictionary containing 'people_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        people_id = inputs["people_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/people/{people_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={"success": True, "message": f"Person {people_id} deleted successfully"},
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete person {people_id}: {str(e)}")


# ---- Projects Resource Actions ----

@float.action("list_projects")
class ListProjectsHandler(ActionHandler):
    """Handler for listing all projects"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all projects with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of projects
        """
        params = {}

        # Add optional filters
        optional_params = [
            "active", "client_id", "project_manager", "modified_since",
            "start_date", "end_date", "page", "per_page", "fields", "sort"
        ]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "active":
                    params[param] = 1 if inputs[param] else 0
                elif param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/projects",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list projects: {str(e)}")


@float.action("get_project")
class GetProjectHandler(ActionHandler):
    """Handler for retrieving a specific project by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific project.

        Args:
            inputs: Dictionary containing 'project_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing project details
        """
        project_id = inputs["project_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/projects/{project_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get project {project_id}: {str(e)}")


@float.action("create_project")
class CreateProjectHandler(ActionHandler):
    """Handler for creating a new project"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new project in Float.

        Args:
            inputs: Dictionary containing 'name' (required) and optional fields
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created project details
        """
        request_body = {
            "name": inputs["name"]
        }

        # Add optional fields
        optional_fields = [
            "client_id", "color", "project_code", "tags", "project_team",
            "project_manager", "all_pms_schedule", "status", "budget_type",
            "budget_total", "budget_per_phase", "non_billable", "start_date",
            "end_date", "active", "notes"
        ]

        for field in optional_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/projects",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create project: {str(e)}")


@float.action("update_project")
class UpdateProjectHandler(ActionHandler):
    """Handler for updating an existing project"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing project's information.

        Args:
            inputs: Dictionary containing 'project_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated project details
        """
        project_id = inputs["project_id"]
        request_body = {}

        # Add updatable fields
        updatable_fields = [
            "name", "client_id", "color", "project_code", "tags", "project_team",
            "project_manager", "all_pms_schedule", "status", "budget_type",
            "budget_total", "budget_per_phase", "non_billable", "start_date",
            "end_date", "active", "notes"
        ]

        for field in updatable_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/projects/{project_id}",
                method="PATCH",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update project {project_id}: {str(e)}")


@float.action("delete_project")
class DeleteProjectHandler(ActionHandler):
    """Handler for deleting a project"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a project from Float.

        Args:
            inputs: Dictionary containing 'project_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        project_id = inputs["project_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/projects/{project_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "success": True,
                    "message": f"Project {project_id} deleted successfully"
                },
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete project {project_id}: {str(e)}")


# ---- Tasks/Allocations Resource Actions ----

@float.action("list_tasks")
class ListTasksHandler(ActionHandler):
    """Handler for listing all tasks/allocations"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all tasks/allocations with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of tasks
        """
        params = {}

        # Add optional filters
        optional_params = [
            "people_id", "project_id", "start_date", "end_date",
            "modified_since", "page", "per_page", "fields", "sort"
        ]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/tasks",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list tasks: {str(e)}")


@float.action("get_task")
class GetTaskHandler(ActionHandler):
    """Handler for retrieving a specific task by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific task/allocation.

        Args:
            inputs: Dictionary containing 'task_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing task details
        """
        task_id = inputs["task_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/tasks/{task_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get task {task_id}: {str(e)}")


@float.action("create_task")
class CreateTaskHandler(ActionHandler):
    """Handler for creating a new task/allocation"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new task/allocation in Float.

        Args:
            inputs: Dictionary containing required fields (people_id, project_id, start_date, end_date, hours)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created task details
        """
        request_body = {
            "people_id": inputs["people_id"],
            "project_id": inputs["project_id"],
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "hours": inputs["hours"]
        }

        # Add optional fields
        optional_fields = [
            "name", "notes", "status", "billable", "repeat_state",
            "repeat_end_date", "root_task_id", "parent_task_id"
        ]

        for field in optional_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/tasks",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create task: {str(e)}")


@float.action("update_task")
class UpdateTaskHandler(ActionHandler):
    """Handler for updating an existing task/allocation"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing task/allocation's information.

        Args:
            inputs: Dictionary containing 'task_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated task details
        """
        task_id = inputs["task_id"]
        request_body = {}

        # Add updatable fields
        updatable_fields = [
            "people_id", "project_id", "start_date", "end_date", "hours",
            "name", "notes", "status", "billable", "repeat_state",
            "repeat_end_date", "root_task_id", "parent_task_id"
        ]

        for field in updatable_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/tasks/{task_id}",
                method="PATCH",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update task {task_id}: {str(e)}")


@float.action("delete_task")
class DeleteTaskHandler(ActionHandler):
    """Handler for deleting a task/allocation"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a task/allocation from Float.

        Args:
            inputs: Dictionary containing 'task_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        task_id = inputs["task_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/tasks/{task_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "success": True,
                    "message": f"Task {task_id} deleted successfully"
                },
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete task {task_id}: {str(e)}")


# ---- Time Off Resource Actions ----

@float.action("list_time_off")
class ListTimeOffHandler(ActionHandler):
    """Handler for listing all time off entries"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all time off entries with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of time off entries
        """
        params = {}

        # Add optional filters
        optional_params = [
            "people_id", "timeoff_type_id", "start_date", "end_date",
            "modified_since", "page", "per_page", "fields", "sort"
        ]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoffs",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list time off: {str(e)}")


@float.action("get_time_off")
class GetTimeOffHandler(ActionHandler):
    """Handler for retrieving a specific time off entry by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific time off entry.

        Args:
            inputs: Dictionary containing 'timeoff_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing time off details
        """
        timeoff_id = inputs["timeoff_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoffs/{timeoff_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get time off {timeoff_id}: {str(e)}")


@float.action("create_time_off")
class CreateTimeOffHandler(ActionHandler):
    """Handler for creating a new time off entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new time off entry in Float.

        Args:
            inputs: Dictionary containing required fields (people_id, timeoff_type_id, start_date, end_date, hours)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created time off details
        """
        request_body = {
            "people_id": inputs["people_id"],
            "timeoff_type_id": inputs["timeoff_type_id"],
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "hours": inputs["hours"]
        }

        # Add optional fields
        if "full_day" in inputs and inputs["full_day"] is not None:
            request_body["full_day"] = inputs["full_day"]

        if "notes" in inputs and inputs["notes"]:
            request_body["notes"] = inputs["notes"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoffs",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create time off: {str(e)}")


@float.action("update_time_off")
class UpdateTimeOffHandler(ActionHandler):
    """Handler for updating an existing time off entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing time off entry's information.

        Args:
            inputs: Dictionary containing 'timeoff_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated time off details
        """
        timeoff_id = inputs["timeoff_id"]
        request_body = {}

        # Add updatable fields
        updatable_fields = [
            "people_id", "timeoff_type_id", "start_date", "end_date",
            "hours", "full_day", "notes"
        ]

        for field in updatable_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoffs/{timeoff_id}",
                method="PATCH",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update time off {timeoff_id}: {str(e)}")


@float.action("delete_time_off")
class DeleteTimeOffHandler(ActionHandler):
    """Handler for deleting a time off entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a time off entry from Float.

        Args:
            inputs: Dictionary containing 'timeoff_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        timeoff_id = inputs["timeoff_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoffs/{timeoff_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={"success": True, "message": f"Time off {timeoff_id} deleted successfully"},
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete time off {timeoff_id}: {str(e)}")


# ---- Logged Time Resource Actions ----

@float.action("list_logged_time")
class ListLoggedTimeHandler(ActionHandler):
    """Handler for listing all logged time entries"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all logged time entries with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of logged time entries
        """
        params = {}

        # Add optional filters
        optional_params = [
            "people_id", "project_id", "start_date", "end_date",
            "modified_since", "page", "per_page", "fields", "sort"
        ]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/logged-time",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list logged time: {str(e)}")


@float.action("get_logged_time")
class GetLoggedTimeHandler(ActionHandler):
    """Handler for retrieving a specific logged time entry by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific logged time entry.

        Args:
            inputs: Dictionary containing 'logged_time_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing logged time details
        """
        logged_time_id = inputs["logged_time_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/logged-time/{logged_time_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get logged time {logged_time_id}: {str(e)}")


@float.action("create_logged_time")
class CreateLoggedTimeHandler(ActionHandler):
    """Handler for creating a new logged time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new logged time entry in Float.

        Args:
            inputs: Dictionary containing required fields (people_id, project_id, date, hours)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created logged time details
        """
        request_body = {
            "people_id": inputs["people_id"],
            "project_id": inputs["project_id"],
            "date": inputs["date"],
            "hours": inputs["hours"]
        }

        # Add optional fields
        if "task_id" in inputs and inputs["task_id"]:
            request_body["task_id"] = inputs["task_id"]

        if "notes" in inputs and inputs["notes"]:
            request_body["notes"] = inputs["notes"]

        if "billable" in inputs and inputs["billable"] is not None:
            request_body["billable"] = inputs["billable"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/logged-time",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create logged time: {str(e)}")


@float.action("update_logged_time")
class UpdateLoggedTimeHandler(ActionHandler):
    """Handler for updating an existing logged time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing logged time entry's information.

        Args:
            inputs: Dictionary containing 'logged_time_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated logged time details
        """
        logged_time_id = inputs["logged_time_id"]
        request_body = {}

        # Add updatable fields
        updatable_fields = [
            "people_id", "project_id", "date", "hours", "task_id", "notes", "billable"
        ]

        for field in updatable_fields:
            if field in inputs and inputs[field] is not None:
                request_body[field] = inputs[field]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/logged-time/{logged_time_id}",
                method="PATCH",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update logged time {logged_time_id}: {str(e)}")


@float.action("delete_logged_time")
class DeleteLoggedTimeHandler(ActionHandler):
    """Handler for deleting a logged time entry"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a logged time entry from Float.

        Args:
            inputs: Dictionary containing 'logged_time_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        logged_time_id = inputs["logged_time_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/logged-time/{logged_time_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "success": True,
                    "message": f"Logged time {logged_time_id} deleted successfully"
                },
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete logged time {logged_time_id}: {str(e)}")


# ---- Clients Resource Actions ----

@float.action("list_clients")
class ListClientsHandler(ActionHandler):
    """Handler for listing all clients"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all clients with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of clients
        """
        params = {}

        # Add optional filters
        optional_params = [
            "active", "modified_since", "page", "per_page", "fields", "sort"
        ]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "active":
                    params[param] = 1 if inputs[param] else 0
                elif param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/clients",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list clients: {str(e)}")


@float.action("get_client")
class GetClientHandler(ActionHandler):
    """Handler for retrieving a specific client by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific client.

        Args:
            inputs: Dictionary containing 'client_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing client details
        """
        client_id = inputs["client_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/clients/{client_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get client {client_id}: {str(e)}")


@float.action("create_client")
class CreateClientHandler(ActionHandler):
    """Handler for creating a new client"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Create a new client in Float.

        Args:
            inputs: Dictionary containing 'name' (required) and optional fields
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing created client details
        """
        request_body = {
            "name": inputs["name"]
        }

        # Add optional fields
        if "active" in inputs and inputs["active"] is not None:
            request_body["active"] = inputs["active"]

        if "notes" in inputs and inputs["notes"]:
            request_body["notes"] = inputs["notes"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/clients",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to create client: {str(e)}")


@float.action("update_client")
class UpdateClientHandler(ActionHandler):
    """Handler for updating an existing client"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Update an existing client's information.

        Args:
            inputs: Dictionary containing 'client_id' and fields to update
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing updated client details
        """
        client_id = inputs["client_id"]
        request_body = {}

        # Add updatable fields
        if "name" in inputs and inputs["name"]:
            request_body["name"] = inputs["name"]

        if "active" in inputs and inputs["active"] is not None:
            request_body["active"] = inputs["active"]

        if "notes" in inputs and inputs["notes"] is not None:
            request_body["notes"] = inputs["notes"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/clients/{client_id}",
                method="PATCH",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to update client {client_id}: {str(e)}")


@float.action("delete_client")
class DeleteClientHandler(ActionHandler):
    """Handler for deleting a client"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Delete a client from Float.

        Args:
            inputs: Dictionary containing 'client_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing success message
        """
        client_id = inputs["client_id"]
        headers = get_auth_headers(context)

        try:
            await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/clients/{client_id}",
                method="DELETE",
                headers=headers
            )

            return ActionResult(
                data={
                    "success": True,
                    "message": f"Client {client_id} deleted successfully"
                },
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to delete client {client_id}: {str(e)}")


# ---- Departments Resource Actions ----

@float.action("list_departments")
class ListDepartmentsHandler(ActionHandler):
    """Handler for listing all departments"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all departments with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of departments
        """
        params = {}

        # Add optional filters
        optional_params = ["page", "per_page", "fields", "sort"]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/departments",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list departments: {str(e)}")


@float.action("get_department")
class GetDepartmentHandler(ActionHandler):
    """Handler for retrieving a specific department by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific department.

        Args:
            inputs: Dictionary containing 'department_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing department details
        """
        department_id = inputs["department_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/departments/{department_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get department {department_id}: {str(e)}")


# ---- Roles Resource Actions ----

@float.action("list_roles")
class ListRolesHandler(ActionHandler):
    """Handler for listing all roles"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all roles with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of roles
        """
        params = {}

        # Add optional filters
        optional_params = ["page", "per_page", "fields", "sort"]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/roles",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list roles: {str(e)}")


@float.action("get_role")
class GetRoleHandler(ActionHandler):
    """Handler for retrieving a specific role by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific role.

        Args:
            inputs: Dictionary containing 'role_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing role details
        """
        role_id = inputs["role_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/roles/{role_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get role {role_id}: {str(e)}")


# ---- Time Off Types Resource Actions ----

@float.action("list_time_off_types")
class ListTimeOffTypesHandler(ActionHandler):
    """Handler for listing all time off types"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all time off types.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of time off types
        """
        params = {}

        # Add optional filters
        optional_params = ["page", "per_page", "fields", "sort"]

        for param in optional_params:
            if param in inputs and inputs[param] is not None:
                if param == "per_page":
                    params["per-page"] = inputs[param]
                else:
                    params[param] = inputs[param]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoff-types",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list time off types: {str(e)}")


@float.action("get_time_off_type")
class GetTimeOffTypeHandler(ActionHandler):
    """Handler for retrieving a specific time off type by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific time off type.

        Args:
            inputs: Dictionary containing 'timeoff_type_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing time off type details
        """
        timeoff_type_id = inputs["timeoff_type_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/timeoff-types/{timeoff_type_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get time off type {timeoff_type_id}: {str(e)}")


# ---- Accounts Resource Actions ----

@float.action("list_accounts")
class ListAccountsHandler(ActionHandler):
    """Handler for listing all accounts"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all accounts with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of accounts
        """
        params = {}

        # Add optional filters
        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/accounts",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list accounts: {str(e)}")


@float.action("get_account")
class GetAccountHandler(ActionHandler):
    """Handler for retrieving a specific account by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific account.

        Args:
            inputs: Dictionary containing 'account_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing account details
        """
        account_id = inputs["account_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/accounts/{account_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get account {account_id}: {str(e)}")


# ---- Statuses Resource Actions ----

@float.action("list_statuses")
class ListStatusesHandler(ActionHandler):
    """Handler for listing all statuses"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all statuses with optional pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of statuses
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/status",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list statuses: {str(e)}")


@float.action("get_status")
class GetStatusHandler(ActionHandler):
    """Handler for retrieving a specific status by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific status.

        Args:
            inputs: Dictionary containing 'status_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing status details
        """
        status_id = inputs["status_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/status/{status_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get status {status_id}: {str(e)}")


# ---- Public Holidays Resource Actions ----

@float.action("list_public_holidays")
class ListPublicHolidaysHandler(ActionHandler):
    """Handler for listing all public holidays"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all public holidays with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of public holidays
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/public-holidays",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list public holidays: {str(e)}")


@float.action("get_public_holiday")
class GetPublicHolidayHandler(ActionHandler):
    """Handler for retrieving a specific public holiday by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific public holiday.

        Args:
            inputs: Dictionary containing 'public_holiday_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing public holiday details
        """
        public_holiday_id = inputs["public_holiday_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/public-holidays/{public_holiday_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get public holiday {public_holiday_id}: {str(e)}")


# ---- Team Holidays Resource Actions ----

@float.action("list_team_holidays")
class ListTeamHolidaysHandler(ActionHandler):
    """Handler for listing all team holidays"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all team holidays with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of team holidays
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/holidays",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list team holidays: {str(e)}")


@float.action("get_team_holiday")
class GetTeamHolidayHandler(ActionHandler):
    """Handler for retrieving a specific team holiday by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific team holiday.

        Args:
            inputs: Dictionary containing 'holiday_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing team holiday details
        """
        holiday_id = inputs["holiday_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/holidays/{holiday_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get team holiday {holiday_id}: {str(e)}")


# ---- Project Stages Resource Actions ----

@float.action("list_project_stages")
class ListProjectStagesHandler(ActionHandler):
    """Handler for listing all project stages"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all project stages with optional pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of project stages
        """
        params = {}

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-stages",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list project stages: {str(e)}")


@float.action("get_project_stage")
class GetProjectStageHandler(ActionHandler):
    """Handler for retrieving a specific project stage by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific project stage.

        Args:
            inputs: Dictionary containing 'project_stage_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing project stage details
        """
        project_stage_id = inputs["project_stage_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-stages/{project_stage_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get project stage {project_stage_id}: {str(e)}")


# ---- Project Expenses Resource Actions ----

@float.action("list_project_expenses")
class ListProjectExpensesHandler(ActionHandler):
    """Handler for listing all project expenses"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all project expenses with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of project expenses
        """
        params = {}

        if "project_id" in inputs and inputs["project_id"]:
            params["project_id"] = inputs["project_id"]

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-expenses",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list project expenses: {str(e)}")


@float.action("get_project_expense")
class GetProjectExpenseHandler(ActionHandler):
    """Handler for retrieving a specific project expense by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific project expense.

        Args:
            inputs: Dictionary containing 'project_expense_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing project expense details
        """
        project_expense_id = inputs["project_expense_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-expenses/{project_expense_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get project expense {project_expense_id}: {str(e)}")


# ---- Phases Resource Actions ----

@float.action("list_phases")
class ListPhasesHandler(ActionHandler):
    """Handler for listing all phases"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all phases with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of phases
        """
        params = {}

        if "project_id" in inputs and inputs["project_id"]:
            params["project_id"] = inputs["project_id"]

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/phases",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list phases: {str(e)}")


@float.action("get_phase")
class GetPhaseHandler(ActionHandler):
    """Handler for retrieving a specific phase by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific phase.

        Args:
            inputs: Dictionary containing 'phase_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing phase details
        """
        phase_id = inputs["phase_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/phases/{phase_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get phase {phase_id}: {str(e)}")


# ---- Project Tasks Resource Actions ----

@float.action("list_project_tasks")
class ListProjectTasksHandler(ActionHandler):
    """Handler for listing all project tasks (default task names)"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all project tasks with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of project tasks
        """
        params = {}

        if "project_id" in inputs and inputs["project_id"]:
            params["project_id"] = inputs["project_id"]

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-tasks",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list project tasks: {str(e)}")


@float.action("get_project_task")
class GetProjectTaskHandler(ActionHandler):
    """Handler for retrieving a specific project task by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific project task.

        Args:
            inputs: Dictionary containing 'project_task_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing project task details
        """
        project_task_id = inputs["project_task_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-tasks/{project_task_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get project task {project_task_id}: {str(e)}")


@float.action("merge_project_tasks")
class MergeProjectTasksHandler(ActionHandler):
    """Handler for merging project tasks"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Merge multiple project tasks into one.

        Args:
            inputs: Dictionary containing 'source_ids' and 'target_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing merged task details
        """
        request_body = {
            "source_ids": inputs["source_ids"],
            "target_id": inputs["target_id"]
        }

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/project-tasks/merge",
                method="POST",
                headers=headers,
                json=request_body
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to merge project tasks: {str(e)}")


# ---- Milestones Resource Actions ----

@float.action("list_milestones")
class ListMilestonesHandler(ActionHandler):
    """Handler for listing all milestones"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        List all milestones with optional filtering and pagination.

        Args:
            inputs: Dictionary containing optional filters
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing list of milestones
        """
        params = {}

        if "project_id" in inputs and inputs["project_id"]:
            params["project_id"] = inputs["project_id"]

        if "page" in inputs and inputs["page"]:
            params["page"] = inputs["page"]

        if "per_page" in inputs and inputs["per_page"]:
            params["per-page"] = inputs["per_page"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/milestones",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to list milestones: {str(e)}")


@float.action("get_milestone")
class GetMilestoneHandler(ActionHandler):
    """Handler for retrieving a specific milestone by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Get details of a specific milestone.

        Args:
            inputs: Dictionary containing 'milestone_id'
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing milestone details
        """
        milestone_id = inputs["milestone_id"]
        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/milestones/{milestone_id}",
                method="GET",
                headers=headers
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to get milestone {milestone_id}: {str(e)}")


# ---- Reports Resource Actions ----

@float.action("get_people_report")
class GetPeopleReportHandler(ActionHandler):
    """Handler for generating people report"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Generate a people report with optional filtering.

        Args:
            inputs: Dictionary containing optional filters (start_date, end_date, people_id)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing people report data
        """
        params = {}

        if "start_date" in inputs and inputs["start_date"]:
            params["start_date"] = inputs["start_date"]

        if "end_date" in inputs and inputs["end_date"]:
            params["end_date"] = inputs["end_date"]

        if "people_id" in inputs and inputs["people_id"]:
            params["people_id"] = inputs["people_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/reports/people",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to generate people report: {str(e)}")


@float.action("get_projects_report")
class GetProjectsReportHandler(ActionHandler):
    """Handler for generating projects report"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        """
        Generate a projects report with optional filtering.

        Args:
            inputs: Dictionary containing optional filters (start_date, end_date, project_id)
            context: Execution context with auth and network capabilities

        Returns:
            ActionResult containing projects report data
        """
        params = {}

        if "start_date" in inputs and inputs["start_date"]:
            params["start_date"] = inputs["start_date"]

        if "end_date" in inputs and inputs["end_date"]:
            params["end_date"] = inputs["end_date"]

        if "project_id" in inputs and inputs["project_id"]:
            params["project_id"] = inputs["project_id"]

        headers = get_auth_headers(context)

        try:
            response = await context.fetch(
                url=f"{FLOAT_API_BASE_URL}/reports/projects",
                method="GET",
                headers=headers,
                params=params
            )

            return ActionResult(
                data=response,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Failed to generate projects report: {str(e)}")
