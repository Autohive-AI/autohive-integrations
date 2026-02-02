from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
microsoft_planner = Integration.load()

# Base URL for Microsoft Graph API
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"


# ---- Helper Functions ----

# Microsoft Graph uses OAuth 2.0 (platform auth), so context.fetch() handles auth automatically
# No custom headers needed for authentication - access token is injected by the SDK


async def get_etag(context: ExecutionContext, resource_url: str) -> Optional[str]:
    """
    Fetch the current ETag for a resource.
    ETags are required for UPDATE and DELETE operations in Microsoft Planner API.

    Args:
        context: ExecutionContext for making API calls
        resource_url: The URL of the resource to get the ETag for

    Returns:
        The ETag value or None if not found
    """
    try:
        response = await context.fetch(
            resource_url,
            method="GET"
        )
        # ETag is returned in the response with @odata.etag key
        return response.get('@odata.etag')
    except Exception:
        return None


# ---- Action Handlers ----

# ---- Group Handlers ----

@microsoft_planner.action("list_groups")
class ListGroupsAction(ActionHandler):
    """List all Microsoft 365 groups the authenticated user is a member of."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get('limit', 100)

            params = {
                '$top': limit,
                '$filter': "groupTypes/any(c:c eq 'Unified')"  # Only unified groups (Microsoft 365 groups)
            }

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/me/memberOf/microsoft.graph.group",
                method="GET",
                params=params
            )

            groups = response.get('value', [])
            return {"groups": groups, "result": True}

        except Exception as e:
            return {"groups": [], "result": False, "error": str(e)}


# ---- User Handlers ----

@microsoft_planner.action("get_user_by_email")
class GetUserByEmailAction(ActionHandler):
    """Get user information by email address to retrieve their user ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            email = inputs['email']

            # Use the users endpoint with a filter
            params = {
                '$filter': f"mail eq '{email}' or userPrincipalName eq '{email}'"
            }

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/users",
                method="GET",
                params=params
            )

            users = response.get('value', [])

            if users:
                user = users[0]
                return {
                    "user": user,
                    "user_id": user.get('id'),
                    "display_name": user.get('displayName'),
                    "email": user.get('mail') or user.get('userPrincipalName'),
                    "result": True
                }
            else:
                return {
                    "user": {},
                    "result": False,
                    "error": f"User with email '{email}' not found"
                }

        except Exception as e:
            return {"user": {}, "result": False, "error": str(e)}


@microsoft_planner.action("search_users")
class SearchUsersAction(ActionHandler):
    """Search for users by display name or email to find their user IDs."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            search_query = inputs['query']
            limit = inputs.get('limit', 10)

            # Use the users endpoint with search
            params = {
                '$search': f'"displayName:{search_query}" OR "mail:{search_query}"',
                '$top': limit
            }

            # Search requires ConsistencyLevel header
            headers = {
                'ConsistencyLevel': 'eventual'
            }

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/users",
                method="GET",
                params=params,
                headers=headers
            )

            users = response.get('value', [])

            # Format users for easier consumption
            formatted_users = [
                {
                    "user_id": user.get('id'),
                    "display_name": user.get('displayName'),
                    "email": user.get('mail') or user.get('userPrincipalName'),
                    "job_title": user.get('jobTitle')
                }
                for user in users
            ]

            return {"users": formatted_users, "result": True}

        except Exception as e:
            return {"users": [], "result": False, "error": str(e)}


@microsoft_planner.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Get the currently authenticated user's information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/me",
                method="GET"
            )

            return {
                "user": response,
                "user_id": response.get('id'),
                "display_name": response.get('displayName'),
                "email": response.get('mail') or response.get('userPrincipalName'),
                "result": True
            }

        except Exception as e:
            return {"user": {}, "result": False, "error": str(e)}


@microsoft_planner.action("list_user_tasks")
class ListUserTasksAction(ActionHandler):
    """List all tasks assigned to a specific user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs.get('user_id', 'me')  # Default to 'me' for current user

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/users/{user_id}/planner/tasks",
                method="GET"
            )

            tasks = response.get('value', [])
            return {"tasks": tasks, "result": True}

        except Exception as e:
            return {"tasks": [], "result": False, "error": str(e)}


