# Slide Maker Integration

Create professional PowerPoint presentations automatically using markdown syntax. Perfect for generating slides, filling templates, and automating presentation workflows.

## What You Can Do

- **Create Presentations with Markdown**: Use familiar markdown syntax (headings, lists, tables, formatting) to generate PowerPoint slides
- **Fill Templates Safely**: Intelligently detect and replace placeholders with built-in safety checks and automatic font sizing
- **Add Rich Content**: Insert images, charts, tables, formatted text with automatic positioning
- **Smart Find & Replace**: Context-aware text replacement that prevents unintended changes and preserves formatting

## Quick Setup

1. **Install the Integration**: Add Slide Maker to your Autohive workspace
2. **Start Creating**: Use markdown in your workflows immediately
3. **No Authentication Required**: Works out of the box - no account setup needed

## Available Actions

### Create Presentation

Generate a PowerPoint presentation from scratch or from a template.

**Common Parameters:**
- `title`: Optional title for the first slide (supports markdown formatting)
- `subtitle`: Optional subtitle for the first slide
- `files`: Optional template file to use as starting point
- `custom_filename`: Optional filename for the output (auto-adds .pptx)

**Example Use Cases:**
- Generate weekly sales presentations from data
- Create training decks automatically
- Build pitch decks from structured data

### Add Elements

Add content to slides using markdown with two powerful modes.

**Mode 1: Auto-Layout** (Recommended for quick content)
- `auto_layout: true` - Automatic vertical flow layout
- `markdown`: Single markdown document with full formatting support
- Supports: headings (H1-H6), paragraphs, bullets, tables, blockquotes, code blocks

**Mode 2: Granular** (For precise control)
- `auto_layout: false` - Manual positioning control
- `elements`: Array of markdown elements with positions
- `auto_position`: Enable intelligent overlap avoidance

**Example Use Cases:**
- Add multiple slides of content from a document
- Position charts and text precisely
- Automatically flow markdown content into slides

### Find and Replace

Search and replace text throughout presentations with safety checks and automatic formatting.

**Common Parameters:**
- `replacements`: List of find/replace pairs
- `replace_all`: Replace all occurrences (requires confirmation for multiple matches)
- `forced_font_size`: Override automatic font size calculation
- `case_sensitive`: Match exact case (default: no)

**Safety Features:**
- Warns when search term might match unintended text
- Automatic font size calculation to fit replacement text
- Preserves original formatting (colors, bold, italic, bullets)
- Supports markdown formatting in replacement text
- Detects placeholder metadata for advanced formatting control

### Add Slide

Add blank slides to existing presentations for additional content.

### Add Image

Insert images with precise positioning and sizing. Supports PNG, JPG, JPEG, GIF, and BMP formats.

### Add Chart

Create data visualizations with multiple chart types.

**Supported Chart Types:**
- Column (clustered)
- Line
- Pie
- Bar (clustered)
- Area
- XY Scatter

## Markdown Syntax Quick Reference

### Headings
```markdown
# H1 - Main Title (large, bold)
## H2 - Section Heading
### H3 - Subsection
#### H4-H6 - Smaller headings
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
  - Nested bullet (indented)

1. Numbered item
2. Another number
```

### Tables
```markdown
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Row 2    | Value    | Info     |
```

### Blockquotes and Code
```markdown
> This is a blockquote
> Great for callouts and emphasis

```
Code blocks for technical content
Preserves formatting and spacing
```
```

## Best Practices

### Template Design
- Use clear placeholders like `{{FIELD_NAME}}` or `[FIELD_NAME]` instead of generic words
- Include metadata in placeholders for formatting: `[Title, Fontsize=32pt, Bold=true, Color=#FF0000]`
- Make placeholders unique to avoid accidental replacements
- Test templates before bulk processing

### Safe Text Replacement
- **Always include context** in your find phrases:
  - ✅ Good: `"Project: {{PROJECT_NAME}}"`
  - ❌ Bad: `"project"` (too generic)
- Let the system analyze for complex templates
- Review safety warnings - they provide specific guidance
- Use `replace_all: true` only when you're certain
- Trust automatic font sizing - it preserves template intent

