# Microsoft Teams Integration for Autohive

Connect your Autohive agents to Microsoft Teams to read and send messages, manage channels, teams, and members — all via the Microsoft Graph API.

## Key Features

- List all teams the user belongs to
- Read and send messages in channels and chats
- Create new channels
- List, add, and remove team members
- Read 1:1 and group chat messages

## Setup & Authentication

This integration uses **OAuth2** via your Microsoft (Azure AD) account.

**Required OAuth Scopes:**

| Scope | Purpose |
|-------|---------|
| `Team.ReadBasic.All` | List and read teams |
| `Channel.ReadBasic.All` | List and read channels |
| `Channel.Create` | Create new channels |
| `ChannelMessage.Read.All` | Read channel messages |
| `ChannelMessage.Send` | Send messages to channels |
| `TeamMember.Read.All` | List team members |
| `TeamMember.ReadWrite.All` | Add and remove members |
| `Chat.Read` | List chats and read chat messages |
| `Chat.ReadWrite` | Send messages to chats |
| `ChatMessage.Send` | Send chat messages |

> **Note:** Some scopes (e.g. `ChannelMessage.Read.All`, `TeamMember.ReadWrite.All`) require **admin consent** from your organisation's IT administrator.

**Steps:**
1. Connect your Microsoft account in Autohive.
2. Grant the requested permissions (an admin may need to approve some).
3. Once connected, your agent can access all teams and channels you are a member of.

---

## Actions

### list_teams

List all Microsoft Teams the authenticated user is a member of.

**Inputs:** None

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `teams` | array | List of teams |
| `teams[].id` | string | Unique team ID |
| `teams[].display_name` | string | Display name of the team |
| `teams[].description` | string | Team description |

---

### get_team

Get details of a specific Microsoft Team by its ID.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `team.id` | string | Unique team ID |
| `team.display_name` | string | Display name |
| `team.description` | string | Description |
| `team.web_url` | string | URL to open the team in Teams |

---

### list_channels

List all channels in a Microsoft Teams team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `channels` | array | List of channels |
| `channels[].id` | string | Unique channel ID |
| `channels[].display_name` | string | Channel name |
| `channels[].description` | string | Channel description |
| `channels[].membership_type` | string | `standard`, `private`, or `shared` |

---

### get_channel

Get details of a specific channel within a team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |
| `channel_id` | string | ✅ | The unique identifier of the channel |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `channel.id` | string | Unique channel ID |
| `channel.display_name` | string | Channel name |
| `channel.description` | string | Channel description |
| `channel.membership_type` | string | Membership type |
| `channel.web_url` | string | URL to open the channel in Teams |

---

### create_channel

Create a new channel in a Microsoft Teams team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The team to create the channel in |
| `display_name` | string | ✅ | Name for the new channel |
| `description` | string | ❌ | Optional description |
| `membership_type` | string | ❌ | `standard` (default) or `private` |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the channel was created |
| `channel.id` | string | ID of the new channel |
| `channel.display_name` | string | Name of the new channel |

---

### list_messages

List messages from a Teams channel (most recent first).

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |
| `channel_id` | string | ✅ | The unique identifier of the channel |
| `limit` | integer | ❌ | Number of messages to return (default 20, max 50) |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `messages` | array | List of messages |
| `messages[].id` | string | Message ID |
| `messages[].body` | string | Text content of the message |
| `messages[].from` | string | Display name of the sender |
| `messages[].created_at` | string | ISO 8601 timestamp |

---

### get_message

Get a specific message from a Teams channel by its ID.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |
| `channel_id` | string | ✅ | The unique identifier of the channel |
| `message_id` | string | ✅ | The unique identifier of the message |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `message.id` | string | Message ID |
| `message.body` | string | Text content |
| `message.from` | string | Sender display name |
| `message.created_at` | string | ISO 8601 timestamp |

---

### send_channel_message

Send a message to a Teams channel.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |
| `channel_id` | string | ✅ | The unique identifier of the channel |
| `message` | string | ✅ | The text content to send |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the message was sent |
| `message_id` | string | ID of the sent message |

---

### list_members

List all members of a Microsoft Teams team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The unique identifier of the team |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `members` | array | List of members |
| `members[].id` | string | Membership ID |
| `members[].user_id` | string | Azure AD user ID |
| `members[].display_name` | string | Member display name |
| `members[].email` | string | Member email address |
| `members[].roles` | array | Roles held (e.g. `owner`) |

---

### add_member

Add a user to a Microsoft Teams team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The team to add the member to |
| `user_id` | string | ✅ | Azure AD user ID or email of the user |
| `role` | string | ❌ | `member` (default) or `owner` |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the member was added |
| `membership_id` | string | The new membership ID |

---

### remove_member

Remove a member from a Microsoft Teams team.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `team_id` | string | ✅ | The team to remove the member from |
| `membership_id` | string | ✅ | Membership ID from `list_members` |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the member was removed |

---

### list_chats

List all chats (1:1 and group) the authenticated user is part of.

**Inputs:** None

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `chats` | array | List of chats |
| `chats[].id` | string | Unique chat ID |
| `chats[].topic` | string | Chat topic or name |
| `chats[].chat_type` | string | `oneOnOne`, `group`, or `meeting` |

---

### list_chat_messages

List messages from a specific Teams chat.

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chat_id` | string | ✅ | The unique identifier of the chat |
| `limit` | integer | ❌ | Number of messages to return (default 20, max 50) |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the action succeeded |
| `messages` | array | List of messages |
| `messages[].id` | string | Message ID |
| `messages[].body` | string | Text content |
| `messages[].from` | string | Sender display name |
| `messages[].created_at` | string | ISO 8601 timestamp |

---

### send_chat_message

Send a message to a Teams chat (1:1 or group).

**Inputs:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chat_id` | string | ✅ | The unique identifier of the chat |
| `message` | string | ✅ | The text content to send |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Whether the message was sent |
| `message_id` | string | ID of the sent message |

---

## Requirements

- `autohive-integrations-sdk~=1.0.2`

## API Info

- **Base URL:** `https://graph.microsoft.com/v1.0`
- **Docs:** https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview
- **API Version:** v1.0

## Rate Limiting

Microsoft Graph enforces per-app throttling. If you hit limits, the API returns HTTP `429` with a `Retry-After` header. The integration will surface this as an error — retry after the specified delay.

## Error Handling

| Error | Cause |
|-------|-------|
| `401 Unauthorized` | Access token is expired or missing |
| `403 Forbidden` | Missing required permission scope or admin consent not granted |
| `404 Not Found` | The team, channel, chat, or message ID does not exist |
| `429 Too Many Requests` | API rate limit exceeded — check `Retry-After` header |

## Troubleshooting

**"403 Forbidden" on read_messages / list_messages**
→ `ChannelMessage.Read.All` requires admin consent. Ask your IT admin to approve the permission in Azure AD.

**"403 Forbidden" on add_member / remove_member**
→ `TeamMember.ReadWrite.All` requires admin consent.

**Sending messages returns 403**
→ Ensure the authenticated user is a member of the channel or chat. App-only (non-delegated) sending is not supported by Graph for regular messages.

**list_teams returns empty array**
→ The authenticated user is not a member of any team, or the account lacks a Teams licence.

**"404 Not Found" on a channel**
→ Private channels require the authenticated user to be a member of that specific private channel to access it.

## Version History

| Version | Notes |
|---------|-------|
| 1.0.0 | Initial release — 14 actions covering teams, channels, messages, members, and chats |
