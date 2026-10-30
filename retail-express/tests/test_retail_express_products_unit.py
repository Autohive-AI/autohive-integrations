import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from retail_express import retail_express


pytestmark = pytest.mark.unit


def queue_api_response(mock_context, data):
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
        FetchResponse(status=200, headers={}, data=data),
    ]


class TestListProducts:
    async def test_returns_products_and_passes_filters(self, mock_context):
        product = {"id": 42, "sku": "SKU-42", "name": "Test product"}
        queue_api_response(
            mock_context,
            {"data": [product], "page_number": 2, "page_size": 25, "total_records": 26},
        )

        result = await retail_express.execute_action(
            "list_products",
            {
                "page_number": 2,
                "page_size": 25,
                "sku": "SKU-42",
                "modified_since": "2026-01-01T00:00:00Z",
            },
            mock_context,
        )

        assert result.result.data == {
            "products": [product],
            "page_number": 2,
            "page_size": 25,
            "total_records": 26,
            "result": True,
        }
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/products"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["params"] == {
            "page_number": 2,
            "page_size": 25,
            "sku": "SKU-42",
            "modified_since": "2026-01-01T00:00:00Z",
        }

    async def test_uses_defaults_when_pagination_metadata_is_missing(self, mock_context):
        queue_api_response(mock_context, {"data": []})

        result = await retail_express.execute_action("list_products", {}, mock_context)

        assert result.result.data == {
            "products": [],
            "page_number": 1,
            "page_size": 20,
            "total_records": 0,
            "result": True,
        }

    async def test_returns_action_error_when_fetch_fails(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("products unavailable")

        result = await retail_express.execute_action("list_products", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "products unavailable"


class TestGetProduct:
    async def test_gets_product_by_id(self, mock_context):
        product = {"id": 42, "sku": "SKU-42"}
        queue_api_response(mock_context, {"data": product})

        result = await retail_express.execute_action("get_product", {"product_id": "42"}, mock_context)

        assert result.result.data == {"product": product, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/products/42"
        assert request.kwargs["method"] == "GET"

    async def test_accepts_unwrapped_product_response(self, mock_context):
        product = {"id": 42, "sku": "SKU-42"}
        queue_api_response(mock_context, product)

        result = await retail_express.execute_action("get_product", {"product_id": "42"}, mock_context)

        assert result.result.data["product"] == product

    async def test_returns_action_error_when_fetch_fails(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("product unavailable")

        result = await retail_express.execute_action("get_product", {"product_id": "42"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "product unavailable"

    async def test_requires_product_id(self, mock_context):
        result = await retail_express.execute_action("get_product", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()
