import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk.integration import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from stripe.stripe import stripe

pytestmark = pytest.mark.unit

SAMPLE_CUSTOMER = {
    "id": "cus_test123",
    "object": "customer",
    "email": "test@example.com",
    "name": "Test Customer",
}

SAMPLE_INVOICE = {
    "id": "in_test123",
    "object": "invoice",
    "customer": "cus_test123",
    "status": "draft",
    "total": 5000,
}

SAMPLE_PRODUCT = {
    "id": "prod_test123",
    "object": "product",
    "name": "Test Product",
    "active": True,
}

SAMPLE_PRICE = {
    "id": "price_test123",
    "object": "price",
    "product": "prod_test123",
    "unit_amount": 1999,
    "currency": "usd",
}

SAMPLE_SUBSCRIPTION = {
    "id": "sub_test123",
    "object": "subscription",
    "customer": "cus_test123",
    "status": "active",
}

SAMPLE_LIST = {
    "object": "list",
    "data": [],
    "has_more": False,
}


@pytest.fixture
def ctx():
    mock = MagicMock(name="ExecutionContext")
    mock.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data={}))
    mock.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "sk_test_fake"}}  # nosec B105
    return mock


# ---- Customers ----


class TestListCustomers:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": [SAMPLE_CUSTOMER]})
        result = await stripe.execute_action("list_customers", {"limit": 5}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["result"] is True
        assert len(result.result.data["customers"]) == 1

    async def test_url_and_method(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_LIST)
        await stripe.execute_action("list_customers", {}, ctx)
        call = ctx.fetch.call_args
        assert "customers" in call.args[0]
        assert call.kwargs["method"] == "GET"

    async def test_exception_returns_action_error(self, ctx):
        ctx.fetch.side_effect = Exception("timeout")
        result = await stripe.execute_action("list_customers", {}, ctx)
        assert result.type == ResultType.ACTION_ERROR
        assert "timeout" in result.result.message


class TestGetCustomer:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_CUSTOMER)
        result = await stripe.execute_action("get_customer", {"customer_id": "cus_test123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["result"] is True
        assert result.result.data["customer"]["id"] == "cus_test123"

    async def test_url_contains_customer_id(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_CUSTOMER)
        await stripe.execute_action("get_customer", {"customer_id": "cus_abc"}, ctx)
        assert "cus_abc" in ctx.fetch.call_args.args[0]


class TestCreateCustomer:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_CUSTOMER)
        result = await stripe.execute_action(
            "create_customer",
            {"email": "test@example.com", "name": "Test"},
            ctx,
        )
        assert result.result.data["result"] is True
        assert "customer" in result.result.data

    async def test_uses_post(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_CUSTOMER)
        await stripe.execute_action("create_customer", {"email": "x@x.com"}, ctx)
        assert ctx.fetch.call_args.kwargs["method"] == "POST"


class TestDeleteCustomer:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {"id": "cus_test123", "deleted": True})
        result = await stripe.execute_action("delete_customer", {"customer_id": "cus_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["deleted"] is True


# ---- Invoices ----


class TestListInvoices:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": [SAMPLE_INVOICE]})
        result = await stripe.execute_action("list_invoices", {"limit": 5}, ctx)
        assert result.result.data["result"] is True
        assert len(result.result.data["invoices"]) == 1

    async def test_status_filter(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_LIST)
        await stripe.execute_action("list_invoices", {"status": "draft"}, ctx)
        params = ctx.fetch.call_args.kwargs.get("params", {})
        assert params.get("status") == "draft"


class TestGetInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_INVOICE)
        result = await stripe.execute_action("get_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["invoice"]["id"] == "in_test123"


class TestDeleteInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {"id": "in_test123", "deleted": True})
        result = await stripe.execute_action("delete_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["deleted"] is True


# ---- Products ----


class TestListProducts:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": [SAMPLE_PRODUCT]})
        result = await stripe.execute_action("list_products", {"limit": 3}, ctx)
        assert result.result.data["result"] is True
        assert len(result.result.data["products"]) == 1

    async def test_active_filter(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_LIST)
        await stripe.execute_action("list_products", {"active": True}, ctx)
        params = ctx.fetch.call_args.kwargs.get("params", {})
        assert params.get("active") == "true"


class TestGetProduct:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_PRODUCT)
        result = await stripe.execute_action("get_product", {"product_id": "prod_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["product"]["id"] == "prod_test123"


# ---- Prices ----


class TestListPrices:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": [SAMPLE_PRICE]})
        result = await stripe.execute_action("list_prices", {"limit": 3}, ctx)
        assert result.result.data["result"] is True
        assert len(result.result.data["prices"]) == 1


class TestGetPrice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_PRICE)
        result = await stripe.execute_action("get_price", {"price_id": "price_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["price"]["id"] == "price_test123"


# ---- Invoice Items ----


class TestListInvoiceItems:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": []})
        result = await stripe.execute_action("list_invoice_items", {}, ctx)
        assert result.result.data["result"] is True
        assert "invoice_items" in result.result.data

    async def test_invoice_filter(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_LIST)
        await stripe.execute_action("list_invoice_items", {"invoice": "in_test123"}, ctx)
        params = ctx.fetch.call_args.kwargs.get("params", {})
        assert params.get("invoice") == "in_test123"


class TestGetInvoiceItem:
    async def test_success(self, ctx):
        item = {"id": "ii_test123", "object": "invoiceitem", "amount": 500}
        ctx.fetch.return_value = FetchResponse(200, {}, item)
        result = await stripe.execute_action("get_invoice_item", {"invoice_item_id": "ii_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["invoice_item"]["id"] == "ii_test123"


class TestCreateInvoiceItem:
    async def test_success(self, ctx):
        item = {"id": "ii_test123", "object": "invoiceitem", "amount": 500}
        ctx.fetch.return_value = FetchResponse(200, {}, item)
        result = await stripe.execute_action(
            "create_invoice_item",
            {"customer": "cus_test123", "unit_amount": 500, "currency": "usd"},
            ctx,
        )
        assert result.result.data["result"] is True

    async def test_uses_post(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {})
        await stripe.execute_action(
            "create_invoice_item",
            {"customer": "cus_test123", "unit_amount": 500, "currency": "usd"},
            ctx,
        )
        assert ctx.fetch.call_args.kwargs["method"] == "POST"


class TestDeleteInvoiceItem:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {"id": "ii_test123", "deleted": True})
        result = await stripe.execute_action("delete_invoice_item", {"invoice_item_id": "ii_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["deleted"] is True


# ---- Invoice Lifecycle ----


class TestFinalizeInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_INVOICE, "status": "open"})
        result = await stripe.execute_action("finalize_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["invoice"]["status"] == "open"

    async def test_url_contains_finalize(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_INVOICE)
        await stripe.execute_action("finalize_invoice", {"invoice_id": "in_abc"}, ctx)
        assert "finalize" in ctx.fetch.call_args.args[0]
        assert "in_abc" in ctx.fetch.call_args.args[0]


class TestVoidInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_INVOICE, "status": "void"})
        result = await stripe.execute_action("void_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True

    async def test_url_contains_void(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_INVOICE)
        await stripe.execute_action("void_invoice", {"invoice_id": "in_abc"}, ctx)
        assert "void" in ctx.fetch.call_args.args[0]


class TestSendInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_INVOICE, "status": "open"})
        result = await stripe.execute_action("send_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True

    async def test_url_contains_send(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_INVOICE)
        await stripe.execute_action("send_invoice", {"invoice_id": "in_abc"}, ctx)
        assert "send" in ctx.fetch.call_args.args[0]


class TestPayInvoice:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_INVOICE, "status": "paid"})
        result = await stripe.execute_action("pay_invoice", {"invoice_id": "in_test123"}, ctx)
        assert result.result.data["result"] is True

    async def test_url_contains_pay(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_INVOICE)
        await stripe.execute_action("pay_invoice", {"invoice_id": "in_abc"}, ctx)
        assert "/pay" in ctx.fetch.call_args.args[0]


# ---- Subscriptions ----


class TestListSubscriptions:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": [SAMPLE_SUBSCRIPTION]})
        result = await stripe.execute_action("list_subscriptions", {"limit": 3}, ctx)
        assert result.result.data["result"] is True
        assert len(result.result.data["subscriptions"]) == 1


class TestGetSubscription:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_SUBSCRIPTION)
        result = await stripe.execute_action("get_subscription", {"subscription_id": "sub_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["subscription"]["id"] == "sub_test123"


class TestCreateSubscription:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_SUBSCRIPTION)
        result = await stripe.execute_action(
            "create_subscription",
            {"customer": "cus_test123", "items": [{"price": "price_test123"}]},
            ctx,
        )
        assert result.result.data["result"] is True
        assert "subscription" in result.result.data

    async def test_uses_post(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_SUBSCRIPTION)
        await stripe.execute_action(
            "create_subscription",
            {"customer": "cus_test123", "items": [{"price": "price_test123"}]},
            ctx,
        )
        assert ctx.fetch.call_args.kwargs["method"] == "POST"


class TestUpdateSubscription:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_SUBSCRIPTION)
        result = await stripe.execute_action(
            "update_subscription",
            {"subscription_id": "sub_test123", "metadata": {"key": "val"}},
            ctx,
        )
        assert result.result.data["result"] is True

    async def test_url_contains_subscription_id(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, SAMPLE_SUBSCRIPTION)
        await stripe.execute_action(
            "update_subscription",
            {"subscription_id": "sub_abc"},
            ctx,
        )
        assert "sub_abc" in ctx.fetch.call_args.args[0]


class TestCancelSubscription:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_SUBSCRIPTION, "status": "canceled"})
        result = await stripe.execute_action(
            "cancel_subscription",
            {"subscription_id": "sub_test123"},
            ctx,
        )
        assert result.result.data["result"] is True
        assert result.result.data["subscription"]["status"] == "canceled"


