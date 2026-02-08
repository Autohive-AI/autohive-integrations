"""
Humanitix integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ActionResult, ExecutionContext
from typing import Any, Dict
from urllib.parse import urlencode

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


def build_url(path: str, params: Dict[str, Any] | None = None) -> str:
    url = f"{HUMANITIX_API_BASE}/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


async def fetch_single_resource(context: ExecutionContext, path: str, params: Dict[str, Any], result_key: str) -> ActionResult:
    url = build_url(path, params or None)
    response = await context.fetch(url, method="GET", headers=get_api_headers(context))
    if error := build_error_result(response): return error
    return ActionResult(data={"result": True, result_key: response})


def build_paginated_result(response, key: str, page: int, page_size: int | None = None) -> ActionResult:
    items = response.get(key, []) if isinstance(response, dict) else []
    is_dict = isinstance(response, dict)
    return ActionResult(data={
        "result": True,
        key: items,
        "total": response.get("total", len(items)) if is_dict else len(items),
        "page": response.get("page", page) if is_dict else page,
        "pageSize": response.get("pageSize", page_size or 100) if is_dict else (page_size or 100),
    })


def build_error_result(response) -> ActionResult | None:
    if not isinstance(response, dict) or "statusCode" not in response:
        return None
    return ActionResult(data={
        "result": False,
        "statusCode": response.get("statusCode"),
        "error": response.get("error", ""),
        "message": response.get("message", "")
    })

