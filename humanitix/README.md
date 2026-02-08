# Humanitix Integration

Humanitix integration for Autohive. Manage events, orders, tickets, and tags from a unified interface.

## Features

| Category | Capabilities |
|----------|-------------|
| **Events** | Retrieve event details including dates, venue, and status |
| **Orders** | Access order information with buyer details and payment status |
| **Tickets** | View ticket details, attendee info, and check-in status |
| **Tags** | Retrieve tags for event categorization |

## Actions

### Events

#### `get_events`
Retrieve events from your Humanitix account. Fetch a single event by ID, or list events with pagination and filtering.

When `event_id` is provided, the action fetches that single event directly. The `page_size`, `since`, and `page` parameters are ignored in this mode — only `override_location` is supported.

When `event_id` is omitted, the action returns a paginated list of events with optional filtering.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `event_id` | No | Specific event ID. If provided, fetches that single event directly. |
| `override_location` | No | ISO 3166-1 alpha-2 country code to override user location (e.g. `AU`). Works for both single and list queries. |
| `page_size` | No | Results per page, 1–100 (default 100). List mode only. |
| `since` | No | ISO 8601 date-time to filter events since (e.g. `2021-02-01T23:26:13.485Z`). List mode only. |
| `page` | No | Page number, starts at 1 (default 1). List mode only. |

**Outputs:** Event ID, name, slug, status, timezone, dates, venue, URL

---

### Orders

#### `get_orders`
Retrieve orders for a specific event. Fetch a single order by ID, or list orders with pagination and filtering.

When `order_id` is provided, the action fetches that single order directly. The `page_size`, `since`, and `page` parameters are ignored in this mode — only `override_location` and `event_date_id` are supported.

When `order_id` is omitted, the action returns a paginated list of orders with optional filtering.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `event_id` | Yes | The event ID to get orders for. |
| `order_id` | No | Specific order ID. If provided, fetches that single order directly. |
| `override_location` | No | ISO 3166-1 alpha-2 country code to override user location (e.g. `AU`). Works for both single and list queries. |
| `event_date_id` | No | Filter by a specific event date ID. Works for both single and list queries. |
| `page_size` | No | Results per page, 1–100 (default 100). List mode only. |
| `since` | No | ISO 8601 date-time to filter orders since (e.g. `2021-02-01T23:26:13.485Z`). List mode only. |
| `page` | No | Page number, starts at 1 (default 1). List mode only. |

**Outputs:** Order ID, order number, status, buyer info, total amount, currency, ticket count

---

### Tickets

#### `get_tickets`
Retrieve tickets for a specific event. Fetch a single ticket by ID, or list tickets with pagination and filtering.

When `ticket_id` is provided, the action fetches that single ticket directly. The `page_size`, `since`, `status`, `event_date_id`, and `page` parameters are ignored in this mode — only `override_location` is supported.

When `ticket_id` is omitted, the action returns a paginated list of tickets with optional filtering.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `event_id` | Yes | The event ID to get tickets for. |
| `ticket_id` | No | Specific ticket ID. If provided, fetches that single ticket directly. |
| `override_location` | No | ISO 3166-1 alpha-2 country code to override user location (e.g. `AU`). Works for both single and list queries. |
| `event_date_id` | No | Filter by a specific event date ID. List mode only. |
| `page_size` | No | Results per page, 1–100 (default 100). List mode only. |
| `since` | No | ISO 8601 date-time to filter tickets since (e.g. `2021-02-01T23:26:13.485Z`). List mode only. |
| `status` | No | Filter by ticket status (`complete` or `cancelled`). List mode only. |
| `page` | No | Page number, starts at 1 (default 1). List mode only. |

**Outputs:** Ticket ID, type, status, check-in status, attendee info, order ID

---

### Tags

#### `get_tags`
Retrieve tags from your Humanitix account. Fetch a single tag by ID, or list tags with pagination.

When `tag_id` is provided, the action fetches that single tag directly. The `page_size` and `page` parameters are ignored in this mode.

When `tag_id` is omitted, the action returns a paginated list of tags.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `tag_id` | No | Specific tag ID. If provided, fetches that single tag directly. |
| `page_size` | No | Results per page, 1–100 (default 100). List mode only. |
| `page` | No | Page number, starts at 1 (default 1). List mode only. |

**Outputs:** Tag ID, name, color

---

## Authentication

This integration uses API Key authentication.

### Getting Your API Key

1. Log into your Humanitix account
2. Navigate to **Account > Advanced > API Key**
3. Generate your API key

**Important:**
- Do not share your API key - it provides access to sensitive event data
- Generating a new key will invalidate any existing keys
- All requests use HTTPS

---

## Rate Limits

The Humanitix API enforces rate limits:

- **Limit:** 200 requests per minute
- **Response when exceeded:** HTTP 429 (Too Many Requests)

---

## Project Structure

```
humanitix/
├── humanitix.py         # Entry point, loads Integration
├── config.json          # Integration configuration
├── helpers.py           # Shared utilities (API base URL, headers)
├── actions/
│   ├── __init__.py      # Imports all action submodules
│   ├── events.py        # Event retrieval actions
│   ├── orders.py        # Order retrieval actions
│   ├── tickets.py       # Ticket retrieval actions
│   └── tags.py          # Tag retrieval actions
└── requirements.txt     # Python dependencies
```

---

## API Version

This integration uses Humanitix Public API **v1**.

Base URL: `https://api.humanitix.com/v1`

For more information, see the [Humanitix API Documentation](https://humanitix.stoplight.io/docs/humanitix-public-api/).
