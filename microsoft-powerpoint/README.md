# Microsoft PowerPoint Integration for Autohive

Connects Autohive to the Microsoft Graph API to allow users to read, create, and manipulate PowerPoint presentations stored in OneDrive for Business or SharePoint.

## Description

This integration provides comprehensive access to Microsoft PowerPoint functionality through the Microsoft Graph API. It enables users to:

- **Manage Presentations**: List, create, and retrieve presentation metadata from OneDrive/SharePoint
- **Slide Operations**: Add, update, and delete slides with support for titles, content, and speaker notes
- **Export Capabilities**: Convert presentations to PDF format
- **Thumbnail Access**: Retrieve presentation thumbnails for preview purposes

The integration uses the `python-pptx` library for slide manipulation operations, which requires downloading the presentation, modifying it locally, and re-uploading. This approach is necessary because Microsoft Graph does not provide a dedicated PowerPoint API for direct slide editing.

## Setup & Authentication

This integration uses **OAuth 2.0 Platform Authentication** through Microsoft's identity platform. Users authenticate via Microsoft's OAuth flow to grant the integration access to their OneDrive/SharePoint files.

**Required Scopes:**

- `Files.Read` - Read access to presentations
- `Files.ReadWrite` - Read and write access to presentations
- `User.Read` - Read user profile information
- `offline_access` - Maintain access via refresh tokens

**Setup Steps:**

1. In Autohive, add the Microsoft PowerPoint integration to your workspace
2. Click "Connect" to initiate the OAuth flow
3. Sign in with your Microsoft 365 Business account
4. Grant the requested permissions
5. You'll be redirected back to Autohive with the integration connected

**Requirements:**

- Microsoft 365 Business account (OneDrive for Business or SharePoint)
- **Note**: OneDrive Consumer (personal) accounts are NOT supported
- Presentations must be in `.pptx` format (`.ppt` is NOT supported)

## Actions

### Presentation Management

#### `powerpoint_list_presentations`

- **Description:** Find accessible PowerPoint presentations (.pptx) in OneDrive/SharePoint with optional filtering
- **Inputs:**
  - `name_contains` (optional): Filter presentations whose name contains this string
  - `folder_path` (optional): Folder path to search in (default: root)
  - `page_size` (optional): Maximum results to return (default: 25, max: 100)
  - `page_token` (optional): Token for pagination
- **Outputs:**
  - `presentations`: Array of presentation objects with id, name, webUrl, lastModifiedDateTime, size
  - `next_page_token`: Token for next page if more results exist
  - `result`: Boolean indicating success

#### `powerpoint_get_presentation`

- **Description:** Retrieve presentation properties including file info, author, and timestamps
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
- **Outputs:**
  - `id`: Drive item ID
  - `name`: File name
  - `size`: File size in bytes
  - `webUrl`: URL to open in browser
  - `createdDateTime`: Creation timestamp
  - `lastModifiedDateTime`: Last modified timestamp
  - `createdBy`: User who created the file
  - `lastModifiedBy`: User who last modified the file
  - `result`: Boolean indicating success

#### `powerpoint_create_presentation`

- **Description:** Create a new PowerPoint presentation in the specified folder
- **Inputs:**
  - `name` (required): Name for the new presentation (without .pptx extension)
  - `folder_path` (optional): Folder path to create in (default: root)
  - `template_id` (optional): Drive item ID of template presentation to copy
- **Outputs:**
  - `id`: Drive item ID of created presentation
  - `name`: Full file name (with .pptx extension)
  - `webUrl`: URL to open in browser
  - `result`: Boolean indicating success
  - `message`: Status message (especially for async template copy operations)

### Slide Operations

#### `powerpoint_get_slides`

- **Description:** List all slides in a presentation with optional thumbnail URLs
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `include_thumbnails` (optional): Include thumbnail URLs (default: true)
  - `thumbnail_size` (optional): Thumbnail size - small, medium, large (default: medium)
