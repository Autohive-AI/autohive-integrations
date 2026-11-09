from unittest.mock import MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType
from shopify_storefront import (
    build_headers,
    extract_edges,
    extract_user_errors,
    get_storefront_url,
    parse_graphql_response,
    require_input,
    require_one_of,
    shopify_storefront,
    validate_shop_url,
)

pytestmark = pytest.mark.unit

STOREFRONT_URL = "https://test-store.myshopify.com/api/2026-10/graphql.json"
CART_ID = "gid://shopify/Cart/abc123"
FAKE_CUSTOMER_CREDENTIAL = "customer-access-value"
FAKE_LOGIN_VALUE = "Example123!"
ROTATED_CUSTOMER_CREDENTIAL = "rotated-value"
FAKE_PRIVATE_CREDENTIAL = "private-value"
FAKE_PUBLIC_CREDENTIAL = "test-public-value"

SAMPLE_PRODUCT = {"id": "gid://shopify/Product/1", "title": "T-Shirt", "handle": "t-shirt"}
SAMPLE_COLLECTION = {"id": "gid://shopify/Collection/1", "title": "Summer", "handle": "summer"}
SAMPLE_CART = {"id": CART_ID, "checkoutUrl": "https://test-store.myshopify.com/cart/c/abc", "totalQuantity": 1}
SAMPLE_CUSTOMER = {"id": "gid://shopify/Customer/1", "email": "jane@example.com", "firstName": "Jane"}


def gql(data=None, errors=None):
    body = {}
    if data is not None:
        body["data"] = data
    if errors is not None:
        body["errors"] = errors
    return FetchResponse(status=200, headers={}, data=body)


def sent_variables(mock_context):
    return mock_context.fetch.call_args.kwargs["json"]["variables"]


# ---- Helpers ----


class TestValidateShopUrl:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("test-store.myshopify.com", "test-store.myshopify.com"),
            ("https://test-store.myshopify.com", "test-store.myshopify.com"),
            ("http://test-store.myshopify.com/", "test-store.myshopify.com"),
        ],
    )
    def test_valid_urls_are_normalised(self, raw, expected):
        assert validate_shop_url(raw) == expected

    @pytest.mark.parametrize(
        "raw, match",
        [
            ("", "Missing required credential"),
            ("evil.com/test-store.myshopify.com", "forbidden characters"),
            ("user@test-store.myshopify.com", "forbidden characters"),
            ("test-store.myshopify.com:8080", "forbidden characters"),
            ("example.com", "myshopify.com"),
        ],
    )
    def test_invalid_urls_raise(self, raw, match):
        with pytest.raises(ValueError, match=match):
            validate_shop_url(raw)


class TestBuildHeaders:
    def test_public_token_header(self, mock_context):
        headers = build_headers(mock_context)
        assert headers["X-Shopify-Storefront-Access-Token"] == "test-public-value"
        assert headers["Content-Type"] == "application/json"

    def test_private_token_header_with_buyer_ip(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"private_token": FAKE_PRIVATE_CREDENTIAL, "buyer_ip": "203.0.113.5"}}
        headers = build_headers(ctx)
        assert headers["Shopify-Storefront-Private-Token"] == FAKE_PRIVATE_CREDENTIAL
        assert headers["Shopify-Storefront-Buyer-IP"] == "203.0.113.5"
        assert "X-Shopify-Storefront-Access-Token" not in headers

    def test_private_token_wins_when_both_set(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"private_token": FAKE_PRIVATE_CREDENTIAL, "public_token": FAKE_PUBLIC_CREDENTIAL}}
        headers = build_headers(ctx)
        assert headers["Shopify-Storefront-Private-Token"] == FAKE_PRIVATE_CREDENTIAL
        assert "X-Shopify-Storefront-Access-Token" not in headers

    def test_buyer_ip_ignored_for_public_token(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"public_token": FAKE_PUBLIC_CREDENTIAL, "buyer_ip": "203.0.113.5"}}
        headers = build_headers(ctx)
        assert headers["X-Shopify-Storefront-Access-Token"] == FAKE_PUBLIC_CREDENTIAL
        assert "Shopify-Storefront-Buyer-IP" not in headers

    def test_no_token_raises(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {}}
        with pytest.raises(ValueError, match="public_token or private_token"):
            build_headers(ctx)

    @pytest.mark.asyncio
    async def test_connection_without_any_token_is_rejected(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {"shop_url": "test-store.myshopify.com"}}

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_with_only_private_token_is_accepted(self, mock_context):
        mock_context.auth = {
            "auth_type": "Custom",
            "credentials": {"shop_url": "test-store.myshopify.com", "private_token": FAKE_PRIVATE_CREDENTIAL},
        }
        mock_context.fetch.return_value = gql({"products": {"edges": [], "pageInfo": {}}})

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.ACTION

    def test_storefront_url(self, mock_context):
        assert get_storefront_url(mock_context) == STOREFRONT_URL


class TestInputHelpers:
    def test_require_input_returns_value(self):
        assert require_input("abc", "cart_id") == "abc"

    @pytest.mark.parametrize("value", [None, ""])
    def test_require_input_rejects_empty(self, value):
        with pytest.raises(ValueError, match="Missing required parameter: cart_id"):
            require_input(value, "cart_id")

    def test_require_one_of_passes_when_any_present(self):
        require_one_of({"product_id": "1"}, "handle", "product_id")

    def test_require_one_of_raises_when_none_present(self):
        with pytest.raises(ValueError, match="handle, product_id"):
            require_one_of({}, "handle", "product_id")


