"""
End-to-end integration tests for the HubSpot CRM integration.

These tests call the real HubSpot API and require a valid OAuth access token
set in the HUBSPOT_ACCESS_TOKEN environment variable (via .env or export).

Read-only tests require specific object IDs set in environment variables:
    HUBSPOT_TEST_CONTACT_ID, HUBSPOT_TEST_COMPANY_ID, HUBSPOT_TEST_DEAL_ID,
    HUBSPOT_TEST_TICKET_ID, HUBSPOT_TEST_LIST_ID, HUBSPOT_TEST_OWNER_ID

Destructive tests also use HUBSPOT_TEST_CONTACT_EMAIL (contact upsert) and
HUBSPOT_TEST_COMPANY_ID (record linking).

The list-membership tests require HUBSPOT_TEST_LIST_ID to identify a MANUAL or
SNAPSHOT list and HUBSPOT_TEST_CONTACT_ID to identify the contact to update.

Run read-only tests with:
    pytest hubspot/tests/test_hubspot_integration.py -m "integration and not destructive"

Tests that create, update, or delete data are marked @pytest.mark.destructive.
Run them deliberately on a test account only; this command mutates real data:
    pytest hubspot/tests/test_hubspot_integration.py -m "integration and destructive"

For the targeted nullable-subject regression, set
HUBSPOT_TEST_UNSET_SUBJECT_TICKET_ID to a ticket returned in the latest 100
modified tickets whose search response has subject=null. No tickets are created
or modified to prepare this test.

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import asyncio
import os
import time
from copy import deepcopy

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.integration

TEST_CONTACT_ID = os.environ.get("HUBSPOT_TEST_CONTACT_ID", "")
TEST_COMPANY_ID = os.environ.get("HUBSPOT_TEST_COMPANY_ID", "")
TEST_DEAL_ID = os.environ.get("HUBSPOT_TEST_DEAL_ID", "")
TEST_TICKET_ID = os.environ.get("HUBSPOT_TEST_TICKET_ID", "")
TEST_LIST_ID = os.environ.get("HUBSPOT_TEST_LIST_ID", "")
TEST_OWNER_ID = os.environ.get("HUBSPOT_TEST_OWNER_ID", "")
TEST_CONTACT_EMAIL = os.environ.get("HUBSPOT_TEST_CONTACT_EMAIL", "")


@pytest.fixture
def live_context(env_credentials):
    """Execution context wired to a real HTTP client with HubSpot OAuth token.

    The HubSpot integration relies on context.fetch to auto-inject the OAuth token
    (auth.type = "platform"). In tests we bypass the SDK auth layer and manually
    add the Authorization header to every request.
    """
    access_token = env_credentials("HUBSPOT_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("HUBSPOT_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    api_responses = []

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                if resp.status >= 400:
                    raise HTTPError(resp.status, f"HubSpot API returned HTTP {resp.status}")
                if resp.status == 204:
                    data = {}
                else:
                    data = await resp.json(content_type=None)
                api_responses.append(deepcopy(data))
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.api_responses = api_responses
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": access_token},
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


async def contact_is_in_test_list(context):
    """Return whether the configured contact currently belongs to the configured list."""
    response = await context.fetch(
        f"https://api.hubapi.com/crm/lists/2026-03/records/0-1/{TEST_CONTACT_ID}/memberships",
        method="GET",
    )
    return any(str(membership.get("listId")) == str(TEST_LIST_ID) for membership in response.data.get("results", []))


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
    @pytest.mark.parametrize("limit", [5, 100])
    async def test_returns_provider_response_without_dropping_tickets(self, live_context, limit):
        result = await hubspot.execute_action(
            "get_recent_tickets",
            {
                "limit": limit,
                "sort_property": "hs_lastmodifieddate",
                "sort_direction": "DESC",
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, f"Unexpected SDK result type: {result.type}"
        tickets = result.result.data["tickets"]
        assert tickets == live_context.api_responses[-1]
        assert isinstance(tickets["total"], int)
        assert isinstance(tickets["results"], list)
        assert len(tickets["results"]) <= limit
        if not tickets["results"]:
            pytest.skip("No tickets in the test account; ticket-record assertions were not exercised")
        for ticket in tickets["results"]:
            assert isinstance(ticket["id"], str)
            assert isinstance(ticket["properties"], dict)
            for value in ticket["properties"].values():
                assert value is None or isinstance(value, str)
        modified_dates = [ticket["properties"].get("hs_lastmodifieddate") for ticket in tickets["results"]]
        modified_dates = [value for value in modified_dates if value]
        assert modified_dates == sorted(modified_dates, reverse=True)
        if "paging" in tickets:
            assert "after" in tickets["paging"]["next"]

    async def test_known_null_subject_ticket_is_preserved(self, live_context, env_credentials):
        ticket_id = env_credentials("HUBSPOT_TEST_UNSET_SUBJECT_TICKET_ID")
        if not ticket_id:
            pytest.skip("HUBSPOT_TEST_UNSET_SUBJECT_TICKET_ID not set — null-subject live regression not exercised")

        result = await hubspot.execute_action("get_recent_tickets", {"limit": 100}, live_context)

        assert result.type == ResultType.ACTION, f"Unexpected SDK result type: {result.type}"
        provider_response = live_context.api_responses[-1]
        target = next((ticket for ticket in provider_response["results"] if ticket["id"] == ticket_id), None)
        assert target is not None, "Configured ticket must be among the latest 100 modified tickets in this account"
        assert "subject" in target["properties"], (
            "Configured fixture must have an explicit null subject, not an omitted one"
        )
        assert target["properties"]["subject"] is None, (
            "Configured fixture must have subject=null in the search response"
        )
        assert result.result.data["tickets"] == provider_response


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
class TestAddContactToList:
    async def test_add_contact_to_static_list(self, live_context):
        require_contact_id()
        require_list_id()

        was_member = await contact_is_in_test_list(live_context)
        try:
            result = await hubspot.execute_action(
                "add_contact_to_list",
                {"list_id": TEST_LIST_ID, "contact_id": TEST_CONTACT_ID},
                live_context,
            )
            api_result = result.result.data["result"]

            assert "category" not in api_result
            assert any(
                key in api_result
                for key in ("recordIdsAdded", "recordsIdsAdded", "recordIdsMissing", "recordIdsRemoved")
            )
            assert await contact_is_in_test_list(live_context)
        finally:
            if not was_member:
                await hubspot.execute_action(
                    "remove_contact_from_list",
                    {"list_id": TEST_LIST_ID, "contact_id": TEST_CONTACT_ID},
                    live_context,
                )


@pytest.mark.destructive
class TestRemoveContactFromList:
    async def test_remove_contact_from_static_list(self, live_context):
        require_contact_id()
        require_list_id()

        was_member = await contact_is_in_test_list(live_context)
        try:
            if not was_member:
                await hubspot.execute_action(
                    "add_contact_to_list",
                    {"list_id": TEST_LIST_ID, "contact_id": TEST_CONTACT_ID},
                    live_context,
                )

            result = await hubspot.execute_action(
                "remove_contact_from_list",
                {"list_id": TEST_LIST_ID, "contact_id": TEST_CONTACT_ID},
                live_context,
            )
            api_result = result.result.data["result"]

            assert TEST_CONTACT_ID in api_result.get("recordIdsRemoved", [])
            assert not await contact_is_in_test_list(live_context)
        finally:
            restore_action = "add_contact_to_list" if was_member else "remove_contact_from_list"
            await hubspot.execute_action(
                restore_action,
                {"list_id": TEST_LIST_ID, "contact_id": TEST_CONTACT_ID},
                live_context,
            )


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
        note_id = None
        try:
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

            # Step 2: Read. get_contact_notes uses HubSpot search, which takes a few seconds to index a new note
            note_ids = []
            for _ in range(15):
                read_result = await hubspot.execute_action(
                    "get_contact_notes",
                    {"contact_id": TEST_CONTACT_ID, "limit": 5},
                    live_context,
                )
                note_ids = [n["id"] for n in read_result.result.data["notes"]]
                if note_id in note_ids:
                    break
                await asyncio.sleep(2)
            assert note_id in note_ids

            # Step 3: Update
            update_result = await hubspot.execute_action(
                "update_note",
                {"note_id": note_id, "note_body": "Updated integration test note."},
                live_context,
            )
            assert update_result.result.data["success"] is True

            # Step 4: Delete
            delete_result = await hubspot.execute_action("delete_note", {"note_id": note_id}, live_context)
            assert delete_result.result.data["success"] is True
            note_id = None
        finally:
            if note_id:
                await hubspot.execute_action("delete_note", {"note_id": note_id}, live_context)


@pytest.mark.destructive
class TestAddTicketComment:
    async def test_adds_internal_note_and_associates_it_to_ticket(self, live_context):
        require_ticket_id()
        note_id = None
        try:
            result = await hubspot.execute_action(
                "add_ticket_comment",
                {
                    "ticket_id": TEST_TICKET_ID,
                    "comment": f"Integration test internal ticket note {os.getpid()}",
                },
                live_context,
            )
            data = result.result.data
            assert data["result"]["success"] is True
            note_id = data["result"]["note"]["id"]
            assert note_id
            assert data["result"]["verification"] is not None

            verification_response = await live_context.fetch(
                f"https://api.hubapi.com/crm/v3/objects/notes/{note_id}",
                method="GET",
                params={"associations": "ticket"},
            )
            association_results = verification_response.data.get("associations", {}).get("tickets", {}).get(
                "results", []
            ) or verification_response.data.get("associations", {}).get("ticket", {}).get("results", [])
            assert any(str(association.get("id")) == str(TEST_TICKET_ID) for association in association_results)
        finally:
            if note_id:
                await hubspot.execute_action("delete_note", {"note_id": note_id}, live_context)


CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"


def unique_suffix():
    return f"{os.getpid()}{int(time.time() * 1000)}"


async def create_disposable_contact(context, created_contact_ids, **properties):
    response = await context.fetch(CONTACTS_URL, method="POST", json={"properties": properties})
    contact_id = str(response.data["id"])
    created_contact_ids.append(contact_id)
    return contact_id


async def delete_contacts(context, contact_ids):
    for contact_id in contact_ids:
        await context.fetch(f"{CONTACTS_URL}/{contact_id}", method="DELETE")


async def wait_until_name_is_searchable(context, first_name, last_name, contact_id):
    # Name matching uses HubSpot search, which takes a few seconds to index a new contact and
    # answers inconsistently for a while after, so require several hits in a row
    filters = [
        {"propertyName": "firstname", "operator": "EQ", "value": first_name},
        {"propertyName": "lastname", "operator": "EQ", "value": last_name},
    ]
    hits = 0
    for _ in range(20):
        response = await context.fetch(
            f"{CONTACTS_URL}/search", method="POST", json={"filterGroups": [{"filters": filters}], "limit": 5}
        )
        found = [str(c["id"]) for c in response.data.get("results", [])] == [contact_id]
        hits = hits + 1 if found else 0
        if hits == 3:
            return
        await asyncio.sleep(2)
    pytest.fail(f"Contact {contact_id} never became searchable by name")


async def log_and_collect_created_ids(context, inputs, created_ids):
    """Run log_linkedin_messages, keeping every ID from HubSpot's raw batch response for cleanup."""
    responses_before = len(context.api_responses)
    try:
        return await hubspot.execute_action("log_linkedin_messages", inputs, context)
    finally:
        for body in context.api_responses[responses_before:]:
            if isinstance(body, dict) and any(
                "hs_communication_body" in (r.get("properties") or {}) for r in body.get("results", [])
            ):
                created_ids.update(str(item["id"]) for item in body["results"] if item.get("id"))


