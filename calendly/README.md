# Calendly Integration for Autohive

Connects Autohive to the Calendly API v2 for managing scheduled events, event types, invitees, availability, and webhooks.

## Description

This integration provides comprehensive access to Calendly's scheduling platform. It allows users to view event types, retrieve scheduled events, manage invitees, check availability, configure webhooks, and work with routing forms programmatically.

The integration uses Calendly REST API v2 with OAuth 2.0 authentication and implements 20 actions covering all major Calendly read operations and event management.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your Calendly account.

### Authentication Method

Calendly OAuth 2.0 does not use traditional scopes. Once authenticated, API access is determined by the user's subscription level:
- **Free**: Access to most GET endpoints (users, event types, scheduled events, invitees, availability)
- **Standard+**: Access to webhooks and advanced features
- **Teams/Enterprise**: Access to organization-level features and routing forms

### Setup Steps in Autohive

1. Add Calendly integration in Autohive
2. Click "Connect to Calendly" to authorize the integration
3. Sign in to your Calendly account when prompted
4. Review and authorize the requested permissions
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh.

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

## Actions (20 Total)

### Users (2 actions)

#### `get_current_user`
Get information about the currently authenticated user.

**Inputs:** None

**Outputs:**
- `user`: User information including uri, name, email, scheduling_url, timezone, and current_organization
- `result`: Success status

---

#### `get_user`
Get information about a specific user by their UUID.

**Inputs:**
- `user_uuid` (required): The UUID of the user to retrieve

**Outputs:**
- `user`: User information
- `result`: Success status

---

### Event Types (2 actions)

#### `list_event_types`
List all event types for a user or organization.

**Inputs:**
- `user` (optional): User URI to filter event types
- `organization` (optional): Organization URI to filter event types
- `active` (optional): Filter by active status
- `sort` (optional): Sort order (e.g., 'name:asc', 'name:desc')
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `event_types`: List of event types with uri, name, active status, duration, and scheduling_url
- `pagination`: Pagination information
- `result`: Success status

---

#### `get_event_type`
Get details of a specific event type.

**Inputs:**
- `event_type_uuid` (required): The UUID of the event type

**Outputs:**
- `event_type`: Event type details including name, duration, color, and scheduling_url
- `result`: Success status

---

### Scheduled Events (3 actions)

#### `list_scheduled_events`
List scheduled events for a user or organization with optional date filtering.

**Inputs:**
- `user` (optional): User URI to filter events
- `organization` (optional): Organization URI to filter events
- `invitee_email` (optional): Filter by invitee email address
- `status` (optional): Filter by status: active or canceled
- `min_start_time` (optional): Filter events starting after this time (ISO 8601)
- `max_start_time` (optional): Filter events starting before this time (ISO 8601)
- `sort` (optional): Sort order (e.g., 'start_time:asc', 'start_time:desc')
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `events`: List of scheduled events with uri, name, start_time, end_time, status
- `pagination`: Pagination information
- `result`: Success status

---

#### `get_scheduled_event`
Get details of a specific scheduled event.

**Inputs:**
- `event_uuid` (required): The UUID of the scheduled event

**Outputs:**
- `event`: Scheduled event details including name, start_time, end_time, location, and invitees_counter
- `result`: Success status

---

#### `cancel_scheduled_event`
Cancel a scheduled event.

**Inputs:**
- `event_uuid` (required): The UUID of the scheduled event to cancel
- `reason` (optional): Reason for cancellation

**Outputs:**
- `canceled`: Whether the event was canceled
- `result`: Success status

---

### Invitees (2 actions)

#### `list_event_invitees`
List all invitees for a scheduled event.

**Inputs:**
- `event_uuid` (required): The UUID of the scheduled event
- `status` (optional): Filter by status: active or canceled
- `sort` (optional): Sort order (e.g., 'created_at:asc')
- `email` (optional): Filter by invitee email
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `invitees`: List of invitees with uri, name, email, status, and questions_and_answers
- `pagination`: Pagination information
- `result`: Success status

---

#### `get_invitee`
Get details of a specific invitee for a scheduled event.

**Inputs:**
- `event_uuid` (required): The UUID of the scheduled event
- `invitee_uuid` (required): The UUID of the invitee

**Outputs:**
- `invitee`: Invitee details including name, email, timezone, and questions_and_answers
- `result`: Success status

---

### Availability (3 actions)

#### `get_event_type_available_times`
Get available time slots for an event type (max 7 days per request).

**Inputs:**
- `event_type` (required): Event type URI
- `start_time` (required): Start of time range (ISO 8601)
- `end_time` (required): End of time range (ISO 8601, max 7 days from start)

**Outputs:**
- `available_times`: List of available time slots with start_time and scheduling_url
- `result`: Success status

---

#### `get_user_busy_times`
Get busy time slots for a user.

**Inputs:**
- `user` (required): User URI
- `start_time` (required): Start of time range (ISO 8601)
- `end_time` (required): End of time range (ISO 8601)

**Outputs:**
- `busy_times`: List of busy time slots with start_time and end_time
- `result`: Success status

---

#### `list_user_availability_schedules`
List availability schedules for a user.

**Inputs:**
- `user` (required): User URI

**Outputs:**
- `availability_schedules`: List of availability schedules with rules and timezone
- `result`: Success status

