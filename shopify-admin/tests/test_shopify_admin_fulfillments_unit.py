from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from shopify_admin import CreateFulfillmentHandler, build_fulfillment_order_payload, shopify_admin

pytestmark = pytest.mark.unit


CLIENT_SECRET = uuid4().hex
ACCESS_TOKEN = uuid4().hex


@pytest.fixture
def fulfillment_context():
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


def fulfillment_orders_response():
    return [
        {
            "id": 900,
            "assigned_location_id": 300,
            "supported_actions": ["create_fulfillment"],
            "line_items": [
                {
                    "id": 901,
                    "line_item_id": 101,
                    "quantity": 2,
                    "fulfillable_quantity": 2,
                }
            ],
        },
        {
            "id": 910,
            "assigned_location_id": 400,
            "supported_actions": ["create_fulfillment"],
            "line_items": [{"id": 911, "line_item_id": 102, "quantity": 1}],
        },
    ]


def test_build_fulfillment_order_payload_fulfills_all_items_at_location():
    payload = build_fulfillment_order_payload(fulfillment_orders_response(), "300", [])

    assert payload == [{"fulfillmentOrderId": "gid://shopify/FulfillmentOrder/900"}]


def test_build_fulfillment_order_payload_maps_order_line_item_ids():
    payload = build_fulfillment_order_payload(
        fulfillment_orders_response(),
        "300",
        [{"id": "101", "quantity": 1}],
    )

    assert payload == [
        {
            "fulfillmentOrderId": "gid://shopify/FulfillmentOrder/900",
            "fulfillmentOrderLineItems": [{"id": "gid://shopify/FulfillmentOrderLineItem/901", "quantity": 1}],
        }
    ]


def test_build_fulfillment_order_payload_rejects_unmatched_items():
    with pytest.raises(ValueError, match="Line items not fulfillable"):
        build_fulfillment_order_payload(
            fulfillment_orders_response(),
            "300",
            [{"id": "999", "quantity": 1}],
        )


async def test_create_fulfillment_uses_graphql_fulfillment_order_workflow(fulfillment_context):
    fulfillment_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": ACCESS_TOKEN}),
        FetchResponse(
            status=200,
            headers={},
            data={
                "data": {
                    "order": {
                        "fulfillmentOrders": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/FulfillmentOrder/900",
                                    "assignedLocation": {"location": {"id": "gid://shopify/Location/300"}},
                                    "supportedActions": [{"action": "CREATE_FULFILLMENT"}],
                                    "lineItems": {
                                        "nodes": [
                                            {
                                                "id": "gid://shopify/FulfillmentOrderLineItem/901",
                                                "lineItem": {"id": "gid://shopify/LineItem/101"},
                                                "totalQuantity": 2,
                                                "remainingQuantity": 2,
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                }
            },
        ),
        FetchResponse(status=200, headers={}, data={"access_token": ACCESS_TOKEN}),
        FetchResponse(
            status=200,
            headers={},
            data={
                "data": {
                    "fulfillmentCreate": {
                        "fulfillment": {
                            "id": "gid://shopify/Fulfillment/1000",
                            "status": "SUCCESS",
                            "trackingInfo": [],
                        },
                        "userErrors": [],
                    }
                }
            },
        ),
    ]

    result = await CreateFulfillmentHandler().execute(
        {
            "order_id": "500",
            "location_id": "300",
            "tracking_number": "TRACK-123",
            "tracking_company": "UPS",
            "notify_customer": True,
            "line_items": [{"id": "101", "quantity": 1}],
        },
        fulfillment_context,
    )

    assert result.data == {
        "success": True,
        "fulfillment": {
            "id": "1000",
            "status": "success",
            "created_at": None,
            "updated_at": None,
            "tracking_company": None,
            "tracking_number": None,
            "tracking_url": None,
        },
    }

    fulfillment_orders_call = fulfillment_context.fetch.await_args_list[1]
    assert fulfillment_orders_call.args[0] == ("https://example-store.myshopify.com/admin/api/2026-07/graphql.json")
    assert fulfillment_orders_call.kwargs["method"] == "POST"
    assert fulfillment_orders_call.kwargs["json"]["variables"] == {"id": "gid://shopify/Order/500"}

    create_call = fulfillment_context.fetch.await_args_list[3]
    assert create_call.args[0] == "https://example-store.myshopify.com/admin/api/2026-07/graphql.json"
    assert create_call.kwargs["json"]["variables"] == {
        "fulfillment": {
            "lineItemsByFulfillmentOrder": [
                {
                    "fulfillmentOrderId": "gid://shopify/FulfillmentOrder/900",
                    "fulfillmentOrderLineItems": [{"id": "gid://shopify/FulfillmentOrderLineItem/901", "quantity": 1}],
                }
            ],
            "notifyCustomer": True,
            "trackingInfo": {"number": "TRACK-123", "company": "UPS"},
        }
    }


async def test_create_fulfillment_error_returns_action_error(fulfillment_context):
    fulfillment_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": ACCESS_TOKEN}),
        Exception("Shopify rejected the fulfillment"),
    ]

    result = await shopify_admin.execute_action(
        "create_fulfillment",
        {"order_id": "500", "location_id": "300"},
        fulfillment_context,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Shopify rejected the fulfillment"
