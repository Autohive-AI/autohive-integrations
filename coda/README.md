# Coda Integration for Autohive

Document management integration for Coda. Create, list, and retrieve Coda docs programmatically to streamline document-based workflows.

## Description

This integration provides access to Coda's API for managing documents, enabling automation workflows to interact with Coda docs. It returns structured data optimized for integration with other systems.

Key features include:
- List all accessible Coda docs with filtering options
- Retrieve detailed metadata for specific docs
- Create new Coda docs (optionally from templates)
- Filter docs by owner, query, published status, and starred status
- Support for pagination and result limits

This integration uses the Coda API v1 and provides robust error handling with structured response formats.

## Setup & Authentication

This integration uses custom API token authentication.

**How to get your API token:**
1. Go to your Coda account settings
2. Navigate to **API Settings** section
3. Click **"Generate API Token"**
4. Choose scope:
   - **Unrestricted** - Access all your docs
   - **Specific doc/table** - Limit access to specific resources
5. Copy and securely store your API token

**Authentication URL:** https://coda.io/account

The integration automatically handles:
- Bearer token authentication
- API request headers
- Error handling for authentication failures

## Actions

### list_docs

Returns a list of Coda docs accessible by the user. Docs are returned in reverse chronological order by the latest event relevant to the user (last viewed, edited, or shared).

**Input Parameters:**
- `is_owner` (optional): Boolean - Show only docs owned by the user (default: false)
- `query` (optional): String - Search term to filter docs by name
- `source_doc` (optional): String - Show only docs copied from the specified doc ID
- `is_published` (optional): Boolean - Show only published docs
- `is_starred` (optional): Boolean - Show only starred docs
- `limit` (optional): Integer - Maximum number of results to return (1-500, default: 100)

**Output:**
- `docs`: Array of document objects with:
  - `id`: Document ID
  - `type`: Resource type
  - `href`: Full API URL
  - `name`: Document name
  - `owner`: Owner email
  - `workspace`: Workspace details
  - `createdAt`: Creation timestamp
  - `updatedAt`: Last update timestamp
- `result`: Boolean - Whether the operation was successful
- `error`: String - Error message if operation failed

**Example Usage:**

List all your docs:
```
Get all my Coda docs
```

List only owned docs:
```
Show me only the Coda docs I own
```

Search for specific docs:
```
Find Coda docs with "project" in the name
```

List published docs:
```
Show all published Coda docs
```

### get_doc

Returns metadata for the specified Coda doc, including name, owner, creation date, and other details.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc (e.g., "AbCDeFGH")

**Output:**
- `data`: Object with doc metadata including:
  - `id`: Document ID
  - `type`: Resource type
  - `href`: Full API URL
  - `name`: Document name
  - `owner`: Owner email
  - `workspace`: Workspace details
  - `createdAt`: Creation timestamp
  - `updatedAt`: Last update timestamp
  - Additional metadata fields
- `result`: Boolean - Whether the operation was successful
- `error`: String - Error message if operation failed

**Example Usage:**

Get doc by ID:
```
Get Coda doc with ID "abc123xyz"
```

Retrieve doc details:
```
Show me details for Coda doc "AbCDeFGH"
```

### create_doc

Creates a new Coda doc. Optionally copies content from an existing doc. Returns HTTP 202 (Accepted) as doc creation is processed asynchronously.

**Input Parameters:**
- `title` (required): String - Title of the new doc
- `source_doc` (optional): String - Doc ID to copy content from (e.g., "AbCDeFGH")
- `timezone` (optional): String - Timezone for the doc (e.g., "America/Los_Angeles")
- `folder_id` (optional): String - Folder ID where the doc should be created

**Output:**
- `data`: Object with created doc details including:
  - `id`: New document ID
  - `name`: Document name
  - `href`: Full API URL
  - `requestId`: Async processing request ID
- `result`: Boolean - Whether the operation was successful
- `error`: String - Error message if operation failed

**Example Usage:**

