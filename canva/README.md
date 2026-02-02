# Canva Integration

Comprehensive Canva integration for managing assets, designs, and folders through the Canva Connect API.

## Overview

This integration provides full access to Canva's Connect API, enabling workflows to:
- Manage and organize assets (images, videos, audio)
- Create and export designs in various formats
- Organize content using folders

## Authentication

This integration uses OAuth 2.0 with PKCE (Proof Key for Code Exchange) for secure authentication. The following scopes are requested:

- `asset:read` - View asset metadata
- `asset:write` - Upload, update, and delete assets
- `design:content:read` - View design contents
- `design:content:write` - Create designs
- `design:meta:read` - View design metadata
- `folder:read` - View folder metadata and contents
- `folder:write` - Create, update, and delete folders

## Actions

### Asset Management

#### Upload Asset
Upload an asset (image, video, or audio) to Canva's asset library.

**Inputs:**
- `file` or `files`: File object(s) with base64-encoded content, name, and contentType

**Outputs:**
- `job_id`: Upload job ID for status tracking
- `status`: Initial job status
- `result`: Boolean indicating success
- `error`: Error message if failed

**Note:** This is an asynchronous operation. Use `get_asset_upload_status` to poll for completion.

#### Get Asset Upload Status
Check the status of an asset upload job and retrieve asset details when complete.

**Inputs:**
- `job_id` (required): Upload job ID from upload_asset action

**Outputs:**
- `status`: Upload status (in_progress, success, failed)
- `asset`: Complete asset details including id, name, tags, thumbnail (only if status is "success")
- `result`: Boolean indicating success
- `error`: Error message if failed

**Example Response (Success):**
```json
{
  "status": "success",
  "asset": {
    "id": "Msd59349ff",
    "name": "Company Logo",
    "tags": ["branding", "logo"],
    "created_at": 1377396000,
    "updated_at": 1692928800,
    "thumbnail": {
      "width": 595,
      "height": 335,
      "url": "https://document-export.canva.com/..."
    }
  },
  "result": true
}
```

#### Get Asset
Retrieve metadata for a specific asset.

**Inputs:**
- `asset_id` (required): Asset ID

**Outputs:**
- `asset`: Asset metadata including id, name, tags, timestamps
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Update Asset
Update an asset's name or tags.

**Inputs:**
- `asset_id` (required): Asset ID
- `name` (optional): New name for the asset
- `tags` (optional): New tags for the asset

**Outputs:**
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Delete Asset
Delete an asset (moves to trash).

**Inputs:**
- `asset_id` (required): Asset ID

**Outputs:**
- `result`: Boolean indicating success
- `error`: Error message if failed

### Design Management

#### Create Design
Create a new blank Canva design using preset types.

