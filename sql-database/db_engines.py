"""Connection-string parsing and per-engine execution for the SQL Database integration.

Every action opens a fresh connection and closes it before returning. Queries
run inside a database-enforced read-only transaction (PostgreSQL, MySQL) or a
transaction that is never committed (SQL Server, which has no read-only mode),
so a write that slipped past sql_guard.py is still refused or discarded.
"""

import base64
import binascii
import contextlib
import datetime
import decimal
import functools
import hashlib
import json
import math
import os
import re
import ssl
import tempfile
import threading
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, quote, unquote, urlsplit

import certifi
import psycopg
import pymssql
import pymysql
import pymysql.cursors
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.datetime import DateLoader, TimeLoader, TimestampLoader, TimestamptzLoader, TimetzLoader
from psycopg.types.string import TextLoader
from pymysql.constants import CLIENT, FIELD_TYPE
from pymysql.converters import conversions

from sql_guard import split_placeholders

SQLSERVER = "sqlserver"
POSTGRESQL = "postgresql"
MYSQL = "mysql"

ENGINE_ALIASES = {
    "sqlserver": SQLSERVER,
    "mssql": SQLSERVER,
    "azuresql": SQLSERVER,
    "microsoftsqlserver": SQLSERVER,
    "postgresql": POSTGRESQL,
    "postgres": POSTGRESQL,
    "pg": POSTGRESQL,
    "mysql": MYSQL,
    "mariadb": MYSQL,
}
SQLGLOT_DIALECTS = {SQLSERVER: "tsql", POSTGRESQL: "postgres", MYSQL: "mysql"}

READ_ONLY = "read-only"
READ_WRITE = "read-write"

CONNECT_TIMEOUT_SECONDS = 15
APPLICATION_NAME = "Autohive"

# Results stay well under AWS Lambda's 6 MB response limit, and single long
# values cannot fill an agent's context on their own.
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_VALUE_CHARS = 64 * 1024
MAX_RETURNED_ROWS = 1000


class ConnectionConfigError(ValueError):
    """Raised when the connection settings are missing or invalid."""


class StatementTimeoutError(Exception):
    """Raised when a statement was cancelled because it ran past its timeout."""


class CommitOutcomeUnknownError(Exception):
    """Raised when the connection failed during COMMIT, so the change may or may not have been saved."""


DATABASE_ERRORS = (
    psycopg.Error,
    pymysql.err.MySQLError,
    pymssql.Error,
    StatementTimeoutError,
    CommitOutcomeUnknownError,
)

# libpq options that read or write local files (sslkey, passfile, service,
# sslkeylogfile, ...) are deliberately absent: the connection string is user input.
POSTGRES_ALLOWED_PARAMS = {
    "host",
    "hostaddr",
    "port",
    "dbname",
    "user",
    "password",
    "sslmode",
    "sslnegotiation",
    "channel_binding",
    "connect_timeout",
    "application_name",
    "options",
    "target_session_attrs",
    "load_balance_hosts",
    "keepalives",
    "keepalives_idle",
    "keepalives_interval",
    "keepalives_count",
    "tcp_user_timeout",
}

