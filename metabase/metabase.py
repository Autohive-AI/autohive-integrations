from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    HTTPError,
)
import asyncio
import base64
import csv
import io
import json
import re
import secrets
import uuid
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


async def _gateway_request(
    url: str, method: str, headers: Dict[str, str], allow_text: bool = False, **kwargs: Any
) -> Any:
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
                    raise HTTPError(response.status, "Request failed. Check gateway and Metabase access.", {})
                # CSV exports are text, even when the CSV happens to read as JSON (a lone "2024" header).
                if allow_text and "json" not in response.headers.get("Content-Type", ""):
                    return await response.text(errors="replace")
                try:
                    return await response.json(content_type=None)
                except (ValueError, UnicodeError):
                    if allow_text:
                        return await response.text(errors="replace")
                    raise ValueError("Metabase returned a response that isn't JSON. Check the Metabase URL.") from None
    except aiohttp.ClientError:
        raise ValueError("Could not connect to Metabase. Check the URL, TLS certificate and gateway access.") from None


def _path_id(value: Any) -> str:
    return quote(str(value), safe="")


async def _api(context: ExecutionContext, method: str, path: str, allow_text: bool = False, **kwargs: Any) -> Any:
    """Call the Metabase API. allow_text accepts a text body (CSV exports); other calls must answer with JSON."""
    if method != "GET":
        kwargs.setdefault("retry_count", NO_RETRY)
    url = f"{get_base_url(context)}/api{path}"
    headers = get_auth_headers(context)
    if "content_type" in kwargs:
        # Headers win over content_type in the SDK, so a form body must not carry the JSON header.
        del headers["Content-Type"]
    if _credentials(context).get("gateway_header_name"):
        content_type = kwargs.pop("content_type", None)
        if content_type:
            headers["Content-Type"] = content_type
        data = await _gateway_request(url, method, headers, allow_text=allow_text, **kwargs)
    else:
        response = await context.fetch(url, method=method, headers=headers, **kwargs)
        data = response.data
    if allow_text and isinstance(data, str) and not re.match(r"\s*<(?:!doctype|html)", data, re.I):
        return data
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


async def _checked_parameters(
    context: ExecutionContext,
    card_id: str,
    parameters: List[Any],
    also_without_defaults: bool = True,
    saving: bool = False,
) -> List[Any]:
    """Refuse to run a saved question whose SQL can write, and return the filters to run it with.

    Metabase expands the question into the exact SQL it will run (filter values, optional [[ ]] clauses, snippets,
    and the questions it is built on), and that SQL is checked the way run_sql_query checks SQL. Card filter defaults
    are sent explicitly, so the checked SQL and the run use the same values. Unless also_without_defaults is turned off
    (for runs that send those defaults themselves), the SQL is also checked without them, because Metabase leaves
    them out when it runs the question on a dashboard or a schedule.

    saving is for actions that save the question's SQL somewhere new (copies, reverts, questions built on it) without
    running it: the SQL is also checked with every filter set, so no optional clause goes unchecked, and a question
    that can't be expanded without filter values isn't refused for that."""
    card = await _api(context, "GET", f"/card/{card_id}") or {}
    dataset_query = card.get("dataset_query") or {}
    sql, tags = _saved_native(dataset_query)
    # Metabase runs a filter given by id against that filter's own target, whatever target the caller sent, so the
    # target is taken from the question; otherwise the check could expand different SQL from the run.
    targets = {
        str(p["id"]): p["target"]
        for p in _merge_parameters(card.get("parameters") or [], _template_tag_parameters(tags))
        if p.get("id") and p.get("target")
    }
    parameters = [
        {**p, "target": targets[str(p["id"])]} if isinstance(p, dict) and str(p.get("id")) in targets else p
        for p in parameters
    ]
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
    variants = [parameters + defaults] + ([parameters] if also_without_defaults and defaults else [])
    engine = await _database_engine(context, card.get("database_id") or dataset_query.get("database"))
    if saving:
        covered = {json.dumps(p.get("target")) for p in parameters if isinstance(p, dict)}
        stand_ins = _tag_stand_ins(tags, await _field_filter_types(context, tags))
        every_filter = parameters + [p for p in stand_ins if json.dumps(p["target"]) not in covered]
        await _check_compiled(context, card_id, dataset_query, every_filter, engine)
    for variant in variants:
        try:
            await _check_compiled(context, card_id, dataset_query, variant, engine)
        except HTTPError:
            # Nothing runs when saving, and a question missing a filter value it needs can't run either; the check
            # with every filter set above has covered its SQL. Any other failure (Metabase reports both as a 500)
            # leaves this form unchecked, so it is refused.
            if not (saving and _missing_needed_filter(sql, tags, variant)):
                raise
    return variants[0]


def _missing_needed_filter(sql: Any, tags: Dict[str, Any], parameters: List[Any]) -> bool:
    """Whether a filter the SQL needs (used outside an optional [[ ]] clause, or marked required) has no default and
    gets no value from these parameters, so Metabase can't expand the SQL."""
    outside = set(_placeholders(re.sub(r"\[\[.*?\]\]", "", str(sql or ""), flags=re.S)))
    given = {
        str(target[1][1])
        for p in parameters
        if isinstance(p, dict)
        and isinstance(target := p.get("target"), list)
        and len(target) > 1
        and isinstance(target[1], list)
        and len(target[1]) > 1
    }
    return any(
        (t.get("required") or name in outside) and t.get("default") is None and name not in given
        for name, t in tags.items()
        if t.get("type") not in ("snippet", "card")
    )


# A text-style field filter's stand-in must parse as the column's type, or Metabase refuses to expand the SQL.
NUMBER_FIELD_TYPES = {"type/Integer", "type/BigInteger", "type/Float", "type/Decimal", "type/Number"}


def _has_default(tag: Dict[str, Any]) -> bool:
    return tag.get("default") not in (None, "", [])


def _text_widget_field(tag: Dict[str, Any]) -> Any:
    """The column a field filter shown as a text or ID box points at, as (id or name, options), or None. Metabase
    0.49 saves the column as ["field", id, options], newer versions as ["field", options, id]."""
    widget = str(tag.get("widget-type") or "category")
    dimension = tag.get("dimension")
    if (
        tag.get("type") != "dimension"
        or _has_default(tag)
        or widget.startswith(("date", "number"))
        or not isinstance(dimension, list)
        or len(dimension) < 3
        or dimension[0] != "field"
    ):
        return None
    options, field = (dimension[1], dimension[2]) if isinstance(dimension[1], dict) else (dimension[2], dimension[1])
    return field, options if isinstance(options, dict) else {}


async def _field_filter_types(context: ExecutionContext, tags: Dict[str, Any]) -> Dict[str, str]:
    """The column type behind each text or ID field filter without a default, by tag name."""
    types = {}
    for name, tag in tags.items():
        column = _text_widget_field(tag)
        if column is None:
            continue
        field_id, options = column
        if not (options.get("effective-type") or options.get("base-type")):
            if not isinstance(field_id, int):
                continue
            try:
                options = await _api(context, "GET", f"/field/{field_id}") or {}
            except HTTPError:
                # Without the column's type the text stand-in is tried; Metabase refuses it if it doesn't fit.
                continue
        types[name] = str(
            options.get("effective-type")
            or options.get("base-type")
            or options.get("effective_type")
            or options.get("base_type")
            or ""
        )
    return types


def _tag_stand_ins(tags: Dict[str, Any], field_types: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """A value for every filter in a question's SQL, so expanding it includes every optional [[ ]] clause.
    field_types gives the column type behind text or ID field filters (from _field_filter_types)."""
    field_types = field_types or {}
    params = []
    for name, tag in tags.items():
        kind = tag.get("type")
        if kind in FILTER_STAND_INS:
            widget, value = FILTER_STAND_INS[kind]
            params.append({"type": widget, "target": ["variable", ["template-tag", name]], "value": value})
        elif kind == "dimension":
            widget = str(tag.get("widget-type") or "category")
            if widget.startswith("date"):
                value: Any = "2020-01-01"
            elif widget.startswith("number"):
                # A range filter needs both ends; Metabase 0.49 refuses one.
                value = [1, 2] if widget == "number/between" else [1]
            elif _has_default(tag):
                # The saved default already fits the column; an empty one would leave optional clauses out.
                value = tag["default"]
            elif field_types.get(name) == "type/UUID":
                value = ["00000000-0000-0000-0000-000000000000"]
            elif field_types.get(name) in NUMBER_FIELD_TYPES:
                value = [1]
            else:
                value = ["x"]
            params.append({"type": widget, "target": ["dimension", ["template-tag", name]], "value": value})
        elif kind == "temporal-unit":
            # A time grouping filter (Metabase 0.50+) is a dimension target too.
            params.append({"type": "temporal-unit", "target": ["dimension", ["template-tag", name]], "value": "month"})
    return params


async def _check_compiled(
    context: ExecutionContext,
    card_id: str,
    dataset_query: Dict[str, Any],
    parameters: List[Any],
    engine: Any,
    refusal: Optional[str] = None,
) -> None:
    """Expand a query with Metabase and check the SQL it would run. refusal starts the error (default: the saved
    question wasn't run); SQL not yet saved has nothing saved to fall back on, so it needs the expansion."""
    refusal = refusal or f"Saved question {card_id} wasn't run."
    try:
        compiled = await _api(
            context, "POST", "/dataset/native", json={**dataset_query, "parameters": parameters, "pretty": False}
        )
        query = compiled.get("query") if isinstance(compiled, dict) else None
        if query is None:
            raise ValueError(f"{refusal} Metabase didn't return SQL for it to check.")
    except HTTPError as e:
        # Metabase only expands questions for groups allowed to write native queries; groups that can only run saved
        # questions get a 403, so the question is checked as saved when that is enough to know what will run.
        if e.status != 403:
            raise
        if card_id is None:
            raise ValueError(
                f"{refusal} SQL with {{{{ }}}} can only be checked when the API key's group can write native queries "
                "on its database in Metabase."
            ) from None
        query = _saved_query_as_run(card_id, dataset_query)
    try:
        if query is not None and engine == "mongo":
            _ensure_read_only_mongo(query)
        elif isinstance(query, str):
            _ensure_read_only_sql(query, engine)
        elif query is not None:
            raise ValueError("Metabase didn't return SQL for it to check.")
    except ValueError as e:
        raise ValueError(f"{refusal} {e}") from None


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


def _require_id(item: Dict[str, Any], what: str) -> None:
    """A create that returns no id didn't save anything usable; what is e.g. "a question"."""
    if item.get("id") is None:
        raise ValueError(f"Metabase did not return {what} id")


def _format_error_message(error: Exception, saved_check: Optional[str] = None) -> str:
    """saved_check names how to look for a create that may have been saved before the response timed out."""
    if isinstance(error, HTTPError):
        data = error.response_data
        detail = None
        if isinstance(data, dict):
            detail = data.get("error") or data.get("message") or data.get("errors")
        return f"Metabase returned HTTP {error.status}: {detail or error.message}"
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
        # A combined chart's other questions; filter connections take their id as question_id.
        "series": [{"id": sr.get("id"), "name": sr.get("name")} for sr in dashcard.get("series") or []],
    }


