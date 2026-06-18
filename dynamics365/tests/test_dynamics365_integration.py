import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from dynamics365.dynamics365 import dynamics365

pytestmark = pytest.mark.integration

D365_ORG_URL = os.getenv("D365_ORG_URL", "")
D365_ACCESS_TOKEN = os.getenv("D365_ACCESS_TOKEN", "")
D365_TEST_ACCOUNT_ID = os.getenv("D365_TEST_ACCOUNT_ID", "")
D365_TEST_CONTACT_ID = os.getenv("D365_TEST_CONTACT_ID", "")
D365_TEST_LEAD_ID = os.getenv("D365_TEST_LEAD_ID", "")
D365_TEST_OPPORTUNITY_ID = os.getenv("D365_TEST_OPPORTUNITY_ID", "")


@pytest.fixture
def live_context(make_context):
    if not D365_ORG_URL or not D365_ACCESS_TOKEN:
        pytest.skip("D365_ORG_URL and D365_ACCESS_TOKEN must be set")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, data=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=dict(headers or {}),
            ) as resp:
                if resp.status == 429:
                    raise RateLimitError(f"Rate limited: {resp.status}")
                if resp.status >= 400:
                    text = await resp.text()
                    raise HTTPError(f"HTTP {resp.status}: {text}")
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "org_url": D365_ORG_URL,
            "credentials": {"access_token": D365_ACCESS_TOKEN},
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Accounts ----

@pytest.mark.asyncio
async def test_list_accounts_live(live_context):
    result = await dynamics365.execute_action("list_accounts", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["accounts"], list)
    assert "count" in result.result.data


@pytest.mark.asyncio
async def test_get_account_live(live_context):
    if not D365_TEST_ACCOUNT_ID:
        pytest.skip("D365_TEST_ACCOUNT_ID not set")
    result = await dynamics365.execute_action(
        "get_account", {"account_id": D365_TEST_ACCOUNT_ID}, live_context
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["account"]["accountid"] == D365_TEST_ACCOUNT_ID


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_update_account_live(live_context):
    create_result = await dynamics365.execute_action(
        "create_account",
        {"name": "Autohive Test Account", "email": "test@autohive.com"},
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message

    account = create_result.result.data["account"]
    account_id = account.get("accountid")
    if not account_id:
        pytest.skip("Create did not return accountid — cannot update")

    update_result = await dynamics365.execute_action(
        "update_account",
        {"account_id": account_id, "name": "Autohive Test Account (Updated)"},
        live_context,
    )
    assert update_result.type == ResultType.ACTION, update_result.result.message
    assert update_result.result.data["updated"] is True


# ---- Contacts ----

@pytest.mark.asyncio
async def test_list_contacts_live(live_context):
    result = await dynamics365.execute_action("list_contacts", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["contacts"], list)


@pytest.mark.asyncio
async def test_get_contact_live(live_context):
    if not D365_TEST_CONTACT_ID:
        pytest.skip("D365_TEST_CONTACT_ID not set")
    result = await dynamics365.execute_action(
        "get_contact", {"contact_id": D365_TEST_CONTACT_ID}, live_context
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["contact"]["contactid"] == D365_TEST_CONTACT_ID


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_contact_live(live_context):
    result = await dynamics365.execute_action(
        "create_contact",
        {"first_name": "Test", "last_name": "User", "email": "testuser@autohive.com"},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- Leads ----

@pytest.mark.asyncio
async def test_list_leads_live(live_context):
    result = await dynamics365.execute_action("list_leads", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["leads"], list)


@pytest.mark.asyncio
async def test_get_lead_live(live_context):
    if not D365_TEST_LEAD_ID:
        pytest.skip("D365_TEST_LEAD_ID not set")
    result = await dynamics365.execute_action("get_lead", {"lead_id": D365_TEST_LEAD_ID}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["lead"]["leadid"] == D365_TEST_LEAD_ID


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_lead_live(live_context):
    result = await dynamics365.execute_action(
        "create_lead",
        {"first_name": "Test", "last_name": "Lead", "company": "Test Corp", "email": "lead@test.com"},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- Opportunities ----

@pytest.mark.asyncio
async def test_list_opportunities_live(live_context):
    result = await dynamics365.execute_action("list_opportunities", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["opportunities"], list)


@pytest.mark.asyncio
async def test_get_opportunity_live(live_context):
    if not D365_TEST_OPPORTUNITY_ID:
        pytest.skip("D365_TEST_OPPORTUNITY_ID not set")
    result = await dynamics365.execute_action(
        "get_opportunity", {"opportunity_id": D365_TEST_OPPORTUNITY_ID}, live_context
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["opportunity"]["opportunityid"] == D365_TEST_OPPORTUNITY_ID


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_opportunity_live(live_context):
    result = await dynamics365.execute_action(
        "create_opportunity",
        {"name": "Autohive Test Opportunity", "estimated_value": 10000.0},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


# ---- Tasks ----

@pytest.mark.asyncio
async def test_list_tasks_live(live_context):
    result = await dynamics365.execute_action("list_tasks", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["tasks"], list)


@pytest.mark.asyncio
@pytest.mark.destructive
async def test_create_task_live(live_context):
    result = await dynamics365.execute_action(
        "create_task",
        {"subject": "Autohive Test Task", "priority": "Normal"},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
