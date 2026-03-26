# Meetup Integration Design

**Date:** 2026-03-27
**Status:** Approved

---

## Overview

A Meetup integration for the Autohive platform enabling automated event management across multiple Meetup groups. The primary use case is a group organizer (managing 9+ groups) who wants to create an event once and publish or adapt it across all their groups — eliminating repetitive manual admin work.

The integration uses Meetup's GraphQL API with standard OAuth2 authentication. No Meetup Pro account is required; the integration loops through groups individually, which an agent orchestrates.

---

## Architecture

Follows the standard Autohive integration pattern:

- `meetup/config.json` — action schemas and OAuth2 auth config
- `meetup/meetup.py` — action handlers using `autohive_integrations_sdk`
- `meetup/helpers.py` — GraphQL query/mutation strings and shared utilities
- `meetup/__init__.py` — re-exports the integration
- `meetup/requirements.txt`
- `meetup/icon.png`
- `meetup/README.md`
- `meetup/tests/` — unit tests for each action

**API:** Meetup GraphQL endpoint `https://api.meetup.com/gql`
**Auth:** OAuth2 platform auth via Meetup (`https://secure.meetup.com/oauth2/authorize`)

---

## Actions

### User
- **`get_self`** — Get the authenticated user's profile (id, name, email, member since)

### Groups
- **`list_groups`** — List groups the authenticated user organizes. Returns urlname, name, id, member count, city. Used by agents to enumerate targets when publishing across groups.
- **`get_group`** — Get a specific group by urlname. Returns full group details.

### Events
- **`list_events`** — List upcoming (or past) events for a group. Inputs: `group_urlname`, optional `past` (bool), optional `first` (int, default 20).
- **`get_event`** — Get a specific event by event id. Returns full event details including title, description, venue, start time, duration, status.
- **`create_event`** — Create a new event (as draft) in a group. Inputs: `group_urlname`, `title`, `description`, `start_date_time` (ISO8601), `duration` (minutes), optional `venue_id`, optional `how_to_find_us`, optional `is_online` (bool).
- **`update_event`** — Update an existing event. Inputs: `event_id`, plus any of the create fields as optional updates.
- **`delete_event`** — Delete/cancel an event. Input: `event_id`.
- **`publish_event`** — Publish a draft event, making it visible to group members. Input: `event_id`.

---

## Data Flow

For Terza's use case, an agent would:
1. Call `list_groups` to get all group urlnames
2. Call `create_event` for each group with the event template (adapting title/description per group if needed)
3. Call `publish_event` for each created event id

Each action is independent and composable — the looping logic lives in the agent, not the integration.

---

## Auth

OAuth2 via Meetup's platform provider. Scopes:
- `basic` — read user profile and group membership
- `event_management` — create, edit, delete events

The SDK injects the Bearer token into `context.fetch()` calls automatically.

---

## Error Handling

Each action catches exceptions and returns `{"result": False, "error": str(e)}` on failure, consistent with other integrations. GraphQL errors (returned as `errors` array in 200 responses) are checked explicitly and surfaced as error strings.

---

## Testing

Unit tests per action in `meetup/tests/test_meetup.py` using mocked `context.fetch`. Tests cover:
- Happy path for each action
- Missing required input validation
- GraphQL error response handling
- Network/exception handling