Create a blank doc:
```
Create a new Coda doc called "Meeting Notes"
```

Create from template:
```
Create a Coda doc called "Q1 Report" using template doc "template123"
```

Create with timezone:
```
Create a Coda doc called "Project Plan" in America/New_York timezone
```

### update_doc

Updates metadata for a Coda doc (title and icon). Requires Doc Maker permissions for updating the title.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc to update (e.g., "AbCDeFGH")
- `title` (optional): String - New title for the doc
- `icon_name` (optional): String - New icon name (e.g., "rocket", "star", "heart")

**Output:**
- `data`: Object with updated doc details
- `result`: Boolean - Whether the operation was successful
- `error`: String - Error message if operation failed

**Example Usage:**

Update doc title:
```
Update Coda doc "abc123" with new title "Q4 Project Tracker"
```

Update doc icon:
```
Update Coda doc "abc123" with rocket icon
```

Update both:
```
Update Coda doc "abc123" with title "Launch Plan" and rocket icon
```

### delete_doc

Deletes a Coda doc. Returns HTTP 202 (Accepted) as deletion is queued for processing. This action is permanent and cannot be undone.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc to delete (e.g., "AbCDeFGH")

**Output:**
- `data`: Object with deletion confirmation
- `result`: Boolean - Whether the operation was successful
- `error`: String - Error message if operation failed

**Warning:** This action permanently deletes the doc and cannot be reversed.

**Example Usage:**

Delete a doc:
```
Delete Coda doc "abc123"
```

### list_pages

Returns a list of pages in a Coda doc. Use this to discover the doc structure and navigate between pages.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc (e.g., "AbCDeFGH")
- `limit` (optional): Integer - Maximum number of results per page (1-500, default: 100)
- `page_token` (optional): String - Token for fetching next page of results

**Output:**
- `pages`: Array of page objects with metadata (id, name, subtitle, icon, parent, children)
- `next_page_token`: String - Token for next page if more results available
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

List all pages in a doc:
```
List all pages in Coda doc "abc123"
```

List with pagination:
```
List first 10 pages in doc "abc123"
```

### get_page

Returns detailed metadata for a specific page including title, subtitle, icon, image, parent/child relationships, and authors.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc (e.g., "AbCDeFGH")
- `page_id_or_name` (required): String - Page ID or name (e.g., "canvas-abc123")

**Output:**
- `data`: Object with comprehensive page metadata:
  - `id`: Page ID
  - `name`: Page name
  - `subtitle`: Page subtitle
  - `icon`: Icon details
  - `image`: Cover image details
  - `parent`: Parent page reference
  - `children`: Array of child pages
  - `authors`: Array of author details
  - `createdAt`: Creation timestamp
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Get page by ID:
```
Get Coda page "canvas-xyz789" from doc "abc123"
```

Get page details:
```
Show me details for page "Project Overview" in doc "abc123"
```

### create_page

Creates a new page in a Coda doc with optional content, subtitle, icon, and parent page. Returns HTTP 202 (Accepted) as creation is processed asynchronously. Requires Doc Maker permissions.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `name` (required): String - Page name/title
- `subtitle` (optional): String - Page subtitle text
- `icon_name` (optional): String - Icon name (e.g., "rocket", "star", "heart", "bell", "calendar")
- `image_url` (optional): String - URL for cover image
- `parent_page_id` (optional): String - Parent page ID to create as subpage
- `content_format` (optional): String - Format of page content: "html" or "markdown" (default: "html")
- `content` (optional): String - Page content in HTML or Markdown format

**Output:**
- `data`: Object with created page details including id and requestId
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Create a blank page:
```
Create a page called "Meeting Notes" in doc "abc123"
```

Create page with content:
```
Create a page called "Status Update" with HTML content "<h1>Project Status</h1><p>On track</p>" in doc "abc123"
```

Create a subpage:
```
Create a page called "Q1 Goals" as a subpage of "canvas-parent123" in doc "abc123"
```

