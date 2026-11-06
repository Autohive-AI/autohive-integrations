"""Tests for sql_guard: read-only queries must not be able to write, and writes must stay in scope.

Every BYPASS_ATTEMPTS case is a technique that works against a real server without
the guard (verified against SQL Server 2022, PostgreSQL 16, MySQL 8.4 and MariaDB 11).
"""

import importlib
import sys
from unittest.mock import patch

import pytest

from sql_guard import SqlRejectedError, check_read_only_query, check_write_statement, split_placeholders

pytestmark = pytest.mark.unit

ALL_DIALECTS = ["tsql", "postgres", "mysql"]

BYPASS_ATTEMPTS = [
    # T-SQL runs this as two statements; sqlglot reads DELETE as a column alias.
    ("tsql", "SELECT 1 DELETE FROM dbo.t", "DELETE"),
    ("tsql", "SELECT * FROM t UPDATE t SET a = 1", "UPDATE"),
    ("tsql", "SELECT 1 COMMIT DELETE FROM t COMMIT", "COMMIT"),
    ("tsql", "SELECT 1 TRUNCATE TABLE t", "TRUNCATE"),
    ("tsql", "SELECT 1 DROP TABLE t", "DROP"),
    ("tsql", "SELECT 1 EXEC sp_configure 'xp_cmdshell', 1", "EXEC"),
    ("tsql", "SELECT 1 SET IMPLICIT_TRANSACTIONS OFF", "SET"),
    ("tsql", "SELECT 1 DECLARE @x INT", "DECLARE"),
    ("tsql", "SELECT 1 KILL 55", "KILL"),
    ("tsql", "SELECT 1 SHUTDOWN", "SHUTDOWN"),
    ("tsql", "SELECT 1 WAITFOR DELAY '00:10'", "WAITFOR"),
    ("tsql", "SELECT 1 DISABLE TRIGGER trg ON t", "DISABLE"),
    ("tsql", "SELECT 1 GRANT SELECT ON t TO public", "GRANT"),
    ("tsql", "SELECT 1 BULK INSERT t FROM 'c:\\x.csv'", "BULK"),
    ("tsql", "EXEC xp_cmdshell 'dir'", "EXEC"),
    ("tsql", "SELECT * INTO dbo.copy FROM dbo.t", "INTO"),
    ("tsql", "SELECT NEXT VALUE FOR dbo.seq", "NEXT VALUE FOR"),
    ("tsql", "SELECT * FROM OPENQUERY(linked, 'DELETE FROM t')", "OPENQUERY"),
    ("tsql", "SELECT * FROM OPENROWSET('SQLNCLI', 'x', 'SELECT 1')", "OPENROWSET"),
    ("tsql", "SELECT * FROM t WITH (UPDLOCK)", "UPDLOCK"),
    ("tsql", "SELECT * FROM t WITH (TABLOCKX, HOLDLOCK)", "TABLOCKX"),
    ("tsql", "WITH c AS (SELECT * FROM t) DELETE FROM c", "DELETE"),
    ("tsql", "SELECT * FROM t; DELETE FROM t", "DELETE"),
    # SQL Server treats U+200B as whitespace; sqlglot would glue it to DELETE.
    ("tsql", "SELECT 1\u200bDELETE FROM t", "U+200B"),
    ("tsql", "SELECT 1\u00a0DELETE FROM t", "U+00A0"),
    ("tsql", "SELECT 1\x00DELETE FROM t", "U+0000"),
    ("tsql", "SELECT 1\u202eDELETE FROM t", "U+202E"),
    ("postgres", "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d", "DELETE"),
    ("postgres", "SELECT 1; DELETE FROM t", "DELETE"),
    ("postgres", "SET TRANSACTION READ WRITE", "SET"),
    ("postgres", "COMMIT", "COMMIT"),
    ("postgres", "SELECT * FROM t FOR UPDATE", "UPDATE"),
    ("postgres", "SELECT * FROM t FOR SHARE", "FOR SHARE"),
    ("postgres", "SELECT * INTO copy FROM t", "INTO"),
    ("postgres", "EXPLAIN ANALYZE DELETE FROM t", "DELETE"),
    ("postgres", "COPY t TO PROGRAM 'id'", "COPY"),
    ("postgres", "CALL do_writes()", "COMMAND"),
    ("postgres", "DO $$ BEGIN DELETE FROM t; END $$", "COMMAND"),
    ("postgres", "SELECT dblink_exec('dbname=x', 'DELETE FROM t')", "dblink_exec"),
    ("postgres", "SELECT * FROM dblink('dbname=x', 'SELECT 1') AS r(a int)", "dblink"),
    ("postgres", "SELECT public.dblink_exec('x', 'y')", "dblink_exec"),
    ("postgres", "SELECT set_config('transaction_read_only', 'off', false)", "set_config"),
    ("postgres", "SELECT \"set_config\"('a', 'b', false)", "set_config"),
    ("postgres", r"""SELECT U&"set_confi\0067"('a', 'b', false)""", "Unicode-escaped identifiers"),
    ("postgres", r"""SELECT U&"pg_read_\0066ile"('/tmp/x')""", "Unicode-escaped identifiers"),
    ("postgres", "SELECT pg_terminate_backend(123)", "pg_terminate_backend"),
    ("postgres", "SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
    ("postgres", "SELECT lo_export(1, '/tmp/x')", "lo_export"),
    ("postgres", "SELECT query_to_xml('DELETE FROM t RETURNING *', true, true, '')", "query_to_xml"),
    ("postgres", "SELECT nextval('seq')", "nextval"),
    ("postgres", "SELECT pg_advisory_lock(1)", "pg_advisory_lock"),
    ("postgres", "SELECT pg_notify('ch', 'x')", "pg_notify"),
    # MySQL runs the contents of executable comments; sqlglot treats them as comments.
    ("mysql", "SELECT * FROM t /*!50000 INTO OUTFILE '/tmp/x' */", "executable comments"),
    ("mysql", "SELECT 1 /*M! , SLEEP(100) */", "executable comments"),
    ("mysql", "SELECT /*+ SET_VAR(sql_mode='') */ 1", "optimizer hints"),
    ("mysql", "SELECT * FROM t INTO OUTFILE '/tmp/x'", "INTO"),
    ("mysql", "SELECT * FROM t INTO DUMPFILE '/tmp/x'", "INTO"),
    # In MySQL "--1" is arithmetic, not a comment, so INTO OUTFILE still runs.
    ("mysql", "SELECT 1 --1 INTO OUTFILE '/tmp/x'", "INTO"),
    ("mysql", "SELECT * FROM t LOCK IN SHARE MODE", "FOR UPDATE"),
    ("mysql", "SELECT * FROM t FOR UPDATE", "UPDATE"),
    ("mysql", "REPLACE t (a) VALUES (1)", "REPLACE"),
    ("mysql", "SELECT GET_LOCK('x', 10)", "GET_LOCK"),
    ("mysql", "SELECT LOAD_FILE('/etc/passwd')", "LOAD_FILE"),
    ("mysql", "SELECT sys_exec('id')", "sys_exec"),
    ("mysql", "HANDLER t OPEN", "parsed"),
    ("mysql", "SELECT 1; DELETE FROM t", "DELETE"),
]


@pytest.mark.parametrize("dialect,sql,reason", BYPASS_ATTEMPTS)
def test_read_only_query_rejects_bypass_attempts(dialect, sql, reason):
    with pytest.raises(SqlRejectedError) as excinfo:
        check_read_only_query(sql, dialect)
    assert reason.lower() in str(excinfo.value).lower()


# SQL Server never reads an unquoted reserved word as a name (checked against
# SQL Server 2022), but sqlglot accepts most of them as aliases. SQL Server runs
# the CHECKPOINT and RETURN below as separate statements.
@pytest.mark.parametrize(
    "sql,reason",
    [
        ("SELECT 1 CHECKPOINT", "CHECKPOINT"),
        ("SELECT 1 RETURN", "RETURN"),
        ("SELECT name FROM t READTEXT", "READTEXT"),
        ("SELECT 1 RAISERROR", "RAISERROR"),
        ("SELECT a key FROM t", "KEY"),
        ("SELECT * FROM t WITH (SERIALIZABLE)", "SERIALIZABLE"),
        ("SELECT * FROM t WITH (REPEATABLEREAD)", "REPEATABLEREAD"),
    ],
)
def test_tsql_reserved_words_cannot_be_read_as_names(sql, reason):
    with pytest.raises(SqlRejectedError, match=reason):
        check_read_only_query(sql, "tsql")


def test_tsql_reserved_word_check_also_covers_writes():
    with pytest.raises(SqlRejectedError, match="CHECKPOINT"):
        check_write_statement("INSERT INTO t SELECT 1 CHECKPOINT", "tsql")
    with pytest.raises(SqlRejectedError, match="RETURN"):
        check_write_statement("INSERT INTO t SELECT 1 RETURN", "tsql")


# Functions that run SQL passed as text, or change state that a read-only
# transaction does not protect (replication slots, index pages, server logs).
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM ts_stat('SELECT v FROM t')",
        "SELECT ts_rewrite(q, 'SELECT a, b FROM aliases') FROM t",
        "SELECT * FROM crosstab('SELECT a, b, c FROM t') AS ct(a text, b int)",
        "SELECT * FROM crosstab3('SELECT a, b, c FROM t')",
        "SELECT * FROM connectby('t', 'id', 'parent_id', '1', 0) AS c(id int, parent int, level int)",
        "SELECT * FROM xpath_table('id', 'doc', 't', '/a', 'true') AS x(id int, a text)",
        "SELECT pg_background_launch('DELETE FROM t')",
        "SELECT pg_replication_slot_advance('slot', '0/0')",
        "SELECT * FROM pg_logical_slot_get_changes('slot', NULL, NULL)",
        "SELECT * FROM pg_logical_slot_get_binary_changes('slot', NULL, NULL)",
        "SELECT brin_summarize_new_values('t_brin')",
        "SELECT brin_desummarize_range('t_brin', 0)",
        "SELECT gin_clean_pending_list('t_gin')",
        "SELECT pg_log_backend_memory_contexts(123)",
    ],
)
def test_postgres_side_effect_functions_are_rejected(sql):
    with pytest.raises(SqlRejectedError, match="is not allowed"):
        check_read_only_query(sql, "postgres")