# ---- Payment Methods ----


class TestListPaymentMethods:
    async def test_success(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {**SAMPLE_LIST, "data": []})
        result = await stripe.execute_action(
            "list_payment_methods",
            {"customer": "cus_test123", "type": "card"},
            ctx,
        )
        assert result.result.data["result"] is True
        assert "payment_methods" in result.result.data


class TestGetPaymentMethod:
    async def test_success(self, ctx):
        pm = {"id": "pm_test123", "object": "payment_method", "type": "card"}
        ctx.fetch.return_value = FetchResponse(200, {}, pm)
        result = await stripe.execute_action("get_payment_method", {"payment_method_id": "pm_test123"}, ctx)
        assert result.result.data["result"] is True
        assert result.result.data["payment_method"]["id"] == "pm_test123"


class TestAttachPaymentMethod:
    async def test_success(self, ctx):
        pm = {"id": "pm_test123", "object": "payment_method", "customer": "cus_test123"}
        ctx.fetch.return_value = FetchResponse(200, {}, pm)
        result = await stripe.execute_action(
            "attach_payment_method",
            {"payment_method_id": "pm_test123", "customer": "cus_test123"},
            ctx,
        )
        assert result.result.data["result"] is True

    async def test_url_contains_attach(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {})
        await stripe.execute_action(
            "attach_payment_method",
            {"payment_method_id": "pm_abc", "customer": "cus_test123"},
            ctx,
        )
        assert "attach" in ctx.fetch.call_args.args[0]
        assert "pm_abc" in ctx.fetch.call_args.args[0]


