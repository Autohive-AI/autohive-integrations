"""
Unit tests for Shopify Customer Account API Integration.

Refactored from test_unit.py with improved style, additional coverage,
and proper pytest patterns (no bare try/except).
"""

import importlib.util
import os

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from autohive_integrations_sdk.integration import ResultType, ValidationError  # noqa: E402

_spec = importlib.util.spec_from_file_location("shopify_customer_mod", os.path.join(_parent, "shopify_customer.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

shopify_customer = _mod.shopify_customer
get_shop_url = _mod.get_shop_url
get_customer_api_url = _mod.get_customer_api_url
build_headers = _mod.build_headers
generate_pkce_pair = _mod.generate_pkce_pair
build_authorization_url = _mod.build_authorization_url
extract_edges = _mod.extract_edges

pytestmark = pytest.mark.unit


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "access_token": "test_token_123",  # nosec B105
            "shop_url": "test-store.myshopify.com",
            "client_id": "test_client_id",
        }
    }
    return ctx


# ============================================================================
# Helper Functions
# ============================================================================


class TestHelpers:
    def test_get_shop_url_strips_https(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"shop_url": "https://test-store.myshopify.com/"}}
        assert get_shop_url(ctx) == "test-store.myshopify.com"

    def test_get_shop_url_strips_http(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"shop_url": "http://test-store.myshopify.com/"}}
        assert get_shop_url(ctx) == "test-store.myshopify.com"

    def test_get_shop_url_plain(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"shop_url": "test-store.myshopify.com"}}
        assert get_shop_url(ctx) == "test-store.myshopify.com"

    def test_get_customer_api_url_correct_path(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"shop_url": "test-store.myshopify.com"}}
        result = get_customer_api_url(ctx)
        assert result == "https://test-store.myshopify.com/customer/api/2024-10/graphql"
        assert "/account/" not in result

    def test_build_headers(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"access_token": "test_token"}}  # nosec B105
        result = build_headers(ctx)
        assert result["Authorization"] == "Bearer test_token"
        assert result["Content-Type"] == "application/json"


# ============================================================================
# OAuth Helpers
# ============================================================================


class TestOAuthHelpers:
    def test_generate_pkce_pair_returns_two_distinct_values(self):
        verifier, challenge = generate_pkce_pair()
        assert len(verifier) > 0
        assert len(challenge) > 0
        assert verifier != challenge

    def test_generate_pkce_pair_unique_each_call(self):
        pair_a = generate_pkce_pair()
        pair_b = generate_pkce_pair()
        assert pair_a[0] != pair_b[0]

    def test_build_authorization_url(self):
        url = build_authorization_url(
            shop_url="test-store.myshopify.com",
            client_id="test_client",
            redirect_uri="https://example.com/callback",
            scopes=["openid", "email"],
            state="test_state",
            code_challenge="test_challenge",
        )
        assert "test-store.myshopify.com" in url
        assert "/authentication/oauth/authorize" in url
        assert "client_id=test_client" in url
        assert "openid" in url
        assert "email" in url
        assert "code_challenge=test_challenge" in url
        assert "code_challenge_method=S256" in url


# ============================================================================
# extract_edges
# ============================================================================


class TestExtractEdges:
    def test_extracts_nodes_from_edges(self):
        data = {
            "orders": {
                "edges": [
                    {"node": {"id": "1", "name": "Order #1"}},
                    {"node": {"id": "2", "name": "Order #2"}},
                ],
            }
        }
        result = extract_edges(data, "orders")
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["name"] == "Order #2"

    def test_nested_path(self):
        data = {
            "customer": {
                "addresses": {
                    "edges": [{"node": {"id": "addr_1"}}],
                }
            }
        }
        result = extract_edges(data, "customer.addresses")
        assert len(result) == 1
        assert result[0]["id"] == "addr_1"

    def test_returns_empty_list_when_path_missing(self):
        assert extract_edges({}, "missing.path") == []

    def test_returns_empty_list_when_none_in_path(self):
        data = {"customer": None}
        assert extract_edges(data, "customer.addresses") == []

    def test_returns_empty_list_when_no_edges_key(self):
        data = {"orders": {"something_else": []}}
        assert extract_edges(data, "orders") == []


# ============================================================================
# Action: customer_get_profile
# ============================================================================


class TestGetProfile:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customer": {
                    "id": "gid://shopify/Customer/123",
                    "email": "test@example.com",
                    "firstName": "Test",
                    "lastName": "User",
                }
            }
        }

        result = await shopify_customer.execute_action("customer_get_profile", {}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["customer"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context):
        mock_context.fetch.return_value = {"errors": [{"message": "Unauthorized"}]}

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action("customer_get_profile", {}, mock_context)


# ============================================================================
# Action: customer_list_addresses
# ============================================================================


class TestListAddresses:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customer": {
                    "addresses": {
                        "edges": [
                            {
                                "cursor": "cursor1",
                                "node": {
                                    "id": "gid://shopify/CustomerAddress/1",
                                    "address1": "123 Main St",
                                    "city": "New York",
                                },
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "end_cursor_value",
                        },
                    },
                    "defaultAddress": {"id": "gid://shopify/CustomerAddress/1"},
                }
            }
        }

        result = await shopify_customer.execute_action("customer_list_addresses", {"first": 10}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["count"] == 1
        assert result.result.data["addresses"][0]["city"] == "New York"


# ============================================================================
# Action: customer_create_address
# ============================================================================


class TestCreateAddress:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customerAddressCreate": {
                    "customerAddress": {
                        "id": "gid://shopify/CustomerAddress/new",
                        "address1": "456 Oak Ave",
                        "city": "Los Angeles",
                    },
                    "userErrors": [],
                }
            }
        }

        result = await shopify_customer.execute_action(
            "customer_create_address",
            {
                "address1": "456 Oak Ave",
                "city": "Los Angeles",
                "country": "US",
                "zip": "90001",
            },
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["address"]["city"] == "Los Angeles"

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customerAddressCreate": {
                    "customerAddress": None,
                    "userErrors": [{"field": "zip", "message": "Invalid postal code"}],
                }
            }
        }

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_create_address",
                {
                    "address1": "456 Oak Ave",
                    "city": "LA",
                    "country": "US",
                    "zip": "invalid",
                },
                mock_context,
            )