def _dashcards_for_put(existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dashboard cards in the shape PUT /dashboard/:id accepts. PUT replaces the whole card list, so every card
    that should stay is sent back unchanged."""
    dashcards = [{k: dc[k] for k in DASHCARD_PUT_KEYS if k in dc} for dc in existing]
    for dc in dashcards:
        # GET returns each extra series as a full card, but PUT only accepts its id.
        if dc.get("series"):
            dc["series"] = [{"id": s["id"]} for s in dc["series"]]
        # GET hides a link the API key can't read as {"restricted": true}; leaving the settings out
        # keeps the stored link instead of overwriting it.
        link = ((dc.get("visualization_settings") or {}).get("link") or {}).get("entity") or {}
        if link.get("restricted"):
            del dc["visualization_settings"]
    return dashcards


def _list_data(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        return data.get("data") or []
    return data or []


def _paged(key: str, items: List[Dict[str, Any]], data: Any, page: Dict[str, int]) -> Dict[str, Any]:
    total = data.get("total") if isinstance(data, dict) else len(items)
    return {key: items, "count": len(items), "total": total, **page}


def _handled(saved_check: Optional[str] = None):
    """Wrap an action: what it returns becomes the result, and any error becomes an ActionError message (with the
    API key and gateway secret hidden; saved_check names the action to check whether a timed-out write saved)."""

    def wrap(execute):
        async def run(self, inputs: Dict[str, Any], context: ExecutionContext):
            try:
                data = await execute(self, inputs, context)
            except Exception as e:
                return ActionError(message=_error_message(e, context=context, saved_check=saved_check))
            return ActionResult(data=data, cost_usd=0.0)

        return run

    return wrap


# ---- Account ----


@metabase.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Return the Metabase user the API key acts as (useful as a connection check)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        user = await _api(context, "GET", "/user/current") or {}
        return {
            "id": user.get("id"),
            "email": user.get("email"),
            "common_name": user.get("common_name"),
            "is_superuser": bool(user.get("is_superuser")),
            "group_ids": user.get("group_ids") or [],
            "personal_collection_id": user.get("personal_collection_id"),
        }


# ---- Data model ----


@metabase.action("list_databases")
class ListDatabasesAction(ActionHandler):
    """List the databases connected to Metabase."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
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
        return {"databases": databases, "count": len(databases)}


@metabase.action("get_database_schema")
class GetDatabaseSchemaAction(ActionHandler):
    """List a database's tables (and optionally their fields), filtered by schema or table name."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
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
        return {
            "database_id": database.get("id"),
            "database_name": database.get("name"),
            "engine": database.get("engine"),
            "tables": returned,
            "count": len(returned),
            "total": len(tables),
            **page,
        }


@metabase.action("get_table")
class GetTableAction(ActionHandler):
    """Get a table's fields, types and foreign keys."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        table_id = _path_id(inputs["table_id"])
        table = await _api(context, "GET", f"/table/{table_id}/query_metadata") or {}
        summary = _table_summary(table, include_fields=True)
        summary["database_id"] = table.get("db_id")
        return summary


# ---- Search and collections ----


@metabase.action("search")
class SearchAction(ActionHandler):
    """Search questions, models, metrics, dashboards, collections, tables and databases."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
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
        return _note_dropped(_paged("results", results, data, page), dropped)


@metabase.action("list_collections")
class ListCollectionsAction(ActionHandler):
    """List collections the API key can see."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
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
        return {"collections": collections, "count": len(collections)}


@metabase.action("list_collection_items")
class ListCollectionItemsAction(ActionHandler):
    """List the questions, dashboards and sub-collections inside a collection."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
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
        return _note_dropped(_paged("items", items, data, page), dropped)


@metabase.action("create_collection")
class CreateCollectionAction(ActionHandler):
    """Create a collection, optionally inside another collection."""

    @_handled(saved_check="list_collections")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        name = _required_text(inputs["name"], "name")
        body = _with_optional(
            {"name": name}, description=inputs.get("description"), parent_id=inputs.get("parent_collection_id")
        )

        collection = await _api(context, "POST", "/collection", json=body) or {}
        _require_id(collection, "a collection")
        return {
            "id": collection.get("id"),
            "name": collection.get("name") or name,
            "location": collection.get("location"),
        }


# ---- Questions and queries ----


@metabase.action("get_question")
class GetQuestionAction(ActionHandler):
    """Get a saved question (card), including its SQL when it is a native query."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        card_id = _path_id(inputs["question_id"])
        data = await _api(context, "GET", f"/card/{card_id}")
        return _card_summary(data or {})


@metabase.action("run_question")
class RunQuestionAction(ActionHandler):
    """Run a saved question and return its rows."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        card_id = _path_id(inputs["question_id"])
        max_rows = _clamp(inputs.get("max_rows"), DEFAULT_MAX_ROWS, MAX_ROWS_LIMIT)
        parameters = [_run_parameter(p) for p in inputs.get("parameters") or []]
        # The run sends the saved defaults itself, so the SQL is only checked with them.
        parameters = await _checked_parameters(context, card_id, parameters, also_without_defaults=False)
        body: Dict[str, Any] = {"parameters": parameters} if parameters else {}

        data = await _api(context, "POST", f"/card/{card_id}/query", json=body, timeout=QUERY_TIMEOUT_SECONDS)
        return _query_result(data, max_rows)


@metabase.action("run_sql_query")
class RunSqlQueryAction(ActionHandler):
    """Run a native SQL query against a Metabase database and return its rows."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        sql = await _read_only_sql(context, inputs["database_id"], inputs["sql"])
        max_rows = _clamp(inputs.get("max_rows"), DEFAULT_MAX_ROWS, MAX_ROWS_LIMIT)

        data = await _api(
            context,
            "POST",
            "/dataset",
            json=_native_query(inputs["database_id"], sql),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
        return _query_result(data, max_rows)


@metabase.action("create_question")
class CreateQuestionAction(ActionHandler):
    """Save a native SQL query as a question."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        _required_text(inputs["name"], "name")
        dataset_query = await _new_native_query(context, inputs["database_id"], inputs["sql"], inputs.get("filters"))
        card = await _create_card(context, inputs, "question", dataset_query)
        return _card_summary(card)


# ---- Dashboards ----


@metabase.action("get_dashboard")
class GetDashboardAction(ActionHandler):
    """Get a dashboard with its cards, tabs and filters."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard_id = _path_id(inputs["dashboard_id"])
        dashboard = await _api(context, "GET", f"/dashboard/{dashboard_id}") or {}
        summary = _dashboard_summary(dashboard)
        return {k: v for k, v in summary.items() if k not in ("width", "auto_apply_filters")}


@metabase.action("create_dashboard")
class CreateDashboardAction(ActionHandler):
    """Create an empty dashboard."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        name = _required_text(inputs["name"], "name")
        body = _with_optional(
            {"name": name}, description=inputs.get("description"), collection_id=inputs.get("collection_id")
        )

        dashboard = await _api(context, "POST", "/dashboard", json=body) or {}
        _require_id(dashboard, "a dashboard")
        return {
            "id": dashboard.get("id"),
            "name": dashboard.get("name") or name,
            "collection_id": dashboard.get("collection_id"),
        }


@metabase.action("add_question_to_dashboard")
class AddQuestionToDashboardAction(ActionHandler):
    """Add a saved question to a dashboard, placed below the existing cards."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        size_x = _clamp(inputs.get("width"), DEFAULT_CARD_WIDTH, DASHBOARD_GRID_WIDTH)
        size_y = _clamp(inputs.get("height"), DEFAULT_CARD_HEIGHT, MAX_CARD_HEIGHT)

        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        existing = dashboard.get("dashcards") or []
        tabs = dashboard.get("tabs") or []
        tab_id = _check_tab(inputs.get("tab_id"), tabs, inputs["dashboard_id"])
        dashcards = _dashcards_for_put(existing)
        next_row = _bottom_row(existing, tab_id)

        dashcards.append(_new_dashcard(inputs["question_id"], next_row, 0, size_x, size_y, tab_id))
        if await _has_subscriptions(context, dashboard.get("id")):
            # Metabase adds the question to the dashboard's subscriptions, which then run it with nobody watching.
            await _checked_parameters(context, _path_id(inputs["question_id"]), [])

        updated, added = await _put_new_dashcard(context, inputs["dashboard_id"], existing, dashcards, tabs)
        return {
            "dashboard_id": updated.get("id") or dashboard.get("id"),
            "dashcard_id": added.get("id"),
            "card_id": inputs["question_id"],
            "row": next_row,
            "col": 0,
            "size_x": size_x,
            "size_y": size_y,
            "card_count": len(updated.get("dashcards") or dashcards),
        }


# ---- Editing helpers ----

TEXT_CARD_KINDS = ("text", "heading", "link")
DEFAULT_TEXT_CARD_HEIGHT = {"text": 3, "heading": 1, "link": 1}
DEFAULT_DASHBOARD_RUN_ROWS = 20
MAX_DASHBOARD_CARDS_RUN = 25
# run_dashboard runs its questions one after another; it stops starting new ones in time to answer within the
# ~150 second Lambda timeout, and keeps the rows it returns well under the 6 MB Lambda response limit.
DASHBOARD_RUN_SECONDS = 135
MIN_DASHBOARD_CARD_SECONDS = 10
MAX_DASHBOARD_RESULT_CHARS = 4_000_000
DEFAULT_EXPORT_ROWS = 1000
MAX_EXPORT_ROWS = 10_000
MAX_EXPORT_CHARS = 1_000_000
# Item type -> API path for archive and restore. Questions, models and metrics are all cards.
ARCHIVE_PATHS = {
    "question": "card",
    "model": "card",
    "metric": "card",
    "dashboard": "dashboard",
    "collection": "collection",
    "segment": "segment",
    "subscription": "pulse",
    "timeline": "timeline",
    "timeline_event": "timeline-event",
}
REVISION_ENTITIES = {
    "question": "card",
    "model": "card",
    "metric": "card",
    "dashboard": "dashboard",
    "segment": "segment",
}
# Metabase stores a change message with every segment edit.
SEGMENT_REVISION_MESSAGE = "Updated through the Autohive Metabase integration"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
ALERT_CONDITIONS = ("has_result", "goal_above", "goal_below")


def _int_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


async def _get_dashboard(context: ExecutionContext, dashboard_id: Any) -> Dict[str, Any]:
    return await _api(context, "GET", f"/dashboard/{_path_id(dashboard_id)}") or {}


def _tabs_for_put(tabs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"id": t.get("id"), "name": t.get("name")} for t in tabs]


async def _put_dashboard_layout(
    context: ExecutionContext, dashboard_id: Any, dashcards: List[Dict[str, Any]], tabs: List[Dict[str, Any]], **extra
) -> Dict[str, Any]:
    """PUT the dashboard's full card and tab lists (Metabase replaces both on every update)."""
    body: Dict[str, Any] = {"dashcards": dashcards, **extra}
    if tabs:
        body["tabs"] = tabs
    return await _api(context, "PUT", f"/dashboard/{_path_id(dashboard_id)}", json=body) or {}


def _new_dashcard(
    card_id: Any, row: int, col: int, size_x: int, size_y: int, tab_id: Any, settings: Optional[Dict] = None
) -> Dict[str, Any]:
    """A card to add to a dashboard; the negative id tells Metabase to create it."""
    card = {
        "id": -1,
        "card_id": card_id,
        "row": row,
        "col": col,
        "size_x": size_x,
        "size_y": size_y,
        "series": [],
        "parameter_mappings": [],
        "visualization_settings": settings or {},
    }
    if tab_id is not None:
        card["dashboard_tab_id"] = tab_id
    return card


async def _put_new_dashcard(
    context: ExecutionContext, dashboard_id: Any, existing: List[Dict[str, Any]], dashcards: List[Dict[str, Any]], tabs
) -> tuple:
    """PUT the cards with one new card (the last) and return the updated dashboard and the card Metabase created."""
    updated = await _put_dashboard_layout(context, dashboard_id, dashcards, _tabs_for_put(tabs))
    known_ids = {dc.get("id") for dc in existing}
    card_id = dashcards[-1]["card_id"]
    added = next(
        (dc for dc in updated.get("dashcards") or [] if dc.get("id") not in known_ids and dc.get("card_id") == card_id),
        {},
    )
    return updated, added


def _dashboard_summary(dashboard: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": dashboard.get("id"),
        "name": dashboard.get("name"),
        "description": dashboard.get("description"),
        "collection_id": dashboard.get("collection_id"),
        "width": dashboard.get("width"),
        "auto_apply_filters": dashboard.get("auto_apply_filters"),
        "archived": bool(dashboard.get("archived")),
        "tabs": [{"id": t.get("id"), "name": t.get("name")} for t in dashboard.get("tabs") or []],
        "parameters": [
            {"id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"), "type": p.get("type")}
            for p in dashboard.get("parameters") or []
        ],
        "cards": [_dashcard_summary(dc) for dc in dashboard.get("dashcards") or []],
    }


def _check_tab(tab_id: Any, tabs: List[Dict[str, Any]], dashboard_id: Any) -> Any:
    """The tab a card goes on: the given tab, or the first tab when the dashboard has tabs."""
    if tab_id is None:
        return tabs[0].get("id") if tabs else None
    if tab_id not in [t.get("id") for t in tabs]:
        raise ValueError(f"tab_id {tab_id} is not a tab on dashboard {dashboard_id}")
    return tab_id


def _check_grid(col: int, size_x: int) -> None:
    if col < 0 or col + size_x > DASHBOARD_GRID_WIDTH:
        raise ValueError(f"A card must fit the {DASHBOARD_GRID_WIDTH}-column grid: col + width is at most 24.")


def _bottom_row(dashcards: List[Dict[str, Any]], tab_id: Any) -> int:
    same_tab = [dc for dc in dashcards if tab_id is None or dc.get("dashboard_tab_id") == tab_id]
    return max((int(dc.get("row") or 0) + int(dc.get("size_y") or 0) for dc in same_tab), default=0)


def _slug(name: str) -> str:
    # Letters in any script are kept, so "日付" and "地域" (or "Région" and "R gion") get different slugs.
    return re.sub(r"\W+", "_", name.lower()).strip("_") or "filter"


def _filter_target(dashcard: Dict[str, Any], question: Dict[str, Any], connection: Dict[str, Any]) -> List[Any]:
    """Metabase target for connecting a dashboard filter to one question on a card: a column, or a SQL question's
    filter tag."""
    field_id = _int_or_none(connection.get("field_id"))
    tag = str(connection.get("template_tag") or "").strip()
    if bool(field_id) == bool(tag):
        raise ValueError("Each filter connection needs exactly one of field_id or template_tag.")
    if field_id:
        return ["dimension", ["field", field_id, None]]
    _, tags = _saved_native(question.get("dataset_query") or {})
    if tag not in tags:
        raise ValueError(f"Card {dashcard.get('id')} has no SQL filter named {tag}.")
    kind = "dimension" if tags[tag].get("type") in ("dimension", "temporal-unit") else "variable"
    return [kind, ["template-tag", tag]]


