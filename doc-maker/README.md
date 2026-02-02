# Doc Maker Integration

Create professional Word documents automatically using markdown syntax. Perfect for generating reports, filling templates, and automating document workflows.

## What You Can Do

- **Create Documents with Markdown**: Use familiar markdown syntax (headings, lists, tables, formatting) to generate Word documents
- **Fill Templates Safely**: Intelligently detect and replace placeholders with built-in safety checks
- **Add Rich Content**: Insert images, tables, formatted text, and page breaks
- **Smart Find & Replace**: Context-aware text replacement that prevents unintended changes

## Quick Setup

1. **Install the Integration**: Add Doc Maker to your Autohive workspace
2. **Start Creating**: Use markdown in your workflows immediately
3. **No Authentication Required**: Works out of the box - no account setup needed

## Available Actions

### Create Document

Generate a Word document from markdown content.

**Common Parameters:**
- `markdown_content`: Your markdown text (headings, lists, tables, formatting)
- `custom_filename`: Optional filename for the output (auto-adds .docx)

**Example Use Cases:**
- Generate weekly reports from data
- Create meeting notes automatically
- Build customer proposals from templates

### Fill Template

Intelligently fill Word templates with your data using multiple safe approaches.

**Common Parameters:**
- `document_id`: The template to fill
- `template_data`: Your data in various formats (placeholders, positions, or searches)

**Example Use Cases:**
- Auto-fill invoices with customer data
- Generate personalized contracts
- Populate monthly report templates

### Find and Replace

Search and replace text throughout documents with safety checks.

**Common Parameters:**
- `replacements`: List of find/replace pairs with context
- `case_sensitive`: Match exact case (default: no)

**Safety Feature:** The system warns you if your search term might match unintended text!

### Add Content

Add more markdown content, images, tables, or page breaks to existing documents.

**Example Use Cases:**
- Append new sections to reports
- Insert charts and graphs
- Add signature pages

## Example Workflows

### Weekly Report Generation
```
1. Create document with markdown header and metrics
2. Add table with weekly data
3. Insert performance charts as images
4. Add page break and executive summary
5. Send to stakeholders
```

### Invoice Automation
```
1. Load invoice template
2. Analyze template to find fillable fields
3. Fill client info, line items, and totals
4. Save with custom filename (INV-001.docx)
5. Email to client
```

### Contract Generation
```
1. Upload contract template
2. Fill client name, dates, and terms
3. Find and replace legal placeholders
4. Add signature page
5. Store in document management system
```

### Template Batch Processing
```
1. Load employee review template
2. For each employee:
   - Fill name, department, metrics
   - Add performance chart
   - Save as [EmployeeName]_Review_2024.docx
3. Send batch completion notification
```

## Markdown Syntax Quick Reference

### Headings
```markdown
# Heading 1
## Heading 2
### Heading 3
```

### Text Formatting
```markdown
**Bold text**
*Italic text*
`Code text`
~~Strikethrough~~
__Underline__
```

### Lists
```markdown
- Bullet point
- Another bullet

1. Numbered item
2. Another number
```

### Tables
```markdown
| Header 1 | Header 2 |
|----------|----------|
| Data 1   | Data 2   |
```

## Best Practices

### Template Design
- Use clear placeholders like `{{FIELD_NAME}}` instead of generic words
- Include context: `"Date: ___"` is safer than just `"date"`
- Make placeholders unique to avoid accidental replacements
- Test templates before bulk processing

### Safe Text Replacement
- **Always include context** in your find phrases:
  - ✅ Good: `"Project Name: placeholder"`
  - ❌ Bad: `"name"` (too generic)
- Let the system analyze templates first for complex documents
- Review safety warnings - they provide specific guidance
- Use position-based updates for maximum precision

