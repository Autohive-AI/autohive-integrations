# Eventbrite Integration for Autohive

A comprehensive Eventbrite integration for the Autohive platform that enables full event management, venue operations, ticket sales, order tracking, and attendee management.

## Description

This integration provides complete access to Eventbrite's REST API (v3), allowing you to automate your entire event management workflow through Autohive. Whether you're creating events, managing venues, tracking orders, or monitoring attendees, this integration has you covered.

### Key Features

- **Event Management**: Create, read, update, delete, publish, unpublish, cancel, and copy events
- **Venue Operations**: Create and manage venues for your events
- **Ticket Classes**: Full CRUD operations for ticket types and pricing
- **Order Tracking**: View and monitor orders by event or organization
- **Attendee Management**: Track and manage event attendees
- **Organization Support**: Manage events across multiple organizations
- **Category Browsing**: Browse and filter by event categories

## Setup & Authentication

This integration uses Eventbrite's OAuth2 platform authentication for secure access to your Eventbrite account.

### Authentication Type

**OAuth2 Platform Authentication** via Eventbrite

### Required Scopes

The integration requests the following OAuth2 scopes:

- `event.read` - Read event information
- `event.write` - Create and modify events
- `order.read` - Read order information
- `attendee.read` - Read attendee information
- `venue.read` - Read venue information
- `venue.write` - Create and modify venues
- `organization.read` - Read organization information
- `user.read` - Read user profile information

### Setup Steps

1. In Autohive, navigate to Integrations
2. Select "Eventbrite" integration
3. Click "Connect" or "Authenticate"
4. You'll be redirected to Eventbrite's OAuth authorization page
5. Review the requested permissions and click "Allow"
6. You'll be redirected back to Autohive with the integration connected

## Actions

### User Actions

#### `get_current_user`

Retrieves information about the currently authenticated user.

**Inputs:** None required

**Outputs:**
- `user` (object): User details including id, name, email
- `result` (boolean): Operation success status
- `error` (string): Error message if operation failed

---

#### `list_organizations`

Lists all organizations the authenticated user is a member of.

**Inputs:** None required

**Outputs:**
- `organizations` (array): List of organizations
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

### Event Actions

#### `get_event`

Retrieves details of a specific event by its ID.

**Inputs:**
- `event_id` (string, required): The ID of the event to retrieve
- `expand` (array, optional): Expansions to include (e.g., `['venue', 'organizer', 'category']`)

**Outputs:**
- `event` (object): Event details
- `result` (boolean): Operation success status

---

#### `list_events`

Lists events for an organization.

**Inputs:**
- `organization_id` (string, required): Organization ID to list events from
- `status` (string, optional): Filter by status (`draft`, `live`, `started`, `ended`, `completed`, `canceled`, `all`)
- `order_by` (string, optional): Sort order (`start_asc`, `start_desc`, `created_asc`, `created_desc`, `name_asc`, `name_desc`)
- `time_filter` (string, optional): Time filter (`all`, `past`, `current_future`)
- `page_size` (integer, optional): Results per page (max 50)

**Outputs:**
- `events` (array): List of events
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

#### `create_event`

Creates a new event in an organization.

**Inputs:**
- `organization_id` (string, required): Organization ID
- `name` (string, required): Event name/title
- `start_utc` (string, required): Start date/time in UTC (ISO 8601, e.g., `2024-12-25T18:00:00Z`)
- `end_utc` (string, required): End date/time in UTC (ISO 8601)
- `timezone` (string, required): Timezone (e.g., `America/Los_Angeles`)
- `currency` (string, required): Currency code (e.g., `USD`)
- `summary` (string, optional): Short description (max 140 chars)
- `online_event` (boolean, optional): Whether this is an online event
- `venue_id` (string, optional): Venue ID for in-person events
- `organizer_id` (string, optional): Organizer ID
- `category_id` (string, optional): Category ID
- `listed` (boolean, optional): Whether publicly listed
- `shareable` (boolean, optional): Whether shareable
- `capacity` (integer, optional): Maximum capacity

**Outputs:**
- `event` (object): Created event details
- `result` (boolean): Operation success status

---

#### `update_event`

Updates an existing event.