MYSQL_SSL_MODES = {"DISABLED", "PREFERRED", "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}

# ADO.NET / ODBC keywords, lower-cased with spaces removed.
SQLSERVER_KEYS = {
    "server": "server",
    "datasource": "server",
    "address": "server",
    "addr": "server",
    "networkaddress": "server",
    "database": "database",
    "initialcatalog": "database",
    "userid": "user",
    "uid": "user",
    "user": "user",
    "username": "user",
    # These values name a driver parameter; they are not credentials.
    "password": "password",  # nosec B105
    "pwd": "password",  # nosec B105
    "encrypt": "encrypt",
    "trustservercertificate": "trust_server_certificate",
    "connectiontimeout": "connect_timeout",
    "connecttimeout": "connect_timeout",
    "timeout": "connect_timeout",
    "applicationname": "application_name",
    "app": "application_name",
    "applicationintent": "application_intent",
    "integratedsecurity": "integrated_security",
    "trustedconnection": "integrated_security",
    "authentication": "authentication",
}
# Common in copied connection strings and safe to ignore.
SQLSERVER_IGNORED_KEYS = {
    "driver",
    "persistsecurityinfo",
    "multipleactiveresultsets",
    "pooling",
    "maxpoolsize",
    "minpoolsize",
    "multisubnetfailover",
    "packetsize",
    "workstationid",
    "wsid",
    "currentlanguage",
    "language",
    "connectretrycount",
    "connectretryinterval",
    "loadbalancetimeout",
    "connectionlifetime",
    "commandtimeout",
    "enlist",
    "transparentnetworkipresolution",
}
# Microsoft keywords that are recognised but not supported. Only these are named
# in errors: any other "keyword" may be part of a password that contains a semicolon.
SQLSERVER_UNSUPPORTED_KEYS = {
    "attachdbfilename",
    "extendedproperties",
    "initialfilename",
    "userinstance",
    "failoverpartner",
    "failoverpartnerspn",
    "columnencryptionsetting",
    "attestationprotocol",
    "enclaveattestationurl",
    "hostnameincertificate",
    "servercertificate",
    "serverspn",
    "contextconnection",
    "asynchronousprocessing",
    "async",
    "replication",
    "typesystemversion",
    "poolblockingperiod",
    "ipaddresspreference",
    "networklibrary",
    "network",
    "net",
}
TRUE_VALUES = {"true", "yes", "1", "mandatory"}
FALSE_VALUES = {"false", "no", "0", "optional"}

# FreeTDS timeout settings and FREETDSCONF are process-wide. Keep each SQL
# Server operation, including connection setup and close, inside the same lock.
_FREETDS_LOCK = threading.RLock()

# Files the drivers read by path (CA bundles and the FreeTDS config) live in a
# private directory and are written again if something removes them.
_FILES_DIR = tempfile.mkdtemp(prefix="autohive-sql-")
# FreeTDS reads this file on every connect. The variable is set once, at import,
# so the environment never changes while another thread (libpq) may be reading it.
_FREETDS_CONF = os.path.join(_FILES_DIR, "freetds.conf")
os.environ["FREETDSCONF"] = _FREETDS_CONF

# FreeTDS errors that mean the connection failed rather than the server refusing the statement.
_FREETDS_CONNECTION_ERRORS = {20003, 20004, 20006, 20017, 20047}

_DBLIB_HEADER = re.compile(r"DB-Lib error message (\d+), severity \d+:\n?")

_PEM_CERTIFICATE = re.compile(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)


def resolve_engine(database_type: Optional[str]) -> str:
    key = "".join(ch for ch in (database_type or "").lower() if ch.isalnum())
    engine = ENGINE_ALIASES.get(key)
    if engine is None:
        raise ConnectionConfigError(
            f"Unsupported database type {database_type!r}. Use one of: sqlserver, postgresql, mysql."
        )
    return engine


def resolve_access_mode(access_mode: Optional[str]) -> str:
    """Connections are read-only unless writes are explicitly enabled."""
    key = "".join(ch for ch in (access_mode or "").lower() if ch.isalnum())
    if key in ("", "readonly"):
        return READ_ONLY
    if key == "readwrite":
        return READ_WRITE
    raise ConnectionConfigError(f"Unsupported access mode {access_mode!r}. Use read-only or read-write.")


def ca_certificate_file(pem: Optional[str]) -> Optional[str]:
    """Validate a pasted PEM bundle and return the path of a file containing it."""
    if not pem or not pem.strip():
        return None
    return _private_file(_ca_bundle(pem), ".pem")


@functools.lru_cache(maxsize=16)
def _ca_bundle(pem: str) -> str:
    """Validate a pasted PEM bundle once and return it with standard line wrapping."""
    certificates = []
    for body in _PEM_CERTIFICATE.findall(pem):
        # Single-line form fields drop newlines, so re-wrap each certificate.
        encoded = "".join(body.split())
        try:
            base64.b64decode(encoded, validate=True)
        except binascii.Error:
            raise ConnectionConfigError("The CA certificate is not valid PEM.") from None
        lines = "\n".join(encoded[i : i + 64] for i in range(0, len(encoded), 64))
        certificates.append(f"-----BEGIN CERTIFICATE-----\n{lines}\n-----END CERTIFICATE-----\n")
    if not certificates:
        raise ConnectionConfigError("The CA certificate must contain a -----BEGIN CERTIFICATE----- block.")
    bundle = "".join(certificates)
    try:
        ssl.create_default_context(cadata=bundle)
    except ssl.SSLError:
        raise ConnectionConfigError("The CA certificate could not be loaded. Paste the CA's PEM text.") from None
    return bundle


def run_query(
    engine: str,
    connection_string: str,
    sql: str,
    parameters: Optional[Sequence[Any]],
    max_rows: int,
    timeout_seconds: int,
    ca_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a read-only query and return at most ``max_rows`` rows."""
    runner = {POSTGRESQL: _postgres_query, MYSQL: _mysql_query, SQLSERVER: _sqlserver_query}[engine]
    with _FREETDS_LOCK if engine == SQLSERVER else contextlib.nullcontext():
        return runner(connection_string, sql, parameters, max_rows, timeout_seconds, ca_file)


def run_write(
    engine: str,
    connection_string: str,
    sql: str,
    parameters: Optional[Sequence[Any]],
    timeout_seconds: int,
    ca_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one write statement in a transaction and commit it."""
    runner = {POSTGRESQL: _postgres_write, MYSQL: _mysql_write, SQLSERVER: _sqlserver_write}[engine]
    with _FREETDS_LOCK if engine == SQLSERVER else contextlib.nullcontext():
        rows_affected, returned = runner(connection_string, sql, parameters, timeout_seconds, ca_file)
    return {
        "rows_affected": rows_affected,
        "columns": returned["columns"],
        "returned_rows": returned["rows"],
        "returned_rows_truncated": returned["truncated"] or returned["values_truncated"],
    }


def describe_database_error(error: Exception) -> str:
    """Turn a driver exception into a single readable message."""
    # pymssql.connect() wraps the (number, message) pair in another tuple.
    args = error.args[0] if len(error.args) == 1 and isinstance(error.args[0], tuple) else error.args
    if isinstance(error, pymssql.Error) and len(args) == 2 and isinstance(args[1], bytes):
        return _describe_sqlserver_error(args[0], args[1].decode("utf-8", "replace"))
    if isinstance(error, pymysql.err.MySQLError) and len(error.args) == 2:
        return f"{error.args[0]}: {error.args[1]}"
    return str(error).strip() or type(error).__name__


def _describe_sqlserver_error(number: Any, text: str) -> str:
    # The text is the server's message, if any, then FreeTDS entries:
    # "DB-Lib error message <code>, severity <n>:\n<detail lines>".
    parts = _DBLIB_HEADER.split(text)
    server_message = parts[0].strip()
    if server_message:
        return f"{number}: {server_message}"
    # Without a server message, use the codes in the text: pymssql does not reset
    # its process-wide error number between failed connections, so it can be stale.
    codes = parts[1::2]
    details: List[str] = []
    for line in "\n".join(parts[2::2]).splitlines():
        if line.strip() and line.strip() not in details:
            details.append(line.strip())
    if not codes:
        return f"{number}: SQL Server connection failed"
    if "20018" in codes and "20002" in codes:
        # The server sent its reason (e.g. login failed), which pymssql may have dropped.
        return (
            "20018: SQL Server rejected the login. Check the user name, password and database name, "
            "and that the login can open the database."
        )
    return f"{codes[0]}: {'; '.join(details)}"


def redact_secrets(message: str, credentials: Dict[str, Any]) -> str:
    """Remove the connection string and password from a message before it is shown."""
    connection_string = str(credentials.get("connection_string") or "").strip()
    secrets = {connection_string}
    with contextlib.suppress(Exception):  # best effort: the string may not parse
        password = _password(resolve_engine(credentials.get("database_type")), connection_string)
        secrets |= {password, quote(password, safe="")}
    for secret in sorted(secrets, key=len, reverse=True):
        if len(secret) >= 4:
            message = message.replace(secret, "[redacted]")
    return message


_CA_WITHOUT_ENCRYPTION = (
    "A CA certificate is set, but the connection string turns encryption off ({setting}). "
    "Remove {setting} or clear the CA certificate."
)


def _connect_timeout(seconds: int) -> int:
    """Cap the connect timeout; 0 or less means "no limit" in connection strings, so use the cap."""
    return CONNECT_TIMEOUT_SECONDS if seconds <= 0 else min(seconds, CONNECT_TIMEOUT_SECONDS)


def _commit(conn: Any, connection_lost: Callable[[Exception], bool]) -> None:
    """Commit, reporting a lost connection as an unknown outcome rather than a failure."""
    try:
        conn.commit()
    except Exception as error:
        if connection_lost(error):
            raise CommitOutcomeUnknownError(
                "the connection was lost while committing, so the change may or may not have been saved. "
                "Check the data before running the statement again."
            ) from None
        raise


def _password(engine: str, connection_string: str) -> str:
    if engine == POSTGRESQL:
        return conninfo_to_dict(connection_string).get("password") or ""
    if engine == MYSQL:
        return unquote(urlsplit(connection_string.strip()).password or "")
    return sqlserver_connect_params(connection_string)["password"]


# ---- PostgreSQL ----


def postgres_connect_params(connection_string: str, ca_file: Optional[str] = None) -> Dict[str, Any]:
    try:
        params = conninfo_to_dict(connection_string)
    except psycopg.ProgrammingError:
        # The parser's message can echo part of the string, including the password.
        raise ConnectionConfigError(
            "The PostgreSQL connection string could not be parsed. Use "
            "postgresql://user:password@host:5432/database or host=... dbname=... user=... password=..."
        ) from None
    unsupported = sorted(set(params) - POSTGRES_ALLOWED_PARAMS)
    if unsupported:
        raise ConnectionConfigError(f"Unsupported PostgreSQL connection parameter(s): {', '.join(unsupported)}")
    if not params.get("host") and not params.get("hostaddr"):
        raise ConnectionConfigError("The PostgreSQL connection string must include a host.")
    # Encrypt unless the string opts out. A custom CA is always used to verify the
    # server: modes that would skip verification become verify-ca, which is also
    # what libpq does for sslmode=require when a root certificate is present.
    sslmode = params.setdefault("sslmode", "verify-full" if ca_file else "require")
    if ca_file and sslmode == "disable":
        raise ConnectionConfigError(_CA_WITHOUT_ENCRYPTION.format(setting="sslmode=disable"))
    if ca_file and sslmode in ("allow", "prefer", "require"):
        params["sslmode"] = "verify-ca"
    if params["sslmode"] in ("verify-ca", "verify-full"):
        params["sslrootcert"] = ca_file or certifi.where()
    try:
        connect_timeout = int(params.get("connect_timeout") or 0)
    except ValueError:
        raise ConnectionConfigError("connect_timeout must be a whole number of seconds.") from None
    params["connect_timeout"] = str(_connect_timeout(connect_timeout))
    params.setdefault("application_name", APPLICATION_NAME)
    return params


def _text_when_out_of_range(loader: type) -> type:
    """Return values Python cannot represent (infinity, BC dates, 24:00) as PostgreSQL's text."""

    class Loader(loader):
        def load(self, data):
            try:
                return super().load(data)
            except psycopg.DataError:
                return bytes(data).decode()

    return Loader


_POSTGRES_LOADERS = {
    "date": _text_when_out_of_range(DateLoader),
    "time": _text_when_out_of_range(TimeLoader),
    "timetz": _text_when_out_of_range(TimetzLoader),
    "timestamp": _text_when_out_of_range(TimestampLoader),
    "timestamptz": _text_when_out_of_range(TimestamptzLoader),
    # The session's intervalstyle is iso_8601, so intervals arrive as e.g. P1DT2H.
    "interval": TextLoader,
}


def _postgres_connect(connection_string: str, ca_file: Optional[str]) -> Any:
    conn = psycopg.connect(**postgres_connect_params(connection_string, ca_file))
    for type_name, loader in _POSTGRES_LOADERS.items():
        conn.adapters.register_loader(type_name, loader)
    return conn


def _postgres_session(cursor: Any, timeout_seconds: int) -> None:
    # Transaction-scoped (is_local) so nothing leaks through PgBouncer-style poolers.
    # standard_conforming_strings keeps the server's string parsing the same as sql_guard's.
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true), set_config('standard_conforming_strings', 'on', true), "
        "set_config('intervalstyle', 'iso_8601', true)",
        [str(timeout_seconds * 1000)],
    )


