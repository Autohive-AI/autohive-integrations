"""
Integration tests for the Xero integration (read-only actions).

Requires XERO_ACCESS_TOKEN and XERO_TENANT_ID set in environment.

Run with:
    pytest xero/tests/test_xero_integration.py -m integration
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

os.chdir(_parent)
_spec = importlib.util.spec_from_file_location("xero_mod", os.path.join(_parent, "xero.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

xero = _mod.xero

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("XERO_ACCESS_TOKEN", "")
TENANT_ID = os.environ.get("XERO_TENANT_ID", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("XERO_ACCESS_TOKEN not set — skipping integration tests")
    if not TENANT_ID:
        pytest.skip("XERO_TENANT_ID not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
        if headers:
            merged_headers.update(headers)
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": API_KEY, "tenant_id": TENANT_ID}}  # nosec B105
    return ctx


class TestGetAvailableConnections:
    async def test_returns_companies(self, live_context):
        result = await xero.execute_action("get_available_connections", {}, live_context)

        data = result.result.data
        assert "companies" in data
        assert isinstance(data["companies"], list)


class TestGetInvoices:
    async def test_returns_invoices(self, live_context):
        inputs = {"tenant_id": TENANT_ID, "page": 1}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        assert isinstance(data["Invoices"], list)

    async def test_filter_by_status(self, live_context):
        inputs = {"tenant_id": TENANT_ID, "where": 'Status=="AUTHORISED"'}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        for invoice in data["Invoices"]:
            assert invoice["Status"] == "AUTHORISED"


class TestGetAccounts:
    async def test_returns_accounts(self, live_context):
        inputs = {"tenant_id": TENANT_ID}
        result = await xero.execute_action("get_accounts", inputs, live_context)

        data = result.result.data
        assert "Accounts" in data
        assert isinstance(data["Accounts"], list)

    async def test_accounts_have_required_fields(self, live_context):
        inputs = {"tenant_id": TENANT_ID}
        result = await xero.execute_action("get_accounts", inputs, live_context)

        accounts = result.result.data.get("Accounts", [])
        if not accounts:
            pytest.skip("No accounts in Xero org")

        account = accounts[0]
        assert "AccountID" in account
        assert "Name" in account
        assert "Type" in account


class TestGetPurchaseOrders:
    async def test_returns_purchase_orders(self, live_context):
        inputs = {"tenant_id": TENANT_ID}
        result = await xero.execute_action("get_purchase_orders", inputs, live_context)

        data = result.result.data
        assert "PurchaseOrders" in data
        assert isinstance(data["PurchaseOrders"], list)
