# Skill: Building Autohive Integrations

## Overview

This guide covers how to build integrations for the Autohive platform using the `autohive_integrations_sdk`. Every integration connects Autohive to a third-party service by defining **actions** (API operations a user can trigger) and optionally **polling triggers** (event monitors). The codebase contains 80+ integrations across services like GitHub, Facebook, Dropbox, Shopify, and more.

---

## Project Structure

### Single-File Integration (simple integrations, <10 actions)

```
my-integration/
├── my_integration.py       # Main integration file (entry point)
├── config.json             # Integration metadata, auth, actions, schemas
├── requirements.txt        # Python dependencies (always includes autohive-integrations-sdk)
├── __init__.py             # Package marker
├── .gitignore              # Excludes dependencies/
├── icon.png                # Integration logo
├── README.md               # Documentation
└── tests/
    ├── __init__.py
    ├── context.py           # Path setup + integration import
    └── test_my_integration.py
```

### Modular Integration (complex integrations, 10+ actions)

```
my-integration/
├── my_integration.py       # Entry point - loads config, imports actions/
├── helpers.py              # Shared constants, auth helpers, error builders, API utilities
├── actions/
│   ├── __init__.py          # Imports all action modules to register handlers
│   ├── resources_a.py       # Actions for resource type A
│   ├── resources_b.py       # Actions for resource type B
│   └── resources_c.py       # Actions for resource type C
├── config.json
├── requirements.txt
├── __init__.py
├── .gitignore
├── icon.png
├── README.md
└── tests/
    ├── __init__.py
    ├── context.py
    └── test_my_integration.py
```

**When to go modular:** Split into `actions/` when you have more than ~8 actions or multiple distinct resource types (e.g., Facebook splits into pages, posts, comments, insights).

---

## config.json

The config.json defines the integration's identity, authentication method, actions, and triggers. It is the contract between the integration and the Autohive platform.

### Full Structure

```json
{
    "name": "my-service",
    "version": "1.0.0",
    "description": "Connects Autohive to My Service for managing resources.",
    "display_name": "My Service",
    "entry_point": "my_service.py",
    "auth": { ... },
    "actions": { ... },
    "polling_triggers": { ... }
}
```

### Authentication Types

**Platform OAuth** (for services with standard OAuth2 flows managed by Autohive):

```json
"auth": {
    "type": "platform",
    "provider": "github",
    "scopes": ["repo", "read:org", "workflow"]
}
```

Known providers include: `github`, `facebook`, `google`, `Dropbox`, `box`, `microsoft`, `tiktok`, `linkedin`, and others. Scopes are provider-specific.

**Custom Auth** (for API keys, bearer tokens, or non-standard auth):

```json
"auth": {
    "identifier": "my_service_auth",
    "type": "custom",
    "title": "My Service Authentication",
    "fields": {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "format": "password",
                "label": "API Key",
                "help_text": "Find your API key at https://myservice.com/settings/api"
            },
            "base_url": {
                "type": "string",
                "format": "text",
                "label": "Base URL",
                "help_text": "Your instance URL (e.g., https://mycompany.myservice.com)"
            }
        },
        "required": ["api_key"]
    }
}
```

- `format: "password"` hides the field value in the UI
- `format: "text"` shows the field as plain text
- Always include `help_text` to guide users on where to find their credentials

### Action Definitions

Each action has an `input_schema` and `output_schema` using JSON Schema:

```json
"actions": {
    "create_post": {
        "display_name": "Create Post",
        "description": "Publish content to a page. Supports text, photo, video, and link posts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Page ID to post to"
                },
                "message": {
                    "type": "string",
                    "description": "The text content of the post"
                },
                "media_type": {
                    "type": "string",
                    "enum": ["text", "photo", "video", "link"],
                    "description": "Type of post content",
                    "default": "text"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-100)",
                    "default": 25
                }
            },
            "required": ["page_id", "message"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "ID of the created post"},
                "permalink_url": {"type": "string"},
                "is_scheduled": {"type": "boolean"}
            },
            "required": ["post_id"]
        }
    }
}
```

