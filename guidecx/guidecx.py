from typing import Any, Dict, List, Optional, Tuple

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)

guidecx = Integration.load()

# GUIDEcx Open API. v2 is still served but is superseded by v3, and the legacy
# workspace tokens that v2 accepts are deprecated in favour of user-based tokens.
API_BASE_URL = "https://api.guidecx.com/api/v3"

# Search endpoints paginate with limit/offset and report the unfiltered match
# count in metadata.total. The API's own default page size is undocumented, so a
# page size is always sent explicitly for predictable results.
#
# MAX_LIMIT is the server-side cap, verified against the live API: a larger value
# is accepted but silently clamped (limit=1000 comes back as metadata.limit=500),
# so requesting more would quietly return fewer records than asked for.
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def get_api_token(context: ExecutionContext) -> str:
    """Read the GUIDEcx bearer token from the execution context."""
    credentials = context.auth.get("credentials") or {}
    token = credentials.get("api_token") or context.auth.get("api_token")
    if not token:
        raise ValueError("GUIDEcx API token is required in auth (field 'api_token').")
    return token


def get_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for GUIDEcx Open API requests."""
    return {
        "Authorization": f"Bearer {get_api_token(context)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def clamp_limit(value: Any) -> int:
    """Coerce a caller-supplied page size into the range the API accepts."""
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def prune(params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop query parameters the caller did not set.

    A value that is None, an empty string, or an empty list means "no filter",
    and sending it would either be rejected or silently narrow the results.
    Zero is kept, since ``offset=0`` is meaningful.

    Non-empty list values are passed through unchanged: the repeatable filters
    (``id``, ``status``, ``statusCategory``, ``customerId``, ``tag``, ...) are
    declared as arrays in the spec and are sent as repeated query parameters.

    Use :func:`prune_body` for request bodies, where an empty list is a
    meaningful instruction rather than an absent filter.
    """
    return {key: value for key, value in params.items() if value is not None and value != "" and value != []}


