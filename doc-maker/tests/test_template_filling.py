# Test template filling functionality
import asyncio
import os
import base64
from context import doc_maker
from autohive_integrations_sdk import ExecutionContext

async def test_template_analysis_and_filling():
    """Test template analysis and filling using existing original template"""
    print("[TEST] Testing template analysis and filling...")

    auth = {}

    # Load the existing comprehensive template file
    template_path = os.path.join(os.path.dirname(__file__), "ORIGINAL_COMPREHENSIVE_TEMPLATE.docx")

    if not os.path.exists(template_path):
        print(f"[ERROR] Original template not found: {template_path}")
        print("[INFO] Run create_original_templates.py first to create the template files!")
        return None

    # Read the template file
    with open(template_path, 'rb') as f:
        template_content = f.read()

    template_base64 = base64.b64encode(template_content).decode('utf-8')

    # Load template into doc-maker
    create_inputs = {
        "files": [{
            "name": "comprehensive_template.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "content": template_base64
        }]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Load existing template (this creates a new document_id but loads the existing file)
            template_result = await doc_maker.execute_action("create_document", create_inputs, context)
            document_id = template_result['document_id']

            print(f"[SUCCESS] Template created with {template_result['paragraph_count']} paragraphs")

            # Step 2: Analyze template structure
            analysis_inputs = {
                "document_id": document_id,
                "include_content": True,
                "files": [template_result['file']]
            }

            analysis_result = await doc_maker.execute_action("get_document_elements", analysis_inputs, context)

            print(f"[ANALYSIS] Template structure:")
            print(f"   Template summary: {analysis_result['template_summary']}")
            print(f"   Fillable total: {analysis_result['template_summary']['fillable_total']}")
            print(f"   Fillable paragraphs: {len(analysis_result['fillable_paragraphs'])}")
            print(f"   Fillable cells: {len(analysis_result['fillable_cells'])}")

            # Show some fillable elements
            print(f"   Detected fillable elements:")
            for elem in analysis_result['fillable_paragraphs'][:5]:  # Show first 5
                print(f"     - {elem['id']}: '{elem['content'][:50]}...' (pattern: {elem['pattern']})")

            if analysis_result['fillable_cells']:
                print(f"   First fillable cells:")
                for cell in analysis_result['fillable_cells'][:3]:
                    print(f"     - {cell['id']}: '{cell['content']}' at {cell['location']}")

            # Step 3: Fill template using comprehensive approach
            template_data = {
                # Exact placeholder replacements
                "placeholder_data": {
                    "{{REPORT_TITLE}}": "Q4 2024 Performance Report",
                    "{{AUTHOR_NAME}}": "John Smith, Senior Analyst",
                    "{{REPORT_DATE}}": "January 15, 2025",
                    "{{GENERATION_DATE}}": "January 15, 2025 at 3:30 PM",
                    "{Q3_SHARE}": "23.5%",
                    "{Q4_SHARE}": "26.8%"
                },
                # Natural language placeholder replacements
                "search_replace": [
                    {"find": "Please insert executive summary here", "replace": "Q4 2024 showed exceptional growth across all business units, with revenue increasing 17% and customer acquisition exceeding targets by 25%."},
                    {"find": "data here", "replace": "exceeded expectations with record-breaking results"},
                    {"find": "company name", "replace": "Acme Corporation"},
                    {"find": "previous revenue", "replace": "$1.8M"},
                    {"find": "current revenue", "replace": "$2.1M"},
                    {"find": "growth data", "replace": "+16.7%"},
                    {"find": "customer count Q3", "replace": "1,920"},
                    {"find": "customer count Q4", "replace": "2,340"},
                    {"find": "customer growth", "replace": "+21.9%"},
                    {"find": "share change", "replace": "+3.3%"},
                    {"find": "Performance data goes here", "replace": "North American operations generated $1.2M in revenue with 1,150 new customers."},
                    {"find": "Insert European data here", "replace": "European markets contributed $650K in revenue with strong growth in Germany and France."},
                    {"find": "TBD - analysis conclusion to be added", "replace": "The strong Q4 performance positions us well for continued growth in 2025, with particular strength in customer retention and market expansion."}
                ]
            }

            fill_inputs = {
                "document_id": document_id,
                "template_data": template_data,
                "files": [template_result['file']]
            }

            filled_result = await doc_maker.execute_action("fill_template_fields", fill_inputs, context)

            print(f"[SUCCESS] Template filled successfully!")
            print(f"   Success: {filled_result['success']}")
            print(f"   Completed operations: {filled_result['completed_operations']}")
            print(f"   Template status: {filled_result['template_status']}")
            if filled_result.get('filled_summary'):
                print(f"   Filled summary: {filled_result['filled_summary']}")
            if filled_result.get('safety_warnings'):
                print(f"   Safety warnings: {len(filled_result['safety_warnings'])} warnings")

            # Save filled template with new name
            file_content = base64.b64decode(filled_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "COMPREHENSIVE_TEMPLATE_EDITED.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Edited template saved to: {output_path}")
            print(f"   [INFO] Compare ORIGINAL_COMPREHENSIVE_TEMPLATE.docx with COMPREHENSIVE_TEMPLATE_EDITED.docx!")

            return filled_result

        except Exception as e:
            print(f"[ERROR] Error in template filling test: {e}")
            return None

async def test_natural_language_placeholders():
    """Test filling templates with natural language placeholders using existing template"""
    print("\n[TEST] Testing natural language placeholder filling...")

    auth = {}

    # Load the existing natural language template file
    template_path = os.path.join(os.path.dirname(__file__), "ORIGINAL_NATURAL_TEMPLATE.docx")

    if not os.path.exists(template_path):
        print(f"[ERROR] Original natural template not found: {template_path}")
        print("[INFO] Run create_original_templates.py first!")
        return None

    # Read the template file
    with open(template_path, 'rb') as f:
        template_content = f.read()

    template_base64 = base64.b64encode(template_content).decode('utf-8')

    # Load template into doc-maker
    create_inputs = {
        "files": [{
            "name": "natural_template.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "content": template_base64
        }]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Load existing template
            template_result = await doc_maker.execute_action("create_document", create_inputs, context)
            document_id = template_result['document_id']

            # Analyze to see what's detected as fillable
            analysis_result = await doc_maker.execute_action("get_document_elements", {
                "document_id": document_id,
                "files": [template_result['file']]
            }, context)

            print(f"[ANALYSIS] Natural language template:")
            print(f"   Fillable paragraphs: {analysis_result['fillable_paragraphs']}")
            print(f"   Fillable cells: {analysis_result['fillable_cells']}")

            # Fill using find_and_replace for natural language
            replacements = [
                {"find": "company name here", "replace": "TechCorp Industries"},
                {"find": "department name", "replace": "Sales Department"},
                {"find": "manager name here", "replace": "Sarah Johnson"},
                {"find": "Please add summary content here", "replace": "December 2024 was our strongest month yet, with exceptional performance across all key metrics and successful launch of our new product line."},
                {"find": "sales data", "replace": "$850K"},
                {"find": "add notes here", "replace": "15% above target"},
                {"find": "customer data", "replace": "1,240"},
                {"find": "customer notes", "replace": "22% growth"},
                {"find": "growth percentage", "replace": "18.5%"},
                {"find": "growth details", "replace": "Exceeded projections"},
                {"find": "Enter analysis here", "replace": "The strong performance was driven by increased demand for our premium services and successful retention strategies."},
                {"find": "Add recommendations here", "replace": "Continue current strategies while expanding into new market segments. Increase customer service capacity to handle growing demand."}
            ]

            replace_inputs = {
                "document_id": document_id,
                "replacements": replacements,
                "case_sensitive": False,
                "files": [template_result['file']]
            }

            filled_result = await doc_maker.execute_action("find_and_replace", replace_inputs, context)

            print(f"[SUCCESS] Natural language template filled!")
            print(f"   Success: {filled_result['success']}")
            print(f"   Replacements made: {filled_result['replaced']}")
            print(f"   Processed: {filled_result['processed']} replacement patterns")
            if filled_result.get('alerts'):
                print(f"   Alerts: {filled_result['alerts']}")

            # Save edited natural template with new name
            file_content = base64.b64decode(filled_result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "NATURAL_TEMPLATE_EDITED.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Edited natural template saved to: {output_path}")
            print(f"   [INFO] Compare ORIGINAL_NATURAL_TEMPLATE.docx with NATURAL_TEMPLATE_EDITED.docx!")

            return filled_result

        except Exception as e:
            print(f"[ERROR] Error in natural language test: {e}")
            return None

async def main():
    """Run template filling tests"""
    print("[STARTING] Template Filling Tests")
    print("="*40)

    # Test 1: Comprehensive template with mixed placeholder types
    result1 = await test_template_analysis_and_filling()

    # Test 2: Natural language placeholders only
    result2 = await test_natural_language_placeholders()

    # Summary
    print("\n[SUMMARY] Template Filling Test Results:")
    print("="*40)

    test_results = [
        ("Comprehensive Template Filling", result1 is not None),
        ("Natural Language Placeholders", result2 is not None)
    ]

    passed = 0
    for test_name, success in test_results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1

    print(f"\nResults: {passed}/{len(test_results)} template tests passed")

    if passed == len(test_results):
        print("\n[SUCCESS] All template filling tests passed!")
        print("[FILES] Template comparison files:")
        print("   ORIGINAL -> EDITED:")
        print("   - ORIGINAL_COMPREHENSIVE_TEMPLATE.docx -> COMPREHENSIVE_TEMPLATE_EDITED.docx")
        print("   - ORIGINAL_NATURAL_TEMPLATE.docx -> NATURAL_TEMPLATE_EDITED.docx")
        print("\n[INFO] Open original and edited files side-by-side to see template modifications!")
    else:
        print("\n[WARNING] Some template tests failed.")

if __name__ == "__main__":
    asyncio.run(main())