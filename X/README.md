# X Integration for Autohive

Connects Autohive to the X API to enable posting, engagement management, user interactions, and social media automation.

## Description

This integration provides a comprehensive connection to X's social media platform. It allows users to automate post creation, search and retrieve posts, manage likes and reposts, follow/unfollow users, and retrieve user information directly from Autohive.

The integration uses X API v2 with OAuth 2.0 authentication and implements 12 actions covering posts, reposts, and users.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your X account.

### Authentication Method

X supports multiple authentication methods:

1. **OAuth 2.0** (Used by this integration)
   - Provides secure, token-based authentication
   - Users authorize access to their account
   - Tokens are managed automatically by the platform
   - Recommended for multi-user integrations
   - Required scopes: `tweet.read`, `tweet.write`, `media.write`, `users.read`, `follows.read`, `follows.write`, `like.read`, `offline.access`

2. **OAuth 1.0a** (Alternative method)
   - Uses API Key, API Secret, Access Token, and Access Token Secret
   - Requires manual token management

This integration uses OAuth 2.0 for enhanced security and easier token management.

### Setup Steps in Autohive

1. Add X integration in Autohive
2. Click "Connect to X" to authorize the integration
3. Sign in to your X account when prompted
4. Authorize the requested permissions for your account
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh, so you don't need to manually manage access tokens.

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields (e.g., `post`, `user`, `posts`)

Example successful response:
```json
{
  "result": true,
  "post": { "id": "1234567890", "text": "Hello World!" }
}
```

Example error response:
```json
{
  "result": false,
  "error": "Post not found",
  "post": {}
}
```

## Actions

### Posts (5 actions)

#### `create_tweet`
Creates a new post on X, optionally with media (image, GIF, or video).

**Inputs:**
- `text` (required): The text content of the post (max 280 characters for standard accounts)
- `file` (optional): Media file to upload and attach. Object containing:
  - `content`: Base64-encoded file content
  - `name`: Filename
  - `contentType`: MIME type (image/jpeg, image/png, image/gif, video/mp4, etc.)
- `reply_to` (optional): Post ID to reply to
- `quote_tweet_id` (optional): Post ID to quote
- `poll_options` (optional): Poll options (2-4 options)
- `poll_duration_minutes` (optional): Poll duration in minutes (default: 1440 = 24 hours)

**Outputs:**
- `post`: Created post object
- `media_id`: The media ID that was uploaded (if media was included)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Example (text only):**
```json
{
  "text": "Hello from Autohive! #automation"
}
```

**Example (with media):**
```json
{
  "text": "Check out this image! #automation",
  "file": {
    "content": "base64_encoded_image_data",
    "name": "image.png",
    "contentType": "image/png"
  }
}
```

---

#### `get_tweet`
Retrieves details of a specific post by its ID.

**Inputs:**
- `post_id` (required): The ID of the post
- `include_user` (optional): Include author user information (boolean)
- `include_metrics` (optional): Include engagement metrics (boolean)

**Outputs:**
- `post`: Post object with details
- `includes`: Additional data like user information
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete_tweet`
Deletes a post permanently.

**Inputs:**
- `post_id` (required): The ID of the post to delete

**Outputs:**
- `deleted`: Whether the post was deleted (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `search_tweets`
Searches for posts matching a query.

**Inputs:**
- `query` (required): Search query (use X search operators like `from:`, `to:`, `#hashtag`, etc.)
- `max_results` (optional): Maximum number of results (10-100, default: 10)
- `start_time` (optional): Start time in ISO 8601 format (YYYY-MM-DDTHH:mm:ssZ)
- `end_time` (optional): End time in ISO 8601 format
- `next_token` (optional): Pagination token from previous response

**Outputs:**
- `posts`: Array of matching posts
- `includes`: Additional data like user information
- `meta`: Metadata including pagination tokens
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Example Query:**
```
from:elonmusk tesla
#AI lang:en -is:retweet
"machine learning" min_faves:100
```

---

#### `get_user_tweets`
Retrieves posts from a user's timeline.

**Inputs:**
- `user_id` (required): The ID of the user
- `max_results` (optional): Maximum number of results (5-100, default: 10)
- `exclude_replies` (optional): Exclude replies (boolean)
- `exclude_retweets` (optional): Exclude reposts (boolean)
- `pagination_token` (optional): Pagination token from previous response

**Outputs:**
- `posts`: Array of posts
- `meta`: Metadata including pagination tokens
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Likes (1 action)

#### `get_liked_tweets`
Retrieves posts liked by a user.

**Inputs:**
- `user_id` (required): The ID of the user
- `max_results` (optional): Maximum number of results (5-100, default: 10)
- `pagination_token` (optional): Pagination token from previous response

**Outputs:**
- `posts`: Array of liked posts
- `includes`: Additional data like user information
- `meta`: Metadata including pagination tokens
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Reposts (2 actions)

#### `retweet`
Reposts a post.

**Inputs:**
- `user_id` (required): The ID of the authenticated user
- `post_id` (required): The ID of the post to repost

