# Microsoft Word Integration

<img src="icon.png" alt="Microsoft Word" width="64" height="64" />

Read, create, and manipulate Word documents (.docx) stored in OneDrive for Business, SharePoint, or Group drives via Microsoft Graph API.

## Authentication

This integration uses OAuth 2.0 with Microsoft 365. Required scopes:
- `Files.Read` - Read access to documents
- `Files.ReadWrite` - Read and write access to documents
- `offline_access` - Refresh token support

## Supported Features

| Action | Description |
|--------|-------------|
| `word_list_documents` | Find Word documents in OneDrive/SharePoint with optional filtering |
| `word_get_document` | Get document metadata and properties |
| `word_get_content` | Read document text content (text, HTML, or markdown) |
| `word_create_document` | Create new documents with optional content or from template |
| `word_update_content` | Replace document content |
| `word_insert_text` | Insert text at specific locations |
| `word_get_paragraphs` | Get paragraphs with content and formatting |
| `word_search_replace` | Find and replace text in documents |
| `word_export_pdf` | Export documents to PDF format |
| `word_get_tables` | Extract tables as structured data |

## Requirements

- Microsoft 365 account (OneDrive for Business, SharePoint, or Group drives)
- Only `.docx` format is supported (not `.doc`)
- OneDrive Consumer is NOT supported

## Usage Examples

### List Word Documents
```python
# List all Word documents in root
result = await word_list_documents({})

# Filter by name in specific folder
result = await word_list_documents({
    "name_contains": "Report",
    "folder_path": "Documents/Reports",
    "page_size": 50
})
```

### Get Document Content
```python
# Get plain text content
result = await word_get_content({
    "document_id": "abc123",
    "format": "text"
})

# Get HTML with metadata
result = await word_get_content({
    "document_id": "abc123",
    "format": "html",
    "include_metadata": True
})
```

### Create Document
```python
# Create with initial content
result = await word_create_document({
    "name": "New Report",
    "content": "This is the initial content.",
    "folder_path": "Documents"
})

# Create from template
result = await word_create_document({
    "name": "Contract",
    "template_id": "template-doc-id"
})
```

### Search and Replace
```python
result = await word_search_replace({
    "document_id": "abc123",
    "search_text": "{{customer_name}}",
    "replace_text": "Acme Corp",
    "match_case": False,
    "replace_all": True
})
```

### Export to PDF
```python
# Get download URL
result = await word_export_pdf({
    "document_id": "abc123"
})

# Save PDF to OneDrive
result = await word_export_pdf({
    "document_id": "abc123",
    "save_to_drive": True,
    "output_name": "Report_Final.pdf",
    "folder_path": "Exports"
})
```

## API Limits

- **File Size**: Maximum 250 MB for document operations
- **Request Rate**: Standard Microsoft Graph limits (~10,000 requests per 10 minutes)

## Error Handling

Common HTTP error codes:
- `400` - Invalid request format or parameters
- `401` - Invalid or expired access token
- `403` - Insufficient permissions
- `404` - Document or folder not found
- `429` - Rate limit exceeded

## References

- [Microsoft Graph DriveItem API](https://learn.microsoft.com/en-us/graph/api/resources/driveitem)
- [Download File Content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content)
- [Upload File Content](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content)
- [Convert File Format](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format)
