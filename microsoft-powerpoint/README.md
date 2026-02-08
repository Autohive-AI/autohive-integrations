# Microsoft PowerPoint Integration

Autohive integration for reading, creating, and manipulating PowerPoint presentations in OneDrive/SharePoint via Microsoft Graph API.

## Features

- **List Presentations**: Find accessible .pptx files with filtering
- **Get Presentation Metadata**: Retrieve file properties, author, timestamps
- **Get Slides**: List all slides with thumbnails
- **Create Presentation**: Create new presentations or copy from templates
- **Add/Update/Delete Slides**: Modify slide content programmatically
- **Export to PDF**: Convert presentations to PDF format
- **Get Slide Images**: Retrieve slide thumbnails in various sizes

## Authentication

This integration uses Microsoft 365 OAuth 2.0 platform authentication with the following scopes:

- `Files.Read` - Read access to presentations
- `Files.ReadWrite` - Read and write access to presentations
- `User.Read` - Read user profile
- `offline_access` - Refresh token support

## Requirements

- Microsoft 365 Business account (OneDrive for Business or SharePoint)
- **Note**: OneDrive Consumer (personal) accounts are NOT supported
- Presentations must be in `.pptx` format (`.ppt` is NOT supported)

## Dependencies

```bash
pip install -r requirements.txt
```

- `autohive-integrations-sdk>=1.0.0`
- `python-pptx>=0.6.21` - Required for slide manipulation actions

## Actions

### powerpoint_list_presentations
Find accessible PowerPoint presentations in OneDrive/SharePoint.

**Inputs:**
- `name_contains` (optional): Filter by name
- `folder_path` (optional): Folder to search in
- `page_size` (optional): Max results (default: 25, max: 100)
- `page_token` (optional): Pagination token

### powerpoint_get_presentation
Get presentation metadata including file info and timestamps.

**Inputs:**
- `presentation_id` (required): Drive item ID

### powerpoint_get_slides
List all slides with thumbnails.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `include_thumbnails` (optional): Include thumbnail URLs (default: true)
- `thumbnail_size` (optional): small, medium, large (default: medium)

### powerpoint_get_slide
Get details for a specific slide.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `slide_index` (required): 1-based slide index
- `include_thumbnail` (optional): Include thumbnail URL (default: true)
- `thumbnail_size` (optional): small, medium, large (default: large)

### powerpoint_create_presentation
Create a new presentation.

**Inputs:**
- `name` (required): Presentation name (without .pptx extension)
- `folder_path` (optional): Destination folder
- `template_id` (optional): Template presentation ID to copy

### powerpoint_add_slide
Add a new slide to a presentation.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `position` (optional): 1-based position (default: end)
- `layout` (optional): blank, title, titleContent, etc. (default: blank)
- `title` (optional): Slide title text
- `content` (optional): Slide body content

### powerpoint_update_slide
Update existing slide content.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `slide_index` (required): 1-based slide index
- `title` (optional): New title text
- `content` (optional): New body content
- `notes` (optional): Speaker notes

### powerpoint_delete_slide
Delete a slide from the presentation.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `slide_index` (required): 1-based slide index to delete

### powerpoint_export_pdf
Export presentation to PDF.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `output_folder` (optional): Destination folder
- `output_name` (optional): PDF file name

### powerpoint_get_slide_image
Get a slide as an image thumbnail.

**Inputs:**
- `presentation_id` (required): Drive item ID
- `slide_index` (required): 1-based slide index
- `size` (optional): small, medium, large (default: large)
- `format` (optional): png, jpeg (default: png)

## API Limitations

- Microsoft Graph does not provide a dedicated PowerPoint API like Excel
- Slide content manipulation requires downloading, modifying with python-pptx, and re-uploading
- Maximum file size: 250 MB
- Thumbnails are rate-limited separately from file operations

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v
```

## References

- [Microsoft Graph DriveItem API](https://learn.microsoft.com/en-us/graph/api/resources/driveitem)
- [DriveItem Thumbnails](https://learn.microsoft.com/en-us/graph/api/driveitem-list-thumbnails)
- [python-pptx Documentation](https://python-pptx.readthedocs.io/)