def _card_parameters_for(
    dashcard: Dict[str, Any], values: Dict[str, Dict[str, Any]], card_id: Any = None
) -> List[Dict[str, Any]]:
    """Dashboard filter values as the parameters of one question on a card (the card's own question, or one of a
    combined chart's extra series), through that question's filter connections."""
    card_id = dashcard.get("card_id") if card_id is None else card_id
    params = []
    for mapping in dashcard.get("parameter_mappings") or []:
        # Each question on a combined chart has its own connections; one without a card id is the card's own.
        if (mapping.get("card_id") or dashcard.get("card_id")) != card_id:
            continue
        value = values.get(mapping.get("parameter_id"))
        if value is not None and mapping.get("target"):
            params.append(
                {"id": value["id"], "type": value.get("type"), "target": mapping["target"], "value": value["value"]}
            )
    return params


def _dashboard_questions(dashcards: List[Dict[str, Any]]) -> List[tuple]:
    """(dashcard, question id, name) for every question shown: each card's own question and a combined chart's extra
    series, which Metabase runs too."""
    questions = []
    for dc in dashcards:
        if not dc.get("card_id") or dc.get("action_id"):
            continue
        questions.append((dc, dc["card_id"], (dc.get("card") or {}).get("name")))
        questions.extend(
            (dc, series["id"], series.get("name")) for series in dc.get("series") or [] if series.get("id")
        )
    return questions


