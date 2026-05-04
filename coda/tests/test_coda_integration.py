"""
End-to-end integration tests for the Coda integration.

These tests call the real Coda API and require a valid API token
set in the CODA_API_KEY environment variable (via .env or export).

Run with:
    pytest coda/tests/test_coda_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("coda_mod_integration", os.path.join(_parent, "coda.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

coda = _mod.coda

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("CODA_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("CODA_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_token": API_KEY}}  # nosec B105
    return ctx


# ---- Read-Only Tests ----


class TestListDocs:
    async def test_returns_docs_list(self, live_context):
        result = await coda.execute_action("list_docs", {}, live_context)

        data = result.result.data
        assert "docs" in data
        assert isinstance(data["docs"], list)

    async def test_filter_by_query(self, live_context):
        result = await coda.execute_action("list_docs", {"query": "test"}, live_context)

        data = result.result.data
        assert "docs" in data

    async def test_is_owner_filter(self, live_context):
        result = await coda.execute_action("list_docs", {"is_owner": True}, live_context)

        data = result.result.data
        assert "docs" in data

    async def test_limit_respected(self, live_context):
        result = await coda.execute_action("list_docs", {"limit": 2}, live_context)

        data = result.result.data
        assert len(data["docs"]) <= 2


class TestGetDoc:
    async def test_returns_doc_metadata(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("get_doc", {"doc_id": doc_id}, live_context)

        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == doc_id

    async def test_doc_has_expected_fields(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("get_doc", {"doc_id": doc_id}, live_context)

        doc = result.result.data["data"]
        assert "id" in doc
        assert "name" in doc
        assert "type" in doc


class TestListPages:
    async def test_returns_pages_list(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("list_pages", {"doc_id": doc_id}, live_context)

        data = result.result.data
        assert "pages" in data
        assert isinstance(data["pages"], list)

    async def test_limit_respected(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("list_pages", {"doc_id": doc_id, "limit": 2}, live_context)

        data = result.result.data
        assert len(data["pages"]) <= 2


class TestGetPage:
    async def test_returns_page_metadata(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        pages_result = await coda.execute_action("list_pages", {"doc_id": doc_id}, live_context)
        pages = pages_result.result.data["pages"]

        if not pages:
            pytest.skip("No pages in doc to test with")

        page_id = pages[0]["id"]
        result = await coda.execute_action("get_page", {"doc_id": doc_id, "page_id_or_name": page_id}, live_context)

        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == page_id

    async def test_page_has_expected_fields(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        pages_result = await coda.execute_action("list_pages", {"doc_id": doc_id}, live_context)
        pages = pages_result.result.data["pages"]

        if not pages:
            pytest.skip("No pages in doc to test with")

        page_id = pages[0]["id"]
        result = await coda.execute_action("get_page", {"doc_id": doc_id, "page_id_or_name": page_id}, live_context)

        page = result.result.data["data"]
        assert "id" in page
        assert "name" in page
        assert "type" in page


class TestListTables:
    async def test_returns_tables_list(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)

        data = result.result.data
        assert "tables" in data
        assert isinstance(data["tables"], list)

    async def test_limit_respected(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        result = await coda.execute_action("list_tables", {"doc_id": doc_id, "limit": 2}, live_context)

        data = result.result.data
        assert len(data["tables"]) <= 2


class TestGetTable:
    async def test_returns_table_metadata(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action("get_table", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context)

        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == table_id

    async def test_table_has_expected_fields(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action("get_table", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context)

        table = result.result.data["data"]
        assert "id" in table
        assert "name" in table
        assert "type" in table


class TestListColumns:
    async def test_returns_columns_list(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action(
            "list_columns", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context
        )

        data = result.result.data
        assert "columns" in data
        assert isinstance(data["columns"], list)

    async def test_columns_have_expected_fields(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action(
            "list_columns", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context
        )

        columns = result.result.data["columns"]
        if columns:
            assert "id" in columns[0]
            assert "name" in columns[0]


class TestGetColumn:
    async def test_returns_column_metadata(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        cols_result = await coda.execute_action(
            "list_columns", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context
        )
        columns = cols_result.result.data["columns"]

        if not columns:
            pytest.skip("No columns in table to test with")

        col_id = columns[0]["id"]
        result = await coda.execute_action(
            "get_column", {"doc_id": doc_id, "table_id_or_name": table_id, "column_id_or_name": col_id}, live_context
        )

        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == col_id


class TestListRows:
    async def test_returns_rows_list(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action("list_rows", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context)

        data = result.result.data
        assert "rows" in data
        assert isinstance(data["rows"], list)

    async def test_limit_respected(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        result = await coda.execute_action(
            "list_rows", {"doc_id": doc_id, "table_id_or_name": table_id, "limit": 2}, live_context
        )

        data = result.result.data
        assert len(data["rows"]) <= 2


class TestGetRow:
    async def test_returns_row_data(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = tables_result.result.data["tables"]

        if not tables:
            pytest.skip("No tables in doc to test with")

        table_id = tables[0]["id"]
        rows_result = await coda.execute_action(
            "list_rows", {"doc_id": doc_id, "table_id_or_name": table_id, "limit": 1}, live_context
        )
        rows = rows_result.result.data["rows"]

        if not rows:
            pytest.skip("No rows in table to test with")

        row_id = rows[0]["id"]
        result = await coda.execute_action(
            "get_row", {"doc_id": doc_id, "table_id_or_name": table_id, "row_id_or_name": row_id}, live_context
        )

        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == row_id


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestDocLifecycle:
    """End-to-end workflow: create doc → update → delete."""

    async def test_full_lifecycle(self, live_context):
        doc_name = f"Integration Test Doc {os.getpid()}"

        create_result = await coda.execute_action("create_doc", {"title": doc_name}, live_context)
        assert "data" in create_result.result.data
        doc_id = create_result.result.data["data"].get("id")
        assert doc_id is not None

        update_result = await coda.execute_action(
            "update_doc", {"doc_id": doc_id, "title": f"{doc_name} Updated"}, live_context
        )
        assert "data" in update_result.result.data

        delete_result = await coda.execute_action("delete_doc", {"doc_id": doc_id}, live_context)
        assert "data" in delete_result.result.data


@pytest.mark.destructive
class TestPageLifecycle:
    """End-to-end workflow: create page → update → delete."""

    async def test_full_lifecycle(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        page_name = f"Integration Test Page {os.getpid()}"

        create_result = await coda.execute_action("create_page", {"doc_id": doc_id, "name": page_name}, live_context)
        assert "data" in create_result.result.data
        page_id = create_result.result.data["data"].get("id")
        assert page_id is not None

        update_result = await coda.execute_action(
            "update_page",
            {"doc_id": doc_id, "page_id_or_name": page_id, "name": f"{page_name} Updated"},
            live_context,
        )
        assert "data" in update_result.result.data

        delete_result = await coda.execute_action(
            "delete_page", {"doc_id": doc_id, "page_id_or_name": page_id}, live_context
        )
        assert "data" in delete_result.result.data


@pytest.mark.destructive
class TestRowLifecycle:
    """End-to-end workflow: upsert rows → get row → update row → delete row."""

    async def test_full_lifecycle(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = [t for t in tables_result.result.data["tables"] if t.get("tableType") == "table"]

        if not tables:
            pytest.skip("No base tables in doc to test with")

        table_id = tables[0]["id"]

        cols_result = await coda.execute_action(
            "list_columns", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context
        )
        columns = cols_result.result.data["columns"]

        if not columns:
            pytest.skip("No columns in table to test with")

        col_id = columns[0]["id"]
        test_value = f"Integration Test {os.getpid()}"

        upsert_result = await coda.execute_action(
            "upsert_rows",
            {
                "doc_id": doc_id,
                "table_id_or_name": table_id,
                "rows": [{"cells": [{"column": col_id, "value": test_value}]}],
            },
            live_context,
        )
        assert "data" in upsert_result.result.data

        rows_result = await coda.execute_action(
            "list_rows", {"doc_id": doc_id, "table_id_or_name": table_id, "limit": 1}, live_context
        )
        rows = rows_result.result.data["rows"]

        if not rows:
            pytest.skip("No rows found after upsert")

        row_id = rows[0]["id"]

        update_result = await coda.execute_action(
            "update_row",
            {
                "doc_id": doc_id,
                "table_id_or_name": table_id,
                "row_id_or_name": row_id,
                "cells": [{"column": col_id, "value": f"{test_value} Updated"}],
            },
            live_context,
        )
        assert "data" in update_result.result.data

        delete_result = await coda.execute_action(
            "delete_row",
            {"doc_id": doc_id, "table_id_or_name": table_id, "row_id_or_name": row_id},
            live_context,
        )
        assert "data" in delete_result.result.data


@pytest.mark.destructive
class TestDeleteRows:
    async def test_delete_multiple_rows(self, live_context):
        list_result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        docs = list_result.result.data["docs"]

        if not docs:
            pytest.skip("No docs in account to test with")

        doc_id = docs[0]["id"]
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc_id}, live_context)
        tables = [t for t in tables_result.result.data["tables"] if t.get("tableType") == "table"]

        if not tables:
            pytest.skip("No base tables in doc to test with")

        table_id = tables[0]["id"]
        cols_result = await coda.execute_action(
            "list_columns", {"doc_id": doc_id, "table_id_or_name": table_id}, live_context
        )
        columns = cols_result.result.data["columns"]

        if not columns:
            pytest.skip("No columns in table to test with")

        col_id = columns[0]["id"]

        upsert_result = await coda.execute_action(
            "upsert_rows",
            {
                "doc_id": doc_id,
                "table_id_or_name": table_id,
                "rows": [
                    {"cells": [{"column": col_id, "value": f"Delete Test A {os.getpid()}"}]},
                    {"cells": [{"column": col_id, "value": f"Delete Test B {os.getpid()}"}]},
                ],
            },
            live_context,
        )
        assert "data" in upsert_result.result.data

        rows_result = await coda.execute_action(
            "list_rows", {"doc_id": doc_id, "table_id_or_name": table_id, "limit": 2}, live_context
        )
        row_ids = [r["id"] for r in rows_result.result.data["rows"]]

        if len(row_ids) < 2:
            pytest.skip("Not enough rows to test delete_rows")

        delete_result = await coda.execute_action(
            "delete_rows",
            {"doc_id": doc_id, "table_id_or_name": table_id, "row_ids": row_ids[:2]},
            live_context,
        )
        assert "data" in delete_result.result.data
