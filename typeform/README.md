# Typeform Integration for Autohive

Connects Autohive to the Typeform API for managing forms, responses, workspaces, themes, images, and webhooks.

## Description

This integration provides comprehensive access to Typeform's form building and data collection platform. It allows users to create and manage forms, retrieve responses, organize workspaces, customize themes, manage images, and configure webhooks programmatically.

The integration uses Typeform REST API with OAuth 2.0 authentication and implements 24 actions covering all major Typeform operations.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your Typeform account.

### Authentication Method

The integration uses OAuth 2.0 with the following scopes:
- `accounts:read` - Read account information
- `forms:read` - Access form lists and details
- `forms:write` - Create, update, and delete forms
- `responses:read` - Retrieve form submissions
- `responses:write` - Delete form submissions
- `workspaces:read` - Access workspace data
- `workspaces:write` - Create and modify workspaces
- `themes:read` - Access theme information
- `themes:write` - Create and modify themes
- `images:read` - Retrieve images
- `images:write` - Add and remove images
- `webhooks:read` - View webhook configurations
- `webhooks:write` - Create and manage webhooks
- `offline` - Receive refresh token for long-term access

### Setup Steps in Autohive

1. Add Typeform integration in Autohive
2. Click "Connect to Typeform" to authorize the integration
3. Sign in to your Typeform account when prompted
4. Review and authorize the requested permissions
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh (tokens expire after 1 week and are automatically refreshed).

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields

## Rate Limit Handling

Typeform API has rate limits that can require 30+ second waits. Since this exceeds Lambda timeout limits, the integration returns structured rate limit information instead of retrying internally.

### Rate Limit Response

When a 429 (rate limit) error occurs, the action returns:

```json
{
  "result": false,
  "error": "Rate limit exceeded. Please wait 37 seconds before retrying...",
  "error_type": "rate_limit",
  "retry_after_seconds": 37,
  "retry_attempt": 0,
  "max_retries": 3,
  "can_retry": true,
  "retry_instructions": "To retry: wait at least 37 seconds, then call this action again with _retry_attempt=1..."
}
```

### Retry Mechanism

All actions accept an optional `_retry_attempt` parameter:

1. **First call**: Omit `_retry_attempt` or set to `0`
2. **On rate limit**: Wait `retry_after_seconds`, then call with `_retry_attempt=1`
3. **Continue**: Increment `_retry_attempt` on each retry
4. **Max retries**: After 3 retries, `can_retry` becomes `false`

### Agent Instructions

For agents using this integration, include guidance like:

> "If a Typeform action returns `error_type: 'rate_limit'`, wait the specified `retry_after_seconds` and retry with `_retry_attempt` incremented. Do not retry more than 3 times."

## Actions (24 Total)

### User (1 action)

#### `get_current_user`
Get information about the authenticated user account.

**Inputs:** None

**Outputs:**
- `user`: User account information including user_id, email, alias, and language
- `result`: Success status

---

### Forms (5 actions)

#### `list_forms`
List all forms in your account with optional filtering.

**Inputs:**
- `workspace_id` (optional): Filter forms by workspace ID
- `search` (optional): Search forms by title
- `page` (optional): Page number for pagination
- `page_size` (optional): Number of forms per page (max 200)

**Outputs:**
- `forms`: Array of form objects with id, title, and metadata
- `total_items`: Total number of forms
- `result`: Success status

---

#### `get_form`
Get detailed information about a specific form.

**Inputs:**
- `form_id` (required): The unique identifier of the form

**Outputs:**
- `form`: Form details including fields, settings, theme, and logic
- `result`: Success status

---

#### `create_form`
Create a new form with specified title, fields, and settings.

**Inputs:**
- `title` (required): Title of the form
- `workspace_id` (optional): Workspace ID to create the form in
- `fields` (optional): Array of field objects defining the form questions
- `settings` (optional): Form settings (language, is_public, progress_bar, etc.)
- `theme_id` (optional): Theme ID to apply to the form
- `welcome_screens` (optional): Welcome screen configurations
- `thankyou_screens` (optional): Thank you screen configurations

**Outputs:**
- `form`: Created form details including id and _links
- `result`: Success status

---

#### `update_form`
Update an existing form's title, fields, settings, or theme.