- **Outputs:**
  - `slides`: Array of slide objects with index, layout, title, and content information
  - `slide_count`: Total number of slides
  - `presentation_thumbnail`: Presentation-level thumbnail (see Important Notes)
  - `result`: Boolean indicating success

#### `powerpoint_get_slide`

- **Description:** Get details for a specific slide by its index (1-based)
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `slide_index` (required): Slide index (1-based)
  - `include_thumbnail` (optional): Include thumbnail URL (default: true)
  - `thumbnail_size` (optional): Thumbnail size - small, medium, large (default: large)
- **Outputs:**
  - `index`: Slide index (1-based)
  - `id`: Slide identifier
  - `thumbnailUrl`: URL to presentation thumbnail (see Important Notes)
  - `result`: Boolean indicating success

#### `powerpoint_add_slide`

- **Description:** Add a new slide to an existing presentation
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `position` (optional): Position to insert slide (1-based, null = end)
  - `layout` (optional): Slide layout - blank, title, titleContent, twoContent, comparison, titleOnly, contentCaption, pictureCaption (default: blank)
  - `title` (optional): Title text for the slide
  - `content` (optional): Body content text for the slide
- **Outputs:**
  - `slide_index`: Index of the new slide (1-based)
  - `slide_count`: Total slides after addition
  - `result`: Boolean indicating success

#### `powerpoint_update_slide`

- **Description:** Update the content of an existing slide
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `slide_index` (required): Slide index to update (1-based)
  - `title` (optional): New title text
  - `content` (optional): New body content text
  - `notes` (optional): Speaker notes for the slide
- **Outputs:**
  - `updated`: Boolean indicating whether slide was updated
  - `slide_index`: Index of updated slide
  - `result`: Boolean indicating success

#### `powerpoint_delete_slide`

- **Description:** Delete a slide from the presentation
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `slide_index` (required): Slide index to delete (1-based)
- **Outputs:**
  - `deleted`: Boolean indicating whether slide was deleted
  - `slide_count`: Remaining slide count
  - `result`: Boolean indicating success

### Export & Images

#### `powerpoint_export_pdf`

- **Description:** Export the presentation to PDF format
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `output_folder` (optional): Folder path for output file (default: same as source)
  - `output_name` (optional): Name for PDF file (default: same as presentation name)
- **Outputs:**
  - `pdf_id`: Drive item ID of created PDF
  - `pdf_name`: PDF file name
  - `pdf_webUrl`: URL to PDF file
  - `pdf_size`: PDF file size in bytes
  - `download_url`: Direct download URL (temporary)
  - `result`: Boolean indicating success

#### `powerpoint_get_slide_image`

- **Description:** Get a slide as an image thumbnail
- **Inputs:**
  - `presentation_id` (required): The drive item ID of the presentation
  - `slide_index` (required): Slide index to export (1-based)
  - `size` (optional): Image size - small (176x144), medium (800x600), large (1600x1200) (default: large)
  - `format` (optional): Image format - png, jpeg (default: png)
- **Outputs:**
  - `image_url`: URL to slide image (temporary)
  - `width`: Image width in pixels
  - `height`: Image height in pixels
  - `format`: Image format
  - `result`: Boolean indicating success

## Important Notes

### Thumbnail Limitation

Microsoft Graph API only provides **presentation-level thumbnails**, not individual slide thumbnails. The thumbnail returned by `powerpoint_get_slides`, `powerpoint_get_slide`, and `powerpoint_get_slide_image` actions represents the entire presentation (typically the first slide or a generated preview), not the specific slide requested.

### File Size Limitations

- **Upload Limit**: Slide modification operations (add, update, delete) use simple upload which has a **4MB limit**. Presentations with many images may exceed this limit after modification.
- **Download**: Large presentations (500MB+) may cause memory issues during slide operations.
- **Maximum File Size**: Microsoft Graph supports files up to 250MB for simple operations.

### Template Copy Operations

