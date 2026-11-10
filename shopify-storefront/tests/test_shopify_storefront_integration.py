"""
End-to-end integration tests for the Shopify Storefront integration.

These tests call the real Storefront API and require:
    SHOPIFY_STOREFRONT_SHOP_URL      e.g. your-test-store.myshopify.com
    SHOPIFY_STOREFRONT_PUBLIC_TOKEN  a Storefront API public access token

Optional:
    SHOPIFY_STOREFRONT_TEST_GIFT_CARD_CODE  a test-store gift card code; the gift-card
                                            lifecycle test is skipped without it

Read-only tests need at least one product and one collection in the store.
Cart and customer tests create real carts/customer accounts and are marked destructive.

Run read-only tests:
    pytest shopify-storefront/tests/test_shopify_storefront_integration.py -m "integration and not destructive"

Run destructive tests deliberately:
    pytest shopify-storefront/tests/test_shopify_storefront_integration.py -m "integration and destructive"
"""

import time
from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from shopify_storefront import shopify_storefront
from shopify_storefront import API_VERSION

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    """Return a production-shaped context whose fetch method calls the Storefront API."""
    shop_url = env_credentials("SHOPIFY_STOREFRONT_SHOP_URL")
    public_token = env_credentials("SHOPIFY_STOREFRONT_PUBLIC_TOKEN")
    missing = [
        name
        for name, value in (
            ("SHOPIFY_STOREFRONT_SHOP_URL", shop_url),
            ("SHOPIFY_STOREFRONT_PUBLIC_TOKEN", public_token),
        )
        if not value
    ]
    if missing:
        pytest.skip(f"Missing Shopify Storefront integration-test credentials: {', '.join(missing)}")

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise RuntimeError(f"Shopify Storefront API returned HTTP {resp.status}")
                # Shopify silently serves retired versions with its oldest supported one.
                served = resp.headers.get("X-Shopify-API-Version")
                assert served == API_VERSION, (
                    f"Shopify served API version {served!r} instead of {API_VERSION!r}; "
                    "the requested version may be retired or unsupported"
                )
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    context = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"shop_url": shop_url, "public_token": public_token},
        }
    )
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


def action_data(result):
    """Assert a successful SDK action result and return its data."""
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["success"] is True
    return result.result.data


async def first_product(live_context):
    data = action_data(await shopify_storefront.execute_action("storefront_list_products", {"first": 1}, live_context))
    if not data["products"]:
        pytest.skip("No products available in the Storefront test store")
    return data["products"][0]


async def first_variant_id(live_context):
    product = await first_product(live_context)
    data = action_data(
        await shopify_storefront.execute_action("storefront_get_product", {"handle": product["handle"]}, live_context)
    )
    variants = [edge["node"] for edge in (data["product"].get("variants") or {}).get("edges", [])]
    available = [variant for variant in variants if variant.get("availableForSale")]
    if not available:
        pytest.skip("No variant available for sale in the Storefront test store")
    return available[0]["id"]


# ---- Read-Only Tests ----


class TestProducts:
    async def test_list_products(self, live_context):
        data = action_data(
            await shopify_storefront.execute_action("storefront_list_products", {"first": 2}, live_context)
        )
        assert isinstance(data["products"], list)
        assert data["count"] == len(data["products"]) <= 2
        assert isinstance(data["has_next_page"], bool)

    async def test_list_products_pagination(self, live_context):
        first_page = action_data(
            await shopify_storefront.execute_action("storefront_list_products", {"first": 1}, live_context)
        )
        if not first_page["has_next_page"]:
            pytest.skip("Pagination requires at least two products")
        second_page = action_data(
            await shopify_storefront.execute_action(
                "storefront_list_products", {"first": 1, "after": first_page["end_cursor"]}, live_context
            )
        )
        assert second_page["products"][0]["id"] != first_page["products"][0]["id"]

    async def test_get_product_by_handle(self, live_context):
        product = await first_product(live_context)
        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_product", {"handle": product["handle"]}, live_context
            )
        )
        assert data["product"]["id"] == product["id"]

    async def test_get_product_by_id(self, live_context):
        product = await first_product(live_context)
        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_product", {"product_id": product["id"]}, live_context
            )
        )
        assert data["product"]["handle"] == product["handle"]

    async def test_get_missing_product_returns_error(self, live_context):
        result = await shopify_storefront.execute_action(
            "storefront_get_product", {"handle": f"no-such-product-{int(time.time())}"}, live_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message

    async def test_search_products(self, live_context):
        product = await first_product(live_context)
        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_search_products", {"query": product["title"], "first": 5}, live_context
            )
        )
        assert isinstance(data["products"], list)
        assert data["count"] <= 5
        assert isinstance(data["total_count"], int)


