from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any
from urllib.parse import quote

microsoft_excel = Integration.load()

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
EXCEL_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def encode_path_segment(segment: str) -> str:
    return quote(segment, safe="")


@microsoft_excel.action("excel_list_workbooks")
class ListWorkbooks(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            name_contains = inputs.get("name_contains")
            folder_path = inputs.get("folder_path")
            page_size = inputs.get("page_size", 25)
            page_token = inputs.get("page_token")

            if folder_path:
                url = f"{GRAPH_BASE_URL}/me/drive/root:/{folder_path}:/children"
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

            if response.status_code != 200:
                return ActionResult(data={
                    "workbooks": [],
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            items = data.get("value", [])

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
            next_link = data.get("@odata.nextLink")
            if next_link:
                result_data["next_page_token"] = next_link

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"workbooks": [], "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_get_workbook")
class GetWorkbook(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]

            file_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}"
            file_response = await context.fetch(file_url, method="GET")

            if file_response.status_code != 200:
                return ActionResult(data={
                    "result": False,
                    "error": f"Failed to get file info: {file_response.status_code}",
                }, cost_usd=0.0)

            file_data = file_response.json()

            worksheets_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
            ws_response = await context.fetch(worksheets_url, method="GET")

            worksheets = []
            if ws_response.status_code == 200:
                ws_data = ws_response.json()
                for ws in ws_data.get("value", []):
                    worksheets.append({
                        "id": ws.get("id"),
                        "name": ws.get("name"),
                        "position": ws.get("position"),
                        "visibility": ws.get("visibility"),
                    })

            tables_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables"
            tables_response = await context.fetch(tables_url, method="GET")

            tables = []
            if tables_response.status_code == 200:
                tables_data = tables_response.json()
                for table in tables_data.get("value", []):
                    tables.append({
                        "id": table.get("id"),
                        "name": table.get("name"),
                        "showHeaders": table.get("showHeaders"),
                        "showTotals": table.get("showTotals"),
                        "style": table.get("style"),
                    })

            names_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/names"
            names_response = await context.fetch(names_url, method="GET")

            named_ranges = []
            if names_response.status_code == 200:
                names_data = names_response.json()
                for name in names_data.get("value", []):
                    named_ranges.append({
                        "name": name.get("name"),
                        "value": name.get("value"),
                        "type": name.get("type"),
                    })

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
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_list_worksheets")
class ListWorksheets(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]

            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets"
            response = await context.fetch(url, method="GET")

            if response.status_code != 200:
                return ActionResult(data={
                    "worksheets": [],
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            worksheets = []
            for ws in data.get("value", []):
                worksheets.append({
                    "id": ws.get("id"),
                    "name": ws.get("name"),
                    "position": ws.get("position"),
                    "visibility": ws.get("visibility"),
                })

            return ActionResult(data={"worksheets": worksheets, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"worksheets": [], "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_read_range")
class ReadRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            value_render_option = inputs.get("value_render_option", "FORMATTED_VALUE")

            encoded_ws = encode_path_segment(worksheet_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{range_address}')"
            response = await context.fetch(url, method="GET")

            if response.status_code != 200:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            values = data.get("values", [])
            formulas = data.get("formulas", []) if value_render_option == "FORMULA" else []
            number_format = data.get("numberFormat", [])

            row_count = len(values)
            column_count = len(values[0]) if values else 0

            return ActionResult(data={
                "range": data.get("address", range_address),
                "values": values,
                "formulas": formulas,
                "number_format": number_format,
                "row_count": row_count,
                "column_count": column_count,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_write_range")
class WriteRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            values = inputs["values"]

            encoded_ws = encode_path_segment(worksheet_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{range_address}')"

            body = {"values": values}
            response = await context.fetch(url, method="PATCH", json=body)

            if response.status_code not in [200, 201]:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            row_count = len(values)
            column_count = len(values[0]) if values else 0

            return ActionResult(data={
                "updated_range": data.get("address", range_address),
                "updated_rows": row_count,
                "updated_columns": column_count,
                "updated_cells": row_count * column_count,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


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

            if response.status_code != 200:
                return ActionResult(data={
                    "tables": [],
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            tables = []
            for table in data.get("value", []):
                tables.append({
                    "id": table.get("id"),
                    "name": table.get("name"),
                    "showHeaders": table.get("showHeaders"),
                    "showTotals": table.get("showTotals"),
                    "style": table.get("style"),
                })

            return ActionResult(data={"tables": tables, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"tables": [], "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_get_table_data")
class GetTableData(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            select_columns = inputs.get("select_columns")
            top = inputs.get("top")
            skip = inputs.get("skip")

            encoded_table = encode_path_segment(table_name)
            header_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/headerRowRange"
            header_response = await context.fetch(header_url, method="GET")

            if header_response.status_code != 200:
                return ActionResult(data={
                    "result": False,
                    "error": f"Failed to get table headers: {header_response.status_code}",
                }, cost_usd=0.0)

            header_data = header_response.json()
            all_headers = header_data.get("values", [[]])[0]

            rows_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/dataBodyRange"
            rows_response = await context.fetch(rows_url, method="GET")

            if rows_response.status_code != 200:
                return ActionResult(data={
                    "result": False,
                    "error": f"Failed to get table data: {rows_response.status_code}",
                }, cost_usd=0.0)

            rows_data = rows_response.json()
            all_rows = rows_data.get("values", [])

            if select_columns:
                col_indices = [all_headers.index(c) for c in select_columns if c in all_headers]
                headers_out = [all_headers[i] for i in col_indices]
                rows_out = [[row[i] for i in col_indices if i < len(row)] for row in all_rows]
            else:
                headers_out = all_headers
                rows_out = all_rows

            if skip:
                rows_out = rows_out[skip:]
            if top:
                rows_out = rows_out[:top]

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
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


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

            response = await context.fetch(url, method="POST", json=body)

            if response.status_code not in [200, 201]:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            range_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/range"
            range_response = await context.fetch(range_url, method="GET")
            table_range = ""
            if range_response.status_code == 200:
                table_range = range_response.json().get("address", "")

            return ActionResult(data={
                "added_rows": len(rows),
                "table_range": table_range,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


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

            if response.status_code != 200:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            values = data.get("values", [])

            return ActionResult(data={
                "range": data.get("address", ""),
                "row_count": data.get("rowCount", len(values)),
                "column_count": data.get("columnCount", len(values[0]) if values else 0),
                "values": values,
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_create_worksheet")
class CreateWorksheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            name = inputs["name"]

            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/add"

            body = {"name": name}
            response = await context.fetch(url, method="POST", json=body)

            if response.status_code not in [200, 201]:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()

            return ActionResult(data={
                "worksheet": {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "position": data.get("position"),
                    "visibility": data.get("visibility"),
                },
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_delete_worksheet")
class DeleteWorksheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]

            encoded_ws = encode_path_segment(worksheet_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}"
            response = await context.fetch(url, method="DELETE")

            if response.status_code not in [200, 204]:
                return ActionResult(data={
                    "deleted": False,
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            return ActionResult(data={"deleted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"deleted": False, "result": False, "error": str(e)}, cost_usd=0.0)


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

            if response.status_code not in [200, 201]:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            return ActionResult(data={
                "table": {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "showHeaders": data.get("showHeaders"),
                },
                "result": True,
            }, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


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

            if response.status_code not in [200, 201]:
                return ActionResult(data={
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            data = response.json()
            return ActionResult(data={"updated_row": data, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_delete_table_row")
class DeleteTableRow(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            row_index = inputs["row_index"]

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/rows/itemAt(index={row_index})"
            response = await context.fetch(url, method="DELETE")

            if response.status_code not in [200, 204]:
                return ActionResult(data={
                    "deleted": False,
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            return ActionResult(data={"deleted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"deleted": False, "result": False, "error": str(e)}, cost_usd=0.0)


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
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{range_address}')/sort/apply"

            fields = []
            for sf in sort_fields:
                fields.append({
                    "key": sf.get("column_index", 0),
                    "ascending": sf.get("ascending", True),
                })

            body = {"fields": fields, "hasHeaders": has_headers, "matchCase": False}
            response = await context.fetch(url, method="POST", json=body)

            if response.status_code not in [200, 204]:
                return ActionResult(data={
                    "sorted": False,
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            return ActionResult(data={"sorted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"sorted": False, "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_apply_filter")
class ApplyFilter(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]
            column_index = inputs["column_index"]
            filter_criteria = inputs["filter_criteria"]

            encoded_table = encode_path_segment(table_name)
            columns_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/columns"
            columns_response = await context.fetch(columns_url, method="GET")

            if columns_response.status_code != 200:
                return ActionResult(data={
                    "filtered": False,
                    "result": False,
                    "error": f"Failed to get columns: {columns_response.status_code}",
                }, cost_usd=0.0)

            columns = columns_response.json().get("value", [])
            if column_index >= len(columns):
                return ActionResult(data={
                    "filtered": False,
                    "result": False,
                    "error": "Column index out of range",
                }, cost_usd=0.0)

            column_id = columns[column_index].get("id")
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/columns/{column_id}/filter/apply"

            body = {"criteria": filter_criteria}
            response = await context.fetch(url, method="POST", json=body)

            if response.status_code not in [200, 204]:
                return ActionResult(data={
                    "filtered": False,
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            return ActionResult(data={"filtered": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"filtered": False, "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_clear_filter")
class ClearFilter(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            table_name = inputs["table_name"]

            encoded_table = encode_path_segment(table_name)
            url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/tables/{encoded_table}/clearFilters"
            response = await context.fetch(url, method="POST")

            if response.status_code not in [200, 204]:
                return ActionResult(data={
                    "cleared": False,
                    "result": False,
                    "error": f"Microsoft Graph API error: {response.status_code}",
                }, cost_usd=0.0)

            return ActionResult(data={"cleared": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"cleared": False, "result": False, "error": str(e)}, cost_usd=0.0)


@microsoft_excel.action("excel_format_range")
class FormatRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            workbook_id = inputs["workbook_id"]
            worksheet_name = inputs["worksheet_name"]
            range_address = inputs["range"]
            format_spec = inputs["format"]

            encoded_ws = encode_path_segment(worksheet_name)
            base_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{range_address}')/format"

            if "font" in format_spec:
                font_url = f"{base_url}/font"
                await context.fetch(font_url, method="PATCH", json=format_spec["font"])

            if "fill" in format_spec:
                fill_url = f"{base_url}/fill"
                await context.fetch(fill_url, method="PATCH", json=format_spec["fill"])

            alignment_body = {}
            if "horizontalAlignment" in format_spec:
                alignment_body["horizontalAlignment"] = format_spec["horizontalAlignment"]
            if "verticalAlignment" in format_spec:
                alignment_body["verticalAlignment"] = format_spec["verticalAlignment"]

            if alignment_body:
                await context.fetch(base_url, method="PATCH", json=alignment_body)

            if "numberFormat" in format_spec:
                range_url = f"{GRAPH_BASE_URL}/me/drive/items/{workbook_id}/workbook/worksheets/{encoded_ws}/range(address='{range_address}')"
                await context.fetch(range_url, method="PATCH", json={"numberFormat": format_spec["numberFormat"]})

            return ActionResult(data={"formatted": True, "result": True}, cost_usd=0.0)

        except Exception as e:
            return ActionResult(data={"formatted": False, "result": False, "error": str(e)}, cost_usd=0.0)
