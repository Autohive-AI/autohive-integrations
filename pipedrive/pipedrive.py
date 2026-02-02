from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
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
            data = {
                "title": inputs['title']
            }

            # Add optional fields
            if 'value' in inputs and inputs['value'] is not None:
                data['value'] = inputs['value']
            if 'currency' in inputs and inputs['currency']:
                data['currency'] = inputs['currency']
            if 'person_id' in inputs and inputs['person_id']:
                data['person_id'] = inputs['person_id']
            if 'org_id' in inputs and inputs['org_id']:
                data['org_id'] = inputs['org_id']
            if 'pipeline_id' in inputs and inputs['pipeline_id']:
                data['pipeline_id'] = inputs['pipeline_id']
            if 'stage_id' in inputs and inputs['stage_id']:
                data['stage_id'] = inputs['stage_id']
            if 'status' in inputs and inputs['status']:
                data['status'] = inputs['status']
            if 'expected_close_date' in inputs and inputs['expected_close_date']:
                data['expected_close_date'] = inputs['expected_close_date']
            if 'user_id' in inputs and inputs['user_id']:
                data['user_id'] = inputs['user_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/deals",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"deal": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deal": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("get_deal")
class GetDealAction(ActionHandler):
    """Get details of a specific deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs['deal_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}",
                method="GET"
            )

            return ActionResult(
                data={"deal": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deal": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("update_deal")
class UpdateDealAction(ActionHandler):
    """Update an existing deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs['deal_id']
            data = {}

            # Add only provided fields
            if 'title' in inputs and inputs['title']:
                data['title'] = inputs['title']
            if 'value' in inputs and inputs['value'] is not None:
                data['value'] = inputs['value']
            if 'currency' in inputs and inputs['currency']:
                data['currency'] = inputs['currency']
            if 'person_id' in inputs:
                data['person_id'] = inputs['person_id']
            if 'org_id' in inputs:
                data['org_id'] = inputs['org_id']
            if 'stage_id' in inputs and inputs['stage_id']:
                data['stage_id'] = inputs['stage_id']
            if 'status' in inputs and inputs['status']:
                data['status'] = inputs['status']
            if 'expected_close_date' in inputs:
                data['expected_close_date'] = inputs['expected_close_date']
            if 'user_id' in inputs and inputs['user_id']:
                data['user_id'] = inputs['user_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"deal": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deal": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("list_deals")
class ListDealsAction(ActionHandler):
    """List deals with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'user_id' in inputs and inputs['user_id']:
                params['user_id'] = inputs['user_id']
            if 'stage_id' in inputs and inputs['stage_id']:
                params['stage_id'] = inputs['stage_id']
            if 'status' in inputs and inputs['status']:
                params['status'] = inputs['status']
            if 'filter_id' in inputs and inputs['filter_id']:
                params['filter_id'] = inputs['filter_id']
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']
            if 'sort' in inputs and inputs['sort']:
                params['sort'] = inputs['sort']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/deals",
                method="GET",
                params=params
            )

            deals = response.get('data', [])
            return ActionResult(
                data={"deals": deals, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deals": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("delete_deal")
class DeleteDealAction(ActionHandler):
    """Delete a deal."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            deal_id = inputs['deal_id']

            await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/deals/{deal_id}",
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


# ---- Person Handlers ----

@pipedrive.action("create_person")
class CreatePersonAction(ActionHandler):
    """Create a new person (contact) in Pipedrive."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "name": inputs['name']
            }

            # Add optional fields
            if 'email' in inputs and inputs['email']:
                data['email'] = inputs['email']
            if 'phone' in inputs and inputs['phone']:
                data['phone'] = inputs['phone']
            if 'org_id' in inputs and inputs['org_id']:
                data['org_id'] = inputs['org_id']
            if 'owner_id' in inputs and inputs['owner_id']:
                data['owner_id'] = inputs['owner_id']
            if 'visible_to' in inputs and inputs['visible_to']:
                data['visible_to'] = inputs['visible_to']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/persons",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"person": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"person": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("get_person")
class GetPersonAction(ActionHandler):
    """Get details of a specific person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs['person_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}",
                method="GET"
            )

            return ActionResult(
                data={"person": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"person": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("update_person")
class UpdatePersonAction(ActionHandler):
    """Update an existing person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs['person_id']
            data = {}

            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'email' in inputs:
                data['email'] = inputs['email']
            if 'phone' in inputs:
                data['phone'] = inputs['phone']
            if 'org_id' in inputs:
                data['org_id'] = inputs['org_id']
            if 'owner_id' in inputs and inputs['owner_id']:
                data['owner_id'] = inputs['owner_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"person": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"person": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("list_persons")
class ListPersonsAction(ActionHandler):
    """List persons with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'user_id' in inputs and inputs['user_id']:
                params['user_id'] = inputs['user_id']
            if 'filter_id' in inputs and inputs['filter_id']:
                params['filter_id'] = inputs['filter_id']
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']
            if 'sort' in inputs and inputs['sort']:
                params['sort'] = inputs['sort']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/persons",
                method="GET",
                params=params
            )

            persons = response.get('data', [])
            return ActionResult(
                data={"persons": persons, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"persons": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("delete_person")
class DeletePersonAction(ActionHandler):
    """Delete a person."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            person_id = inputs['person_id']

            await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/persons/{person_id}",
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


# ---- Organization Handlers ----

@pipedrive.action("create_organization")
class CreateOrganizationAction(ActionHandler):
    """Create a new organization in Pipedrive."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "name": inputs['name']
            }

            if 'owner_id' in inputs and inputs['owner_id']:
                data['owner_id'] = inputs['owner_id']
            if 'visible_to' in inputs and inputs['visible_to']:
                data['visible_to'] = inputs['visible_to']
            if 'address' in inputs and inputs['address']:
                data['address'] = inputs['address']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/organizations",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"organization": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"organization": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("get_organization")
class GetOrganizationAction(ActionHandler):
    """Get details of a specific organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs['org_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}",
                method="GET"
            )

            return ActionResult(
                data={"organization": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"organization": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("update_organization")
class UpdateOrganizationAction(ActionHandler):
    """Update an existing organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs['org_id']
            data = {}

            if 'name' in inputs and inputs['name']:
                data['name'] = inputs['name']
            if 'owner_id' in inputs and inputs['owner_id']:
                data['owner_id'] = inputs['owner_id']
            if 'address' in inputs:
                data['address'] = inputs['address']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"organization": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"organization": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("list_organizations")
class ListOrganizationsAction(ActionHandler):
    """List organizations with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'user_id' in inputs and inputs['user_id']:
                params['user_id'] = inputs['user_id']
            if 'filter_id' in inputs and inputs['filter_id']:
                params['filter_id'] = inputs['filter_id']
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']
            if 'sort' in inputs and inputs['sort']:
                params['sort'] = inputs['sort']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/organizations",
                method="GET",
                params=params
            )

            organizations = response.get('data', [])
            return ActionResult(
                data={"organizations": organizations, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"organizations": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("delete_organization")
class DeleteOrganizationAction(ActionHandler):
    """Delete an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            org_id = inputs['org_id']

            await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/organizations/{org_id}",
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


# ---- Activity Handlers ----

@pipedrive.action("create_activity")
class CreateActivityAction(ActionHandler):
    """Create a new activity (task, call, meeting, etc.)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "subject": inputs['subject'],
                "type": inputs['type']
            }

            if 'due_date' in inputs and inputs['due_date']:
                data['due_date'] = inputs['due_date']
            if 'due_time' in inputs and inputs['due_time']:
                data['due_time'] = inputs['due_time']
            if 'duration' in inputs and inputs['duration']:
                data['duration'] = inputs['duration']
            if 'deal_id' in inputs and inputs['deal_id']:
                data['deal_id'] = inputs['deal_id']
            if 'person_id' in inputs and inputs['person_id']:
                data['person_id'] = inputs['person_id']
            if 'org_id' in inputs and inputs['org_id']:
                data['org_id'] = inputs['org_id']
            if 'user_id' in inputs and inputs['user_id']:
                data['user_id'] = inputs['user_id']
            if 'note' in inputs and inputs['note']:
                data['note'] = inputs['note']
            if 'done' in inputs and inputs['done'] is not None:
                data['done'] = inputs['done']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"activity": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"activity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("get_activity")
class GetActivityAction(ActionHandler):
    """Get details of a specific activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs['activity_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}",
                method="GET"
            )

            return ActionResult(
                data={"activity": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"activity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("update_activity")
class UpdateActivityAction(ActionHandler):
    """Update an existing activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs['activity_id']
            data = {}

            if 'subject' in inputs and inputs['subject']:
                data['subject'] = inputs['subject']
            if 'type' in inputs and inputs['type']:
                data['type'] = inputs['type']
            if 'due_date' in inputs:
                data['due_date'] = inputs['due_date']
            if 'due_time' in inputs:
                data['due_time'] = inputs['due_time']
            if 'duration' in inputs:
                data['duration'] = inputs['duration']
            if 'done' in inputs and inputs['done'] is not None:
                data['done'] = inputs['done']
            if 'note' in inputs:
                data['note'] = inputs['note']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}",
                method="PUT",
                json=data
            )

            return ActionResult(
                data={"activity": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"activity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("list_activities")
class ListActivitiesAction(ActionHandler):
    """List activities with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'user_id' in inputs and inputs['user_id']:
                params['user_id'] = inputs['user_id']
            if 'deal_id' in inputs and inputs['deal_id']:
                params['deal_id'] = inputs['deal_id']
            if 'person_id' in inputs and inputs['person_id']:
                params['person_id'] = inputs['person_id']
            if 'org_id' in inputs and inputs['org_id']:
                params['org_id'] = inputs['org_id']
            if 'type' in inputs and inputs['type']:
                params['type'] = inputs['type']
            if 'done' in inputs and inputs['done'] is not None:
                params['done'] = 1 if inputs['done'] else 0
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities",
                method="GET",
                params=params
            )

            activities = response.get('data', [])
            return ActionResult(
                data={"activities": activities, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"activities": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("delete_activity")
class DeleteActivityAction(ActionHandler):
    """Delete an activity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            activity_id = inputs['activity_id']

            await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/activities/{activity_id}",
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


# ---- Note Handlers ----

@pipedrive.action("create_note")
class CreateNoteAction(ActionHandler):
    """Add a note to a deal, person, or organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = {
                "content": inputs['content']
            }

            if 'deal_id' in inputs and inputs['deal_id']:
                data['deal_id'] = inputs['deal_id']
            if 'person_id' in inputs and inputs['person_id']:
                data['person_id'] = inputs['person_id']
            if 'org_id' in inputs and inputs['org_id']:
                data['org_id'] = inputs['org_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/notes",
                method="POST",
                json=data
            )

            return ActionResult(
                data={"note": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"note": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("list_notes")
class ListNotesAction(ActionHandler):
    """List notes with filtering options."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'deal_id' in inputs and inputs['deal_id']:
                params['deal_id'] = inputs['deal_id']
            if 'person_id' in inputs and inputs['person_id']:
                params['person_id'] = inputs['person_id']
            if 'org_id' in inputs and inputs['org_id']:
                params['org_id'] = inputs['org_id']
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/notes",
                method="GET",
                params=params
            )

            notes = response.get('data', [])
            return ActionResult(
                data={"notes": notes, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"notes": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Pipeline Handlers ----

@pipedrive.action("list_pipelines")
class ListPipelinesAction(ActionHandler):
    """List all pipelines."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/pipelines",
                method="GET"
            )

            pipelines = response.get('data', [])
            return ActionResult(
                data={"pipelines": pipelines, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"pipelines": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@pipedrive.action("get_pipeline")
class GetPipelineAction(ActionHandler):
    """Get details of a specific pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            pipeline_id = inputs['pipeline_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/pipelines/{pipeline_id}",
                method="GET"
            )

            return ActionResult(
                data={"pipeline": response.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"pipeline": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Stage Handlers ----

@pipedrive.action("list_stages")
class ListStagesAction(ActionHandler):
    """List stages in a pipeline."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if 'pipeline_id' in inputs and inputs['pipeline_id']:
                params['pipeline_id'] = inputs['pipeline_id']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/stages",
                method="GET",
                params=params if params else None
            )

            stages = response.get('data', [])
            return ActionResult(
                data={"stages": stages, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"stages": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Search Handler ----

@pipedrive.action("search")
class SearchAction(ActionHandler):
    """Search across all items (deals, persons, organizations, etc.)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "term": inputs['term']
            }

            if 'item_types' in inputs and inputs['item_types']:
                params['item_types'] = ','.join(inputs['item_types'])
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            if 'exact_match' in inputs and inputs['exact_match'] is not None:
                params['exact_match'] = inputs['exact_match']
            if 'start' in inputs:
                params['start'] = inputs['start']
            if 'limit' in inputs:
                params['limit'] = inputs['limit']

            response = await context.fetch(
                f"{PIPEDRIVE_API_BASE_URL}/itemSearch",
                method="GET",
                params=params
            )

            items = response.get('data', {}).get('items', [])
            return ActionResult(
                data={"items": items, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"items": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )
