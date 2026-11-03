"""
Live tests for the SQL Database integration against real database servers.

These tests create, change and drop a table called autohive_sqldb_test, so only
point them at disposable databases. tests/docker-compose.yml starts one of each:

    docker compose -f sql-database/tests/docker-compose.yml up -d
    pytest sql-database/tests/test_sql_database_integration.py -m integration

Each engine is skipped unless its SQL_DATABASE_TEST_* variable is set (see .env.example).
"""

import json
import os
import time

import psycopg
import pymysql
import pytest
from autohive_integrations_sdk import ResultType

import db_engines
from db_engines import mysql_connect_params, postgres_connect_params
from sql_database import sql_database
from sql_guard import SqlRejectedError, check_read_only_query

pytestmark = [pytest.mark.integration, pytest.mark.destructive]

ENGINES = {
    # name: (database_type, environment variable)
    "sqlserver": ("sqlserver", "SQL_DATABASE_TEST_SQLSERVER"),
    "postgresql": ("postgresql", "SQL_DATABASE_TEST_POSTGRESQL"),
    "mysql": ("mysql", "SQL_DATABASE_TEST_MYSQL"),
    "mariadb": ("mysql", "SQL_DATABASE_TEST_MARIADB"),
}

SETUP = {
    "sqlserver": [
        "IF OBJECT_ID('autohive_sqldb_test') IS NOT NULL DROP TABLE autohive_sqldb_test",
        "CREATE TABLE autohive_sqldb_test "
        "(id INT PRIMARY KEY, name NVARCHAR(50), amount DECIMAL(10, 2), created_at DATETIME2)",
    ],
    "postgresql": [
        "DROP TABLE IF EXISTS autohive_sqldb_test",
        "CREATE TABLE autohive_sqldb_test "
        "(id INT PRIMARY KEY, name VARCHAR(50), amount DECIMAL(10, 2), created_at TIMESTAMP)",
    ],
    "mysql": [
        "DROP TABLE IF EXISTS autohive_sqldb_test",
        "CREATE TABLE autohive_sqldb_test "
        "(id INT PRIMARY KEY, name VARCHAR(50), amount DECIMAL(10, 2), created_at DATETIME)",
    ],
}
SEED = (
    "INSERT INTO autohive_sqldb_test (id, name, amount, created_at) VALUES "
    "(1, 'alpha', 10.50, '2026-01-02 03:04:05'), (2, 'beta', 20.00, '2026-02-03 04:05:06'), "
    "(3, '50% off', 30.25, '2026-03-04 05:06:07')"
)
# Queries that take well over a second on an otherwise idle server.
SLOW_QUERY = {
    "sqlserver": "SELECT COUNT_BIG(*) FROM sys.all_objects a CROSS JOIN sys.all_objects b "
    "CROSS JOIN sys.all_objects c WHERE (a.object_id + b.object_id + c.object_id) % 7 = 3",
    "postgresql": "SELECT pg_sleep(5)",
    "mysql": "SELECT COUNT(*) FROM information_schema.columns a, information_schema.columns b, "
    "information_schema.columns c",
}


def _admin(database_type: str, connection_string: str, statements):
    """Run setup SQL directly through the driver (the execute action does not allow DDL)."""
    if database_type == "postgresql":
        with psycopg.connect(**postgres_connect_params(connection_string), autocommit=True) as conn:
            for sql in statements:
                conn.execute(sql)
        return
    if database_type == "mysql":
        conn = pymysql.connect(**mysql_connect_params(connection_string), autocommit=True)
    else:
        conn = db_engines._sqlserver_connect(connection_string, 30)
        conn.autocommit(True)
    try:
        cursor = conn.cursor()
        for sql in statements:
            cursor.execute(sql)
    finally:
        conn.close()


def _count(database_type: str, connection_string: str) -> int:
    result = db_engines.run_query(
        database_type, connection_string, "SELECT COUNT(*) AS n FROM autohive_sqldb_test", None, 1, 30
    )
    return int(result["rows"][0]["n"])


