# Google Docs Integration for Autohive

Connects Autohive to the Google Docs API, enabling document creation, text insertion, content formatting, and document analysis.

## Description

This integration provides comprehensive access to Google Docs functionality through the Google Docs API v1. It allows you to:

- Create new Google Docs documents
- Retrieve full document content and structure
- Insert plain text paragraphs
- Insert markdown-formatted content with automatic styling (headings, bold, italic)
- Apply text formatting (bold, italic, font size, colors)
- Parse document structure to identify headings and paragraphs
- Execute complex batch update operations

**Note:** Google Docs API does not support programmatic tab creation or management via API.

## Setup & Authentication

This integration uses OAuth2 authentication via the Autohive platform. The required Google API scopes are automatically configured.

**Required Scopes:**

*   `https://www.googleapis.com/auth/documents` - Full access to Google Docs

**Setup Steps:**

1. Configure the Google Docs integration in your Autohive platform
2. Authenticate with your Google account
3. Grant the requested permissions

## Actions

### Action: `docs_create`

*   **Description:** Create a new Google Doc with an optional title.
*   **Inputs:**
    *   `title` (optional): Title of the document. Defaults to "Untitled Document" if not provided.
*   **Outputs:**
    *   `documentId`: The ID of the newly created document
    *   `title`: The title of the document
    *   `result`: Boolean indicating success
    *   `error`: Error message if operation failed

### Action: `docs_get`

*   **Description:** Retrieve the full content of a Google Doc.
*   **Inputs:**
    *   `document_id` (required): The ID of the document to retrieve
    *   `include_tabs_content` (optional): Whether to include tab content. Defaults to true.
*   **Outputs:**
    *   `document`: Complete document object with all content and metadata
    *   `result`: Boolean indicating success
    *   `error`: Error message if operation failed

### Action: `docs_insert_paragraphs`

*   **Description:** Insert multiple plain text paragraphs into the document. Each paragraph is separated by double newlines.
*   **Inputs:**
    *   `document_id` (required): The ID of the document
    *   `paragraphs` (required): Array of paragraph text strings
    *   `append` (optional): If true, append to end; if false, insert at beginning. Defaults to true.
    *   `tab_id` (optional): Optional tab ID if working with a specific tab
*   **Outputs:**
    *   `result`: Boolean indicating success
    *   `paragraphs_inserted`: Number of paragraphs inserted
    *   `inserted_at_index`: The index where content was inserted
    *   `error`: Error message if operation failed

### Action: `docs_insert_markdown_content`

