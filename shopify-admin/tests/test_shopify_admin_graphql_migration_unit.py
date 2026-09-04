from unittest.mock import AsyncMock, MagicMock

import pytest

import shopify_admin as module

pytestmark = pytest.mark.unit


@pytest.fixture
def context():
    execution_context = MagicMock(name="ExecutionContext")
    execution_context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "shop_url": "example-store.myshopify.com",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",  # nosec B105
        },
    }
    return execution_context


def graphql_mock(monkeypatch, *, return_value=None, side_effect=None):
    mock = AsyncMock(return_value=return_value, side_effect=side_effect)
    monkeypatch.setattr(module, "execute_graphql", mock)
    return mock


CUSTOMER_NODE = {
    "id": "gid://shopify/Customer/1",
    "defaultEmailAddress": {"emailAddress": "buyer@example.com"},
    "defaultPhoneNumber": {"phoneNumber": "+64210000000"},
    "firstName": "Buyer",
    "tags": ["vip"],
    "addressesV2": {
        "nodes": [
            {
                "id": "gid://shopify/MailingAddress/11",
                "city": "Auckland",
                "countryCodeV2": "NZ",
            }
        ],
        "pageInfo": {"hasNextPage": True, "endCursor": "address-cursor"},
    },
}
ORDER_NODE = {
    "id": "gid://shopify/Order/2",
    "name": "#1002",
    "displayFinancialStatus": "PAID",
    "displayFulfillmentStatus": "UNFULFILLED",
    "tags": [],
    "lineItems": {
        "nodes": [],
        "pageInfo": {"hasNextPage": True, "endCursor": "order-line-cursor"},
    },
}
DRAFT_NODE = {
    "id": "gid://shopify/DraftOrder/3",
    "name": "#D3",
    "status": "OPEN",
    "note2": "Call before delivery",
    "tags": [],
    "lineItems": {
        "nodes": [],
        "pageInfo": {"hasNextPage": True, "endCursor": "draft-line-cursor"},
    },
}


async def test_list_customers_uses_graphql_filters(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        return_value={
            "customers": {
                "nodes": [CUSTOMER_NODE],
                "pageInfo": {"hasNextPage": True, "endCursor": "customer-cursor"},
            }
        },
    )

    result = await module.ListCustomersHandler().execute(
        {"limit": 10, "after": "previous-cursor", "since_id": "20", "created_at_min": "2026-01-01"},
        context,
    )

    assert result.data["customers"][0]["id"] == "1"
    assert result.data["customers"][0]["addresses"][0]["city"] == "Auckland"
    assert result.data["customers"][0]["addresses_has_next_page"] is True
    assert result.data["customers"][0]["addresses_end_cursor"] == "address-cursor"
    assert result.data["hasNextPage"] is True
    assert result.data["endCursor"] == "customer-cursor"
    variables = graphql.await_args.args[2]
    assert variables["first"] == 10
    assert variables["after"] == "previous-cursor"
    assert 'id:>"20"' in variables["query"]
    assert 'created_at:>="2026-01-01"' in variables["query"]


async def test_get_and_search_customers_use_graphql(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {"customer": CUSTOMER_NODE},
            {"customers": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}},
        ],
    )

    result = await module.GetCustomerHandler().execute({"customer_id": "1"}, context)
    search = await module.SearchCustomersHandler().execute(
        {"query": "email:buyer@example.com", "after": "search-cursor"}, context
    )

    assert result.data["customer"]["id"] == "1"
    assert search.data["count"] == 0
    assert search.data["hasNextPage"] is False
    assert "endCursor" not in search.data
    assert graphql.await_args_list[0].args[2] == {"id": "gid://shopify/Customer/1"}
    assert graphql.await_args_list[1].args[2] == {
        "first": 50,
        "after": "search-cursor",
        "query": "email:buyer@example.com",
    }


