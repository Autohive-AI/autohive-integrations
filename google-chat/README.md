# Google Chat Integration for Autohive

Connects Autohive to Google Chat to enable sending messages, managing spaces, and interacting with conversations as a user.

## Description

This integration provides user-authenticated access to Google Chat (formerly Hangouts Chat), allowing users to automate their Google Chat interactions. Users can send messages, create and manage spaces, react to messages, and manage space memberships directly from Autohive workflows.

Key features:
- List and manage spaces (direct messages, group chats, named spaces)
- Send, list, update, and delete messages
- React to messages with emoji
- Manage space members
- Find direct message conversations

## Setup & Authentication

The integration uses Google's OAuth2 platform authentication. Users need to authenticate through Google's OAuth flow within Autohive to grant chat access permissions.

**Authentication Type:** Platform (Google Chat)

**Required Scopes:**
- `https://www.googleapis.com/auth/chat.messages` - Read and send messages
- `https://www.googleapis.com/auth/chat.spaces` - View and manage Chat spaces
- `https://www.googleapis.com/auth/chat.messages.reactions` - Add and remove message reactions

No additional configuration fields are required as authentication is handled through Google's OAuth2 flow.

## Actions

### Spaces (3 actions)

#### `list_spaces`
- **Description:** List all Google Chat spaces the user is a member of, including direct messages, group chats, and named spaces
- **Inputs:**
  - `page_size`: Maximum number of spaces to return (default: 100, max: 1000) (optional)
  - `page_token`: Page token for pagination from previous response (optional)
  - `filter`: Filter spaces by type (e.g., `spaceType = "SPACE"` for named spaces only) (optional)
- **Outputs:**
  - `spaces`: Array of space objects with name, display_name, space_type, and other properties
  - `next_page_token`: Token for retrieving the next page of results
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `get_space`
- **Description:** Get details about a specific Google Chat space including its properties and settings
- **Inputs:**
  - `space_name`: Resource name of the space (e.g., `spaces/AAAAMpdlehY`) (required)
- **Outputs:**
  - `space`: Complete space object with all properties
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `create_space`
- **Description:** Create a new Google Chat space with specified settings and initial members
- **Inputs:**
  - `display_name`: Display name for the new space (required)
  - `space_type`: Type of space to create (default: `SPACE`) (optional)
  - `space_details`: Object containing description and guidelines (optional)
- **Outputs:**
  - `space`: Created space object with name, display_name, and space_type
  - `result`: Success status
  - `error`: Error message (if operation failed)

### Messages (5 actions)

#### `send_message`
- **Description:** Send a text message to a Google Chat space. With user authentication, only text messages with basic formatting are supported
- **Inputs:**
  - `space_name`: Resource name of the space to send message to (required)
  - `text`: Text content of the message (supports @mentions, hyperlinks, and basic formatting) (required)
  - `thread_key`: Thread key to reply to a specific thread (optional)
  - `message_id`: Client-assigned message ID (must start with `client-`) (optional)
  - `message_reply_option`: How to handle replies in threaded spaces (optional)
- **Outputs:**
  - `message`: Sent message object with name, text, create_time, sender, and thread info
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `list_messages`
- **Description:** List messages from a Google Chat space with filtering and pagination options
- **Inputs:**
  - `space_name`: Resource name of the space (required)
  - `page_size`: Maximum number of messages to return (default: 25, max: 1000) (optional)
  - `page_token`: Page token for pagination (optional)
  - `filter`: Filter messages by timestamp (e.g., `createTime > "2023-04-21T11:30:00-04:00"`) (optional)
  - `order_by`: Sort order for messages (e.g., `createTime desc`) (optional)
  - `show_deleted`: Whether to include deleted messages (default: false) (optional)
- **Outputs:**
  - `messages`: Array of message objects
  - `next_page_token`: Token for next page of results
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `get_message`
- **Description:** Get details about a specific message in Google Chat
- **Inputs:**
  - `message_name`: Resource name of the message (e.g., `spaces/AAAAMpdlehY/messages/xyz`) (required)