@microsoft_planner.action("list_user_plans")
class ListUserPlansAction(ActionHandler):
    """List all plans shared with a specific user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs.get('user_id', 'me')  # Default to 'me' for current user

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/users/{user_id}/planner/plans",
                method="GET"
            )

            plans = response.get('value', [])
            return {"plans": plans, "result": True}

        except Exception as e:
            return {"plans": [], "result": False, "error": str(e)}


# ---- Plan Handlers ----

@microsoft_planner.action("list_plans")
class ListPlansAction(ActionHandler):
    """List all plans owned by a specific group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            group_id = inputs['group_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/groups/{group_id}/planner/plans",
                method="GET"
            )

            plans = response.get('value', [])
            return {"plans": plans, "result": True}

        except Exception as e:
            return {"plans": [], "result": False, "error": str(e)}


@microsoft_planner.action("get_plan")
class GetPlanAction(ActionHandler):
    """Get details of a specific plan by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}",
                method="GET"
            )

            return {"plan": response, "result": True}

        except Exception as e:
            return {"plan": {}, "result": False, "error": str(e)}


@microsoft_planner.action("create_plan")
class CreatePlanAction(ActionHandler):
    """Create a new plan in a Microsoft 365 group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body with required fields
            body = {
                "title": inputs['title']
            }

            # Add container information (required)
            # Container specifies where the plan lives (typically a Microsoft 365 group)
            if 'container' in inputs and inputs['container']:
                body['container'] = inputs['container']
            else:
                # If not provided, build container from group_id
                group_id = inputs.get('group_id')
                if group_id:
                    body['container'] = {
                        "containerId": group_id,
                        "type": "group"
                    }
                else:
                    return {"plan": {}, "result": False, "error": "Either 'container' or 'group_id' is required"}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans",
                method="POST",
                json=body
            )

            return {"plan": response, "result": True}

        except Exception as e:
            return {"plan": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_plan")
class UpdatePlanAction(ActionHandler):
    """Update a plan's title."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}")

            if not etag:
                return {"plan": {}, "result": False, "error": "Failed to retrieve plan ETag"}

            # Build request body
            body = {"title": inputs['title']}

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"plan": response if response else {}, "result": True}

        except Exception as e:
            return {"plan": {}, "result": False, "error": str(e)}


@microsoft_planner.action("delete_plan")
class DeletePlanAction(ActionHandler):
    """Delete a plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            # Get current ETag (required for deletes)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}")

            if not etag:
                return {"result": False, "error": "Failed to retrieve plan ETag"}

            # Delete requires If-Match header with ETag
            headers = {"If-Match": etag}

            await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}",
                method="DELETE",
                headers=headers
            )

            return {"result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


# ---- Plan Details Handlers ----

@microsoft_planner.action("get_plan_details")
class GetPlanDetailsAction(ActionHandler):
    """Get plan details including category descriptions and sharing information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}/details",
                method="GET"
            )

            return {"plan_details": response, "result": True}

        except Exception as e:
            return {"plan_details": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_plan_details")
class UpdatePlanDetailsAction(ActionHandler):
    """Update plan details including category descriptions and sharing information."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}/details")

            if not etag:
                return {"plan_details": {}, "result": False, "error": "Failed to retrieve plan details ETag"}

            # Build request body with only provided fields
            body = {}

            if 'category_descriptions' in inputs:
                # Category descriptions is an object mapping category names to descriptions
                # Example: {"category1": "Description 1", "category2": "Description 2"}
                body['categoryDescriptions'] = inputs['category_descriptions']
            if 'shared_with' in inputs:
                # SharedWith is an object mapping user IDs to sharing details
                # Example: {"user-id": {"@odata.type": "microsoft.graph.plannerUserIds"}}
                body['sharedWith'] = inputs['shared_with']

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}/details",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"plan_details": response if response else {}, "result": True}

        except Exception as e:
            return {"plan_details": {}, "result": False, "error": str(e)}


# ---- Bucket Handlers ----

