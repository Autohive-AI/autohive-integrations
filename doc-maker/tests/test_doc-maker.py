# Comprehensive tests for doc-maker integration
# Tests markdown parsing, document creation, and file operations
import asyncio
import os
import base64
from context import doc_maker
from autohive_integrations_sdk import ExecutionContext

async def test_create_document_with_markdown():
    """Test creating a document with comprehensive markdown content"""
    print("\n[TEST] Testing create_document with comprehensive markdown...")

    auth = {}  # No auth needed for this integration

    # Comprehensive markdown content showcasing all features
    markdown_content = """# Project Report: Q4 2024 Analysis

This is the **executive summary** of our Q4 performance analysis. The document contains *important insights* and `technical specifications` for stakeholders.

## Key Performance Indicators

Our analysis reveals several critical findings:

### Revenue Metrics
- **Total Revenue**: $2.4M (↑15% from Q3)
- **Recurring Revenue**: $1.8M (↑8% from Q3)
- **New Customer Acquisition**: 150 customers

### Market Analysis

> The market conditions in Q4 showed unprecedented growth, with our company outperforming industry benchmarks by 23%.

#### Competitive Landscape

1. **Market Leader Position**: Maintained #2 position
2. **Customer Satisfaction**: 94% retention rate
3. **Product Innovation**: 3 major features released

## Technical Implementation

### Code Quality Metrics

Our development team implemented the following improvements:

```python
def calculate_performance():
    metrics = {
        'uptime': 99.97,
        'response_time': 120,
        'error_rate': 0.03
    }
    return metrics
```

### Database Performance

| Metric | Q3 2024 | Q4 2024 | Change |
|--------|---------|---------|---------|
| Query Speed | 45ms | 32ms | ↓28% |
| Storage Used | 2.1TB | 2.8TB | ↑33% |
| Active Users | 15,420 | 18,750 | ↑22% |

## Risk Assessment

The following risks were identified:

- **High Priority**: Infrastructure scaling needs
- **Medium Priority**: Compliance requirements
- **Low Priority**: Legacy system migration

### Mitigation Strategies

1. Implement auto-scaling infrastructure
2. Hire additional compliance officer
3. Plan phased legacy migration for Q2 2025

## Recommendations

Based on our analysis, we recommend:

1. **Immediate Actions**:
   - Increase server capacity by 40%
   - Implement new monitoring tools

2. **Long-term Strategy**:
   - Expand to European markets
   - Develop mobile application

> **Note**: All financial projections are based on current market conditions and may vary based on external factors.

## Conclusion

Q4 2024 demonstrated strong performance across all key metrics. The team's dedication to excellence and customer focus has positioned us well for continued growth in 2025.

### Next Steps

- [ ] Review budget allocations
- [ ] Schedule stakeholder meetings
- [ ] Prepare Q1 2025 planning session
"""

    inputs = {
        "markdown_content": markdown_content,
        "custom_filename": "Q4_2024_Report.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await doc_maker.execute_action("create_document", inputs, context)

            print(f"[SUCCESS] Document created successfully!")
            print(f"   Document ID: {result['document_id']}")
            print(f"   Paragraphs: {result['paragraph_count']}")
            print(f"   Markdown processed: {result['markdown_processed']}")
            print(f"   File size: {len(result['file']['content'])} chars (base64)")
            print(f"   Filename: {result['file']['name']}")

            # Save the file locally for inspection
            file_content = base64.b64decode(result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "output_test_document.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Document saved to: {output_path}")
            print(f"   You can open this file in Microsoft Word to verify the output!")

            return result

        except Exception as e:
            print(f"[ERROR] Error testing create_document: {e}")
            return None

async def test_add_markdown_content():
    """Test adding additional markdown content to existing document"""
    print("\n[TEST] Testing add_markdown_content...")

    auth = {}

    # First create a simple document
    initial_content = """# Test Document

This is the initial content."""

    inputs = {
        "markdown_content": initial_content,
        "custom_filename": "test_append.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create initial document
            result = await doc_maker.execute_action("create_document", inputs, context)
            document_id = result['document_id']

            # Additional content to append
            additional_content = """
## Additional Section

This content was added using the `add_markdown_content` action.

### New Features
- **Feature A**: Description of feature A
- **Feature B**: Description of feature B

| Feature | Status | Priority |
|---------|--------|----------|
| Feature A | Complete | High |
| Feature B | In Progress | Medium |

> This demonstrates that the append functionality works correctly.
"""

            # Add the additional content
            append_inputs = {
                "document_id": document_id,
                "markdown_content": additional_content,
                "files": [result['file']]  # Pass the current document
            }

            append_result = await doc_maker.execute_action("add_markdown_content", append_inputs, context)

            print(f"[SUCCESS] Content added successfully!")
            print(f"   Elements added: {append_result['elements_added']}")
            print(f"   Markdown processed: {append_result['markdown_processed']}")

            # Save the updated document
            file_content = base64.b64decode(append_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "output_test_append.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Updated document saved to: {output_path}")
            return append_result

        except Exception as e:
            print(f"[ERROR] Error testing add_markdown_content: {e}")
            return None

async def test_add_image():
    """Test adding an image to a document"""
    print("\n[TEST] Testing add_image...")

    auth = {}

    # Create a simple test image (1x1 pixel PNG)
    # This is a minimal PNG file in base64
    test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77ywAAAABJRU5ErkJggg=="

    # First create a document
    initial_content = """# Document with Image

This document will contain an embedded image below:

## Image Section

The image appears here:"""

    create_inputs = {
        "markdown_content": initial_content,
        "custom_filename": "test_with_image.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create initial document
            result = await doc_maker.execute_action("create_document", create_inputs, context)
            document_id = result['document_id']

            # Add image to the document
            image_inputs = {
                "document_id": document_id,
                "width": 2.0,  # 2 inches wide
                "height": 1.5, # 1.5 inches tall
                "files": [
                    result['file'],  # Current document
                    {
                        "name": "test_image.png",
                        "contentType": "image/png",
                        "content": test_image_base64
                    }
                ]
            }

            image_result = await doc_maker.execute_action("add_image", image_inputs, context)

            print(f"[SUCCESS] Image added successfully!")
            print(f"   Image added: {image_result['image_added']}")

            # Save the document with image
            file_content = base64.b64decode(image_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "output_test_with_image.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Document with image saved to: {output_path}")
            return image_result

        except Exception as e:
            print(f"[ERROR] Error testing add_image: {e}")
            return None

async def test_add_table():
    """Test adding a structured table to a document"""
    print("\n[TEST] Testing add_table with structured data...")

    auth = {}

    # First create a document
    initial_content = """# Sales Report

The following table shows our quarterly sales data:"""

    create_inputs = {
        "markdown_content": initial_content,
        "custom_filename": "test_with_table.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create initial document
            result = await doc_maker.execute_action("create_document", create_inputs, context)
            document_id = result['document_id']

            # Add structured table
            table_data = [
                ["Quarter", "Revenue", "Customers", "Growth"],
                ["Q1 2024", "$1.2M", "1,250", "12%"],
                ["Q2 2024", "$1.5M", "1,580", "25%"],
                ["Q3 2024", "$1.8M", "1,920", "20%"],
                ["Q4 2024", "$2.1M", "2,340", "17%"]
            ]

            table_inputs = {
                "document_id": document_id,
                "rows": 5,
                "cols": 4,
                "data": table_data,
                "files": [result['file']]
            }

            table_result = await doc_maker.execute_action("add_table", table_inputs, context)

            print(f"[SUCCESS] Table added successfully!")
            print(f"   Table dimensions: {table_result['table_rows']}x{table_result['table_cols']}")

            # Save the document with table
            file_content = base64.b64decode(table_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "output_test_with_table.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Document with table saved to: {output_path}")
            return table_result

        except Exception as e:
            print(f"[ERROR] Error testing add_table: {e}")
            return None

async def test_add_page_break():
    """Test adding page breaks to a document"""
    print("\n[TEST] Testing add_page_break...")

    auth = {}

    # Create document with content
    content = """# Page 1 Content

This is the content on the first page of the document.

## Section A

Some content here that will be on page 1."""

    create_inputs = {
        "markdown_content": content,
        "custom_filename": "test_page_break.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create initial document
            result = await doc_maker.execute_action("create_document", create_inputs, context)
            document_id = result['document_id']

            # Add page break
            page_break_inputs = {
                "document_id": document_id,
                "files": [result['file']]
            }

            page_break_result = await doc_maker.execute_action("add_page_break", page_break_inputs, context)

            # Add content after page break
            page2_content = """# Page 2 Content

This content should appear on the second page after the page break.

## Section B

This demonstrates that the page break functionality works correctly."""

            append_inputs = {
                "document_id": document_id,
                "markdown_content": page2_content,
                "files": [page_break_result['file']]
            }

            final_result = await doc_maker.execute_action("add_markdown_content", append_inputs, context)

            print(f"[SUCCESS] Page break added successfully!")
            print(f"   Page break added: {page_break_result['page_break_added']}")

            # Save the document with page break
            file_content = base64.b64decode(final_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "output_test_page_break.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Document with page break saved to: {output_path}")
            return final_result

        except Exception as e:
            print(f"[ERROR] Error testing add_page_break: {e}")
            return None

async def test_comprehensive_document():
    """Create one comprehensive document showcasing all features"""
    print("\n[TEST] Creating comprehensive showcase document...")

    auth = {}

    # Create comprehensive markdown content with all features
    comprehensive_content = """# Doc Maker Integration - Feature Showcase

This document demonstrates all the markdown-to-Word conversion capabilities of the Doc Maker integration.

## Executive Summary

This integration allows **AI agents** to create professional Word documents using *familiar markdown syntax*. The system automatically converts markdown elements to properly formatted Word document components.

### Key Features Demonstrated

1. **Heading Levels**: From H1 through H6
2. **Text Formatting**: Bold, italic, and `inline code`
3. **Lists**: Both bulleted and numbered
4. **Tables**: Markdown table syntax support
5. **Blockquotes**: Professional quote formatting
6. **Code Blocks**: Syntax highlighting and monospace fonts

## Formatting Examples

### Text Styling

Here are examples of **bold text**, *italic text*, and `inline code snippets`. You can also combine ***bold and italic*** formatting.

### Lists and Organization

#### Bullet Lists
- **Primary Point**: This is a main bullet point
- **Secondary Point**: This shows list hierarchy
  - Sub-point A: Nested bullet example
  - Sub-point B: Another nested item
- **Final Point**: Concluding bullet

#### Numbered Lists
1. **First Step**: Initialize the document
2. **Second Step**: Add your markdown content
3. **Third Step**: Process and convert to Word
4. **Fourth Step**: Download the generated document

### Data Tables

The following table shows quarterly performance metrics:

| Quarter | Revenue | Customers | Growth Rate | Status |
|---------|---------|-----------|-------------|---------|
| Q1 2024 | $1.2M | 1,250 | 12.5% | Complete |
| Q2 2024 | $1.5M | 1,580 | 25.3% | Complete |
| Q3 2024 | $1.8M | 1,920 | 20.1% | Complete |
| Q4 2024 | $2.1M | 2,340 | 16.7% | In Progress |

### Technical Implementation

#### Code Examples

Here's a Python function that demonstrates the integration usage:

```python
def create_document_from_markdown():
    inputs = {
        "markdown_content": markdown_text,
        "custom_filename": "output.docx"
    }

    result = await doc_maker.execute_action(
        "create_document",
        inputs,
        context
    )

    return result["file"]
```

#### System Architecture

The doc-maker integration uses the following technology stack:

- **python-docx**: Core Word document manipulation
- **markdown**: Markdown to HTML conversion
- **beautifulsoup4**: HTML parsing and processing
- **autohive-integrations-sdk**: Integration framework

### Important Notes and Quotes

> **Performance Note**: The integration processes markdown content efficiently, converting a typical business document (2-3 pages) in under 100ms.

> **Compatibility**: Generated documents are fully compatible with Microsoft Word 2016+ and other Office suites that support .docx format.

## Advanced Features

### Multi-level Headings

# Heading Level 1
## Heading Level 2
### Heading Level 3
#### Heading Level 4
##### Heading Level 5
###### Heading Level 6

### Mixed Content Types

This section shows how different markdown elements work together:

1. **Lists with formatting**: You can have *italic* text in lists
2. **Code in lists**: Use `inline code` within bullet points
3. **Links and references**: While not yet implemented, future versions will support [links](http://example.com)

### Business Use Cases

The Doc Maker integration is perfect for:

- **Report Generation**: Quarterly reports, analysis documents
- **Documentation**: Technical specs, user manuals
- **Proposals**: Business proposals, project plans
- **Communications**: Memos, announcements, newsletters

## Testing and Quality Assurance

### Test Coverage

This document itself serves as a comprehensive test of the integration's capabilities:

| Feature | Status | Notes |
|---------|--------|-------|
| Headings (H1-H6) | ✓ Working | All levels supported |
| Text Formatting | ✓ Working | Bold, italic, code |
| Bullet Lists | ✓ Working | Multiple levels supported |
| Numbered Lists | ✓ Working | Automatic numbering |
| Tables | ✓ Working | Full markdown table support |
| Blockquotes | ✓ Working | Professional styling |
| Code Blocks | ✓ Working | Monospace formatting |

### Performance Metrics

> **Processing Speed**: Markdown parsing and conversion completes in milliseconds
> **Output Quality**: Generated documents maintain professional formatting
> **Compatibility**: Full .docx standard compliance

## Conclusion

The Doc Maker integration successfully bridges the gap between markdown simplicity and Word document professionalism. AI agents can now generate sophisticated business documents using familiar markdown syntax, dramatically simplifying the document creation process.

### Next Steps

After reviewing this document, you can:

1. **Verify formatting**: Check that all elements appear correctly
2. **Test modifications**: Use `add_markdown_content` to append sections
3. **Add images**: Use the `add_image` action for visual content
4. **Insert page breaks**: Use `add_page_break` for multi-page documents

---

*This document was generated automatically by the Doc Maker integration test suite to demonstrate markdown-to-Word conversion capabilities.*"""

    # Test creating comprehensive document
    inputs = {
        "markdown_content": comprehensive_content,
        "custom_filename": "Complete_Feature_Showcase.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await doc_maker.execute_action("create_document", inputs, context)
            document_id = result['document_id']

            print(f"[SUCCESS] Comprehensive document created!")
            print(f"   Document ID: {result['document_id']}")
            print(f"   Paragraphs: {result['paragraph_count']}")

            # Add a page break before additional content
            page_break_inputs = {
                "document_id": document_id,
                "files": [result['file']]
            }

            page_break_result = await doc_maker.execute_action("add_page_break", page_break_inputs, context)

            # Add a structured table using the direct table action
            additional_content = """
# Appendix A: Additional Data

The following section was added using the `add_markdown_content` action to demonstrate document modification capabilities."""

            append_inputs = {
                "document_id": document_id,
                "markdown_content": additional_content,
                "files": [page_break_result['file']]
            }

            append_result = await doc_maker.execute_action("add_markdown_content", append_inputs, context)

            # Add a structured table with detailed sales data
            detailed_table_data = [
                ["Region", "Q1 Revenue", "Q2 Revenue", "Q3 Revenue", "Q4 Revenue", "Total", "Growth"],
                ["North America", "$450K", "$520K", "$610K", "$720K", "$2.3M", "60%"],
                ["Europe", "$380K", "$420K", "$480K", "$550K", "$1.83M", "45%"],
                ["Asia Pacific", "$290K", "$350K", "$430K", "$510K", "$1.58M", "76%"],
                ["Latin America", "$180K", "$210K", "$260K", "$320K", "$970K", "78%"],
                ["Total", "$1.3M", "$1.5M", "$1.78M", "$2.1M", "$6.68M", "62%"]
            ]

            table_inputs = {
                "document_id": document_id,
                "rows": 6,
                "cols": 7,
                "data": detailed_table_data,
                "files": [append_result['file']]
            }

            table_result = await doc_maker.execute_action("add_table", table_inputs, context)

            # Add a test image
            test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77ywAAAABJRU5ErkJggg=="

            image_inputs = {
                "document_id": document_id,
                "width": 1.5,
                "height": 1.0,
                "files": [
                    table_result['file'],
                    {
                        "name": "test_chart.png",
                        "contentType": "image/png",
                        "content": test_image_base64
                    }
                ]
            }

            final_result = await doc_maker.execute_action("add_image", image_inputs, context)

            # Save the comprehensive document
            file_content = base64.b64decode(final_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "COMPREHENSIVE_SHOWCASE.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Comprehensive showcase saved to: {output_path}")
            print(f"   [INFO] This file demonstrates ALL integration features in one document!")

            return final_result

        except Exception as e:
            print(f"[ERROR] Error creating comprehensive document: {e}")
            return None

async def main():
    """Run all tests"""
    print("[STARTING] Testing Doc Maker Integration")
    print("="*50)

    # First create the comprehensive showcase document
    comprehensive_result = await test_comprehensive_document()

    # Run individual tests
    test_results = []

    test_results.append(("comprehensive_showcase", comprehensive_result is not None))

    result1 = await test_create_document_with_markdown()
    test_results.append(("create_document", result1 is not None))

    result2 = await test_add_markdown_content()
    test_results.append(("add_markdown_content", result2 is not None))

    result3 = await test_add_image()
    test_results.append(("add_image", result3 is not None))

    result4 = await test_add_table()
    test_results.append(("add_table", result4 is not None))

    result5 = await test_add_page_break()
    test_results.append(("add_page_break", result5 is not None))

    # Print test summary
    print("\n[SUMMARY] Test Summary:")
    print("="*30)

    passed = 0
    total = len(test_results)

    for test_name, success in test_results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("[SUCCESS] All tests passed! Check the generated .docx files in the tests directory.")
    else:
        print("[WARNING] Some tests failed. Check the error messages above.")

    print("\n[FILES] Generated test files:")
    test_dir = os.path.dirname(__file__)
    for filename in os.listdir(test_dir):
        if filename.startswith("output_test_") and filename.endswith(".docx"):
            print(f"   - {os.path.join(test_dir, filename)}")

if __name__ == "__main__":
    asyncio.run(main())
