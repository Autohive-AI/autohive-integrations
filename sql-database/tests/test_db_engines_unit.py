import datetime
import decimal
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock, patch

import pymssql
import pymysql
import pytest

import db_engines
from db_engines import (
    CommitOutcomeUnknownError,
    ConnectionConfigError,
    StatementTimeoutError,
    ca_certificate_file,
    describe_database_error,
    mysql_connect_params,
    postgres_connect_params,
    redact_secrets,
    resolve_access_mode,
    resolve_engine,
    run_query,
    run_write,
    sqlserver_connect_params,
)

pytestmark = pytest.mark.unit

AZURE_SQL = (
    "Server=tcp:contoso.database.windows.net,1433;Initial Catalog=sales;Persist Security Info=False;"
    "User ID=reader;Password=test-only;MultipleActiveResultSets=False;Encrypt=True;"
    "TrustServerCertificate=False;Connection Timeout=30;"
)
CA_FILE = "custom-ca.pem"  # a path that is only compared, never opened


def _result(rows, columns, truncation_reason=None, values_truncated=False):
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncation_reason is not None,
        "truncation_reason": truncation_reason,
        "values_truncated": values_truncated,
    }


# ---- Engine selection ----


@pytest.mark.parametrize(
    "value,engine",
    [
        ("sqlserver", "sqlserver"),
        ("SQL Server", "sqlserver"),
        ("mssql", "sqlserver"),
        ("Azure SQL", "sqlserver"),
        ("postgresql", "postgresql"),
        ("Postgres", "postgresql"),
        ("mysql", "mysql"),
        ("MariaDB", "mysql"),
    ],
)
def test_resolve_engine_accepts_aliases(value, engine):
    assert resolve_engine(value) == engine


@pytest.mark.parametrize("value", ["oracle", "", None])
def test_resolve_engine_rejects_unknown(value):
    with pytest.raises(ConnectionConfigError, match="sqlserver, postgresql, mysql"):
        resolve_engine(value)


@pytest.mark.parametrize(
    "value,mode",
    [(None, "read-only"), ("", "read-only"), ("Read Only", "read-only"), ("read_write", "read-write")],
)
def test_resolve_access_mode_defaults_to_read_only(value, mode):
    assert resolve_access_mode(value) == mode


def test_resolve_access_mode_rejects_unknown_values():
    with pytest.raises(ConnectionConfigError, match="read-only or read-write"):
        resolve_access_mode("write")


# ---- CA certificates ----


def _public_ca_pem() -> str:
    with open(db_engines.certifi.where()) as handle:
        return re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", handle.read(), re.S).group(0)


def test_ca_certificate_is_rewrapped_after_newlines_are_lost():
    pem = _public_ca_pem()
    path = ca_certificate_file("  " + pem.replace("\n", " ") + "  ")
    with open(path) as handle:
        written = handle.read()
    assert written.splitlines()[0] == "-----BEGIN CERTIFICATE-----"
    assert all(len(line) <= 64 for line in written.splitlines())
    assert "".join(written.split()) == "".join(pem.split())
    assert ca_certificate_file(pem) == path  # identical content reuses the same file


@pytest.mark.parametrize(
    "pem,reason",
    [
        ("hello", "BEGIN CERTIFICATE"),
        ("-----BEGIN CERTIFICATE-----!!!-----END CERTIFICATE-----", "not valid PEM"),
        ("-----BEGIN CERTIFICATE-----QUJD-----END CERTIFICATE-----", "could not be loaded"),
    ],
)
def test_invalid_ca_certificates_are_rejected(pem, reason):
    with pytest.raises(ConnectionConfigError, match=reason):
        ca_certificate_file(pem)


def test_blank_ca_certificate_is_ignored():
    assert ca_certificate_file("  ") is None


def test_ca_certificate_is_validated_once_and_rewritten_if_deleted():
    pem = _public_ca_pem()
    db_engines._ca_bundle.cache_clear()
    with patch.object(db_engines.ssl, "create_default_context", wraps=db_engines.ssl.create_default_context) as load:
        path = ca_certificate_file(pem)
        os.remove(path)
        assert ca_certificate_file(pem) == path
    assert load.call_count == 1
    assert os.path.exists(path)


# ---- SQL Server connection strings ----


def test_sqlserver_parses_azure_portal_string():
    params = sqlserver_connect_params(AZURE_SQL)
    # The password below is a synthetic parser fixture.
    assert params == {
        "server": "contoso.database.windows.net",
        "port": "1433",
        "user": "reader",
        "password": "test-only",  # nosec B105
        "database": "sales",
        "appname": "Autohive",
        "login_timeout": 15,
        "read_only": False,
        "encryption": "require",
        "ca_file": db_engines.certifi.where(),
        "check_hostname": True,
    }


