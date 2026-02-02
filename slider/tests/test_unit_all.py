"""
Comprehensive unit tests for all slide_maker helper functions.
Run this file to verify all functionality is working correctly.

Usage: python test_unit_all.py
"""

import sys
import os

# Change to parent directory to import slide_maker
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(parent_dir)
sys.path.insert(0, parent_dir)

# Now import
try:
    from slide_maker import (
        detect_placeholders_with_metadata,
        get_font_path,
        calculate_best_fit_font_size,
        has_markdown_formatting
    )
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Parent directory: {parent_dir}")
    print(f"Files in parent: {os.listdir(parent_dir)[:10]}")
    sys.exit(1)


class TestRunner:
    """Simple test runner with clear pass/fail output"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name, condition, details=""):
        """Record test result"""
        self.tests.append({
            'name': name,
            'passed': condition,
            'details': details
        })

        if condition:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}")
            if details:
                print(f"         {details}")

    def summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"\nTotal tests: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Pass rate: {pass_rate:.1f}%")

        if self.failed > 0:
            print("\n" + "=" * 70)
            print("FAILED TESTS:")
            print("=" * 70)
            for test in self.tests:
                if not test['passed']:
                    print(f"  - {test['name']}")
                    if test['details']:
                        print(f"    {test['details']}")

        print("\n" + "=" * 70)
        if self.failed == 0:
            print("ALL TESTS PASSED!")
        else:
            print(f"SOME TESTS FAILED - Review failures above")
        print("=" * 70)

        return self.failed == 0


def test_placeholder_detection():
    """Test placeholder detection with various formats"""
    print("\n" + "=" * 70)
    print("PLACEHOLDER DETECTION TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test 1: Simple brackets
    placeholders, _ = detect_placeholders_with_metadata("[Company Name]")
    runner.test(
        "Detects simple bracket placeholder",
        placeholders == ["[Company Name]"]
    )

    # Test 2: Curly braces
    placeholders, _ = detect_placeholders_with_metadata("{Company}")
    runner.test(
        "Detects curly brace placeholder",
        placeholders == ["{Company}"]
    )

    # Test 3: Double curly
    placeholders, _ = detect_placeholders_with_metadata("{{Date}}")
    runner.test(
        "Detects double curly placeholder",
        placeholders == ["{{Date}}"]
    )

    # Test 4: Multiple placeholders
    placeholders, _ = detect_placeholders_with_metadata("[A] and [B] and [C]")
    runner.test(
        "Detects multiple placeholders",
        len(placeholders) == 3 and "[A]" in placeholders
    )

    # Test 5: Special characters
    placeholders, _ = detect_placeholders_with_metadata("[$x,xxx]")
    runner.test(
        "Handles special characters (dollar, comma)",
        placeholders == ["[$x,xxx]"]
    )

    # Test 6: No placeholders
    placeholders, _ = detect_placeholders_with_metadata("Plain text with no placeholders")
    runner.test(
        "Returns empty for plain text",
        placeholders == []
    )

    return runner


def test_metadata_parsing():
    """Test metadata extraction from placeholders"""
    print("\n" + "=" * 70)
    print("METADATA PARSING TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test 1: Fontsize extraction
    _, metadata = detect_placeholders_with_metadata("[Title, Fontsize=32pt]")
    meta = metadata.get("[Title, Fontsize=32pt]", {})
    runner.test(
        "Extracts Fontsize=32pt",
        meta.get('fontsize') == '32pt'
    )

    # Test 2: Fontsize without pt
    _, metadata = detect_placeholders_with_metadata("[Title, Fontsize=24]")
    meta = metadata.get("[Title, Fontsize=24]", {})
    runner.test(
        "Extracts Fontsize=24 (no pt suffix)",
        meta.get('fontsize') == '24'
    )

    # Test 3: Bold shorthand
    _, metadata = detect_placeholders_with_metadata("[Title, Bold]")
    meta = metadata.get("[Title, Bold]", {})
    runner.test(
        "Bold shorthand converts to Bold=true",
        meta.get('bold') == 'true'
    )

    # Test 4: Bold negation
    _, metadata = detect_placeholders_with_metadata("[Text, !Bold]")
    meta = metadata.get("[Text, !Bold]", {})
    runner.test(
        "!Bold converts to Bold=false",
        meta.get('bold') == 'false'
    )

    # Test 5: Italic shorthand
    _, metadata = detect_placeholders_with_metadata("[Quote, Italic]")
    meta = metadata.get("[Quote, Italic]", {})
    runner.test(
        "Italic shorthand converts to Italic=true",
        meta.get('italic') == 'true'
    )

    # Test 6: Italic negation
    _, metadata = detect_placeholders_with_metadata("[Text, !Italic]")
    meta = metadata.get("[Text, !Italic]", {})
    runner.test(
        "!Italic converts to Italic=false",
        meta.get('italic') == 'false'
    )

    # Test 7: Underline
    _, metadata = detect_placeholders_with_metadata("[Important, Underline]")
    meta = metadata.get("[Important, Underline]", {})
    runner.test(
        "Underline shorthand works",
        meta.get('underline') == 'true'
    )

    # Test 8: Color extraction
    _, metadata = detect_placeholders_with_metadata("[Title, Color=#FF0000]")
    meta = metadata.get("[Title, Color=#FF0000]", {})
    runner.test(
        "Extracts Color=#FF0000",
        meta.get('color') == '#FF0000'
    )

    # Test 9: Font extraction
    _, metadata = detect_placeholders_with_metadata("[Title, Font=Sofia Pro]")
    meta = metadata.get("[Title, Font=Sofia Pro]", {})
    runner.test(
        "Extracts Font=Sofia Pro",
        meta.get('font') == 'Sofia Pro'
    )

    # Test 10: Complex combined metadata
    _, metadata = detect_placeholders_with_metadata("[Title, Fontsize=32pt, Bold, !Italic, Color=#003366]")
    meta = metadata.get("[Title, Fontsize=32pt, Bold, !Italic, Color=#003366]", {})
    runner.test(
        "Parses complex combined metadata",
        meta.get('fontsize') == '32pt' and
        meta.get('bold') == 'true' and
        meta.get('italic') == 'false' and
        meta.get('color') == '#003366'
    )

    # Test 11: Case insensitivity
    _, metadata = detect_placeholders_with_metadata("[Title, BOLD, FONTSIZE=24PT]")
    meta = metadata.get("[Title, BOLD, FONTSIZE=24PT]", {})
    runner.test(
        "Case-insensitive parsing (BOLD, FONTSIZE)",
        meta.get('bold') == 'true' and meta.get('fontsize') == '24PT'
    )

    # Test 12: No metadata (simple placeholder)
    _, metadata = detect_placeholders_with_metadata("[Company]")
    runner.test(
        "Simple placeholder has no metadata",
        metadata == {}
    )

    return runner


# Markdown stripping test removed - inline code in find_and_replace can't be unit tested
# To test markdown stripping, use integration tests with actual find_and_replace calls


def test_font_path_resolution():
    """Test font path resolution"""
    print("\n" + "=" * 70)
    print("FONT PATH RESOLUTION TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test bundled fonts
    bundled_fonts = ['Calibri', 'Arial', 'Times New Roman', 'Courier New']

    for font in bundled_fonts:
        path = get_font_path(font)
        runner.test(
            f"Resolves bundled font: {font}",
            path is not None and os.path.exists(path) if path else False,
            f"Path: {path}" if path else "Not found"
        )

    # Test bold variant
    path = get_font_path('Calibri Bold')
    runner.test(
        "Resolves Calibri Bold variant",
        path is not None and 'Bold' in path if path else False
    )

    # Test case insensitivity
    path = get_font_path('CALIBRI')
    runner.test(
        "Case-insensitive font resolution (CALIBRI)",
        path is not None and 'Calibri' in path if path else False
    )

    # Test Google Fonts alternative (auto-downloads or uses cached)
    path = get_font_path('Sofia Pro Light')
    runner.test(
        "Handles Google Fonts alternative (Sofia Pro -> Poppins)",
        path is not None,
        f"Downloaded: {os.path.basename(path)}" if path else "Download failed (check network)"
    )

    # Test nonexistent font
    path = get_font_path('NonexistentFont12345')
    runner.test(
        "Returns None for nonexistent font",
        path is None
    )

    return runner


def test_markdown_detection():
    """Test has_markdown_formatting function"""
    print("\n" + "=" * 70)
    print("MARKDOWN DETECTION TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    test_cases = [
        ("**Bold text**", True),
        ("*Italic text*", True),
        ("`Code text`", True),
        ("~~Strikethrough~~", True),
        ("__Underline__", True),
        ("Plain text", False),
        ("Text with no markdown", False),
        ("", False),
        ("**Bold** and *italic*", True),
    ]

    for text, expected in test_cases:
        result = has_markdown_formatting(text)
        runner.test(
            f"Detects markdown in '{text[:30]}': {expected}",
            result == expected
        )

    return runner


def test_font_size_calculation():
    """Test font size calculation (basic sanity checks)"""
    print("\n" + "=" * 70)
    print("FONT SIZE CALCULATION TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test 1: Short text in large box should stay at max size
    size = calculate_best_fit_font_size(
        "Hello",
        width_inches=8.0,
        height_inches=2.0,
        max_font_size=24
    )
    runner.test(
        "Short text stays at max size (24pt)",
        size == 24,
        f"Got: {size}pt"
    )

    # Test 2: Long text should scale down
    long_text = "This is a very long piece of text that contains significantly more content " * 5
    size = calculate_best_fit_font_size(
        long_text,
        width_inches=4.0,
        height_inches=1.0,
        max_font_size=18
    )
    runner.test(
        "Long text scales down from 18pt",
        size < 18,
        f"Scaled to: {size}pt"
    )

    # Test 3: Minimum size enforced
    very_long_text = "Text " * 1000
    size = calculate_best_fit_font_size(
        very_long_text,
        width_inches=1.0,
        height_inches=0.5,
        max_font_size=18
    )
    runner.test(
        "Minimum size is 10pt",
        size >= 10,
        f"Got: {size}pt"
    )

    # Test 4: Empty text returns max size
    size = calculate_best_fit_font_size(
        "",
        width_inches=5.0,
        height_inches=2.0,
        max_font_size=20
    )
    runner.test(
        "Empty text returns max size",
        size == 20
    )

    # Test 5: Bullet text gets extra spacing
    bullet_text = "• Point 1\n• Point 2\n• Point 3"
    size_no_bullets = calculate_best_fit_font_size(
        bullet_text,
        width_inches=4.0,
        height_inches=2.0,
        max_font_size=18,
        is_bullets=False
    )
    size_with_bullets = calculate_best_fit_font_size(
        bullet_text,
        width_inches=4.0,
        height_inches=2.0,
        max_font_size=18,
        is_bullets=True
    )
    runner.test(
        "Bullet text gets smaller size (needs more space)",
        size_with_bullets <= size_no_bullets,
        f"No bullets: {size_no_bullets}pt, With bullets: {size_with_bullets}pt"
    )

    return runner


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print("\n" + "=" * 70)
    print("EDGE CASE TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test 1: Placeholder with commas but no metadata
    placeholders, metadata = detect_placeholders_with_metadata("[$x,xxx]")
    runner.test(
        "[$x,xxx] detected as placeholder",
        placeholders == ["[$x,xxx]"]
    )
    runner.test(
        "[$x,xxx] has no metadata",
        metadata == {}
    )

    # Test 2: Email-like placeholder
    placeholders, _ = detect_placeholders_with_metadata("[email@example.com]")
    runner.test(
        "Email-like placeholder detected",
        placeholders == ["[email@example.com]"]
    )

    # Test 3: Date with slashes
    placeholders, _ = detect_placeholders_with_metadata("[Date / 13 October 2025]")
    runner.test(
        "Date with slashes detected",
        placeholders == ["[Date / 13 October 2025]"]
    )

    # Test 4: Mixed bracket types
    placeholders, _ = detect_placeholders_with_metadata("[Bracket] and {Curly}")
    runner.test(
        "Detects mixed bracket types",
        len(placeholders) == 2
    )

    # Test 5: Nested brackets (shouldn't match inner)
    placeholders, _ = detect_placeholders_with_metadata("[[Nested]]")
    runner.test(
        "Handles nested brackets",
        len(placeholders) > 0  # Should detect something
    )

    # Test 6: Very long placeholder
    long_placeholder = f"[{'A' * 200}]"
    placeholders, _ = detect_placeholders_with_metadata(long_placeholder)
    runner.test(
        "Handles very long placeholder",
        len(placeholders) == 1
    )

    # Test 7: Unicode characters
    placeholders, _ = detect_placeholders_with_metadata("[Café]")
    runner.test(
        "Handles unicode in placeholder",
        placeholders == ["[Café]"]
    )

    # Test 8: Multiple metadata with same key (last wins)
    _, metadata = detect_placeholders_with_metadata("[Title, Bold, !Bold]")
    meta = metadata.get("[Title, Bold, !Bold]", {})
    runner.test(
        "Last metadata value wins (!Bold overrides Bold)",
        meta.get('bold') == 'false',
        f"Got: {meta.get('bold')}"
    )

    return runner


def test_metadata_formats():
    """Test various metadata format variations"""
    print("\n" + "=" * 70)
    print("METADATA FORMAT VARIATIONS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test different fontsize formats
    fontsize_tests = [
        ("[T, Fontsize=32pt]", "32pt"),
        ("[T, Fontsize=32]", "32"),
        ("[T, FONTSIZE=24PT]", "24PT"),
        ("[T, fontsize=18]", "18"),
    ]

    for placeholder, expected_value in fontsize_tests:
        _, metadata = detect_placeholders_with_metadata(placeholder)
        meta = metadata.get(placeholder, {})
        runner.test(
            f"Fontsize format: {placeholder}",
            meta.get('fontsize') == expected_value
        )

    # Test explicit vs shorthand
    test_pairs = [
        (("[T, Bold]", 'true'), ("[T, Bold=true]", 'true')),
        (("[T, !Bold]", 'false'), ("[T, Bold=false]", 'false')),
        (("[T, Italic]", 'true'), ("[T, Italic=true]", 'true')),
    ]

    for (p1, v1), (p2, v2) in test_pairs:
        _, meta1 = detect_placeholders_with_metadata(p1)
        _, meta2 = detect_placeholders_with_metadata(p2)

        m1 = meta1.get(p1, {})
        m2 = meta2.get(p2, {})

        # Get the key (bold, italic, etc.)
        key = 'bold' if 'Bold' in p1 else 'italic'

        runner.test(
            f"Shorthand {p1} equivalent to {p2}",
            m1.get(key) == v1 and m2.get(key) == v2
        )

    # Test case variations
    case_tests = [
        ("[T, BOLD]", 'bold', 'true'),
        ("[T, bold]", 'bold', 'true'),
        ("[T, Bold]", 'bold', 'true'),
        ("[T, !ITALIC]", 'italic', 'false'),
        ("[T, !italic]", 'italic', 'false'),
    ]

    for placeholder, key, expected_value in case_tests:
        _, metadata = detect_placeholders_with_metadata(placeholder)
        meta = metadata.get(placeholder, {})
        runner.test(
            f"Case-insensitive: {placeholder}",
            meta.get(key) == expected_value
        )

    return runner


def test_combined_functionality():
    """Test realistic combined scenarios"""
    print("\n" + "=" * 70)
    print("COMBINED FUNCTIONALITY TESTS")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Test 1: Real SOW placeholder
    placeholder = "[Client Company Name, Fontsize=32pt, Bold, Color=#003366, Font=Sofia Pro]"
    placeholders, metadata = detect_placeholders_with_metadata(placeholder)
    meta = metadata.get(placeholder, {})

    runner.test(
        "Real SOW placeholder detected",
        len(placeholders) == 1
    )

    runner.test(
        "All metadata extracted from SOW placeholder",
        meta.get('fontsize') == '32pt' and
        meta.get('bold') == 'true' and
        meta.get('color') == '#003366' and
        meta.get('font') == 'Sofia Pro'
    )

    # Test 2: Multiple placeholders in one text
    text = "Contact [Name | Title] at [email@example.com] or call [Phone]"
    placeholders, _ = detect_placeholders_with_metadata(text)
    runner.test(
        "Detects all placeholders in sentence",
        len(placeholders) == 3
    )

    # Test 3: Complex paragraph with metadata and plain placeholders
    paragraph = "[Title, Bold, Fontsize=24] prepared by [Author] on [Date]"
    placeholders, metadata = detect_placeholders_with_metadata(paragraph)
    runner.test(
        "Mixed metadata and plain placeholders",
        len(placeholders) == 3 and len(metadata) == 1
    )

    # Test 4: Agent's real placeholder formats
    agent_placeholders = [
        "[Problem definition, Bold]",
        "[Proposed Solution, Bold]",
        "[Title Clients Challenge, Font=36pt]",
    ]

    for p in agent_placeholders:
        placeholders, metadata = detect_placeholders_with_metadata(p)
        meta = metadata.get(p, {})
        runner.test(
            f"Agent format: {p}",
            len(placeholders) == 1 and len(meta) > 1
        )

    return runner


def test_font_availability():
    """Test font file availability"""
    print("\n" + "=" * 70)
    print("FONT FILE AVAILABILITY")
    print("=" * 70 + "\n")

    runner = TestRunner()

    # Check fonts directory exists
    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
    runner.test(
        "fonts/ directory exists",
        os.path.exists(fonts_dir)
    )

    # Check key font files exist
    expected_fonts = [
        'Calibri.ttf',
        'Calibri-Bold.ttf',
        'Arial.ttf',
        'Times.ttf',
        'Courier.ttf'
    ]

    for font_file in expected_fonts:
        font_path = os.path.join(fonts_dir, font_file)
        runner.test(
            f"Font file exists: {font_file}",
            os.path.exists(font_path)
        )

    # Check config files exist
    config_files = [
        'font_alternatives.json',
        'google_fonts_downloader.py',
        'README.md'
    ]

    for config_file in config_files:
        config_path = os.path.join(fonts_dir, config_file)
        runner.test(
            f"Config file exists: {config_file}",
            os.path.exists(config_path)
        )

    return runner


def main():
    """Run all tests"""
    print("=" * 70)
    print("SLIDE MAKER COMPREHENSIVE UNIT TESTS")
    print("=" * 70)
    print("\nTesting all helper functions and utilities...")

    all_runners = []

    # Run all test suites
    all_runners.append(test_placeholder_detection())
    all_runners.append(test_metadata_parsing())
    # Markdown stripping test removed - inline code can't be unit tested
    all_runners.append(test_font_path_resolution())
    all_runners.append(test_markdown_detection())
    all_runners.append(test_edge_cases())
    all_runners.append(test_metadata_formats())
    all_runners.append(test_combined_functionality())
    all_runners.append(test_font_availability())

    # Calculate totals
    total_passed = sum(r.passed for r in all_runners)
    total_failed = sum(r.failed for r in all_runners)
    total_tests = total_passed + total_failed
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    # Print overall summary
    print("\n" + "=" * 70)
    print("OVERALL TEST SUMMARY")
    print("=" * 70)
    print(f"\nTotal test suites: {len(all_runners)}")
    print(f"Total tests run: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Pass rate: {pass_rate:.1f}%")

    if total_failed == 0:
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED - SLIDE MAKER IS WORKING CORRECTLY!")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print(f"{total_failed} TEST(S) FAILED - REVIEW FAILURES ABOVE")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
