"""
Unit tests for the Uber Ride Requests integration using mocked fetch.

These tests drive the integration through ``execute_action`` with a mocked
``context.fetch`` that returns ``FetchResponse`` objects (SDK 2.0.0). They are
CI-safe — no credentials, no network.
"""

import importlib.util
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

# The integration folder ships an __init__.py that turns `uber` into a package
# exposing only the integration object, so `import uber` is ambiguous with uber.py.
# Load the action source directly by file path to get the handlers/helpers too.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("uber_integration_mod", os.path.join(_parent, "uber.py"))
uber_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uber_mod)

uber_integration = uber_mod.uber
validate_coordinates = uber_mod.validate_coordinates
validate_seat_count = uber_mod.validate_seat_count
validate_limit = uber_mod.validate_limit
validate_offset = uber_mod.validate_offset
validate_required_string = uber_mod.validate_required_string
validate_id = uber_mod.validate_id
classify_error = uber_mod.classify_error
UberAPIError = uber_mod.UberAPIError

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def make_ctx(response_data=None):
    """Mock context whose fetch returns a successful FetchResponse."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok({} if response_data is None else response_data))
    ctx.auth = {}
    return ctx


def make_ctx_error(exc):
    """Mock context whose fetch raises (simulating an upstream API error)."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc)
    ctx.auth = {}
    return ctx


def assert_action_error(result, *substrings):
    assert result.type == ResultType.ACTION_ERROR
    message = result.result.message
    for sub in substrings:
        assert sub in message, f"expected {sub!r} in {message!r}"


def fetch_params(ctx):
    return ctx.fetch.call_args.kwargs.get("params", {})


def fetch_body(ctx):
    return ctx.fetch.call_args.kwargs.get("json", {})


# =============================================================================
# Validation Helper Tests (pure functions)
# =============================================================================


class TestValidationHelpers:
    def test_validate_coordinates_valid(self):
        assert validate_coordinates(37.7749, -122.4194) is None
        assert validate_coordinates(0, 0) is None
        assert validate_coordinates(-90, -180) is None
        assert validate_coordinates(90, 180) is None

    def test_validate_coordinates_invalid_range(self):
        assert "latitude must be between" in validate_coordinates(91, -122.4194)
        assert "longitude must be between" in validate_coordinates(37.7749, 181)
        assert "latitude must be between" in validate_coordinates(-91, 0)

    def test_validate_coordinates_missing(self):
        assert "required" in validate_coordinates(None, -122.4194)
        assert "required" in validate_coordinates(37.7749, None)

    def test_validate_coordinates_invalid_type(self):
        assert "must be numbers" in validate_coordinates("invalid", -122.4194)

    def test_validate_coordinates_with_prefix(self):
        assert "start_latitude" in validate_coordinates(None, None, "start_")

    def test_validate_seat_count(self):
        assert validate_seat_count(1) == 1
        assert validate_seat_count(2) == 2
        assert validate_seat_count(0) == 1  # clamped to minimum 1
        assert validate_seat_count(3) == 2  # clamped to maximum 2
        assert validate_seat_count(None) == 2  # default when not provided

    def test_validate_seat_count_invalid_type(self):
        with pytest.raises(UberAPIError) as exc_info:
            validate_seat_count("invalid")
        assert "seat_count must be an integer" in str(exc_info.value)

        with pytest.raises(UberAPIError) as exc_info:
            validate_seat_count(1.5)
        assert "seat_count must be an integer" in str(exc_info.value)

    def test_validate_limit(self):
        assert validate_limit(10) == 10
        assert validate_limit(50) == 50
        assert validate_limit(100) == 50
        assert validate_limit(0) == 1
        assert validate_limit(-1) == 1
        assert validate_limit(None) == 10
        assert validate_limit("invalid") == 10

    def test_validate_limit_custom_max(self):
        assert validate_limit(100, max_limit=100) == 100
        assert validate_limit(200, max_limit=100) == 100

    def test_validate_offset(self):
        assert validate_offset(0) == 0
        assert validate_offset(10) == 10
        assert validate_offset(-1) == 0
        assert validate_offset(None) == 0
        assert validate_offset("invalid") == 0

    def test_validate_required_string_valid(self):
        assert validate_required_string("abc123", "field") is None
        assert validate_required_string("  valid  ", "field") is None

    def test_validate_required_string_invalid(self):
        assert "request_id is required" in validate_required_string(None, "request_id")
        assert "non-empty string" in validate_required_string("", "request_id")
        assert "non-empty string" in validate_required_string("   ", "request_id")
        assert "non-empty string" in validate_required_string(123, "request_id")

    def test_validate_id_valid(self):
        assert validate_id("abc123", "request_id") is None
        assert validate_id("ABC-123", "request_id") is None
        assert validate_id("abc_123", "request_id") is None
        assert validate_id("a1111c8c-c720-46c3-8534-2fcdd730040d", "request_id") is None
        assert validate_id("id@domain", "request_id") is None
        assert validate_id("id:colon", "request_id") is None
        assert validate_id("id.dot", "request_id") is None

    def test_validate_id_invalid_missing(self):
        assert "request_id is required" in validate_id(None, "request_id")
        assert "non-empty string" in validate_id("", "request_id")
        assert "non-empty string" in validate_id("   ", "request_id")

    def test_validate_id_path_traversal(self):
        assert "invalid characters" in validate_id("../history", "request_id")
        assert "invalid characters" in validate_id("../../etc/passwd", "request_id")
        assert "invalid characters" in validate_id("request/../other", "request_id")
        assert "invalid characters" in validate_id("id/with/slashes", "request_id")
        assert "invalid characters" in validate_id("id\\backslash", "request_id")

    def test_validate_id_url_injection(self):
        assert "invalid characters" in validate_id("id?force=true", "request_id")
        assert "invalid characters" in validate_id("id&param=value", "request_id")
        assert "invalid characters" in validate_id("id#fragment", "request_id")
        assert "invalid characters" in validate_id("id%20encoded", "request_id")


