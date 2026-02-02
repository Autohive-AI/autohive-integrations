"""
Comprehensive Test Suite for Spreadsheet Tools Integration

Tests the convert_to_json action with various scenarios:
- Valid Excel files (.xlsx, .xls)
- Valid CSV files
- Files with special headers (duplicates, invalid characters)
- Empty files
- Invalid/malformed files
- Error handling

Uses pytest for test organization and asyncio for async execution.
"""
import asyncio
import pytest
import json
import base64
import io
from context import spreadsheet_tools
from autohive_integrations_sdk import ExecutionContext


def create_csv_file(content: str) -> bytes:
    """Helper to create CSV file bytes"""
    return content.encode('utf-8')


def create_excel_file_simple(data: list, headers: list) -> bytes:
    """Helper to create a simple Excel file using openpyxl"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    
    # Write headers
    ws.append(headers)
    
    # Write data rows
    for row in data:
        ws.append(row)
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()


def encode_file(file_bytes: bytes) -> str:
    """Helper to base64 encode file content"""
    return base64.b64encode(file_bytes).decode('utf-8')


class TestConvertToJson:
    """Test suite for convert_to_json action"""

    @pytest.mark.asyncio
    async def test_simple_csv_conversion(self):
        """Test converting a simple CSV file to JSON"""
        csv_content = "Name,Age,City\nJohn,30,New York\nJane,25,Los Angeles\nBob,35,Chicago"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "test.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            assert "file" in result
            assert result["file"]["name"] == "test.json"
            assert result["file"]["contentType"] == "application/json"
            
            # Decode and verify JSON content
            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            assert len(json_data) == 3
            assert json_data[0]["Name"] == "John"
            assert json_data[0]["Age"] == 30
            assert json_data[0]["City"] == "New York"
            assert json_data[1]["Name"] == "Jane"
            assert json_data[2]["Name"] == "Bob"

    @pytest.mark.asyncio
    async def test_excel_conversion(self):
        """Test converting an Excel file to JSON"""
        data = [
            ["Alice", 28, "Seattle"],
            ["Charlie", 32, "Boston"],
            ["Diana", 29, "Austin"]
        ]
        headers = ["Name", "Age", "City"]
        file_bytes = create_excel_file_simple(data, headers)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "employees.xlsx",
                "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            assert "file" in result
            assert result["file"]["name"] == "employees.json"
            
            # Decode and verify JSON content
            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            assert len(json_data) == 3
            assert json_data[0]["Name"] == "Alice"
            assert json_data[1]["Name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_headers_with_special_characters(self):
        """Test sanitization of headers with special characters"""
        csv_content = "First Name,Last-Name,Age (years),City/State,Email@Address\nJohn,Doe,30,NY/NY,john@test.com"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "test_special.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            # Check sanitized headers
            assert "First_Name" in json_data[0]
            assert "Last_Name" in json_data[0]
            assert "Age_years" in json_data[0]
            assert "City_State" in json_data[0]
            assert "Email_Address" in json_data[0]

    @pytest.mark.asyncio
    async def test_duplicate_headers(self):
        """Test handling of duplicate header names"""
        csv_content = "Name,Age,Name,City,Name\nJohn,30,Doe,NYC,Jr"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "duplicates.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            # Check deduplicated headers
            keys = list(json_data[0].keys())
            assert "Name" in keys
            assert "Name_1" in keys
            assert "Name_2" in keys
            assert json_data[0]["Name"] == "John"
            assert json_data[0]["Name_1"] == "Doe"
            assert json_data[0]["Name_2"] == "Jr"

    @pytest.mark.asyncio
    async def test_empty_headers(self):
        """Test handling of empty/missing header names"""
        csv_content = ",Age,,City\nJohn,30,data,NYC"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "empty_headers.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            # Empty headers should be replaced with "column"
            keys = list(json_data[0].keys())
            assert "column" in keys or "column_1" in keys

    @pytest.mark.asyncio
    async def test_numeric_headers(self):
        """Test headers that start with numbers"""
        csv_content = "1Name,2Age,3City\nJohn,30,NYC"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "numeric.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            # Headers starting with numbers should be prefixed
            keys = list(json_data[0].keys())
            assert "col_1Name" in keys
            assert "col_2Age" in keys
            assert "col_3City" in keys

    @pytest.mark.asyncio
    async def test_null_values(self):
        """Test handling of null/empty values in data"""
        csv_content = "Name,Age,City\nJohn,30,\nJane,,Los Angeles\n,25,Chicago"
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "nulls.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            # Empty values should be None in JSON
            assert json_data[0]["City"] == "" or json_data[0]["City"] is None
            assert json_data[1]["Age"] is None or json_data[1]["Age"] == ""
            assert json_data[2]["Name"] is None or json_data[2]["Name"] == ""

    @pytest.mark.asyncio
    async def test_multiple_rows(self):
        """Test conversion with many rows"""
        rows = ["Name,Score"]
        for i in range(100):
            rows.append(f"Person{i},{i * 10}")
        csv_content = "\n".join(rows)
        file_bytes = create_csv_file(csv_content)
        
        inputs = {
            "file": {
                "content": encode_file(file_bytes),
                "name": "large.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)

            json_content = base64.b64decode(result["file"]["content"]).decode('utf-8')
            json_data = json.loads(json_content)
            
            assert len(json_data) == 100
            assert json_data[0]["Name"] == "Person0"
            assert json_data[99]["Name"] == "Person99"
            assert json_data[99]["Score"] == 990

    @pytest.mark.asyncio
    async def test_invalid_file_content(self):
        """Test error handling for invalid file content"""
        invalid_content = b"This is not a valid spreadsheet file"
        
        inputs = {
            "file": {
                "content": encode_file(invalid_content),
                "name": "invalid.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            with pytest.raises(ValueError) as exc_info:
                await spreadsheet_tools.execute_action("convert_to_json", inputs, context)
            
            assert "Failed to parse" in str(exc_info.value) or "Unable to parse" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_base64_encoding(self):
        """Test error handling for invalid base64 content"""
        inputs = {
            "file": {
                "content": "not-valid-base64!!!",
                "name": "test.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            with pytest.raises(ValueError) as exc_info:
                await spreadsheet_tools.execute_action("convert_to_json", inputs, context)
            
            assert "Failed to decode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_file(self):
        """Test error handling when file is missing"""
        inputs = {}

        async with ExecutionContext() as context:
            with pytest.raises(ValueError) as exc_info:
                await spreadsheet_tools.execute_action("convert_to_json", inputs, context)
            
            assert "File is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_content(self):
        """Test error handling when file content is missing"""
        inputs = {
            "file": {
                "content": "",
                "name": "test.csv",
                "contentType": "text/csv"
            }
        }

        async with ExecutionContext() as context:
            with pytest.raises(ValueError) as exc_info:
                await spreadsheet_tools.execute_action("convert_to_json", inputs, context)
            
            assert "content is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_output_filename_generation(self):
        """Test that output filename is correctly generated"""
        csv_content = "A,B\n1,2"
        file_bytes = create_csv_file(csv_content)
        
        test_cases = [
            ("data.csv", "data.json"),
            ("report.xlsx", "report.json"),
            ("file.with.dots.csv", "file.with.dots.json"),
            ("noextension", "noextension.json")
        ]
        
        for input_name, expected_name in test_cases:
            inputs = {
                "file": {
                    "content": encode_file(file_bytes),
                    "name": input_name,
                    "contentType": "text/csv"
                }
            }

            async with ExecutionContext() as context:
                result = await spreadsheet_tools.execute_action("convert_to_json", inputs, context)
                assert result["file"]["name"] == expected_name


# Manual test runner (alternative to pytest)
async def main():
    """
    Run all tests manually without pytest.
    This provides a simple way to run tests without pytest infrastructure.
    """
    print("=" * 60)
    print("Spreadsheet Tools Integration Test Suite")
    print("=" * 60)

    tests = TestConvertToJson()
    
    test_methods = [
        ("Simple CSV Conversion", tests.test_simple_csv_conversion),
        ("Excel Conversion", tests.test_excel_conversion),
        ("Special Characters in Headers", tests.test_headers_with_special_characters),
        ("Duplicate Headers", tests.test_duplicate_headers),
        ("Empty Headers", tests.test_empty_headers),
        ("Numeric Headers", tests.test_numeric_headers),
        ("Null Values", tests.test_null_values),
        ("Multiple Rows", tests.test_multiple_rows),
        ("Invalid File Content", tests.test_invalid_file_content),
        ("Invalid Base64 Encoding", tests.test_invalid_base64_encoding),
        ("Missing File", tests.test_missing_file),
        ("Missing Content", tests.test_missing_content),
        ("Output Filename Generation", tests.test_output_filename_generation)
    ]
    
    passed = 0
    failed = 0
    
    for idx, (name, test_func) in enumerate(test_methods, 1):
        print(f"\n[{idx}/{len(test_methods)}] Testing: {name}...")
        try:
            await test_func()
            print(f"✓ {name} passed")
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {str(e)}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Suite Complete: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
