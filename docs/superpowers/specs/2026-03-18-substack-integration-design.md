# Substack Integration — Design Spec

**Date:** 2026-03-18
**Status:** Approved

---

## Overview

A Substack integration for the autohive-integrations repository that enables reading publication posts, fetching post content, searching publications and posts, retrieving comments, and accessing a user's personal subscriptions and reader feed.

Substack has no official public API. This integration uses undocumented internal REST endpoints that are stable in practice and widely used by the community, combined with an optional session cookie for authenticated actions.

---

## Auth

**Type:** `custom`

Two optional fields:

| Field | Type | Purpose |
|---|---|---|
| `connect_sid` | password | Primary session cookie (`connect.sid`) from browser |
| `substack_sid` | password | Secondary session cookie (`substack.sid`) from browser |

Users obtain these from browser DevTools (Application → Cookies → substack.com) after logging in. Public actions work without any credentials. Authenticated actions (`get_subscriptions`, `get_reader_feed`) require both.

When credentials are provided, they are passed as a `Cookie` header:
```
Cookie: connect.sid=<connect_sid>; substack.sid=<substack_sid>
```

---

## Actions

### 1. `get_publication_posts`
List posts from a Substack publication archive.

**Endpoint:** `GET https://{publication_url}/api/v1/archive`

**Inputs:**
- `publication_url` (string, required) — base URL of the publication, e.g. `https://example.substack.com` or a custom domain
- `sort` (enum: `new` | `top`, default: `new`)
- `search` (string, optional) — keyword filter
- `offset` (integer, default: 0) — pagination offset (number of posts to skip)
- `limit` (integer, default: 12, max: 50)

**Outputs:**
- `posts` (array) — each item: `id`, `slug`, `title`, `subtitle`, `post_date`, `canonical_url`, `audience`, `paywall`, `reading_time_minutes`, `cover_image`, `like_count`, `comment_count`, `type`

---

### 2. `get_post`
Get full content of a specific post by slug.

**Endpoint:** `GET https://{publication_url}/api/v1/posts/{slug}`

**Inputs:**
- `publication_url` (string, required)
- `slug` (string, required) — post slug from the URL or archive listing

**Outputs:**
- `id`, `slug`, `title`, `subtitle`, `body_html`, `post_date`, `canonical_url`, `audience`, `paywall`, `reading_time_minutes`, `cover_image`, `like_count`, `comment_count`, `type`, `audio_url`

Note: `body_html` is truncated for paywalled posts unless the user has a valid subscriber session.

---

### 3. `get_publication_info`
Get metadata about a Substack publication.

**Endpoint:** `GET https://{publication_url}/api/v1/publication`

**Inputs:**
- `publication_url` (string, required)

**Outputs:**
- `id`, `name`, `subdomain`, `custom_domain`, `logo_url`, `cover_photo_url`, `hero_text`, `subscriber_count`, `author_id`, `email_from_name`, `type`

---

### 4. `search_publications`
Search for publications across all of Substack.

**Endpoint:** `GET https://substack.com/api/v1/publication/search`

**Inputs:**
- `query` (string, required)
- `page` (integer, default: 0) — 0-based page number
- `limit` (integer, default: 10, max: 100)

**Outputs:**
- `publications` (array) — each item: `id`, `name`, `subdomain`, `custom_domain`, `logo_url`, `description`, `subscriber_count`
- `more` (boolean) — whether additional pages exist

---

### 5. `search_posts`
Search posts within a specific publication.

**Endpoint:** `GET https://{publication_url}/api/v1/posts/search`

**Inputs:**
- `publication_url` (string, required)
- `query` (string, required)
- `offset` (integer, default: 0)
- `limit` (integer, default: 10)

**Outputs:**
- `posts` (array) — same shape as `get_publication_posts` output items

---

### 6. `get_post_comments`
Get comments on a specific post.

**Endpoint:** `GET https://{publication_url}/api/v1/post/{post_id}/comments`

Note: uses numeric `post_id` (from archive/post listing), not slug.

**Inputs:**
- `publication_url` (string, required)
- `post_id` (integer, required) — numeric post ID
- `sort` (enum: `best` | `newest`, default: `best`)
- `all_comments` (boolean, default: true)

**Outputs:**
- `comments` (array) — each item: `id`, `body`, `date`, `author_name`, `author_id`, `like_count`, `children` (nested replies array, same shape)

---

### 7. `get_subscriptions`
Get the authenticated user's list of Substack subscriptions. **Requires auth.**

**Endpoint:** `GET https://substack.com/api/v1/user/{user_id}/public_profile/self`

Note: `user_id` is resolved by first calling `https://substack.com/api/v1/profile` to get the current user's numeric ID.

**Inputs:**
- *(none — uses authenticated session)*

**Outputs:**
- `subscriptions` (array) — each item: `name`, `subdomain`, `custom_domain`, `author_name`, `is_paid`, `subscriber_count`, `logo_url`

---

### 8. `get_reader_feed`
Get the authenticated user's Substack reader activity feed. **Requires auth.**

**Endpoint:** `GET https://substack.com/api/v1/reader/feed/profile/{user_id}`

**Inputs:**
- `types` (array of enum: `like` | `restack`, optional) — filter by activity type

**Outputs:**
- `items` (array) — each item: `id`, `type`, `date`, `post_title`, `post_url`, `publication_name`, `publication_url`

---

## Architecture

```
substack/
├── __init__.py
├── substack.py          # Entry point — all action handlers
├── config.json          # Actions + auth schema
├── requirements.txt     # httpx
├── icon.png
├── README.md
└── tests/
    ├── __init__.py
    ├── context.py
    └── test_substack.py
```

**Key design decisions:**

- **`httpx`** for async HTTP (consistent with other integrations in this repo that make HTTP calls)
- **No third-party Substack library** — avoids dependency on unofficial wrappers that may break; endpoints are simple REST calls
- **`publication_url` normalisation** — strip trailing slash and handle both `https://pub.substack.com` and custom domains transparently
- **Auth resolution for user actions** — `get_subscriptions` and `get_reader_feed` call `/api/v1/profile` first to resolve the numeric user ID, then proceed to the target endpoint
- **Error handling** — categorise HTTP errors as: `auth_error` (401/403), `not_found` (404), `rate_limited` (429), `server_error` (5xx), `api_error` (other)

---

## Testing

Tests use `unittest.mock` to patch `httpx.AsyncClient.get`. Cover:

- Success path for each action
- Auth header is set correctly when credentials provided
- Auth header absent when credentials not provided
- 401/403 raises auth error
- 404 raises not found error
- 429 raises rate limited error
- `publication_url` normalisation (trailing slash, http vs https)
- Pagination parameters passed correctly

---

## Limitations & Notes

- Paywalled post body is truncated without a valid paid-subscriber session
- Rate limiting: no official limit published; stay at ~1 req/sec for bulk use
- Session cookies can be invalidated by logging out in the browser
- Endpoints are undocumented and may change without notice
- Substack ToS prohibits scraping; personal/automation use is low risk but commercial use carries ToS risk