### Content Creation with Auto-Layout
- Use `auto_layout: true` for 90% of content creation (it's faster)
- Provide single markdown document - let the integration handle positioning
- Use headings to structure content logically
- Add images and charts separately with precise positioning
- Break very long documents into sections for better control

### Positioning Control
- Default positions use vertical stacking (safe, no overlaps)
- Enable `auto_position: true` for intelligent overlap avoidance
- Manually specify positions only when precise control is needed
- Standard slide size: 10 inches wide × 7.5 inches tall

### Performance
- Batch similar operations when possible
- Process presentations in memory (no temp files needed)
- Use appropriate limits for large templates
- Test with sample data first

## Placeholder Strategies

### Strategy 1: Simple Placeholders (Easiest)
Use formal placeholders that won't appear in normal text:
```
{{COMPANY_NAME}} → "Acme Corp"
[DATE] → "January 15, 2025"
{PROJECT} → "Q4 Integration"
```

### Strategy 2: Placeholders with Metadata (Powerful)
Embed formatting instructions in placeholders:
```
[Title, Fontsize=32pt, Bold=true] → "Quarterly Results"
[ClientName, Font=Sofia Pro, Color=#FF0000] → "Acme Corp"
[Date, Format=short] → "Jan 15, 2025"
```

**Supported Metadata:**
- `Fontsize=32pt` - Force specific font size
- `Font=Sofia Pro` - Font face to use
- `Bold=true/false` - Apply bold formatting
- `Italic=true/false` - Apply italic formatting
- `Underline=true/false` - Apply underline
- `Color=#FF0000` - Text color (hex format)

### Strategy 3: Contextual Replacement (Balanced)
Include surrounding text for safety:
```
"Project Name: placeholder text" → "Project Name: Q4 Integration"
"Date: TBD" → "Date: January 15, 2025"
```

## Safety Features

### Automatic Detection
The integration automatically detects risky replacements and warns you:
- Multiple matches found (might replace wrong text)
- Generic terms that could corrupt content
- Ambiguous placeholders
- Blocked operations requiring `replace_all: true` confirmation

### Smart Font Sizing
When replacing text, the integration:
- Preserves original template designer's intent
- Automatically calculates best-fit font size
- Respects placeholder metadata (Fontsize=32pt)
- Honors `forced_font_size` parameter for override
- Prevents text overflow and maintains readability

### Intelligent Guidance
When issues are detected, you get:
- Exact match locations (slide, element, row/col for tables)
- Detailed changelog showing each replacement
- Font sizes applied to replaced text
- Suggestions for safer alternatives
- Status tracking: all_successful, partial_success, all_failed, all_blocked

### Example Warning
```
⚠️ BLOCKED: "name" found 8 times
- Requires replace_all=true for multiple matches
- First 5 locations shown:
  - Slide 0, Element 5 (text_box)
  - Slide 1, Element 3 (table_cell, row 2, col 1)
  ...

Suggestion: Add context or enable replace_all
```

## Troubleshooting

**Presentation not found error?**
- The integration works statelessly - always pass the presentation file in subsequent actions
- Use the file returned from previous actions in the `files` parameter

**Formatting not applied correctly?**
- Check markdown syntax (spaces matter in tables)
- Use proper escaping for special characters
- View generated files in PowerPoint to verify
- Enable FONT_SIZE_DEBUG environment variable for detailed sizing logs

**Safety warnings blocking replacements?**
- Add more context to your find phrases
- Use `replace_all: true` if you're certain about multiple replacements
- Consider placeholder metadata for complex formatting
- Review the detailed changelog for specific issues

**Elements overlapping on slide?**
- Enable `auto_position: true` for automatic overlap avoidance
- Use `auto_layout: true` mode for vertical flow
- Review element positions with validate action
- Adjust positions manually if needed

**Text doesn't fit in box?**
- Trust automatic font sizing - it adapts to content length
- Use `forced_font_size` only when absolutely necessary
- Check if original template font size was too large
- Consider splitting long content across multiple elements


### Markdown Formatting in Replacements

Replacement text supports inline markdown formatting that's automatically converted:

```json
{
  "find": "{{SUMMARY}}",
  "replace": "Q4 showed **exceptional growth** with *record* results of `$2.1M`."
}
```

Automatically applied in PowerPoint:
- `**text**` → Bold
- `*text*` → Italic
- `__text__` → Underline
- `~~text~~` → Strikethrough
- `` `text` `` → Code (monospace)
- `\n` → Line breaks

### Placeholder Pattern Detection

Automatically detected patterns:

| Pattern Type | Examples | Use Case |
|--------------|----------|----------|
| **Formal Placeholders** | `{{FIELD}}`, `{FIELD}`, `[FIELD]` | Exact replacement |
| **Metadata Placeholders** | `[Title, Fontsize=32pt, Bold=true]` | Formatted replacement |
| **Form Fields** | `Name: ____`, `Date: ---` | Form-style templates |

### Automatic Font Sizing

The integration intelligently calculates font sizes:
1. Preserves original template designer's font size as maximum
2. Calculates best-fit size based on text length and box dimensions
3. Respects placeholder metadata (Fontsize=32pt)
4. Honors `forced_font_size` parameter for override
5. Considers markdown formatting overhead (bullets, bold, etc.)
6. Prevents text overflow while maintaining readability

**Debug Mode:** Set `FONT_SIZE_DEBUG=true` environment variable for detailed sizing logs.

### Intelligent Position Validation

When adding elements with `auto_position: true`:
1. Checks for overlap with existing elements
2. Validates slide boundary constraints
3. Searches for safe alternative positions
4. Provides detailed adjustment reasons
5. Gracefully handles positioning failures

### Element Type Auto-Detection

From markdown content:
- `| Col1 | Col2 |` with separator → **table**
- `- Item` or `1. Item` → **bullets**
- Plain text or inline formatting → **text box**
- `# Heading` (auto-layout) → **h1-h6**
- `> Quote` (auto-layout) → **blockquote**
- ` ``` code ``` ` (auto-layout) → **code block**

**Slide Maker Integration v1.0.0** | Built for Autohive Platform