async def test_create_customer_maps_input_and_invite(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {"customerCreate": {"customer": CUSTOMER_NODE, "userErrors": []}},
            {"customerSendAccountInviteEmail": {"customer": {"id": CUSTOMER_NODE["id"]}, "userErrors": []}},
        ],
    )

    result = await module.CreateCustomerHandler().execute(
        {
            "email": "buyer@example.com",
            "first_name": "Buyer",
            "tags": "vip, wholesale",
            "address": {"first_name": "Buyer", "country_code": "NZ"},
            "send_email_welcome": True,
        },
        context,
    )

    assert result.data["customer"]["email"] == "buyer@example.com"
    customer_input = graphql.await_args_list[0].args[2]["input"]
    assert customer_input["firstName"] == "Buyer"
    assert customer_input["tags"] == ["vip", "wholesale"]
    assert customer_input["addresses"] == [{"firstName": "Buyer", "countryCode": "NZ"}]
    assert graphql.await_args_list[1].args[2] == {"customerId": CUSTOMER_NODE["id"]}


async def test_create_customer_preserves_customer_when_invite_fails(monkeypatch, context):
    graphql_mock(
        monkeypatch,
        side_effect=[
            {"customerCreate": {"customer": CUSTOMER_NODE, "userErrors": []}},
            Exception("Invitation service unavailable"),
        ],
    )

    result = await module.CreateCustomerHandler().execute(
        {"email": "buyer@example.com", "send_email_welcome": True},
        context,
    )

    assert result.data["success"] is False
    assert result.data["partial_success"] is True
    assert result.data["customer"]["id"] == "1"
    assert "Customer was created" in result.data["message"]
    assert "Invitation service unavailable" in result.data["message"]


async def test_update_customer_maps_id_and_fields(monkeypatch, context):
    graphql = graphql_mock(monkeypatch, return_value={"customerUpdate": {"customer": CUSTOMER_NODE, "userErrors": []}})

    result = await module.UpdateCustomerHandler().execute(
        {"customer_id": "1", "last_name": "Person", "tax_exempt": True}, context
    )

    assert result.data["customer"]["id"] == "1"
    assert graphql.await_args.args[2]["input"] == {
        "id": "gid://shopify/Customer/1",
        "lastName": "Person",
        "taxExempt": True,
    }


async def test_create_customer_rejects_unrepresentable_unverified_email(monkeypatch, context):
    graphql = graphql_mock(monkeypatch)

    result = await module.CreateCustomerHandler().execute({"verified_email": False}, context)

    assert "verified_email=false" in result.message
    graphql.assert_not_awaited()


async def test_list_and_get_orders_use_graphql(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {"orders": {"nodes": [ORDER_NODE], "pageInfo": {"hasNextPage": True, "endCursor": "order-cursor"}}},
            {"order": ORDER_NODE},
        ],
    )

    listed = await module.ListOrdersHandler().execute(
        {"status": "open", "financial_status": "paid", "limit": 5, "after": "previous-order-cursor"},
        context,
    )
    fetched = await module.GetOrderHandler().execute({"order_id": "2"}, context)

    assert listed.data["orders"][0]["financial_status"] == "paid"
    assert listed.data["orders"][0]["line_items_has_next_page"] is True
    assert listed.data["orders"][0]["line_items_end_cursor"] == "order-line-cursor"
    assert listed.data["hasNextPage"] is True
    assert listed.data["endCursor"] == "order-cursor"
    assert fetched.data["order"]["id"] == "2"
    assert graphql.await_args_list[0].args[2] == {
        "first": 5,
        "after": "previous-order-cursor",
        "query": "status:open AND financial_status:paid",
    }
    assert graphql.await_args_list[1].args[2] == {"id": "gid://shopify/Order/2"}


async def test_create_order_maps_line_items_customer_and_options(monkeypatch, context):
    graphql = graphql_mock(monkeypatch, return_value={"orderCreate": {"order": ORDER_NODE, "userErrors": []}})

    result = await module.CreateOrderHandler().execute(
        {
            "line_items": [{"variant_id": "9", "quantity": 2}],
            "customer_id": "1",
            "financial_status": "paid",
            "send_receipt": True,
            "tags": "phone, priority",
        },
        context,
    )

    assert result.data["order"]["id"] == "2"
    variables = graphql.await_args.args[2]
    assert variables["order"]["lineItems"] == [{"quantity": 2, "variantId": "gid://shopify/ProductVariant/9"}]
    assert variables["order"]["customer"] == {"toAssociate": {"id": "gid://shopify/Customer/1"}}
    assert variables["order"]["financialStatus"] == "PAID"
    assert variables["options"]["sendReceipt"] is True


