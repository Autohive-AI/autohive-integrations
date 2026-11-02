from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    HTTPError,
)
import asyncio
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urlparse

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
    return {"x-api-key": get_api_key(context), "Content-Type": "application/json"}


def _path_id(value: Any) -> str:
    return quote(str(value), safe="")


async def _api(context: ExecutionContext, method: str, path: str, **kwargs: Any) -> Any:
    if method != "GET":
        kwargs.setdefault("retry_count", NO_RETRY)
    response = await context.fetch(
        f"{get_base_url(context)}/api{path}",
        method=method,
        headers=get_auth_headers(context),
        **kwargs,
    )
    # Metabase always answers with JSON; HTML or an empty body means the URL points somewhere else, such as a
    # login proxy or the wrong path.
    if not isinstance(response.data, (dict, list)):
        raise ValueError("Metabase returned a response that isn't JSON. Check the Metabase URL.")
    return response.data


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
    r"|openquery|openrowset|opendatasource|query|query_to_xml\w*|ts_stat|ts_rewrite"
    r"|(?:url|s3|gcs|file|hdfs|deltalake|hudi)(?:cluster)?|remote|remotesecure|azureblobstorage\w*|iceberg\w*"
    r"|arrowflight|input|jdbc|odbc|mysql|postgresql|mongodb|redis|sqlite|executable|reflect|try_reflect|java_method"
    r"|httpuritype|glob|parquet_\w+|sniff_csv|delta_scan|(?:sqlite|postgres|mysql)_(?:scan|query|execute|attach)\w*|st_read\w*",
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
# Template tags in saved SQL: {{name}} and optional [[ ... ]] clauses, which Metabase drops when their filter is
# empty, so SQL is checked with them kept and with them dropped. Metabase passes filter values as values, never as
# SQL, so a tag is checked as a stand-in of the same kind.
TEMPLATE_TAG = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)
OPTIONAL_CLAUSE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
TAG_STAND_INS = {"dimension": "1 = 1", "table": "metabase_table", "card": "(SELECT 1)", "number": "1"}
# Saved questions can be built on other saved questions; how deep to follow them before refusing.
MAX_SAVED_QUESTION_DEPTH = 5


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


def _query_sources(dataset_query: Any) -> tuple:
    """What a question is built on, including its joins: saved questions (source-table "card__12" or MBQL 5
    source-card) and SQL written into it (top-level or as a source-query)."""
    cards: List[Any] = []
    statements: List[tuple] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
        if not isinstance(value, dict):
            return
        if found := _native_sql(value):
            statements.append(found)
        for key, item in value.items():
            if key in ("source-card", "source_card") and item is not None:
                cards.append(item)
            elif key in ("source-table", "source_table") and isinstance(item, str):
                if match := re.fullmatch(r"card__(\d+)", item):
                    cards.append(int(match.group(1)))
            elif key != "native":
                walk(item)

    walk(dataset_query)
    return cards, statements


def _sql_variants(sql: str) -> List[str]:
    """Saved SQL as it runs with every optional [[ ... ]] clause kept, and with every one dropped."""
    return list(dict.fromkeys([OPTIONAL_CLAUSE.sub(r"\1", sql), OPTIONAL_CLAUSE.sub("", sql)]))


