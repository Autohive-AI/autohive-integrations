import re
import threading
from unittest.mock import patch

import certifi
import psycopg
import pytest
from autohive_integrations_sdk import ResultType

from db_engines import ConnectionConfigError
from sql_database import sql_database

pytestmark = pytest.mark.unit

QUERY_RESULT = {
    "columns": ["id"],
    "rows": [{"id": 1}],
    "row_count": 1,
    "truncated": False,
    "truncation_reason": None,
    "values_truncated": False,
}
WRITE_RESULT = {"rows_affected": 1, "columns": [], "returned_rows": [], "returned_rows_truncated": False}
POSTGRES = "postgresql://reader:s3cret-pass@db.example.com:5432/app"


def _public_ca_pem() -> str:
    with open(certifi.where()) as handle:
        return re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", handle.read(), re.S).group(0)


# ---- query ----


async def test_query_runs_validated_sql_with_defaults(mock_context):
    with patch("sql_database.run_query", return_value=QUERY_RESULT) as run_query:
        result = await sql_database.execute_action("query", {"sql": "SELECT TOP 1 id FROM dbo.t"}, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data == QUERY_RESULT
    engine, connection_string, sql, parameters, max_rows, timeout, ca_file = run_query.call_args.args
    assert (engine, sql, parameters, max_rows, timeout, ca_file) == (
        "sqlserver",
        "SELECT TOP 1 id FROM dbo.t",
        None,
        100,
        30,
        None,
    )
    assert connection_string.startswith("Server=tcp:db.example.com")


async def test_query_passes_parameters_and_limits(mock_context):
    inputs = {"sql": "SELECT id FROM t WHERE email = %s", "parameters": ["a@b.c"], "max_rows": 5, "timeout_seconds": 9}
    with patch("sql_database.run_query", return_value=QUERY_RESULT) as run_query:
        await sql_database.execute_action("query", inputs, mock_context)
    assert run_query.call_args.args[3:6] == (["a@b.c"], 5, 9)


async def test_query_treats_empty_parameters_as_none(mock_context):
    with patch("sql_database.run_query", return_value=QUERY_RESULT) as run_query:
        result = await sql_database.execute_action(
            "query", {"sql": "SELECT id FROM t WHERE name LIKE 'a%'", "parameters": []}, mock_context
        )
    assert result.type == ResultType.ACTION
    assert run_query.call_args.args[3] is None


@pytest.mark.parametrize("database_type", ["PostgreSQL", "Postgres", "postgresql", "pg"])
async def test_query_accepts_database_type_in_any_case(sql_context, database_type):
    with patch("sql_database.run_query", return_value=QUERY_RESULT) as run_query:
        result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, sql_context(database_type, POSTGRES))
    assert result.type == ResultType.ACTION
    assert run_query.call_args.args[0] == "postgresql"