def _postgres_query(connection_string, sql, parameters, max_rows, timeout_seconds, ca_file):
    conn = _postgres_connect(connection_string, ca_file)
    try:
        conn.read_only = True
        cursor = conn.cursor()
        _postgres_session(cursor, timeout_seconds)
        # stream() always uses the extended protocol, so the server refuses
        # multi-statement text, and rows are read one at a time.
        return _collect(cursor.stream(sql, parameters), lambda: _column_names(cursor), max_rows)
    finally:
        conn.close()  # never committed: the read-only transaction is discarded


def _postgres_write(connection_string, sql, parameters, timeout_seconds, ca_file):
    conn = _postgres_connect(connection_string, ca_file)
    try:
        cursor = conn.cursor()
        _postgres_session(cursor, timeout_seconds)
        # Pipeline mode always uses the extended protocol, so the server refuses
        # multi-statement text for writes too.
        with conn.pipeline():
            cursor.execute(sql, parameters)
        returned = _collect_returned(cursor)
        rows_affected = cursor.rowcount
        _commit(conn, lambda error: conn.broken)
    finally:
        conn.close()
    return rows_affected, returned


# ---- MySQL / MariaDB ----

_MYSQL_CONVERSIONS = {
    **conversions,
    FIELD_TYPE.BIT: lambda value: int.from_bytes(value, "big"),
    FIELD_TYPE.JSON: json.loads,
}