class _SavedQuestionCheck:
    """Refuses to run a saved question whose SQL, or the SQL of anything it is built on, writes. Saved SQL is checked
    the way run_sql_query checks SQL, with each template tag replaced by a stand-in. Each question, database and
    snippet is fetched once per run."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.checked: set = set()
        self.engines: Dict[str, Optional[str]] = {}
        self.snippets_by_id: Dict[str, Dict[str, Any]] = {}
        self.snippets_by_name: Optional[Dict[str, Dict[str, Any]]] = None

    async def check(self, card_id: Any, depth: int = 0) -> None:
        key = str(card_id)
        if key in self.checked:
            return
        if depth > MAX_SAVED_QUESTION_DEPTH:
            raise ValueError(
                "This saved question is built on too many other saved questions to check, so it wasn't run."
            )
        # Marked before its sources are checked, so questions built on each other are each fetched once.
        self.checked.add(key)
        card = await _api(self.context, "GET", f"/card/{_path_id(card_id)}") or {}
        dataset_query = card.get("dataset_query") or {}
        sources, statements = _query_sources(dataset_query)
        for source in sources:
            await self.check(source, depth + 1)
        if statements:
            engine = await self._engine(card.get("database_id") or dataset_query.get("database"))
            for sql, tags in statements:
                for variant in _sql_variants(sql):
                    expanded = await self._expand(variant, tags, depth)
                    try:
                        _ensure_read_only_sql(expanded, engine)
                    except ValueError as e:
                        raise ValueError(f"Saved question {card.get('id', card_id)} wasn't run. {e}") from None

    async def _engine(self, database_id: Any) -> Optional[str]:
        key = str(database_id)
        if key not in self.engines:
            self.engines[key] = await _database_engine(self.context, database_id)
        return self.engines[key]

    async def _snippet(self, name: str, tag: Dict[str, Any]) -> str:
        """A snippet's SQL, found by its id or, when the tag stores only a name, by its name."""
        snippet_id = tag.get("snippet-id")
        if snippet_id is not None:
            key = str(snippet_id)
            if key not in self.snippets_by_id:
                path = f"/native-query-snippet/{_path_id(snippet_id)}"
                self.snippets_by_id[key] = await _api(self.context, "GET", path) or {}
            snippet = self.snippets_by_id[key]
        else:
            if self.snippets_by_name is None:
                # Archived snippets still run in the questions that use them.
                listed = _list_data(await _api(self.context, "GET", "/native-query-snippet"))
                listed += _list_data(await _api(self.context, "GET", "/native-query-snippet?archived=true"))
                self.snippets_by_name = {item.get("name"): item for item in listed}
            snippet = self.snippets_by_name.get(tag.get("snippet-name") or name.split(":", 1)[-1].strip())
            if snippet is None:
                raise ValueError(f"Snippet {name} in a saved question can't be found, so the question wasn't run.")
        content = snippet.get("content") or ""
        if TEMPLATE_TAG.search(content) or "[[" in content:
            raise ValueError(f"Snippet {name} uses filters, so the saved question can't be checked and wasn't run.")
        return content

    async def _expand(self, sql: str, tags: Dict[str, Any], depth: int) -> str:
        pieces: List[str] = []
        end = 0
        for match in TEMPLATE_TAG.finditer(sql):
            name = match.group(1)
            tag = tags.get(name) or {}
            kind = tag.get("type")
            if kind == "snippet" or name.lower().startswith("snippet:"):
                stand_in = await self._snippet(name, tag)
            elif kind == "card" or name.startswith("#"):
                reference = re.match(r"#(\d+)", name)
                card_id = tag.get("card-id") or (reference and reference.group(1))
                if card_id is None:
                    raise ValueError(f"{name} in a saved question can't be checked, so the question wasn't run.")
                await self.check(card_id, depth + 1)
                stand_in = TAG_STAND_INS["card"]
            elif name in tags:
                stand_in = TAG_STAND_INS.get(kind, "NULL")
            else:
                # Not a filter the question defines, so where Metabase's {{ }} starts and ends can't be trusted.
                raise ValueError(f"{{{{{name[:40]}}}}} isn't one of the saved question's filters, so it wasn't run.")
            pieces += [sql[end : match.start()], stand_in]
            end = match.end()
        return "".join(pieces) + sql[end:]


def _native_query(database_id: Any, sql: str) -> Dict[str, Any]:
    return {"database": database_id, "type": "native", "native": {"query": sql, "template-tags": {}}}


def _with_optional(body: Dict[str, Any], **values: Any) -> Dict[str, Any]:
    """Add optional fields to a request body, skipping ones that are missing or empty."""
    body.update({key: value for key, value in values.items() if value is not None and value != ""})
    return body


