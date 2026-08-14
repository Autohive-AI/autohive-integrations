"""
15Five — performance management integration for the 15Five Public API.

Actions:
- list_users, get_user
- list_groups, get_group, list_group_types, get_group_type
- list_departments, get_department
- get_feature_status
- list_attributes, get_attribute, create_attribute
- list_attribute_values, get_attribute_value, create_attribute_value
- list_objectives, get_objective, create_objectives, list_objective_history,
  get_objective_history, list_key_results
- list_high_fives, get_high_five, create_high_five
- list_reports, get_report
- list_answers, get_answer
- list_questions, get_question
- list_priorities, create_priorities
- list_pulses, get_pulse
- list_review_cycles, get_review_cycle, list_review_cycle_participants,
  list_review_cycle_results_answers, list_review_cycle_results_performance_measurements,
  list_reviews
- list_one_on_ones, get_one_on_one
- list_vacations
- list_security_audit
"""

from typing import Any, Dict

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
)

fifteenfive = Integration.load()


# ---- Helper Functions ----


def get_base_url(context: ExecutionContext) -> str:
    """Return the 15Five API base URL for the configured company subdomain."""
    subdomain = context.auth["credentials"].get("subdomain", "")
    return f"https://{subdomain}.15five.com/api/public"


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build authentication headers for 15Five Public API requests (Bearer token)."""
    api_key = context.auth["credentials"].get("api_key", "")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def extract_error_message(error: HTTPError) -> str:
    """Extract a human-readable error message from a 15Five error response."""
    data = error.response_data
    if isinstance(data, dict):
        if data.get("detail"):
            return str(data["detail"])
        if data.get("message"):
            return str(data["message"])
        field_errors = [
            f"{field}: {', '.join(msgs) if isinstance(msgs, list) else msgs}" for field, msgs in data.items()
        ]
        if field_errors:
            return "; ".join(field_errors)
    return f"15Five API error (HTTP {error.status}): {error.message}"


def _serialize(value: Any) -> Any:
    """Serialize a filter value for the 15Five query string (lists -> CSV, bools -> lowercase string)."""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    if isinstance(value, bool):
        return str(value).lower()
    return value


# ---- User Action Handlers ----


@fifteenfive.action("list_users")
class ListUsersAction(ActionHandler):
    """List users in the 15Five company, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("email") is not None:
                params["email"] = inputs.get("email")

            if inputs.get("employee_id") is not None:
                params["employee_id"] = inputs.get("employee_id")

            if inputs.get("first_name") is not None:
                params["first_name"] = inputs.get("first_name")

            if inputs.get("last_name") is not None:
                params["last_name"] = inputs.get("last_name")

            if inputs.get("location") is not None:
                params["location"] = inputs.get("location")

            if inputs.get("is_active") is not None:
                params["is_active"] = _serialize(inputs.get("is_active"))

            if inputs.get("is_company_admin") is not None:
                params["is_company_admin"] = _serialize(inputs.get("is_company_admin"))

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/user/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "users": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_user")
class GetUserAction(ActionHandler):
    """Retrieve a single 15Five user by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            user_id = inputs["user_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/user/{user_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"user": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Group & Department Action Handlers ----


@fifteenfive.action("list_groups")
class ListGroupsAction(ActionHandler):
    """List company groups, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("name__in") is not None:
                params["name__in"] = _serialize(inputs.get("name__in"))

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/group/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "groups": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_group")
class GetGroupAction(ActionHandler):
    """Retrieve a single company group by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            group_id = inputs["group_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/group/{group_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"group": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_group_types")
class ListGroupTypesAction(ActionHandler):
    """List company group types, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("name_plural") is not None:
                params["name_plural"] = inputs.get("name_plural")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/group-type/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "group_types": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_group_type")
