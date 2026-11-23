import asyncio
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError
from autohive_integrations_sdk import ExecutionContext, FetchResponse, HTTPError, RateLimitError, ResultType

from businesscentral import businesscentral, base_url

pytestmark = pytest.mark.unit
TENANT = "11111111-1111-1111-1111-111111111111"
COMPANY = "22222222-2222-2222-2222-222222222222"
ITEM = "33333333-3333-3333-3333-333333333333"
DOCUMENT = "44444444-4444-4444-4444-444444444444"
INPUTS = {"tenant_id": TENANT, "environment": "Sandbox", "company_id": COMPANY}
ITEM_DATA = {
    "id": ITEM,
    "number": "BOX-1",
    "type": "Inventory",
    "inventory": 100,
    "unitCost": 0.1,
    "baseUnitOfMeasureCode": "PCS",
}


def response(data, status=200, headers=None):
    return FetchResponse(status=status, headers=headers or {}, data=data)


def assert_success(result):
    assert result.type == ResultType.ACTION, result.result
    return result.result.data


LIST_CASES = [
    ("list_companies", {}, "companies"),
    ("get_company_information", {}, "companyInformation"),
    ("list_items", {}, "items"),
    ("list_locations", {}, "locations"),
    ("list_item_variants", {}, "itemVariants"),
    ("list_units_of_measure", {}, "unitsOfMeasure"),
    ("list_vendors", {}, "vendors"),
    ("list_item_ledger_entries", {}, "itemLedgerEntries"),
    ("list_purchase_orders", {}, "purchaseOrders"),
    ("list_purchase_order_lines", {"purchase_order_id": DOCUMENT}, f"purchaseOrders({DOCUMENT})/purchaseOrderLines"),
    ("list_sales_orders", {}, "salesOrders"),
    ("list_sales_order_lines", {"sales_order_id": DOCUMENT}, f"salesOrders({DOCUMENT})/salesOrderLines"),
    ("list_purchase_invoices", {}, "purchaseInvoices"),
    (
        "list_purchase_invoice_lines",
        {"purchase_invoice_id": DOCUMENT},
        f"purchaseInvoices({DOCUMENT})/purchaseInvoiceLines",
    ),
]


@pytest.mark.parametrize("action,extra,resource", LIST_CASES)
async def test_list_actions_preserve_provider_data(mock_context, action, extra, resource):
    inputs = dict(INPUTS, **extra, page_size=20)
    if action == "list_companies":
        inputs.pop("company_id")
    record = {"id": ITEM, "quantity": 12, "receivedQuantity": 5, "currencyCode": "NZD"}
    mock_context.fetch.return_value = response({"value": [record]})
    data = assert_success(await businesscentral.execute_action(action, inputs, mock_context))
    assert data == {"records": [record], "count": 1, "next_link": None, "has_more": False}
    call = mock_context.fetch.await_args
    assert call.args[0] == f"{base_url(inputs, action != 'list_companies')}/{resource}"
    assert call.kwargs["method"] == "GET"
    assert call.kwargs["headers"]["Prefer"] == "odata.maxpagesize=20"
    assert "$top" not in parse_qs(urlsplit(call.args[0]).query)


@pytest.mark.parametrize("action,extra,resource", LIST_CASES)
async def test_empty_collection_is_success(mock_context, action, extra, resource):
    inputs = dict(INPUTS, **extra)
    if action == "list_companies":
        inputs.pop("company_id")
    mock_context.fetch.return_value = response({"value": []})
    assert assert_success(await businesscentral.execute_action(action, inputs, mock_context))["count"] == 0


@pytest.mark.parametrize(
    "action,id_name,resource",
    [
        ("get_item", "item_id", "items"),
        ("get_purchase_order", "purchase_order_id", "purchaseOrders"),
        ("get_sales_order", "sales_order_id", "salesOrders"),
    ],
)
async def test_get_actions(mock_context, action, id_name, resource):
    mock_context.fetch.return_value = response({"id": DOCUMENT, "status": "Open"})
    result = await businesscentral.execute_action(action, dict(INPUTS, **{id_name: DOCUMENT}), mock_context)
    assert assert_success(result)["record"]["id"] == DOCUMENT
    assert mock_context.fetch.await_args.args[0] == f"{base_url(INPUTS)}/{resource}({DOCUMENT})"


async def test_filters_escape_odata_strings_and_validate_dates(mock_context):
    mock_context.fetch.return_value = response({"value": []})
    result = await businesscentral.execute_action(
        "list_item_ledger_entries",
        dict(INPUTS, item_number="BOX'1", start_date="2026-01-01", end_date="2026-01-31"),
        mock_context,
    )
    assert_success(result)
    assert parse_qs(urlsplit(mock_context.fetch.await_args.args[0]).query)["$filter"][0] == (
        "itemNumber eq 'BOX''1' and postingDate ge 2026-01-01 and postingDate le 2026-01-31"
    )


