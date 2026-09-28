from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse, ResultType

from shopify_admin import (
    PRODUCTS_QUERY,
    PRODUCT_CREATE_MUTATION,
    PRODUCT_QUERY,
    PRODUCT_UPDATE_MUTATION,
    PRODUCT_VARIANTS_BULK_CREATE_MUTATION,
    PRODUCT_VARIANTS_BULK_UPDATE_MUTATION,
    CreateProductHandler,
    build_product_query_filter,
    build_product_variant_input,
    shopify_admin,
    transform_product_response,
)

pytestmark = pytest.mark.unit


CLIENT_SECRET = uuid4().hex
ACCESS_TOKEN = uuid4().hex


@pytest.fixture
def product_context():
    context = MagicMock()
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "shop_url": "example-store.myshopify.com",
            "client_id": "test-client-id",
            "client_secret": CLIENT_SECRET,
        },
    }
    context.fetch = AsyncMock()
    return context


def fetch_response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def test_product_queries_use_inventory_item_measurement_for_weight():
    for query in (PRODUCTS_QUERY, PRODUCT_QUERY):
        assert "weightUnit" not in query
        assert "inventoryItem" in query
        assert "measurement" in query
        assert "weight {" in query
        assert "value" in query
        assert "unit" in query


def test_product_mutations_use_2026_07_input_contracts():
    assert "$product: ProductCreateInput!" in PRODUCT_CREATE_MUTATION
    assert "productCreate(product: $product)" in PRODUCT_CREATE_MUTATION
    assert "ProductInput" not in PRODUCT_CREATE_MUTATION

    assert "$product: ProductUpdateInput!" in PRODUCT_UPDATE_MUTATION
    assert "productUpdate(product: $product)" in PRODUCT_UPDATE_MUTATION
    assert "ProductInput" not in PRODUCT_UPDATE_MUTATION

    assert "productVariantsBulkCreate" in PRODUCT_VARIANTS_BULK_CREATE_MUTATION
    assert "productVariantsBulkUpdate" in PRODUCT_VARIANTS_BULK_UPDATE_MUTATION


def test_build_product_query_filter_quotes_iso_date_bounds():
    query = build_product_query_filter(
        {
            "created_at_min": "2026-01-02T03:04:05Z",
            "created_at_max": "2026-02-03T04:05:06+12:00",
        }
    )

    assert query == 'created_at:>"2026-01-02T03:04:05Z" AND created_at:<"2026-02-03T04:05:06+12:00"'


def test_build_product_query_filter_escapes_special_characters_in_date_bounds():
    query = build_product_query_filter({"created_at_min": '2026-01-02T03:04:05Z" OR status:active\\'})

    assert query == 'created_at:>"2026-01-02T03:04:05Z\\" OR status:active\\\\"'


def test_build_product_variant_input_uses_inventory_item_and_option_values():
    variant = build_product_variant_input(
        {
            "price": "19.99",
            "compare_at_price": "24.99",
            "sku": "SHIRT-LARGE",
            "barcode": "123456789",
            "weight": 0.5,
            "weight_unit": "kg",
            "option_values": [{"option_name": "Size", "name": "Large"}],
        },
        [{"name": "Size", "values": ["Small", "Large"]}],
    )

    assert variant == {
        "price": "19.99",
        "compareAtPrice": "24.99",
        "barcode": "123456789",
        "inventoryItem": {
            "sku": "SHIRT-LARGE",
            "measurement": {"weight": {"value": 0.5, "unit": "KILOGRAMS"}},
        },
        "optionValues": [{"optionName": "Size", "name": "Large"}],
    }


def test_transform_product_response_reads_inventory_item_weight():
    product = transform_product_response(
        {
            "id": "gid://shopify/Product/100",
            "variants": {
                "nodes": [
                    {
                        "id": "gid://shopify/ProductVariant/200",
                        "title": "Default Title",
                        "inventoryItem": {
                            "measurement": {
                                "weight": {"value": 1.25, "unit": "KILOGRAMS"},
                            }
                        },
                    }
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "variant-cursor"},
            },
            "images": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": "image-cursor"},
            },
        }
    )

    assert product["variants"][0]["weight"] == 1.25
    assert product["variants"][0]["weight_unit"] == "KILOGRAMS"
    assert product["variants_has_next_page"] is True
    assert product["variants_end_cursor"] == "variant-cursor"
    assert product["images_has_next_page"] is False
    assert product["images_end_cursor"] == "image-cursor"