class TestCollections:
    async def test_list_collections(self, live_context):
        data = action_data(
            await shopify_storefront.execute_action("storefront_list_collections", {"first": 2}, live_context)
        )
        assert isinstance(data["collections"], list)
        assert data["count"] <= 2

    async def test_get_collection(self, live_context):
        listed = action_data(
            await shopify_storefront.execute_action("storefront_list_collections", {"first": 1}, live_context)
        )
        if not listed["collections"]:
            pytest.skip("No collections available in the Storefront test store")
        collection = listed["collections"][0]
        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_collection", {"handle": collection["handle"], "products_first": 2}, live_context
            )
        )
        assert data["collection"]["id"] == collection["id"]


class TestCartReads:
    async def test_get_missing_cart_returns_error(self, live_context):
        result = await shopify_storefront.execute_action(
            "storefront_get_cart", {"cart_id": "gid://shopify/Cart/does-not-exist"}, live_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestContentAndDiscovery:
    async def test_get_shop_policies(self, live_context):
        data = action_data(await shopify_storefront.execute_action("storefront_get_shop_policies", {}, live_context))
        assert set(data["policies"]) == {
            "privacy_policy",
            "refund_policy",
            "shipping_policy",
            "terms_of_service",
            "subscription_policy",
        }

    async def test_list_and_get_page(self, live_context):
        data = action_data(await shopify_storefront.execute_action("storefront_list_pages", {"first": 1}, live_context))
        if not data["pages"]:
            pytest.skip("No pages available in the Storefront test store")
        page = data["pages"][0]

        fetched = action_data(
            await shopify_storefront.execute_action("storefront_get_page", {"handle": page["handle"]}, live_context)
        )
        assert fetched["page"]["id"] == page["id"]

    async def test_list_and_get_article(self, live_context):
        data = action_data(
            await shopify_storefront.execute_action("storefront_list_articles", {"first": 1}, live_context)
        )
        if not data["articles"]:
            pytest.skip("No blog articles available in the Storefront test store")
        article = data["articles"][0]

        fetched = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_article", {"article_id": article["id"]}, live_context
            )
        )
        assert fetched["article"]["id"] == article["id"]

    async def test_get_main_menu(self, live_context):
        result = await shopify_storefront.execute_action("storefront_get_menu", {"handle": "main-menu"}, live_context)
        if result.type == ResultType.ACTION_ERROR and result.result.message == "Menu not found":
            pytest.skip("No main-menu in the Storefront test store")
        assert action_data(result)["menu"]["handle"] == "main-menu"

    async def test_product_recommendations(self, live_context):
        product = await first_product(live_context)

        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_product_recommendations", {"product_handle": product["handle"]}, live_context
            )
        )
        assert data["count"] == len(data["products"]) <= 10

    async def test_predictive_search(self, live_context):
        product = await first_product(live_context)

        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_predictive_search", {"query": product["title"][:4], "limit": 3}, live_context
            )
        )
        assert len(data["products"]) <= 3

    async def test_predictive_search_limit_applies_per_type(self, live_context):
        data = action_data(
            await shopify_storefront.execute_action(
                "storefront_predictive_search",
                {"query": "s", "limit": 2, "types": ["PRODUCT", "COLLECTION"]},
                live_context,
            )
        )
        assert len(data["products"]) <= 2
        assert len(data["collections"]) <= 2
        # A combined limit would cap products + collections at 2 in total.
        if len(data["products"]) == 2:
            assert data["collections"], "limit should apply per result type, not across all types"


# ---- Destructive Tests (Write Operations) ----
# These create carts and customer accounts in the connected store.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCartLifecycle:
    async def test_create_add_update_discount_remove(self, live_context):
        variant_id = await first_variant_id(live_context)

        cart = action_data(await shopify_storefront.execute_action("storefront_create_cart", {}, live_context))["cart"]
        cart_id = cart["id"]

        added = action_data(
            await shopify_storefront.execute_action(
                "storefront_add_to_cart",
                {"cart_id": cart_id, "lines": [{"merchandiseId": variant_id, "quantity": 1}]},
                live_context,
            )
        )["cart"]
        line_id = added["lines"]["edges"][0]["node"]["id"]

        fetched = action_data(
            await shopify_storefront.execute_action("storefront_get_cart", {"cart_id": cart_id}, live_context)
        )["cart"]
        assert fetched["id"] == cart_id

        updated = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_cart_line",
                {"cart_id": cart_id, "lines": [{"id": line_id, "quantity": 2}]},
                live_context,
            )
        )["cart"]
        assert updated["totalQuantity"] == 2

        action_data(
            await shopify_storefront.execute_action(
                "storefront_apply_discount", {"cart_id": cart_id, "discount_codes": ["INTEGRATIONTEST"]}, live_context
            )
        )

        removed = action_data(
            await shopify_storefront.execute_action(
                "storefront_remove_from_cart", {"cart_id": cart_id, "line_ids": [line_id]}, live_context
            )
        )["cart"]
        assert removed["totalQuantity"] == 0