@microsoft_planner.action("list_buckets")
class ListBucketsAction(ActionHandler):
    """List all buckets in a specific plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            # Microsoft Graph requires planId filter for listing buckets
            params = {'$filter': f"planId eq '{plan_id}'"}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets",
                method="GET",
                params=params
            )

            buckets = response.get('value', [])
            return {"buckets": buckets, "result": True}

        except Exception as e:
            return {"buckets": [], "result": False, "error": str(e)}


@microsoft_planner.action("get_bucket")
class GetBucketAction(ActionHandler):
    """Get details of a specific bucket by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            bucket_id = inputs['bucket_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}",
                method="GET"
            )

            return {"bucket": response, "result": True}

        except Exception as e:
            return {"bucket": {}, "result": False, "error": str(e)}


@microsoft_planner.action("create_bucket")
class CreateBucketAction(ActionHandler):
    """Create a new bucket in a plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body
            body = {
                "name": inputs['name'],
                "planId": inputs['plan_id'],
                "orderHint": inputs.get('order_hint', ' !')
            }

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets",
                method="POST",
                json=body
            )

            return {"bucket": response, "result": True}

        except Exception as e:
            return {"bucket": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_bucket")
class UpdateBucketAction(ActionHandler):
    """Update a bucket's name."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            bucket_id = inputs['bucket_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}")

            if not etag:
                return {"bucket": {}, "result": False, "error": "Failed to retrieve bucket ETag"}

            # Build request body
            body = {"name": inputs['name']}

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"bucket": response if response else {}, "result": True}

        except Exception as e:
            return {"bucket": {}, "result": False, "error": str(e)}


@microsoft_planner.action("delete_bucket")
class DeleteBucketAction(ActionHandler):
    """Delete a bucket from a plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            bucket_id = inputs['bucket_id']

            # Get current ETag (required for deletes)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}")

            if not etag:
                return {"result": False, "error": "Failed to retrieve bucket ETag"}

            # Delete requires If-Match header with ETag
            headers = {"If-Match": etag}

            await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}",
                method="DELETE",
                headers=headers
            )

            return {"result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


@microsoft_planner.action("list_bucket_tasks")
class ListBucketTasksAction(ActionHandler):
    """List all tasks in a specific bucket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            bucket_id = inputs['bucket_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/buckets/{bucket_id}/tasks",
                method="GET"
            )

            tasks = response.get('value', [])
            return {"tasks": tasks, "result": True}

        except Exception as e:
            return {"tasks": [], "result": False, "error": str(e)}


# ---- Task Handlers ----

