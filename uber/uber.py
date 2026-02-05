"""
Uber Ride Requests Integration for Autohive Platform

This module provides comprehensive Uber Riders API integration including:
- Product discovery (UberX, UberXL, Black, etc.)
- Price and time estimates
- Ride requests and tracking
- Receipts and history

API Version: v1.2
Reference: https://developer.uber.com/docs/riders/introduction
"""

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler,
    ActionResult
)
from typing import Dict, Any, Optional, Callable, TypeVar
from functools import wraps
import os
import re


uber = Integration.load()

# Support sandbox environment via environment variable
# Production: https://api.uber.com
# Sandbox: https://sandbox-api.uber.com
UBER_API_BASE_URL = os.getenv("UBER_API_BASE_URL", "https://api.uber.com")
API_VERSION = "v1.2"

T = TypeVar('T')


# =============================================================================
# ERROR HANDLING
# =============================================================================

class UberAPIError(Exception):
    """Custom exception for Uber API errors."""
    def __init__(self, message: str, error_type: str = "api_error"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type


def handle_uber_errors(action_name: str):
    """
    Decorator that wraps action execute methods with error handling.
    
    Catches exceptions and returns ActionResult with proper error messages
    and error type classification.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
            try:
                return await func(self, inputs, context)
                
            except UberAPIError as e:
                return ActionResult(data={
                    "result": False,
                    "error": e.message,
                    "error_type": e.error_type
                }, cost_usd=0.0)

            except Exception as e:
                error_str = str(e)
                error_type = classify_error(error_str)

                return ActionResult(data={
                    "result": False,
                    "error": f"Uber API error in {action_name}: {error_str}",
                    "error_type": error_type
                }, cost_usd=0.0)
        
        return wrapper
    return decorator


def classify_error(error_str: str) -> str:
    """Classify error string into error type."""
    error_lower = error_str.lower()

    # Extract HTTP status code if present (e.g., "401", "500 Server Error", "API Error: 429")
    status_match = re.search(r'\b([45]\d{2})\b', error_str)
    status_code = status_match.group(1) if status_match else None

    if status_code == "401" or "unauthorized" in error_lower:
        return "auth_error"
    elif status_code == "429" or "too many requests" in error_lower or "rate limit" in error_lower:
        return "rate_limited"
    elif status_code in ("400", "422") or "validation" in error_lower or "invalid" in error_lower:
        return "validation_error"
    elif status_code == "404" or "not found" in error_lower:
        return "not_found"
    elif status_code and status_code.startswith("5"):
        return "server_error"

    return "api_error"


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_coordinates(
    lat: Optional[float],
    lng: Optional[float],
    field_prefix: str = ""
) -> Optional[str]:
    """Validate latitude and longitude values. Returns error message if invalid."""
    if lat is None or lng is None:
        return f"{field_prefix}latitude and longitude are required"
    
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return f"{field_prefix}latitude and longitude must be numbers"
    
    if lat < -90 or lat > 90:
        return f"{field_prefix}latitude must be between -90 and 90"
    
    if lng < -180 or lng > 180:
        return f"{field_prefix}longitude must be between -180 and 180"
    
    return None


def validate_seat_count(seat_count: Any) -> int:
    """
    Validate and normalize seat count for POOL products.

    Note: Uber POOL only supports 1-2 seats. Values outside this range
    are clamped. For non-POOL products, seat_count is ignored by the API.
    This matches the schema constraint (maximum: 2).

    Raises UberAPIError if seat_count is not None and not an integer.
    """
    if seat_count is None:
        return 2  # Default to 2 seats when not provided

    if not isinstance(seat_count, int):
        raise UberAPIError(
            "seat_count must be an integer (1 or 2)",
            "validation_error"
        )

    return max(1, min(seat_count, 2))


def validate_limit(limit: Optional[int], max_limit: int = 50) -> int:
    """Validate and normalize limit parameter."""
    if limit is None or not isinstance(limit, int):
        return 10
    return max(1, min(limit, max_limit))


def validate_offset(offset: Optional[int]) -> int:
    """Validate and normalize offset parameter."""
    if offset is None or not isinstance(offset, int):
        return 0
    return max(0, offset)


def validate_required_string(value: Any, field_name: str) -> Optional[str]:
    """Validate that a value is a non-empty string. Returns error message if invalid."""
    if value is None:
        return f"{field_name} is required"
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be a non-empty string"
    return None


def validate_id(value: Any, field_name: str) -> Optional[str]:
    """
    Validate that a value is a valid ID.
    Prevents path traversal and parameter injection attacks.
    Returns error message if invalid.
    """
    if value is None:
        return f"{field_name} is required"
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be a non-empty string"

    # Block path traversal and URL metacharacters
    # This prevents injection while allowing most legitimate ID formats
    v = value.strip()
    dangerous_chars = ['/', '\\', '..', '?', '&', '#', '%']
    if any(char in v for char in dangerous_chars):
        return f"{field_name} contains invalid characters"

    return None


# =============================================================================
# API HELPERS
# =============================================================================

def get_common_headers() -> Dict[str, str]:
    """Return common headers for Uber API requests."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en_US"
    }


