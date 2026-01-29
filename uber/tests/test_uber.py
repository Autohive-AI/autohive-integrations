import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from context import (
    GetProductsAction,
    GetPriceEstimateAction,
    GetTimeEstimateAction,
    GetRideEstimateAction,
    RequestRideAction,
    GetRideStatusAction,
    GetRideMapAction,
    CancelRideAction,
    GetRideReceiptAction,
    GetUserProfileAction,
    GetRideHistoryAction,
    GetPaymentMethodsAction,
    validate_coordinates,
    validate_seat_count,
    validate_limit,
    validate_offset,
    validate_required_string
)


@pytest.fixture
def mock_context():
    """Create a mock ExecutionContext with async fetch method."""
    context = MagicMock()
    context.fetch = AsyncMock(return_value={})
    return context


# ---- Validation Helper Tests ----

class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_coordinates_valid(self):
        """Test valid coordinate validation."""
        assert validate_coordinates(37.7749, -122.4194) is None
        assert validate_coordinates(0, 0) is None
        assert validate_coordinates(-90, -180) is None
        assert validate_coordinates(90, 180) is None

    def test_validate_coordinates_invalid_range(self):
        """Test coordinate validation with out-of-range values."""
        error = validate_coordinates(91, -122.4194)
        assert "latitude must be between" in error

        error = validate_coordinates(37.7749, 181)
        assert "longitude must be between" in error

        error = validate_coordinates(-91, 0)
        assert "latitude must be between" in error

    def test_validate_coordinates_missing(self):
        """Test coordinate validation with missing values."""
        error = validate_coordinates(None, -122.4194)
        assert "required" in error

        error = validate_coordinates(37.7749, None)
        assert "required" in error

    def test_validate_coordinates_invalid_type(self):
        """Test coordinate validation with invalid types."""
        error = validate_coordinates("invalid", -122.4194)
        assert "must be numbers" in error

    def test_validate_coordinates_with_prefix(self):
        """Test coordinate validation with field prefix."""
        error = validate_coordinates(None, None, "start_")
        assert "start_latitude" in error

    def test_validate_seat_count(self):
        """Test seat count validation and normalization."""
        assert validate_seat_count(1) == 1
        assert validate_seat_count(2) == 2
        assert validate_seat_count(0) == 1
        assert validate_seat_count(3) == 2
        assert validate_seat_count(None) == 2
        assert validate_seat_count("invalid") == 2

    def test_validate_limit(self):
        """Test limit validation and normalization."""
        assert validate_limit(10) == 10
        assert validate_limit(50) == 50
        assert validate_limit(100) == 50
        assert validate_limit(0) == 1
        assert validate_limit(-1) == 1
        assert validate_limit(None) == 10
        assert validate_limit("invalid") == 10

    def test_validate_limit_custom_max(self):
        """Test limit validation with custom max."""
        assert validate_limit(100, max_limit=100) == 100
        assert validate_limit(200, max_limit=100) == 100

    def test_validate_offset(self):
        """Test offset validation and normalization."""
        assert validate_offset(0) == 0
        assert validate_offset(10) == 10
        assert validate_offset(-1) == 0
        assert validate_offset(None) == 0
        assert validate_offset("invalid") == 0

    def test_validate_required_string_valid(self):
        """Test required string validation with valid input."""
        assert validate_required_string("abc123", "field") is None
        assert validate_required_string("  valid  ", "field") is None

    def test_validate_required_string_invalid(self):
        """Test required string validation with invalid input."""
        error = validate_required_string(None, "request_id")
        assert "request_id is required" in error

        error = validate_required_string("", "request_id")
        assert "non-empty string" in error

        error = validate_required_string("   ", "request_id")
        assert "non-empty string" in error

        error = validate_required_string(123, "request_id")
        assert "non-empty string" in error


# ---- Product Tests ----