**Inputs:**
- `form_id` (required): The unique identifier of the form to update
- `title` (optional): New title for the form
- `fields` (optional): Updated array of field objects
- `settings` (optional): Updated form settings
- `theme_id` (optional): New theme ID to apply
- `welcome_screens` (optional): Updated welcome screen configurations
- `thankyou_screens` (optional): Updated thank you screen configurations

**Outputs:**
- `form`: Updated form details
- `result`: Success status

---

#### `delete_form`
Delete a form permanently.

**Inputs:**
- `form_id` (required): The unique identifier of the form to delete

**Outputs:**
- `deleted`: Whether the form was deleted
- `result`: Success status

---

### Responses (2 actions)

#### `list_responses`
Retrieve responses for a form with optional filtering.

**Inputs:**
- `form_id` (required): The unique identifier of the form
- `page_size` (optional): Number of responses per page (max 1000, default 25)
- `since` (optional): Filter responses submitted after this date (ISO 8601)
- `until` (optional): Filter responses submitted before this date (ISO 8601)
- `after` (optional): Pagination cursor - response token to start after
- `before` (optional): Pagination cursor - response token to end before
- `completed` (optional): Filter by completion status
- `sort` (optional): Sort order (e.g., 'submitted_at,desc')
- `query` (optional): Search responses by text content
- `fields` (optional): Comma-separated list of field IDs to include

**Outputs:**
- `responses`: Array of form responses with answers, metadata, and timestamps
- `total_items`: Total number of responses
- `page_count`: Total number of pages
- `result`: Success status

---

#### `delete_responses`
Delete responses from a form by response IDs.

**Inputs:**
- `form_id` (required): The unique identifier of the form
- `included_response_ids` (required): Comma-separated list of response IDs to delete

**Outputs:**
- `deleted`: Whether the responses were deleted
- `result`: Success status

---

### Workspaces (5 actions)

#### `list_workspaces`
List all workspaces in your account.

**Inputs:**
- `search` (optional): Search workspaces by name
- `page` (optional): Page number for pagination
- `page_size` (optional): Number of workspaces per page (max 200)

**Outputs:**
- `workspaces`: Array of workspaces with id, name, and metadata
- `total_items`: Total number of workspaces
- `result`: Success status

---

#### `get_workspace`
Get details of a specific workspace.

**Inputs:**
- `workspace_id` (required): The unique identifier of the workspace

**Outputs:**
- `workspace`: Workspace details including name, forms, and members
- `result`: Success status

---

#### `create_workspace`
Create a new workspace.

**Inputs:**
- `name` (required): Name of the workspace

**Outputs:**
- `workspace`: Created workspace details
- `result`: Success status

---

#### `update_workspace`
Update a workspace's name.

**Inputs:**
- `workspace_id` (required): The unique identifier of the workspace
- `name` (required): New name for the workspace

**Outputs:**
- `workspace`: Updated workspace details
- `result`: Success status

---

#### `delete_workspace`
Delete a workspace.

**Inputs:**
- `workspace_id` (required): The unique identifier of the workspace to delete

**Outputs:**
- `deleted`: Whether the workspace was deleted
- `result`: Success status

---

### Themes (4 actions)

#### `list_themes`
List all themes in your account.

**Inputs:**
- `page` (optional): Page number for pagination
- `page_size` (optional): Number of themes per page (max 200)

**Outputs:**
- `themes`: Array of themes with id, name, colors, and fonts
- `total_items`: Total number of themes
- `result`: Success status

---

#### `get_theme`
Get details of a specific theme.

**Inputs:**
- `theme_id` (required): The unique identifier of the theme

**Outputs:**
- `theme`: Theme details including colors, fonts, and background
- `result`: Success status

---

#### `create_theme`
Create a new theme with custom colors, fonts, and background.

**Inputs:**
- `name` (required): Name of the theme
- `colors` (optional): Color settings (question, answer, button, background)
- `font` (optional): Font family to use
- `has_transparent_button` (optional): Whether buttons should be transparent
- `background` (optional): Background settings (image_id, layout, brightness)

**Outputs:**
- `theme`: Created theme details
- `result`: Success status

---

#### `delete_theme`
Delete a theme.

**Inputs:**
- `theme_id` (required): The unique identifier of the theme to delete

**Outputs:**
- `deleted`: Whether the theme was deleted
- `result`: Success status

---

### Images (3 actions)