def mysql_connect_params(connection_string: str, ca_file: Optional[str] = None) -> Dict[str, Any]:
    try:
        parts = urlsplit(connection_string.strip())
        host = parts.hostname
    except ValueError:
        # urlsplit may include the entire credential-bearing authority in errors.
        raise ConnectionConfigError("The MySQL connection string could not be parsed. Check its URL format.") from None
    if parts.scheme.lower() not in ("mysql", "mariadb") or not host:
        raise ConnectionConfigError(
            "MySQL connection strings must look like mysql://user:password@host:3306/database "
            "(percent-encode special characters in the password)."
        )
    try:
        port = parts.port or 3306
    except ValueError:
        raise ConnectionConfigError("The MySQL connection string has an invalid port.") from None

    # Encrypt unless the string opts out. A custom CA is always used to verify the
    # server: modes that would skip verification become VERIFY_CA.
    ssl_mode = "VERIFY_IDENTITY" if ca_file else "REQUIRED"
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower().replace("_", "-") not in ("ssl-mode", "sslmode"):
            # The key is not repeated: an unencoded ? in the password also ends up here.
            raise ConnectionConfigError(
                "MySQL connection strings support only the ssl-mode parameter. "
                "Percent-encode special characters such as ? # / @ in the password."
            )
        ssl_mode = value.upper().replace("-", "_")
    if ssl_mode not in MYSQL_SSL_MODES:
        raise ConnectionConfigError(f"ssl-mode must be one of: {', '.join(sorted(MYSQL_SSL_MODES))}")
    if ca_file and ssl_mode == "DISABLED":
        raise ConnectionConfigError(_CA_WITHOUT_ENCRYPTION.format(setting="ssl-mode=DISABLED"))
    if ca_file and ssl_mode in ("PREFERRED", "REQUIRED"):
        ssl_mode = "VERIFY_CA"

    params: Dict[str, Any] = {
        "host": host,
        "port": port,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": unquote(parts.path.lstrip("/")) or None,
        "charset": "utf8mb4",
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "program_name": APPLICATION_NAME,
        # A hostile server could otherwise ask the client to upload local files.
        "local_infile": False,
        # Report matched rows, like PostgreSQL and SQL Server, not only changed rows.
        "client_flag": CLIENT.FOUND_ROWS,
        "conv": _MYSQL_CONVERSIONS,
    }
    if ssl_mode == "DISABLED":
        params["ssl_disabled"] = True
    elif ssl_mode == "REQUIRED":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        params["ssl"] = context
    elif ssl_mode in ("VERIFY_CA", "VERIFY_IDENTITY"):
        params["ssl_ca"] = ca_file or certifi.where()
        params["ssl_verify_cert"] = True
        params["ssl_verify_identity"] = ssl_mode == "VERIFY_IDENTITY"
    # PREFERRED is PyMySQL's default: TLS only when the server offers it.
    return params