def test_product_queries_expose_nested_connection_page_info():
    for query in (PRODUCTS_QUERY, PRODUCT_QUERY, PRODUCT_CREATE_MUTATION, PRODUCT_UPDATE_MUTATION):
        assert query.count("pageInfo { hasNextPage endCursor }") >= 2


async def test_list_products_returns_weight_from_current_schema(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "products": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/Product/100",
                                    "title": "Test product",
                                    "variants": {
                                        "nodes": [
                                            {
                                                "id": "gid://shopify/ProductVariant/200",
                                                "inventoryItem": {
                                                    "measurement": {
                                                        "weight": {"value": 500.0, "unit": "GRAMS"},
                                                    }
                                                },
                                            }
                                        ]
                                    },
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        ),
    ]

    result = await shopify_admin.execute_action("list_products", {"limit": 1}, product_context)

    data = result.result.data
    assert data["success"] is True
    assert data["products"][0]["variants"][0]["weight"] == 500.0
    graphql_call = product_context.fetch.await_args_list[1]
    assert "inventoryItem" in graphql_call.kwargs["json"]["query"]


@pytest.mark.parametrize(
    "requested_limit, expected_limit",
    [
        (0, 50),
        (-1, 1),
        (251, 250),
    ],
)
async def test_list_products_clamps_limit_boundaries(product_context, requested_limit, expected_limit):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "products": {
                        "edges": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        ),
    ]

    result = await shopify_admin.execute_action("list_products", {"limit": requested_limit}, product_context)

    assert result.type == ResultType.ACTION
    graphql_call = product_context.fetch.await_args_list[1]
    assert graphql_call.kwargs["json"]["variables"]["first"] == expected_limit


async def test_get_product_error_returns_action_error(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        Exception("GraphQL Error: invalid product query"),
    ]

    result = await shopify_admin.execute_action("get_product", {"product_id": "100"}, product_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "GraphQL Error" in result.result.message


async def test_get_product_null_returns_not_found_error(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response({"data": {"product": None}}),
    ]

    result = await shopify_admin.execute_action("get_product", {"product_id": "100"}, product_context)

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Product 100 was not found"


async def test_update_product_sends_explicit_empty_fields(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productUpdate": {
                        "product": {"id": "gid://shopify/Product/100", "title": "Test product"},
                        "userErrors": [],
                    }
                }
            }
        ),
    ]

    result = await shopify_admin.execute_action(
        "update_product",
        {
            "product_id": "100",
            "body_html": "",
            "vendor": "",
            "product_type": "",
            "tags": "",
        },
        product_context,
    )

    assert result.type == ResultType.ACTION
    graphql_call = product_context.fetch.await_args_list[1]
    assert graphql_call.kwargs["json"]["variables"] == {
        "product": {
            "id": "gid://shopify/Product/100",
            "descriptionHtml": "",
            "vendor": "",
            "productType": "",
            "tags": [],
        }
    }


async def test_create_product_updates_the_standalone_variant(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productCreate": {
                        "product": {
                            "id": "gid://shopify/Product/100",
                            "title": "Test product",
                            "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/200"}]},
                        },
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productVariantsBulkUpdate": {
                        "productVariants": [{"id": "gid://shopify/ProductVariant/200"}],
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "product": {
                        "id": "gid://shopify/Product/100",
                        "title": "Test product",
                        "variants": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/ProductVariant/200",
                                    "price": "19.99",
                                    "sku": "TEST-SKU",
                                }
                            ]
                        },
                    }
                }
            }
        ),
    ]

    result = await CreateProductHandler().execute(
        {
            "title": "Test product",
            "variants": [{"price": "19.99", "sku": "TEST-SKU"}],
        },
        product_context,
    )

    assert result.data["success"] is True
    assert result.data["product"]["variants"][0]["sku"] == "TEST-SKU"

    create_call = product_context.fetch.await_args_list[1]
    assert create_call.kwargs["json"]["variables"] == {"product": {"title": "Test product"}}

    variant_call = product_context.fetch.await_args_list[3]
    assert "productVariantsBulkUpdate" in variant_call.kwargs["json"]["query"]
    assert variant_call.kwargs["json"]["variables"] == {
        "productId": "gid://shopify/Product/100",
        "variants": [
            {
                "id": "gid://shopify/ProductVariant/200",
                "price": "19.99",
                "inventoryItem": {"sku": "TEST-SKU"},
            }
        ],
    }