def _default_values(dashboard: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The dashboard's filter defaults, which scheduled sends and runs without filter values use."""
    return {
        p["id"]: {"id": p["id"], "type": p.get("type"), "value": p["default"]}
        for p in dashboard.get("parameters") or []
        if p.get("default") is not None
    }


async def _has_subscriptions(context: ExecutionContext, dashboard_id: Any) -> bool:
    """Whether a dashboard may have subscriptions. Metabase only lists other people's subscriptions to admins, so for
    any other API key an empty list proves nothing and the dashboard is treated as having one."""
    params = [("dashboard_id", dashboard_id), ("archived", "false")]
    if _list_data(await _api(context, "GET", _with_query("/pulse", params))):
        return True
    return not (await _api(context, "GET", "/user/current") or {}).get("is_superuser")


def _pulse_flags(pulse: Dict[str, Any]) -> Dict[str, bool]:
    """Metabase resets archived and skip_if_empty when a subscription update leaves them out, so both are sent."""
    return {"archived": bool(pulse.get("archived")), "skip_if_empty": bool(pulse.get("skip_if_empty"))}


async def _check_dashboard_questions(
    context: ExecutionContext, dashboard: Dict[str, Any], saving: bool = False, pulse: Optional[Dict[str, Any]] = None
) -> None:
    """Check every question on a dashboard with the dashboard's filter defaults, as a scheduled send runs them, and
    with a subscription's own filter values (Metabase Pro) over them when pulse is given. saving checks them as
    questions about to be copied (see _checked_parameters)."""
    values = _default_values(dashboard)
    for p in (pulse or {}).get("parameters") or []:
        if isinstance(p, dict) and p.get("id") and p.get("value") is not None:
            values[p["id"]] = {"id": p["id"], "type": p.get("type"), "value": p["value"]}
    checked = set()
    for dc, card_id, name in _dashboard_questions(dashboard.get("dashcards") or []):
        if saving and name is None:
            # Metabase shows only the id of a question the API key can't read, and leaves it out of a copy (listed as
            # uncopied), so there is nothing of it to check.
            continue
        params = _card_parameters_for(dc, values, card_id)
        key = (card_id, json.dumps(params, sort_keys=True))
        if key not in checked:
            checked.add(key)
            await _checked_parameters(context, _path_id(card_id), params, saving=saving)


def _cron(frequency: str, hour: int, day: str) -> str:
    """Quartz cron (Metabase notifications) for an hourly, daily or weekly schedule."""
    if frequency == "hourly":
        return "0 0 * * * ? *"
    if frequency == "weekly":
        return f"0 0 {hour} ? * {day.upper()} *"
    return f"0 0 {hour} * * ? *"


def _schedule(inputs: Dict[str, Any]) -> tuple:
    frequency = inputs.get("frequency") or "daily"
    if frequency not in ("hourly", "daily", "weekly"):
        raise ValueError("frequency must be hourly, daily or weekly")
    hour = _int_or_none(inputs.get("hour"))
    hour = hour if hour is not None and 0 <= hour <= 23 else 8
    day = str(inputs.get("day_of_week") or "mon").lower()
    if day not in WEEKDAYS:
        raise ValueError("day_of_week must be one of mon, tue, wed, thu, fri, sat or sun")
    return frequency, hour, day


def _recipients(inputs: Dict[str, Any]) -> tuple:
    user_ids = [u for u in inputs.get("recipient_user_ids") or [] if _int_or_none(u)]
    emails = [str(e).strip() for e in inputs.get("recipient_emails") or [] if str(e).strip()]
    if not user_ids and not emails:
        raise ValueError("Give at least one recipient in recipient_user_ids or recipient_emails.")
    return user_ids, emails


def _pulse_schedule(frequency: str, hour: int, day: str) -> Dict[str, Any]:
    return {
        "schedule_type": frequency,
        "schedule_hour": None if frequency == "hourly" else hour,
        "schedule_day": day if frequency == "weekly" else None,
        "schedule_frame": None,
    }


def _pulse_recipients(user_ids: List[int], emails: List[str]) -> List[Dict[str, Any]]:
    return [{"id": u} for u in user_ids] + [{"email": e} for e in emails]


def _pulse_channel(frequency: str, hour: int, day: str, user_ids: List[int], emails: List[str]) -> Dict[str, Any]:
    """Email channel of a dashboard subscription or old-style (/api/alert) alert."""
    return {
        "enabled": True,
        "channel_type": "email",
        **_pulse_schedule(frequency, hour, day),
        "recipients": _pulse_recipients(user_ids, emails),
    }


def _subscription_summary(pulse: Dict[str, Any]) -> Dict[str, Any]:
    channel = next((c for c in pulse.get("channels") or [] if c.get("channel_type") == "email"), {})
    return {
        "id": pulse.get("id"),
        "name": pulse.get("name"),
        "dashboard_id": pulse.get("dashboard_id"),
        "archived": bool(pulse.get("archived")),
        "skip_if_empty": bool(pulse.get("skip_if_empty")),
        "frequency": channel.get("schedule_type"),
        "hour": channel.get("schedule_hour"),
        "day_of_week": channel.get("schedule_day"),
        "recipients": [r.get("email") or r.get("common_name") or r.get("id") for r in channel.get("recipients") or []],
    }


def _alert_summary(alert: Dict[str, Any]) -> Dict[str, Any]:
    """An alert from /api/notification (0.54+) or the older /api/alert."""
    if "payload_type" in alert:
        payload = alert.get("payload") or {}
        subscription = next(iter(alert.get("subscriptions") or []), {})
        recipients = []
        for handler in alert.get("handlers") or []:
            for r in handler.get("recipients") or []:
                user = r.get("user") or {}
                recipients.append(user.get("email") or (r.get("details") or {}).get("value") or r.get("user_id"))
        return {
            "id": alert.get("id"),
            "question_id": payload.get("card_id"),
            "condition": payload.get("send_condition"),
            "send_once": bool(payload.get("send_once")),
            "active": bool(alert.get("active", True)),
            "schedule": subscription.get("cron_schedule"),
            "recipients": recipients,
        }
    condition = "has_result"
    if alert.get("alert_condition") == "goal":
        condition = "goal_above" if alert.get("alert_above_goal") else "goal_below"
    channel = next(iter(alert.get("channels") or []), {})
    return {
        "id": alert.get("id"),
        "question_id": (alert.get("card") or {}).get("id"),
        "condition": condition,
        "send_once": bool(alert.get("alert_first_only")),
        "active": not alert.get("archived"),
        "schedule": " ".join(
            str(v)
            for v in (channel.get("schedule_type"), channel.get("schedule_day"), channel.get("schedule_hour"))
            if v is not None
        ),
        "recipients": [r.get("email") or r.get("id") for r in channel.get("recipients") or []],
    }


async def _set_alert_active(context: ExecutionContext, alert_id: Any, active: bool) -> Dict[str, Any]:
    """Turn an alert off or back on: /api/notification on Metabase 0.54+, /api/alert before."""
    path = f"/notification/{_path_id(alert_id)}"
    try:
        notification = await _api(context, "GET", path) or {}
    except HTTPError as e:
        if e.status != 404:
            raise
        try:
            if active:
                # Turned back on, the question runs unattended again; it may have changed while the alert was off.
                alert = await _api(context, "GET", f"/alert/{_path_id(alert_id)}") or {}
                await _checked_parameters(context, _path_id((alert.get("card") or {}).get("id")), [])
            return await _api(context, "PUT", f"/alert/{_path_id(alert_id)}", json={"archived": not active}) or {}
        except HTTPError as legacy_error:
            if legacy_error.status == 404:
                raise ValueError(f"There's no alert {alert_id}.") from None
            raise
    if notification.get("payload_type") != "notification/card":
        raise ValueError(f"Notification {alert_id} isn't a question alert.")
    if active:
        await _checked_parameters(context, _path_id((notification.get("payload") or {}).get("card_id")), [])
    # The update takes the whole notification; timestamps Metabase sets itself are left out. The id is sent:
    # without it, Metabase 0.54-0.63 deletes the alert instead of updating it.
    body = {
        k: notification[k] for k in ("id", "payload_type", "payload", "handlers", "subscriptions") if k in notification
    }
    body["active"] = active
    return await _api(context, "PUT", path, json=body) or {}


# {{name}}, {{snippet: name}} or {{#12-saved-question}}; Metabase trims the spaces inside the braces.
TEMPLATE_TAG = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")


def _without_sql_comments(sql: str) -> str:
    """SQL with its -- and /* */ comments removed, read as Metabase reads them: a marker inside 'quotes', a [[ ]]
    clause or a {{ }} doesn't start a comment."""
    out, i, quoted, optional = [], 0, False, 0
    while i < len(sql):
        if sql.startswith("{{", i):
            end = sql.find("}}", i)
            end = len(sql) if end < 0 else end + 2
            out.append(sql[i:end])
            i = end
            continue
        if not quoted and not optional and sql.startswith(("--", "/*"), i):
            line = sql.startswith("--", i)
            end = sql.find("\n" if line else "*/", i + 2)
            i = len(sql) if end < 0 else end + (0 if line else 2)
            continue
        if sql.startswith("[[", i) or (optional and sql.startswith("]]", i)):
            optional += 1 if sql[i] == "[" else -1
            out.append(sql[i : i + 2])
            i += 2
            continue
        quoted ^= sql[i] == "'"
        out.append(sql[i])
        i += 1
    return "".join(out)


def _placeholders(sql: Any) -> List[str]:
    """Names of the {{ }} in SQL, in order, without repeats. Metabase skips ones inside SQL comments."""
    return list(dict.fromkeys(TEMPLATE_TAG.findall(_without_sql_comments(str(sql or "")))))


def _updated_native_query(card: Dict[str, Any], database_id: Any, sql: str, tags: Dict[str, Any]) -> Dict[str, Any]:
    """The question's query with new SQL, in the format the question is saved in. Metabase 0.57+ saves MBQL 5
    stages, and its filter tags (field filters) can't be sent back in the older format."""
    dataset_query = card.get("dataset_query") or {}
    stages = dataset_query.get("stages")
    if isinstance(stages, list) and stages and isinstance(stages[0], dict) and "native" in stages[0]:
        stage = {k: v for k, v in stages[0].items() if k != "template-tags"}
        saved_tags = stages[0].get("template-tags")
        stage["native"] = sql
        stage["template-tags"] = list(tags.values()) if isinstance(saved_tags, list) else tags
        # Steps after the SQL (summarize, filter) are kept.
        return {**dataset_query, "stages": [stage, *stages[1:]]}
    query = _native_query(database_id, sql)
    query["native"]["template-tags"] = tags
    return query


# Filter types create_question and update_question can define, and the Metabase tag type each is saved as.
FILTER_TAG_TYPES = {"text": "text", "number": "number", "date": "date", "field": "dimension"}
# Stand-in values for filters without a default, so the SQL can be expanded and checked. Metabase quotes every
# value, so the stand-in doesn't change what the SQL does.
FILTER_STAND_INS = {
    "text": ("category", "x"),
    "number": ("number/=", 1),
    "date": ("date/single", "2020-01-01"),
    "boolean": ("boolean/=", [True]),
}


async def _template_tags(context: ExecutionContext, sql: str, filters: Any, existing: Dict[str, Any]) -> Dict[str, Any]:
    """Template tags for every {{ }} in the SQL: a filter given in filters, one the question already has, a snippet
    ({{snippet: name}}) or a saved question ({{#12}}). Anything else is refused, because Metabase can't run SQL with
    an undefined filter."""
    given = {}
    for f in filters or []:
        name = _required_text(f.get("name") if isinstance(f, dict) else None, "filter name")
        filter_type = f.get("type") or "text"
        if filter_type not in FILTER_TAG_TYPES:
            raise ValueError("filter type must be text, number, date or field")
        tag: Dict[str, Any] = {
            "id": (existing.get(name) or {}).get("id") or str(uuid.uuid4()),
            "name": name,
            "display-name": f.get("display_name") or name.replace("_", " ").title(),
            "type": FILTER_TAG_TYPES[filter_type],
            "required": bool(f.get("required", False)),
        }
        if filter_type == "field":
            if not _int_or_none(f.get("field_id")):
                raise ValueError(f"Filter {name} is a field filter, so it needs field_id (from get_table).")
            tag["dimension"] = ["field", f["field_id"], None]
            tag["widget-type"] = f.get("widget_type") or "category"
        if f.get("default") is not None:
            tag["default"] = f["default"]
        if tag["required"] and tag.get("default") is None:
            raise ValueError(f"Filter {name} is required, so it needs a default value.")
        given[name] = tag
    used = _placeholders(sql)
    unused = sorted(set(given) - set(used))
    if unused:
        raise ValueError(f"Filter {unused[0]} isn't used in the SQL; write it as {{{{{unused[0]}}}}}.")
    tags: Dict[str, Any] = {}
    snippets = None
    for name in used:
        if name in given:
            tags[name] = given[name]
        elif name in existing:
            tags[name] = existing[name]
        elif name.startswith("snippet:"):
            if snippets is None:
                snippets = {
                    sn.get("name"): sn for sn in _list_data(await _api(context, "GET", "/native-query-snippet"))
                }
            snippet = snippets.get(name[len("snippet:") :].strip())
            if snippet is None:
                raise ValueError(f"There's no snippet named {name[len('snippet:') :].strip()} in Metabase.")
            tags[name] = {
                "id": str(uuid.uuid4()),
                "name": name,
                "display-name": name,
                "type": "snippet",
                "snippet-name": snippet.get("name"),
                "snippet-id": snippet.get("id"),
            }
        elif re.fullmatch(r"#(\d+)(?:-[\w-]*)?", name):
            tags[name] = {
                "id": str(uuid.uuid4()),
                "name": name,
                "display-name": name,
                "type": "card",
                "card-id": int(re.match(r"#(\d+)", name).group(1)),
            }
        else:
            raise ValueError(
                f"The SQL uses {{{{{name}}}}}; define it in filters (name, type and optionally a default)."
            )
    return tags


def _stand_in_parameters(tags: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Values for filters that have no default, so Metabase can expand the SQL for the check."""
    params = []
    for tag in tags.values():
        stand_in = FILTER_STAND_INS.get(tag.get("type"))
        if stand_in and tag.get("default") is None:
            params.append(
                {"type": stand_in[0], "target": ["variable", ["template-tag", tag["name"]]], "value": stand_in[1]}
            )
    return params


async def _new_native_query(context: ExecutionContext, database_id: Any, sql: Any, filters: Any) -> Dict[str, Any]:
    """A new SQL question or model's query, with its {{ }} filters defined and its SQL checked."""
    sql = _required_text(sql, "sql")
    dataset_query = _native_query(database_id, sql)
    tags = await _template_tags(context, sql, filters, {})
    dataset_query["native"]["template-tags"] = tags
    await _check_new_sql(context, database_id, sql, dataset_query, tags)
    return dataset_query


async def _check_new_sql(
    context: ExecutionContext, database_id: Any, sql: str, dataset_query: Dict[str, Any], tags: Dict[str, Any]
) -> None:
    """Check SQL a question is about to be saved with. SQL with {{ }} is checked as Metabase expands it (filters,
    snippets, saved questions); optional [[ ]] clauses would be left out of that expansion, so they are refused."""
    if "{{" not in sql:
        await _read_only_sql(context, database_id, sql)
        return
    if "[[" in sql:
        raise ValueError("SQL with optional [[ ]] clauses can't be saved through this integration.")
    engine = await _database_engine(context, database_id)
    await _check_compiled(context, None, dataset_query, _stand_in_parameters(tags), engine, refusal="Not saved.")


def _has_key(value: Any, key: str) -> bool:
    """Whether a key appears anywhere, read as Metabase reads it: case and _ vs - don't matter ("NATIVE" is native)."""
    if isinstance(value, dict):
        return any(str(k).lower().replace("_", "-") == key for k in value) or any(
            _has_key(v, key) for v in value.values()
        )
    if isinstance(value, list):
        return any(_has_key(v, key) for v in value)
    return False


def _mbql_query(value: Any, key: str = "query") -> Dict[str, Any]:
    """A query-builder (MBQL) query, refused if it embeds SQL (a "native" query anywhere, such as a source-query),
    which would skip the SQL check. The word native as a filter value is fine."""
    if not isinstance(value, dict) or not value.get("source-table"):
        raise ValueError(f"{key} must be a query-builder query object with a source-table")
    if _has_key(value, "native"):
        raise ValueError(f"{key} can't contain SQL; use the SQL actions for SQL questions")
    return value


def _mbql_dataset_query(database_id: Any, query: Dict[str, Any]) -> Dict[str, Any]:
    return {"database": database_id, "type": "query", "query": query}


async def _check_source_questions(context: ExecutionContext, query: Dict[str, Any]) -> None:
    """A query-builder query built on saved questions (source-table "card__12") runs their SQL, so it is checked."""
    for card_id in sorted(set(re.findall(r'"card__(\d+)"', json.dumps(query)))):
        await _checked_parameters(context, card_id, [], saving=True)


async def _create_card(
    context: ExecutionContext, inputs: Dict[str, Any], card_type: str, dataset_query: Dict[str, Any]
):
    body: Dict[str, Any] = {
        "name": _required_text(inputs["name"], "name"),
        "type": card_type,
        "display": inputs.get("display") or ("scalar" if card_type == "metric" else "table"),
        "visualization_settings": {},
        "dataset_query": dataset_query,
    }
    _with_optional(body, description=inputs.get("description"), collection_id=inputs.get("collection_id"))
    card = await _api(context, "POST", "/card", json=body) or {}
    _require_id(card, "a question")
    return card


XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Excel files are returned base64-encoded in the action result, which must stay under the 6 MB Lambda response limit.
MAX_XLSX_BYTES = 3_500_000


async def _download(context: ExecutionContext, path: str, form: Dict[str, str]) -> bytes:
    """POST a form and return the binary body (Excel exports). The SDK's fetch reads every body as text, which breaks
    binary files, so this one request is made directly. Redirects aren't followed, so the API key only goes to the
    Metabase URL."""
    headers = get_auth_headers(context)
    del headers["Content-Type"]
    gateway = bool(_credentials(context).get("gateway_header_name"))
    timeout = aiohttp.ClientTimeout(total=QUERY_TIMEOUT_SECONDS)
    content = bytearray()
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # aiohttp retries a request on disconnect; an export reruns the question, so it is sent once.
            session._retry_connection = False
            async with session.post(
                f"{get_base_url(context)}/api{path}", data=form, headers=headers, allow_redirects=False
            ) as response:
                if response.status >= 300:
                    if gateway:
                        # As in _gateway_request, a gateway's error body isn't passed on.
                        raise HTTPError(response.status, "Request failed. Check gateway and Metabase access.", {})
                    if 300 <= response.status < 400:
                        raise ValueError("Metabase redirected the request. Use the final HTTPS Metabase URL.")
                    text = await response.text(errors="replace")
                    try:
                        data: Any = json.loads(text)
                    except ValueError:
                        data = text[:MAX_ERROR_LENGTH]
                    raise HTTPError(response.status, text[:MAX_ERROR_LENGTH], data)
                if "spreadsheetml" not in response.headers.get("Content-Type", ""):
                    # Metabase reports a failed query as JSON instead of the file.
                    text = (await response.text(errors="replace"))[:MAX_ERROR_LENGTH]
                    raise ValueError(f"Query failed: {text}")
                async for chunk in response.content.iter_chunked(64 * 1024):
                    content += chunk
                    if content[:1] == b"{":
                        # Metabase 0.49 sends a failed export's error as JSON under the spreadsheet content type.
                        content += await response.content.read()
                        failure = json.loads(content.decode("utf-8", "replace"))
                        raise ValueError(f"Query failed: {failure.get('error') or 'unknown error'}")
                    if len(content) > MAX_XLSX_BYTES:
                        raise ValueError(
                            "The Excel file is over 3.5 MB, too big to return. Filter the question or export as csv."
                        )
    except aiohttp.ClientError:
        raise ValueError("Could not connect to Metabase. Check the URL, TLS certificate and gateway access.") from None
    return bytes(content)


def _csv_export(text: str, max_rows: int) -> Dict[str, Any]:
    """Keep the header and up to max_rows CSV records, whole records only, within MAX_EXPORT_CHARS. Records are read
    with the csv module, so a value with a line break in quotes counts as one row."""
    # Any cell in the download may be read, even one past the rows kept (csv's default limit is 131,072 characters).
    csv.field_size_limit(max(csv.field_size_limit(), len(text) + 1))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    rows = 0
    truncated = False
    for i, record in enumerate(csv.reader(io.StringIO(text.lstrip("\ufeff")))):
        if i > max_rows:
            truncated = True
            break
        before = out.tell()
        # A blank line is a record with one empty value (a single-column NULL), not nothing.
        writer.writerow(record or [""])
        if out.tell() > MAX_EXPORT_CHARS:
            out.seek(before)
            out.truncate()
            truncated = True
            break
        rows = i
    return {"format": "csv", "content": out.getvalue().rstrip("\n"), "row_count": rows, "truncated": truncated}


async def _metabase_release(context: ExecutionContext) -> Optional[int]:
    """Metabase's release number, 49 for v0.49.25 and v1.49.25 alike (open source and paid share it)."""
    tag = str(((await _api(context, "GET", "/session/properties")) or {}).get("version", {}).get("tag") or "")
    match = re.match(r"v?\d+\.(\d+)", tag)
    return int(match.group(1)) if match else None


async def _has_legacy_metrics(context: ExecutionContext) -> bool:
    """Metabase 0.49 keeps metrics as table metrics at /api/metric, with their own ids. From 0.50 a metric is a
    question of type metric (0.50 moved the old ones to /api/legacy-metric)."""
    release = await _metabase_release(context)
    return release is not None and release < 50


async def _create_legacy_metric(
    context: ExecutionContext, inputs: Dict[str, Any], query: Dict[str, Any], error: HTTPError
) -> Dict[str, Any]:
    """Save a metric the way Metabase 0.49 keeps them: on a table, at /api/metric."""
    if not await _has_legacy_metrics(context):
        # A newer Metabase rejected the metric for another reason; that reason is the answer.
        raise ValueError(_error_message(error, context=context)) from None
    table_id = query.get("source-table")
    unsupported = sorted(set(query) - {"source-table", "aggregation", "filter"})
    if unsupported:
        raise ValueError(
            "On Metabase 0.49 a metric can only have a table, one aggregation and a filter, "
            f"not {', '.join(unsupported)}."
        )
    if not _int_or_none(table_id):
        raise ValueError(
            f"{_error_message(error, context=context)} On Metabase 0.49, a metric must be built on a table."
        )
    body = _with_optional(
        {
            "name": _required_text(inputs["name"], "name"),
            "table_id": table_id,
            "definition": query,
        },
        description=inputs.get("description"),
    )
    try:
        metric = await _api(context, "POST", "/metric", json=body) or {}
    except HTTPError as e:
        if e.status == 404:
            raise ValueError(_error_message(error, context=context)) from None
        raise
    _require_id(metric, "a metric")
    return {
        "id": metric["id"],
        "name": metric.get("name"),
        "description": metric.get("description"),
        "type": "legacy_metric",
        "display": None,
        "database_id": inputs["database_id"],
        "query_type": "query",
        "native_sql": None,
        "collection_id": None,
        "collection": None,
        "archived": bool(metric.get("archived")),
        "parameters": [],
        "note": "Saved as a table metric (Metabase 0.49). Its id is a metric id, not a question id; edit it "
        "under Admin → Table Metadata.",
    }


def _segment_summary(segment: Dict[str, Any]) -> Dict[str, Any]:
    definition = segment.get("definition") or {}
    return {
        "id": segment.get("id"),
        "name": segment.get("name"),
        "description": segment.get("description"),
        "table_id": segment.get("table_id"),
        "archived": bool(segment.get("archived")),
        # Metabase 0.57+ returns the definition as MBQL 5 stages, with a list of filters.
        "filter": (definition.get("query") or definition).get("filter")
        or next(iter(definition.get("stages") or [{}]), {}).get("filters"),
    }


async def _segment_definition(context: ExecutionContext, table_id: Any, filter_clause: Any) -> Dict[str, Any]:
    """A segment's definition as a full query, which Metabase 0.65 requires. 0.49 saves it too but then matches no
    rows, so _save_segment sends the inner query first."""
    # One clause starting with its operator. The newer form Metabase 0.57+ shows in list_segments (a list of clauses
    # with {"lib/uuid": ...} options) is stored as a filter that matches every row, so it is refused.
    if (
        not isinstance(filter_clause, list)
        or not filter_clause
        or not isinstance(filter_clause[0], str)
        or _has_key(filter_clause, "lib/uuid")
    ):
        raise ValueError(
            'filter must be one query-builder filter clause, e.g. [">", ["field", 12, null], 100] or '
            '["and", [...], [...]]; the form list_segments shows on Metabase 0.57+ can\'t be sent back.'
        )
    table = await _api(context, "GET", f"/table/{_path_id(table_id)}") or {}
    return {
        "database": table.get("db_id"),
        "type": "query",
        "query": {"source-table": table_id, "filter": filter_clause},
    }


async def _save_segment(context: ExecutionContext, method: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Save a segment with the definition shape this Metabase reads: the inner query (source-table + filter) on older
    versions, the full query on newer ones, which refuse the inner form with a 400 before saving anything."""
    definition = body.get("definition")
    if definition is not None:
        try:
            return await _api(context, method, path, json={**body, "definition": definition["query"]}) or {}
        except HTTPError as e:
            # Only the "needs a full query" refusal; any other 400 on 0.49 would save the shape it can't read. Through
            # a gateway the refusal's text is hidden, so a 400 from a Metabase past 0.50 is taken as that refusal.
            if e.status != 400:
                raise
            if ":type" not in json.dumps([e.message, e.response_data], default=str):
                release = await _metabase_release(context)
                if release is None or release < 51:
                    raise
    return await _api(context, method, path, json=body) or {}


def _timeline_event_summary(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": event.get("id"),
        "timeline_id": event.get("timeline_id"),
        "name": event.get("name"),
        "description": event.get("description"),
        "timestamp": event.get("timestamp"),
        "archived": bool(event.get("archived")),
    }


# ---- Editing dashboards ----


@metabase.action("update_dashboard")
class UpdateDashboardAction(ActionHandler):
    """Change a dashboard's name, description, collection, width or filter auto-apply setting."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard_id = _path_id(inputs["dashboard_id"])
        body = _with_optional(
            {},
            name=inputs.get("name"),
            collection_id=inputs.get("collection_id"),
            width=inputs.get("width"),
            auto_apply_filters=inputs.get("auto_apply_filters"),
        )
        if inputs.get("description") is not None:
            # An empty description clears it.
            body["description"] = inputs["description"] or None
        if not body:
            raise ValueError("Give at least one of name, description, collection_id, width or auto_apply_filters.")
        dashboard = await _api(context, "PUT", f"/dashboard/{dashboard_id}", json=body) or {}
        return _dashboard_summary(dashboard)


@metabase.action("update_dashboard_cards")
class UpdateDashboardCardsAction(ActionHandler):
    """Move, resize, retitle, move to another tab or remove cards on a dashboard."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        existing = dashboard.get("dashcards") or []
        tabs = dashboard.get("tabs") or []
        given = [c for c in inputs["cards"] if isinstance(c, dict)]
        changes = {c.get("dashcard_id"): c for c in given}
        if len(changes) != len(given):
            raise ValueError("Each card can be listed once; put all of a card's changes in one entry.")
        unknown = set(changes) - {dc.get("id") for dc in existing}
        if unknown:
            raise ValueError(f"Not cards on dashboard {inputs['dashboard_id']}: {sorted(unknown, key=str)}")

        dashcards = []
        for dc, original in zip(_dashcards_for_put(existing), existing):
            change = changes.get(dc.get("id"))
            if change is None:
                dashcards.append(dc)
                continue
            if change.get("remove"):
                continue
            for key, field in (("row", "row"), ("col", "col"), ("width", "size_x"), ("height", "size_y")):
                if _int_or_none(change.get(key)) is not None:
                    dc[field] = change[key]
            _check_grid(int(dc.get("col") or 0), int(dc.get("size_x") or 1))
            if change.get("tab_id") is not None:
                dc["dashboard_tab_id"] = _check_tab(change["tab_id"], tabs, inputs["dashboard_id"])
            if change.get("title") is not None:
                if "visualization_settings" not in dc:
                    raise ValueError(
                        f"Card {dc['id']} links to an item the API key can't read, so it can't be retitled."
                    )
                settings = dict(original.get("visualization_settings") or {})
                settings["card.title"] = change["title"]
                dc["visualization_settings"] = settings
            dashcards.append(dc)

        updated = await _put_dashboard_layout(context, inputs["dashboard_id"], dashcards, _tabs_for_put(tabs))
        return _dashboard_summary(updated)


@metabase.action("add_text_to_dashboard")
class AddTextToDashboardAction(ActionHandler):
    """Add a text, heading or link card to a dashboard."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        kind = inputs["kind"]
        if kind not in TEXT_CARD_KINDS:
            raise ValueError("kind must be text, heading or link")
        text = str(inputs.get("text") or "").strip()
        url = str(inputs.get("url") or "").strip()
        if kind == "link" and not url:
            raise ValueError("url is required for a link card")
        if kind != "link" and not text:
            raise ValueError("text is required for a text or heading card")

        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        existing = dashboard.get("dashcards") or []
        tabs = dashboard.get("tabs") or []
        tab_id = _check_tab(inputs.get("tab_id"), tabs, inputs["dashboard_id"])
        size_x = _clamp(inputs.get("width"), DASHBOARD_GRID_WIDTH if kind != "link" else 8, DASHBOARD_GRID_WIDTH)
        size_y = _clamp(inputs.get("height"), DEFAULT_TEXT_CARD_HEIGHT[kind], MAX_CARD_HEIGHT)
        col = _int_or_none(inputs.get("col")) or 0
        _check_grid(col, size_x)
        row = _int_or_none(inputs.get("row"))
        row = _bottom_row(existing, tab_id) if row is None else row

        settings: Dict[str, Any] = {
            "virtual_card": {
                "name": None,
                "display": kind,
                "visualization_settings": {},
                "dataset_query": {},
                "archived": False,
            }
        }
        if kind == "link":
            settings["link"] = {"url": url}
        else:
            settings["text"] = text
        dashcards = _dashcards_for_put(existing) + [_new_dashcard(None, row, col, size_x, size_y, tab_id, settings)]
        updated, added = await _put_new_dashcard(context, inputs["dashboard_id"], existing, dashcards, tabs)
        return {
            "dashboard_id": updated.get("id") or dashboard.get("id"),
            "dashcard_id": added.get("id"),
            "kind": kind,
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y,
        }


@metabase.action("update_dashboard_tabs")
class UpdateDashboardTabsAction(ActionHandler):
    """Add, rename, reorder or remove a dashboard's tabs."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        existing = dashboard.get("dashcards") or []
        old_tabs = dashboard.get("tabs") or []
        old_ids = {t.get("id") for t in old_tabs}
        tabs = []
        for i, tab in enumerate(t for t in inputs["tabs"] if isinstance(t, dict)):
            name = _required_text(tab.get("name"), "tab name")
            tab_id = tab.get("id")
            if tab_id is not None and tab_id not in old_ids:
                raise ValueError(
                    f"Tab {tab_id} is not on dashboard {inputs['dashboard_id']}; leave id out for a new tab."
                )
            # Negative ids mark new tabs for Metabase to create.
            tabs.append({"id": tab_id if tab_id is not None else -(i + 1), "name": name})

        kept = {t["id"] for t in tabs}
        dashcards = _dashcards_for_put(existing)
        orphaned = [
            dc["id"]
            for dc in dashcards
            if dc.get("dashboard_tab_id") is not None and dc["dashboard_tab_id"] not in kept
        ]
        if orphaned and tabs:
            raise ValueError(
                f"Cards {orphaned} are on tabs being removed. Move or remove them (update_dashboard_cards) first."
            )
        if not tabs and len({dc.get("dashboard_tab_id") for dc in dashcards}) > 1:
            raise ValueError("Cards are on more than one tab. Move them onto one tab before removing every tab.")
        for dc in dashcards:
            # A dashboard getting its first tabs puts every card on the first one; one losing its tabs keeps them.
            if not tabs:
                dc["dashboard_tab_id"] = None
            elif dc.get("dashboard_tab_id") is None:
                dc["dashboard_tab_id"] = tabs[0]["id"]

        path = f"/dashboard/{_path_id(inputs['dashboard_id'])}"
        try:
            updated = await _api(context, "PUT", path, json={"dashcards": dashcards, "tabs": tabs}) or {}
        except HTTPError as e:
            # Through a gateway the error body is hidden, so any 400 to this request counts.
            hidden = not e.response_data
            if (
                tabs
                or not old_tabs
                or e.status != 400
                or not (hidden or "every card has a tab" in str(e.response_data))
            ):
                raise
            # Metabase 0.49 can't remove a dashboard's last tab. One tab looks the same (Metabase shows no tab
            # bar for a single tab), so the cards' tab is kept and the others removed.
            keep = next(
                (dc.get("dashboard_tab_id") for dc in existing if dc.get("dashboard_tab_id")), old_tabs[0]["id"]
            )
            kept_tab = next(t for t in old_tabs if t.get("id") == keep)
            dashcards = [{**dc, "dashboard_tab_id": keep} for dc in dashcards]
            tabs = [{"id": keep, "name": kept_tab.get("name")}]
            updated = await _api(context, "PUT", path, json={"dashcards": dashcards, "tabs": tabs}) or {}
            summary = _dashboard_summary(updated)
            summary["note"] = "This Metabase can't remove the last tab, so one tab was kept; it shows no tab bar."
            return summary
        return _dashboard_summary(updated)


@metabase.action("update_dashboard_filters")
class UpdateDashboardFiltersAction(ActionHandler):
    """Set a dashboard's filters: add, change or remove them, their defaults, linked filters and card connections."""

    @_handled(saved_check="get_dashboard")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        existing = dashboard.get("dashcards") or []
        by_dashcard = {dc.get("id"): dc for dc in existing}
        old_params = {p.get("id"): p for p in dashboard.get("parameters") or []}

        parameters = []
        connections: Dict[str, List[Dict[str, Any]]] = {}
        linked_given = set()
        for f in inputs["filters"]:
            if not isinstance(f, dict):
                continue
            name = _required_text(f.get("name"), "filter name")
            filter_type = _required_text(f.get("type"), "filter type")
            filter_id = f.get("id") or secrets.token_hex(4)
            if any(p["id"] == f.get("id") for p in parameters):
                raise ValueError(f"Filter {f['id']} is listed twice; put all of its changes in one entry.")
            if f.get("id") and f["id"] not in old_params:
                raise ValueError(
                    f"Filter {f['id']} is not on dashboard {inputs['dashboard_id']}; leave id out for a new filter."
                )
            param = {
                **old_params.get(filter_id, {}),
                "id": filter_id,
                "name": name,
                "slug": _slug(name),
                "type": filter_type,
                "sectionId": filter_type.split("/")[0],
            }
            if filter_id in old_params and old_params[filter_id].get("type") != filter_type:
                # Settings for the old type (a text default or value list on a date filter) would break the new one.
                for key in ("default", "values_source_type", "values_source_config", "temporal_units"):
                    param.pop(key, None)
            if "default" in f:
                param["default"] = f["default"]
            if "required" in f:
                param["required"] = bool(f["required"])
            if param.get("required") and param.get("default") is None:
                raise ValueError(f"Filter {name} is required, so it needs a default value.")
            if "linked_filter_ids" in f:
                param["filteringParameters"] = list(f["linked_filter_ids"] or [])
                linked_given.add(filter_id)
            parameters.append(param)
            if "connections" in f:
                connections[filter_id] = list(f["connections"] or [])

        slugs = [p["slug"] for p in parameters]
        if len(set(slugs)) != len(slugs):
            raise ValueError("Two filters would have the same name; give each filter a different name.")
        kept = {p["id"] for p in parameters}
        for p in parameters:
            links = p.get("filteringParameters")
            unknown = [i for i in links or [] if i not in kept]
            if unknown and p["id"] in linked_given:
                raise ValueError(f"Filter {p['name']} is linked to {', '.join(map(str, unknown))}, which isn't kept.")
            if unknown:
                # A removed filter is dropped from the filters linked to it.
                p["filteringParameters"] = [i for i in links if i in kept]
        dashcards = _dashcards_for_put(existing)
        for dc in dashcards:
            # Connections of removed filters go; filters given new connections replace their old ones.
            mappings = [
                m
                for m in dc.get("parameter_mappings") or []
                if m.get("parameter_id") in kept and m.get("parameter_id") not in connections
            ]
            dc["parameter_mappings"] = mappings
            if dc.get("inline_parameters"):
                # Filters shown on the card itself (Metabase 0.55+) go when the filter is removed.
                dc["inline_parameters"] = [p for p in dc["inline_parameters"] if p in kept]
        param_names = {p["id"]: p["name"] for p in parameters}
        for filter_id, conns in connections.items():
            for conn in conns:
                original = by_dashcard.get(conn.get("dashcard_id"))
                if not original or not original.get("card_id"):
                    raise ValueError(f"Card {conn.get('dashcard_id')} is not a question card on this dashboard.")
                # A combined chart's other questions are connected by giving their question_id.
                questions = {original["card_id"]: original.get("card") or {}} | {
                    sr.get("id"): sr for sr in original.get("series") or []
                }
                question_id = conn.get("question_id") or original["card_id"]
                if question_id not in questions:
                    raise ValueError(f"Question {question_id} isn't shown on card {original['id']}.")
                dc = next(d for d in dashcards if d.get("id") == original["id"])
                if any(
                    m["parameter_id"] == filter_id and m["card_id"] == question_id for m in dc["parameter_mappings"]
                ):
                    # Metabase applies only one, so the other column would quietly stay unfiltered.
                    raise ValueError(
                        f"Filter {param_names[filter_id]} is connected to card {original['id']} twice; pick one."
                    )
                dc["parameter_mappings"].append(
                    {
                        "parameter_id": filter_id,
                        "card_id": question_id,
                        "target": _filter_target(original, questions[question_id], conn),
                    }
                )

        removed = set(old_params) - kept
        if (
            connections
            or removed
            or any(
                (p.get("default"), p.get("type"))
                != (old_params.get(p["id"], {}).get("default"), old_params.get(p["id"], {}).get("type"))
                for p in parameters
            )
        ):
            # Subscriptions run the questions with the filter defaults, types and connections, so new ones are checked;
            # a removed filter changes what they run too.
            if await _has_subscriptions(context, dashboard.get("id")):
                await _check_dashboard_questions(
                    context, {**dashboard, "parameters": parameters, "dashcards": dashcards}
                )
        updated = await _put_dashboard_layout(
            context,
            inputs["dashboard_id"],
            dashcards,
            _tabs_for_put(dashboard.get("tabs") or []),
            parameters=parameters,
        )
        return _dashboard_summary(updated)


@metabase.action("copy_dashboard")
class CopyDashboardAction(ActionHandler):
    """Copy a dashboard, optionally with copies of its questions."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard_id = _path_id(inputs["dashboard_id"])
        name = _required_text(inputs["name"], "name")
        collection_id = inputs.get("collection_id")
        copy_questions = bool(inputs.get("copy_questions", False))
        if collection_id is None or copy_questions:
            original = await _get_dashboard(context, inputs["dashboard_id"])
            if collection_id is None:
                # Metabase puts a copy at the top level unless told otherwise; keep it next to the original.
                collection_id = original.get("collection_id")
            if copy_questions:
                # Copies of the questions are new saved SQL, so they are checked like any question saved here.
                await _check_dashboard_questions(context, original, saving=True)
        body = _with_optional(
            {"is_deep_copy": copy_questions, "name": name},
            description=inputs.get("description"),
            collection_id=collection_id,
        )
        copy = await _api(context, "POST", f"/dashboard/{dashboard_id}/copy", json=body) or {}
        _require_id(copy, "a dashboard")
        result = {"id": copy.get("id"), "name": copy.get("name"), "collection_id": copy.get("collection_id")}
        # Metabase still makes the copy without some questions (ones this API key can't read, or archived
        # ones) and lists them, once per card they were on.
        uncopied = list(
            {
                c.get("id"): {"id": c.get("id"), "name": c.get("name")}
                for c in copy.get("uncopied") or []
                if isinstance(c, dict)
            }.values()
        )
        if uncopied:
            result["uncopied_questions"] = uncopied
            result["note"] = (
                f"Metabase left {len(uncopied)} question(s) off the copy, such as ones this API key can't read or "
                "archived ones."
            )
        return result


def _fit_rows(summary: Dict[str, Any], chars_left: int) -> int:
    """Drop a card's last rows until its result fits in chars_left; returns the characters left after it, 0 once rows
    are cut, so no more questions run."""
    size = len(json.dumps(summary, default=str))
    rows = summary.get("rows")
    if size <= chars_left or not rows:
        return chars_left - size
    budget = chars_left - len(json.dumps({**summary, "rows": []}, default=str))
    kept = 0
    for row in rows:
        budget -= len(json.dumps(row, default=str)) + 2
        if budget < 0:
            break
        kept += 1
    summary.update(rows=rows[:kept], row_count=kept, truncated=True)
    return 0


@metabase.action("run_dashboard")
class RunDashboardAction(ActionHandler):
    """Run every question on a dashboard (or one tab) with filter values, and return each card's rows."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        max_rows = _clamp(inputs.get("max_rows"), DEFAULT_DASHBOARD_RUN_ROWS, MAX_ROWS_LIMIT)
        tab_id = inputs.get("tab_id")
        if tab_id is not None:
            _check_tab(tab_id, dashboard.get("tabs") or [], inputs["dashboard_id"])
        params = dashboard.get("parameters") or []
        by_key = {p.get("id"): p for p in params} | {p.get("slug"): p for p in params}

        # Filter values: the ones given (by id or slug), else each filter's default, sent explicitly so the
        # checked SQL and the run use the same values.
        values = _default_values(dashboard)
        for given in inputs.get("filters") or []:
            param = by_key.get(given.get("filter")) if isinstance(given, dict) else None
            if param is None:
                raise ValueError(
                    f"No filter {given.get('filter') if isinstance(given, dict) else given} on this dashboard."
                )
            values[param["id"]] = {"id": param["id"], "type": param.get("type"), "value": given.get("value")}

        dashcards = [
            dc for dc in dashboard.get("dashcards") or [] if tab_id is None or dc.get("dashboard_tab_id") == tab_id
        ]
        questions = _dashboard_questions(dashcards)
        results = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + DASHBOARD_RUN_SECONDS
        chars_left = MAX_DASHBOARD_RESULT_CHARS
        for dc, card_id, card_name in questions[:MAX_DASHBOARD_CARDS_RUN]:
            seconds_left = deadline - loop.time()
            if seconds_left < MIN_DASHBOARD_CARD_SECONDS or chars_left <= 0:
                break
            summary = {"dashcard_id": dc.get("id"), "card_id": card_id, "card_name": card_name}

            async def run() -> Any:
                card_params = _card_parameters_for(dc, values, card_id)
                # A dashboard run applies a SQL filter's own default but not the question's saved filter
                # defaults, so the question is also checked without those.
                await _checked_parameters(context, _path_id(card_id), card_params)
                used = [values[p] for p in dict.fromkeys(p["id"] for p in card_params)]
                return await _api(
                    context,
                    "POST",
                    f"/dashboard/{_path_id(dashboard.get('id'))}/dashcard/{_path_id(dc['id'])}/card/{_path_id(card_id)}/query",
                    json={"parameters": used},
                    timeout=min(QUERY_TIMEOUT_SECONDS, max(1, int(deadline - loop.time()))),
                )

            try:
                # The check's requests count against the time left too, not just the query.
                summary.update(_query_result(await asyncio.wait_for(run(), seconds_left), max_rows))
            except Exception as e:
                summary["error"] = _error_message(e, context=context)
            chars_left = _fit_rows(summary, chars_left)
            results.append(summary)
        skipped = len(questions) - len(results)
        return {
            "dashboard_id": dashboard.get("id"),
            "cards": results,
            "card_count": len(results),
            "skipped_card_count": skipped,
            **(
                {
                    "skipped_reason": (
                        "Stopped early to stay within the time or size limit"
                        if skipped > max(len(questions) - MAX_DASHBOARD_CARDS_RUN, 0)
                        else f"Only {MAX_DASHBOARD_CARDS_RUN} cards are run at a time"
                    )
                    + "; run the skipped questions with run_question, or this action with tab_id or a lower "
                    "max_rows."
                }
                if skipped
                else {}
            ),
        }


# ---- History ----


async def _revision_entity(context: ExecutionContext, item_type: Any) -> str:
    entity = REVISION_ENTITIES.get(item_type)
    if entity is None:
        raise ValueError(f"item_type must be one of {', '.join(REVISION_ENTITIES)}")
    if item_type == "metric" and await _has_legacy_metrics(context):
        raise ValueError("On Metabase 0.49 a metric's history is under Admin → Table Metadata, not here.")
    return entity


async def _revisions(context: ExecutionContext, entity: str, item_id: Any) -> Any:
    try:
        return await _api(context, "GET", _with_query("/revision", [("entity", entity), ("id", item_id)]))
    except HTTPError as e:
        # Metabase 0.49 keeps segment history at /segment/:id/revisions; its /revision only takes cards and dashboards.
        if entity != "segment" or e.status != 400:
            raise
        return await _api(context, "GET", f"/segment/{_path_id(item_id)}/revisions")


async def _revert(context: ExecutionContext, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return await _api(context, "POST", "/revision/revert", json=body) or {}
    except HTTPError as e:
        if body["entity"] != "segment" or e.status != 400:
            raise
        path = f"/segment/{_path_id(body['id'])}/revert"
        return await _api(context, "POST", path, json={"revision_id": body["revision_id"]}) or {}


@metabase.action("get_revision_history")
class GetRevisionHistoryAction(ActionHandler):
    """List the saved versions of a question, model, metric, dashboard or segment."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        entity = await _revision_entity(context, inputs["item_type"])
        data = await _revisions(context, entity, inputs["item_id"])
        revisions = [
            {
                "revision_id": r.get("id"),
                "description": r.get("description"),
                "timestamp": r.get("timestamp"),
                "user": (r.get("user") or {}).get("common_name"),
                "is_creation": bool(r.get("is_creation")),
                "is_reversion": bool(r.get("is_reversion")),
                "most_recent": bool(r.get("most_recent")),
            }
            for r in _list_data(data)
        ]
        return {"revisions": revisions, "count": len(revisions)}


@metabase.action("revert_to_revision")
class RevertToRevisionAction(ActionHandler):
    """Put a question, model, metric, dashboard or segment back to an earlier saved version."""

    @_handled(saved_check="get_revision_history")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        entity = await _revision_entity(context, inputs["item_type"])
        body = {"entity": entity, "id": inputs["item_id"], "revision_id": inputs["revision_id"]}
        item_id = inputs["item_id"]
        checked = entity == "card" or (entity == "dashboard" and await _has_subscriptions(context, item_id))
        current = None
        if checked:
            history = _list_data(await _revisions(context, entity, item_id))
            current = next((r.get("id") for r in history if r.get("most_recent")), None)
        revision = await _revert(context, body)
        if checked:
            try:
                if entity == "card":
                    await _checked_parameters(context, _path_id(item_id), [], saving=True)
                else:
                    # Its subscriptions send the questions with the old version's filter defaults and connections.
                    await _check_dashboard_questions(context, await _get_dashboard(context, item_id))
            except Exception as e:
                # A question put back to SQL that writes would run it for anyone (or any alert) that runs it, and
                # one that couldn't be checked isn't known to be safe, so either way it is put back.
                if current is not None:
                    await _revert(context, {**body, "revision_id": current})
                reason = "is refused" if isinstance(e, ValueError) else "couldn't be checked"
                raise ValueError(
                    f"Not reverted: that version's SQL {reason}, so the {inputs['item_type']} was put back. "
                    f"{_error_message(e, context=context)}"
                ) from None
        return {
            "item_type": inputs["item_type"],
            "item_id": inputs["item_id"],
            "new_revision_id": revision.get("id"),
            "description": revision.get("description"),
        }


# ---- Editing questions, models and metrics ----


def _leave_dashboard_to_move(card: Dict[str, Any], changes: Dict[str, Any]) -> None:
    """A question saved inside a dashboard (Metabase 0.53+) has to leave it to move to another collection."""
    if card.get("dashboard_id") is not None and changes.get("collection_id", card.get("collection_id")) != card.get(
        "collection_id"
    ):
        changes["dashboard_id"] = None


@metabase.action("update_question")
class UpdateQuestionAction(ActionHandler):
    """Change a saved question, model or metric: name, description, SQL, chart type, chart settings or collection."""

    @_handled(saved_check="get_question")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        card_id = _path_id(inputs["question_id"])
        body = _with_optional(
            {},
            name=inputs.get("name"),
            description=inputs.get("description"),
            display=inputs.get("display"),
            collection_id=inputs.get("collection_id"),
        )
        settings = inputs.get("visualization_settings")
        if inputs.get("filters") and inputs.get("sql") is None:
            raise ValueError("filters can only be given together with sql.")
        if inputs.get("sql") is not None or settings is not None or "collection_id" in body:
            card = await _api(context, "GET", f"/card/{card_id}") or {}
            _leave_dashboard_to_move(card, body)
            if inputs.get("sql") is not None:
                database_id = card.get("database_id") or (card.get("dataset_query") or {}).get("database")
                sql = _required_text(inputs["sql"], "sql")
                _, existing = _saved_native(card.get("dataset_query") or {})
                tags = await _template_tags(context, sql, inputs.get("filters"), existing)
                body["dataset_query"] = _updated_native_query(card, database_id, sql, tags)
                await _check_new_sql(context, database_id, sql, body["dataset_query"], tags)

            if settings is not None:
                if not isinstance(settings, dict):
                    raise ValueError("visualization_settings must be an object")
                # Given keys are merged into the saved settings; a key set to null is removed.
                merged = {**(card.get("visualization_settings") or {}), **settings}
                body["visualization_settings"] = {k: v for k, v in merged.items() if v is not None}
        if not body:
            raise ValueError("Give a change: name, description, sql, display, visualization_settings or collection_id.")
        card = await _api(context, "PUT", f"/card/{card_id}", json=body) or {}
        return _card_summary(card)


@metabase.action("copy_question")
class CopyQuestionAction(ActionHandler):
    """Copy a saved question, model or metric, optionally renaming it or putting it in another collection."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        # The copy is new saved SQL, so the question is checked like any question saved here.
        await _checked_parameters(context, _path_id(inputs["question_id"]), [], saving=True)
        card = await _api(context, "POST", f"/card/{_path_id(inputs['question_id'])}/copy") or {}
        _require_id(card, "a question")
        changes = _with_optional({}, name=inputs.get("name"), collection_id=inputs.get("collection_id"))
        # A copy of a question saved in a dashboard is saved there too, with its own card on that dashboard, which
        # Metabase only removes as the copy leaves when asked to.
        _leave_dashboard_to_move(card, changes)
        path = f"/card/{_path_id(card['id'])}" + ("?delete_old_dashcards=true" if "dashboard_id" in changes else "")
        if changes:
            try:
                card = await _api(context, "PUT", path, json=changes) or card
            except Exception as e:
                raise ValueError(
                    f"The copy was made as question {card['id']} but couldn't be renamed or moved: "
                    f"{_error_message(e, context=context)}. Change it with update_question, don't copy again."
                ) from None
        return _card_summary(card)


@metabase.action("create_query_builder_question")
class CreateQueryBuilderQuestionAction(ActionHandler):
    """Save a query-builder (point-and-click) question from a query-builder query."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = _mbql_query(inputs["query"])
        await _check_source_questions(context, query)
        card = await _create_card(context, inputs, "question", _mbql_dataset_query(inputs["database_id"], query))
        return _card_summary(card)


@metabase.action("create_model")
class CreateModelAction(ActionHandler):
    """Save a model (a curated table others explore) from SQL or a query-builder query."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        sql, query = inputs.get("sql"), inputs.get("query")
        if (sql is None) == (query is None):
            raise ValueError("Give exactly one of sql or query.")
        if sql is not None:
            # Metabase refuses {{ }} filters in a model; snippets and saved questions are fine.
            names = [t for t in _placeholders(sql) if not t.startswith(("snippet:", "#"))]
            if names:
                raise ValueError(
                    f"A model can't have {{{{ }}}} filters ({', '.join(names)}); save a question for that instead."
                )
            dataset_query = await _new_native_query(context, inputs["database_id"], sql, None)
        else:
            query = _mbql_query(query)
            await _check_source_questions(context, query)
            dataset_query = _mbql_dataset_query(inputs["database_id"], query)
        card = await _create_card(context, inputs, "model", dataset_query)
        return _card_summary(card)


@metabase.action("create_metric")
class CreateMetricAction(ActionHandler):
    """Save a metric (an official reusable calculation) from a query-builder query with one aggregation."""

    @_handled(saved_check="search")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        query = _mbql_query(inputs["query"])
        if not isinstance(query.get("aggregation"), list) or len(query["aggregation"]) != 1:
            raise ValueError('A metric\'s query needs exactly one aggregation, e.g. [["sum", ["field", 12, null]]].')
        await _check_source_questions(context, query)
        try:
            card = await _create_card(context, inputs, "metric", _mbql_dataset_query(inputs["database_id"], query))
        except HTTPError as e:
            if e.status != 400:
                raise
            # Metabase 0.49 has no metric questions, only the older table metrics.
            legacy = await _create_legacy_metric(context, inputs, query, e)
            return legacy
        return _card_summary(card)


@metabase.action("export_question_results")
class ExportQuestionResultsAction(ActionHandler):
    """Run a saved question and return its full results as CSV text or JSON rows (more than run_question's 2,000)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        card_id = _path_id(inputs["question_id"])
        export_format = inputs.get("format") or "csv"
        if export_format not in ("csv", "json", "xlsx"):
            raise ValueError("format must be csv, json or xlsx")
        max_rows = _clamp(inputs.get("max_rows"), DEFAULT_EXPORT_ROWS, MAX_EXPORT_ROWS)
        parameters = [_run_parameter(p) for p in inputs.get("parameters") or []]
        parameters = await _checked_parameters(context, card_id, parameters, also_without_defaults=False)
        # Export endpoints read their options from a form, as Metabase's own download button sends them.
        form = {"parameters": json.dumps(parameters), "format_rows": "false"}
        if export_format == "xlsx":
            content = await _download(context, f"/card/{card_id}/query/xlsx", form)
            return {
                "format": "xlsx",
                "file": {
                    "name": f"question-{inputs['question_id']}.xlsx",
                    "contentType": XLSX_CONTENT_TYPE,
                    "content": base64.b64encode(content).decode("ascii"),
                },
                "row_count": None,
                "truncated": False,
            }
        data = await _api(
            context,
            "POST",
            f"/card/{card_id}/query/{export_format}",
            allow_text=True,
            data=form,
            content_type="application/x-www-form-urlencoded",
            timeout=QUERY_TIMEOUT_SECONDS,
        )
        if export_format == "json" and not isinstance(data, dict):
            rows = data if isinstance(data, list) else []
            # Whole rows only, within the same size budget as CSV, so the result fits the response limit.
            kept, size = [], 0
            for row in rows[:max_rows]:
                size += len(json.dumps(row, default=str)) + 1
                if size > MAX_EXPORT_CHARS:
                    break
                kept.append(row)
            return {"format": "json", "rows": kept, "row_count": len(kept), "truncated": len(rows) > len(kept)}
        if isinstance(data, dict):
            # Metabase reports a failed query as a JSON object instead of the file.
            raise ValueError(f"Query failed: {data.get('error') or data.get('message') or 'unknown error'}")
        data = data if isinstance(data, str) else ""
        if data.lstrip().startswith("{"):
            # Metabase 0.49 answers a failed CSV export with HTTP 200 and the error as JSON.
            try:
                failure = json.loads(data)
            except ValueError:
                failure = None
            if isinstance(failure, dict) and (failure.get("error") or failure.get("status") == "failed"):
                raise ValueError(f"Query failed: {failure.get('error') or 'unknown error'}")
        return _csv_export(data, max_rows)


# ---- Segments ----


@metabase.action("list_segments")
class ListSegmentsAction(ActionHandler):
    """List saved segments (named filters), optionally for one table."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        table_id = inputs.get("table_id")
        segments = [
            _segment_summary(s)
            for s in _list_data(await _api(context, "GET", "/segment"))
            if table_id is None or s.get("table_id") == table_id
        ]
        return {"segments": segments, "count": len(segments)}


@metabase.action("create_segment")
class CreateSegmentAction(ActionHandler):
    """Save a segment: a named filter on a table, such as 'Active customers'."""

    @_handled(saved_check="list_segments")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {
                "name": _required_text(inputs["name"], "name"),
                "table_id": inputs["table_id"],
                "definition": await _segment_definition(context, inputs["table_id"], inputs["filter"]),
            },
            description=inputs.get("description"),
        )
        segment = await _save_segment(context, "POST", "/segment", body)
        _require_id(segment, "a segment")
        return _segment_summary(segment)


@metabase.action("update_segment")
class UpdateSegmentAction(ActionHandler):
    """Change a segment's name, description or filter."""

    @_handled(saved_check="list_segments")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        segment_id = _path_id(inputs["segment_id"])
        body = _with_optional({}, name=inputs.get("name"), description=inputs.get("description"))
        if inputs.get("filter") is not None:
            segment = await _api(context, "GET", f"/segment/{segment_id}") or {}
            body["definition"] = await _segment_definition(context, segment.get("table_id"), inputs["filter"])
        if not body:
            raise ValueError("Give at least one of name, description or filter.")
        body["revision_message"] = SEGMENT_REVISION_MESSAGE
        segment = await _save_segment(context, "PUT", f"/segment/{segment_id}", body)
        return _segment_summary(segment)


# ---- Organising content ----


async def _collection_archived(context: ExecutionContext, path: str) -> bool:
    """Whether a collection is in the trash. An edit sends it back, because Metabase 0.65 takes a missing archived as
    false and would bring a trashed collection (and everything in it) back without restore_item's checks."""
    return bool((await _api(context, "GET", path) or {}).get("archived"))


@metabase.action("update_collection")
class UpdateCollectionAction(ActionHandler):
    """Rename a collection, change its description, or move it into another collection."""

    @_handled(saved_check="list_collections")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {},
            name=inputs.get("name"),
            description=inputs.get("description"),
            parent_id=inputs.get("parent_collection_id"),
        )
        if inputs.get("move_to_root"):
            if inputs.get("parent_collection_id") is not None:
                raise ValueError("Give either parent_collection_id or move_to_root, not both.")
            body["parent_id"] = None
        if not body:
            raise ValueError("Give at least one of name, description, parent_collection_id or move_to_root.")
        path = f"/collection/{_path_id(inputs['collection_id'])}"
        body["archived"] = await _collection_archived(context, path)
        collection = await _api(context, "PUT", path, json=body) or {}
        return {
            "id": collection.get("id"),
            "name": collection.get("name"),
            "description": collection.get("description"),
            "parent_id": _parent_from_location(collection.get("location")),
            "location": collection.get("location"),
        }


@metabase.action("move_items")
class MoveItemsAction(ActionHandler):
    """Move questions, models, metrics, dashboards or collections into a collection (or the root)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        target = inputs.get("collection_id")
        if (target is None) == (not inputs.get("move_to_root")):
            raise ValueError("Give either collection_id, or move_to_root to move items to the top level.")
        results = []
        for item in inputs["items"]:
            item_type = item.get("item_type") if isinstance(item, dict) else None
            path = (
                ARCHIVE_PATHS.get(item_type)
                if item_type in ("question", "model", "metric", "dashboard", "collection")
                else None
            )
            result: Dict[str, Any] = {
                "item_type": item_type,
                "id": item.get("id") if isinstance(item, dict) else None,
            }
            try:
                if path is None:
                    raise ValueError("item_type must be question, model, metric, dashboard or collection")
                if item_type == "metric" and await _has_legacy_metrics(context):
                    raise ValueError("On Metabase 0.49 metrics belong to a table, not a collection.")
                key = "parent_id" if item_type == "collection" else "collection_id"
                body: Dict[str, Any] = {key: target}
                if path == "card":
                    # A question saved inside a dashboard (Metabase 0.53+) has to leave it to move.
                    card = await _api(context, "GET", f"/card/{_path_id(item['id'])}") or {}
                    if card.get("dashboard_id") is not None:
                        body["dashboard_id"] = None
                if path == "collection":
                    body["archived"] = await _collection_archived(context, f"/collection/{_path_id(item['id'])}")
                await _api(context, "PUT", f"/{path}/{_path_id(item['id'])}", json=body)
                result["moved"] = True
            except Exception as e:
                result.update(moved=False, error=_error_message(e, context=context))
            results.append(result)
        moved = sum(1 for r in results if r["moved"])
        return {"items": results, "moved_count": moved, "failed_count": len(results) - moved}


async def _set_archived(context: ExecutionContext, inputs: Dict[str, Any], archived: bool) -> Dict[str, Any]:
    item_type = inputs["item_type"]
    if item_type == "alert":
        await _set_alert_active(context, inputs["item_id"], not archived)
    elif item_type == "subscription":
        path = f"/pulse/{_path_id(inputs['item_id'])}"
        pulse = await _api(context, "GET", path) or {}
        if not archived:
            # Turned back on, it runs every question on the dashboard on its schedule, so they're checked as when
            # it was created; the SQL may have changed while it was off.
            await _check_dashboard_questions(
                context, await _get_dashboard(context, pulse.get("dashboard_id")), pulse=pulse
            )
        await _api(context, "PUT", path, json={**_pulse_flags(pulse), "archived": archived})
    elif item_type == "dashboard" and not archived and await _has_subscriptions(context, inputs["item_id"]):
        # Metabase holds a trashed dashboard's subscriptions and sends them again once it's back, so its questions
        # are checked as when a subscription is turned back on.
        path = f"/dashboard/{_path_id(inputs['item_id'])}"
        try:
            dashboard: Optional[Dict[str, Any]] = await _get_dashboard(context, inputs["item_id"])
        except HTTPError as e:
            # Metabase before 0.51 won't show a trashed dashboard, so there it is restored, checked, and put back in
            # the trash if refused.
            if e.status != 404:
                raise
            dashboard = None
        if dashboard is not None:
            await _check_dashboard_questions(context, dashboard)
        await _api(context, "PUT", path, json={"archived": False})
        if dashboard is None:
            try:
                await _check_dashboard_questions(context, await _get_dashboard(context, inputs["item_id"]))
            except Exception as e:
                await _api(context, "PUT", path, json={"archived": True})
                reason = "is refused" if isinstance(e, ValueError) else "couldn't be checked"
                raise ValueError(
                    f"Not restored: a question's SQL {reason}, so the dashboard was put back in the trash. "
                    f"{_error_message(e, context=context)}"
                ) from None
    else:
        path = ARCHIVE_PATHS.get(item_type)
        if path is None:
            raise ValueError(f"item_type must be one of {', '.join([*ARCHIVE_PATHS, 'alert'])}")
        body: Dict[str, Any] = {"archived": archived}
        if item_type == "metric" and await _has_legacy_metrics(context):
            # create_metric returned a table metric id here, not a question id.
            path = "metric"
        if path in ("segment", "metric"):
            body["revision_message"] = SEGMENT_REVISION_MESSAGE
        await _api(context, "PUT", f"/{path}/{_path_id(inputs['item_id'])}", json=body)
    return {"item_type": item_type, "item_id": inputs["item_id"], "archived": archived}


@metabase.action("archive_item")
class ArchiveItemAction(ActionHandler):
    """Move an item to Metabase's trash (or turn an alert off). Nothing is deleted; restore_item brings it back."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        return await _set_archived(context, inputs, True)


@metabase.action("restore_item")
class RestoreItemAction(ActionHandler):
    """Bring an item back from Metabase's trash (or turn an alert back on)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        return await _set_archived(context, inputs, False)


# ---- Alerts and subscriptions ----


@metabase.action("list_alerts")
class ListAlertsAction(ActionHandler):
    """List question alerts, optionally for one question."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        question_id = inputs.get("question_id")
        include_inactive = "true" if inputs.get("include_inactive") else "false"
        params = [
            ("payload_type", "notification/card"),
            ("include_inactive", include_inactive),
            ("card_id", question_id),
        ]
        try:
            data = await _api(context, "GET", _with_query("/notification", params))
        except HTTPError as e:
            # Metabase before 0.54 keeps alerts at /api/alert.
            if e.status != 404:
                raise
            # The old API lists either active or archived alerts, so turned-off ones are a second request.
            data = _list_data(await _api(context, "GET", _with_query("/alert", [("archived", "false")])))
            if inputs.get("include_inactive"):
                data += _list_data(await _api(context, "GET", _with_query("/alert", [("archived", "true")])))
        alerts = [_alert_summary(a) for a in _list_data(data)]
        alerts = [a for a in alerts if question_id is None or a["question_id"] == question_id]
        return {"alerts": alerts, "count": len(alerts)}


@metabase.action("create_alert")
class CreateAlertAction(ActionHandler):
    """Email people when a saved question has results, or goes above or below its goal line."""

    @_handled(saved_check="list_alerts")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        question_id = inputs["question_id"]
        condition = inputs.get("condition") or "has_result"
        if condition not in ALERT_CONDITIONS:
            raise ValueError("condition must be has_result, goal_above or goal_below")
        frequency, hour, day = _schedule(inputs)
        user_ids, emails = _recipients(inputs)
        send_once = bool(inputs.get("send_once", False))
        # Metabase runs the question on the schedule with nobody watching, so it is checked like run_question.
        await _checked_parameters(context, _path_id(question_id), [])
        notification = {
            "payload_type": "notification/card",
            "payload": {"card_id": question_id, "send_condition": condition, "send_once": send_once},
            "handlers": [
                {
                    "channel_type": "channel/email",
                    "recipients": [{"type": "notification-recipient/user", "user_id": u} for u in user_ids]
                    + [{"type": "notification-recipient/raw-value", "details": {"value": e}} for e in emails],
                }
            ],
            "subscriptions": [{"type": "notification-subscription/cron", "cron_schedule": _cron(frequency, hour, day)}],
        }
        try:
            alert = await _api(context, "POST", "/notification", json=notification) or {}
        except HTTPError as e:
            # Metabase before 0.54 creates alerts at /api/alert.
            if e.status != 404:
                raise
            legacy = {
                "card": {"id": question_id, "include_csv": False, "include_xls": False},
                "alert_condition": "rows" if condition == "has_result" else "goal",
                "alert_above_goal": {"goal_above": True, "goal_below": False}.get(condition),
                "alert_first_only": send_once,
                "channels": [_pulse_channel(frequency, hour, day, user_ids, emails)],
            }
            alert = await _api(context, "POST", "/alert", json=legacy) or {}
        _require_id(alert, "an alert")
        return _alert_summary(alert)


@metabase.action("list_subscriptions")
class ListSubscriptionsAction(ActionHandler):
    """List dashboard subscriptions (scheduled emails of a dashboard), optionally for one dashboard."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        params = [
            ("dashboard_id", inputs.get("dashboard_id")),
            ("archived", "true" if inputs.get("archived") else None),
        ]
        subscriptions = [
            _subscription_summary(p) for p in _list_data(await _api(context, "GET", _with_query("/pulse", params)))
        ]
        return {"subscriptions": subscriptions, "count": len(subscriptions)}


@metabase.action("create_subscription")
class CreateSubscriptionAction(ActionHandler):
    """Email a dashboard to people on a schedule."""

    @_handled(saved_check="list_subscriptions")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        dashboard = await _get_dashboard(context, inputs["dashboard_id"])
        frequency, hour, day = _schedule(inputs)
        user_ids, emails = _recipients(inputs)
        cards = [
            {"id": dc["card_id"], "dashboard_card_id": dc["id"], "include_csv": False, "include_xls": False}
            for dc in dashboard.get("dashcards") or []
            if dc.get("card_id") and not dc.get("action_id")
        ]
        if not cards:
            raise ValueError("The dashboard has no questions to send.")
        # Metabase runs every question (combined charts' series too) on the schedule with the dashboard's filter
        # defaults and nobody watching, so each is checked that way first.
        await _check_dashboard_questions(context, dashboard)
        body = {
            "name": inputs.get("name") or dashboard.get("name"),
            "dashboard_id": dashboard.get("id"),
            "cards": cards,
            "channels": [_pulse_channel(frequency, hour, day, user_ids, emails)],
            "skip_if_empty": bool(inputs.get("skip_if_empty", False)),
        }
        pulse = await _api(context, "POST", "/pulse", json=body) or {}
        _require_id(pulse, "a subscription")
        return _subscription_summary(pulse)


@metabase.action("update_subscription")
class UpdateSubscriptionAction(ActionHandler):
    """Change a dashboard subscription's schedule, recipients, name or skip-if-empty setting."""

    @_handled(saved_check="list_subscriptions")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        path = f"/pulse/{_path_id(inputs['subscription_id'])}"
        body = _with_optional({}, name=inputs.get("name"), skip_if_empty=inputs.get("skip_if_empty"))
        schedule = _with_optional(
            {}, frequency=inputs.get("frequency"), hour=inputs.get("hour"), day_of_week=inputs.get("day_of_week")
        )
        recipients = _with_optional(
            {},
            recipient_user_ids=inputs.get("recipient_user_ids"),
            recipient_emails=inputs.get("recipient_emails"),
        )
        if not body and not schedule and not recipients:
            raise ValueError("Give at least one change.")
        pulse = await _api(context, "GET", path) or {}
        body = {**_pulse_flags(pulse), **body}
        if schedule or recipients:
            channels = pulse.get("channels") or []
            channel = next((c for c in channels if c.get("channel_type") == "email"), {})
            updated = dict(channel)
            # Every channel but the one edited is sent back as it is; Metabase deletes the ones left out.
            others = [c for c in channels if c is not channel]
            # A subscription with no email channel yet gets one on its other channel's schedule.
            source = channel or (others[0] if others else {})
            current = {
                "frequency": source.get("schedule_type"),
                "hour": source.get("schedule_hour"),
                "day_of_week": source.get("schedule_day"),
            }
            if schedule and current["frequency"] == "monthly" and "frequency" not in schedule:
                # A monthly schedule (set in Metabase) keeps its week of the month; only the hour or day change.
                _, hour, day = _schedule({**current, "frequency": "weekly", **schedule})
                updated.update(
                    schedule_hour=hour if "hour" in schedule else updated.get("schedule_hour"),
                    schedule_day=day if "day_of_week" in schedule else updated.get("schedule_day"),
                )
            elif schedule:
                updated.update(_pulse_schedule(*_schedule({**current, **schedule})))
            # A schedule left alone (monthly ones included) is kept exactly as it is.
            if recipients:
                old_users = [r["id"] for r in channel.get("recipients") or [] if r.get("id")]
                old_emails = [r["email"] for r in channel.get("recipients") or [] if not r.get("id") and r.get("email")]
                user_ids, emails = _recipients(
                    {"recipient_user_ids": old_users, "recipient_emails": old_emails, **recipients}
                )
                updated["recipients"] = _pulse_recipients(user_ids, emails)
            if not channel and not recipients:
                # No email channel and no one to email: the schedule change goes to the channels it has (Slack).
                others = [{**c, **updated} for c in others]
                updated = None
            elif not channel:
                # A new email channel starts sending, maybe for a subscription that was paused (its Slack channel
                # turned off) while its questions changed, so they are checked as when it was created.
                dashboard = await _get_dashboard(context, pulse.get("dashboard_id"))
                await _check_dashboard_questions(context, dashboard, pulse=pulse)
                # Schedule changes are already in updated; otherwise the other channel's schedule is copied.
                schedule_fields = {
                    k: source[k]
                    for k in ("schedule_type", "schedule_hour", "schedule_day", "schedule_frame")
                    if k in source
                }
                updated = {**_pulse_channel(*_schedule({}), *_recipients(recipients)), **schedule_fields, **updated}
            body["channels"] = others + ([updated] if updated else [])
        pulse = await _api(context, "PUT", path, json=body) or {}
        return _subscription_summary(pulse)


@metabase.action("list_users")
class ListUsersAction(ActionHandler):
    """List Metabase users (to pick alert and subscription recipients). Needs an admin API key on most setups."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        page = _page(inputs)
        query = str(inputs.get("query") or "").strip() or None
        data = await _api(context, "GET", _with_query("/user", [("query", query), *page.items()]))
        users = [
            {
                "id": u.get("id"),
                "name": u.get("common_name"),
                "email": u.get("email"),
                "is_active": bool(u.get("is_active", True)),
            }
            for u in _list_data(data)
        ]
        return _paged("users", users, data, page)


# ---- Data descriptions ----


@metabase.action("update_table")
class UpdateTableAction(ActionHandler):
    """Change a table's display name or description in Metabase (not in the database)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional({}, display_name=inputs.get("display_name"), description=inputs.get("description"))
        if not body:
            raise ValueError("Give display_name or description.")
        table = await _api(context, "PUT", f"/table/{_path_id(inputs['table_id'])}", json=body) or {}
        return _table_summary(table, include_fields=False)


@metabase.action("update_field")
class UpdateFieldAction(ActionHandler):
    """Change a column's display name, description or semantic type in Metabase (not in the database)."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {},
            display_name=inputs.get("display_name"),
            description=inputs.get("description"),
            semantic_type=inputs.get("semantic_type"),
        )
        if not body:
            raise ValueError("Give display_name, description or semantic_type.")
        path = f"/field/{_path_id(inputs['field_id'])}"
        # Metabase 0.49 clears a column's conversion (e.g. UNIX seconds shown as a date) when it isn't sent. It is read
        # with the edit permission, so someone who can edit the data model but not query the table isn't refused.
        editable = _with_query(path, [("include_editable_data_model", "true")])
        coercion = (await _api(context, "GET", editable) or {}).get("coercion_strategy")
        if coercion:
            body["coercion_strategy"] = coercion
        field = await _api(context, "PUT", path, json=body) or {}
        return _field_summary(field)


@metabase.action("sync_database")
class SyncDatabaseAction(ActionHandler):
    """Ask Metabase to pick up new or changed tables and columns in a database. Runs in the background."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _api(context, "POST", f"/database/{_path_id(inputs['database_id'])}/sync_schema")
        return {"database_id": inputs["database_id"], "started": True}


@metabase.action("rescan_field_values")
class RescanFieldValuesAction(ActionHandler):
    """Ask Metabase to refresh the values it lists in filter dropdowns for a database. Runs in the background."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        await _api(context, "POST", f"/database/{_path_id(inputs['database_id'])}/rescan_values")
        return {"database_id": inputs["database_id"], "started": True}


# ---- Timelines ----


@metabase.action("list_timelines")
class ListTimelinesAction(ActionHandler):
    """List event timelines (markers shown on time-series charts) with their events."""

    @_handled()
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        collection_id = inputs.get("collection_id")
        # The per-collection timeline URL differs between versions, so all timelines are read and filtered here.
        params = [("include", "events"), ("archived", "true" if inputs.get("archived") else None)]
        timelines = [
            t
            for t in _list_data(await _api(context, "GET", _with_query("/timeline", params)))
            if collection_id is None or t.get("collection_id") == collection_id
        ]
        result = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "description": t.get("description"),
                "collection_id": t.get("collection_id"),
                "archived": bool(t.get("archived")),
                "events": [_timeline_event_summary(e) for e in t.get("events") or []],
            }
            for t in timelines
        ]
        return {"timelines": result, "count": len(result)}


@metabase.action("create_timeline")
class CreateTimelineAction(ActionHandler):
    """Create an event timeline in a collection."""

    @_handled(saved_check="list_timelines")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {"name": _required_text(inputs["name"], "name"), "icon": inputs.get("icon") or "star"},
            description=inputs.get("description"),
            collection_id=inputs.get("collection_id"),
        )
        timeline = await _api(context, "POST", "/timeline", json=body) or {}
        _require_id(timeline, "a timeline")
        return {
            "id": timeline.get("id"),
            "name": timeline.get("name"),
            "collection_id": timeline.get("collection_id"),
        }


@metabase.action("create_timeline_event")
class CreateTimelineEventAction(ActionHandler):
    """Add an event (a release, campaign or incident) to a timeline, shown as a marker on time-series charts."""

    @_handled(saved_check="list_timelines")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {
                "timeline_id": inputs["timeline_id"],
                "name": _required_text(inputs["name"], "name"),
                "timestamp": _required_text(inputs["timestamp"], "timestamp"),
                "timezone": inputs.get("timezone") or "UTC",
                "time_matters": bool(inputs.get("time_matters", False)),
                "icon": inputs.get("icon") or "star",
            },
            description=inputs.get("description"),
        )
        event = await _api(context, "POST", "/timeline-event", json=body) or {}
        _require_id(event, "an event")
        return _timeline_event_summary(event)


@metabase.action("update_timeline_event")
class UpdateTimelineEventAction(ActionHandler):
    """Change a timeline event's name, description, date or time."""

    @_handled(saved_check="list_timelines")
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        body = _with_optional(
            {},
            name=inputs.get("name"),
            description=inputs.get("description"),
            timestamp=inputs.get("timestamp"),
            timezone=inputs.get("timezone"),
            time_matters=inputs.get("time_matters"),
        )
        if not body:
            raise ValueError("Give at least one change.")
        event = await _api(context, "PUT", f"/timeline-event/{_path_id(inputs['event_id'])}", json=body) or {}
        return _timeline_event_summary(event)
