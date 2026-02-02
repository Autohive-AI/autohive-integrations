# Quick test to verify spacing fix
import asyncio
import os
import base64
from context import doc_maker
from autohive_integrations_sdk import ExecutionContext

async def test_spacing():
    """Test that text spacing is preserved in formatted text"""
    print("[TEST] Testing text spacing preservation...")

    auth = {}

    # Test content with specific spacing issues
    test_content = """# Text Spacing Test

Here are examples of **bold text**, *italic text*, and `inline code snippets`. You can also combine ***bold and italic*** formatting.

This paragraph has **multiple** *different* `formatting` elements **mixed** together with proper spacing.

## List with Formatting

- **Bold item**: This should have proper spacing
- *Italic item*: This should also have proper spacing
- `Code item`: And this should maintain spacing too
"""

    inputs = {
        "markdown_content": test_content,
        "custom_filename": "spacing_test.docx"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await doc_maker.execute_action("create_document", inputs, context)

            print(f"[SUCCESS] Spacing test document created!")
            print(f"   Paragraphs: {result['paragraph_count']}")

            # Save for inspection
            file_content = base64.b64decode(result['file']['content'])
            output_path = os.path.join(os.path.dirname(__file__), "SPACING_TEST.docx")

            with open(output_path, 'wb') as f:
                f.write(file_content)

            print(f"   [FILE] Spacing test saved to: {output_path}")
            print(f"   [INFO] Open this file to verify proper spacing between formatted text!")

            return result

        except Exception as e:
            print(f"[ERROR] Error in spacing test: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(test_spacing())