async def test_create_product_bulk_creates_optioned_variants(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productCreate": {
                        "product": {
                            "id": "gid://shopify/Product/100",
                            "title": "Test shirt",
                            "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/200"}]},
                        },
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productVariantsBulkCreate": {
                        "productVariants": [
                            {"id": "gid://shopify/ProductVariant/201"},
                            {"id": "gid://shopify/ProductVariant/202"},
                        ],
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "product": {
                        "id": "gid://shopify/Product/100",
                        "title": "Test shirt",
                        "variants": {
                            "nodes": [
                                {"id": "gid://shopify/ProductVariant/201", "title": "Small", "price": "19.99"},
                                {"id": "gid://shopify/ProductVariant/202", "title": "Large", "price": "21.99"},
                            ]
                        },
                    }
                }
            }
        ),
    ]

    result = await CreateProductHandler().execute(
        {
            "title": "Test shirt",
            "options": [{"name": "Size", "values": ["Small", "Large"]}],
            "variants": [
                {"price": "19.99", "option_values": {"Size": "Small"}},
                {"price": "21.99", "option_values": {"Size": "Large"}},
            ],
        },
        product_context,
    )

    assert result.data["success"] is True
    assert len(result.data["product"]["variants"]) == 2

    create_call = product_context.fetch.await_args_list[1]
    assert create_call.kwargs["json"]["variables"] == {
        "product": {
            "title": "Test shirt",
            "productOptions": [{"name": "Size", "values": [{"name": "Small"}, {"name": "Large"}]}],
        }
    }

    variant_call = product_context.fetch.await_args_list[3]
    assert "productVariantsBulkCreate" in variant_call.kwargs["json"]["query"]
    assert variant_call.kwargs["json"]["variables"] == {
        "productId": "gid://shopify/Product/100",
        "variants": [
            {"price": "19.99", "optionValues": [{"optionName": "Size", "name": "Small"}]},
            {"price": "21.99", "optionValues": [{"optionName": "Size", "name": "Large"}]},
        ],
        "strategy": "REMOVE_STANDALONE_VARIANT",
    }


async def test_create_product_reports_partial_success_when_variant_setup_fails(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productCreate": {
                        "product": {
                            "id": "gid://shopify/Product/100",
                            "title": "Partially created product",
                            "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/200"}]},
                        },
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productVariantsBulkUpdate": {
                        "productVariants": [],
                        "userErrors": [{"field": ["variants", "0", "price"], "message": "Invalid price"}],
                    }
                }
            }
        ),
    ]

    integration_result = await shopify_admin.execute_action(
        "create_product",
        {
            "title": "Partially created product",
            "variants": [{"price": "invalid"}],
        },
        product_context,
    )
    result = integration_result.result

    assert integration_result.type == ResultType.ACTION
    assert result.data["success"] is False
    assert result.data["partial_success"] is True
    assert result.data["product"]["id"] == "100"
    assert "Product 100 was created" in result.data["message"]
    assert "Invalid price" in result.data["message"]


async def test_create_product_reports_partial_success_when_refetch_fails(product_context):
    product_context.fetch.side_effect = [
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productCreate": {
                        "product": {
                            "id": "gid://shopify/Product/100",
                            "title": "Created product",
                            "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/200"}]},
                        },
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        fetch_response(
            {
                "data": {
                    "productVariantsBulkUpdate": {
                        "productVariants": [{"id": "gid://shopify/ProductVariant/200"}],
                        "userErrors": [],
                    }
                }
            }
        ),
        fetch_response({"access_token": ACCESS_TOKEN}),
        Exception("Product refetch unavailable"),
    ]

    result = await CreateProductHandler().execute(
        {
            "title": "Created product",
            "variants": [{"price": "19.99"}],
        },
        product_context,
    )

    assert result.data["success"] is False
    assert result.data["partial_success"] is True
    assert result.data["product"]["id"] == "100"
    assert "Product refetch unavailable" in result.data["message"]


async def test_create_product_rejects_ambiguous_variants_before_creating_product(product_context):
    result = await CreateProductHandler().execute(
        {
            "title": "Ambiguous product",
            "variants": [{"price": "19.99"}, {"price": "21.99"}],
        },
        product_context,
    )

    assert isinstance(result, ActionError)
    assert "must provide option_values" in result.message
    product_context.fetch.assert_not_awaited()