class GetGroupTypeAction(ActionHandler):
    """Retrieve a single company group type by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            group_type_id = inputs["group_type_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/group-type/{group_type_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"group_type": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_departments")
class ListDepartmentsAction(ActionHandler):
    """List company departments, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("name") is not None:
                params["name"] = inputs.get("name")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/department/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "departments": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_department")
class GetDepartmentAction(ActionHandler):
    """Retrieve a single company department by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            department_id = inputs["department_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/department/{department_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"department": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Feature Status Action Handlers ----


@fifteenfive.action("get_feature_status")
class GetFeatureStatusAction(ActionHandler):
    """Retrieve which optional 15Five features are enabled for the company."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            response = await context.fetch(
                f"{get_base_url(context)}/feature-status/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"feature_status": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- People Attribute Action Handlers ----


@fifteenfive.action("list_attributes")
class ListAttributesAction(ActionHandler):
    """List custom people attribute definitions, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            response = await context.fetch(
                f"{get_base_url(context)}/attribute/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "attributes": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_attribute")
class GetAttributeAction(ActionHandler):
    """Retrieve a single custom people attribute definition by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            attribute_id = inputs["attribute_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/attribute/{attribute_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"attribute": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("create_attribute")
class CreateAttributeAction(ActionHandler):
    """Create a new custom people attribute definition."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            payload = {"name": inputs["name"], "datatype": inputs["datatype"]}

            response = await context.fetch(
                f"{get_base_url(context)}/attribute/",
                method="POST",
                headers=get_auth_headers(context),
                json=payload,
            )

            return ActionResult(data={"attribute": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_attribute_values")
class ListAttributeValuesAction(ActionHandler):
    """List values set for custom people attributes, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            response = await context.fetch(
                f"{get_base_url(context)}/attribute_value/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "attribute_values": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_attribute_value")
class GetAttributeValueAction(ActionHandler):
    """Retrieve a single people attribute value by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            attribute_value_id = inputs["attribute_value_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/attribute_value/{attribute_value_id}/",
                method="GET",
                headers=get_auth_headers(context),
            )

            return ActionResult(data={"attribute_value": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("create_attribute_value")
class CreateAttributeValueAction(ActionHandler):
    """Set a value for a custom people attribute on a user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            payload = {"name": inputs["name"], "value": inputs["value"]}

            if inputs.get("user_id") is not None:
                payload["user_id"] = inputs.get("user_id")

            response = await context.fetch(
                f"{get_base_url(context)}/attribute_value/",
                method="POST",
                headers=get_auth_headers(context),
                json=payload,
            )

            return ActionResult(data={"attribute_value": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Objective Action Handlers ----


@fifteenfive.action("list_objectives")
class ListObjectivesAction(ActionHandler):
    """List objectives (OKRs), with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("parent_id") is not None:
                params["parent_id"] = inputs.get("parent_id")

            if inputs.get("department_id") is not None:
                params["department_id"] = inputs.get("department_id")

            if inputs.get("scope") is not None:
                params["scope"] = inputs.get("scope")

            if inputs.get("state") is not None:
                params["state"] = inputs.get("state")

            if inputs.get("color") is not None:
                params["color"] = inputs.get("color")

            if inputs.get("start_after") is not None:
                params["start_after"] = inputs.get("start_after")

            if inputs.get("end_before") is not None:
                params["end_before"] = inputs.get("end_before")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/objective/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "objectives": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_objective")
class GetObjectiveAction(ActionHandler):
    """Retrieve a single objective (OKR) by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            objective_id = inputs["objective_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/objective/{objective_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"objective": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("create_objectives")
class CreateObjectivesAction(ActionHandler):
    """Create one or more objectives (OKRs) in a single request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            payload = inputs["objectives"]

            response = await context.fetch(
                f"{get_base_url(context)}/objective/",
                method="POST",
                headers=get_auth_headers(context),
                json=payload,
            )

            return ActionResult(data={"objectives": response.data or []})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_objective_history")
class ListObjectiveHistoryAction(ActionHandler):
    """List change history events across all objectives, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/objective/history/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "history": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_objective_history")
class GetObjectiveHistoryAction(ActionHandler):
    """Retrieve the change history for a single objective by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            objective_id = inputs["objective_id"]
            params = {}

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/objective/{objective_id}/history/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )

            return ActionResult(data={"history": response.data or []})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_key_results")
class ListKeyResultsAction(ActionHandler):
    """List the key results belonging to a single objective."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            objective_id = inputs["objective_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/objective/{objective_id}/", method="GET", headers=get_auth_headers(context)
            )
            objective = response.data or {}

            return ActionResult(data={"key_results": objective.get("key_results", [])})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- High Five Action Handlers ----


@fifteenfive.action("list_high_fives")
class ListHighFivesAction(ActionHandler):
    """List High Five peer recognition posts, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("report_id") is not None:
                params["report_id"] = inputs.get("report_id")

            if inputs.get("receiver_id") is not None:
                params["receiver_id"] = inputs.get("receiver_id")

            if inputs.get("created_on_start") is not None:
                params["created_on_start"] = inputs.get("created_on_start")

            if inputs.get("created_on_end") is not None:
                params["created_on_end"] = inputs.get("created_on_end")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/high-five/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "high_fives": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_high_five")
class GetHighFiveAction(ActionHandler):
    """Retrieve a single High Five recognition post by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            high_five_id = inputs["high_five_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/high-five/{high_five_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"high_five": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("create_high_five")
class CreateHighFiveAction(ActionHandler):
    """Post a new High Five recognition."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            payload = {"text": inputs["text"], "creator_id": inputs["creator_id"]}

            response = await context.fetch(
                f"{get_base_url(context)}/high-five/",
                method="POST",
                headers=get_auth_headers(context),
                json=payload,
            )

            return ActionResult(data={"high_five": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Check-in Report Action Handlers ----


@fifteenfive.action("list_reports")
class ListReportsAction(ActionHandler):
    """List check-in reports, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("due_date_start") is not None:
                params["due_date_start"] = inputs.get("due_date_start")

            if inputs.get("due_date_end") is not None:
                params["due_date_end"] = inputs.get("due_date_end")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/report/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "reports": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_report")
class GetReportAction(ActionHandler):
    """Retrieve a single check-in report by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            report_id = inputs["report_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/report/{report_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"report": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Answer Action Handlers ----


@fifteenfive.action("list_answers")
class ListAnswersAction(ActionHandler):
    """List answers submitted to check-in questions, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("question_id") is not None:
                params["question_id"] = inputs.get("question_id")

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("created_on_start") is not None:
                params["created_on_start"] = inputs.get("created_on_start")

            if inputs.get("created_on_end") is not None:
                params["created_on_end"] = inputs.get("created_on_end")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/answer/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "answers": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_answer")
class GetAnswerAction(ActionHandler):
    """Retrieve a single check-in answer by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            answer_id = inputs["answer_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/answer/{answer_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"answer": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Question Action Handlers ----


@fifteenfive.action("list_questions")
class ListQuestionsAction(ActionHandler):
    """List check-in question templates, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("group_id") is not None:
                params["group_id"] = inputs.get("group_id")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/question/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "questions": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_question")
class GetQuestionAction(ActionHandler):
    """Retrieve a single check-in question template by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            question_id = inputs["question_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/question/{question_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"question": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Priority Action Handlers ----


@fifteenfive.action("list_priorities")
class ListPrioritiesAction(ActionHandler):
    """List check-in priorities, with optional filters. This endpoint is not paginated."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("manager_id") is not None:
                params["manager_id"] = inputs.get("manager_id")

            if inputs.get("group_id") is not None:
                params["group_id"] = inputs.get("group_id")

            if inputs.get("include_past_checkins") is not None:
                params["include_past_checkins"] = _serialize(inputs.get("include_past_checkins"))

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/priority/", method="GET", headers=get_auth_headers(context), params=params
            )

            return ActionResult(data={"priorities": response.data or []})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("create_priorities")
class CreatePrioritiesAction(ActionHandler):
    """Create one or more check-in priorities in a single request."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            payload = inputs["priorities"]

            response = await context.fetch(
                f"{get_base_url(context)}/priority/",
                method="POST",
                headers=get_auth_headers(context),
                json=payload,
            )

            return ActionResult(data={"priorities": response.data or []})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Pulse Action Handlers ----


@fifteenfive.action("list_pulses")
class ListPulsesAction(ActionHandler):
    """List submitted employee Pulse scores, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("report_id") is not None:
                params["report_id"] = inputs.get("report_id")

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("created_on_start") is not None:
                params["created_on_start"] = inputs.get("created_on_start")

            if inputs.get("created_on_end") is not None:
                params["created_on_end"] = inputs.get("created_on_end")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("updated_after") is not None:
                params["updated_after"] = inputs.get("updated_after")

            if inputs.get("updated_before") is not None:
                params["updated_before"] = inputs.get("updated_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/pulse/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "pulses": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_pulse")
class GetPulseAction(ActionHandler):
    """Retrieve a single Pulse score by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            pulse_id = inputs["pulse_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/pulse/{pulse_id}/", method="GET", headers=get_auth_headers(context)
            )

            return ActionResult(data={"pulse": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Review Cycle Action Handlers ----


@fifteenfive.action("list_review_cycles")
class ListReviewCyclesAction(ActionHandler):
    """List performance review cycles, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("created_on_start") is not None:
                params["created_on_start"] = inputs.get("created_on_start")

            if inputs.get("created_on_end") is not None:
                params["created_on_end"] = inputs.get("created_on_end")

            if inputs.get("started_on_start") is not None:
                params["started_on_start"] = inputs.get("started_on_start")

            if inputs.get("started_on_end") is not None:
                params["started_on_end"] = inputs.get("started_on_end")

            if inputs.get("ended_on_start") is not None:
                params["ended_on_start"] = inputs.get("ended_on_start")

            if inputs.get("ended_on_end") is not None:
                params["ended_on_end"] = inputs.get("ended_on_end")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "review_cycles": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_review_cycle")
class GetReviewCycleAction(ActionHandler):
    """Retrieve a single performance review cycle by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            review_cycle_id = inputs["review_cycle_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/{review_cycle_id}/",
                method="GET",
                headers=get_auth_headers(context),
            )

            return ActionResult(data={"review_cycle": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_review_cycle_participants")
class ListReviewCycleParticipantsAction(ActionHandler):
    """List the participants of a review cycle, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            review_cycle_id = inputs["review_cycle_id"]
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("group_id") is not None:
                params["group_id"] = inputs.get("group_id")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/{review_cycle_id}/participants/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "participants": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_review_cycle_results_answers")
class ListReviewCycleResultsAnswersAction(ActionHandler):
    """Retrieve the questions and answers submitted within a review cycle."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            review_cycle_id = inputs["review_cycle_id"]
            params = {}

            if inputs.get("section_type") is not None:
                params["section_type"] = inputs.get("section_type")

            if inputs.get("participating_user_id") is not None:
                params["participating_user_id"] = inputs.get("participating_user_id")

            if inputs.get("manager_id") is not None:
                params["manager_id"] = inputs.get("manager_id")

            if inputs.get("question_id") is not None:
                params["question_id"] = inputs.get("question_id")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/{review_cycle_id}/results/answers/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "results": body.get("results", {}),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_review_cycle_results_performance_measurements")
class ListReviewCycleResultsPerformanceMeasurementsAction(ActionHandler):
    """Retrieve the performance measurements calculated for a review cycle."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            review_cycle_id = inputs["review_cycle_id"]
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("manager_id") is not None:
                params["manager_id"] = inputs.get("manager_id")

            if inputs.get("group_id") is not None:
                params["group_id"] = inputs.get("group_id")

            if inputs.get("definition_type") is not None:
                params["definition_type"] = inputs.get("definition_type")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/{review_cycle_id}/results/performance-measurements/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "performance_measurements": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("list_reviews")
class ListReviewsAction(ActionHandler):
    """List individual reviews within a review cycle, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            review_cycle_id = inputs["review_cycle_id"]
            params = {}

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("due_date_start") is not None:
                params["due_date_start"] = inputs.get("due_date_start")

            if inputs.get("due_date_end") is not None:
                params["due_date_end"] = inputs.get("due_date_end")

            if inputs.get("is_complete") is not None:
                params["is_complete"] = _serialize(inputs.get("is_complete"))

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/review-cycle/{review_cycle_id}/reviews/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "reviews": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- 1-on-1 Action Handlers ----


@fifteenfive.action("list_one_on_ones")
class ListOneOnOnesAction(ActionHandler):
    """List 1-on-1 meetings, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("type") is not None:
                params["type"] = inputs.get("type")

            if inputs.get("is_draft") is not None:
                params["is_draft"] = _serialize(inputs.get("is_draft"))

            if inputs.get("group_id") is not None:
                params["group_id"] = inputs.get("group_id")

            if inputs.get("user_id") is not None:
                params["user_id"] = inputs.get("user_id")

            if inputs.get("created_on_start") is not None:
                params["created_on_start"] = inputs.get("created_on_start")

            if inputs.get("created_on_end") is not None:
                params["created_on_end"] = inputs.get("created_on_end")

            if inputs.get("scheduled_on_start") is not None:
                params["scheduled_on_start"] = inputs.get("scheduled_on_start")

            if inputs.get("scheduled_on_end") is not None:
                params["scheduled_on_end"] = inputs.get("scheduled_on_end")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            response = await context.fetch(
                f"{get_base_url(context)}/one-on-one/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "one_on_ones": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


@fifteenfive.action("get_one_on_one")
class GetOneOnOneAction(ActionHandler):
    """Retrieve a single 1-on-1 meeting by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            one_on_one_id = inputs["one_on_one_id"]

            response = await context.fetch(
                f"{get_base_url(context)}/one-on-one/{one_on_one_id}/",
                method="GET",
                headers=get_auth_headers(context),
            )

            return ActionResult(data={"one_on_one": response.data or {}})
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Vacation Action Handlers ----


@fifteenfive.action("list_vacations")
class ListVacationsAction(ActionHandler):
    """List recorded user vacations, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("user") is not None:
                params["user"] = _serialize(inputs.get("user"))

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/vacation/", method="GET", headers=get_auth_headers(context), params=params
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "vacations": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))


# ---- Security Audit Action Handlers ----


@fifteenfive.action("list_security_audit")
class ListSecurityAuditAction(ActionHandler):
    """List security audit log events for the company, with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Any:
        try:
            params = {}

            if inputs.get("actor_id") is not None:
                params["actor_id"] = inputs.get("actor_id")

            if inputs.get("created_after") is not None:
                params["created_after"] = inputs.get("created_after")

            if inputs.get("created_before") is not None:
                params["created_before"] = inputs.get("created_before")

            if inputs.get("page") is not None:
                params["page"] = inputs.get("page")

            if inputs.get("order_by") is not None:
                params["order_by"] = inputs.get("order_by")

            response = await context.fetch(
                f"{get_base_url(context)}/security-audit/",
                method="GET",
                headers=get_auth_headers(context),
                params=params,
            )
            body = response.data or {}

            return ActionResult(
                data={
                    "count": body.get("count"),
                    "next": body.get("next"),
                    "previous": body.get("previous"),
                    "events": body.get("results", []),
                }
            )
        except HTTPError as e:
            return ActionError(message=extract_error_message(e))
        except Exception as e:
            return ActionError(message=str(e))
