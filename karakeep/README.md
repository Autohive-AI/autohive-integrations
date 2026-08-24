# Karakeep Integration for Autohive

Connects Autohive to a Karakeep instance (Karakeep Cloud or self-hosted) to save bookmarks and manage tags.

## Description

This integration covers bookmark and tag management:

- **Create bookmarks** (link, text, or asset) with optional title, note, and summary. Duplicate URLs return the existing bookmark with `already_existed` set to true.
- **Attach tags by name or id** (missing names are created automatically)
- **Create and list tags**
- **List bookmarks**, including by tag
- **Search** bookmarks
- **Get** a bookmark by id

## Setup & Authentication

Karakeep is available as Karakeep Cloud (https://cloud.karakeep.app) or as a self-hosted app. This integration works with both. When connecting in Autohive, the user enters:

1. **Base URL** — the HTTPS URL of their Karakeep instance:
   - **Karakeep Cloud:** `https://cloud.karakeep.app`
   - **Self-hosted:** your HTTPS URL, for example `https://karakeep.example.com`
2. **API Key** — created in that Karakeep app under **Settings → API Keys**. Grant the scopes for the actions you want (bookmarks read/write, tags read/write). Since Karakeep 0.32, API keys have granular per-resource scopes; if the key lacks a scope for an action, that action will return an error.

Do not include a trailing slash or `/api/v1` on the base URL.

### HTTPS is required

The integration only accepts `https://` URLs. The API key is sent in the `Authorization` header on every request; allowing plain HTTP would leak that key to anyone on the network path.

Karakeep itself does not terminate TLS — the Docker container serves plain HTTP. To use this integration with a self-hosted instance you must put Karakeep behind something that provides HTTPS. Common options:

- **Cloudflare Tunnel** — free, gives you a public HTTPS hostname pointed at your instance without exposing your IP or opening ports
- **Tailscale Funnel** — public HTTPS from a Tailscale-connected node, similar model to Cloudflare Tunnel
- **Caddy** or **nginx** + Let's Encrypt — traditional reverse proxy with automated certificates
- **Traefik** — reverse proxy with automated certificates, popular with Docker Compose setups

If you are running Karakeep on a VM with only a raw `http://<ip>:<port>` endpoint, this integration will refuse to connect. Front it with one of the options above (or use Karakeep Cloud) and it will work.

### Authentication Fields

| Field | Format | Used For |
|-------|--------|----------|
| `base_url` | Instance URL (https required) | All actions |
| `api_key` | API key from the Karakeep app | All actions — Bearer token |

## Actions

### `create_bookmark`

Create a bookmark of type `link` (URL), `text` (note), or `asset` (image/pdf). For link bookmarks, returns the existing one if the URL is already saved.

**Inputs (type-dependent):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | `"link" \| "text" \| "asset"` | No (default `"link"`) | Bookmark type |
| `url` | string | If `type=link` | URL to bookmark |
| `text` | string | If `type=text` | Text content |
| `asset_type` | `"image" \| "pdf"` | If `type=asset` | Asset media type |
| `asset_id` | string | If `type=asset` | ID from a prior Karakeep asset upload (`POST /assets`). This integration does not upload files. |
| `file_name` | string | No | For asset bookmarks |
| `source_url` | string | No | For text/asset bookmarks |
| `title` | string | No | Optional title (max 1000 chars) |
| `note` | string | No | Optional note |
| `summary` | string | No | Optional summary |
| `archived` | boolean | No | Archive on creation (default: false) |
| `favourited` | boolean | No | Favourite on creation (default: false) |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `bookmark_id` | string | Bookmark id |
| `bookmark` | object | Bookmark object from Karakeep |
| `already_existed` | boolean | `true` if this URL was already saved (only meaningful for type `link`) |

---

### `attach_tags`

Attach tags to a bookmark by name or existing tag id. Tags that do not exist yet are created when attached by name.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bookmark_id` | string | **Yes** | Bookmark id |
| `tags` | array of strings | No | Tag names to attach |
| `tag_ids` | array of strings | No | Existing tag IDs to attach |
| `attached_by` | `"ai" \| "human"` | No | Who is attaching these tags. Omitted unless set; Karakeep defaults to `human` |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `attached` | array of strings | IDs of attached tags |
| `count` | integer | Number of tag items sent |

---

### `search_bookmarks`

Full-text, semantic, or hybrid search over bookmarks.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **Yes** | Search string |
| `limit` | integer | No | Results per page (default: 20, max: 100) |
| `cursor` | string | No | Pagination cursor |
| `search_mode` | `"fts" \| "semantic" \| "hybrid"` | No | Search strategy (default: `fts`) |
| `sort_order` | `"asc" \| "desc" \| "relevance"` | No | Result ordering (default: `relevance`) |
| `include_content` | boolean | No | Include full HTML/text content (default: false) |

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
| `include_content` | boolean | No | Include full HTML/text content (default: false) |

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

List tags, optionally filtered by name or attachment source.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name_contains` | string | No | Substring filter |
| `limit` | integer | No | Results per page (default: 20, max: 1000) |
| `cursor` | string | No | Pagination cursor |
| `sort` | `"name" \| "usage" \| "relevance"` | No | Sort order (default: `usage`) |
| `attached_by` | `"ai" \| "human" \| "none"` | No | Filter by who attached tags |

**Outputs:**

| Field | Type | Description |
|-------|------|-------------|
| `tags` | array | Tag objects with usage counts |
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
| `sort_order` | `"asc" \| "desc"` | No | Sort by creation date (default: `desc`) |
| `include_content` | boolean | No | Include full HTML/text content (default: false) |

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
| `sort_order` | `"asc" \| "desc"` | No | Sort by creation date (default: `desc`) |
| `include_content` | boolean | No | Include full HTML/text content (default: false) |

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

Live tests call a real Karakeep instance. Set `KARAKEEP_BASE_URL` (https:// only) and `KARAKEEP_API_KEY`:

```bash
# KARAKEEP_BASE_URL=https://cloud.karakeep.app
# KARAKEEP_API_KEY=...
```

Plain `http://` URLs are refused — the API key is sent on every request.

```bash
# Read-only integration tests (default — safe to run against any instance)
uv run --with-requirements requirements-test.txt --with-requirements karakeep/requirements.txt \
  pytest karakeep/tests/test_karakeep_integration.py -m "integration and not destructive"

# Include destructive tests (creates and modifies real data)
uv run --with-requirements requirements-test.txt --with-requirements karakeep/requirements.txt \
  pytest karakeep/tests/test_karakeep_integration.py -m integration
```

## API Reference

- [Karakeep API Docs](https://docs.karakeep.app/api/karakeep-api/)
- Base URL: `{your_karakeep}/api/v1/...`
- Authentication: `Authorization: Bearer <api_key>`
- Rate limits: depend on the instance. Karakeep Cloud may impose limits; self-hosted has none unless configured.

## Version History

- **1.0.0** — Initial release: `create_bookmark` (link, text, asset), `attach_tags` (names or ids), `search_bookmarks`, `get_bookmark`, `create_tag`, `list_tags`, `list_bookmarks`, `get_tag_bookmarks`. HTTPS-only base URL; works with Karakeep Cloud and self-hosted.
