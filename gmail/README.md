# Gmail Integration for Autohive

Connects Autohive to the Gmail API to send, read, search, label, and organise email messages, threads, and drafts on behalf of an authenticated user.

## Description

This integration provides comprehensive Gmail functionality through Google's Gmail API v1. It supports the full email lifecycle — composing and sending plain-text or HTML messages with attachments, reading and replying to threads, managing drafts, applying and removing labels, and archiving messages.

HTML email bodies are sanitised with [`bleach`](https://github.com/mozilla/bleach) before sending to prevent XSS and to strip disallowed tags/attributes/protocols. A plain-text fallback is generated automatically from the sanitised HTML for maximum email-client compatibility.

Key features:

- Send plain-text or rich-HTML email with attachments, CC, and BCC
- Optional `signature` input on send/reply/draft actions appends a signature to the body with format-appropriate separators
- Reply to threads with automatic recipient and subject handling
- Draft lifecycle: create, update, list, get, send, delete
- Read inbox / all mail with read/unread filtering and pagination
- Read full threads and individual messages (with body, headers, and attachments)
- Time-window filtering via optional `after` / `before` (ISO 8601) inputs on `read_inbox`, `read_all_mail`, and `list_emails_by_label`, plus an optional raw `q` passthrough for power-user Gmail search operators
- Label management: list, create, apply, remove, list-by-label
- List per-send-as default signatures via `list_send_as_signatures`
- Archive and mark as read/unread in batch
- Pagination via `nextPageToken` on all list endpoints

## Setup & Authentication

The integration uses Google's platform OAuth 2.0 authentication. Users authenticate through the Google OAuth flow inside Autohive to grant access to their Gmail account.

**Authentication Type:** Platform (Gmail)

**Required Scopes:**

- `https://www.googleapis.com/auth/gmail.modify` — read, compose, send, and permanently delete email is **not** included; the scope allows full mailbox modification (labels, drafts, sending) but excludes permanent deletion of messages.

No additional configuration fields are required as authentication is handled through Google's OAuth 2.0 flow.

## Actions

The integration exposes 22 actions across messages, threads, drafts, labels, and settings.

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

### Settings

| Action | Description |
|---|---|
| `list_send_as_signatures` | List the user's send-as addresses (primary + aliases) with the signature bound to each as the new-mail default. The Gmail API does not expose the user's full saved-signatures library — only the per-send-as default. |

See [`config.json`](config.json) for the full input/output schema of every action.

## HTML Email Notes

When `body_format` is `"html"` on `send_email` / `reply_to_thread` / `create_draft`:

- The HTML body is sanitised by `bleach` against an allow-list of tags, attributes, and protocols.
- **Do not** include `<style>` blocks or `<script>` — they are stripped. Use inline `style="..."` attributes instead.
- A plain-text version is generated automatically from the sanitised HTML and sent as the `text/plain` alternative.

### Inline CSS policy

Inline `style` declarations are preserved, but only against an allow-list of visual-formatting properties
(`ALLOWED_CSS_PROPERTIES` in `gmail.py`): text and font, colour, `background-color`, the box model, borders,
`box-shadow` and `text-shadow`, and the table and list primitives that email templates rely on.

CSS animations are not supported and cannot be. `animation` requires an `@keyframes` rule and `transition`
requires a state selector, and both need a CSS rule block; `<style>` is not an allowed tag, because email clients
strip stylesheet blocks anyway. That is the reason the schemas ask for inline styles in the first place.

Declarations outside that list are dropped, and the rest of the `style` attribute is kept. Notable exclusions and why:

| Excluded | Reason |
|---|---|
| `background`, `background-image`, `list-style-image`, `cursor`, `border-image` | Take a `url()`, which fetches remote content and leaks the recipient's IP and open time, defeating the client's image blocking |
| `position`, `z-index`, `top`/`right`/`bottom`/`left`, `float`, `clip`, `transform` | Overlay and off-canvas tricks used to hide or spoof content |
| `opacity`, `visibility` | Conceal text from the reader while leaving it in the document |
| `behavior`, `expression`, `-moz-binding`, `filter` | Legacy script-execution vectors |
| `animation`, `transition`, `transform` | Need `@keyframes` or a selector, neither of which can exist in an inline `style` attribute, so they could never do anything |
| `fill`, `stroke`, `fill-opacity`, `stroke-opacity` and the rest of bleach's default SVG set | Outside the allow-list; the opacity variants hide content, and `<svg>` is not an allowed tag |

`CSSSanitizer` also keeps its own default SVG property allow-list independently of `allowed_css_properties`, so that is cleared explicitly (`allowed_svg_properties=[]`); otherwise eight SVG properties would survive despite not being listed below.

A property allow-list alone is not enough, because bleach's `CSSSanitizer` matches property *names* and never
inspects values: `background-color: url(...)` would otherwise survive on an allowed property. `EmailCSSSanitizer`
therefore also rejects any declaration whose value contains `url(`, `expression(`, `-moz-binding`, `javascript:` or
`vbscript:`.

This needs the `css` extra (`bleach[css]`), which pulls in `tinycss2`. Without a CSS sanitiser bleach warns
(`NoCssSanitizerWarning`) and silently empties every declaration, so allowing `style` without one means inline
styling is advertised but never delivered.

## Requirements

Pinned in [`requirements.txt`](requirements.txt):

- `autohive-integrations-sdk~=2.0.0`
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
