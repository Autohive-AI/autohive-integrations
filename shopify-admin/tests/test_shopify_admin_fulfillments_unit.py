from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from shopify_admin import CreateFulfillmentHandler, build_fulfillment_order_payload, shopify_admin

pytestmark = pytest.mark.unit


@pytest.fixture
def fulfillment_context():
    context = MagicMock()
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "shop_url": "example-store.myshopify.com",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
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

    assert payload == [{"fulfillment_order_id": 900}]


def test_build_fulfillment_order_payload_maps_order_line_item_ids():
    payload = build_fulfillment_order_payload(
        fulfillment_orders_response(),
        "300",
        [{"id": "101", "quantity": 1}],
    )

    assert payload == [
        {
            "fulfillment_order_id": 900,
            "fulfillment_order_line_items": [{"id": 901, "quantity": 1}],
        }
    ]


def test_build_fulfillment_order_payload_rejects_unmatched_items():
    with pytest.raises(ValueError, match="Line items not fulfillable"):
        build_fulfillment_order_payload(
            fulfillment_orders_response(),
            "300",
            [{"id": "999", "quantity": 1}],
        )


async def test_create_fulfillment_uses_2026_07_fulfillment_order_endpoint(fulfillment_context):
    fulfillment_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": "test-access-token"}),  # nosec B105
        FetchResponse(status=200, headers={}, data={"fulfillment_orders": fulfillment_orders_response()}),
        FetchResponse(status=201, headers={}, data={"fulfillment": {"id": 1000, "status": "success"}}),
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
        "fulfillment": {"id": 1000, "status": "success"},
    }

    fulfillment_orders_call = fulfillment_context.fetch.await_args_list[1]
    assert fulfillment_orders_call.args[0] == (
        "https://example-store.myshopify.com/admin/api/2026-07/orders/500/fulfillment_orders.json"
    )
    assert fulfillment_orders_call.kwargs["method"] == "GET"

    create_call = fulfillment_context.fetch.await_args_list[2]
    assert create_call.args[0] == "https://example-store.myshopify.com/admin/api/2026-07/fulfillments.json"
    assert create_call.kwargs["json"] == {
        "fulfillment": {
            "line_items_by_fulfillment_order": [
                {
                    "fulfillment_order_id": 900,
                    "fulfillment_order_line_items": [{"id": 901, "quantity": 1}],
                }
            ],
            "notify_customer": True,
            "tracking_info": {"number": "TRACK-123", "company": "UPS"},
        }
    }


async def test_create_fulfillment_error_returns_action_error(fulfillment_context):
    fulfillment_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": "test-access-token"}),  # nosec B105
        Exception("Shopify rejected the fulfillment"),
    ]

    result = await shopify_admin.execute_action(
        "create_fulfillment",
        {"order_id": "500", "location_id": "300"},
        fulfillment_context,
    )

    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Shopify rejected the fulfillment"
