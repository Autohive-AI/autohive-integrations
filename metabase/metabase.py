from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    HTTPError,
)
import asyncio
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
    return response.data


def _required_text(value: Any, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{key} is required")
    return text


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
    # argument JSON-encodes lists, so build the query string here instead.
    params = [(k, v) for k, v in params if v is not None]
    return f"{url}?{urlencode(params)}" if params else url


def _unique_names(cols: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    seen: Dict[str, int] = {}
    for index, col in enumerate(cols):
        name = str(col.get("name") or col.get("display_name") or f"column_{index + 1}")
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
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


def _card_summary(card: Dict[str, Any]) -> Dict[str, Any]:
    dataset_query = card.get("dataset_query") or {}
    native = dataset_query.get("native") or {}
    sql = native.get("query")
    # MBQL 5 (Metabase 0.57+) stores native SQL under stages[0].native.
    if sql is None:
        stages = dataset_query.get("stages") or []
        if stages and isinstance(stages[0], dict) and isinstance(stages[0].get("native"), str):
            sql = stages[0]["native"]
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
        "parameters": card.get("parameters") or [],
    }


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

            data = await _api(
                context,
                "GET",
                f"/database/{database_id}/metadata",
                params={"skip_fields": "false" if include_fields else "true"},
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
            data = await _api(
                context,
                "GET",
                "/collection",
                params={"archived": "true" if inputs.get("archived") else "false"},
            )
            include_personal = bool(inputs.get("include_personal", False))
            collections = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "parent_id": c.get("parent_id"),
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
                body["parameters"] = inputs["parameters"]

            data = await _api(context, "POST", f"/card/{card_id}/query", json=body, timeout=QUERY_TIMEOUT_SECONDS)
            return ActionResult(data=_query_result(data, max_rows), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=_error_message(e))


@metabase.action("run_sql_query")
class RunSqlQueryAction(ActionHandler):
    """Run a native SQL query against a Metabase database and return its rows."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            sql = _required_text(inputs["sql"], "sql")
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
            sql = _required_text(inputs["sql"], "sql")
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