def test_sqlserver_parses_odbc_string_with_braced_password():
    params = sqlserver_connect_params(
        "Driver={ODBC Driver 18 for SQL Server};Server=db.local;Database=app;UID=sa;PWD={p;w}}d};"
        "TrustServerCertificate=yes"
    )
    assert params["password"] == "p;w}d"
    assert params["server"] == "db.local"
    assert params["ca_file"] is None
    assert "port" not in params


def test_sqlserver_parses_quoted_values_and_named_instance():
    params = sqlserver_connect_params(
        'Data Source=host\\SQLEXPRESS; User Id = app ; Password="a;b""c"; Application Name=Flow'
    )
    assert params["server"] == "host\\SQLEXPRESS"
    assert params["user"] == "app"
    assert params["password"] == 'a;b"c'
    assert params["appname"] == "Flow"


def test_sqlserver_encrypt_false_requests_tls_without_verification():
    params = sqlserver_connect_params("Server=h;User ID=u;Password=p;Encrypt=False")
    assert params["encryption"] == "request"
    assert params["ca_file"] is None


def test_sqlserver_verifies_against_a_custom_ca():
    params = sqlserver_connect_params(AZURE_SQL, CA_FILE)
    assert (params["ca_file"], params["check_hostname"]) == (CA_FILE, True)
    # TrustServerCertificate=True still checks the custom CA, but not the host name.
    trusted = AZURE_SQL.replace("TrustServerCertificate=False", "TrustServerCertificate=True")
    assert sqlserver_connect_params(trusted)["ca_file"] is None
    params = sqlserver_connect_params(trusted, CA_FILE)
    assert (params["ca_file"], params["check_hostname"]) == (CA_FILE, False)


def test_sqlserver_custom_ca_cannot_be_combined_with_encryption_off():
    with pytest.raises(ConnectionConfigError, match="Encrypt=False"):
        sqlserver_connect_params("Server=h;User ID=u;Password=p;Encrypt=False", CA_FILE)


@pytest.mark.parametrize("value,expected", [("0", 15), ("", 15), ("5", 5), ("90", 15)])
def test_sqlserver_connect_timeout_is_capped(value, expected):
    params = sqlserver_connect_params(f"Server=h;User ID=u;Password=p;Connection Timeout={value}")
    assert params["login_timeout"] == expected


def test_sqlserver_application_intent_read_only_is_honoured():
    assert sqlserver_connect_params("Server=h;User ID=u;Password=p;ApplicationIntent=ReadOnly")["read_only"] is True


@pytest.mark.parametrize(
    "connection_string,reason",
    [
        ("Server=h;Integrated Security=SSPI", "Windows authentication"),
        ("Server=h;Trusted_Connection=yes;User ID=u", "Windows authentication"),
        ("Server=h;User ID=u;Authentication=Active Directory Password", "Only SQL authentication"),
        ("Server=h;User ID=u;Encrypt=Strict", "Encrypt=Strict"),
        ("Server=h;User ID=u;Encrypt=maybe", "Encrypt must be"),
        ("Server=h,abc;User ID=u", "port must be a number"),
        ("Server=h;User ID=u;Pasword=typo", "has a keyword that is not supported"),
        ("Server=h;User ID=u;Failover Partner=h2", "keyword 'failover partner' is not supported"),
        ("User ID=u;Password=p", "must include Server and User ID"),
        ("Server=h;User ID=u;Password='unterminated", "is not closed"),
        ("just some text", "Key=Value"),
        ("Server=h;User ID=u;Connection Timeout=soon", "Connection Timeout"),
    ],
)
def test_sqlserver_rejects_unsupported_settings(connection_string, reason):
    with pytest.raises(ConnectionConfigError, match=reason):
        sqlserver_connect_params(connection_string)


@pytest.mark.parametrize(
    "connection_string", ["Server=h;User ID=u;Password=ab;cd;Encrypt=True", "Server=h;Password=ab;cdef=1"]
)
def test_sqlserver_errors_do_not_repeat_password_fragments(connection_string):
    # An unbraced ; ends the password early, so the rest looks like another keyword.
    with pytest.raises(ConnectionConfigError) as excinfo:
        sqlserver_connect_params(connection_string)
    assert "cd" not in str(excinfo.value).lower()


# ---- PostgreSQL connection strings ----


def test_postgres_accepts_url_and_sets_defaults():
    params = postgres_connect_params("postgresql://reader:test-only@db.example.com:5432/app?sslmode=require")
    assert params["host"] == "db.example.com"
    assert params["dbname"] == "app"
    assert params["sslmode"] == "require"
    assert params["connect_timeout"] == "15"
    assert params["application_name"] == "Autohive"
    assert "sslrootcert" not in params


