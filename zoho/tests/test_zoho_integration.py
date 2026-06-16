"""
End-to-end integration tests for the Zoho CRM integration.

These tests call the real Zoho CRM API (v8) and require a valid OAuth access
token in the ZOHO_ACCESS_TOKEN environment variable. The datacenter domain is
read from ZOHO_API_DOMAIN (defaults to https://www.zohoapis.com).

Run read-only tests:
    pytest zoho/tests/test_zoho_integration.py -m "integration and not destructive"

Run destructive tests (creates/updates/deletes real CRM records):
    pytest zoho/tests/test_zoho_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import importlib.util
import os
import sys
import time

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
# zoho ships an __init__.py that shadows zoho.py, so load the source by file path.
_spec = importlib.util.spec_from_file_location("zoho_integration_mod", os.path.join(_parent, "zoho.py"))
zoho_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zoho_mod)

zoho = zoho_mod.zoho

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("ZOHO_ACCESS_TOKEN", "")
API_DOMAIN = os.environ.get("ZOHO_API_DOMAIN", "https://www.zohoapis.com")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("ZOHO_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=headers or {}) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                # Mirror the SDK contract: context.fetch() raises on non-2xx so the
                # action's try/except surfaces an ActionError. Returning a FetchResponse
                # for an error status would let an error body masquerade as success data.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN, "api_domain": API_DOMAIN}}
    return ctx


def _assert_ok(result):
    assert result.type != ResultType.ACTION_ERROR, getattr(result.result, "message", "")
    return result.result.data


# =============================================================================
# READ-ONLY — list / search / COQL across modules
# =============================================================================


class TestListReadOnly:
    @pytest.mark.parametrize(
        "action,key",
        [
            ("list_contacts", "contacts"),
            ("list_accounts", "accounts"),
            ("list_deals", "deals"),
            ("list_leads", "leads"),
            ("list_tasks", "tasks"),
            ("list_events", "events"),
            ("list_calls", "calls"),
        ],
    )
    async def test_list_returns_collection(self, live_context, action, key):
        result = await zoho.execute_action(action, {"page": 1, "per_page": 5}, live_context)
        data = _assert_ok(result)
        assert isinstance(data[key], list)
        assert "info" in data


class TestSearchReadOnly:
    async def test_search_contacts_word(self, live_context):
        result = await zoho.execute_action(
            "search_contacts", {"search_type": "word", "word": "a", "per_page": 5}, live_context
        )
        # A search with no matches returns 204 (raised as HTTPError) in Zoho; either a
        # clean empty result or an ActionError is acceptable, but never a crash.
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"No matching contacts / search unavailable: {result.result.message}")
        assert isinstance(result.result.data["contacts"], list)


class TestCOQL:
    async def test_simple_query(self, live_context):
        result = await zoho.execute_action(
            "execute_coql_query",
            {"select_query": "SELECT id FROM Contacts WHERE id is not null LIMIT 2"},
            live_context,
        )
        if result.type == ResultType.ACTION_ERROR:
            pytest.skip(f"COQL unavailable on this org: {result.result.message}")
        assert isinstance(result.result.data["data"], list)


class TestGetChainedFromList:
    async def test_get_contact_by_listed_id(self, live_context):
        listed = await zoho.execute_action("list_contacts", {"per_page": 1}, live_context)
        contacts = _assert_ok(listed)["contacts"]
        if not contacts:
            pytest.skip("No contacts in this CRM to fetch")
        contact_id = contacts[0]["id"]
        result = await zoho.execute_action("get_contact", {"contact_id": contact_id}, live_context)
        data = _assert_ok(result)
        assert data["contact"]["id"] == contact_id

    async def test_get_missing_contact_is_action_error(self, live_context):
        # A non-existent ID must surface as a clean ActionError, not a crash.
        result = await zoho.execute_action("get_contact", {"contact_id": "0000000000000000001"}, live_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# DESTRUCTIVE — full create/update/note/delete lifecycle (writes to real CRM)
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestContactLifecycle:
    async def test_create_update_note_delete(self, live_context):
        ts = int(time.time())
        # create
        create = await zoho.execute_action(
            "create_contact",
            {"Last_Name": "ZohoIT", "First_Name": "Temp", "Email": f"zoho.it.{ts}@example.com"},
            live_context,
        )
        contact_id = _assert_ok(create)["contact"]["id"]
        assert contact_id

        # get
        got = await zoho.execute_action("get_contact", {"contact_id": contact_id}, live_context)
        assert _assert_ok(got)["contact"]["id"] == contact_id

        # update
        updated = await zoho.execute_action(
            "update_contact", {"contact_id": contact_id, "Title": "Updated by integration test"}, live_context
        )
        assert _assert_ok(updated)["contact"]["id"] == contact_id

        # note on the contact
        note = await zoho.execute_action(
            "create_note",
            {"module": "Contacts", "record_id": contact_id, "Note_Content": "integration test note"},
            live_context,
        )
        note_id = _assert_ok(note)["note"]["id"]
        assert note_id

        notes = await zoho.execute_action(
            "get_contact_notes", {"module": "Contacts", "record_id": contact_id}, live_context
        )
        assert isinstance(_assert_ok(notes)["notes"], list)

        # delete the note, then the contact
        del_note = await zoho.execute_action("delete_note", {"note_id": note_id}, live_context)
        _assert_ok(del_note)

        deleted = await zoho.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
        assert _assert_ok(deleted)["details"]["id"] == contact_id


@pytest.mark.destructive
class TestDealLifecycle:
    async def test_create_update_delete(self, live_context):
        ts = int(time.time())
        create = await zoho.execute_action(
            "create_deal",
            {"Deal_Name": f"IT Deal {ts}", "Stage": "Qualification", "Amount": 1000},
            live_context,
        )
        deal_id = _assert_ok(create)["deal"]["id"]
        assert deal_id

        updated = await zoho.execute_action("update_deal", {"deal_id": deal_id, "Amount": 2000}, live_context)
        assert _assert_ok(updated)["deal"]["id"] == deal_id

        deleted = await zoho.execute_action("delete_deal", {"deal_id": deal_id}, live_context)
        assert _assert_ok(deleted)["details"]["id"] == deal_id