Schema tips:
- Use `"enum"` for constrained string choices
- Use `"default"` for optional parameters with sensible defaults
- Include `"description"` on every property
- Only put truly required fields in the `"required"` array
- Match output schema to what the action actually returns

### Polling Trigger Definitions

```json
"polling_triggers": {
    "new_order": {
        "description": "Triggers when a new order is placed",
        "polling_interval": "5m",
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string", "description": "Store to monitor"}
            },
            "required": ["store_id"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "total": {"type": "number"}
            }
        }
    }
}
```

---

## The ExecutionContext Object

`ExecutionContext` is the runtime context passed to every action handler. It provides authentication, HTTP capabilities, logging, and session management.

### Core Properties & Methods

#### `context.auth` - Authentication Credentials

A dictionary containing the credentials configured during connection setup. Structure depends on auth type:

```python
# Platform OAuth (GitHub, Facebook, Google, etc.)
credentials = context.auth.get("credentials", {})
access_token = credentials.get("access_token")

# Custom Auth (API keys, tokens)
credentials = context.auth.get("credentials", {})
api_key = credentials.get("api_key")
base_url = credentials.get("base_url", "https://default.api.com")
```

Always use `.get()` with defaults rather than direct key access to avoid KeyError.

#### `context.fetch()` - HTTP Client

The primary method for making API calls. Handles JSON serialization/deserialization automatically.

```python
# GET request
response = await context.fetch(
    "https://api.example.com/resources",
    method="GET",
    params={"limit": 50, "offset": 0},
    headers={"Authorization": f"Bearer {token}"}
)

# POST with JSON body
response = await context.fetch(
    "https://api.example.com/resources",
    method="POST",
    json={"name": "New Resource", "type": "example"},
    headers={"Authorization": f"Bearer {token}"}
)

# POST with form data
response = await context.fetch(
    "https://api.example.com/upload",
    method="POST",
    data={"field": "value"},
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

# PUT with binary data
response = await context.fetch(
    "https://api.example.com/files/content",
    method="PUT",
    data=binary_bytes,
    headers={"Content-Type": "application/octet-stream"}
)
```

Parameters:
- `url` (str, required): The endpoint URL
- `method` (str): HTTP method - `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
- `params` (dict): Query string parameters
- `json` (dict): JSON request body (auto-serialized)
- `data` (dict or bytes): Form data or raw binary content
- `headers` (dict): Custom HTTP headers

The response is automatically parsed as JSON. For binary responses, use `context._session` directly (see File Handling section).

#### `context.metadata` - Connection Metadata

Additional metadata from OAuth flows. Used sparingly for service-specific routing:

```python
# Example: Mailchimp requires a data center code from OAuth
if hasattr(context, 'metadata') and context.metadata:
    dc = context.metadata.get("dc")  # e.g., "us19"
```

#### `context.logger` - Structured Logging

```python
context.logger.info(f"Processing {len(items)} items")
context.logger.warn(f"Rate limit approaching: {remaining} remaining")
context.logger.error(f"Failed to fetch resource: {error}")
```

Use logging for diagnostic information during execution. Available methods: `info()`, `warn()`, `error()`.

#### `context._session` - Raw HTTP Session (Advanced)

For operations that `context.fetch()` cannot handle (binary downloads, multipart uploads), access the underlying `aiohttp.ClientSession`:

```python
import aiohttp

async with context:
    session = context._session
    if not session:
        session = aiohttp.ClientSession()
        context._session = session

    headers = {}
    if context.auth and "credentials" in context.auth:
        access_token = context.auth["credentials"]["access_token"]
        headers["Authorization"] = f"Bearer {access_token}"

    async with session.get(download_url, headers=headers) as response:
        file_bytes = await response.read()