@pytest.mark.parametrize(
    "action,extra,expected",
    [
        ("list_items", {"item_number": "BOX-1"}, "number eq 'BOX-1'"),
        ("list_vendors", {"vendor_number": "V1"}, "number eq 'V1'"),
        ("list_item_variants", {"item_id": ITEM}, f"itemId eq {ITEM}"),
        (
            "list_purchase_orders",
            {"vendor_id": ITEM, "start_date": "2026-01-01"},
            f"vendorId eq {ITEM} and orderDate ge 2026-01-01",
        ),
        ("list_sales_orders", {"end_date": "2026-01-31"}, "orderDate le 2026-01-31"),
        ("list_purchase_invoices", {"end_date": "2026-01-31"}, "postingDate le 2026-01-31"),
        ("list_purchase_order_lines", {"purchase_order_id": DOCUMENT, "item_id": ITEM}, f"itemId eq {ITEM}"),
    ],
)
async def test_resource_filters(mock_context, action, extra, expected):
    mock_context.fetch.return_value = response({"value": []})
    assert_success(await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context))
    assert parse_qs(urlsplit(mock_context.fetch.await_args.args[0]).query)["$filter"][0] == expected


async def test_continuation_preserves_query_and_ignores_new_filters(mock_context):
    link = f"{base_url(INPUTS)}/items?$skiptoken=abc%2Bdef"
    mock_context.fetch.return_value = response({"value": [{"id": ITEM}], "@odata.nextLink": link})
    data = assert_success(await businesscentral.execute_action("list_items", INPUTS, mock_context))
    assert data["has_more"] and data["next_link"] == link
    mock_context.fetch.return_value = response({"value": []})
    assert_success(
        await businesscentral.execute_action(
            "list_items", dict(INPUTS, next_link=link, item_number="ignored"), mock_context
        )
    )
    assert mock_context.fetch.await_args.args[0] == link
    assert mock_context.fetch.await_args.kwargs["params"] is None


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.example/items",
        "http://api.businesscentral.dynamics.com/items",
        f"{base_url(INPUTS)}/vendors?$skiptoken=x",
        f"{base_url(INPUTS)}/items#fragment",
        f"{base_url(INPUTS)}/items/../vendors",
        "https://user@api.businesscentral.dynamics.com/items",
        f"{base_url(dict(INPUTS, environment='Production'))}/items?$skiptoken=x",
        f"{base_url(INPUTS)}/items\n?x=y",
    ],
)
async def test_rejects_unsafe_input_continuations_before_fetch(mock_context, link):
    result = await businesscentral.execute_action("list_items", dict(INPUTS, next_link=link), mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_awaited()


async def test_rejects_unsafe_provider_continuation(mock_context):
    mock_context.fetch.return_value = response({"value": [], "@odata.nextLink": "https://evil.example"})
    result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
@pytest.mark.parametrize("raises", [True, False])
async def test_http_errors_are_sanitized(mock_context, status, raises):
    if raises:
        mock_context.fetch.side_effect = HTTPError(status, "sensitive-provider-data")
    else:
        mock_context.fetch.return_value = response({"error": {"message": "sensitive-provider-data"}}, status)
    result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "sensitive-provider-data" not in result.result.message


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_errors_retry_with_bounded_delay(mock_context, status):
    mock_context.fetch.side_effect = [response({}, status, {"Retry-After": "2"}), response({"value": []})]
    with patch("businesscentral.asyncio.sleep") as sleep:
        assert_success(await businesscentral.execute_action("list_items", INPUTS, mock_context))
    sleep.assert_awaited_once_with(2)


async def test_long_throttle_delay_returns_without_sleep(mock_context):
    mock_context.fetch.return_value = response({}, 429, {"Retry-After": "60"})
    with patch("businesscentral.asyncio.sleep") as sleep:
        result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    sleep.assert_not_awaited()


async def test_sdk_rate_limit_exception_respects_retry_after(mock_context):
    mock_context.fetch.side_effect = RateLimitError(60, 429, "Rate limit exceeded")
    with patch("businesscentral.asyncio.sleep") as sleep:
        result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    sleep.assert_not_awaited()


async def test_sdk_short_rate_limit_exception_waits_then_recovers(mock_context):
    mock_context.fetch.side_effect = [RateLimitError(2, 429, "Rate limit exceeded"), response({"value": []})]
    with patch("businesscentral.asyncio.sleep") as sleep:
        assert_success(await businesscentral.execute_action("list_items", INPUTS, mock_context))
    sleep.assert_awaited_once_with(2)
    assert mock_context.fetch.await_count == 2


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), ClientConnectionError("private transport detail")])
@pytest.mark.parametrize("action,extra", [("list_items", {}), ("get_item", {"item_id": ITEM})])
async def test_exhausted_transport_failures_return_sanitized_retry_guidance(mock_context, error, action, extra):
    mock_context.fetch.side_effect = error
    result = await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Retry this action later" in result.result.message
    assert "private" not in result.result.message