async def test_custom_order_price_resolves_shop_currency(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {"shop": {"currencyCode": "NZD"}},
            {"orderCreate": {"order": ORDER_NODE, "userErrors": []}},
        ],
    )

    await module.CreateOrderHandler().execute(
        {"line_items": [{"title": "Service", "price": "25.00", "quantity": 1}]}, context
    )

    money = graphql.await_args_list[1].args[2]["order"]["lineItems"][0]["priceSet"]
    assert money == {"shopMoney": {"amount": "25.00", "currencyCode": "NZD"}}


async def test_cancel_order_returns_pending_job_without_fetching_order(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        return_value={
            "orderCancel": {
                "job": {"id": "gid://shopify/Job/1", "done": False},
                "orderCancelUserErrors": [],
            }
        },
    )

    integration_result = await module.shopify_admin.execute_action(
        "cancel_order",
        {"order_id": "2", "reason": "customer", "email": False, "restock": True},
        context,
    )
    result = integration_result.result

    assert result.data == {
        "success": True,
        "cancellation_status": "pending",
        "job_id": "gid://shopify/Job/1",
        "job_done": False,
    }
    graphql.assert_awaited_once()
    assert graphql.await_args_list[0].args[2] == {
        "orderId": "gid://shopify/Order/2",
        "notifyCustomer": False,
        "refundMethod": {"originalPaymentMethodsRefund": True},
        "restock": True,
        "reason": "CUSTOMER",
    }


async def test_cancel_order_fetches_order_when_job_is_already_done(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {
                "orderCancel": {
                    "job": {"id": "gid://shopify/Job/1", "done": True},
                    "orderCancelUserErrors": [],
                }
            },
            {"order": ORDER_NODE},
        ],
    )

    result = await module.CancelOrderHandler().execute({"order_id": "2"}, context)

    assert result.data["cancellation_status"] == "completed"
    assert result.data["job_done"] is True
    assert result.data["order"]["id"] == "2"
    assert graphql.await_args_list[1].args[1] == module.ORDER_QUERY
    assert graphql.await_args_list[1].args[2] == {"id": "gid://shopify/Order/2"}


async def test_cancel_order_stays_successful_when_completed_order_refetch_fails(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {
                "orderCancel": {
                    "job": {"id": "gid://shopify/Job/1", "done": True},
                    "orderCancelUserErrors": [],
                }
            },
            Exception("Order lookup unavailable"),
        ],
    )

    result = await module.CancelOrderHandler().execute({"order_id": "2"}, context)

    assert result.data["success"] is True
    assert result.data["cancellation_status"] == "completed"
    assert result.data["job_done"] is True
    assert "order" not in result.data
    assert "cancellation completed" in result.data["message"].lower()
    assert "Order lookup unavailable" in result.data["message"]
    assert graphql.await_count == 2


async def test_get_inventory_levels_by_item_uses_nodes(monkeypatch, context):
    level = {
        "id": "gid://shopify/InventoryLevel/7?inventory_item_id=8",
        "item": {"id": "gid://shopify/InventoryItem/8"},
        "location": {"id": "gid://shopify/Location/6"},
        "quantities": [{"name": "available", "quantity": 4}],
    }
    graphql = graphql_mock(monkeypatch, return_value={"nodes": [{"inventoryLevels": {"nodes": [level]}}]})

    result = await module.GetInventoryLevelsHandler().execute({"inventory_item_ids": "8", "location_ids": "6"}, context)

    assert result.data["inventory_levels"][0]["available"] == 4
    assert graphql.await_args.args[2]["ids"] == ["gid://shopify/InventoryItem/8"]


async def test_get_inventory_levels_by_location_uses_location_nodes(monkeypatch, context):
    graphql = graphql_mock(monkeypatch, return_value={"nodes": [{"inventoryLevels": {"nodes": []}}]})

    result = await module.GetInventoryLevelsHandler().execute({"location_ids": "6"}, context)

    assert result.data["count"] == 0
    assert graphql.await_args.args[1] == module.LOCATION_INVENTORY_QUERY


