# Circle Integration for Autohive

Connects Autohive to the Circle.so community platform API to allow users to manage posts, members, spaces, events, and comments within their Circle communities.

## Description

This integration provides comprehensive access to Circle.so community management capabilities through the Circle Admin API v2. It enables automated community engagement, content management, and member operations.

The integration solves key community management challenges:
- Automated post creation and updates with markdown support
- Member search and profile management
- Space and event discovery
- Community engagement through comments
- Real-time access to community statistics and information

Key features include markdown-to-TipTap conversion for rich post formatting, comprehensive error handling, pagination support for large datasets, and full CRUD operations across all major Circle entities.

## Setup & Authentication

The integration uses Circle's Admin API Token for authentication. You'll need admin access to your Circle community to generate an API token.

**How to obtain your API Token:**

1. Log in to your Circle community with admin privileges
2. Navigate to **Settings** → **Developers** → **Tokens**
3. Create a new API token or copy an existing one
4. Store this token securely (it provides full admin access to your community)

**Authentication Fields:**

*   `api_token`: Your Circle Admin API Token (found in Settings → Developers → Tokens). This token provides full access to your community's data and operations.

## Actions

### Action: `search_posts`

*   **Description:** Search for posts in the community by keyword, tag, space, or status with pagination support.
*   **Inputs:**
    *   `query`: (optional) Search query to find posts by title or content
    *   `space_id`: (optional) Filter posts by specific space ID
    *   `tag`: (optional) Filter posts by tag
    *   `status`: (optional) Filter by post status (published, draft, archived)
    *   `per_page`: (optional) Number of posts to return (default: 10)
    *   `page`: (optional) Page number for pagination
*   **Outputs:**
    *   `posts`: Array of matching posts with full details
    *   `count`: Total number of posts found
    *   `result`: Boolean indicating operation success

### Action: `get_post`

*   **Description:** Retrieve detailed information about a specific post.
*   **Inputs:**
    *   `post_id`: (required) The post ID to retrieve
*   **Outputs:**
    *   `post`: Post object with title, body, author, and metadata
    *   `result`: Boolean indicating operation success

### Action: `create_post`

*   **Description:** Create a new post in a space with full markdown support. Markdown is automatically converted to Circle's TipTap/ProseMirror format.
*   **Inputs:**
    *   `space_id`: (required) The space ID where the post will be created (integer)
    *   `name`: (required) Post title
    *   `body`: (required) Post content in markdown format
    *   `status`: (optional) Post status - published, draft, scheduled (default: published)
    *   `is_pinned`: (optional) Whether to pin the post (default: false)
    *   `is_comments_enabled`: (optional) Whether to enable comments (default: true)
    *   `user_email`: (optional) Email of the user to create the post as
*   **Outputs:**
    *   `post`: Created post details including ID, URL, and metadata
    *   `result`: Boolean indicating operation success

### Action: `update_post`

*   **Description:** Update an existing post including title, content, status, or pinned state.
*   **Inputs:**
    *   `post_id`: (required) The post ID to update
    *   `name`: (optional) Updated post title
    *   `body`: (optional) Updated post content
    *   `status`: (optional) Updated post status
    *   `is_pinned`: (optional) Whether to pin the post
*   **Outputs:**
    *   `post`: Updated post details
    *   `result`: Boolean indicating operation success

### Action: `search_member_by_email`

*   **Description:** Find a specific community member by their email address.
*   **Inputs:**
    *   `email`: (required) Email address of the member to find
*   **Outputs:**
    *   `member`: Member details if found
    *   `result`: Boolean indicating operation success

### Action: `list_members`

*   **Description:** List community members with optional filtering by status and pagination support.
*   **Inputs:**
    *   `status`: (optional) Filter by member status (active, inactive, pending)
    *   `per_page`: (optional) Number of members to return (default: 10)
    *   `page`: (optional) Page number for pagination (default: 1)
*   **Outputs:**
    *   `members`: Array of member objects
    *   `count`: Total number of members
    *   `result`: Boolean indicating operation success

### Action: `get_member`

*   **Description:** Get detailed information about a specific community member.
*   **Inputs:**
    *   `member_id`: (required) The member ID to retrieve
*   **Outputs:**
    *   `member`: Member details including profile, activity, and membership info
    *   `result`: Boolean indicating operation success

