# Dropbox Integration for Autohive

Connects Autohive to the Dropbox API to enable file browsing, metadata retrieval, uploads, and file management operations.

## Description

This integration provides access to Dropbox's file storage platform. It lets users browse folders, retrieve metadata, get temporary download links, upload files, create folders, and manage files (move, copy, delete) directly from Autohive.

The integration targets Dropbox API v2 with OAuth 2.0 authentication and exposes 8 actions covering file listing, metadata, downloads, uploads, and file management.

## Setup & Authentication

This integration uses **OAuth 2.0** via Autohive's platform auth — no API keys or manual token handling are needed.

### OAuth scopes

- `files.metadata.read` — Read file and folder metadata
- `files.content.read` — Read file content and download files
- `files.content.write` — Upload, create, delete, move, and copy files/folders

### Setup steps in Autohive

1. Add the Dropbox integration in Autohive.
2. Click **Connect to Dropbox** to authorize the integration.
3. Sign in to your Dropbox account when prompted.
4. Review and authorize the requested permissions.
5. You'll be redirected back to Autohive once authorization is complete.

Token management and refresh are handled by the platform.

## Action Results

Each action returns its action-specific payload directly. Errors are surfaced as `ActionError` results (no `result`/`error` keys are mixed into the success payload).

Example success — `get_metadata`:

```json
{
  "metadata": {
    ".tag": "file",
    "name": "document.pdf",
    "path_display": "/Documents/document.pdf",
    "id": "id:a4ayc_80_OEAAAAAAAAAXw",
    "size": 12345
  }
}
```

Errors come back from the SDK as an `ActionError` payload with a single `message` field, e.g. `"path/not_found/.."`.

## Actions

### File and folder listing

#### `list_folder`

Lists the contents of a folder. Supports pagination — pass the returned `cursor` back to `list_folder` when `has_more` is `true`.

**Inputs:**
- `path` (optional, default `""`) — Folder path (empty string is the root, `"/folder_name"` for subfolders).
- `cursor` (optional) — Cursor from a previous `list_folder` call. When provided, other parameters are ignored.
- `recursive` (optional, default `false`)
- `include_deleted` (optional, default `false`)
- `include_has_explicit_shared_members` (optional, default `false`)
- `include_mounted_folders` (optional, default `true`)
- `limit` (optional, 1–2000)

**Outputs:**
- `entries` — Array of file and folder entries.
- `cursor` — Pagination cursor (omitted when not provided by the API).
- `has_more` — Whether more entries are available.

Each entry includes `.tag` (`"file"` or `"folder"`), `name`, `path_display`, `id`, and (for files) `size`, `client_modified`, `server_modified`, etc.

---

### Metadata

#### `get_metadata`

Returns metadata for a file or folder at a given path.

**Inputs:**
- `path` (required) — e.g. `"/folder/file.txt"`.
- `include_deleted` (optional, default `false`)
- `include_has_explicit_shared_members` (optional, default `false`)

**Outputs:**
- `metadata` — File or folder metadata object.

---

### Download

#### `get_temporary_link`

Gets a temporary link to stream a file's content. Valid for 4 hours.

**Inputs:**
- `path` (required) — File path.

**Outputs:**
- `link` — Temporary download URL (no auth required for the next 4 hours).
- `metadata` — File metadata.

---

### Write operations

#### `upload_file`

Upload a file to Dropbox. Files are supplied as a structured object so the action can be wired to any file source that produces base64-encoded content (chat uploads, prior action outputs, etc.).

**Inputs:**
- `file` (required) — Object:
  - `name` — File name (used as the destination filename).
  - `content` — File content encoded as base64. Zero-byte content (`""`) is allowed.
  - `contentType` — MIME type.
- `path` (optional, default root) — Destination folder. The file's `name` is appended to this. A leading `/` is added automatically and trailing slashes are stripped. For backwards compatibility with the previous flat-path schema, if `path` already ends in the same `name` (e.g. `"/folder/a.txt"` with `file.name = "a.txt"`) the path is used as-is.
- `mode` (optional, default `"add"`) — `"add"` (rename on conflict), `"overwrite"`, or `"update"`.
- `autorename` (optional, default `false`)
- `mute` (optional, default `false`)

**Outputs:**
- `file` — Uploaded file metadata returned by Dropbox.

---

#### `create_folder`

Create a new folder.

**Inputs:**
- `path` (required) — e.g. `"/my_folder"`.
- `autorename` (optional, default `false`)

**Outputs:**
- `folder` — Created folder metadata.

---

#### `delete`

Delete a file or folder. Works for both.

**Inputs:**
- `path` (required) — e.g. `"/folder/file.txt"` or `"/folder"`.

**Outputs:**
- `metadata` — Metadata of the deleted item.

---

