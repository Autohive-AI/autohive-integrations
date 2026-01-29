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


uber = Integration.load()

UBER_API_BASE_URL = "https://api.uber.com"
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
                })
                
            except Exception as e:
                error_str = str(e)
                error_type = classify_error(error_str)
                
                return ActionResult(data={
                    "result": False,
                    "error": f"Uber API error in {action_name}: {error_str}",
                    "error_type": error_type
                })
        
        return wrapper
    return decorator


def classify_error(error_str: str) -> str:
    """Classify error string into error type."""
    error_lower = error_str.lower()
    
    if "401" in error_str or "unauthorized" in error_lower:
        return "auth_error"
    elif "429" in error_str or "rate" in error_lower:
        return "rate_limited"
    elif "400" in error_str or "422" in error_str or "validation" in error_lower:
        return "validation_error"
    elif "404" in error_str or "not found" in error_lower:
        return "not_found"
    elif error_str[:1] == "5":
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


def validate_seat_count(seat_count: Optional[int]) -> int:
    """Validate and normalize seat count for POOL products."""
    if seat_count is None or not isinstance(seat_count, int):
        return 2
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
    
    Raises UberAPIError on failure.
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
        coord_error = validate_coordinates(
            inputs.get("latitude"),
            inputs.get("longitude")
        )
        if coord_error:
            raise UberAPIError(coord_error, "validation_error")

        params = {
            "latitude": inputs["latitude"],
            "longitude": inputs["longitude"]
        }

        response = await uber_fetch(context, "products", params=params)

        return ActionResult(data={
            "products": response.get("products", []),
            "result": True
        })


# =============================================================================
# ESTIMATE ACTIONS
# =============================================================================

@uber.action("get_price_estimate")
class GetPriceEstimateAction(ActionHandler):
    """Get price estimates for a trip between two locations."""

    @handle_uber_errors("get_price_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        start_error = validate_coordinates(
            inputs.get("start_latitude"),
            inputs.get("start_longitude"),
            "start_"
        )
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(
            inputs.get("end_latitude"),
            inputs.get("end_longitude"),
            "end_"
        )
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        params = {
            "start_latitude": inputs["start_latitude"],
            "start_longitude": inputs["start_longitude"],
            "end_latitude": inputs["end_latitude"],
            "end_longitude": inputs["end_longitude"]
        }

        if inputs.get("seat_count") is not None:
            params["seat_count"] = validate_seat_count(inputs["seat_count"])

        response = await uber_fetch(context, "estimates/price", params=params)

        return ActionResult(data={
            "prices": response.get("prices", []),
            "result": True
        })


@uber.action("get_time_estimate")
class GetTimeEstimateAction(ActionHandler):
    """Get ETA estimates for available products at a location."""

    @handle_uber_errors("get_time_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        coord_error = validate_coordinates(
            inputs.get("start_latitude"),
            inputs.get("start_longitude"),
            "start_"
        )
        if coord_error:
            raise UberAPIError(coord_error, "validation_error")

        params = {
            "start_latitude": inputs["start_latitude"],
            "start_longitude": inputs["start_longitude"]
        }

        product_id = inputs.get("product_id")
        if product_id and isinstance(product_id, str) and product_id.strip():
            params["product_id"] = product_id.strip()

        response = await uber_fetch(context, "estimates/time", params=params)

        return ActionResult(data={
            "times": response.get("times", []),
            "result": True
        })


