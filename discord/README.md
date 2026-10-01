# Discord Integration for Autohive

Connects Autohive to [Discord](https://discord.com/developers/docs/intro), letting workflows read channel history, post messages, and manage reactions in a Discord server.

## Description

This integration talks to the Discord REST API (v10) as a bot. The user installs Autohive's Discord bot into their server through the OAuth flow, and the integration then acts on that server's channels using the bot's own credentials.

Key features:
- List the channels of the connected server
- Read channel message history with paging via a `before` message ID
- Send messages, optionally as a threaded reply to an existing message
- Add and remove reactions, using either Unicode emoji or custom emoji IDs
- Every channel-scoped action verifies the channel belongs to the authorized server before acting, so a workflow cannot reach into an unrelated guild

## Setup & Authentication

Authentication is handled by the Autohive platform using Discord's OAuth flow. Installing the integration adds Autohive's Discord bot to the chosen server, and the resulting server (guild) ID is stored with the connection.

**Authentication Type:** Platform (`discord`)

**Scopes:** `bot`

The bot's own token is supplied to the runtime through the `DISCORD_BOT_TOKEN` environment variable and is never stored in this repository. All API calls authenticate with that bot token, so what an action may do is governed by the bot's permissions in the server, not by OAuth scopes. The bot needs these Discord permissions in any channel it is used against:

| Action | Required bot permission |
| --- | --- |
| `list_channels` | View Channels |
| `get_message_history` | View Channels, Read Message History |
| `send_message` | Send Messages (plus Read Message History to reply) |
| `add_reaction` | Add Reactions |
| `remove_reaction` | Manage Messages is not required — the bot only removes its own reaction |

## Actions

### Action: `list_channels`

- **Description:** List all channels in the connected Discord server
- **Inputs:** none — the server is taken from the connection
- **Outputs:**
  - `channels`: Array of Discord channel objects

### Action: `get_message_history`

- **Description:** Retrieve message history from a Discord channel
- **Inputs:**
  - `channel`: The ID of the Discord channel (required)
  - `limit`: Maximum number of messages to retrieve, up to 100 (optional, defaults to 100)
  - `before`: Return only messages before this message ID, for paging (optional)
- **Outputs:**
  - `messages`: Array of Discord message objects, newest first
  - `has_more`: `true` when a full page was returned, indicating more history may exist

### Action: `send_message`

- **Description:** Send a message to a Discord channel
- **Inputs:**
  - `channel`: The ID of the Discord channel (required)
  - `text`: The text content of the message (required)
  - `reference_message_id`: Message ID to reply to (optional)
- **Outputs:**
  - `id`: ID of the created message
  - `channel_id`: ID of the channel the message was posted to

### Action: `add_reaction`

- **Description:** Add a reaction emoji to a message
- **Inputs:**
  - `channel`: The ID of the Discord channel (required)
  - `message_id`: The ID of the message to react to (required)
  - `reaction`: The emoji to react with, either a Unicode emoji or a custom emoji ID (required)
- **Outputs:**
  - `success`: `true` when the reaction was added

### Action: `remove_reaction`

- **Description:** Remove Autohive's own reaction from a message
- **Inputs:**
  - `channel`: The ID of the Discord channel (required)
  - `message_id`: The ID of the message to remove a reaction from (required)
  - `reaction`: The emoji to remove (required)
- **Outputs:**
  - `success`: `true` when the reaction was removed

## Requirements

- `autohive-integrations-sdk~=2.0.1`

## Usage Examples

**Read the last 10 messages in a channel:**

```json
{
  "action": "get_message_history",
  "inputs": {
    "channel": "222222222222222222",
    "limit": 10
  }
}
```

**Post a message:**

```json
{
  "action": "send_message",
  "inputs": {
    "channel": "222222222222222222",
    "text": "Deploy finished successfully."
  }
}
```

**Reply to an existing message:**

```json
{
  "action": "send_message",
  "inputs": {
    "channel": "222222222222222222",
    "text": "Picking this up now.",
    "reference_message_id": "333333333333333333"
  }
}
```

**React to a message:**

```json
{
  "action": "add_reaction",
  "inputs": {
    "channel": "222222222222222222",
    "message_id": "333333333333333333",
    "reaction": "👍"
  }
}
```

## Testing

Unit tests mock the Discord API and cover every action, the guild-authorization check, message paging, threaded replies, and emoji URL encoding for both Unicode and alphanumeric custom emoji:

```bash
pytest discord/ -v
```

Live testing needs `DISCORD_BOT_TOKEN` set in your environment, plus a server the bot has been installed into.
