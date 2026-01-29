# Microsoft Excel Integration

Read, write, and manipulate Excel workbooks stored in OneDrive for Business or SharePoint via Microsoft Graph API.

## Features

- List and search Excel workbooks in OneDrive/SharePoint
- Read and write cell ranges using A1 notation
- Manage worksheets (create, delete, list)
- Work with Excel tables (create, read, add/update/delete rows)
- Sort and filter data
- Apply formatting (font, fill, alignment, number format)

## Requirements

- Microsoft 365 account with OneDrive for Business or SharePoint
- OAuth 2.0 authentication via Microsoft 365
- Only `.xlsx` files are supported (not `.xls`)

## Authentication

This integration uses platform authentication with Microsoft 365 OAuth 2.0.

Required scopes:
- `Files.Read` - Read access to workbooks
- `Files.ReadWrite` - Read and write access to workbooks
- `offline_access` - Refresh token support

## Actions

### Phase 1 - Basic Features

| Action | Description |
|--------|-------------|
| `excel_list_workbooks` | Find accessible Excel workbooks in OneDrive/SharePoint |
| `excel_get_workbook` | Retrieve workbook properties including worksheets, tables, and named ranges |
| `excel_list_worksheets` | List all worksheet tabs in a workbook |
| `excel_read_range` | Read cell values from a specified range |
| `excel_write_range` | Write values to a specified cell range |
| `excel_list_tables` | List all tables in a workbook or worksheet |
| `excel_get_table_data` | Read all rows from a table including headers |
| `excel_add_table_row` | Append one or more rows to an existing table |
| `excel_create_worksheet` | Add a new worksheet tab |
| `excel_delete_worksheet` | Remove a worksheet |

### Phase 2 - Advanced Features

| Action | Description |
|--------|-------------|
| `excel_create_table` | Convert a range to an Excel table |
| `excel_update_table_row` | Update values in an existing table row |
| `excel_delete_table_row` | Remove a row from a table |
| `excel_sort_range` | Sort a range by specified columns |
| `excel_apply_filter` | Apply filter to a table column |
| `excel_clear_filter` | Clear filters from a table |
| `excel_get_used_range` | Get the range that contains data in a worksheet |
| `excel_format_range` | Apply formatting to a cell range |

## Usage Examples

### List Workbooks
```python
{
    "name_contains": "Sales Report",
    "page_size": 10
}
```

### Read Range
```python
{
    "workbook_id": "01ABC123...",
    "worksheet_name": "Sheet1",
    "range": "A1:D10"
}
```

### Write Range
```python
{
    "workbook_id": "01ABC123...",
    "worksheet_name": "Sheet1",
    "range": "A1:C3",
    "values": [
        ["Name", "Email", "Status"],
        ["John Doe", "john@example.com", "Active"],
        ["Jane Smith", "jane@example.com", "Pending"]
    ]
}
```

### Add Table Rows
```python
{
    "workbook_id": "01ABC123...",
    "table_name": "SalesData",
    "rows": [
        ["2024-01-15", "Product A", 150],
        ["2024-01-16", "Product B", 200]
    ]
}
```

### Format Range
```python
{
    "workbook_id": "01ABC123...",
    "worksheet_name": "Sheet1",
    "range": "A1:D1",
    "format": {
        "font": {
            "bold": true,
            "color": "#FFFFFF",
            "size": 12
        },
        "fill": {
            "color": "#4472C4"
        },
        "horizontalAlignment": "Center"
    }
}
```

## API Reference

This integration uses the [Microsoft Graph Excel API](https://learn.microsoft.com/en-us/graph/api/resources/excel).

### Limitations

- Only works with OneDrive for Business and SharePoint (not consumer OneDrive)
- Only `.xlsx` files are supported
- Large range operations (>5M cells) should be avoided
- Sessions expire after 5-7 minutes of inactivity
