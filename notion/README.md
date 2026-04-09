# Notion Integration

Enhanced integration with Notion API featuring database querying, block management, page property operations, and advanced search capabilities.

## Features

### Search & Discovery
- **Search Notion** - Search for pages and databases in your workspace
- Filter by type (page/database) with advanced sorting options

### Page Operations
- **Get Page Content** - Retrieve full page content and properties
- **Create Page** - Create new pages in existing pages or databases
- **Update Page Properties** - Modify page properties, icons, covers, and archive status
- **Create Comment** - Add comments to existing pages

### Block Operations
- **Get Block Children** - Retrieve child blocks/content from pages
- **Append Block Children** - Add new content blocks (paragraphs, headings, lists, etc.)
- **Update Block** - Modify existing block content (paragraphs, headings, lists, code, quotes, etc.)
- **Delete Block** - Archive/delete blocks by moving to trash

### Database Operations
- **Query Database** - Advanced database queries with filtering, sorting, and pagination
- **Get Database Schema** - Retrieve database structure, properties, and metadata
- **Get Page Property** - Retrieve specific property values from database pages

## Authentication

Uses Notion platform authentication (OAuth) with automatic token management.

## Supported Block Types

- Paragraphs
- Headings (H1, H2, H3) with toggleable support
- Bulleted and numbered lists
- To-do items with checkbox state
- Code blocks with syntax highlighting
- Quotes
- Callouts
- And more...

## Supported Property Types

- Title and Rich Text
- Select and Multi-select
- Number, Date, Checkbox
- People assignments
- Relations to other databases
- URL, Email, Phone
- Files & Media attachments

## Usage Examples

### Update a paragraph block
```json
{
  "block_id": "your-block-id",
  "paragraph": {
    "rich_text": [
      {
        "type": "text",
        "text": {"content": "Updated content"}
      }
    ]
  }
}
```

### Update page properties
```json
{
  "page_id": "your-page-id",
  "properties": {
    "Status": {
      "select": {"name": "In Progress"}
    }
  }
}
```

### Add page icon
```json
{
  "page_id": "your-page-id", 
  "icon": {
    "type": "emoji",
    "emoji": "🐄"
  }
}
```

## Requirements

- Notion integration with update content capabilities
- Access to pages, databases, and blocks you want to modify

## Version History

- **1.0.0** - Initial release with comprehensive CRUD operations for pages, blocks, and database properties