When creating a presentation from a template using `template_id`, the Microsoft Graph `/copy` endpoint operates **asynchronously**. The action may return a success message before the copy operation completes. Allow a few seconds before performing operations on the newly created presentation.

### Slide Modification Pattern

Slide operations (add, update, delete) follow a download-modify-upload pattern:

1. Download the entire presentation file
2. Modify using python-pptx library
3. Re-upload the modified file

This means:
- Concurrent modifications may overwrite each other
- Operations are slower than direct API calls
- Memory usage scales with presentation size

### Supported Layouts

The `layout` parameter for `powerpoint_add_slide` maps to standard PowerPoint layouts. Available options depend on the presentation's slide master. Common layouts include:

- `blank` - Empty slide
- `title` - Title slide
- `titleContent` - Title and content
- `twoContent` - Two content areas
- `comparison` - Side-by-side comparison
- `titleOnly` - Title only
- `contentCaption` - Content with caption
- `pictureCaption` - Picture with caption

## Requirements

- `autohive_integrations_sdk>=1.0.0`
- `python-pptx>=0.6.21` - Required for slide manipulation actions

## Usage Examples

**Example 1: List and get presentation details**

```python
# Step 1: Find presentations containing "Q4" in the name
presentations = await powerpoint_list_presentations({
    "name_contains": "Q4",
    "page_size": 10
})

# Step 2: Get details for the first result
if presentations['presentations']:
    details = await powerpoint_get_presentation({
        "presentation_id": presentations['presentations'][0]['id']
    })
```

**Example 2: Create a presentation and add slides**

```python
# Step 1: Create a new presentation
result = await powerpoint_create_presentation({
    "name": "Sales Report",
    "folder_path": "Reports/2025"
})
presentation_id = result['id']

# Step 2: Add a title slide
await powerpoint_add_slide({
    "presentation_id": presentation_id,
    "layout": "title",
    "title": "Q4 Sales Report",
    "content": "Prepared by Sales Team"
})

# Step 3: Add content slides
await powerpoint_add_slide({
    "presentation_id": presentation_id,
    "layout": "titleContent",
    "title": "Revenue Overview",
    "content": "Total revenue increased by 15% compared to Q3"
})
```

**Example 3: Update slide content**

```python
# Update the title and add speaker notes to slide 2
await powerpoint_update_slide({
    "presentation_id": "abc123",
    "slide_index": 2,
    "title": "Updated Revenue Overview",
    "notes": "Remember to mention the new client acquisitions"
})
```

**Example 4: Export presentation to PDF**

```python
# Export to PDF in the same folder
pdf_result = await powerpoint_export_pdf({
    "presentation_id": "abc123",
    "output_name": "Sales_Report_Final"
})
print(f"PDF available at: {pdf_result['download_url']}")
```

## API Limitations

- Microsoft Graph does not provide a dedicated PowerPoint API like it does for Excel
- No direct slide editing API - must download, modify with python-pptx, and re-upload
- Thumbnails are presentation-level only, not per-slide
- Rate limits apply separately for file operations and thumbnail requests
- `.ppt` format is not supported - only `.pptx`
- OneDrive Consumer (personal) accounts are not supported

## Testing

To test the integration:

1. Ensure you have a Microsoft 365 Business account with OneDrive access
2. Configure the integration in your Autohive workspace
3. Test basic operations:
   - List presentations in your OneDrive
   - Create a test presentation
   - Add, update, and delete slides
   - Export to PDF
   - Verify slide count after modifications
4. Clean up test presentations after testing

To run unit tests:

```bash
cd microsoft-powerpoint
pip install -r requirements.txt
python -m pytest tests/ -v
```

## References

- [Microsoft Graph DriveItem API](https://learn.microsoft.com/en-us/graph/api/resources/driveitem)
- [DriveItem Thumbnails](https://learn.microsoft.com/en-us/graph/api/driveitem-list-thumbnails)
- [DriveItem Copy](https://learn.microsoft.com/en-us/graph/api/driveitem-copy)
- [python-pptx Documentation](https://python-pptx.readthedocs.io/)
