# Documentation Reference

## Integration README.md

Every integration MUST have a `README.md` in its directory. Follow this format:

```markdown
# [Integration Name] Integration

Brief one-line description of the integration.

## Features

| Category | Capabilities |
|----------|-------------|
| **[Domain A]** | Brief list of capabilities |
| **[Domain B]** | Brief list of capabilities |

## Actions

### [Domain Group]

#### `action_name`
Description of what the action does, including behavior with optional parameters.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `param_1` | Yes | Description |
| `param_2` | No | Description including default value |

**Outputs:**
- **On success:** `field_a`, `field_b`
- **On error:** `result` (false), `statusCode`, `error`, `message`

---

## Authentication

### [Auth Type] (e.g., OAuth 2.0 / API Key)

Instructions for how to authenticate.

**Required Scopes/Permissions:** (if OAuth)
| Scope | Purpose |
|-------|---------|
| `scope_name` | What it enables |

**Getting Your API Key:** (if API key)
1. Step-by-step instructions
2. Where to find it in the service's UI

---

## Project Structure

\```
my-integration/
├── my_integration.py     # Entry point, loads Integration
├── config.json           # Integration configuration
├── helpers.py            # Shared utilities
├── actions/
│   ├── __init__.py       # Imports all action submodules
│   ├── domain_a.py       # [Domain A] actions
│   └── domain_b.py       # [Domain B] actions
└── tests/
    ├── context.py        # Test import configuration
    └── test_my_integration.py  # Test suite
\```

## Running Tests

\```bash
cd my-integration
pytest tests/ -v
\```

---

## API Version

This integration uses [API Name] **[version]**.

Base URL: `https://api.example.com/v1`
```

### Key Points

- Use **features table** at the top for quick scanning
- **Group actions by domain** with `---` separators
- **Parameter tables** for every action with Required column
- **Document behavior** of optional params ("If omitted, returns a list")
- Include **project structure** diagram
- Include **auth setup instructions** so users know exactly what to do
- State the **API version** being used

## Root README.md

**ALWAYS update the root `README.md`** when adding or modifying an integration. This is critical for discoverability.

### Root README Format

The root README lists all integrations under `## Integrations`. Each entry follows this pattern:

```markdown
### [Integration Display Name]

[directory-name](directory-name): Comprehensive description covering all capabilities...
```

### Writing the Root README Entry

The description should be a single dense paragraph covering:

1. **What it integrates with** — API name and version
2. **All capabilities** — List every major feature
3. **Auth method** — OAuth 2.0, API key, etc.
4. **Number of actions** — "Includes N actions covering..."
5. **Ideal use cases** — "Ideal for..."

### Example Entry

```markdown
### Humanitix

[humanitix](humanitix): Event management integration with Humanitix Public API v1 for retrieving events, orders, tickets, and attendee check-ins. Supports event retrieval (single event by ID or paginated list with date filtering), order retrieval with buyer details and payment status, ticket access with attendee information and check-in status filtering, attendee check-in and check-out operations with scanning message support, and tag retrieval for event categorization. Features API key authentication, location override with ISO 3166-1 alpha-2 country codes, pagination support (up to 100 results per page), and date-time filtering with ISO 8601. Includes 6 actions covering events, orders, tickets, check-in/check-out, and tags. Ideal for event operations, attendee tracking, and ticketing workflows.
```

### Where to Add

- Add new entries in **alphabetical order** by integration name, or at the end of the integrations section
- Check if an entry already exists and update it if improving an existing integration
- The entry should be added BEFORE the `## Template` section at the bottom

## Icon Requirements

- **Filename:** Must be exactly `icon.png`
- **Format:** PNG only (not .webp, .svg, .jpg, or any other format)
- **Content:** Should be a recognizable logo/icon for the service being integrated
- **Location:** Root of the integration directory

## requirements.txt

Always required. At minimum:

```
autohive-integrations-sdk
```

Add any third-party libraries the integration uses. Do NOT include:
- Standard library modules (os, json, asyncio, etc.)
- pytest or test dependencies