---

### Organization (1 action)

#### `list_organization_memberships`
List all members of an organization.

**Inputs:**
- `organization` (optional): Organization URI
- `user` (optional): Filter by user URI
- `email` (optional): Filter by user email
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `memberships`: List of organization memberships with user details and role
- `pagination`: Pagination information
- `result`: Success status

---

### Webhooks (4 actions)

#### `list_webhooks`
List webhook subscriptions for a user or organization.

**Inputs:**
- `organization` (required): Organization URI to filter webhooks
- `user` (optional): User URI to filter webhooks
- `scope` (optional): Filter by scope: user or organization
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `webhooks`: List of webhook subscriptions with uri, callback_url, events, and state
- `pagination`: Pagination information
- `result`: Success status

---

#### `get_webhook`
Get details of a specific webhook subscription.

**Inputs:**
- `webhook_uuid` (required): The UUID of the webhook subscription

**Outputs:**
- `webhook`: Webhook subscription details
- `result`: Success status

---

#### `create_webhook`
Create a webhook subscription for event notifications (requires paid plan).

**Inputs:**
- `url` (required): The URL to receive webhook payloads
- `events` (required): Events to subscribe to: invitee.created, invitee.canceled, routing_form_submission.created
- `organization` (required): Organization URI for organization-level webhook
- `scope` (required): Scope of the webhook: user or organization
- `user` (optional): User URI for user-level webhook
- `signing_key` (optional): Secret key for webhook signature verification

**Outputs:**
- `webhook`: Created webhook subscription details
- `result`: Success status

---

#### `delete_webhook`
Delete a webhook subscription.

**Inputs:**
- `webhook_uuid` (required): The UUID of the webhook subscription to delete

**Outputs:**
- `deleted`: Whether the webhook was deleted
- `result`: Success status

---

### Routing Forms (3 actions)

#### `list_routing_forms`
List routing forms for an organization.

**Inputs:**
- `organization` (required): Organization URI
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `routing_forms`: List of routing forms
- `pagination`: Pagination information
- `result`: Success status

---

#### `get_routing_form`
Get details of a specific routing form.

**Inputs:**
- `routing_form_uuid` (required): The UUID of the routing form

**Outputs:**
- `routing_form`: Routing form details
- `result`: Success status

---

#### `list_routing_form_submissions`
List submissions for a routing form.

**Inputs:**
- `routing_form` (required): Routing form URI
- `count` (optional): Number of results per page (max 100)
- `page_token` (optional): Token for pagination

**Outputs:**
- `submissions`: List of routing form submissions with questions and answers
- `pagination`: Pagination information
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URL**: `https://api.calendly.com`
- **Authentication**: OAuth 2.0
- **Documentation**: https://developer.calendly.com/api-docs

## Important Notes

- **No Traditional Scopes**: Calendly OAuth does not use scopes. Access is determined by subscription level.
- **Webhooks Require Paid Plan**: Webhook endpoints require Standard plan or higher ($10/user/month).
- **Availability Limit**: The `get_event_type_available_times` endpoint can only retrieve 7 days of availability per request.
- **Read-Only Event Types**: You cannot create or modify event types via the API - only read them.
- **Read-Only Availability**: You cannot set availability via the API - only read it.
- **No Direct Booking**: The API does not support directly booking events. Use Calendly widgets or scheduling links instead.
- **API v1 Deprecation**: Calendly API v1 will be deprecated by August 2025.

## URI Format

Calendly uses full URIs for resource references:
- **User**: `https://api.calendly.com/users/{uuid}`
- **Organization**: `https://api.calendly.com/organizations/{uuid}`
- **Event Type**: `https://api.calendly.com/event_types/{uuid}`
- **Scheduled Event**: `https://api.calendly.com/scheduled_events/{uuid}`

## Common Use Cases

**View Scheduled Meetings:**
- List all upcoming and past scheduled events
- Get details of specific meetings including invitee information
- Filter events by date range or status

**Check Availability:**
- Get available time slots for event types
- View user's busy times
- List availability schedules

**Manage Event Cancellations:**
- Cancel scheduled events with optional reason
- Track canceled vs active events

**Webhook Automation:**
- Receive real-time notifications when events are booked or canceled
- Integrate with CRM or other systems

**Organization Management:**
- List all team members in an organization
- View member roles and permissions

## Version History

- **1.0.0** - Initial release with 20 actions
  - Users: get_current_user, get_user (2 actions)
  - Event Types: list_event_types, get_event_type (2 actions)
  - Scheduled Events: list, get, cancel (3 actions)
  - Invitees: list_event_invitees, get_invitee (2 actions)
  - Availability: get_available_times, get_busy_times, list_schedules (3 actions)
  - Organization: list_memberships (1 action)
  - Webhooks: list, get, create, delete (4 actions)
  - Routing Forms: list, get, list_submissions (3 actions)

## Sources

- [Calendly Developer Portal](https://developer.calendly.com/getting-started)
- [Calendly API Reference](https://developer.calendly.com/api-docs)
- [Calendly OAuth Documentation](https://developer.calendly.com/how-to-access-calendly-data-on-behalf-of-authenticated-users)
- [Calendly Webhooks](https://developer.calendly.com/receive-data-from-scheduled-events-in-real-time-with-webhook-subscriptions)