def _mysql_connect(connection_string: str, timeout_seconds: int, cursorclass: type, ca_file=None) -> Any:
    return pymysql.connect(
        **mysql_connect_params(connection_string, ca_file),
        autocommit=False,
        read_timeout=timeout_seconds + 5,
        write_timeout=timeout_seconds + 5,
        cursorclass=cursorclass,
    )


def _mysql_session(conn: Any, cursor: Any, timeout_seconds: int) -> None:
    # Match the tokenizer: double quotes are strings and backslashes escape them.
    # Composite modes would re-enable ANSI_QUOTES when the mode list is assigned.
    cursor.execute("SELECT @@SESSION.sql_mode")
    sql_mode = cursor.fetchone()[0]
    cursor.fetchall()  # consume the streaming cursor's EOF before the next command
    incompatible_modes = {
        "NO_BACKSLASH_ESCAPES",
        "ANSI_QUOTES",
        "ANSI",
        "DB2",
        "MAXDB",
        "MSSQL",
        "ORACLE",
        "POSTGRESQL",
    }
    modes = [mode for mode in sql_mode.split(",") if mode.upper() not in incompatible_modes]
    cursor.execute("SET SESSION sql_mode = %s", (",".join(modes),))
    # Lock waits (row and metadata) give up at the timeout instead of 50 seconds or more.
    cursor.execute(
        "SET SESSION lock_wait_timeout = %s, SESSION innodb_lock_wait_timeout = %s",
        (timeout_seconds, timeout_seconds),
    )
    if "mariadb" in conn.get_server_info().lower():
        cursor.execute("SET SESSION max_statement_time = %s", (timeout_seconds,))
    else:
        cursor.execute("SET SESSION max_execution_time = %s", (timeout_seconds * 1000,))


@contextlib.contextmanager
def _mysql_cancel_on_timeout(conn: Any, connection_string: str, ca_file: Optional[str], timeout_seconds: int):
    """When the client read times out, stop the statement the server would otherwise keep running."""
    thread_id = conn.thread_id()
    try:
        yield
    except pymysql.err.OperationalError as error:
        if error.args[0] != 2013 or "timed out" not in str(error.args[-1]):
            raise
        with contextlib.suppress(pymysql.err.MySQLError, OSError):
            limits = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
            killer = pymysql.connect(**{**mysql_connect_params(connection_string, ca_file), **limits})
            try:
                killer.cursor().execute("KILL QUERY %s", (thread_id,))
            finally:
                killer.close()
        unit = "second" if timeout_seconds == 1 else "seconds"
        raise StatementTimeoutError(
            f"the statement did not finish within {timeout_seconds} {unit} and was cancelled"
        ) from None


