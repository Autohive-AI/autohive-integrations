"""
Live integration tests for the Freshdesk integration.

Requires FRESHDESK_API_KEY and FRESHDESK_DOMAIN set in the environment.

Run with:
    pytest freshdesk/tests/test_freshdesk_integration.py -m "integration" --import-mode=importlib --tb=short
"""

import time

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from freshdesk.freshdesk import freshdesk

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("FRESHDESK_API_KEY")
    domain = env_credentials("FRESHDESK_DOMAIN")
    if not api_key:
        pytest.skip("FRESHDESK_API_KEY not set — skipping integration tests")
    if not domain:
        pytest.skip("FRESHDESK_DOMAIN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, **kwargs) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"api_key": api_key, "domain": domain})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


async def test_list_companies(live_context):
    result = await freshdesk.execute_action("list_companies", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "companies" in result.result.data
    assert isinstance(result.result.data["companies"], list)


async def test_list_tickets(live_context):
    result = await freshdesk.execute_action("list_tickets", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "tickets" in result.result.data
    assert isinstance(result.result.data["tickets"], list)


async def test_list_contacts(live_context):
    result = await freshdesk.execute_action("list_contacts", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "contacts" in result.result.data
    assert isinstance(result.result.data["contacts"], list)


async def test_search_companies(live_context):
    result = await freshdesk.execute_action("search_companies", {"name": "a"}, live_context)
    assert result.type == ResultType.ACTION
    assert "companies" in result.result.data


async def test_search_contacts(live_context):
    result = await freshdesk.execute_action("search_contacts", {"term": "a"}, live_context)
    assert result.type == ResultType.ACTION
    assert "contacts" in result.result.data


# ---- Destructive / Lifecycle Tests ----


@pytest.mark.destructive
async def test_company_lifecycle(live_context):
    """create -> get -> update -> delete company."""
    uid = int(time.time())

    # Create
    create = await freshdesk.execute_action(
        "create_company",
        {"name": f"AH Test Co {uid}", "description": "Created by integration test"},
        live_context,
    )
    assert create.type == ResultType.ACTION
    company_id = create.result.data["company"]["id"]
    assert company_id

    # Get
    get = await freshdesk.execute_action("get_company", {"company_id": company_id}, live_context)
    assert get.type == ResultType.ACTION
    assert get.result.data["company"]["id"] == company_id

    # Update
    update = await freshdesk.execute_action(
        "update_company",
        {"company_id": company_id, "description": f"Updated at {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["company"]["id"] == company_id

    # Delete
    delete = await freshdesk.execute_action("delete_company", {"company_id": company_id}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_contact_lifecycle(live_context):
    """create -> get -> update -> delete contact."""
    uid = int(time.time())

    # Create
    create = await freshdesk.execute_action(
        "create_contact",
        {"name": f"AH Test Contact {uid}", "email": f"ah-test-{uid}@example.com"},
        live_context,
    )
    assert create.type == ResultType.ACTION
    contact_id = create.result.data["contact"]["id"]
    assert contact_id

    # Get
    get = await freshdesk.execute_action("get_contact", {"contact_id": contact_id}, live_context)
    assert get.type == ResultType.ACTION
    assert get.result.data["contact"]["id"] == contact_id

    # Update
    update = await freshdesk.execute_action(
        "update_contact",
        {"contact_id": contact_id, "job_title": "Test Engineer"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["contact"]["id"] == contact_id

    # Delete (soft delete)
    delete = await freshdesk.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_ticket_lifecycle(live_context):
    """create -> get -> update -> list_conversations -> create_note -> create_reply -> delete ticket."""
    uid = int(time.time())

    # Create
    create = await freshdesk.execute_action(
        "create_ticket",
        {
            "subject": f"AH Test Ticket {uid}",
            "email": f"ah-test-{uid}@example.com",
            "description": "Integration test ticket",
            "priority": 1,
            "status": 2,
        },
        live_context,
    )
    assert create.type == ResultType.ACTION
    ticket_id = create.result.data["ticket"]["id"]
    assert ticket_id

    # Get
    get = await freshdesk.execute_action("get_ticket", {"ticket_id": ticket_id}, live_context)
    assert get.type == ResultType.ACTION
    assert get.result.data["ticket"]["id"] == ticket_id

    # Update
    update = await freshdesk.execute_action(
        "update_ticket",
        {"ticket_id": ticket_id, "priority": 2, "subject": f"AH Updated Ticket {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["ticket"]["id"] == ticket_id

    # List conversations
    convs = await freshdesk.execute_action("list_conversations", {"ticket_id": ticket_id}, live_context)
    assert convs.type == ResultType.ACTION
    assert "conversations" in convs.result.data

    # Create note
    note = await freshdesk.execute_action(
        "create_note",
        {"ticket_id": ticket_id, "body": f"Test note at {uid}"},
        live_context,
    )
    assert note.type == ResultType.ACTION
    assert "conversation" in note.result.data

    # Create reply
    reply = await freshdesk.execute_action(
        "create_reply",
        {"ticket_id": ticket_id, "body": f"Test reply at {uid}"},
        live_context,
    )
    assert reply.type == ResultType.ACTION
    assert "conversation" in reply.result.data

    # Delete
    delete = await freshdesk.execute_action("delete_ticket", {"ticket_id": ticket_id}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True
