"""Unit tests for the Count integration."""

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from unittest.mock import AsyncMock

from count.count import count


def make_response(data, status=200):
    return FetchResponse(
        status=status,
        headers={},
        data={"status": "success", "message": "ok", "data": data},
    )


@pytest.fixture
def ctx(mock_context):
    return mock_context


@pytest.mark.asyncio
async def test_list_accounts(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "acc-1", "name": "Cash"}]))
    result = await count.execute_action("list_accounts", {}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True
    assert isinstance(result.result.data["accounts"], list)


@pytest.mark.asyncio
async def test_create_account(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "acc-1", "name": "Revenue"}))
    result = await count.execute_action("create_account", {"name": "Revenue", "type": "income"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["account"]["uuid"] == "acc-1"


@pytest.mark.asyncio
async def test_update_account(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "acc-1", "name": "Updated"}))
    result = await count.execute_action("update_account", {"account_uuid": "acc-1", "name": "Updated"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_account(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_account", {"account_uuid": "acc-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_customers(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "cust-1", "name": "Acme"}]))
    result = await count.execute_action("list_customers", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["customers"], list)


@pytest.mark.asyncio
async def test_get_customer(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "cust-1", "name": "Acme"}))
    result = await count.execute_action("get_customer", {"customer_uuid": "cust-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["customer"]["uuid"] == "cust-1"


@pytest.mark.asyncio
async def test_find_customer_by_email(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "cust-1", "email": "test@example.com"}))
    result = await count.execute_action("find_customer_by_email", {"email": "test@example.com"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_create_customer(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "cust-2", "name": "New Corp"}))
    result = await count.execute_action("create_customer", {"name": "New Corp", "email": "new@corp.com"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["customer"]["uuid"] == "cust-2"


@pytest.mark.asyncio
async def test_update_customer(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "cust-1"}))
    result = await count.execute_action("update_customer", {"customer_uuid": "cust-1", "name": "Acme Updated"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_customer(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_customer", {"customer_uuid": "cust-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_vendors(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "ven-1", "name": "Supplier Co"}]))
    result = await count.execute_action("list_vendors", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["vendors"], list)


@pytest.mark.asyncio
async def test_create_vendor(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "ven-2", "name": "New Vendor"}))
    result = await count.execute_action("create_vendor", {"name": "New Vendor"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["vendor"]["uuid"] == "ven-2"


@pytest.mark.asyncio
async def test_update_vendor(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "ven-1"}))
    result = await count.execute_action("update_vendor", {"vendor_uuid": "ven-1", "name": "Updated Vendor"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_vendor(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_vendor", {"vendor_uuid": "ven-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_products(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "prod-1", "name": "Widget"}]))
    result = await count.execute_action("list_products", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["products"], list)


@pytest.mark.asyncio
async def test_get_product(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "prod-1", "name": "Widget"}))
    result = await count.execute_action("get_product", {"product_uuid": "prod-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["product"]["uuid"] == "prod-1"


@pytest.mark.asyncio
async def test_find_product_by_name(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "prod-1", "name": "Widget"}))
    result = await count.execute_action("find_product_by_name", {"name": "Widget"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_create_product(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "prod-2", "name": "Gadget"}))
    result = await count.execute_action("create_product", {"name": "Gadget", "price": 99.99}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["product"]["uuid"] == "prod-2"


@pytest.mark.asyncio
async def test_update_product(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "prod-1"}))
    result = await count.execute_action("update_product", {"product_uuid": "prod-1", "price": 49.99}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_product(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_product", {"product_uuid": "prod-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_transactions(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "txn-1", "amount": 100}]))
    result = await count.execute_action("list_transactions", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["transactions"], list)


