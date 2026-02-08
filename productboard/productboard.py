from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, parse_qs
import re

productboard = Integration.load()

PRODUCTBOARD_API_BASE_URL = "https://api.productboard.com"
API_VERSION = "v2"

SUCCESS_STATUSES = {200, 201}
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


def get_common_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def parse_error(response, default_msg: str = "Unknown error") -> str:
    """Extract error message from Productboard API error response."""
    try:
        body = response.json()
    except Exception:
        return f"{default_msg} (HTTP {response.status_code})"

    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0] or {}
        detail = first.get("detail") or first.get("title")
        code = first.get("code")
        if code:
            return f"{detail or default_msg} (code={code}, http={response.status_code})"
        return detail or default_msg

    return f"{default_msg} (HTTP {response.status_code})"


def extract_page_cursor(next_link: Optional[str]) -> Optional[str]:
    """Extract pageCursor value from a full pagination URL."""
    if not next_link:
        return None
    try:
        parsed = urlparse(next_link)
        qs = parse_qs(parsed.query)
        cursors = qs.get("pageCursor")
        return cursors[0] if cursors else None
    except Exception:
        return None


def is_uuid(value: str) -> bool:
    """Check if a string looks like a UUID."""
    return bool(UUID_PATTERN.match(value))


def build_status_value(status: str) -> Dict[str, str]:
    """Build status field assignment object."""
    if is_uuid(status):
        return {"id": status}
    return {"name": status}


# ---- Entity Handlers ----

@productboard.action("list_entities")
class ListEntitiesAction(ActionHandler):
    """Retrieves a paginated list of entities."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get('type'):
                params['type'] = inputs['type']
            if inputs.get('archived') is not None:
                params['archived'] = str(inputs['archived']).lower()
            if inputs.get('fields'):
                params['fields'] = inputs['fields']
            if inputs.get('page_cursor'):
                params['pageCursor'] = inputs['page_cursor']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/entities",
                method="GET",
                headers=get_common_headers(),
                params=params if params else None
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "entities": [],
                        "result": False,
                        "error": parse_error(response, "Failed to list entities")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            next_link = data.get('links', {}).get('next')
            next_cursor = extract_page_cursor(next_link)

            return ActionResult(
                data={
                    "entities": data.get('data', []),
                    "next_cursor": next_cursor,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"entities": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("get_entity")
class GetEntityAction(ActionHandler):
    """Retrieves details of a specific entity by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            entity_id = inputs['entity_id']
            params = {}

            if inputs.get('fields'):
                params['fields'] = inputs['fields']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/entities/{entity_id}",
                method="GET",
                headers=get_common_headers(),
                params=params if params else None
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get entity")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"entity": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"entity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("create_entity")
class CreateEntityAction(ActionHandler):
    """Creates a new entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            custom_fields = inputs.get('custom_fields')
            if custom_fields and not isinstance(custom_fields, dict):
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": "custom_fields must be an object"
                    },
                    cost_usd=0.0
                )

            entity_data = {
                "type": inputs['type'],
                "fields": {
                    "name": inputs['name']
                }
            }

            if inputs.get('parent_id'):
                entity_data['relationships'] = {
                    "parent": {
                        "data": {"id": inputs['parent_id']}
                    }
                }
            if inputs.get('status'):
                entity_data['fields']['status'] = build_status_value(inputs['status'])
            if inputs.get('description'):
                entity_data['fields']['description'] = inputs['description']
            if custom_fields:
                entity_data['fields'].update(custom_fields)

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/entities",
                method="POST",
                headers=get_common_headers(),
                json={"data": entity_data}
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": parse_error(response, "Failed to create entity")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"entity": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"entity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("update_entity")
class UpdateEntityAction(ActionHandler):
    """Updates an existing entity."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            entity_id = inputs['entity_id']

            custom_fields = inputs.get('custom_fields')
            if custom_fields and not isinstance(custom_fields, dict):
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": "custom_fields must be an object"
                    },
                    cost_usd=0.0
                )

            patch_operations = []

            if inputs.get('name'):
                patch_operations.append({
                    "op": "set",
                    "field": "name",
                    "value": inputs['name']
                })
            if inputs.get('status'):
                patch_operations.append({
                    "op": "set",
                    "field": "status",
                    "value": build_status_value(inputs['status'])
                })
            if inputs.get('description'):
                patch_operations.append({
                    "op": "set",
                    "field": "description",
                    "value": inputs['description']
                })
            if inputs.get('archived') is not None:
                patch_operations.append({
                    "op": "set",
                    "field": "archived",
                    "value": inputs['archived']
                })
            if custom_fields:
                for field_name, field_value in custom_fields.items():
                    patch_operations.append({
                        "op": "set",
                        "field": field_name,
                        "value": field_value
                    })

            if not patch_operations:
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": "No fields provided to update"
                    },
                    cost_usd=0.0
                )

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/entities/{entity_id}",
                method="PATCH",
                headers=get_common_headers(),
                json={"data": {"patch": patch_operations}}
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "entity": {},
                        "result": False,
                        "error": parse_error(response, "Failed to update entity")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"entity": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"entity": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("get_entity_configuration")
