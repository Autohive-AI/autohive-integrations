"""
Humanitix integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ActionResult, ActionError, ExecutionContext
from typing import Any, Dict
from urllib.parse import quote, urlencode

# Humanitix API configuration
HUMANITIX_API_BASE = "https://api.humanitix.com/v1"


def get_api_headers(context: ExecutionContext) -> Dict[str, str]:
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")
    return {"x-api-key": api_key, "Accept": "application/json"}


def build_url(path: str, params: Dict[str, Any] | None = None) -> str:
    safe_path = "/".join(quote(segment, safe="") for segment in path.split("/"))
    url = f"{HUMANITIX_API_BASE}/{safe_path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


async def fetch_single_resource(
    context: ExecutionContext, path: str, params: Dict[str, Any], result_key: str
) -> ActionResult:
    url = build_url(path, params or None)
    response = await context.fetch(url, method="GET", headers=get_api_headers(context))
    if response.status >= 400:
        data = response.data
        message = (
            data.get("message", f"HTTP {response.status}") if isinstance(data, dict) else f"HTTP {response.status}"
        )
        return ActionError(message=message)
    return ActionResult(data={"result": True, result_key: response.data}, cost_usd=0.0)


def build_paginated_result(response, key: str, page: int, page_size: int | None = None) -> ActionResult:
    data = response.data if hasattr(response, "data") else response
    items = data.get(key, []) if isinstance(data, dict) else []
    return ActionResult(
        data={
            "result": True,
            key: items,
            "total": data.get("total", len(items)) if isinstance(data, dict) else len(items),
            "page": data.get("page", page) if isinstance(data, dict) else page,
            "pageSize": data.get("pageSize", page_size or 100) if isinstance(data, dict) else (page_size or 100),
        },
        cost_usd=0.0,
    )


def build_error_result(response) -> ActionError | None:
    if not hasattr(response, "status"):
        return None
    if response.status < 400:
        return None
    data = response.data or {}
    message = data.get("message", f"HTTP {response.status}") if isinstance(data, dict) else f"HTTP {response.status}"
    return ActionError(message=message)