@uber.action("get_ride_estimate")
class GetRideEstimateAction(ActionHandler):
    """Get a detailed fare estimate for a specific ride request."""

    @handle_uber_errors("get_ride_estimate")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        product_error = validate_required_string(inputs.get("product_id"), "product_id")
        if product_error:
            raise UberAPIError(product_error, "validation_error")

        start_error = validate_coordinates(
            inputs.get("start_latitude"),
            inputs.get("start_longitude"),
            "start_"
        )
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(
            inputs.get("end_latitude"),
            inputs.get("end_longitude"),
            "end_"
        )
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        body = {
            "product_id": inputs["product_id"].strip(),
            "start_latitude": inputs["start_latitude"],
            "start_longitude": inputs["start_longitude"],
            "end_latitude": inputs["end_latitude"],
            "end_longitude": inputs["end_longitude"]
        }

        if inputs.get("seat_count") is not None:
            body["seat_count"] = validate_seat_count(inputs["seat_count"])

        response = await uber_fetch(
            context, "requests/estimate", method="POST", json_body=body
        )

        return ActionResult(data={
            "estimate": response,
            "result": True
        })


# =============================================================================
# RIDE REQUEST ACTIONS
# =============================================================================

@uber.action("request_ride")
class RequestRideAction(ActionHandler):
    """Request an Uber ride on behalf of the user."""

    @handle_uber_errors("request_ride")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        product_error = validate_required_string(inputs.get("product_id"), "product_id")
        if product_error:
            raise UberAPIError(product_error, "validation_error")

        start_error = validate_coordinates(
            inputs.get("start_latitude"),
            inputs.get("start_longitude"),
            "start_"
        )
        if start_error:
            raise UberAPIError(start_error, "validation_error")

        end_error = validate_coordinates(
            inputs.get("end_latitude"),
            inputs.get("end_longitude"),
            "end_"
        )
        if end_error:
            raise UberAPIError(end_error, "validation_error")

        body: Dict[str, Any] = {
            "product_id": inputs["product_id"].strip(),
            "start_latitude": inputs["start_latitude"],
            "start_longitude": inputs["start_longitude"],
            "end_latitude": inputs["end_latitude"],
            "end_longitude": inputs["end_longitude"]
        }

        optional_string_fields = [
            "start_address", "start_nickname", "end_address", "end_nickname",
            "fare_id", "surge_confirmation_id", "payment_method_id"
        ]
        for field in optional_string_fields:
            value = inputs.get(field)
            if value and isinstance(value, str) and value.strip():
                body[field] = value.strip()

        if inputs.get("seat_count") is not None:
            body["seat_count"] = validate_seat_count(inputs["seat_count"])

        response = await uber_fetch(context, "requests", method="POST", json_body=body)

        return ActionResult(data={
            "request_id": response.get("request_id"),
            "status": response.get("status"),
            "eta": response.get("eta"),
            "surge_multiplier": response.get("surge_multiplier"),
            "driver": response.get("driver"),
            "vehicle": response.get("vehicle"),
            "result": True
        })


@uber.action("get_ride_status")
class GetRideStatusAction(ActionHandler):
    """Get the current status and details of an active ride request."""

    @handle_uber_errors("get_ride_status")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_required_string(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}")

        return ActionResult(data={
            "ride": response,
            "result": True
        })


@uber.action("get_ride_map")
class GetRideMapAction(ActionHandler):
    """Get a map URL showing the real-time location of an active ride."""

    @handle_uber_errors("get_ride_map")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_required_string(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}/map")

        return ActionResult(data={
            "href": response.get("href"),
            "result": True
        })


@uber.action("cancel_ride")
class CancelRideAction(ActionHandler):
    """Cancel an active ride request."""

    @handle_uber_errors("cancel_ride")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_required_string(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        await uber_fetch(context, f"requests/{request_id}", method="DELETE")

        return ActionResult(data={"result": True})


@uber.action("get_ride_receipt")
class GetRideReceiptAction(ActionHandler):
    """Get the receipt for a completed ride."""

    @handle_uber_errors("get_ride_receipt")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        request_id_error = validate_required_string(inputs.get("request_id"), "request_id")
        if request_id_error:
            raise UberAPIError(request_id_error, "validation_error")

        request_id = inputs["request_id"].strip()
        response = await uber_fetch(context, f"requests/{request_id}/receipt")

        return ActionResult(data={
            "receipt": response,
            "result": True
        })


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
        })


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
        })


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
        })
