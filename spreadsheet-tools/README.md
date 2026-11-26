# Spreadsheet Tools Integration

Tools for working with spreadsheet files, including conversion to JSON format with automatic header sanitization and type inference.

## Features

### Actions
- **Convert Spreadsheet to JSON** - Converts Excel (.xlsx/.xls) and CSV files to JSON format with automatic data type detection and header sanitization

## Setup

### Installation
```bash
pip install -r requirements.txt
```

### Required Dependencies
- `openpyxl` - For reading Excel .xlsx files
- `xlrd` - For reading Excel .xls files
- `autohive_integrations_sdk` - Autohive integration framework

## Usage Examples

Run this fragment inside an async function. `integration` must be the registered `spreadsheet_tools` instance from `spreadsheet_tools.py`; import `ResultType` from `autohive_integrations_sdk`. Your caller must supply an open `ExecutionContext` named `context`, managed with `async with ExecutionContext() as context`; no authentication is needed.

`execute_action` returns an `IntegrationResult`. Check `ResultType.ACTION` before reading `result.result.data`; handle other result types as failures. See the [SDK calling patterns](https://github.com/autohive-ai/integrations-sdk/blob/release/2.1.0/docs/manual/patterns.md). This example doesn't change the SDK pin in [requirements.txt](requirements.txt).

### Convert Spreadsheet to JSON

```python
import base64

# Use actual base64 file content, not a placeholder string.
csv_bytes = b"Name,Age,Email\nJohn Doe,30,john@example.com\nJane Smith,25,jane@example.com\n"
result = await integration.execute_action(
    "convert_to_json",
    {
        "file": {
            "content": base64.b64encode(csv_bytes).decode("ascii"),
            "name": "sales_data.csv",
            "contentType": "text/csv",
        }
    },
    context,
)

assert result.type == ResultType.ACTION, result.result
# The action payload contains a JSON file with converted data.
json_file = result.result.data["file"]
print(f"Converted file: {json_file['name']}")
print(f"Content type: {json_file['contentType']}")
```

## Features in Detail

### Supported File Formats
- **Excel .xlsx** - Modern Excel format (Office 2007+)
- **Excel .xls** - Legacy Excel format (Office 97-2003)
- **CSV** - Comma-separated values with UTF-8/BOM support

### Automatic Header Sanitization
The integration automatically sanitizes column headers to create valid JSON property names:
- Removes/replaces invalid characters with underscores
- Ensures headers don't start with numbers (prefixes with "col_")
- Handles duplicate headers by adding numeric suffixes
- Removes consecutive and trailing underscores
- Provides default names for empty headers

**Examples:**
- `"First Name"` → `"First_Name"`
- `"2023 Sales"` → `"col_2023_Sales"`
- `"Email@Address"` → `"Email_Address"`
- Duplicate `"Amount"` columns → `"Amount"`, `"Amount_1"`

### Type Inference
Automatically converts cell values to appropriate JSON types:
- Numeric strings → numbers (integers or floats)
- Empty cells → `null`
- Boolean values preserved
- Text values remain as strings

### Output Format
The converted JSON is returned as an array of objects, where:
- Each object represents a row from the spreadsheet
- Object properties correspond to sanitized column headers
- Values are properly typed (strings, numbers, booleans, or null)

**Example Input (CSV):**
```csv
Name,Age,Email
John Doe,30,john@example.com
Jane Smith,25,jane@example.com
```

**Example Output (JSON):**
```json
[
  {
    "Name": "John Doe",
    "Age": 30,
    "Email": "john@example.com"
  },
  {
    "Name": "Jane Smith",
    "Age": 25,
    "Email": "jane@example.com"
  }
]
```

## API Reference

### Actions

#### `convert_to_json`
Converts a spreadsheet file to JSON format with automatic header sanitization and type conversion.

**Input:**
- `file` (required): File object containing:
  - `content` (required): Base64-encoded file content
  - `name` (required): Name of the file (with extension)
  - `contentType` (required): MIME type of the file

**Output:**
- `file`: JSON file object containing:
  - `content`: Base64-encoded JSON content
  - `name`: Generated filename with .json extension
  - `contentType`: "application/json"

**Supported Content Types:**
- `text/csv`
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (.xlsx)
- `application/vnd.ms-excel` (.xls)

## Error Handling

The integration includes comprehensive error handling:
- Invalid or corrupted files return descriptive error messages
- Unsupported file formats provide guidance on supported types
- Empty files are detected and reported
- Base64 decoding errors are caught and explained
- File type auto-detection fallback for ambiguous formats

## Testing

Install HiveUp 2.5.4 from a Tooling local build as described in the root [contribution guide](../CONTRIBUTING.md). HiveUp isn't published to PyPI and isolates each integration's existing requirements. From the repository root, run:

```bash
hiveup test spreadsheet-tools
```

HiveUp discovers `tests/test_*_unit.py`. This directory only has the legacy `tests/test_spreadsheet_tools.py`, so the command reports a skip rather than running that suite. A skip isn't a passing test result. Don't use an ambiguous `pytest tests/` command as evidence that these tests ran; see the root guide for test discovery and isolated environments.

## Development

### Project Structure
```
spreadsheet-tools/
├── config.json          # Integration configuration
├── requirements.txt     # Python dependencies  
├── spreadsheet_tools.py # Main integration code
├── icon.png            # Integration icon
├── README.md           # This file
└── tests/              # Test suite
```

### Adding New Features
1. Update `config.json` with new action definitions
2. Add implementation in `spreadsheet_tools.py` with matching decorators
3. Add corresponding tests in `tests/`
4. Update this documentation

## Troubleshooting

### Common Issues

1. **File Format Not Recognized**
   - Ensure the file extension matches the actual format (.xlsx, .xls, or .csv)
   - Verify the contentType is correct for the file format
   - The integration will attempt auto-detection if format is ambiguous

2. **Invalid Base64 Content**
   - Verify the file content is properly base64-encoded
   - Check that the entire file content is included without truncation

3. **Empty or Invalid Spreadsheet**
   - Ensure the file contains at least a header row
   - Verify the file is not corrupted
   - Check that the spreadsheet has data in the first sheet (for Excel files)

4. **Special Characters in Headers**
   - All headers are automatically sanitized to valid JSON property names
   - Check the output to see how headers were transformed
   - Original header information is preserved through sanitization rules

### Debug Tips
- The integration handles UTF-8 and UTF-8 BOM encoding for CSV files
- Excel files are read with `data_only=True` to get calculated values instead of formulas
- Type conversion attempts numeric parsing for string values
- Duplicate headers receive automatic suffixes (_1, _2, etc.)

## Version History

- **1.0.0** - Initial release with CSV and Excel conversion support
