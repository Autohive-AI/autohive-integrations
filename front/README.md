# Front Integration

Connects to the Front API to allow users to manage customer conversations, messages, and team collaboration directly from their workflows.

## Description

This integration provides comprehensive Front customer service functionality, enabling users to manage conversations, send messages, organize inboxes, and collaborate with team members. It supports conversation filtering, message threading, assignee management, and conversation tagging. The integration uses Front's platform authentication to securely access workspace resources.

Key features:
- List and manage inboxes and their channels
- List and filter conversations from specific inboxes
- View and send messages within conversations
- Create new messages and reply to existing conversations
- Access message templates for consistent responses
- Manage conversation assignments and status updates
- Support for CC/BCC messaging and conversation updates
- Optional author assignment using teammate IDs for message authorship control

## Setup & Authentication

The integration uses Front's OAuth2 platform authentication. Users need to authenticate through Front's OAuth flow within Autohive to grant workspace access permissions.

**Authentication Type:** Platform (Front)

**Required Scopes:**
- `Shared resources` - Access to workspace-wide conversations and data

No additional configuration fields are required as authentication is handled through Front's OAuth2 flow.

## Actions

### Inbox Management

#### Action: `list_inboxes`
- **Description:** List all accessible inboxes in the workspace
- **Inputs:**
  - `limit`: Maximum number of inboxes to return (optional, default: 50)
- **Outputs:**
  - `inboxes`: Array of inbox objects with ID, name, address, type, and send_as information
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `get_inbox`
- **Description:** Get details of a specific inbox
- **Inputs:**
  - `inbox_id`: The inbox ID to retrieve
- **Outputs:**
  - `inbox`: Inbox object with detailed information
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `list_inbox_conversations`
- **Description:** List conversations from a specific inbox with filtering options
- **Inputs:**
  - `inbox_id`: The inbox ID to get conversations from (required)
  - `status`: Filter by conversation status - archived, deleted, open, assigned, unassigned (optional)
  - `tag_id`: Filter conversations by tag ID (optional)
  - `limit`: Maximum number of conversations to return (optional, default: 50)
- **Outputs:**
  - `conversations`: Array of conversation objects with:
    - Required fields: `id`, `subject`, `status`
    - Optional fields: `status_id` (only present if ticketing is enabled), `status_category` (open/waiting/resolved), `ticket_ids`, `assignee`, `recipient`, `tags`, `links`, `scheduled_reminders`, `custom_fields`, `metadata`, `created_at`, `waiting_since`, `is_private`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Conversation Management

#### Action: `get_conversation`
- **Description:** Retrieve detailed information about a specific conversation including metadata
- **Inputs:**
  - `conversation_id`: The conversation ID to retrieve (required)
- **Outputs:**
  - `conversation`: Complete conversation object with:
    - Required fields: `id`, `subject`, `status`
    - Optional fields: `status_id` (only present if ticketing is enabled), `status_category` (open/waiting/resolved), `ticket_ids`, `assignee`, `recipient`, `tags`, `links`, `scheduled_reminders`, `custom_fields`, `metadata`, `created_at`, `waiting_since`, `is_private`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `update_conversation`
- **Description:** Update conversation properties including assignee, inbox, status, and tags
- **Inputs:**
  - `conversation_id`: The conversation ID to update (required)
  - `assignee_id`: ID of teammate to assign conversation to (optional, can be null to unassign)
  - `inbox_id`: ID of the inbox to move the conversation to (optional)
  - `status`: New conversation status - archived, deleted, open, spam (optional)
  - `status_id`: Unique identifier of the status to set. Only one of status and status_id should be provided. Ticketing must be enabled (optional)
  - `tags`: Array of all tag IDs replacing the old conversation tags (optional)
  - `custom_fields`: Custom fields for this conversation. Include all custom fields, not just ones to update (optional)
- **Outputs:**
  - `conversation`: Updated conversation object with fields including `id`, `subject`, `status`, `status_id`, `status_category`, `ticket_ids`, `assignee`, `recipient`, `tags`, `created_at`, `waiting_since`, `is_private`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Message Management

#### Action: `list_conversation_messages`
- **Description:** List all messages within a specific conversation with pagination support
- **Inputs:**
  - `conversation_id`: The conversation ID to get messages from (required)
  - `limit`: Maximum number of messages to return (optional, default: 50)
- **Outputs:**
  - `messages`: Array of message objects with:
    - Required fields: `id`, `type`, `is_inbound`, `author`
    - Optional fields: `recipients`, `subject`, `body`, `created_at`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `get_message`
- **Description:** Get details of a specific message including attachments metadata
- **Inputs:**
  - `message_id`: The message ID to retrieve (required)