**Inputs:**
- `preset_type` (required): Design type - 'doc' (Canva's online text editor), 'whiteboard' (infinite design space), or 'presentation' (for presenting to an audience)
- `title` (optional): Design title (1-255 characters)
- `asset_id` (optional): Image asset ID to insert into the design (currently only supports image assets)

**Outputs:**
- `design`: Created design details including id, title, and URLs
- `result`: Boolean indicating success
- `error`: Error message if failed

**Example:**
```json
{
  "preset_type": "presentation",
  "title": "Q4 Sales Presentation"
}
```

#### List Designs
List user's Canva designs with optional filtering and sorting.

**Inputs:**
- `query` (optional): Search term to filter designs (max 255 characters)
- `continuation` (optional): Pagination token
- `ownership` (optional): Filter by ownership - `any` (default, owned by and shared with user), `owned` (owned by user), `shared` (shared with user)
- `sort_by` (optional): Sort method - `relevance` (default), `modified_descending`, `modified_ascending`, `title_descending`, `title_ascending`

**Outputs:**
- `designs`: Array of design objects with id, title, timestamps
- `continuation`: Token for next page of results
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Get Design
Retrieve metadata for a specific design.

**Inputs:**
- `design_id` (required): Design ID

**Outputs:**
- `design`: Design metadata including id, title, timestamps, URLs
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Export Design
Export a Canva design to various formats.

**Inputs:**
- `design_id` (required): Design ID
- `format` (required): Export format type (pdf, png, jpg, pptx, gif, mp4)
- `export_quality` (optional): Overall export quality - `regular` (default) or `pro` (may fail if user lacks Canva Pro)
- `jpg_quality` (optional): JPG compression quality (1-100, default 85)
- `image_quality` (optional): Quality for PNG/MP4/GIF - orientation_resolution format (e.g., 'horizontal_1080p')
- `paper_size` (optional): PDF paper size for Documents - `a4`, `a3`, `letter`, `legal`
- `width` (optional): Width in pixels (40-25000) for JPG/PNG exports
- `height` (optional): Height in pixels (40-25000) for JPG/PNG exports
- `lossless` (optional): PNG only - export without compression (default true)
- `transparent_background` (optional): PNG only - export with transparency (requires Canva Pro)
- `as_single_image` (optional): PNG only - merge multi-page designs into single image
- `pages` (optional): Array of specific page numbers to export

**Outputs:**
- `job_id`: Export job ID for status tracking
- `result`: Boolean indicating success
- `error`: Error message if failed

**Note:** This is an asynchronous operation. Use `get_export_status` to poll for completion and retrieve download URLs.

#### Get Export Status
Check the status of a design export job and get download URLs.

**Inputs:**
- `export_id` (required): Export job ID from export_design action

**Outputs:**
- `status`: Export status (in_progress, success, failed)
- `urls`: Array of download URLs for exported files
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Import Design
Import external design files (PDF, PPTX, etc.) into Canva as editable designs.

**Inputs:**
- `file` or `files`: File object(s) with base64-encoded content, name, and contentType
- `title` (optional): Title for the imported design (uses filename if not provided)

**Outputs:**
- `job_id`: Import job ID for status tracking
- `status`: Initial job status
- `result`: Boolean indicating success
- `error`: Error message if failed

**Note:** This is an asynchronous operation. Use `get_design_import_status` to poll for completion. Large files may be split into multiple Canva designs.

#### Get Design Import Status
Check the status of a design import job and retrieve imported design details.

**Inputs:**
- `job_id` (required): Import job ID from import_design action

**Outputs:**
- `status`: Import status (in_progress, success, failed)
- `designs`: Array of imported design objects with id, title, urls (only if status is "success")
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Import Design from URL
Import a design from a publicly accessible URL instead of uploading binary data.

**Inputs:**
- `url` (required): Publicly accessible file URL (1-2048 characters)
- `title` (required): Title for the imported design (1-255 characters)
- `mime_type` (optional): MIME type of the file (auto-detected if omitted)

**Outputs:**
- `job_id`: URL import job ID for status tracking
- `status`: Initial job status (typically "in_progress")
- `result`: Boolean indicating success
- `error`: Error message if failed

**Example:**
```json
{
  "url": "https://example.com/presentations/sales-report.pptx",
  "title": "Q4 Sales Report",
  "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
}
```

**Note:** This is an asynchronous operation. Use `get_url_import_status` to poll for completion.

#### Get URL Import Status
Check the status of a URL import job and retrieve imported design details.

**Inputs:**
- `job_id` (required): URL import job ID from import_design_from_url action

**Outputs:**
- `status`: Import status (in_progress, success, failed)
- `designs`: Array of imported design objects with id, title, urls (only if status is "success")
- `result`: Boolean indicating success
- `error`: Error message if failed

### Folder Management

#### Create Folder
Create a new folder in Canva.

**Inputs:**
- `name` (required): Folder name
- `parent_folder_id` (optional): Parent folder ID (defaults to root)

**Outputs:**
- `folder`: Created folder details with id and name
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Get Folder
Retrieve metadata for a specific folder.

**Inputs:**
- `folder_id` (required): Folder ID

**Outputs:**
- `folder`: Folder metadata including id, name, timestamps
- `result`: Boolean indicating success
- `error`: Error message if failed

#### List Folder Items
List all items (designs, assets, folders) in a folder.

**Inputs:**
- `folder_id` (required): Folder ID
- `continuation` (optional): Pagination token

**Outputs:**
- `items`: Array of items with id, name, and type
- `continuation`: Token for next page of results
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Update Folder
Update a folder's name.

**Inputs:**
- `folder_id` (required): Folder ID
- `name` (required): New folder name

**Outputs:**
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Delete Folder
Delete a folder.

**Inputs:**
- `folder_id` (required): Folder ID

**Outputs:**
- `result`: Boolean indicating success
- `error`: Error message if failed

#### Move Item to Folder
Move an item (design, asset, or folder) to a different folder.

**Inputs:**
- `item_id` (required): ID of the item to move (design, asset, or folder)
- `destination_folder_id` (required): Destination folder ID (use 'root' for top level)

**Outputs:**
- `result`: Boolean indicating success
- `error`: Error message if failed

**Note:** Video assets cannot be moved.

## Use Cases

### Content Creation Automation
- Automatically create Canva designs from templates
- Upload marketing assets from external sources
- Export designs in multiple formats for distribution

### Asset Management
- Organize uploaded assets into folders
- Tag assets for easy discovery
- Maintain a centralized asset library

### Design Organization
- Organize designs and assets into folder structures
- Move items between folders for workflow management
- Track and search designs by title and modification date

### Design Workflow Integration
- Export designs to various formats (PDF, PNG, PPTX)
- Move designs between folders based on approval status
- Track design creation and modification timestamps

## Error Handling

All actions return a `result` boolean field indicating success or failure. When an action fails, an `error` field contains the error message. This allows workflows to handle errors gracefully.

Example error response:
```json
{
  "result": false,
  "error": "Invalid design_id provided"
}
```

## Pagination

Actions that return lists (list_designs, list_folder_items) support pagination using continuation tokens. When a response includes a `continuation` field, pass it to the next request to retrieve the next page of results.

## Async Operations

Asset uploads and design exports are asynchronous operations. Use the corresponding status-check actions (get_asset_upload_status, get_export_status) to poll for completion.

## Rate Limiting

The Canva Connect API implements rate limiting. This integration handles rate limits automatically through the SDK's error handling and retry mechanisms.

## Version

Current version: 1.0.0

## API Reference

For detailed information about the Canva Connect API, visit:
https://www.canva.dev/docs/connect/

## Support

For issues or questions about this integration, please refer to the Autohive documentation or contact support.