class TestResponseHelpers:
    def test_parse_graphql_response_with_error_codes(self):
        data, errors = parse_graphql_response(
            {"data": {"x": 1}, "errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}, {}]}
        )
        assert data == {"x": 1}
        assert errors == ["THROTTLED: Throttled", "GraphQL error"]

    def test_parse_graphql_response_non_dict(self):
        assert parse_graphql_response("oops") == (None, ["Invalid response type from API"])

    def test_extract_user_errors(self):
        data = {"cartLinesAdd": {"userErrors": [{"message": "Bad line"}, {"field": "x"}]}}
        assert extract_user_errors(data, "cartLinesAdd") == ["Bad line"]

    def test_extract_user_errors_empty(self):
        assert extract_user_errors(None, "cartLinesAdd") == []
        assert extract_user_errors({"cartLinesAdd": None}, "cartLinesAdd") == []

    def test_extract_edges(self):
        data = {"products": {"edges": [{"node": {"id": "1"}}, {"node": {"id": "2"}}]}}
        assert extract_edges(data, "products") == [{"id": "1"}, {"id": "2"}]

    def test_extract_edges_missing_path(self):
        assert extract_edges({}, "products") == []


# ---- Product Actions ----


class TestListProducts:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "products": {
                    "edges": [{"node": SAMPLE_PRODUCT}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                }
            }
        )

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True
        assert result.result.data["products"] == [SAMPLE_PRODUCT]
        assert result.result.data["count"] == 1
        assert result.result.data["has_next_page"] is True
        assert result.result.data["end_cursor"] == "cur1"

    @pytest.mark.asyncio
    async def test_request_url_method_and_headers(self, mock_context):
        mock_context.fetch.return_value = gql({"products": {"edges": [], "pageInfo": {}}})

        await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == STOREFRONT_URL
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["headers"]["X-Shopify-Storefront-Access-Token"] == "test-public-value"

    @pytest.mark.asyncio
    async def test_default_first_and_passthrough(self, mock_context):
        mock_context.fetch.return_value = gql({"products": {"edges": [], "pageInfo": {}}})

        await shopify_storefront.execute_action("storefront_list_products", {"query": "tag:sale"}, mock_context)

        variables = sent_variables(mock_context)
        assert variables["first"] == 20
        assert variables["query"] == "tag:sale"
        assert variables["after"] is None

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context):
        mock_context.fetch.return_value = gql(errors=[{"message": "Access denied"}])

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Access denied"

    @pytest.mark.asyncio
    async def test_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_invalid_shop_url_returns_error(self, mock_context):
        mock_context.auth["credentials"]["shop_url"] = "example.com"

        result = await shopify_storefront.execute_action("storefront_list_products", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "myshopify.com" in result.result.message
        mock_context.fetch.assert_not_called()


class TestGetProduct:
    @pytest.mark.asyncio
    async def test_by_handle(self, mock_context):
        mock_context.fetch.return_value = gql({"product": SAMPLE_PRODUCT})

        result = await shopify_storefront.execute_action("storefront_get_product", {"handle": "t-shirt"}, mock_context)

        assert result.result.data == {"success": True, "product": SAMPLE_PRODUCT}
        assert sent_variables(mock_context) == {"handle": "t-shirt"}
        query = mock_context.fetch.call_args.kwargs["json"]["query"]
        assert "product(handle: $handle)" in query
        assert "$id" not in query

    @pytest.mark.asyncio
    async def test_by_id(self, mock_context):
        mock_context.fetch.return_value = gql({"product": SAMPLE_PRODUCT})

        await shopify_storefront.execute_action(
            "storefront_get_product", {"product_id": "gid://shopify/Product/1"}, mock_context
        )

        assert sent_variables(mock_context) == {"id": "gid://shopify/Product/1"}
        query = mock_context.fetch.call_args.kwargs["json"]["query"]
        assert "product(id: $id)" in query
        assert "$handle" not in query

    @pytest.mark.asyncio
    async def test_missing_identifier(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_product", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "handle, product_id" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"product": None})

        result = await shopify_storefront.execute_action("storefront_get_product", {"handle": "nope"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Product not found"

    @pytest.mark.asyncio
    async def test_graphql_errors_joined(self, mock_context):
        mock_context.fetch.return_value = gql(errors=[{"message": "A"}, {"message": "B"}])

        result = await shopify_storefront.execute_action("storefront_get_product", {"handle": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "A; B"


class TestSearchProducts:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"search": {"edges": [{"node": SAMPLE_PRODUCT}], "totalCount": 42}})

        result = await shopify_storefront.execute_action("storefront_search_products", {"query": "shirt"}, mock_context)

        assert result.result.data["products"] == [SAMPLE_PRODUCT]
        assert result.result.data["count"] == 1
        assert result.result.data["total_count"] == 42

    @pytest.mark.asyncio
    async def test_variables(self, mock_context):
        mock_context.fetch.return_value = gql({"search": {"edges": []}})

        await shopify_storefront.execute_action(
            "storefront_search_products", {"query": "shirt", "first": 5}, mock_context
        )

        assert sent_variables(mock_context) == {"query": "shirt", "first": 5}

    @pytest.mark.asyncio
    async def test_missing_query_is_validation_error(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_search_products", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context):
        mock_context.fetch.return_value = gql(errors=[{"message": "Bad query"}])

        result = await shopify_storefront.execute_action("storefront_search_products", {"query": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Bad query"


# ---- Collection Actions ----


class TestListCollections:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"collections": {"edges": [{"node": SAMPLE_COLLECTION}], "pageInfo": {"hasNextPage": False}}}
        )

        result = await shopify_storefront.execute_action("storefront_list_collections", {}, mock_context)

        assert result.result.data["collections"] == [SAMPLE_COLLECTION]
        assert result.result.data["count"] == 1
        assert result.result.data["has_next_page"] is False
        assert result.result.data["end_cursor"] is None

    @pytest.mark.asyncio
    async def test_pagination_variables(self, mock_context):
        mock_context.fetch.return_value = gql({"collections": {"edges": [], "pageInfo": {}}})

        await shopify_storefront.execute_action(
            "storefront_list_collections", {"first": 10, "after": "cur"}, mock_context
        )

        assert sent_variables(mock_context) == {"first": 10, "after": "cur"}

    @pytest.mark.asyncio
    async def test_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 500")

        result = await shopify_storefront.execute_action("storefront_list_collections", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


class TestGetCollection:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"collection": SAMPLE_COLLECTION})

        result = await shopify_storefront.execute_action(
            "storefront_get_collection", {"handle": "summer"}, mock_context
        )

        assert result.result.data == {"success": True, "collection": SAMPLE_COLLECTION}

    @pytest.mark.asyncio
    async def test_variables_default_products_first(self, mock_context):
        mock_context.fetch.return_value = gql({"collection": SAMPLE_COLLECTION})

        await shopify_storefront.execute_action(
            "storefront_get_collection", {"collection_id": "gid://shopify/Collection/1"}, mock_context
        )

        assert sent_variables(mock_context) == {"id": "gid://shopify/Collection/1", "first": 20}
        query = mock_context.fetch.call_args.kwargs["json"]["query"]
        assert "collection(id: $id)" in query
        assert "$handle" not in query

    @pytest.mark.asyncio
    async def test_missing_identifier(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_collection", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"collection": None})

        result = await shopify_storefront.execute_action("storefront_get_collection", {"handle": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Collection not found"


# ---- Cart Actions ----


class TestCreateCart:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"cartCreate": {"cart": SAMPLE_CART, "userErrors": []}})

        result = await shopify_storefront.execute_action(
            "storefront_create_cart",
            {"lines": [{"merchandiseId": "gid://shopify/ProductVariant/1", "quantity": 1}]},
            mock_context,
        )

        assert result.result.data == {"success": True, "cart": SAMPLE_CART}

    @pytest.mark.asyncio
    async def test_maps_buyer_identity(self, mock_context):
        mock_context.fetch.return_value = gql({"cartCreate": {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action(
            "storefront_create_cart", {"buyer_identity": {"email": "jane@example.com"}}, mock_context
        )

        assert sent_variables(mock_context) == {"input": {"buyerIdentity": {"email": "jane@example.com"}}}

    @pytest.mark.asyncio
    async def test_empty_cart_sends_empty_input(self, mock_context):
        mock_context.fetch.return_value = gql({"cartCreate": {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action("storefront_create_cart", {}, mock_context)

        assert sent_variables(mock_context) == {"input": {}}

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"cartCreate": {"cart": None, "userErrors": [{"message": "Variant not found"}]}}
        )

        result = await shopify_storefront.execute_action("storefront_create_cart", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Variant not found"


class TestCartWarnings:
    STOCK_WARNING = {
        "code": "MERCHANDISE_NOT_ENOUGH_STOCK",
        "message": "Only 0 items were added to your cart due to stock availability.",
        "target": "gid://shopify/CartLine/1",
    }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action, mutation_key, inputs",
        [
            ("storefront_create_cart", "cartCreate", {"lines": [{"merchandiseId": "v1", "quantity": 1}]}),
            ("storefront_add_to_cart", "cartLinesAdd", {"cart_id": CART_ID, "lines": [{"merchandiseId": "v1"}]}),
            (
                "storefront_update_cart_line",
                "cartLinesUpdate",
                {"cart_id": CART_ID, "lines": [{"id": "l1", "quantity": 2}]},
            ),
        ],
    )
    async def test_warnings_returned(self, mock_context, action, mutation_key, inputs):
        mock_context.fetch.return_value = gql(
            {mutation_key: {"cart": SAMPLE_CART, "userErrors": [], "warnings": [self.STOCK_WARNING]}}
        )

        result = await shopify_storefront.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"success": True, "cart": SAMPLE_CART, "warnings": [self.STOCK_WARNING]}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("storefront_create_cart", {}),
            ("storefront_add_to_cart", {"cart_id": CART_ID, "lines": [{"merchandiseId": "v1"}]}),
            ("storefront_update_cart_line", {"cart_id": CART_ID, "lines": [{"id": "l1", "quantity": 2}]}),
        ],
    )
    async def test_query_requests_warnings(self, mock_context, action, inputs):
        mock_context.fetch.return_value = gql({})

        await shopify_storefront.execute_action(action, inputs, mock_context)

        assert "warnings { code message target }" in mock_context.fetch.call_args.kwargs["json"]["query"]

    @pytest.mark.asyncio
    async def test_empty_warnings_omitted(self, mock_context):
        mock_context.fetch.return_value = gql({"cartLinesAdd": {"cart": SAMPLE_CART, "userErrors": [], "warnings": []}})

        result = await shopify_storefront.execute_action(
            "storefront_add_to_cart", {"cart_id": CART_ID, "lines": [{"merchandiseId": "v1"}]}, mock_context
        )

        assert result.result.data == {"success": True, "cart": SAMPLE_CART}


class TestGetCart:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"cart": SAMPLE_CART})

        result = await shopify_storefront.execute_action("storefront_get_cart", {"cart_id": CART_ID}, mock_context)

        assert result.result.data == {"success": True, "cart": SAMPLE_CART}
        assert sent_variables(mock_context) == {"cartId": CART_ID}

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"cart": None})

        result = await shopify_storefront.execute_action("storefront_get_cart", {"cart_id": CART_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Cart not found"

    @pytest.mark.asyncio
    async def test_empty_cart_id(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_cart", {"cart_id": ""}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "cart_id" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_cart_id_is_validation_error(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_cart", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR


CART_LINE_ACTIONS = [
    ("storefront_add_to_cart", "cartLinesAdd", "lines", "lines", [{"merchandiseId": "v1", "quantity": 2}]),
    ("storefront_update_cart_line", "cartLinesUpdate", "lines", "lines", [{"id": "line1", "quantity": 3}]),
    ("storefront_remove_from_cart", "cartLinesRemove", "line_ids", "lineIds", ["line1"]),
    ("storefront_apply_discount", "cartDiscountCodesUpdate", "discount_codes", "discountCodes", ["SAVE10"]),
]


@pytest.mark.parametrize("action, mutation_key, input_key, variable_key, value", CART_LINE_ACTIONS)
class TestCartMutations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context, action, mutation_key, input_key, variable_key, value):
        mock_context.fetch.return_value = gql({mutation_key: {"cart": SAMPLE_CART, "userErrors": []}})

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: value}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"success": True, "cart": SAMPLE_CART}

    @pytest.mark.asyncio
    async def test_request_variables(self, mock_context, action, mutation_key, input_key, variable_key, value):
        mock_context.fetch.return_value = gql({mutation_key: {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: value}, mock_context)

        assert mock_context.fetch.call_args.args[0] == STOREFRONT_URL
        assert sent_variables(mock_context) == {"cartId": CART_ID, variable_key: value}

    @pytest.mark.asyncio
    async def test_empty_list_rejected(self, mock_context, action, mutation_key, input_key, variable_key, value):
        if action == "storefront_apply_discount":
            pytest.skip("an empty list clears discount codes; see TestApplyDiscount")

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: []}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_errors_joined(self, mock_context, action, mutation_key, input_key, variable_key, value):
        mock_context.fetch.return_value = gql(
            {mutation_key: {"cart": None, "userErrors": [{"message": "First"}, {"message": "Second"}]}}
        )

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: value}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "First; Second"

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context, action, mutation_key, input_key, variable_key, value):
        mock_context.fetch.return_value = gql(errors=[{"message": "Cart expired", "extensions": {"code": "GONE"}}])

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: value}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "GONE: Cart expired"

    @pytest.mark.asyncio
    async def test_exception(self, mock_context, action, mutation_key, input_key, variable_key, value):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: value}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message


