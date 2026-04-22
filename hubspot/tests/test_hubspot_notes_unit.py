import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("hubspot_mod", os.path.join(_parent, "hubspot.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

hubspot = _mod.hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


NOTES_API_URL = "https://api.hubapi.com/crm/v3/objects/notes"

SAMPLE_NOTE_RESPONSE = {
    "id": "12345",
    "properties": {
        "hs_note_body": "Test note content",
        "hs_timestamp": "1700000000000",
        "hs_createdate": "2025-01-15T10:00:00.000Z",
    },
}


# ---- Create Note ----


class TestCreateNote:
    @pytest.mark.asyncio
    async def test_create_note_with_contact_association(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action(
            "create_note",
            {"note_body": "Follow up with client", "contact_id": "501"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["note"] == SAMPLE_NOTE_RESPONSE

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == NOTES_API_URL
        assert call_kwargs.kwargs["method"] == "POST"

        payload = call_kwargs.kwargs["json"]
        assert payload["properties"]["hs_note_body"] == "Follow up with client"
        assert len(payload["associations"]) == 1
        assoc = payload["associations"][0]
        assert assoc["to"]["id"] == "501"
        assert assoc["types"][0]["associationTypeId"] == 202

    @pytest.mark.asyncio
    async def test_create_note_multiple_associations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action(
            "create_note",
            {
                "note_body": "Multi-assoc note",
                "contact_id": "100",
                "company_id": "200",
                "deal_id": "300",
            },
            mock_context,
        )

        assert result.result.data["success"] is True

        payload = mock_context.fetch.call_args.kwargs["json"]
        associations = payload["associations"]
        assert len(associations) == 3

        type_ids = [a["types"][0]["associationTypeId"] for a in associations]
        assert type_ids == [202, 190, 214]

        to_ids = [a["to"]["id"] for a in associations]
        assert to_ids == ["100", "200", "300"]

    @pytest.mark.asyncio
    async def test_create_note_with_custom_timestamp(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action(
            "create_note",
            {"note_body": "Timestamped note", "contact_id": "501", "timestamp": 1700000000000},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"]["hs_timestamp"] == "1700000000000"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("create_note", {"note_body": "test", "contact_id": "1"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == NOTES_API_URL
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("create_note", {"note_body": "My note body", "contact_id": "1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "hs_note_body" in payload["properties"]
        assert payload["properties"]["hs_note_body"] == "My note body"

    @pytest.mark.asyncio
    async def test_company_association_type_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("create_note", {"note_body": "note", "company_id": "200"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assoc = payload["associations"][0]
        assert assoc["to"]["id"] == "200"
        assert assoc["types"][0]["associationTypeId"] == 190

    @pytest.mark.asyncio
    async def test_deal_association_type_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("create_note", {"note_body": "note", "deal_id": "300"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assoc = payload["associations"][0]
        assert assoc["to"]["id"] == "300"
        assert assoc["types"][0]["associationTypeId"] == 214

    @pytest.mark.asyncio
    async def test_no_associations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("create_note", {"note_body": "orphan note"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["associations"] == []

    @pytest.mark.asyncio
    async def test_response_success_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action("create_note", {"note_body": "note"}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_response_contains_message(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action("create_note", {"note_body": "note"}, mock_context)

        assert result.result.data["message"] == "Note created successfully"

    @pytest.mark.asyncio
    async def test_create_note_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await hubspot.execute_action(
            "create_note",
            {"note_body": "Will fail", "contact_id": "501"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to create note" in result.result.message


# ---- Update Note ----


class TestUpdateNote:
    @pytest.mark.asyncio
    async def test_update_note_body(self, mock_context):
        updated_response = {
            "id": "12345",
            "properties": {"hs_note_body": "Updated content"},
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated_response)

        result = await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "note_body": "Updated content"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["note"] == updated_response

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == f"{NOTES_API_URL}/12345"
        assert call_kwargs.kwargs["method"] == "PATCH"
        assert call_kwargs.kwargs["json"]["properties"]["hs_note_body"] == "Updated content"

    @pytest.mark.asyncio
    async def test_update_note_timestamp(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "timestamp": 1700000000000},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"]["hs_timestamp"] == "1700000000000"

    @pytest.mark.asyncio
    async def test_update_note_additional_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action(
            "update_note",
            {
                "note_id": "12345",
                "note_body": "Body",
                "additional_properties": {"hs_attachment_ids": "999"},
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"]["hs_note_body"] == "Body"
        assert payload["properties"]["hs_attachment_ids"] == "999"
        assert result.result.data["updated_properties"]["hs_attachment_ids"] == "999"

    @pytest.mark.asyncio
    async def test_request_url_contains_note_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("update_note", {"note_id": "67890", "note_body": "text"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{NOTES_API_URL}/67890"

    @pytest.mark.asyncio
    async def test_request_method_is_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action("update_note", {"note_id": "12345", "note_body": "text"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_payload_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "note_body": "New body", "timestamp": 1700000000000},
            mock_context,
        )

        props = mock_context.fetch.call_args.kwargs["json"]["properties"]
        assert props["hs_note_body"] == "New body"
        assert props["hs_timestamp"] == "1700000000000"

    @pytest.mark.asyncio
    async def test_response_includes_updated_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "note_body": "Changed"},
            mock_context,
        )

        assert "updated_properties" in result.result.data
        assert result.result.data["updated_properties"]["hs_note_body"] == "Changed"

    @pytest.mark.asyncio
    async def test_response_success_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_NOTE_RESPONSE)

        result = await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "note_body": "text"},
            mock_context,
        )

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_update_note_no_properties_returns_action_error(self, mock_context):
        result = await hubspot.execute_action(
            "update_note",
            {"note_id": "12345"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "No properties provided to update"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_note_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action(
            "update_note",
            {"note_id": "12345", "note_body": "Will fail"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to update note" in result.result.message


# ---- Delete Note ----


class TestDeleteNote:
    @pytest.mark.asyncio
    async def test_delete_note_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await hubspot.execute_action(
            "delete_note",
            {"note_id": "12345"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["note_id"] == "12345"

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == f"{NOTES_API_URL}/12345"
        assert call_kwargs.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_request_url_contains_note_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await hubspot.execute_action("delete_note", {"note_id": "55555"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{NOTES_API_URL}/55555"

    @pytest.mark.asyncio
    async def test_request_method_is_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await hubspot.execute_action("delete_note", {"note_id": "12345"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_response_contains_note_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await hubspot.execute_action("delete_note", {"note_id": "77777"}, mock_context)

        assert result.result.data["note_id"] == "77777"

    @pytest.mark.asyncio
    async def test_response_message(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await hubspot.execute_action("delete_note", {"note_id": "12345"}, mock_context)

        assert "deleted successfully" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_delete_note_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action(
            "delete_note",
            {"note_id": "99999"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to delete note" in result.result.message