async def test_set_inventory_level_is_idempotent(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        return_value={
            "inventorySetQuantities": {
                "inventoryAdjustmentGroup": {"changes": [{"name": "available", "quantityAfterChange": 12}]},
                "userErrors": [],
            }
        },
    )

    result = await module.SetInventoryLevelHandler().execute(
        {"inventory_item_id": "8", "location_id": "6", "available": 12}, context
    )

    assert result.data["inventory_level"]["available"] == 12
    variables = graphql.await_args.args[2]
    assert variables["idempotencyKey"]
    quantity = variables["input"]["quantities"][0]
    assert quantity["inventoryItemId"].endswith("/8")
    assert quantity["changeFromQuantity"] is None
    assert "ignoreCompareQuantity" not in variables["input"]


async def test_set_inventory_level_falls_back_when_shopify_omits_quantity_after_change(monkeypatch, context):
    graphql_mock(
        monkeypatch,
        return_value={
            "inventorySetQuantities": {
                "inventoryAdjustmentGroup": {"changes": [{"name": "available", "quantityAfterChange": None}]},
                "userErrors": [],
            }
        },
    )

    result = await module.SetInventoryLevelHandler().execute(
        {"inventory_item_id": "8", "location_id": "6", "available": 12}, context
    )

    assert result.data["inventory_level"]["available"] == 12


async def test_list_and_get_locations_use_graphql(monkeypatch, context):
    location = {"id": "gid://shopify/Location/6", "name": "Main", "isActive": True}
    graphql = graphql_mock(monkeypatch, side_effect=[{"locations": {"nodes": [location]}}, {"location": location}])

    listed = await module.ListLocationsHandler().execute({}, context)
    fetched = await module.GetLocationHandler().execute({"location_id": "6"}, context)

    assert listed.data["locations"][0]["id"] == "6"
    assert fetched.data["location"]["name"] == "Main"
    assert graphql.await_args_list[1].args[2] == {"id": "gid://shopify/Location/6"}


async def test_get_shop_uses_graphql(monkeypatch, context):
    graphql_mock(
        monkeypatch,
        return_value={
            "shop": {
                "id": "gid://shopify/Shop/4",
                "name": "Example",
                "myshopifyDomain": "example.myshopify.com",
                "currencyCode": "NZD",
                "ianaTimezone": "Pacific/Auckland",
                "shopAddress": {"countryCodeV2": "NZ"},
            }
        },
    )

    result = await module.GetShopHandler().execute({}, context)

    assert result.data["shop"]["id"] == "4"
    assert result.data["shop"]["country_code"] == "NZ"


async def test_list_draft_orders_uses_graphql_filters(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        return_value={
            "draftOrders": {
                "nodes": [DRAFT_NODE],
                "pageInfo": {"hasNextPage": True, "endCursor": "draft-order-cursor"},
            }
        },
    )

    result = await module.ListDraftOrdersHandler().execute(
        {"limit": 4, "after": "previous-draft-cursor", "since_id": "2", "status": "open"}, context
    )

    assert result.data["draft_orders"][0]["id"] == "3"
    assert result.data["draft_orders"][0]["note"] == "Call before delivery"
    assert result.data["draft_orders"][0]["line_items_has_next_page"] is True
    assert result.data["draft_orders"][0]["line_items_end_cursor"] == "draft-line-cursor"
    assert result.data["hasNextPage"] is True
    assert result.data["endCursor"] == "draft-order-cursor"
    assert graphql.await_args.args[2] == {
        "first": 4,
        "after": "previous-draft-cursor",
        "query": 'id:>"2" AND status:open',
    }


async def test_create_draft_order_maps_graphql_input(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        return_value={"draftOrderCreate": {"draftOrder": DRAFT_NODE, "userErrors": []}},
    )

    result = await module.CreateDraftOrderHandler().execute(
        {
            "line_items": [{"variant_id": "9", "quantity": 2}],
            "customer_id": "1",
            "tags": "draft, wholesale",
            "use_customer_default_address": True,
        },
        context,
    )

    assert result.data["draft_order"]["id"] == "3"
    draft_input = graphql.await_args.args[2]["input"]
    assert draft_input["purchasingEntity"] == {"customerId": "gid://shopify/Customer/1"}
    assert draft_input["lineItems"][0]["variantId"].endswith("/9")
    assert draft_input["tags"] == ["draft", "wholesale"]


