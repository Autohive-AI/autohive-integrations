# Gmail Integration for Autohive

Connects Autohive to the Gmail API to send, read, search, label, and organise email messages, threads, and drafts on behalf of an authenticated user.

## Description

This integration provides comprehensive Gmail functionality through Google's Gmail API v1. It supports the full email lifecycle — composing and sending plain-text or HTML messages with attachments, reading and replying to threads, managing drafts, applying and removing labels, and archiving messages.

HTML email bodies are sanitised with [`bleach`](https://github.com/mozilla/bleach) before sending to prevent XSS and to strip disallowed tags/attributes/protocols. A plain-text fallback is generated automatically from the sanitised HTML for maximum email-client compatibility.

Key features:

- Send plain-text or rich-HTML email with attachments, CC, and BCC
- Reply to threads with automatic recipient and subject handling
- Draft lifecycle: create, update, list, get, send, delete
- Read inbox / all mail with read/unread filtering and pagination
- Read full threads and individual messages (with body, headers, and attachments)
- Label management: list, create, apply, remove, list-by-label
- Archive and mark as read/unread in batch
- Pagination via `nextPageToken` on all list endpoints

## Setup & Authentication

The integration uses Google's platform OAuth 2.0 authentication. Users authenticate through the Google OAuth flow inside Autohive to grant access to their Gmail account.

**Authentication Type:** Platform (Gmail)

**Required Scopes:**

- `https://www.googleapis.com/auth/gmail.modify` — read, compose, send, and permanently delete email is **not** included; the scope allows full mailbox modification (labels, drafts, sending) but excludes permanent deletion of messages.

No additional configuration fields are required as authentication is handled through Google's OAuth 2.0 flow.

## Actions

The integration exposes 21 actions across messages, threads, drafts, and labels.

### Messages

| Action | Description |
|---|---|
| `send_email` | Send a new email (text or HTML) with optional CC/BCC and attachments |
| `read_email` | Retrieve a single message by ID, including body, headers, and attachments |
| `read_inbox` | List inbox messages, filtered by read/unread, with pagination |
| `read_all_mail` | List messages across the entire mailbox with read/unread filtering and pagination |
| `mark_emails_as_read` | Mark one or more messages as read |
| `mark_emails_as_unread` | Mark one or more messages as unread |
| `archive_emails` | Remove messages from the inbox (archive) |
| `get_user_info` | Get profile information for the authenticated Gmail user |

### Threads

| Action | Description |
|---|---|
| `reply_to_thread` | Reply to an existing thread, with text/HTML body, attachments, and optional additional recipients |
| `get_thread_emails` | Retrieve all messages in a thread |

### Drafts

| Action | Description |
|---|---|
| `create_draft` | Create a new draft, optionally as a reply to a thread/message |
| `update_draft` | Update an existing draft |
| `list_drafts` | List drafts with optional Gmail-search-syntax query and pagination |
| `get_draft` | Retrieve a single draft by ID |
| `send_draft` | Send a previously created draft |
| `delete_draft` | Delete a draft |

### Labels

| Action | Description |
|---|---|
| `list_labels` | List all labels in the mailbox |
| `create_label` | Create a new user label |
| `add_labels_to_emails` | Apply one or more labels to one or more messages |
| `remove_labels_from_emails` | Remove one or more labels from one or more messages |
| `list_emails_by_label` | List messages with a given label, paginated |

See [`config.json`](config.json) for the full input/output schema of every action.

## HTML Email Notes

When `body_format` is `"html"` on `send_email` / `reply_to_thread` / `create_draft`:

- The HTML body is sanitised by `bleach` against an allow-list of tags, attributes, and protocols.
- **Do not** include `<style>` blocks or `<script>` — they are stripped. Use inline `style="..."` attributes instead.
- A plain-text version is generated automatically from the sanitised HTML and sent as the `text/plain` alternative.

## Requirements

Pinned in [`requirements.txt`](requirements.txt):

- `autohive-integrations-sdk~=1.0.2`
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`
- `html2text`
- `bleach`

## Usage Examples

**Example 1: Send an HTML email with an attachment**

```json
{
  "to": ["alice@example.com"],
  "cc": ["bob@example.com"],
  "subject": "Q3 report",
  "body": "<p>Hi Alice,</p><p>Please find the Q3 report attached.</p>",
  "body_format": "html",
  "files": [
    {
      "name": "q3-report.pdf",
      "contentType": "application/pdf",
      "content": "JVBERi0xLjQK..."
    }
  ]
}
```

**Example 2: Reply to a thread**

```json
{
  "thread_id": "18dc14a8b32cb7e3",
  "message_id": "18dc14a8b32cb7e3",
  "body": "Thanks — confirmed on our side."
}
```

**Example 3: List unread inbox messages, page through results**

```json
{
  "user_id": "me",
  "scope": "unread"
}
```

Then on the next call, pass the `nextPageToken` from the previous response:

```json
{
  "user_id": "me",
  "scope": "unread",
  "pageToken": "0987654321"
}
```

## Testing

The `tests/` directory follows the public repo testing pattern. Unit tests (`test_*_unit.py`) are auto-discovered by pytest and run in CI; integration tests (`test_*_integration.py`) require live credentials and are opt-in. See the SDK's [writing-unit-tests](https://github.com/autohive-ai/integrations-sdk/blob/master/skills/writing-unit-tests/SKILL.md) and [writing-integration-tests](https://github.com/autohive-ai/integrations-sdk/blob/master/skills/writing-integration-tests/SKILL.md) skills for the full pattern.