def _mysql_query(connection_string, sql, parameters, max_rows, timeout_seconds, ca_file):
    # SSCursor streams rows instead of buffering the whole result in memory.
    conn = _mysql_connect(connection_string, timeout_seconds, pymysql.cursors.SSCursor, ca_file)
    cursor = None
    try:
        with _mysql_cancel_on_timeout(conn, connection_string, ca_file, timeout_seconds):
            cursor = conn.cursor()
            _mysql_session(conn, cursor, timeout_seconds)
            # The server stops sending rows after this many (an explicit LIMIT in the query wins).
            cursor.execute("SET SESSION sql_select_limit = %s", (max_rows + 1,))
            # The session setting also covers statements that implicitly commit.
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(sql, parameters)
            return _collect(cursor, lambda: _column_names(cursor), max_rows)
    finally:
        # SSCursor.close() and MySQLResult.__del__ otherwise drain every unread
        # row, including when an explicit LIMIT overrides sql_select_limit.
        # PyMySQL has no public cancel API. This disposable connection is being
        # closed, so disable its cleanup drain (covered by live driver tests).
        if cursor is not None and cursor._result is not None:
            cursor._result.unbuffered_active = False
            cursor._result.has_next = False
        conn.close()  # never committed: the server rolls the transaction back
        if cursor is not None:
            cursor.close()


def _mysql_write(connection_string, sql, parameters, timeout_seconds, ca_file):
    conn = _mysql_connect(connection_string, timeout_seconds, pymysql.cursors.Cursor, ca_file)
    try:
        with _mysql_cancel_on_timeout(conn, connection_string, ca_file, timeout_seconds):
            cursor = conn.cursor()
            _mysql_session(conn, cursor, timeout_seconds)
            cursor.execute(sql, parameters)
            returned = _collect_returned(cursor)
            rows_affected = cursor.rowcount
        # Outside the timeout handler: once COMMIT is sent, KILL QUERY cannot undo it.
        _commit(conn, _mysql_connection_lost)
    finally:
        conn.close()
    return rows_affected, returned


def _mysql_connection_lost(error: Exception) -> bool:
    # 2006: server has gone away, 2013: lost connection during query (including read timeouts).
    return isinstance(error, pymysql.err.InterfaceError) or (
        isinstance(error, pymysql.err.OperationalError) and error.args[:1] in ((2006,), (2013,))
    )


# ---- SQL Server ----


def sqlserver_connect_params(connection_string: str, ca_file: Optional[str] = None) -> Dict[str, Any]:
    settings: Dict[str, str] = {}
    for key, value in _split_key_values(connection_string):
        normalized = key.replace(" ", "").replace("_", "")
        if normalized in SQLSERVER_IGNORED_KEYS:
            continue
        if normalized in SQLSERVER_UNSUPPORTED_KEYS:
            raise ConnectionConfigError(f"The SQL Server connection string keyword {key!r} is not supported.")
        if normalized not in SQLSERVER_KEYS:
            raise ConnectionConfigError(
                "The SQL Server connection string has a keyword that is not supported. Use Server, Database, "
                "User ID, Password, Encrypt, TrustServerCertificate, Connection Timeout, Application Name and "
                "ApplicationIntent, and wrap a password that contains ; in braces, e.g. Password={a;b}."
            )
        settings[SQLSERVER_KEYS[normalized]] = value

    if settings.get("integrated_security", "").lower() in TRUE_VALUES | {"sspi"}:
        raise ConnectionConfigError(
            "Windows authentication (Integrated Security) is not supported. Use a SQL login with User ID and Password."
        )
    if settings.get("authentication", "sqlpassword").replace(" ", "").lower() != "sqlpassword":
        raise ConnectionConfigError(
            "Only SQL authentication is supported (Microsoft Entra ID authentication is not). "
            "Remove the Authentication keyword and use a SQL login."
        )
    server = settings.get("server", "")
    if not server or not settings.get("user"):
        raise ConnectionConfigError("The SQL Server connection string must include Server and User ID.")

    if server.lower().startswith("tcp:"):
        server = server[4:]
    host, _, port = server.partition(",")
    if port and not port.strip().isdigit():
        raise ConnectionConfigError("The SQL Server port must be a number, e.g. Server=myhost,1433.")

    encrypt = settings.get("encrypt", "true").lower()
    if encrypt == "strict":
        raise ConnectionConfigError("Encrypt=Strict (TDS 8) is not supported. Use Encrypt=True.")
    if encrypt not in TRUE_VALUES | FALSE_VALUES:
        raise ConnectionConfigError("Encrypt must be True or False.")
    trust_certificate = settings.get("trust_server_certificate", "false").lower() in TRUE_VALUES
    if ca_file and encrypt in FALSE_VALUES:
        raise ConnectionConfigError(_CA_WITHOUT_ENCRYPTION.format(setting="Encrypt=False"))
    # A custom CA is always used to verify the server. TrustServerCertificate=True
    # then only skips the host name check, like PostgreSQL's verify-ca.
    verify_certificate = encrypt in TRUE_VALUES and (bool(ca_file) or not trust_certificate)

    try:
        login_timeout = int(settings.get("connect_timeout") or 0)
    except ValueError:
        raise ConnectionConfigError("Connection Timeout must be a number of seconds.") from None

    params = {
        "server": host.strip(),
        "user": settings["user"],
        "password": settings.get("password", ""),
        "database": settings.get("database", ""),
        "appname": settings.get("application_name", APPLICATION_NAME),
        "login_timeout": _connect_timeout(login_timeout),
        "read_only": settings.get("application_intent", "").replace(" ", "").lower() == "readonly",
        # Defaults match Microsoft.Data.SqlClient: encrypted and certificate-verified.
        "encryption": "require" if encrypt in TRUE_VALUES else "request",
        "ca_file": (ca_file or certifi.where()) if verify_certificate else None,
        "check_hostname": not trust_certificate,
    }
    if port:
        params["port"] = port.strip()
    return params