async def test_complete_and_delete_draft_order_use_mutations(monkeypatch, context):
    graphql = graphql_mock(
        monkeypatch,
        side_effect=[
            {"draftOrderComplete": {"draftOrder": DRAFT_NODE, "userErrors": []}},
            {"draftOrderDelete": {"deletedId": DRAFT_NODE["id"], "userErrors": []}},
        ],
    )

    completed = await module.CompleteDraftOrderHandler().execute(
        {"draft_order_id": "3", "payment_pending": True}, context
    )
    deleted = await module.DeleteDraftOrderHandler().execute({"draft_order_id": "3"}, context)

    assert completed.data["draft_order"]["id"] == "3"
    assert deleted.data["deleted"] is True
    assert graphql.await_args_list[0].args[2]["paymentPending"] is True
    assert graphql.await_args_list[1].args[2] == {"input": {"id": "gid://shopify/DraftOrder/3"}}


async def test_list_fulfillments_uses_order_connection(monkeypatch, context):
    fulfillment = {
        "id": "gid://shopify/Fulfillment/5",
        "status": "SUCCESS",
        "trackingInfo": [{"number": "TRACK"}],
    }
    graphql = graphql_mock(
        monkeypatch,
        return_value={"order": {"fulfillments": [fulfillment]}},
    )

    result = await module.ListFulfillmentsHandler().execute({"order_id": "2"}, context)

    assert result.data["fulfillments"][0]["tracking_number"] == "TRACK"
    assert graphql.await_args.args[2] == {"id": "gid://shopify/Order/2"}


async def test_update_fulfillment_tracking_uses_graphql_input(monkeypatch, context):
    fulfillment = {
        "id": "gid://shopify/Fulfillment/5",
        "status": "SUCCESS",
        "trackingInfo": [{"number": "NEW"}],
    }
    graphql = graphql_mock(
        monkeypatch,
        return_value={
            "fulfillmentTrackingInfoUpdate": {
                "fulfillment": fulfillment,
                "userErrors": [],
            }
        },
    )

    result = await module.UpdateFulfillmentTrackingHandler().execute(
        {
            "fulfillment_id": "5",
            "tracking_number": "NEW",
            "tracking_company": "NZ Post",
            "notify_customer": True,
        },
        context,
    )

    assert result.data["fulfillment"]["tracking_number"] == "NEW"
    assert graphql.await_args.args[2] == {
        "id": "gid://shopify/Fulfillment/5",
        "input": {"number": "NEW", "company": "NZ Post"},
        "notify": True,
    }


def test_queries_match_shopify_2026_07_collection_and_object_shapes():
    assert "addressesV2(first: 10)" in module.CUSTOMER_FIELDS
    assert "addresses(first: 10)" not in module.CUSTOMER_FIELDS
    assert "pageInfo { hasNextPage endCursor }" in module.CUSTOMER_FIELDS
    assert "pageInfo { hasNextPage endCursor }" in module.ORDER_FIELDS
    assert "pageInfo { hasNextPage endCursor }" in module.DRAFT_ORDER_FIELDS
    for query in (module.CUSTOMERS_QUERY, module.ORDERS_QUERY, module.DRAFT_ORDERS_QUERY):
        assert "$after: String" in query
        assert "after: $after" in query
        assert "pageInfo { hasNextPage endCursor }" in query
    assert "note2" in module.DRAFT_ORDER_FIELDS
    assert " note " not in module.DRAFT_ORDER_FIELDS
    assert "supportedActions { action }" in module.FULFILLMENT_ORDERS_QUERY
    assert "fulfillments(first: 250) { nodes" not in module.ORDER_FULFILLMENTS_QUERY


async def test_mutation_user_errors_return_action_error(monkeypatch, context):
    graphql_mock(
        monkeypatch,
        return_value={
            "customerUpdate": {
                "customer": None,
                "userErrors": [{"field": ["input", "email"], "message": "Invalid email"}],
            }
        },
    )

    result = await module.UpdateCustomerHandler().execute({"customer_id": "1", "email": "bad@example.com"}, context)

    assert "Invalid email" in result.message