@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("tsql", "SELECT TOP 10 * FROM [dbo].[Orders] WHERE Total > 100 ORDER BY Total DESC"),
        ("tsql", "SELECT [update], [delete] FROM t WHERE name = 'DROP TABLE t; DELETE FROM t'"),
        ("tsql", "SELECT a FROM t ORDER BY a OFFSET 10 ROWS FETCH NEXT 5 ROWS ONLY"),
        ("tsql", "SELECT COUNT(*), SUM(Total) FROM dbo.Orders WITH (NOLOCK)"),
        ("tsql", "SELECT 1 /* nested /* DELETE */ comment */"),
        ("tsql", "SELECT 'it''s', N'unicode ✓', 0x1F"),
        ("tsql", "WITH recent AS (SELECT * FROM dbo.Orders WHERE OrderDate > '2026-01-01') SELECT * FROM recent"),
        ("tsql", "SELECT a FROM t UNION ALL SELECT b FROM u EXCEPT SELECT c FROM v"),
        ("tsql", "SELECT REPLACE(Name, 'a', 'b'), LEFT(Name, 3), TRUNCATE_ONLY = 1 FROM t"),
        ("tsql", "SELECT name FROM sys.tables"),
        ("tsql", "SELECT USER, CURRENT_USER, SESSION_USER, CURRENT_TIMESTAMP"),
        ("tsql", "SELECT a [order], b AS [key] FROM t"),
        ("tsql", "SELECT SUM(a) OVER (ORDER BY b ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM t"),
        ("tsql", "SELECT a FROM t FOR JSON PATH, ROOT('rows')"),
        ("tsql", "SELECT * FROM t CROSS APPLY OPENJSON(t.j) WITH (id INT '$.id') AS j"),
        ("postgres", "SELECT slot_name, active FROM pg_replication_slots"),
        ("postgres", "SELECT ts_rank(to_tsvector(body), to_tsquery('x')) FROM docs"),
        ("postgres", "SELECT id, data->>'email' FROM users WHERE created_at > now() - interval '7 days' LIMIT 50"),
        ("postgres", "SELECT * FROM t WHERE note LIKE '%delete from%'"),
        ("postgres", "SELECT $$DROP TABLE t$$, $tag$DELETE$tag$"),
        ("postgres", "SELECT replace(name, 'a', 'b') FROM t"),
        ("postgres", "(SELECT 1) UNION (SELECT 2)"),
        ("postgres", "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"),
        ("postgres", "SELECT 1;"),
        ("mysql", "SELECT REPLACE(name, 'x', 'y') AS n FROM t # comment"),
        ("mysql", "SELECT COUNT(*) FROM t -- comment"),
        ("mysql", "SELECT 'it\\'s', `delete` FROM t"),
        ("mysql", "SELECT * FROM t /* plain comment */ LIMIT 5"),
    ],
)
def test_read_only_query_allows_reads(dialect, sql):
    check_read_only_query(sql, dialect)