def _split_key_values(text: str) -> List[Tuple[str, str]]:
    """Parse ``key=value;`` pairs, honouring "quoted", 'quoted' and {braced} values."""
    pairs = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n;":
            i += 1
        if i >= n:
            break
        equals = text.find("=", i)
        if equals == -1:
            raise ConnectionConfigError("The SQL Server connection string must be a list of Key=Value; pairs.")
        key = text[i:equals].strip().lower()
        i = equals + 1
        while i < n and text[i] in " \t":
            i += 1
        if i < n and text[i] in "\"'{":
            closing = "}" if text[i] == "{" else text[i]
            i += 1
            chars = []
            while True:
                if i >= n:
                    raise ConnectionConfigError("A quoted value in the SQL Server connection string is not closed.")
                if text[i] == closing:
                    if text[i + 1 : i + 2] == closing:  # doubled quote or brace is a literal
                        chars.append(closing)
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(text[i])
                i += 1
            value = "".join(chars)
        else:
            end = text.find(";", i)
            end = n if end == -1 else end
            value = text[i:end].strip()
            i = end
        pairs.append((key, value))
    return pairs


def _freetds_config(ca_file: Optional[str], check_hostname: bool) -> str:
    """Return FreeTDS settings; with a CA file FreeTDS verifies the server certificate."""
    if not ca_file:
        return "[global]\n"
    return f"[global]\n\tca file = {ca_file}\n\tcheck certificate hostname = {'yes' if check_hostname else 'no'}\n"


def _sqlserver_connect(connection_string: str, timeout_seconds: int, ca_file: Optional[str] = None) -> Any:
    params = sqlserver_connect_params(connection_string, ca_file)
    config = _freetds_config(params.pop("ca_file"), params.pop("check_hostname"))
    # pymssql has no certificate option; FreeTDS reads FREETDSCONF on every connect,
    # so the file is rewritten each time (and restored if it was deleted).
    with _FREETDS_LOCK:
        _write_file(_FREETDS_CONF, config)
        return pymssql.connect(**params, timeout=timeout_seconds, tds_version="7.4", autocommit=False)


def _sqlserver_parameters(sql: str, parameters: Optional[Sequence[Any]]) -> Tuple[str, Optional[tuple]]:
    # pymssql has no %% escape, so unescape it here; sql_guard has already
    # rejected SQL whose literal text would contain %s or %d. pymssql copies
    # values into the SQL text, so a space before each one stops a negative
    # number after a minus sign (x-%s with -1) from becoming a -- comment.
    if parameters is None:
        return sql, None
    return " %s".join(split_placeholders(sql)), tuple(parameters)


def _sqlserver_connection_lost(error: Exception) -> bool:
    if isinstance(error, pymssql.InterfaceError):
        return True
    code = re.search(r"DB-Lib error message (\d+)", str(error))
    return code is not None and int(code.group(1)) in _FREETDS_CONNECTION_ERRORS


def _sqlserver_query(connection_string, sql, parameters, max_rows, timeout_seconds, ca_file):
    conn = _sqlserver_connect(connection_string, timeout_seconds, ca_file)
    try:
        cursor = conn.cursor()
        # SQL Server has no read-only transaction. pymssql opened a transaction that
        # is never committed; with implicit transactions on, a write after a stray
        # COMMIT starts a new transaction that is also discarded on close.
        cursor.execute("SET IMPLICIT_TRANSACTIONS ON")
        cursor.execute(*_sqlserver_parameters(sql, parameters))
        return _collect(cursor, lambda: _column_names(cursor), max_rows)
    finally:
        conn.close()


