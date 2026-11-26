# Webcal Integration for Autohive

Connects Autohive to WebCalendar (iCal) feeds for fetching and processing calendar events from any webcal or iCal URL.

## Description

This integration provides access to webcal/iCal calendar feeds, enabling automated calendar event retrieval and search capabilities. Key features include:

- **Fetch Events**: Retrieve upcoming events from any webcal/iCal URL within a configurable time range
- **Search Events**: Search for specific events by keywords in summary, description, or location
- **Timezone Support**: Display events in any timezone with automatic conversion
- **Recurring Event Detection**: Identify recurring events in the feed
- **All-Day Event Handling**: Proper handling of all-day vs timed events

## Setup & Authentication

This integration requires no authentication. Simply provide a valid webcal or iCal URL to fetch events.

### Supported URL Formats

- `webcal://example.com/calendar.ics`
- `https://example.com/calendar.ics`

The integration automatically converts `webcal://` URLs to `https://` for fetching.

## Actions

### `fetch_events`
Retrieve events from a webcal URL within a specified time range.

**Inputs:**
- `webcal_url` (string, required): URL of the webcal/ical calendar (starting with webcal:// or https://)
- `timezone` (string, optional): Timezone to display events in (e.g., 'UTC', 'America/New_York', 'Pacific/Auckland'). Default: 'UTC'
- `look_ahead_days` (integer, optional): Number of days to look ahead for events. Default: 7

**Outputs:**
- `timezone` (string): The timezone used for event times
- `events` (array): List of event objects containing:
  - `summary` (string): Event title
  - `description` (string|null): Event description
  - `location` (string|null): Event location
  - `start_time` (string): Start time in the specified timezone
  - `end_time` (string): End time in the specified timezone
  - `all_day` (boolean): Whether this is an all-day event
  - `organizer` (string|null): Event organizer
  - `attendees` (array): List of attendee emails
  - `url` (string|null): Event URL if provided
  - `recurring` (boolean): Whether this is a recurring event
- `result` (boolean): Success status

---

### `search_events`
Search for specific events in a webcal feed based on keywords.

**Inputs:**
- `webcal_url` (string, required): URL of the webcal/ical calendar (starting with webcal:// or https://)
- `search_term` (string, required): Term to search for in event summary, description, or location
- `timezone` (string, optional): Timezone to display events in. Default: 'UTC'
- `look_ahead_days` (integer, optional): Number of days to look ahead for events. Default: 30
- `case_sensitive` (boolean, optional): Whether the search should be case sensitive. Default: false

**Outputs:**
- `timezone` (string): The timezone used for event times
- `search_term` (string): The search term used
- `events` (array): List of matching event objects (same structure as fetch_events, plus):
  - `match_field` (string): Field where the search term was found (summary, description, location)
- `result` (boolean): Success status

---

## Requirements

- `autohive-integrations-sdk~=2.0.0` - Autohive Integration SDK (the existing pin in `requirements.txt`)
- `icalendar` - iCalendar parsing library
- `pytz` - Timezone handling
- `requests` - HTTP requests

## Usage Examples

Run these fragments inside an async function with the registered `webcal` instance from `webcal.py`. Import `ResultType` from `autohive_integrations_sdk`. Your caller must supply an open `ExecutionContext` named `context`, managed with `async with ExecutionContext() as context`; no authentication is needed. Replace the feed URLs with your calendar's URL, and keep private feed URLs out of tracked files.

`execute_action` returns an `IntegrationResult`. Check `ResultType.ACTION` before reading `result.result.data`; handle other result types as failures. See the [SDK calling patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md). This calling convention doesn't change the integration's existing dependency pin.

### Example 1: Fetch Upcoming Events

```python
result = await webcal.execute_action(
    "fetch_events",
    {"webcal_url": "webcal://calendar.example.com/feed.ics", "timezone": "Pacific/Auckland", "look_ahead_days": 14},
    context,
)

assert result.type == ResultType.ACTION, result.result
for event in result.result.data["events"]:
    print(f"{event['summary']}: {event['start_time']} - {event['end_time']}")
```

### Example 2: Search for Meetings

```python
result = await webcal.execute_action(
    "search_events",
    {
        "webcal_url": "https://calendar.google.com/calendar/ical/xxx/basic.ics",
        "search_term": "standup",
        "timezone": "America/New_York",
        "look_ahead_days": 30,
        "case_sensitive": False,
    },
    context,
)

assert result.type == ResultType.ACTION, result.result
print(f"Found {len(result.result.data['events'])} events matching 'standup'")
for event in result.result.data["events"]:
    print(f"  - {event['summary']} (matched in {event['match_field']})")
```

## Testing

Install HiveUp 2.5.4 from a Tooling local build as described in the root [contribution guide](../CONTRIBUTING.md). HiveUp isn't published to PyPI and isolates this integration's existing requirements. From the repository root, run the offline unit tests:

```bash
hiveup test webcal
```

## Common Calendar Sources

This integration works with any iCal-compatible calendar:

- **Google Calendar**: Settings → Calendar → Integrate calendar → Secret address in iCal format
- **Apple iCloud**: Calendar → Share → Public Calendar → Copy Link
- **Microsoft Outlook**: Calendar → Settings → Shared calendars → Publish a calendar
- **Airbnb**: Hosting → Calendar → Availability → Export calendar

## API Reference

- [iCalendar Specification (RFC 5545)](https://datatracker.ietf.org/doc/html/rfc5545)
- [Timezone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
