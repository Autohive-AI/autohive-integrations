from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any

# Create the integration using the config.json
pipedrive = Integration.load()

# Base URL for Pipedrive API
PIPEDRIVE_API_BASE_URL = "https://api.pipedrive.com/v1"


# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.


# ---- Deal Handlers ----


@pipedrive.action("create_deal")
class CreateDealAction(ActionHandler):
    """Create a new deal in Pipedrive."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"title": inputs["title"]}

            # Add optional fields
            if inputs.get("value") is not None:
                data["value"] = inputs.get("value")
            if inputs.get("currency"):
                data["currency"] = inputs.get("currency")
            if inputs.get("person_id"):
                data["person_id"] = inputs.get("person_id")
            if inputs.get("org_id"):
                data["org_id"] = inputs.get("org_id")
            if inputs.get("pipeline_id"):
                data["pipeline_id"] = inputs.get("pipeline_id")
            if inputs.get("stage_id"):
                data["stage_id"] = inputs.get("stage_id")
            if inputs.get("status"):
                data["status"] = inputs.get("status")
            if inputs.get("expected_close_date"):
                data["expected_close_date"] = inputs.get("expected_close_date")
            if inputs.get("user_id"):
                data["user_id"] = inputs.get("user_id")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/deals", method="POST", json=data)

            return ActionResult(data={"deal": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("get_deal")
class GetDealAction(ActionHandler):
    """Get details of a specific deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs["deal_id"]

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}", method="GET")

            return ActionResult(data={"deal": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("update_deal")
class UpdateDealAction(ActionHandler):
    """Update an existing deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs["deal_id"]
            data = {}

            # Add only provided fields
            if inputs.get("title"):
                data["title"] = inputs.get("title")
            if inputs.get("value") is not None:
                data["value"] = inputs.get("value")
            if inputs.get("currency"):
                data["currency"] = inputs.get("currency")
            if "person_id" in inputs:
                data["person_id"] = inputs.get("person_id")
            if "org_id" in inputs:
                data["org_id"] = inputs.get("org_id")
            if inputs.get("stage_id"):
                data["stage_id"] = inputs.get("stage_id")
            if inputs.get("status"):
                data["status"] = inputs.get("status")
            if "expected_close_date" in inputs:
                data["expected_close_date"] = inputs.get("expected_close_date")
            if inputs.get("user_id"):
                data["user_id"] = inputs.get("user_id")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}", method="PUT", json=data)

            return ActionResult(data={"deal": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("list_deals")
class ListDealsAction(ActionHandler):
    """List deals with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("user_id"):
                params["user_id"] = inputs.get("user_id")
            if inputs.get("stage_id"):
                params["stage_id"] = inputs.get("stage_id")
            if inputs.get("status"):
                params["status"] = inputs.get("status")
            if inputs.get("filter_id"):
                params["filter_id"] = inputs.get("filter_id")
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")
            if inputs.get("sort"):
                params["sort"] = inputs.get("sort")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/deals", method="GET", params=params)

            deals = response.data.get("data", [])
            return ActionResult(data={"deals": deals}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("delete_deal")
class DeleteDealAction(ActionHandler):
    """Delete a deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs["deal_id"]

            await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}", method="DELETE")

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Person Handlers ----


@pipedrive.action("create_person")
class CreatePersonAction(ActionHandler):
    """Create a new person (contact) in Pipedrive."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"name": inputs["name"]}

            # Add optional fields
            if inputs.get("email"):
                data["email"] = inputs.get("email")
            if inputs.get("phone"):
                data["phone"] = inputs.get("phone")
            if inputs.get("org_id"):
                data["org_id"] = inputs.get("org_id")
            if inputs.get("owner_id"):
                data["owner_id"] = inputs.get("owner_id")
            if inputs.get("visible_to"):
                data["visible_to"] = inputs.get("visible_to")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/persons", method="POST", json=data)

            return ActionResult(data={"person": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("get_person")
class GetPersonAction(ActionHandler):
    """Get details of a specific person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs["person_id"]

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}", method="GET")

            return ActionResult(data={"person": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("update_person")
class UpdatePersonAction(ActionHandler):
    """Update an existing person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs["person_id"]
            data = {}

            if inputs.get("name"):
                data["name"] = inputs.get("name")
            if "email" in inputs:
                data["email"] = inputs.get("email")
            if "phone" in inputs:
                data["phone"] = inputs.get("phone")
            if "org_id" in inputs:
                data["org_id"] = inputs.get("org_id")
            if inputs.get("owner_id"):
                data["owner_id"] = inputs.get("owner_id")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}", method="PUT", json=data)

            return ActionResult(data={"person": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("list_persons")
class ListPersonsAction(ActionHandler):
    """List persons with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("user_id"):
                params["user_id"] = inputs.get("user_id")
            if inputs.get("filter_id"):
                params["filter_id"] = inputs.get("filter_id")
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")
            if inputs.get("sort"):
                params["sort"] = inputs.get("sort")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/persons", method="GET", params=params)

            persons = response.data.get("data", [])
            return ActionResult(data={"persons": persons}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("delete_person")
class DeletePersonAction(ActionHandler):
    """Delete a person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs["person_id"]

            await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}", method="DELETE")

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Organization Handlers ----


@pipedrive.action("create_organization")
class CreateOrganizationAction(ActionHandler):
    """Create a new organization in Pipedrive."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"name": inputs["name"]}

            if inputs.get("owner_id"):
                data["owner_id"] = inputs.get("owner_id")
            if inputs.get("visible_to"):
                data["visible_to"] = inputs.get("visible_to")
            if inputs.get("address"):
                data["address"] = inputs.get("address")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/organizations", method="POST", json=data)

            return ActionResult(data={"organization": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("get_organization")
class GetOrganizationAction(ActionHandler):
    """Get details of a specific organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs["org_id"]

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}", method="GET")

            return ActionResult(data={"organization": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("update_organization")
class UpdateOrganizationAction(ActionHandler):
    """Update an existing organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs["org_id"]
            data = {}

            if inputs.get("name"):
                data["name"] = inputs.get("name")
            if inputs.get("owner_id"):
                data["owner_id"] = inputs.get("owner_id")
            if "address" in inputs:
                data["address"] = inputs.get("address")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}", method="PUT", json=data)

            return ActionResult(data={"organization": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("list_organizations")
class ListOrganizationsAction(ActionHandler):
    """List organizations with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("user_id"):
                params["user_id"] = inputs.get("user_id")
            if inputs.get("filter_id"):
                params["filter_id"] = inputs.get("filter_id")
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")
            if inputs.get("sort"):
                params["sort"] = inputs.get("sort")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/organizations", method="GET", params=params)

            organizations = response.data.get("data", [])
            return ActionResult(data={"organizations": organizations}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("delete_organization")
class DeleteOrganizationAction(ActionHandler):
    """Delete an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs["org_id"]

            await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}", method="DELETE")

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Activity Handlers ----


@pipedrive.action("create_activity")
class CreateActivityAction(ActionHandler):
    """Create a new activity (task, call, meeting, etc.)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"subject": inputs["subject"], "type": inputs["type"]}

            if inputs.get("due_date"):
                data["due_date"] = inputs.get("due_date")
            if inputs.get("due_time"):
                data["due_time"] = inputs.get("due_time")
            if inputs.get("duration"):
                data["duration"] = inputs.get("duration")
            if inputs.get("deal_id"):
                data["deal_id"] = inputs.get("deal_id")
            if inputs.get("person_id"):
                data["person_id"] = inputs.get("person_id")
            if inputs.get("org_id"):
                data["org_id"] = inputs.get("org_id")
            if inputs.get("user_id"):
                data["user_id"] = inputs.get("user_id")
            if inputs.get("note"):
                data["note"] = inputs.get("note")
            if inputs.get("done") is not None:
                data["done"] = inputs.get("done")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/activities", method="POST", json=data)

            return ActionResult(data={"activity": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("get_activity")
class GetActivityAction(ActionHandler):
    """Get details of a specific activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs["activity_id"]

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}", method="GET")

            return ActionResult(data={"activity": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("update_activity")
class UpdateActivityAction(ActionHandler):
    """Update an existing activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs["activity_id"]
            data = {}

            if inputs.get("subject"):
                data["subject"] = inputs.get("subject")
            if inputs.get("type"):
                data["type"] = inputs.get("type")
            if "due_date" in inputs:
                data["due_date"] = inputs.get("due_date")
            if "due_time" in inputs:
                data["due_time"] = inputs.get("due_time")
            if "duration" in inputs:
                data["duration"] = inputs.get("duration")
            if inputs.get("done") is not None:
                data["done"] = inputs.get("done")
            if "note" in inputs:
                data["note"] = inputs.get("note")

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}", method="PUT", json=data
            )

            return ActionResult(data={"activity": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("list_activities")
class ListActivitiesAction(ActionHandler):
    """List activities with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("user_id"):
                params["user_id"] = inputs.get("user_id")
            if inputs.get("deal_id"):
                params["deal_id"] = inputs.get("deal_id")
            if inputs.get("person_id"):
                params["person_id"] = inputs.get("person_id")
            if inputs.get("org_id"):
                params["org_id"] = inputs.get("org_id")
            if inputs.get("type"):
                params["type"] = inputs.get("type")
            if inputs.get("done") is not None:
                params["done"] = 1 if inputs.get("done") else 0
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/activities", method="GET", params=params)

            activities = response.data.get("data", [])
            return ActionResult(data={"activities": activities}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("delete_activity")
class DeleteActivityAction(ActionHandler):
    """Delete an activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs["activity_id"]

            await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}", method="DELETE")

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Note Handlers ----


@pipedrive.action("create_note")
class CreateNoteAction(ActionHandler):
    """Add a note to a deal, person, or organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {"content": inputs["content"]}

            if inputs.get("deal_id"):
                data["deal_id"] = inputs.get("deal_id")
            if inputs.get("person_id"):
                data["person_id"] = inputs.get("person_id")
            if inputs.get("org_id"):
                data["org_id"] = inputs.get("org_id")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/notes", method="POST", json=data)

            return ActionResult(data={"note": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("list_notes")
class ListNotesAction(ActionHandler):
    """List notes with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("deal_id"):
                params["deal_id"] = inputs.get("deal_id")
            if inputs.get("person_id"):
                params["person_id"] = inputs.get("person_id")
            if inputs.get("org_id"):
                params["org_id"] = inputs.get("org_id")
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/notes", method="GET", params=params)

            notes = response.data.get("data", [])
            return ActionResult(data={"notes": notes}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Pipeline Handlers ----


@pipedrive.action("list_pipelines")
class ListPipelinesAction(ActionHandler):
    """List all pipelines."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/pipelines", method="GET")

            pipelines = response.data.get("data", [])
            return ActionResult(data={"pipelines": pipelines}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@pipedrive.action("get_pipeline")
class GetPipelineAction(ActionHandler):
    """Get details of a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            pipeline_id = inputs["pipeline_id"]

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/pipelines/{pipeline_id}", method="GET")

            return ActionResult(data={"pipeline": response.data.get("data", {})}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Stage Handlers ----


@pipedrive.action("list_stages")
class ListStagesAction(ActionHandler):
    """List stages in a pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("pipeline_id"):
                params["pipeline_id"] = inputs.get("pipeline_id")

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/stages", method="GET", params=params if params else None
            )

            stages = response.data.get("data", [])
            return ActionResult(data={"stages": stages}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


# ---- Search Handler ----


@pipedrive.action("search")
class SearchAction(ActionHandler):
    """Search across all items (deals, persons, organizations, etc.)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"term": inputs["term"]}

            if inputs.get("item_types"):
                params["item_types"] = ",".join(inputs.get("item_types"))
            if inputs.get("fields"):
                params["fields"] = ",".join(inputs.get("fields"))
            if inputs.get("exact_match") is not None:
                params["exact_match"] = "true" if inputs.get("exact_match") else "false"
            if "start" in inputs:
                params["start"] = inputs.get("start")
            if "limit" in inputs:
                params["limit"] = inputs.get("limit")

            response = await context.fetch(f"{PIPEDRIVE_API_BASE_URL}/itemSearch", method="GET", params=params)

            items = response.data.get("data", {}).get("items", [])
            return ActionResult(data={"items": items}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
