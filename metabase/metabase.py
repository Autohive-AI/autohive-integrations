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
READ_ONLY_SQL_KEYWORDS = ("select", "with", "explain", "show", "describe", "desc", "values")
# Databases disagree on quoting and comments (backslash escapes, $$ quotes, [brackets], # and --1 in MySQL,
# /*! */ code), so every check below reads the raw SQL. A semicolon or write word inside a quoted value or a
# comment is refused too; that only refuses more, never less.
# Words that start a statement which changes data, schema, settings, sessions or the server. SQL Server runs a
# second statement without a semicolon (SELECT 1 SHUTDOWN), so these are refused anywhere, not just first.
STATEMENT_WORDS = (
    # Standard SQL and PostgreSQL/MySQL writes
    "insert update delete merge upsert drop create alter truncate rename grant revoke deny"
    " copy unload lock into vacuum reindex refresh optimize purge flush"
    # Procedures, sessions and transactions
    " exec execute call do set use declare begin commit rollback savepoint prepare discard notify listen unlisten"
    # SQL Server statements (Transact-SQL statement reference)
    " shutdown kill backup restore dbcc reconfigure checkpoint waitfor setuser revert enable disable"
    " updatetext writetext bulk raiserror openquery openrowset opendatasource"
    # SQLite, ClickHouse, Spark/Databricks, Oracle
    " attach detach pragma system msck uncache"
).split()
WRITE_KEYWORD = re.compile(
    r"\b(?:" + "|".join(STATEMENT_WORDS) + r")\b"
    # SQL Server stored procedures, Oracle packages, SQL Server Service Broker and key statements
    r"|\b(?:sp|xp|dbms|utl)_\w+|\bload\s+data\b|\bcache\s+(?:lazy\s+)?table\b"
    r"|\b(?:end|move|get)\s+conversation\b|\bsend\s+on\s+conversation\b|\breceive\s+(?:top\b|\*|\w+\s+from\b)"
    r"|\b(?:open|close)\s+(?:master|symmetric|all\s+symmetric)\s+keys?\b|\badd\s+(?:counter\s+)?signature\b"
    # Functions with side effects: sequences, sessions, locks, sleeps, server files, replication, remote
    # databases and URLs, and commands (ClickHouse executable, Spark reflect)
    r"|\b(?:setval|nextval|set_config|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_rotate_logfile\w*"
    r"|pg_promote|pg_switch_wal|pg_create_restore_point|pg_wal_replay_\w+|pg_notify|pg_(?:try_)?advisory\w*"
    r"|pg_file_\w+|pg_stat_reset\w*|pg_logical_\w+|pg_import_system_collations|pg_replication_\w+"
    r"|pg_\w*replication_slot\w*|lo_\w+|dblink\w*|get_lock|release_lock|release_all_locks|csvwrite|file_write"
    r"|link_schema|pg_sleep\w*|pg_read_file|pg_read_binary_file|pg_ls_\w+|pg_stat_file|pg_logdir_ls|sleep|benchmark"
    r"|load_file|file_read|url|urlcluster|s3|s3cluster|gcs|file|remote|remotesecure|hdfs|azureblobstorage\w*"
    r"|deltalake|iceberg\w*|hudi|input|jdbc|odbc|mysql|postgresql|mongodb|redis|sqlite|executable|reflect"
    r"|java_method|httpuritype)\s*\(",
    re.IGNORECASE,
)
# EXPLAIN ANALYZE runs the statement it explains.
EXPLAIN_ANALYZE = re.compile(r"\bexplain\s*(?:\([^)]*)?\banaly[sz]e\b", re.IGNORECASE)
# PostgreSQL nests block comments, so /* a /* b */ c */ could hide the real first word.
NESTED_BLOCK_COMMENT = re.compile(r"/\*(?:(?!\*/).)*?/\*", re.DOTALL)
LEADING_COMMENT = re.compile(r"\s*(?:--[^\r\n]*|#[^\r\n]*|/\*.*?\*/|\()", re.DOTALL)