- **Outputs:**
  - `message`: Message object with:
    - Required fields: `id`, `type`, `is_inbound`, `author`
    - Optional fields: `recipients`, `subject`, `body`, `created_at`, `attachments` (array with url, filename, content_type for each attachment)
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `download_message_attachment`
- **Description:** Download the content of a message attachment and return as base64-encoded data
- **Inputs:**
  - `attachment_url`: The URL of the attachment to download from message.attachments[].url (required)
- **Outputs:**
  - `file`: File object with base64-encoded content, name, contentType, and size
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)
- **Workflow:** Call `get_message` first to get attachment URLs, then use this action to download the file content

#### Action: `create_message`
- **Description:** Create a new message (starts new conversation) via a channel with optional file attachments
- **Inputs:**
  - `channel_id`: Channel ID to send from (required)
  - `body`: Message body content (required)
  - `to`: Array of recipient email addresses (required)
  - `cc`: Array of CC email addresses (optional)
  - `bcc`: Array of BCC email addresses (optional)
  - `sender_name`: Name used for the sender info of the message (optional)
  - `subject`: Message subject for email messages (optional)
  - `author_id`: ID of the teammate on behalf of whom the message is sent (optional)
  - `text`: Text version of the body for email messages (optional)
  - `signature_id`: ID of the signature to attach to this message (optional)
  - `should_add_default_signature`: Whether to add the default signature (optional)
  - `files`: Array of file attachments (optional) - upload files directly in the conversation
- **Outputs:**
  - `message_uid`: Temporary message UID for async processing
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `create_message_reply`
- **Description:** Reply to an existing conversation with optional file attachments
- **Inputs:**
  - `conversation_id`: The conversation ID to reply to (required)
  - `body`: Message body content (required)
  - `to`: Array of recipient email addresses (optional)
  - `cc`: Array of CC email addresses (optional)
  - `bcc`: Array of BCC email addresses (optional)
  - `sender_name`: Name used for the sender info of the message (optional)
  - `subject`: Message subject for email messages (optional)
  - `author_id`: ID of the teammate on behalf of whom the message is sent (optional)
  - `channel_id`: Channel ID the message is sent from (optional)
  - `text`: Text version of the body for email messages (optional)
  - `quote_body`: Body for the quote that the message is referencing (email channels only) (optional)
  - `signature_id`: ID of the signature to attach to this message (optional)
  - `should_add_default_signature`: Whether to add the default signature (optional)
  - `files`: Array of file attachments (optional) - upload files directly in the conversation
- **Outputs:**
  - `message_uid`: Temporary message UID for async processing
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Channel Management

#### Action: `list_channels`
- **Description:** List all channels in the account
- **Inputs:**
  - `limit`: Maximum number of channels to return (optional, default: 50)
- **Outputs:**
  - `channels`: Array of channel objects with ID, name, type, and settings
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `list_inbox_channels`
- **Description:** List channels for a specific inbox
- **Inputs:**
  - `inbox_id`: The inbox ID to get channels from
  - `limit`: Maximum number of channels to return (optional, default: 50)
- **Outputs:**
  - `channels`: Array of channel objects with ID, name, type, and settings
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `get_channel`
- **Description:** Get details of a specific channel
- **Inputs:**
  - `channel_id`: The channel ID to retrieve
- **Outputs:**
  - `channel`: Channel object with detailed information
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Message Templates

#### Action: `list_message_templates`
- **Description:** List all message templates available
- **Inputs:**
  - `limit`: Maximum number of templates to return (optional, default: 50)
- **Outputs:**
  - `templates`: Array of template objects with required fields: `id`, `name`, `subject`, `body`, `attachments`, `metadata`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `get_message_template`
- **Description:** Get details of a specific message template
- **Inputs:**
  - `message_template_id`: The message template ID to retrieve (required)
- **Outputs:**
  - `template`: Template object with required fields: `id`, `name`, `subject`, `body`, `attachments`, `metadata` (includes inbox availability)
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Team Management

#### Action: `list_teammates`
- **Description:** List all teammates in the workspace
- **Inputs:**
  - `limit`: Maximum number of teammates to return (optional, default: 50)
- **Outputs:**
  - `teammates`: Array of teammate objects with required fields: `id`, `email`, `username`, `first_name`, `last_name`, `is_admin`, `is_available`, `is_blocked`, `type` (user/visitor/rule/macro/API/integration/CSAT), `custom_fields`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `get_teammate`
- **Description:** Get details of a specific teammate by their ID
- **Inputs:**
  - `teammate_id`: The teammate ID to retrieve (required)
- **Outputs:**
  - `teammate`: Teammate object with required fields: `id`, `email`, `username`, `first_name`, `last_name`, `is_admin`, `is_available`, `is_blocked`, `type` (user/visitor/rule/macro/API/integration/CSAT), `custom_fields`
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Helper Actions

These actions provide convenient search functionality using client-side filtering, since the Front API doesn't support server-side search.

