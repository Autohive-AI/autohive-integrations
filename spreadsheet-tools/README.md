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

### Convert Spreadsheet to JSON

```python
# Convert a CSV or Excel file to JSON format
result = await integration.execute_action("convert_to_json", {
    "file": {
        "content": "<base64_encoded_file_content>",
        "name": "sales_data.xlsx",
        "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
})

# The result contains a JSON file with converted data
json_file = result["file"]
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

To run the tests:

1. Navigate to the integration's directory: `cd spreadsheet-tools`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the tests: `python -m pytest tests/` (if tests are available)

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