### Action: `search_spaces`

*   **Description:** Search for spaces (groups/categories) in the community by name or type.
*   **Inputs:**
    *   `query`: (optional) Search query to find spaces by name
    *   `space_type`: (optional) Filter by space type (post, event, chat, course)
    *   `per_page`: (optional) Number of spaces to return (default: 10)
*   **Outputs:**
    *   `spaces`: Array of matching spaces
    *   `count`: Total number of spaces found
    *   `result`: Boolean indicating operation success

### Action: `get_space`

*   **Description:** Get detailed information about a specific space.
*   **Inputs:**
    *   `space_id`: (required) The space ID to retrieve
*   **Outputs:**
    *   `space`: Space details including name, type, and settings
    *   `result`: Boolean indicating operation success

### Action: `search_events`

*   **Description:** Search for upcoming or past events in the community with filtering options.
*   **Inputs:**
    *   `query`: (optional) Search query to find events by name
    *   `time_filter`: (optional) Filter events by time (upcoming, past, all) - default: upcoming
    *   `space_id`: (optional) Filter events by specific space ID
    *   `per_page`: (optional) Number of events to return (default: 10)
*   **Outputs:**
    *   `events`: Array of matching events
    *   `count`: Total number of events found
    *   `result`: Boolean indicating operation success

### Action: `get_event`

*   **Description:** Get detailed information about a specific event.
*   **Inputs:**
    *   `event_id`: (required) The event ID to retrieve
*   **Outputs:**
    *   `event`: Event details including date, location, attendees, and description
    *   `result`: Boolean indicating operation success

### Action: `create_comment`

*   **Description:** Add a comment to a post for community engagement.
*   **Inputs:**
    *   `post_id`: (required) The post ID to comment on
    *   `body`: (required) Comment content
*   **Outputs:**
    *   `comment`: Created comment details
    *   `result`: Boolean indicating operation success

### Action: `get_post_comments`

*   **Description:** Retrieve all comments for a specific post with pagination support.
*   **Inputs:**
    *   `post_id`: (required) The post ID to get comments from
    *   `per_page`: (optional) Number of comments to return (default: 20)
*   **Outputs:**
    *   `comments`: Array of comment objects
    *   `count`: Total number of comments
    *   `result`: Boolean indicating operation success

### Action: `get_community_info`

*   **Description:** Get information about the community including name, settings, and statistics.
*   **Inputs:**
    *   (No inputs required)
*   **Outputs:**
    *   `community`: Community details including name, settings, and statistics
    *   `result`: Boolean indicating operation success

## Requirements

*   `autohive-integrations-sdk`: Core Autohive integration framework
*   `mistune`: Markdown parser used for converting markdown to TipTap format

## Usage Examples

**Example 1: Create a formatted announcement post**

```python
# Create a post with rich markdown formatting
{
  "space_id": 12345,
  "name": "Weekly Community Update - January 2025",
  "body": """
# Welcome to this week's update!

Here's what's happening:

- **New features** launched this week
- *Member spotlight* on @john_doe
- Check out our [resources](https://example.com)

## Upcoming Events
1. Monday - Team standup
2. Friday - Community call

> Remember to check the #announcements channel!
  """,
  "status": "published",
  "is_comments_enabled": true
}
```

**Example 2: Find and engage with a member**

```python
# Search for a member by email
{
  "email": "user@example.com"
}

# Then get their full profile
{
  "member_id": "abc123"
}

# Add a welcoming comment to their post
{
  "post_id": "xyz789",
  "body": "Welcome to the community! Looking forward to your contributions."
}
```

**Example 3: List upcoming events in a specific space**

```python
# Search for events space
{
  "query": "events",
  "space_type": "event"
}

# Get upcoming events in that space
{
  "space_id": "67890",
  "time_filter": "upcoming",
  "per_page": 20
}
```

## Testing

To run the tests:

1.  Navigate to the integration's directory: `cd circle`
2.  Install dependencies: `pip install -r requirements.txt`
3.  Set up authentication: Create a test environment with your Circle API token
4.  Run the tests: `python -m pytest tests/`

**Note:** Testing requires a valid Circle community with admin API token access. Ensure you're testing against a development/sandbox community to avoid affecting production data.
