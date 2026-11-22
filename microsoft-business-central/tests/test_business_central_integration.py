"""Read-only sandbox tests. No customer data or credentials are committed."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from business_central import business_central

pytestmark = pytest.mark.integration


@pytest.fixture
def live_inputs(env_credentials):
    values = {
        "tenant_id": env_credentials("MICROSOFT_BUSINESS_CENTRAL_TENANT_ID"),
        "environment": env_credentials("MICROSOFT_BUSINESS_CENTRAL_ENVIRONMENT"),
        "company_id": env_credentials("MICROSOFT_BUSINESS_CENTRAL_COMPANY_ID"),
    }
    if not all(values.values()):
        pytest.skip("Business Central sandbox tenant, environment and company variables are required.")
    return values


@pytest.fixture
def live_context(env_credentials):
    token = env_credentials("MICROSOFT_BUSINESS_CENTRAL_ACCESS_TOKEN")
    if not token:
        pytest.skip("MICROSOFT_BUSINESS_CENTRAL_ACCESS_TOKEN is required.")

    async def real_fetch(url, *, method="GET", headers=None, params=None):
        request_headers = dict(headers or {}, Authorization=f"Bearer {token}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                method, url, headers=request_headers, params=params, allow_redirects=False
            ) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    context = MagicMock()
    context.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


async def execute(action, inputs, context):
    result = await business_central.execute_action(action, inputs, context)
    assert result.type == ResultType.ACTION, f"{action} failed; check sandbox access and inputs."
    return result.result.data


SIMPLE_LISTS = [
    "list_companies",
    "get_company_information",
    "list_items",
    "list_locations",
    "list_item_variants",
    "list_units_of_measure",
    "list_vendors",
    "list_item_ledger_entries",
    "list_purchase_orders",
    "list_sales_orders",
    "list_purchase_invoices",
]


@pytest.mark.parametrize("action", SIMPLE_LISTS)
async def test_read_collection(live_context, live_inputs, action):
    inputs = dict(live_inputs, page_size=2)
    if action == "list_companies":
        inputs.pop("company_id")
    data = await execute(action, inputs, live_context)
    assert isinstance(data["records"], list)
    assert data["count"] == len(data["records"])
    assert data["count"] <= 2
    if data["next_link"]:
        await execute(action, dict(inputs, next_link=data["next_link"]), live_context)


@pytest.mark.parametrize(
    "action,parent,id_key",
    [
        ("get_item", "list_items", "item_id"),
        ("get_purchase_order", "list_purchase_orders", "purchase_order_id"),
        ("get_sales_order", "list_sales_orders", "sales_order_id"),
        ("list_purchase_order_lines", "list_purchase_orders", "purchase_order_id"),
        ("list_sales_order_lines", "list_sales_orders", "sales_order_id"),
        ("list_purchase_invoice_lines", "list_purchase_invoices", "purchase_invoice_id"),
    ],
)
async def test_document_round_trip(live_context, live_inputs, action, parent, id_key):
    parents = await execute(parent, dict(live_inputs, page_size=1), live_context)
    if not parents["records"]:
        pytest.skip(f"Sandbox needs a record for {parent}.")
    record_id = parents["records"][0]["id"]
    data = await execute(action, dict(live_inputs, **{id_key: record_id}), live_context)
    if action.startswith("get_"):
        assert data["record"]["id"] == record_id
    else:
        assert all(row["documentId"] == record_id for row in data["records"])


@pytest.mark.parametrize("action", ["estimate_reorder_cost", "forecast_stock"])
async def test_inventory_planning(live_context, live_inputs, action):
    items = await execute("list_items", dict(live_inputs, page_size=100), live_context)
    item = next((row for row in items["records"] if row.get("type") == "Inventory"), None)
    if not item:
        pytest.skip("Sandbox needs an Inventory item in the first item page.")
    inputs = dict(live_inputs, item_id=item["id"])
    if action == "forecast_stock":
        today = datetime.now(timezone.utc).date()
        inputs.update(
            start_date=str(today - timedelta(days=30)), end_date=str(today - timedelta(days=1)), forecast_days=7
        )
    else:
        inputs["quantity"] = 3
    data = await execute(action, inputs, live_context)
    assert data["item_id"] == item["id"]
    assert data["limitations"]
