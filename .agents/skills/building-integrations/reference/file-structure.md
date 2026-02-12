# File Structure Reference

## Multi-File Layout (Preferred)

Use this structure for integrations with 4+ actions, or when any file would exceed ~200 lines.

```
my-integration/
├── my_integration.py       # Entry point
├── config.json             # Configuration and schemas
├── helpers.py              # Shared utilities
├── actions/
│   ├── __init__.py         # Registers all action modules
│   ├── domain_a.py         # Actions grouped by domain
│   └── domain_b.py
├── tests/
│   ├── context.py          # Test import setup
│   └── test_my_integration.py
├── requirements.txt
├── icon.png
└── README.md
```

## Entry Point Pattern

The entry point file should be minimal. Its job is to:
1. Load the integration from `config.json`
2. Import the actions package (which triggers handler registration)
3. Optionally define the `ConnectedAccountHandler`

```python
"""
My Integration for Autohive

This module provides [brief capabilities list].
All actions use the [API Name] [version].
"""

from autohive_integrations_sdk import Integration
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
my_integration = Integration.load(config_path)

# Import actions to register handlers
import actions  # noqa: F401 - registers action handlers
```

**Naming convention:** The entry point filename should match the integration directory name, with hyphens replaced by underscores. E.g., `google-calendar/` → `google_calendar.py`.

The `config.json` must have `"entry_point": "my_integration.py"` pointing to this file.

## Helpers Module Pattern

`helpers.py` contains shared utilities used across multiple action files.

### What goes in helpers.py:

1. **API constants** (base URL, version)
2. **Auth helpers** (token retrieval, header builders)
3. **Response builders** (pagination, error formatting)
4. **Shared data transformations**

### Platform Auth (OAuth) Example

```python
"""
My Integration helper functions.

This module contains shared utility functions used across multiple action files.
"""

from autohive_integrations_sdk import ExecutionContext

GRAPH_API_VERSION = "v21.0"
API_BASE = f"https://api.example.com/{GRAPH_API_VERSION}"


async def get_page_access_token(context: ExecutionContext, page_id: str) -> str:
    """
    Retrieve the access token for a specific resource.
    
    Args:
        context: The execution context with authentication
        page_id: The resource ID
        
    Returns:
        The access token string
        
    Raises:
        Exception: If the resource is not accessible
    """
    response = await context.fetch(
        f"{API_BASE}/{page_id}",
        method="GET",
        params={"fields": "access_token"}
    )
    token = response.get("access_token")
    if not token:
        raise Exception(f"Failed to retrieve access token for '{page_id}'.")
    return token
```

### Custom Auth (API Key) Example

```python
"""
My Integration helper functions.
"""

from autohive_integrations_sdk import ActionResult, ExecutionContext
from typing import Any, Dict
from urllib.parse import quote, urlencode

API_BASE = "https://api.example.com/v1"


def get_api_headers(context: ExecutionContext) -> Dict[str, str]:
    """Get authentication headers from context credentials."""
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")
    return {
        "x-api-key": api_key,
        "Accept": "application/json"
    }


def build_url(path: str, params: Dict[str, Any] | None = None) -> str:
    """Build a full API URL with optional query parameters."""
    safe_path = "/".join(quote(segment, safe="") for segment in path.split("/"))
    url = f"{API_BASE}/{safe_path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def build_error_result(response) -> ActionResult | None:
    """Check if a response is an API error and return formatted result."""
    if not isinstance(response, dict) or "statusCode" not in response:
        return None
    return ActionResult(data={
        "result": False,
        "statusCode": response.get("statusCode"),
        "error": response.get("error", ""),
        "message": response.get("message", "")
    })


def build_paginated_result(response, key: str, page: int, page_size: int | None = None) -> ActionResult:
    """Build a standardized paginated response."""
    items = response.get(key, []) if isinstance(response, dict) else []
    is_dict = isinstance(response, dict)
    return ActionResult(data={
        "result": True,
        key: items,
        "total": response.get("total", len(items)) if is_dict else len(items),
        "page": response.get("page", page) if is_dict else page,
        "pageSize": response.get("pageSize", page_size or 100) if is_dict else (page_size or 100),
    })


async def fetch_single_resource(context: ExecutionContext, path: str, params: Dict[str, Any], result_key: str) -> ActionResult:
    """Fetch a single resource by path and return standardized result."""
    url = build_url(path, params or None)
    response = await context.fetch(url, method="GET", headers=get_api_headers(context))
    if error := build_error_result(response):
        return error
    return ActionResult(data={"result": True, result_key: response})
```

