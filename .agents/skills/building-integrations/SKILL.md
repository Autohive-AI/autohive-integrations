---
name: building-integrations
description: "Build or improve Autohive integrations following best practices. Use when creating new integrations, refactoring existing ones, or adding actions/tests/docs to integrations. Covers multi-file structure, action design, config.json, testing, and documentation."
---

# Building Autohive Integrations

Build production-quality Autohive integrations using the `autohive-integrations-sdk`. This skill covers new integrations and refactoring existing ones.

## Workflow

Follow these steps in order when building or improving an integration:

### Step 1: Plan Actions

Before writing code, study the target API and plan which actions to expose.

**Critical rules:**
- **Merge get-one and get-many** into a single action. If an API has `GET /items` and `GET /items/{id}`, create ONE `get_items` action with an optional `item_id` parameter. Do NOT create separate `get_item` and `list_items` actions.
- **Group related mutations** into one action using an `action` enum parameter (e.g., `manage_comment` with `action: reply|hide|unhide|like|unlike`).
- **Avoid redundant actions.** If multiple API endpoints return the same type of data with minor filtering differences, combine them with filter parameters instead of creating separate actions.
- **Think about what a user or AI agent would want to do**, not what the API exposes. Actions should be task-oriented.

Read `reference/action-design.md` for detailed guidance and examples.

### Step 2: Choose File Structure

- **Multi-file** (preferred): Use when the integration has **4 or more actions**, or when any single file would exceed ~200 lines.
- **Single-file**: Acceptable ONLY for very small integrations (3 or fewer simple actions).

**Multi-file layout:**
```
my-integration/
├── my_integration.py     # Entry point — loads Integration, imports actions
├── config.json           # Integration configuration and action schemas
├── helpers.py            # Shared utilities (API base URL, auth headers, builders)
├── actions/
│   ├── __init__.py       # Imports all action submodules to register them
│   ├── domain_a.py       # Actions grouped by domain (e.g., posts.py, events.py)
│   └── domain_b.py
├── tests/
│   ├── context.py        # Path setup and integration import
│   └── test_my_integration.py  # Comprehensive test suite
├── requirements.txt      # Must include autohive-integrations-sdk
├── icon.png              # Integration icon (MUST be icon.png, no other formats)
└── README.md             # Integration documentation
```

Read `reference/file-structure.md` for the exact patterns and code templates.

### Step 3: Write config.json

The config.json defines the integration's identity, auth, and action schemas. It is read by both AI agents and humans.

**Key requirements:**
- `display_name` on every action
- Descriptions must explain what the action does AND how parameters behave (e.g., "If omitted, returns recent posts")
- Input schemas must document optional vs required parameters clearly
- Output schemas must cover success AND error cases

Read `reference/config-schema.md` for the full schema reference with auth types.

### Step 4: Write Entry Point

The entry point file is minimal — it loads the integration and imports actions:

```python
"""
My Integration for Autohive

Brief description of capabilities.
All actions use the [API Name] [version].
"""

from autohive_integrations_sdk import Integration
import os

config_path = os.path.join(os.path.dirname(__file__), "config.json")
my_integration = Integration.load(config_path)

# Import actions to register handlers
import actions  # noqa: F401
```

### Step 5: Write Helpers

Put shared utilities in `helpers.py`:
- API base URL and version constants
- Auth header builders
- Common response builders (pagination, errors)
- Shared data transformation functions

Read `reference/file-structure.md` for helper patterns.

### Step 6: Write Actions

Each action file contains one or more related `ActionHandler` classes, grouped by domain.

**Key patterns:**
- Use `@integration.action("action_name")` decorator
- Class must extend `ActionHandler`
- Implement `async def execute(self, inputs, context) -> ActionResult`
- Use private helper functions (e.g., `_build_post_response`) for data normalization
- Always return `ActionResult(data={...})`

Read `reference/action-design.md` and `reference/examples.md` for code patterns.

### Step 7: Implement Connected Account (When Applicable)

If the integration uses OAuth (platform auth), implement `ConnectedAccountHandler` to display the connected user's info in the UI:

```python
from autohive_integrations_sdk import ConnectedAccountHandler, ConnectedAccountInfo

@my_integration.connected_account()
class MyConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        response = await context.fetch(f"{API_BASE}/me", method="GET", params={"fields": "id,username,name,profile_picture_url"})
        return ConnectedAccountInfo(
            username=response.get("username"),
            first_name=response.get("first_name"),
            last_name=response.get("last_name"),
            avatar_url=response.get("profile_picture_url"),
            user_id=response.get("id")
        )
```

This should be implemented for ALL integrations where the API provides a "current user" or "me" endpoint.

### Step 8: Write Tests

Every action MUST have tests. Use the `MockExecutionContext` pattern with URL-routed responses.

**Minimum test coverage per action:**
- Success case (happy path)
- Empty results (e.g., no items found)
- Error responses (API errors, auth failures)
- Edge cases (missing optional fields, validation errors)
- Input validation (required fields, invalid enum values)

Read `reference/testing.md` for the complete testing pattern and template.

### Step 9: Write Documentation

**Integration README.md** — Use the standard format with features table, parameter tables per action, project structure, and auth setup instructions.

**Root README.md** — ALWAYS update the root `README.md` to add or update the integration's entry. Follow the existing format: integration name as H3, linked directory, comprehensive description covering all capabilities.

Read `reference/documentation.md` for templates and the root README format.

### Step 10: Final Checklist

Before considering an integration complete:

- [ ] `config.json` — valid JSON, all actions have `display_name`, `description`, `input_schema`, `output_schema`
- [ ] Entry point — loads config, imports actions
- [ ] `helpers.py` — shared constants and utilities extracted
- [ ] `actions/` — grouped by domain, registered via decorator
- [ ] `actions/__init__.py` — imports all action modules
- [ ] Connected account handler — implemented if API has a "me" endpoint
- [ ] Tests — every action tested (success, empty, error, edge cases)
- [ ] `tests/context.py` — path setup for imports
- [ ] `requirements.txt` — includes `autohive-integrations-sdk` and any other dependencies
- [ ] `icon.png` — present, named exactly `icon.png`
- [ ] `README.md` — complete integration documentation
- [ ] Root `README.md` — updated with integration entry
- [ ] Multi-file structure used (if 4+ actions)

## Anti-Patterns to Avoid

1. **Separate get/list actions** — NEVER create both `get_item` and `list_items`. Merge them.
2. **Duplicate actions with minor differences** — Don't create `get_top_stories`, `get_new_stories`, `get_best_stories` when one `get_stories(type=...)` works.
3. **Giant single files** — If a file exceeds ~200 lines, split it. A 1300-line single file is unmaintainable.
4. **Missing tests** — Every action must be tested.
5. **Vague descriptions** — "Gets data" tells nobody anything. Be specific about what, how, and when.
6. **Hardcoded auth** — Always use `context.auth` or `context.fetch` for authentication.
7. **Missing error handling** — Always handle API error responses gracefully.
8. **Wrong icon format** — Must be `icon.png`, not `.webp`, `.svg`, `.jpg`, or anything else.
