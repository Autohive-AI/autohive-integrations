import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave
from windcave.windcave import (
    extract_error_message,
    get_auth_headers,
    redact_card_objects,
)

pytestmark = pytest.mark.unit

TRANSACTION_ID = "0000001c00000001"
MISSING_TRANSACTION_ID = "0000001c00000002"

SAMPLE_TRANSACTION = {
    "id": TRANSACTION_ID,
    "authorised": True,
    "amount": "19.99",
    "currency": "NZD",
    "merchantReference": "ORDER-1",
    "settlementDate": "20260703",
    "amountSurcharge": "0.50",
    "card": {
        "id": "card_token_1",
        "cardHolderName": "TEST CUSTOMER",
        "cardNumber": "411111......1111",
        "dateExpiryMonth": "12",
        "dateExpiryYear": "30",
        "type": "visa",
    },
}

SAMPLE_SESSION = {
    "id": "session_1",
    "state": "complete",
    "type": "purchase",
    "amount": "19.99",
    "currency": "NZD",
    "merchantReference": "ORDER-1",
    "expires": "2026-09-02T00:00:00Z",
    "transactions": [
        {
            "id": "txn_1",
            "authorised": False,
            "responseText": "DECLINED",
            "card": {
                "id": "card_token_1",
                "cardHolderName": "TEST CUSTOMER",
                "cardNumber": "411111......1111",
                "dateExpiryMonth": "12",
                "dateExpiryYear": "30",
                "type": "visa",
                "metadata": {"issuer": "Test Bank"},
            },
        },
        {
            "id": "txn_2",
            "authorised": True,
            "responseText": "APPROVED",
            "card": {
                "id": "card_token_2",
                "cardHolderName": "ANOTHER CUSTOMER",
                "cardNumber": "545301......5323",
                "dateExpiryMonth": "11",
                "dateExpiryYear": "31",
                "type": "mastercard",
            },
        },
    ],
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


class TestRedactCardObjects:
    def test_preserves_card_shape_and_redacts_all_values(self):
        result = redact_card_objects(SAMPLE_SESSION)

        card = result["transactions"][0]["card"]
        assert set(card) == set(SAMPLE_SESSION["transactions"][0]["card"])
        assert card["id"] == "[REDACTED]"
        assert card["cardHolderName"] == "[REDACTED]"
        assert card["cardNumber"] == "[REDACTED]"
        assert card["metadata"]["issuer"] == "[REDACTED]"

    def test_does_not_mutate_source_data(self):
        redact_card_objects(SAMPLE_SESSION)

        assert SAMPLE_SESSION["transactions"][0]["card"]["cardNumber"] == "411111......1111"


# ---- Custom Auth Contract ----
# config.json requires username and api_key, and the header helper also rejects
# missing or blank credentials before a request reaches Windcave.


class TestCustomAuthValidation:
    @pytest.mark.asyncio
    async def test_missing_credentials_rejected_by_schema_validation(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {}})

        result = await windcave.execute_action("get_transaction", {"transaction_id": TRANSACTION_ID}, ctx)

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

        result = await windcave.execute_action("get_transaction", {"transaction_id": TRANSACTION_ID}, mock_context)

        assert result.type == ResultType.ACTION


# ---- get_transaction ----


class TestGetTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("get_transaction", {"transaction_id": TRANSACTION_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == TRANSACTION_ID
        assert result.result.data["transaction"]["merchantReference"] == "ORDER-1"
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_redacts_card_data_in_transaction(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("get_transaction", {"transaction_id": TRANSACTION_ID}, mock_context)

        transaction = result.result.data["transaction"]
        assert transaction["card"]["id"] == "[REDACTED]"
        assert transaction["card"]["cardHolderName"] == "[REDACTED]"
        assert transaction["card"]["cardNumber"] == "[REDACTED]"
        assert "411111" not in str(result.result.data)
        assert "TEST CUSTOMER" not in str(result.result.data)

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("get_transaction", {"transaction_id": TRANSACTION_ID}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"https://uat.windcave.com/api/v1/transactions/{TRANSACTION_ID}"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_path_traversal_id_rejected_before_fetch(self, mock_context):
        result = await windcave.execute_action(
            "get_transaction", {"transaction_id": "../sessions/session_1"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"message": "Transaction not found"})

        result = await windcave.execute_action(
            "get_transaction", {"transaction_id": MISSING_TRANSACTION_ID}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Transaction not found" in result.result.message


# ---- get_session ----


class TestGetSession:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action("get_session", {"session_id": "session_1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["session_id"] == "session_1"
        assert result.result.data["state"] == "complete"
        assert result.result.data["merchant_reference"] == "ORDER-1"
        assert len(result.result.data["transactions"]) == 2
        assert result.result.data["session"]["id"] == "session_1"

    @pytest.mark.asyncio
    async def test_redacts_card_data_in_transactions_and_full_session(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action("get_session", {"session_id": "session_1"}, mock_context)

        output = result.result.data
        for transaction in output["transactions"]:
            assert transaction["card"]
            assert transaction["card"]["id"] == "[REDACTED]"
            assert transaction["card"]["cardHolderName"] == "[REDACTED]"
            assert transaction["card"]["cardNumber"] == "[REDACTED]"
        serialized_output = str(output)
        assert "411111" not in serialized_output
        assert "545301" not in serialized_output
        assert "TEST CUSTOMER" not in serialized_output
        assert output["session"]["transactions"] == output["transactions"]

    @pytest.mark.asyncio
    async def test_request_url_method_and_headers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_SESSION)

        await windcave.execute_action("get_session", {"session_id": "session/1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://uat.windcave.com/api/v1/sessions/session%2F1"
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["headers"]["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_session_without_transactions_returns_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "session_1"})

        result = await windcave.execute_action("get_session", {"session_id": "session_1"}, mock_context)

        assert result.result.data["transactions"] == []

    @pytest.mark.asyncio
    async def test_empty_session_id_returns_validation_error(self, mock_context):
        result = await windcave.execute_action("get_session", {"session_id": ""}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"message": "Session not found"})

        result = await windcave.execute_action("get_session", {"session_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Session not found" in result.result.message
