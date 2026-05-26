# WhatsApp Business Integration for Autohive

Connects Autohive to the WhatsApp Business API to send text messages, pre-approved templates, and media content, and to read WhatsApp Business phone-number health, through Meta's Graph API.

## Description

This integration provides WhatsApp Business API functionality for automated messaging through Autohive workflows. It supports text messages, pre-approved templates, media sharing (images, documents, audio, video), and retrieving the connection status and quality rating of a WhatsApp Business phone number. The integration uses Meta's Graph API v18.0 and requires a WhatsApp Business Account with proper API access.

## Setup & Authentication

Configure the integration within Autohive using platform authentication for WhatsApp Business API access through Meta Business Manager.

**Authentication Type:** Platform (OAuth2)
**Provider:** WhatsApp Business
**Required Scopes:**
- `whatsapp_business_messaging`
- `whatsapp_business_management`

Authentication itself is handled by Autohive's platform OAuth flow — the access token is injected at execution time, not configured by the user. Every action additionally takes a `phone_number_id` input (the Phone Number ID from Meta Business Manager) to route messages from the correct WhatsApp Business number.

**Setup Steps:**
1. Create a WhatsApp Business Account through Meta Business Manager
2. Configure WhatsApp Business API access in your Meta Business Account
3. Set up and verify a phone number for business messaging
4. Connect the WhatsApp Business provider in Autohive (grants the required scopes)
5. Copy the Phone Number ID from WhatsApp Business API settings — you'll pass it as the `phone_number_id` input on each action

## Actions

**Error handling:** On failure, actions return an `ActionError` with a `message` field (e.g. `"Invalid phone number format"`, `"Object does not exist"`). On success, `data` contains only the documented output fields listed below — there is no `success` boolean or `error` string in the payload.

### Action: `send_message`

- **Description:** Send a text message to a WhatsApp contact using the Business API
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format (e.g., +1234567890)
  - `message` (required): Text content of the message to send
  - `phone_number_id` (required): The Phone Number ID associated with the WhatsApp Business account
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier

### Action: `send_template_message`

- **Description:** Send a pre-approved template message with optional parameters
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format
  - `template_name` (required): Name of the approved message template
  - `phone_number_id` (required): The Phone Number ID associated with the WhatsApp Business account
  - `language_code` (required): Language code matching the approved template locale (e.g., `en_US`, `es`, `pt_BR`). Templates are approved per-locale on Meta, so this must match the locale you submitted (Meta's built-in `hello_world` template, for example, only exists in `en_US`).
  - `parameters` (optional): Array of string parameters for template substitution
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier

### Action: `send_media_message`

- **Description:** Send media content (image, document, audio, video) to a WhatsApp contact
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format
  - `media_type` (required): Media type - "image", "document", "audio", or "video"
  - `media_url` (required): HTTPS URL of the media content to send
  - `phone_number_id` (required): The Phone Number ID associated with the WhatsApp Business account
  - `caption` (optional): Text caption for the media (images, videos, documents)
  - `filename` (optional): Custom filename for document type media
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier

### Action: `get_phone_number_health`

- **Description:** Retrieve the health status and quality rating of the WhatsApp Business phone number.
- **Inputs:**
  - `phone_number_id` (required): The Phone Number ID associated with the WhatsApp Business account.
- **Outputs:**
  - `status`: Connection status of the phone number (e.g., "CONNECTED", "PENDING", "OFFLINE").
  - `quality_rating`: Quality rating of the phone number (e.g., "GREEN", "YELLOW", "RED", "UNKNOWN").

## Requirements

- `autohive-integrations-sdk`

## Usage Examples

**Example 1: Send a welcome message to a new customer**

```json
{
  "to": "+1234567890",
  "message": "Welcome to our service! Thank you for signing up.",
  "phone_number_id": "123456789012345"
}
```

**Example 2: Send a template message with customer name**

```json
{
  "to": "+1234567890",
  "template_name": "customer_welcome",
  "phone_number_id": "123456789012345",
  "language_code": "en_US",
  "parameters": ["John Doe", "Premium"]
}
```

**Example 3: Send an invoice document**

```json
{
  "to": "+1234567890",
  "media_type": "document",
  "media_url": "https://yourdomain.com/invoices/invoice-123.pdf",
  "phone_number_id": "123456789012345",
  "filename": "Invoice-123.pdf",
  "caption": "Your invoice for Order #123"
}
```

Note: Only media via a Public URL is supported through the WhatsApp API. Not locally uploaded media (e.g. through an agent chat). Images and PDF's can be sent.

## Testing

The integration ships with two test suites:

- **Unit tests** (`tests/test_whatsapp_unit.py`) — no network, no credentials. Use `FetchResponse` to fake Graph API responses. Safe to run anywhere, including CI.
- **Integration tests** (`tests/test_whatsapp_integration.py`) — hit the real WhatsApp Cloud (Facebook Graph) API. Require a valid Meta access token and a business phone number ID (see `.env.example`).

Install dependencies first:

```bash
pip install -r requirements.txt
```

### Run unit tests

```bash
pytest whatsapp/tests/test_whatsapp_unit.py -v
```

The repo's default pytest filter (`-m unit`) excludes integration tests, and `test_*_integration.py` is not matched by `python_files`, so integration tests never run in CI by accident.

### Run integration tests

Set the `WHATSAPP_*` environment variables (see `.env.example` for the full list — at minimum `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`, plus `WHATSAPP_RECIPIENT_PHONE` / `WHATSAPP_MEDIA_URL` for destructive tests). Then:

```bash
# Read-only tests (safe — phone number health + validation paths only)
pytest whatsapp/tests/test_whatsapp_integration.py -m "integration and not destructive"

# Destructive tests (sends real messages to WHATSAPP_RECIPIENT_PHONE — review first!)
pytest whatsapp/tests/test_whatsapp_integration.py -m "integration and destructive"
```

Tests that need a specific env var will be `skip`-ed automatically when the var is missing, so you can run a subset by exporting only the vars you care about.

## Error Handling

The integration handles various error scenarios:
- Invalid phone number formats (validates E.164 format)
- WhatsApp API authentication failures
- Network connectivity issues
- Invalid template names or missing parameters
- Unsupported media types or inaccessible media URLs
- Rate limit exceeded responses
- Recipient not registered with WhatsApp Business API

## Rate Limits

WhatsApp Business API enforces the following rate limits:
- **Messaging Rate:** 1,000 messages per second per phone number
- **Daily Limits:** Based on business verification status (Unverified: 250, Verified: 1,000+)
- **Template Approval:** New templates require approval through Meta Business Manager

## Additional Notes

- Phone numbers must be in E.164 international format (e.g., +1234567890)
- Template messages require pre-approval through Meta Business Manager before use
- Media files must be publicly accessible via HTTPS URLs and meet WhatsApp's file size limits
- The integration uses WhatsApp Business API version 18.0
- Message delivery status tracking requires webhook configuration (not included in this integration)
- Business accounts have different messaging windows and capabilities compared to personal WhatsApp