@pytest.mark.parametrize("dialect", ALL_DIALECTS)
@pytest.mark.parametrize(
    "sql,reason",
    [
        ("", "empty"),
        ("   ", "empty"),
        ("SELECT 1; SELECT 2", "exactly one statement"),
        ("SELECT 'unterminated", "tokenized"),
        ("SELECT FROM WHERE", "parsed"),
    ],
)
def test_read_only_query_rejects_malformed_sql(dialect, sql, reason):
    with pytest.raises(SqlRejectedError) as excinfo:
        check_read_only_query(sql, dialect)
    assert reason in str(excinfo.value)


def test_read_only_query_rejects_oversized_sql():
    with pytest.raises(SqlRejectedError, match="longer than"):
        check_read_only_query("SELECT 1 " + " " * 100_000, "postgres")


def test_read_only_query_rejects_deep_nesting():
    with pytest.raises(SqlRejectedError):
        check_read_only_query("SELECT " + "(" * 5000 + "1" + ")" * 5000, "postgres")


def test_read_only_message_points_writes_to_execute():
    with pytest.raises(SqlRejectedError, match="Use the execute action"):
        check_read_only_query("DELETE FROM t WHERE id = 1", "postgres")


# ---- Parameters ----


@pytest.mark.parametrize("dialect", ALL_DIALECTS)
def test_parameters_are_validated_with_placeholders_bound(dialect):
    check_read_only_query("SELECT * FROM t WHERE a = %s AND b LIKE '50%%' AND c IN (%s, %s)", dialect, ["x", 1, None])