async def linked_contact_ids(context, communication_id):
    result = await hubspot.execute_action("get_linkedin_message", {"communication_id": communication_id}, context)
    communication = result.result.data["communication"]
    contact_ids = {str(a["id"]) for a in communication.get("associations", {}).get("contacts", {}).get("results", [])}
    return communication["properties"]["hs_communication_body"], contact_ids


@pytest.mark.destructive
class TestBulkLinkedInMessages:
    """Bulk logging against real HubSpot: several contacts, each matching method, and a mixed batch."""

    async def test_logs_distinct_messages_on_contacts_found_by_id_email_and_name(self, live_context):
        suffix = unique_suffix()
        contact_ids, created_ids = [], set()
        try:
            by_id = await create_disposable_contact(live_context, contact_ids, email=f"li-id-{suffix}@example.com")
            email = f"li-email-{suffix}@example.com"
            by_email = await create_disposable_contact(live_context, contact_ids, email=email)
            first_name, last_name = f"Linked{suffix}", "Bulktest"
            by_name = await create_disposable_contact(
                live_context,
                contact_ids,
                email=f"li-name-{suffix}@example.com",
                firstname=first_name,
                lastname=last_name,
            )
            await wait_until_name_is_searchable(live_context, first_name, last_name, by_name)

            rows = [
                ({"contact_id": by_id}, by_id),
                ({"email": email.upper()}, by_email),
                ({"first_name": first_name, "last_name": last_name}, by_name),
            ]
            bodies = [f"Bulk LinkedIn test {suffix} row {i}" for i in range(len(rows))]
            result = await log_and_collect_created_ids(
                live_context,
                {"messages": [{**row, "message_body": body} for (row, _), body in zip(rows, bodies)]},
                created_ids,
            )

            data = result.result.data
            assert (data["logged"], data["success"], data["unmatched_communication_ids"]) == (3, True, []), data
            assert len(created_ids) == 3
            for (_, contact_id), body, row in zip(rows, bodies, data["results"]):
                assert (row["status"], row["contact_id"]) == ("logged", contact_id), row
                assert await linked_contact_ids(live_context, row["communication_id"]) == (body, {contact_id})
        finally:
            for created_id in created_ids:
                await hubspot.execute_action("delete_linkedin_message", {"communication_id": created_id}, live_context)
            await delete_contacts(live_context, contact_ids)

    async def test_mixed_batch_with_a_missing_contact(self, live_context):
        suffix = unique_suffix()
        contact_ids, created_ids = [], set()
        try:
            valid_id = await create_disposable_contact(
                live_context, contact_ids, email=f"li-mixed-{suffix}@example.com"
            )
            body = f"Mixed batch LinkedIn test {suffix}"
            result = await log_and_collect_created_ids(
                live_context,
                {"messages": [{"contact_id": valid_id}, {"contact_id": "1"}], "default_message_body": body},
                created_ids,
            )

            # HubSpot rejects the whole batch when one association target is missing, so nothing is created
            data = result.result.data
            assert [r["status"] for r in data["results"]] == ["failed", "failed"], data
            assert (data["success"], data["unmatched_communication_ids"], created_ids) == (False, [], set())
        finally:
            for created_id in created_ids:
                await hubspot.execute_action("delete_linkedin_message", {"communication_id": created_id}, live_context)
            await delete_contacts(live_context, contact_ids)


