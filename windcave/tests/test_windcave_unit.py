import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave
from windcave.windcave import (
    extract_error_message,
    get_auth_headers,
)

pytestmark = pytest.mark.unit

SAMPLE_TRANSACTION = {
    "id": "txn_1",
    "authorised": True,
    "amount": "19.99",
    "currency": "NZD",
    "merchantReference": "ORDER-1",
    "settlementDate": "20260703",
    "amountSurcharge": "0.50",
}


# ---- Helper Functions ----


class TestGetAuthHeaders:
    def test_builds_basic_auth_header(self, mock_context):
        headers = get_auth_headers(mock_context)
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_encodes_username_and_key(self, mock_context):
        import base64

        headers = get_auth_headers(mock_context)
        encoded = headers["Authorization"].removeprefix("Basic ")
        decoded = base64.b64decode(encoded).decode("ascii")
        assert decoded == "test_user:test_api_key"


class TestExtractErrorMessage:
    def test_extracts_from_errors_list(self):
        err = HTTPError(400, "Bad Request", {"errors": [{"message": "Invalid currency"}]})
        assert extract_error_message(err) == "Invalid currency"

    def test_joins_multiple_errors(self):
        err = HTTPError(400, "Bad Request", {"errors": [{"message": "A"}, {"message": "B"}]})
        assert extract_error_message(err) == "A; B"

    def test_extracts_from_message_field(self):
        err = HTTPError(500, "Server Error", {"message": "Something went wrong"})
        assert extract_error_message(err) == "Something went wrong"

    def test_falls_back_to_status_and_message(self):
        err = HTTPError(502, "Bad Gateway", "not json")
        assert extract_error_message(err) == "Windcave API error (HTTP 502): Bad Gateway"


# ---- Custom Auth Contract ----
# config.json requires username and api_key, and the header helper also rejects
# missing or blank credentials before a request reaches Windcave.


class TestCustomAuthValidation:
    @pytest.mark.asyncio
    async def test_missing_credentials_rejected_by_schema_validation(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {}})

        result = await windcave.execute_action("get_transaction", {"transaction_id": "txn_1"}, ctx)

        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_awaited()

    def test_missing_credentials_rejected_by_header_helper(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {}})

        with pytest.raises(ValueError, match="username is required"):
            get_auth_headers(ctx)

    def test_blank_api_key_rejected_by_header_helper(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {"username": "test_user", "api_key": " "}})

        with pytest.raises(ValueError, match="key is required"):
            get_auth_headers(ctx)

    @pytest.mark.asyncio
    async def test_full_credentials_pass_validation(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("get_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION


# ---- get_transaction ----


class TestGetTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("get_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == "txn_1"
        assert result.result.data["transaction"] == SAMPLE_TRANSACTION
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("get_transaction", {"transaction_id": "txn_1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://uat.windcave.com/api/v1/transactions/txn_1"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"message": "Transaction not found"})

        result = await windcave.execute_action("get_transaction", {"transaction_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Transaction not found" in result.result.message