@pytest.mark.destructive
class TestCartGiftCards:
    async def test_add_and_remove_gift_card(self, live_context, env_credentials):
        code = env_credentials("SHOPIFY_STOREFRONT_TEST_GIFT_CARD_CODE")
        if not code:
            pytest.skip("SHOPIFY_STOREFRONT_TEST_GIFT_CARD_CODE not set")
        variant_id = await first_variant_id(live_context)

        cart = action_data(
            await shopify_storefront.execute_action(
                "storefront_create_cart", {"lines": [{"merchandiseId": variant_id, "quantity": 1}]}, live_context
            )
        )["cart"]
        cart_id = cart["id"]

        added = action_data(
            await shopify_storefront.execute_action(
                "storefront_add_gift_cards", {"cart_id": cart_id, "gift_card_codes": [code]}, live_context
            )
        )["cart"]
        applied = added["appliedGiftCards"]
        assert len(applied) == 1
        assert applied[0]["lastCharacters"].lower() == code[-4:].lower()

        # Removal takes the applied gift card ID from appliedGiftCards, not the code.
        removed = action_data(
            await shopify_storefront.execute_action(
                "storefront_remove_gift_cards",
                {"cart_id": cart_id, "applied_gift_card_ids": [applied[0]["id"]]},
                live_context,
            )
        )["cart"]
        assert removed["appliedGiftCards"] == []


@pytest.mark.destructive
class TestCartDetails:
    async def test_buyer_identity_note_and_attributes(self, live_context):
        cart_id = action_data(await shopify_storefront.execute_action("storefront_create_cart", {}, live_context))[
            "cart"
        ]["id"]

        buyer = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_cart_buyer_identity", {"cart_id": cart_id, "country_code": "US"}, live_context
            )
        )["cart"]
        assert buyer["buyerIdentity"]["countryCode"] == "US"

        noted = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_cart_note", {"cart_id": cart_id, "note": "Integration test"}, live_context
            )
        )["cart"]
        assert noted["note"] == "Integration test"

        attributed = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_cart_attributes",
                {"cart_id": cart_id, "attributes": [{"key": "source", "value": "integration-test"}]},
                live_context,
            )
        )["cart"]
        assert attributed["attributes"] == [{"key": "source", "value": "integration-test"}]

        cleared = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_cart_attributes", {"cart_id": cart_id, "attributes": []}, live_context
            )
        )["cart"]
        assert cleared["attributes"] == []


@pytest.mark.destructive
class TestCustomerLifecycle:
    async def test_create_login_get_update_recover(self, live_context):
        timestamp = int(time.time())
        email = f"integration.test.{timestamp}@example.com"
        login_value = f"Integration{timestamp}!"

        action_data(
            await shopify_storefront.execute_action(
                "storefront_create_customer",
                {"email": email, "password": login_value, "first_name": "Integration", "last_name": "Test"},
                live_context,
            )
        )

        login = action_data(
            await shopify_storefront.execute_action(
                "storefront_customer_login", {"email": email, "password": login_value}, live_context
            )
        )
        customer_token = login["customer_access_token"]
        assert customer_token

        customer = action_data(
            await shopify_storefront.execute_action(
                "storefront_get_customer", {"customer_access_token": customer_token}, live_context
            )
        )["customer"]
        assert customer["email"] == email

        updated = action_data(
            await shopify_storefront.execute_action(
                "storefront_update_customer",
                {"customer_access_token": customer_token, "first_name": "Updated"},
                live_context,
            )
        )
        customer_token = updated["customer_access_token"] or customer_token

        renewed = action_data(
            await shopify_storefront.execute_action(
                "storefront_renew_customer_token", {"customer_access_token": customer_token}, live_context
            )
        )
        assert renewed["expires_at"]
        customer_token = renewed["customer_access_token"]

        action_data(
            await shopify_storefront.execute_action(
                "storefront_customer_logout", {"customer_access_token": customer_token}, live_context
            )
        )
        signed_out = await shopify_storefront.execute_action(
            "storefront_get_customer", {"customer_access_token": customer_token}, live_context
        )
        assert signed_out.type == ResultType.ACTION_ERROR

        action_data(
            await shopify_storefront.execute_action("storefront_recover_customer", {"email": email}, live_context)
        )