@pytest.mark.destructive
class TestLinkedInMessageWorkflow:
    """End-to-end workflow: log → read → update → delete a LinkedIn message on the test contact."""

    async def test_full_linkedin_message_lifecycle(self, live_context):
        require_contact_id()
        # IDs come from HubSpot's raw batch response, so cleanup doesn't depend on the action matching rows
        created_ids = set()
        responses_before = len(live_context.api_responses)
        try:
            try:
                log_result = await hubspot.execute_action(
                    "log_linkedin_messages",
                    {
                        "messages": [{"contact_id": TEST_CONTACT_ID}],
                        "default_message_body": f"Integration test LinkedIn message {os.getpid()} — will be deleted.",
                    },
                    live_context,
                )
            finally:
                for body in live_context.api_responses[responses_before:]:
                    created_ids.update(str(item["id"]) for item in body.get("results", []) if item.get("id"))
            row = log_result.result.data["results"][0]
            communication_id = row["communication_id"]
            assert row["status"] == "logged", row
            assert communication_id

            get_result = await hubspot.execute_action(
                "get_linkedin_message", {"communication_id": communication_id}, live_context
            )
            communication = get_result.result.data["communication"]
            assert communication["properties"]["hs_communication_channel_type"] == "LINKEDIN_MESSAGE"
            contact_ids = [
                str(a["id"]) for a in communication.get("associations", {}).get("contacts", {}).get("results", [])
            ]
            assert str(TEST_CONTACT_ID) in contact_ids

            updated_body = f"Updated integration test LinkedIn message {os.getpid()}."
            update_result = await hubspot.execute_action(
                "update_linkedin_message",
                {"communication_id": communication_id, "message_body": updated_body},
                live_context,
            )
            assert update_result.result.data["success"] is True

            reread = await hubspot.execute_action(
                "get_linkedin_message", {"communication_id": communication_id}, live_context
            )
            assert reread.result.data["communication"]["properties"]["hs_communication_body"] == updated_body

            delete_result = await hubspot.execute_action(
                "delete_linkedin_message", {"communication_id": communication_id}, live_context
            )
            assert delete_result.result.data["success"] is True
            created_ids.discard(communication_id)

            # A deleted (archived) communication is no longer returned by a normal read
            with pytest.raises(HTTPError, match="HTTP 404"):
                await live_context.fetch(
                    f"https://api.hubapi.com/crm/v3/objects/communications/{communication_id}", method="GET"
                )
        finally:
            for created_id in created_ids:
                await hubspot.execute_action("delete_linkedin_message", {"communication_id": created_id}, live_context)


