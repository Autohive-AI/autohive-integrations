import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(parent_dir)
sys.path.insert(0, parent_dir)

from productboard import (
    ListEntitiesAction,
    GetEntityAction,
    CreateEntityAction,
    UpdateEntityAction,
    GetEntityConfigurationAction,
    ListNotesAction,
    GetNoteAction,
    CreateNoteAction,
    UpdateNoteAction,
    GetNoteConfigurationAction,
    ListAnalyticsReportsAction,
    GetAnalyticsReportAction,
    GetCurrentUserAction,
    extract_page_cursor,
    parse_error,
    build_status_value,
    is_uuid,
)


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.fetch = AsyncMock()
    return context


# ---- Helper Function Tests ----

def test_extract_page_cursor_from_url():
    url = "https://api.productboard.com/v2/notes?pageCursor=abc123"
    assert extract_page_cursor(url) == "abc123"


def test_extract_page_cursor_none():
    assert extract_page_cursor(None) is None
    assert extract_page_cursor("") is None


def test_extract_page_cursor_no_cursor_param():
    url = "https://api.productboard.com/v2/notes?other=value"
    assert extract_page_cursor(url) is None


def test_is_uuid_valid():
    assert is_uuid("a38f981d-52da-47b1-818c-fbaa9ab56e0c") is True
    assert is_uuid("A38F981D-52DA-47B1-818C-FBAA9AB56E0C") is True


def test_is_uuid_invalid():
    assert is_uuid("not-a-uuid") is False
    assert is_uuid("active") is False
    assert is_uuid("") is False


def test_build_status_value_with_name():
    result = build_status_value("In progress")
    assert result == {"name": "In progress"}


def test_build_status_value_with_uuid():
    result = build_status_value("a38f981d-52da-47b1-818c-fbaa9ab56e0c")
    assert result == {"id": "a38f981d-52da-47b1-818c-fbaa9ab56e0c"}


# ---- Entity Tests ----

@pytest.mark.asyncio
async def test_list_entities_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "entity-1", "type": "feature", "fields": {"name": "Feature 1"}},
            {"id": "entity-2", "type": "feature", "fields": {"name": "Feature 2"}}
        ],
        "links": {"next": "https://api.productboard.com/v2/entities?pageCursor=cursor-123"}
    }
    mock_context.fetch.return_value = mock_response

    action = ListEntitiesAction()
    result = await action.execute({"type": "feature"}, mock_context)

    assert result.data["result"] is True
    assert len(result.data["entities"]) == 2
    assert result.data["next_cursor"] == "cursor-123"


@pytest.mark.asyncio
async def test_list_entities_with_filters(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [], "links": {}}
    mock_context.fetch.return_value = mock_response

    action = ListEntitiesAction()
    await action.execute({
        "type": "product",
        "archived": False,
        "fields": "name,status"
    }, mock_context)

    mock_context.fetch.assert_called_once()
    call_args = mock_context.fetch.call_args
    assert call_args[1]["params"]["type"] == "product"
    assert call_args[1]["params"]["archived"] == "false"
    assert call_args[1]["params"]["fields"] == "name,status"


@pytest.mark.asyncio
async def test_list_entities_api_error(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errors": [{"detail": "Invalid or expired token"}]
    }
    mock_context.fetch.return_value = mock_response

    action = ListEntitiesAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is False
    assert "Invalid or expired token" in result.data["error"]


@pytest.mark.asyncio
async def test_get_entity_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "id": "entity-123",
            "type": "feature",
            "fields": {"name": "Test Feature", "status": "active"}
        }
    }
    mock_context.fetch.return_value = mock_response

    action = GetEntityAction()
    result = await action.execute({"entity_id": "entity-123"}, mock_context)

    assert result.data["result"] is True
    assert result.data["entity"]["id"] == "entity-123"


@pytest.mark.asyncio
async def test_get_entity_not_found(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {
        "errors": [{"detail": "Resource not found by ID"}]
    }
    mock_context.fetch.return_value = mock_response

    action = GetEntityAction()
    result = await action.execute({"entity_id": "invalid-id"}, mock_context)

    assert result.data["result"] is False
    assert "not found" in result.data["error"]


@pytest.mark.asyncio
async def test_create_entity_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "data": {
            "id": "new-entity-123",
            "type": "feature",
            "links": {"self": "/v2/entities/new-entity-123"}
        }
    }
    mock_context.fetch.return_value = mock_response

    action = CreateEntityAction()
    result = await action.execute({
        "type": "feature",
        "name": "New Feature",
        "description": "Feature description"
    }, mock_context)

    assert result.data["result"] is True
    assert result.data["entity"]["id"] == "new-entity-123"


