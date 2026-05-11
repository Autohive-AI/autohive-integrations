"""
End-to-end integration tests for the Coda integration.

These tests call the real Coda API and require a valid API token
set in the CODA_API_KEY environment variable (via .env or export).

Run with:
    pytest coda/tests/test_coda_integration.py -m integration

A session-scoped fixture creates one test doc (with a page, table, and rows)
at the start and tears it down at the end, so all tests have real data to work with.
"""

import asyncio
import os

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse

from coda.coda import coda

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("CODA_API_KEY", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
async def test_doc(live_context):
    """Creates a test doc at session start and deletes it at the end."""
    result = await coda.execute_action("create_doc", {"title": "AH Integration Test Doc"}, live_context)
    doc_id = result.result.data["data"]["id"]
    await asyncio.sleep(5)  # Coda needs a moment before the doc is accessible via API
    yield doc_id
    await coda.execute_action("delete_doc", {"doc_id": doc_id}, live_context)


@pytest.fixture(scope="session")
async def test_page(live_context, test_doc):
    """Creates a test page inside the test doc."""
    result = await coda.execute_action("create_page", {"doc_id": test_doc, "name": "AH Test Page"}, live_context)
    page_id = result.result.data["data"]["id"]
    await asyncio.sleep(3)  # Coda needs a moment before the page appears in list_pages
    yield page_id
    await coda.execute_action("delete_page", {"doc_id": test_doc, "page_id_or_name": page_id}, live_context)


async def _find_doc_with_table(live_context):
    """Search all docs for one that has a table with at least one column. Returns (doc_id, table_id, col_id) or None."""
    all_docs = (await coda.execute_action("list_docs", {}, live_context)).result.data["docs"]
    for doc in all_docs:
        tables_result = await coda.execute_action("list_tables", {"doc_id": doc["id"]}, live_context)
        tables = tables_result.result.data.get("tables", [])
        for table in tables:
            cols_result = await coda.execute_action(
                "list_columns", {"doc_id": doc["id"], "table_id_or_name": table["id"]}, live_context
            )
            cols = cols_result.result.data.get("columns", [])
            if cols:
                return doc["id"], table["id"], cols[0]["id"]
    return None


@pytest.fixture(scope="session")
async def test_table_doc(live_context):
    """
    Finds a doc with at least one table+column.

    Strategy:
    1. If CODA_TABLE_DOC_ID env var is set, use that doc directly.
    2. Otherwise scan all existing docs.
    3. If none found, create a doc from Coda's Getting Started template (sourceDoc copy).
    4. If that still yields no tables, skip with an actionable message.

    To enable table tests: create a doc with at least one table in the Coda account,
    then set CODA_TABLE_DOC_ID=<doc_id> or just re-run (the scan will find it).
    """
    # 1. Explicit override
    override_id = os.environ.get("CODA_TABLE_DOC_ID", "")
    if override_id:
        tables_result = await coda.execute_action("list_tables", {"doc_id": override_id}, live_context)
        tables = tables_result.result.data.get("tables", [])
        for table in tables:
            cols_result = await coda.execute_action(
                "list_columns", {"doc_id": override_id, "table_id_or_name": table["id"]}, live_context
            )
            cols = cols_result.result.data.get("columns", [])
            if cols:
                return override_id, table["id"], cols[0]["id"]

    # 2. Scan existing docs
    found = await _find_doc_with_table(live_context)
    if found:
        return found

    pytest.skip(
        "No doc with a table+column found. "
        "Create a doc with at least one table in your Coda account and re-run, "
        "or set CODA_TABLE_DOC_ID=<doc_id> to point directly at one."
    )


@pytest.fixture(scope="session")
async def test_table_and_col(live_context, test_table_doc):
    """Returns (table_id, col_id) from a doc that has real tables."""
    _, table_id, col_id = test_table_doc
    return table_id, col_id


@pytest.fixture(scope="session")
async def table_doc_id(test_table_doc):
    """Returns the doc_id that contains usable tables."""
    doc_id, _, _ = test_table_doc
    return doc_id


@pytest.fixture(scope="session")
async def test_row(live_context, table_doc_id, test_table_and_col):
    """Upserts a row and returns its id."""
    table_id, col_id = test_table_and_col
    await coda.execute_action(
        "upsert_rows",
        {
            "doc_id": table_doc_id,
            "table_id_or_name": table_id,
            "rows": [{"cells": [{"column": col_id, "value": "Test Row"}]}],
        },
        live_context,
    )
    rows_result = await coda.execute_action(
        "list_rows", {"doc_id": table_doc_id, "table_id_or_name": table_id, "limit": 1}, live_context
    )
    rows = rows_result.result.data["rows"]
    if not rows:
        pytest.skip("No rows found after upsert")
    return rows[0]["id"]


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------


class TestListDocs:
    async def test_returns_docs_list(self, live_context, test_doc):
        result = await coda.execute_action("list_docs", {}, live_context)
        data = result.result.data
        assert "docs" in data
        assert isinstance(data["docs"], list)
        assert len(data["docs"]) >= 1

    async def test_filter_by_query(self, live_context, test_doc):
        result = await coda.execute_action("list_docs", {"query": "AH Integration"}, live_context)
        data = result.result.data
        assert "docs" in data
        assert any("AH Integration" in d.get("name", "") for d in data["docs"])

    async def test_is_owner_filter(self, live_context, test_doc):
        result = await coda.execute_action("list_docs", {"is_owner": True}, live_context)
        assert "docs" in result.result.data

    async def test_limit_respected(self, live_context, test_doc):
        result = await coda.execute_action("list_docs", {"limit": 1}, live_context)
        assert len(result.result.data["docs"]) <= 1


class TestGetDoc:
    async def test_returns_doc_metadata(self, live_context, test_doc):
        result = await coda.execute_action("get_doc", {"doc_id": test_doc}, live_context)
        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == test_doc

    async def test_doc_has_expected_fields(self, live_context, test_doc):
        result = await coda.execute_action("get_doc", {"doc_id": test_doc}, live_context)
        doc = result.result.data["data"]
        assert "id" in doc
        assert "name" in doc
        assert "type" in doc


class TestUpdateDoc:
    async def test_update_doc_title(self, live_context, test_doc):
        result = await coda.execute_action(
            "update_doc", {"doc_id": test_doc, "title": "AH Integration Test Doc (updated)"}, live_context
        )
        assert "data" in result.result.data


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


class TestListPages:
    async def test_returns_pages_list(self, live_context, test_doc, test_page):
        result = await coda.execute_action("list_pages", {"doc_id": test_doc}, live_context)
        data = result.result.data
        assert "pages" in data
        assert isinstance(data["pages"], list)
        assert len(data["pages"]) >= 1

    async def test_limit_respected(self, live_context, test_doc, test_page):
        result = await coda.execute_action("list_pages", {"doc_id": test_doc, "limit": 1}, live_context)
        assert len(result.result.data["pages"]) <= 1


class TestGetPage:
    async def test_returns_page_metadata(self, live_context, test_doc, test_page):
        pages = (await coda.execute_action("list_pages", {"doc_id": test_doc}, live_context)).result.data["pages"]
        if not pages:
            pytest.skip("No pages in test doc")
        page_id = pages[0]["id"]
        result = await coda.execute_action("get_page", {"doc_id": test_doc, "page_id_or_name": page_id}, live_context)
        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == page_id

    async def test_page_has_expected_fields(self, live_context, test_doc, test_page):
        pages = (await coda.execute_action("list_pages", {"doc_id": test_doc}, live_context)).result.data["pages"]
        if not pages:
            pytest.skip("No pages in test doc")
        page_id = pages[0]["id"]
        result = await coda.execute_action("get_page", {"doc_id": test_doc, "page_id_or_name": page_id}, live_context)
        page = result.result.data["data"]
        assert "id" in page
        assert "name" in page


class TestUpdatePage:
    async def test_update_page_name(self, live_context, test_doc, test_page):
        result = await coda.execute_action(
            "update_page",
            {"doc_id": test_doc, "page_id_or_name": test_page, "name": "AH Test Page (updated)"},
            live_context,
        )
        assert "data" in result.result.data


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class TestListTables:
    async def test_returns_tables_list(self, live_context, table_doc_id, test_table_and_col):
        result = await coda.execute_action("list_tables", {"doc_id": table_doc_id}, live_context)
        data = result.result.data
        assert "tables" in data
        assert isinstance(data["tables"], list)
        assert len(data["tables"]) >= 1

    async def test_limit_respected(self, live_context, table_doc_id, test_table_and_col):
        result = await coda.execute_action("list_tables", {"doc_id": table_doc_id, "limit": 1}, live_context)
        assert len(result.result.data["tables"]) <= 1


class TestGetTable:
    async def test_returns_table_metadata(self, live_context, table_doc_id, test_table_and_col):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "get_table", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == table_id

    async def test_table_has_expected_fields(self, live_context, table_doc_id, test_table_and_col):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "get_table", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        table = result.result.data["data"]
        assert "id" in table
        assert "name" in table
        assert "type" in table


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


class TestListColumns:
    async def test_returns_columns_list(self, live_context, table_doc_id, test_table_and_col):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "list_columns", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        data = result.result.data
        assert "columns" in data
        assert isinstance(data["columns"], list)
        assert len(data["columns"]) >= 1

    async def test_columns_have_expected_fields(self, live_context, table_doc_id, test_table_and_col):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "list_columns", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        col = result.result.data["columns"][0]
        assert "id" in col
        assert "name" in col


class TestGetColumn:
    async def test_returns_column_metadata(self, live_context, table_doc_id, test_table_and_col):
        table_id, col_id = test_table_and_col
        result = await coda.execute_action(
            "get_column",
            {"doc_id": table_doc_id, "table_id_or_name": table_id, "column_id_or_name": col_id},
            live_context,
        )
        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == col_id


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


class TestListRows:
    async def test_returns_rows_list(self, live_context, table_doc_id, test_table_and_col, test_row):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "list_rows", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        data = result.result.data
        assert "rows" in data
        assert isinstance(data["rows"], list)
        assert len(data["rows"]) >= 1

    async def test_limit_respected(self, live_context, table_doc_id, test_table_and_col, test_row):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "list_rows", {"doc_id": table_doc_id, "table_id_or_name": table_id, "limit": 1}, live_context
        )
        assert len(result.result.data["rows"]) <= 1


