"""
Live integration tests for the Xero integration (read-only actions).

Requires XERO_ACCESS_TOKEN and XERO_TENANT_ID set in environment.

Safe read-only run:
    pytest xero/tests/test_xero_integration.py -m "integration and not destructive"

This file intentionally avoids attachment-content smoke tests because that
action reads from the SDK-managed aiohttp session on the execution context.
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse

from xero import xero

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("XERO_ACCESS_TOKEN")
    tenant_id = env_credentials("XERO_TENANT_ID")
    if not access_token:
        pytest.skip("XERO_ACCESS_TOKEN not set — skipping integration tests")
    if not tenant_id:
        pytest.skip("XERO_TENANT_ID not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        if headers:
            merged_headers.update(headers)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                headers=merged_headers,
                params=params,
                **kwargs,
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError:
                    data = {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {
                "access_token": access_token,
                "tenant_id": tenant_id,
            },
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.tenant_id = tenant_id
    return ctx


@pytest.fixture
def tenant_id(env_credentials):
    tenant_id = env_credentials("XERO_TENANT_ID")
    if not tenant_id:
        pytest.skip("XERO_TENANT_ID not set — skipping integration tests")
    return tenant_id


class TestGetAvailableConnections:
    async def test_returns_companies(self, live_context):
        result = await xero.execute_action("get_available_connections", {}, live_context)

        data = result.result.data
        assert "companies" in data
        assert isinstance(data["companies"], list)


class TestGetInvoices:
    async def test_returns_invoices(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id, "page": 1}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        assert isinstance(data["Invoices"], list)

    async def test_filter_by_status(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id, "where": 'Status=="AUTHORISED"'}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        for invoice in data["Invoices"]:
            assert invoice["Status"] == "AUTHORISED"


class TestGetAccounts:
    async def test_returns_accounts(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id}
        result = await xero.execute_action("get_accounts", inputs, live_context)

        data = result.result.data
        assert "Accounts" in data
        assert isinstance(data["Accounts"], list)

    async def test_accounts_have_required_fields(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id}
        result = await xero.execute_action("get_accounts", inputs, live_context)

        accounts = result.result.data.get("Accounts", [])
        if not accounts:
            pytest.skip("No accounts in Xero org")

        account = accounts[0]
        assert "AccountID" in account
        assert "Name" in account
        assert "Type" in account


class TestGetPurchaseOrders:
    async def test_returns_purchase_orders(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id}
        result = await xero.execute_action("get_purchase_orders", inputs, live_context)

        data = result.result.data
        assert "PurchaseOrders" in data
        assert isinstance(data["PurchaseOrders"], list)
