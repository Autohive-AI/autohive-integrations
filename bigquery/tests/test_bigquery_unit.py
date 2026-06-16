"""
Unit tests for the BigQuery integration using mocked fetch.

These tests mock context.fetch (returning FetchResponse) and never hit the
real BigQuery API — safe for CI. Run with:

    pytest bigquery/tests/test_bigquery_unit.py -m unit
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

# Make the integration importable as the ``bigquery`` package from the repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from bigquery.bigquery import (  # noqa: E402
    bigquery as bigquery_integration,
    parse_rows,
    format_schema,
    MAX_RESULTS_LIMIT,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {}
    return ctx


def make_ctx_error(exc):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc)
    ctx.auth = {}
    return ctx


# =============================================================================
# HELPERS — parse_rows / format_schema
# =============================================================================


def test_parse_rows_simple():
    schema = {"fields": [{"name": "id", "type": "INTEGER"}, {"name": "name", "type": "STRING"}]}
    rows = [{"f": [{"v": "1"}, {"v": "Alice"}]}, {"f": [{"v": "2"}, {"v": "Bob"}]}]
    parsed = parse_rows(schema, rows)
    assert parsed == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]


def test_parse_rows_empty():
    assert parse_rows({}, []) == []
    assert parse_rows({"fields": [{"name": "x", "type": "STRING"}]}, []) == []


def test_parse_rows_repeated_scalar():
    schema = {"fields": [{"name": "tags", "type": "STRING", "mode": "REPEATED"}]}
    rows = [{"f": [{"v": [{"v": "a"}, {"v": "b"}]}]}]
    parsed = parse_rows(schema, rows)
    assert parsed == [{"tags": ["a", "b"]}]


def test_parse_rows_nested_record():
    schema = {
        "fields": [
            {
                "name": "person",
                "type": "RECORD",
                "fields": [{"name": "first", "type": "STRING"}, {"name": "last", "type": "STRING"}],
            }
        ]
    }
    rows = [{"f": [{"v": {"f": [{"v": "Jane"}, {"v": "Doe"}]}}]}]
    parsed = parse_rows(schema, rows)
    assert parsed == [{"person": {"first": "Jane", "last": "Doe"}}]


def test_parse_rows_missing_value_defaults_none():
    schema = {"fields": [{"name": "a", "type": "STRING"}, {"name": "b", "type": "STRING"}]}
    rows = [{"f": [{"v": "only-a"}]}]  # second value missing
    parsed = parse_rows(schema, rows)
    assert parsed == [{"a": "only-a", "b": None}]


def test_format_schema_basic():
    schema = {"fields": [{"name": "id", "type": "INTEGER"}, {"name": "name", "type": "STRING", "mode": "REQUIRED"}]}
    formatted = format_schema(schema)
    assert formatted == {
        "fields": [
            {"name": "id", "type": "INTEGER", "mode": "NULLABLE"},
            {"name": "name", "type": "STRING", "mode": "REQUIRED"},
        ]
    }


def test_format_schema_nested():
    schema = {
        "fields": [
            {"name": "rec", "type": "RECORD", "fields": [{"name": "inner", "type": "STRING", "description": "d"}]}
        ]
    }
    formatted = format_schema(schema)
    assert formatted["fields"][0]["fields"][0]["name"] == "inner"
    assert formatted["fields"][0]["fields"][0]["description"] == "d"


def test_format_schema_empty():
    assert format_schema({}) == {}


# =============================================================================
# RUN QUERY
# =============================================================================


@pytest.mark.asyncio
async def test_run_query_success():
    ctx = make_ctx(
        {
            "schema": {"fields": [{"name": "n", "type": "INTEGER"}]},
            "rows": [{"f": [{"v": "1"}]}],
            "jobComplete": True,
            "jobReference": {"jobId": "job_123"},
            "totalRows": "1",
            "totalBytesProcessed": "1024",
            "cacheHit": False,
        }
    )
    result = await bigquery_integration.execute_action(
        "run_query", {"project_id": "proj", "query": "SELECT 1 as n"}, ctx
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["rows"] == [{"n": "1"}]
    assert data["total_rows"] == 1
    assert data["job_id"] == "job_123"
    assert data["job_complete"] is True
    assert data["total_bytes_processed"] == 1024
    assert data["cache_hit"] is False


@pytest.mark.asyncio
async def test_run_query_dry_run():
    ctx = make_ctx({"totalBytesProcessed": "2048"})
    result = await bigquery_integration.execute_action(
        "run_query", {"project_id": "proj", "query": "SELECT *", "dry_run": True}, ctx
    )
    data = result.result.data
    assert data["dry_run"] is True
    assert data["total_bytes_processed"] == 2048
    assert data["rows"] == []
    assert data["job_complete"] is True
    # payload should carry dryRun flag
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["dryRun"] is True


@pytest.mark.asyncio
async def test_run_query_max_results_capped():
    ctx = make_ctx({"jobComplete": True, "rows": [], "schema": {}})
    await bigquery_integration.execute_action(
        "run_query", {"project_id": "proj", "query": "SELECT 1", "max_results": 999999}, ctx
    )
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["maxResults"] == MAX_RESULTS_LIMIT


@pytest.mark.asyncio
async def test_run_query_page_token_added():
    ctx = make_ctx({"jobComplete": True, "rows": [], "schema": {}, "pageToken": "tok_abc"})
    result = await bigquery_integration.execute_action("run_query", {"project_id": "proj", "query": "SELECT 1"}, ctx)
    assert result.result.data["page_token"] == "tok_abc"


@pytest.mark.asyncio
async def test_run_query_location_forwarded():
    ctx = make_ctx({"jobComplete": True, "rows": [], "schema": {}})
    await bigquery_integration.execute_action(
        "run_query", {"project_id": "proj", "query": "SELECT 1", "location": "EU"}, ctx
    )
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["location"] == "EU"


@pytest.mark.asyncio
async def test_run_query_error_returns_action_error():
    ctx = make_ctx_error(Exception("Query failed: invalid syntax"))
    result = await bigquery_integration.execute_action("run_query", {"project_id": "proj", "query": "BAD"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "invalid syntax" in result.result.message


@pytest.mark.asyncio
async def test_run_query_missing_query_validation_error():
    ctx = make_ctx({})
    result = await bigquery_integration.execute_action("run_query", {"project_id": "proj"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_run_query_completed_with_errors_no_result_returns_action_error():
    # BigQuery can return HTTP 200 with an `errors` body when a query fails at
    # runtime — must surface as ActionError, not an empty success.
    ctx = make_ctx({"jobComplete": True, "errors": [{"message": "Division by zero"}]})
    result = await bigquery_integration.execute_action("run_query", {"project_id": "proj", "query": "SELECT 1/0"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Division by zero" in result.result.message


@pytest.mark.asyncio
async def test_run_query_warnings_on_successful_query_still_succeeds():
    # `errors` can also carry non-fatal warnings; when the query produced a
    # result set (schema + rows), it must NOT be treated as a failure.
    ctx = make_ctx(
        {
            "jobComplete": True,
            "errors": [{"reason": "stopped", "message": "some rows were skipped"}],
            "schema": {"fields": [{"name": "n", "type": "INTEGER"}]},
            "rows": [{"f": [{"v": "1"}]}],
        }
    )
    result = await bigquery_integration.execute_action(
        "run_query", {"project_id": "proj", "query": "SELECT n FROM t"}, ctx
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["rows"] == [{"n": "1"}]


# =============================================================================
# GET QUERY RESULTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_query_results_success():
    ctx = make_ctx(
        {
            "schema": {"fields": [{"name": "v", "type": "STRING"}]},
            "rows": [{"f": [{"v": "x"}]}],
            "jobComplete": True,
            "totalRows": "1",
        }
    )
    result = await bigquery_integration.execute_action(
        "get_query_results", {"project_id": "proj", "job_id": "job_1"}, ctx
    )
    data = result.result.data
    assert data["rows"] == [{"v": "x"}]
    assert data["job_complete"] is True
    assert data["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_query_results_params_forwarded_and_capped():
    ctx = make_ctx({"jobComplete": True, "rows": [], "schema": {}})
    await bigquery_integration.execute_action(
        "get_query_results",
        {"project_id": "proj", "job_id": "j", "max_results": 999999, "page_token": "pt", "start_index": 0},  # nosec B105
        ctx,
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["maxResults"] == MAX_RESULTS_LIMIT
    assert params["pageToken"] == "pt"
    assert params["startIndex"] == 0


@pytest.mark.asyncio
async def test_get_query_results_error():
    ctx = make_ctx_error(Exception("Job not found"))
    result = await bigquery_integration.execute_action(
        "get_query_results", {"project_id": "proj", "job_id": "missing"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "not found" in result.result.message


@pytest.mark.asyncio
async def test_get_query_results_completed_with_errors_no_result_returns_action_error():
    ctx = make_ctx({"jobComplete": True, "errors": [{"message": "Query failed"}]})
    result = await bigquery_integration.execute_action("get_query_results", {"project_id": "proj", "job_id": "j1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Query failed" in result.result.message


@pytest.mark.asyncio
async def test_get_query_results_warnings_with_result_still_succeeds():
    ctx = make_ctx(
        {
            "jobComplete": True,
            "errors": [{"message": "warning only"}],
            "schema": {"fields": [{"name": "v", "type": "STRING"}]},
            "rows": [{"f": [{"v": "x"}]}],
        }
    )
    result = await bigquery_integration.execute_action("get_query_results", {"project_id": "proj", "job_id": "j1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["rows"] == [{"v": "x"}]


# =============================================================================
# LIST DATASETS
# =============================================================================


@pytest.mark.asyncio
async def test_list_datasets_success():
    ctx = make_ctx(
        {
            "datasets": [
                {
                    "id": "proj:ds1",
                    "datasetReference": {"datasetId": "ds1", "projectId": "proj"},
                    "friendlyName": "First",
                    "location": "US",
                    "labels": {"env": "prod"},
                }
            ],
            "nextPageToken": "next_1",
        }
    )
    result = await bigquery_integration.execute_action("list_datasets", {"project_id": "proj"}, ctx)
    data = result.result.data
    assert len(data["datasets"]) == 1
    assert data["datasets"][0]["dataset_id"] == "ds1"
    assert data["datasets"][0]["location"] == "US"
    assert data["next_page_token"] == "next_1"


@pytest.mark.asyncio
async def test_list_datasets_empty():
    ctx = make_ctx({"datasets": []})
    result = await bigquery_integration.execute_action("list_datasets", {"project_id": "proj"}, ctx)
    assert result.result.data["datasets"] == []
    assert "next_page_token" not in result.result.data


@pytest.mark.asyncio
async def test_list_datasets_filter_and_all_forwarded():
    ctx = make_ctx({"datasets": []})
    await bigquery_integration.execute_action(
        "list_datasets", {"project_id": "proj", "filter": "labels.env:prod", "all": True}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["filter"] == "labels.env:prod"
    assert params["all"] == "true"


@pytest.mark.asyncio
async def test_list_datasets_error():
    ctx = make_ctx_error(Exception("403 forbidden"))
    result = await bigquery_integration.execute_action("list_datasets", {"project_id": "proj"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "403" in result.result.message


# =============================================================================
# GET DATASET
# =============================================================================


@pytest.mark.asyncio
async def test_get_dataset_success():
    ctx = make_ctx(
        {
            "id": "proj:ds1",
            "datasetReference": {"datasetId": "ds1", "projectId": "proj"},
            "location": "EU",
            "creationTime": "12345",
            "labels": {"team": "data"},
        }
    )
    result = await bigquery_integration.execute_action("get_dataset", {"project_id": "proj", "dataset_id": "ds1"}, ctx)
    data = result.result.data
    assert data["dataset"]["dataset_id"] == "ds1"
    assert data["dataset"]["location"] == "EU"
    assert data["dataset"]["labels"] == {"team": "data"}


@pytest.mark.asyncio
async def test_get_dataset_missing_required_validation_error():
    ctx = make_ctx({})
    result = await bigquery_integration.execute_action("get_dataset", {"project_id": "proj"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_dataset_error():
    ctx = make_ctx_error(Exception("Dataset not found"))
    result = await bigquery_integration.execute_action("get_dataset", {"project_id": "proj", "dataset_id": "nope"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "not found" in result.result.message


# =============================================================================
# CREATE DATASET
# =============================================================================


@pytest.mark.asyncio
async def test_create_dataset_success():
    ctx = make_ctx(
        {
            "id": "proj:newds",
            "datasetReference": {"datasetId": "newds", "projectId": "proj"},
            "location": "US",
            "creationTime": "999",
        }
    )
    result = await bigquery_integration.execute_action(
        "create_dataset",
        {"project_id": "proj", "dataset_id": "newds", "description": "d", "labels": {"a": "b"}},
        ctx,
    )
    assert result.result.data["dataset"]["dataset_id"] == "newds"
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["datasetReference"] == {"projectId": "proj", "datasetId": "newds"}
    assert payload["description"] == "d"
    assert payload["labels"] == {"a": "b"}


@pytest.mark.asyncio
async def test_create_dataset_default_location_us():
    ctx = make_ctx({"datasetReference": {"datasetId": "x", "projectId": "proj"}})
    await bigquery_integration.execute_action("create_dataset", {"project_id": "proj", "dataset_id": "x"}, ctx)
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["location"] == "US"


@pytest.mark.asyncio
async def test_create_dataset_error():
    ctx = make_ctx_error(Exception("Already exists"))
    result = await bigquery_integration.execute_action(
        "create_dataset", {"project_id": "proj", "dataset_id": "dup"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Already exists" in result.result.message


# =============================================================================
# DELETE DATASET
# =============================================================================


@pytest.mark.asyncio
async def test_delete_dataset_success():
    ctx = make_ctx(None)  # DELETE returns no body
    result = await bigquery_integration.execute_action(
        "delete_dataset", {"project_id": "proj", "dataset_id": "ds1"}, ctx
    )
    assert result.result.data["deleted"] is True
    assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"


@pytest.mark.asyncio
async def test_delete_dataset_delete_contents_param():
    ctx = make_ctx(None)
    await bigquery_integration.execute_action(
        "delete_dataset", {"project_id": "proj", "dataset_id": "ds1", "delete_contents": True}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["deleteContents"] == "true"


@pytest.mark.asyncio
async def test_delete_dataset_error():
    ctx = make_ctx_error(Exception("not empty"))
    result = await bigquery_integration.execute_action(
        "delete_dataset", {"project_id": "proj", "dataset_id": "ds1"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "not empty" in result.result.message


# =============================================================================
# LIST TABLES
# =============================================================================


@pytest.mark.asyncio
async def test_list_tables_success():
    ctx = make_ctx(
        {
            "tables": [
                {
                    "id": "proj:ds.t1",
                    "tableReference": {"tableId": "t1", "datasetId": "ds", "projectId": "proj"},
                    "type": "TABLE",
                }
            ],
            "totalItems": 1,
            "nextPageToken": "np",
        }
    )
    result = await bigquery_integration.execute_action("list_tables", {"project_id": "proj", "dataset_id": "ds"}, ctx)
    data = result.result.data
    assert data["tables"][0]["table_id"] == "t1"
    assert data["tables"][0]["type"] == "TABLE"
    assert data["total_items"] == 1
    assert data["next_page_token"] == "np"


@pytest.mark.asyncio
async def test_list_tables_error():
    ctx = make_ctx_error(Exception("dataset gone"))
    result = await bigquery_integration.execute_action("list_tables", {"project_id": "proj", "dataset_id": "ds"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "gone" in result.result.message


# =============================================================================
# GET TABLE
# =============================================================================


@pytest.mark.asyncio
async def test_get_table_success():
    ctx = make_ctx(
        {
            "id": "proj:ds.t1",
            "tableReference": {"tableId": "t1", "datasetId": "ds", "projectId": "proj"},
            "type": "TABLE",
            "schema": {"fields": [{"name": "c", "type": "STRING"}]},
            "numRows": "100",
            "numBytes": "2048",
        }
    )
    result = await bigquery_integration.execute_action(
        "get_table", {"project_id": "proj", "dataset_id": "ds", "table_id": "t1"}, ctx
    )
    data = result.result.data
    assert data["table"]["table_id"] == "t1"
    assert data["table"]["num_rows"] == "100"
    assert data["table"]["schema"]["fields"][0]["name"] == "c"


@pytest.mark.asyncio
async def test_get_table_error():
    ctx = make_ctx_error(Exception("Table 404"))
    result = await bigquery_integration.execute_action(
        "get_table", {"project_id": "proj", "dataset_id": "ds", "table_id": "x"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "404" in result.result.message


# =============================================================================
# CREATE TABLE
# =============================================================================


@pytest.mark.asyncio
async def test_create_table_success():
    ctx = make_ctx(
        {
            "id": "proj:ds.newt",
            "tableReference": {"tableId": "newt", "datasetId": "ds", "projectId": "proj"},
            "schema": {"fields": [{"name": "id", "type": "INTEGER"}]},
            "creationTime": "111",
        }
    )
    result = await bigquery_integration.execute_action(
        "create_table",
        {
            "project_id": "proj",
            "dataset_id": "ds",
            "table_id": "newt",
            "schema": {"fields": [{"name": "id", "type": "INTEGER"}]},
        },
        ctx,
    )
    assert result.result.data["table"]["table_id"] == "newt"
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["tableReference"]["tableId"] == "newt"


@pytest.mark.asyncio
async def test_create_table_time_partitioning_camelcase():
    ctx = make_ctx({"tableReference": {"tableId": "t", "datasetId": "ds", "projectId": "proj"}})
    await bigquery_integration.execute_action(
        "create_table",
        {
            "project_id": "proj",
            "dataset_id": "ds",
            "table_id": "t",
            "schema": {"fields": []},
            "time_partitioning": {"type": "DAY", "field": "ts", "expiration_ms": 86400000},
        },
        ctx,
    )
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    tp = payload["timePartitioning"]
    assert tp["type"] == "DAY"
    assert tp["field"] == "ts"
    assert tp["expirationMs"] == "86400000"  # snake_case input converted + stringified


@pytest.mark.asyncio
async def test_create_table_missing_schema_validation_error():
    ctx = make_ctx({})
    result = await bigquery_integration.execute_action(
        "create_table", {"project_id": "proj", "dataset_id": "ds", "table_id": "t"}, ctx
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_table_error():
    ctx = make_ctx_error(Exception("schema invalid"))
    result = await bigquery_integration.execute_action(
        "create_table",
        {"project_id": "proj", "dataset_id": "ds", "table_id": "t", "schema": {"fields": []}},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "schema invalid" in result.result.message


# =============================================================================
# DELETE TABLE
# =============================================================================


@pytest.mark.asyncio
async def test_delete_table_success():
    ctx = make_ctx(None)
    result = await bigquery_integration.execute_action(
        "delete_table", {"project_id": "proj", "dataset_id": "ds", "table_id": "t1"}, ctx
    )
    assert result.result.data["deleted"] is True
    assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"


@pytest.mark.asyncio
async def test_delete_table_error():
    ctx = make_ctx_error(Exception("cannot delete"))
    result = await bigquery_integration.execute_action(
        "delete_table", {"project_id": "proj", "dataset_id": "ds", "table_id": "t1"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "cannot delete" in result.result.message


# =============================================================================
# INSERT ROWS
# =============================================================================


@pytest.mark.asyncio
async def test_insert_rows_all_success():
    ctx = make_ctx({})  # no insertErrors → all inserted
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    result = await bigquery_integration.execute_action(
        "insert_rows", {"project_id": "proj", "dataset_id": "ds", "table_id": "t", "rows": rows}, ctx
    )
    data = result.result.data
    assert data["inserted_count"] == 3
    assert data["insert_errors"] == []
    # rows wrapped in {"json": row}
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["rows"][0] == {"json": {"a": 1}}


@pytest.mark.asyncio
async def test_insert_rows_default_any_error_is_action_error():
    # With the default skip_invalid_rows=False, BigQuery fails the ENTIRE request
    # if any row is invalid — even though only one row carries an insertErrors
    # entry, zero rows are written. Must surface as ActionError, not a partial
    # success that misreports inserted_count.
    ctx = make_ctx({"insertErrors": [{"index": 1, "errors": [{"reason": "invalid", "message": "bad row"}]}]})
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    result = await bigquery_integration.execute_action(
        "insert_rows", {"project_id": "proj", "dataset_id": "ds", "table_id": "t", "rows": rows}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "no rows were written" in result.result.message
    assert "bad row" in result.result.message  # first row's error detail surfaced


@pytest.mark.asyncio
async def test_insert_rows_skip_invalid_partial_success():
    # With skip_invalid_rows=True, valid rows are inserted and invalid ones are
    # skipped → a real partial success, returned as an ACTION result carrying
    # inserted_count + insert_errors (NOT an ActionError).
    ctx = make_ctx({"insertErrors": [{"index": 1, "errors": [{"reason": "invalid", "message": "bad row"}]}]})
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    result = await bigquery_integration.execute_action(
        "insert_rows",
        {
            "project_id": "proj",
            "dataset_id": "ds",
            "table_id": "t",
            "rows": rows,
            "skip_invalid_rows": True,
        },
        ctx,
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["inserted_count"] == 2  # one row skipped
    assert len(data["insert_errors"]) == 1
    assert data["insert_errors"][0]["index"] == 1


@pytest.mark.asyncio
async def test_insert_rows_skip_invalid_all_rejected_returns_action_error():
    # skip_invalid_rows=True but every row is invalid → nothing was inserted, so
    # surface as ActionError rather than an empty success.
    ctx = make_ctx(
        {
            "insertErrors": [
                {"index": 0, "errors": [{"reason": "invalid", "message": "bad row"}]},
                {"index": 1, "errors": [{"reason": "invalid", "message": "also bad"}]},
            ]
        }
    )
    rows = [{"a": 1}, {"a": 2}]
    result = await bigquery_integration.execute_action(
        "insert_rows",
        {
            "project_id": "proj",
            "dataset_id": "ds",
            "table_id": "t",
            "rows": rows,
            "skip_invalid_rows": True,
        },
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "rejected all 2 row(s)" in result.result.message
    assert "bad row" in result.result.message  # first row's error detail surfaced


@pytest.mark.asyncio
async def test_insert_rows_error():
    ctx = make_ctx_error(Exception("table missing"))
    result = await bigquery_integration.execute_action(
        "insert_rows", {"project_id": "proj", "dataset_id": "ds", "table_id": "t", "rows": [{"a": 1}]}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "table missing" in result.result.message


# =============================================================================
# LIST JOBS
# =============================================================================


@pytest.mark.asyncio
async def test_list_jobs_success():
    ctx = make_ctx(
        {
            "jobs": [
                {
                    "id": "proj:job1",
                    "jobReference": {"jobId": "job1", "projectId": "proj", "location": "US"},
                    "status": {"state": "DONE"},
                    "statistics": {"creationTime": "100", "totalBytesProcessed": "500"},
                    "user_email": "me@example.com",
                }
            ],
            "nextPageToken": "njp",
        }
    )
    result = await bigquery_integration.execute_action("list_jobs", {"project_id": "proj"}, ctx)
    data = result.result.data
    assert data["jobs"][0]["job_id"] == "job1"
    assert data["jobs"][0]["state"] == "DONE"
    assert data["jobs"][0]["user_email"] == "me@example.com"
    assert data["next_page_token"] == "njp"


@pytest.mark.asyncio
async def test_list_jobs_state_filter_forwarded():
    ctx = make_ctx({"jobs": []})
    await bigquery_integration.execute_action(
        "list_jobs", {"project_id": "proj", "state_filter": "running", "all_users": True}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["stateFilter"] == "running"
    assert params["allUsers"] == "true"


@pytest.mark.asyncio
async def test_list_jobs_error():
    ctx = make_ctx_error(Exception("jobs unavailable"))
    result = await bigquery_integration.execute_action("list_jobs", {"project_id": "proj"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "unavailable" in result.result.message


# =============================================================================
# GET JOB
# =============================================================================


@pytest.mark.asyncio
async def test_get_job_success():
    ctx = make_ctx(
        {
            "id": "proj:job1",
            "jobReference": {"jobId": "job1", "projectId": "proj", "location": "US"},
            "status": {"state": "DONE", "errors": []},
            "statistics": {"creationTime": "100", "query": {"totalBytesBilled": "1000", "cacheHit": True}},
            "configuration": {"query": {"query": "SELECT 1"}},
            "user_email": "me@example.com",
        }
    )
    result = await bigquery_integration.execute_action("get_job", {"project_id": "proj", "job_id": "job1"}, ctx)
    data = result.result.data
    assert data["job"]["job_id"] == "job1"
    assert data["job"]["state"] == "DONE"
    assert data["job"]["total_bytes_billed"] == "1000"
    assert data["job"]["cache_hit"] is True


@pytest.mark.asyncio
async def test_get_job_location_forwarded():
    ctx = make_ctx({"jobReference": {"jobId": "j"}, "status": {}, "statistics": {}})
    await bigquery_integration.execute_action(
        "get_job", {"project_id": "proj", "job_id": "j", "location": "asia-northeast1"}, ctx
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["location"] == "asia-northeast1"


@pytest.mark.asyncio
async def test_get_job_error():
    ctx = make_ctx_error(Exception("job 404"))
    result = await bigquery_integration.execute_action("get_job", {"project_id": "proj", "job_id": "x"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "404" in result.result.message


# =============================================================================
# LIST PROJECTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_projects_success():
    ctx = make_ctx(
        {
            "projects": [
                {
                    "id": "proj",
                    "projectReference": {"projectId": "proj"},
                    "numericId": "123",
                    "friendlyName": "My Project",
                }
            ],
            "nextPageToken": "pnt",
        }
    )
    result = await bigquery_integration.execute_action("list_projects", {}, ctx)
    data = result.result.data
    assert data["projects"][0]["project_id"] == "proj"
    assert data["projects"][0]["friendly_name"] == "My Project"
    assert data["next_page_token"] == "pnt"


@pytest.mark.asyncio
async def test_list_projects_empty():
    ctx = make_ctx({"projects": []})
    result = await bigquery_integration.execute_action("list_projects", {}, ctx)
    assert result.result.data["projects"] == []
    assert "next_page_token" not in result.result.data


@pytest.mark.asyncio
async def test_list_projects_error():
    ctx = make_ctx_error(Exception("auth expired"))
    result = await bigquery_integration.execute_action("list_projects", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "auth expired" in result.result.message
