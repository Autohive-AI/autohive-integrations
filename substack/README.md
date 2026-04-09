# Substack Integration for Autohive

Integration with Substack for searching publications, reading posts and comments. No authentication required — all actions use Substack's public APIs.

## Overview

This integration provides read-only access to public Substack content. It allows you to:

- Browse and paginate a publication's post archive
- Fetch full post content including body HTML
- Search for publications across the entire Substack platform
- Search posts within a specific publication by keyword
- Retrieve comments on any post

> **Note:** Substack has no official public API. This integration uses internal endpoints that are widely used but undocumented and subject to change.

## Authentication

No authentication required. All 5 actions work without credentials.

## Actions

### get_publication_posts

List posts from a Substack publication's archive. Supports sorting, keyword filtering, and pagination.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `publication_url` | string | Yes | Base URL of the publication, e.g. `https://example.substack.com` or a custom domain |
| `sort` | string | No | Sort order: `new` (default) or `top` |
| `search` | string | No | Optional keyword filter |
| `offset` | integer | No | Number of posts to skip for pagination (default: 0) |
| `limit` | integer | No | Maximum posts to return, 1–50 (default: 12) |

**Example:**
```json
{
  "publication_url": "https://on.substack.com",
  "sort": "top",
  "limit": 5
}
```

**Output:**
```json
{
  "posts": [
    {
      "id": 12345678,
      "slug": "my-post-title",
      "title": "My Post Title",
      "subtitle": "A subtitle",
      "post_date": "2024-01-01T00:00:00.000Z",
      "canonical_url": "https://example.substack.com/p/my-post-title",
      "audience": "everyone",
      "paywall": false,
      "reading_time_minutes": 5,
      "like_count": 42,
      "comment_count": 8,
      "type": "newsletter"
    }
  ],
  "count": 1
}
```

---

### get_post

Fetch the full content of a specific post by its slug. Returns body HTML. Paywalled posts return truncated content for non-subscribers.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `publication_url` | string | Yes | Base URL of the publication |
| `slug` | string | Yes | Post slug from the URL (e.g. `my-post-title` from `.../p/my-post-title`) |

**Example:**
```json
{
  "publication_url": "https://on.substack.com",
  "slug": "introducing-the-substack-recording"
}
```

**Output:**
```json
{
  "id": 190636964,
  "slug": "introducing-the-substack-recording",
  "title": "Introducing the Substack Recording Studio",
  "subtitle": "Pre-record your show, plus new tools for going live",
  "body_html": "<p>Full post content here...</p>",
  "post_date": "2026-03-12T17:01:34.272Z",
  "canonical_url": "https://on.substack.com/p/introducing-the-substack-recording",
  "audience": "everyone",
  "paywall": false,
  "reading_time_minutes": 3,
  "like_count": 120,
  "comment_count": 15,
  "type": "newsletter"
}
```

---

### search_publications

Search for Substack publications by keyword across the entire platform.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | Yes | Search query |
| `page` | integer | No | 0-based page number (default: 0) |
| `limit` | integer | No | Results per page, 1–100 (default: 10) |

**Example:**
```json
{
  "query": "technology startups",
  "limit": 5
}
```

**Output:**
```json
{
  "publications": [
    {
      "id": 1234,
      "name": "Tech Newsletter",
      "subdomain": "technewsletter",
      "description": "Weekly tech insights",
      "subscriber_count": 15000,
      "logo_url": "https://..."
    }
  ],
  "more": true
}
```

---

### search_posts

Search posts within a specific Substack publication by keyword.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `publication_url` | string | Yes | Base URL of the publication |
| `query` | string | Yes | Search query |
| `offset` | integer | No | Pagination offset (default: 0) |
| `limit` | integer | No | Maximum results, 1–50 (default: 10) |

**Example:**
```json
{
  "publication_url": "https://on.substack.com",
  "query": "writers",
  "limit": 5
}
```

**Output:**
```json
{
  "posts": [
    {
      "id": 99887766,
      "slug": "matching-post",
      "title": "Matching Post",
      "post_date": "2024-06-01T00:00:00.000Z",
      "canonical_url": "https://on.substack.com/p/matching-post",
      "audience": "everyone",
      "paywall": false,
      "like_count": 30,
      "comment_count": 4,
      "type": "newsletter"
    }
  ],
  "count": 1
}
```

---

### get_post_comments

Fetch comments for a specific post. Requires the numeric post `id` (not the slug).

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `publication_url` | string | Yes | Base URL of the publication |
| `post_id` | integer | Yes | Numeric post ID — the `id` field from `get_publication_posts` or `get_post` |
| `sort` | string | No | Sort order: `best` (default) or `newest` |
| `all_comments` | boolean | No | Return all comments (default: true) |

**Example:**
```json
{
  "publication_url": "https://on.substack.com",
  "post_id": 190636964,
  "sort": "newest"
}
```

**Output:**
```json
{
  "comments": [
    {
      "id": 55443322,
      "body": "Great post!",
      "date": "2024-01-02T00:00:00.000Z",
      "author_name": "Alice",
      "author_id": 99,
      "like_count": 3,
      "children": []
    }
  ],
  "count": 1
}
```

---

## Notes

- `publication_url` accepts both `https://example.substack.com` and bare hostnames like `example.substack.com`
- Custom domains (e.g. `https://newsletter.example.com`) are supported
- `get_post_comments` requires the numeric `post_id`, not the slug — get it from `get_publication_posts` or `get_post`
- Paywalled post `body_html` is truncated for non-subscribers
- Substack's undocumented APIs may change without notice