```

Only use `_session` when `context.fetch()` is insufficient. See the File Handling section for detailed patterns.

---

## Defining Actions

### ActionHandler Pattern

Every action is a class that inherits from `ActionHandler` and is registered with the `@integration.action()` decorator:

```python
from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
my_service = Integration.load(config_path)

@my_service.action("get_resources")
class GetResourcesAction(ActionHandler):
    """Retrieve a list of resources from My Service."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        credentials = context.auth.get("credentials", {})
        api_key = credentials.get("api_key")

        response = await context.fetch(
            "https://api.myservice.com/v1/resources",
            method="GET",
            params={"limit": inputs.get("limit", 25)},
            headers={"Authorization": f"Bearer {api_key}"}
        )

        resources = response.get("data", [])
        return ActionResult(data={"resources": resources})
```

The action name in the decorator (`"get_resources"`) must exactly match a key in `config.json`'s `"actions"` section.

### ActionResult

**Success:**
```python
return ActionResult(data={"resources": items, "total": len(items)})
# or with cost tracking:
return ActionResult(data={"resources": items}, cost_usd=0.001)
```

**Failure:**
```python
return ActionResult.failure(error="Resource not found. Verify the ID is correct.")
```

Rules:
- `data` is a dictionary matching your `output_schema`
- `cost_usd` is optional (defaults to 0.0), used for cost tracking on paid APIs
- Use `ActionResult.failure()` for errors — never return raw dicts or raise unhandled exceptions
- Provide user-friendly error messages that suggest what to fix

### ConnectedAccountHandler

Used to fetch user profile information after OAuth connection:

```python
from autohive_integrations_sdk import ConnectedAccountHandler, ConnectedAccountInfo

@my_service.connected_account()
class MyServiceConnectedAccount(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        response = await context.fetch(
            "https://api.myservice.com/v1/me",
            method="GET",
            headers=get_headers(context)
        )

        return ConnectedAccountInfo(
            user_id=str(response.get("id", "")),
            email=response.get("email"),
            username=response.get("username"),
            first_name=response.get("first_name"),
            last_name=response.get("last_name"),
            avatar_url=response.get("avatar_url"),
            organization=response.get("company")
        )
```

---

## Best Practices (with Examples from the Codebase)

### 1. Centralize Authentication in Helpers

**Good** (from `humanitix/helpers.py`):
```python
HUMANITIX_API_BASE = "https://api.humanitix.com/v1"

def get_api_headers(context: ExecutionContext) -> Dict[str, str]:
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key", "")
    return {"x-api-key": api_key, "Accept": "application/json"}
```

**Bad** (repeated in every action):
```python
# DON'T do this in every action handler
credentials = context.auth.get("credentials", {})
api_key = credentials.get("api_key")
headers = {"x-api-key": api_key, "Accept": "application/json"}
```

### 2. Use a Reusable Error Handling Decorator

**Good** (from `github/github.py`):
```python
class MyServiceAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

def handle_errors(action_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, inputs, context) -> ActionResult:
            try:
                credentials = context.auth.get("credentials", {})
                token = credentials.get("access_token")
                if not token:
                    return ActionResult.failure(
                        error="Authentication failed: No access token found. Please reconnect."
                    )
                return await func(self, inputs, context)
            except MyServiceAPIError as e:
                if e.status_code == 401:
                    return ActionResult.failure(error="Authentication failed: token expired.")
                elif e.status_code == 403:
                    return ActionResult.failure(error=f"Access denied: {e.message}")
                elif e.status_code == 404:
                    return ActionResult.failure(error=f"Resource not found: {e.message}")
                return ActionResult.failure(error=f"API error in {action_name}: {e.message}")
            except Exception as e:
                return ActionResult.failure(error=f"Unexpected error in {action_name}: {str(e)}")
        return wrapper
    return decorator

@my_service.action("get_thing")
class GetThingAction(ActionHandler):
    @handle_errors("get_thing")
    async def execute(self, inputs, context):
        # Just focus on business logic — errors handled by decorator
        ...
```

### 3. Build Reusable Error Checkers

**Good** (from `humanitix/helpers.py`):
```python
def build_error_result(response) -> ActionResult | None:
    """Returns an ActionResult if the response indicates an error, else None."""
    if not isinstance(response, dict) or "statusCode" not in response:
        return None
    return ActionResult(data={
        "result": False,
        "statusCode": response.get("statusCode"),
        "error": response.get("error", ""),
        "message": response.get("message", "")
    })

# Used with the walrus operator for clean checks:
async def execute(self, inputs, context):
    response = await context.fetch(url, method="GET", headers=get_api_headers(context))
    if error := build_error_result(response):
        return error
    return ActionResult(data={"result": True, "items": response.get("items", [])})
```

### 4. Normalize API Responses

**Good** (from `facebook/actions/posts.py`):
```python
def _build_post_response(post: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a post from the Graph API into a consistent response format."""
    shares = post.get("shares", {})
    likes = post.get("likes", {}).get("summary", {})
    comments = post.get("comments", {}).get("summary", {})

    return {
        "id": post.get("id", ""),
        "message": post.get("message", ""),
        "created_time": post.get("created_time", ""),
        "shares_count": shares.get("count", 0),
        "likes_count": likes.get("total_count", 0),
        "comments_count": comments.get("total_count", 0),
    }