- **Outputs:**
  - `message`: Complete message object with all properties
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `update_message`
- **Description:** Update a message that was previously sent. Only text content can be updated with user authentication
- **Inputs:**
  - `message_name`: Resource name of the message to update (required)
  - `text`: New text content for the message (required)
  - `update_mask`: Field mask specifying which fields to update (default: `text`) (optional)
- **Outputs:**
  - `message`: Updated message object
  - `result`: Success status
  - `error`: Error message (if operation failed)

Note: You can only update messages that you sent.

#### `delete_message`
- **Description:** Delete a message from Google Chat. Only messages sent by the authenticated user can be deleted
- **Inputs:**
  - `message_name`: Resource name of the message to delete (required)
  - `force`: When true, deletes message for all users. When false, only removes for the calling user (default: false) (optional)
- **Outputs:**
  - `result`: Success status
  - `error`: Error message (if operation failed)

### Members (1 action)

#### `list_members`
- **Description:** List all members in a Google Chat space, including users and Chat apps
- **Inputs:**
  - `space_name`: Resource name of the space (required)
  - `page_size`: Maximum number of members to return (default: 100, max: 1000) (optional)
  - `page_token`: Page token for pagination (optional)
  - `filter`: Filter members by role (e.g., `role="ROLE_MANAGER"`) (optional)
- **Outputs:**
  - `members`: Array of membership objects with name, member details, state, role, and timestamps
  - `next_page_token`: Token for next page of results
  - `result`: Success status
  - `error`: Error message (if operation failed)

### Reactions (3 actions)

#### `add_reaction`
- **Description:** Add an emoji reaction to a message in Google Chat
- **Inputs:**
  - `message_name`: Resource name of the message to react to (required)
  - `emoji`: Emoji object containing either unicode (e.g., `👍`) or custom_emoji with uid (required)
- **Outputs:**
  - `reaction`: Created reaction object
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `list_reactions`
- **Description:** List all reactions on a specific message in Google Chat
- **Inputs:**
  - `message_name`: Resource name of the message (required)
  - `page_size`: Maximum number of reactions to return (default: 25, max: 1000) (optional)
  - `page_token`: Page token for pagination (optional)
  - `filter`: Filter reactions by emoji (optional)
- **Outputs:**
  - `reactions`: Array of reaction objects
  - `next_page_token`: Token for next page of results
  - `result`: Success status
  - `error`: Error message (if operation failed)

#### `remove_reaction`
- **Description:** Remove an emoji reaction from a message in Google Chat
- **Inputs:**
  - `reaction_name`: Resource name of the reaction to remove (required)
- **Outputs:**
  - `result`: Success status
  - `error`: Error message (if operation failed)

### Utilities (1 action)

#### `find_direct_message`
- **Description:** Find an existing direct message conversation with another user, or returns details to create one
- **Inputs:**
  - `user_name`: Resource name of the user to find DM with (e.g., `users/example@gmail.com`) (required)
- **Outputs:**
  - `space`: Direct message space object
  - `result`: Success status
  - `error`: Error message (if operation failed)

## Requirements

- Python dependencies are handled by the Autohive platform
- Google Chat API access
- Valid Google account with chat permissions

## Usage Examples

**Example 1: Send a message to a space**

```json
{
  "space_name": "spaces/AAAAMpdlehY",
  "text": "Hello team! This is an automated message from Autohive."
}
```

**Example 2: List recent messages from a space**

```json
{
  "space_name": "spaces/AAAAMpdlehY",
  "page_size": 10,
  "order_by": "createTime desc"
}
```

**Example 3: Create a new space**

```json
{
  "display_name": "Project Alpha Team",
  "space_details": {
    "description": "Collaboration space for Project Alpha",
    "guidelines": "Please keep discussions relevant to the project"
  }
}
```

**Example 4: Add a reaction to a message**

```json
{
  "message_name": "spaces/AAAAMpdlehY/messages/xyz",
  "emoji": {
    "unicode": "👍"
  }
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd google-chat`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the tests: `python tests/test_google_chat.py`