class TestClassifyError:
    def test_classify_401_auth_error(self):
        assert classify_error("401 Unauthorized") == "auth_error"
        assert classify_error("HTTP 401: Authentication required") == "auth_error"
        assert classify_error("Error: unauthorized access") == "auth_error"

    def test_classify_429_rate_limited(self):
        assert classify_error("429 Too Many Requests") == "rate_limited"
        assert classify_error("Rate limit exceeded") == "rate_limited"
        assert classify_error("too many requests") == "rate_limited"

    def test_classify_rate_not_too_broad(self):
        assert classify_error("accelerate your request") == "api_error"
        assert classify_error("prorate the amount") == "api_error"
        assert classify_error("separate error occurred") == "api_error"

    def test_classify_400_422_validation_error(self):
        assert classify_error("400 Bad Request") == "validation_error"
        assert classify_error("422 Unprocessable Entity") == "validation_error"
        assert classify_error("Validation failed") == "validation_error"
        assert classify_error("Invalid request format") == "validation_error"

    def test_classify_404_not_found(self):
        assert classify_error("404 Not Found") == "not_found"
        assert classify_error("Resource not found") == "not_found"

    def test_classify_5xx_server_error(self):
        assert classify_error("500 Internal Server Error") == "server_error"
        assert classify_error("502 Bad Gateway") == "server_error"
        assert classify_error("503 Service Unavailable") == "server_error"
        assert classify_error("API Error: 500") == "server_error"
        assert classify_error("Error 504: Gateway Timeout") == "server_error"

    def test_classify_unknown_api_error(self):
        assert classify_error("Unknown error occurred") == "api_error"
        assert classify_error("Connection refused") == "api_error"


# =============================================================================
# GET PRODUCTS
# =============================================================================