Create with icon:
```
Create a page called "Launch Plan" with rocket icon in doc "abc123"
```

### update_page

Updates a page's metadata (name, subtitle, icon, image). Cannot update page content after creation. Returns HTTP 202 (Accepted). Requires Doc Maker permissions for updating title/icon.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `page_id_or_name` (required): String - Page ID or name to update
- `name` (optional): String - New page name/title
- `subtitle` (optional): String - New page subtitle
- `icon_name` (optional): String - New icon name (e.g., "rocket", "star", "heart")
- `image_url` (optional): String - New cover image URL

**Output:**
- `data`: Object with updated page details including id and requestId
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Update page title:
```
Update page "canvas-xyz789" in doc "abc123" with new name "Updated Project Plan"
```

Update page icon:
```
Update page "canvas-xyz789" in doc "abc123" with star icon
```

Update multiple fields:
```
Update page "canvas-xyz789" in doc "abc123" with name "Final Report" and subtitle "Q4 2024"
```

### delete_page

Deletes the specified page from a Coda doc. Returns HTTP 202 (Accepted) as deletion is queued for processing. Use page IDs rather than names when possible.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `page_id_or_name` (required): String - Page ID or name to delete

**Output:**
- `data`: Object with deletion confirmation including id and requestId
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Note:** Using names is discouraged as they can be changed by users. If multiple pages have the same name, an arbitrary one will be selected.

**Example Usage:**

Delete page by ID:
```
Delete page "canvas-xyz789" from doc "abc123"
```

Delete page by name:
```
Delete page "Old Notes" from doc "abc123"
```

### list_tables

Returns a list of tables in a Coda doc. By default, returns both base tables and views. Use tableTypes to filter results.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc (e.g., "AbCDeFGH")
- `limit` (optional): Integer - Maximum number of results per page (1-500, default: 100)
- `page_token` (optional): String - Token for fetching next page of results
- `sort_by` (optional): String - Sort order for tables
- `table_types` (optional): String - Comma-separated types: "table,view" (default), "table", or "view"

**Output:**
- `tables`: Array of table objects with metadata (id, name, rowCount, displayColumn, parent, etc.)
- `next_page_token`: String - Token for next page if more results available
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

List all tables and views:
```
List all tables in Coda doc "abc123"
```

List only base tables:
```
List tables in doc "abc123" with table_types "table"
```

List with pagination:
```
List first 20 tables in doc "abc123"
```

### get_table

Returns detailed metadata for a specific table or view, including row count, columns, display column, and sort configuration.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc (e.g., "AbCDeFGH")
- `table_id_or_name` (required): String - Table ID or name (IDs recommended, e.g., "grid-xyz123")

**Output:**
- `data`: Object with comprehensive table metadata:
  - `id`: Table ID
  - `type`: "table" or "view"
  - `name`: Table name
  - `parent`: Parent page reference
  - `parentTable`: Parent table (for views only)
  - `displayColumn`: Display column details
  - `rowCount`: Number of rows
  - `sorts`: Array of sort configurations
  - `layout`: Table layout type
  - `createdAt` / `updatedAt`: Timestamps
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Get table by ID:
```
Get Coda table "grid-xyz789" from doc "abc123"
```

Get table by name:
```
Get table "Projects" from doc "abc123"
```

### list_columns

Returns a list of columns in a table or view. Use this to discover the table structure before inserting or reading rows.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name (IDs recommended)
- `limit` (optional): Integer - Maximum results per page (1-500, default: 100)
- `page_token` (optional): String - Pagination token
- `visible_only` (optional): Boolean - If true, returns only UI-visible columns (default: false)

**Output:**
- `columns`: Array of column objects with:
  - `id`: Column ID (e.g., "c-column123")
  - `name`: Column name
  - `type`: "column"
  - `calculated`: Boolean (true if formula column)
  - `formula`: Formula expression (if calculated)
  - `display`: Boolean (is display column)
  - `valueType`: Data type (text, number, date, person, etc.)
  - `defaultValue`: Default value for new rows
