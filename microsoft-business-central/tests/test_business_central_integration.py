"""Read-only live tests for the configured environment; destructive writes require Sandbox."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType

from businesscentral import businesscentral

pytestmark = pytest.mark.integration


@pytest.fixture
def live_inputs(env_credentials):
    values = {
        "tenant_id": env_credentials("MICROSOFT_BUSINESS_CENTRAL_TENANT_ID"),
        "environment": env_credentials("MICROSOFT_BUSINESS_CENTRAL_ENVIRONMENT"),
        "company_id": env_credentials("MICROSOFT_BUSINESS_CENTRAL_COMPANY_ID"),
    }
    if not all(values.values()):
        pytest.skip("Business Central test tenant, environment and company variables are required.")
    return values


@pytest.fixture
async def live_context(env_credentials):
    token = env_credentials("MICROSOFT_BUSINESS_CENTRAL_ACCESS_TOKEN")
    if not token:
        pytest.skip("MICROSOFT_BUSINESS_CENTRAL_ACCESS_TOKEN is required.")

    async with ExecutionContext(
        auth={"auth_type": "PlatformOauth2", "credentials": {"access_token": token}},
        request_config={"max_retries": 0, "timeout": 30},
    ) as context:
        yield context


@pytest.mark.destructive
@pytest.mark.parametrize("with_lines", [False, True])
async def test_create_purchase_order(live_context, live_inputs, env_credentials, with_lines):
    vendor = env_credentials("MICROSOFT_BUSINESS_CENTRAL_TEST_VENDOR_NUMBER")
    if not vendor or live_inputs["environment"].lower() != "sandbox":
        pytest.skip("Requires Sandbox and an explicitly configured test vendor; leaves a draft for manual cleanup.")
    inputs = dict(live_inputs, vendor_number=vendor)
    if with_lines:
        item_id = env_credentials("MICROSOFT_BUSINESS_CENTRAL_TEST_ITEM_ID")
        if not item_id:
            pytest.skip("Line creation requires an explicitly configured sandbox test item.")
        inputs["lines"] = [{"item_id": item_id, "quantity": 1}]
    data = await execute("create_purchase_order", inputs, live_context)
    record = data["record"]
    assert record["id"] and record["number"]
    assert record["vendorNumber"] == vendor
    saved = await execute("get_purchase_order", dict(live_inputs, purchase_order_id=record["id"]), live_context)
    assert saved["record"]["id"] == record["id"]
    if with_lines:
        lines = await execute(
            "list_purchase_order_lines", dict(live_inputs, purchase_order_id=record["id"]), live_context
        )
        assert any(line["itemId"] == item_id and line["quantity"] == 1 for line in lines["records"])


@pytest.mark.destructive
async def test_remove_purchase_order(live_context, live_inputs, env_credentials):
    vendor = env_credentials("MICROSOFT_BUSINESS_CENTRAL_TEST_VENDOR_NUMBER")
    if not vendor or live_inputs["environment"].lower() != "sandbox":
        pytest.skip("Requires Sandbox and an explicitly configured test vendor.")
    created = await execute("create_purchase_order", dict(live_inputs, vendor_number=vendor), live_context)
    order_id = created["record"]["id"]
    inputs = dict(live_inputs, purchase_order_id=order_id)
    saved = await execute("get_purchase_order", inputs, live_context)
    removed = await execute("remove_purchase_order", dict(inputs, etag=saved["record"]["@odata.etag"]), live_context)
    assert removed == {"purchase_order_id": order_id, "deleted": True}
    missing = await businesscentral.execute_action("get_purchase_order", inputs, live_context)
    assert missing.type == ResultType.ACTION_ERROR
    assert "not found" in missing.result.message


async def execute(action, inputs, context):
    result = await businesscentral.execute_action(action, inputs, context)
    assert result.type == ResultType.ACTION, f"{action} failed; check test environment access and inputs."
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
    "list_customers",
    "list_sales_invoices",
    "list_sales_credit_memos",
    "list_accounts",
    "list_general_ledger_entries",
    "list_dimensions",
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
        ("get_customer", "list_customers", "customer_id"),
        ("get_sales_invoice", "list_sales_invoices", "sales_invoice_id"),
        ("list_sales_invoice_lines", "list_sales_invoices", "sales_invoice_id"),
        ("list_dimension_values", "list_dimensions", "dimension_id"),
        ("list_general_ledger_entry_dimensions", "list_general_ledger_entries", "general_ledger_entry_id"),
        ("get_receivables_aging", "list_customers", "customer_id"),
        ("get_payables_aging", "list_vendors", "vendor_id"),
    ],
)
async def test_document_round_trip(live_context, live_inputs, action, parent, id_key):
    parents = await execute(parent, dict(live_inputs, page_size=1), live_context)
    if not parents["records"]:
        pytest.skip(f"Test company needs a record for {parent}.")
    record_id = parents["records"][0]["id"]
    data = await execute(action, dict(live_inputs, **{id_key: record_id}), live_context)
    if action == "get_receivables_aging":
        assert data["record"]["customerId"] == record_id
        assert "agedAsOfDate" in data["record"] and "currencyCode" in data["record"]
    elif action == "get_payables_aging":
        assert data["record"]["vendorId"] == record_id
        assert "agedAsOfDate" in data["record"] and "currencyCode" in data["record"]
    elif action.startswith("get_"):
        assert data["record"]["id"] == record_id
    elif action == "list_dimension_values":
        assert all(row["dimensionId"] == record_id for row in data["records"])
    elif action == "list_general_ledger_entry_dimensions":
        assert all(row["parentId"] == record_id for row in data["records"])
    else:
        assert all(row["documentId"] == record_id for row in data["records"])


@pytest.mark.parametrize("action", ["estimate_reorder_cost", "forecast_stock"])
async def test_inventory_planning(live_context, live_inputs, action):
    items = await execute("list_items", dict(live_inputs, page_size=100), live_context)
    item = next((row for row in items["records"] if row.get("type") == "Inventory"), None)
    if not item:
        pytest.skip("Test company needs an Inventory item in the first item page.")
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


@pytest.mark.parametrize("action", ["get_trial_balance", "get_income_statement"])
async def test_native_financial_reports(live_context, live_inputs, action):
    today = datetime.now(timezone.utc).date()
    inputs = dict(live_inputs, start_date=str(today - timedelta(days=30)), end_date=str(today), page_size=2)
    data = await execute(action, inputs, live_context)
    assert isinstance(data["records"], list)
    assert data["count"] == len(data["records"])
    if data["next_link"]:
        await execute(action, dict(inputs, next_link=data["next_link"]), live_context)


async def test_overdue_open_invoice_filter(live_context, live_inputs):
    cutoff = str(datetime.now(timezone.utc).date())
    data = await execute(
        "list_sales_invoices", dict(live_inputs, outstanding_only=True, due_before=cutoff, page_size=2), live_context
    )
    assert all(
        row["status"] == "Open" and Decimal(str(row["remainingAmount"])) > 0 and row["dueDate"] < cutoff
        for row in data["records"]
    )