@microsoft_planner.action("list_tasks")
class ListTasksAction(ActionHandler):
    """List all tasks in a specific plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            plan_id = inputs['plan_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/plans/{plan_id}/tasks",
                method="GET"
            )

            tasks = response.get('value', [])
            return {"tasks": tasks, "result": True}

        except Exception as e:
            return {"tasks": [], "result": False, "error": str(e)}


@microsoft_planner.action("get_task")
class GetTaskAction(ActionHandler):
    """Get details of a specific task by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}",
                method="GET"
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@microsoft_planner.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a new task in a plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body with required fields
            body = {
                "planId": inputs['plan_id'],
                "bucketId": inputs['bucket_id'],
                "title": inputs['title']
            }

            # Add optional fields
            if 'assignments' in inputs and inputs['assignments']:
                # Assignments should be an object like:
                # {"user-id": {"@odata.type": "#microsoft.graph.plannerAssignment", "orderHint": "optional string"}}
                # Process assignments to ensure proper format with @odata.type
                processed_assignments = {}
                for user_id, assignment in inputs['assignments'].items():
                    if assignment is None:
                        # null means remove the assignment
                        processed_assignments[user_id] = None
                    else:
                        # Ensure @odata.type is present for proper type recognition
                        if isinstance(assignment, dict):
                            processed_assignment = {
                                "@odata.type": "#microsoft.graph.plannerAssignment"
                            }
                            # Copy orderHint if provided
                            if 'orderHint' in assignment and assignment['orderHint']:
                                processed_assignment['orderHint'] = assignment['orderHint']
                        else:
                            # If assignment is not a dict, create a minimal valid assignment
                            processed_assignment = {
                                "@odata.type": "#microsoft.graph.plannerAssignment"
                            }
                        processed_assignments[user_id] = processed_assignment
                body['assignments'] = processed_assignments
            if 'due_date_time' in inputs and inputs['due_date_time']:
                body['dueDateTime'] = inputs['due_date_time']
            if 'start_date_time' in inputs and inputs['start_date_time']:
                body['startDateTime'] = inputs['start_date_time']
            if 'percent_complete' in inputs and inputs['percent_complete'] is not None:
                body['percentComplete'] = inputs['percent_complete']
            if 'priority' in inputs and inputs['priority'] is not None:
                body['priority'] = inputs['priority']
            if 'applied_categories' in inputs:
                # Applied categories is an object mapping category names to boolean values
                # Example: {"category1": true, "category2": false}
                body['appliedCategories'] = inputs['applied_categories']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks",
                method="POST",
                json=body
            )

            return {"task": response, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update an existing task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}")

            if not etag:
                return {"task": {}, "result": False, "error": "Failed to retrieve task ETag"}

            # Build request body with only provided fields
            body = {}

            if 'title' in inputs and inputs['title']:
                body['title'] = inputs['title']
            if 'bucket_id' in inputs and inputs['bucket_id']:
                body['bucketId'] = inputs['bucket_id']
            if 'assignments' in inputs and inputs['assignments']:
                # Process assignments to ensure proper format with @odata.type
                processed_assignments = {}
                for user_id, assignment in inputs['assignments'].items():
                    if assignment is None:
                        # null means remove the assignment
                        processed_assignments[user_id] = None
                    else:
                        # Ensure @odata.type is present for proper type recognition
                        if isinstance(assignment, dict):
                            processed_assignment = {
                                "@odata.type": "#microsoft.graph.plannerAssignment"
                            }
                            # Copy orderHint if provided
                            if 'orderHint' in assignment and assignment['orderHint']:
                                processed_assignment['orderHint'] = assignment['orderHint']
                        else:
                            # If assignment is not a dict, create a minimal valid assignment
                            processed_assignment = {
                                "@odata.type": "#microsoft.graph.plannerAssignment"
                            }
                        processed_assignments[user_id] = processed_assignment

                # Only add assignments to body if we have any to process
                if processed_assignments:
                    body['assignments'] = processed_assignments
            if 'due_date_time' in inputs:
                body['dueDateTime'] = inputs['due_date_time']
            if 'start_date_time' in inputs:
                body['startDateTime'] = inputs['start_date_time']
            if 'percent_complete' in inputs and inputs['percent_complete'] is not None:
                body['percentComplete'] = inputs['percent_complete']
            if 'priority' in inputs and inputs['priority'] is not None:
                body['priority'] = inputs['priority']
            if 'applied_categories' in inputs:
                # Applied categories is an object mapping category names to boolean values
                # Example: {"category1": true, "category2": false}
                body['appliedCategories'] = inputs['applied_categories']
            if 'assignee_priority' in inputs:
                body['assigneePriority'] = inputs['assignee_priority']
            if 'conversation_thread_id' in inputs:
                body['conversationThreadId'] = inputs['conversation_thread_id']
            if 'order_hint' in inputs:
                body['orderHint'] = inputs['order_hint']

            # Check if body is empty (no fields to update)
            if not body:
                return {"task": {}, "result": False, "error": "No fields provided to update. Please specify at least one field to modify."}

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}",
                method="PATCH",
                headers=headers,
                json=body
            )

            # Ensure we always return an object for task, even if response is None
            return {"task": response if response else {}, "result": True}

        except Exception as e:
            return {"task": {}, "result": False, "error": str(e)}


