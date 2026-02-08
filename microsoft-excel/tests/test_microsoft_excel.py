# Testbed for Microsoft Excel integration
import asyncio
from context import microsoft_excel
from autohive_integrations_sdk import ExecutionContext


async def test_list_workbooks():
    """Test listing Excel workbooks in OneDrive/SharePoint."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_list_workbooks", inputs, context)
            print(f"List Workbooks Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'workbooks' in result, "Response missing 'workbooks' field"
            if result.get('workbooks'):
                print(f"  -> Found {len(result['workbooks'])} workbook(s)")
                for wb in result['workbooks'][:5]:
                    print(f"     - {wb.get('name')} (ID: {wb.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_workbooks: {e}")
            return None


async def test_list_workbooks_with_filter():
    """Test listing workbooks with name filter."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "name_contains": "your_filter_here",
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_list_workbooks", inputs, context)
            print(f"List Workbooks (Filtered) Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing list_workbooks with filter: {e}")
            return None


async def test_get_workbook():
    """Test getting workbook metadata including worksheets, tables, and named ranges."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_get_workbook", inputs, context)
            print(f"Get Workbook Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('workbook'):
                print(f"  -> Workbook: {result['workbook'].get('name')}")
            if result.get('worksheets'):
                print(f"  -> Worksheets: {len(result['worksheets'])}")
            if result.get('tables'):
                print(f"  -> Tables: {len(result['tables'])}")
            return result
        except Exception as e:
            print(f"Error testing get_workbook: {e}")
            return None


async def test_list_worksheets():
    """Test listing worksheets in a workbook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_list_worksheets", inputs, context)
            print(f"List Worksheets Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'worksheets' in result, "Response missing 'worksheets' field"
            if result.get('worksheets'):
                print(f"  -> Found {len(result['worksheets'])} worksheet(s)")
                for ws in result['worksheets']:
                    print(f"     - {ws.get('name')} (Position: {ws.get('position')})")
            return result
        except Exception as e:
            print(f"Error testing list_worksheets: {e}")
            return None


async def test_read_range():
    """Test reading cell values from a range."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1",
        "range": "A1:D10"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_read_range", inputs, context)
            print(f"Read Range Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('values'):
                print(f"  -> Rows: {result.get('row_count')}, Columns: {result.get('column_count')}")
                print(f"  -> First row: {result['values'][0] if result['values'] else 'empty'}")
            return result
        except Exception as e:
            print(f"Error testing read_range: {e}")
            return None


async def test_write_range():
    """Test writing values to a cell range."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1",
        "range": "A1:C2",
        "values": [
            ["Name", "Email", "Status"],
            ["Test User", "test@example.com", "Active"]
        ]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_write_range", inputs, context)
            print(f"Write Range Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Updated: {result.get('updated_cells')} cells")
            return result
        except Exception as e:
            print(f"Error testing write_range: {e}")
            return None


async def test_list_tables():
    """Test listing tables in a workbook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_list_tables", inputs, context)
            print(f"List Tables Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'tables' in result, "Response missing 'tables' field"
            if result.get('tables'):
                print(f"  -> Found {len(result['tables'])} table(s)")
                for table in result['tables']:
                    print(f"     - {table.get('name')} (ID: {table.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_tables: {e}")
            return None


async def test_get_table_data():
    """Test getting data from a table."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here",
        "top": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_get_table_data", inputs, context)
            print(f"Get Table Data Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('headers'):
                print(f"  -> Headers: {result['headers']}")
            if result.get('rows'):
                print(f"  -> Rows: {len(result['rows'])} (Total: {result.get('total_rows')})")
            return result
        except Exception as e:
            print(f"Error testing get_table_data: {e}")
            return None


async def test_add_table_row():
    """Test adding rows to a table."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here",
        "rows": [
            ["New Entry", "new@example.com", "Pending"]
        ]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_add_table_row", inputs, context)
            print(f"Add Table Row Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Added {result.get('added_rows')} row(s)")
            return result
        except Exception as e:
            print(f"Error testing add_table_row: {e}")
            return None


async def test_create_worksheet():
    """Test creating a new worksheet."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "name": "NewSheet"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_create_worksheet", inputs, context)
            print(f"Create Worksheet Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('worksheet'):
                print(f"  -> Created: {result['worksheet'].get('name')}")
            return result
        except Exception as e:
            print(f"Error testing create_worksheet: {e}")
            return None


async def test_delete_worksheet():
    """Test deleting a worksheet."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "SheetToDelete"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_delete_worksheet", inputs, context)
            print(f"Delete Worksheet Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Deleted: {result.get('deleted')}")
            return result
        except Exception as e:
            print(f"Error testing delete_worksheet: {e}")
            return None


async def test_create_table():
    """Test creating a table from a range."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1",
        "range": "A1:C5",
        "has_headers": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_create_table", inputs, context)
            print(f"Create Table Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            if result.get('table'):
                print(f"  -> Created: {result['table'].get('name')}")
            return result
        except Exception as e:
            print(f"Error testing create_table: {e}")
            return None


async def test_update_table_row():
    """Test updating a table row."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here",
        "row_index": 0,
        "values": ["Updated Name", "updated@example.com", "Inactive"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_update_table_row", inputs, context)
            print(f"Update Table Row Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing update_table_row: {e}")
            return None


async def test_delete_table_row():
    """Test deleting a table row."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here",
        "row_index": 0
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_delete_table_row", inputs, context)
            print(f"Delete Table Row Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Deleted: {result.get('deleted')}")
            return result
        except Exception as e:
            print(f"Error testing delete_table_row: {e}")
            return None


async def test_get_used_range():
    """Test getting the used range of a worksheet."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_get_used_range", inputs, context)
            print(f"Get Used Range Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Range: {result.get('range')}")
            print(f"  -> Size: {result.get('row_count')} rows x {result.get('column_count')} columns")
            return result
        except Exception as e:
            print(f"Error testing get_used_range: {e}")
            return None


async def test_sort_range():
    """Test sorting a range."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1",
        "range": "A1:C10",
        "sort_fields": [
            {"column_index": 0, "ascending": True}
        ],
        "has_headers": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_sort_range", inputs, context)
            print(f"Sort Range Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Sorted: {result.get('sorted')}")
            return result
        except Exception as e:
            print(f"Error testing sort_range: {e}")
            return None


async def test_apply_filter():
    """Test applying a filter to a table column."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here",
        "column_index": 0,
        "filter_criteria": {
            "filterOn": "Values",
            "values": ["Active"]
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_apply_filter", inputs, context)
            print(f"Apply Filter Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Filtered: {result.get('filtered')}")
            return result
        except Exception as e:
            print(f"Error testing apply_filter: {e}")
            return None


async def test_clear_filter():
    """Test clearing filters from a table."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "table_name": "your_table_name_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_clear_filter", inputs, context)
            print(f"Clear Filter Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Cleared: {result.get('cleared')}")
            return result
        except Exception as e:
            print(f"Error testing clear_filter: {e}")
            return None


async def test_format_range():
    """Test formatting a cell range."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "workbook_id": "your_workbook_id_here",
        "worksheet_name": "Sheet1",
        "range": "A1:D1",
        "format": {
            "font": {
                "bold": True,
                "color": "#FFFFFF"
            },
            "fill": {
                "color": "#4472C4"
            },
            "horizontalAlignment": "Center"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await microsoft_excel.execute_action("excel_format_range", inputs, context)
            print(f"Format Range Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            print(f"  -> Formatted: {result.get('formatted')}")
            return result
        except Exception as e:
            print(f"Error testing format_range: {e}")
            return None


async def main():
    print("Testing Microsoft Excel Integration - 18 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your Microsoft 365 OAuth access token")
    print("  - your_workbook_id_here: Drive item ID of an Excel workbook")
    print("  - your_table_name_here: Name of a table in the workbook")
    print()
    print("TIP: Run list_workbooks first to discover your workbook IDs!")
    print()
    print("=" * 60)
    print()

    # Discovery actions
    print("DISCOVERY ACTIONS")
    print("-" * 60)
    print("1. Testing list_workbooks...")
    await test_list_workbooks()
    print()

    print("2. Testing list_workbooks (with filter)...")
    await test_list_workbooks_with_filter()
    print()

    print("3. Testing get_workbook...")
    await test_get_workbook()
    print()

    print("4. Testing list_worksheets...")
    await test_list_worksheets()
    print()

    print("5. Testing list_tables...")
    await test_list_tables()
    print()

    print("=" * 60)
    print()
    print("READ ACTIONS")
    print("-" * 60)

    print("6. Testing read_range...")
    await test_read_range()
    print()

    print("7. Testing get_table_data...")
    await test_get_table_data()
    print()

    print("8. Testing get_used_range...")
    await test_get_used_range()
    print()

    print("=" * 60)
    print()
    print("WRITE ACTIONS")
    print("-" * 60)

    print("9. Testing write_range...")
    await test_write_range()
    print()

    print("10. Testing add_table_row...")
    await test_add_table_row()
    print()

    print("11. Testing update_table_row...")
    await test_update_table_row()
    print()

    print("12. Testing delete_table_row...")
    await test_delete_table_row()
    print()

    print("=" * 60)
    print()
    print("WORKSHEET/TABLE MANAGEMENT")
    print("-" * 60)

    print("13. Testing create_worksheet...")
    await test_create_worksheet()
    print()

    print("14. Testing delete_worksheet...")
    await test_delete_worksheet()
    print()

    print("15. Testing create_table...")
    await test_create_table()
    print()

    print("=" * 60)
    print()
    print("SORTING & FILTERING")
    print("-" * 60)

    print("16. Testing sort_range...")
    await test_sort_range()
    print()

    print("17. Testing apply_filter...")
    await test_apply_filter()
    print()

    print("18. Testing clear_filter...")
    await test_clear_filter()
    print()

    print("=" * 60)
    print()
    print("FORMATTING")
    print("-" * 60)

    print("19. Testing format_range...")
    await test_format_range()
    print()

    print("=" * 60)
    print("Testing completed - 18 actions total!")
    print("  - 5 discovery actions (list/get workbooks, worksheets, tables)")
    print("  - 3 read actions (read_range, get_table_data, get_used_range)")
    print("  - 4 write actions (write_range, add/update/delete table rows)")
    print("  - 3 management actions (create/delete worksheet, create table)")
    print("  - 3 sort/filter actions (sort_range, apply/clear filter)")
    print("  - 1 formatting action (format_range)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