@pytest.mark.parametrize(
    "database_type,sql",
    [
        ("sqlserver", "SELECT 1 DELETE FROM dbo.t"),
        ("postgresql", "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d"),
        ("mysql", "SELECT * FROM t /*!50000 INTO OUTFILE '/tmp/x' */"),
    ],
)
async def test_query_rejects_writes_without_touching_the_database(sql_context, database_type, sql):
    context = sql_context(database_type, "unused")
    with patch("sql_database.run_query") as run_query:
        result = await sql_database.execute_action("query", {"sql": sql}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Query rejected: ")
    run_query.assert_not_called()


async def test_query_reports_database_errors(mock_context):
    with patch("sql_database.run_query", side_effect=psycopg.errors.UndefinedTable('relation "t" does not exist')):
        result = await sql_database.execute_action("query", {"sql": "SELECT * FROM t"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == 'Database error: relation "t" does not exist'


async def test_errors_never_include_the_password(sql_context):
    context = sql_context("postgresql", POSTGRES)
    with patch("sql_database.run_query", side_effect=psycopg.OperationalError("auth failed for s3cret-pass")):
        database_error = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    with patch("sql_database.run_query", side_effect=RuntimeError(f"cannot use {POSTGRES}")):
        unexpected = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)

    assert database_error.result.message == "Database error: auth failed for [redacted]"
    assert unexpected.type == ResultType.ACTION_ERROR
    assert unexpected.result.message == "Unexpected error (RuntimeError): cannot use [redacted]"


async def test_connection_setting_errors_are_redacted(sql_context):
    context = sql_context("postgresql", POSTGRES)
    with patch("sql_database.run_query", side_effect=ConnectionConfigError("bad value s3cret-pass")):
        result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.result.message == "bad value [redacted]"


async def test_sql_checks_and_database_work_run_off_the_event_loop(sql_context):
    threads = {}

    def record(name, value):
        def side_effect(*args):
            threads[name] = threading.current_thread()
            return value

        return side_effect

    with (
        patch("sql_database.check_read_only_query", side_effect=record("guard", None)),
        patch("sql_database.run_query", side_effect=record("sqlserver", QUERY_RESULT)),
    ):
        await sql_database.execute_action("query", {"sql": "SELECT 1"}, sql_context("sqlserver", "Server=h;User ID=u"))
    with patch("sql_database.run_query", side_effect=record("postgresql", QUERY_RESULT)):
        await sql_database.execute_action("query", {"sql": "SELECT 1"}, sql_context("postgresql", POSTGRES))

    assert threading.main_thread() not in threads.values()
    # SQL Server statements queue on their own thread; other engines use the shared pool.
    assert threads["sqlserver"].name.startswith("sql-database-sqlserver")
    assert not threads["postgresql"].name.startswith("sql-database-sqlserver")


async def test_query_reports_invalid_connection_settings(sql_context):
    result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, sql_context("oracle", "whatever"))
    assert result.type == ResultType.ACTION_ERROR
    assert "Unsupported database type 'oracle'" in result.result.message


async def test_query_requires_connection_string(sql_context):
    context = sql_context("postgresql", "   ")
    result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.type == ResultType.VALIDATION_ERROR
    assert result.result["source"] == "auth"


async def test_query_invalid_mysql_url_does_not_echo_credentials(sql_context):
    context = sql_context("mysql", "mysql://reader:synthetic-secret@℀/db")
    result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "could not be parsed" in result.result.message
    assert "synthetic-secret" not in result.result.message


async def test_query_validates_max_rows_range(mock_context):
    result = await sql_database.execute_action("query", {"sql": "SELECT 1", "max_rows": 0}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


async def test_query_passes_a_custom_ca_certificate_file(sql_context):
    # Single-line form fields drop the PEM newlines; the certificate must still load.
    pasted = _public_ca_pem().replace("\n", "")
    context = sql_context("postgresql", POSTGRES, ca_certificate=pasted)
    with patch("sql_database.run_query", return_value=QUERY_RESULT) as run_query:
        result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.type == ResultType.ACTION
    with open(run_query.call_args.args[6]) as handle:
        assert handle.read().startswith("-----BEGIN CERTIFICATE-----\n")


async def test_query_rejects_an_invalid_ca_certificate(sql_context):
    context = sql_context("postgresql", POSTGRES, ca_certificate="not a certificate")
    result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "BEGIN CERTIFICATE" in result.result.message


# ---- execute ----


async def test_execute_runs_write_and_reports_statement_type(mock_context):
    inputs = {"sql": "UPDATE dbo.t SET name = %s WHERE id = %s", "parameters": ["b", 1]}
    with patch("sql_database.run_write", return_value=WRITE_RESULT) as run_write:
        result = await sql_database.execute_action("execute", inputs, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data == {"statement_type": "UPDATE", **WRITE_RESULT}
    assert run_write.call_args.args[2:] == ("UPDATE dbo.t SET name = %s WHERE id = %s", ["b", 1], 30, None)


@pytest.mark.parametrize("access_mode", [None, "", "read-only", "Read Only", "READ_ONLY"])
async def test_execute_is_disabled_on_read_only_connections(sql_context, access_mode):
    settings = {} if access_mode is None else {"access_mode": access_mode}
    context = sql_context("postgresql", POSTGRES, **settings)
    with patch("sql_database.run_write") as run_write:
        result = await sql_database.execute_action("execute", {"sql": "DELETE FROM t WHERE id = 1"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "read-only" in result.result.message
    run_write.assert_not_called()


@pytest.mark.parametrize("access_mode", ["read-write", "Read Write", "READ_WRITE"])
async def test_execute_runs_on_read_write_connections(sql_context, access_mode):
    context = sql_context("postgresql", POSTGRES, access_mode=access_mode)
    with patch("sql_database.run_write", return_value=WRITE_RESULT):
        result = await sql_database.execute_action("execute", {"sql": "DELETE FROM t WHERE id = 1"}, context)
    assert result.type == ResultType.ACTION


async def test_invalid_access_mode_is_reported(sql_context):
    context = sql_context("postgresql", POSTGRES, access_mode="admin")
    result = await sql_database.execute_action("query", {"sql": "SELECT 1"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Use read-only or read-write" in result.result.message


async def test_execute_requires_where_unless_allowed(mock_context):
    with patch("sql_database.run_write", return_value=WRITE_RESULT) as run_write:
        rejected = await sql_database.execute_action("execute", {"sql": "DELETE FROM dbo.t"}, mock_context)
        allowed = await sql_database.execute_action(
            "execute", {"sql": "DELETE FROM dbo.t", "allow_all_rows": True}, mock_context
        )
    assert rejected.type == ResultType.ACTION_ERROR
    assert "without a WHERE clause" in rejected.result.message
    assert allowed.type == ResultType.ACTION
    run_write.assert_called_once()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE dbo.t",
        "SELECT * FROM dbo.t",
        "UPDATE t SET a = 1 WHERE id = 1 DROP TABLE t",
        "INSERT INTO t SELECT 1 DELETE FROM t",
    ],
)
async def test_execute_rejects_out_of_scope_sql(mock_context, sql):
    with patch("sql_database.run_write") as run_write:
        result = await sql_database.execute_action("execute", {"sql": sql}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Statement rejected: ")
    run_write.assert_not_called()


async def test_execute_reports_database_errors(mock_context):
    with patch("sql_database.run_write", side_effect=psycopg.errors.UniqueViolation("duplicate key")):
        result = await sql_database.execute_action(
            "execute", {"sql": "INSERT INTO t (id) VALUES (%s)", "parameters": [1]}, mock_context
        )
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Database error: duplicate key"
