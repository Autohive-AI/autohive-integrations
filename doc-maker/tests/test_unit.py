"""
Unit Tests for Doc Maker Integration
Tests individual functions and utilities without full integration testing.
"""

import sys
import os

# Import from context.py which properly loads the module
from context import doc_maker, doc_maker_functions

# Extract the functions we want to test
detect_placeholder_patterns = doc_maker_functions.detect_placeholder_patterns
has_markdown_formatting = doc_maker_functions.has_markdown_formatting
is_likely_placeholder_context = doc_maker_functions.is_likely_placeholder_context
analyze_replacement_safety = doc_maker_functions.analyze_replacement_safety


class TestResult:
    """Simple test result tracker"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def assert_equal(self, actual, expected, test_name):
        """Assert two values are equal"""
        if actual == expected:
            self.passed += 1
            self.tests.append((test_name, True, None))
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            error = f"Expected {expected}, got {actual}"
            self.tests.append((test_name, False, error))
            print(f"  [FAIL] {test_name}: {error}")

    def assert_true(self, condition, test_name):
        """Assert condition is true"""
        if condition:
            self.passed += 1
            self.tests.append((test_name, True, None))
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            error = "Condition was False"
            self.tests.append((test_name, False, error))
            print(f"  [FAIL] {test_name}: {error}")

    def assert_false(self, condition, test_name):
        """Assert condition is false"""
        if not condition:
            self.passed += 1
            self.tests.append((test_name, True, None))
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            error = "Condition was True"
            self.tests.append((test_name, False, error))
            print(f"  [FAIL] {test_name}: {error}")

    def summary(self):
        """Return test summary"""
        total = self.passed + self.failed
        return {
            'passed': self.passed,
            'failed': self.failed,
            'total': total,
            'success_rate': (self.passed / total * 100) if total > 0 else 0
        }


async def test_detect_placeholder_patterns():
    """Test placeholder pattern detection"""
    print("\n[TEST] Placeholder Pattern Detection")
    result = TestResult()

    # Test formal placeholders
    is_placeholder, pattern = detect_placeholder_patterns("{{FIELD_NAME}}")
    result.assert_true(is_placeholder, "Detect {{FIELD_NAME}} as formal placeholder")
    result.assert_equal(pattern, "formal_placeholder", "Correct pattern type for {{FIELD}}")

    is_placeholder, pattern = detect_placeholder_patterns("{FIELD}")
    result.assert_true(is_placeholder, "Detect {FIELD} as formal placeholder")

    is_placeholder, pattern = detect_placeholder_patterns("[PLACEHOLDER]")
    result.assert_true(is_placeholder, "Detect [PLACEHOLDER] as formal placeholder")

    # Test instruction text
    is_placeholder, pattern = detect_placeholder_patterns("(Note: Add details here)")
    result.assert_true(is_placeholder, "Detect instruction text")
    result.assert_equal(pattern, "instruction_text", "Correct pattern for instruction text")

    is_placeholder, pattern = detect_placeholder_patterns("Please insert content here")
    result.assert_true(is_placeholder, "Detect 'Please insert' as instruction")

    # Test form fields
    is_placeholder, pattern = detect_placeholder_patterns("Name: ____")
    result.assert_true(is_placeholder, "Detect form field 'Name: ____'")
    result.assert_equal(pattern, "form_style", "Correct pattern for form field")

    # Test business placeholders
    is_placeholder, pattern = detect_placeholder_patterns("company name")
    result.assert_true(is_placeholder, "Detect 'company name' as business placeholder")
    result.assert_equal(pattern, "business_placeholder", "Correct pattern for business term")

    is_placeholder, pattern = detect_placeholder_patterns("project title here")
    result.assert_true(is_placeholder, "Detect 'project title here' as placeholder")

    # Test generic placeholders
    is_placeholder, pattern = detect_placeholder_patterns("XXX")
    result.assert_true(is_placeholder, "Detect 'XXX' as generic placeholder")

    is_placeholder, pattern = detect_placeholder_patterns("TBD")
    result.assert_true(is_placeholder, "Detect 'TBD' as generic placeholder")

    is_placeholder, pattern = detect_placeholder_patterns("pending")
    result.assert_true(is_placeholder, "Detect 'pending' as generic placeholder")

    # Test empty/whitespace
    is_placeholder, pattern = detect_placeholder_patterns("")
    result.assert_true(is_placeholder, "Detect empty string as placeholder")
    result.assert_equal(pattern, "empty", "Correct pattern for empty")

    is_placeholder, pattern = detect_placeholder_patterns("   ")
    result.assert_true(is_placeholder, "Detect whitespace as placeholder")

    # Test actual content (should NOT be placeholders)
    is_placeholder, pattern = detect_placeholder_patterns("This is a complete sentence with actual content.")
    result.assert_false(is_placeholder, "Regular content not detected as placeholder")
    result.assert_equal(pattern, "content", "Correct pattern for content")

    is_placeholder, pattern = detect_placeholder_patterns("The quarterly revenue exceeded expectations.")
    result.assert_false(is_placeholder, "Business content not detected as placeholder")

    return result.summary()


async def test_has_markdown_formatting():
    """Test markdown formatting detection"""
    print("\n[TEST] Markdown Formatting Detection")
    result = TestResult()

    # Test various markdown formats
    result.assert_true(
        has_markdown_formatting("**bold text**"),
        "Detect bold formatting"
    )

    result.assert_true(
        has_markdown_formatting("*italic text*"),
        "Detect italic formatting"
    )

    result.assert_true(
        has_markdown_formatting("`code text`"),
        "Detect code formatting"
    )

    result.assert_true(
        has_markdown_formatting("~~strikethrough~~"),
        "Detect strikethrough formatting"
    )

    result.assert_true(
        has_markdown_formatting("__underline__"),
        "Detect underline formatting"
    )

    result.assert_true(
        has_markdown_formatting("Text with\nline break"),
        "Detect line break"
    )

    result.assert_true(
        has_markdown_formatting("**bold** and *italic*"),
        "Detect mixed formatting"
    )

    # Test plain text (should be False)
    result.assert_false(
        has_markdown_formatting("Plain text without formatting"),
        "Plain text has no formatting"
    )

    result.assert_false(
        has_markdown_formatting("Just regular words"),
        "Regular text has no formatting"
    )

    return result.summary()


async def test_is_likely_placeholder_context():
    """Test placeholder context detection"""
    print("\n[TEST] Placeholder Context Detection")
    result = TestResult()

    # Test standalone words (likely placeholders)
    result.assert_true(
        is_likely_placeholder_context("name", "name"),
        "Standalone word is placeholder context"
    )

    # Test form field patterns
    result.assert_true(
        is_likely_placeholder_context("Name: ___", "Name"),
        "Form field is placeholder context"
    )

    result.assert_true(
        is_likely_placeholder_context("Date: ---", "Date"),
        "Form field with dashes is placeholder context"
    )

    # Test surrounded by placeholder indicators
    result.assert_true(
        is_likely_placeholder_context("{{name}}", "name"),
        "Braced word is placeholder context"
    )

    result.assert_true(
        is_likely_placeholder_context("[project name]", "project name"),
        "Bracketed phrase is placeholder context"
    )

    # Test instruction phrases
    result.assert_true(
        is_likely_placeholder_context("insert data here", "data"),
        "Instruction phrase is placeholder context"
    )

    result.assert_true(
        is_likely_placeholder_context("add your name here", "name"),
        "Instruction with placeholder word is placeholder context"
    )

    # Test content text (should NOT be placeholder context)
    result.assert_false(
        is_likely_placeholder_context(
            "The project name should be descriptive and clear.",
            "name"
        ),
        "Word in content sentence is NOT placeholder context"
    )

    result.assert_false(
        is_likely_placeholder_context(
            "Please review the customer's data before proceeding.",
            "data"
        ),
        "Word in instruction sentence is NOT placeholder context"
    )

    result.assert_false(
        is_likely_placeholder_context(
            "The date for the meeting has been set.",
            "date"
        ),
        "Word in complete sentence is NOT placeholder context"
    )

    return result.summary()


async def test_analyze_replacement_safety():
    """Test replacement safety analysis"""
    print("\n[TEST] Replacement Safety Analysis")
    result = TestResult()

    # Test safe placeholder matches only
    safe_matches = [
        {"type": "paragraph", "index": 0, "content": "Name: ___"},
        {"type": "paragraph", "index": 1, "content": "Date: ___"}
    ]

    analysis = analyze_replacement_safety("___", safe_matches)
    result.assert_equal(analysis["safety_level"], "low_risk", "Safe matches = low risk")
    result.assert_equal(analysis["safe_matches"], 2, "Correct safe match count")
    result.assert_equal(analysis["unsafe_matches"], 0, "No unsafe matches")

    # Test unsafe content matches
    unsafe_matches = [
        {"type": "paragraph", "index": 0, "content": "The name of the project is important."},
        {"type": "paragraph", "index": 1, "content": "Please update the name field."},
        {"type": "paragraph", "index": 2, "content": "The customer name should be verified."}
    ]

    analysis = analyze_replacement_safety("name", unsafe_matches)
    result.assert_equal(analysis["safety_level"], "high_risk", "Content matches = high risk")
    result.assert_equal(analysis["unsafe_matches"], 3, "Correct unsafe match count")

    # Test mixed safe and unsafe matches
    mixed_matches = [
        {"type": "paragraph", "index": 0, "content": "Name: placeholder"},  # Safe
        {"type": "paragraph", "index": 1, "content": "The name should be clear"},  # Unsafe
        {"type": "paragraph", "index": 2, "content": "Company Name: ___"},  # Safe
        {"type": "paragraph", "index": 3, "content": "Update the project name"}  # Unsafe
    ]

    analysis = analyze_replacement_safety("name", mixed_matches)
    result.assert_equal(analysis["safety_level"], "high_risk", "More unsafe = high risk")
    result.assert_true(analysis["unsafe_matches"] > analysis["safe_matches"], "More unsafe than safe")
    result.assert_true(len(analysis["guidance"]) > 0, "Provides guidance for mixed matches")
    result.assert_true(len(analysis["alternatives"]) > 0, "Provides alternatives")

    return result.summary()


async def run_unit_tests():
    """Run all unit tests"""
    print("\n" + "="*70)
    print("  UNIT TESTS - Doc Maker Core Functions")
    print("="*70)

    all_results = []

    # Run each test suite
    all_results.append(await test_detect_placeholder_patterns())
    all_results.append(await test_has_markdown_formatting())
    all_results.append(await test_is_likely_placeholder_context())
    all_results.append(await test_analyze_replacement_safety())

    # Calculate totals
    total_passed = sum(r['passed'] for r in all_results)
    total_failed = sum(r['failed'] for r in all_results)
    total_tests = total_passed + total_failed

    # Print summary
    print("\n" + "="*70)
    print("  UNIT TEST SUMMARY")
    print("="*70)
    print(f"\nTotal Tests Run: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")

    if total_failed == 0:
        print("\n[SUCCESS] ALL UNIT TESTS PASSED!")
    else:
        print(f"\n[FAILED] {total_failed} UNIT TEST(S) FAILED")

    return {
        'passed': total_passed,
        'failed': total_failed,
        'total': total_tests
    }


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(run_unit_tests())
    sys.exit(0 if result['failed'] == 0 else 1)
