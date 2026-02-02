# Facebook Pages Integration

Facebook Pages integration for Autohive. Manage posts, comments, and insights from a unified interface.

## Features

| Category | Capabilities |
|----------|-------------|
| **Pages** | Discover and list all manageable pages |
| **Posts** | Create, retrieve, schedule, and delete posts (text, photo, video, link) |
| **Comments** | Read comments, reply, hide/unhide, like/unlike, delete |
| **Insights** | Page-level and post-level analytics |

## Actions

### Page Discovery

#### `list_pages`
Discover all Facebook Pages you can manage.

**Outputs:** Page ID, name, category, follower count

---

### Posts

#### `get_posts`
Retrieve posts from a page. Fetch a single post or list recent posts.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `page_id` | Yes | The Facebook Page ID |
| `post_id` | No | Specific post ID (omit to list all) |
| `limit` | No | Max posts to return (default: 25, max: 100) |

#### `create_post`
Publish content to a page. Supports multiple media types and scheduling.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `page_id` | Yes | The Facebook Page ID |
| `message` | Yes | Post text content |
| `media_type` | No | `text`, `photo`, `video`, or `link` (default: text) |
| `media_url` | No* | URL of media (*required for photo/video/link) |
| `scheduled_time` | No | Unix timestamp (seconds) or ISO 8601 format. Must be 10 min to 75 days from now. |

#### `delete_post`
Permanently delete a post. **Cannot be undone.**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `page_id` | Yes | The Facebook Page ID |
| `post_id` | Yes | The post ID to delete |

---

### Comments

#### `get_comments`
Retrieve comments on a post.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `post_id` | Yes | The post ID (format: `PAGEID_POSTID`) |
| `limit` | No | Max comments to return (default: 25, max: 100) |
| `include_hidden` | No | Include hidden comments (default: false) |

#### `manage_comment`
Interact with comments: reply, hide/unhide, or like/unlike.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `page_id` | Yes | The Facebook Page ID |
| `comment_id` | Yes | The comment ID |
| `action` | Yes | `reply`, `hide`, `unhide`, `like`, or `unlike` |
| `message` | No* | Reply text (*required for reply action) |

#### `delete_comment`
Permanently delete a comment. **Cannot be undone.**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `page_id` | Yes | The Facebook Page ID |
| `comment_id` | Yes | The comment ID to delete |

---

### Insights

#### `get_insights`
Retrieve analytics for a page or post.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `target_type` | Yes | `page` or `post` |
| `target_id` | Yes | The page or post ID |
| `metrics` | No | Specific metrics to retrieve (see defaults below) |
| `period` | No | `day`, `week`, or `days_28` (page only, default: days_28) |

**Default Page Metrics:**
- `page_follows` - Total page follows
- `page_daily_follows_unique` - Daily new follows
- `page_daily_unfollows_unique` - Daily unfollows
- `page_post_engagements` - Post engagements
- `page_video_views` - Video views
- `page_media_view` - Media views

**Default Post Metrics:**
- `post_engaged_users` - Users who engaged with the post
- `post_clicks` - Clicks on the post
- `post_reactions_by_type_total` - Reactions breakdown

---

## Required Permissions

This integration requires the following Facebook permissions:

| Scope | Purpose |
|-------|---------|
| `pages_show_list` | List manageable pages |
| `pages_read_engagement` | Read page engagement data |
| `pages_read_user_content` | Read comments |
| `pages_manage_posts` | Create and delete posts |
| `pages_manage_engagement` | Reply to and manage comments |
| `pages_manage_metadata` | Manage page metadata |
| `read_insights` | Access page and post analytics |

---

## Project Structure

This integration uses a multi-file structure for maintainability:

```
facebook/
├── facebook.py          # Entry point, loads Integration
├── config.json          # Integration configuration
├── helpers.py           # Shared utilities (API base URL, token helpers)
├── actions/
│   ├── __init__.py      # Imports all action submodules
│   ├── pages.py         # Page discovery actions
│   ├── posts.py         # Post CRUD actions
│   ├── comments.py      # Comment management actions
│   └── insights.py      # Analytics actions
└── tests/
    ├── context.py       # Test import configuration
    └── test_facebook.py # Comprehensive test suite
```

## Running Tests

```bash
cd facebook
pytest tests/ -v
```

---

## API Version

This integration uses Facebook Graph API **v21.0**.