@pytest.mark.destructive
class TestUpsertContacts:
    async def test_creates_then_updates_a_disposable_contact(self, live_context):
        email = f"upsert-{unique_suffix()}@example.com"
        contact_url = f"{CONTACTS_URL}/{email}"
        lookup_params = {"idProperty": "email", "properties": "email,firstname,jobtitle"}
        try:
            created = await hubspot.execute_action(
                "upsert_contacts",
                {"contacts": [{"email": email, "first_name": "Upsert", "properties": {"jobtitle": "First"}}]},
                live_context,
            )
            created_row = created.result.data["results"][0]
            assert created_row["status"] == "created", created_row

            # email is sent only as the upsert key, so check HubSpot still stored it on the new contact
            stored = await live_context.fetch(contact_url, method="GET", params=lookup_params)
            assert str(stored.data["id"]) == created_row["contact_id"]
            assert stored.data["properties"]["email"] == email
            assert stored.data["properties"]["firstname"] == "Upsert"
            assert stored.data["properties"]["jobtitle"] == "First"

            updated = await hubspot.execute_action(
                "upsert_contacts", {"contacts": [{"email": email, "properties": {"jobtitle": "Second"}}]}, live_context
            )
            updated_row = updated.result.data["results"][0]
            assert (updated_row["status"], updated_row["contact_id"]) == ("updated", created_row["contact_id"])

            after = await live_context.fetch(contact_url, method="GET", params=lookup_params)
            assert str(after.data["id"]) == created_row["contact_id"]
            assert after.data["properties"]["jobtitle"] == "Second"
            assert after.data["properties"]["firstname"] == "Upsert"
        finally:
            # Find the contact by email, so it is removed even if the action failed to report its ID
            try:
                found = await live_context.fetch(contact_url, method="GET", params={"idProperty": "email"})
                await delete_contacts(live_context, [str(found.data["id"])])
            except HTTPError:
                # Best-effort cleanup: ignore if the contact does not exist anymore
                # (e.g., upsert/create failed or it was already deleted).
                pass

    async def test_upsert_existing_contact_by_email_updates_property(self, live_context):
        require_contact_email()
        contact_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{TEST_CONTACT_EMAIL}"
        lookup_params = {"idProperty": "email", "properties": "jobtitle"}
        before = await live_context.fetch(contact_url, method="GET", params=lookup_params)
        original_job_title = before.data["properties"].get("jobtitle") or ""
        marker = f"Integration test {os.getpid()}"
        try:
            result = await hubspot.execute_action(
                "upsert_contacts",
                {"contacts": [{"email": TEST_CONTACT_EMAIL, "properties": {"jobtitle": marker}}]},
                live_context,
            )
            row = result.result.data["results"][0]
            assert row["status"] == "updated", row
            assert row["contact_id"] == str(before.data["id"])

            after = await live_context.fetch(contact_url, method="GET", params=lookup_params)
            assert str(after.data["id"]) == str(before.data["id"])
            assert after.data["properties"]["jobtitle"] == marker
        finally:
            restore = await hubspot.execute_action(
                "upsert_contacts",
                {"contacts": [{"email": TEST_CONTACT_EMAIL, "properties": {"jobtitle": original_job_title}}]},
                live_context,
            )
            assert restore.type == ResultType.ACTION, f"Could not restore jobtitle: {restore.result}"
            restored = await live_context.fetch(contact_url, method="GET", params=lookup_params)
            assert (restored.data["properties"].get("jobtitle") or "") == original_job_title


