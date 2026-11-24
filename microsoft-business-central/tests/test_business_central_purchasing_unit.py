import asyncio

import pytest
from aiohttp import ClientConnectionError
from autohive_integrations_sdk import FetchResponse, ResultType

from businesscentral import base_url, businesscentral

pytestmark = pytest.mark.unit
TENANT = "11111111-1111-1111-1111-111111111111"
COMPANY = "22222222-2222-2222-2222-222222222222"
ITEM = "33333333-3333-3333-3333-333333333333"
ORDER = "44444444-4444-4444-4444-444444444444"
INPUTS = {"tenant_id": TENANT, "environment": "Sandbox", "company_id": COMPANY, "vendor_number": "20000"}


@pytest.mark.parametrize("vendor", [{"vendor_number": "20000"}, {"vendor_id": ITEM}])
async def test_create_header_uses_vendor_and_preserves_response(mock_context, vendor):
    record = {"id": ORDER, "number": "PO100", "status": "Draft", "currencyCode": "NZD"}
    mock_context.request.return_value = FetchResponse(status=201, headers={}, data=record)
    inputs = {k: v for k, v in INPUTS.items() if k != "vendor_number"} | vendor
    result = await businesscentral.execute_action("create_purchase_order", inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == {"record": record}
    call = mock_context.request.await_args
    assert call.args == (f"{base_url(INPUTS)}/purchaseOrders",)
    assert call.kwargs == {
        "method": "POST",
        "json": {"vendorNumber": "20000"} if "vendor_number" in vendor else {"vendorId": ITEM},
    }
    mock_context.request.assert_awaited_once()


REMOVE_INPUTS = {k: v for k, v in INPUTS.items() if k != "vendor_number"} | {
    "purchase_order_id": ORDER,
    "etag": 'W/"current-version"',
}


@pytest.mark.parametrize("etag", ['W/"current-version"', '"current-version"'])
async def test_remove_order_sends_conditional_delete_and_accepts_empty_response(mock_context, etag):
    mock_context.request.return_value = FetchResponse(status=204, headers={}, data=None)
    result = await businesscentral.execute_action("remove_purchase_order", dict(REMOVE_INPUTS, etag=etag), mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == {"purchase_order_id": ORDER, "deleted": True}
    mock_context.request.assert_awaited_once_with(
        f"{base_url(REMOVE_INPUTS)}/purchaseOrders({ORDER})",
        method="DELETE",
        headers={"If-Match": etag},
    )


@pytest.mark.parametrize("etag", ["*", "", "unquoted", 'W/""', 'W/"x"\r\nInjected: yes', '"x", "y"'])
async def test_remove_rejects_invalid_or_wildcard_etags(mock_context, etag):
    result = await businesscentral.execute_action("remove_purchase_order", dict(REMOVE_INPUTS, etag=etag), mock_context)
    assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
    mock_context.request.assert_not_awaited()


@pytest.mark.parametrize("field", ["purchase_order_id", "company_id", "tenant_id"])
async def test_remove_rejects_invalid_ids(mock_context, field):
    result = await businesscentral.execute_action(
        "remove_purchase_order", dict(REMOVE_INPUTS, **{field: "invalid"}), mock_context
    )
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.request.assert_not_awaited()


async def test_remove_requires_etag(mock_context):
    inputs = {k: v for k, v in REMOVE_INPUTS.items() if k != "etag"}
    result = await businesscentral.execute_action("remove_purchase_order", inputs, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.request.assert_not_awaited()


async def test_remove_requires_connection(mock_context):
    mock_context.auth["credentials"] = {}
    result = await businesscentral.execute_action("remove_purchase_order", REMOVE_INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.request.assert_not_awaited()


@pytest.mark.parametrize("status", [200, 202, 400, 401, 403, 404, 409, 412, 429, 500, 503])
async def test_remove_reports_provider_failures_without_retrying(mock_context, status):
    mock_context.request.return_value = FetchResponse(status=status, headers={}, data={"error": "sensitive"})
    result = await businesscentral.execute_action("remove_purchase_order", REMOVE_INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "sensitive" not in result.result.message
    if status == 412:
        assert "changed" in result.result.message
    if status == 404:
        assert "not found" in result.result.message
    mock_context.request.assert_awaited_once()


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), ClientConnectionError("sensitive")])
async def test_remove_handles_uncertain_network_outcome(mock_context, error):
    mock_context.request.side_effect = error
    result = await businesscentral.execute_action("remove_purchase_order", REMOVE_INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "outcome is unknown" in result.result.message
    assert "sensitive" not in result.result.message
    mock_context.request.assert_awaited_once()


async def test_create_order_with_item_lines_and_header_options(mock_context):
    mock_context.request.return_value = FetchResponse(status=201, headers={}, data={"id": ORDER})
    inputs = dict(
        INPUTS,
        order_date="2026-11-24",
        posting_date="2026-11-25",
        requested_receipt_date="2026-12-01",
        currency_code="",
        lines=[
            {
                "item_id": ITEM,
                "quantity": 2.5,
                "direct_unit_cost": 0,
                "unit_of_measure_code": "PCS",
                "description": "Boxes",
            },
            {"item_id": ITEM, "quantity": 1},
        ],
    )
    result = await businesscentral.execute_action("create_purchase_order", inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert mock_context.request.await_args.kwargs["json"] == {
        "vendorNumber": "20000",
        "orderDate": "2026-11-24",
        "postingDate": "2026-11-25",
        "requestedReceiptDate": "2026-12-01",
        "currencyCode": "",
        "purchaseOrderLines": [
            {
                "lineType": "Item",
                "itemId": ITEM,
                "quantity": 2.5,
                "directUnitCost": 0,
                "unitOfMeasureCode": "PCS",
                "description": "Boxes",
            },
            {"lineType": "Item", "itemId": ITEM, "quantity": 1},
        ],
    }
    mock_context.request.assert_awaited_once()


@pytest.mark.parametrize(
    "extra",
    [
        {"vendor_id": ITEM},
        {"vendor_number": ""},
        {"vendor_id": "invalid", "vendor_number": None},
        {"order_date": "2026-02-30"},
        {"lines": []},
        {"lines": [{"item_id": ITEM, "quantity": 0}]},
        {"lines": [{"item_id": ITEM, "quantity": -1}]},
        {"lines": [{"item_id": "invalid", "quantity": 1}]},
        {"lines": [{"item_id": ITEM, "quantity": 1, "direct_unit_cost": -1}]},
        {"lines": [{"item_id": ITEM, "quantity": 1, "receiveQuantity": 1}]},
        {"status": "Open"},
    ],
)
async def test_invalid_inputs_do_not_write(mock_context, extra):
    result = await businesscentral.execute_action("create_purchase_order", dict(INPUTS, **extra), mock_context)
    assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
    mock_context.request.assert_not_awaited()


async def test_missing_vendor_does_not_write(mock_context):
    inputs = {k: v for k, v in INPUTS.items() if k != "vendor_number"}
    result = await businesscentral.execute_action("create_purchase_order", inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.request.assert_not_awaited()


async def test_missing_connection_does_not_write(mock_context):
    mock_context.auth["credentials"] = {}
    result = await businesscentral.execute_action("create_purchase_order", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.request.assert_not_awaited()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503, 504])
async def test_provider_failures_are_sanitized_and_not_retried(mock_context, status):
    mock_context.request.return_value = FetchResponse(status=status, headers={}, data={"error": "sensitive"})
    result = await businesscentral.execute_action("create_purchase_order", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "sensitive" not in result.result.message
    mock_context.request.assert_awaited_once()


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), ClientConnectionError("sensitive")])
async def test_uncertain_network_outcome_requires_check_before_retry(mock_context, error):
    mock_context.request.side_effect = error
    result = await businesscentral.execute_action("create_purchase_order", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Check Business Central before retrying" in result.result.message
    mock_context.request.assert_awaited_once()


@pytest.mark.parametrize("data", [None, [], {}, {"error": "sensitive"}, {"number": "PO100"}])
async def test_malformed_creation_response_does_not_report_success(mock_context, data):
    mock_context.request.return_value = FetchResponse(status=201, headers={}, data=data)
    result = await businesscentral.execute_action("create_purchase_order", INPUTS, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "before retrying" in result.result.message
    mock_context.request.assert_awaited_once()