```

This keeps action handlers clean and ensures consistent output regardless of API response variations.

### 5. Validate Inputs with Clear Error Messages

**Good** (from `facebook/actions/posts.py`):
```python
MIN_SCHEDULE_MINUTES = 10
MAX_SCHEDULE_DAYS = 75

def _parse_scheduled_time(scheduled_time: str | int) -> int:
    now = int(time.time())
    min_time = now + (MIN_SCHEDULE_MINUTES * 60)
    max_time = now + (MAX_SCHEDULE_DAYS * 24 * 60 * 60)

    if isinstance(scheduled_time, int):
        timestamp = scheduled_time
    elif isinstance(scheduled_time, str):
        if scheduled_time.isdigit():
            timestamp = int(scheduled_time)
        else:
            try:
                dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                timestamp = int(dt.timestamp())
            except ValueError:
                raise ValueError(
                    f"Invalid scheduled_time format: '{scheduled_time}'. "
                    "Use Unix timestamp or ISO 8601 (e.g., 2024-12-25T10:00:00Z)"
                )

    if timestamp < min_time:
        raise ValueError(f"scheduled_time must be at least {MIN_SCHEDULE_MINUTES} minutes in the future")
    if timestamp > max_time:
        raise ValueError(f"scheduled_time must be within {MAX_SCHEDULE_DAYS} days from now")

    return timestamp
```

### 6. DRY Pattern for Similar Actions

**Good** (from `humanitix/actions/checkin.py`):
```python
async def _toggle_check(inputs: Dict[str, Any], context: ExecutionContext, action: str) -> ActionResult:
    """Shared check-in/check-out logic."""
    event_id = inputs["event_id"]
    ticket_id = inputs["ticket_id"]
    headers = get_api_headers(context)
    headers["Content-Type"] = "application/json"
    url = build_url(f"events/{event_id}/tickets/{ticket_id}/{action}")

    response = await context.fetch(url, method="POST", headers=headers)
    if error := build_error_result(response):
        return error
    return ActionResult(data={
        "result": True,
        "scanningMessages": response.get("scanningMessages", []) if isinstance(response, dict) else []
    })

@humanitix.action("check_in")
class CheckInAction(ActionHandler):
    async def execute(self, inputs, context):
        return await _toggle_check(inputs, context, "check-in")

@humanitix.action("check_out")
class CheckOutAction(ActionHandler):
    async def execute(self, inputs, context):
        return await _toggle_check(inputs, context, "check-out")