@pytest.mark.parametrize(
    "connection_string,ca_file,sslmode,sslrootcert",
    [
        ("postgresql://u:p@h/db", None, "require", None),
        ("postgresql://u:p@h/db", CA_FILE, "verify-full", CA_FILE),
        ("postgresql://u:p@h/db?sslmode=verify-ca", CA_FILE, "verify-ca", CA_FILE),
        ("postgresql://u:p@h/db?sslmode=disable", None, "disable", None),
        # A custom CA is always checked, as libpq does for require with a root certificate.
        ("postgresql://u:p@h/db?sslmode=require", CA_FILE, "verify-ca", CA_FILE),
        ("postgresql://u:p@h/db?sslmode=prefer", CA_FILE, "verify-ca", CA_FILE),
        ("postgresql://u:p@h/db?sslmode=prefer", None, "prefer", None),
    ],
)
def test_postgres_encrypts_by_default(connection_string, ca_file, sslmode, sslrootcert):
    params = postgres_connect_params(connection_string, ca_file)
    assert params["sslmode"] == sslmode
    assert params.get("sslrootcert") == sslrootcert


def test_postgres_custom_ca_cannot_be_combined_with_encryption_off():
    with pytest.raises(ConnectionConfigError, match="sslmode=disable"):
        postgres_connect_params("postgresql://u:p@h/db?sslmode=disable", CA_FILE)


# 0 means "wait forever" in libpq, so it gets the cap too.
@pytest.mark.parametrize("value,expected", [("600", "15"), ("5", "5"), ("1", "1"), ("0", "15"), ("-1", "15")])
def test_postgres_connect_timeout_is_capped(value, expected):
    assert postgres_connect_params(f"host=h user=u connect_timeout={value}")["connect_timeout"] == expected


def test_postgres_rejects_non_numeric_connect_timeout():
    with pytest.raises(ConnectionConfigError, match="connect_timeout"):
        postgres_connect_params("host=h user=u connect_timeout=soon")


def test_postgres_verify_full_uses_public_ca_bundle():
    params = postgres_connect_params("host=db.example.com dbname=app user=u password=p sslmode=verify-full")
    assert params["sslrootcert"] == db_engines.certifi.where()


@pytest.mark.parametrize("option", ["sslkey=/etc/key", "passfile=/proc/self/environ", "service=prod", "sslrootcert=/x"])
def test_postgres_rejects_options_that_touch_local_files(option):
    with pytest.raises(ConnectionConfigError, match="Unsupported PostgreSQL connection parameter"):
        postgres_connect_params(f"host=db.example.com user=u {option}")


def test_postgres_parse_errors_do_not_echo_the_password():
    with pytest.raises(ConnectionConfigError) as excinfo:
        postgres_connect_params("host=db password=s3cret-value broken")
    assert "s3cret-value" not in str(excinfo.value)


def test_postgres_requires_host():
    with pytest.raises(ConnectionConfigError, match="must include a host"):
        postgres_connect_params("dbname=app user=u")


# ---- MySQL connection strings ----


def test_mysql_parses_url_with_encoded_password():
    params = mysql_connect_params("mysql://app:p%40ss%3Aword@db.example.com:3307/shop")
    assert params["host"] == "db.example.com"
    assert params["port"] == 3307
    assert params["user"] == "app"
    assert params["password"] == "p@ss:word"
    assert params["database"] == "shop"
    assert params["local_infile"] is False
    assert params["client_flag"] & db_engines.CLIENT.FOUND_ROWS
    assert params["ssl"].verify_mode == db_engines.ssl.CERT_NONE  # encrypted by default


def test_mysql_preferred_mode_is_an_explicit_opt_out():
    params = mysql_connect_params("mysql://u:p@h/db?ssl-mode=PREFERRED")
    assert "ssl" not in params and "ssl_disabled" not in params and "ssl_ca" not in params


def test_mysql_custom_ca_defaults_to_full_verification():
    params = mysql_connect_params("mysql://u:p@h/db", CA_FILE)
    assert (params["ssl_ca"], params["ssl_verify_cert"], params["ssl_verify_identity"]) == (CA_FILE, True, True)
    assert mysql_connect_params("mysql://u:p@h/db?ssl-mode=VERIFY_CA", CA_FILE)["ssl_verify_identity"] is False