class GetEntityConfigurationAction(ActionHandler):
    """Returns metadata for a specific entity type."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            entity_type = inputs['type']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/entities/configurations/{entity_type}",
                method="GET",
                headers=get_common_headers()
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "configuration": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get configuration")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"configuration": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"configuration": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Note Handlers ----

@productboard.action("list_notes")
class ListNotesAction(ActionHandler):
    """Retrieves a list of notes from your workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get('archived') is not None:
                params['archived'] = str(inputs['archived']).lower()
            if inputs.get('processed') is not None:
                params['processed'] = str(inputs['processed']).lower()
            if inputs.get('owner_email'):
                params['owner[email]'] = inputs['owner_email']
            if inputs.get('owner_id'):
                params['owner[id]'] = inputs['owner_id']
            if inputs.get('creator_email'):
                params['creator[email]'] = inputs['creator_email']
            if inputs.get('source_record_id'):
                params['source[recordId]'] = inputs['source_record_id']
            if inputs.get('created_from'):
                params['createdFrom'] = inputs['created_from']
            if inputs.get('created_to'):
                params['createdTo'] = inputs['created_to']
            if inputs.get('updated_from'):
                params['updatedFrom'] = inputs['updated_from']
            if inputs.get('updated_to'):
                params['updatedTo'] = inputs['updated_to']
            if inputs.get('fields'):
                params['fields'] = inputs['fields']
            if inputs.get('page_cursor'):
                params['pageCursor'] = inputs['page_cursor']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/notes",
                method="GET",
                headers=get_common_headers(),
                params=params if params else None
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "notes": [],
                        "result": False,
                        "error": parse_error(response, "Failed to list notes")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            next_link = data.get('links', {}).get('next')
            next_cursor = extract_page_cursor(next_link)

            return ActionResult(
                data={
                    "notes": data.get('data', []),
                    "next_cursor": next_cursor,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"notes": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("get_note")
class GetNoteAction(ActionHandler):
    """Retrieves details of a specific note by its ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            note_id = inputs['note_id']
            params = {}

            if inputs.get('fields'):
                params['fields'] = inputs['fields']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/notes/{note_id}",
                method="GET",
                headers=get_common_headers(),
                params=params if params else None
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get note")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"note": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"note": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("create_note")
class CreateNoteAction(ActionHandler):
    """Creates a new note."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            tags = inputs.get('tags')
            if tags and not isinstance(tags, list):
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": "tags must be an array"
                    },
                    cost_usd=0.0
                )

            messages = inputs.get('messages')
            if messages and not isinstance(messages, list):
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": "messages must be an array"
                    },
                    cost_usd=0.0
                )

            note_data = {
                "type": inputs['type'],
                "fields": {
                    "name": inputs['name']
                }
            }

            if inputs.get('content') and inputs['type'] == 'simple':
                note_data['fields']['content'] = inputs['content']
            if messages and inputs['type'] == 'conversation':
                note_data['fields']['content'] = messages
            if inputs.get('owner_email'):
                note_data['fields']['owner'] = {"email": inputs['owner_email']}
            if tags:
                note_data['fields']['tags'] = tags
            if inputs.get('source'):
                note_data['fields']['source'] = inputs['source']

            relationships = {}
            if inputs.get('customer_email'):
                relationships['customer'] = {
                    "data": {
                        "type": "user",
                        "email": inputs['customer_email']
                    }
                }
            if inputs.get('company_id'):
                relationships['customer'] = {
                    "data": {
                        "type": "company",
                        "id": inputs['company_id']
                    }
                }
            if relationships:
                note_data['relationships'] = relationships

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/notes",
                method="POST",
                headers=get_common_headers(),
                json={"data": note_data}
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": parse_error(response, "Failed to create note")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"note": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"note": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("update_note")
class UpdateNoteAction(ActionHandler):
    """Updates an existing note."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            note_id = inputs['note_id']

            tags_to_add = inputs.get('tags_to_add')
            if tags_to_add and not isinstance(tags_to_add, list):
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": "tags_to_add must be an array"
                    },
                    cost_usd=0.0
                )

            tags_to_remove = inputs.get('tags_to_remove')
            if tags_to_remove and not isinstance(tags_to_remove, list):
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": "tags_to_remove must be an array"
                    },
                    cost_usd=0.0
                )

            patch_operations = []

            if inputs.get('name'):
                patch_operations.append({
                    "op": "set",
                    "field": "name",
                    "value": inputs['name']
                })
            if inputs.get('content'):
                patch_operations.append({
                    "op": "set",
                    "field": "content",
                    "value": inputs['content']
                })
            if inputs.get('owner_email'):
                patch_operations.append({
                    "op": "set",
                    "field": "owner",
                    "value": {"email": inputs['owner_email']}
                })
            if inputs.get('archived') is not None:
                patch_operations.append({
                    "op": "set",
                    "field": "archived",
                    "value": inputs['archived']
                })
            if inputs.get('processed') is not None:
                patch_operations.append({
                    "op": "set",
                    "field": "processed",
                    "value": inputs['processed']
                })
            if tags_to_add:
                patch_operations.append({
                    "op": "addItems",
                    "field": "tags",
                    "value": tags_to_add
                })
            if tags_to_remove:
                patch_operations.append({
                    "op": "removeItems",
                    "field": "tags",
                    "value": tags_to_remove
                })

            if not patch_operations:
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": "No fields provided to update"
                    },
                    cost_usd=0.0
                )

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/notes/{note_id}",
                method="PATCH",
                headers=get_common_headers(),
                json={"data": {"patch": patch_operations}}
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "note": {},
                        "result": False,
                        "error": parse_error(response, "Failed to update note")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"note": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"note": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("get_note_configuration")
class GetNoteConfigurationAction(ActionHandler):
    """Returns metadata for notes including available fields."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/notes/configurations",
                method="GET",
                headers=get_common_headers()
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "configuration": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get configuration")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"configuration": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"configuration": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Analytics Handlers ----