```

### 7. Implement Pagination Generically

**Good** (from `github/github.py`):
```python
class MyServiceAPI:
    BASE_URL = "https://api.myservice.com/v1"

    @staticmethod
    async def paginated_fetch(context, url, params=None, data_key=None):
        if params is None:
            params = {}
        params.setdefault('per_page', 100)
        params.setdefault('page', 1)

        all_items = []
        headers = MyServiceAPI.get_headers(context)

        while True:
            response = await context.fetch(url, params=params, headers=headers)

            if data_key and isinstance(response, dict):
                items = response.get(data_key, [])
            elif isinstance(response, list):
                items = response
            else:
                items = [response] if response else []

            if not items:
                break
            all_items.extend(items)

            if len(items) < params['per_page']:
                break
            params['page'] += 1

        return all_items
```

---

## File Handling Patterns

File handling is a common requirement for integrations with cloud storage services (Google Drive, OneDrive, Dropbox, Box). Here are the key patterns observed across the codebase.

### Pattern 1: Binary File Download via Raw Session

When `context.fetch()` cannot return raw bytes (it parses JSON by default), use the underlying session:

**From `microsoft365/microsoft365.py`:**
```python
import aiohttp

async def fetch_binary_content(url: str, context: ExecutionContext) -> bytes:
    """Fetch binary content directly without JSON parsing."""
    headers = {}
    if context.auth and "credentials" in context.auth:
        access_token = context.auth["credentials"]["access_token"]
        headers["Authorization"] = f"Bearer {access_token}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if not response.ok:
                raise Exception(f"HTTP {response.status}: {await response.text()}")
            return await response.read()
```

**From `box/box.py` (using context's own session):**
```python
async with context:
    session = context._session
    if not session:
        session = aiohttp.ClientSession()
        context._session = session

    headers = {}
    if context.auth and "credentials" in context.auth:
        headers["Authorization"] = f"Bearer {context.auth['credentials']['access_token']}"

    async with session.get(content_url, headers=headers) as response:
        file_content = await response.read()
        content_base64 = base64.b64encode(file_content).decode('utf-8')
```

### Pattern 2: File Upload with context.fetch()

For simple uploads where the API accepts binary PUT/POST:

**From `microsoft-word/microsoft_word.py`:**
```python
import urllib.parse

docx_bytes = create_docx_from_text(content)
encoded_name = urllib.parse.quote(name)

if folder_path:
    folder_path = folder_path.strip('/')
    encoded_path = urllib.parse.quote(folder_path)
    upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{encoded_path}/{encoded_name}:/content"
else:
    upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{encoded_name}:/content"

