import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("coda_mod", os.path.join(_parent, "coda.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["coda_mod"] = _mod

coda = _mod.coda

pytestmark = pytest.mark.unit

API_BASE = "https://coda.io/apis/v1"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    return ctx


# ---- list_docs ----


class TestListDocs:
    async def test_returns_docs(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "doc1", "name": "My Doc"}]},
        )

        result = await coda.execute_action("list_docs", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["docs"] == [{"id": "doc1", "name": "My Doc"}]
        assert result.result.data["result"] is True
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{API_BASE}/docs"
        assert call.kwargs["method"] == "GET"

    async def test_auth_header_propagated(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"items": []})

        await coda.execute_action("list_docs", {}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test_token"  # nosec B105

    async def test_empty_docs(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"items": []})

        result = await coda.execute_action("list_docs", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["docs"] == []

    async def test_passes_query_param(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"items": []})

        await coda.execute_action("list_docs", {"query": "budget"}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["query"] == "budget"

    async def test_fetch_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await coda.execute_action("list_docs", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- get_doc ----


class TestGetDoc:
    async def test_returns_doc(self, mock_context):
        doc_data = {"id": "AbCDeFGH", "name": "My Doc", "owner": "user@example.com"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=doc_data)

        result = await coda.execute_action("get_doc", {"doc_id": "AbCDeFGH"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["id"] == "AbCDeFGH"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/AbCDeFGH"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("404 Not Found")

        result = await coda.execute_action("get_doc", {"doc_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


# ---- create_doc ----


class TestCreateDoc:
    async def test_creates_doc(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=202,
            headers={},
            data={"id": "newDoc1", "name": "New Doc", "href": "https://coda.io/d/newDoc1"},
        )

        result = await coda.execute_action("create_doc", {"title": "New Doc"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["id"] == "newDoc1"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{API_BASE}/docs"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["title"] == "New Doc"

    async def test_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data={"id": "d1"})

        await coda.execute_action(
            "create_doc",
            {"title": "Copy", "source_doc": "srcDoc", "timezone": "America/New_York", "folder_id": "fl1"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["sourceDoc"] == "srcDoc"
        assert body["timezone"] == "America/New_York"
        assert body["folderId"] == "fl1"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await coda.execute_action("create_doc", {"title": "Doc"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


# ---- list_pages ----


class TestListPages:
    async def test_returns_pages(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "canvas-abc", "name": "Introduction"}]},
        )

        result = await coda.execute_action("list_pages", {"doc_id": "doc1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["pages"]) == 1
        assert result.result.data["pages"][0]["id"] == "canvas-abc"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/pages"

    async def test_next_page_token_included(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [], "nextPageToken": "tok123"},
        )

        result = await coda.execute_action("list_pages", {"doc_id": "doc1"}, mock_context)

        assert result.result.data["next_page_token"] == "tok123"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await coda.execute_action("list_pages", {"doc_id": "doc1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- get_page ----


class TestGetPage:
    async def test_returns_page(self, mock_context):
        page_data = {"id": "canvas-abc", "name": "Introduction", "subtitle": ""}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=page_data)

        result = await coda.execute_action(
            "get_page", {"doc_id": "doc1", "page_id_or_name": "canvas-abc"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["id"] == "canvas-abc"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/pages/canvas-abc"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await coda.execute_action("get_page", {"doc_id": "doc1", "page_id_or_name": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_tables ----


class TestListTables:
    async def test_returns_tables(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "grid-xyz", "name": "Tasks", "tableType": "table"}]},
        )

        result = await coda.execute_action("list_tables", {"doc_id": "doc1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["tables"]) == 1
        assert result.result.data["tables"][0]["id"] == "grid-xyz"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server Error")

        result = await coda.execute_action("list_tables", {"doc_id": "doc1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Server Error" in result.result.message


# ---- get_table ----


class TestGetTable:
    async def test_returns_table(self, mock_context):
        table_data = {"id": "grid-xyz", "name": "Tasks", "rowCount": 5}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=table_data)

        result = await coda.execute_action(
            "get_table", {"doc_id": "doc1", "table_id_or_name": "grid-xyz"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["rowCount"] == 5
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables/grid-xyz"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await coda.execute_action("get_table", {"doc_id": "doc1", "table_id_or_name": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- list_columns ----


class TestListColumns:
    async def test_returns_columns(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "c-col1", "name": "Name"}, {"id": "c-col2", "name": "Status"}]},
        )

        result = await coda.execute_action(
            "list_columns", {"doc_id": "doc1", "table_id_or_name": "grid-xyz"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["columns"]) == 2
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables/grid-xyz/columns"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await coda.execute_action(
            "list_columns", {"doc_id": "doc1", "table_id_or_name": "grid-xyz"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_column ----


class TestGetColumn:
    async def test_returns_column(self, mock_context):
        col_data = {"id": "c-col1", "name": "Name", "valueType": "text"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=col_data)

        result = await coda.execute_action(
            "get_column",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "column_id_or_name": "c-col1"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["name"] == "Name"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables/grid-xyz/columns/c-col1"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await coda.execute_action(
            "get_column",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "column_id_or_name": "missing"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- list_rows ----


class TestListRows:
    async def test_returns_rows(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "i-row1", "values": {"c-col1": "Alice"}}]},
        )

        result = await coda.execute_action(
            "list_rows", {"doc_id": "doc1", "table_id_or_name": "grid-xyz"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["rows"]) == 1
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables/grid-xyz/rows"

    async def test_passes_filter_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"items": []})

        await coda.execute_action(
            "list_rows",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "query": 'Name:"Alice"', "limit": 10},
            mock_context,
        )

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["query"] == 'Name:"Alice"'
        assert params["limit"] == 10

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await coda.execute_action(
            "list_rows", {"doc_id": "doc1", "table_id_or_name": "grid-xyz"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_row ----


class TestGetRow:
    async def test_returns_row(self, mock_context):
        row_data = {"id": "i-row1", "values": {"c-col1": "Alice"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=row_data)

        result = await coda.execute_action(
            "get_row",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_id_or_name": "i-row1"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["id"] == "i-row1"
        assert mock_context.fetch.call_args.args[0] == f"{API_BASE}/docs/doc1/tables/grid-xyz/rows/i-row1"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await coda.execute_action(
            "get_row",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_id_or_name": "missing"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- upsert_rows ----


class TestUpsertRows:
    async def test_inserts_rows(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=202,
            headers={},
            data={"requestId": "req1", "addedRowIds": ["i-row1"]},
        )
        rows = [{"cells": [{"column": "c-col1", "value": "Alice"}]}]

        result = await coda.execute_action(
            "upsert_rows",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "rows": rows},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["data"]["addedRowIds"] == ["i-row1"]
        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["rows"] == rows

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad Request")

        result = await coda.execute_action(
            "upsert_rows",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "rows": []},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- delete_row ----


class TestDeleteRow:
    async def test_deletes_row(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=202, headers={}, data={"requestId": "req1", "id": "i-row1"}
        )

        result = await coda.execute_action(
            "delete_row",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_id_or_name": "i-row1"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["result"] is True
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not Found")

        result = await coda.execute_action(
            "delete_row",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_id_or_name": "missing"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- delete_rows ----


class TestDeleteRows:
    async def test_deletes_multiple_rows(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=202, headers={}, data={"requestId": "req1", "rowIds": ["i-row1", "i-row2"]}
        )

        result = await coda.execute_action(
            "delete_rows",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_ids": ["i-row1", "i-row2"]},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["result"] is True
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["rowIds"] == ["i-row1", "i-row2"]

    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server Error")

        result = await coda.execute_action(
            "delete_rows",
            {"doc_id": "doc1", "table_id_or_name": "grid-xyz", "row_ids": ["i-row1"]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