@pytest.mark.asyncio
async def test_create_entity_with_parent(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"data": {"id": "entity-123"}}
    mock_context.fetch.return_value = mock_response

    action = CreateEntityAction()
    await action.execute({
        "type": "feature",
        "name": "Child Feature",
        "parent_id": "parent-123"
    }, mock_context)

    call_args = mock_context.fetch.call_args
    json_data = call_args[1]["json"]["data"]
    assert json_data["relationships"]["parent"]["data"]["id"] == "parent-123"


@pytest.mark.asyncio
async def test_create_entity_with_status(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"data": {"id": "entity-123"}}
    mock_context.fetch.return_value = mock_response

    action = CreateEntityAction()
    await action.execute({
        "type": "feature",
        "name": "Feature",
        "status": "In progress"
    }, mock_context)

    call_args = mock_context.fetch.call_args
    json_data = call_args[1]["json"]["data"]
    assert json_data["fields"]["status"] == {"name": "In progress"}


@pytest.mark.asyncio
async def test_create_entity_invalid_custom_fields(mock_context):
    action = CreateEntityAction()
    result = await action.execute({
        "type": "feature",
        "name": "Feature",
        "custom_fields": "not-an-object"
    }, mock_context)

    assert result.data["result"] is False
    assert "custom_fields must be an object" in result.data["error"]


@pytest.mark.asyncio
async def test_update_entity_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"id": "entity-123"}
    }
    mock_context.fetch.return_value = mock_response

    action = UpdateEntityAction()
    result = await action.execute({
        "entity_id": "entity-123",
        "name": "Updated Name",
        "status": "completed"
    }, mock_context)

    assert result.data["result"] is True
    call_args = mock_context.fetch.call_args
    assert call_args[1]["method"] == "PATCH"

    patch_ops = call_args[1]["json"]["data"]["patch"]
    status_op = next((op for op in patch_ops if op["field"] == "status"), None)
    assert status_op is not None
    assert status_op["value"] == {"name": "completed"}


@pytest.mark.asyncio
async def test_update_entity_empty_patch(mock_context):
    action = UpdateEntityAction()
    result = await action.execute({
        "entity_id": "entity-123"
    }, mock_context)

    assert result.data["result"] is False
    assert "No fields provided to update" in result.data["error"]


@pytest.mark.asyncio
async def test_get_entity_configuration_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "type": "feature",
            "fields": [
                {"id": "name", "type": "string", "required": True},
                {"id": "status", "type": "enum", "required": False}
            ]
        }
    }
    mock_context.fetch.return_value = mock_response

    action = GetEntityConfigurationAction()
    result = await action.execute({"type": "feature"}, mock_context)

    assert result.data["result"] is True
    assert result.data["configuration"]["type"] == "feature"


# ---- Note Tests ----

@pytest.mark.asyncio
async def test_list_notes_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "note-1", "type": "simple", "fields": {"name": "Note 1"}},
            {"id": "note-2", "type": "conversation", "fields": {"name": "Note 2"}}
        ],
        "links": {"next": None}
    }
    mock_context.fetch.return_value = mock_response

    action = ListNotesAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is True
    assert len(result.data["notes"]) == 2


@pytest.mark.asyncio
async def test_list_notes_with_filters(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [], "links": {}}
    mock_context.fetch.return_value = mock_response

    action = ListNotesAction()
    await action.execute({
        "archived": False,
        "processed": True,
        "owner_email": "user@example.com",
        "created_from": "2024-01-01T00:00:00Z"
    }, mock_context)

    call_args = mock_context.fetch.call_args
    params = call_args[1]["params"]
    assert params["archived"] == "false"
    assert params["processed"] == "true"
    assert params["owner[email]"] == "user@example.com"
    assert params["createdFrom"] == "2024-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_get_note_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "id": "note-123",
            "type": "simple",
            "fields": {"name": "Test Note", "content": "Note content"}
        }
    }
    mock_context.fetch.return_value = mock_response

    action = GetNoteAction()
    result = await action.execute({"note_id": "note-123"}, mock_context)

    assert result.data["result"] is True
    assert result.data["note"]["id"] == "note-123"


@pytest.mark.asyncio
async def test_create_simple_note_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "data": {
            "id": "new-note-123",
            "type": "simple",
            "links": {"self": "/v2/notes/new-note-123"}
        }
    }
    mock_context.fetch.return_value = mock_response

    action = CreateNoteAction()
    result = await action.execute({
        "type": "simple",
        "name": "Customer Feedback",
        "content": "User requested dark mode",
        "tags": ["feedback", "ui"]
    }, mock_context)

    assert result.data["result"] is True
    assert result.data["note"]["id"] == "new-note-123"


@pytest.mark.asyncio
async def test_create_conversation_note_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"data": {"id": "conv-123", "type": "conversation"}}
    mock_context.fetch.return_value = mock_response

    action = CreateNoteAction()
    result = await action.execute({
        "type": "conversation",
        "name": "Support Chat",
        "messages": [
            {"role": "user", "text": "I need help"},
            {"role": "agent", "text": "How can I help?"}
        ]
    }, mock_context)

    assert result.data["result"] is True


