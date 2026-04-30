from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any

# Create the integration using the config.json
coda = Integration.load()

# Base URL for Coda API
CODA_API_BASE_URL = "https://coda.io/apis/v1"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Coda API requests.

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with Authorization and Content-Type headers
    """
    credentials = context.auth.get("credentials", {})
    api_token = credentials.get("api_token", "")

    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


# ---- Action Handlers ----


@coda.action("list_docs")
class ListDocsAction(ActionHandler):
    """
    Lists all Coda docs accessible by the authenticated user.
    Returns docs in reverse chronological order by latest relevant event.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build query parameters
            params = {}

            if inputs.get("is_owner") is not None:
                params["isOwner"] = str(inputs.get("is_owner")).lower()

            if inputs.get("query"):
                params["query"] = inputs.get("query")

            if inputs.get("source_doc"):
                params["sourceDoc"] = inputs.get("source_doc")

            if inputs.get("is_published") is not None:
                params["isPublished"] = str(inputs.get("is_published")).lower()

            if inputs.get("is_starred") is not None:
                params["isStarred"] = str(inputs.get("is_starred")).lower()

            if inputs.get("limit"):
                params["limit"] = inputs.get("limit")

            # Get auth headers
            headers = get_auth_headers(context)

            # Make API request
            url = f"{CODA_API_BASE_URL}/docs"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            # Extract docs from response
            docs = response.data.get("items", [])

            return ActionResult(data={"docs": docs, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("get_doc")
class GetDocAction(ActionHandler):
    """
    Retrieves metadata for a specific Coda doc by its ID.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}"
            response = await context.fetch(url, method="GET", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("create_doc")
class CreateDocAction(ActionHandler):
    """
    Creates a new Coda doc with the specified title.
    Optionally copies content from an existing doc.
    Returns HTTP 202 (Accepted) as doc creation is processed asynchronously.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"title": inputs["title"]}

            if inputs.get("source_doc"):
                body["sourceDoc"] = inputs.get("source_doc")

            if inputs.get("timezone"):
                body["timezone"] = inputs.get("timezone")

            if inputs.get("folder_id"):
                body["folderId"] = inputs.get("folder_id")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs"
            response = await context.fetch(url, method="POST", headers=headers, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("update_doc")
class UpdateDocAction(ActionHandler):
    """
    Updates metadata for a Coda doc (title and icon).
    Requires Doc Maker permissions for updating the title.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]

            body = {}

            if inputs.get("title"):
                body["title"] = inputs.get("title")

            if inputs.get("icon_name"):
                body["iconName"] = inputs.get("icon_name")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}"
            response = await context.fetch(url, method="PATCH", headers=headers, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("delete_doc")
class DeleteDocAction(ActionHandler):
    """
    Deletes a Coda doc.
    Returns HTTP 202 (Accepted) as deletion is queued for processing.
    This action is permanent and cannot be undone.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}"
            response = await context.fetch(url, method="DELETE", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("list_pages")
class ListPagesAction(ActionHandler):
    """
    Lists all pages in a Coda doc.
    Returns pages with metadata including name, subtitle, icon, and parent/child relationships.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]

            params = {}

            if inputs.get("limit"):
                params["limit"] = inputs.get("limit")

            if inputs.get("page_token"):
                params["pageToken"] = inputs.get("page_token")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/pages"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            pages = response.data.get("items", [])
            next_page_token = response.data.get("nextPageToken")

            result_data = {"pages": pages, "result": True}

            if next_page_token:
                result_data["next_page_token"] = next_page_token

            return ActionResult(data=result_data)

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("get_page")
class GetPageAction(ActionHandler):
    """
    Retrieves detailed metadata for a specific page in a Coda doc.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            page_id_or_name = inputs["page_id_or_name"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/pages/{page_id_or_name}"
            response = await context.fetch(url, method="GET", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("create_page")
class CreatePageAction(ActionHandler):
    """
    Creates a new page in a Coda doc with optional content, subtitle, icon, and parent page.
    Returns HTTP 202 (Accepted) as page creation is processed asynchronously.
    Requires Doc Maker permissions.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            name = inputs["name"]

            body = {"name": name}

            if inputs.get("subtitle"):
                body["subtitle"] = inputs.get("subtitle")

            if inputs.get("icon_name"):
                body["iconName"] = inputs.get("icon_name")

            if inputs.get("image_url"):
                body["imageUrl"] = inputs.get("image_url")

            if inputs.get("parent_page_id"):
                body["parentPageId"] = inputs.get("parent_page_id")

            if inputs.get("content"):
                content_format = inputs.get("content_format", "html")
                body["pageContent"] = {
                    "type": "canvas",
                    "canvasContent": {"format": content_format, "content": inputs.get("content")},
                }

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/pages"
            response = await context.fetch(url, method="POST", headers=headers, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("update_page")
class UpdatePageAction(ActionHandler):
    """
    Updates a page's metadata (name, subtitle, icon, image).
    Cannot update page content after creation.
    Returns HTTP 202 (Accepted) as update is processed asynchronously.
    Requires Doc Maker permissions for updating title/icon.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            page_id_or_name = inputs["page_id_or_name"]

            body = {}

            if inputs.get("name"):
                body["name"] = inputs.get("name")

            if inputs.get("subtitle"):
                body["subtitle"] = inputs.get("subtitle")

            if inputs.get("icon_name"):
                body["iconName"] = inputs.get("icon_name")

            if inputs.get("image_url"):
                body["imageUrl"] = inputs.get("image_url")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/pages/{page_id_or_name}"
            response = await context.fetch(url, method="PUT", headers=headers, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("delete_page")
class DeletePageAction(ActionHandler):
    """
    Deletes the specified page from a Coda doc.
    Returns HTTP 202 (Accepted) as deletion is queued for processing.
    Use page IDs rather than names when possible.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            page_id_or_name = inputs["page_id_or_name"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/pages/{page_id_or_name}"
            response = await context.fetch(url, method="DELETE", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("list_tables")
class ListTablesAction(ActionHandler):
    """
    Lists all tables in a Coda doc.
    By default returns both base tables and views.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]

            params = {}

            if inputs.get("limit"):
                params["limit"] = inputs.get("limit")

            if inputs.get("page_token"):
                params["pageToken"] = inputs.get("page_token")

            if inputs.get("sort_by"):
                params["sortBy"] = inputs.get("sort_by")

            if inputs.get("table_types"):
                params["tableTypes"] = inputs.get("table_types")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            tables = response.data.get("items", [])
            next_page_token = response.data.get("nextPageToken")

            result_data = {"tables": tables, "result": True}

            if next_page_token:
                result_data["next_page_token"] = next_page_token

            return ActionResult(data=result_data)

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("get_table")
class GetTableAction(ActionHandler):
    """
    Retrieves detailed metadata for a specific table or view.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}"
            response = await context.fetch(url, method="GET", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("list_columns")
class ListColumnsAction(ActionHandler):
    """
    Lists all columns in a table or view.
    Use this to discover table structure before inserting or reading rows.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]

            params = {}

            if inputs.get("limit"):
                params["limit"] = inputs.get("limit")

            if inputs.get("page_token"):
                params["pageToken"] = inputs.get("page_token")

            if inputs.get("visible_only") is not None:
                params["visibleOnly"] = str(inputs.get("visible_only")).lower()

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/columns"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            columns = response.data.get("items", [])
            next_page_token = response.data.get("nextPageToken")

            result_data = {"columns": columns, "result": True}

            if next_page_token:
                result_data["next_page_token"] = next_page_token

            return ActionResult(data=result_data)

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("get_column")
class GetColumnAction(ActionHandler):
    """
    Retrieves detailed metadata for a specific column.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            column_id_or_name = inputs["column_id_or_name"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/columns/{column_id_or_name}"
            response = await context.fetch(url, method="GET", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("list_rows")
class ListRowsAction(ActionHandler):
    """
    Lists all rows in a table or view.
    Supports filtering, sorting, and pagination.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]

            params = {}

            if inputs.get("limit"):
                params["limit"] = inputs.get("limit")

            if inputs.get("page_token"):
                params["pageToken"] = inputs.get("page_token")

            if inputs.get("query"):
                params["query"] = inputs.get("query")

            if inputs.get("sort_by"):
                params["sortBy"] = inputs.get("sort_by")

            if inputs.get("use_column_names") is not None:
                params["useColumnNames"] = str(inputs.get("use_column_names")).lower()

            if inputs.get("value_format"):
                params["valueFormat"] = inputs.get("value_format")

            if inputs.get("visible_only") is not None:
                params["visibleOnly"] = str(inputs.get("visible_only")).lower()

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            rows = response.data.get("items", [])
            next_page_token = response.data.get("nextPageToken")

            result_data = {"rows": rows, "result": True}

            if next_page_token:
                result_data["next_page_token"] = next_page_token

            return ActionResult(data=result_data)

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("get_row")
class GetRowAction(ActionHandler):
    """
    Retrieves detailed data for a specific row.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            row_id_or_name = inputs["row_id_or_name"]

            params = {}

            if inputs.get("use_column_names") is not None:
                params["useColumnNames"] = str(inputs.get("use_column_names")).lower()

            if inputs.get("value_format"):
                params["valueFormat"] = inputs.get("value_format")

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("upsert_rows")
class UpsertRowsAction(ActionHandler):
    """
    Inserts rows into a table, or updates existing rows if keyColumns are provided.
    Only works on base tables, not views.
    Returns HTTP 202 (Accepted) as processing is asynchronous.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            rows = inputs["rows"]

            body = {"rows": rows}

            if inputs.get("key_columns"):
                body["keyColumns"] = inputs.get("key_columns")

            params = {}
            if inputs.get("disable_parsing"):
                params["disableParsing"] = str(inputs.get("disable_parsing")).lower()

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows"
            response = await context.fetch(url, method="POST", headers=headers, params=params, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("update_row")
class UpdateRowAction(ActionHandler):
    """
    Updates a specific row in a table.
    Only updates the cells provided, leaving others unchanged.
    Returns HTTP 202 (Accepted).
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            row_id_or_name = inputs["row_id_or_name"]
            cells = inputs["cells"]

            body = {"row": {"cells": cells}}

            params = {}
            if inputs.get("disable_parsing"):
                params["disableParsing"] = str(inputs.get("disable_parsing")).lower()

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
            response = await context.fetch(url, method="PUT", headers=headers, params=params, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("delete_row")
class DeleteRowAction(ActionHandler):
    """
    Deletes a specific row from a table.
    Returns HTTP 202 (Accepted) as deletion is queued for processing.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            row_id_or_name = inputs["row_id_or_name"]

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows/{row_id_or_name}"
            response = await context.fetch(url, method="DELETE", headers=headers)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))


@coda.action("delete_rows")
class DeleteRowsAction(ActionHandler):
    """
    Deletes multiple rows from a table by their IDs.
    Returns HTTP 202 (Accepted) as deletion is queued for processing.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            doc_id = inputs["doc_id"]
            table_id_or_name = inputs["table_id_or_name"]
            row_ids = inputs["row_ids"]

            body = {"rowIds": row_ids}

            headers = get_auth_headers(context)

            url = f"{CODA_API_BASE_URL}/docs/{doc_id}/tables/{table_id_or_name}/rows"
            response = await context.fetch(url, method="DELETE", headers=headers, json=body)

            return ActionResult(data={"data": response.data, "result": True})

        except Exception as e:
            return ActionError(message=str(e))
