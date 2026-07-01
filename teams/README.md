# Microsoft Teams Integration for Autohive

Connects Autohive to Microsoft Teams to allow agents to read channels, send messages, and interact with message threads directly from workflows.

## Description

This integration provides Microsoft Teams channel and messaging functionality via the Bot Framework Connector API and the Microsoft Graph API. It supports listing and searching channels, sending messages, reading recent channel messages, and managing message threads.

Key features:
- List all channels in a Teams team
- Search for channels by name
- Look up a specific channel by name
- Send messages to a Teams channel (with agent attribution)
- Read recent messages from a channel
- Fetch replies in a message thread
- Reply to an existing message thread

## Setup & Authentication

The integration uses Autohive's platform Teams authentication. The bot must be installed in the target Teams team before use.

**Authentication Type:** Platform (Microsoft Teams)

**Credential fields provided by the platform at runtime:**
- `TeamId` — The Teams thread ID for the team
- `GroupId` — The Azure AD Group/Team object ID (used for Graph API calls)
- `TenantId` — The Azure AD tenant ID
- `ServiceUrl` — The Bot Framework service URL for the team
- `SetupChannelId` — (optional) Default channel ID set during bot installation

No manual configuration is required — all credentials are injected by the Autohive platform after the user installs the Teams bot.

## Actions

### `list_channels`

- **Description:** List all available channels in the connected Teams team.
- **Inputs:** None
- **Outputs:**
  - `channels`: Array of `{ id, name }` objects

### `search_channels`

- **Description:** Search for channels whose name contains the query string (case-insensitive).
- **Inputs:**
  - `query` *(required)*: Search string to match against channel names
- **Outputs:**
  - `channels`: Array of matching `{ id, name }` objects

### `get_channel_by_name`

- **Description:** Find a specific channel by its exact name (case-insensitive).
- **Inputs:**
  - `channel_name` *(required)*: The name of the channel to find
- **Outputs:**
  - `found`: Boolean indicating whether the channel was found
  - `channel`: `{ id, name }` object, or `null` if not found

### `send_message`

- **Description:** Send a message to a Teams channel. The message is attributed to the Autohive agent.
- **Inputs:**
  - `channel_id` *(required)*: The ID of the target channel
  - `message` *(required)*: The text to send
- **Outputs:**
  - `success`: Boolean
  - `message`: Confirmation string

### `get_channel_messages`

- **Description:** Fetch recent messages from a Teams channel via the Graph API.
- **Inputs:**
  - `channel_id` *(required)*: The ID of the channel to read
  - `limit` *(optional)*: Maximum number of messages to return (default 20, max 50)
- **Outputs:**
  - `messages`: Array of `{ id, created_at, from, text, has_replies }` objects

### `get_message_replies`

- **Description:** Get all replies in a message thread.
- **Inputs:**
  - `channel_id` *(required)*: The channel containing the message
  - `message_id` *(required)*: The ID of the parent message
- **Outputs:**
  - `replies`: Array of `{ id, created_at, from, text }` objects
  - `count`: Total number of replies

### `reply_to_message`

- **Description:** Post a reply in an existing message thread.
- **Inputs:**
  - `channel_id` *(required)*: The channel containing the message
  - `message_id` *(required)*: The ID of the message to reply to
  - `reply` *(required)*: The reply text
- **Outputs:**
  - `success`: Boolean
  - `reply_id`: The ID of the created reply

## Requirements

```
autohive-integrations-sdk~=1.1.1
aiohttp
jsonschema
requests
botframework-connector==4.17.1
botbuilder-core==4.17.1
botbuilder-schema==4.17.1
```

The bot credentials (`TEAMS_BOT_APP_ID` / `TEAMS_BOT_APP_PASSWORD`) must be available in the environment at runtime. These are provisioned via AWS SSM for the Autohive platform.

## Usage Examples

**List all channels:**
```json
{
  "action": "list_channels",
  "inputs": {}
}
```

**Send a message to a channel:**
```json
{
  "action": "send_message",
  "inputs": {
    "channel_id": "19:abc123@thread.skype",
    "message": "Deployment complete — all services healthy."
  }
}
```

**Get recent messages and fetch replies on the first one:**
```json
{
  "action": "get_channel_messages",
  "inputs": {
    "channel_id": "19:abc123@thread.skype",
    "limit": 5
  }
}
```

## Testing

Unit tests use mocks and require no credentials:

```bash
pytest teams/ -v -m unit
```