async def uber_fetch(
    context: ExecutionContext,
    path: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Centralized Uber API request handler.

    Exceptions from context.fetch() bubble up to the caller.
    Use @handle_uber_errors decorator on actions for error classification.
    """
    url = f"{UBER_API_BASE_URL}/{API_VERSION}/{path.lstrip('/')}"
    
    kwargs: Dict[str, Any] = {
        "method": method,
        "headers": get_common_headers(),
    }
    
    if params:
        kwargs["params"] = params
    if json_body:
        kwargs["json"] = json_body
    
    response = await context.fetch(url, **kwargs)
    return response


# =============================================================================
# PRODUCT ACTIONS
# =============================================================================

@uber.action("get_products")
class GetProductsAction(ActionHandler):
    """Get available Uber products at a given location."""

    @handle_uber_errors("get_products")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        lat = inputs.get("latitude")
        lng = inputs.get("longitude")

        coord_error = validate_coordinates(lat, lng)
        if coord_error:
            raise UberAPIError(coord_error, "validation_error")

        params = {
            "latitude": lat,
            "longitude": lng
        }

        response = await uber_fetch(context, "products", params=params)

        return ActionResult(data={
            "products": response.get("products", []),
            "result": True
        }, cost_usd=0.0)


# =============================================================================
# ESTIMATE ACTIONS
# =============================================================================

@uber.action("get_price_estimate")
class GetPriceEstimateAction(ActionHandler):
    """Get price estimates for a trip between two locations."""

    @handle_uber_errors("get_price_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        start_lat = inputs.get("start_latitude")
        start_lng = inputs.get("start_longitude")
        end_lat = inputs.get("end_latitude")
        end_lng = inputs.get("end_longitude")

        start_error = validate_coordinates(start_lat, start_lng, "start_")
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(end_lat, end_lng, "end_")
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        params = {
            "start_latitude": start_lat,
            "start_longitude": start_lng,
            "end_latitude": end_lat,
            "end_longitude": end_lng
        }

        seat_count = inputs.get("seat_count")
        if seat_count is not None:
            params["seat_count"] = validate_seat_count(seat_count)

        response = await uber_fetch(context, "estimates/price", params=params)

        return ActionResult(data={
            "prices": response.get("prices", []),
            "result": True
        }, cost_usd=0.0)


@uber.action("get_time_estimate")
class GetTimeEstimateAction(ActionHandler):
    """Get ETA estimates for available products at a location."""

    @handle_uber_errors("get_time_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        start_lat = inputs.get("start_latitude")
        start_lng = inputs.get("start_longitude")

        coord_error = validate_coordinates(start_lat, start_lng, "start_")
        if coord_error:
            raise UberAPIError(coord_error, "validation_error")

        params = {
            "start_latitude": start_lat,
            "start_longitude": start_lng
        }

        product_id = inputs.get("product_id")
        if product_id and isinstance(product_id, str) and product_id.strip():
            # Validate product_id to prevent path traversal
            product_id_error = validate_id(product_id, "product_id")
            if product_id_error:
                raise UberAPIError(product_id_error, "validation_error")
            params["product_id"] = product_id.strip()

        response = await uber_fetch(context, "estimates/time", params=params)

        return ActionResult(data={
            "times": response.get("times", []),
            "result": True
        }, cost_usd=0.0)


@uber.action("get_ride_estimate")
class GetRideEstimateAction(ActionHandler):
    """Get a detailed fare estimate for a specific ride request."""

    @handle_uber_errors("get_ride_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        product_id = inputs.get("product_id")
        start_lat = inputs.get("start_latitude")
        start_lng = inputs.get("start_longitude")
        end_lat = inputs.get("end_latitude")
        end_lng = inputs.get("end_longitude")

        product_error = validate_id(product_id, "product_id")
        if product_error:
            raise UberAPIError(product_error, "validation_error")

        start_error = validate_coordinates(start_lat, start_lng, "start_")
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(end_lat, end_lng, "end_")
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        body = {
            "product_id": product_id.strip(),
            "start_latitude": start_lat,
            "start_longitude": start_lng,
            "end_latitude": end_lat,
            "end_longitude": end_lng
        }

        seat_count = inputs.get("seat_count")
        if seat_count is not None:
            body["seat_count"] = validate_seat_count(seat_count)

        response = await uber_fetch(
            context, "requests/estimate", method="POST", json_body=body
        )

        return ActionResult(data={
            "estimate": response,
            "result": True
        }, cost_usd=0.0)


# =============================================================================
# RIDE REQUEST ACTIONS
# =============================================================================

@uber.action("request_ride")
class RequestRideAction(ActionHandler):
    """Request an Uber ride on behalf of the user."""

    @handle_uber_errors("request_ride")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        product_id = inputs.get("product_id")
        start_lat = inputs.get("start_latitude")
        start_lng = inputs.get("start_longitude")
        end_lat = inputs.get("end_latitude")
        end_lng = inputs.get("end_longitude")

        product_error = validate_id(product_id, "product_id")
        if product_error:
            raise UberAPIError(product_error, "validation_error")

        start_error = validate_coordinates(start_lat, start_lng, "start_")
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(end_lat, end_lng, "end_")
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        body: Dict[str, Any] = {
            "product_id": product_id.strip(),
            "start_latitude": start_lat,
            "start_longitude": start_lng,
            "end_latitude": end_lat,
            "end_longitude": end_lng
        }

        optional_string_fields = [
            "start_address", "start_nickname", "end_address", "end_nickname",
            "fare_id", "surge_confirmation_id", "payment_method_id"
        ]
        for field in optional_string_fields:
            value = inputs.get(field)
            if value and isinstance(value, str) and value.strip():
                body[field] = value.strip()

        seat_count = inputs.get("seat_count")
        if seat_count is not None:
            body["seat_count"] = validate_seat_count(seat_count)

        response = await uber_fetch(context, "requests", method="POST", json_body=body)

        return ActionResult(data={
            "request_id": response.get("request_id"),
            "status": response.get("status"),
            "eta": response.get("eta"),
            "surge_multiplier": response.get("surge_multiplier"),
            "driver": response.get("driver"),
            "vehicle": response.get("vehicle"),
            "result": True
        }, cost_usd=0.0)


@uber.action("get_ride_status")
class GetRideStatusAction(ActionHandler):
    """Get the current status and details of an active ride request."""

    @handle_uber_errors("get_ride_status")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_id(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}")

        return ActionResult(data={
            "ride": response,
            "result": True
        }, cost_usd=0.0)


@uber.action("get_ride_map")
class GetRideMapAction(ActionHandler):
    """Get a map URL showing the real-time location of an active ride."""

    @handle_uber_errors("get_ride_map")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_id(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}/map")

        return ActionResult(data={
            "href": response.get("href"),
            "result": True
        }, cost_usd=0.0)


@uber.action("cancel_ride")
class CancelRideAction(ActionHandler):
    """Cancel an active ride request."""

    @handle_uber_errors("cancel_ride")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_id(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        await uber_fetch(context, f"requests/{request_id}", method="DELETE")

        return ActionResult(data={"result": True}, cost_usd=0.0)


@uber.action("get_ride_receipt")
class GetRideReceiptAction(ActionHandler):
    """Get the receipt for a completed ride."""

    @handle_uber_errors("get_ride_receipt")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_id(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}/receipt")

        return ActionResult(data={
            "receipt": response,
            "result": True
        }, cost_usd=0.0)


# =============================================================================
# USER ACTIONS
# =============================================================================

@uber.action("get_user_profile")
class GetUserProfileAction(ActionHandler):
    """Get the authenticated user's Uber profile information."""

    @handle_uber_errors("get_user_profile")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        response = await uber_fetch(context, "me")

        return ActionResult(data={
            "user": response,
            "result": True
        }, cost_usd=0.0)


@uber.action("get_ride_history")
class GetRideHistoryAction(ActionHandler):
    """Get the user's ride history."""

    @handle_uber_errors("get_ride_history")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        params: Dict[str, Any] = {
            "limit": validate_limit(inputs.get("limit"), max_limit=50)
        }

        offset = validate_offset(inputs.get("offset"))
        if offset > 0:
            params["offset"] = offset

        response = await uber_fetch(context, "history", params=params)

        return ActionResult(data={
            "history": response.get("history", []),
            "count": response.get("count", 0),
            "result": True
        }, cost_usd=0.0)


@uber.action("get_payment_methods")
class GetPaymentMethodsAction(ActionHandler):
    """Get the user's available payment methods."""

    @handle_uber_errors("get_payment_methods")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        response = await uber_fetch(context, "payment-methods")

        return ActionResult(data={
            "payment_methods": response.get("payment_methods", []),
            "last_used": response.get("last_used"),
            "result": True
        }, cost_usd=0.0)


# =============================================================================
# PARTNER LOYALTY ACTIONS (v1 API)
# =============================================================================

async def uber_fetch_v1(
    context: ExecutionContext,
    path: str,
    method: str = "POST",
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Uber API request handler for v1 Partner Loyalty endpoints.

    Exceptions from context.fetch() bubble up to the caller.
    Use @handle_uber_errors decorator on actions for error classification.
    """
    url = f"{UBER_API_BASE_URL}/v1/{path.lstrip('/')}"

    kwargs: Dict[str, Any] = {
        "method": method,
        "headers": get_common_headers(),
    }

    if json_body:
        kwargs["json"] = json_body

    response = await context.fetch(url, **kwargs)
    return response


@uber.action("link_loyalty_account")
class LinkLoyaltyAccountAction(ActionHandler):
    """Link a partner loyalty account to the user's Uber account."""

    @handle_uber_errors("link_loyalty_account")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        partner_id = inputs.get("partner_id")
        member_id = inputs.get("member_id")

        partner_error = validate_id(partner_id, "partner_id")
        if partner_error:
            raise UberAPIError(partner_error, "validation_error")

        member_error = validate_required_string(member_id, "member_id")
        if member_error:
            raise UberAPIError(member_error, "validation_error")

        body = {
            "partner_id": partner_id.strip(),
            "member_id": member_id.strip()
        }

        # Add optional fields
        if inputs.get("first_name"):
            body["first_name"] = inputs["first_name"].strip()
        if inputs.get("last_name"):
            body["last_name"] = inputs["last_name"].strip()
        if inputs.get("email"):
            body["email"] = inputs["email"].strip()

        response = await uber_fetch_v1(
            context, "partner-loyalty/link-account", method="POST", json_body=body
        )

        return ActionResult(data={
            "linked": True,
            "response": response,
            "result": True
        }, cost_usd=0.0)


@uber.action("unlink_loyalty_account")
class UnlinkLoyaltyAccountAction(ActionHandler):
    """Unlink a partner loyalty account from the user's Uber account."""

    @handle_uber_errors("unlink_loyalty_account")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        partner_id = inputs.get("partner_id")

        partner_error = validate_id(partner_id, "partner_id")
        if partner_error:
            raise UberAPIError(partner_error, "validation_error")

        body = {
            "partner_id": partner_id.strip()
        }

        response = await uber_fetch_v1(
            context, "partner-loyalty/unlink-account", method="POST", json_body=body
        )

        return ActionResult(data={
            "unlinked": True,
            "response": response,
            "result": True
        }, cost_usd=0.0)


@uber.action("submit_flight_booking_data")
class SubmitFlightBookingDataAction(ActionHandler):
    """Submit flight booking data for partner loyalty integration."""

    @handle_uber_errors("submit_flight_booking_data")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        partner_id = inputs.get("partner_id")
        booking_id = inputs.get("booking_id")

        partner_error = validate_id(partner_id, "partner_id")
        if partner_error:
            raise UberAPIError(partner_error, "validation_error")

        booking_error = validate_required_string(booking_id, "booking_id")
        if booking_error:
            raise UberAPIError(booking_error, "validation_error")

        body: Dict[str, Any] = {
            "partner_id": partner_id.strip(),
            "booking_id": booking_id.strip()
        }

        # Add optional flight details
        optional_fields = [
            "flight_number", "departure_airport", "arrival_airport",
            "departure_time", "arrival_time", "passenger_name"
        ]
        for field in optional_fields:
            value = inputs.get(field)
            if value and isinstance(value, str) and value.strip():
                body[field] = value.strip()

        response = await uber_fetch_v1(
            context, "partner-loyalty/flight-booking-data", method="POST", json_body=body
        )

        return ActionResult(data={
            "submitted": True,
            "response": response,
            "result": True
        }, cost_usd=0.0)