class TestGetRow:
    async def test_returns_row_data(self, live_context, table_doc_id, test_table_and_col, test_row):
        table_id, _ = test_table_and_col
        result = await coda.execute_action(
            "get_row",
            {"doc_id": table_doc_id, "table_id_or_name": table_id, "row_id_or_name": test_row},
            live_context,
        )
        data = result.result.data
        assert "data" in data
        assert data["data"]["id"] == test_row


class TestUpsertRows:
    async def test_upsert_new_row(self, live_context, table_doc_id, test_table_and_col):
        table_id, col_id = test_table_and_col
        result = await coda.execute_action(
            "upsert_rows",
            {
                "doc_id": table_doc_id,
                "table_id_or_name": table_id,
                "rows": [{"cells": [{"column": col_id, "value": "Upsert Test Row"}]}],
            },
            live_context,
        )
        assert "data" in result.result.data


class TestUpdateRow:
    async def test_update_row_value(self, live_context, table_doc_id, test_table_and_col, test_row):
        table_id, col_id = test_table_and_col
        result = await coda.execute_action(
            "update_row",
            {
                "doc_id": table_doc_id,
                "table_id_or_name": table_id,
                "row_id_or_name": test_row,
                "cells": [{"column": col_id, "value": "Updated Value"}],
            },
            live_context,
        )
        assert "data" in result.result.data


