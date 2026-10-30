import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from retail_express import retail_express


pytestmark = pytest.mark.unit


def queue_api_response(mock_context, data):
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
        FetchResponse(status=200, headers={}, data=data),
    ]


class TestListOrders:
    async def test_returns_orders_and_passes_filters(self, mock_context):
        order = {"id": 99, "status": "Completed"}
        queue_api_response(
            mock_context,
            {"data": [order], "page_number": 3, "page_size": 20, "total_records": 41},
        )

        result = await retail_express.execute_action(
            "list_orders",
            {
                "page_number": 3,
                "page_size": 20,
                "order_status_id": 4,
                "customer_id": "7",
                "modified_since": "2026-01-01T00:00:00Z",
                "filter_by": "outlet_id:eq:3",
            },
            mock_context,
        )

        assert result.result.data["orders"] == [order]
        assert result.result.data["total_records"] == 41
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/orders"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["params"] == {
            "page_number": 3,
            "page_size": 20,
            "modified_since": "2026-01-01T00:00:00Z",
            "filter_by": "outlet_id:eq:3,customer_id:eq:7,order_status_id:eq:4",
        }


class TestGetOrder:
    async def test_gets_order_by_id(self, mock_context):
        order = {"id": 99, "status": "Completed"}
        queue_api_response(mock_context, {"data": order})

        result = await retail_express.execute_action("get_order", {"order_id": "99"}, mock_context)

        assert result.result.data == {"order": order, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/orders/99"
        assert request.kwargs["method"] == "GET"


class TestListOutlets:
    async def test_returns_outlets_with_pagination(self, mock_context):
        outlet = {"id": 3, "name": "Queen Street"}
        queue_api_response(
            mock_context,
            {"data": [outlet], "page_number": 2, "page_size": 5, "total_records": 6},
        )

        result = await retail_express.execute_action("list_outlets", {"page_number": 2, "page_size": 5}, mock_context)

        assert result.result.data == {
            "outlets": [outlet],
            "page_number": 2,
            "page_size": 5,
            "total_records": 6,
            "result": True,
        }
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/outlets"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["params"] == {"page_number": 2, "page_size": 5}


class TestGetOutlet:
    async def test_gets_outlet_by_id(self, mock_context):
        outlet = {"id": 3, "name": "Queen Street"}
        queue_api_response(mock_context, {"data": outlet})

        result = await retail_express.execute_action("get_outlet", {"outlet_id": "3"}, mock_context)

        assert result.result.data == {"outlet": outlet, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/outlets/3"
        assert request.kwargs["method"] == "GET"


class TestOrderOutletErrorsAndValidation:
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("list_orders", {}),
            ("get_order", {"order_id": "99"}),
            ("list_outlets", {}),
            ("get_outlet", {"outlet_id": "3"}),
        ],
    )
    async def test_returns_action_error_when_fetch_fails(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RuntimeError("Retail Express unavailable")

        result = await retail_express.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Retail Express unavailable"

    @pytest.mark.parametrize("action", ["get_order", "get_outlet"])
    async def test_rejects_missing_required_id(self, mock_context, action):
        result = await retail_express.execute_action(action, {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()
