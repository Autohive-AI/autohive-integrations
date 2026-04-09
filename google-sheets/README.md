# Google Sheets Integration for Autohive

Connects Autohive to the Google Sheets and Drive APIs to list spreadsheets, read and write ranges, append rows, format cells, freeze panes, run batch updates, and duplicate spreadsheets.

## Description

This integration provides safe, deterministic read/write operations for Google Sheets along with useful formatting and file utilities. It supports:
- Listing spreadsheets you can access (with filtering)
- Getting spreadsheet metadata and sheet tabs
- Reading and writing A1 ranges
- Appending rows
- Formatting a grid range
- Freezing header rows/columns
- Batch update requests
- Duplicating a spreadsheet via Google Drive

## Setup & Authentication

Authentication uses Google OAuth (Platform auth) with the following scopes:
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive.metadata.readonly`
- `https://www.googleapis.com/auth/drive.file`

No additional configuration fields are required beyond the OAuth connection.

## Actions

### `sheets_list_spreadsheets`
- Description: Find accessible spreadsheets. Supports filtering by name and owner.
- Inputs:
  - `name_contains` (string, optional)
  - `owner` (string, optional; email or `me`)
  - `pageSize` (integer, optional)
  - `pageToken` (string, optional)
- Outputs:
  - `files` (array[object])
  - `nextPageToken` (string, optional)
  - `result` (boolean), `error` (string)

### `sheets_get_spreadsheet`
- Description: Fetch spreadsheet properties, sheets, and named ranges.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `include_grid_data` (boolean, optional)
- Outputs: `spreadsheet` (object), `result` (boolean), `error` (string)

### `sheets_list_sheets`
- Description: List sheet tabs with basic properties.
- Inputs: `spreadsheet_id` (string, required)
- Outputs: `sheets` (array[object]), `result` (boolean), `error` (string)

### `sheets_read_range`
- Description: Read values from an A1 or named range.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `range` (string, required)
  - `valueRenderOption` (`FORMATTED_VALUE` | `UNFORMATTED_VALUE` | `FORMULA`, optional)
  - `dateTimeRenderOption` (`SERIAL_NUMBER` | `FORMATTED_STRING`, optional)
- Outputs: `range` (string), `values` (array[array]), `result` (boolean), `error` (string)

### `sheets_write_range`
- Description: Overwrite cells in a given A1 range deterministically.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `range` (string, required)
  - `values` (array[array], required)
  - `inputOption` (`RAW` | `USER_ENTERED`, optional)
  - `dry_run` (boolean, optional)
- Outputs: `updatedRange`, `updatedRows`, `updatedColumns`, `updatedCells`, `dryRun`, `result`, `error`

### `sheets_append_rows`
- Description: Append rows to a table or range.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `range` (string, required; A1 of header row or sheet name)
  - `rows` (array[array], required)
  - `inputOption` (`RAW` | `USER_ENTERED`, optional)
- Outputs: `updates` (object), `result` (boolean), `error` (string)

### `sheets_format_range`
- Description: Apply font, color, and number formatting to a grid range.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `sheetId` (integer, required)
  - `gridRange` (object, required): `startRowIndex`, `endRowIndex`, `startColumnIndex`, `endColumnIndex`
  - `style` (object, required): `userEnteredFormat` fields per Sheets API
- Outputs: `replies` (array[object]), `result` (boolean), `error` (string)

### `sheets_freeze`
- Description: Freeze header rows/columns.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `sheetId` (integer, required)
  - `rows` (integer, optional)
  - `columns` (integer, optional)
- Outputs: `replies` (array[object]), `result` (boolean), `error` (string)

### `sheets_batch_update`
- Description: Run a Sheets `batchUpdate` with one or more requests.
- Inputs:
  - `spreadsheet_id` (string, required)
  - `requests` (array[object], required)
  - `dry_run` (boolean, optional)
- Outputs: `replies` (array[object]), `dryRun` (boolean), `result` (boolean), `error` (string)

### `sheets_duplicate_spreadsheet`
- Description: Duplicate an entire spreadsheet file using Drive API.
- Inputs:
  - `source_spreadsheet_id` (string, required)
  - `new_title` (string, required)
  - `parent_folder_id` (string, optional)
- Outputs: `file_metadata` (object), `result` (boolean), `error` (string)

## Requirements

- `pyyaml`
- `autohive-integrations-sdk`
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`

## Usage Examples

### Read a range
```json
{
  "spreadsheet_id": "1abcDEFghiJKLmnOPQrsTuvWXyz12345",
  "range": "Sheet1!A1:C10",
  "valueRenderOption": "FORMATTED_VALUE"
}
```

### Write a range
```json
{
  "spreadsheet_id": "1abcDEFghiJKLmnOPQrsTuvWXyz12345",
  "range": "Sheet1!A1:B2",
  "values": [["Header 1","Header 2"],["v1","v2"]],
  "inputOption": "USER_ENTERED"
}
```

### Append rows
```json
{
  "spreadsheet_id": "1abcDEFghiJKLmnOPQrsTuvWXyz12345",
  "range": "Sheet1!A1",
  "rows": [["row1-col1","row1-col2"],["row2-col1","row2-col2"]]
}
```

### Duplicate a spreadsheet
```json
{
  "source_spreadsheet_id": "1abcDEFghiJKLmnOPQrsTuvWXyz12345",
  "new_title": "My Duplicated Sheet"
}
```

## Testing

To run the tests:

1. Navigate to the integration's directory: `cd google-sheets`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run the tests: `python tests/test_google_sheets.py`

