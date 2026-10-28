"""Read-only end-to-end tests for the Retail Express integration.

These tests call the real Retail Express API. Set RETAIL_EXPRESS_API_KEY in
the repository-root .env file or export it in the shell.

Run safely with:
    pytest retail-express/tests/test_retail_express_integration.py -m "integration and not destructive" -v

Customer create and update actions are intentionally excluded because Retail
Express exposes no matching customer-delete action for reliable cleanup, and
an update test could not safely restore an arbitrary customer's prior state.
"""

from unittest.mock import AsyncMock

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from retail_express import retail_express


pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("RETAIL_EXPRESS_API_KEY")
    if not api_key:
        pytest.skip("RETAIL_EXPRESS_API_KEY is required")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"Retail Express returned HTTP {response.status}: {data}")
                return FetchResponse(status=response.status, headers=dict(response.headers), data=data)

    context = make_context(auth={"auth_type": "Custom", "credentials": {"api_key": api_key}})
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


def assert_list_result(result, records_key: str, max_items: int) -> list:
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data[records_key], list)
    assert len(data[records_key]) <= max_items
    assert isinstance(data["page_number"], int)
    assert isinstance(data["page_size"], int)
    assert isinstance(data["total_records"], int)
    assert data["result"] is True
    return data[records_key]


class TestProducts:
    async def test_list_and_get_product(self, live_context):
        list_result = await retail_express.execute_action("list_products", {"page_size": 2}, live_context)
        products = assert_list_result(list_result, "products", 2)
        if not products:
            pytest.skip("Retail Express account has no products")

        product_id = products[0].get("id")
        if product_id is None:
            pytest.fail("Product list response did not include an id")

        get_result = await retail_express.execute_action("get_product", {"product_id": str(product_id)}, live_context)
        assert get_result.type == ResultType.ACTION
        assert str(get_result.result.data["product"]["id"]) == str(product_id)
        assert get_result.result.data["result"] is True

    async def test_list_products_accepts_modified_since(self, live_context):
        result = await retail_express.execute_action(
            "list_products",
            {"modified_since": "2000-01-01T00:00:00+10:00", "page_size": 2},
            live_context,
        )

        assert_list_result(result, "products", 2)


class TestInventory:
    async def test_list_inventory_levels(self, live_context):
        result = await retail_express.execute_action("list_inventory_levels", {"page_size": 2}, live_context)
        levels = assert_list_result(result, "inventory_levels", 2)

        for level in levels:
            assert "product_id" in level
            assert "outlet_id" in level
            assert "available" in level
            assert "stock_on_hand" in level

    async def test_list_inventory_movements(self, live_context):
        result = await retail_express.execute_action(
            "list_inventory_movements", {"page_size": 2, "order_by": "created_on desc"}, live_context
        )
        movements = assert_list_result(result, "inventory_movements", 2)

        for movement in movements:
            assert "id" in movement
            assert "product" in movement
            assert "outlet" in movement
            assert "movement_type" in movement


class TestCustomers:
    async def test_list_and_get_customer(self, live_context):
        list_result = await retail_express.execute_action("list_customers", {"page_size": 2}, live_context)
        customers = assert_list_result(list_result, "customers", 2)
        if not customers:
            pytest.skip("Retail Express account has no customers")

        customer_id = customers[0].get("id")
        if customer_id is None:
            pytest.fail("Customer list response did not include an id")

        get_result = await retail_express.execute_action(
            "get_customer", {"customer_id": str(customer_id)}, live_context
        )
        assert get_result.type == ResultType.ACTION
        assert str(get_result.result.data["customer"]["id"]) == str(customer_id)
        assert get_result.result.data["result"] is True

    async def test_filters_customers_by_email_and_modified_since(self, live_context):
        list_result = await retail_express.execute_action("list_customers", {"page_size": 20}, live_context)
        customers = assert_list_result(list_result, "customers", 20)
        customer_with_email = next((customer for customer in customers if customer.get("email")), None)
        if customer_with_email is None:
            pytest.skip("No customer with an email was found on the first page")

        email = customer_with_email["email"]
        filtered_result = await retail_express.execute_action(
            "list_customers",
            {
                "email": email,
                "modified_since": "2000-01-01T00:00:00+10:00",
                "page_size": 20,
            },
            live_context,
        )
        filtered_customers = assert_list_result(filtered_result, "customers", 20)

        assert filtered_customers
        assert all(customer.get("email") == email for customer in filtered_customers)


class TestOrders:
    async def test_list_and_get_order(self, live_context):
        list_result = await retail_express.execute_action("list_orders", {"page_size": 2}, live_context)
        orders = assert_list_result(list_result, "orders", 2)
        if not orders:
            pytest.skip("Retail Express account has no orders")

        order_id = orders[0].get("id")
        if order_id is None:
            pytest.fail("Order list response did not include an id")

        get_result = await retail_express.execute_action("get_order", {"order_id": str(order_id)}, live_context)
        assert get_result.type == ResultType.ACTION
        assert str(get_result.result.data["order"]["id"]) == str(order_id)
        assert get_result.result.data["result"] is True

    async def test_filters_orders_by_customer_status_and_modified_since(self, live_context):
        list_result = await retail_express.execute_action("list_orders", {"page_size": 20}, live_context)
        orders = assert_list_result(list_result, "orders", 20)
        filterable_order = next(
            (
                order
                for order in orders
                if (order.get("customer") or {}).get("id") is not None
                and (order.get("order_status") or {}).get("id") is not None
            ),
            None,
        )
        if filterable_order is None:
            pytest.skip("No order with customer and status IDs was found on the first page")

        customer_id = filterable_order["customer"]["id"]
        order_status_id = filterable_order["order_status"]["id"]
        filtered_result = await retail_express.execute_action(
            "list_orders",
            {
                "customer_id": str(customer_id),
                "order_status_id": order_status_id,
                "modified_since": "2000-01-01T00:00:00+10:00",
                "page_size": 20,
            },
            live_context,
        )
        filtered_orders = assert_list_result(filtered_result, "orders", 20)

        assert filtered_orders
        assert all(str((order.get("customer") or {}).get("id")) == str(customer_id) for order in filtered_orders)
        assert all((order.get("order_status") or {}).get("id") == order_status_id for order in filtered_orders)


class TestOutlets:
    async def test_list_and_get_outlet(self, live_context):
        list_result = await retail_express.execute_action("list_outlets", {"page_size": 2}, live_context)
        outlets = assert_list_result(list_result, "outlets", 2)
        if not outlets:
            pytest.skip("Retail Express account has no outlets")

        outlet_id = outlets[0].get("id")
        if outlet_id is None:
            pytest.fail("Outlet list response did not include an id")

        get_result = await retail_express.execute_action("get_outlet", {"outlet_id": str(outlet_id)}, live_context)
        assert get_result.type == ResultType.ACTION
        assert str(get_result.result.data["outlet"]["id"]) == str(outlet_id)
        assert get_result.result.data["result"] is True