### Content Creation
- Use markdown for 90% of document creation (it's faster)
- Add images and page breaks with dedicated actions
- Break complex documents into sections
- Test formatting with sample data first

### Performance
- Batch similar operations when possible
- Use appropriate limits for large templates
- Process documents in memory (no temp files needed)

## Template Filling Strategies

### Strategy 1: Exact Placeholders (Easiest)
Use formal placeholders that won't appear in normal text:
```
{{COMPANY_NAME}} → "Acme Corp"
{{INVOICE_DATE}} → "January 15, 2025"
```

### Strategy 2: Context-Aware (Balanced)
Include surrounding text for safety:
```
"Project Name: data here" → "Project Name: Q4 Integration"
"Client: client name" → "Client: John Smith"
```

### Strategy 3: Position-Based (Most Precise)
Update specific locations by index:
```
Paragraph 5 → "New content"
Table 0, Row 2, Column 1 → "Updated data"
```

## Safety Features

### Automatic Detection
The integration automatically detects risky replacements and warns you:
- Multiple matches found (might replace wrong text)
- Generic terms in content text (avoid corruption)
- Ambiguous placeholders

### Smart Guidance
When issues are detected, you get:
- Exact match locations
- Suggested safer alternatives
- Risk level assessment
- Fix recommendations

### Example Warning
```
⚠️ BLOCKED: "name" found 8 times
- 2 safe placeholder matches
- 6 content text matches (risky!)

Suggestions:
- Use "Company Name: name" for form fields
- Use "Project Name: name" for project fields
```

## Troubleshooting

**Document not found error?**
- The integration works statelessly - always pass the document file in subsequent actions
- Use the file returned from previous actions

**Formatting not applied correctly?**
- Check markdown syntax (spaces matter in tables)
- Use proper escaping for special characters
- View generated files in Word to verify

**Safety warnings blocking replacements?**
- Add more context to your find phrases
- Use the suggested alternatives from the warning
- Consider position-based updates for complex templates

**Unwanted spacing after deletions?**
- Use `remove_paragraph: true` to eliminate gaps
- Set to `false` to preserve intentional spacing

## Getting Started Examples

### Simple Document
```json
{
  "action": "create_document",
  "inputs": {
    "markdown_content": "# My Report\n\n## Summary\n\nThis quarter exceeded expectations.\n\n- Revenue: $2.1M\n- Growth: 17%",
    "custom_filename": "Q4_Report.docx"
  }
}
```

### Fill a Template
```json
{
  "action": "fill_template_fields",
  "inputs": {
    "document_id": "template-id",
    "template_data": {
      "placeholder_data": {
        "{{COMPANY}}": "Acme Corp",
        "{{DATE}}": "Jan 15, 2025"
      }
    }
  }
}
```

### Safe Find & Replace
```json
{
  "action": "find_and_replace",
  "inputs": {
    "document_id": "doc-id",
    "replacements": [
      {
        "find": "Project Name: placeholder text",
        "replace": "Project Name: Q4 Integration"
      }
    ]
  }
}
```

## Support

Need help?
- Check the [Technical Reference](#technical-reference) below for detailed documentation
- Contact Autohive support through your dashboard

---

# Technical Reference

Complete API documentation for developers and advanced users.

## Installation & Development

### Requirements

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `autohive-integrations-sdk` - Integration framework
- `python-docx` - Word document manipulation
- `pillow` - Image processing
- `markdown` - Markdown to HTML conversion
- `beautifulsoup4` - HTML parsing

### Local Development Setup

```bash
# Install dependencies locally
pip install -r requirements.txt -t dependencies

# Run test suite
cd tests
python test_doc-maker.py           # Main tests (6 tests)
python test_template_filling.py    # Template tests (2 tests)
python test_spacing_fix.py         # Formatting tests
```

### Test Output

All tests generate `.docx` files in `tests/` directory for verification in Microsoft Word.

## Complete Actions Reference

### 1. create_document

**Description:** Create a new Word document with markdown content. Primary action for document creation.

**Input Schema:**
```json
{
  "markdown_content": "string (optional)",
  "custom_filename": "string (optional)",
  "files": [
    {
      "name": "string",
      "contentType": "string",
      "content": "string (base64)"
    }
  ]
}
```

**Output Schema:**
```json
{
  "document_id": "string",
  "paragraph_count": "integer",
  "markdown_processed": "boolean",
  "saved": "boolean",
  "file_path": "string",
  "file": {
    "content": "string (base64)",
    "name": "string",
    "contentType": "string"
  }
}
```

**Example:**
```json
{
  "markdown_content": "# Q4 Report\n\n## Summary\n\n**Revenue:** $2.1M (+17%)",
  "custom_filename": "Q4_Report.docx"
}
```

### 2. add_markdown_content

**Description:** Append markdown content to existing documents. Requires current document file.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "markdown_content": "string (required)",
  "files": [/* current document file */]
}
```

**Output Schema:**
```json
{
  "markdown_processed": "boolean",
  "elements_added": "integer",
  "saved": "boolean",
  "file_path": "string",
  "file": {/* updated document */}
}
```

### 3. get_document_elements

**Description:** Analyze document structure and identify fillable elements. LLM-optimized response.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "files": [/* document to analyze */]
}
```

**Output Schema:**
```json
{
  "template_summary": {
    "structure": "string (e.g., '15p,1t')",
    "fillable_total": "integer",
    "content_elements_hidden": "integer"
  },
  "fillable_paragraphs": [
    {
      "id": "string (e.g., 'p5')",
      "content": "string",
      "pattern": "string",
      "style": "string"
    }
  ],
  "fillable_cells": [
    {
      "id": "string (e.g., 't0r1c2')",
      "content": "string",
      "pattern": "string",
      "location": "string"
    }
  ],
  "pattern_distribution": {},
  "recommended_strategy": "string",
  "template_ready": "boolean"
}
```

### 4. update_by_position

**Description:** Update specific elements by position indices. Most precise method for complex templates.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "updates": [
    {
      "type": "paragraph|table_cell",
      "index": "integer (for paragraphs)",
      "table_index": "integer (for cells)",
      "row": "integer (for cells)",
      "col": "integer (for cells)",
      "content": "string"
    }
  ],
  "files": [/* document file */]
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "applied": "integer",
  "failed": "integer",
  "summary": "string",
  "failures": ["string"],
  "saved": "boolean",
  "file": {/* updated document */}
}
```

### 5. find_and_replace

**Description:** Safe text replacement with context awareness and safety analysis.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "replacements": [
    {
      "find": "string (required)",
      "replace": "string (required)",
      "replace_all": "boolean (default: false)",
      "remove_paragraph": "boolean (default: false)"
    }
  ],
  "case_sensitive": "boolean (default: false)",
  "files": [/* document file */]
}
```