@pytest.fixture(params=list(ENGINES))
def db(request, sql_context):
    database_type, variable = ENGINES[request.param]
    connection_string = os.environ.get(variable, "").strip()
    if not connection_string:
        pytest.skip(f"{variable} not set")
    _admin(database_type, connection_string, SETUP[database_type] + [SEED])
    yield database_type, connection_string, sql_context(database_type, connection_string, access_mode="read-write")
    _admin(database_type, connection_string, [SETUP[database_type][0]])


# ---- query ----


async def test_query_returns_rows_as_json_safe_values(db):
    database_type, _, context = db
    result = await sql_database.execute_action(
        "query", {"sql": "SELECT id, name, amount, created_at FROM autohive_sqldb_test ORDER BY id"}, context
    )
    assert result.type == ResultType.ACTION, result.result
    data = result.result.data
    assert data["columns"] == ["id", "name", "amount", "created_at"]
    assert data["row_count"] == 3 and data["truncated"] is False
    assert data["rows"][0] == {"id": 1, "name": "alpha", "amount": "10.50", "created_at": "2026-01-02T03:04:05"}


async def test_query_binds_parameters_and_keeps_literal_percent(db):
    _, _, context = db
    result = await sql_database.execute_action(
        "query",
        {"sql": "SELECT id FROM autohive_sqldb_test WHERE name LIKE '%%off' AND amount > %s", "parameters": [20]},
        context,
    )
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["rows"] == [{"id": 3}]


async def test_query_parameters_are_not_executed_as_sql(db):
    _, _, context = db
    hostile = "x'; DELETE FROM autohive_sqldb_test; --"
    result = await sql_database.execute_action(
        "query", {"sql": "SELECT id FROM autohive_sqldb_test WHERE name = %s", "parameters": [hostile]}, context
    )
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["rows"] == []
    assert _count(db[0], db[1]) == 3


