# WhatsApp Business Integration for Autohive

Connects Autohive to the WhatsApp Business API to allow users to send messages, templates, media content, and manage conversations through Meta's Graph API.

## Description

This integration provides comprehensive WhatsApp Business API functionality, enabling automated messaging capabilities through Autohive workflows. It supports text messages, pre-approved templates, media sharing (images, documents, audio, video), and contact validation. The integration uses Meta's Graph API v18.0 and requires a WhatsApp Business Account with proper API access.

## Setup & Authentication

Configure the integration within Autohive using platform authentication for WhatsApp Business API access through Meta Business Manager.

**Authentication Type:** Platform (OAuth2)
**Provider:** WhatsApp
**Required Scopes:**
- `whatsapp_business_messaging`
- `whatsapp_business_management`

**Authentication Fields:**
- `access_token`: Meta Graph API access token with WhatsApp permissions
- `phone_number_id`: Phone Number ID from Meta Business Manager WhatsApp settings

**Setup Steps:**
1. Create a WhatsApp Business Account through Meta Business Manager
2. Configure WhatsApp Business API access in your Meta Business Account
3. Set up and verify a phone number for business messaging
4. Generate an access token with the required WhatsApp permissions
5. Copy the Phone Number ID from WhatsApp Business API settings

## Actions

### Action: `send_message`

- **Description:** Send a text message to a WhatsApp contact using the Business API
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format (e.g., +1234567890)
  - `message` (required): Text content of the message to send
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier if successful
  - `success`: Boolean indicating if the message was sent successfully
  - `error`: Error description if the operation failed

### Action: `send_template_message`

- **Description:** Send a pre-approved template message with optional parameters
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format
  - `template_name` (required): Name of the approved message template
  - `language_code` (optional): Template language code (default: "en")
  - `parameters` (optional): Array of string parameters for template substitution
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier if successful
  - `success`: Boolean indicating if the template message was sent
  - `error`: Error description if the operation failed

### Action: `send_media_message`

- **Description:** Send media content (image, document, audio, video) to a WhatsApp contact
- **Inputs:**
  - `to` (required): Recipient's phone number in E.164 format
  - `media_type` (required): Media type - "image", "document", "audio", or "video"
  - `media_url` (required): HTTPS URL of the media content to send
  - `caption` (optional): Text caption for the media (images, videos, documents)
  - `filename` (optional): Custom filename for document type media
- **Outputs:**
  - `message_id`: Unique WhatsApp message identifier if successful
  - `success`: Boolean indicating if the media message was sent
  - `error`: Error description if the operation failed

### Action: `get_phone_number_health`

- **Description:** Retrieve the health status and quality rating of the WhatsApp Business phone number.
- **Inputs:**
  - `phone_number_id` (required): The Phone Number ID associated with the WhatsApp Business account.
- **Outputs:**
  - `status`: Connection status of the phone number (e.g., "CONNECTED", "PENDING", "OFFLINE").
  - `quality_rating`: Quality rating of the phone number (e.g., "GREEN", "YELLOW", "RED", "UNKNOWN").
  - `success`: Boolean indicating if the operation completed successfully.
  - `error`: Error description if the operation failed.

## Requirements

- `autohive-integrations-sdk`
- `requests>=2.32.0`
- `aiohttp>=3.8.0`

## Usage Examples

**Example 1: Send a welcome message to a new customer**

```json
{
  "to": "+1234567890",
  "message": "Welcome to our service! Thank you for signing up."
}
```

**Example 2: Send a template message with customer name**

```json
{
  "to": "+1234567890",
  "template_name": "customer_welcome",
  "language_code": "en",
  "parameters": ["John Doe", "Premium"]
}
```

**Example 3: Send an invoice document**

```json
{
  "to": "+1234567890",
  "media_type": "document",
  "media_url": "https://yourdomain.com/invoices/invoice-123.pdf",
  "filename": "Invoice-123.pdf",
  "caption": "Your invoice for Order #123"
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd whatsapp`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run the tests: `python tests/test_whatsapp.py`

The test suite includes:
- Message sending validation
- Template message functionality
- Media message handling
- Contact information retrieval
- Phone number health check
- Phone number format validation

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