@pytest.mark.parametrize(
    "sql,parameters,reason",
    [
        ("SELECT * FROM t WHERE a = %s", [], "1 %s placeholder(s) but 0"),
        ("SELECT * FROM t", ["x"], "0 %s placeholder(s) but 1"),
        ("SELECT %d", [1], "only %s placeholders"),
        ("SELECT %(name)s", ["x"], "only %s placeholders"),
        ("SELECT * FROM t WHERE a LIKE 'x%' AND b = %s", ["x"], "only %s placeholders"),
    ],
)
def test_parameter_mismatches_are_rejected(sql, parameters, reason):
    with pytest.raises(SqlRejectedError) as excinfo:
        check_read_only_query(sql, "postgres", parameters)
    assert reason in str(excinfo.value)


def test_parameter_placeholders_cannot_hide_keywords():
    with pytest.raises(SqlRejectedError, match="DELETE"):
        check_read_only_query("SELECT %s DELETE FROM t", "tsql", ["x"])


@pytest.mark.parametrize("dialect", ALL_DIALECTS)
@pytest.mark.parametrize("sql", ["SELECT '%s'", "SELECT 1 /* %s */", "SELECT 1 -- %s\n", "SELECT name%s FROM t"])
def test_parameter_placeholders_must_be_standalone_values(dialect, sql):
    with pytest.raises(SqlRejectedError, match="standalone values"):
        check_read_only_query(sql, dialect, ["; COMMIT DELETE FROM t COMMIT --"])