## Actions Package Pattern

### actions/__init__.py

This file imports all action submodules, which triggers their `@integration.action()` decorators to register handlers.

```python
"""
My Integration action handlers.

Importing this module registers all actions with the integration instance.
"""

from . import domain_a
from . import domain_b
from . import domain_c
```

Or with explicit class imports (either style works):

```python
from actions.domain_a import GetItemsAction
from actions.domain_b import CreateItemAction, DeleteItemAction
```

### Action File Pattern

Group actions by domain (e.g., `posts.py`, `comments.py`, `events.py`, `insights.py`).

```python
"""
My Integration [Domain] actions - [Brief description].
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from my_integration import my_integration
from helpers import API_BASE, get_api_headers


def _build_item_response(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an API item into a consistent response format."""
    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "created_at": item.get("created_at", ""),
    }


@my_integration.action("get_items")
class GetItemsAction(ActionHandler):
    """
    Retrieve items. Fetch a single item by ID or list recent items.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        item_id = inputs.get("item_id")
        limit = min(inputs.get("limit", 25), 100)
        
        if item_id:
            # Fetch single item
            response = await context.fetch(
                f"{API_BASE}/items/{item_id}",
                method="GET",
                headers=get_api_headers(context)
            )
            items = [_build_item_response(response)]
        else:
            # List items
            response = await context.fetch(
                f"{API_BASE}/items",
                method="GET",
                headers=get_api_headers(context),
                params={"limit": limit}
            )
            items = [_build_item_response(i) for i in response.get("data", [])]
        
        return ActionResult(data={"items": items})
```

## Single-File Layout (Small Integrations Only)

Only use this for integrations with 3 or fewer simple actions.

```
my-integration/
├── my_integration.py     # Everything in one file
├── config.json
├── tests/
│   ├── context.py
│   └── test_my_integration.py
├── requirements.txt
├── icon.png
└── README.md
```

```python
from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

my_integration = Integration.load()

API_BASE = "https://api.example.com/v1"


@my_integration.action("get_items")
class GetItemsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        # ... implementation
        return ActionResult(data={...})
```

## Connected Account Handler

Place this in the entry point file. Implement it whenever the API has a "me" or "current user" endpoint.

```python
from autohive_integrations_sdk import (
    Integration, ExecutionContext,
    ConnectedAccountHandler, ConnectedAccountInfo
)

# In config.json, set: "supports_connected_account": true

@my_integration.connected_account()
class MyConnectedAccountHandler(ConnectedAccountHandler):
    """
    Handler for fetching connected account information.
    Called once when a user authorizes the integration.
    """

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        response = await context.fetch(
            f"{API_BASE}/me",
            method="GET",
            params={"fields": "id,username,name,profile_picture_url"}
        )

        name = response.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []

        return ConnectedAccountInfo(
            username=response.get("username"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=response.get("profile_picture_url"),
            user_id=response.get("id")
        )
```

Don't forget to add `"supports_connected_account": true` in config.json when using this.

## requirements.txt

Always required. At minimum:

```
autohive-integrations-sdk
```

Add any additional dependencies the integration needs (e.g., `mistune` for markdown parsing). Do NOT include standard library modules.

## Icon File

- **Must be named exactly `icon.png`** — no other name or format
- Place it in the integration root directory
- Should be a recognizable logo/icon for the service being integrated