@pytest.mark.asyncio
async def test_create_note_invalid_tags(mock_context):
    action = CreateNoteAction()
    result = await action.execute({
        "type": "simple",
        "name": "Note",
        "tags": "not-an-array"
    }, mock_context)

    assert result.data["result"] is False
    assert "tags must be an array" in result.data["error"]


@pytest.mark.asyncio
async def test_create_note_invalid_messages(mock_context):
    action = CreateNoteAction()
    result = await action.execute({
        "type": "conversation",
        "name": "Note",
        "messages": "not-an-array"
    }, mock_context)

    assert result.data["result"] is False
    assert "messages must be an array" in result.data["error"]


@pytest.mark.asyncio
async def test_update_note_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"id": "note-123"}}
    mock_context.fetch.return_value = mock_response

    action = UpdateNoteAction()
    result = await action.execute({
        "note_id": "note-123",
        "processed": True,
        "tags_to_add": ["reviewed"]
    }, mock_context)

    assert result.data["result"] is True


@pytest.mark.asyncio
async def test_update_note_with_tags(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"id": "note-123"}}
    mock_context.fetch.return_value = mock_response

    action = UpdateNoteAction()
    await action.execute({
        "note_id": "note-123",
        "tags_to_add": ["important"],
        "tags_to_remove": ["pending"]
    }, mock_context)

    call_args = mock_context.fetch.call_args
    patch_data = call_args[1]["json"]["data"]["patch"]

    add_op = next((op for op in patch_data if op["op"] == "addItems"), None)
    remove_op = next((op for op in patch_data if op["op"] == "removeItems"), None)

    assert add_op is not None
    assert add_op["field"] == "tags"
    assert remove_op is not None
    assert remove_op["field"] == "tags"


@pytest.mark.asyncio
async def test_update_note_empty_patch(mock_context):
    action = UpdateNoteAction()
    result = await action.execute({
        "note_id": "note-123"
    }, mock_context)

    assert result.data["result"] is False
    assert "No fields provided to update" in result.data["error"]


@pytest.mark.asyncio
async def test_update_note_invalid_tags_to_add(mock_context):
    action = UpdateNoteAction()
    result = await action.execute({
        "note_id": "note-123",
        "tags_to_add": "not-an-array"
    }, mock_context)

    assert result.data["result"] is False
    assert "tags_to_add must be an array" in result.data["error"]


@pytest.mark.asyncio
async def test_get_note_configuration_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "types": ["simple", "conversation"],
            "fields": [
                {"id": "name", "type": "string", "required": True},
                {"id": "content", "type": "string", "required": False}
            ]
        }
    }
    mock_context.fetch.return_value = mock_response

    action = GetNoteConfigurationAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is True
    assert "types" in result.data["configuration"]


# ---- Analytics Tests ----

@pytest.mark.asyncio
async def test_list_analytics_reports_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "report-1", "name": "Feature Views"},
            {"id": "report-2", "name": "User Activity"}
        ],
        "links": {}
    }
    mock_context.fetch.return_value = mock_response

    action = ListAnalyticsReportsAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is True
    assert len(result.data["reports"]) == 2


@pytest.mark.asyncio
async def test_get_analytics_report_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "id": "report-123",
            "name": "Feature Views",
            "metrics": {"total_views": 1500}
        }
    }
    mock_context.fetch.return_value = mock_response

    action = GetAnalyticsReportAction()
    result = await action.execute({"report_id": "report-123"}, mock_context)

    assert result.data["result"] is True
    assert result.data["report"]["id"] == "report-123"


# ---- User Tests ----

@pytest.mark.asyncio
async def test_get_current_user_success(mock_context):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "user": {
            "id": "user-123",
            "email": "user@example.com",
            "name": "Test User"
        },
        "workspace": {"id": "ws-123", "name": "My Workspace"}
    }
    mock_context.fetch.return_value = mock_response

    action = GetCurrentUserAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is True
    assert "user" in result.data["user"]


# ---- Exception Handling Tests ----

@pytest.mark.asyncio
async def test_list_entities_exception(mock_context):
    mock_context.fetch.side_effect = Exception("Network error")

    action = ListEntitiesAction()
    result = await action.execute({}, mock_context)

    assert result.data["result"] is False
    assert "Network error" in result.data["error"]


@pytest.mark.asyncio
async def test_create_note_exception(mock_context):
    mock_context.fetch.side_effect = Exception("Connection timeout")

    action = CreateNoteAction()
    result = await action.execute({
        "type": "simple",
        "name": "Test"
    }, mock_context)

    assert result.data["result"] is False
    assert "Connection timeout" in result.data["error"]