@pytest.mark.parametrize("mode", ["REQUIRED", "PREFERRED"])
def test_mysql_custom_ca_is_checked_when_the_mode_would_skip_it(mode):
    params = mysql_connect_params(f"mysql://u:p@h/db?ssl-mode={mode}", CA_FILE)
    assert (params["ssl_ca"], params["ssl_verify_cert"], params["ssl_verify_identity"]) == (CA_FILE, True, False)
    assert "ssl" not in params


def test_mysql_custom_ca_cannot_be_combined_with_encryption_off():
    with pytest.raises(ConnectionConfigError, match="ssl-mode=DISABLED"):
        mysql_connect_params("mysql://u:p@h/db?ssl-mode=DISABLED", CA_FILE)


def test_mysql_converts_bit_and_json_columns():
    conv = mysql_connect_params("mysql://u:p@h/db")["conv"]
    assert conv[db_engines.FIELD_TYPE.BIT](b"\x02\x01") == 513
    assert conv[db_engines.FIELD_TYPE.JSON]('{"a": [1]}') == {"a": [1]}


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("DISABLED", {"ssl_disabled": True}),
        ("VERIFY_CA", {"ssl_verify_cert": True, "ssl_verify_identity": False}),
        ("verify-identity", {"ssl_verify_cert": True, "ssl_verify_identity": True}),
    ],
)
def test_mysql_ssl_modes(mode, expected):
    params = mysql_connect_params(f"mariadb://u:p@h/db?ssl-mode={mode}")
    for key, value in expected.items():
        assert params[key] == value


def test_mysql_ssl_required_encrypts_without_verifying():
    context = mysql_connect_params("mysql://u:p@h/db?ssl_mode=REQUIRED")["ssl"]
    assert context.check_hostname is False
    assert context.verify_mode == db_engines.ssl.CERT_NONE


@pytest.mark.parametrize(
    "connection_string,reason",
    [
        ("postgresql://u:p@h/db", "mysql://user:password@host"),
        ("mysql://u:p@h:notaport/db", "invalid port"),
        ("mysql://u:p@h/db?local_infile=1", "support only the ssl-mode parameter"),
        ("mysql://u:p@h/db?ssl-mode=SOMETIMES", "ssl-mode must be one of"),
        ("mysql://reader:synthetic-secret@℀/db", "could not be parsed"),
        ("mysql://u:p@[bad/db", "could not be parsed"),
    ],
)
def test_mysql_rejects_invalid_strings(connection_string, reason):
    with pytest.raises(ConnectionConfigError, match=reason):
        mysql_connect_params(connection_string)


# ---- Runtime read-only layers (drivers mocked) ----


def _postgres_conn(rows, names):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.stream.return_value = iter(rows)
    cursor.description = [(n,) for n in names]
    return conn, cursor


def _mysql_conn(rows=(), server="8.4.11"):
    conn = MagicMock()
    conn.get_server_info.return_value = server
    conn.thread_id.return_value = 42
    cursor = conn.cursor.return_value
    cursor.__iter__.return_value = iter(rows)
    return conn, cursor


def test_postgres_query_uses_read_only_transaction_and_never_commits():
    conn, cursor = _postgres_conn([(1, "a"), (2, "b"), (3, "c")], ["id", "name"])
    with patch.object(db_engines.psycopg, "connect", return_value=conn) as connect:
        result = run_query("postgresql", "postgresql://u:p@h/db", "SELECT id, name FROM t", None, 2, 10)

    assert connect.call_args.kwargs["host"] == "h"
    assert connect.call_args.kwargs["sslmode"] == "require"
    assert conn.read_only is True
    session_sql, session_args = cursor.execute.call_args.args
    assert "statement_timeout" in session_sql and "intervalstyle" in session_sql and session_args == ["10000"]
    cursor.stream.assert_called_once_with("SELECT id, name FROM t", None)
    registered = {c.args[0] for c in conn.adapters.register_loader.call_args_list}
    assert registered == {"date", "time", "timetz", "timestamp", "timestamptz", "interval"}
    conn.commit.assert_not_called()
    conn.close.assert_called_once()
    assert result == _result([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], ["id", "name"], "max_rows")


def test_postgres_dates_python_cannot_hold_fall_back_to_text():
    loader = db_engines._POSTGRES_LOADERS["timestamp"](db_engines.psycopg.postgres.types["timestamp"].oid)
    assert loader.load(b"infinity") == "infinity"
    assert loader.load(b"2026-01-02 03:04:05") == datetime.datetime(2026, 1, 2, 3, 4, 5)
    date_loader = db_engines._POSTGRES_LOADERS["date"](db_engines.psycopg.postgres.types["date"].oid)
    assert date_loader.load(b"0044-03-15 BC") == "0044-03-15 BC"