async def test_read_cancellation_propagates(mock_context):
    mock_context.fetch.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await businesscentral.execute_action("list_items", INPUTS, mock_context)


async def test_sdk_network_retry_does_not_duplicate_odata_filters():
    context = ExecutionContext(
        auth={"auth_type": "PlatformOauth2", "credentials": {"access_token": "test-token"}},  # nosec B105
        request_config={"max_retries": 1, "timeout": 30},
    )
    provider_response = MagicMock(status=200, headers={"Content-Type": "application/json"}, ok=True)
    provider_response.json = AsyncMock(return_value={"value": []})
    request = MagicMock()
    request.__aenter__ = AsyncMock(side_effect=[ClientConnectionError("connection reset"), provider_response])
    request.__aexit__ = AsyncMock(return_value=False)
    context._session = MagicMock()
    context._session.request.return_value = request
    with patch("businesscentral.asyncio.sleep"):
        assert_success(await businesscentral.execute_action("list_items", dict(INPUTS, item_number="BOX'+1"), context))
    calls = context._session.request.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["url"] == calls[1].kwargs["url"]
    for call in calls:
        assert parse_qs(urlsplit(call.kwargs["url"]).query) == {"$filter": ["number eq 'BOX''+1'"]}


async def test_invalid_retry_header_uses_backoff(mock_context):
    mock_context.fetch.side_effect = [response({}, 503, {"retry-after": "unknown"}), response({"value": []})]
    with patch("businesscentral.asyncio.sleep") as sleep:
        assert_success(await businesscentral.execute_action("list_items", INPUTS, mock_context))
    sleep.assert_awaited_once_with(1)


async def test_retry_exhaustion(mock_context):
    mock_context.fetch.return_value = response({}, 503)
    with patch("businesscentral.asyncio.sleep"):
        result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert mock_context.fetch.await_count == 3


@pytest.mark.parametrize("body", [{}, {"value": {}}, {"value": ["bad"]}, {"error": {}}, "bad"])
async def test_invalid_provider_shapes(mock_context, body):
    mock_context.fetch.return_value = response(body)
    result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR


async def test_missing_token(mock_context):
    mock_context.auth = {"auth_type": "PlatformOauth2", "credentials": {}}
    result = await businesscentral.execute_action("list_items", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "extra",
    [
        {"company_id": "bad"},
        {"tenant_id": "bad"},
        {"environment": "../Production"},
        {"page_size": 0},
        {"page_size": 1001},
        {"start_date": "2026-02-01", "end_date": "2026-01-01"},
        {"start_date": "2026-02-30"},
    ],
)
async def test_invalid_inputs_never_fetch(mock_context, extra):
    result = await businesscentral.execute_action("list_item_ledger_entries", dict(INPUTS, **extra), mock_context)
    assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
    mock_context.fetch.assert_not_awaited()


async def test_reorder_cost_decimal_precision_and_currency(mock_context):
    mock_context.fetch.side_effect = [response(ITEM_DATA), response({"value": [{"currencyCode": "NZD"}]})]
    data = assert_success(
        await businesscentral.execute_action(
            "estimate_reorder_cost", dict(INPUTS, item_id=ITEM, quantity=3), mock_context
        )
    )
    assert data["estimated_cost"] == "0.3"
    assert data["currency_code"] == "NZD"
    assert data["unit_of_measure"] == "PCS"
    assert data["cost_basis"] == "recorded_item_unit_cost"


@pytest.mark.parametrize(
    "item,info",
    [
        (dict(ITEM_DATA, unitCost=None), {"value": [{"currencyCode": "NZD"}]}),
        (dict(ITEM_DATA, type="Service"), {"value": [{"currencyCode": "NZD"}]}),
        (ITEM_DATA, {"value": []}),
        (ITEM_DATA, {"value": [{"currencyCode": ""}]}),
    ],
)
async def test_cost_does_not_invent_missing_data(mock_context, item, info):
    mock_context.fetch.side_effect = [response(item), response(info)]
    result = await businesscentral.execute_action(
        "estimate_reorder_cost", dict(INPUTS, item_id=ITEM, quantity=3), mock_context
    )
    assert result.type == ResultType.ACTION_ERROR


