# Mailchimp Integration for Autohive

Production-ready Mailchimp integration for the Autohive platform, enabling management of mailing lists, audience members, and email campaigns through OAuth2 authentication.

## Overview

This integration provides comprehensive access to Mailchimp's Marketing API v3.0, allowing you to:

- Manage mailing lists (audiences)
- Add, update, and retrieve audience members
- Create and manage email campaigns
- Handle subscriber data and merge fields
- Track campaign performance

## Authentication

### OAuth2 Configuration

The integration uses **Platform OAuth2** (managed by Autohive) with the following specifications:

- **Authorization URL**: `https://login.mailchimp.com/oauth2/authorize`
- **Token URL**: `https://login.mailchimp.com/oauth2/token`
- **Metadata URL**: `https://login.mailchimp.com/oauth2/metadata`

### Critical OAuth2 Requirements

1. **No Scopes Required**: Mailchimp OAuth2 doesn't use scopes
2. **No Refresh Tokens**: Access tokens don't expire unless revoked by the user
3. **Dynamic Data Center**: The `dc` (data center) is fetched from the metadata endpoint after token exchange
4. **Dynamic Base URL**: API base URL is `https://{dc}.api.mailchimp.com/3.0/` where `{dc}` is obtained from metadata

### How Authentication Works

1. User authorizes the integration via Mailchimp OAuth2 flow
2. Autohive platform exchanges authorization code for access token
3. Integration fetches data center from metadata endpoint
4. All API requests use: `Authorization: Bearer {access_token}`

## Rate Limiting

Mailchimp API has the following rate limits:

- **Maximum 10 simultaneous connections**
- Returns HTTP 429 when rate limit is exceeded
- Integration implements automatic retry with exponential backoff
- Default retry delay: 60 seconds
- Maximum retries: 3 attempts

## Available Actions

### List Management

#### `get_lists`
Retrieve all mailing lists from Mailchimp account.

**Input Parameters:**
- `count` (integer, optional): Number of lists to return (default: 10, max: 1000)
- `offset` (integer, optional): Number of lists to skip for pagination

**Output:**
```json
{
  "result": true,
  "lists": [
    {
      "id": "abc123",
      "name": "Newsletter Subscribers",
      "stats": {
        "member_count": 1500,
        "unsubscribe_count": 25
      }
    }
  ],
  "total_items": 5
}
```

#### `get_list`
Get details of a specific mailing list.

**Input Parameters:**
- `list_id` (string, required): Mailchimp list ID

**Output:**
```json
{
  "result": true,
  "list": {
    "id": "abc123",
    "name": "Newsletter Subscribers",
    "stats": { ... }
  }
}
```

#### `create_list`
Create a new mailing list in Mailchimp.

**Input Parameters:**
- `name` (string, required): List name
- `permission_reminder` (string, required): Permission reminder text for subscribers
- `email_type_option` (boolean, optional): Whether to show email format options
- `contact` (object, required): Contact information
  - `company` (string, required)
  - `address1` (string, required)
  - `city` (string, required)
  - `state` (string, required)
  - `zip` (string, required)
  - `country` (string, required): 2-letter country code
- `campaign_defaults` (object, required): Default campaign values
  - `from_name` (string, required)
  - `from_email` (string, required)
  - `subject` (string, required)
  - `language` (string, required): e.g., "en"

**Output:**
```json
{
  "result": true,
  "list": {
    "id": "xyz789",
    "name": "New List"
  }
}
```

### Member Management

#### `add_member`
Add a new member to a mailing list.

**Input Parameters:**
- `list_id` (string, required): Mailchimp list ID
- `email_address` (string, required): Member's email address
- `status` (string, required): Subscription status - `subscribed`, `unsubscribed`, `cleaned`, or `pending`
- `merge_fields` (object, optional): Merge fields like `{"FNAME": "John", "LNAME": "Doe"}`
- `tags` (array, optional): Tags to add to the member

**Output:**
```json
{
  "result": true,
  "member": {
    "id": "member123",
    "email_address": "john@example.com",
    "status": "subscribed"
  }
}
```

#### `update_member`
Update an existing member in a mailing list.

**Input Parameters:**
- `list_id` (string, required): Mailchimp list ID
- `subscriber_hash` (string, optional): MD5 hash of lowercase email address
- `email_address` (string, optional): Email address (used to generate hash if subscriber_hash not provided)
- `status` (string, optional): New subscription status
- `merge_fields` (object, optional): Merge fields to update
- `tags` (array, optional): Tags to add

**Note:** Either `subscriber_hash` or `email_address` must be provided.

**Output:**
```json
{
  "result": true,
  "member": {
    "id": "member123",
    "email_address": "john@example.com",
    "status": "subscribed"
  }
}
```

#### `get_member`
Get details of a specific member in a mailing list.

**Input Parameters:**
- `list_id` (string, required): Mailchimp list ID
- `subscriber_hash` (string, optional): MD5 hash of lowercase email address
- `email_address` (string, optional): Email address (used to generate hash if subscriber_hash not provided)

**Output:**
```json
{
  "result": true,
  "member": {
    "id": "member123",
    "email_address": "john@example.com",
    "status": "subscribed",
    "merge_fields": {
      "FNAME": "John",
      "LNAME": "Doe"
    }
  }
}
```

#### `get_list_members`
Get all members from a mailing list.

**Input Parameters:**
- `list_id` (string, required): Mailchimp list ID
- `count` (integer, optional): Number of members to return (default: 10, max: 1000)
- `offset` (integer, optional): Number of members to skip for pagination
- `status` (string, optional): Filter by status - `subscribed`, `unsubscribed`, `cleaned`, or `pending`