def test_postgres_write_uses_the_extended_protocol_and_commits():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.description = [("id",)]
    cursor.fetchone.side_effect = [(7,), None]
    cursor.fetchall.return_value = []
    cursor.rowcount = 1
    with patch.object(db_engines.psycopg, "connect", return_value=conn):
        result = run_write("postgresql", "postgresql://u:p@h/db", "INSERT INTO t (a) VALUES (%s) RETURNING id", [1], 30)
    conn.pipeline.assert_called_once()
    assert cursor.execute.call_args.args == ("INSERT INTO t (a) VALUES (%s) RETURNING id", [1])
    conn.commit.assert_called_once()
    assert result == {
        "rows_affected": 1,
        "columns": ["id"],
        "returned_rows": [{"id": 7}],
        "returned_rows_truncated": False,
    }


def test_mysql_query_sets_read_only_before_running_sql():
    conn, cursor = _mysql_conn([(1,)])
    cursor.description = [("total",)]
    with patch.object(db_engines.pymysql, "connect", return_value=conn) as connect:
        result = run_query("mysql", "mysql://u:p@h/db", "SELECT COUNT(*) AS total FROM t", ["x"], 5, 20)

    executed = [c.args[0] for c in cursor.execute.call_args_list]
    assert executed[-3:] == [
        "SET SESSION TRANSACTION READ ONLY",
        "START TRANSACTION READ ONLY",
        "SELECT COUNT(*) AS total FROM t",
    ]
    assert cursor.execute.call_args_list[-1].args[1] == ["x"]
    assert any("max_execution_time" in sql for sql in executed)
    assert ("SET SESSION sql_select_limit = %s", (6,)) in [c.args for c in cursor.execute.call_args_list]
    assert connect.call_args.kwargs["cursorclass"] is pymysql.cursors.SSCursor
    assert connect.call_args.kwargs["local_infile"] is False
    conn.commit.assert_not_called()
    assert result == _result([{"total": 1}], ["total"])


def test_mysql_query_uses_max_statement_time_on_mariadb():
    conn, cursor = _mysql_conn(server="11.8.9-MariaDB-ubu2404")
    cursor.description = [("a",)]
    with patch.object(db_engines.pymysql, "connect", return_value=conn):
        run_query("mysql", "mysql://u:p@h/db", "SELECT 1 AS a", None, 5, 7)
    calls = [c.args for c in cursor.execute.call_args_list]
    assert ("SET SESSION max_statement_time = %s", (7,)) in calls


def test_mysql_session_aligns_quoted_strings_and_bounds_lock_waits():
    conn, cursor = MagicMock(), MagicMock()
    conn.get_server_info.return_value = "11.8-MariaDB"
    cursor.fetchone.return_value = ("STRICT_TRANS_TABLES,ANSI_QUOTES,NO_BACKSLASH_ESCAPES,ANSI,ORACLE,PIPES_AS_CONCAT",)
    db_engines._mysql_session(conn, cursor, 5)
    cursor.execute.assert_any_call("SET SESSION sql_mode = %s", ("STRICT_TRANS_TABLES,PIPES_AS_CONCAT",))
    cursor.execute.assert_any_call("SET SESSION lock_wait_timeout = %s, SESSION innodb_lock_wait_timeout = %s", (5, 5))


