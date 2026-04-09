# Google Calendar Integration for Autohive

Connects Autohive to the Google Calendar API to allow users to manage calendars, events, and scheduling directly from their Autohive workflows.

## Description

This integration provides comprehensive Google Calendar functionality, enabling users to create, read, update, and delete calendar events. It supports both timed events and all-day events, attendee management, and calendar listing. The integration uses Google's platform authentication to securely access user calendars with appropriate permissions.

Key features:
- List all accessible Google calendars
- View, create, update, and delete calendar events
- Support for both timed and all-day events
- Attendee management and location setting
- Pagination support for large event lists

## Setup & Authentication

The integration uses Google's OAuth2 platform authentication. Users need to authenticate through Google's OAuth flow within Autohive to grant calendar access permissions.

**Authentication Type:** Platform (Google Calendar)

**Required Scopes:**
- `https://www.googleapis.com/auth/calendar` - Full access to Google Calendar

No additional configuration fields are required as authentication is handled through Google's OAuth2 flow.

## Actions

### Action: `list_calendars`

- **Description:** Retrieve all Google calendars accessible to the authenticated user
- **Inputs:** None required
- **Outputs:**
  - `calendars`: Array of calendar objects with ID, summary, description, primary status, and access role
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `list_events`

- **Description:** List events from a specified Google Calendar with optional filtering and pagination
- **Inputs:**
  - `calendar_id`: Calendar ID to list events from (use 'primary' for user's main calendar)
  - `time_min`: Filter events after this time (RFC3339 timestamp, optional)
  - `time_max`: Filter events before this time (RFC3339 timestamp, optional)
  - `max_results`: Maximum number of events to return (1-2500, optional)
  - `page_token`: Pagination token for retrieving next page (optional)
- **Outputs:**
  - `events`: Array of event objects with full event details
  - `nextPageToken`: Token for next page of results (if available)
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `get_event`

- **Description:** Retrieve detailed information about a specific calendar event
- **Inputs:**
  - `calendar_id`: Calendar ID containing the event
  - `event_id`: Specific event ID to retrieve
- **Outputs:**
  - `event`: Complete event object with all details
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `create_event`

- **Description:** Create a new calendar event in the specified calendar
- **Inputs:**
  - `calendar_id`: Target calendar ID
  - `summary`: Event title (required)
  - `description`: Event description (optional)
  - `start_datetime`: Start time for timed events (RFC3339 format, optional)
  - `end_datetime`: End time for timed events (RFC3339 format, optional)
  - `start_date`: Start date for all-day events (YYYY-MM-DD format, optional)
  - `end_date`: End date for all-day events (YYYY-MM-DD format, optional)
  - `location`: Event location (optional)
  - `attendees`: Array of attendee email addresses (optional)
- **Outputs:**
  - `event`: Created event object with ID and Google Calendar link
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `update_event`

- **Description:** Modify an existing calendar event while preserving unchanged fields
- **Inputs:**
  - `calendar_id`: Calendar ID containing the event
  - `event_id`: Event ID to update
  - `summary`: Updated event title (optional)
  - `description`: Updated event description (optional)
  - `start_datetime`: Updated start time for timed events (optional)
  - `end_datetime`: Updated end time for timed events (optional)
  - `start_date`: Updated start date for all-day events (optional)
  - `end_date`: Updated end date for all-day events (optional)
  - `location`: Updated event location (optional)
  - `attendees`: Updated attendee list (optional)
- **Outputs:**
  - `event`: Updated event object with modification timestamp
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Action: `delete_event`

- **Description:** Permanently delete a calendar event
- **Inputs:**
  - `calendar_id`: Calendar ID containing the event
  - `event_id`: Event ID to delete
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

## Requirements

- Python dependencies are handled by the Autohive platform
- Google Calendar API access
- Valid Google account with calendar permissions

## Usage Examples

**Example 1: Create a team meeting**

```json
{
  "calendar_id": "primary",
  "summary": "Weekly Team Standup",
  "description": "Discuss progress and blockers",
  "start_datetime": "2024-01-15T09:00:00-08:00",
  "end_datetime": "2024-01-15T09:30:00-08:00",
  "location": "Conference Room A",
  "attendees": ["alice@company.com", "bob@company.com"]
}
```

**Example 2: List upcoming events for this week**

```json
{
  "calendar_id": "primary",
  "time_min": "2024-01-15T00:00:00Z",
  "time_max": "2024-01-22T00:00:00Z",
  "max_results": 50
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd google-calendar`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run the tests: `python tests/test_google_calendar.py`

