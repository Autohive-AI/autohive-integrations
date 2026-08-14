"""
Live integration tests for the Freshsales integration.

Requires FRESHSALES_API_KEY and FRESHSALES_BUNDLE_ALIAS set in the environment
(see the Freshsales section of the root .env.example).

Run the safe, read-only tests:
    pytest freshsales/tests/test_freshsales_integration.py \
        -m "integration and not destructive" --import-mode=importlib --tb=short

Destructive lifecycle tests create and delete real records in the connected
account (with cleanup in finally blocks). Opt in explicitly with:
    pytest freshsales/tests/test_freshsales_integration.py \
        -m "integration" --import-mode=importlib --tb=short
"""

import time

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from freshsales.freshsales import freshsales

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("FRESHSALES_API_KEY")
    bundle_alias = env_credentials("FRESHSALES_BUNDLE_ALIAS")
    if not api_key:
        pytest.skip("FRESHSALES_API_KEY not set — skipping integration tests")
    if not bundle_alias:
        pytest.skip("FRESHSALES_BUNDLE_ALIAS not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        # Mirrors SDK 2.0.1 ExecutionContext.fetch(): raise RateLimitError on 429
        # and HTTPError on any other non-2xx instead of returning a FetchResponse,
        # so API failures surface as ActionError rather than empty "successes".
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, **kwargs) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", await resp.text())
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    credentials = {"api_key": api_key, "bundle_alias": bundle_alias}
    ctx = make_context(auth={"auth_type": "Custom", "credentials": credentials})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


async def test_list_views_contacts(live_context):
    result = await freshsales.execute_action("list_views", {"entity": "contacts"}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["views"], list)
    assert result.result.data["total"] >= 1


async def test_list_contacts_auto_view(live_context):
    result = await freshsales.execute_action("list_contacts", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["contacts"], list)


async def test_list_accounts_auto_view(live_context):
    result = await freshsales.execute_action("list_accounts", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["accounts"], list)


async def test_list_deals_auto_view(live_context):
    result = await freshsales.execute_action("list_deals", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["deals"], list)


async def test_list_tasks(live_context):
    result = await freshsales.execute_action("list_tasks", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["tasks"], list)


async def test_list_appointments(live_context):
    # No filter: the live API returns all appointments (the filter param is optional).
    unfiltered = await freshsales.execute_action("list_appointments", {}, live_context)
    assert unfiltered.type == ResultType.ACTION
    assert isinstance(unfiltered.result.data["appointments"], list)

    filtered = await freshsales.execute_action("list_appointments", {"filter": "open"}, live_context)
    assert filtered.type == ResultType.ACTION
    assert isinstance(filtered.result.data["appointments"], list)
    assert len(filtered.result.data["appointments"]) <= len(unfiltered.result.data["appointments"])

    # 'completed' is the other provider-recognized filter value (the documented-looking
    # 'complete' is silently ignored) — pin that it stays accepted and filtering.
    completed = await freshsales.execute_action("list_appointments", {"filter": "completed"}, live_context)
    assert completed.type == ResultType.ACTION
    assert isinstance(completed.result.data["appointments"], list)
    assert len(completed.result.data["appointments"]) <= len(unfiltered.result.data["appointments"])


async def test_search(live_context):
    result = await freshsales.execute_action("search", {"query": "a"}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["results"], list)


# ---- Destructive / Lifecycle Tests ----


@pytest.mark.destructive
async def test_contact_lifecycle(live_context):
    """create -> get -> update -> delete contact."""
    uid = int(time.time())
    contact_id = None

    try:
        create = await freshsales.execute_action(
            "create_contact",
            {"first_name": "AH Test", "last_name": f"Contact {uid}", "email": f"ah.test.{uid}@example.com"},
            live_context,
        )
        assert create.type == ResultType.ACTION
        contact_id = create.result.data["contact"]["id"]

        get = await freshsales.execute_action("get_contact", {"contact_id": contact_id}, live_context)
        assert get.result.data["contact"]["id"] == contact_id

        update = await freshsales.execute_action(
            "update_contact", {"contact_id": contact_id, "job_title": "Integration Test"}, live_context
        )
        assert update.result.data["contact"]["job_title"] == "Integration Test"
    finally:
        if contact_id:
            await freshsales.execute_action("delete_contact", {"contact_id": contact_id}, live_context)


@pytest.mark.destructive
async def test_account_and_deal_lifecycle(live_context):
    """create account -> create deal on it -> update deal -> delete both."""
    uid = int(time.time())
    account_id = None
    deal_id = None

    try:
        acc = await freshsales.execute_action("create_account", {"name": f"AH Test Co {uid}"}, live_context)
        assert acc.type == ResultType.ACTION
        account_id = acc.result.data["account"]["id"]

        deal = await freshsales.execute_action(
            "create_deal", {"name": f"AH Test Deal {uid}", "amount": 100, "sales_account_id": account_id}, live_context
        )
        assert deal.type == ResultType.ACTION
        deal_id = deal.result.data["deal"]["id"]

        update = await freshsales.execute_action("update_deal", {"deal_id": deal_id, "amount": 200}, live_context)
        assert update.type == ResultType.ACTION
    finally:
        if deal_id:
            await freshsales.execute_action("delete_deal", {"deal_id": deal_id}, live_context)
        if account_id:
            await freshsales.execute_action("delete_account", {"account_id": account_id}, live_context)


@pytest.mark.destructive
async def test_task_note_appointment_lifecycle(live_context):
    """create a temp contact, attach task/note/appointment, clean everything up."""
    uid = int(time.time())
    contact_id = None
    task_id = None
    note_id = None
    appointment_id = None

    try:
        contact = await freshsales.execute_action(
            "create_contact",
            {"first_name": "AH Test", "last_name": f"Target {uid}", "email": f"ah.target.{uid}@example.com"},
            live_context,
        )
        contact_id = contact.result.data["contact"]["id"]

        task = await freshsales.execute_action(
            "create_task",
            {
                "title": f"AH Test Task {uid}",
                "due_date": "2027-01-01T10:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": contact_id,
            },
            live_context,
        )
        assert task.type == ResultType.ACTION
        task_id = task.result.data["task"]["id"]

        done = await freshsales.execute_action("update_task", {"task_id": task_id, "status": 1}, live_context)
        assert done.type == ResultType.ACTION

        note = await freshsales.execute_action(
            "create_note",
            {"description": f"AH test note {uid}", "targetable_type": "Contact", "targetable_id": contact_id},
            live_context,
        )
        assert note.type == ResultType.ACTION
        note_id = note.result.data["note"]["id"]

        appt = await freshsales.execute_action(
            "create_appointment",
            {
                "title": f"AH Test Appt {uid}",
                "from_date": "2027-01-01T10:00:00Z",
                "end_date": "2027-01-01T11:00:00Z",
                "targetable_type": "Contact",
                "targetable_id": contact_id,
            },
            live_context,
        )
        assert appt.type == ResultType.ACTION
        appointment_id = appt.result.data["appointment"]["id"]
    finally:
        if appointment_id:
            await freshsales.execute_action("delete_appointment", {"appointment_id": appointment_id}, live_context)
        if note_id:
            await freshsales.execute_action("delete_note", {"note_id": note_id}, live_context)
        if task_id:
            await freshsales.execute_action("delete_task", {"task_id": task_id}, live_context)
        if contact_id:
            await freshsales.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