def _ensure_read_only_sql(sql: str) -> str:
    """Refuse SQL that is not a single read statement. A keyword check, not a parser: a read-only database user in
    Metabase is what fully blocks writes."""
    text = sql
    while match := LEADING_COMMENT.match(text):
        text = text[match.end() :]
    first_word = re.match(r"\s*([A-Za-z]*)", text).group(1).lower()
    # A second statement after a semicolon could be anything, so only one statement is allowed.
    if (
        first_word not in READ_ONLY_SQL_KEYWORDS
        or ";" in sql.strip().rstrip(";")
        or WRITE_KEYWORD.search(sql)
        or EXPLAIN_ANALYZE.search(sql)
        or NESTED_BLOCK_COMMENT.search(sql)
    ):
        raise ValueError(
            "Only a single read-only SQL statement is allowed (SELECT, WITH, EXPLAIN, SHOW, DESCRIBE or VALUES). "
            "Semicolons and words such as INSERT, UPDATE, DELETE, INTO or CREATE are refused anywhere, even inside "
            "quotes or comments, so rephrase the query without them. "
            "Use a read-only database user in Metabase to fully block writes."
        )
    return sql


def _native_query(database_id: Any, sql: str) -> Dict[str, Any]:
    return {"database": database_id, "type": "native", "native": {"query": sql, "template-tags": {}}}


def _with_optional(body: Dict[str, Any], **values: Any) -> Dict[str, Any]:
    """Add optional fields to a request body, skipping ones that are missing or empty."""
    body.update({key: value for key, value in values.items() if value is not None and value != ""})
    return body


def _error_message(error: Exception) -> str:
    if isinstance(error, HTTPError):
        data = error.response_data
        detail = None
        if isinstance(data, dict):
            detail = data.get("error") or data.get("message") or data.get("errors")
        message = f"Metabase returned HTTP {error.status}: {detail or error.message}"
        return message[:MAX_ERROR_LENGTH]
    if isinstance(error, asyncio.TimeoutError):
        return "Metabase did not respond in time. For queries, aggregate or add a LIMIT and try again."
    return str(error)


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
    native = dataset_query.get("native") or {}
    sql = native.get("query")
    tags = native.get("template-tags")
    # MBQL 5 (Metabase 0.57+) stores native SQL and its template tags under stages[0].
    stages = dataset_query.get("stages") or []
    if sql is None and stages and isinstance(stages[0], dict) and isinstance(stages[0].get("native"), str):
        sql = stages[0]["native"]
        tags = stages[0].get("template-tags")
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
            return ActionResult(
                data={
                    "database_id": database.get("id"),
                    "database_name": database.get("name"),
                    "engine": database.get("engine"),
                    "tables": tables,
                    "count": len(tables),
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
            params: List[tuple] = [("q", str(inputs.get("query") or "").strip() or None)]
            params += [("models", m) for m in inputs.get("models") or []]
            if inputs.get("archived"):
                params.append(("archived", "true"))
            params += list(page.items())

            data = await _api(context, "GET", _with_query("/search", params))
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
            return ActionResult(data=_paged("results", results, data, page), cost_usd=0.0)
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
            params: List[tuple] = [("models", m) for m in inputs.get("models") or []]
            params += list(page.items())

            data = await _api(context, "GET", _with_query(f"/collection/{collection_id}/items", params))
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
            return ActionResult(data=_paged("items", items, data, page), cost_usd=0.0)
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
            return ActionError(message=_error_message(e))


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
                # Metabase 0.64+ refuses any other key, such as the widget_type and required that get_question lists.
                body["parameters"] = [
                    {k: v for k, v in p.items() if k in RUN_PARAMETER_KEYS} if isinstance(p, dict) else p
                    for p in inputs["parameters"]
                ]

            data = await _api(context, "POST", f"/card/{card_id}/query", json=body, timeout=QUERY_TIMEOUT_SECONDS)
            return ActionResult(data=_query_result(data, max_rows), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e))


@metabase.action("run_sql_query")
class RunSqlQueryAction(ActionHandler):
    """Run a native SQL query against a Metabase database and return its rows."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            sql = _ensure_read_only_sql(_required_text(inputs["sql"], "sql"))
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
            sql = _ensure_read_only_sql(_required_text(inputs["sql"], "sql"))
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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))


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
            return ActionError(message=_error_message(e))