@pytest.mark.parametrize(
    "dialect,sql", [("tsql", "SELECT [%s]"), ("mysql", "SELECT `%s`"), ("postgres", 'SELECT "%s"')]
)
def test_parameter_placeholders_cannot_be_quoted_identifiers(dialect, sql):
    with pytest.raises(SqlRejectedError, match="standalone values"):
        check_read_only_query(sql, dialect, ["name"])


def test_parameter_placeholders_cannot_be_postgres_dollar_quoted():
    with pytest.raises(SqlRejectedError, match="standalone values"):
        check_read_only_query("SELECT $tag$%s$tag$", "postgres", ["value"])


@pytest.mark.parametrize("dialect", ALL_DIALECTS)
def test_write_parameters_cannot_escape_quoted_placeholders(dialect):
    with pytest.raises(SqlRejectedError, match="standalone values"):
        check_write_statement("INSERT INTO t VALUES ('%s')", dialect, ["; DROP TABLE t; --"])


def test_sqlserver_rejects_literal_placeholder_text_with_parameters():
    # pymssql has no %% escape, so "%%s" would become a second placeholder.
    with pytest.raises(SqlRejectedError, match="literal %s"):
        check_read_only_query("SELECT '%%s', %s", "tsql", [1])


def test_split_placeholders_unescapes_percent():
    assert split_placeholders("a = %s AND b LIKE '5%%' OR c = %s") == ["a = ", " AND b LIKE '5%' OR c = ", ""]


# ---- Writes ----


@pytest.mark.parametrize(
    "dialect,sql,statement_type",
    [
        ("tsql", "INSERT INTO dbo.t (id, name) VALUES (1, N'a')", "INSERT"),
        ("tsql", "UPDATE dbo.t SET name = 'b' OUTPUT inserted.id WHERE id = 1", "UPDATE"),
        ("tsql", "DELETE FROM dbo.t WHERE id = 1", "DELETE"),
        ("tsql", "INSERT INTO t (id) VALUES (NEXT VALUE FOR dbo.seq)", "INSERT"),
        (
            "tsql",
            "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET a = s.a "
            "WHEN NOT MATCHED THEN INSERT (id) VALUES (s.id);",
            "MERGE",
        ),
        ("tsql", "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE;", "MERGE"),
        ("tsql", "UPDATE t SET a = DEFAULT, modified_by = USER WHERE id = 1", "UPDATE"),
        ("tsql", "DELETE TOP (5) FROM t WHERE a < 0", "DELETE"),
        ("postgres", "INSERT INTO t (a) VALUES (1) ON CONFLICT (a) DO UPDATE SET a = 2 RETURNING id", "INSERT"),
        ("postgres", "INSERT INTO t VALUES (nextval('seq'))", "INSERT"),
        ("postgres", "UPDATE t SET a = 1 FROM u WHERE t.id = u.id", "UPDATE"),
        ("postgres", "WITH x AS (DELETE FROM a WHERE id = 1 RETURNING *) INSERT INTO b SELECT * FROM x", "INSERT"),
        ("mysql", "INSERT INTO t (a) VALUES (1) ON DUPLICATE KEY UPDATE a = 2", "INSERT"),
        ("mysql", "DELETE FROM t WHERE created_at < NOW() - INTERVAL 30 DAY", "DELETE"),
    ],
)
def test_write_statement_allows_dml(dialect, sql, statement_type):
    assert check_write_statement(sql, dialect) == statement_type