@microsoft_planner.action("delete_task")
class DeleteTaskAction(ActionHandler):
    """Delete a task from a plan."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for deletes)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}")

            if not etag:
                return {"result": False, "error": "Failed to retrieve task ETag"}

            # Delete requires If-Match header with ETag
            headers = {"If-Match": etag}

            await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}",
                method="DELETE",
                headers=headers
            )

            return {"result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


# ---- Task Details Handlers ----

@microsoft_planner.action("get_task_details")
class GetTaskDetailsAction(ActionHandler):
    """Get details of a task including description, checklist, and references."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="GET"
            )

            return {"task_details": response, "result": True}

        except Exception as e:
            return {"task_details": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_task_details")
class UpdateTaskDetailsAction(ActionHandler):
    """Update task details including description, checklist, references, and preview type."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details")

            if not etag:
                return {"task_details": {}, "result": False, "error": "Failed to retrieve task details ETag"}

            # Build request body with only provided fields
            body = {}

            if 'description' in inputs:
                body['description'] = inputs['description']
            if 'preview_type' in inputs:
                body['previewType'] = inputs['preview_type']
            if 'checklist' in inputs:
                # Checklist is an object mapping item IDs to checklist item objects
                # Example: {"item-id": {"@odata.type": "microsoft.graph.plannerChecklistItem", "title": "Item title", "isChecked": false}}
                body['checklist'] = inputs['checklist']
            if 'references' in inputs:
                # References is an object mapping reference keys to reference objects
                # Example: {"https://example.com": {"@odata.type": "microsoft.graph.plannerExternalReference", "alias": "Example"}}
                body['references'] = inputs['references']

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"task_details": response if response else {}, "result": True}

        except Exception as e:
            return {"task_details": {}, "result": False, "error": str(e)}


@microsoft_planner.action("add_checklist_item")
class AddChecklistItemAction(ActionHandler):
    """Add a new item to a task's checklist."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']
            title = inputs['title']
            is_checked = inputs.get('is_checked', False)
            order_hint = inputs.get('order_hint', ' !')

            # Get current task details to retrieve existing checklist
            current_details = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="GET"
            )

            # Get current ETag (required for updates)
            etag = current_details.get('@odata.etag')
            if not etag:
                return {"result": False, "error": "Failed to retrieve task details ETag"}

            # Get existing checklist or initialize empty dict
            existing_checklist = current_details.get('checklist', {})

            # Clean existing checklist items by removing read-only fields
            # Don't include orderHint for existing items since we're not reordering them
            checklist = {}
            for item_id_key, item in existing_checklist.items():
                if item:
                    checklist[item_id_key] = {
                        "@odata.type": "#microsoft.graph.plannerChecklistItem",
                        "title": item.get('title', ''),
                        "isChecked": item.get('isChecked', False)
                    }

            # Generate a unique item ID using timestamp
            import uuid
            item_id = str(uuid.uuid4())

            # Add new checklist item (include orderHint only for the new item)
            checklist[item_id] = {
                "@odata.type": "#microsoft.graph.plannerChecklistItem",
                "title": title,
                "isChecked": is_checked,
                "orderHint": order_hint
            }

            # Update task details with new checklist
            headers = {"If-Match": etag}
            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="PATCH",
                headers=headers,
                json={"checklist": checklist}
            )

            return {"task_details": response if response else {}, "item_id": item_id, "result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


@microsoft_planner.action("update_checklist_item")
class UpdateChecklistItemAction(ActionHandler):
    """Update an existing checklist item."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']
            item_id = inputs['item_id']

            # Get current task details
            current_details = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="GET"
            )

            # Get current ETag (required for updates)
            etag = current_details.get('@odata.etag')
            if not etag:
                return {"result": False, "error": "Failed to retrieve task details ETag"}

            # Get existing checklist
            existing_checklist = current_details.get('checklist', {})

            if item_id not in existing_checklist:
                return {"result": False, "error": f"Checklist item '{item_id}' not found"}

            # Clean existing checklist items by removing read-only fields
            # Don't include orderHint unless explicitly updating it
            checklist = {}
            for item_id_key, item in existing_checklist.items():
                if item:
                    checklist[item_id_key] = {
                        "@odata.type": "#microsoft.graph.plannerChecklistItem",
                        "title": item.get('title', ''),
                        "isChecked": item.get('isChecked', False)
                    }

            # Update the specific checklist item with provided fields
            if 'title' in inputs:
                checklist[item_id]['title'] = inputs['title']
            if 'is_checked' in inputs:
                checklist[item_id]['isChecked'] = inputs['is_checked']
            if 'order_hint' in inputs:
                checklist[item_id]['orderHint'] = inputs['order_hint']

            # Update task details with modified checklist
            headers = {"If-Match": etag}
            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="PATCH",
                headers=headers,
                json={"checklist": checklist}
            )

            return {"task_details": response if response else {}, "result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


@microsoft_planner.action("remove_checklist_item")
class RemoveChecklistItemAction(ActionHandler):
    """Remove an item from a task's checklist."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']
            item_id = inputs['item_id']

            # Get current task details
            current_details = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="GET"
            )

            # Get current ETag (required for updates)
            etag = current_details.get('@odata.etag')
            if not etag:
                return {"result": False, "error": "Failed to retrieve task details ETag"}

            # Get existing checklist
            existing_checklist = current_details.get('checklist', {})

            if item_id not in existing_checklist:
                return {"result": False, "error": f"Checklist item '{item_id}' not found"}

            # Clean existing checklist items by removing read-only fields
            # Don't include orderHint for items we're not reordering
            checklist = {}
            for item_id_key, item in existing_checklist.items():
                if item:
                    checklist[item_id_key] = {
                        "@odata.type": "#microsoft.graph.plannerChecklistItem",
                        "title": item.get('title', ''),
                        "isChecked": item.get('isChecked', False)
                    }

            # To remove an item, set it to null
            checklist[item_id] = None

            # Update task details with modified checklist
            headers = {"If-Match": etag}
            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/details",
                method="PATCH",
                headers=headers,
                json={"checklist": checklist}
            )

            return {"task_details": response if response else {}, "result": True}

        except Exception as e:
            return {"result": False, "error": str(e)}