- `next_page_token`: String - Token for next page
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

List all columns:
```
List all columns in table "grid-xyz789" from doc "abc123"
```

List only visible columns:
```
List visible columns in table "Projects" from doc "abc123"
```

### get_column

Returns detailed metadata for a specific column including name, type, formula (if calculated), default value, and format settings.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name (IDs recommended)
- `column_id_or_name` (required): String - Column ID or name (IDs recommended, e.g., "c-column123")

**Output:**
- `data`: Object with column metadata:
  - `id`: Column ID
  - `name`: Column name
  - `type`: "column"
  - `calculated`: Boolean indicating if formula column
  - `formula`: Formula expression (if calculated)
  - `display`: Boolean indicating if display column
  - `valueType`: Data type (text, number, date, person, currency, percent, etc.)
  - `defaultValue`: Default value for new rows
  - `format`: Column format details
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Get column by ID:
```
Get column "c-column123" from table "grid-xyz789" in doc "abc123"
```

Get column by name:
```
Get column "Task Name" from table "Projects" in doc "abc123"
```

### list_rows

Returns a list of rows in a table or view. Supports filtering, sorting, and pagination. Use query parameter to filter rows by column values.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name (IDs recommended)
- `limit` (optional): Integer - Max results per page (1-500, default: 100)
- `page_token` (optional): String - Pagination token
- `query` (optional): String - Filter rows (format: `"ColumnName:\"value\""` or `"c-columnId:123"`)
- `sort_by` (optional): String - Sort by column (e.g., "natural", "created", or column ID)
- `use_column_names` (optional): Boolean - Use column names in response (default: false)
- `value_format` (optional): String - Cell value format: "simple", "simpleWithArrays", or "rich" (default: "simple")
- `visible_only` (optional): Boolean - Return only visible columns (default: false)

**Output:**
- `rows`: Array of row objects with id, values, createdAt, updatedAt, etc.
- `next_page_token`: String - Token for next page
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

List all rows:
```
List all rows in table "grid-xyz789" from doc "abc123"
```

Filter rows:
```
List rows in table "Projects" where Status is "Active" from doc "abc123"
```

List with rich format:
```
List rows in table "grid-xyz789" with value_format "rich" from doc "abc123"
```

### get_row

Returns detailed data for a specific row including all cell values, creation date, and update date.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name
- `row_id_or_name` (required): String - Row ID or name (IDs recommended, e.g., "i-rowId123")
- `use_column_names` (optional): Boolean - Use column names in response (default: false)
- `value_format` (optional): String - "simple", "simpleWithArrays", or "rich"

**Output:**
- `data`: Object with row data including id, values, createdAt, updatedAt
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Get row by ID:
```
Get row "i-row123" from table "grid-xyz789" in doc "abc123"
```

Get row with rich format:
```
Get row "i-row123" from table "Projects" with value_format "rich" in doc "abc123"
```

### upsert_rows

Inserts rows into a table, or updates existing rows if keyColumns are provided. Only works on base tables, not views. Returns HTTP 202 (Accepted) as processing is asynchronous.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID (must be base table, not view)
- `rows` (required): Array - Array of row objects with cells
  - Each row: `{"cells": [{"column": "c-col123", "value": "data"}]}`
- `key_columns` (optional): Array - Column IDs/names for upsert matching
- `disable_parsing` (optional): Boolean - Disable automatic value parsing (default: false)

**Output:**
- `data`: Object with addedRowIds array and requestId
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Behavior:**
- **Without keyColumns**: Always inserts new rows
- **With keyColumns**: Creates if key doesn't exist, updates if key exists
- **Multiple matches**: All matching rows are updated

**Example Usage:**

Insert new rows:
```
Insert rows into table "grid-xyz789" in doc "abc123" with data
```

Upsert with key column:
```
Upsert rows into table "Projects" with key_columns ["Email"] in doc "abc123"
```

### update_row