@pytest.mark.parametrize(
    "dialect,sql,reason",
    [
        ("tsql", "INSERT INTO t SELECT 1 DELETE FROM t", "additional statements"),
        ("tsql", "UPDATE t SET a = 1 WHERE id = 1 DROP TABLE t", "DROP"),
        ("tsql", "DELETE FROM t WHERE id = 1 EXEC sp_who", "EXEC"),
        ("tsql", "INSERT INTO t EXEC dbo.proc", "EXEC"),
        ("tsql", "UPDATE t SET a = 1 WHERE id = 1 COMMIT", "COMMIT"),
        ("tsql", "INSERT INTO t SELECT * FROM OPENROWSET('x', 'y', 'z')", "OPENROWSET"),
        ("tsql", "BULK INSERT t FROM 'c:\\x.csv'", "BULK"),
        ("postgres", "TRUNCATE TABLE t", "TRUNCATE"),
        ("postgres", "DROP TABLE t", "DROP"),
        ("postgres", "CREATE TABLE t (id int)", "CREATE"),
        ("postgres", "ALTER TABLE t ADD COLUMN x int", "ALTER"),
        ("postgres", "GRANT ALL ON t TO public", "GRANT"),
        ("postgres", "INSERT INTO t SELECT dblink_exec('x', 'DROP TABLE u')", "dblink_exec"),
        ("postgres", "SELECT * FROM t", "only INSERT, UPDATE, DELETE or MERGE"),
        ("postgres", "INSERT INTO t VALUES (1); DELETE FROM u WHERE id = 1", "exactly one statement"),
        ("mysql", "REPLACE INTO t (a) VALUES (1)", "REPLACE"),
        ("mysql", "INSERT INTO t SELECT * FROM u /*! ; DROP TABLE u */", "executable comments"),
        ("mysql", "CALL do_writes()", "only INSERT, UPDATE, DELETE or MERGE"),
    ],
)
def test_write_statement_rejects_out_of_scope_sql(dialect, sql, reason):
    with pytest.raises(SqlRejectedError) as excinfo:
        check_write_statement(sql, dialect)
    assert reason in str(excinfo.value)


@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("postgres", "DELETE FROM t"),
        ("postgres", "UPDATE t SET a = 1"),
        ("tsql", "DELETE TOP (10) FROM t"),
        ("postgres", "WITH x AS (DELETE FROM a RETURNING *) INSERT INTO b SELECT * FROM x"),
    ],
)
def test_write_statement_requires_where_unless_allowed(dialect, sql):
    with pytest.raises(SqlRejectedError, match="without a WHERE clause"):
        check_write_statement(sql, dialect)
    assert check_write_statement(sql, dialect, allow_all_rows=True) in {"DELETE", "UPDATE", "INSERT"}


def test_guard_never_loads_the_sqlglot_executor():
    # sqlglot ships a pure-Python SQL executor that runs generated code through eval(), and code
    # scanners flag it in the deployed package. The guard only parses SQL, so the executor must stay
    # unloaded. The guard and sqlglot are imported afresh, and sys.modules is restored afterwards.
    with patch.dict(sys.modules):
        for name in [name for name in sys.modules if name == "sql_guard" or name.split(".")[0] == "sqlglot"]:
            del sys.modules[name]
        guard = importlib.import_module("sql_guard")
        for dialect in ALL_DIALECTS:
            guard.check_read_only_query("SELECT a FROM t WHERE b = %s", dialect, [1])
            guard.check_write_statement("UPDATE t SET a = 1 WHERE b = 2", dialect)
            with pytest.raises(guard.SqlRejectedError):
                guard.check_read_only_query("SELECT 1; DELETE FROM t", dialect)
        assert "sqlglot.parser" in sys.modules
        assert [name for name in sys.modules if name.startswith("sqlglot.executor")] == []