@productboard.action("list_analytics_reports")
class ListAnalyticsReportsAction(ActionHandler):
    """Retrieves available analytics reports."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get('page_cursor'):
                params['pageCursor'] = inputs['page_cursor']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/analytics/reports",
                method="GET",
                headers=get_common_headers(),
                params=params if params else None
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "reports": [],
                        "result": False,
                        "error": parse_error(response, "Failed to list reports")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            next_link = data.get('links', {}).get('next')
            next_cursor = extract_page_cursor(next_link)

            return ActionResult(
                data={
                    "reports": data.get('data', []),
                    "next_cursor": next_cursor,
                    "result": True
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"reports": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@productboard.action("get_analytics_report")
class GetAnalyticsReportAction(ActionHandler):
    """Retrieves details of a specific analytics report."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs['report_id']

            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/{API_VERSION}/analytics/reports/{report_id}",
                method="GET",
                headers=get_common_headers()
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "report": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get report")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"report": data.get('data', {}), "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"report": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- User Handlers ----

@productboard.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Retrieves information about the currently authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{PRODUCTBOARD_API_BASE_URL}/oauth2/token/info",
                method="GET",
                headers=get_common_headers()
            )

            if response.status_code not in SUCCESS_STATUSES:
                return ActionResult(
                    data={
                        "user": {},
                        "result": False,
                        "error": parse_error(response, "Failed to get user info")
                    },
                    cost_usd=0.0
                )

            data = response.json()
            return ActionResult(
                data={"user": data, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )
