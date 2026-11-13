import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autohive_integrations_sdk import ExecutionContext, HTTPError, ResultType

from metabase.metabase import NO_RETRY, metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


def _database(engine="postgres"):
    return _ok({"id": 3, "name": "Warehouse", "engine": engine})


def _dataset(rows, cols=("a",), status="completed"):
    return {"status": status, "row_count": len(rows), "data": {"cols": [{"name": c} for c in cols], "rows": rows}}


SAMPLE_CARD = {
    "id": 42,
    "name": "Weekly signups",
    "description": None,
    "type": "question",
    "display": "line",
    "database_id": 3,
    "query_type": "native",
    "collection_id": 4,
    "collection": {"id": 4, "name": "Growth", "slug": "growth"},
    "archived": False,
    "parameters": [{"id": "p1", "slug": "region", "type": "category"}],
    "dataset_query": {"database": 3, "type": "native", "native": {"query": "select 1"}},
}


class TestGetQuestion:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        result = await metabase.execute_action("get_question", {"question_id": 42}, mock_context)
        data = result.result.data
        assert data["native_sql"] == "select 1"
        assert data["collection"] == {"id": 4, "name": "Growth"}
        assert data["parameters"][0]["slug"] == "region"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        await metabase.execute_action("get_question", {"question_id": 42}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/card/42"
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("get_question", {"question_id": 1}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_string_id_rejected(self, mock_context):
        result = await metabase.execute_action("get_question", {"question_id": "42"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR


SAVED_NATIVE = {
    "id": 42,
    "database_id": 3,
    "dataset_query": {"database": 3, "type": "native", "native": {"query": "q"}},
}


NO_NATIVE_PERMISSION = HTTPError(403, "Forbidden", "You don't have permissions to do that.")


def _route(mock_context, card=None, sql="select 1", engine="postgres", result=None, compiled=None):
    """Answer run_question's requests: the question, Metabase's expanded SQL, the database, then the run."""

    async def fetch(url, method="GET", **kwargs):
        if url.endswith("/api/dataset/native"):
            if isinstance(compiled, Exception):
                raise compiled
            return _ok(compiled if compiled is not None else {"query": sql, "params": None})
        if url.endswith("/query"):
            return _ok(result if result is not None else _dataset([[1]]), status=202)
        if "/api/card/" in url:
            return _ok(card or SAVED_NATIVE)
        if "/api/database/" in url:
            return _database(engine)
        raise AssertionError(url)

    mock_context.fetch.side_effect = fetch


class TestRunQuestion:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        _route(mock_context, result=_dataset([[1, "EU"], [2, "US"]], cols=("n", "region")))
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"n": 1, "region": "EU"}, {"n": 2, "region": "US"}]
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_request_with_parameters(self, mock_context):
        _route(mock_context, result=_dataset([]))
        params = [{"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "EU"}]
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": params}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card/42/query"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"parameters": params}
        assert call.kwargs["timeout"] == 120

    @pytest.mark.asyncio
    async def test_parameters_copied_from_get_question_are_trimmed(self, mock_context):
        # Metabase 0.64+ rejects keys outside its parameter-with-value schema with HTTP 400.
        target = ["variable", ["template-tag", "region"]]
        copied = {
            "id": "p1",
            "slug": "region",
            "name": "Region",
            "type": "category",
            "widget_type": None,
            "required": False,
            "default": None,
            "target": target,
            "value": "EU",
        }
        _route(mock_context, result=_dataset([[1]]))
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": [copied]}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "parameters": [
                {
                    "id": "p1",
                    "slug": "region",
                    "type": "category",
                    "default": None,
                    "target": target,
                    "value": "EU",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_name_kept_without_template_tag_target(self, mock_context):
        # Without a template-tag target Metabase can only match the filter by its name.
        param = {"id": "p1", "name": "region", "type": "category", "value": "EU"}
        _route(mock_context, result=_dataset([[1]]))
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": [param]}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"parameters": [param]}

    @pytest.mark.asyncio
    async def test_no_parameters_sends_empty_body(self, mock_context):
        _route(mock_context, result=_dataset([]))
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {}

    @pytest.mark.asyncio
    async def test_metabase_expands_the_sql_that_is_checked(self, mock_context):
        params = [{"id": "p1", "type": "category", "target": ["variable", ["template-tag", "region"]], "value": "EU"}]
        _route(mock_context)
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": params}, mock_context)
        calls = [(c.args[0], c.kwargs.get("method")) for c in mock_context.fetch.call_args_list]
        assert calls == [
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card/42/query", "POST"),
        ]
        compile_body = mock_context.fetch.call_args_list[2].kwargs["json"]
        assert compile_body == {**SAVED_NATIVE["dataset_query"], "parameters": params, "pretty": False}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sql",
        [
            "delete from orders",
            "with x as (delete from orders returning *) select * from x",
            "select nextval('s')",
            # Metabase leaves {{ }} inside comments alone, so the comment closes early and the DELETE runs.
            "SELECT 1 /* {{*/ ; DELETE FROM users; --}} */",
        ],
    )
    async def test_expanded_sql_that_writes_is_not_run(self, mock_context, sql):
        _route(mock_context, sql=sql)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert not any(c.args[0].endswith("/card/42/query") for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_checked_in_the_database_dialect(self, mock_context):
        _route(mock_context, sql="SELECT TOP 10 [order id] FROM dbo.orders WITH (NOLOCK)", engine="sqlserver")
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_card_filter_defaults_sent_to_both_the_check_and_the_run(self, mock_context):
        # The checked SQL and the run use the same values, so an optional clause can't be in one and not the other.
        target = ["variable", ["template-tag", "region"]]
        card = {**SAVED_NATIVE, "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}]}
        _route(mock_context, card=card)
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        expected = [{"id": "p1", "type": "category", "target": target, "value": "EU"}]
        assert mock_context.fetch.call_args_list[2].kwargs["json"]["parameters"] == expected
        assert mock_context.fetch.call_args.kwargs["json"] == {"parameters": expected}

    @pytest.mark.asyncio
    async def test_supplied_value_beats_the_card_default(self, mock_context):
        target = ["variable", ["template-tag", "region"]]
        card = {**SAVED_NATIVE, "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}]}
        params = [{"id": "p1", "type": "category", "target": target, "value": "US"}]
        _route(mock_context, card=card)
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": params}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"parameters": params}

    @pytest.mark.asyncio
    async def test_value_sent_by_target_beats_the_card_default(self, mock_context):
        target = ["variable", ["template-tag", "region"]]
        card = {**SAVED_NATIVE, "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}]}
        params = [{"type": "category", "target": target, "value": "US"}]
        _route(mock_context, card=card)
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": params}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"parameters": params}

    @pytest.mark.asyncio
    async def test_point_and_click_question_checked_through_its_sql(self, mock_context):
        gui = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "type": "query", "query": {"source-table": 5}},
        }
        _route(mock_context, card=gui, sql='SELECT "t"."a" FROM "t" LIMIT 2000')
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        assert mock_context.fetch.call_args_list[2].kwargs["json"]["query"] == {"source-table": 5}

    @pytest.mark.asyncio
    async def test_no_sql_back_is_not_run(self, mock_context):
        _route(mock_context, compiled={"query": {"collection": "orders", "query": []}})
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "didn't return SQL" in result.result.message
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_expansion_error_is_not_run(self, mock_context):
        _route(mock_context, compiled=HTTPError(400, "Bad Request", response_data={"message": "missing required"}))
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_expansion_without_a_query_is_not_run(self, mock_context):
        _route(mock_context, compiled={"params": None})
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "didn't return SQL" in result.result.message
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_without_native_permission_plain_saved_sql_is_checked_as_saved(self, mock_context):
        # Groups that can run saved questions but not write SQL can't expand them, so plain SQL is checked as saved.
        sql = "select * from orders"
        card = {**SAVED_NATIVE, "dataset_query": {"database": 3, "type": "native", "native": {"query": sql}}}
        _route(mock_context, card=card, compiled=NO_NATIVE_PERMISSION)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_without_native_permission_saved_sql_that_writes_is_not_run(self, mock_context):
        card = {**SAVED_NATIVE, "dataset_query": {"database": 3, "type": "native", "native": {"query": "drop table t"}}}
        _route(mock_context, card=card, compiled=NO_NATIVE_PERMISSION)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "Saved question 42 wasn't run" in result.result.message
        assert not any(c.args[0].endswith("/card/42/query") for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dataset_query",
        [
            {"database": 3, "type": "native", "native": {"query": "select * from t where {{region}}"}},
            {"database": 3, "type": "native", "native": {"query": "select 1 [[and {{x}}]]"}},
            {"database": 3, "type": "query", "query": {"source-table": "card__7"}},
            {"database": 3, "stages": [{"lib/type": "mbql.stage/mbql", "source-card": 7}]},
            {"database": 3, "type": "query", "query": {"source-query": {"native": "delete from t"}}},
        ],
    )
    async def test_without_native_permission_unknown_sql_is_not_run(self, mock_context, dataset_query):
        _route(mock_context, card={**SAVED_NATIVE, "dataset_query": dataset_query}, compiled=NO_NATIVE_PERMISSION)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "can write native queries" in result.result.message
        assert not any(c.args[0].endswith("/card/42/query") for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_without_native_permission_point_and_click_question_runs(self, mock_context):
        gui = {**SAVED_NATIVE, "dataset_query": {"database": 3, "type": "query", "query": {"source-table": 5}}}
        _route(mock_context, card=gui, compiled=NO_NATIVE_PERMISSION)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query",
        [
            [{"$match": {"status": "open"}}, {"$limit": 5}],
            '[{"$group": {"_id": "$region", "n": {"$sum": 1}}}]',
            '[{"$group": {"_id": null, "n": {"$sum": "$out"}}}]',
            '[{"$project": {"example": {"$literal": {"$out": "orders_copy"}}}}]',
        ],
    )
    async def test_mongodb_pipeline_runs(self, mock_context, query):
        _route(mock_context, engine="mongo", compiled={"query": query, "collection": "orders"})
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query",
        [
            [{"$match": {}}, {"$out": "orders_copy"}],
            '[{"$merge": {"into": "orders"}}]',
            "[{$out: 'x'}]",
            '[{"$\\u006fut": "backup"}]',
            '[{"\\u0024out": "orders_copy"}]',
            "[{'\\u0024out': 'x'}]",
        ],
    )
    async def test_mongodb_pipeline_that_writes_is_not_run(self, mock_context, query):
        _route(mock_context, engine="mongo", compiled={"query": query, "collection": "orders"})
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "$out and $merge" in result.result.message
        assert not any(c.args[0].endswith("/card/42/query") for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_mongodb_saved_without_native_permission_is_checked_as_saved(self, mock_context):
        native = {"query": '[{"$out": "x"}]', "collection": "orders"}
        card = {**SAVED_NATIVE, "dataset_query": {"database": 3, "type": "native", "native": native}}
        _route(mock_context, card=card, engine="mongo", compiled=NO_NATIVE_PERMISSION)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "$out and $merge" in result.result.message

    @pytest.mark.asyncio
    async def test_max_rows(self, mock_context):
        _route(mock_context, result=_dataset([[i] for i in range(10)]))
        result = await metabase.execute_action("run_question", {"question_id": 42, "max_rows": 3}, mock_context)
        assert result.result.data["row_count"] == 3
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_default_max_rows_100(self, mock_context):
        _route(mock_context, result=_dataset([[i] for i in range(150)]))
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["row_count"] == 100
        assert result.result.data["total_row_count"] == 150

    @pytest.mark.asyncio
    async def test_failed_query(self, mock_context):
        _route(mock_context, result={"status": "failed", "error": "column x does not exist"})
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "column x does not exist" in result.result.message


class TestRunSqlQuery:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            _database(),
            _ok(
                {
                    "status": "completed",
                    "data": {
                        "cols": [
                            {"name": "a", "display_name": "a", "base_type": "type/Integer"},
                            {"name": "b", "display_name": "b", "base_type": "type/Text"},
                        ],
                        "rows": [[1, "x"]],
                    },
                },
                status=202,
            ),
        ]
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select 1 as a, 'x' as b"}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["rows"] == [{"a": 1, "b": "x"}]
        assert result.result.data["columns"][1]["base_type"] == "type/Text"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok(_dataset([]), status=202)]
        await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "  select 1  "}, mock_context)
        lookup, call = mock_context.fetch.call_args_list
        # The database's engine picks the SQL dialect the check reads the query in.
        assert lookup.args[0] == f"{BASE}/api/database/3"
        assert lookup.kwargs["method"] == "GET"
        assert call.args[0] == f"{BASE}/api/dataset"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["headers"]["x-api-key"] == "mb_test_api_key"
        assert call.kwargs["json"] == {
            "database": 3,
            "type": "native",
            "native": {"query": "select 1", "template-tags": {}},
        }
        assert call.kwargs["timeout"] == 120

    @pytest.mark.asyncio
    async def test_failed_query_http_400(self, mock_context):
        mock_context.fetch.side_effect = [
            _database(),
            HTTPError(400, "raw", {"status": "failed", "error": 'ERROR: relation "nope" does not exist'}),
        ]
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select * from nope"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert 'relation "nope" does not exist' in result.result.message

    @pytest.mark.asyncio
    async def test_write_sql_never_sent(self, mock_context):
        mock_context.fetch.side_effect = [_database()]
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "delete from users"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Only a single read statement" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sql",
        [
            "WITH removed AS (DELETE FROM users RETURNING *) SELECT * FROM removed",
            "SELECT * INTO backup FROM users",
            "select 1 SHUTDOWN",
            "SELECT 1 DELETE t",
        ],
    )
    async def test_write_inside_a_read_never_sent(self, mock_context, sql):
        mock_context.fetch.side_effect = [_database("sqlserver")]
        result = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": sql}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_sql_read_in_the_database_dialect(self, mock_context):
        # MySQL quotes names with backticks, so this is one statement there; PostgreSQL can't read it.
        sql = "select `a; drop table t` from t"
        mock_context.fetch.side_effect = [_database("mysql"), _ok(_dataset([["x"]], cols=("x",)), status=202)]
        mysql = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": sql}, mock_context)
        assert mysql.type == ResultType.ACTION
        mock_context.fetch.side_effect = [_database("postgres")]
        postgres = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": sql}, mock_context)
        assert postgres.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_database_lookup_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("run_sql_query", {"database_id": 99, "sql": "select 1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_create_question_rejects_write_sql(self, mock_context):
        mock_context.fetch.side_effect = [_database()]
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "drop table users"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_blank_sql(self, mock_context):
        result = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "   "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_rows_capped_at_2000(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok(_dataset([[i] for i in range(2000)]), status=202)]
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select 1", "max_rows": 2000}, mock_context
        )
        assert result.result.data["row_count"] == 2000
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_max_rows_over_limit_rejected(self, mock_context):
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select 1", "max_rows": 5000}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_missing_sql(self, mock_context):
        result = await metabase.execute_action("run_sql_query", {"database_id": 3}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR


class TestCreateQuestion:
    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_database(), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "create_question", {"name": "New", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert "may still have saved" in result.result.message
        assert "Check with search" in result.result.message

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({**SAMPLE_CARD, "id": 77, "name": "New"})]
        result = await metabase.execute_action(
            "create_question",
            {
                "name": "New",
                "database_id": 3,
                "sql": "select 1",
                "display": "bar",
                "description": "d",
                "collection_id": 4,
            },
            mock_context,
        )
        assert result.result.data["id"] == 77
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "name": "New",
            "type": "question",
            "display": "bar",
            "visualization_settings": {},
            "dataset_query": {"database": 3, "type": "native", "native": {"query": "select 1", "template-tags": {}}},
            "description": "d",
            "collection_id": 4,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("extra", [{}, {"description": ""}])
    async def test_defaults(self, mock_context, extra):
        mock_context.fetch.side_effect = [_database(), _ok({"id": 78, "name": "N"})]
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1", **extra}, mock_context
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["display"] == "table"
        assert "collection_id" not in body
        assert "description" not in body

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action(
            "create_question", {"name": " ", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("display", ["sparkle", "pivot"])
    async def test_invalid_display(self, mock_context, display):
        # Metabase only builds pivot tables from query builder questions, not SQL.
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1", "display": display}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_permission_error(self, mock_context):
        mock_context.fetch.side_effect = [
            _database(),
            HTTPError(403, "x", {"message": "You don't have permissions to do that."}),
        ]
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"name": "N"})]
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "did not return a question id" in result.result.message

    @pytest.mark.asyncio
    async def test_mbql5_response_sql_returned(self, mock_context):
        mock_context.fetch.side_effect = [
            _database(),
            _ok(
                {
                    "id": 80,
                    "name": "N",
                    "database_id": 3,
                    "dataset_query": {"database": 3, "stages": [{"native": "select 1"}]},
                }
            ),
        ]
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.result.data["native_sql"] == "select 1"

    @pytest.mark.asyncio
    async def test_filters_saved_as_template_tags(self, mock_context):
        mock_context.fetch.side_effect = [
            _database(),
            _ok({"query": "select * from orders where region = 'x'", "params": None}),
            _ok({"id": 81, "name": "Orders by region"}),
        ]
        sql = "select * from orders where region = {{region}}"
        filters = [{"name": "region", "type": "text", "display_name": "Sales region", "default": "EU"}]
        result = await metabase.execute_action(
            "create_question",
            {"name": "Orders by region", "database_id": 3, "sql": sql, "filters": filters},
            mock_context,
        )
        assert result.type != ResultType.ACTION_ERROR
        calls = mock_context.fetch.call_args_list
        assert [(c.args[0], c.kwargs["method"]) for c in calls] == [
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card", "POST"),
        ]
        tags = calls[2].kwargs["json"]["dataset_query"]["native"]["template-tags"]
        tag = tags["region"]
        tag_id = tag.pop("id")
        assert isinstance(tag_id, str)
        assert tag == {
            "name": "region",
            "display-name": "Sales region",
            "type": "text",
            "required": False,
            "default": "EU",
        }
        # A filter with a default runs with it, so no stand-in is sent.
        assert calls[1].kwargs["json"]["parameters"] == []
        assert calls[1].kwargs["json"]["native"]["template-tags"] == tags

    @pytest.mark.asyncio
    async def test_stand_ins_for_filters_without_defaults(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"query": "select 1", "params": None}), _ok({"id": 82})]
        sql = "select * from orders where region = {{region}} and total > {{min_total}} and created_at > {{since}}"
        filters = [
            {"name": "region", "type": "text"},
            {"name": "min_total", "type": "number"},
            {"name": "since", "type": "date"},
        ]
        await metabase.execute_action(
            "create_question", {"name": "Big orders", "database_id": 3, "sql": sql, "filters": filters}, mock_context
        )
        assert mock_context.fetch.call_args_list[1].kwargs["json"]["parameters"] == [
            {"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "x"},
            {"type": "number/=", "target": ["variable", ["template-tag", "min_total"]], "value": 1},
            {"type": "date/single", "target": ["variable", ["template-tag", "since"]], "value": "2020-01-01"},
        ]
        tags = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"]
        assert [t["type"] for t in tags.values()] == ["text", "number", "date"]
        assert tags["min_total"]["display-name"] == "Min Total"

    @pytest.mark.asyncio
    async def test_field_filter(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"query": "select 1", "params": None}), _ok({"id": 83})]
        filters = [{"name": "state", "type": "field", "field_id": 56, "widget_type": "string/="}]
        await metabase.execute_action(
            "create_question",
            {"name": "Orders", "database_id": 3, "sql": "select * from orders where {{state}}", "filters": filters},
            mock_context,
        )
        # A field filter isn't a value in the SQL, so it gets no stand-in.
        assert mock_context.fetch.call_args_list[1].kwargs["json"]["parameters"] == []
        tag = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"]["state"]
        assert tag["type"] == "dimension"
        assert tag["dimension"] == ["field", 56, None]
        assert tag["widget-type"] == "string/="

    @pytest.mark.asyncio
    async def test_field_filter_needs_field_id(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {
                "name": "Orders",
                "database_id": 3,
                "sql": "select * from orders where {{state}}",
                "filters": [{"name": "state", "type": "field"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "needs field_id" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_required_filter_needs_default(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {
                "name": "Orders",
                "database_id": 3,
                "sql": "select * from orders where region = {{region}}",
                "filters": [{"name": "region", "required": True}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "needs a default" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unused_filter_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {"name": "Orders", "database_id": 3, "sql": "select 1", "filters": [{"name": "region"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't used in the SQL" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_commented_out_placeholders_are_not_filters(self, mock_context):
        sql = "select 1 /* where region = {{region}} */\n-- and {{country}}\n"
        mock_context.fetch.side_effect = [
            _database(),
            _ok({"query": "select 1", "params": None}),
            _ok({**SAMPLE_CARD, "id": 77, "name": "New"}),
        ]
        result = await metabase.execute_action(
            "create_question", {"name": "New", "database_id": 3, "sql": sql}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"] == {}

    @pytest.mark.asyncio
    async def test_filter_only_in_a_comment_is_unused(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {"name": "Orders", "database_id": 3, "sql": "select 1 -- {{region}}", "filters": [{"name": "region"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't used in the SQL" in result.result.message

    @pytest.mark.asyncio
    async def test_undefined_filter_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {"name": "Orders", "database_id": 3, "sql": "select * from orders where region = {{region}}"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "define it in filters" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_filter_type_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {
                "name": "Orders",
                "database_id": 3,
                "sql": "select * from orders where region = {{region}}",
                "filters": [{"name": "region", "type": "boolean"}],
            },
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_snippets_looked_up_once(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok([{"id": 7, "name": "totals"}, {"id": 8, "name": "active orders"}]),
            _database(),
            _ok({"query": "select 1", "params": None}),
            _ok({"id": 84, "name": "Totals"}),
        ]
        sql = "select {{snippet: totals}} from orders where {{snippet:active orders}}"
        result = await metabase.execute_action(
            "create_question", {"name": "Totals", "database_id": 3, "sql": sql}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == 84
        calls = mock_context.fetch.call_args_list
        assert calls[0].args[0] == f"{BASE}/api/native-query-snippet"
        assert sum(c.args[0].endswith("/native-query-snippet") for c in calls) == 1
        tags = calls[3].kwargs["json"]["dataset_query"]["native"]["template-tags"]
        assert tags["snippet: totals"]["type"] == "snippet"
        assert tags["snippet: totals"]["snippet-id"] == 7
        assert tags["snippet:active orders"]["snippet-name"] == "active orders"

    @pytest.mark.asyncio
    async def test_unknown_snippet_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok([{"id": 7, "name": "totals"}])]
        result = await metabase.execute_action(
            "create_question",
            {"name": "Totals", "database_id": 3, "sql": "select * from orders where {{snippet: other}}"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "no snippet named other" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ref", ["#12", "#12-active-users"])
    async def test_saved_question_reference(self, mock_context, ref):
        mock_context.fetch.side_effect = [_database(), _ok({"query": "select 1", "params": None}), _ok({"id": 85})]
        await metabase.execute_action(
            "create_question",
            {"name": "Active", "database_id": 3, "sql": f"select * from {{{{{ref}}}}} as u"},  # nosec B608 - test SQL
            mock_context,
        )
        tag = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"][ref]
        assert tag["type"] == "card"
        assert tag["card-id"] == 12

    @pytest.mark.asyncio
    async def test_expanded_write_refused(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"query": "select 1; delete from orders", "params": None})]
        result = await metabase.execute_action(
            "create_question",
            {"name": "Active", "database_id": 3, "sql": "select * from {{#12}} as u"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("Not saved.")
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_optional_clause_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_question",
            {
                "name": "Orders",
                "database_id": 3,
                "sql": "select * from orders where 1 = 1 [[and region = {{region}}]]",
                "filters": [{"name": "region"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "optional [[ ]] clauses" in result.result.message
        mock_context.fetch.assert_not_called()


class TestQueriesSentOnce:
    @pytest.mark.parametrize(
        "action, inputs",
        [
            ("run_sql_query", {"database_id": 3, "sql": "select 1"}),
            ("run_question", {"question_id": 42}),
        ],
    )
    @pytest.mark.asyncio
    async def test_query_not_retried(self, mock_context, action, inputs):
        if action == "run_question":
            _route(mock_context)
        else:
            mock_context.fetch.side_effect = [_database(), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action(action, inputs, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        assert mock_context.fetch.call_args.args[0].endswith("/query") or action == "run_sql_query"
        assert mock_context.fetch.call_args.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_create_question_not_retried(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"id": 1, "name": "N"})]
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_timed_out_query_sent_once_through_sdk(self, mock_context):
        context = ExecutionContext(auth=mock_context.auth)
        context._session = MagicMock()
        context._session.request.side_effect = asyncio.TimeoutError
        # The engine lookup is a GET; this test is about the query POST.
        engine = AsyncMock(return_value="select 1")
        with patch("asyncio.sleep") as sleep, patch("metabase.metabase._read_only_sql", engine):
            result = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "select 1"}, context)
        assert result.type == ResultType.ACTION_ERROR
        assert context._session.request.call_count == 1
        sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_question_keeps_retries(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        await metabase.execute_action("get_question", {"question_id": 42}, mock_context)
        assert "retry_count" not in mock_context.fetch.call_args.kwargs
