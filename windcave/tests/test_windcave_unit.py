from unittest.mock import AsyncMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave
from windcave.windcave import (
    extract_error_message,
    find_link,
    format_amount,
    get_auth_headers,
    get_base_url,
    latest_transaction,
)

pytestmark = pytest.mark.unit

SAMPLE_SESSION = {
    "id": "sess_123",
    "state": "complete",
    "links": [
        {"rel": "self", "href": "https://sec.windcave.com/api/v1/sessions/sess_123"},
        {"rel": "hpp", "href": "https://sec.windcave.com/hpp/sess_123"},
    ],
    "transactions": [
        {
            "id": "txn_1",
            "authorised": True,
            "amount": "19.99",
            "settlementDate": "20260703",
            "amountSurcharge": "0.50",
        }
    ],
}

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


class TestFormatAmount:
    def test_formats_two_decimals(self):
        assert format_amount(19.99) == "19.99"

    def test_rounds_to_two_decimals(self):
        assert format_amount(19.9) == "19.90"

    def test_accepts_int(self):
        assert format_amount(5) == "5.00"

    def test_accepts_numeric_string(self):
        assert format_amount("12.5") == "12.50"


class TestFindLink:
    def test_finds_matching_rel(self):
        assert find_link(SAMPLE_SESSION, "hpp") == "https://sec.windcave.com/hpp/sess_123"

    def test_missing_rel_returns_none(self):
        assert find_link(SAMPLE_SESSION, "refund") is None

    def test_missing_links_key_returns_none(self):
        assert find_link({}, "hpp") is None


class TestLatestTransaction:
    def test_returns_first_transaction(self):
        assert latest_transaction(SAMPLE_SESSION) == SAMPLE_SESSION["transactions"][0]

    def test_no_transactions_returns_none(self):
        assert latest_transaction({"transactions": []}) is None

    def test_missing_key_returns_none(self):
        assert latest_transaction({}) is None


class TestGetBaseUrl:
    def test_production_by_default(self, mock_context):
        assert get_base_url(mock_context) == "https://sec.windcave.com/api/v1"

    def test_uat_when_flag_set(self, mock_context):
        mock_context.auth["use_test_environment"] = True
        assert get_base_url(mock_context) == "https://uat.windcave.com/api/v1"


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
# config.json declares auth.fields with an empty `required` list, so the SDK does NOT
# reject calls with missing username/api_key before the handler runs -- Windcave's own
# API is responsible for rejecting bad credentials. context.auth is still the flat shape
# from auth.fields (no "credentials" envelope), matching custom (non-OAuth) auth.