# ============================================================================
# Action: customer_list_orders
# ============================================================================


class TestListOrders:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customer": {
                    "orders": {
                        "edges": [
                            {
                                "cursor": "cursor1",
                                "node": {
                                    "id": "gid://shopify/Order/123",
                                    "orderNumber": 1001,
                                    "totalPrice": {
                                        "amount": "99.99",
                                        "currencyCode": "USD",
                                    },
                                },
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "end_cursor_value",
                        },
                    }
                }
            }
        }

        result = await shopify_customer.execute_action("customer_list_orders", {"first": 10}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["count"] == 1
        assert result.result.data["orders"][0]["orderNumber"] == 1001


# ============================================================================
# Action: customer_get_order
# ============================================================================


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customer": {
                    "order": {
                        "id": "gid://shopify/Order/456",
                        "orderNumber": 1002,
                        "fulfillmentStatus": "FULFILLED",
                        "totalPrice": {"amount": "49.99", "currencyCode": "USD"},
                    }
                }
            }
        }

        result = await shopify_customer.execute_action(
            "customer_get_order",
            {"order_id": "gid://shopify/Order/456"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["order"]["orderNumber"] == 1002

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = {"data": {"customer": {"order": None}}}

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_get_order",
                {"order_id": "gid://shopify/Order/999"},
                mock_context,
            )


# ============================================================================
# Action: customer_set_default_address
# ============================================================================


class TestSetDefaultAddress:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customerDefaultAddressUpdate": {
                    "customer": {"defaultAddress": {"id": "gid://shopify/CustomerAddress/1"}},
                    "userErrors": [],
                }
            }
        }

        result = await shopify_customer.execute_action(
            "customer_set_default_address",
            {"address_id": "gid://shopify/CustomerAddress/1"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["default_address_id"] == "gid://shopify/CustomerAddress/1"

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = {
            "data": {
                "customerDefaultAddressUpdate": {
                    "customer": {"defaultAddress": None},
                    "userErrors": [{"field": "addressId", "message": "Address not found"}],
                }
            }
        }

        result = await shopify_customer.execute_action(
            "customer_set_default_address",
            {"address_id": "gid://shopify/CustomerAddress/999"},
            mock_context,
        )

        assert result.result.data["success"] is False
        assert "Address not found" in result.result.data["message"]


# ============================================================================
# Action: customer_generate_oauth_url
# ============================================================================


class TestGenerateOAuthUrl:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        result = await shopify_customer.execute_action(
            "customer_generate_oauth_url",
            {
                "client_id": "test_client",
                "redirect_uri": "https://example.com/callback",
            },
            mock_context,
        )

        assert result.result.data["success"] is True
        assert "authorization_url" in result.result.data
        assert "code_verifier" in result.result.data
        assert "state" in result.result.data
        assert "/authentication/oauth/authorize" in result.result.data["authorization_url"]

    @pytest.mark.asyncio
    async def test_missing_client_id(self, mock_context):
        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_generate_oauth_url",
                {"redirect_uri": "https://example.com/callback"},
                mock_context,
            )

    @pytest.mark.asyncio
    async def test_missing_redirect_uri(self, mock_context):
        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_generate_oauth_url",
                {"client_id": "test_client"},
                mock_context,
            )


# ============================================================================
# Error Handling
# ============================================================================


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_get_profile_fetch_exception(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Connection refused")

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action("customer_get_profile", {}, mock_context)

    @pytest.mark.asyncio
    async def test_list_orders_fetch_exception(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Timeout")

        result = await shopify_customer.execute_action("customer_list_orders", {"first": 10}, mock_context)

        assert result.result.data["success"] is False

    @pytest.mark.asyncio
    async def test_create_address_fetch_exception(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Network error")

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_create_address",
                {
                    "address1": "123 Main St",
                    "city": "Test",
                    "country": "US",
                    "zip": "12345",
                },
                mock_context,
            )

    @pytest.mark.asyncio
    async def test_set_default_address_fetch_exception(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Service unavailable")

        result = await shopify_customer.execute_action(
            "customer_set_default_address",
            {"address_id": "gid://shopify/CustomerAddress/1"},
            mock_context,
        )

        assert result.result.data["success"] is False

    @pytest.mark.asyncio
    async def test_get_order_fetch_exception(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Bad gateway")

        with pytest.raises(ValidationError):
            await shopify_customer.execute_action(
                "customer_get_order",
                {"order_id": "gid://shopify/Order/123"},
                mock_context,
            )