class TestGetProducts:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx(
            {
                "products": [
                    {"product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d", "display_name": "uberX", "capacity": 4},
                    {"product_id": "d4abaae7-f4d6-4152-91cc-77523e8165a4", "display_name": "BLACK", "capacity": 4},
                ]
            }
        )
        result = await uber_integration.execute_action(
            "get_products", {"latitude": 37.7752315, "longitude": -122.418075}, ctx
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert len(data["products"]) == 2
        assert data["products"][0]["display_name"] == "uberX"
        assert "error" not in data

    @pytest.mark.asyncio
    async def test_api_error(self):
        ctx = make_ctx_error(Exception("API Error: 500"))
        result = await uber_integration.execute_action(
            "get_products", {"latitude": 37.7752315, "longitude": -122.418075}, ctx
        )
        assert_action_error(result, "server_error")

    @pytest.mark.asyncio
    async def test_invalid_latitude(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_products", {"latitude": 999, "longitude": -122.418075}, ctx)
        assert_action_error(result, "latitude must be between")
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_coordinates(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_products", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_error(self):
        ctx = make_ctx_error(Exception("401 Unauthorized"))
        result = await uber_integration.execute_action(
            "get_products", {"latitude": 37.7752315, "longitude": -122.418075}, ctx
        )
        assert_action_error(result, "auth_error")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        ctx = make_ctx_error(Exception("429 Too Many Requests"))
        result = await uber_integration.execute_action(
            "get_products", {"latitude": 37.7752315, "longitude": -122.418075}, ctx
        )
        assert_action_error(result, "rate_limited")


# =============================================================================
# GET PRICE ESTIMATE
# =============================================================================


class TestGetPriceEstimate:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx(
            {
                "prices": [
                    {
                        "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
                        "display_name": "uberX",
                        "estimate": "$13-17",
                        "low_estimate": 13,
                        "high_estimate": 17,
                        "currency_code": "USD",
                    }
                ]
            }
        )
        result = await uber_integration.execute_action(
            "get_price_estimate",
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["prices"]) == 1
        assert result.result.data["prices"][0]["estimate"] == "$13-17"

    @pytest.mark.asyncio
    async def test_seat_count_clamped_min(self):
        # 0 passes the input schema (no minimum) and is clamped to 1 by the action.
        ctx = make_ctx({"prices": []})
        await uber_integration.execute_action(
            "get_price_estimate",
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "seat_count": 0,
            },
            ctx,
        )
        assert fetch_params(ctx)["seat_count"] == 1

    @pytest.mark.asyncio
    async def test_invalid_start_coordinates(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "get_price_estimate",
            {
                "start_latitude": 999,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert_action_error(result, "start_latitude")

    @pytest.mark.asyncio
    async def test_invalid_end_coordinates(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "get_price_estimate",
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": 999,
            },
            ctx,
        )
        assert_action_error(result, "end_longitude")


# =============================================================================
# GET TIME ESTIMATE
# =============================================================================


class TestGetTimeEstimate:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx(
            {
                "times": [
                    {"product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d", "display_name": "uberX", "estimate": 300}
                ]
            }
        )
        result = await uber_integration.execute_action(
            "get_time_estimate", {"start_latitude": 37.7752315, "start_longitude": -122.418075}, ctx
        )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["times"]) == 1

    @pytest.mark.asyncio
    async def test_with_product_filter(self):
        ctx = make_ctx({"times": []})
        await uber_integration.execute_action(
            "get_time_estimate",
            {"start_latitude": 37.7752315, "start_longitude": -122.418075, "product_id": "product_123"},
            ctx,
        )
        assert fetch_params(ctx)["product_id"] == "product_123"

    @pytest.mark.asyncio
    async def test_empty_product_id_ignored(self):
        ctx = make_ctx({"times": []})
        await uber_integration.execute_action(
            "get_time_estimate",
            {"start_latitude": 37.7752315, "start_longitude": -122.418075, "product_id": "   "},
            ctx,
        )
        assert "product_id" not in fetch_params(ctx)

    @pytest.mark.asyncio
    async def test_product_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "get_time_estimate",
            {"start_latitude": 37.7752315, "start_longitude": -122.418075, "product_id": "../products"},
            ctx,
        )
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# GET RIDE ESTIMATE
# =============================================================================


class TestGetRideEstimate:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"fare": {"fare_id": "fare_123", "value": 15.50}})
        result = await uber_integration.execute_action(
            "get_ride_estimate",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["estimate"]["fare"]["fare_id"] == "fare_123"

    @pytest.mark.asyncio
    async def test_missing_product_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "get_ride_estimate",
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_post_method(self):
        ctx = make_ctx({})
        await uber_integration.execute_action(
            "get_ride_estimate",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert ctx.fetch.call_args.kwargs["method"] == "POST"
        assert "json" in ctx.fetch.call_args.kwargs

    @pytest.mark.asyncio
    async def test_product_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "get_ride_estimate",
            {
                "product_id": "../requests",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# REQUEST RIDE
# =============================================================================


class TestRequestRide:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"request_id": "b5512127-a134-4bf4-b1ba-fe9f48f56d9d", "status": "processing", "eta": 5})
        result = await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["request_id"] == "b5512127-a134-4bf4-b1ba-fe9f48f56d9d"
        assert result.result.data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_with_optional_fields(self):
        ctx = make_ctx({"request_id": "req_123", "status": "processing"})
        await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "fare_id": "fare_123",
                "start_address": "123 Main St",
                "payment_method_id": "pm_123",
            },
            ctx,
        )
        body = fetch_body(ctx)
        assert body["fare_id"] == "fare_123"
        assert body["start_address"] == "123 Main St"
        assert body["payment_method_id"] == "pm_123"

    @pytest.mark.asyncio
    async def test_empty_optional_fields_ignored(self):
        ctx = make_ctx({"request_id": "req_123", "status": "processing"})
        await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "fare_id": "",
                "start_address": "   ",
            },
            ctx,
        )
        body = fetch_body(ctx)
        assert "fare_id" not in body
        assert "start_address" not in body

    @pytest.mark.asyncio
    async def test_missing_product_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "request_ride",
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_product_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": "../history",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_response_handling(self):
        ctx = make_ctx({"request_id": "req_123", "status": "processing"})
        result = await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["driver"] is None
        assert result.result.data["vehicle"] is None