FORECAST = dict(INPUTS, item_id=ITEM, start_date="2026-01-01", end_date="2026-01-10", forecast_days=30)


async def test_forecast_uses_net_sales_all_calendar_days_and_all_pages(mock_context):
    link = f"{base_url(INPUTS)}/itemLedgerEntries?$skiptoken=next"
    mock_context.fetch.side_effect = [
        response(ITEM_DATA),
        response(
            {
                "value": [
                    {"id": "1", "entryType": "Sale", "quantity": -40},
                    {"id": "2", "entryType": "Purchase", "quantity": 200},
                    {"id": "3", "entryType": "Transfer", "quantity": -100},
                ],
                "@odata.nextLink": link,
            }
        ),
        response(
            {
                "value": [
                    {"id": "4", "entryType": "Sale", "quantity": 10},
                ]
            }
        ),
    ]
    data = assert_success(await businesscentral.execute_action("forecast_stock", FORECAST, mock_context))
    assert data["history_rows"] == 4 and data["sales_entry_count"] == 2
    assert data["net_sales_quantity"] == "30"
    assert data["average_daily_demand"] == "3"
    assert data["forecast_demand"] == "90"
    assert data["projected_inventory"] == "10"
    for call in mock_context.fetch.await_args_list[1:]:
        assert call.kwargs["headers"]["Prefer"] == "odata.maxpagesize=1000"
    assert parse_qs(urlsplit(mock_context.fetch.await_args_list[1].args[0]).query)["$filter"][0] == (
        "itemNumber eq 'BOX-1' and postingDate ge 2026-01-01 and postingDate le 2026-01-10"
    )


@pytest.mark.parametrize("rows,net", [([], "0"), ([{"id": "1", "entryType": "Sale", "quantity": 5}], "-5")])
async def test_no_positive_net_demand_is_explicit(mock_context, rows, net):
    mock_context.fetch.side_effect = [response(ITEM_DATA), response({"value": rows})]
    data = assert_success(await businesscentral.execute_action("forecast_stock", FORECAST, mock_context))
    assert data["net_sales_quantity"] == net
    assert data["forecast_demand"] == "0"
    assert data["days_of_cover"] is None


@pytest.mark.parametrize("inventory,projected,cover", [(-5, "-95", "0"), (12, "-78", "4")])
async def test_stockout_projection_preserves_negative_stock(mock_context, inventory, projected, cover):
    mock_context.fetch.side_effect = [
        response(dict(ITEM_DATA, inventory=inventory)),
        response(
            {
                "value": [
                    {"id": "1", "entryType": "Sale", "quantity": -30},
                ]
            }
        ),
    ]
    data = assert_success(await businesscentral.execute_action("forecast_stock", FORECAST, mock_context))
    assert data["projected_inventory"] == projected
    assert data["days_of_cover"] == cover


async def test_forecast_fails_when_history_exceeds_bound(mock_context):
    mock_context.fetch.side_effect = [
        response(ITEM_DATA),
        response(
            {
                "value": [
                    {"id": "1", "entryType": "Sale", "quantity": -1},
                    {"id": "2", "entryType": "Sale", "quantity": -1},
                ]
            }
        ),
    ]
    with patch("businesscentral.MAX_HISTORY_ROWS", 1):
        result = await businesscentral.execute_action("forecast_stock", FORECAST, mock_context)
    assert result.type == ResultType.ACTION_ERROR


async def test_forecast_fails_on_repeated_empty_pages(mock_context):
    link = f"{base_url(INPUTS)}/itemLedgerEntries?$skiptoken=next"
    mock_context.fetch.side_effect = [
        response(ITEM_DATA),
        response({"value": [], "@odata.nextLink": link}),
        response({"value": [], "@odata.nextLink": link}),
    ]
    result = await businesscentral.execute_action("forecast_stock", FORECAST, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert mock_context.fetch.await_count == 3


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": "1", "entryType": "Sale", "quantity": -1}] * 2,
        [{"entryType": "Sale", "quantity": -1}],
        [{"id": "1", "entryType": "Sale", "quantity": None}],
    ],
)
async def test_forecast_rejects_invalid_or_duplicated_history(mock_context, rows):
    mock_context.fetch.side_effect = [response(ITEM_DATA), response({"value": rows})]
    result = await businesscentral.execute_action("forecast_stock", FORECAST, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize(
    "extra",
    [
        {"end_date": "2099-01-01"},
        {"start_date": "2020-01-01"},
        {"forecast_days": 0},
        {"forecast_days": 366},
    ],
)
async def test_forecast_window_validation(mock_context, extra):
    result = await businesscentral.execute_action("forecast_stock", dict(FORECAST, **extra), mock_context)
    assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
    mock_context.fetch.assert_not_awaited()
