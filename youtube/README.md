# YouTube Integration

Connects to the YouTube Data API v3 to allow users to manage videos, channels, playlists, comments, and analytics directly from their workflows.

## Description

This integration provides comprehensive YouTube Data API v3 functionality, enabling users to search content, manage videos and playlists, interact with comments, and access channel analytics. It supports advanced filtering, content moderation, playlist organization, and detailed video statistics. The integration uses Google's OAuth2 authentication to securely access YouTube resources with appropriate permissions.

Key features:
- Search videos, channels, and playlists with advanced filtering
- Get detailed video information including statistics and metadata
- Update video properties (title, description, tags, privacy settings)
- Upload custom thumbnails for videos
- Complete playlist management (create, update, delete, reorder)
- Full comment functionality (read, post, reply, update, delete)
- Comment moderation tools for channel owners
- Access channel analytics and statistics
- Support for pagination across all list operations

## Setup & Authentication

The integration uses Google's OAuth2 platform authentication. Users need to authenticate through Google's OAuth flow within Autohive to grant YouTube access permissions.

**Authentication Type:** Platform (YouTube/Google)

**Required Scopes:**
- `https://www.googleapis.com/auth/youtube` - Full YouTube access
- `https://www.googleapis.com/auth/youtube.upload` - Upload thumbnails
- `https://www.googleapis.com/auth/youtube.force-ssl` - Secure SSL access

No additional configuration fields are required as authentication is handled through Google's OAuth2 flow.

## Actions

### Search & Discovery

#### Action: `search`
- **Description:** Search for videos, channels, or playlists on YouTube with advanced filtering
- **Inputs:**
  - `query`: Search query term (required)
  - `type`: Filter by resource type - video, channel, playlist (optional)
  - `max_results`: Maximum results to return (1-50, default: 5) (optional)
  - `order`: Sort order - relevance, date, rating, viewCount, title (optional)
  - `published_after`: Filter content published after this date in RFC 3339 format (optional)
  - `published_before`: Filter content published before this date in RFC 3339 format (optional)
  - `channel_id`: Search within a specific channel (optional)
  - `region_code`: Geographic location code like US, GB (optional)
  - `page_token`: Token for pagination (optional)
- **Outputs:**
  - `items`: Array of search results with id, title, description, thumbnail, published date
  - `next_page_token`: Token for retrieving next page of results
  - `total_results`: Total number of results available
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Video Management

#### Action: `get_video`
- **Description:** Get detailed information about a specific YouTube video
- **Inputs:**
  - `video_id`: YouTube video ID (required)
- **Outputs:**
  - `video`: Complete video object with id, title, description, channel info, statistics (view_count, like_count, comment_count), duration, tags, and thumbnails
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `update_video`
- **Description:** Update video metadata including title, description, tags, and privacy settings
- **Inputs:**
  - `video_id`: YouTube video ID (required)
  - `title`: Updated video title (optional)
  - `description`: Updated video description (optional)
  - `category_id`: Video category ID (optional)
  - `tags`: Array of video tags (optional)
  - `privacy_status`: Privacy setting - private, public, unlisted (optional)
  - `made_for_kids`: Boolean indicating if video is made for kids (optional)
- **Outputs:**
  - `video`: Updated video object with all changes reflected
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `upload_thumbnail`
- **Description:** Upload a custom thumbnail image for a video
- **Inputs:**
  - `video_id`: YouTube video ID (required)
  - `image_url`: URL or path to thumbnail image in JPEG or PNG format, max 2MB (required)
- **Outputs:**
  - `thumbnail`: Thumbnail details object
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Channel Management

#### Action: `get_channel`
- **Description:** Get channel information including subscriber count, video count, and total views
- **Inputs:**
  - `channel_id`: YouTube channel ID (optional)
  - `channel_handle`: Channel handle like @username (optional)
  - `mine`: Boolean to get authenticated user's channel (optional)
- **Outputs:**
  - `channel`: Complete channel object with id, title, description, custom_url, statistics (subscriber_count, video_count, view_count), thumbnails, and publication date
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Playlist Management

#### Action: `list_playlists`
- **Description:** List playlists from a channel or authenticated user
- **Inputs:**
  - `channel_id`: Channel ID to list playlists from (optional)
  - `mine`: Boolean to list authenticated user's playlists (optional)
  - `max_results`: Maximum results to return (1-50, default: 5) (optional)
  - `page_token`: Token for pagination (optional)
- **Outputs:**
  - `playlists`: Array of playlist objects with id, title, description, and item count
  - `next_page_token`: Token for retrieving next page of results
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `create_playlist`
- **Description:** Create a new YouTube playlist
- **Inputs:**
  - `title`: Playlist title (required)
  - `description`: Playlist description (optional)
  - `privacy_status`: Privacy setting - private, public, unlisted (required)
- **Outputs:**
  - `playlist`: Created playlist object with details
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `update_playlist`
- **Description:** Update playlist title, description, or privacy status
- **Inputs:**
  - `playlist_id`: Playlist ID (required)
  - `title`: Updated playlist title (optional)
  - `description`: Updated playlist description (optional)
  - `privacy_status`: Updated privacy setting - private, public, unlisted (optional)
- **Outputs:**
  - `playlist`: Updated playlist object with changes reflected
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `delete_playlist`
- **Description:** Delete a YouTube playlist permanently
- **Inputs:**
  - `playlist_id`: Playlist ID to delete (required)
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `list_playlist_items`
- **Description:** List all videos in a playlist
- **Inputs:**
  - `playlist_id`: Playlist ID (required)
  - `max_results`: Maximum results to return (1-50, default: 5) (optional)
  - `page_token`: Token for pagination (optional)
