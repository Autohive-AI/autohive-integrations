"""
Humanitix integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ActionResult, ExecutionContext
from typing import Dict, Any

# Humanitix API configuration
HUMANITIX_API_BASE = "https://api.humanitix.com/v1"


def get_api_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Get the authentication headers for Humanitix API requests.

    The Humanitix API uses the x-api-key header for authentication.

    Args:
        context: The execution context with authentication credentials

    Returns:
        Dictionary of headers to include in API requests
    """
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")

    return {
        "x-api-key": api_key,
        "Accept": "application/json"
    }


def build_error_result(response) -> ActionResult | None:
    if not isinstance(response, dict) or "statusCode" not in response:
        return None
    return ActionResult(data={
        "result": False,
        "statusCode": response.get("statusCode"),
        "error": response.get("error", ""),
        "message": response.get("message", "")
    })




def _build_tag_response(tag: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a tag object from the Humanitix API into a consistent response format.

    Args:
        tag: Raw tag data from the API

    Returns:
        Normalized tag object with consistent field names
    """
    return {
        "id": tag.get("_id", ""),
        "name": tag.get("name", ""),
        "color": tag.get("color", "")
    }