#### Action: `find_teammate`
- **Description:** Find teammates by searching name or email (case-insensitive partial match)
- **Inputs:**
  - `search_query`: Name or email to search for (case-insensitive, partial match supported) (required)
- **Outputs:**
  - `teammates`: Array of matching teammate objects with required fields: `id`, `email`, `first_name`, `last_name`
  - `count`: Number of matches found
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `find_inbox`
- **Description:** Find inboxes by name (case-insensitive partial match)
- **Inputs:**
  - `inbox_name`: Inbox name to search for (case-insensitive, partial match supported) (required)
- **Outputs:**
  - `inboxes`: Array of matching inbox objects with required fields: `id`, `name`, `address`
  - `count`: Number of matches found
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `find_conversation`
- **Description:** Find conversations by recipient name, email, or subject (case-insensitive partial match)
- **Inputs:**
  - `inbox_id`: The inbox ID to search in (required)
  - `search_query`: Search term for recipient name, email, or subject (case-insensitive, partial match) (required)
  - `limit`: Maximum number of conversations to search through (optional, default: 50)
- **Outputs:**
  - `conversations`: Array of matching conversation objects with required fields: `id`, `subject`, `status`
  - `count`: Number of matches found
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

## Requirements

- Python dependencies are handled by the Autohive platform
- Front API access
- Valid Front workspace with appropriate permissions

## Usage Examples

**Example 1: Find billing inbox and list its conversations**

Step 1 - List inboxes:
```json
{
  "limit": 25
}
```

Step 2 - List conversations from billing inbox:
```json
{
  "inbox_id": "inb_billing123",
  "status": "open",
  "limit": 10
}
```

**Example 2: Reply to a customer conversation with specific author**

Step 1 - List teammates to get author ID:
```json
{
  "limit": 25
}
```

Step 2 - Reply with specific teammate as author:
```json
{
  "conversation_id": "cnv_456",
  "body": "Thank you for reaching out! I'll help you resolve this issue right away.",
  "author_id": "tea_789"
}
```

**Example 3: Create new message using a channel with specific author**

Step 1 - List teammates to get author ID:
```json
{
  "limit": 25
}
```

Step 2 - Get inbox channels:
```json
{
  "inbox_id": "inb_billing123",
  "limit": 10
}
```

Step 3 - Create message via channel with specific author:
```json
{
  "channel_id": "cha_email123",
  "body": "Hello! We received your inquiry and will get back to you shortly.",
  "to": ["customer@example.com"],
  "subject": "Re: Your Support Request",
  "author_id": "tea_789"
}
```

**Example 4: Use message template for consistent responses**

Step 1 - List available templates:
```json
{
  "limit": 20
}
```

Step 2 - Get specific template:
```json
{
  "message_template_id": "tpl_456"
}
```

Step 3 - Use template content in reply:
```json
{
  "conversation_id": "cnv_456",
  "author_id": "tea_789",
  "body": "[Template body content with customizations]"
}
```

**Example 5: Assign conversation and add tags**

```json
{
  "conversation_id": "cnv_456",
  "assignee_id": "tea_789",
  "tags": ["tag_urgent", "tag_billing"]
}
```

**Example 6: Find teammate by name using helper action**

```json
{
  "search_query": "john"
}
```

This will return all teammates whose first name, last name, username, or email contains "john" (case-insensitive).

**Example 7: Find inbox by name using helper action**

```json
{
  "inbox_name": "support"
}
```

This will return all inboxes whose name contains "support" (case-insensitive).

**Example 8: Find conversations by subject or recipient using helper action**

```json
{
  "inbox_id": "inb_billing123",
  "search_query": "billing issue",
  "limit": 50
}
```

This will search through conversations in the specified inbox and return those whose subject or recipient contains "billing issue" (case-insensitive).

**Example 9: Download and forward message attachments**

Step 1 - Get message with attachments:
```json
{
  "message_id": "msg_789"
}
```

Step 2 - Download attachment from the message:
```json
{
  "attachment_url": "https://api2.frontapp.com/download/fil_abc123"
}
```

This returns a file object with base64-encoded content that can be used directly in `create_message` or `create_message_reply`.

Step 3 - Forward attachment in a reply:
Use the downloaded file's base64 content from Step 2 when creating a message or reply with the `files` parameter.

**Example 10: Send message with file attachments**

Step 1 - Upload files in the conversation interface (files will be available as `files` parameter)

Step 2 - Create message with attachments:
```json
{
  "channel_id": "cha_email123",
  "body": "Please find the requested documents attached.",
  "to": ["customer@example.com"],
  "subject": "Requested Documents",
  "author_id": "tea_789"
}
```

Note: Files uploaded in the conversation will automatically be attached to the message. The integration handles multipart/form-data encoding for attachments.

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd front`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the tests: `python tests/test_front.py`

Note: The tests use mock authentication and are designed for development validation. For production testing, ensure you have valid Front OAuth credentials configured.
