import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from retail_express import retail_express


pytestmark = pytest.mark.unit


def queue_api_response(mock_context, data):
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
        FetchResponse(status=200, headers={}, data=data),
    ]


class TestListCustomers:
    async def test_returns_customers_and_passes_filters(self, mock_context):
        customer = {"id": 7, "email": "customer@example.com"}
        queue_api_response(
            mock_context,
            {"data": [customer], "page_number": 2, "page_size": 10, "total_records": 11},
        )

        result = await retail_express.execute_action(
            "list_customers",
            {
                "page_number": 2,
                "page_size": 10,
                "email": "customer@example.com",
                "modified_since": "2026-01-01T00:00:00Z",
                "filter_by": "company:eq:Example Ltd",
            },
            mock_context,
        )

        assert result.result.data["customers"] == [customer]
        assert result.result.data["total_records"] == 11
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/customers"
        assert request.kwargs["method"] == "GET"
        assert request.kwargs["params"] == {
            "page_number": 2,
            "page_size": 10,
            "modified_since": "2026-01-01T00:00:00Z",
            "filter_by": "company:eq:Example Ltd,email:eq:customer@example.com",
        }


class TestGetCustomer:
    async def test_gets_customer_by_id(self, mock_context):
        customer = {"id": 7, "first_name": "Casey"}
        queue_api_response(mock_context, {"data": customer})

        result = await retail_express.execute_action("get_customer", {"customer_id": "7"}, mock_context)

        assert result.result.data == {"customer": customer, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/customers/7"
        assert request.kwargs["method"] == "GET"


class TestCreateCustomer:
    async def test_posts_all_customer_fields(self, mock_context):
        billing_address = {"line1": "1 Queen Street", "city": "Auckland"}
        shipping_address = {"line1": "2 High Street", "city": "Auckland"}
        customer = {"id": 8, "first_name": "Alex", "last_name": "Smith"}
        queue_api_response(mock_context, {"data": customer})
        inputs = {
            "first_name": "Alex",
            "last_name": "Smith",
            "email": "alex@example.com",
            "phone": "09 555 0100",
            "mobile": "021 555 0100",
            "company": "Example Ltd",
            "billing_address": billing_address,
            "shipping_address": shipping_address,
        }

        result = await retail_express.execute_action("create_customer", inputs, mock_context)

        assert result.result.data == {"customer": customer, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/customers"
        assert request.kwargs["method"] == "POST"
        assert request.kwargs["json"] == inputs

    async def test_omits_empty_optional_fields(self, mock_context):
        queue_api_response(mock_context, {"data": {"id": 8}})

        await retail_express.execute_action(
            "create_customer",
            {"first_name": "Alex", "last_name": "Smith", "email": ""},
            mock_context,
        )

        assert mock_context.fetch.await_args_list[1].kwargs["json"] == {
            "first_name": "Alex",
            "last_name": "Smith",
        }


class TestUpdateCustomer:
    async def test_puts_only_supplied_customer_fields(self, mock_context):
        customer = {"id": 7, "first_name": "Alex", "last_name": "Jones"}
        queue_api_response(mock_context, {"data": customer})
        inputs = {
            "customer_id": "7",
            "first_name": "Alex",
            "last_name": "Jones",
            "email": "alex.jones@example.com",
            "phone": "09 555 0101",
            "mobile": "021 555 0101",
            "company": "Updated Ltd",
        }

        result = await retail_express.execute_action("update_customer", inputs, mock_context)

        assert result.result.data == {"customer": customer, "result": True}
        request = mock_context.fetch.await_args_list[1]
        assert request.args[0] == "https://api.retailexpress.com.au/v2.1/customers/7"
        assert request.kwargs["method"] == "PUT"
        assert request.kwargs["json"] == {
            "first_name": "Alex",
            "last_name": "Jones",
            "email": "alex.jones@example.com",
            "phone": "09 555 0101",
            "mobile": "021 555 0101",
            "company": "Updated Ltd",
        }

    async def test_omits_empty_update_fields(self, mock_context):
        queue_api_response(mock_context, {"data": {"id": 7}})

        await retail_express.execute_action(
            "update_customer",
            {"customer_id": "7", "email": "alex@example.com", "company": ""},
            mock_context,
        )

        assert mock_context.fetch.await_args_list[1].kwargs["json"] == {"email": "alex@example.com"}


class TestCustomerErrorsAndValidation:
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("list_customers", {}),
            ("get_customer", {"customer_id": "7"}),
            ("create_customer", {"first_name": "Alex", "last_name": "Smith"}),
            ("update_customer", {"customer_id": "7", "email": "alex@example.com"}),
        ],
    )
    async def test_returns_action_error_when_fetch_fails(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RuntimeError("customer API unavailable")

        result = await retail_express.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "customer API unavailable"

    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("get_customer", {}),
            ("create_customer", {"first_name": "Alex"}),
            ("update_customer", {}),
        ],
    )
    async def test_rejects_missing_required_inputs(self, mock_context, action, inputs):
        result = await retail_express.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()
