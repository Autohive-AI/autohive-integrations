# Ghost Integration for Autohive

Connects Autohive to your Ghost CMS to read and manage posts, pages, members, and newsletters through the Ghost Content API and Admin API.

## Description

This integration provides full access to Ghost's content and membership platform, enabling automated content publishing, member management, and newsletter delivery. Key features include:

- **Post Management**: List posts, fetch individual posts by ID or slug, create and update posts
- **Page Management**: List pages, fetch individual pages by ID or slug, create pages
- **Member Management**: Create and update members with labels and newsletter subscriptions
- **Content Discovery**: Browse tags, authors, site settings, and membership tiers
- **Newsletter Delivery**: Trigger email delivery of published posts to subscribers
- **Image Uploads**: Upload images from the local filesystem to Ghost's media library

## Setup & Authentication

### Getting Your API Keys

1. Log in to your Ghost Admin panel
2. Navigate to **Settings → Integrations**
3. Click **Add custom integration** (or select an existing one)
4. Copy the **Content API Key** and **Admin API Key**
5. Note your Ghost site URL (e.g. `https://yoursite.ghost.io`)

### Authentication Fields

| Field | Format | Used For |
|-------|--------|----------|
| `api_url` | `https://yoursite.ghost.io` | All actions — base URL for API requests |
| `content_api_key` | 26-character hex string | All read actions (Content API) |
| `admin_api_key` | `id:secret` (colon-separated) | All write actions (Admin API) |

> The Admin API key is found in Ghost Admin → Settings → Integrations. It is in the format `id:secret` where both parts are hex strings.

## Actions

### Read Actions (Content API)

#### `get_posts`
List posts from the Ghost Content API.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number of posts to return (default: 15) |
| `page` | integer | No | Page number for pagination |
| `filter` | string | No | Ghost filter string, e.g. `featured:true` |
| `include` | string | No | Relations to include, e.g. `tags,authors` |

**Outputs:**
| Field | Type | Description |
|-------|------|-------------|
| `result` | boolean | Success indicator |
| `posts` | array | List of post objects |
| `meta` | object | Pagination metadata |
| `error` | string | Error message if result is false |
| `error_type` | string | Error type if result is false |

---

#### `get_post`
Get a single post by ID or slug.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | No* | Post ID |
| `slug` | string | No* | Post slug (used if id not provided) |
| `include` | string | No | Relations to include |

*Either `id` or `slug` is required.

**Outputs:** `result`, `post` (object or null), `error`, `error_type`

---

#### `get_pages`
List pages from the Ghost Content API.

**Inputs:** `limit`, `page`, `filter` (same as `get_posts`)

**Outputs:** `result`, `pages` (array), `meta`, `error`, `error_type`

---

#### `get_page`
Get a single page by ID or slug. Same inputs as `get_post`.

**Outputs:** `result`, `page` (object or null), `error`, `error_type`

---

#### `get_tags`
List tags from the Ghost Content API.

**Inputs:** `limit`, `page`, `filter`

**Outputs:** `result`, `tags` (array), `meta`, `error`, `error_type`

---

#### `get_authors`
List authors from the Ghost Content API.

**Inputs:** `limit`, `page`

**Outputs:** `result`, `authors` (array), `meta`, `error`, `error_type`

---

#### `get_settings`
Get site-wide settings (title, description, logo, etc.). No inputs required.

**Outputs:** `result`, `settings` (object), `error`, `error_type`

---

#### `get_tiers`
List membership tiers. No inputs required.

**Outputs:** `result`, `tiers` (array), `error`, `error_type`

---

### Write Actions (Admin API)

#### `create_post`
Create a new post in Ghost.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | **Yes** | Post title |
| `html` | string | No | Post body as HTML |
| `lexical` | string | No | Post body in Lexical JSON format |
| `status` | string | No | `draft` or `published` (default: `draft`) |
| `tags` | array | No | Tag objects, e.g. `[{"name": "news"}]` |
| `authors` | array | No | Author objects, e.g. `[{"email": "author@example.com"}]` |
| `feature_image` | string | No | URL of the feature image |
| `excerpt` | string | No | Post excerpt |

**Outputs:** `result`, `post` (object), `error`, `error_type`

---

#### `update_post`
Update an existing post. The `updated_at` timestamp is required by Ghost for conflict detection.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **Yes** | Post ID |
| `updated_at` | string | **Yes** | ISO 8601 timestamp from the current post (prevents overwriting concurrent edits) |
| `title`, `html`, `lexical`, `status`, `tags`, `authors`, `feature_image`, `excerpt` | various | No | Fields to update |

**Outputs:** `result`, `post` (object), `error`, `error_type`

---

#### `create_page`
Create a new page in Ghost.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | **Yes** | Page title |
| `html` | string | No | Page body as HTML |
| `lexical` | string | No | Page body in Lexical JSON format |
| `status` | string | No | `draft` or `published` (default: `draft`) |

**Outputs:** `result`, `page` (object), `error`, `error_type`

---

#### `upload_image`
Upload an image from the local filesystem to Ghost's media library.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | **Yes** | Absolute path to the image file |
| `purpose` | string | No | `image`, `profile_image`, or `icon` (default: `image`) |

**Outputs:** `result`, `image` (object with `url`), `error`, `error_type`

---

#### `create_member`
Create a new member in Ghost.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | **Yes** | Member email address |
| `name` | string | No | Member display name |
| `labels` | array | No | Label objects, e.g. `[{"name": "vip"}]` |
| `newsletters` | array | No | Newsletter objects to subscribe to |
| `note` | string | No | Internal note about the member |

**Outputs:** `result`, `member` (object), `error`, `error_type`

---

#### `update_member`
Update an existing member.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | **Yes** | Member ID |
| `email`, `name`, `labels`, `newsletters`, `note` | various | No | Fields to update |

**Outputs:** `result`, `member` (object), `error`, `error_type`

---

#### `send_newsletter`
Trigger email delivery of a published post to subscribers.

**Inputs:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `post_id` | string | **Yes** | ID of the post to send |
| `updated_at` | string | **Yes** | ISO 8601 timestamp from the post (conflict detection) |
| `newsletter_id` | string | No | Newsletter ID to use (uses default if omitted) |

**Outputs:** `result`, `post` (object), `error`, `error_type`

---

## Action Results

All actions return a response with the following structure:

```json
{
  "result": true,
  "posts": [...],
  "meta": { "pagination": { "page": 1, "limit": 15, "total": 42 } }
}
```

On failure:

```json
{
  "result": false,
  "error": "Resource not found",
  "error_type": "NotFoundError"
}
```

## Testing

```bash
cd ghost
pip install -r requirements.txt
# Edit tests/test_ghost.py and fill in TEST_AUTH with your credentials
python tests/test_ghost.py
```

> **Note:** Write actions (`create_post`, `create_member`, etc.) create real content in your Ghost instance. Clean up test content after running.

## API Reference

- [Ghost Content API Docs](https://ghost.org/docs/content-api/)
- [Ghost Admin API Docs](https://ghost.org/docs/admin-api/)
- [Ghost API Authentication](https://ghost.org/docs/admin-api/#authentication)
- **Base URLs:** `/ghost/api/content/` (read) · `/ghost/api/admin/` (write)
- **Rate Limits:** Ghost does not publish rate limit details; self-hosted instances have no enforced limits by default

## Version History

- **1.0.0** - Initial release: 8 read actions (Content API) + 7 write actions (Admin API)
