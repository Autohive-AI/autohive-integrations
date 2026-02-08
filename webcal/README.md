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

- `autohive-integrations-sdk~=1.0.2` - Autohive Integration SDK
- `icalendar` - iCalendar parsing library
- `pytz` - Timezone handling
- `requests` - HTTP requests

## Usage Examples

### Example 1: Fetch Upcoming Events

```python
result = await webcal.execute_action("fetch_events", {
    "webcal_url": "webcal://calendar.example.com/feed.ics",
    "timezone": "Pacific/Auckland",
    "look_ahead_days": 14
}, context)

for event in result.data["events"]:
    print(f"{event['summary']}: {event['start_time']} - {event['end_time']}")
```

### Example 2: Search for Meetings

```python
result = await webcal.execute_action("search_events", {
    "webcal_url": "https://calendar.google.com/calendar/ical/xxx/basic.ics",
    "search_term": "standup",
    "timezone": "America/New_York",
    "look_ahead_days": 30,
    "case_sensitive": False
}, context)

print(f"Found {len(result.data['events'])} events matching 'standup'")
for event in result.data["events"]:
    print(f"  - {event['summary']} (matched in {event['match_field']})")
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
