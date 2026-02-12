# config.json Schema Reference

## Full Structure

```json
{
    "name": "My Integration",
    "display_name": "My Integration",
    "version": "1.0.0",
    "description": "Brief description of the integration's purpose",
    "entry_point": "my_integration.py",
    "supports_connected_account": true,
    "auth": { ... },
    "actions": { ... }
}
```

## Top-Level Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Integration name (displayed to users) |
| `display_name` | No | Alternative display name (overrides `name` in UI) |
| `version` | Yes | Semantic version (e.g., `"1.0.0"`) |
| `description` | Yes | Brief description of the integration |
| `entry_point` | Yes | Python file that loads the Integration (e.g., `"my_integration.py"`) |
| `supports_connected_account` | No | Set to `true` if the integration implements `ConnectedAccountHandler` |
| `auth` | Yes | Authentication configuration |
| `actions` | Yes | Map of action name to action definition |

## Auth Types

### Platform Auth (OAuth 2.0)

Used when the service supports OAuth and Autohive has a registered OAuth provider.

```json
{
    "auth": {
        "type": "platform",
        "provider": "facebook",
        "scopes": [
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts"
        ]
    }
}
```

- `type`: Must be `"platform"`
- `provider`: The OAuth provider registered with Autohive
- `scopes`: Array of OAuth scopes required

With platform auth, the SDK handles token management. Use `context.fetch()` and it automatically includes the OAuth token.

### Custom Auth (API Key, Bearer Token, etc.)

Used when the service uses API keys, bearer tokens, or other non-OAuth authentication.

```json
{
    "auth": {
        "type": "custom",
        "title": "Humanitix API Key",
        "fields": {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "format": "password",
                    "label": "API Key",
                    "help_text": "Your API Key. Find it at Account > Settings > API."
                }
            },
            "required": ["api_key"]
        }
    }
}
```

- `type`: Must be `"custom"`
- `title`: Displayed in the auth form UI
- `fields`: JSON Schema for the auth form
  - Use `"format": "password"` for sensitive fields (masks input)
  - Use `"format": "text"` for non-sensitive fields
  - `label`: Display label for the field
  - `help_text`: Instructions for the user (where to find the key, etc.)

Access custom auth credentials in code:

```python
credentials = context.auth.get("credentials", {})
api_key = credentials.get("api_key", "")
```

## Action Definition

Each action is a key in the `"actions"` object. The key is the action's programmatic name used in code with `@integration.action("action_name")`.

```json
{
    "action_name": {
        "display_name": "Human-Readable Action Name",
        "description": "Detailed description for AI agents and human users",
        "input_schema": { ... },
        "output_schema": { ... }
    }
}
```

### Field Requirements

| Field | Required | Description |
|-------|----------|-------------|
| `display_name` | **Yes** | Human-readable name shown in UI |
| `description` | **Yes** | Detailed description (read by AI agents AND humans) |
| `input_schema` | **Yes** | JSON Schema for action inputs |
| `output_schema` | **Yes** | JSON Schema for action outputs |

### Action Naming Conventions

- Use `snake_case` for action keys: `get_posts`, `create_event`, `manage_comment`
- Use verb-noun format: `get_`, `create_`, `delete_`, `manage_`, `check_in`
- For merged get/list: use plural noun (`get_posts`, `get_events`)
- For grouped mutations: use `manage_` prefix (`manage_comment`)

### display_name Conventions

- Use Title Case: `"Get Posts"`, `"Create Event"`, `"Manage Comment"`
- Should be concise (2-3 words)
- Match the action key's semantics

## Input Schema

JSON Schema describing the action's input parameters.

```json
{
    "input_schema": {
        "type": "object",
        "properties": {
            "required_field": {
                "type": "string",
                "description": "This field is always required"
            },
            "optional_id": {
                "type": "string",
                "description": "Optional: Specific item ID. If provided, fetches that single item. If omitted, returns a list."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 25, max: 100). Only used when listing.",
                "default": 25
            },
            "action": {
                "type": "string",
                "enum": ["reply", "hide", "unhide"],
                "description": "Action to perform: 'reply' to respond, 'hide'/'unhide' to toggle visibility"
            },
            "conditional_field": {
                "type": "string",
                "description": "Required for 'reply' action: Your reply text"
            }
        },
        "required": ["required_field"]
    }
}
```

### Description Writing Rules for Properties

1. **Start with "Optional:"** if the field is not in `required` and changes behavior when omitted
2. **Explain behavior when omitted** — "If omitted, returns a paginated list"
3. **State constraints** — "default: 25, max: 100"
4. **State conditional requirements** — "Required for 'reply' action: ..."
5. **State which mode it applies to** — "Only used when listing events (ignored if event_id is provided)"

### Supported Types

- `"string"` — text, IDs, URLs, ISO timestamps
- `"integer"` — numbers (use `"default"`, `"minimum"`, `"maximum"`)
- `"boolean"` — true/false flags (use `"default"`)
- `"array"` — lists (specify `"items"` type)
- `"object"` — nested objects
- `["string", "null"]` — nullable string

### Enums

Use enums for constrained choices:

```json
{
    "media_type": {
        "type": "string",
        "enum": ["text", "photo", "video", "link"],
        "description": "Type of post (default: text)",
        "default": "text"
    }
}
```

## Output Schema

JSON Schema describing what the action returns. Should cover both success and error cases.

```json
{
    "output_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "List of items (single item if item_id was specified)",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": { "type": "string", "description": "Unique item ID" },
                        "name": { "type": "string", "description": "Item name" }
                    }
                }
            },
            "total": { "type": "integer", "description": "Total number of items" },
            "next_cursor": {
                "type": ["string", "null"],
                "description": "Pagination cursor. Null if no more results."
            }
        },
        "required": ["items"]
    }
}
```

### Output Schema for Error-Aware Actions

When using the result-based error pattern (common with custom auth):

```json
{
    "output_schema": {
        "type": "object",
        "properties": {
            "result": { "type": "boolean", "description": "Whether the request was successful" },
            "statusCode": { "type": "integer", "description": "HTTP status code on error" },
            "error": { "type": "string", "description": "Error type on failure" },
            "message": { "type": "string", "description": "Detailed error message on failure" },
            "items": { "type": "array", "description": "Items on success" }
        },
        "required": ["result"]
    }
}
```