*   **Description:** Insert markdown-formatted content with automatic styling. Detects ALL heading levels (# through ######) and inline formatting (**bold**, *italic*) in a single operation. Automatically applies Google Docs styles (HEADING_1-6, bold, italic) without showing markdown symbols. For plain paragraphs without any formatting, use `docs_insert_paragraphs` instead.
*   **Inputs:**
    *   `document_id` (required): The ID of the document
    *   `content` (required): Markdown text with headings and inline formatting (e.g., "# Overview\n**Bold text** and *italic text*\n\n## Details\nMore text")
    *   `tab_id` (optional): Optional tab ID if working with a specific tab
    *   `append` (optional): If true, append to end of document (default: true)
*   **Outputs:**
    *   `result`: Boolean indicating success
    *   `headings_inserted`: Number of headings inserted
    *   `paragraphs_inserted`: Number of paragraphs inserted
    *   `total_elements`: Total elements inserted
    *   `error`: Error message if operation failed
*   **Supported Markdown Features:**
    *   Headings: `#` through `######` (H1 through H6)
    *   Bold: `**text**`
    *   Italic: `*text*`

### Action: `docs_batch_update`

*   **Description:** Execute multiple document update operations in a single batch request. Use this for text formatting (bold, italic, colors), paragraph styling, and any custom Google Docs API operations.
*   **Inputs:**
    *   `document_id` (required): The ID of the document
    *   `requests` (required): Array of request objects following the Google Docs API format
*   **Outputs:**
    *   `replies`: Array of response objects from each request
    *   `result`: Boolean indicating success
    *   `error`: Error message if operation failed
*   **Common Examples:**
    *   Apply bold: `{"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 10}, "textStyle": {"bold": true}, "fields": "bold"}}`
    *   Apply italic: `{"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 10}, "textStyle": {"italic": true}, "fields": "italic"}}`
    *   Change font size: `{"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 10}, "textStyle": {"fontSize": {"magnitude": 14, "unit": "PT"}}, "fields": "fontSize"}}`

### Action: `docs_parse_structure`

*   **Description:** Parse document structure to identify headings, paragraphs, tables, and their positions with style information.
*   **Inputs:**
    *   `document_id` (required): The ID of the document
    *   `tab_id` (optional): Optional tab ID to parse a specific tab
*   **Outputs:**
    *   `structure`: Array of elements with type, style, text, startIndex, endIndex, and alignment
    *   `result`: Boolean indicating success
    *   `error`: Error message if operation failed

## Requirements

*   `autohive-integrations-sdk`
*   `google-api-python-client>=2.0.0`
*   `google-auth>=2.0.0`
*   `google-auth-oauthlib>=0.5.0`
*   `google-auth-httplib2>=0.1.0`

## Usage Examples

**Example 1: Creating a document and inserting plain paragraphs**

```json
// Step 1: Create a new document
{
  "action": "docs_create",
  "inputs": {
    "title": "Project Proposal"
  }
}
// Response: { "documentId": "abc123...", "title": "Project Proposal", "result": true }

// Step 2: Insert multiple paragraphs
{
  "action": "docs_insert_paragraphs",
  "inputs": {
    "document_id": "abc123...",
    "paragraphs": [
      "This is the introduction paragraph.",
      "This is the second paragraph with more details.",
      "This is the conclusion paragraph."
    ],
    "append": true
  }
}
// Response: { "result": true, "paragraphs_inserted": 3, "inserted_at_index": 1 }
```

**Example 2: Inserting structured content with markdown**

```json
// Insert content with automatic styling (all heading levels and inline formatting)
{
  "action": "docs_insert_markdown_content",
  "inputs": {
    "document_id": "abc123...",
    "content": "# Lead Analysis Report\n\n**Prepared for:** Autohive **Date:** October 23, 2025\n\n## 1. Executive Summary\n\nThis is a paragraph with **bold** and *italic* text.\n\n### Key Findings\n\n- Point one with **emphasis**\n- Point two with *italic style*\n\n## 2. Detailed Analysis\n\nFinal paragraph with mixed formatting.",
    "append": true
  }
}
// Response: { "result": true, "headings_inserted": 4, "paragraphs_inserted": 3, "total_elements": 7 }
```

**Example 3: Applying text formatting with batch update**

```json
// Apply bold and italic formatting to text
{
  "action": "docs_batch_update",
  "inputs": {
    "document_id": "abc123...",
    "requests": [
      {
        "updateTextStyle": {
          "range": { "startIndex": 1, "endIndex": 10 },
          "textStyle": {
            "bold": true,
            "italic": true,
            "fontSize": { "magnitude": 14, "unit": "PT" }
          },
          "fields": "bold,italic,fontSize"
        }
      },
      {
        "updateTextStyle": {
          "range": { "startIndex": 20, "endIndex": 30 },
          "textStyle": {
            "foregroundColor": {
              "color": { "rgbColor": { "red": 1.0, "green": 0.0, "blue": 0.0 } }
            }
          },
          "fields": "foregroundColor"
        }
      }
    ]
  }
}
```

**Example 4: Parsing document structure**

```json
// Parse the document to find all headings and paragraphs
{
  "action": "docs_parse_structure",
  "inputs": {
    "document_id": "abc123..."
  }
}
// Response: {
//   "result": true,
//   "structure": [
//     {
//       "type": "heading",
//       "style": "HEADING_1",
//       "text": "Overview",
//       "startIndex": 1,
//       "endIndex": 10
//     },
//     {
//       "type": "paragraph",
//       "style": "NORMAL_TEXT",
//       "text": "This is a paragraph.",
//       "startIndex": 10,
//       "endIndex": 32
//     }
//   ]
// }
```

## Testing

To run the tests:

1.  Navigate to the integration's directory: `cd google-docs`
2.  Install dependencies: `pip install -r requirements.txt -t dependencies`
3.  Run the tests: `python tests/test_google-docs.py`

Note: Tests require valid Google OAuth2 credentials. For local testing, you may need to set up a test access token.