class TestDetachPaymentMethod:
    async def test_success(self, ctx):
        pm = {"id": "pm_test123", "object": "payment_method", "customer": None}
        ctx.fetch.return_value = FetchResponse(200, {}, pm)
        result = await stripe.execute_action("detach_payment_method", {"payment_method_id": "pm_test123"}, ctx)
        assert result.result.data["result"] is True

    async def test_url_contains_detach(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {})
        await stripe.execute_action("detach_payment_method", {"payment_method_id": "pm_abc"}, ctx)
        assert "detach" in ctx.fetch.call_args.args[0]


# ---- ConnectedAccountHandler ----


class TestConnectedAccountHandler:
    async def test_returns_account_name(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            200,
            {},
            {
                "id": "acct_test123",
                "business_profile": {"name": "Acme Corp", "support_email": ""},
                "email": "owner@acme.com",
            },
        )
        result = await stripe.get_connected_account(ctx)
        assert result.result.username == "Acme Corp"
        assert result.result.user_id == "acct_test123"

    async def test_falls_back_to_email_when_no_name(self, ctx):
        ctx.fetch.return_value = FetchResponse(
            200,
            {},
            {
                "id": "acct_test456",
                "email": "owner@example.com",
                "business_profile": {"name": None, "support_email": ""},
            },
        )
        result = await stripe.get_connected_account(ctx)
        assert result.result.username == "owner@example.com"
        assert result.result.user_id == "acct_test456"

    async def test_falls_back_to_stripe_account_on_exception(self, ctx):
        ctx.fetch.side_effect = Exception("network error")
        result = await stripe.get_connected_account(ctx)
        assert result.result.username == "Stripe Account"

    async def test_calls_account_endpoint(self, ctx):
        ctx.fetch.return_value = FetchResponse(200, {}, {"id": "acct_test123", "email": "x@x.com"})
        await stripe.get_connected_account(ctx)
        assert "/account" in ctx.fetch.call_args.args[0]
        assert ctx.fetch.call_args.kwargs["method"] == "GET"