**Outputs:**
- `reposted`: Whether the post was reposted (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `unretweet`
Removes a repost.

**Inputs:**
- `user_id` (required): The ID of the authenticated user
- `post_id` (required): The ID of the post to undo repost

**Outputs:**
- `unreposted`: Whether the repost was removed (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Users (4 actions)

#### `get_user`
Retrieves user profile information by ID or username.

**Inputs:**
- `user_id` (optional): The ID of the user (required if username not provided)
- `username` (optional): The username of the user (required if user_id not provided)

**Outputs:**
- `user`: User profile details including bio, followers count, following count, etc.
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `get_me`
Retrieves the authenticated user's profile information.

**Inputs:** None

**Outputs:**
- `user`: Authenticated user's profile details
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `follow_user`
Follows a user.

**Inputs:**
- `source_user_id` (required): The ID of the authenticated user (follower)
- `target_user_id` (required): The ID of the user to follow

**Outputs:**
- `followed`: Whether the user was followed (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `unfollow_user`
Unfollows a user.

**Inputs:**
- `source_user_id` (required): The ID of the authenticated user (follower)
- `target_user_id` (required): The ID of the user to unfollow

**Outputs:**
- `unfollowed`: Whether the user was unfollowed (boolean)
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

## Requirements

- `autohive_integrations_sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URL**: `https://api.x.com/2`
- **Authentication**: OAuth 2.0
- **Documentation**: https://developer.x.com/en/docs/x-api
- **Rate Limits**:
  - Varies by endpoint and access level (Essential, Elevated, or Academic)
  - Post creation: 50 requests per 24 hours (Essential), 100 requests per 24 hours (Elevated)
  - Post retrieval: 500,000 posts per month (Essential), 2,000,000 posts per month (Elevated)
  - Search: 10 requests per 15 minutes (Essential), 450 requests per 15 minutes (Elevated)

## Important Notes

- OAuth tokens are automatically managed by the platform
- Tokens are automatically refreshed when needed
- You can revoke access at any time from your X account settings
- Standard (free) accounts have a 280-character limit per post
- X Premium and X Premium+ accounts may have higher limits
- Post IDs are strings, not integers
- Rate limits vary based on your X API access level (Essential, Elevated, or Academic)
- Some actions require specific OAuth 2.0 scopes

## Testing

To test the integration:

1. Navigate to the integration directory: `cd x-twitter`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OAuth credentials through the Autohive platform
4. Run tests: `python tests/test_x.py`

## Common Use Cases

**Social Media Automation:**
1. Auto-post from RSS feeds, blogs, or other sources
2. Schedule posts for optimal engagement times
3. Reply to mentions or specific keywords automatically
4. Quote post interesting content with your commentary

**Engagement Management:**
1. Auto-like posts containing specific hashtags or keywords
2. Repost content from specific accounts or topics
3. Track engagement metrics for your posts
4. Monitor post performance and analytics

**User Management:**
1. Auto-follow users who mention specific keywords
2. Unfollow inactive accounts
3. Get follower and following lists for analysis
4. Monitor follower growth and engagement

**Content Curation:**
1. Search for posts on specific topics
2. Collect posts for content research
3. Monitor brand mentions and sentiment
4. Track competitor activity

**Customer Service:**
1. Monitor and respond to customer mentions
2. Track support-related keywords
3. Auto-reply to common questions
4. Escalate issues based on keywords

## Version History

- **1.0.2** - Merged post actions
  - Merged `post_with_media` into `create_tweet` (file parameter is now optional)
  - Single action now supports text-only posts, posts with media, replies, quotes, and polls

- **1.0.1** - Updated actions
  - Removed standalone upload_media action (use post_with_media instead)
  - Added follow_user action
  - Added follows.read scope

- **1.0.0** - Initial release with 13 actions
  - Media: upload_media (1 action)
  - Posts: create, post_with_media, get, delete, search, get_user_posts (6 actions)
  - Likes: get_liked_posts (1 action)
  - Reposts: repost, undo repost (2 actions)
  - Users: get_user, get_me, unfollow (3 actions)

## Additional Resources

- [X API Documentation](https://developer.x.com/en/docs/x-api)
- [X API Authentication](https://developer.x.com/en/docs/authentication/oauth-2-0)
- [X API Reference](https://developer.x.com/en/docs/api-reference-index)
- [X Developer Portal](https://developer.x.com/en/portal/dashboard)
- [X API Rate Limits](https://developer.x.com/en/docs/x-api/rate-limits)

## Troubleshooting

### Common Issues

**403 Forbidden Error:**
- Check that your app has the required OAuth 2.0 scopes
- Verify your API access level (Essential/Elevated)
- Ensure you're not exceeding rate limits

**401 Unauthorized Error:**
- OAuth token may be expired (automatically refreshed by platform)
- Check OAuth credentials are correctly configured

**Rate Limit Exceeded:**
- Wait for the rate limit window to reset
- Consider upgrading to Elevated or Academic access
- Implement exponential backoff in your workflows

**Post Not Found (404):**
- Post may have been deleted
- Post ID may be incorrect
- User may have protected posts

**Media Upload Issues:**
- Media upload functionality may have limitations depending on your X API access level
- Ensure you have the correct API access tier (some features require Pro or Enterprise access)
- If media upload fails, try posting without media first to verify connectivity
