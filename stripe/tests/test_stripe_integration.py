"""
Live integration tests for the Stripe integration.

Requires STRIPE_TEST_API_KEY set in the environment (use a test-mode key: sk_test_...).

Run with:
    pytest stripe/tests/test_stripe_integration.py -m "integration" -o "addopts=--import-mode=importlib --tb=short"
"""

import time

import pytest
from autohive_integrations_sdk.integration import ResultType

from stripe.stripe import stripe

pytestmark = pytest.mark.integration


# ---- Read-Only Tests ----


class TestListCustomers:
    async def test_returns_list(self, stripe_context):
        result = await stripe.execute_action("list_customers", {"limit": 5}, stripe_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert "customers" in data
        assert isinstance(data["customers"], list)


class TestListInvoices:
    async def test_returns_list(self, stripe_context):
        result = await stripe.execute_action("list_invoices", {"limit": 5}, stripe_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert "invoices" in data


class TestListProducts:
    async def test_returns_list(self, stripe_context):
        result = await stripe.execute_action("list_products", {"limit": 5}, stripe_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert "products" in data

    async def test_active_filter(self, stripe_context):
        result = await stripe.execute_action("list_products", {"limit": 5, "active": True}, stripe_context)
        data = result.result.data
        assert data["result"] is True
        for p in data["products"]:
            assert p.get("active") is True


class TestListPrices:
    async def test_returns_list(self, stripe_context):
        result = await stripe.execute_action("list_prices", {"limit": 5}, stripe_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert "prices" in data


class TestListSubscriptions:
    async def test_returns_list(self, stripe_context):
        result = await stripe.execute_action("list_subscriptions", {"limit": 5}, stripe_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert "subscriptions" in data


# ---- Destructive Tests ----


@pytest.mark.destructive
class TestCustomerLifecycle:
    """Create → get → update → delete a test customer."""

    async def test_full_lifecycle(self, stripe_context):
        uid = int(time.time())

        # Create
        create = await stripe.execute_action(
            "create_customer",
            {"email": f"ah-test-{uid}@example.com", "name": f"AH Test {uid}"},
            stripe_context,
        )
        assert create.result.data["result"] is True
        customer_id = create.result.data["customer"]["id"]
        assert customer_id.startswith("cus_")

        # Get
        get = await stripe.execute_action("get_customer", {"customer_id": customer_id}, stripe_context)
        assert get.result.data["customer"]["id"] == customer_id

        # Update
        update = await stripe.execute_action(
            "update_customer",
            {"customer_id": customer_id, "name": f"AH Updated {uid}"},
            stripe_context,
        )
        assert update.result.data["result"] is True

        # Delete (cleanup)
        delete = await stripe.execute_action("delete_customer", {"customer_id": customer_id}, stripe_context)
        assert delete.result.data["result"] is True
        assert delete.result.data["deleted"] is True


@pytest.mark.destructive
class TestProductAndPriceLifecycle:
    """Create product → create price → get each → cleanup."""

    async def test_full_lifecycle(self, stripe_context):
        uid = int(time.time())

        # Create product
        prod = await stripe.execute_action(
            "create_product",
            {"name": f"AH Test Product {uid}", "active": True},
            stripe_context,
        )
        assert prod.result.data["result"] is True
        product_id = prod.result.data["product"]["id"]

        # Create price
        price = await stripe.execute_action(
            "create_price",
            {"product": product_id, "currency": "usd", "unit_amount": 999},
            stripe_context,
        )
        assert price.result.data["result"] is True
        price_id = price.result.data["price"]["id"]

        # Get price
        get_price = await stripe.execute_action("get_price", {"price_id": price_id}, stripe_context)
        assert get_price.result.data["price"]["id"] == price_id

        # Get product
        get_prod = await stripe.execute_action("get_product", {"product_id": product_id}, stripe_context)
        assert get_prod.result.data["product"]["id"] == product_id