def _error_message(error: Exception, saved_check: Optional[str] = None) -> str:
    """saved_check names how to look for a create that may have been saved before the response timed out."""
    if isinstance(error, HTTPError):
        data = error.response_data
        detail = None
        if isinstance(data, dict):
            detail = data.get("error") or data.get("message") or data.get("errors")
        message = f"Metabase returned HTTP {error.status}: {detail or error.message}"
        return message[:MAX_ERROR_LENGTH]
    if isinstance(error, asyncio.TimeoutError):
        if saved_check:
            return (
                "Metabase did not respond in time, but it may still have saved the change. "
                f"Check with {saved_check} before trying again, so it isn't created twice."
            )
        return "Metabase did not respond in time. For queries, aggregate or add a LIMIT and try again."
    return str(error)


# Item types older Metabase versions reject outright (HTTP 400 for the whole request): minimum 0.x minor version.
MODELS_SINCE = {"metric": 51, "document": 57}


async def _supported_models(context: ExecutionContext, models: Any) -> tuple:
    """Drop item types this Metabase is too old for, and say which were dropped."""
    models = list(models or [])
    if not any(m in MODELS_SINCE for m in models):
        return models, []
    properties = await _api(context, "GET", "/session/properties") or {}
    tag = str((properties.get("version") or {}).get("tag") or "")
    match = re.match(r"v?\d+\.(\d+)", tag)
    if not match:
        return models, []
    minor = int(match.group(1))
    dropped = [m for m in models if minor < MODELS_SINCE.get(m, 0)]
    return [m for m in models if m not in dropped], dropped


def _note_dropped(result: Dict[str, Any], dropped: List[str]) -> Dict[str, Any]:
    if dropped:
        result["note"] = f"This Metabase version doesn't support {', '.join(dropped)}, so they were left out."
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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


# ---- Search and collections ----


@metabase.action("search")
class SearchAction(ActionHandler):
    """Search questions, models, metrics, dashboards, collections, tables and databases."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page = _page(inputs)
            models, dropped = await _supported_models(context, inputs.get("models"))
            params: List[tuple] = [("q", str(inputs.get("query") or "").strip() or None)]
            params += [("models", m) for m in models]
            if inputs.get("archived"):
                params.append(("archived", "true"))
            params += list(page.items())

            # Every asked-for type is too new for this Metabase: nothing to search for.
            data = await _api(context, "GET", _with_query("/search", params)) if models or not dropped else []
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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


@metabase.action("list_collection_items")
class ListCollectionItemsAction(ActionHandler):
    """List the questions, dashboards and sub-collections inside a collection."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            collection_id = _path_id(inputs.get("collection_id") or "root")
            page = _page(inputs)
            models, dropped = await _supported_models(context, inputs.get("models"))
            params: List[tuple] = [("models", m) for m in models]
            params += list(page.items())

            path = _with_query(f"/collection/{collection_id}/items", params)
            data = await _api(context, "GET", path) if models or not dropped else []
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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e, saved_check="list_collections"))


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
            return ActionError(message=_error_message(e))


@metabase.action("run_question")
class RunQuestionAction(ActionHandler):
    """Run a saved question and return its rows."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            card_id = _path_id(inputs["question_id"])
            max_rows = _clamp(inputs.get("max_rows"), DEFAULT_MAX_ROWS, MAX_ROWS_LIMIT)
            body: Dict[str, Any] = {}
            if inputs.get("parameters"):
                body["parameters"] = [_run_parameter(p) for p in inputs["parameters"]]
            await _SavedQuestionCheck(context).check(card_id)

            data = await _api(context, "POST", f"/card/{card_id}/query", json=body, timeout=QUERY_TIMEOUT_SECONDS)
            return ActionResult(data=_query_result(data, max_rows), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e, saved_check="search"))


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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e, saved_check="search"))


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
            return ActionError(message=_error_message(e, saved_check="get_dashboard"))
