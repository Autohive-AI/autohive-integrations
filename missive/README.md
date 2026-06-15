# Missive

Missive is a collaborative team inbox app that unifies email, SMS, WhatsApp, and live chat into shared conversations. This integration provides 22 actions covering conversations, messages, drafts, posts, contacts, and analytics.

## Auth Setup

1. Open Missive and go to **Preferences → API**
2. Click **Create a new token**
3. Copy the token (format: `missive_pat-...`)
4. Paste it into the **API Token** field when connecting

> **Note:** Token generation requires the **Productive plan** or higher.

## Actions

| Action | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `list_conversations` | List conversations by mailbox | `mailbox`, `limit`, `until` | `conversations[]` |
| `get_conversation` | Get a specific conversation | `conversation_id` | `conversation` |
| `update_conversation` | Update conversation state | `conversation_id`, `closed`, `assignee_id` | `result` |
| `merge_conversations` | Merge two conversations | `conversation_id`, `target_conversation_id` | `result` |
| `list_conversation_messages` | List messages in a conversation | `conversation_id` | `messages[]` |
| `list_conversation_comments` | List comments in a conversation | `conversation_id` | `comments[]` |
| `list_conversation_posts` | List posts in a conversation | `conversation_id` | `posts[]` |
| `list_conversation_drafts` | List drafts in a conversation | `conversation_id` | `drafts[]` |
| `list_messages` | List messages globally | `limit` | `messages[]` |
| `get_message` | Get a specific message | `message_id` | `message` |
| `create_message` | Create an incoming custom channel message | `channel_id`, `body` | `message` |
| `create_draft` | Create or send a draft | `channel_id`, `body`, `to`, `send` | `draft` |
| `delete_draft` | Delete a draft | `draft_id` | `result` |
| `create_post` | Inject a post and manage conversation state | `text`, `conversation_id`, `close` | `post`, `conversation` |
| `list_contacts` | List contacts with optional search | `search`, `contact_book_id` | `contacts[]` |
| `get_contact` | Get a specific contact | `contact_id` | `contact` |
| `create_contact` | Create one or more contacts | `contacts[]` | `contacts[]` |
| `update_contact` | Update a contact | `contact_id`, `first_name`, `infos` | `contact` |
| `list_contact_books` | List contact books | `limit` | `contact_books[]` |
| `list_contact_groups` | List groups in a contact book | `contact_book_id`, `kind` | `contact_groups[]` |
| `create_analytics_report` | Generate an analytics report (async) | `start`, `end`, `organization_id` | `report_id` |
| `get_analytics_report` | Retrieve a completed analytics report | `report_id` | `report` |

## API Info

- **Base URL:** `https://public.missiveapp.com/v1`
- **Docs:** https://missiveapp.com/docs/developers/rest-api
- **Rate limits:** 300 requests/minute, max 5 concurrent requests
- **Auth:** Bearer token in `Authorization` header

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Invalid or missing API token | Regenerate your token in Preferences → API |
| `401 Unauthorized` | Not on Productive plan | Upgrade your Missive plan |
| `429 Too Many Requests` | Rate limit exceeded | Wait for `Retry-After` seconds before retrying |
| Analytics returns 403 | Analytics requires Business plan for filtering | Remove `team_ids`/`user_ids` filters or upgrade plan |
| `update_conversation` / `update_contact` returns `Invalid resource ID(s)` | The API token owner must be an **Operator** (not just Member) of the Missive organization | Go to Settings → Organization → Members and promote the token owner to Operator |
| `update_contact` overwrites data | `infos` array is a full replacement | Always include the complete `infos` array when updating |
