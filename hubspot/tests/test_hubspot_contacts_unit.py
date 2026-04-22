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


# ---- GetContact ----


class TestGetContact:
    @pytest.mark.asyncio
    async def test_contact_found(self, mock_context):
        contact_data = {
            "id": "123",
            "properties": {
                "email": "test@example.com",
                "firstname": "John",
                "lastname": "Doe",
            },
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [contact_data]})

        result = await hubspot.execute_action("get_contact", {"email": "test@example.com"}, mock_context)

        assert result.result.data["contact"] == contact_data
        mock_context.fetch.assert_called_once()
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/contacts/search"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_contact_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await hubspot.execute_action("get_contact", {"email": "nobody@example.com"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Contact not found" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"id": "1", "properties": {}}]}
        )

        await hubspot.execute_action("get_contact", {"email": "a@b.com"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/contacts/search"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"id": "1", "properties": {}}]}
        )

        await hubspot.execute_action("get_contact", {"email": "test@example.com"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert len(payload["filterGroups"]) == 1
        filters = payload["filterGroups"][0]["filters"]
        assert len(filters) == 1
        assert filters[0]["propertyName"] == "email"
        assert filters[0]["operator"] == "EQ"
        assert filters[0]["value"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_custom_properties_in_request(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"id": "1", "properties": {}}]}
        )

        await hubspot.execute_action(
            "get_contact",
            {"email": "a@b.com", "properties": ["email", "website"]},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"] == ["email", "website"]

    @pytest.mark.asyncio
    async def test_default_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"results": [{"id": "1", "properties": {}}]}
        )

        await hubspot.execute_action("get_contact", {"email": "a@b.com"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"] == ["email", "firstname", "lastname", "phone", "company", "jobtitle"]


# ---- GetContactNotes ----


class TestGetContactNotes:
    @pytest.mark.asyncio
    async def test_notes_returned_with_timestamps(self, mock_context):
        notes_data = {
            "results": [
                {
                    "id": "note-1",
                    "properties": {
                        "hs_note_body": "Called the client",
                        "hs_timestamp": "2025-03-15T10:30:00.000Z",
                        "hs_createdate": "2025-03-15T10:30:00.000Z",
                        "hs_lastmodifieddate": None,
                    },
                }
            ]
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=notes_data)

        result = await hubspot.execute_action("get_contact_notes", {"contact_id": "123"}, mock_context)

        data = result.result.data
        assert data["contact_id"] == "123"
        assert data["total"] == 1
        assert len(data["notes"]) == 1
        # Timestamps should be converted to UTC strings
        props = data["notes"][0]["properties"]
        assert "UTC" in props["hs_timestamp"]
        assert "UTC" in props["hs_createdate"]

    @pytest.mark.asyncio
    async def test_empty_notes(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await hubspot.execute_action("get_contact_notes", {"contact_id": "999"}, mock_context)

        data = result.result.data
        assert data["notes"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API timeout")

        result = await hubspot.execute_action("get_contact_notes", {"contact_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve notes" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_contact_notes", {"contact_id": "123"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/notes/search"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_custom_limit_passed_to_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_contact_notes", {"contact_id": "123", "limit": 50}, mock_context)

        mock_context.fetch.assert_called_once()
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 50

    @pytest.mark.asyncio
    async def test_default_limit_is_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_contact_notes", {"contact_id": "123"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 100

    @pytest.mark.asyncio
    async def test_custom_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action(
            "get_contact_notes",
            {"contact_id": "123", "properties": ["hs_note_body", "hs_timestamp"]},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["properties"] == ["hs_note_body", "hs_timestamp"]

    @pytest.mark.asyncio
    async def test_sort_order(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_contact_notes", {"contact_id": "123"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["sorts"] == [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}]


# ---- GetContactEmails ----


class TestGetContactEmails:
    @pytest.mark.asyncio
    async def test_happy_path_with_emails(self, mock_context):
        associations_data = {
            "results": [
                {"toObjectId": "email-1"},
                {"toObjectId": "email-2"},
            ]
        }
        email_1 = {
            "id": "email-1",
            "properties": {
                "hs_email_subject": "Hello",
                "hs_timestamp": "2025-04-01T12:00:00.000Z",
                "hs_email_direction": "OUTBOUND",
            },
        }
        email_2 = {
            "id": "email-2",
            "properties": {
                "hs_email_subject": "Follow-up",
                "hs_timestamp": "2025-04-02T08:00:00.000Z",
                "hs_email_direction": "INBOUND",
            },
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=associations_data),
            FetchResponse(status=200, headers={}, data=email_1),
            FetchResponse(status=200, headers={}, data=email_2),
        ]

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        data = result.result.data
        assert data["contact_id"] == "123"
        assert data["email_summary"]["total_emails_retrieved"] == 2
        # Should be sorted most recent first
        assert data["recent_emails"][0]["id"] == "email-2"

    @pytest.mark.asyncio
    async def test_empty_associations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        data = result.result.data
        assert data["recent_emails"] == []
        assert data["email_summary"]["total_emails_retrieved"] == 0

    @pytest.mark.asyncio
    async def test_email_fetch_failure_skipped(self, mock_context):
        associations_data = {
            "results": [
                {"toObjectId": "email-ok"},
                {"toObjectId": "email-fail"},
            ]
        }
        email_ok = {
            "id": "email-ok",
            "properties": {
                "hs_email_subject": "Good email",
                "hs_timestamp": "2025-04-01T12:00:00.000Z",
            },
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=associations_data),
            FetchResponse(status=200, headers={}, data=email_ok),
            Exception("Email not found"),
        ]

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        data = result.result.data
        assert data["email_summary"]["total_emails_retrieved"] == 1

    @pytest.mark.asyncio
    async def test_email_limit_respected(self, mock_context):
        associations_data = {
            "results": [
                {"toObjectId": "email-1"},
                {"toObjectId": "email-2"},
                {"toObjectId": "email-3"},
            ]
        }
        email_1 = {
            "id": "email-1",
            "properties": {"hs_email_subject": "E1", "hs_timestamp": "2025-04-01T12:00:00.000Z"},
        }
        email_2 = {
            "id": "email-2",
            "properties": {"hs_email_subject": "E2", "hs_timestamp": "2025-04-02T12:00:00.000Z"},
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=associations_data),
            FetchResponse(status=200, headers={}, data=email_1),
            FetchResponse(status=200, headers={}, data=email_2),
        ]

        result = await hubspot.execute_action(
            "get_contact_emails", {"contact_id": "123", "email_limit": 2}, mock_context
        )

        data = result.result.data
        assert data["email_summary"]["total_emails_retrieved"] == 2
        # Third email should NOT have been fetched
        assert mock_context.fetch.call_count == 3  # 1 associations + 2 emails

    @pytest.mark.asyncio
    async def test_timestamp_conversion(self, mock_context):
        associations_data = {"results": [{"toObjectId": "email-1"}]}
        email_1 = {
            "id": "email-1",
            "properties": {"hs_email_subject": "Hi", "hs_timestamp": "2025-04-01T12:00:00.000Z"},
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=associations_data),
            FetchResponse(status=200, headers={}, data=email_1),
        ]

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        ts = result.result.data["recent_emails"][0]["properties"]["hs_timestamp"]
        assert "UTC" in ts

    @pytest.mark.asyncio
    async def test_emails_sorted_by_timestamp(self, mock_context):
        associations_data = {"results": [{"toObjectId": "email-old"}, {"toObjectId": "email-new"}]}
        email_old = {
            "id": "email-old",
            "properties": {"hs_email_subject": "Old", "hs_timestamp": "2025-03-01T12:00:00.000Z"},
        }
        email_new = {
            "id": "email-new",
            "properties": {"hs_email_subject": "New", "hs_timestamp": "2025-04-15T12:00:00.000Z"},
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=associations_data),
            FetchResponse(status=200, headers={}, data=email_old),
            FetchResponse(status=200, headers={}, data=email_new),
        ]

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        emails = result.result.data["recent_emails"]
        assert emails[0]["id"] == "email-new"
        assert emails[1]["id"] == "email-old"


# ---- CreateContact ----


class TestCreateContact:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        created = {"id": "501", "properties": {"email": "new@example.com"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=created)

        result = await hubspot.execute_action(
            "create_contact",
            {"properties": {"email": "new@example.com", "firstname": "Jane"}},
            mock_context,
        )

        data = result.result.data
        assert data["contact"]["id"] == "501"
        mock_context.fetch.assert_called_once()
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/contacts/v1/contact"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_additional_properties_merge(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "502"})

        result = await hubspot.execute_action(
            "create_contact",
            {
                "properties": {"email": "merge@example.com"},
                "additional_properties": {"company": "Acme"},
            },
            mock_context,
        )

        data = result.result.data
        assert data["created_properties"]["email"] == "merge@example.com"
        assert data["created_properties"]["company"] == "Acme"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "503"})

        await hubspot.execute_action(
            "create_contact",
            {"properties": {"email": "new@example.com"}},
            mock_context,
        )

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/contacts/v1/contact"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "504"})

        await hubspot.execute_action(
            "create_contact",
            {"properties": {"email": "payload@example.com", "firstname": "Test"}},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in payload
        assert payload["properties"]["email"] == "payload@example.com"
        assert payload["properties"]["firstname"] == "Test"


# ---- UpdateContact ----


class TestUpdateContact:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        updated = {"id": "123", "properties": {"firstname": "Updated"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await hubspot.execute_action(
            "update_contact",
            {"contact_id": "123", "properties": {"firstname": "Updated"}},
            mock_context,
        )

        data = result.result.data
        assert data["contact"]["id"] == "123"
        mock_context.fetch.assert_called_once()
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/contacts/123"
        assert call_kwargs.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_additional_properties_merge(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "123"})

        result = await hubspot.execute_action(
            "update_contact",
            {
                "contact_id": "123",
                "properties": {"firstname": "Jane"},
                "additional_properties": {"phone": "555-1234"},
            },
            mock_context,
        )

        data = result.result.data
        assert data["updated_properties"]["firstname"] == "Jane"
        assert data["updated_properties"]["phone"] == "555-1234"

    @pytest.mark.asyncio
    async def test_request_url_contains_contact_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "789"})

        await hubspot.execute_action(
            "update_contact",
            {"contact_id": "789", "properties": {"firstname": "Test"}},
            mock_context,
        )

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.hubapi.com/crm/v3/objects/contacts/789"

    @pytest.mark.asyncio
    async def test_request_method_is_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "789"})

        await hubspot.execute_action(
            "update_contact",
            {"contact_id": "789", "properties": {"firstname": "Test"}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"


# ---- SearchContacts ----


class TestSearchContacts:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_context):
        search_results = {
            "total": 1,
            "results": [{"id": "100", "properties": {"email": "found@example.com"}}],
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=search_results)

        result = await hubspot.execute_action("search_contacts", {"query": "found@example.com"}, mock_context)

        data = result.result.data
        assert data["total"] == 1
        assert len(data["results"]) == 1
        mock_context.fetch.assert_called_once()
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "found@example.com"

    @pytest.mark.asyncio
    async def test_with_after_pagination(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"total": 0, "results": []})

        await hubspot.execute_action(
            "search_contacts",
            {"query": "test", "after": "next-cursor-abc"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["after"] == "next-cursor-abc"

    @pytest.mark.asyncio
    async def test_request_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"total": 0, "results": []})

        await hubspot.execute_action("search_contacts", {"query": "test@co.com", "limit": 50}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "test@co.com"
        assert payload["limit"] == 50

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"total": 0, "results": []})

        await hubspot.execute_action("search_contacts", {"query": "anything"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["limit"] == 100


# ---- AddContactToList ----


class TestAddContactToList:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        api_result = {"recordIdsAdded": ["456"], "recordIdsDisallowed": []}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=api_result)

        result = await hubspot.execute_action(
            "add_contact_to_list",
            {"list_id": "10", "contact_id": "456"},
            mock_context,
        )

        data = result.result.data
        assert data["result"]["recordIdsAdded"] == ["456"]
        mock_context.fetch.assert_called_once()
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/lists/10/memberships/add"
        assert call_kwargs.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"recordIdsAdded": ["99"], "recordIdsDisallowed": []}
        )

        await hubspot.execute_action("add_contact_to_list", {"list_id": "42", "contact_id": "99"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/lists/42/memberships/add"
        assert call_kwargs.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_payload_contains_record_ids(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"recordIdsAdded": ["77"], "recordIdsDisallowed": []}
        )

        await hubspot.execute_action("add_contact_to_list", {"list_id": "5", "contact_id": "77"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["recordIds"] == ["77"]


# ---- GetRecentContacts ----


class TestGetRecentContacts:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        contacts = {
            "results": [
                {"id": "1", "properties": {"email": "a@example.com"}},
                {"id": "2", "properties": {"email": "b@example.com"}},
            ]
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=contacts)

        result = await hubspot.execute_action("get_recent_contacts", {"limit": 10}, mock_context)

        data = result.result.data
        assert len(data["recent_contacts"]["results"]) == 2
        mock_context.fetch.assert_called_once()
        url = mock_context.fetch.call_args.args[0]
        assert "limit=10" in url
        assert "sort=createdat" in url

    @pytest.mark.asyncio
    async def test_request_url_with_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_contacts", {"limit": 25}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "limit=25" in url
        assert "sort=createdat" in url

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_contacts", {}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "limit=100" in url