response = await context.fetch(
    upload_url,
    method="PUT",
    headers={'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    data=docx_bytes
)
```

### Pattern 3: Multipart Form Upload

For APIs requiring multipart form data (e.g., Box):

**From `box/box.py`:**
```python
import aiohttp
import json

file_content = base64.b64decode(content_base64)

data = aiohttp.FormData()
data.add_field('attributes', json.dumps({
    'name': file_name,
    'parent': {'id': folder_id}
}), content_type='application/json')
data.add_field('file', file_content, filename=file_name, content_type=content_type)

async with context:
    session = context._session or aiohttp.ClientSession()
    headers = {"Authorization": f"Bearer {access_token}"}

    async with session.post(upload_url, headers=headers, data=data) as response:
        upload_result = await response.json()
```

### Pattern 4: Base64 Encoding for Transport

Binary file content is transported as base64-encoded strings through JSON:

```python
import base64

# Encoding (for returning file content)
file_bytes = await response.read()
content_base64 = base64.b64encode(file_bytes).decode('utf-8')
return ActionResult(data={
    "file": {
        "name": file_name,
        "content": content_base64,
        "contentType": content_type
    }
})

# Decoding (for receiving file content)
content_base64 = inputs.get("content")
if isinstance(content_base64, str):
    file_bytes = base64.b64decode(content_base64)
```

### Pattern 5: Using Third-Party SDKs (Google)

**From `google-sheets/google_sheets.py`:**
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def build_credentials(context: ExecutionContext) -> Credentials:
    access_token = context.auth['credentials']['access_token']
    return Credentials(token=access_token, token_uri='https://oauth2.googleapis.com/token')

def build_drive_service(context: ExecutionContext):
    return build('drive', 'v3', credentials=build_credentials(context))

def build_sheets_service(context: ExecutionContext):
    return build('sheets', 'v4', credentials=build_credentials(context))
```

### Pattern 6: Safe URL Encoding for File Paths

**From `microsoft-excel/microsoft_excel.py`:**
```python
from urllib.parse import quote

def encode_path_segment(segment: str) -> str:
    """URL-encode a path segment (no slashes allowed)."""
    return quote(segment, safe="")

def encode_folder_path(path: str) -> str:
    """URL-encode a folder path, preserving slashes."""
    return quote(path.strip("/"), safe="/")
```

### Pattern 7: Size Limit Enforcement

**From `microsoft-powerpoint/microsoft_powerpoint.py`:**
```python
MAX_SIMPLE_UPLOAD_SIZE = 4 * 1024 * 1024  # 4MB

if len(content) > MAX_SIMPLE_UPLOAD_SIZE:
    raise ValueError(f"File size ({len(content)} bytes) exceeds the {MAX_SIMPLE_UPLOAD_SIZE} byte upload limit")
```

### Security: Use defusedxml for XML Parsing

When parsing XML-based file formats (DOCX, XLSX, PPTX), always use `defusedxml` to prevent XXE attacks:

```python
from defusedxml import ElementTree as ET

# SAFE - use defusedxml
tree = ET.fromstring(document_xml)

# UNSAFE - never use stdlib xml for untrusted content
# import xml.etree.ElementTree as ET  # DON'T
```

Also use `html.escape()` when embedding user content in XML:
```python
import html
escaped = html.escape(user_text)
body += f'<w:t xml:space="preserve">{escaped}</w:t>'
```

---

## Common Anti-Patterns to Avoid

These are patterns found in existing integrations that should not be replicated.

### 1. Returning Raw Dicts Instead of ActionResult

**Bad** (from `heartbeat/heartbeat.py`):
```python
async def execute(self, inputs, context):
    try:
        response = await context.fetch(...)
        return {"channels": channels, "result": True}       # WRONG
    except Exception as e:
        return {"channels": [], "result": False, "error": str(e)}  # WRONG
```

**Fix:** Always return `ActionResult`:
```python
return ActionResult(data={"channels": channels})
# or on error:
return ActionResult.failure(error=str(e))
```

### 2. Catch-All Exception Handling Without Differentiation

**Bad:**
```python
except Exception as e:
    return ActionResult(data={"error": str(e), "data": None}, cost_usd=0.0)
```

**Fix:** Catch specific errors and give actionable messages:
```python
except AuthenticationError:
    return ActionResult.failure(error="Authentication failed. Please reconnect your account.")
except NotFoundException:
    return ActionResult.failure(error=f"Resource '{resource_id}' not found. Verify the ID.")
except Exception as e:
    return ActionResult.failure(error=f"Unexpected error: {str(e)}")
```

### 3. Global Mutable State

**Bad** (from `slider/slide_maker.py`):
```python
presentations = {}   # Module-level mutable dict - concurrency hazard
uploaded_images = {}
```

**Fix:** Pass state through function parameters or use the context.

### 4. Giant Monolithic Files

**Bad:** A single file with 1000+ lines and all actions mixed together.

**Fix:** Split by resource type into `actions/` directory with a `helpers.py` for shared logic.

### 5. Silent Failures

**Bad:**
```python
try:
    prs = Presentation(file_stream)
except Exception as e:
    continue  # Silently ignores the error
```

**Fix:** Log errors and return meaningful messages:
```python
except Exception as e:
    context.logger.error(f"Failed to load presentation: {e}")
    return ActionResult.failure(error=f"Failed to load file: {str(e)}")
```

### 6. No Input Validation

**Bad:**
```python
body = {"long_url": inputs["long_url"]}  # Crashes with KeyError if missing
```

**Fix:** Validate required inputs and enforce constraints:
```python
long_url = inputs.get("long_url")
if not long_url:
    return ActionResult.failure(error="long_url is required")
if not long_url.startswith(("http://", "https://")):
    return ActionResult.failure(error="long_url must be a valid HTTP(S) URL")
```

### 7. Inconsistent API Version Usage

**Bad:** Mixing `v1` and `v2` endpoints within the same integration without clear reason.

**Fix:** Define the API version as a constant and use it consistently:
```python
API_VERSION = "v2"
API_BASE = f"https://api.example.com/{API_VERSION}"
```

---

## Testing

### Test File Structure

Every integration should have tests in a `tests/` directory:

```
tests/
├── __init__.py
├── context.py              # Path setup + integration import
└── test_my_integration.py  # Test cases
```

### context.py (Required Boilerplate)

```python
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

from my_integration import my_service
```

### Testing Approach 1: Unit Tests with Mocked Context (Recommended)

Use `pytest` + `pytest-asyncio` with a mocked `ExecutionContext` that routes URL patterns to canned responses. This is the best approach for CI/CD because it requires no real credentials.

**From `linkedin/tests/test_linkedin.py`:**
```python
import pytest
from context import my_service

pytestmark = pytest.mark.asyncio


class MockExecutionContext:
    """Mock context that routes requests to pre-configured responses."""

    def __init__(self, responses: dict = None):
        self.auth = {}
        self._responses = responses or {}
        self._requests = []  # Track requests for assertions

    async def fetch(self, url, method="GET", params=None, data=None, json=None, headers=None, **kwargs):
        self._requests.append({
            "url": url, "method": method, "params": params,
            "data": data, "json": json, "headers": headers
        })

        # Route based on URL pattern and method
        if "/users/me" in url and method == "GET":
            return self._responses.get("GET /users/me", {
                "id": "user123",
                "email": "test@example.com",
                "name": "Test User"
            })

        if "/resources" in url and method == "POST":
            return self._responses.get("POST /resources", {
                "id": "res456",
                "status": "created"
            })

        if "/resources/" in url and method == "GET":
            return self._responses.get("GET /resources/{id}", {
                "id": "res456",
                "name": "Test Resource"
            })

        return {}


# --- Test Cases ---

async def test_get_resources_success():
    context = MockExecutionContext()
    result = await my_service.execute_action("get_resources", {"limit": 10}, context)

    assert result.result.data.get("resources") is not None
    assert len(context._requests) == 1
    assert context._requests[0]["method"] == "GET"


async def test_get_resources_custom_response():
    context = MockExecutionContext(responses={
        "GET /resources": {"data": [{"id": "1"}, {"id": "2"}]}
    })
    result = await my_service.execute_action("get_resources", {}, context)
    assert len(result.result.data["resources"]) == 2


async def test_create_resource_sends_correct_body():
    context = MockExecutionContext()
    inputs = {"name": "New Resource", "type": "example"}
    await my_service.execute_action("create_resource", inputs, context)

    # Verify the request was made correctly
    assert len(context._requests) == 1
    req = context._requests[0]
    assert req["method"] == "POST"
    assert "/resources" in req["url"]


async def test_action_handles_error():
    context = MockExecutionContext(responses={
        "GET /resources/{id}": {"error": "not_found", "statusCode": 404}
    })
    result = await my_service.execute_action("get_resource", {"id": "bad"}, context)

    # Depending on your error handling, check for failure
    assert result.result.data.get("result") is False or "error" in str(result.result)
```

### Testing Approach 2: Integration Tests with Real Auth

For manual testing against real APIs. Use placeholder credentials that are filled in during local testing:

```python
import asyncio
from context import my_service
from autohive_integrations_sdk import ExecutionContext

# Replace with real credentials for manual testing
ACCESS_TOKEN = "your-token-here"

TEST_AUTH = {
    "credentials": {
        "access_token": ACCESS_TOKEN
    }
}

async def test_list_resources():
    """Test listing resources from the real API."""
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await my_service.execute_action(
            "list_resources",
            {"limit": 5},
            context
        )
        print(f"Result: {result.result.data}")
        assert result.result.data.get("resources") is not None

async def main():
    print("=" * 60)
    print("My Service Integration Tests")
    print("=" * 60)
    await test_list_resources()

if __name__ == "__main__":
    asyncio.run(main())
```

### Testing Approach 3: Pytest with AsyncMock Fixtures

For fine-grained unit testing of individual action behavior:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from context import my_service

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.auth = {"credentials": {"access_token": "test_token"}}
    context.fetch = AsyncMock()
    context.logger = MagicMock()
    return context


async def test_get_profile_success(mock_context):
    mock_context.fetch.return_value = {
        "id": "user123",
        "email": "test@example.com",
        "name": "Test User"
    }

    result = await my_service.execute_action("get_profile", {}, mock_context)

    assert result.result.data["email"] == "test@example.com"
    mock_context.fetch.assert_called_once()


async def test_get_profile_missing_token():
    context = MagicMock()
    context.auth = {"credentials": {}}  # No token
    context.fetch = AsyncMock()

    result = await my_service.execute_action("get_profile", {}, context)

    # Should fail gracefully
    assert "error" in str(result.result) or result.result.data.get("result") is False
```

### What to Test

1. **Success paths** - Happy path for each action with expected inputs
2. **Missing/invalid inputs** - Verify validation catches bad input
3. **Auth failures** - Verify behavior when credentials are missing or invalid
4. **API error responses** - Verify error codes (401, 403, 404, 422) are handled
5. **Edge cases** - Empty results, pagination boundaries, optional parameters
6. **Request verification** - Confirm the correct URL, method, and body are sent

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt -t dependencies
pip install pytest pytest-asyncio

# Run tests
cd my-integration
pytest tests/ -v

# Or run directly
python tests/test_my_integration.py
```

---

## Execution Flow Summary

1. User triggers an action on the Autohive platform
2. The SDK calls `integration.execute_action(action_name, inputs, context)`
3. The matching `@integration.action(action_name)` handler class is instantiated
4. The `execute()` method is called with `inputs` (dict from input_schema) and `context` (ExecutionContext with auth)
5. The action uses `context.fetch()` to call the external API
6. The action returns `ActionResult(data={...})` or `ActionResult.failure(error="...")`
7. The SDK wraps the result in an `IntegrationResult` and returns it to the caller

---

## Quick Reference: Integration Checklist

- [ ] `config.json` has correct `name`, `version`, `description`, `entry_point`
- [ ] Auth config matches the service's auth mechanism (platform vs custom)
- [ ] Every action in `config.json` has a matching `@integration.action()` handler
- [ ] All action handlers return `ActionResult` (never raw dicts)
- [ ] Input validation provides clear error messages
- [ ] Error handling differentiates auth errors, not-found, validation, and general errors
- [ ] API base URL and version defined as constants (not hardcoded in every action)
- [ ] Auth extraction centralized in a helper function
- [ ] Response data normalized with `.get()` and sensible defaults
- [ ] `requirements.txt` includes `autohive-integrations-sdk` and all dependencies
- [ ] `tests/context.py` sets up path imports correctly
- [ ] Tests cover success paths, error paths, and input validation
- [ ] `README.md` documents setup, auth fields, actions, and how to run tests
- [ ] No global mutable state
- [ ] No secrets or real credentials committed
- [ ] XML parsing uses `defusedxml` (if applicable)
- [ ] File content transported as base64 strings (if applicable)
- [ ] URL paths properly encoded with `urllib.parse.quote()`
