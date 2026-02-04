from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any
from urllib.parse import quote

microsoft_excel = Integration.load()

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def encode_path_segment(segment: str) -> str:
    """URL-encode a path segment for use in Graph API URLs."""
    return quote(segment, safe="")


def encode_range_address(address: str) -> str:
    """URL-encode a range address, preserving A1 notation characters."""
    return quote(address, safe=":")


@microsoft_excel.action("excel_list_workbooks")
class ListWorkbooks(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            name_contains = inputs.get("name_contains")
            folder_path = inputs.get("folder_path")
            page_size = inputs.get("page_size", 25)
            page_token = inputs.get("page_token")

            if folder_path:
                encoded_path = encode_path_segment(folder_path)
                url = f"{GRAPH_BASE_URL}/me/drive/root:/{encoded_path}:/children"
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/root/children"

            params = {
                "$top": min(page_size, 100),
                "$select": "id,name,webUrl,lastModifiedDateTime,file,size",
                "$orderby": "lastModifiedDateTime desc",
            }

            if page_token:
                url = page_token
                params = None

            response = await context.fetch(url, method="GET", params=params)

            items = response.get("value", [])

            workbooks = []
            for item in items:
                if item.get("file", {}).get("mimeType") == EXCEL_MIMETYPE:
                    if name_contains and name_contains.lower() not in item.get("name", "").lower():
                        continue
                    workbooks.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "webUrl": item.get("webUrl"),
                        "lastModifiedDateTime": item.get("lastModifiedDateTime"),
                        "size": item.get("size"),
                    })

            result_data = {"workbooks": workbooks, "result": True}
            next_link = response.get("@odata.nextLink")
            if next_link:
                result_data["next_page_token"] = next_link

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "workbooks": [],
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_get_workbook")
class GetWorkbook(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]

            # Get file info
            file_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
            file_data = await context.fetch(file_url, method="GET")

            # Get worksheets (non-fatal: continue with empty list if API call fails)
            worksheets_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
            worksheets = []
            try:
                ws_data = await context.fetch(worksheets_url, method="GET")
                for ws in ws_data.get("value", []):
                    worksheets.append({
                        "id": ws.get("id"),
                        "name": ws.get("name"),
                        "position": ws.get("position"),
                        "visibility": ws.get("visibility"),
                    })
            except Exception:
                # API error handled - return partial data without worksheets
                pass

            # Get tables (non-fatal: continue with empty list if API call fails)
            tables_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables"
            tables = []
            try:
                tables_data = await context.fetch(tables_url, method="GET")
                for table in tables_data.get("value", []):
                    tables.append({
                        "id": table.get("id"),
                        "name": table.get("name"),
                        "showHeaders": table.get("showHeaders"),
                        "showTotals": table.get("showTotals"),
                        "style": table.get("style"),
                    })
            except Exception:
                # API error handled - return partial data without tables
                pass

            # Get named ranges (non-fatal: continue with empty list if API call fails)
            names_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/names"
            named_ranges = []
            try:
                names_data = await context.fetch(names_url, method="GET")
                for name in names_data.get("value", []):
                    named_ranges.append({
                        "name": name.get("name"),
                        "value": name.get("value"),
                        "type": name.get("type"),
                    })
            except Exception:
                # API error handled - return partial data without named ranges
                pass

            return ActionResult(data={
                "workbook": {
                    "id": file_data.get("id"),
                    "name": file_data.get("name"),
                    "webUrl": file_data.get("webUrl"),
                    "lastModifiedDateTime": file_data.get("lastModifiedDateTime"),
                },
                "worksheets": worksheets,
                "tables": tables,
                "named_ranges": named_ranges,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_list_worksheets")
class ListWorksheets(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]

            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
            response = await context.fetch(url, method="GET")

            worksheets = []
            for ws in response.get("value", []):
                worksheets.append({
                    "id": ws.get("id"),
                    "name": ws.get("name"),
                    "position": ws.get("position"),
                    "visibility": ws.get("visibility"),
                })

            return ActionResult(data={"worksheets": worksheets, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "worksheets": [],
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_read_range")
class ReadRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            value_render_option = inputs.get("value_render_option", "FORMATTED_VALUE")

            encoded_ws = encode_path_segment(worksheet_name)
            encoded_range = encode_range_address(range_address)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{encoded_range}')"
            response = await context.fetch(url, method="GET")

            values = response.get("values", [])
            formulas = response.get("formulas", []) if value_render_option == "FORMULA" else []
            number_format = response.get("numberFormat", [])

            row_count = len(values)
            column_count = len(values[0]) if values else 0

            return ActionResult(data={
                "range": response.get("address", range_address),
                "values": values,
                "formulas": formulas,
                "number_format": number_format,
                "row_count": row_count,
                "column_count": column_count,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_write_range")
class WriteRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            values = inputs["values"]

            encoded_ws = encode_path_segment(worksheet_name)
            encoded_range = encode_range_address(range_address)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{encoded_range}')"

            body = {"values": values}
            response = await context.fetch(url, method="PATCH", json=body)

            row_count = len(values)
            column_count = len(values[0]) if values else 0

            return ActionResult(data={
                "updated_range": response.get("address", range_address),
                "updated_rows": row_count,
                "updated_columns": column_count,
                "updated_cells": row_count * column_count,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_list_tables")
class ListTables(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs.get("worksheet_name")

            if worksheet_name:
                encoded_ws = encode_path_segment(worksheet_name)
                url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/tables"
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables"

            response = await context.fetch(url, method="GET")

            tables = []
            for table in response.get("value", []):
                tables.append({
                    "id": table.get("id"),
                    "name": table.get("name"),
                    "showHeaders": table.get("showHeaders"),
                    "showTotals": table.get("showTotals"),
                    "style": table.get("style"),
                })

            return ActionResult(data={"tables": tables, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "tables": [],
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_get_table_data")
class GetTableData(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            select_columns = inputs.get("select_columns")
            top = inputs.get("top")
            skip = inputs.get("skip")
            max_rows = inputs.get("max_rows", 5000)

            encoded_table = encode_path_segment(table_name)

            # Get headers
            header_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/headerRowRange"
            header_data = await context.fetch(header_url, method="GET")
            all_headers = header_data.get("values", [[]])[0]

            # Validate select_columns if specified
            if select_columns:
                missing_cols = [c for c in select_columns if c not in all_headers]
                if missing_cols:
                    return ActionResult(data={
                        "result": False,
                        "error": f"Columns not found: {missing_cols}. Available columns: {all_headers}",
                    }, cost_usd=0.0)

            # Get rows
            rows_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/dataBodyRange"
            rows_data = await context.fetch(rows_url, method="GET")
            all_rows = rows_data.get("values", [])

            # Check max_rows safety limit
            if max_rows and len(all_rows) > max_rows:
                return ActionResult(data={
                    "result": False,
                    "error": f"Table has {len(all_rows)} rows, exceeding max_rows limit of {max_rows}. Use pagination (top/skip) or increase max_rows.",
                }, cost_usd=0.0)

            # Filter columns if specified
            if select_columns:
                col_indices = [all_headers.index(c) for c in select_columns]
                headers_out = [all_headers[i] for i in col_indices]
                rows_out = [[row[i] for i in col_indices if i < len(row)] for row in all_rows]
            else:
                headers_out = all_headers
                rows_out = all_rows

            # Apply pagination (handle 0 values correctly)
            if skip is not None and skip > 0:
                rows_out = rows_out[skip:]
            if top is not None:
                rows_out = rows_out[:top]

            # Convert to row objects
            row_objects = []
            for row in rows_out:
                row_obj = {}
                for i, header in enumerate(headers_out):
                    row_obj[header] = row[i] if i < len(row) else None
                row_objects.append(row_obj)

            return ActionResult(data={
                "headers": headers_out,
                "rows": row_objects,
                "total_rows": len(all_rows),
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_add_table_row")
class AddTableRow(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            rows = inputs["rows"]
            index = inputs.get("index")

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/rows/add"

            body: Dict[str, Any] = {"values": rows}
            if index is not None:
                body["index"] = index

            await context.fetch(url, method="POST", json=body)

            # Get updated table range (non-fatal: return empty string if API call fails)
            range_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/range"
            table_range = ""
            try:
                range_data = await context.fetch(range_url, method="GET")
                table_range = range_data.get("address", "")
            except Exception:
                # API error handled - rows were added, range info is optional
                pass

            return ActionResult(data={
                "added_rows": len(rows),
                "table_range": table_range,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_get_used_range")
class GetUsedRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            values_only = inputs.get("values_only", False)

            encoded_ws = encode_path_segment(worksheet_name)
            if values_only:
                url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/usedRange(valuesOnly=true)"
            else:
                url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/usedRange"

            response = await context.fetch(url, method="GET")
            values = response.get("values", [])

            return ActionResult(data={
                "range": response.get("address", ""),
                "row_count": response.get("rowCount", len(values)),
                "column_count": response.get("columnCount", len(values[0]) if values else 0),
                "values": values,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_create_worksheet")
class CreateWorksheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            name = inputs["name"]

            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/add"

            body = {"name": name}
            response = await context.fetch(url, method="POST", json=body)

            return ActionResult(data={
                "worksheet": {
                    "id": response.get("id"),
                    "name": response.get("name"),
                    "position": response.get("position"),
                    "visibility": response.get("visibility"),
                },
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_delete_worksheet")
class DeleteWorksheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]

            encoded_ws = encode_path_segment(worksheet_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}"
            await context.fetch(url, method="DELETE")

            return ActionResult(data={"deleted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "deleted": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_create_table")
class CreateTable(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            has_headers = inputs.get("has_headers", True)

            encoded_ws = encode_path_segment(worksheet_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/tables/add"

            body = {"address": range_address, "hasHeaders": has_headers}
            response = await context.fetch(url, method="POST", json=body)

            return ActionResult(data={
                "table": {
                    "id": response.get("id"),
                    "name": response.get("name"),
                    "showHeaders": response.get("showHeaders"),
                },
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_update_table_row")
class UpdateTableRow(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            row_index = inputs["row_index"]
            values = inputs["values"]

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/rows/itemAt(index={row_index})"

            body = {"values": [values]}
            response = await context.fetch(url, method="PATCH", json=body)

            return ActionResult(data={"updated_row": response, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_delete_table_row")
class DeleteTableRow(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            row_index = inputs["row_index"]

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/rows/itemAt(index={row_index})"
            await context.fetch(url, method="DELETE")

            return ActionResult(data={"deleted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "deleted": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_sort_range")
class SortRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            sort_fields = inputs["sort_fields"]
            has_headers = inputs.get("has_headers", True)

            encoded_ws = encode_path_segment(worksheet_name)
            encoded_range = encode_range_address(range_address)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{encoded_range}')/sort/apply"

            fields = []
            for sf in sort_fields:
                fields.append({
                    "key": sf.get("column_index", 0),
                    "ascending": sf.get("ascending", True),
                })

            body = {"fields": fields, "hasHeaders": has_headers, "matchCase": False}
            await context.fetch(url, method="POST", json=body)

            return ActionResult(data={"sorted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "sorted": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_apply_filter")
class ApplyFilter(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            column_index = inputs["column_index"]
            filter_criteria = inputs["filter_criteria"]

            encoded_table = encode_path_segment(table_name)

            # Get columns
            columns_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/columns"
            columns_data = await context.fetch(columns_url, method="GET")

            columns = columns_data.get("value", [])
            if column_index < 0 or column_index >= len(columns):
                return ActionResult(data={
                    "filtered": False,
                    "result": False,
                    "error": f"Column index {column_index} out of range (must be 0-{len(columns) - 1})",
                }, cost_usd=0.0)

            column_id = columns[column_index].get("id")
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/columns/{column_id}/filter/apply"

            body = {"criteria": filter_criteria}
            await context.fetch(url, method="POST", json=body)

            return ActionResult(data={"filtered": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "filtered": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_clear_filter")
class ClearFilter(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/clearFilters"
            await context.fetch(url, method="POST")

            return ActionResult(data={"cleared": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "cleared": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)


@microsoft_excel.action("excel_format_range")
class FormatRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            format_spec = inputs["format"]

            encoded_ws = encode_path_segment(worksheet_name)
            encoded_range = encode_range_address(range_address)
            base_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{encoded_range}')/format"

            errors = []

            # Apply font formatting
            if "font" in format_spec:
                font_url = f"{base_url}/font"
                try:
                    await context.fetch(font_url, method="PATCH", json=format_spec["font"])
                except Exception as e:
                    errors.append(f"Font: {str(e)}")

            # Apply fill formatting
            if "fill" in format_spec:
                fill_url = f"{base_url}/fill"
                try:
                    await context.fetch(fill_url, method="PATCH", json=format_spec["fill"])
                except Exception as e:
                    errors.append(f"Fill: {str(e)}")

            # Apply alignment formatting
            alignment_body = {}
            if "horizontalAlignment" in format_spec:
                alignment_body["horizontalAlignment"] = format_spec["horizontalAlignment"]
            if "verticalAlignment" in format_spec:
                alignment_body["verticalAlignment"] = format_spec["verticalAlignment"]

            if alignment_body:
                try:
                    await context.fetch(base_url, method="PATCH", json=alignment_body)
                except Exception as e:
                    errors.append(f"Alignment: {str(e)}")

            # Apply number format
            if "numberFormat" in format_spec:
                range_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{encoded_range}')"
                try:
                    await context.fetch(range_url, method="PATCH", json={"numberFormat": format_spec["numberFormat"]})
                except Exception as e:
                    errors.append(f"NumberFormat: {str(e)}")

            if errors:
                return ActionResult(data={
                    "formatted": False,
                    "result": False,
                    "error": "; ".join(errors),
                }, cost_usd=0.0)

            return ActionResult(data={"formatted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={
                "formatted": False,
                "result": False,
                "error": str(e),
            }, cost_usd=0.0)