**Inputs:**
- `event_id` (string, required): The ID of the event to update
- All other event fields are optional

**Outputs:**
- `event` (object): Updated event details
- `result` (boolean): Operation success status

---

#### `delete_event`

Deletes an event. Event must not have any pending or completed orders.

**Inputs:**
- `event_id` (string, required): The ID of the event to delete

**Outputs:**
- `deleted` (boolean): Whether the event was deleted
- `result` (boolean): Operation success status

---

#### `publish_event`

Publishes a draft event to make it live.

**Inputs:**
- `event_id` (string, required): The ID of the event to publish

**Outputs:**
- `published` (boolean): Whether the event was published
- `result` (boolean): Operation success status

---

#### `unpublish_event`

Unpublishes a live event back to draft status.

**Inputs:**
- `event_id` (string, required): The ID of the event to unpublish

**Outputs:**
- `unpublished` (boolean): Whether the event was unpublished
- `result` (boolean): Operation success status

---

#### `cancel_event`

Cancels an event.

**Inputs:**
- `event_id` (string, required): The ID of the event to cancel

**Outputs:**
- `canceled` (boolean): Whether the event was canceled
- `result` (boolean): Operation success status

---

#### `copy_event`

Creates a copy of an existing event.

**Inputs:**
- `event_id` (string, required): The ID of the event to copy
- `name` (string, optional): Name for the copied event
- `start_utc` (string, optional): New start date/time
- `end_utc` (string, optional): New end date/time
- `timezone` (string, optional): Timezone for the copied event

**Outputs:**
- `event` (object): Copied event details
- `result` (boolean): Operation success status

---

#### `get_event_description`

Retrieves the full HTML description of an event.

**Inputs:**
- `event_id` (string, required): The ID of the event

**Outputs:**
- `description` (string): Full HTML description
- `result` (boolean): Operation success status

---

### Venue Actions

#### `get_venue`

Retrieves details of a specific venue.

**Inputs:**
- `venue_id` (string, required): The ID of the venue to retrieve

**Outputs:**
- `venue` (object): Venue details
- `result` (boolean): Operation success status

---

#### `list_venues`

Lists venues for an organization.

**Inputs:**
- `organization_id` (string, required): Organization ID to list venues from

**Outputs:**
- `venues` (array): List of venues
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

#### `create_venue`

Creates a new venue for an organization.

**Inputs:**
- `organization_id` (string, required): Organization ID
- `name` (string, required): Venue name
- `address_1` (string, optional): Street address line 1
- `address_2` (string, optional): Street address line 2
- `city` (string, optional): City
- `region` (string, optional): State/Province/Region code
- `postal_code` (string, optional): Postal/ZIP code
- `country` (string, optional): Country code (ISO 3166-1 alpha-2)
- `latitude` (string, optional): Latitude coordinate
- `longitude` (string, optional): Longitude coordinate
- `capacity` (integer, optional): Venue capacity

**Outputs:**
- `venue` (object): Created venue details
- `result` (boolean): Operation success status

---

### Order Actions

#### `get_order`

Retrieves details of a specific order.

**Inputs:**
- `order_id` (string, required): The ID of the order to retrieve
- `expand` (array, optional): Expansions (e.g., `['event', 'attendees']`)

**Outputs:**
- `order` (object): Order details
- `result` (boolean): Operation success status

---

#### `list_orders_by_event`

Lists orders for a specific event.

**Inputs:**
- `event_id` (string, required): Event ID to list orders from
- `status` (string, optional): Filter by status (`active`, `inactive`, `both`, `all_not_deleted`)
- `changed_since` (string, optional): Only return orders changed after this time (ISO 8601)

**Outputs:**
- `orders` (array): List of orders
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

#### `list_orders_by_organization`

Lists orders for an organization across all events.

**Inputs:**
- `organization_id` (string, required): Organization ID to list orders from
- `status` (string, optional): Filter by status
- `changed_since` (string, optional): Only return orders changed after this time

**Outputs:**
- `orders` (array): List of orders
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

### Attendee Actions

#### `get_attendee`

Retrieves details of a specific attendee.