@pytest.mark.destructive
class TestCreateAssociation:
    async def test_links_unlinked_test_contact_and_company(self, live_context):
        require_contact_id()
        require_company_id()
        associations_url = f"https://api.hubapi.com/crm/v4/objects/contacts/{TEST_CONTACT_ID}/associations/companies"

        async def linked_company_ids():
            # Read every page, so an existing link past the first page isn't mistaken for ours and deleted
            company_ids, after = set(), None
            while True:
                params = {"limit": 500, **({"after": after} if after else {})}
                response = await live_context.fetch(associations_url, method="GET", params=params)
                company_ids.update(str(item["toObjectId"]) for item in response.data.get("results", []))
                after = ((response.data.get("paging") or {}).get("next") or {}).get("after")
                if not after:
                    return company_ids

        if str(TEST_COMPANY_ID) in await linked_company_ids():
            pytest.skip("HUBSPOT_TEST_CONTACT_ID is already linked to HUBSPOT_TEST_COMPANY_ID; use an unlinked pair")

        try:
            result = await hubspot.execute_action(
                "create_association",
                {
                    "from_object_type": "contacts",
                    "from_object_id": TEST_CONTACT_ID,
                    "to_object_type": "companies",
                    "to_object_id": TEST_COMPANY_ID,
                },
                live_context,
            )
            assert result.result.data["success"] is True
            assert str(TEST_COMPANY_ID) in await linked_company_ids()
        finally:
            # Remove only the link this test created
            await live_context.fetch(f"{associations_url}/{TEST_COMPANY_ID}", method="DELETE")
