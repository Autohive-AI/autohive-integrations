import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

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
    async def test_retries_rate_limit_and_returns_contact(self, mock_context, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", sleep_mock)
        contact_data = {"id": "123", "properties": {"email": "test@example.com"}}
        mock_context.fetch.side_effect = [
            RateLimitError(1, 429, "Rate limit exceeded"),
            FetchResponse(status=200, headers={}, data={"results": [contact_data]}),
        ]

        result = await hubspot.execute_action("get_contact", {"email": "test@example.com"}, mock_context)

        assert result.result.data["contact"] == contact_data
        assert mock_context.fetch.call_count == 2
        sleep_mock.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_rate_limit_exhaustion_surfaces_error(self, mock_context, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", sleep_mock)
        mock_context.fetch.side_effect = RateLimitError(1, 429, "Rate limit exceeded")

        with pytest.raises(HTTPError, match="HTTP 429"):
            await hubspot.execute_action("get_contact", {"email": "test@example.com"}, mock_context)

        assert mock_context.fetch.call_count == 4
        assert sleep_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_contact_read_by_id(self, mock_context):
        contact_data = {"id": "123", "properties": {"email": "test@example.com", "jobtitle": "CTO"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=contact_data)

        result = await hubspot.execute_action(
            "get_contact",
            {"contact_id": "123", "email": "other@example.com", "properties": ["email", "jobtitle"]},
            mock_context,
        )

        assert result.result.data["contact"] == contact_data
        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.hubapi.com/crm/objects/2026-09/contacts/123"
        assert call.kwargs["params"] == {"properties": "email,jobtitle"}

    @pytest.mark.asyncio
    async def test_unknown_contact_id_not_found(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action("get_contact", {"contact_id": "999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Contact not found"

    @pytest.mark.asyncio
    async def test_contact_id_or_email_required(self, mock_context):
        result = await hubspot.execute_action("get_contact", {"properties": ["email"]}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Give contact_id or email"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_contact_id_cannot_change_the_path(self, mock_context):
        result = await hubspot.execute_action("get_contact", {"contact_id": "1/../../owners"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

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
        assert payload["properties"] == [
            "email",
            "firstname",
            "lastname",
            "phone",
            "company",
            "jobtitle",
        ]


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


EMAILS_SEARCH_URL = "https://api.hubapi.com/crm/objects/2026-09/emails/search"


def emails_found(*emails):
    return FetchResponse(status=200, headers={}, data={"total": len(emails), "results": list(emails)})


def email(email_id, timestamp):
    return {"id": email_id, "properties": {"hs_email_subject": email_id, "hs_timestamp": timestamp}}


class TestGetContactEmails:
    @pytest.mark.asyncio
    async def test_searches_newest_emails_on_the_contact(self, mock_context):
        mock_context.fetch.return_value = emails_found(email("new", "2025-04-15T12:00:00.000Z"))

        await hubspot.execute_action("get_contact_emails", {"contact_id": "123", "email_limit": 3}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == EMAILS_SEARCH_URL
        body = call.kwargs["json"]
        assert body["filterGroups"] == [
            {"filters": [{"propertyName": "associations.contact", "operator": "EQ", "value": "123"}]}
        ]
        # HubSpot sorts by the real timestamp, so the newest come back first across every email on the contact
        assert body["sorts"] == [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}]
        assert body["limit"] == 3
        assert "hs_email_subject" in body["properties"]

    @pytest.mark.asyncio
    async def test_default_limit_is_5(self, mock_context):
        mock_context.fetch.return_value = emails_found()

        await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"]["limit"] == 5

    @pytest.mark.asyncio
    async def test_emails_returned_in_hubspot_order(self, mock_context):
        mock_context.fetch.return_value = emails_found(
            email("new", "2025-04-15T12:00:00.000Z"), email("old", "2025-03-30T12:00:00.000Z")
        )

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        data = result.result.data
        assert [e["id"] for e in data["recent_emails"]] == ["new", "old"]
        assert data["email_summary"] == {"total_emails_retrieved": 2, "email_limit_applied": 5}

    @pytest.mark.asyncio
    async def test_timestamp_conversion(self, mock_context):
        mock_context.fetch.return_value = emails_found(email("1", "2025-04-01T12:00:00.000Z"))

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        assert result.result.data["recent_emails"][0]["properties"]["hs_timestamp"] == "01 Apr 2025 12:00 PM UTC"

    @pytest.mark.asyncio
    async def test_no_emails(self, mock_context):
        mock_context.fetch.return_value = emails_found()

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        assert result.result.data["recent_emails"] == []

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Missing scopes")

        result = await hubspot.execute_action("get_contact_emails", {"contact_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to retrieve emails: HTTP 403: Missing scopes"


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
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/contacts"
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
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/contacts"
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
    def test_config_requests_list_write_scope(self):
        config_path = Path(__file__).parents[1] / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        assert "crm.lists.write" in config["auth"]["scopes"]

    def test_config_allows_hubspot_to_omit_empty_result_arrays(self):
        config_path = Path(__file__).parents[1] / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        result_schema = config["actions"]["add_contact_to_list"]["output_schema"]["properties"]["result"]

        assert "required" not in result_schema

    @pytest.mark.asyncio
    async def test_accepts_success_response_with_omitted_empty_arrays(self, mock_context):
        api_result = {"recordsIdsAdded": ["456"]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=api_result)

        result = await hubspot.execute_action(
            "add_contact_to_list",
            {"list_id": "10", "contact_id": "456"},
            mock_context,
        )

        data = result.result.data
        assert data["result"]["recordsIdsAdded"] == ["456"]
        mock_context.fetch.assert_called_once()
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/lists/10/memberships/add"
        assert call_kwargs.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"recordsIdsAdded": ["99"], "recordIdsMissing": [], "recordIdsRemoved": []},
        )

        await hubspot.execute_action("add_contact_to_list", {"list_id": "42", "contact_id": "99"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/lists/42/memberships/add"
        assert call_kwargs.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_payload_is_record_id_array(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"recordsIdsAdded": ["77"], "recordIdsMissing": [], "recordIdsRemoved": []},
        )

        await hubspot.execute_action("add_contact_to_list", {"list_id": "5", "contact_id": "77"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload == ["77"]


# ---- RemoveContactFromList ----


class TestRemoveContactFromList:
    def test_config_requests_list_write_scope(self):
        config_path = Path(__file__).parents[1] / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        assert "crm.lists.write" in config["auth"]["scopes"]

    def test_config_allows_hubspot_to_omit_empty_result_arrays(self):
        config_path = Path(__file__).parents[1] / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        result_schema = config["actions"]["remove_contact_from_list"]["output_schema"]["properties"]["result"]

        assert "required" not in result_schema

    @pytest.mark.asyncio
    async def test_accepts_success_response_with_omitted_empty_arrays(self, mock_context):
        api_result = {"recordIdsRemoved": ["456"]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=api_result)

        result = await hubspot.execute_action(
            "remove_contact_from_list",
            {"list_id": "10", "contact_id": "456"},
            mock_context,
        )

        assert result.result.data["result"] == api_result

    @pytest.mark.asyncio
    async def test_request_matches_hubspot_lists_api(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"recordIdsRemoved": ["99"], "recordIdsMissing": []},
        )

        await hubspot.execute_action("remove_contact_from_list", {"list_id": "42", "contact_id": "99"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/lists/2026-03/42/memberships/remove"
        assert call_kwargs.kwargs["method"] == "PUT"
        assert call_kwargs.kwargs["json"] == ["99"]
        assert call_kwargs.kwargs["headers"] == {"Content-Type": "application/json"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "inputs",
        [
            {"list_id": "../other-list", "contact_id": "99"},
            {"list_id": "42", "contact_id": "not-a-contact-id"},
        ],
    )
    async def test_rejects_non_numeric_ids_before_http(self, mock_context, inputs):
        result = await hubspot.execute_action("remove_contact_from_list", inputs, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert result.result["source"] == "input"
        mock_context.fetch.assert_not_called()


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
