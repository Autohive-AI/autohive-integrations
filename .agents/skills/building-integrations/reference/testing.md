# Testing Reference

## Overview

Every action MUST have tests. Tests use a `MockExecutionContext` that simulates API responses without making real HTTP calls. Tests run with `pytest` and `pytest-asyncio`.

## File Structure

```
tests/
├── context.py              # Path setup and integration import
└── test_my_integration.py  # All tests
```

## context.py Template

This file sets up Python path so tests can import the integration modules:

```python
# -*- coding: utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

from my_integration import my_integration
```

**Important:** The import name must match the variable name in your entry point file (e.g., `from facebook import facebook`, `from humanitix import humanitix`).

## MockExecutionContext Pattern

The mock context intercepts `context.fetch()` calls and returns pre-configured responses based on URL patterns and HTTP methods.

### For Platform Auth (OAuth)

```python
class MockExecutionContext:
    """
    Mock execution context that simulates API responses.
    Routes requests based on URL patterns and HTTP methods.
    """
    
    def __init__(self, responses: dict[str, Any]):
        self.auth = {}
        self._responses = responses
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data
        })
        
        # Route to appropriate response based on URL and method
        if "/posts" in url and method == "GET":
            return self._responses.get("GET /posts", {"data": []})
        
        if "/posts" in url and method == "POST":
            return self._responses.get("POST /posts", {"id": ""})
        
        if method == "DELETE":
            return self._responses.get("DELETE", {"success": True})
        
        # Single item fetch (fallback)
        single = self._responses.get("GET /single")
        if single and method == "GET":
            return single
        
        return {}
```

### For Custom Auth (API Key)

```python
class MockExecutionContext:
    """
    Mock execution context for API key authenticated integrations.
    """
    
    def __init__(self, responses: dict[str, Any]):
        self.auth = {
            "credentials": {
                "api_key": "test_api_key_123"
            }
        }
        self._responses = responses
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data,
            "headers": headers
        })

        # Route responses based on URL patterns
        if "/events/" in url and method == "GET":
            return self._responses.get("GET /event", {})
        
        if "/events" in url and method == "GET":
            return self._responses.get("GET /events", {"events": [], "total": 0})
        
        return {}
```

## Test File Template

```python
"""
Tests for [Integration Name] Integration

Tests all actions with mocked API responses to verify correct behavior
without making actual API calls.
"""

from typing import Any

import pytest

from context import my_integration

pytestmark = pytest.mark.asyncio


class MockExecutionContext:
    # ... (as above)


# =============================================================================
# GET ITEMS TESTS
# =============================================================================

async def test_get_items_list():
    """Test listing items returns correct structure."""
    responses = {
        "GET /items": {
            "data": [
                {"id": "item_001", "name": "First Item"},
                {"id": "item_002", "name": "Second Item"}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await my_integration.execute_action("get_items", {}, context)
    data = result.result.data

    assert "items" in data
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "item_001"
    assert data["items"][0]["name"] == "First Item"


async def test_get_items_single_by_id():
    """Test fetching a single item by ID."""
    responses = {
        "GET /single": {
            "id": "item_001",
            "name": "Specific Item"
        }
    }
    context = MockExecutionContext(responses)
    result = await my_integration.execute_action("get_items", {
        "item_id": "item_001"
    }, context)
    data = result.result.data

    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "item_001"


async def test_get_items_empty():
    """Test listing items when none exist."""
    responses = {
        "GET /items": {"data": []}
    }
    context = MockExecutionContext(responses)
    result = await my_integration.execute_action("get_items", {}, context)
    data = result.result.data

    assert "items" in data
    assert len(data["items"]) == 0
```

## What to Test Per Action

### Read Actions (get/list)

| Test | Purpose |
|------|---------|
| `test_get_items_list` | Happy path: listing returns correct structure |
| `test_get_items_single_by_id` | Single item fetch works |
| `test_get_items_empty` | Empty results handled gracefully |
| `test_get_items_with_pagination` | Pagination params passed correctly |
| `test_get_items_with_filters` | Filter params passed correctly |

### Create Actions

| Test | Purpose |
|------|---------|
| `test_create_item_success` | Happy path: item created, ID returned |
| `test_create_item_with_optional_fields` | Optional fields work |
| `test_create_item_missing_required` | Error on missing required field |
| `test_create_item_validation` | Validates constraints (e.g., media_url required for photo) |

### Delete Actions

| Test | Purpose |
|------|---------|
| `test_delete_item_success` | Happy path: deletion confirmed |

### Manage/Mutation Actions

| Test | Purpose |
|------|---------|
| `test_manage_item_action_a` | Each enum value works |
| `test_manage_item_action_b` | Each enum value works |
| `test_manage_item_missing_conditional` | Error when conditional field is missing (e.g., message for reply) |
| `test_manage_item_invalid_action` | Error on invalid enum value |

### Error Handling Tests (for custom auth)

| Test | Purpose |
|------|---------|
| `test_action_api_error` | API returns error status code |
| `test_action_unauthorized` | API returns 401 |

### URL and Header Tests

| Test | Purpose |
|------|---------|
| `test_action_url_structure` | Correct URL constructed |
| `test_action_headers` | Correct auth headers sent |

## Testing Patterns

### Asserting Request Details

Use `context._requests` to verify the integration sent the correct request:

```python
async def test_check_in_url_structure():
    """Test that check-in URL includes event_id and ticket_id."""
    responses = {"POST /check-in": {}}
    context = MockExecutionContext(responses)
    await my_integration.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert "events/evt_001/tickets/tkt_001/check-in" in req["url"]
    assert req["method"] == "POST"


async def test_check_in_headers():
    """Test that correct headers are sent."""
    responses = {"POST /check-in": {}}
    context = MockExecutionContext(responses)
    await my_integration.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert req["headers"]["x-api-key"] == "test_api_key_123"
```

### Testing Exception Handling

```python
async def test_manage_comment_reply_missing_message():
    """Test error when reply action missing message."""
    responses = {}
    context = MockExecutionContext(responses)
    
    try:
        await my_integration.execute_action("manage_comment", {
            "comment_id": "c1",
            "action": "reply"
        }, context)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "message is required" in str(e)
```

### Testing Error Responses (Result-Based)

```python
async def test_get_events_api_error():
    """Test listing events when API returns an error."""
    responses = {
        "GET /events": {
            "statusCode": 401,
            "error": "Unauthorized",
            "message": "Invalid API key"
        }
    }
    context = MockExecutionContext(responses)
    result = await my_integration.execute_action("get_events", {}, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 401
    assert data["error"] == "Unauthorized"
```

## Test Organization

- Group tests by action using section comment headers:

```python
# =============================================================================
# GET EVENTS TESTS
# =============================================================================

async def test_get_events_list():
    ...

async def test_get_events_empty():
    ...

# =============================================================================
# CREATE EVENT TESTS
# =============================================================================

async def test_create_event_success():
    ...
```

## Running Tests

```bash
cd my-integration
pytest tests/ -v
```

Make sure `autohive-integrations-sdk` is installed in your environment.
