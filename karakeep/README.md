# Karakeep Integration for Autohive

Connects Autohive to a self-hosted [Karakeep](https://karakeep.app) instance to save bookmarks and manage tags.

## Description

This integration covers bookmark and tag management:

- **Create bookmarks** with optional title, note, and summary. Duplicate URLs return the existing bookmark with `already_existed` set to true.
- **Attach tags by name** (missing names are created automatically)
- **Create and list tags**
- **List bookmarks**, including by tag
- **Search** bookmarks
- **Get** a bookmark by id

## Setup & Authentication

Karakeep is self-hosted. When connecting in Autohive, the user enters both:

1. **Base URL** — the URL of their Karakeep instance, including host and port (for example `http://localhost:3000`, `http://192.168.1.10:3000`, or `https://karakeep.example.com`)
2. **API Key** — created in that Karakeep app under **Settings → API Keys**

Do not include a trailing slash or `/api/v1` on the base URL. `http` is valid for local or private instances.

### Authentication Fields

| Field | Format | Used For |
|-------|--------|----------|
| `base_url` | Instance URL (host + port) | All actions |
| `api_key` | API key from the Karakeep app | All actions — Bearer token |

## Actions

### `create_bookmark`

Create a URL bookmark, or return the existing one if that URL is already saved.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | **Yes** | URL to bookmark |
| `title` | string | No | Optional title |
| `note` | string | No | Optional note |
| `summary` | string | No | Optional summary |
| `archived` | boolean | No | Archive on creation (default: `false`) |
| `favourited` | boolean | No | Favourite on creation (default: `false`) |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmark_id` | string | Bookmark id |
| `bookmark` | object | Bookmark object from Karakeep |
| `already_existed` | boolean | `true` if the URL was already saved |

---

### `attach_tags`

Attach tags to a bookmark by name. Tags that do not exist yet are created.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bookmark_id` | string | **Yes** | Bookmark id |
| `tags` | array of strings | **Yes** | Tag names |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `attached` | array of strings | IDs of attached tags |
| `count` | integer | Number of tag names sent |

---

### `search_bookmarks`

Full-text search over bookmarks.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **Yes** | Search string |
| `limit` | integer | No | Results per page (default: 20, max: 100) |
| `cursor` | string | No | Pagination cursor |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmarks` | array | Matching bookmarks |
| `count` | integer | Results in this page |
| `next_cursor` | string | Next page cursor, or null |

---

### `get_bookmark`

Retrieve a bookmark by id.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bookmark_id` | string | **Yes** | Bookmark id |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmark` | object | Bookmark object |

---

### `create_tag`

Create a tag by name.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | **Yes** | Tag name |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `tag_id` | string | Tag id |
| `name` | string | Tag name |
| `tag` | object | Tag object |

---

### `list_tags`

List tags, optionally filtered by name.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name_contains` | string | No | Substring filter |
| `limit` | integer | No | Results per page (default: 20, max: 1000) |
| `cursor` | string | No | Pagination cursor |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `tags` | array | Tag objects |
| `count` | integer | Results in this page |
| `next_cursor` | string | Next page cursor, or null |

---

### `list_bookmarks`

List bookmarks. Optional filters: `archived`, `favourited`.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `archived` | boolean | No | Filter by archived status |
| `favourited` | boolean | No | Filter by favourited status |
| `limit` | integer | No | Results per page (default: 20, max: 100) |
| `cursor` | string | No | Pagination cursor |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmarks` | array | Bookmark objects |
| `count` | integer | Results in this page |
| `next_cursor` | string | Next page cursor, or null |

---

### `get_tag_bookmarks`

List bookmarks that have a given tag.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tag_id` | string | **Yes** | Tag id |
| `limit` | integer | No | Results per page (default: 20, max: 100) |
| `cursor` | string | No | Pagination cursor |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmarks` | array | Bookmark objects |
| `count` | integer | Results in this page |
| `next_cursor` | string | Next page cursor, or null |

## Requirements

- `autohive-integrations-sdk`

## Testing

```bash
cd autohive-integrations
uv run --with-requirements requirements-test.txt --with-requirements karakeep/requirements.txt pytest karakeep/tests/test_karakeep_unit.py
```

Live tests call a real Karakeep instance. Set `KARAKEEP_BASE_URL` to that instance (for example `http://localhost:3000`) and `KARAKEEP_API_KEY` to a key from **Settings → API Keys**:

```bash
uv run --with-requirements requirements-test.txt --with-requirements karakeep/requirements.txt pytest karakeep/tests/test_karakeep_integration.py -m integration
```

## API Reference

- [Karakeep API Docs](https://docs.karakeep.app/API/karakeep-api)
- Base URL: `{your_karakeep}/api/v1/...`
- Authentication: `Authorization: Bearer <api_key>`
- Rate limits: none published; they depend on the self-hosted instance


## Version History

- **1.0.0** — Initial release: `create_bookmark`, `attach_tags`, `search_bookmarks`, `get_bookmark`, `create_tag`, `list_tags`, `list_bookmarks`, `get_tag_bookmarks`
