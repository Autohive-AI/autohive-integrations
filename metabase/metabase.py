from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    HTTPError,
)
import asyncio
import json
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urlparse

import aiohttp
import sqlglot
from sqlglot import exp
from sqlglot.dialects.mysql import MySQL
from sqlglot.dialects.postgres import Postgres

metabase = Integration.load()

# Metabase caps unaggregated API query results at 2,000 rows (MB_UNAGGREGATED_QUERY_ROW_LIMIT).
MAX_ROWS_LIMIT = 2000
DEFAULT_MAX_ROWS = 100
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200
QUERY_TIMEOUT_SECONDS = 120
DASHBOARD_GRID_WIDTH = 24
DEFAULT_CARD_WIDTH = 12
DEFAULT_CARD_HEIGHT = 6
MAX_CARD_HEIGHT = 50
MAX_ERROR_LENGTH = 500
# The SDK retries any request on network errors and timeouts. Starting a POST/PUT at a retry count
# above its limit sends it exactly once, so a slow create or query is never repeated.
NO_RETRY = 1_000
# Dashcard fields sent back unchanged on PUT (the PUT dashcard shape; server-managed fields are left out).
DASHCARD_PUT_KEYS = (
    "id",
    "card_id",
    "dashboard_tab_id",
    "row",
    "col",
    "size_x",
    "size_y",
    "series",
    "parameter_mappings",
    "visualization_settings",
    "action_id",
    "inline_parameters",
)


# ---- Helper Functions ----


def _credentials(context: ExecutionContext) -> Dict[str, Any]:
    auth = context.auth or {}
    return auth.get("credentials") or auth


def get_api_key(context: ExecutionContext) -> str:
    api_key = str(_credentials(context).get("api_key") or "").strip()
    if not api_key:
        raise ValueError("api_key is required in auth")
    return api_key