class TestCustomAuthValidation:
    @pytest.mark.asyncio
    async def test_missing_credentials_not_rejected_by_schema_validation(self, make_context):
        ctx = make_context(auth={"use_test_environment": False})
        ctx.fetch = AsyncMock(side_effect=HTTPError(401, "Unauthorized", {"message": "Invalid credentials"}))

        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid credentials" in result.result.message

    def test_missing_credentials_build_basic_auth_from_empty_strings(self, make_context):
        import base64

        ctx = make_context(auth={})
        headers = get_auth_headers(ctx)

        assert headers["Authorization"] == f"Basic {base64.b64encode(b':').decode('ascii')}"

    @pytest.mark.asyncio
    async def test_full_credentials_pass_validation(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION


# ---- create_session ----


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["session_id"] == "sess_123"
        assert result.result.data["hpp_url"] == "https://sec.windcave.com/hpp/sess_123"
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_missing_hpp_link_returns_none(self, mock_context):
        session_without_hpp_link = {**SAMPLE_SESSION, "links": [{"rel": "self", "href": "https://example.com"}]}
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=session_without_hpp_link)

        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["hpp_url"] is None

    @pytest.mark.asyncio
    async def test_request_url_method_and_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/sessions"
        assert call_args.kwargs["method"] == "POST"
        body = call_args.kwargs["json"]
        assert body["type"] == "purchase"
        assert body["amount"] == "19.99"
        assert body["currency"] == "NZD"
        assert body["merchantReference"] == "ORDER-1"

    @pytest.mark.asyncio
    async def test_uses_uat_base_url_when_configured(self, mock_context):
        mock_context.auth["use_test_environment"] = True
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0] == "https://uat.windcave.com/api/v1/sessions"

    @pytest.mark.asyncio
    async def test_validate_type_does_not_require_amount(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action(
            "create_session",
            {"type": "validate", "currency": "NZD", "merchant_reference": "ORDER-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        body = mock_context.fetch.call_args.kwargs["json"]
        assert "amount" not in body

    @pytest.mark.asyncio
    async def test_purchase_without_amount_returns_action_error(self, mock_context):
        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "amount" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_optional_fields_included_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_SESSION)

        await windcave.execute_action(
            "create_session",
            {
                "currency": "NZD",
                "merchant_reference": "ORDER-1",
                "amount": 19.99,
                "methods": ["card"],
                "store_card": True,
                "language": "en",
                "approved_callback_url": "https://example.com/ok",
                "declined_callback_url": "https://example.com/declined",
                "cancelled_callback_url": "https://example.com/cancelled",
                "notification_url": "https://example.com/notify",
                "amount_surcharge": 0.5,
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["methods"] == ["card"]
        assert body["storeCard"] is True
        assert body["language"] == "en"
        assert body["callbackUrls"] == {
            "approved": "https://example.com/ok",
            "declined": "https://example.com/declined",
            "cancelled": "https://example.com/cancelled",
        }
        assert body["notificationUrl"] == "https://example.com/notify"
        assert body["amountSurcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"errors": [{"message": "Invalid currency"}]})

        result = await windcave.execute_action(
            "create_session",
            {"currency": "XXX", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid currency" in result.result.message

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await windcave.execute_action(
            "create_session",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message


# ---- get_session ----


class TestGetSession:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_SESSION)

        result = await windcave.execute_action("get_session", {"session_id": "sess_123"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["session_id"] == "sess_123"
        assert result.result.data["authorised"] is True
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"
        assert result.result.data["transactions"] == SAMPLE_SESSION["transactions"]

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_SESSION)

        await windcave.execute_action("get_session", {"session_id": "sess_123"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/sessions/sess_123"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_session_with_no_transactions_yet(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": "sess_999", "state": "incomplete", "transactions": []}
        )

        result = await windcave.execute_action("get_session", {"session_id": "sess_999"}, mock_context)

        assert result.result.data["authorised"] is None
        assert result.result.data["settlement_date"] is None
        assert result.result.data["amount_surcharge"] is None
        assert result.result.data["transactions"] == []

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"message": "Session not found"})

        result = await windcave.execute_action("get_session", {"session_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Session not found" in result.result.message


# ---- create_transaction ----


class TestCreateTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action(
            "create_transaction",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "card_id": "card_abc", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == "txn_1"
        assert result.result.data["authorised"] is True
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "create_transaction",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "card_id": "card_abc", "amount": 19.99},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/transactions"
        body = call_args.kwargs["json"]
        assert body == {
            "type": "purchase",
            "currency": "NZD",
            "merchantReference": "ORDER-1",
            "cardId": "card_abc",
            "amount": "19.99",
        }

    @pytest.mark.asyncio
    async def test_request_body_includes_amount_surcharge_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "create_transaction",
            {
                "currency": "NZD",
                "merchant_reference": "ORDER-1",
                "card_id": "card_abc",
                "amount": 19.99,
                "amount_surcharge": 0.5,
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["amountSurcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_validate_type_does_not_require_amount(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action(
            "create_transaction",
            {"type": "validate", "currency": "NZD", "merchant_reference": "ORDER-1", "card_id": "card_abc"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert "amount" not in mock_context.fetch.call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_auth_without_amount_returns_action_error(self, mock_context):
        result = await windcave.execute_action(
            "create_transaction",
            {"type": "auth", "currency": "NZD", "merchant_reference": "ORDER-1", "card_id": "card_abc"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(402, "Payment Required", {"errors": [{"message": "Declined"}]})

        result = await windcave.execute_action(
            "create_transaction",
            {"currency": "NZD", "merchant_reference": "ORDER-1", "card_id": "card_abc", "amount": 19.99},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Declined" in result.result.message


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
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/transactions/txn_1"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not Found", {"message": "Transaction not found"})

        result = await windcave.execute_action("get_transaction", {"transaction_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Transaction not found" in result.result.message


# ---- complete_transaction ----


class TestCompleteTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("complete_transaction", {"transaction_id": "txn_auth_1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == "txn_1"
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_request_body_minimal(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("complete_transaction", {"transaction_id": "txn_auth_1"}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body == {"type": "complete", "transaction": {"id": "txn_auth_1"}}

    @pytest.mark.asyncio
    async def test_request_body_with_partial_amount_and_reference(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "complete_transaction",
            {"transaction_id": "txn_auth_1", "amount": 10.5, "merchant_reference": "ORDER-1-CAP"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["amount"] == "10.50"
        assert body["merchantReference"] == "ORDER-1-CAP"

    @pytest.mark.asyncio
    async def test_request_body_includes_amount_surcharge_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "complete_transaction",
            {"transaction_id": "txn_auth_1", "amount_surcharge": 0.5},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["amountSurcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            409, "Conflict", {"errors": [{"message": "Transaction already completed"}]}
        )

        result = await windcave.execute_action("complete_transaction", {"transaction_id": "txn_auth_1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "already completed" in result.result.message


# ---- refund_transaction ----


class TestRefundTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("refund_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == "txn_1"
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_full_refund_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("refund_transaction", {"transaction_id": "txn_1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/transactions"
        assert call_args.kwargs["json"] == {"type": "refund", "transaction": {"id": "txn_1"}}

    @pytest.mark.asyncio
    async def test_partial_refund_includes_amount(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("refund_transaction", {"transaction_id": "txn_1", "amount": 5}, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["amount"] == "5.00"

    @pytest.mark.asyncio
    async def test_request_body_includes_amount_surcharge_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "refund_transaction",
            {"transaction_id": "txn_1", "amount_surcharge": 0.5},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["amountSurcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            400, "Bad Request", {"errors": [{"message": "Refund exceeds original amount"}]}
        )

        result = await windcave.execute_action("refund_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "exceeds original amount" in result.result.message


# ---- void_transaction ----


class TestVoidTransaction:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        result = await windcave.execute_action("void_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == "txn_1"
        assert result.result.data["settlement_date"] == "20260703"
        assert result.result.data["amount_surcharge"] == "0.50"

    @pytest.mark.asyncio
    async def test_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action("void_transaction", {"transaction_id": "txn_1"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://sec.windcave.com/api/v1/transactions"
        assert call_args.kwargs["json"] == {"type": "void", "transaction": {"id": "txn_1"}}

    @pytest.mark.asyncio
    async def test_includes_merchant_reference_when_provided(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TRANSACTION)

        await windcave.execute_action(
            "void_transaction", {"transaction_id": "txn_1", "merchant_reference": "ORDER-1-VOID"}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["merchantReference"] == "ORDER-1-VOID"

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            409, "Conflict", {"errors": [{"message": "Transaction already settled"}]}
        )

        result = await windcave.execute_action("void_transaction", {"transaction_id": "txn_1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "already settled" in result.result.message