**Output:**
```json
{
  "result": true,
  "members": [
    {
      "id": "member123",
      "email_address": "john@example.com",
      "status": "subscribed"
    }
  ],
  "total_items": 150
}
```

### Campaign Management

#### `get_campaigns`
Retrieve all campaigns from Mailchimp account.

**Input Parameters:**
- `count` (integer, optional): Number of campaigns to return (default: 10, max: 1000)
- `offset` (integer, optional): Number of campaigns to skip for pagination
- `status` (string, optional): Filter by status - `save`, `paused`, `schedule`, `sending`, or `sent`

**Output:**
```json
{
  "result": true,
  "campaigns": [
    {
      "id": "campaign123",
      "type": "regular",
      "status": "sent"
    }
  ],
  "total_items": 20
}
```

#### `create_campaign`
Create a new email campaign in Mailchimp.

**Input Parameters:**
- `type` (string, required): Campaign type - `regular`, `plaintext`, `absplit`, `rss`, or `variate`
- `list_id` (string, required): List ID to send the campaign to
- `subject_line` (string, required): Campaign subject line
- `from_name` (string, required): From name for the campaign
- `reply_to` (string, required): Reply-to email address
- `title` (string, optional): Campaign title (internal use)

**Output:**
```json
{
  "result": true,
  "campaign": {
    "id": "campaign456",
    "type": "regular",
    "status": "save"
  }
}
```

#### `get_campaign`
Get details of a specific campaign.

**Input Parameters:**
- `campaign_id` (string, required): Mailchimp campaign ID

**Output:**
```json
{
  "result": true,
  "campaign": {
    "id": "campaign123",
    "type": "regular",
    "status": "sent",
    "settings": { ... },
    "report_summary": { ... }
  }
}
```

## Error Handling

All actions return a consistent error format:

```json
{
  "result": false,
  "error": "Error message describing what went wrong"
}
```

### Common Error Scenarios

1. **Rate Limit Exceeded**
   ```json
   {
     "result": false,
     "error": "Rate limit exceeded. Retry after 60 seconds."
   }
   ```

2. **Missing Required Field**
   ```json
   {
     "result": false,
     "error": "list_id is required"
   }
   ```

3. **API Error**
   ```json
   {
     "result": false,
     "error": "Mailchimp API error: Invalid list ID"
   }
   ```

## Implementation Details

### Key Features

1. **Dynamic Data Center Handling**: Automatically fetches and uses the correct data center from OAuth2 metadata
2. **Automatic Rate Limiting**: Built-in retry logic with exponential backoff
3. **Email Hash Generation**: Automatically generates MD5 hashes for member operations when email is provided
4. **Comprehensive Error Handling**: Graceful error handling with informative error messages
5. **Pagination Support**: All list operations support pagination via `count` and `offset` parameters

### Technical Architecture

- **SDK**: Built on `autohive-integrations-sdk`
- **Async/Await**: All operations are asynchronous for optimal performance
- **Type Safety**: Full type hints for all functions and parameters
- **Rate Limiter**: Custom rate limiter class with configurable retry logic

### File Structure

```
mailchimp/
├── __init__.py                 # Empty initialization file
├── mailchimp.py                # Main integration implementation
├── config.json                 # Integration configuration and action schemas
├── requirements.txt            # Python dependencies
└── README.md                   # This documentation
```

## API Reference

### Mailchimp API Version
This integration uses **Mailchimp Marketing API v3.0**.

### Base URL
`https://{dc}.api.mailchimp.com/3.0/`

Where `{dc}` is the data center obtained from the metadata endpoint (e.g., `us19`, `us20`).

### Documentation
- [Mailchimp Marketing API Documentation](https://mailchimp.com/developer/marketing/api/)
- [Mailchimp OAuth2 Documentation](https://mailchimp.com/developer/marketing/guides/access-user-data-oauth-2/)

## Development

### Testing Locally

1. Ensure you have the SDK installed:
   ```bash
   pip install autohive-integrations-sdk
   ```

2. Load the integration:
   ```python
   from autohive_integrations_sdk import Integration
   integration = Integration.load("./mailchimp/config.json")
   ```

3. Execute an action:
   ```python
   result = await integration.execute_action(
       "get_lists",
       inputs={"count": 10},
       context=execution_context
   )
   ```

### Adding New Actions

1. Define the action schema in `config.json`
2. Implement the action handler class in `mailchimp.py`
3. Use the `@mailchimp.action("action_name")` decorator
4. Follow the existing pattern for error handling and rate limiting

## Security Considerations

1. **No Token Storage**: The integration never stores OAuth2 tokens - they are managed by the Autohive platform
2. **No Scopes**: Mailchimp OAuth2 doesn't use scopes, so all authenticated users have full account access
3. **HTTPS Only**: All API requests use HTTPS
4. **Input Validation**: All required inputs are validated before API calls

## Limitations

1. **No Refresh Tokens**: Access tokens don't expire unless revoked by the user
2. **Rate Limits**: Maximum 10 simultaneous connections
3. **No Scope Granularity**: Full account access is granted on OAuth2 authorization

## Support

For issues or questions:
- Review [Mailchimp API Documentation](https://mailchimp.com/developer/marketing/api/)
- Check [Autohive Integration Documentation](https://github.com/Autohive-AI/integrations-autohive)
- File an issue in the repository

## License

This integration is part of the Autohive integrations repository.

## Changelog

### Version 1.0.0 (Initial Release)
- OAuth2 authentication with dynamic data center support
- List management actions (get_lists, get_list, create_list)
- Member management actions (add_member, update_member, get_member, get_list_members)
- Campaign management actions (get_campaigns, create_campaign, get_campaign)
- Rate limiting with automatic retry
- Comprehensive error handling
