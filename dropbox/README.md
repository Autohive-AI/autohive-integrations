# Dropbox Integration for Autohive

Connects Autohive to the Dropbox API to enable file browsing, metadata retrieval, uploads, and file management operations.

## Description

This integration provides full access to Dropbox's file storage platform. It allows users to browse folders, retrieve metadata, get temporary download links, upload files, create folders, and manage files (move, copy, delete) directly from Autohive.

The integration uses Dropbox API v2 with OAuth 2.0 authentication and implements 9 comprehensive actions covering file listing, metadata, downloads, uploads, and file management.

## Setup & Authentication

This integration uses **OAuth 2.0** authentication for secure access to your Dropbox account.

### Authentication Method

The integration uses OAuth 2.0 with the following scopes:
- `account_info.read` - Read account information
- `files.metadata.read` - Read file and folder metadata
- `files.content.read` - Read file content and download files
- `files.content.write` - Upload, create, delete, move, and copy files/folders


### Setup Steps in Autohive

1. Add Dropbox integration in Autohive
2. Click "Connect to Dropbox" to authorize the integration
3. Sign in to your Dropbox account when prompted
4. Review and authorize the requested permissions
5. You'll be redirected back to Autohive once authorization is complete

The OAuth integration automatically handles token management and refresh, so you don't need to manually manage access tokens.

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- Additional action-specific data fields (e.g., `entries`, `metadata`, `account`)

Example successful response:
```json
{
  "result": true,
  "metadata": {
    ".tag": "file",
    "name": "document.pdf",
    "path_display": "/Documents/document.pdf",
    "id": "id:a4ayc_80_OEAAAAAAAAAXw"
  }
}
```

Example error response:
```json
{
  "result": false,
  "error": "path/not_found/...",
  "metadata": {}
}
```

## Actions

### File and Folder Listing (2 actions)

#### `list_folder`
Lists contents of a folder.

**Inputs:**
- `path` (optional): Path to the folder (default: "" for root folder, or "/folder_name" for subfolders)
- `recursive` (optional): If true, list folder recursively (default: false)
- `include_deleted` (optional): If true, include deleted files (default: false)
- `include_has_explicit_shared_members` (optional): If true, include sharing info (default: false)
- `include_mounted_folders` (optional): If true, include mounted folders (default: true)
- `limit` (optional): Maximum number of results to return (1-2000)

**Outputs:**
- `entries`: Array of file and folder entries
- `cursor`: Cursor for pagination (use with list_folder_continue)
- `has_more`: Whether there are more entries to fetch
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Entry Structure:**
Each entry includes:
- `.tag`: "file" or "folder"
- `name`: File or folder name
- `path_display`: Display path
- `id`: Unique identifier
- For files: `size`, `client_modified`, `server_modified`, etc.

---

#### `list_folder_continue`
Continues listing folder contents using a cursor from list_folder.

**Inputs:**
- `cursor` (required): Cursor from previous list_folder call

**Outputs:**
- `entries`: Array of file and folder entries
- `cursor`: Cursor for pagination
- `has_more`: Whether there are more entries to fetch
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Metadata (1 action)

#### `get_metadata`
Returns metadata for a file or folder at a given path.

**Inputs:**
- `path` (required): Path to the file or folder (e.g., "/folder/file.txt")
- `include_deleted` (optional): If true, will return deleted metadata (default: false)
- `include_has_explicit_shared_members` (optional): If true, include sharing info (default: false)

**Outputs:**
- `metadata`: File or folder metadata object
  - `.tag`: "file" or "folder"
  - `name`: File or folder name
  - `path_display`: Display path
  - `id`: Unique identifier
  - For files: `size`, `client_modified`, `server_modified`, `content_hash`, etc.
  - For folders: `shared_folder_id`, etc.
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

### Download (1 action)

#### `get_temporary_link`
Gets a temporary link to stream content of a file. Valid for 4 hours.

**Inputs:**
- `path` (required): Path to the file (e.g., "/folder/file.txt")

**Outputs:**
- `link`: Temporary download link (valid for 4 hours)
- `metadata`: Metadata for the file
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

**Note:** The temporary link allows direct download of the file content without authentication for 4 hours.

---

### Write Operations (5 actions)

#### `upload_file`
Upload a file to Dropbox.

**Inputs:**
- `path` (required): Path where the file should be saved (e.g., "/folder/file.txt")
- `content` (required): File content as a base64-encoded string
- `mode` (optional): How to handle conflicts - "add" (rename if exists), "overwrite", or "update" (default: "add")
- `autorename` (optional): If true, rename the file if there's a conflict (default: false)
- `mute` (optional): If true, don't notify the user about this upload (default: false)

