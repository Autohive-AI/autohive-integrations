# Box Integration for Autohive

Box is a cloud content management platform for storing, sharing, and collaborating on files. This integration provides access to Box files and folders via the Box API.

## Setup & Authentication

- **Auth type**: Custom (OAuth2 access token)
- **Field required**: `access_token`
- Generate an access token from the [Box Developer Console](https://developer.box.com/).

## Actions

### `list_shared_folders`
List all shared folders accessible to the authenticated user.

### `list_files`
List files in a Box folder.

**Required:** `folder_id`

### `list_folder_contents`
List the full contents of a specific folder, including subfolders and files.

**Required:** `folder_id`

### `get_file`
Retrieve metadata and download URL for a specific file.

**Required:** `file_id`

### `upload_file`
Upload a file to a Box folder.

**Required:** `folder_id`, `file_name`, `content`

## Requirements

- `autohive-integrations-sdk~=1.0.2`

## API Info

- **Base URL**: `https://api.box.com/2.0`
- **Docs**: [https://developer.box.com/reference](https://developer.box.com/reference)

## Rate Limiting

Box enforces per-user and per-app rate limits. See [Box rate limits](https://developer.box.com/guides/api-calls/permissions-and-errors/rate-limits/).

## Error Handling

| Error | Cause |
|-------|-------|
| 401 Unauthorized | Invalid or expired access token |
| 404 Not Found | File or folder ID not found |
| 403 Forbidden | Insufficient permissions |

## Troubleshooting

**401 errors**: Re-authenticate and provide a fresh access token.

**404 on folder**: Verify the `folder_id` — root folder ID is `"0"`.

## Version History

- **v1.0.0** — Initial release. 5 actions: list_shared_folders, list_files, list_folder_contents, get_file, upload_file.