**Inputs:**
- `event_id` (string, required): Event ID the attendee belongs to
- `attendee_id` (string, required): The ID of the attendee to retrieve

**Outputs:**
- `attendee` (object): Attendee details
- `result` (boolean): Operation success status

---

#### `list_attendees`

Lists attendees for a specific event.

**Inputs:**
- `event_id` (string, required): Event ID to list attendees from
- `status` (string, optional): Filter by status (`attending`, `not_attending`, `unpaid`)
- `changed_since` (string, optional): Only return attendees changed after this time

**Outputs:**
- `attendees` (array): List of attendees
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

### Ticket Class Actions

#### `get_ticket_class`

Retrieves details of a specific ticket class.

**Inputs:**
- `event_id` (string, required): Event ID the ticket class belongs to
- `ticket_class_id` (string, required): The ID of the ticket class to retrieve

**Outputs:**
- `ticket_class` (object): Ticket class details
- `result` (boolean): Operation success status

---

#### `list_ticket_classes`

Lists ticket classes for a specific event.

**Inputs:**
- `event_id` (string, required): Event ID to list ticket classes from
- `pos` (string, optional): Point of sale filter (`online`, `at_the_door`)

**Outputs:**
- `ticket_classes` (array): List of ticket classes
- `pagination` (object): Pagination information
- `result` (boolean): Operation success status

---

#### `create_ticket_class`

Creates a new ticket class for an event.

**Inputs:**
- `event_id` (string, required): Event ID to create the ticket class for
- `name` (string, required): Ticket class name
- `quantity_total` (integer, required): Total number of tickets available
- `description` (string, optional): Ticket class description
- `cost` (string, optional): Cost in format `CURRENCY,AMOUNT` (e.g., `USD,2500` for $25.00)
- `free` (boolean, optional): Whether this is a free ticket
- `donation` (boolean, optional): Whether this is a donation ticket
- `minimum_quantity` (integer, optional): Minimum quantity per order
- `maximum_quantity` (integer, optional): Maximum quantity per order
- `sales_start` (string, optional): When ticket sales start (ISO 8601)
- `sales_end` (string, optional): When ticket sales end (ISO 8601)
- `hidden` (boolean, optional): Whether hidden from public

**Outputs:**
- `ticket_class` (object): Created ticket class details
- `result` (boolean): Operation success status

---

#### `update_ticket_class`

Updates an existing ticket class.

**Inputs:**
- `event_id` (string, required): Event ID the ticket class belongs to
- `ticket_class_id` (string, required): The ID of the ticket class to update
- All other ticket class fields are optional

**Outputs:**
- `ticket_class` (object): Updated ticket class details
- `result` (boolean): Operation success status

---

#### `delete_ticket_class`

Deletes a ticket class. Cannot delete if tickets have been sold.

**Inputs:**
- `event_id` (string, required): Event ID the ticket class belongs to
- `ticket_class_id` (string, required): The ID of the ticket class to delete

**Outputs:**
- `deleted` (boolean): Whether the ticket class was deleted
- `result` (boolean): Operation success status

---

### Category Actions

#### `list_categories`

Lists all available event categories.

**Inputs:** None required

**Outputs:**
- `categories` (array): List of categories
- `result` (boolean): Operation success status

---

#### `get_category`

Retrieves details of a specific category.

**Inputs:**
- `category_id` (string, required): The ID of the category to retrieve

**Outputs:**
- `category` (object): Category details
- `result` (boolean): Operation success status

---

## Error Handling

All actions return a consistent error format:

```json
{
  "result": false,
  "error": "Error message describing what went wrong"
}
```

Common error scenarios:
- **Authentication errors**: Token expired or invalid permissions
- **Not found errors**: Resource (event, venue, etc.) doesn't exist
- **Validation errors**: Missing required fields or invalid data
- **Permission errors**: Insufficient permissions for the operation

## Rate Limiting

Eventbrite API has rate limits. The integration handles rate limiting gracefully, but for high-volume operations, consider spacing out requests.

## Support

For issues with this integration, please check:
1. Your Eventbrite OAuth connection is active
2. You have the required permissions for the operation
3. The resource IDs are correct and accessible

For Eventbrite API documentation, visit: https://www.eventbrite.com/platform/api