Updates a specific row in a table. Only updates the cells provided, leaving others unchanged. Returns HTTP 202 (Accepted).

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name
- `row_id_or_name` (required): String - Row ID or name (IDs recommended)
- `cells` (required): Array - Cell objects to update: `[{"column": "c-col123", "value": "new value"}]`
- `disable_parsing` (optional): Boolean - Disable automatic value parsing (default: false)

**Output:**
- `data`: Object with requestId and id
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Update row cells:
```
Update row "i-row123" in table "grid-xyz789" setting Status to "Complete" in doc "abc123"
```

### delete_row

Deletes a specific row from a table. Returns HTTP 202 (Accepted) as deletion is queued for processing.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name
- `row_id_or_name` (required): String - Row ID or name to delete (IDs recommended)

**Output:**
- `data`: Object with requestId and id
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Delete row by ID:
```
Delete row "i-row123" from table "grid-xyz789" in doc "abc123"
```

### delete_rows

Deletes multiple rows from a table by their IDs. Returns HTTP 202 (Accepted) as deletion is queued for processing.

**Input Parameters:**
- `doc_id` (required): String - ID of the doc
- `table_id_or_name` (required): String - Table ID or name
- `row_ids` (required): Array - Array of row IDs to delete (e.g., ["i-row1", "i-row2"])

**Output:**
- `data`: Object with requestId and rowIds
- `result`: Boolean - Whether operation was successful
- `error`: String - Error message if failed

**Example Usage:**

Delete multiple rows:
```
Delete rows ["i-row1", "i-row2", "i-row3"] from table "grid-xyz789" in doc "abc123"
```

## Rate Limits

- **Reading data (GET)**: 100 requests per 6 seconds
- **Writing data (POST/PUT/PATCH)**: 10 requests per 6 seconds
- **Writing doc/page content (POST/PUT/PATCH)**: 5 requests per 10 seconds
- **Listing docs**: 4 requests per 6 seconds

**Note:** Write operations (like create_doc, create_page, update_page, delete_page) return HTTP 202, indicating the edit has been accepted and queued for asynchronous processing. Changes are typically processed within a few seconds.

## Error Handling

The integration provides structured error responses for:
- Invalid or expired API tokens (401 errors)
- Access forbidden - no permission to resource (403 errors)
- Resource not found (404 errors)
- Rate limit exceeded (429 errors)
- General API failures

All actions return a consistent structure:
```json
{
  "data": {} or "docs": [],
  "result": true/false,
  "error": "Error message if failed"
}
```

## Use Cases

- Automated doc creation from templates
- Document inventory and management
- Doc metadata retrieval for reporting
- Workflow automation with Coda docs
- Cross-platform doc synchronization
- Team doc organization and filtering
- Automated doc provisioning for projects
- Document lifecycle management
- **Page management and organization**
- **Automated page creation with content**
- **Doc structure discovery and navigation**
- **Dynamic content generation in pages**
- **Page metadata management (icons, subtitles)**
- **Subpage creation for hierarchical docs**

## Technical Details

- **API Endpoint**: `https://coda.io/apis/v1`
- **Authentication**: Bearer token (Custom API token)
- **Response Format**: JSON
- **Async Processing**: Create operations return 202 and process asynchronously
- **API Version**: v1 (Standard Coda API)

## Permissions

**For list_docs, get_doc, list_pages, and get_page:**
- Requires read access to docs (granted by API token scope)

**For create_doc:**
- Token owner must be **Doc Maker** (or Admin) in the workspace
- OR workspace must have "Any member can create docs" enabled (Editor auto-promoted to Doc Maker)

**For create_page, update_page, and delete_page:**
- Token owner must be **Doc Maker** (or Admin) in the workspace
- Updating page title or icon specifically requires Doc Maker permissions

## Additional Resources

- [Coda API Official Documentation](https://coda.io/developers)
- [Coda API Getting Started Guide](https://coda.io/@oleg/getting-started-guide-coda-api)
- [Coda Account Settings (API Token)](https://coda.io/account)