class TestGetProducts:
    """Tests for get_products action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful product retrieval."""
        mock_context.fetch.return_value = {
            "products": [
                {
                    "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
                    "display_name": "uberX",
                    "capacity": 4
                },
                {
                    "product_id": "d4abaae7-f4d6-4152-91cc-77523e8165a4",
                    "display_name": "BLACK",
                    "capacity": 4
                }
            ]
        }

        action = GetProductsAction()
        result = await action.execute(
            {"latitude": 37.7752315, "longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is True
        assert len(result.data["products"]) == 2
        assert result.data["products"][0]["display_name"] == "uberX"
        assert "error" not in result.data

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        """Test product retrieval with API error."""
        mock_context.fetch.side_effect = Exception("API Error: 500")

        action = GetProductsAction()
        result = await action.execute(
            {"latitude": 37.7752315, "longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is False
        assert "error" in result.data
        assert "error_type" in result.data

    @pytest.mark.asyncio
    async def test_invalid_latitude(self, mock_context):
        """Test with invalid latitude."""
        action = GetProductsAction()
        result = await action.execute(
            {"latitude": 999, "longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is False
        assert "latitude must be between" in result.data["error"]
        assert result.data["error_type"] == "validation_error"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_coordinates(self, mock_context):
        """Test with missing coordinates."""
        action = GetProductsAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is False
        assert "required" in result.data["error"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context):
        """Test authentication error detection."""
        mock_context.fetch.side_effect = Exception("401 Unauthorized")

        action = GetProductsAction()
        result = await action.execute(
            {"latitude": 37.7752315, "longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is False
        assert result.data["error_type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_context):
        """Test rate limit error detection."""
        mock_context.fetch.side_effect = Exception("429 Too Many Requests")

        action = GetProductsAction()
        result = await action.execute(
            {"latitude": 37.7752315, "longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is False
        assert result.data["error_type"] == "rate_limited"


# ---- Price Estimate Tests ----

class TestGetPriceEstimate:
    """Tests for get_price_estimate action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful price estimate."""
        mock_context.fetch.return_value = {
            "prices": [
                {
                    "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
                    "display_name": "uberX",
                    "estimate": "$13-17",
                    "low_estimate": 13,
                    "high_estimate": 17,
                    "currency_code": "USD"
                }
            ]
        }

        action = GetPriceEstimateAction()
        result = await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is True
        assert len(result.data["prices"]) == 1
        assert result.data["prices"][0]["estimate"] == "$13-17"

    @pytest.mark.asyncio
    async def test_with_seat_count_normalized(self, mock_context):
        """Test seat count is normalized to valid range."""
        mock_context.fetch.return_value = {"prices": []}

        action = GetPriceEstimateAction()
        await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "seat_count": 5
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args[1]["params"]["seat_count"] == 2

    @pytest.mark.asyncio
    async def test_invalid_start_coordinates(self, mock_context):
        """Test with invalid start coordinates."""
        action = GetPriceEstimateAction()
        result = await action.execute(
            {
                "start_latitude": 999,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is False
        assert "start_latitude" in result.data["error"]

    @pytest.mark.asyncio
    async def test_invalid_end_coordinates(self, mock_context):
        """Test with invalid end coordinates."""
        action = GetPriceEstimateAction()
        result = await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": 999
            },
            mock_context
        )

        assert result.data["result"] is False
        assert "end_longitude" in result.data["error"]


# ---- Time Estimate Tests ----

class TestGetTimeEstimate:
    """Tests for get_time_estimate action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful time estimate."""
        mock_context.fetch.return_value = {
            "times": [
                {
                    "product_id": "a1111c8c-c720-46c3-8534-2fcdd730040d",
                    "display_name": "uberX",
                    "estimate": 300
                }
            ]
        }

        action = GetTimeEstimateAction()
        result = await action.execute(
            {"start_latitude": 37.7752315, "start_longitude": -122.418075},
            mock_context
        )

        assert result.data["result"] is True
        assert len(result.data["times"]) == 1

    @pytest.mark.asyncio
    async def test_with_product_filter(self, mock_context):
        """Test filtering by product ID."""
        mock_context.fetch.return_value = {"times": []}

        action = GetTimeEstimateAction()
        await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "product_id": "product_123"
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args[1]["params"]["product_id"] == "product_123"

    @pytest.mark.asyncio
    async def test_empty_product_id_ignored(self, mock_context):
        """Test that empty product_id is not passed."""
        mock_context.fetch.return_value = {"times": []}

        action = GetTimeEstimateAction()
        await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "product_id": "   "
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        assert "product_id" not in call_args[1]["params"]


# ---- Ride Estimate Tests ----

class TestGetRideEstimate:
    """Tests for get_ride_estimate action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful ride estimate."""
        mock_context.fetch.return_value = {
            "fare": {"fare_id": "fare_123", "value": 15.50}
        }

        action = GetRideEstimateAction()
        result = await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is True
        assert result.data["estimate"]["fare"]["fare_id"] == "fare_123"

    @pytest.mark.asyncio
    async def test_missing_product_id(self, mock_context):
        """Test with missing product_id."""
        action = GetRideEstimateAction()
        result = await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is False
        assert "product_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_uses_post_method(self, mock_context):
        """Test that POST method is used."""
        mock_context.fetch.return_value = {}

        action = GetRideEstimateAction()
        await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        assert call_args[1]["method"] == "POST"
        assert "json" in call_args[1]


# ---- Request Ride Tests ----

class TestRequestRide:
    """Tests for request_ride action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful ride request."""
        mock_context.fetch.return_value = {
            "request_id": "b5512127-a134-4bf4-b1ba-fe9f48f56d9d",
            "status": "processing",
            "eta": 5
        }

        action = RequestRideAction()
        result = await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is True
        assert result.data["request_id"] == "b5512127-a134-4bf4-b1ba-fe9f48f56d9d"
        assert result.data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_with_optional_fields(self, mock_context):
        """Test ride request with optional fields."""
        mock_context.fetch.return_value = {"request_id": "req_123", "status": "processing"}

        action = RequestRideAction()
        await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "fare_id": "fare_123",
                "start_address": "123 Main St",
                "payment_method_id": "pm_123"
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        body = call_args[1]["json"]
        assert body["fare_id"] == "fare_123"
        assert body["start_address"] == "123 Main St"
        assert body["payment_method_id"] == "pm_123"

    @pytest.mark.asyncio
    async def test_empty_optional_fields_ignored(self, mock_context):
        """Test that empty optional fields are not sent."""
        mock_context.fetch.return_value = {"request_id": "req_123", "status": "processing"}

        action = RequestRideAction()
        await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075,
                "fare_id": "",
                "start_address": "   "
            },
            mock_context
        )

        call_args = mock_context.fetch.call_args
        body = call_args[1]["json"]
        assert "fare_id" not in body
        assert "start_address" not in body

    @pytest.mark.asyncio
    async def test_missing_product_id(self, mock_context):
        """Test with missing product_id."""
        action = RequestRideAction()
        result = await action.execute(
            {
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is False
        assert "error" in result.data
        assert result.data["error_type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_partial_response_handling(self, mock_context):
        """Test handling of response without driver/vehicle (initial state)."""
        mock_context.fetch.return_value = {
            "request_id": "req_123",
            "status": "processing"
        }

        action = RequestRideAction()
        result = await action.execute(
            {
                "product_id": "product_123",
                "start_latitude": 37.7752315,
                "start_longitude": -122.418075,
                "end_latitude": 37.7752415,
                "end_longitude": -122.518075
            },
            mock_context
        )

        assert result.data["result"] is True
        assert result.data["driver"] is None
        assert result.data["vehicle"] is None


# ---- Ride Status Tests ----

class TestGetRideStatus:
    """Tests for get_ride_status action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful ride status retrieval."""
        mock_context.fetch.return_value = {
            "request_id": "req_123",
            "status": "accepted",
            "driver": {"name": "John"},
            "vehicle": {"make": "Toyota"}
        }

        action = GetRideStatusAction()
        result = await action.execute(
            {"request_id": "req_123"},
            mock_context
        )

        assert result.data["result"] is True
        assert result.data["ride"]["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_missing_request_id(self, mock_context):
        """Test with missing request_id."""
        action = GetRideStatusAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is False
        assert "request_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_empty_request_id(self, mock_context):
        """Test with empty request_id."""
        action = GetRideStatusAction()
        result = await action.execute({"request_id": "   "}, mock_context)

        assert result.data["result"] is False
        assert "non-empty string" in result.data["error"]

    @pytest.mark.asyncio
    async def test_not_found_error(self, mock_context):
        """Test 404 error detection."""
        mock_context.fetch.side_effect = Exception("404 Not Found")

        action = GetRideStatusAction()
        result = await action.execute({"request_id": "invalid_id"}, mock_context)

        assert result.data["result"] is False
        assert result.data["error_type"] == "not_found"


# ---- Cancel Ride Tests ----

class TestCancelRide:
    """Tests for cancel_ride action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful ride cancellation."""
        mock_context.fetch.return_value = {}

        action = CancelRideAction()
        result = await action.execute({"request_id": "req_123"}, mock_context)

        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_uses_delete_method(self, mock_context):
        """Test that DELETE method is used."""
        mock_context.fetch.return_value = {}

        action = CancelRideAction()
        await action.execute({"request_id": "req_123"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args[1]["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_missing_request_id(self, mock_context):
        """Test with missing request_id."""
        action = CancelRideAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is False


# ---- Receipt Tests ----

class TestGetRideReceipt:
    """Tests for get_ride_receipt action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful receipt retrieval."""
        mock_context.fetch.return_value = {
            "total_charged": 15.50,
            "currency_code": "USD"
        }

        action = GetRideReceiptAction()
        result = await action.execute({"request_id": "req_123"}, mock_context)

        assert result.data["result"] is True
        assert result.data["receipt"]["total_charged"] == 15.50


# ---- User Profile Tests ----

class TestGetUserProfile:
    """Tests for get_user_profile action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful user profile retrieval."""
        mock_context.fetch.return_value = {
            "first_name": "John",
            "email": "john@example.com"
        }

        action = GetUserProfileAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is True
        assert result.data["user"]["first_name"] == "John"


# ---- Ride History Tests ----

class TestGetRideHistory:
    """Tests for get_ride_history action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful ride history retrieval."""
        mock_context.fetch.return_value = {
            "history": [{"request_id": "ride_1"}, {"request_id": "ride_2"}],
            "count": 25
        }

        action = GetRideHistoryAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["history"]) == 2
        assert result.data["count"] == 25

    @pytest.mark.asyncio
    async def test_limit_normalized(self, mock_context):
        """Test limit is normalized to max 50."""
        mock_context.fetch.return_value = {"history": [], "count": 0}

        action = GetRideHistoryAction()
        await action.execute({"limit": 100}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args[1]["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_negative_offset_normalized(self, mock_context):
        """Test negative offset is normalized to 0."""
        mock_context.fetch.return_value = {"history": [], "count": 0}

        action = GetRideHistoryAction()
        await action.execute({"limit": 10, "offset": -5}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "offset" not in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_valid_offset_included(self, mock_context):
        """Test valid offset is included in params."""
        mock_context.fetch.return_value = {"history": [], "count": 0}

        action = GetRideHistoryAction()
        await action.execute({"limit": 10, "offset": 20}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args[1]["params"]["offset"] == 20


# ---- Payment Methods Tests ----

class TestGetPaymentMethods:
    """Tests for get_payment_methods action."""

    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        """Test successful payment methods retrieval."""
        mock_context.fetch.return_value = {
            "payment_methods": [{"payment_method_id": "pm_123"}],
            "last_used": "pm_123"
        }

        action = GetPaymentMethodsAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["payment_methods"]) == 1
        assert result.data["last_used"] == "pm_123"

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_context):
        """Test handling of empty payment methods."""
        mock_context.fetch.return_value = {}

        action = GetPaymentMethodsAction()
        result = await action.execute({}, mock_context)

        assert result.data["result"] is True
        assert result.data["payment_methods"] == []
        assert result.data["last_used"] is None