def get_base_url(context: ExecutionContext) -> str:
    base_url = str(_credentials(context).get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("base_url is required in auth")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("base_url must be an https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain a username or password")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain a query string or fragment")
    # Metabase can be served from a sub-path (e.g. https://example.com/metabase), so keep the
    # path but drop a trailing /api that users sometimes paste in.
    if base_url.endswith("/api"):
        base_url = base_url[: -len("/api")]
    return base_url


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    headers = {"x-api-key": get_api_key(context), "Content-Type": "application/json"}
    credentials = _credentials(context)
    name = credentials.get("gateway_header_name")
    value = credentials.get("gateway_header_value")
    if name in (None, "") and value in (None, ""):
        return headers
    if not isinstance(name, str) or not isinstance(value, str) or not name or not value:
        raise ValueError("Supply both gateway_header_name and gateway_header_value, or leave both empty.")
    if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
        raise ValueError("gateway_header_name must be a valid HTTP header name.")
    if name.lower() in {
        "x-api-key",
        "host",
        "content-type",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
        "accept-encoding",
    }:
        raise ValueError("gateway_header_name must not override an API or transport header.")
    if not value.strip() or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("gateway_header_value must contain printable ASCII without control characters.")
    headers[name] = value
    return headers


async def _gateway_request(url: str, method: str, headers: Dict[str, str], **kwargs: Any) -> Any:
    # SDK fetch follows redirects and logs error bodies; neither is safe for a gateway secret.
    timeout = aiohttp.ClientTimeout(total=kwargs.pop("timeout", 30))
    kwargs.pop("retry_count", None)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # aiohttp retries PUT on disconnect, but creating a Metabase dashcard is not idempotent.
            session._retry_connection = False
            async with session.request(method, url, headers=headers, allow_redirects=False, **kwargs) as response:
                if 300 <= response.status < 400:
                    raise ValueError("Metabase redirected the request. Use the final HTTPS Metabase URL.")
                if response.status >= 400:
                    # Keep only Metabase's reason fields; action errors redact credentials before showing them.
                    try:
                        body = await response.json(content_type=None)
                    except (ValueError, UnicodeError):
                        body = {}
                    if not isinstance(body, dict):
                        body = {}
                    detail = {k: body[k] for k in ("error", "message", "errors") if k in body}
                    raise HTTPError(response.status, "Request failed. Check gateway and Metabase access.", detail)
                try:
                    return await response.json(content_type=None)
                except (ValueError, UnicodeError):
                    raise ValueError("Metabase returned a response that isn't JSON. Check the Metabase URL.") from None
    except aiohttp.ClientError:
        raise ValueError("Could not connect to Metabase. Check the URL, TLS certificate and gateway access.") from None


def _path_id(value: Any) -> str:
    return quote(str(value), safe="")


async def _api(context: ExecutionContext, method: str, path: str, **kwargs: Any) -> Any:
    if method != "GET":
        kwargs.setdefault("retry_count", NO_RETRY)
    url = f"{get_base_url(context)}/api{path}"
    headers = get_auth_headers(context)
    if _credentials(context).get("gateway_header_name"):
        data = await _gateway_request(url, method, headers, **kwargs)
    else:
        response = await context.fetch(url, method=method, headers=headers, **kwargs)
        data = response.data
    # Metabase always answers with JSON; HTML or an empty body means the URL points somewhere else, such as a
    # login proxy or the wrong path.
    if not isinstance(data, (dict, list)):
        raise ValueError("Metabase returned a response that isn't JSON. Check the Metabase URL.")
    return data


def _required_text(value: Any, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{key} is required")
    return text


# Keys Metabase accepts on a parameter value when running a saved question (parameters.schema/parameter-with-value).
RUN_PARAMETER_KEYS = ("id", "name", "slug", "sectionId", "type", "value", "default", "target", "options")


def _run_parameter(param: Any) -> Any:
    """Shape a filter for running a saved question."""
    if not isinstance(param, dict):
        return param
    # Metabase 0.64+ refuses any other key, such as the widget_type and required that get_question lists.
    param = {k: v for k, v in param.items() if k in RUN_PARAMETER_KEYS}
    # Metabase 0.49 looks a filter up by name before target, and get_question's name is the display label
    # ("Region", not the tag "region"). A template-tag target already names the tag, so the label is dropped.
    target = param.get("target")
    if (
        isinstance(target, list)
        and len(target) > 1
        and isinstance(target[1], list)
        and target[1][:1] == ["template-tag"]
    ):
        param.pop("name", None)
    return param


# Metabase database engine -> sqlglot dialect, so quotes, comments and brackets are read the way that database
# reads them. Other engines are read as generic SQL.
SQL_DIALECTS = {
    "postgres": "postgres",
    "redshift": "redshift",
    "mysql": "mysql",
    "sqlserver": "tsql",
    "bigquery-cloud-sdk": "bigquery",
    "snowflake": "snowflake",
    "oracle": "oracle",
    "sqlite": "sqlite",
    "clickhouse": "clickhouse",
    "sparksql": "spark",
    "databricks": "databricks",
    "presto-jdbc": "presto",
    "athena": "athena",
    "starburst": "trino",
    "teradata": "teradata",
    "druid-jdbc": "druid",
    "duckdb": "duckdb",
}


class MySQLNoBackslashEscapes(MySQL):
    """MySQL on a server with NO_BACKSLASH_ESCAPES, where a backslash in quotes is an ordinary character."""

    class Tokenizer(MySQL.Tokenizer):
        STRING_ESCAPES = ["'", '"']


class MySQLAnsiQuotes(MySQL):
    """MySQL on a server with ANSI_QUOTES, where "..." is a name, so a backslash inside it is an ordinary character."""

    class Tokenizer(MySQL.Tokenizer):
        QUOTES = ["'"]
        IDENTIFIERS = ["`", '"']
        STRING_ESCAPES = ["'", "\\"]


class MySQLAnsiQuotesNoBackslashEscapes(MySQLAnsiQuotes):
    """MySQL on a server with both ANSI_QUOTES and NO_BACKSLASH_ESCAPES."""

    class Tokenizer(MySQLAnsiQuotes.Tokenizer):
        STRING_ESCAPES = ["'"]


class PostgresBackslashEscapes(Postgres):
    """PostgreSQL on a server with standard_conforming_strings off, where a backslash in quotes escapes."""

    class Tokenizer(Postgres.Tokenizer):
        STRING_ESCAPES = ["'", "\\"]


# A server can be set to read a backslash in quotes differently from its default, which moves where text ends.
# Metabase can't say how a server is set, so SQL with a backslash must also be safe under every other reading.
OTHER_BACKSLASH_READINGS = {
    "mysql": (MySQLNoBackslashEscapes, MySQLAnsiQuotes, MySQLAnsiQuotesNoBackslashEscapes),
    "postgres": (PostgresBackslashEscapes,),
}

READ_STATEMENTS = (exp.Select, exp.SetOperation, exp.Values, exp.Describe, exp.Show, exp.Subquery)
# Writes that can sit inside a read statement: WITH x AS (DELETE ...), SELECT ... INTO, SQL Server's
# NEXT VALUE FOR (advances a sequence), Spark's SELECT TRANSFORM(...) USING 'command' (runs a shell command), and
# FOR UPDATE / FOR SHARE (locks rows so other users can't change them).
WRITE_NODES = (exp.DML, exp.DDL, exp.Into, exp.Command, exp.NextValueFor, exp.QueryTransform, exp.Lock)
# SQL Server table hints that lock a table against writers for the length of the query (NOLOCK is fine).
TSQL_LOCK_HINTS = frozenset("holdlock repeatableread serializable tablock tablockx updlock xlock".split())
# EXPLAIN options before the statement it explains (EXPLAIN ANALYZE runs it, so that statement is checked too).
EXPLAIN_OPTIONS = re.compile(r"\s*(?:\([^)]*\)|analy[sz]e\b|verbose\b|format\s*=\s*\w+)", re.IGNORECASE)
# SQL Server runs a second statement without a semicolon (SELECT 1 SHUTDOWN), which sqlglot reads as a column alias.
# These words are reserved in SQL Server, so they are never real unquoted names there.
TSQL_STATEMENT_WORDS = frozenset(
    "backup begin bulk checkpoint close commit create dbcc deallocate declare delete deny drop end exec execute fetch"
    " grant insert kill merge open print raiserror readtext reconfigure restore revert revoke rollback save set"
    " setuser shutdown truncate update updatetext use waitfor while writetext".split()
)
# Read-only PostgreSQL pg_ functions analysts use (sizes, types, definitions, visibility, server status).
PG_READ_FUNCTIONS = (
    r"(?:size_pretty|size_bytes|\w*_size|typeof|get_\w+|has_role|\w+_is_visible|encoding_to_char|client_encoding"
    r"|postmaster_start_time|conf_load_time|backend_pid|is_in_recovery|last_xact_replay_timestamp|jit_available"
    r"|input_is_valid|input_error_info|column_compression|describe_object|identify_object\w*|blocking_pids"
    r"|tablespace_location|options_to_table|current_snapshot|snapshot_\w+|visible_in_snapshot|xact_status"
    r"|current_xact_id_if_assigned|stat_get_\w+|index_column_has_property|index_has_property"
    r"|indexam_has_property|collation_is_visible|char_to_encoding|safe_snapshot_blocking_pids|trigger_depth"
    r"|my_temp_schema|is_other_temp_schema|listening_channels|notification_queue_usage)"
)
# Read-only Snowflake SYSTEM$ functions analysts use (types, clustering, plans, tags, pipe and stream status).
SNOWFLAKE_READ_FUNCTIONS = (
    r"(?:typeof|clustering_\w+|explain_\w+|get_\w+|\w+_status|stream_has_data|last_change_commit_time"
    r"|allowlist\w*|whitelist\w*|estimate_\w+)"
)
# Functions with side effects: sequences, settings, sessions, locks, sleeps, server files, remote databases and
# URLs, commands (ClickHouse executable, Spark reflect), and SQL run from a string (PostgreSQL query_to_xml, DuckDB
# and Trino query). Every PostgreSQL pg_ and Snowflake SYSTEM$ function is refused except common read-only ones,
# and every Oracle dbms_ or utl_ package.
SIDE_EFFECT_FUNCTION = re.compile(
    r"pg_(?!" + PG_READ_FUNCTIONS + r"$)\w+|system\$(?!" + SNOWFLAKE_READ_FUNCTIONS + r"$)\w+|(?:dbms|utl)_\w+"
    r"|setval|nextval|getnextval|set_config|lo_\w+|dblink\w*|get_lock|release_lock|release_all_locks|csvread|csvwrite"
    r"|file_write|link_schema|sleep|sleepeachrow|benchmark|load_file|file_read|read_\w+|bfilename|load_extension"
    r"|openquery|openrowset|opendatasource|query|to_query|query_to_xml\w*|ts_stat|ts_rewrite"
    r"|(?:url|s3|gcs|file|hdfs|deltalake|hudi)(?:cluster)?|remote|remotesecure|azureblobstorage\w*|iceberg\w*"
    r"|arrowflight|input|jdbc|odbc|mysql|postgresql|mongodb|redis|sqlite|executable|reflect|try_reflect|java_method"
    r"|httpuritype|query_table|glob|parquet_\w+|sniff_csv|delta_scan|(?:sqlite|postgres|mysql)_(?:scan|query|execute|attach)\w*|st_read\w*",
    re.IGNORECASE,
)
# sqlglot skips MySQL /*! ... */ comments, which MySQL runs, and doesn't decode PostgreSQL U&"..." names, which can
# spell any function in escapes (U&"\0073etval").
UNREAD_SQL = re.compile(r"/\*M?!|\bu&[\"']", re.IGNORECASE)
# DuckDB reads a table name that looks like a file, glob or URL ('/etc/passwd', "data/*.csv", 'https://...') as
# that file, so such names are refused there.
DUCKDB_FILE_NAME = re.compile(
    r"[/\\:*?~\[\]{}]|\.(?:csv|tsv|txt|json|jsonl|ndjson|parquet|arrow|xlsx|db|duckdb|sqlite|gz|zst)$", re.IGNORECASE
)


def _refuse_sql(reason: str) -> ValueError:
    return ValueError(
        f"Only a single read statement (SELECT, WITH, EXPLAIN, SHOW, DESCRIBE or VALUES) is allowed: {reason}. "
        "This blocks common writes; only a read-only database user in Metabase blocks every write."
    )


def _ensure_read_only_sql(sql: str, engine: Optional[str] = None) -> str:
    """Refuse SQL that isn't a single read statement, or that writes or calls a function with side effects. SQL is
    parsed for the database's dialect, so names, quoted text and comments are never mistaken for writes."""
    dialect = SQL_DIALECTS.get(str(engine or ""))
    _check_read_only(sql, dialect)
    if "\\" in sql:
        for reading in OTHER_BACKSLASH_READINGS.get(dialect, ()):
            try:
                _check_read_only(sql, reading)
            except ValueError:
                raise _refuse_sql(
                    "a backslash in quotes is checked for every way the server can be set to read it, so double a "
                    "quote inside text instead of escaping it, and don't end text with a backslash"
                ) from None
    return sql


def _check_read_only(sql: str, dialect: Any) -> None:
    if UNREAD_SQL.search(sql):
        raise _refuse_sql("MySQL /*! */ comments and PostgreSQL U& names are refused")
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.SqlglotError:
        raise _refuse_sql(f"the SQL couldn't be read as {dialect or 'standard'} SQL") from None
    if len(statements) != 1:
        raise _refuse_sql("send exactly one statement")
    statement = statements[0]
    if isinstance(statement, exp.Command) and statement.name.upper() == "EXPLAIN":
        explained = statement.expression.name
        while match := EXPLAIN_OPTIONS.match(explained):
            explained = explained[match.end() :]
        _check_read_only(explained, dialect)
        return
    if isinstance(statement, exp.Command) and statement.name.upper() == "SHOW":
        # SHOW forms the parser can't read (MySQL SHOW EXTENDED FULL ... WHERE ...) can't be checked for functions.
        if "(" in sql:
            raise _refuse_sql("this SHOW can't be checked when it calls a function")
        return
    if not isinstance(statement, READ_STATEMENTS):
        raise _refuse_sql(f"{statement.key.upper()} statements are refused")
    for node in statement.walk():
        if isinstance(node, WRITE_NODES):
            raise _refuse_sql(f"{node.key.upper()} is refused, even inside a read")
        if isinstance(node, exp.Func):
            name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
            if SIDE_EFFECT_FUNCTION.fullmatch(name):
                raise _refuse_sql(f"{name}() has side effects")
        # Oracle, Snowflake and engines read as generic SQL (H2, DB2, Vertica) advance a sequence on seq.NEXTVAL.
        if (
            dialect in (None, "oracle", "snowflake")
            and isinstance(node, exp.Column)
            and node.table
            and node.name.lower() == "nextval"
        ):
            raise _refuse_sql("NEXTVAL advances a sequence")
        if isinstance(node, exp.WithTableHint):
            for hint in node.expressions:
                if hint.name.lower() in TSQL_LOCK_HINTS:
                    raise _refuse_sql(f"table hint {hint.name.upper()} locks the table")
        # Oracle packages are called as package.function, with or without brackets; a plain dbms_version is a name.
        qualifiers: Any = ()
        if isinstance(node, exp.Column):
            qualifiers = node.parts[:-1]
        elif isinstance(node, exp.Table) and isinstance(node.this, exp.Func):
            # FROM dbms_cloud.list_files(...) keeps the package on the table, not the function.
            qualifiers = [p for p in (node.args.get("catalog"), node.args.get("db")) if p is not None]
        elif isinstance(node, exp.Dot) and isinstance(node.expression, exp.Func):
            qualifiers = node.this.find_all(exp.Identifier)
        for part in qualifiers:
            if re.fullmatch(r"(?:dbms|utl)_\w+", part.name, re.IGNORECASE):
                raise _refuse_sql(f"Oracle package {part.name} is refused")
        if dialect == "duckdb" and isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier):
            if DUCKDB_FILE_NAME.search(node.name):
                raise _refuse_sql(f"DuckDB reads '{node.name}' as a file or URL")
        if isinstance(node, exp.Identifier):
            if dialect == "tsql" and not node.quoted and node.name.lower() in TSQL_STATEMENT_WORDS:
                raise _refuse_sql(f"{node.name.upper()} starts a second SQL Server statement")


async def _database_engine(context: ExecutionContext, database_id: Any) -> Optional[str]:
    database = await _api(context, "GET", f"/database/{_path_id(database_id)}") or {}
    return database.get("engine")


async def _read_only_sql(context: ExecutionContext, database_id: Any, sql: Any) -> str:
    """Check SQL in the dialect of the database it will run on."""
    sql = _required_text(sql, "sql")
    return _ensure_read_only_sql(sql, await _database_engine(context, database_id))


def _tags_by_name(tags: Any) -> Dict[str, Any]:
    if isinstance(tags, list):
        return {t.get("name"): t for t in tags if isinstance(t, dict)}
    return tags if isinstance(tags, dict) else {}


def _native_sql(query: Dict[str, Any]) -> Optional[tuple]:
    """SQL and template tags of one native query: legacy {"native": {"query", "template-tags"}} or an MBQL 5 stage
    {"native": "...", "template-tags"} (Metabase 0.57+)."""
    native = query.get("native")
    if isinstance(native, str):
        return native, _tags_by_name(query.get("template-tags"))
    if isinstance(native, dict) and isinstance(native.get("query"), str):
        return native["query"], _tags_by_name(native.get("template-tags"))
    return None


def _saved_native(dataset_query: Dict[str, Any]) -> tuple:
    """A saved question's SQL and template tags, or (None, {}) when it is a point-and-click question."""
    stages = dataset_query.get("stages") or []
    first_stage = stages[0] if stages and isinstance(stages[0], dict) else {}
    return _native_sql(dataset_query) or _native_sql(first_stage) or (None, {})


async def _checked_parameters(context: ExecutionContext, card_id: str, parameters: List[Any]) -> List[Any]:
    """Refuse to run a saved question whose SQL can write, and return the filters to run it with.

    Metabase expands the question into the exact SQL it will run (filter values, optional [[ ]] clauses, snippets,
    and the questions it is built on), and that SQL is checked the way run_sql_query checks SQL. Card filter defaults
    are sent explicitly, so the checked SQL and the run use the same values."""
    card = await _api(context, "GET", f"/card/{card_id}") or {}
    dataset_query = card.get("dataset_query") or {}
    # A filter can be sent by id or by target; either one overrides the saved default.
    supplied = {str(p.get(key)) for p in parameters if isinstance(p, dict) for key in ("id", "target") if p.get(key)}
    defaults = [
        {"id": p["id"], "type": p.get("type"), "target": p["target"], "value": p["default"]}
        for p in card.get("parameters") or []
        if p.get("default") is not None
        and p.get("target")
        and p.get("id")
        and not {str(p["id"]), str(p["target"])} & supplied
    ]
    parameters = parameters + defaults
    engine = await _database_engine(context, card.get("database_id") or dataset_query.get("database"))
    try:
        compiled = await _api(
            context, "POST", "/dataset/native", json={**dataset_query, "parameters": parameters, "pretty": False}
        )
        query = compiled.get("query") if isinstance(compiled, dict) else None
        if query is None:
            raise ValueError(f"Saved question {card_id} wasn't run: Metabase didn't return SQL for it to check.")
    except HTTPError as e:
        # Metabase only expands questions for groups allowed to write native queries; groups that can only run saved
        # questions get a 403, so the question is checked as saved when that is enough to know what will run.
        if e.status != 403:
            raise
        query = _saved_query_as_run(card_id, dataset_query)
    try:
        if query is not None and engine == "mongo":
            _ensure_read_only_mongo(query)
        elif isinstance(query, str):
            _ensure_read_only_sql(query, engine)
        elif query is not None:
            raise ValueError("Metabase didn't return SQL for it to check.")
    except ValueError as e:
        raise ValueError(f"Saved question {card_id} wasn't run. {e}") from None
    return parameters


# MongoDB aggregation stages that write: $out replaces a collection, $merge writes into one.
MONGO_WRITE_STAGES = ("$out", "$merge")


def _ensure_read_only_mongo(query: Any) -> None:
    """Refuse a MongoDB pipeline with a write stage, read by its decoded keys so escapes like "$\\u006fut" count."""
    if isinstance(query, str):
        try:
            query = json.loads(query)
        except ValueError:
            # Metabase also accepts relaxed JSON (unquoted keys, ObjectId(...)); that is checked as text, so escapes
            # that could hide a stage name are refused.
            if "\\" in query or re.search(r"\$(?:out|merge)\b", query):
                raise ValueError(
                    "MongoDB $out and $merge stages write to a collection, so they are refused, and so are pipelines "
                    "that aren't plain JSON and contain backslashes."
                ) from None
            return
    # MongoDB only allows $out and $merge as top-level pipeline stages, so stage names are all that need checking
    # ("$out" inside $literal or a field value is data).
    stages = query if isinstance(query, list) else [query]
    if any(isinstance(stage, dict) and set(stage) & set(MONGO_WRITE_STAGES) for stage in stages):
        raise ValueError("MongoDB $out and $merge stages write to a collection, so they are refused.")


def _saved_query_as_run(card_id: str, dataset_query: Dict[str, Any]) -> Optional[str]:
    """What a saved question runs when it can be known without Metabase expanding it: SQL with no filters, snippets
    or references runs as saved, and a point-and-click question that isn't built on other questions or SQL only
    reads (None). Anything else can't be checked without native query permission."""
    sql, _ = _saved_native(dataset_query)
    if sql is None:
        uses_other_questions = re.search(r'card__\d|"source[-_]card"|"native"', json.dumps(dataset_query))
        if not uses_other_questions:
            return None
    elif "{{" not in sql and "[[" not in sql:
        return sql
    raise ValueError(
        f"Saved question {card_id} wasn't run: its SQL can only be checked when the API key's group can write native "
        "queries on its database in Metabase."
    )


def _native_query(database_id: Any, sql: str) -> Dict[str, Any]:
    return {"database": database_id, "type": "native", "native": {"query": sql, "template-tags": {}}}


def _with_optional(body: Dict[str, Any], **values: Any) -> Dict[str, Any]:
    """Add optional fields to a request body, skipping ones that are missing or empty."""
    body.update({key: value for key, value in values.items() if value is not None and value != ""})
    return body


def _error_message(
    error: Exception, saved_check: Optional[str] = None, context: Optional[ExecutionContext] = None
) -> str:
    message = _format_error_message(error, saved_check)
    if context is not None and _credentials(context).get("gateway_header_name"):
        secrets = [_credentials(context).get(key) for key in ("api_key", "gateway_header_value")]
        for secret in sorted((s for s in secrets if isinstance(s, str) and s), key=len, reverse=True):
            message = message.replace(secret, "[REDACTED]")
    return message[:MAX_ERROR_LENGTH]


def _format_error_message(error: Exception, saved_check: Optional[str] = None) -> str:
    """saved_check names how to look for a create that may have been saved before the response timed out."""
    if isinstance(error, HTTPError):
        data = error.response_data
        detail = None
        if isinstance(data, dict):
            detail = data.get("error") or data.get("message") or data.get("errors")
        message = f"Metabase returned HTTP {error.status}: {detail or error.message}"
        return message
    if isinstance(error, asyncio.TimeoutError):
        if saved_check:
            return (
                "Metabase did not respond in time, but it may still have saved the change. "
                f"Check with {saved_check} before trying again, so it isn't created twice."
            )
        return "Metabase did not respond in time. For queries, aggregate or add a LIMIT and try again."
    return str(error)


# Item types some Metabase versions and editions reject outright (HTTP 400 for the whole request): metric before
# 0.51, document before 0.57 and on some open-source releases after it.
NEWER_MODELS = ("metric", "document")


async def _get_with_models(
    context: ExecutionContext, path: str, before: List[tuple], models: Any, after: List[tuple]
) -> tuple:
    """GET a list filtered by item types, leaving out newer types this Metabase rejects, newest first, so a
    supported metric isn't dropped along with an unsupported document. Returns (data, dropped)."""
    kept = list(models or [])
    dropped: List[str] = []
    while True:
        try:
            if models and not kept:
                return [], dropped
            data = await _api(context, "GET", _with_query(path, before + [("models", m) for m in kept] + after))
            return data, dropped
        except HTTPError as e:
            newest = next((m for m in reversed(NEWER_MODELS) if m in kept), None)
            if e.status != 400 or newest is None:
                raise
            kept = [m for m in kept if m != newest]
            dropped.insert(0, newest)


def _note_dropped(result: Dict[str, Any], dropped: List[str]) -> Dict[str, Any]:
    if dropped:
        result["note"] = f"Left out item types this Metabase doesn't support: {', '.join(dropped)}."
    return result


def _clamp(value: Any, default: int, maximum: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return min(value, maximum)
    return default


def _page(inputs: Dict[str, Any]) -> Dict[str, int]:
    return {
        "limit": _clamp(inputs.get("limit"), DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT),
        "offset": _clamp(inputs.get("offset"), 0, sys.maxsize),
    }


def _with_query(url: str, params: List[tuple]) -> str:
    # Metabase expects repeated keys (models=card&models=dashboard); the SDK's params
    # argument JSON-encodes lists, and SDK 2.0.1 appends params a second time when it retries a GET
    # (archived=true&archived=true, which Metabase reads as false). So queries are always built here.
    params = [(k, v) for k, v in params if v is not None]
    return f"{url}?{urlencode(params)}" if params else url


def _unique_names(cols: List[Dict[str, Any]]) -> List[str]:
    raw = [str(col.get("name") or col.get("display_name") or f"column_{i + 1}") for i, col in enumerate(cols)]
    # Reserve every real name first so a generated suffix (id_2) never collides with a real column.
    used = set(raw)
    names: List[str] = []
    seen: set = set()
    for name in raw:
        if name in seen:
            suffix = 2
            while f"{name}_{suffix}" in used:
                suffix += 1
            name = f"{name}_{suffix}"
            used.add(name)
        seen.add(name)
        names.append(name)
    return names


def _query_result(data: Any, max_rows: int) -> Dict[str, Any]:
    """Convert a Metabase query response into columns + row objects, or raise on a failed query."""
    if not isinstance(data, dict):
        raise ValueError("Metabase returned an unexpected query response")
    if data.get("status") == "failed" or data.get("error"):
        raise ValueError(f"Query failed: {data.get('error') or 'unknown error'}")
    result = data.get("data") or {}
    cols = result.get("cols") or []
    names = _unique_names(cols)
    rows = result.get("rows") or []
    returned = rows[:max_rows]
    return {
        "columns": [
            {
                "name": name,
                "display_name": col.get("display_name") or name,
                "base_type": col.get("base_type"),
            }
            for name, col in zip(names, cols)
        ],
        "rows": [dict(zip(names, row)) for row in returned],
        "row_count": len(returned),
        "total_row_count": len(rows),
        "truncated": len(rows) > len(returned) or bool(result.get("rows_truncated")),
    }


def _field_summary(field: Dict[str, Any]) -> Dict[str, Any]:
    target = field.get("target") or {}
    return {
        "id": field.get("id"),
        "name": field.get("name"),
        "display_name": field.get("display_name"),
        "base_type": field.get("base_type"),
        "semantic_type": field.get("semantic_type"),
        "description": field.get("description"),
        "foreign_key_target_field_id": field.get("fk_target_field_id") or target.get("id"),
    }


def _table_summary(table: Dict[str, Any], include_fields: bool) -> Dict[str, Any]:
    summary = {
        "id": table.get("id"),
        "schema": table.get("schema"),
        "name": table.get("name"),
        "display_name": table.get("display_name"),
        "description": table.get("description"),
    }
    if include_fields:
        summary["fields"] = [_field_summary(f) for f in table.get("fields") or []]
    return summary


def _collection_ref(collection: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(collection, dict):
        return None
    return {"id": collection.get("id"), "name": collection.get("name")}


def _template_tag_parameters(tags: Any) -> List[Dict[str, Any]]:
    """Describe a native question's filters from its template tags (legacy dict or MBQL 5 list)."""
    if isinstance(tags, dict):
        tags = list(tags.values())
    parameters = []
    for tag in tags or []:
        # Snippets, saved-question references and table references insert SQL; they are not filters.
        if not isinstance(tag, dict) or tag.get("type") in ("snippet", "card", "table"):
            continue
        # A filter whose widget is set to None has no filter box in Metabase, so it is hidden unless the question
        # cannot run without a value for it.
        if tag.get("widget-type") == "none" and (not tag.get("required") or tag.get("default") is not None):
            continue
        # Metabase matches field filters and time grouping tags by dimension targets, other tags by variable.
        kind = "dimension" if tag.get("type") in ("dimension", "temporal-unit") else "variable"
        parameters.append(
            {
                "id": tag.get("id"),
                "slug": tag.get("name"),
                "name": tag.get("display-name") or tag.get("name"),
                # Metabase wants the widget type as the value type; a field filter's tag type (dimension)
                # is only valid in the target.
                "type": tag.get("widget-type") or ("category" if tag.get("type") == "dimension" else tag.get("type")),
                "widget_type": tag.get("widget-type"),
                "required": bool(tag.get("required")),
                "default": tag.get("default"),
                "target": [kind, ["template-tag", tag.get("name")]],
            }
        )
    return parameters


def _merge_parameters(explicit: List[Dict[str, Any]], from_tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the card's own parameters, filling a missing target from their tag, and add any tag they leave out."""
    by_id = {t["id"]: t for t in from_tags if t["id"] is not None}
    by_slug = {t["slug"]: t for t in from_tags if t["slug"] is not None}
    merged = []
    for param in explicit:
        tag = by_id.get(param.get("id")) or by_slug.get(param.get("slug"))
        # Metabase runs a parameter by its target, so one stored without a target borrows its tag's.
        if tag and not param.get("target"):
            param = {**param, "target": tag["target"]}
        merged.append(param)
    known = ({p.get("id") for p in explicit} | {p.get("slug") for p in explicit}) - {None}
    return merged + [p for p in from_tags if p["id"] not in known and p["slug"] not in known]


def _card_summary(card: Dict[str, Any]) -> Dict[str, Any]:
    dataset_query = card.get("dataset_query") or {}
    sql, tags = _saved_native(dataset_query)
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "description": card.get("description"),
        "type": card.get("type"),
        "display": card.get("display"),
        "database_id": card.get("database_id") or dataset_query.get("database"),
        "query_type": card.get("query_type"),
        "native_sql": sql,
        "collection_id": card.get("collection_id"),
        "collection": _collection_ref(card.get("collection")),
        "archived": bool(card.get("archived")),
        # Native questions often keep some or all of their filters only as template tags.
        "parameters": _merge_parameters(card.get("parameters") or [], _template_tag_parameters(tags)),
    }


def _parent_from_location(location: Any) -> Optional[int]:
    """'/28/31/' -> 31; top-level collections have location '/'."""
    ids = [part for part in str(location or "").split("/") if part.isdigit()]
    return int(ids[-1]) if ids else None


def _dashcard_summary(dashcard: Dict[str, Any]) -> Dict[str, Any]:
    card = dashcard.get("card") or {}
    return {
        "dashcard_id": dashcard.get("id"),
        "card_id": dashcard.get("card_id"),
        "card_name": card.get("name"),
        "display": card.get("display"),
        "row": dashcard.get("row"),
        "col": dashcard.get("col"),
        "size_x": dashcard.get("size_x"),
        "size_y": dashcard.get("size_y"),
        "dashboard_tab_id": dashcard.get("dashboard_tab_id"),
    }


def _list_data(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        return data.get("data") or []
    return data or []


def _paged(key: str, items: List[Dict[str, Any]], data: Any, page: Dict[str, int]) -> Dict[str, Any]:
    total = data.get("total") if isinstance(data, dict) else len(items)
    return {key: items, "count": len(items), "total": total, **page}


# ---- Account ----


@metabase.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Return the Metabase user the API key acts as (useful as a connection check)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user = await _api(context, "GET", "/user/current") or {}
            return ActionResult(
                data={
                    "id": user.get("id"),
                    "email": user.get("email"),
                    "common_name": user.get("common_name"),
                    "is_superuser": bool(user.get("is_superuser")),
                    "group_ids": user.get("group_ids") or [],
                    "personal_collection_id": user.get("personal_collection_id"),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


# ---- Data model ----


@metabase.action("list_databases")
class ListDatabasesAction(ActionHandler):
    """List the databases connected to Metabase."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = await _api(context, "GET", "/database")
            databases = [
                {
                    "id": db.get("id"),
                    "name": db.get("name"),
                    "engine": db.get("engine"),
                    "description": db.get("description"),
                    "is_sample": bool(db.get("is_sample")),
                }
                for db in _list_data(data)
            ]
            return ActionResult(data={"databases": databases, "count": len(databases)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("get_database_schema")
class GetDatabaseSchemaAction(ActionHandler):
    """List a database's tables (and optionally their fields), filtered by schema or table name."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            database_id = _path_id(inputs["database_id"])
            include_fields = bool(inputs.get("include_fields", False))
            schema = str(inputs.get("schema") or "").strip().lower()
            name_contains = str(inputs.get("table_name_contains") or "").strip().lower()
            page = _page(inputs)

            skip_fields = "false" if include_fields else "true"
            data = await _api(
                context, "GET", _with_query(f"/database/{database_id}/metadata", [("skip_fields", skip_fields)])
            )
            database = data or {}
            tables = []
            for table in database.get("tables") or []:
                if schema and str(table.get("schema") or "").lower() != schema:
                    continue
                if name_contains and name_contains not in str(table.get("name") or "").lower():
                    continue
                tables.append(_table_summary(table, include_fields))
            # Metabase sends every table at once, so a large warehouse is paged here.
            returned = tables[page["offset"] : page["offset"] + page["limit"]]
            return ActionResult(
                data={
                    "database_id": database.get("id"),
                    "database_name": database.get("name"),
                    "engine": database.get("engine"),
                    "tables": returned,
                    "count": len(returned),
                    "total": len(tables),
                    **page,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("get_table")
class GetTableAction(ActionHandler):
    """Get a table's fields, types and foreign keys."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            table_id = _path_id(inputs["table_id"])
            table = await _api(context, "GET", f"/table/{table_id}/query_metadata") or {}
            summary = _table_summary(table, include_fields=True)
            summary["database_id"] = table.get("db_id")
            return ActionResult(data=summary, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


# ---- Search and collections ----


@metabase.action("search")
class SearchAction(ActionHandler):
    """Search questions, models, metrics, dashboards, collections, tables and databases."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page = _page(inputs)
            query: List[tuple] = [("q", str(inputs.get("query") or "").strip() or None)]
            archived = [("archived", "true")] if inputs.get("archived") else []
            data, dropped = await _get_with_models(
                context, "/search", query, inputs.get("models"), archived + list(page.items())
            )
            results = [
                {
                    "model": item.get("model"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "collection": _collection_ref(item.get("collection")),
                    "database_id": item.get("database_id"),
                    "table_schema": item.get("table_schema"),
                    "archived": bool(item.get("archived")),
                    "updated_at": item.get("updated_at"),
                }
                for item in _list_data(data)
            ]
            return ActionResult(data=_note_dropped(_paged("results", results, data, page), dropped), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("list_collections")
class ListCollectionsAction(ActionHandler):
    """List collections the API key can see."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            archived = "true" if inputs.get("archived") else "false"
            data = await _api(context, "GET", _with_query("/collection", [("archived", archived)]))
            include_personal = bool(inputs.get("include_personal", False))
            collections = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "parent_id": c.get("parent_id") or _parent_from_location(c.get("location")),
                    "location": c.get("effective_location") or c.get("location"),
                    "is_personal": bool(c.get("is_personal")),
                    "archived": bool(c.get("archived")),
                }
                for c in _list_data(data)
                if include_personal or not c.get("is_personal")
            ]
            return ActionResult(data={"collections": collections, "count": len(collections)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("list_collection_items")
class ListCollectionItemsAction(ActionHandler):
    """List the questions, dashboards and sub-collections inside a collection."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            collection_id = _path_id(inputs.get("collection_id") or "root")
            page = _page(inputs)
            path = f"/collection/{collection_id}/items"
            data, dropped = await _get_with_models(context, path, [], inputs.get("models"), list(page.items()))
            items = [
                {
                    "model": item.get("model"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "display": item.get("display"),
                }
                for item in _list_data(data)
            ]
            return ActionResult(data=_note_dropped(_paged("items", items, data, page), dropped), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("create_collection")
class CreateCollectionAction(ActionHandler):
    """Create a collection, optionally inside another collection."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            name = _required_text(inputs["name"], "name")
            body = _with_optional(
                {"name": name}, description=inputs.get("description"), parent_id=inputs.get("parent_collection_id")
            )

            collection = await _api(context, "POST", "/collection", json=body) or {}
            if collection.get("id") is None:
                raise ValueError("Metabase did not return a collection id")
            return ActionResult(
                data={
                    "id": collection.get("id"),
                    "name": collection.get("name") or name,
                    "location": collection.get("location"),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context, saved_check="list_collections"))


# ---- Questions and queries ----


@metabase.action("get_question")
class GetQuestionAction(ActionHandler):
    """Get a saved question (card), including its SQL when it is a native query."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = _path_id(inputs["question_id"])
            data = await _api(context, "GET", f"/card/{card_id}")
            return ActionResult(data=_card_summary(data or {}), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("run_question")
class RunQuestionAction(ActionHandler):
    """Run a saved question and return its rows."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = _path_id(inputs["question_id"])
            max_rows = _clamp(inputs.get("max_rows"), DEFAULT_MAX_ROWS, MAX_ROWS_LIMIT)
            parameters = [_run_parameter(p) for p in inputs.get("parameters") or []]
            parameters = await _checked_parameters(context, card_id, parameters)
            body: Dict[str, Any] = {"parameters": parameters} if parameters else {}

            data = await _api(context, "POST", f"/card/{card_id}/query", json=body, timeout=QUERY_TIMEOUT_SECONDS)
            return ActionResult(data=_query_result(data, max_rows), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("run_sql_query")
class RunSqlQueryAction(ActionHandler):
    """Run a native SQL query against a Metabase database and return its rows."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            sql = await _read_only_sql(context, inputs["database_id"], inputs["sql"])
            max_rows = _clamp(inputs.get("max_rows"), DEFAULT_MAX_ROWS, MAX_ROWS_LIMIT)

            data = await _api(
                context,
                "POST",
                "/dataset",
                json=_native_query(inputs["database_id"], sql),
                timeout=QUERY_TIMEOUT_SECONDS,
            )
            return ActionResult(data=_query_result(data, max_rows), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("create_question")
class CreateQuestionAction(ActionHandler):
    """Save a native SQL query as a question."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            name = _required_text(inputs["name"], "name")
            sql = await _read_only_sql(context, inputs["database_id"], inputs["sql"])
            body: Dict[str, Any] = {
                "name": name,
                "type": "question",
                "display": inputs.get("display") or "table",
                "visualization_settings": {},
                "dataset_query": _native_query(inputs["database_id"], sql),
            }
            _with_optional(body, description=inputs.get("description"), collection_id=inputs.get("collection_id"))

            card = await _api(context, "POST", "/card", json=body) or {}
            if card.get("id") is None:
                raise ValueError("Metabase did not return a question id")
            return ActionResult(data=_card_summary(card), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e, context=context, saved_check="search"))


# ---- Dashboards ----


@metabase.action("get_dashboard")
class GetDashboardAction(ActionHandler):
    """Get a dashboard with its cards, tabs and filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dashboard_id = _path_id(inputs["dashboard_id"])
            dashboard = await _api(context, "GET", f"/dashboard/{dashboard_id}") or {}
            return ActionResult(
                data={
                    "id": dashboard.get("id"),
                    "name": dashboard.get("name"),
                    "description": dashboard.get("description"),
                    "collection_id": dashboard.get("collection_id"),
                    "archived": bool(dashboard.get("archived")),
                    "tabs": [{"id": t.get("id"), "name": t.get("name")} for t in dashboard.get("tabs") or []],
                    "parameters": [
                        {"id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"), "type": p.get("type")}
                        for p in dashboard.get("parameters") or []
                    ],
                    "cards": [_dashcard_summary(dc) for dc in dashboard.get("dashcards") or []],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context))


@metabase.action("create_dashboard")
class CreateDashboardAction(ActionHandler):
    """Create an empty dashboard."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            name = _required_text(inputs["name"], "name")
            body = _with_optional(
                {"name": name}, description=inputs.get("description"), collection_id=inputs.get("collection_id")
            )

            dashboard = await _api(context, "POST", "/dashboard", json=body) or {}
            if dashboard.get("id") is None:
                raise ValueError("Metabase did not return a dashboard id")
            return ActionResult(
                data={
                    "id": dashboard.get("id"),
                    "name": dashboard.get("name") or name,
                    "collection_id": dashboard.get("collection_id"),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context, saved_check="search"))


@metabase.action("add_question_to_dashboard")
class AddQuestionToDashboardAction(ActionHandler):
    """Add a saved question to a dashboard, placed below the existing cards."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dashboard_id = _path_id(inputs["dashboard_id"])
            size_x = _clamp(inputs.get("width"), DEFAULT_CARD_WIDTH, DASHBOARD_GRID_WIDTH)
            size_y = _clamp(inputs.get("height"), DEFAULT_CARD_HEIGHT, MAX_CARD_HEIGHT)

            dashboard = await _api(context, "GET", f"/dashboard/{dashboard_id}") or {}
            existing = dashboard.get("dashcards") or []
            tabs = dashboard.get("tabs") or []
            tab_id = inputs.get("tab_id")
            if tab_id is None and tabs:
                tab_id = tabs[0].get("id")
            elif tab_id is not None and tab_id not in [t.get("id") for t in tabs]:
                raise ValueError(f"tab_id {tab_id} is not a tab on dashboard {inputs['dashboard_id']}")

            # PUT replaces the whole dashcard list, so every existing card is sent back unchanged.
            dashcards = [{k: dc[k] for k in DASHCARD_PUT_KEYS if k in dc} for dc in existing]
            # GET returns each extra series as a full card, but PUT only accepts its id.
            for dc in dashcards:
                if dc.get("series"):
                    dc["series"] = [{"id": s["id"]} for s in dc["series"]]
                # GET hides a link the API key can't read as {"restricted": true}; leaving the settings out
                # keeps the stored link instead of overwriting it.
                link = ((dc.get("visualization_settings") or {}).get("link") or {}).get("entity") or {}
                if link.get("restricted"):
                    del dc["visualization_settings"]
            same_tab = [dc for dc in existing if tab_id is None or dc.get("dashboard_tab_id") == tab_id]
            next_row = max((int(dc.get("row") or 0) + int(dc.get("size_y") or 0) for dc in same_tab), default=0)

            # Negative ids mark new dashcards for Metabase to create.
            new_card = {
                "id": -1,
                "card_id": inputs["question_id"],
                "row": next_row,
                "col": 0,
                "size_x": size_x,
                "size_y": size_y,
                "series": [],
                "parameter_mappings": [],
                "visualization_settings": {},
            }
            if tab_id is not None:
                new_card["dashboard_tab_id"] = tab_id
            dashcards.append(new_card)

            body: Dict[str, Any] = {"dashcards": dashcards}
            if tabs:
                body["tabs"] = [{"id": t.get("id"), "name": t.get("name")} for t in tabs]

            updated = await _api(context, "PUT", f"/dashboard/{dashboard_id}", json=body) or {}
            known_ids = {dc.get("id") for dc in existing}
            added = next(
                (
                    dc
                    for dc in updated.get("dashcards") or []
                    if dc.get("id") not in known_ids and dc.get("card_id") == inputs["question_id"]
                ),
                None,
            )
            return ActionResult(
                data={
                    "dashboard_id": updated.get("id") or dashboard.get("id"),
                    "dashcard_id": (added or {}).get("id"),
                    "card_id": inputs["question_id"],
                    "row": next_row,
                    "col": 0,
                    "size_x": size_x,
                    "size_y": size_y,
                    "card_count": len(updated.get("dashcards") or dashcards),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=_error_message(e, context=context, saved_check="get_dashboard"))
