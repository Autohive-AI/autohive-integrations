"""End-to-end tests for the Shopify Admin integration.

These tests call a real Shopify store using a merchant-owned Dev Dashboard app.
They never run in CI because this file is not matched by the unit-test discovery
pattern and every test is marked ``integration``.

Run read-only tests (safe default):
    pytest shopify-admin/tests/test_shopify_admin_integration.py -m "integration and not destructive"

Run destructive tests deliberately:
    pytest shopify-admin/tests/test_shopify_admin_integration.py -m "integration and destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from shopify_admin import shopify_admin

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    """Return a production-shaped context whose fetch method calls Shopify."""
    variable_names = ("SHOPIFY_STORE_URL", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    values = {name: env_credentials(name) for name in variable_names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"Missing Shopify integration-test credentials: {', '.join(missing)}")

    async def real_fetch(
        url,
        *,
        method="GET",
        json=None,
        data=None,
        headers=None,
        params=None,
        content_type=None,
        **kwargs,
    ):
        request_headers = dict(headers or {})
        if content_type:
            request_headers.setdefault("Content-Type", content_type)

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                data=data,
                headers=request_headers,
                params=params,
                **kwargs,
            ) as response:
                try:
                    response_data = await response.json(content_type=None)
                except ValueError:
                    response_data = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"Shopify API returned HTTP {response.status}")
                return FetchResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    data=response_data,
                )

    context = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {
                "shop_url": values["SHOPIFY_STORE_URL"],
                "client_id": values["SHOPIFY_CLIENT_ID"],
                "client_secret": values["SHOPIFY_CLIENT_SECRET"],
            },
        }
    )
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


@pytest.fixture
def test_ids(env_credentials):
    """Optional stable resource IDs; tests fall back to list actions where possible."""
    return {
        "customer": env_credentials("SHOPIFY_ADMIN_TEST_CUSTOMER_ID"),
        "order": env_credentials("SHOPIFY_ADMIN_TEST_ORDER_ID"),
        "product": env_credentials("SHOPIFY_ADMIN_TEST_PRODUCT_ID"),
        "location": env_credentials("SHOPIFY_ADMIN_TEST_LOCATION_ID"),
        "inventory_item": env_credentials("SHOPIFY_ADMIN_TEST_INVENTORY_ITEM_ID"),
    }


def action_data(result):
    """Assert a successful SDK action result and return its data."""
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["success"] is True
    return result.result.data


async def first_resource_id(live_context, configured_id, list_action, collection_key):
    """Use a configured resource ID or discover one through a safe list action."""
    if configured_id:
        return configured_id

    result = await shopify_admin.execute_action(list_action, {"limit": 1}, live_context)
    resources = action_data(result)[collection_key]
    if not resources:
        pytest.skip(f"No Shopify {collection_key.replace('_', ' ')} available")
    return resources[0]["id"]


# ---- Customer actions ----


class TestCustomers:
    async def test_list_customers(self, live_context):
        data = action_data(await shopify_admin.execute_action("list_customers", {"limit": 2}, live_context))

        assert isinstance(data["customers"], list)
        assert data["count"] == len(data["customers"])
        assert data["count"] <= 2

    async def test_get_customer(self, live_context, test_ids):
        customer_id = await first_resource_id(live_context, test_ids["customer"], "list_customers", "customers")
        data = action_data(
            await shopify_admin.execute_action("get_customer", {"customer_id": customer_id}, live_context)
        )

        assert data["customer"]["id"] == str(customer_id)

    async def test_search_customers(self, live_context, test_ids):
        customer_id = await first_resource_id(live_context, test_ids["customer"], "list_customers", "customers")
        data = action_data(
            await shopify_admin.execute_action(
                "search_customers",
                {"query": f"id:{customer_id}", "limit": 2},
                live_context,
            )
        )

        assert isinstance(data["customers"], list)
        assert data["count"] == len(data["customers"])


# ---- Order actions ----


class TestOrders:
    async def test_list_orders(self, live_context):
        data = action_data(await shopify_admin.execute_action("list_orders", {"limit": 2}, live_context))

        assert isinstance(data["orders"], list)
        assert data["count"] == len(data["orders"])
        assert data["count"] <= 2

    async def test_get_order(self, live_context, test_ids):
        order_id = await first_resource_id(live_context, test_ids["order"], "list_orders", "orders")
        data = action_data(await shopify_admin.execute_action("get_order", {"order_id": order_id}, live_context))

        assert data["order"]["id"] == str(order_id)


# ---- Product actions ----


class TestProducts:
    async def test_list_products(self, live_context):
        data = action_data(await shopify_admin.execute_action("list_products", {"limit": 2}, live_context))

        assert isinstance(data["products"], list)
        assert data["count"] == len(data["products"])
        assert data["count"] <= 2
        assert isinstance(data["hasNextPage"], bool)

    async def test_list_products_with_filter(self, live_context):
        data = action_data(
            await shopify_admin.execute_action(
                "list_products",
                {"limit": 2, "status": "active"},
                live_context,
            )
        )

        assert all(product["status"] == "active" for product in data["products"])

    async def test_get_product(self, live_context, test_ids):
        product_id = await first_resource_id(live_context, test_ids["product"], "list_products", "products")
        data = action_data(await shopify_admin.execute_action("get_product", {"product_id": product_id}, live_context))

        assert data["product"]["id"] == str(product_id)
        assert isinstance(data["product"]["variants"], list)


# ---- Inventory and location actions ----


class TestInventoryAndLocations:
    async def test_list_locations(self, live_context):
        data = action_data(await shopify_admin.execute_action("list_locations", {}, live_context))

        assert isinstance(data["locations"], list)
        assert data["count"] == len(data["locations"])

    async def test_get_location(self, live_context, test_ids):
        location_id = await first_resource_id(live_context, test_ids["location"], "list_locations", "locations")
        data = action_data(
            await shopify_admin.execute_action("get_location", {"location_id": location_id}, live_context)
        )

        assert data["location"]["id"] == str(location_id)

    async def test_get_inventory_levels(self, live_context, test_ids):
        if test_ids["inventory_item"]:
            inputs = {"inventory_item_ids": test_ids["inventory_item"], "limit": 2}
        else:
            location_id = await first_resource_id(live_context, test_ids["location"], "list_locations", "locations")
            inputs = {"location_ids": location_id, "limit": 2}

        data = action_data(await shopify_admin.execute_action("get_inventory_levels", inputs, live_context))

        assert isinstance(data["inventory_levels"], list)
        assert data["count"] == len(data["inventory_levels"])
        assert data["count"] <= 2


# ---- Shop, draft-order, and fulfillment actions ----


class TestStoreOperations:
    async def test_get_shop(self, live_context):
        data = action_data(await shopify_admin.execute_action("get_shop", {}, live_context))

        assert data["shop"]["id"]
        assert data["shop"]["myshopify_domain"]

    async def test_list_draft_orders(self, live_context):
        data = action_data(await shopify_admin.execute_action("list_draft_orders", {"limit": 2}, live_context))

        assert isinstance(data["draft_orders"], list)
        assert data["count"] == len(data["draft_orders"])
        assert data["count"] <= 2

    async def test_list_fulfillments(self, live_context, test_ids):
        order_id = await first_resource_id(live_context, test_ids["order"], "list_orders", "orders")
        data = action_data(
            await shopify_admin.execute_action("list_fulfillments", {"order_id": order_id}, live_context)
        )

        assert isinstance(data["fulfillments"], list)
        assert data["count"] == len(data["fulfillments"])


# ---- Destructive lifecycle tests ----
# These mutate the connected store. Run only with: -m "integration and destructive"


@pytest.mark.destructive
class TestDraftOrderLifecycle:
    async def test_create_and_delete_draft_order(self, live_context):
        draft_order_id = None
        try:
            create_data = action_data(
                await shopify_admin.execute_action(
                    "create_draft_order",
                    {
                        "line_items": [
                            {
                                "title": "Autohive integration test item",
                                "price": "1.00",
                                "quantity": 1,
                            }
                        ],
                        "note": "Created by the Autohive Shopify Admin integration test",
                        "tags": "autohive,integration-test",
                    },
                    live_context,
                )
            )
            draft_order_id = create_data["draft_order"]["id"]
            assert draft_order_id
        finally:
            if draft_order_id:
                delete_data = action_data(
                    await shopify_admin.execute_action(
                        "delete_draft_order",
                        {"draft_order_id": draft_order_id},
                        live_context,
                    )
                )
                assert delete_data["deleted"] is True