class TestDeleteRow:
    async def test_delete_row(self, live_context, table_doc_id, test_table_and_col):
        table_id, col_id = test_table_and_col
        await coda.execute_action(
            "upsert_rows",
            {
                "doc_id": table_doc_id,
                "table_id_or_name": table_id,
                "rows": [{"cells": [{"column": col_id, "value": "To Delete"}]}],
            },
            live_context,
        )
        rows_result = await coda.execute_action(
            "list_rows", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        row_id = rows_result.result.data["rows"][-1]["id"]
        result = await coda.execute_action(
            "delete_row",
            {"doc_id": table_doc_id, "table_id_or_name": table_id, "row_id_or_name": row_id},
            live_context,
        )
        assert "data" in result.result.data


class TestDeleteRows:
    async def test_delete_multiple_rows(self, live_context, table_doc_id, test_table_and_col):
        table_id, col_id = test_table_and_col
        await coda.execute_action(
            "upsert_rows",
            {
                "doc_id": table_doc_id,
                "table_id_or_name": table_id,
                "rows": [
                    {"cells": [{"column": col_id, "value": "Bulk Delete A"}]},
                    {"cells": [{"column": col_id, "value": "Bulk Delete B"}]},
                ],
            },
            live_context,
        )
        rows_result = await coda.execute_action(
            "list_rows", {"doc_id": table_doc_id, "table_id_or_name": table_id}, live_context
        )
        row_ids = [r["id"] for r in rows_result.result.data["rows"]][-2:]
        result = await coda.execute_action(
            "delete_rows",
            {"doc_id": table_doc_id, "table_id_or_name": table_id, "row_ids": row_ids},
            live_context,
        )
        assert "data" in result.result.data


# ---------------------------------------------------------------------------
# Doc / Page cleanup (create + delete tested as part of lifecycle)
# ---------------------------------------------------------------------------


class TestCreateDeleteDoc:
    async def test_create_and_delete_doc(self, live_context):
        create_result = await coda.execute_action("create_doc", {"title": "AH Temp Doc"}, live_context)
        doc_id = create_result.result.data["data"]["id"]
        assert doc_id

        delete_result = await coda.execute_action("delete_doc", {"doc_id": doc_id}, live_context)
        assert "data" in delete_result.result.data


class TestCreateDeletePage:
    async def test_create_and_delete_page(self, live_context, test_doc):
        create_result = await coda.execute_action(
            "create_page", {"doc_id": test_doc, "name": "AH Temp Page"}, live_context
        )
        page_id = create_result.result.data["data"]["id"]
        assert page_id

        delete_result = await coda.execute_action(
            "delete_page", {"doc_id": test_doc, "page_id_or_name": page_id}, live_context
        )
        assert "data" in delete_result.result.data