async def test_query_rejects_parameters_inside_quoted_sql(db):
    _, _, context = db
    result = await sql_database.execute_action(
        "query",
        {
            "sql": "SELECT '%s'",
            "parameters": ["; COMMIT DELETE FROM autohive_sqldb_test COMMIT --"],
        },
        context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "standalone values" in result.result.message
    assert _count(db[0], db[1]) == 3


async def test_query_truncates_at_max_rows(db):
    _, _, context = db
    result = await sql_database.execute_action(
        "query", {"sql": "SELECT id FROM autohive_sqldb_test ORDER BY id", "max_rows": 2}, context
    )
    assert result.result.data["rows"] == [{"id": 1}, {"id": 2}]
    assert result.result.data["truncated"] is True


def test_mysql_truncation_does_not_drain_rows_with_explicit_limit(db, monkeypatch):
    database_type, connection_string, _ = db
    if database_type != "mysql":
        pytest.skip("MySQL/MariaDB streaming cleanup")
    collect = db_engines._collect
    read_packet = pymysql.connections.Connection._read_packet
    limit_reached = False
    drained_packets = 0

    def collect_then_flag(*args):
        nonlocal limit_reached
        result = collect(*args)
        limit_reached = True
        return result

    def count_drain(connection, *args, **kwargs):
        nonlocal drained_packets
        if limit_reached:
            drained_packets += 1
        return read_packet(connection, *args, **kwargs)

    monkeypatch.setattr(db_engines, "_collect", collect_then_flag)
    monkeypatch.setattr(pymysql.connections.Connection, "_read_packet", count_drain)
    data = db_engines.run_query(
        database_type, connection_string, "SELECT id FROM autohive_sqldb_test ORDER BY id LIMIT 100", None, 1, 30
    )
    assert data["rows"] == [{"id": 1}]
    assert data["truncated"] is True
    assert drained_packets == 0


def test_mysql_normalizes_nonstandard_string_modes(db, monkeypatch):
    database_type, connection_string, _ = db
    if database_type != "mysql":
        pytest.skip("MySQL/MariaDB string parsing modes")
    connect = db_engines._mysql_connect

    def connect_with_ansi_mode(*args):
        conn = connect(*args)
        cursor = conn.cursor()
        cursor.execute("SET SESSION sql_mode = 'ANSI,NO_BACKSLASH_ESCAPES'")
        cursor.close()
        return conn

    monkeypatch.setattr(db_engines, "_mysql_connect", connect_with_ansi_mode)
    data = db_engines.run_query(
        database_type, connection_string, "SELECT 'it\\'s' AS note, \"text\" AS label", None, 1, 30
    )
    assert data["rows"] == [{"note": "it's", "label": "text"}]


async def test_query_times_out(db):
    database_type, _, context = db
    started = time.monotonic()
    result = await sql_database.execute_action(
        "query", {"sql": SLOW_QUERY[database_type], "timeout_seconds": 1}, context
    )
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Database error:")
    assert time.monotonic() - started < 15


async def test_query_rejection_leaves_data_untouched(db):
    database_type, connection_string, context = db
    sql = {
        "sqlserver": "SELECT 1 DELETE FROM autohive_sqldb_test",
        "postgresql": "WITH d AS (DELETE FROM autohive_sqldb_test RETURNING *) SELECT * FROM d",
        "mysql": "SELECT * FROM autohive_sqldb_test /*!50000 FOR UPDATE */",
    }[database_type]
    result = await sql_database.execute_action("query", {"sql": sql}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Query rejected:")
    assert _count(database_type, connection_string) == 3


TYPE_QUERIES = {
    "sqlserver": (
        "SELECT CAST('03:04:05' AS TIME) AS t, CAST(1 AS BIT) AS flag",
        {"t": "03:04:05", "flag": True},
    ),
    "postgresql": (
        "SELECT 'infinity'::timestamp AS inf, '0044-03-15 BC'::date AS bc, '24:00:00'::time AS midnight, "
        "interval '1 day 2 hours' AS span, '{\"a\": 1}'::jsonb AS doc",
        {"inf": "infinity", "bc": "0044-03-15 BC", "midnight": "24:00:00", "span": "P1DT2H", "doc": {"a": 1}},
    ),
}


async def test_query_returns_edge_case_types(db):
    database_type, connection_string, context = db
    if database_type == "mysql":
        mariadb = connection_string.startswith("mariadb")
        _admin(
            database_type,
            connection_string,
            [
                "DROP TABLE IF EXISTS autohive_sqldb_types",
                "CREATE TABLE autohive_sqldb_types (flag BIT(1), mask BIT(10), span TIME, doc JSON)",
                "INSERT INTO autohive_sqldb_types VALUES (1, b'1000000001', '-838:00:00', '{\"a\": 1}')",
            ],
        )
        sql = "SELECT flag, mask, span, doc FROM autohive_sqldb_types"
        # MariaDB stores JSON as LONGTEXT, so it arrives as text.
        expected = {"flag": 1, "mask": 513, "span": "-838:00:00", "doc": '{"a": 1}' if mariadb else {"a": 1}}
    else:
        sql, expected = TYPE_QUERIES[database_type]
    try:
        result = await sql_database.execute_action("query", {"sql": sql}, context)
    finally:
        if database_type == "mysql":
            _admin(database_type, connection_string, ["DROP TABLE autohive_sqldb_types"])
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["rows"] == [expected]


LONG_VALUE = {
    "sqlserver": "SELECT REPLICATE(CAST('x' AS NVARCHAR(MAX)), 70000) AS v",
    "postgresql": "SELECT repeat('x', 70000) AS v",
    "mysql": "SELECT REPEAT('x', 70000) AS v",
}
WIDE_ROWS = {
    "sqlserver": "SELECT TOP 100 REPLICATE(CAST('x' AS NVARCHAR(MAX)), 60000) AS v FROM sys.all_objects",
    "postgresql": "SELECT repeat('x', 60000) AS v FROM generate_series(1, 100)",
    "mysql": "WITH RECURSIVE n (i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 100) "
    "SELECT REPEAT('x', 60000) AS v FROM n",
}


async def test_long_values_are_cut(db):
    database_type, _, context = db
    result = await sql_database.execute_action("query", {"sql": LONG_VALUE[database_type]}, context)
    assert result.type == ResultType.ACTION, result.result
    assert len(result.result.data["rows"][0]["v"]) == db_engines.MAX_VALUE_CHARS
    assert result.result.data["values_truncated"] is True


async def test_results_stop_at_the_size_limit(db):
    database_type, _, context = db
    result = await sql_database.execute_action("query", {"sql": WIDE_ROWS[database_type], "max_rows": 1000}, context)
    assert result.type == ResultType.ACTION, result.result
    data = result.result.data
    assert data["truncation_reason"] == "max_bytes" and data["truncated"] is True
    assert 60 < data["row_count"] < 100
    assert len(json.dumps(data)) <= db_engines.MAX_RESPONSE_BYTES


async def test_database_errors_are_readable(db):
    _, _, context = db
    result = await sql_database.execute_action("query", {"sql": "SELECT * FROM no_such_table_here"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "no_such_table_here" in result.result.message


# ---- Database-level read-only layer, with the static guard bypassed ----


@pytest.mark.parametrize(
    "family,sql",
    [
        ("postgresql", "DELETE FROM autohive_sqldb_test"),
        ("postgresql", "WITH d AS (DELETE FROM autohive_sqldb_test RETURNING *) SELECT * FROM d"),
        ("postgresql", "SET TRANSACTION READ WRITE; DELETE FROM autohive_sqldb_test"),
        ("postgresql", "COMMIT; DELETE FROM autohive_sqldb_test"),
        ("postgresql", "SELECT * INTO autohive_sqldb_test_copy FROM autohive_sqldb_test"),
        ("mysql", "DELETE FROM autohive_sqldb_test"),
        ("mysql", "DROP TABLE autohive_sqldb_test"),
        ("mysql", "CREATE TEMPORARY TABLE autohive_sqldb_test_tmp (id INT)"),
        ("mysql", "SELECT 1; DELETE FROM autohive_sqldb_test"),
        ("sqlserver", "SELECT 1 DELETE FROM autohive_sqldb_test"),
        ("sqlserver", "SELECT 1 COMMIT DELETE FROM autohive_sqldb_test"),
        ("sqlserver", "SELECT 1 ROLLBACK DELETE FROM autohive_sqldb_test"),
        ("sqlserver", "DELETE FROM autohive_sqldb_test; SELECT 1"),
    ],
)
def test_runtime_layer_blocks_writes_without_the_guard(db, family, sql):
    database_type, connection_string, _ = db
    if database_type != family:
        pytest.skip(f"{family} case")
    try:
        db_engines.run_query(database_type, connection_string, sql, None, 10, 30)
    except db_engines.DATABASE_ERRORS:
        pass  # PostgreSQL and MySQL refuse the write; SQL Server discards it on close
    assert _count(database_type, connection_string) == 3


def test_sqlserver_runtime_layer_alone_cannot_stop_repeated_commit(db):
    """SQL Server has no read-only transaction, so a second COMMIT persists the write.

    This is why the static guard (and a read-only login) matter most on SQL Server.
    """
    database_type, connection_string, _ = db
    if database_type != "sqlserver":
        pytest.skip("SQL Server only")
    sql = "SELECT 1 COMMIT DELETE FROM autohive_sqldb_test COMMIT"
    with pytest.raises(SqlRejectedError):
        check_read_only_query(sql, "tsql")
    db_engines.run_query(database_type, connection_string, sql, None, 10, 30)
    assert _count(database_type, connection_string) == 0


def test_postgres_requires_tls_unless_disabled(db):
    database_type, connection_string, _ = db
    if database_type != "postgresql" or "sslmode=disable" not in connection_string:
        pytest.skip("needs a PostgreSQL server without TLS and an explicit sslmode=disable")
    default = connection_string.replace("?sslmode=disable", "").replace("&sslmode=disable", "")
    with pytest.raises(db_engines.DATABASE_ERRORS, match="SSL"):
        db_engines.run_query(database_type, default, "SELECT 1 AS a", None, 1, 10)


def test_mysql_verifies_the_server_against_a_custom_ca(db):
    database_type, connection_string, _ = db
    ca_path = os.environ.get("SQL_DATABASE_TEST_MYSQL_CA", "").strip()
    if database_type != "mysql" or connection_string.startswith("mariadb") or not ca_path:
        pytest.skip("needs SQL_DATABASE_TEST_MYSQL_CA (the MySQL container's ca.pem)")
    with open(ca_path) as handle:
        ca_file = db_engines.ca_certificate_file(handle.read())
    verify_ca = connection_string + ("&" if "?" in connection_string else "?") + "ssl-mode=VERIFY_CA"
    assert db_engines.run_query(database_type, verify_ca, "SELECT 1 AS a", None, 1, 10, ca_file)["rows"] == [{"a": 1}]
    # With a CA the default is VERIFY_IDENTITY, and the auto-generated certificate
    # was not issued for this host name.
    with pytest.raises(db_engines.DATABASE_ERRORS):
        db_engines.run_query(database_type, connection_string, "SELECT 1 AS a", None, 1, 10, ca_file)
    with open(db_engines.certifi.where()) as handle:
        unrelated_ca = db_engines.ca_certificate_file(
            handle.read().split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----"
        )
    with pytest.raises(db_engines.DATABASE_ERRORS):
        db_engines.run_query(database_type, verify_ca, "SELECT 1 AS a", None, 1, 10, unrelated_ca)
    # ssl-mode=REQUIRED alone skips verification, but a custom CA is still checked.
    required = connection_string + ("&" if "?" in connection_string else "?") + "ssl-mode=REQUIRED"
    assert db_engines.run_query(database_type, required, "SELECT 1 AS a", None, 1, 10, ca_file)["rows"] == [{"a": 1}]
    with pytest.raises(db_engines.DATABASE_ERRORS):
        db_engines.run_query(database_type, required, "SELECT 1 AS a", None, 1, 10, unrelated_ca)


def test_sqlserver_verifies_certificates_by_default(db):
    database_type, connection_string, _ = db
    local = "127.0.0.1" in connection_string or "localhost" in connection_string
    if database_type != "sqlserver" or not local:
        pytest.skip("needs the self-signed SQL Server from docker-compose.yml")
    verified = connection_string.replace("TrustServerCertificate=True", "TrustServerCertificate=False")
    with pytest.raises(db_engines.DATABASE_ERRORS):
        db_engines.run_query(database_type, verified, "SELECT 1 AS a", None, 1, 10)


def test_sqlserver_custom_ca_is_checked_even_when_the_certificate_is_trusted(db):
    database_type, connection_string, _ = db
    if database_type != "sqlserver" or "TrustServerCertificate=True" not in connection_string:
        pytest.skip("needs the self-signed SQL Server from docker-compose.yml")
    assert db_engines.run_query(database_type, connection_string, "SELECT 1 AS a", None, 1, 10)["rows"] == [{"a": 1}]
    with open(db_engines.certifi.where()) as handle:
        unrelated_ca = db_engines.ca_certificate_file(
            handle.read().split("-----END CERTIFICATE-----")[0] + "-----END CERTIFICATE-----"
        )
    with pytest.raises(db_engines.DATABASE_ERRORS):
        db_engines.run_query(database_type, connection_string, "SELECT 1 AS a", None, 1, 10, unrelated_ca)


def test_sqlserver_reader_permissions_hold_when_static_checks_are_bypassed(db, monkeypatch):
    database_type, connection_string, _ = db
    if database_type != "sqlserver":
        pytest.skip("SQL Server reader permissions")
    _admin(database_type, connection_string, ["CREATE USER autohive_sqldb_test_reader WITHOUT LOGIN"])
    try:
        _admin(
            database_type,
            connection_string,
            ["GRANT SELECT ON dbo.autohive_sqldb_test TO autohive_sqldb_test_reader"],
        )
        connect = db_engines._sqlserver_connect

        def connect_as_reader(*args):
            conn = connect(*args)
            conn.cursor().execute("EXECUTE AS USER = 'autohive_sqldb_test_reader'")
            return conn

        with monkeypatch.context() as scope:
            scope.setattr(db_engines, "_sqlserver_connect", connect_as_reader)
            data = db_engines.run_query(
                database_type, connection_string, "SELECT id FROM autohive_sqldb_test ORDER BY id", None, 1, 30
            )
            assert data["rows"] == [{"id": 1}]
            with pytest.raises(db_engines.DATABASE_ERRORS):
                db_engines.run_query(database_type, connection_string, "DELETE FROM autohive_sqldb_test", None, 10, 30)
            # A later permission error in a multi-result batch may not surface
            # until nextset(); the protection is that the data remains unchanged.
            try:
                db_engines.run_query(
                    database_type,
                    connection_string,
                    "SELECT 1 COMMIT DELETE FROM autohive_sqldb_test COMMIT",
                    None,
                    10,
                    30,
                )
            except db_engines.DATABASE_ERRORS:
                pass
        assert _count(database_type, connection_string) == 3
    finally:
        _admin(database_type, connection_string, ["DROP USER autohive_sqldb_test_reader"])


# ---- execute ----


async def test_execute_rejects_a_hidden_second_write(db):
    database_type, connection_string, context = db
    if database_type != "sqlserver":
        pytest.skip("SQL Server permits semicolonless stacked statements")
    result = await sql_database.execute_action(
        "execute",
        {"sql": "INSERT INTO autohive_sqldb_test (id) SELECT 4 DELETE FROM autohive_sqldb_test"},
        context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Statement rejected:")
    assert _count(database_type, connection_string) == 3


async def test_execute_insert_update_delete(db):
    database_type, connection_string, context = db
    returning = {"sqlserver": " OUTPUT inserted.id", "postgresql": "", "mysql": ""}[database_type]
    suffix = " RETURNING id" if database_type == "postgresql" else ""

    # returning and suffix are fixed dialect fragments, never external input.
    insert = await sql_database.execute_action(
        "execute",
        {
            "sql": f"INSERT INTO autohive_sqldb_test (id, name, amount){returning} VALUES (%s, %s, %s){suffix}",  # nosec B608
            "parameters": [4, "delta", 4.5],
        },
        context,
    )
    assert insert.type == ResultType.ACTION, insert.result
    assert insert.result.data["statement_type"] == "INSERT"
    assert insert.result.data["rows_affected"] == 1
    if database_type != "mysql":
        assert insert.result.data["returned_rows"] == [{"id": 4}]

    update = await sql_database.execute_action(
        "execute",
        {"sql": "UPDATE autohive_sqldb_test SET amount = amount + 1 WHERE id IN (%s, %s)", "parameters": [1, 2]},
        context,
    )
    assert update.result.data["rows_affected"] == 2

    delete = await sql_database.execute_action(
        "execute", {"sql": "DELETE FROM autohive_sqldb_test WHERE id = %s", "parameters": [4]}, context
    )
    assert delete.result.data["rows_affected"] == 1
    assert _count(database_type, connection_string) == 3

    check = db_engines.run_query(
        database_type, connection_string, "SELECT amount FROM autohive_sqldb_test WHERE id = 1", None, 1, 30
    )
    assert check["rows"] == [{"amount": "11.50"}]


async def test_negative_parameter_after_minus_keeps_the_where_clause(db):
    database_type, connection_string, context = db
    # SQL Server's driver copies values into the SQL text; x-%s with -1 must not become x--1 (a comment).
    result = await sql_database.execute_action(
        "execute",
        {"sql": "UPDATE autohive_sqldb_test SET amount = amount-%s WHERE id = %s", "parameters": [-1, 1]},
        context,
    )
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["rows_affected"] == 1
    check = db_engines.run_query(
        database_type, connection_string, "SELECT id, amount FROM autohive_sqldb_test ORDER BY id", None, 10, 30
    )
    assert [row["amount"] for row in check["rows"]] == ["11.50", "20.00", "30.25"]


async def test_execute_reports_matched_rows_for_no_op_updates(db):
    _, _, context = db
    result = await sql_database.execute_action(
        "execute", {"sql": "UPDATE autohive_sqldb_test SET name = name WHERE id = 1"}, context
    )
    assert result.type == ResultType.ACTION, result.result
    assert result.result.data["rows_affected"] == 1


async def test_execute_is_disabled_on_read_only_connections(db, sql_context):
    database_type, connection_string, _ = db
    read_only = sql_context(database_type, connection_string)
    result = await sql_database.execute_action(
        "execute", {"sql": "DELETE FROM autohive_sqldb_test WHERE id = 1"}, read_only
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "read-only" in result.result.message
    assert _count(database_type, connection_string) == 3


def _running_statements(connection_string: str, marker: str) -> int:
    conn = pymysql.connect(**mysql_connect_params(connection_string), autocommit=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.processlist WHERE info LIKE %s AND id <> CONNECTION_ID()",
            (f"%{marker}%",),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


async def test_mysql_lock_waits_end_at_the_timeout(db):
    database_type, connection_string, context = db
    if database_type != "mysql":
        pytest.skip("MySQL/MariaDB lock waits")
    holder = pymysql.connect(**mysql_connect_params(connection_string), autocommit=False)
    try:
        holder.cursor().execute("SELECT * FROM autohive_sqldb_test WHERE id = 1 FOR UPDATE")
        started = time.monotonic()
        result = await sql_database.execute_action(
            "execute",
            {"sql": "UPDATE autohive_sqldb_test SET name = 'lock-wait' WHERE id = 1", "timeout_seconds": 2},
            context,
        )
        elapsed = time.monotonic() - started
    finally:
        holder.rollback()
        holder.close()
    assert result.type == ResultType.ACTION_ERROR
    assert "Lock wait timeout" in result.result.message or "max_statement_time" in result.result.message
    assert elapsed < 5
    assert _running_statements(connection_string, "lock-wait") == 0


async def test_mysql_runaway_write_is_cancelled_on_the_server(db):
    database_type, connection_string, context = db
    if database_type != "mysql":
        pytest.skip("MySQL/MariaDB statement cancellation")
    result = await sql_database.execute_action(
        "execute",
        {"sql": "UPDATE autohive_sqldb_test SET name = 'runaway' WHERE id = 1 AND SLEEP(30) = 0", "timeout_seconds": 1},
        context,
    )
    assert result.type == ResultType.ACTION_ERROR
    # MySQL has no server-side DML timeout, so the client cancels the statement;
    # MariaDB's max_statement_time stops it on the server.
    assert "cancelled" in result.result.message or "max_statement_time" in result.result.message
    deadline = time.monotonic() + 5
    while _running_statements(connection_string, "SLEEP(30)") and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _running_statements(connection_string, "SLEEP(30)") == 0
    assert _count(database_type, connection_string) == 3


async def test_execute_requires_where_clause(db):
    database_type, connection_string, context = db
    rejected = await sql_database.execute_action("execute", {"sql": "DELETE FROM autohive_sqldb_test"}, context)
    assert rejected.type == ResultType.ACTION_ERROR
    assert _count(database_type, connection_string) == 3

    allowed = await sql_database.execute_action(
        "execute", {"sql": "DELETE FROM autohive_sqldb_test", "allow_all_rows": True}, context
    )
    assert allowed.result.data["rows_affected"] == 3
    assert _count(database_type, connection_string) == 0


async def test_execute_failure_is_rolled_back(db):
    database_type, connection_string, context = db
    result = await sql_database.execute_action(
        "execute", {"sql": "INSERT INTO autohive_sqldb_test (id, name) VALUES (5, 'ok'), (1, 'duplicate')"}, context
    )
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message.startswith("Database error:")
    assert _count(database_type, connection_string) == 3
