# Create original template files for comparison
import asyncio
import os
import base64
from context import doc_maker
from autohive_integrations_sdk import ExecutionContext

async def create_original_templates():
    """Create the original template files for comparison"""
    print("[CREATING] Original template files for comparison...")

    auth = {}

    # Template 1: Comprehensive template with mixed placeholder types
    comprehensive_template = """# {{REPORT_TITLE}}

**Prepared by:** {{AUTHOR_NAME}}
**Date:** {{REPORT_DATE}}

## Executive Summary

Please insert executive summary here.

### Key Performance Indicators

Our company name performance this quarter was data here.

| Metric | Q3 Value | Q4 Value | Change |
|--------|----------|----------|---------|
| Revenue | previous revenue | current revenue | growth data |
| Customers | customer count Q3 | customer count Q4 | customer growth |
| Market Share | {Q3_SHARE} | {Q4_SHARE} | share change |

## Regional Performance

The following sections need to be filled:

### North America
Performance data goes here.

### Europe
Insert European data here.

### Conclusion

TBD - analysis conclusion to be added.

---
*Report generated on: {{GENERATION_DATE}}*"""

    # Template 2: Natural language placeholders only
    natural_template = """# Monthly Report

**Company:** company name here
**Department:** department name
**Manager:** manager name here

## Summary

Please add summary content here.

## Key Metrics

| Metric | Value | Notes |
|--------|-------|--------|
| Sales | sales data | add notes here |
| Customers | customer data | customer notes |
| Growth | growth percentage | growth details |

## Analysis

Enter analysis here.

## Recommendations

Add recommendations here.
"""

    async with ExecutionContext(auth=auth) as context:
        try:
            # Create comprehensive template
            result1 = await doc_maker.execute_action("create_document", {
                "markdown_content": comprehensive_template,
                "custom_filename": "comprehensive_template.docx"
            }, context)

            file_content1 = base64.b64decode(result1['file']['content'])
            output_path1 = os.path.join(os.path.dirname(__file__), "ORIGINAL_COMPREHENSIVE_TEMPLATE.docx")

            with open(output_path1, 'wb') as f:
                f.write(file_content1)

            print(f"[SUCCESS] Comprehensive template saved to: {output_path1}")

            # Create natural language template
            result2 = await doc_maker.execute_action("create_document", {
                "markdown_content": natural_template,
                "custom_filename": "natural_template.docx"
            }, context)

            file_content2 = base64.b64decode(result2['file']['content'])
            output_path2 = os.path.join(os.path.dirname(__file__), "ORIGINAL_NATURAL_TEMPLATE.docx")

            with open(output_path2, 'wb') as f:
                f.write(file_content2)

            print(f"[SUCCESS] Natural template saved to: {output_path2}")

            # Create a business invoice template as well
            invoice_template = """# INVOICE

**Invoice #:** invoice number here
**Date:** invoice date
**Due Date:** due date here

---

**Bill To:**
customer name here
customer address line 1
customer address line 2

**From:**
{{COMPANY_NAME}}
{{COMPANY_ADDRESS}}
{{COMPANY_PHONE}}

---

## Items

| Description | Quantity | Unit Price | Total |
|-------------|----------|------------|-------|
| service description 1 | qty1 | price1 | total1 |
| service description 2 | qty2 | price2 | total2 |
| service description 3 | qty3 | price3 | total3 |

---

**Subtotal:** subtotal amount
**Tax (8.5%):** tax amount
**TOTAL:** total amount due

## Payment Terms

Payment terms go here.

## Notes

Additional notes here.

---
*Thank you for your business!*"""

            result3 = await doc_maker.execute_action("create_document", {
                "markdown_content": invoice_template,
                "custom_filename": "invoice_template.docx"
            }, context)

            file_content3 = base64.b64decode(result3['file']['content'])
            output_path3 = os.path.join(os.path.dirname(__file__), "ORIGINAL_INVOICE_TEMPLATE.docx")

            with open(output_path3, 'wb') as f:
                f.write(file_content3)

            print(f"[SUCCESS] Invoice template saved to: {output_path3}")

            print("\n[COMPLETE] All original templates created!")
            print("[INFO] You can now compare these with their filled versions:")
            print("   ORIGINAL_COMPREHENSIVE_TEMPLATE.docx -> FILLED_TEMPLATE.docx")
            print("   ORIGINAL_NATURAL_TEMPLATE.docx -> FILLED_NATURAL_TEMPLATE.docx")
            print("   ORIGINAL_INVOICE_TEMPLATE.docx -> (create your own filled version!)")

        except Exception as e:
            print(f"[ERROR] Error creating templates: {e}")

if __name__ == "__main__":
    asyncio.run(create_original_templates())