def test_mysql_timeout_cancels_the_statement_on_the_server():
    conn, cursor = _mysql_conn()
    timed_out = pymysql.err.OperationalError(2013, "Lost connection to MySQL server during query (timed out)")
    cursor.execute.side_effect = [None] * 4 + [timed_out]
    killer = MagicMock()
    with patch.object(db_engines.pymysql, "connect", side_effect=[conn, killer]) as connect:
        with pytest.raises(StatementTimeoutError, match="within 3 seconds and was cancelled"):
            run_write("mysql", "mysql://u:p@h/db", "UPDATE t SET a = 1 WHERE id = 1", None, 3)
    killer_limits = {key: connect.call_args.kwargs[key] for key in ("connect_timeout", "read_timeout", "write_timeout")}
    assert killer_limits == {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    killer.cursor.return_value.execute.assert_called_once_with("KILL QUERY %s", (42,))
    killer.close.assert_called_once()
    conn.commit.assert_not_called()


def test_mysql_lost_commit_reply_is_reported_as_unknown_not_cancelled():
    conn, cursor = _mysql_conn()
    cursor.description = None
    conn.commit.side_effect = pymysql.err.OperationalError(
        2013, "Lost connection to MySQL server during query (timed out)"
    )
    with patch.object(db_engines.pymysql, "connect", return_value=conn) as connect:
        with pytest.raises(CommitOutcomeUnknownError, match="may or may not have been saved"):
            run_write("mysql", "mysql://u:p@h/db", "UPDATE t SET a = 1 WHERE id = 1", None, 3)
    assert connect.call_count == 1  # no KILL QUERY: the statement itself had finished


def test_mysql_other_connection_errors_are_not_treated_as_timeouts():
    conn, cursor = _mysql_conn()
    cursor.execute.side_effect = [None] * 4 + [pymysql.err.OperationalError(2013, "Lost connection to server")]
    with patch.object(db_engines.pymysql, "connect", return_value=conn) as connect:
        with pytest.raises(pymysql.err.OperationalError):
            run_write("mysql", "mysql://u:p@h/db", "UPDATE t SET a = 1 WHERE id = 1", None, 3)
    assert connect.call_count == 1


def test_sqlserver_query_never_commits_and_enables_implicit_transactions():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.__iter__.return_value = iter([(3,), (4,)])
    cursor.description = [("",)]
    with patch.object(db_engines.pymssql, "connect", return_value=conn) as connect:
        result = run_query("sqlserver", AZURE_SQL, "SELECT COUNT(*) FROM t WHERE a LIKE %s", ["5%"], 1, 12)

    kwargs = connect.call_args.kwargs
    assert kwargs["timeout"] == 12 and kwargs["autocommit"] is False and kwargs["encryption"] == "require"
    assert "ca_file" not in kwargs
    assert cursor.execute.call_args_list[0].args == ("SET IMPLICIT_TRANSACTIONS ON",)
    assert cursor.execute.call_args_list[1].args == ("SELECT COUNT(*) FROM t WHERE a LIKE  %s", ("5%",))
    conn.commit.assert_not_called()
    conn.close.assert_called_once()
    assert result == _result([{"column_1": 3}], ["column_1"], "max_rows")


def test_sqlserver_unescapes_percent_when_parameters_are_used():
    conn = MagicMock()
    conn.cursor.return_value.description = [("a",)]
    with patch.object(db_engines.pymssql, "connect", return_value=conn):
        run_query("sqlserver", AZURE_SQL, "SELECT a FROM t WHERE b LIKE '50%%' AND c = %s", [1], 5, 5)
    assert conn.cursor.return_value.execute.call_args.args == ("SELECT a FROM t WHERE b LIKE '50%' AND c =  %s", (1,))


def test_sqlserver_negative_parameter_after_minus_does_not_become_a_comment():
    # pymssql copies values into the SQL text: x-%s with -1 would otherwise be x--1.
    sql, parameters = db_engines._sqlserver_parameters("UPDATE t SET x = x-%s WHERE id = %s", [-1, 5])
    assert sql == "UPDATE t SET x = x- %s WHERE id =  %s"
    assert "--" not in sql % parameters


def test_sqlserver_certificate_verification_follows_trust_setting():
    conn = MagicMock()
    conn.cursor.return_value.description = []

    def freetds_config():
        with open(os.environ["FREETDSCONF"]) as handle:
            return handle.read()

    trusted = AZURE_SQL.replace("TrustServerCertificate=False", "TrustServerCertificate=True")
    with patch.object(db_engines.pymssql, "connect", return_value=conn):
        run_query("sqlserver", AZURE_SQL, "SELECT 1", None, 1, 5)
        assert f"ca file = {db_engines.certifi.where()}" in freetds_config()
        assert "check certificate hostname = yes" in freetds_config()
        run_query("sqlserver", trusted, "SELECT 1", None, 1, 5)
        assert "ca file" not in freetds_config()
        run_query("sqlserver", trusted, "SELECT 1", None, 1, 5, CA_FILE)
        assert f"ca file = {CA_FILE}" in freetds_config()
        assert "check certificate hostname = no" in freetds_config()
        # The variable never changes; a deleted config is written again before connecting.
        assert os.environ["FREETDSCONF"] == db_engines._FREETDS_CONF
        os.remove(db_engines._FREETDS_CONF)
        run_query("sqlserver", AZURE_SQL, "SELECT 1", None, 1, 5, CA_FILE)
        assert f"ca file = {CA_FILE}" in freetds_config()


def test_sqlserver_queries_and_writes_do_not_overlap_in_one_process():
    first_running, release_first, second_running = Event(), Event(), Event()

    def first(*args):
        first_running.set()
        assert release_first.wait(5)
        return _result([{"n": 1}], ["n"])

    def second(*args):
        second_running.set()
        return 1, _result([], [])

    with (
        patch.object(db_engines, "_sqlserver_query", side_effect=first),
        patch.object(db_engines, "_sqlserver_write", side_effect=second),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        query = pool.submit(run_query, "sqlserver", AZURE_SQL, "SELECT 1", None, 1, 1)
        assert first_running.wait(5)
        write = pool.submit(run_write, "sqlserver", AZURE_SQL, "INSERT INTO t VALUES (1)", None, 10)
        try:
            assert not second_running.wait(0.05)
        finally:
            release_first.set()
        assert query.result(timeout=5)["rows"] == [{"n": 1}]
        assert write.result(timeout=5)["rows_affected"] == 1


def test_write_returned_rows_are_capped():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.description = [("id",)]
    cursor.fetchone.side_effect = [(i,) for i in range(1001)] + [None]
    cursor.rowcount = 1001
    with patch.object(db_engines.psycopg, "connect", return_value=conn):
        result = run_write("postgresql", "postgresql://u:p@h/db", "DELETE FROM t WHERE a > 0 RETURNING id", None, 30)
    assert len(result["returned_rows"]) == 1000
    assert result["returned_rows_truncated"] is True
    assert cursor.fetchone.call_count == 1002  # leftover rows are read, one at a time, before commit
    cursor.fetchall.assert_not_called()
    conn.commit.assert_called_once()


def test_lost_connection_during_commit_is_reported_as_unknown():
    conn = MagicMock()
    conn.cursor.return_value.description = None
    conn.broken = True
    conn.commit.side_effect = db_engines.psycopg.OperationalError("server closed the connection unexpectedly")
    with patch.object(db_engines.psycopg, "connect", return_value=conn):
        with pytest.raises(CommitOutcomeUnknownError):
            run_write("postgresql", "postgresql://u:p@h/db", "DELETE FROM t WHERE id = 1", None, 30)

    conn = MagicMock()
    conn.cursor.return_value.description = None
    conn.commit.side_effect = pymssql.OperationalError(
        "Cannot commit transaction: (20017, b'DB-Lib error message 20017, severity 9:\\n"
        "Unexpected EOF from the server\\n')"
    )
    with patch.object(db_engines.pymssql, "connect", return_value=conn):
        with pytest.raises(CommitOutcomeUnknownError):
            run_write("sqlserver", AZURE_SQL, "DELETE FROM t WHERE id = 1", None, 30)


def test_commit_rejected_by_the_server_is_reported_as_is():
    conn = MagicMock()
    conn.cursor.return_value.description = None
    conn.broken = False
    conn.commit.side_effect = db_engines.psycopg.errors.SerializationFailure("could not serialize access")
    with patch.object(db_engines.psycopg, "connect", return_value=conn):
        with pytest.raises(db_engines.psycopg.errors.SerializationFailure):
            run_write("postgresql", "postgresql://u:p@h/db", "DELETE FROM t WHERE id = 1", None, 30)


def test_write_is_not_committed_when_the_statement_fails():
    conn, cursor = _mysql_conn()
    cursor.execute.side_effect = [None] * 4 + [pymysql.err.IntegrityError(1062, "Duplicate entry")]
    with patch.object(db_engines.pymysql, "connect", return_value=conn), pytest.raises(pymysql.err.IntegrityError):
        run_write("mysql", "mysql://u:p@h/db", "INSERT INTO t VALUES (1)", None, 30)
    conn.commit.assert_not_called()
    conn.close.assert_called_once()


# ---- Result shaping and errors ----


def test_values_are_converted_to_json_safe_types():
    when = datetime.datetime(2026, 10, 27, 9, 30, tzinfo=datetime.timezone.utc)
    ident = uuid.UUID("12345678-1234-5678-1234-567812345678")
    result = db_engines._collect(
        [
            (
                decimal.Decimal("12.3400"),
                when,
                b"\x00\xff",
                ident,
                1.5,
                float("nan"),
                {"k": [decimal.Decimal("1.0")]},
                datetime.timedelta(hours=838),
                -datetime.timedelta(hours=1, minutes=30, microseconds=5),
                1,
                2,
                None,
            )
        ],
        lambda: ["d", "dt", "b", "u", "f", "nan", "j", "time", "neg", "id", "id", ""],
        10,
    )
    assert result["columns"] == ["d", "dt", "b", "u", "f", "nan", "j", "time", "neg", "id", "id_2", "column_12"]
    assert result["rows"][0] == {
        "d": "12.3400",
        "dt": "2026-10-27T09:30:00+00:00",
        "b": "AP8=",
        "u": "12345678-1234-5678-1234-567812345678",
        "f": 1.5,
        "nan": "nan",
        "j": {"k": ["1.0"]},
        "time": "838:00:00",
        "neg": "-01:30:00.000005",
        "id": 1,
        "id_2": 2,
        "column_12": None,
    }


def test_long_values_are_cut_and_flagged():
    limit = db_engines.MAX_VALUE_CHARS
    result = db_engines._collect(
        [("x" * (limit + 10), b"\x01" * limit, {"k": "y" * limit}, "short")], lambda: ["t", "b", "j", "s"], 10
    )
    row = result["rows"][0]
    assert len(row["t"]) == limit
    assert len(row["b"]) == limit  # base64 of the first three-quarters of the limit
    assert isinstance(row["j"], str) and len(row["j"]) == limit
    assert row["s"] == "short"
    assert result["values_truncated"] is True and result["truncated"] is False


def test_results_stop_at_the_response_size_limit():
    with patch.object(db_engines, "MAX_RESPONSE_BYTES", 100):
        result = db_engines._collect([("a" * 40,)] * 5, lambda: ["v"], 10)
    assert result["row_count"] == 2
    assert result["truncated"] is True and result["truncation_reason"] == "max_bytes"
    assert result["values_truncated"] is False


def test_empty_results_still_report_columns():
    assert db_engines._collect([], lambda: ["a", "a"], 10) == _result([], ["a", "a_2"])


def test_describe_database_error_formats_driver_errors():
    sqlserver = pymssql.OperationalError(
        18456, b"Login failed for user 'reader'.DB-Lib error message 20018, severity 14:\nGeneral SQL Server error"
    )
    assert describe_database_error(sqlserver) == "18456: Login failed for user 'reader'."
    assert describe_database_error(pymysql.err.OperationalError(1045, "Access denied")) == "1045: Access denied"
    assert describe_database_error(db_engines.psycopg.OperationalError("connection refused\n")) == "connection refused"
    assert describe_database_error(StatementTimeoutError("cancelled")) == "cancelled"


# Error shapes captured from pymssql 2.4.6 in the AWS Lambda Python 3.13 image.
@pytest.mark.parametrize(
    "args,expected",
    [
        (
            (
                20009,
                b"DB-Lib error message 20009, severity 9:\nUnable to connect: TDS server is unavailable or does "
                b"not exist (db.example.com)\nNet-Lib error during Connection refused (111)\n",
            ),
            "20009: Unable to connect: TDS server is unavailable or does not exist (db.example.com); "
            "Net-Lib error during Connection refused (111)",
        ),
        (
            (
                20009,
                b"DB-Lib error message 20009, severity 9:\nUnable to connect: TDS server is unavailable or does "
                b"not exist (192.0.2.1)\nNet-Lib error during Connection timed out (110)\n",
            ),
            "20009: Unable to connect: TDS server is unavailable or does not exist (192.0.2.1); "
            "Net-Lib error during Connection timed out (110)",
        ),
        (
            (
                18456,
                b"Login failed for user 'reader'.DB-Lib error message 20018, severity 14:\nGeneral SQL Server "
                b"error: Check messages from the SQL Server\nDB-Lib error message 20002, severity 9:\n"
                b"TDS server connection failed (db.example.com)\n",
            ),
            "18456: Login failed for user 'reader'.",
        ),
        # pymssql dropped the server's message and kept a stale number from an earlier failure.
        (
            (
                18456,
                b"DB-Lib error message 20018, severity 14:\nGeneral SQL Server error: Check messages from the "
                b"SQL Server\nDB-Lib error message 20002, severity 9:\nTDS server connection failed (db.example.com)\n",
            ),
            "20018: SQL Server rejected the login. Check the user name, password and database name, "
            "and that the login can open the database.",
        ),
        (
            (18456, b"DB-Lib error message 20002, severity 9:\nTDS server connection failed (db.example.com)\n"),
            "20002: TDS server connection failed (db.example.com)",
        ),
    ],
)
def test_sqlserver_connection_errors_name_the_real_cause(args, expected):
    assert describe_database_error(pymssql.OperationalError(args)) == expected


@pytest.mark.parametrize(
    "database_type,connection_string,secrets",
    [
        ("postgresql", "postgresql://u:pg-secret@h/db", ["pg-secret"]),
        ("mysql", "mysql://u:my%40secret@h/db", ["my@secret", "my%40secret"]),
        ("sqlserver", "Server=h;User ID=u;Password={ms;secret}", ["ms;secret"]),
    ],
)
def test_redact_secrets_removes_passwords_and_connection_strings(database_type, connection_string, secrets):
    credentials = {"database_type": database_type, "connection_string": connection_string}
    message = redact_secrets(f"failed: {' / '.join(secrets)} / {connection_string}", credentials)
    assert message == "failed: " + " / ".join(["[redacted]"] * (len(secrets) + 1))


def test_redact_secrets_tolerates_unparseable_settings():
    assert redact_secrets("plain message", {"database_type": "oracle", "connection_string": ""}) == "plain message"