@pytest.mark.asyncio
async def test_create_transaction(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "txn-2", "amount": 500}))
    result = await count.execute_action(
        "create_transaction",
        {"date": "2026-01-01", "amount": 500, "accountUuid": "acc-1"},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["transaction"]["uuid"] == "txn-2"


@pytest.mark.asyncio
async def test_update_transaction(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "txn-1"}))
    result = await count.execute_action("update_transaction", {"transaction_uuid": "txn-1", "amount": 600}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_transaction(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_transaction", {"transaction_uuid": "txn-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_get_invoice(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "inv-1", "invoiceNumber": "INV-001"}))
    result = await count.execute_action("get_invoice", {"invoice_uuid": "inv-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["invoice"]["uuid"] == "inv-1"


@pytest.mark.asyncio
async def test_create_invoice(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "inv-2", "invoiceNumber": "INV-002"}))
    result = await count.execute_action(
        "create_invoice",
        {
            "customerUuid": "cust-1",
            "invoiceNumber": "INV-002",
            "date": "2026-01-01",
            "dueDate": "2026-01-31",
            "invoiceType": "invoice",
            "products": [{"productUuid": "prod-1", "quantity": 1, "price": 100}],
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["invoice"]["uuid"] == "inv-2"


@pytest.mark.asyncio
async def test_update_invoice(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "inv-1"}))
    result = await count.execute_action("update_invoice", {"invoice_uuid": "inv-1", "notes": "Updated"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_invoice(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_invoice", {"invoice_uuid": "inv-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_create_bill(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "bill-1"}))
    result = await count.execute_action(
        "create_bill",
        {
            "vendorUuid": "ven-1",
            "date": "2026-01-01",
            "dueDate": "2026-01-31",
            "products": [{"productUuid": "prod-1", "quantity": 2, "price": 50}],
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["bill"]["uuid"] == "bill-1"


@pytest.mark.asyncio
async def test_update_bill(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "bill-1"}))
    result = await count.execute_action("update_bill", {"bill_uuid": "bill-1", "notes": "Revised"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_bill(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_bill", {"bill_uuid": "bill-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_approve_bill(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "bill-1", "status": "approved"}))
    result = await count.execute_action("approve_bill", {"bill_uuid": "bill-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_list_journal_entries(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "je-1"}]))
    result = await count.execute_action("list_journal_entries", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["journal_entries"], list)


@pytest.mark.asyncio
async def test_create_journal_entry(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "je-2"}))
    result = await count.execute_action(
        "create_journal_entry",
        {
            "date": "2026-01-01",
            "lines": [
                {"accountUuid": "acc-1", "amount": 100, "type": "debit"},
                {"accountUuid": "acc-2", "amount": 100, "type": "credit"},
            ],
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["journal_entry"]["uuid"] == "je-2"


@pytest.mark.asyncio
async def test_update_journal_entry(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "je-1"}))
    result = await count.execute_action(
        "update_journal_entry",
        {"journal_entry_uuid": "je-1", "description": "Updated"},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_journal_entry(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_journal_entry", {"journal_entry_uuid": "je-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_tags(ctx):
    ctx.fetch = AsyncMock(return_value=make_response([{"uuid": "tag-1", "name": "Q1"}]))
    result = await count.execute_action("list_tags", {}, ctx)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["tags"], list)


@pytest.mark.asyncio
async def test_create_tag(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "tag-2", "name": "Q2"}))
    result = await count.execute_action("create_tag", {"name": "Q2"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["tag"]["uuid"] == "tag-2"


@pytest.mark.asyncio
async def test_update_tag(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"uuid": "tag-1"}))
    result = await count.execute_action("update_tag", {"tag_uuid": "tag-1", "name": "Q1 Updated"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True


@pytest.mark.asyncio
async def test_delete_tag(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({}))
    result = await count.execute_action("delete_tag", {"tag_uuid": "tag-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_get_trial_balance(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"accounts": [], "totalDebits": 0, "totalCredits": 0}))
    result = await count.execute_action("get_trial_balance", {}, ctx)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


@pytest.mark.asyncio
async def test_get_balance_sheet(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"assets": [], "liabilities": [], "equity": []}))
    result = await count.execute_action("get_balance_sheet", {}, ctx)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


@pytest.mark.asyncio
async def test_get_profit_and_loss(ctx):
    ctx.fetch = AsyncMock(return_value=make_response({"income": [], "expenses": [], "netProfit": 0}))
    result = await count.execute_action("get_profit_and_loss", {}, ctx)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


@pytest.mark.asyncio
async def test_api_error_returns_false(ctx):
    ctx.fetch = AsyncMock(
        return_value=FetchResponse(status=401, headers={}, data={"message": "Unauthorized", "status": "error"})
    )
    result = await count.execute_action("list_accounts", {}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is False
    assert "error" in result.result.data