def prune_body(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Drop unset fields from a request body, keeping empty collections.

    This differs from :func:`prune` in one important way: an empty list is
    preserved. In a query string ``tag=[]`` means "do not filter by tag", but in
    an upsert body ``"tags": []`` is how a caller clears a project's tags, and
    the API honours it (verified against a live workspace: sending an empty
    ``tags`` array removes the existing tags, while omitting the key leaves them
    untouched). Pruning it would make clearing tags impossible.

    Only None and the empty string are treated as "not supplied", since neither
    is a value the API accepts as a deliberate reset here.
    """
    return {key: value for key, value in fields.items() if value is not None and value != ""}


async def gcx_fetch(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    """Call the GUIDEcx Open API and return the parsed response body.

    Non-2xx responses raise (``context.fetch`` raises ``HTTPError``); callers
    convert exceptions into ``ActionError``.
    """
    url = f"{API_BASE_URL}{endpoint}"
    headers = get_headers(context)

    if method == "GET":
        response = await context.fetch(url, headers=headers, params=params)
    else:
        response = await context.fetch(url, method=method, headers=headers, params=params, json=json_body)

    return getattr(response, "data", response)


def paged_result(body: Any, key: str, limit: int, offset: int) -> Dict[str, Any]:
    """Shape a search response into a list plus pagination fields.

    ``metadata.total`` counts every record matching the filters, not just the
    current page, so ``has_more`` is derived from it rather than from page size.
    """
    body = body or {}
    items = body.get("data") or []
    metadata = body.get("metadata") or {}
    total = metadata.get("total")
    returned_offset = metadata.get("offset", offset)
    returned_limit = metadata.get("limit", limit)

    if isinstance(total, int):
        has_more = returned_offset + len(items) < total
    else:
        # metadata.total is documented but treat its absence as "unknown" and
        # fall back to a full page meaning there is probably another one.
        has_more = len(items) >= returned_limit

    return {
        key: items,
        "total": total,
        "limit": returned_limit,
        "offset": returned_offset,
        "has_more": has_more,
    }


@guidecx.action("list_projects")
class ListProjectsAction(ActionHandler):
    """Search onboarding projects with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = clamp_limit(inputs.get("limit", DEFAULT_LIMIT))
            offset = int(inputs.get("offset") or 0)

            params = prune(
                {
                    "status": inputs.get("status"),
                    "statusCategory": inputs.get("status_category"),
                    "customerId": inputs.get("customer_id"),
                    "projectManagerId": inputs.get("project_manager_id"),
                    "tag": inputs.get("tag"),
                    "updatedAfter": inputs.get("updated_after"),
                    "updatedBefore": inputs.get("updated_before"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/projects", params=params)
            return ActionResult(data=paged_result(body, "projects", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("get_project")
class GetProjectAction(ActionHandler):
    """Retrieve a single project by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            # There is no GET /projects/{id} in the v3 API. The search endpoint
            # accepts a repeatable `id` filter, so a single-id search is the
            # supported way to fetch one project.
            body = await gcx_fetch(context, "GET", "/projects", params={"id": [project_id], "limit": 1})

            projects = (body or {}).get("data") or []
            if not projects:
                return ActionError(message=f"No GUIDEcx project found with id '{project_id}'.")

            return ActionResult(data={"project": projects[0]}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_milestones")
class ListMilestonesAction(ActionHandler):
    """List the milestones of a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = clamp_limit(inputs.get("limit", DEFAULT_LIMIT))
            offset = int(inputs.get("offset") or 0)

            params = prune(
                {
                    "projectId": inputs["project_id"],
                    "phaseId": inputs.get("phase_id"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/milestones", params=params)
            return ActionResult(data=paged_result(body, "milestones", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_tasks")
class ListTasksAction(ActionHandler):
    """Search tasks with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = clamp_limit(inputs.get("limit", DEFAULT_LIMIT))
            offset = int(inputs.get("offset") or 0)

            params = prune(
                {
                    "projectId": inputs.get("project_id"),
                    "milestoneId": inputs.get("milestone_id"),
                    "assigneeId": inputs.get("assignee_id"),
                    "statusCategory": inputs.get("status_category"),
                    "name": inputs.get("name"),
                    "typeFilter": inputs.get("type_filter"),
                    "updatedAfter": inputs.get("updated_after"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/tasks", params=params)
            return ActionResult(data=paged_result(body, "tasks", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("update_task")
class UpdateTaskAction(ActionHandler):
    """Update a task's status, due date, assignee or priority."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            task_id = inputs["task_id"]

            # Fields left out of the entry are not modified, so only the ones
            # the caller actually set are sent.
            task: Dict[str, Any] = prune_body(
                {
                    "status": inputs.get("status"),
                    "endDate": inputs.get("end_date"),
                    "assigneeId": inputs.get("assignee_id"),
                    "priority": inputs.get("priority"),
                }
            )
            if not task:
                return ActionError(
                    message=(
                        "No update fields provided. Set at least one of status, end_date, assignee_id or priority."
                    )
                )
            task["id"] = task_id

            # The API exposes only a project-scoped batch upsert for tasks.
            # Sending an entry with an existing `id` updates that task; fields
            # left out of the entry are not modified.
            body = await gcx_fetch(
                context,
                "PATCH",
                f"/projects/{project_id}/tasks",
                json_body={"tasks": [task]},
            )

            updated: List[Dict[str, Any]] = (body or {}).get("data") or []
            if not updated:
                return ActionError(
                    message=f"GUIDEcx accepted the update for task '{task_id}' but returned no task record."
                )

            return ActionResult(data={"task": updated[0]}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("add_task_note")
class AddTaskNoteAction(ActionHandler):
    """Post a note to a task's message channel."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]
            content = inputs["content"]
            internal_only = bool(inputs.get("internal_only", False))

            # The endpoint is a bulk create; a single note is sent as a one-item
            # list. The message is attributed to the owner of the API token.
            body = await gcx_fetch(
                context,
                "POST",
                f"/tasks/{task_id}/messages",
                json_body={"messages": [{"formattedContent": content, "internalOnly": internal_only}]},
            )

            return ActionResult(data={"messages": (body or {}).get("data") or []}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("get_customer")
class GetCustomerAction(ActionHandler):
    """Retrieve a customer by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            customer_id = inputs["customer_id"]

            body = await gcx_fetch(context, "GET", f"/customers/{customer_id}")

            customer = (body or {}).get("data")
            if not customer:
                return ActionError(message=f"No GUIDEcx customer found with id '{customer_id}'.")

            return ActionResult(data={"customer": customer}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


def page_args(inputs: Dict[str, Any]) -> Tuple[int, int]:
    """Read the caller's page size and offset, clamped to what the API accepts."""
    return clamp_limit(inputs.get("limit", DEFAULT_LIMIT)), int(inputs.get("offset") or 0)


def first_record(body: Any) -> Optional[Dict[str, Any]]:
    """Return the single record from a bulk-write response, if there is one.

    The write endpoints are all batch operations returning a ``data`` list.
    Every action here sends exactly one item, so the result is its first entry.
    """
    records = (body or {}).get("data") or []
    return records[0] if records else None


@guidecx.action("list_phases")
class ListPhasesAction(ActionHandler):
    """List the phases of a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)
            params = prune({"projectId": inputs["project_id"], "limit": limit, "offset": offset})

            body = await gcx_fetch(context, "GET", "/phases", params=params)
            return ActionResult(data=paged_result(body, "phases", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_project_members")
class ListProjectMembersAction(ActionHandler):
    """List the members assigned to a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            limit, offset = page_args(inputs)
            params = prune(
                {
                    "email": inputs.get("email"),
                    "projectRole": inputs.get("project_role"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", f"/projects/{project_id}/members", params=params)
            return ActionResult(data=paged_result(body, "members", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("remove_project_member")
class RemoveProjectMemberAction(ActionHandler):
    """Unassign a member from a project's team."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            member_id = inputs["member_id"]

            # A successful delete returns an empty JSON object, so there is
            # nothing to unwrap: reaching this point without raising is success.
            await gcx_fetch(context, "DELETE", f"/projects/{project_id}/members/{member_id}")

            return ActionResult(data={"removed": True, "member_id": member_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_members")
class ListMembersAction(ActionHandler):
    """Search the workspace's members."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)
            params = prune(
                {
                    "email": inputs.get("email"),
                    "role": inputs.get("role"),
                    "status": inputs.get("status"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/members", params=params)
            return ActionResult(data=paged_result(body, "members", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_roles")
class ListRolesAction(ActionHandler):
    """List the roles configured in the workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)
            params = prune({"name": inputs.get("name"), "limit": limit, "offset": offset})

            body = await gcx_fetch(context, "GET", "/roles", params=params)
            return ActionResult(data=paged_result(body, "roles", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_webhooks")
class ListWebhooksAction(ActionHandler):
    """List the workspace's webhook subscriptions."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)
            include_disabled = inputs.get("include_disabled")
            # This endpoint is the one place the API uses snake_case for both
            # query parameters and response fields instead of camelCase.
            #
            # The SDK's fetch rejects bool query values ("value should be str,
            # int or float"), so the flag is sent as a lowercase string, which
            # is what the API expects on the wire anyway.
            params = prune(
                {
                    "include_disabled": None if include_disabled is None else str(bool(include_disabled)).lower(),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/webhooks", params=params)
            return ActionResult(data=paged_result(body, "webhooks", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("upsert_webhook")
class UpsertWebhookAction(ActionHandler):
    """Create or update a webhook subscription."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            webhook = prune_body(
                {
                    "id": inputs.get("webhook_id"),
                    "eventType": inputs["event_type"],
                    "url": inputs["url"],
                    "description": inputs.get("description"),
                }
            )

            # The request field is camelCase (`eventType`) while the response
            # field is snake_case (`event_type`), and GUIDEcx returns event_type
            # as null here even when the upsert succeeded.
            body = await gcx_fetch(context, "PATCH", "/webhooks", json_body={"webhooks": [webhook]})

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the webhook upsert but returned no webhook record.")

            return ActionResult(data={"webhook": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("delete_webhook")
class DeleteWebhookAction(ActionHandler):
    """Delete a webhook subscription."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            webhook_id = inputs["webhook_id"]

            await gcx_fetch(context, "DELETE", f"/webhooks/{webhook_id}")

            return ActionResult(data={"deleted": True, "webhook_id": webhook_id}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_time_categories")
class ListTimeCategoriesAction(ActionHandler):
    """List the workspace's time categories."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)

            body = await gcx_fetch(context, "GET", "/time-categories", params={"limit": limit, "offset": offset})
            return ActionResult(data=paged_result(body, "time_categories", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_time_records")
class ListTimeRecordsAction(ActionHandler):
    """Search logged time."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit, offset = page_args(inputs)
            params = prune(
                {
                    "projectId": inputs.get("project_id"),
                    "taskId": inputs.get("task_id"),
                    "memberId": inputs.get("member_id"),
                    "timeCategoryId": inputs.get("time_category_id"),
                    "workedAfter": inputs.get("worked_after"),
                    "workedBefore": inputs.get("worked_before"),
                    "limit": limit,
                    "offset": offset,
                }
            )

            body = await gcx_fetch(context, "GET", "/time-records", params=params)
            return ActionResult(data=paged_result(body, "time_records", limit, offset), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


def time_record_body(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build the one-item bulk body shared by the two time-logging actions."""
    record = prune_body(
        {
            "memberId": inputs["member_id"],
            "dateOfWork": inputs["date_of_work"],
            "hoursWorked": inputs["hours_worked"],
            "comment": inputs.get("comment"),
            "timeCategoryId": inputs.get("time_category_id"),
        }
    )
    return {"timeRecords": [record]}


@guidecx.action("log_task_time")
class LogTaskTimeAction(ActionHandler):
    """Log hours worked against a task."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            task_id = inputs["task_id"]

            body = await gcx_fetch(
                context,
                "POST",
                f"/tasks/{task_id}/time-records",
                json_body=time_record_body(inputs),
            )

            created = first_record(body)
            if created is None:
                return ActionError(
                    message=f"GUIDEcx accepted the time entry for task '{task_id}' but returned no record."
                )

            return ActionResult(data={"time_record": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("log_project_time")
class LogProjectTimeAction(ActionHandler):
    """Log hours worked against a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            body = await gcx_fetch(
                context,
                "POST",
                f"/projects/{project_id}/time-records",
                json_body=time_record_body(inputs),
            )

            created = first_record(body)
            if created is None:
                return ActionError(
                    message=f"GUIDEcx accepted the time entry for project '{project_id}' but returned no record."
                )

            return ActionResult(data={"time_record": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# The batch-upsert endpoints accept a `placement` object saying where the new
# item lands in its parent's ordering. Only the two ends are exposed; positional
# insertion needs sortOrder values the caller would have to fetch first.
PLACEMENTS = {"at_start": {"atStart": True}, "at_end": {"atEnd": True}}


def placement_body(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Translate the `placement` input into the API's placement object."""
    return PLACEMENTS.get(inputs.get("placement") or "at_end", {"atEnd": True})


@guidecx.action("create_project")
class CreateProjectAction(ActionHandler):
    """Create an onboarding project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project = prune_body(
                {
                    "name": inputs["name"],
                    "templateId": inputs.get("template_id"),
                    "startDate": inputs.get("start_date"),
                    "endDate": inputs.get("end_date"),
                    "status": inputs.get("status"),
                    "tags": inputs.get("tags"),
                    "cashValue": inputs.get("cash_value"),
                }
            )

            # A customer is either referenced by ID or created inline from a
            # name and domain. There is no dedicated create-customer endpoint,
            # so the inline form is the only way to make one via the API.
            customer_id = inputs.get("customer_id")
            if customer_id:
                project["customer"] = {"id": customer_id}
            elif inputs.get("customer_name"):
                project["customer"] = prune({"name": inputs["customer_name"], "domain": inputs.get("customer_domain")})

            if inputs.get("project_manager_id"):
                project["internalTeam"] = [{"id": inputs["project_manager_id"], "role": "PROJECT_MANAGER"}]

            body = await gcx_fetch(context, "PATCH", "/projects", json_body={"projects": [project]})

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the project but returned no project record.")

            # Projects carry no customerId field; the customer link is the only
            # place the ID appears, as the last segment of the path.
            link = (created.get("_links") or {}).get("customer")
            resolved_customer = str(link).rstrip("/").rsplit("/", 1)[-1] if link else None

            return ActionResult(
                data={"project": created, "customer_id": resolved_customer},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("update_project")
class UpdateProjectAction(ActionHandler):
    """Update an existing project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            project = prune_body(
                {
                    "name": inputs.get("name"),
                    "startDate": inputs.get("start_date"),
                    "endDate": inputs.get("end_date"),
                    "status": inputs.get("status"),
                    "statusExplanation": inputs.get("status_explanation"),
                    "tags": inputs.get("tags"),
                    "cashValue": inputs.get("cash_value"),
                }
            )
            if not project:
                return ActionError(
                    message=(
                        "No update fields provided. Set at least one of name, start_date, end_date, "
                        "status, status_explanation, tags or cash_value."
                    )
                )
            project["id"] = project_id

            body = await gcx_fetch(context, "PATCH", "/projects", json_body={"projects": [project]})

            updated = first_record(body)
            if updated is None:
                return ActionError(
                    message=f"GUIDEcx accepted the update for project '{project_id}' but returned no record."
                )

            return ActionResult(data={"project": updated}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("create_phase")
class CreatePhaseAction(ActionHandler):
    """Create a phase in a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            phase = prune_body(
                {
                    "name": inputs["name"],
                    "templateId": inputs.get("template_id"),
                    "formattedDescription": inputs.get("description"),
                }
            )

            body = await gcx_fetch(
                context,
                "PATCH",
                f"/projects/{project_id}/phases",
                json_body={"phases": [phase], "placement": placement_body(inputs)},
            )

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the phase but returned no phase record.")

            return ActionResult(data={"phase": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("create_milestone")
class CreateMilestoneAction(ActionHandler):
    """Create a milestone inside a phase."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            milestone = prune_body(
                {
                    "name": inputs["name"],
                    "phaseId": inputs["phase_id"],
                    "templateId": inputs.get("template_id"),
                    "formattedDescription": inputs.get("description"),
                }
            )

            body = await gcx_fetch(
                context,
                "PATCH",
                f"/projects/{project_id}/milestones",
                json_body={"milestones": [milestone], "placement": placement_body(inputs)},
            )

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the milestone but returned no milestone record.")

            return ActionResult(data={"milestone": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("create_task")
class CreateTaskAction(ActionHandler):
    """Create a task under a milestone."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]

            # `parentId` must be a milestone: a task cannot hang directly off a
            # project, and omitting it fails with
            # 'task [0] has an invalid parentId: ""'.
            task = prune_body(
                {
                    "name": inputs["name"],
                    "parentId": inputs["milestone_id"],
                    "formattedDescription": inputs.get("description"),
                    "startDate": inputs.get("start_date"),
                    "endDate": inputs.get("end_date"),
                    "assigneeId": inputs.get("assignee_id"),
                    "priority": inputs.get("priority"),
                    "responsibility": inputs.get("responsibility"),
                    "visibility": inputs.get("visibility"),
                    "estimatedHours": inputs.get("estimated_hours"),
                    "tags": inputs.get("tags"),
                }
            )

            body = await gcx_fetch(
                context,
                "PATCH",
                f"/projects/{project_id}/tasks",
                json_body={"tasks": [task], "placement": placement_body(inputs)},
            )

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the task but returned no task record.")

            return ActionResult(data={"task": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("list_dependencies")
class ListDependenciesAction(ActionHandler):
    """List task dependencies."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = prune(
                {
                    "projectId": inputs.get("project_id"),
                    "parentId": inputs.get("parent_id"),
                    "dependentId": inputs.get("dependent_id"),
                }
            )

            # Unlike every other search endpoint, /dependencies takes no
            # limit/offset and returns no metadata block, so there is nothing to
            # paginate and no total to report.
            body = await gcx_fetch(context, "GET", "/dependencies", params=params)

            dependencies = (body or {}).get("data") or []
            return ActionResult(
                data={"dependencies": dependencies, "count": len(dependencies)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("add_dependency")
class AddDependencyAction(ActionHandler):
    """Make one task depend on another."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dependency = {"parentId": inputs["parent_id"], "dependentId": inputs["dependent_id"]}

            body = await gcx_fetch(context, "POST", "/dependencies", json_body={"dependencies": [dependency]})

            created = first_record(body)
            if created is None:
                return ActionError(message="GUIDEcx accepted the dependency but returned no dependency record.")

            return ActionResult(data={"dependency": created}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@guidecx.action("remove_dependency")
class RemoveDependencyAction(ActionHandler):
    """Remove a dependency between two tasks."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            parent_id = inputs["parent_id"]
            dependent_id = inputs["dependent_id"]

            # The delete identifies the dependency by both ends as query
            # parameters rather than by a dependency ID in the path.
            await gcx_fetch(
                context,
                "DELETE",
                "/dependencies",
                params={"parentId": parent_id, "dependentId": dependent_id},
            )

            return ActionResult(
                data={"removed": True, "parent_id": parent_id, "dependent_id": dependent_id},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))