#### `move`

Move a file or folder to a different location.

**Inputs:**
- `from_path` (required)
- `to_path` (required)
- `autorename` (optional, default `false`)
- `allow_ownership_transfer` (optional, default `false`)

**Outputs:**
- `metadata` — Metadata of the moved item.

---

#### `copy`

Copy a file or folder to a different location.

**Inputs:**
- `from_path` (required)
- `to_path` (required)
- `autorename` (optional, default `false`)

**Outputs:**
- `metadata` — Metadata of the copied item.

---

## Requirements

- `autohive-integrations-sdk~=2.0.0`

## API Information

- **API Version:** v2
- **Base URLs:**
  - API: `https://api.dropboxapi.com/2`
  - Content: `https://content.dropboxapi.com/2`
- **Authentication:** OAuth 2.0 (platform-managed)
- **Documentation:** https://www.dropbox.com/developers/documentation/http/documentation
- **Rate limits:** Dropbox uses a points-based rate limiting system. The SDK surfaces 429s as `RateLimitError` which the actions return as `ActionError`.

## Important Notes

- OAuth tokens are automatically managed and refreshed by the platform.
- All paths are relative to the app's root folder.
- Empty string (`""`) represents the root folder for `list_folder`. All other paths must start with `/`.
- Files and folders have both `path_display` (display format) and `path_lower` (normalized lowercase).
- Each item has a unique `id` (e.g. `"id:abc123xyz"`).
- Temporary links from `get_temporary_link` expire after 4 hours.
- Dropbox does **not** auto-create parent folders for `upload_file` or `copy` — create them first with `create_folder` when needed.

## Testing

### Unit tests (mocked, run in CI)

```bash
python -m pytest dropbox/tests/test_dropbox_unit.py -v
```

### Integration tests (real Dropbox API)

Integration tests are excluded from CI. To run them locally, set `DROPBOX_ACCESS_TOKEN` in the repo-root `.env` (see [.env.example](../.env.example)) and pick the appropriate marker:

```bash
# Safe — read-only tests against your Dropbox account
pytest dropbox/tests/test_dropbox_integration.py -m "integration and not destructive"

# ⚠ Destructive — creates, copies, moves, and deletes files inside
# DROPBOX_TEST_FOLDER (default: /autohive_integration_test). Each run uses a
# unique subfolder that is cleaned up at the end, but this still mutates real
# data — only run against a test Dropbox account.
pytest dropbox/tests/test_dropbox_integration.py -m "integration and destructive"
```

Environment variables (documented in repo-root `.env.example`):

- `DROPBOX_ACCESS_TOKEN` — required. OAuth access token.
- `DROPBOX_TEST_FOLDER` — optional. Parent folder for destructive tests (default `/autohive_integration_test`).

## Common Use Cases

- Browse and explore Dropbox folder hierarchies (`list_folder`).
- Inspect file/folder metadata before processing (`get_metadata`).
- Generate short-lived download links to share with downstream actions (`get_temporary_link`).
- Save files produced by prior workflow steps into Dropbox (`upload_file`).
- Reorganize files: `create_folder`, `move`, `copy`, `delete`.

## Path Examples

- Root folder: `""`
- Subfolder: `"/Documents"`
- File in root: `"/file.txt"`
- File in subfolder: `"/Documents/report.pdf"`
- Nested path: `"/Projects/2024/Q1/report.xlsx"`

## OAuth Scopes Explained

- **files.metadata.read** — listing folders and reading file/folder metadata.
- **files.content.read** — downloading file content and getting temporary links.
- **files.content.write** — uploading files, creating folders, deleting, moving, and copying.

## Version History

- **2.0.0**
  - Upgraded to `autohive-integrations-sdk~=2.0.0` (uses `FetchResponse` and `ActionError`).
  - **Breaking**: `upload_file` now takes a structured `file` object (`{ name, content, contentType }`) instead of a flat `content` string, so the platform's file inputs can be wired in directly. The `path` input is now an optional destination folder; the file name comes from `file.name`. Callers passing the previous full-file-path `path` continue to work via a backwards-compatibility fallback when the basename matches `file.name`.
  - Errors are now returned as `ActionError`. Output schemas no longer carry `result`/`error` keys.
  - Removed the redundant `list_folder_continue` action — `list_folder` already handles cursor-based pagination.
  - Added `pytest` unit and integration test suites.
- **1.0.0** — Initial release with 9 actions (SDK 1.0.x).

## Sources

- [Dropbox API v2 Documentation](https://www.dropbox.com/developers/documentation/http/documentation)
- [Dropbox OAuth Guide](https://developers.dropbox.com/oauth-guide)
- [Customizing OAuth Scopes](https://dropbox.tech/developers/customizing-scopes-in-oauth-flow)