**Outputs:**
- `file`: Uploaded file metadata
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `create_folder`
Create a new folder in Dropbox.

**Inputs:**
- `path` (required): Path of the folder to create (e.g., "/my_folder")
- `autorename` (optional): If true, rename the folder if there's a conflict (default: false)

**Outputs:**
- `folder`: Created folder metadata
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `delete`
Delete a file or folder from Dropbox. Works for both files and folders.

**Inputs:**
- `path` (required): Path to the file or folder to delete (e.g., "/folder/file.txt" or "/folder")

**Outputs:**
- `metadata`: Metadata of the deleted item
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `move`
Move a file or folder to a different location in Dropbox.

**Inputs:**
- `from_path` (required): Current path of the file or folder
- `to_path` (required): New path for the file or folder
- `autorename` (optional): If true, rename if there's a conflict at destination (default: false)
- `allow_ownership_transfer` (optional): Allow moving a shared folder to a different parent (default: false)

**Outputs:**
- `metadata`: Metadata of the moved item
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

#### `copy`
Copy a file or folder to a different location in Dropbox.

**Inputs:**
- `from_path` (required): Path of the file or folder to copy
- `to_path` (required): Destination path for the copy
- `autorename` (optional): If true, rename if there's a conflict at destination (default: false)

**Outputs:**
- `metadata`: Metadata of the copied item
- `result`: Success status (boolean)
- `error`: Error message if action failed (optional)

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK

## API Information

- **API Version**: v2
- **Base URLs**:
  - API: `https://api.dropboxapi.com/2`
  - Content: `https://content.dropboxapi.com/2`
- **Authentication**: OAuth 2.0
- **Documentation**: https://www.dropbox.com/developers/documentation/http/documentation
- **Rate Limits**: Dropbox uses a points-based rate limiting system. Each endpoint costs different points.

## Important Notes

- OAuth tokens are automatically managed by the platform
- Tokens are automatically refreshed when needed
- You can revoke access at any time from your Dropbox account settings
- All paths are relative to the app's root folder
- Empty string ("") represents the root folder
- All other paths must start with a slash (e.g., "/Documents/file.txt")
- Files and folders have both `path_display` (display format) and `path_lower` (normalized lowercase)
- Each file and folder has a unique `id` (e.g., "id:abc123xyz")
- Temporary links from `get_temporary_link` expire after 4 hours
- Write operations (upload, delete, move, copy) require appropriate OAuth scopes

## Testing

To test the integration:

1. Navigate to the integration directory: `cd dropbox`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OAuth credentials through the Autohive platform
4. Run tests to verify functionality

## Common Use Cases

**File Browsing:**
1. List all files in root folder
2. Navigate through folder hierarchy
3. Get detailed metadata for specific files
4. Check file sizes and modification dates

**File Access:**
1. Get temporary download links for files
2. Access file content without full download

**File Management:**
1. Upload new files to Dropbox
2. Create folder structures
3. Delete files or folders
4. Move files between folders
5. Copy files to new locations

**Workflow Automation:**
1. Monitor folders for new files
2. Extract metadata for reporting
3. Generate download links for sharing
4. Automate file organization (move/copy)
5. Backup workflows with uploads

## Path Examples

- Root folder: `""`
- Subfolder: `"/Documents"`
- File in root: `"/file.txt"`
- File in subfolder: `"/Documents/report.pdf"`
- Nested path: `"/Projects/2024/Q1/report.xlsx"`

## OAuth Scopes Explained

- **account_info.read**: Allows reading basic account information like name, email, and account type
- **files.metadata.read**: Allows listing folders and reading file/folder metadata
- **files.content.read**: Allows downloading file content and getting temporary links
- **files.content.write**: Allows uploading files, creating folders, deleting, moving, and copying files/folders


## Version History

- **1.0.0** - Initial release with 9 actions
  - Listing: list_folder, list_folder_continue (2 actions)
  - Metadata: get_metadata (1 action)
  - Download: get_temporary_link (1 action)
  - Write Operations: upload_file, create_folder, delete, move, copy (5 actions)

## Sources

- [Dropbox API v2 Documentation](https://www.dropbox.com/developers/documentation/http/documentation)
- [Dropbox OAuth Guide](https://developers.dropbox.com/oauth-guide)
- [Customizing OAuth Scopes](https://dropbox.tech/developers/customizing-scopes-in-oauth-flow)