**Output Schema:**
```json
{
  "success": "boolean",
  "replaced": "integer",
  "processed": "integer",
  "blocked": [
    {
      "phrase": "string",
      "warning": "string",
      "safe_matches": "integer",
      "unsafe_matches": "integer",
      "alternatives": ["string"]
    }
  ],
  "alerts": ["string"],
  "safety_active": "boolean",
  "saved": "boolean",
  "file": {/* updated document */}
}
```

**CRITICAL SAFETY RULE:** Always include sufficient context in find phrases!
- ✅ SAFE: `"Date: ___"` → `"Date: January 15, 2025"`
- ❌ UNSAFE: `"date"` → `"January 15"` (corrupts "the update date")

### 6. fill_template_fields

**Description:** Comprehensive template filling with multiple strategies and safety analysis.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "template_data": {
    "placeholder_data": {
      "{{FIELD}}": "value"
    },
    "position_data": {
      "paragraph_5": "content",
      "table_0_row_1_col_2": "content"
    },
    "search_replace": [
      {
        "find": "context phrase",
        "replace": "new value",
        "replace_all": "boolean",
        "remove_paragraph": "boolean"
      }
    ]
  },
  "files": [/* template file */]
}
```

**Output Schema:**
```json
{
  "SAFETY_STATUS": "OK|CRITICAL_ISSUES_DETECTED",
  "success": "boolean",
  "completed_operations": "integer",
  "blocked_operations": "integer",
  "safety_warnings": [
    {
      "CRITICAL_WARNING": "string",
      "find_phrase": "string",
      "risk_assessment": "string",
      "intelligent_alternatives": ["string"],
      "fix_required": "string"
    }
  ],
  "filled_summary": {},
  "template_status": "complete|partially_complete",
  "action_required": "string",
  "saved": "boolean",
  "file": {/* filled document */}
}
```

### 7. add_image

**Description:** Insert images into documents. Supports PNG, JPG, GIF, BMP, WebP.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "width": "number (inches, optional)",
  "height": "number (inches, optional)",
  "files": [
    /* document file */,
    /* image file */
  ]
}
```

