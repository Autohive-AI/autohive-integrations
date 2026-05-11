"""
Live integration tests for the Freshdesk integration.

Requires FRESHDESK_API_KEY and FRESHDESK_DOMAIN set in the environment or
project .env.

Credential extraction recipe:
1. In Freshdesk, open Profile Settings > View API key and copy the API key to
   FRESHDESK_API_KEY.
2. Copy the Freshdesk subdomain to FRESHDESK_DOMAIN. For example, use
   "acme" for https://acme.freshdesk.com.
3. Add both values to the project .env file or export them in your shell before
   running these tests.

Safe read-only run:
    pytest freshdesk/tests/test_freshdesk_integration.py -m "integration and not destructive"
"""

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from freshdesk import freshdesk

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
            async with session.request(
                method,
                url,
                json=json,
                headers=headers,
                params=params,
                **kwargs,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"api_key": api_key, "domain": domain})
    ctx.fetch.side_effect = real_fetch
    return ctx


async def _first_ticket_id(live_context):
    result = await freshdesk.execute_action("list_tickets", {"per_page": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Freshdesk tickets: {result.result.message}")

    tickets = result.result.data["tickets"]
    if not tickets:
        pytest.skip("No Freshdesk tickets available for ticket-scoped live tests")
    return tickets[0]["id"]


async def _first_company_id(live_context):
    result = await freshdesk.execute_action("list_companies", {"per_page": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Freshdesk companies: {result.result.message}")

    companies = result.result.data["companies"]
    if not companies:
        pytest.skip("No Freshdesk companies available for company-scoped live tests")
    return companies[0]["id"]


async def _first_contact_id(live_context):
    result = await freshdesk.execute_action("list_contacts", {"per_page": 5}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"Unable to list Freshdesk contacts: {result.result.message}")

    contacts = result.result.data["contacts"]
    if not contacts:
        pytest.skip("No Freshdesk contacts available for contact-scoped live tests")
    return contacts[0]["id"]


async def test_list_companies_returns_companies(live_context):
    result = await freshdesk.execute_action("list_companies", {"per_page": 5}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "companies" in data
    assert isinstance(data["companies"], list)


async def test_list_tickets_returns_tickets(live_context):
    result = await freshdesk.execute_action("list_tickets", {"per_page": 5}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "tickets" in data
    assert isinstance(data["tickets"], list)


async def test_list_contacts_returns_contacts(live_context):
    result = await freshdesk.execute_action("list_contacts", {"per_page": 5}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "contacts" in data
    assert isinstance(data["contacts"], list)


async def test_get_company_returns_company_shape(live_context):
    company_id = await _first_company_id(live_context)

    result = await freshdesk.execute_action("get_company", {"company_id": company_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "company" in data
    assert data["company"]["id"] == company_id


async def test_get_ticket_returns_ticket_shape(live_context):
    ticket_id = await _first_ticket_id(live_context)

    result = await freshdesk.execute_action("get_ticket", {"ticket_id": ticket_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "ticket" in data
    assert data["ticket"]["id"] == ticket_id


async def test_get_contact_returns_contact_shape(live_context):
    contact_id = await _first_contact_id(live_context)

    result = await freshdesk.execute_action("get_contact", {"contact_id": contact_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "contact" in data
    assert data["contact"]["id"] == contact_id


async def test_list_conversations_returns_conversations(live_context):
    ticket_id = await _first_ticket_id(live_context)

    result = await freshdesk.execute_action("list_conversations", {"ticket_id": ticket_id}, live_context)

    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "conversations" in data
    assert isinstance(data["conversations"], list)