#### `list_images`
List all images in your account.

**Inputs:**
- `page` (optional): Page number for pagination
- `page_size` (optional): Number of images per page

**Outputs:**
- `images`: Array of images with id, src, file_name, and dimensions
- `total_items`: Total number of images
- `result`: Success status

---

#### `get_image`
Get details of a specific image.

**Inputs:**
- `image_id` (required): The unique identifier of the image

**Outputs:**
- `image`: Image details including src, file_name, width, height
- `result`: Success status

---

#### `delete_image`
Delete an image from your account.

**Inputs:**
- `image_id` (required): The unique identifier of the image to delete

**Outputs:**
- `deleted`: Whether the image was deleted
- `result`: Success status

---

### Webhooks (4 actions)

#### `list_webhooks`
List all webhooks for a form.

**Inputs:**
- `form_id` (required): The unique identifier of the form

**Outputs:**
- `webhooks`: Array of webhooks with tag, url, enabled status
- `result`: Success status

---

#### `get_webhook`
Get details of a specific webhook.

**Inputs:**
- `form_id` (required): The unique identifier of the form
- `tag` (required): The webhook tag/identifier

**Outputs:**
- `webhook`: Webhook details including url, enabled, created_at
- `result`: Success status

---

#### `create_webhook`
Create or update a webhook for a form.

**Inputs:**
- `form_id` (required): The unique identifier of the form
- `tag` (required): Unique tag/identifier for the webhook
- `url` (required): The webhook endpoint URL to receive payloads
- `enabled` (optional): Whether the webhook is enabled (default true)
- `secret` (optional): Secret for HMAC SHA256 signature verification

**Outputs:**
- `webhook`: Created/updated webhook details
- `result`: Success status

---

#### `delete_webhook`
Delete a webhook from a form.

**Inputs:**
- `form_id` (required): The unique identifier of the form
- `tag` (required): The webhook tag/identifier to delete

**Outputs:**
- `deleted`: Whether the webhook was deleted
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **Base URL**: `https://api.typeform.com`
- **Authentication**: OAuth 2.0
- **Documentation**: https://www.typeform.com/developers/
- **Token Expiry**: Access tokens expire after 1 week

## Supported Field Types

Typeform supports 24+ question types including:
- `short_text`, `long_text` - Text inputs
- `multiple_choice`, `dropdown` - Selection inputs
- `yes_no`, `legal` - Boolean inputs
- `rating`, `opinion_scale`, `nps` - Scale inputs
- `email`, `phone_number`, `website` - Contact inputs
- `date`, `number` - Data inputs
- `file_upload` - File inputs
- `payment` - Payment processing
- `group`, `matrix` - Complex inputs
- `statement` - Information display

## Common Use Cases

**Form Management:**
- Create survey forms programmatically
- Update form questions and settings
- Organize forms into workspaces

**Response Collection:**
- Retrieve form submissions
- Filter responses by date or completion status
- Search response content

**Automation:**
- Set up webhooks for real-time notifications
- Trigger workflows on form submission
- Sync responses with external systems

**Branding:**
- Create custom themes for consistent branding
- Manage image assets for forms
- Apply themes across multiple forms

## Version History

- **1.1.0** - Rate limit handling
  - Added structured rate limit responses for all actions
  - Added `_retry_attempt` parameter for retry tracking
  - Returns `error_type: 'rate_limit'` with `retry_after_seconds` on 429 errors
  - Supports up to 3 automatic retries with LLM coordination

- **1.0.0** - Initial release with 24 actions
  - User: get_current_user (1 action)
  - Forms: list, get, create, update, delete (5 actions)
  - Responses: list, delete (2 actions)
  - Workspaces: list, get, create, update, delete (5 actions)
  - Themes: list, get, create, delete (4 actions)
  - Images: list, get, delete (3 actions)
  - Webhooks: list, get, create, delete (4 actions)

## Sources

- [Typeform Developer Platform](https://www.typeform.com/developers/)
- [Typeform API Reference](https://www.typeform.com/developers/get-started/)
- [OAuth 2.0 Scopes](https://www.typeform.com/developers/get-started/scopes/)
- [Create API](https://www.typeform.com/developers/create/)
- [Responses API](https://www.typeform.com/developers/responses/)
- [Webhooks API](https://www.typeform.com/developers/webhooks/)