**Output Schema:**
```json
{
  "image_added": "boolean",
  "saved": "boolean",
  "file": {/* updated document */}
}
```

### 8. add_table

**Description:** Create tables from structured data arrays.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "rows": "integer (required, min: 1)",
  "cols": "integer (required, min: 1)",
  "data": [
    ["Header 1", "Header 2"],
    ["Row 1 Col 1", "Row 1 Col 2"]
  ],
  "files": [/* document file */]
}
```

**Output Schema:**
```json
{
  "table_rows": "integer",
  "table_cols": "integer",
  "saved": "boolean",
  "file": {/* updated document */}
}
```

### 9. add_page_break

**Description:** Insert page break for layout control.

**Input Schema:**
```json
{
  "document_id": "string (required)",
  "files": [/* document file */]
}
```

**Output Schema:**
```json
{
  "page_break_added": "boolean",
  "saved": "boolean",
  "file": {/* updated document */}
}
```

## Advanced Features

### Markdown Formatting in Replacements

Replacement text supports inline markdown formatting:

```json
{
  "find": "summary here",
  "replace": "Q4 showed **exceptional growth** with *record* results of `$2.1M`."
}
```

Automatically applied in Word:
- `**text**` → Bold
- `*text*` → Italic
- `__text__` → Underline
- `~~text~~` → Strikethrough
- `` `text` `` → Code (monospace)
- `\n` → Line breaks

### Spacing Control

Control paragraph spacing when deleting text:

```json
{
  "find": "(Note: Delete this instruction)",
  "replace": " ",
  "remove_paragraph": true  // Removes paragraph completely
}
```

- `remove_paragraph: true` - Completely removes paragraph (no gap)
- `remove_paragraph: false` (default) - Preserves paragraph spacing

### Placeholder Pattern Detection

Automatically detected patterns:

| Pattern Type | Examples | Use Case |
|--------------|----------|----------|
| **Formal Placeholders** | `{{FIELD}}`, `{FIELD}`, `[FIELD]` | Exact replacement |
| **Instruction Text** | `(Note: add details)`, `Please insert...` | Template instructions |
| **Form Fields** | `Name: ____`, `Date: ---` | Form-style templates |
| **Business Placeholders** | `company name`, `project title` | Natural language |
| **Generic** | `XXX`, `TBD`, `pending` | Common placeholders |


## Key Implementation Details

### Core Functions

**Document Creation:**
- `parse_markdown_to_docx()` - Convert markdown to Word elements
- `parse_and_apply_markdown_formatting()` - Apply inline formatting

**Template Analysis:**
- `analyze_document_structure()` - Scan for fillable elements
- `detect_placeholder_patterns()` - Pattern classification
- `analyze_replacement_safety()` - Safety analysis engine

**Helper Functions:**
- `iter_block_items()` - Iterate paragraphs and tables in order
- `has_markdown_formatting()` - Detect formatting markers
- `is_likely_placeholder_context()` - Context-based detection

**Doc Maker Integration v1.0.0** | Built for Autohive Platform