# ---- Customer Actions ----


class TestApplyDiscount:
    @pytest.mark.asyncio
    async def test_empty_list_clears_codes(self, mock_context):
        mock_context.fetch.return_value = gql({"cartDiscountCodesUpdate": {"cart": SAMPLE_CART, "userErrors": []}})

        result = await shopify_storefront.execute_action(
            "storefront_apply_discount", {"cart_id": CART_ID, "discount_codes": []}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert sent_variables(mock_context) == {"cartId": CART_ID, "discountCodes": []}

    @pytest.mark.asyncio
    async def test_non_list_rejected(self, mock_context):
        result = await shopify_storefront.execute_action(
            "storefront_apply_discount", {"cart_id": CART_ID, "discount_codes": "SAVE10"}, mock_context
        )

        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
        mock_context.fetch.assert_not_called()


class TestCreateCustomer:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": SAMPLE_CUSTOMER, "customerUserErrors": []}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_create_customer",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.result.data == {"success": True, "customer": SAMPLE_CUSTOMER}

    @pytest.mark.asyncio
    async def test_maps_optional_fields_to_camel_case(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": SAMPLE_CUSTOMER, "customerUserErrors": []}}
        )

        await shopify_storefront.execute_action(
            "storefront_create_customer",
            {
                "email": "jane@example.com",
                "password": FAKE_LOGIN_VALUE,
                "first_name": "Jane",
                "last_name": "Doe",
                "phone": "+15555550100",
                "accepts_marketing": False,
            },
            mock_context,
        )

        assert sent_variables(mock_context)["input"] == {
            "email": "jane@example.com",
            "password": FAKE_LOGIN_VALUE,
            "firstName": "Jane",
            "lastName": "Doe",
            "phone": "+15555550100",
            "acceptsMarketing": False,
        }

    @pytest.mark.asyncio
    async def test_omits_unset_optional_fields(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": SAMPLE_CUSTOMER, "customerUserErrors": []}}
        )

        await shopify_storefront.execute_action(
            "storefront_create_customer",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert set(sent_variables(mock_context)["input"]) == {"email", "password"}

    @pytest.mark.asyncio
    async def test_accepts_legacy_camel_case_fields(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": SAMPLE_CUSTOMER, "customerUserErrors": []}}
        )

        await shopify_storefront.execute_action(
            "storefront_create_customer",
            {
                "email": "jane@example.com",
                "password": FAKE_LOGIN_VALUE,
                "firstName": "Jane",
                "lastName": "Doe",
                "acceptsMarketing": True,
            },
            mock_context,
        )

        sent = sent_variables(mock_context)["input"]
        assert sent["firstName"] == "Jane"
        assert sent["lastName"] == "Doe"
        assert sent["acceptsMarketing"] is True

    @pytest.mark.asyncio
    async def test_snake_case_wins_over_camel_case(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": SAMPLE_CUSTOMER, "customerUserErrors": []}}
        )

        await shopify_storefront.execute_action(
            "storefront_create_customer",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE, "first_name": "Snake", "firstName": "Camel"},
            mock_context,
        )

        assert sent_variables(mock_context)["input"]["firstName"] == "Snake"

    @pytest.mark.asyncio
    async def test_customer_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerCreate": {"customer": None, "customerUserErrors": [{"message": "Email has already been taken"}]}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_create_customer",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Email has already been taken"

    @pytest.mark.asyncio
    async def test_missing_password_is_validation_error(self, mock_context):
        result = await shopify_storefront.execute_action(
            "storefront_create_customer", {"email": "jane@example.com"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR


class TestCustomerLogin:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "customerAccessTokenCreate": {
                    "customerAccessToken": {"accessToken": FAKE_CUSTOMER_CREDENTIAL, "expiresAt": "2026-12-01"},
                    "customerUserErrors": [],
                }
            }
        )

        result = await shopify_storefront.execute_action(
            "storefront_customer_login",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.result.data == {
            "success": True,
            "customer_access_token": FAKE_CUSTOMER_CREDENTIAL,
            "expires_at": "2026-12-01",
        }
        assert sent_variables(mock_context) == {"input": {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE}}

    @pytest.mark.asyncio
    async def test_bad_credentials(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "customerAccessTokenCreate": {
                    "customerAccessToken": None,
                    "customerUserErrors": [{"message": "Unidentified customer"}],
                }
            }
        )

        result = await shopify_storefront.execute_action(
            "storefront_customer_login",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Unidentified customer"

    @pytest.mark.asyncio
    async def test_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network down")

        result = await shopify_storefront.execute_action(
            "storefront_customer_login",
            {"email": "jane@example.com", "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Network down" in result.result.message


class TestGetCustomer:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"customer": SAMPLE_CUSTOMER})

        result = await shopify_storefront.execute_action(
            "storefront_get_customer", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.result.data == {"success": True, "customer": SAMPLE_CUSTOMER}
        assert sent_variables(mock_context) == {"customerAccessToken": FAKE_CUSTOMER_CREDENTIAL}

    @pytest.mark.asyncio
    async def test_invalid_token(self, mock_context):
        mock_context.fetch.return_value = gql({"customer": None})

        result = await shopify_storefront.execute_action(
            "storefront_get_customer", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Customer not found or invalid token"


class TestRecoverCustomer:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"customerRecover": {"customerUserErrors": []}})

        result = await shopify_storefront.execute_action(
            "storefront_recover_customer", {"email": "jane@example.com"}, mock_context
        )

        assert result.result.data == {"success": True, "message": "Recovery email sent if account exists"}
        assert sent_variables(mock_context) == {"email": "jane@example.com"}

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerRecover": {"customerUserErrors": [{"message": "Too many requests"}]}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_recover_customer", {"email": "jane@example.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Too many requests"


class TestUpdateCustomer:
    @pytest.mark.asyncio
    async def test_happy_path_returns_rotated_token(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "customerUpdate": {
                    "customer": SAMPLE_CUSTOMER,
                    "customerAccessToken": {"accessToken": ROTATED_CUSTOMER_CREDENTIAL, "expiresAt": "2027-01-01"},
                    "customerUserErrors": [],
                }
            }
        )

        result = await shopify_storefront.execute_action(
            "storefront_update_customer",
            {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL, "password": FAKE_LOGIN_VALUE},
            mock_context,
        )

        assert result.result.data == {
            "success": True,
            "customer": SAMPLE_CUSTOMER,
            "customer_access_token": ROTATED_CUSTOMER_CREDENTIAL,
            "expires_at": "2027-01-01",
        }

    @pytest.mark.asyncio
    async def test_maps_fields_and_skips_none(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerUpdate": {"customer": SAMPLE_CUSTOMER, "customerAccessToken": None, "customerUserErrors": []}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_update_customer",
            {
                "customer_access_token": FAKE_CUSTOMER_CREDENTIAL,
                "first_name": "Janet",
                "last_name": "Doe",
                "email": "janet@example.com",
                "phone": "+15555550101",
                "accepts_marketing": True,
            },
            mock_context,
        )

        assert sent_variables(mock_context) == {
            "customerAccessToken": FAKE_CUSTOMER_CREDENTIAL,
            "customer": {
                "firstName": "Janet",
                "lastName": "Doe",
                "email": "janet@example.com",
                "phone": "+15555550101",
                "acceptsMarketing": True,
            },
        }
        assert result.result.data["customer_access_token"] is None

    @pytest.mark.asyncio
    async def test_no_fields_rejected(self, mock_context):
        result = await shopify_storefront.execute_action(
            "storefront_update_customer", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "At least one customer field" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerUpdate": {"customer": None, "customerUserErrors": [{"message": "Phone is invalid"}]}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_update_customer",
            {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL, "phone": "bad"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Phone is invalid"


def sent_query(mock_context):
    return mock_context.fetch.call_args.kwargs["json"]["query"]


# ---- Cart: buyer identity, note, attributes, gift cards ----

NEW_CART_MUTATIONS = [
    (
        "storefront_update_cart_buyer_identity",
        "cartBuyerIdentityUpdate",
        {"country_code": "CA"},
        {"buyerIdentity": {"countryCode": "CA"}},
    ),
    ("storefront_update_cart_note", "cartNoteUpdate", {"note": "Gift wrap please"}, {"note": "Gift wrap please"}),
    (
        "storefront_update_cart_attributes",
        "cartAttributesUpdate",
        {"attributes": [{"key": "Engraving", "value": "Happy Birthday"}]},
        {"attributes": [{"key": "Engraving", "value": "Happy Birthday"}]},
    ),
    (
        "storefront_add_gift_cards",
        "cartGiftCardCodesAdd",
        {"gift_card_codes": ["GIFT-1234"]},
        {"giftCardCodes": ["GIFT-1234"]},
    ),
    (
        "storefront_remove_gift_cards",
        "cartGiftCardCodesRemove",
        {"applied_gift_card_ids": ["gid://shopify/AppliedGiftCard/1"]},
        {"appliedGiftCardIds": ["gid://shopify/AppliedGiftCard/1"]},
    ),
]


@pytest.mark.parametrize("action, mutation_key, inputs, expected_variables", NEW_CART_MUTATIONS)
class TestNewCartMutations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context, action, mutation_key, inputs, expected_variables):
        mock_context.fetch.return_value = gql({mutation_key: {"cart": SAMPLE_CART, "userErrors": [], "warnings": []}})

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"success": True, "cart": SAMPLE_CART}

    @pytest.mark.asyncio
    async def test_request_variables(self, mock_context, action, mutation_key, inputs, expected_variables):
        mock_context.fetch.return_value = gql({mutation_key: {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert mock_context.fetch.call_args.args[0] == STOREFRONT_URL
        assert sent_variables(mock_context) == {"cartId": CART_ID, **expected_variables}
        assert f"{mutation_key}(" in sent_query(mock_context)

    @pytest.mark.asyncio
    async def test_warnings_returned(self, mock_context, action, mutation_key, inputs, expected_variables):
        warning = {"code": "PAYMENTS_GIFT_CARDS_UNAVAILABLE", "message": "Gift cards unavailable", "target": CART_ID}
        mock_context.fetch.return_value = gql(
            {mutation_key: {"cart": SAMPLE_CART, "userErrors": [], "warnings": [warning]}}
        )

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert result.result.data["warnings"] == [warning]

    @pytest.mark.asyncio
    async def test_user_errors_joined(self, mock_context, action, mutation_key, inputs, expected_variables):
        mock_context.fetch.return_value = gql(
            {mutation_key: {"cart": None, "userErrors": [{"message": "First"}, {"message": "Second"}]}}
        )

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "First; Second"

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context, action, mutation_key, inputs, expected_variables):
        mock_context.fetch.return_value = gql(errors=[{"message": "Cart expired", "extensions": {"code": "GONE"}}])

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "GONE: Cart expired"

    @pytest.mark.asyncio
    async def test_empty_cart_id(self, mock_context, action, mutation_key, inputs, expected_variables):
        result = await shopify_storefront.execute_action(action, {"cart_id": "", **inputs}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "cart_id" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception(self, mock_context, action, mutation_key, inputs, expected_variables):
        mock_context.fetch.side_effect = Exception("Network down")

        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, **inputs}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network down" in result.result.message


class TestUpdateCartBuyerIdentity:
    @pytest.mark.asyncio
    async def test_maps_all_fields(self, mock_context):
        mock_context.fetch.return_value = gql({"cartBuyerIdentityUpdate": {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action(
            "storefront_update_cart_buyer_identity",
            {
                "cart_id": CART_ID,
                "customer_access_token": FAKE_CUSTOMER_CREDENTIAL,
                "email": "jane@example.com",
                "phone": "+16135551111",
                "country_code": "US",
            },
            mock_context,
        )

        assert sent_variables(mock_context)["buyerIdentity"] == {
            "customerAccessToken": FAKE_CUSTOMER_CREDENTIAL,
            "email": "jane@example.com",
            "phone": "+16135551111",
            "countryCode": "US",
        }

    @pytest.mark.asyncio
    async def test_blank_fields_dropped(self, mock_context):
        mock_context.fetch.return_value = gql({"cartBuyerIdentityUpdate": {"cart": SAMPLE_CART, "userErrors": []}})

        await shopify_storefront.execute_action(
            "storefront_update_cart_buyer_identity",
            {"cart_id": CART_ID, "email": "", "country_code": "CA"},
            mock_context,
        )

        assert sent_variables(mock_context)["buyerIdentity"] == {"countryCode": "CA"}

    @pytest.mark.asyncio
    async def test_no_fields_rejected(self, mock_context):
        result = await shopify_storefront.execute_action(
            "storefront_update_cart_buyer_identity", {"cart_id": CART_ID}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "At least one buyer identity field" in result.result.message
        mock_context.fetch.assert_not_called()


class TestUpdateCartNote:
    @pytest.mark.asyncio
    async def test_empty_note_clears(self, mock_context):
        mock_context.fetch.return_value = gql({"cartNoteUpdate": {"cart": SAMPLE_CART, "userErrors": []}})

        result = await shopify_storefront.execute_action(
            "storefront_update_cart_note", {"cart_id": CART_ID, "note": ""}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert sent_variables(mock_context) == {"cartId": CART_ID, "note": ""}

    @pytest.mark.asyncio
    async def test_missing_note_is_validation_error(self, mock_context):
        result = await shopify_storefront.execute_action(
            "storefront_update_cart_note", {"cart_id": CART_ID}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR


class TestUpdateCartAttributes:
    @pytest.mark.asyncio
    async def test_empty_list_clears(self, mock_context):
        mock_context.fetch.return_value = gql({"cartAttributesUpdate": {"cart": SAMPLE_CART, "userErrors": []}})

        result = await shopify_storefront.execute_action(
            "storefront_update_cart_attributes", {"cart_id": CART_ID, "attributes": []}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert sent_variables(mock_context) == {"cartId": CART_ID, "attributes": []}


class TestGiftCards:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action, input_key",
        [("storefront_add_gift_cards", "gift_card_codes"), ("storefront_remove_gift_cards", "applied_gift_card_ids")],
    )
    async def test_empty_list_rejected(self, mock_context, action, input_key):
        result = await shopify_storefront.execute_action(action, {"cart_id": CART_ID, input_key: []}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "non-empty array" in result.result.message
        mock_context.fetch.assert_not_called()


class TestGetCartFields:
    @pytest.mark.asyncio
    async def test_query_includes_note_attributes_buyer_and_gift_cards(self, mock_context):
        mock_context.fetch.return_value = gql({"cart": SAMPLE_CART})

        await shopify_storefront.execute_action("storefront_get_cart", {"cart_id": CART_ID}, mock_context)

        query = sent_query(mock_context)
        for field in ("note", "attributes { key value }", "buyerIdentity", "appliedGiftCards"):
            assert field in query

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("storefront_get_cart", {"cart_id": CART_ID}),
            ("storefront_update_cart_note", {"cart_id": CART_ID, "note": "Hi"}),
        ],
    )
    async def test_cart_reads_do_not_need_customer_scope(self, mock_context, action, inputs):
        # buyerIdentity.customer needs unauthenticated_read_customers; ordinary cart calls must not.
        mock_context.fetch.return_value = gql({"cart": SAMPLE_CART})

        await shopify_storefront.execute_action(action, inputs, mock_context)

        assert "customer {" not in sent_query(mock_context)


# ---- Customer: logout and token renew ----


class TestCustomerLogout:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerAccessTokenDelete": {"deletedAccessToken": FAKE_CUSTOMER_CREDENTIAL, "userErrors": []}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_customer_logout", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.result.data == {"success": True, "message": "Customer signed out"}
        assert sent_variables(mock_context) == {"customerAccessToken": FAKE_CUSTOMER_CREDENTIAL}

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerAccessTokenDelete": {"deletedAccessToken": None, "userErrors": [{"message": "Access denied"}]}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_customer_logout", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Access denied"

    @pytest.mark.asyncio
    async def test_missing_token_is_validation_error(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_customer_logout", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR


class TestCustomerLogoutUnknownToken:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload", [None, {"deletedAccessToken": None, "userErrors": []}], ids=["null_payload", "nothing_deleted"]
    )
    async def test_unknown_token_is_error(self, mock_context, payload):
        mock_context.fetch.return_value = gql({"customerAccessTokenDelete": payload})

        result = await shopify_storefront.execute_action(
            "storefront_customer_logout", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Customer access token not found or already signed out"


class TestRenewCustomerToken:
    @pytest.mark.asyncio
    async def test_null_payload_is_error(self, mock_context):
        mock_context.fetch.return_value = gql({"customerAccessTokenRenew": None})

        result = await shopify_storefront.execute_action(
            "storefront_renew_customer_token", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Customer access token could not be renewed"

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "customerAccessTokenRenew": {
                    "customerAccessToken": {"accessToken": ROTATED_CUSTOMER_CREDENTIAL, "expiresAt": "2027-01-01"},
                    "userErrors": [],
                }
            }
        )

        result = await shopify_storefront.execute_action(
            "storefront_renew_customer_token", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.result.data == {
            "success": True,
            "customer_access_token": ROTATED_CUSTOMER_CREDENTIAL,
            "expires_at": "2027-01-01",
        }

    @pytest.mark.asyncio
    async def test_expired_token_without_errors_is_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerAccessTokenRenew": {"customerAccessToken": None, "userErrors": []}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_renew_customer_token", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "could not be renewed" in result.result.message

    @pytest.mark.asyncio
    async def test_user_error(self, mock_context):
        mock_context.fetch.return_value = gql(
            {"customerAccessTokenRenew": {"customerAccessToken": None, "userErrors": [{"message": "Access denied"}]}}
        )

        result = await shopify_storefront.execute_action(
            "storefront_renew_customer_token", {"customer_access_token": FAKE_CUSTOMER_CREDENTIAL}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Access denied"


# ---- Content ----

SAMPLE_POLICY = {"title": "Refund policy", "handle": "refund-policy", "url": "https://example.com/r", "body": "30 days"}
SAMPLE_PAGE = {"id": "gid://shopify/Page/1", "title": "FAQ", "handle": "faq"}
SAMPLE_ARTICLE = {"id": "gid://shopify/Article/1", "title": "News", "handle": "news"}


class TestGetShopPolicies:
    @pytest.mark.asyncio
    async def test_happy_path_maps_policies(self, mock_context):
        mock_context.fetch.return_value = gql({"shop": {"refundPolicy": SAMPLE_POLICY, "privacyPolicy": None}})

        result = await shopify_storefront.execute_action("storefront_get_shop_policies", {}, mock_context)

        assert result.result.data == {
            "success": True,
            "policies": {
                "privacy_policy": None,
                "refund_policy": SAMPLE_POLICY,
                "shipping_policy": None,
                "terms_of_service": None,
                "subscription_policy": None,
            },
        }

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context):
        mock_context.fetch.return_value = gql(errors=[{"message": "Throttled", "extensions": {"code": "THROTTLED"}}])

        result = await shopify_storefront.execute_action("storefront_get_shop_policies", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "THROTTLED: Throttled"


@pytest.mark.parametrize(
    "action, connection, output_key, item",
    [
        ("storefront_list_pages", "pages", "pages", SAMPLE_PAGE),
        ("storefront_list_articles", "articles", "articles", SAMPLE_ARTICLE),
    ],
)
class TestListContent:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context, action, connection, output_key, item):
        mock_context.fetch.return_value = gql(
            {connection: {"edges": [{"node": item}], "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}}
        )

        result = await shopify_storefront.execute_action(action, {"first": 5, "query": "tag:news"}, mock_context)

        assert result.result.data == {
            "success": True,
            output_key: [item],
            "count": 1,
            "has_next_page": True,
            "end_cursor": "c1",
        }
        assert sent_variables(mock_context) == {"first": 5, "after": None, "query": "tag:news"}

    @pytest.mark.asyncio
    async def test_default_first(self, mock_context, action, connection, output_key, item):
        mock_context.fetch.return_value = gql({connection: {"edges": [], "pageInfo": {"hasNextPage": False}}})

        result = await shopify_storefront.execute_action(action, {}, mock_context)

        assert sent_variables(mock_context)["first"] == 20
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_graphql_error(self, mock_context, action, connection, output_key, item):
        mock_context.fetch.return_value = gql(errors=[{"message": "Bad query"}])

        result = await shopify_storefront.execute_action(action, {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Bad query"


class TestGetPage:
    @pytest.mark.asyncio
    async def test_by_handle_sends_handle_only(self, mock_context):
        mock_context.fetch.return_value = gql({"page": SAMPLE_PAGE})

        result = await shopify_storefront.execute_action("storefront_get_page", {"handle": "faq"}, mock_context)

        assert result.result.data == {"success": True, "page": SAMPLE_PAGE}
        assert sent_variables(mock_context) == {"handle": "faq"}
        assert "page(handle: $handle)" in sent_query(mock_context)

    @pytest.mark.asyncio
    async def test_by_id_sends_id_only(self, mock_context):
        mock_context.fetch.return_value = gql({"page": SAMPLE_PAGE})

        await shopify_storefront.execute_action(
            "storefront_get_page", {"handle": "faq", "page_id": SAMPLE_PAGE["id"]}, mock_context
        )

        assert sent_variables(mock_context) == {"id": SAMPLE_PAGE["id"]}
        assert "page(id: $id)" in sent_query(mock_context)

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"page": None})

        result = await shopify_storefront.execute_action("storefront_get_page", {"handle": "nope"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Page not found"

    @pytest.mark.asyncio
    async def test_requires_handle_or_id(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_page", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


class TestGetArticle:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql({"article": SAMPLE_ARTICLE})

        result = await shopify_storefront.execute_action(
            "storefront_get_article", {"article_id": SAMPLE_ARTICLE["id"]}, mock_context
        )

        assert result.result.data == {"success": True, "article": SAMPLE_ARTICLE}
        assert sent_variables(mock_context) == {"id": SAMPLE_ARTICLE["id"]}

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"article": None})

        result = await shopify_storefront.execute_action(
            "storefront_get_article", {"article_id": "gid://shopify/Article/404"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Article not found"


class TestGetMenu:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        menu = {"id": "gid://shopify/Menu/1", "handle": "main-menu", "items": [{"title": "Home"}]}
        mock_context.fetch.return_value = gql({"menu": menu})

        result = await shopify_storefront.execute_action("storefront_get_menu", {"handle": "main-menu"}, mock_context)

        assert result.result.data == {"success": True, "menu": menu}
        assert sent_variables(mock_context) == {"handle": "main-menu"}

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.return_value = gql({"menu": None})

        result = await shopify_storefront.execute_action("storefront_get_menu", {"handle": "nope"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Menu not found"

    @pytest.mark.asyncio
    async def test_empty_handle(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_menu", {"handle": ""}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


# ---- Discovery ----


class TestGetProductRecommendations:
    @pytest.mark.asyncio
    async def test_by_handle_defaults_to_related(self, mock_context):
        mock_context.fetch.return_value = gql({"productRecommendations": [SAMPLE_PRODUCT]})

        result = await shopify_storefront.execute_action(
            "storefront_get_product_recommendations", {"product_handle": "t-shirt"}, mock_context
        )

        assert result.result.data == {"success": True, "products": [SAMPLE_PRODUCT], "count": 1}
        assert sent_variables(mock_context) == {"handle": "t-shirt", "intent": "RELATED"}
        query = sent_query(mock_context)
        assert "productHandle: $handle" in query
        assert "$id" not in query

    @pytest.mark.asyncio
    async def test_by_id_with_intent(self, mock_context):
        mock_context.fetch.return_value = gql({"productRecommendations": []})

        await shopify_storefront.execute_action(
            "storefront_get_product_recommendations",
            {"product_id": SAMPLE_PRODUCT["id"], "intent": "COMPLEMENTARY"},
            mock_context,
        )

        assert sent_variables(mock_context) == {"id": SAMPLE_PRODUCT["id"], "intent": "COMPLEMENTARY"}
        query = sent_query(mock_context)
        assert "productId: $id" in query
        assert "$handle" not in query

    @pytest.mark.asyncio
    async def test_unknown_product(self, mock_context):
        mock_context.fetch.return_value = gql({"productRecommendations": None})

        result = await shopify_storefront.execute_action(
            "storefront_get_product_recommendations", {"product_handle": "nope"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Product not found"

    @pytest.mark.asyncio
    async def test_requires_handle_or_id(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_get_product_recommendations", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


class TestPredictiveSearch:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = gql(
            {
                "predictiveSearch": {
                    "queries": [{"text": "snowboard", "styledText": "<mark>snow</mark>board"}],
                    "products": [SAMPLE_PRODUCT],
                    "collections": [],
                    "pages": None,
                    "articles": [],
                }
            }
        )

        result = await shopify_storefront.execute_action(
            "storefront_predictive_search", {"query": "snow", "limit": 5, "types": ["PRODUCT", "QUERY"]}, mock_context
        )

        assert result.result.data == {
            "success": True,
            "queries": [{"text": "snowboard", "styledText": "<mark>snow</mark>board"}],
            "products": [SAMPLE_PRODUCT],
            "collections": [],
            "pages": [],
            "articles": [],
        }
        assert sent_variables(mock_context) == {"query": "snow", "limit": 5, "types": ["PRODUCT", "QUERY"]}

    @pytest.mark.asyncio
    async def test_defaults(self, mock_context):
        mock_context.fetch.return_value = gql({"predictiveSearch": None})

        result = await shopify_storefront.execute_action(
            "storefront_predictive_search", {"query": "snow"}, mock_context
        )

        assert sent_variables(mock_context) == {"query": "snow", "limit": 10}
        assert result.result.data["products"] == []

    @pytest.mark.asyncio
    async def test_empty_query(self, mock_context):
        result = await shopify_storefront.execute_action("storefront_predictive_search", {"query": ""}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()
