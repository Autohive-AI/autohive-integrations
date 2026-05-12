"""
End-to-end integration tests for the HubSpot CRM integration.

These tests call the real HubSpot API and require a valid OAuth access token
set in the HUBSPOT_ACCESS_TOKEN environment variable (via .env or export).

Read-only tests require specific object IDs set in environment variables:
    HUBSPOT_TEST_CONTACT_ID, HUBSPOT_TEST_COMPANY_ID, HUBSPOT_TEST_DEAL_ID,
    HUBSPOT_TEST_TICKET_ID, HUBSPOT_TEST_LIST_ID, HUBSPOT_TEST_OWNER_ID

Tests that create, update, or delete data are marked @pytest.mark.destructive
and excluded by default. Run them explicitly with:
    pytest hubspot/tests/test_hubspot_integration.py -m "integration and destructive"

Run read-only tests with:
    pytest hubspot/tests/test_hubspot_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
TEST_CONTACT_ID = os.environ.get("HUBSPOT_TEST_CONTACT_ID", "")
TEST_COMPANY_ID = os.environ.get("HUBSPOT_TEST_COMPANY_ID", "")
TEST_DEAL_ID = os.environ.get("HUBSPOT_TEST_DEAL_ID", "")
TEST_TICKET_ID = os.environ.get("HUBSPOT_TEST_TICKET_ID", "")
TEST_LIST_ID = os.environ.get("HUBSPOT_TEST_LIST_ID", "")
TEST_OWNER_ID = os.environ.get("HUBSPOT_TEST_OWNER_ID", "")
TEST_CONTACT_EMAIL = os.environ.get("HUBSPOT_TEST_CONTACT_EMAIL", "")


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client with HubSpot OAuth token.

    The HubSpot integration relies on context.fetch to auto-inject the OAuth token
    (auth.type = "platform"). In tests we bypass the SDK auth layer and manually
    add the Authorization header to every request.
    """
    if not ACCESS_TOKEN:
        pytest.skip("HUBSPOT_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


def require_contact_id():
    if not TEST_CONTACT_ID:
        pytest.skip("HUBSPOT_TEST_CONTACT_ID not set")


def require_contact_email():
    if not TEST_CONTACT_EMAIL:
        pytest.skip("HUBSPOT_TEST_CONTACT_EMAIL not set")


def require_company_id():
    if not TEST_COMPANY_ID:
        pytest.skip("HUBSPOT_TEST_COMPANY_ID not set")


def require_deal_id():
    if not TEST_DEAL_ID:
        pytest.skip("HUBSPOT_TEST_DEAL_ID not set")


def require_ticket_id():
    if not TEST_TICKET_ID:
        pytest.skip("HUBSPOT_TEST_TICKET_ID not set")


def require_list_id():
    if not TEST_LIST_ID:
        pytest.skip("HUBSPOT_TEST_LIST_ID not set")


def require_owner_id():
    if not TEST_OWNER_ID:
        pytest.skip("HUBSPOT_TEST_OWNER_ID not set")


# ---- Contact Management (Read-Only) ----


class TestGetContact:
    async def test_search_by_email(self, live_context):
        require_contact_email()
        result = await hubspot.execute_action("get_contact", {"email": TEST_CONTACT_EMAIL}, live_context)
        data = result.result.data
        assert "contact" in data
        assert "id" in data["contact"]

    async def test_returns_contact_properties(self, live_context):
        require_contact_email()
        result = await hubspot.execute_action(
            "get_contact",
            {
                "email": TEST_CONTACT_EMAIL,
                "properties": ["email", "firstname", "lastname"],
            },
            live_context,
        )
        data = result.result.data
        assert "contact" in data
        assert "properties" in data["contact"]


class TestSearchContacts:
    async def test_search_returns_results(self, live_context):
        result = await hubspot.execute_action("search_contacts", {"query": "test", "limit": 5}, live_context)
        data = result.result.data
        assert "results" in data

    async def test_respects_limit(self, live_context):
        result = await hubspot.execute_action("search_contacts", {"query": "a", "limit": 2}, live_context)
        data = result.result.data
        assert len(data.get("results", [])) <= 2


class TestGetRecentContacts:
    async def test_returns_contacts(self, live_context):
        result = await hubspot.execute_action("get_recent_contacts", {"limit": 5}, live_context)
        data = result.result.data
        assert "recent_contacts" in data


class TestGetContactEmails:
    async def test_returns_emails(self, live_context):
        require_contact_id()
        result = await hubspot.execute_action(
            "get_contact_emails",
            {"contact_id": TEST_CONTACT_ID, "email_limit": 3},
            live_context,
        )
        data = result.result.data
        assert "contact_id" in data
        assert "recent_emails" in data
        assert data["contact_id"] == TEST_CONTACT_ID


class TestGetContactNotes:
    async def test_returns_notes(self, live_context):
        require_contact_id()
        result = await hubspot.execute_action(
            "get_contact_notes",
            {"contact_id": TEST_CONTACT_ID, "limit": 5},
            live_context,
        )
        data = result.result.data
        assert data["contact_id"] == TEST_CONTACT_ID
        assert "notes" in data
        assert "total" in data


# ---- Company Management (Read-Only) ----


class TestGetCompany:
    async def test_returns_company(self, live_context):
        require_company_id()
        result = await hubspot.execute_action("get_company", {"company_id": TEST_COMPANY_ID}, live_context)
        data = result.result.data
        assert "company" in data
        assert data["company"]["id"] == TEST_COMPANY_ID


class TestSearchCompanies:
    async def test_search_returns_results(self, live_context):
        result = await hubspot.execute_action("search_companies", {"query": "test", "limit": 5}, live_context)
        data = result.result.data
        assert "results" in data


class TestGetCompanyNotes:
    async def test_returns_notes(self, live_context):
        require_company_id()
        result = await hubspot.execute_action(
            "get_company_notes",
            {"company_id": TEST_COMPANY_ID, "limit": 5},
            live_context,
        )
        data = result.result.data
        assert data["company_id"] == TEST_COMPANY_ID
        assert "notes" in data


# ---- Deal Management (Read-Only) ----


class TestGetDeals:
    async def test_single_page(self, live_context):
        result = await hubspot.execute_action(
            "get_deals",
            {
                "limit": 5,
                "sort_property": "hs_lastmodifieddate",
                "sort_direction": "DESC",
                "fetch_all": False,
            },
            live_context,
        )
        data = result.result.data
        assert "results" in data
        assert "total" in data

    async def test_respects_limit(self, live_context):
        result = await hubspot.execute_action("get_deals", {"limit": 2, "fetch_all": False}, live_context)
        data = result.result.data
        assert len(data.get("results", [])) <= 2


class TestGetDeal:
    async def test_returns_deal(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action("get_deal", {"deal_id": TEST_DEAL_ID}, live_context)
        data = result.result.data
        assert "deal" in data

    async def test_custom_properties(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action(
            "get_deal",
            {
                "deal_id": TEST_DEAL_ID,
                "properties": ["dealname", "amount", "closedate"],
            },
            live_context,
        )
        data = result.result.data
        assert "deal" in data


class TestSearchDeals:
    async def test_search_returns_results(self, live_context):
        result = await hubspot.execute_action(
            "search_deals",
            {"query": "deal", "limit": 5, "fetch_all": False},
            live_context,
        )
        data = result.result.data
        assert "results" in data


class TestGetDealPipelines:
    async def test_returns_pipelines(self, live_context):
        result = await hubspot.execute_action("get_deal_pipelines", {}, live_context)
        data = result.result.data
        assert "pipelines" in data
        assert len(data["pipelines"]) > 0


class TestGetDealNotes:
    async def test_returns_notes(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action("get_deal_notes", {"deal_id": TEST_DEAL_ID, "limit": 5}, live_context)
        data = result.result.data
        assert data["deal_id"] == TEST_DEAL_ID
        assert "notes" in data


# ---- Ticket Management (Read-Only) ----


class TestGetRecentTickets:
    async def test_returns_tickets(self, live_context):
        result = await hubspot.execute_action(
            "get_recent_tickets",
            {
                "limit": 5,
                "sort_property": "hs_lastmodifieddate",
                "sort_direction": "DESC",
            },
            live_context,
        )
        data = result.result.data
        assert "tickets" in data


# ---- Properties Discovery (Read-Only) ----


class TestGetDealProperties:
    async def test_returns_properties(self, live_context):
        result = await hubspot.execute_action("get_deal_properties", {"include_details": True}, live_context)
        data = result.result.data
        assert "properties" in data
        assert data["total_properties"] > 0

    async def test_custom_properties_counted(self, live_context):
        result = await hubspot.execute_action("get_deal_properties", {"include_details": True}, live_context)
        data = result.result.data
        assert "custom_properties_count" in data
        assert isinstance(data["custom_properties_count"], int)


class TestGetContactProperties:
    async def test_returns_properties(self, live_context):
        result = await hubspot.execute_action("get_contact_properties", {"include_details": False}, live_context)
        data = result.result.data
        assert "properties" in data
        assert data["total_properties"] > 0


class TestGetCompanyProperties:
    async def test_returns_properties(self, live_context):
        result = await hubspot.execute_action("get_company_properties", {"include_details": False}, live_context)
        data = result.result.data
        assert "properties" in data
        assert data["total_properties"] > 0


# ---- Lists (Read-Only) ----


class TestGetLists:
    async def test_returns_lists(self, live_context):
        result = await hubspot.execute_action("get_lists", {"processing_types": ["DYNAMIC", "MANUAL"]}, live_context)
        data = result.result.data
        assert "lists" in data
        assert "total_lists" in data


class TestGetList:
    async def test_returns_list_details(self, live_context):
        require_list_id()
        result = await hubspot.execute_action("get_list", {"list_id": TEST_LIST_ID}, live_context)
        data = result.result.data
        assert "list" in data


class TestSearchLists:
    async def test_search_returns_results(self, live_context):
        result = await hubspot.execute_action("search_lists", {"query": "Customer", "count": 5}, live_context)
        data = result.result.data
        assert "results" in data


class TestGetListMemberships:
    async def test_returns_memberships(self, live_context):
        require_list_id()
        result = await hubspot.execute_action(
            "get_list_memberships", {"list_id": TEST_LIST_ID, "limit": 10}, live_context
        )
        data = result.result.data
        assert "memberships" in data


# ---- Associations (Read-Only) ----


class TestGetContactAssociations:
    async def test_returns_associations(self, live_context):
        require_contact_id()
        result = await hubspot.execute_action(
            "get_contact_associations",
            {
                "contact_id": TEST_CONTACT_ID,
                "association_types": ["companies", "deals"],
            },
            live_context,
        )
        data = result.result.data
        assert data["contact_id"] == TEST_CONTACT_ID
        assert "associations" in data
        assert "total_associations" in data


class TestGetCompanyAssociations:
    async def test_returns_associations(self, live_context):
        require_company_id()
        result = await hubspot.execute_action(
            "get_company_associations",
            {"company_id": TEST_COMPANY_ID, "association_types": ["contacts", "deals"]},
            live_context,
        )
        data = result.result.data
        assert data["company_id"] == TEST_COMPANY_ID
        assert "associations" in data


class TestGetDealAssociations:
    async def test_returns_associations(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action(
            "get_deal_associations",
            {"deal_id": TEST_DEAL_ID, "association_types": ["contacts", "companies"]},
            live_context,
        )
        data = result.result.data
        assert data["deal_id"] == TEST_DEAL_ID
        assert "associations" in data


# ---- Owner (Read-Only) ----


class TestGetOwner:
    async def test_returns_owner(self, live_context):
        require_owner_id()
        result = await hubspot.execute_action("get_owner", {"owner_id": TEST_OWNER_ID}, live_context)
        data = result.result.data
        assert "owner" in data
        assert data["owner"]["id"] == TEST_OWNER_ID

    async def test_owner_has_expected_fields(self, live_context):
        require_owner_id()
        result = await hubspot.execute_action("get_owner", {"owner_id": TEST_OWNER_ID}, live_context)
        owner = result.result.data["owner"]
        assert "email" in owner
        assert "firstName" in owner
        assert "lastName" in owner


# ---- Calls and Meetings (Read-Only) ----


class TestGetContactCallsAndMeetings:
    async def test_returns_calls_and_meetings(self, live_context):
        require_contact_id()
        result = await hubspot.execute_action(
            "get_contact_calls_and_meetings",
            {"contact_id": TEST_CONTACT_ID, "limit": 5},
            live_context,
        )
        data = result.result.data
        assert data["contact_id"] == TEST_CONTACT_ID
        assert "calls" in data
        assert "meetings" in data
        assert "total_calls" in data
        assert "total_meetings" in data


class TestGetDealCallsAndMeetings:
    async def test_returns_calls_and_meetings(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action(
            "get_deal_calls_and_meetings",
            {"deal_id": TEST_DEAL_ID, "limit": 5},
            live_context,
        )
        data = result.result.data
        assert data["deal_id"] == TEST_DEAL_ID
        assert "calls" in data
        assert "meetings" in data


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data in HubSpot.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCreateContact:
    async def test_creates_contact(self, live_context):
        result = await hubspot.execute_action(
            "create_contact",
            {
                "properties": {
                    "email": f"integration-test-{os.getpid()}@example.com",
                    "firstname": "Integration",
                    "lastname": "Test",
                }
            },
            live_context,
        )
        data = result.result.data
        assert "contact" in data
        assert data["contact"]["id"] is not None


@pytest.mark.destructive
class TestUpdateContact:
    async def test_updates_contact(self, live_context):
        require_contact_id()
        result = await hubspot.execute_action(
            "update_contact",
            {
                "contact_id": TEST_CONTACT_ID,
                "properties": {"jobtitle": "Integration Test"},
            },
            live_context,
        )
        data = result.result.data
        assert "contact" in data


@pytest.mark.destructive
class TestCreateCompany:
    async def test_creates_company(self, live_context):
        result = await hubspot.execute_action(
            "create_company",
            {
                "properties": {
                    "name": f"Integration Test Co {os.getpid()}",
                    "domain": "integration-test.example.com",
                }
            },
            live_context,
        )
        data = result.result.data
        assert "company" in data
        assert data["company"]["id"] is not None


@pytest.mark.destructive
class TestUpdateCompany:
    async def test_updates_company(self, live_context):
        require_company_id()
        result = await hubspot.execute_action(
            "update_company",
            {
                "company_id": TEST_COMPANY_ID,
                "properties": {"description": "Integration test update"},
            },
            live_context,
        )
        data = result.result.data
        assert "company" in data


@pytest.mark.destructive
class TestCreateDeal:
    async def test_creates_deal(self, live_context):
        result = await hubspot.execute_action(
            "create_deal",
            {
                "properties": {
                    "dealname": f"Integration Test Deal {os.getpid()}",
                    "amount": "1000",
                    "pipeline": "default",
                }
            },
            live_context,
        )
        data = result.result.data
        assert "deal" in data


@pytest.mark.destructive
class TestUpdateDeal:
    async def test_updates_deal(self, live_context):
        require_deal_id()
        result = await hubspot.execute_action(
            "update_deal",
            {
                "deal_id": TEST_DEAL_ID,
                "properties": {"dealname": "Integration Test Updated Deal"},
            },
            live_context,
        )
        data = result.result.data
        assert "deal" in data


@pytest.mark.destructive
class TestNoteWorkflow:
    """End-to-end workflow: create → read → update → delete a note."""

    async def test_full_note_lifecycle(self, live_context):
        require_contact_id()

        # Step 1: Create
        create_result = await hubspot.execute_action(
            "create_note",
            {
                "note_body": "Integration test note — will be deleted.",
                "contact_id": TEST_CONTACT_ID,
            },
            live_context,
        )
        assert create_result.result.data["success"] is True
        note_id = create_result.result.data["note"]["id"]
        assert note_id is not None

        # Step 2: Read
        read_result = await hubspot.execute_action(
            "get_contact_notes",
            {"contact_id": TEST_CONTACT_ID, "limit": 5},
            live_context,
        )
        note_ids = [n["id"] for n in read_result.result.data["notes"]]
        assert note_id in note_ids

        # Step 3: Update
        update_result = await hubspot.execute_action(
            "update_note",
            {"note_id": note_id, "note_body": "Updated integration test note."},
            live_context,
        )
        assert update_result.result.data["success"] is True

        # Step 4: Delete (cleanup)
        delete_result = await hubspot.execute_action("delete_note", {"note_id": note_id}, live_context)
        assert delete_result.result.data["success"] is True


@pytest.mark.destructive
class TestAddTicketComment:
    async def test_adds_comment(self, live_context):
        require_ticket_id()
        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": TEST_TICKET_ID, "comment": "Integration test comment."},
            live_context,
        )
        data = result.result.data
        assert "result" in data