- **Outputs:**
  - `items`: Array of playlist items with video details and position information
  - `next_page_token`: Token for retrieving next page of results
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `add_video_to_playlist`
- **Description:** Add a video to a playlist
- **Inputs:**
  - `playlist_id`: Playlist ID (required)
  - `video_id`: Video ID to add (required)
  - `position`: Position in playlist, 0-based index (optional)
- **Outputs:**
  - `playlist_item`: Added playlist item object with details
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `remove_video_from_playlist`
- **Description:** Remove a video from a playlist
- **Inputs:**
  - `playlist_item_id`: Playlist item ID to remove, not the video ID (required)
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

### Comment Management

#### Action: `list_comments`
- **Description:** List top-level comments for a video with sorting and pagination
- **Inputs:**
  - `video_id`: Video ID (required)
  - `max_results`: Maximum results to return (1-100, default: 20) (optional)
  - `order`: Sort order - time, relevance (optional)
  - `page_token`: Token for pagination (optional)
- **Outputs:**
  - `comments`: Array of comment objects with id, text, author info, like count, and timestamps
  - `next_page_token`: Token for retrieving next page of results
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `list_comment_replies`
- **Description:** List all replies to a specific comment
- **Inputs:**
  - `parent_comment_id`: Parent comment ID (required)
  - `max_results`: Maximum results to return (1-100, default: 20) (optional)
  - `page_token`: Token for pagination (optional)
- **Outputs:**
  - `replies`: Array of reply comment objects
  - `next_page_token`: Token for retrieving next page of results
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `post_comment`
- **Description:** Post a top-level comment on a video
- **Inputs:**
  - `video_id`: Video ID (required)
  - `text`: Comment text (required)
- **Outputs:**
  - `comment`: Posted comment object with details
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `reply_to_comment`
- **Description:** Reply to an existing comment
- **Inputs:**
  - `parent_comment_id`: Parent comment ID (required)
  - `text`: Reply text (required)
- **Outputs:**
  - `comment`: Posted reply object with details
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `update_comment`
- **Description:** Update your own comment text
- **Inputs:**
  - `comment_id`: Comment ID (required)
  - `text`: Updated comment text (required)
- **Outputs:**
  - `comment`: Updated comment object with changes reflected
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `delete_comment`
- **Description:** Delete a comment you own or moderate
- **Inputs:**
  - `comment_id`: Comment ID to delete (required)
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

#### Action: `moderate_comment`
- **Description:** Set comment moderation status, channel owner only
- **Inputs:**
  - `comment_id`: Comment ID (required)
  - `moderation_status`: Moderation status - published, heldForReview, rejected (required)
  - `ban_author`: Boolean to ban comment author from channel (optional)
- **Outputs:**
  - `result`: Success status boolean
  - `error`: Error message (if operation failed)

## Requirements

- Python dependencies are handled by the Autohive platform
- YouTube Data API v3 access
- Valid Google account with YouTube access
- YouTube Data API quota (default: 10,000 units per day)

## Usage Examples

**Example 1: Search for videos and get detailed information**

Step 1 - Search for videos:
```json
{
  "query": "Python programming tutorial",
  "type": "video",
  "max_results": 10,
  "order": "relevance"
}
```

Step 2 - Get detailed video information:
```json
{
  "video_id": "dQw4w9WgXcQ"
}
```

**Example 2: Update video metadata and upload custom thumbnail**

Step 1 - Update video details:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Updated Video Title",
  "description": "This is my updated video description with more details",
  "tags": ["tutorial", "howto", "educational"],
  "privacy_status": "public"
}
```

Step 2 - Upload custom thumbnail:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "image_url": "https://example.com/thumbnail.jpg"
}
```

**Example 3: Create playlist and add videos**

Step 1 - Create new playlist:
```json
{
  "title": "My Favorite Tutorials",
  "description": "A collection of helpful tutorial videos",
  "privacy_status": "public"
}
```

Step 2 - Add video to playlist:
```json
{
  "playlist_id": "PLxxxxxxxxxxxxxxxx",
  "video_id": "dQw4w9WgXcQ"
}
```

Step 3 - List playlist items to verify:
```json
{
  "playlist_id": "PLxxxxxxxxxxxxxxxx",
  "max_results": 50
}
```

**Example 4: Manage comments on your videos**

Step 1 - List comments on video:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "max_results": 50,
  "order": "time"
}
```

Step 2 - Reply to a comment:
```json
{
  "parent_comment_id": "UgzXXXXXXXXXXXXXXXX",
  "text": "Thank you for your feedback! I'm glad you found this helpful."
}
```

Step 3 - Moderate inappropriate comment:
```json
{
  "comment_id": "UgzYYYYYYYYYYYYYYYY",
  "moderation_status": "rejected",
  "ban_author": false
}
```

**Example 5: Get your channel analytics**

```json
{
  "mine": true
}
```

**Example 6: Post comment and monitor engagement**

Step 1 - Post comment on video:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "text": "Great video! This was really helpful, thanks for sharing."
}
```

Step 2 - List replies to your comment:
```json
{
  "parent_comment_id": "UgzZZZZZZZZZZZZZZZZ",
  "max_results": 20
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd youtube`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the tests: `python tests/test_youtube.py`

Note: The tests use mock authentication and are designed for development validation. For production testing, ensure you have valid Google OAuth2 credentials configured with appropriate YouTube API scopes.