def _sqlserver_write(connection_string, sql, parameters, timeout_seconds, ca_file):
    conn = _sqlserver_connect(connection_string, timeout_seconds, ca_file)
    try:
        cursor = conn.cursor()
        cursor.execute(*_sqlserver_parameters(sql, parameters))
        returned = _collect_returned(cursor)
        rows_affected = cursor.rowcount
        _commit(conn, _sqlserver_connection_lost)
    finally:
        conn.close()
    return rows_affected, returned


# ---- Result shaping ----


def _column_names(cursor: Any) -> List[str]:
    return [column[0] for column in cursor.description or []]


def _collect(rows: Iterable[Sequence[Any]], column_names: Callable[[], List[str]], max_rows: int) -> Dict[str, Any]:
    """Shape rows into JSON objects, stopping at max_rows rows or MAX_RESPONSE_BYTES."""
    columns: Optional[List[str]] = None
    shaped: List[Dict[str, Any]] = []
    size = 0
    reason = None
    values_truncated = False
    for row in rows:
        if len(shaped) == max_rows:
            reason = "max_rows"
            break
        if columns is None:
            columns = _unique_column_names(column_names())
        values = [_shape_value(value) for value in row]
        item = dict(zip(columns, (value for value, _ in values)))
        size += len(json.dumps(item)) + 1
        if size > MAX_RESPONSE_BYTES:
            reason = "max_bytes"
            break
        shaped.append(item)
        values_truncated = values_truncated or any(cut for _, cut in values)
    return {
        "columns": columns if columns is not None else _unique_column_names(column_names()),
        "rows": shaped,
        "row_count": len(shaped),
        "truncated": reason is not None,
        "truncation_reason": reason,
        "values_truncated": values_truncated,
    }


def _collect_returned(cursor: Any) -> Dict[str, Any]:
    """Collect rows from a RETURNING or OUTPUT clause, then read any that were left over."""
    if cursor.description is None:
        return _collect([], list, MAX_RETURNED_ROWS)
    returned = _collect(iter(cursor.fetchone, None), lambda: _column_names(cursor), MAX_RETURNED_ROWS)
    # Read past rows over the cap one at a time, without keeping them, because
    # SQL Server cannot commit while results are pending.
    for _ in iter(cursor.fetchone, None):
        pass
    return returned


def _unique_column_names(names: List[str]) -> List[str]:
    """Name blank columns (e.g. SQL Server's COUNT(*)) and suffix duplicates (id, id_2)."""
    columns: List[str] = []
    for position, name in enumerate(names, start=1):
        base = name or f"column_{position}"
        candidate, suffix = base, 2
        while candidate in columns:
            candidate = f"{base}_{suffix}"
            suffix += 1
        columns.append(candidate)
    return columns


def _shape_value(value: Any) -> Tuple[Any, bool]:
    """Convert a value to JSON, cutting it to MAX_VALUE_CHARS. Returns (value, was_cut)."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        limit = MAX_VALUE_CHARS * 3 // 4  # base64 grows data by a third
        return base64.b64encode(data[:limit]).decode("ascii"), len(data) > limit
    converted = _json_value(value)
    if isinstance(converted, (dict, list)):
        text = json.dumps(converted)
        if len(text) <= MAX_VALUE_CHARS:
            return converted, False
        converted = text  # too long to keep as a structure; return it as cut JSON text
    if isinstance(converted, str) and len(converted) > MAX_VALUE_CHARS:
        return converted[:MAX_VALUE_CHARS], True
    return converted, False


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)  # keeps full precision
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return _format_duration(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)  # UUID, network types, ranges


def _format_duration(value: datetime.timedelta) -> str:
    """Format like MySQL's TIME type: [-]HH:MM:SS[.ffffff], with hours past 24."""
    magnitude = abs(value)
    hours, remainder = divmod(magnitude.days * 86400 + magnitude.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    sign = "-" if value < datetime.timedelta(0) else ""
    text = f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{text}.{magnitude.microseconds:06d}" if magnitude.microseconds else text


def _private_file(content: str, suffix: str) -> str:
    """Return the path of a file holding ``content``, named by its hash and written if missing."""
    path = os.path.join(_FILES_DIR, hashlib.sha256(content.encode()).hexdigest() + suffix)
    if not os.path.exists(path):
        _write_file(path, content)
    return path


def _write_file(path: str, content: str) -> None:
    """Replace ``path`` atomically, so a reader never sees a half-written file."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as handle:
        handle.write(content)
    os.replace(temporary, path)
