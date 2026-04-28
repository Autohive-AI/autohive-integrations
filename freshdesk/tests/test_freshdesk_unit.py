import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("freshdesk_mod", os.path.join(_parent, "freshdesk.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

freshdesk = _mod.freshdesk  # the Integration instance
get_auth_headers = _mod.get_auth_headers
get_base_url = _mod.get_base_url

pytestmark = pytest.mark.unit


# ---- Fixtures ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"api_key": "test_api_key", "domain": "testcompany"}  # nosec B105
    return ctx


# ---- Sample Data ----

SAMPLE_COMPANY = {
    "id": 1001,
    "name": "Acme Corp",
    "description": "A test company",
    "domains": ["acme.com"],
    "note": "VIP customer",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
}

SAMPLE_TICKET = {
    "id": 5001,
    "subject": "Test issue",
    "description": "<p>Something broke</p>",
    "status": 2,
    "priority": 1,
    "email": "customer@example.com",
    "created_at": "2024-01-01T00:00:00Z",
}

SAMPLE_CONTACT = {
    "id": 3001,
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "555-0100",
    "created_at": "2024-01-01T00:00:00Z",
}

SAMPLE_CONVERSATION = {
    "id": 7001,
    "body": "<p>Note content</p>",
    "private": True,
    "created_at": "2024-01-01T00:00:00Z",
}


# ---- Helper Function Tests ----


class TestGetAuthHeaders:
    def test_returns_authorization_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_returns_content_type_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Content-Type"] == "application/json"

    def test_uses_api_key_from_auth(self, mock_context):
        import base64

        headers = get_auth_headers(mock_context)
        encoded = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("ascii")
        assert decoded == "test_api_key:X"  # nosec B105


class TestGetBaseUrl:
    def test_includes_domain(self, mock_context):
        url = get_base_url(mock_context)
        assert "testcompany" in url

    def test_freshdesk_subdomain_format(self, mock_context):
        url = get_base_url(mock_context)
        assert url == "https://testcompany.freshdesk.com/api/v2"


# ---- Company Tests ----


class TestListCompanies:
    @pytest.mark.asyncio
    async def test_happy_path_returns_companies(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_COMPANY])

        result = await freshdesk.execute_action("list_companies", {}, mock_context)

        assert result.result.data["companies"] == [SAMPLE_COMPANY]
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_companies", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "testcompany.freshdesk.com/api/v2/companies" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_default_pagination_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_companies", {}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["page"] == 1
        assert params["per_page"] == 30

    @pytest.mark.asyncio
    async def test_custom_pagination_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_companies", {"page": 2, "per_page": 10}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["page"] == 2
        assert params["per_page"] == 10

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "bad"})

        result = await freshdesk.execute_action("list_companies", {}, mock_context)

        assert result.result.data["companies"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await freshdesk.execute_action("list_companies", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


class TestCreateCompany:
    @pytest.mark.asyncio
    async def test_happy_path_returns_company(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMPANY)

        result = await freshdesk.execute_action("create_company", {"name": "Acme Corp"}, mock_context)

        assert result.result.data["company"] == SAMPLE_COMPANY

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("create_company", {"name": "Acme Corp"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "testcompany.freshdesk.com/api/v2/companies" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_name_included_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("create_company", {"name": "Acme Corp"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_optional_fields_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action(
            "create_company",
            {"name": "Acme Corp", "description": "Test desc", "domains": ["acme.com"], "note": "VIP"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["description"] == "Test desc"
        assert body["domains"] == ["acme.com"]
        assert body["note"] == "VIP"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await freshdesk.execute_action("create_company", {"name": "Acme Corp"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


class TestGetCompany:
    @pytest.mark.asyncio
    async def test_happy_path_returns_company(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMPANY)

        result = await freshdesk.execute_action("get_company", {"company_id": 1001}, mock_context)

        assert result.result.data["company"] == SAMPLE_COMPANY

    @pytest.mark.asyncio
    async def test_request_url_includes_company_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("get_company", {"company_id": 1001}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "/companies/1001" in url

    @pytest.mark.asyncio
    async def test_request_method_is_get(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("get_company", {"company_id": 1001}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await freshdesk.execute_action("get_company", {"company_id": 9999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


class TestUpdateCompany:
    @pytest.mark.asyncio
    async def test_happy_path_returns_company(self, mock_context):
        updated = {**SAMPLE_COMPANY, "name": "New Name"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await freshdesk.execute_action(
            "update_company", {"company_id": 1001, "name": "New Name"}, mock_context
        )

        assert result.result.data["company"]["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("update_company", {"company_id": 1001, "name": "New Name"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/companies/1001" in call_args.args[0]
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_only_provided_fields_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMPANY)

        await freshdesk.execute_action("update_company", {"company_id": 1001, "name": "New Name"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "name" in body
        assert "description" not in body

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update failed")

        result = await freshdesk.execute_action("update_company", {"company_id": 1001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Update failed" in result.result.message


class TestDeleteCompany:
    @pytest.mark.asyncio
    async def test_happy_path_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await freshdesk.execute_action("delete_company", {"company_id": 1001}, mock_context)

        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await freshdesk.execute_action("delete_company", {"company_id": 1001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/companies/1001" in call_args.args[0]
        assert call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await freshdesk.execute_action("delete_company", {"company_id": 1001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


class TestSearchCompanies:
    @pytest.mark.asyncio
    async def test_happy_path_returns_companies(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"companies": [{"id": 1001, "name": "Acme Corp"}]}
        )

        result = await freshdesk.execute_action("search_companies", {"name": "Acme"}, mock_context)

        assert len(result.result.data["companies"]) == 1
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"companies": []})

        await freshdesk.execute_action("search_companies", {"name": "Acme"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/companies/autocomplete" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_name_passed_as_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"companies": []})

        await freshdesk.execute_action("search_companies", {"name": "Acme"}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_no_companies_key_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await freshdesk.execute_action("search_companies", {"name": "Acme"}, mock_context)

        assert result.result.data["companies"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Search failed")

        result = await freshdesk.execute_action("search_companies", {"name": "Acme"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Search failed" in result.result.message


# ---- Ticket Tests ----


class TestCreateTicket:
    @pytest.mark.asyncio
    async def test_happy_path_returns_ticket(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TICKET)

        result = await freshdesk.execute_action(
            "create_ticket", {"subject": "Test issue", "email": "customer@example.com"}, mock_context
        )

        assert result.result.data["ticket"] == SAMPLE_TICKET

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action(
            "create_ticket", {"subject": "Test issue", "email": "customer@example.com"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert "testcompany.freshdesk.com/api/v2/tickets" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_required_fields_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action(
            "create_ticket", {"subject": "Test issue", "email": "customer@example.com"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["subject"] == "Test issue"
        assert body["email"] == "customer@example.com"

    @pytest.mark.asyncio
    async def test_optional_fields_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action(
            "create_ticket",
            {"subject": "Test", "email": "c@example.com", "priority": 2, "status": 2, "tags": ["bug"]},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["priority"] == 2
        assert body["status"] == 2
        assert body["tags"] == ["bug"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create ticket failed")

        result = await freshdesk.execute_action(
            "create_ticket", {"subject": "Test", "email": "c@example.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Create ticket failed" in result.result.message


class TestListTickets:
    @pytest.mark.asyncio
    async def test_happy_path_returns_tickets(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TICKET])

        result = await freshdesk.execute_action("list_tickets", {}, mock_context)

        assert result.result.data["tickets"] == [SAMPLE_TICKET]
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_request_method_is_get(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_tickets", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_default_pagination(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_tickets", {}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["page"] == 1
        assert params["per_page"] == 30

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("List failed")

        result = await freshdesk.execute_action("list_tickets", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "List failed" in result.result.message


class TestGetTicket:
    @pytest.mark.asyncio
    async def test_happy_path_returns_ticket(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TICKET)

        result = await freshdesk.execute_action("get_ticket", {"ticket_id": 5001}, mock_context)

        assert result.result.data["ticket"] == SAMPLE_TICKET

    @pytest.mark.asyncio
    async def test_request_url_includes_ticket_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action("get_ticket", {"ticket_id": 5001}, mock_context)

        assert "/tickets/5001" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Ticket not found")

        result = await freshdesk.execute_action("get_ticket", {"ticket_id": 9999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Ticket not found" in result.result.message


class TestUpdateTicket:
    @pytest.mark.asyncio
    async def test_happy_path_returns_ticket(self, mock_context):
        updated = {**SAMPLE_TICKET, "status": 4}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await freshdesk.execute_action("update_ticket", {"ticket_id": 5001, "status": 4}, mock_context)

        assert result.result.data["ticket"]["status"] == 4

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action("update_ticket", {"ticket_id": 5001, "status": 4}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/tickets/5001" in call_args.args[0]
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_only_provided_fields_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TICKET)

        await freshdesk.execute_action("update_ticket", {"ticket_id": 5001, "status": 4}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "status" in body
        assert "subject" not in body

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update failed")

        result = await freshdesk.execute_action("update_ticket", {"ticket_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Update failed" in result.result.message


class TestDeleteTicket:
    @pytest.mark.asyncio
    async def test_happy_path_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await freshdesk.execute_action("delete_ticket", {"ticket_id": 5001}, mock_context)

        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await freshdesk.execute_action("delete_ticket", {"ticket_id": 5001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/tickets/5001" in call_args.args[0]
        assert call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete failed")

        result = await freshdesk.execute_action("delete_ticket", {"ticket_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Delete failed" in result.result.message


# ---- Contact Tests ----


class TestCreateContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contact(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONTACT)

        result = await freshdesk.execute_action(
            "create_contact", {"name": "John Doe", "email": "john@example.com"}, mock_context
        )

        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONTACT)

        await freshdesk.execute_action(
            "create_contact", {"name": "John Doe", "email": "john@example.com"}, mock_context
        )

        call_args = mock_context.fetch.call_args
        assert "testcompany.freshdesk.com/api/v2/contacts" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_required_fields_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONTACT)

        await freshdesk.execute_action(
            "create_contact", {"name": "John Doe", "email": "john@example.com"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "John Doe"
        assert body["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_optional_fields_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONTACT)

        await freshdesk.execute_action(
            "create_contact",
            {"name": "John Doe", "email": "john@example.com", "phone": "555-0100", "job_title": "Engineer"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["phone"] == "555-0100"
        assert body["job_title"] == "Engineer"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Duplicate email")

        result = await freshdesk.execute_action(
            "create_contact", {"name": "John Doe", "email": "john@example.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Duplicate email" in result.result.message


class TestListContacts:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contacts(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_CONTACT])

        result = await freshdesk.execute_action("list_contacts", {}, mock_context)

        assert result.result.data["contacts"] == [SAMPLE_CONTACT]
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=None)

        result = await freshdesk.execute_action("list_contacts", {}, mock_context)

        assert result.result.data["contacts"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("List contacts failed")

        result = await freshdesk.execute_action("list_contacts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "List contacts failed" in result.result.message


class TestGetContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contact(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONTACT)

        result = await freshdesk.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        assert result.result.data["contact"] == SAMPLE_CONTACT

    @pytest.mark.asyncio
    async def test_request_url_includes_contact_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONTACT)

        await freshdesk.execute_action("get_contact", {"contact_id": 3001}, mock_context)

        assert "/contacts/3001" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Contact not found")

        result = await freshdesk.execute_action("get_contact", {"contact_id": 9999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Contact not found" in result.result.message


class TestUpdateContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contact(self, mock_context):
        updated = {**SAMPLE_CONTACT, "job_title": "Senior Engineer"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await freshdesk.execute_action(
            "update_contact", {"contact_id": 3001, "job_title": "Senior Engineer"}, mock_context
        )

        assert result.result.data["contact"]["job_title"] == "Senior Engineer"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONTACT)

        await freshdesk.execute_action("update_contact", {"contact_id": 3001, "name": "Jane Doe"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/contacts/3001" in call_args.args[0]
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update contact failed")

        result = await freshdesk.execute_action("update_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Update contact failed" in result.result.message


class TestDeleteContact:
    @pytest.mark.asyncio
    async def test_happy_path_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await freshdesk.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await freshdesk.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/contacts/3001" in call_args.args[0]
        assert call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete contact failed")

        result = await freshdesk.execute_action("delete_contact", {"contact_id": 3001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Delete contact failed" in result.result.message


class TestSearchContacts:
    @pytest.mark.asyncio
    async def test_happy_path_returns_contacts(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[{"id": 3001, "name": "John Doe"}])

        result = await freshdesk.execute_action("search_contacts", {"term": "John"}, mock_context)

        assert len(result.result.data["contacts"]) == 1
        assert result.result.data["total"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("search_contacts", {"term": "John"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/contacts/autocomplete" in call_args.args[0]
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_term_passed_as_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("search_contacts", {"term": "John"}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["term"] == "John"

    @pytest.mark.asyncio
    async def test_non_list_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "oops"})

        result = await freshdesk.execute_action("search_contacts", {"term": "John"}, mock_context)

        assert result.result.data["contacts"] == []
        assert result.result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Search failed")

        result = await freshdesk.execute_action("search_contacts", {"term": "John"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Search failed" in result.result.message


# ---- Conversation Tests ----


class TestListConversations:
    @pytest.mark.asyncio
    async def test_happy_path_returns_conversations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_CONVERSATION])

        result = await freshdesk.execute_action("list_conversations", {"ticket_id": 5001}, mock_context)

        assert result.result.data["conversations"] == [SAMPLE_CONVERSATION]

    @pytest.mark.asyncio
    async def test_request_url_includes_ticket_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_conversations", {"ticket_id": 5001}, mock_context)

        assert "/tickets/5001/conversations" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_request_method_is_get(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await freshdesk.execute_action("list_conversations", {"ticket_id": 5001}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_non_list_response_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=None)

        result = await freshdesk.execute_action("list_conversations", {"ticket_id": 5001}, mock_context)

        assert result.result.data["conversations"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Conversations failed")

        result = await freshdesk.execute_action("list_conversations", {"ticket_id": 5001}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Conversations failed" in result.result.message


class TestCreateNote:
    @pytest.mark.asyncio
    async def test_happy_path_returns_conversation(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        result = await freshdesk.execute_action("create_note", {"ticket_id": 5001, "body": "<p>Note</p>"}, mock_context)

        assert result.result.data["conversation"] == SAMPLE_CONVERSATION

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action("create_note", {"ticket_id": 5001, "body": "<p>Note</p>"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/tickets/5001/notes" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_private_true_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action("create_note", {"ticket_id": 5001, "body": "<p>Note</p>"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["private"] is True
        assert body["body"] == "<p>Note</p>"

    @pytest.mark.asyncio
    async def test_notify_emails_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action(
            "create_note",
            {"ticket_id": 5001, "body": "<p>Note</p>", "notify_emails": ["agent@example.com"]},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["notify_emails"] == ["agent@example.com"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create note failed")

        result = await freshdesk.execute_action("create_note", {"ticket_id": 5001, "body": "<p>Note</p>"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Create note failed" in result.result.message


class TestCreateReply:
    @pytest.mark.asyncio
    async def test_happy_path_returns_conversation(self, mock_context):
        reply = {**SAMPLE_CONVERSATION, "private": False}
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=reply)

        result = await freshdesk.execute_action(
            "create_reply", {"ticket_id": 5001, "body": "<p>Reply</p>"}, mock_context
        )

        assert result.result.data["conversation"]["private"] is False

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action("create_reply", {"ticket_id": 5001, "body": "<p>Reply</p>"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "/tickets/5001/reply" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_body_in_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action("create_reply", {"ticket_id": 5001, "body": "<p>Reply</p>"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["body"] == "<p>Reply</p>"

    @pytest.mark.asyncio
    async def test_from_email_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_CONVERSATION)

        await freshdesk.execute_action(
            "create_reply",
            {"ticket_id": 5001, "body": "<p>Reply</p>", "from_email": "support@company.com"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["from_email"] == "support@company.com"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create reply failed")

        result = await freshdesk.execute_action(
            "create_reply", {"ticket_id": 5001, "body": "<p>Reply</p>"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Create reply failed" in result.result.message
