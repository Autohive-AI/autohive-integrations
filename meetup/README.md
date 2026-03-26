# Meetup Integration for Autohive

Automate Meetup event management across multiple groups — create once, publish everywhere.

## Description

This integration connects to Meetup's GraphQL API and enables agents to manage events across all groups you organize. The primary use case is reducing the repetitive admin work of creating and updating similar events across multiple Meetup groups.

### Key Features

- **Multi-group event management**: List all groups you organize and manage events on each
- **Full event lifecycle**: Create (draft), update, publish, and delete events
- **Cross-group publishing**: Agents can loop through your groups and replicate events with per-group customization
- **No Meetup Pro required**: Works with standard Meetup OAuth

## Setup & Authentication

This integration uses Meetup's OAuth2 platform authentication.

### Required Scopes

- `basic` — read user profile and group membership
- `event_management` — create, edit, delete events

### Setup Steps

1. In Autohive, navigate to Integrations
2. Select "Meetup" and click "Connect"
3. Authorize the requested permissions on Meetup's OAuth page
4. You'll be redirected back to Autohive with the integration connected

## Actions

| Action | Description |
|---|---|
| `get_self` | Get the authenticated user's profile |
| `list_groups` | List all groups you organize |
| `get_group` | Get details of a specific group by urlname |
| `list_events` | List upcoming or past events for a group |
| `get_event` | Get details of a specific event |
| `create_event` | Create a new draft event in a group |
| `update_event` | Update an existing event |
| `delete_event` | Delete/cancel an event |
| `publish_event` | Publish a draft event to group members |

## Testing

Edit `tests/test_meetup.py` and set:
- `AUTH["credentials"]["access_token"]` — your Meetup OAuth access token
- `TEST_GROUP_URLNAME` — the urlname of a group you organize
- `TEST_EVENT_ID` — an existing event ID (for the `get_event` test)

Then run:

```bash
cd meetup
python tests/test_meetup.py
```