# ---- Task Board Format Handlers ----

@microsoft_planner.action("get_task_assigned_to_board_format")
class GetTaskAssignedToBoardFormatAction(ActionHandler):
    """Get the assigned-to task board format for a task (ordering by assignee)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/assignedToTaskBoardFormat",
                method="GET"
            )

            return {"board_format": response, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_task_assigned_to_board_format")
class UpdateTaskAssignedToBoardFormatAction(ActionHandler):
    """Update the assigned-to task board format for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/assignedToTaskBoardFormat")

            if not etag:
                return {"board_format": {}, "result": False, "error": "Failed to retrieve board format ETag"}

            # Build request body
            body = {}

            if 'unassigned_order_hint' in inputs:
                body['unassignedOrderHint'] = inputs['unassigned_order_hint']
            if 'order_hints_by_assignee' in inputs:
                # Object mapping user IDs to order hint strings
                # Example: {"user-id": "order-hint-value"}
                body['orderHintsByAssignee'] = inputs['order_hints_by_assignee']

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/assignedToTaskBoardFormat",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"board_format": response if response else {}, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}


@microsoft_planner.action("get_task_bucket_board_format")
class GetTaskBucketBoardFormatAction(ActionHandler):
    """Get the bucket task board format for a task (ordering within buckets)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/bucketTaskBoardFormat",
                method="GET"
            )

            return {"board_format": response, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_task_bucket_board_format")
class UpdateTaskBucketBoardFormatAction(ActionHandler):
    """Update the bucket task board format for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/bucketTaskBoardFormat")

            if not etag:
                return {"board_format": {}, "result": False, "error": "Failed to retrieve board format ETag"}

            # Build request body
            body = {}

            if 'order_hint' in inputs:
                body['orderHint'] = inputs['order_hint']

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/bucketTaskBoardFormat",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"board_format": response if response else {}, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}


@microsoft_planner.action("get_task_progress_board_format")
class GetTaskProgressBoardFormatAction(ActionHandler):
    """Get the progress task board format for a task (ordering by progress state)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/progressTaskBoardFormat",
                method="GET"
            )

            return {"board_format": response, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}


@microsoft_planner.action("update_task_progress_board_format")
class UpdateTaskProgressBoardFormatAction(ActionHandler):
    """Update the progress task board format for a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs['task_id']

            # Get current ETag (required for updates)
            etag = await get_etag(context, f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/progressTaskBoardFormat")

            if not etag:
                return {"board_format": {}, "result": False, "error": "Failed to retrieve board format ETag"}

            # Build request body
            body = {}

            if 'order_hint' in inputs:
                body['orderHint'] = inputs['order_hint']

            # Update requires If-Match header with ETag
            headers = {"If-Match": etag}

            response = await context.fetch(
                f"{GRAPH_API_BASE_URL}/planner/tasks/{task_id}/progressTaskBoardFormat",
                method="PATCH",
                headers=headers,
                json=body
            )

            return {"board_format": response if response else {}, "result": True}

        except Exception as e:
            return {"board_format": {}, "result": False, "error": str(e)}