# =============================================================================
# GET RIDE STATUS
# =============================================================================


class TestGetRideStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx(
            {
                "request_id": "req_123",
                "status": "accepted",
                "driver": {"name": "John"},
                "vehicle": {"make": "Toyota"},
            }
        )
        result = await uber_integration.execute_action("get_ride_status", {"request_id": "req_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["ride"]["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_missing_request_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_ride_status", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_request_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_ride_status", {"request_id": "   "}, ctx)
        assert_action_error(result, "non-empty string")
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found_error(self):
        ctx = make_ctx_error(Exception("404 Not Found"))
        result = await uber_integration.execute_action("get_ride_status", {"request_id": "invalid_id"}, ctx)
        assert_action_error(result, "not_found")

    @pytest.mark.asyncio
    async def test_request_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_ride_status", {"request_id": "../history"}, ctx)
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# GET RIDE MAP
# =============================================================================


class TestGetRideMap:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"href": "https://trip.uber.com/abc123"})
        result = await uber_integration.execute_action("get_ride_map", {"request_id": "req_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["href"] == "https://trip.uber.com/abc123"

    @pytest.mark.asyncio
    async def test_missing_href_returns_null(self):
        # An empty 200 body yields href=None — output schema permits null.
        ctx = make_ctx({})
        result = await uber_integration.execute_action("get_ride_map", {"request_id": "req_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["href"] is None

    @pytest.mark.asyncio
    async def test_request_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_ride_map", {"request_id": "../history"}, ctx)
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# CANCEL RIDE
# =============================================================================


class TestCancelRide:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({})
        result = await uber_integration.execute_action("cancel_ride", {"request_id": "req_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self):
        ctx = make_ctx({})
        await uber_integration.execute_action("cancel_ride", {"request_id": "req_123"}, ctx)
        assert ctx.fetch.call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_missing_request_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("cancel_ride", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("cancel_ride", {"request_id": "../history"}, ctx)
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# GET RIDE RECEIPT
# =============================================================================


class TestGetRideReceipt:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"total_charged": 15.50, "currency_code": "USD"})
        result = await uber_integration.execute_action("get_ride_receipt", {"request_id": "req_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["receipt"]["total_charged"] == 15.50

    @pytest.mark.asyncio
    async def test_request_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("get_ride_receipt", {"request_id": "../history"}, ctx)
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


# =============================================================================
# GET USER PROFILE
# =============================================================================


class TestGetUserProfile:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"first_name": "John", "email": "john@example.com"})
        result = await uber_integration.execute_action("get_user_profile", {}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["user"]["first_name"] == "John"


# =============================================================================
# GET RIDE HISTORY
# =============================================================================


class TestGetRideHistory:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"history": [{"request_id": "ride_1"}, {"request_id": "ride_2"}], "count": 25})
        result = await uber_integration.execute_action("get_ride_history", {}, ctx)
        assert result.type == ResultType.ACTION
        assert len(result.result.data["history"]) == 2
        assert result.result.data["count"] == 25

    @pytest.mark.asyncio
    async def test_default_limit(self):
        ctx = make_ctx({"history": [], "count": 0})
        await uber_integration.execute_action("get_ride_history", {}, ctx)
        assert fetch_params(ctx)["limit"] == 10

    @pytest.mark.asyncio
    async def test_limit_forwarded(self):
        ctx = make_ctx({"history": [], "count": 0})
        await uber_integration.execute_action("get_ride_history", {"limit": 50}, ctx)
        assert fetch_params(ctx)["limit"] == 50

    @pytest.mark.asyncio
    async def test_negative_offset_normalized(self):
        ctx = make_ctx({"history": [], "count": 0})
        await uber_integration.execute_action("get_ride_history", {"limit": 10, "offset": -5}, ctx)
        assert "offset" not in fetch_params(ctx)

    @pytest.mark.asyncio
    async def test_valid_offset_included(self):
        ctx = make_ctx({"history": [], "count": 0})
        await uber_integration.execute_action("get_ride_history", {"limit": 10, "offset": 20}, ctx)
        assert fetch_params(ctx)["offset"] == 20


# =============================================================================
# GET PAYMENT METHODS
# =============================================================================


class TestGetPaymentMethods:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"payment_methods": [{"payment_method_id": "pm_123"}], "last_used": "pm_123"})
        result = await uber_integration.execute_action("get_payment_methods", {}, ctx)
        assert result.type == ResultType.ACTION
        assert len(result.result.data["payment_methods"]) == 1
        assert result.result.data["last_used"] == "pm_123"

    @pytest.mark.asyncio
    async def test_empty_response(self):
        ctx = make_ctx({})
        result = await uber_integration.execute_action("get_payment_methods", {}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["payment_methods"] == []
        assert result.result.data["last_used"] is None


# =============================================================================
# PARTNER LOYALTY (v1 API)
# =============================================================================


class TestLinkLoyaltyAccount:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"status": "linked"})
        result = await uber_integration.execute_action(
            "link_loyalty_account", {"partner_id": "partner_123", "member_id": "member_456"}, ctx
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["linked"] is True
        assert result.result.data["response"] == {"status": "linked"}

    @pytest.mark.asyncio
    async def test_optional_fields_forwarded(self):
        ctx = make_ctx({})
        await uber_integration.execute_action(
            "link_loyalty_account",
            {
                "partner_id": "partner_123",
                "member_id": "member_456",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
            },
            ctx,
        )
        body = fetch_body(ctx)
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        assert body["email"] == "jane@example.com"

    @pytest.mark.asyncio
    async def test_missing_partner_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("link_loyalty_account", {"member_id": "member_456"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_partner_id_path_traversal_blocked(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action(
            "link_loyalty_account", {"partner_id": "../link-account", "member_id": "member_456"}, ctx
        )
        assert_action_error(result, "invalid characters")
        ctx.fetch.assert_not_called()


class TestUnlinkLoyaltyAccount:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"status": "unlinked"})
        result = await uber_integration.execute_action("unlink_loyalty_account", {"partner_id": "partner_123"}, ctx)
        assert result.type == ResultType.ACTION
        assert result.result.data["unlinked"] is True

    @pytest.mark.asyncio
    async def test_missing_partner_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("unlink_loyalty_account", {}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()


class TestSubmitFlightBookingData:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = make_ctx({"status": "received"})
        result = await uber_integration.execute_action(
            "submit_flight_booking_data", {"partner_id": "partner_123", "booking_id": "booking_789"}, ctx
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["submitted"] is True

    @pytest.mark.asyncio
    async def test_optional_flight_fields_forwarded(self):
        ctx = make_ctx({})
        await uber_integration.execute_action(
            "submit_flight_booking_data",
            {
                "partner_id": "partner_123",
                "booking_id": "booking_789",
                "flight_number": "UA123",
                "departure_airport": "SFO",
                "arrival_airport": "JFK",
            },
            ctx,
        )
        body = fetch_body(ctx)
        assert body["flight_number"] == "UA123"
        assert body["departure_airport"] == "SFO"
        assert body["arrival_airport"] == "JFK"

    @pytest.mark.asyncio
    async def test_missing_booking_id(self):
        ctx = make_ctx()
        result = await uber_integration.execute_action("submit_flight_booking_data", {"partner_id": "partner_123"}, ctx)
        assert result.type == ResultType.VALIDATION_ERROR
        ctx.fetch.assert_not_called()
