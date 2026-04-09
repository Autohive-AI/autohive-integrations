# Heartbeat Integration for Autohive

Connects Autohive to the Heartbeat.chat API to allow users to retrieve channel information, manage threads and comments, access user data, and view community events.

## Description

This integration provides comprehensive access to Heartbeat.chat community data through their API. It enables users to:

- Retrieve channels and their details
- Access threads within channels and create new ones
- Manage comments on threads
- Get user information and community member data
- View community events and their details

The integration interacts with the Heartbeat.chat API v0 to provide standardized data structures for all community content.

## Setup & Authentication

To configure this integration in Autohive, you'll need a Heartbeat.chat Bearer token with appropriate permissions.

**Authentication Fields:**

*   `api_key`: Your Heartbeat.chat Bearer token (API key)

To obtain your API key:
1. Log into your Heartbeat.chat community
2. Navigate to your account settings or developer settings
3. Generate or copy your API Bearer token
4. Use this token as the `api_key` in the Autohive integration configuration

## Actions

### Action: `get_heartbeat_channels`

*   **Description:** Retrieve a list of all channels in the Heartbeat community
*   **Inputs:** None required
*   **Outputs:**
    *   `channels`: Array of channel objects with id, name, description, channelCategoryID, and private status
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_channel`

*   **Description:** Get detailed information about a specific channel
*   **Inputs:**
    *   `channel_id`: The ID of the channel to retrieve
*   **Outputs:**
    *   `channel`: Channel object with detailed information
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_channel_threads`

*   **Description:** Retrieve all threads from a specific channel
*   **Inputs:**
    *   `channel_id`: The ID of the channel to get threads from
*   **Outputs:**
    *   `threads`: Array of thread objects with id, title, content, author information, and timestamps
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_thread`

*   **Description:** Get detailed information about a specific thread
*   **Inputs:**
    *   `thread_id`: The ID of the thread to retrieve
*   **Outputs:**
    *   `thread`: Thread object with complete details including comments
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_users`

*   **Description:** Retrieve a list of all users in the Heartbeat community
*   **Inputs:** None required
*   **Outputs:**
    *   `users`: Array of user objects with id, email, name, bio, avatar, and creation timestamp
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_user`

*   **Description:** Get detailed information about a specific user
*   **Inputs:**
    *   `user_id`: The ID of the user to retrieve
*   **Outputs:**
    *   `user`: User object with detailed profile information
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_events`

*   **Description:** Retrieve a list of all events in the Heartbeat community
*   **Inputs:** None required
*   **Outputs:**
    *   `events`: Array of event objects with id, title, description, start/end times, and location
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `get_heartbeat_event`

*   **Description:** Get detailed information about a specific event
*   **Inputs:**
    *   `event_id`: The ID of the event to retrieve
*   **Outputs:**
    *   `event`: Event object with complete details
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `create_heartbeat_comment`

*   **Description:** Create a new comment on a thread in the Heartbeat community
*   **Inputs:**
    *   `thread_id`: The ID of the thread to comment on
    *   `content`: The text content of the comment (supports Rich Text formatting)
    *   `parent_id`: (Optional) The ID of the parent comment if this is a reply
    *   `user_id`: (Optional) The ID of the admin user to create the comment as
*   **Outputs:**
    *   `comment`: Created comment object with id, content, thread ID, author details, and timestamps
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

### Action: `create_heartbeat_thread`

*   **Description:** Create a new thread in a channel in the Heartbeat community
*   **Inputs:**
    *   `channel_id`: The ID of the channel to create the thread in
    *   `content`: The text content of the thread (supports Rich Text formatting)
    *   `user_id`: (Optional) The ID of the admin user to create the thread as
*   **Outputs:**
    *   `thread`: Created thread object with complete details
    *   `result`: Boolean indicating success/failure
    *   `error`: Error message if the action failed

## Requirements

*   `autohive_integrations_sdk`

## Usage Examples

**Example 1: Get all channels and then retrieve threads from the first channel**

```json
{
  "action": "get_heartbeat_channels"
}
```

Then use the channel ID from the result:

```json
{
  "channel_id": "channel_id_from_previous_result"
}
```

**Example 2: Create a new thread in a specific channel**

```json
{
  "channel_id": "your_channel_id",
  "content": "Hello! This is a new thread created via the API."
}
```

## Testing

To run the tests:

1.  Navigate to the integration's directory: `cd heartbeat`
2.  Install dependencies: `pip install -r requirements.txt`
3.  Update the API key in `tests/test_heartbeat.py` (replace `YOUR_HEARTBEAT_API_KEY_HERE` with your actual Bearer token)
4.  Run the tests: `python tests/test_heartbeat.py`

Note: The tests include placeholder IDs that will need to be replaced with actual IDs from your Heartbeat community for full functionality testing.

