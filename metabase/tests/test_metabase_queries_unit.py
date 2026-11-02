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


class TestRunQuestion:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([[1, "EU"], [2, "US"]], cols=("n", "region")), status=202)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"n": 1, "region": "EU"}, {"n": 2, "region": "US"}]
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_request_with_parameters(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([]), status=202)
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
        mock_context.fetch.return_value = _ok(_dataset([[1]]), status=202)
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
        mock_context.fetch.return_value = _ok(_dataset([[1]]), status=202)
        await metabase.execute_action("run_question", {"question_id": 42, "parameters": [param]}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"parameters": [param]}

    @pytest.mark.asyncio
    async def test_no_parameters_sends_empty_body(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([]), status=202)
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {}

    @pytest.mark.asyncio
    async def test_saved_sql_checked_before_running(self, mock_context):
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "type": "native", "native": {"query": "select 1"}},
        }
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        urls = [c.args[0] for c in mock_context.fetch.call_args_list]
        assert urls == [f"{BASE}/api/card/42", f"{BASE}/api/database/3", f"{BASE}/api/card/42/query"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sql",
        ["delete from orders", "with x as (delete from orders returning *) select * from x", "select nextval('s')"],
    )
    async def test_saved_sql_that_writes_is_not_run(self, mock_context, sql):
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "type": "native", "native": {"query": sql}},
        }
        mock_context.fetch.side_effect = [_ok(card), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_mbql5_saved_sql_with_template_tags_runs(self, mock_context):
        sql = "select * from orders where 1=1 [[and {{region}}]] [[and status = {{status}}]] limit {{n}}"
        tags = [
            {"name": "region", "type": "dimension"},
            {"name": "status", "type": "text"},
            {"name": "n", "type": "number"},
        ]
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "stages": [{"native": sql, "template-tags": tags}]},
        }
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type != ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_referenced_question_and_snippet_checked(self, mock_context):
        sql = "select * from {{#7-base}} b where {{snippet: active}}"
        tags = {
            "#7-base": {"name": "#7-base", "type": "card", "card-id": 7},
            "snippet: active": {"name": "snippet: active", "type": "snippet", "snippet-id": 9},
        }
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "native": {"query": sql, "template-tags": tags}},
        }
        base = {"id": 7, "database_id": 3, "dataset_query": {"database": 3, "native": {"query": "delete from t"}}}
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(base), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "Saved question 7 wasn't run" in result.result.message

    @pytest.mark.asyncio
    async def test_snippet_that_writes_is_not_run(self, mock_context):
        tags = {"snippet: x": {"name": "snippet: x", "type": "snippet", "snippet-id": 9}}
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "native": {"query": "select 1; {{snippet: x}}", "template-tags": tags}},
        }
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok({"content": "delete from t"})]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_args_list[2].args[0] == f"{BASE}/api/native-query-snippet/9"

    @pytest.mark.asyncio
    async def test_snippet_found_by_name(self, mock_context):
        tags = {"snippet: active": {"name": "snippet: active", "type": "snippet", "snippet-name": "active"}}
        native = {"query": "select * from t where {{snippet: active}}", "template-tags": tags}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        snippets = [{"id": 1, "name": "other", "content": "1 = 1"}, {"id": 9, "name": "active", "content": "x > 0"}]
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _ok(snippets),
            _ok([]),
            _ok(_dataset([[1]]), status=202),
        ]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        assert mock_context.fetch.call_args_list[2].args[0] == f"{BASE}/api/native-query-snippet"

    @pytest.mark.asyncio
    async def test_snippet_name_that_writes_is_not_run(self, mock_context):
        tags = {"snippet: x": {"name": "snippet: x", "type": "snippet", "snippet-name": "x"}}
        native = {"query": "select 1 where {{snippet: x}}", "template-tags": tags}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _ok([]),
            _ok([{"id": 9, "name": "x", "content": "nextval('s') > 0", "archived": True}]),
        ]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        # Archived snippets still run in the questions that use them, so they are checked too.
        assert "nextval() has side effects" in result.result.message
        assert mock_context.fetch.call_args_list[3].args[0] == f"{BASE}/api/native-query-snippet?archived=true"

    @pytest.mark.asyncio
    async def test_sql_hidden_after_an_empty_optional_clause_is_not_run(self, mock_context):
        # With no value for n Metabase drops the whole [[...]], so the -- no longer hides nextval.
        native = {"query": "SELECT [[{{n}} --]] nextval('orders_id_seq')", "template-tags": {"n": {"type": "number"}}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "nextval() has side effects" in result.result.message

    @pytest.mark.asyncio
    async def test_dropped_optional_clause_leaves_nothing_behind(self, mock_context):
        # Metabase removes an empty [[...]] without a space, so "*[[...]]/" closes the comment and DELETE runs.
        native = {"query": "SELECT 1 /* *[[{{a}}]]/ ; DELETE FROM t; -- */", "template-tags": {"a": {"type": "text"}}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_braces_that_are_not_a_filter_are_not_run(self, mock_context):
        native = {"query": "SELECT '{{' ; DELETE FROM t; SELECT '}}'", "template-tags": {}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "isn't one of the saved question's filters" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_snippet_is_not_run(self, mock_context):
        tags = {"snippet: gone": {"name": "snippet: gone", "type": "snippet", "snippet-name": "gone"}}
        native = {"query": "select 1 where {{snippet: gone}}", "template-tags": tags}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok({"data": [{"id": 1, "name": "other"}]}), _ok([])]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "can't be found" in result.result.message

    @pytest.mark.asyncio
    async def test_snippet_with_filters_is_not_run(self, mock_context):
        tags = {"snippet: s": {"name": "snippet: s", "type": "snippet", "snippet-id": 9}}
        native = {"query": "select 1 where {{snippet: s}}", "template-tags": tags}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok({"content": "a = {{x}}"})]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "uses filters" in result.result.message

    @pytest.mark.asyncio
    async def test_field_filter_and_table_tags_run(self, mock_context):
        tags = {"region": {"type": "dimension"}, "t": {"type": "table"}, "unit": {"type": "temporal-unit"}}
        sql = "select {{unit}}, count(*) from {{t}} where {{region}} group by 1"
        card = {
            "id": 42,
            "database_id": 3,
            "dataset_query": {"database": 3, "native": {"query": sql, "template-tags": tags}},
        }
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_number_filter_in_sql_server_top_runs(self, mock_context):
        native = {"query": "SELECT TOP {{n}} * FROM dbo.orders", "template-tags": {"n": {"type": "number"}}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database("sqlserver"), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_card_tag_without_id_is_not_run(self, mock_context):
        native = {"query": "select * from {{#base}}", "template-tags": {"#base": {"type": "card"}}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        mock_context.fetch.side_effect = [_ok(card), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "can't be checked" in result.result.message

    @pytest.mark.asyncio
    async def test_same_question_as_text_and_number_fetched_once(self, mock_context):
        native = {"query": "select * from {{#7-base}}", "template-tags": {"#7-base": {"type": "card", "card-id": 7}}}
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": native}}
        gui = {
            "id": 42,
            "dataset_query": {"database": 3, "query": {"source-table": "card__7", "joins": [{"source-card": 7}]}},
        }
        base = {"id": 7, "dataset_query": {"database": 3, "query": {"source-table": 5}}}
        mock_context.fetch.side_effect = [_ok(gui), _ok(base), _ok(_dataset([[1]]), status=202)]
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert mock_context.fetch.call_count == 3
        mock_context.fetch.reset_mock()
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(base), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_failed_check_never_runs_the_question(self, mock_context):
        card = {"id": 42, "database_id": 3, "dataset_query": {"database": 3, "native": {"query": "drop table t"}}}
        mock_context.fetch.side_effect = [_ok(card), _database()]
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert all(c.kwargs.get("method", "GET") == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_inline_sql_source_is_checked(self, mock_context):
        source = {"native": "SELECT nextval('orders_id_seq')"}
        gui = {"id": 42, "dataset_query": {"database": 3, "type": "query", "query": {"source-query": source}}}
        mock_context.fetch.side_effect = [_ok(gui), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "nextval() has side effects" in result.result.message

    @pytest.mark.asyncio
    async def test_inline_sql_in_a_join_is_checked(self, mock_context):
        join = {"source-query": {"native": "delete from t"}, "alias": "j"}
        gui = {"id": 42, "dataset_query": {"database": 3, "query": {"source-table": 5, "joins": [join]}}}
        mock_context.fetch.side_effect = [_ok(gui), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_card_spelling_in_a_filter_value_is_not_a_source(self, mock_context):
        query = {"source-table": 5, "filter": ["=", ["field", 9, None], "card__7"]}
        gui = {"id": 42, "dataset_query": {"database": 3, "type": "query", "query": query}}
        mock_context.fetch.side_effect = [_ok(gui), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_shared_source_checked_once(self, mock_context):
        # 42 is built on 7 and joins 7 twice more; 7 is fetched once.
        joins = [{"source-table": "card__7"}, {"source-table": "card__7"}]
        gui = {"id": 42, "dataset_query": {"database": 3, "query": {"source-table": "card__7", "joins": joins}}}
        base = {"id": 7, "dataset_query": {"database": 3, "query": {"source-table": 5}}}
        mock_context.fetch.side_effect = [_ok(gui), _ok(base), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_gui_question_on_saved_sql_is_checked(self, mock_context):
        gui = {"id": 42, "dataset_query": {"database": 3, "type": "query", "query": {"source-table": "card__7"}}}
        base = {"id": 7, "database_id": 3, "dataset_query": {"database": 3, "native": {"query": "drop table t"}}}
        mock_context.fetch.side_effect = [_ok(gui), _ok(base), _database()]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "Saved question 7 wasn't run" in result.result.message

    @pytest.mark.asyncio
    async def test_gui_question_runs_without_database_lookup(self, mock_context):
        gui = {"id": 42, "dataset_query": {"lib/type": "mbql/query", "stages": [{"source-table": 5}]}}
        mock_context.fetch.side_effect = [_ok(gui), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_questions_built_on_each_other_fetched_once(self, mock_context):
        one = {"id": 1, "dataset_query": {"database": 3, "query": {"source-table": "card__2"}}}
        two = {"id": 2, "dataset_query": {"database": 3, "query": {"source-table": "card__1"}}}
        mock_context.fetch.side_effect = [_ok(one), _ok(two), _ok(_dataset([[1]]), status=202)]
        result = await metabase.execute_action("run_question", {"question_id": 1}, mock_context)
        assert result.result.data["rows"] == [{"a": 1}]
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_long_chain_of_questions_stops(self, mock_context):
        chain = [
            _ok({"id": n, "dataset_query": {"database": 3, "stages": [{"source-card": n + 1}]}}) for n in range(10)
        ]
        mock_context.fetch.side_effect = chain
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert "too many other saved questions" in result.result.message

    @pytest.mark.asyncio
    async def test_max_rows(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([[i] for i in range(10)]), status=202)
        result = await metabase.execute_action("run_question", {"question_id": 42, "max_rows": 3}, mock_context)
        assert result.result.data["row_count"] == 3
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_default_max_rows_100(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([[i] for i in range(150)]), status=202)
        result = await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert result.result.data["row_count"] == 100
        assert result.result.data["total_row_count"] == 150

    @pytest.mark.asyncio
    async def test_failed_query(self, mock_context):
        mock_context.fetch.return_value = _ok({"status": "failed", "error": "column x does not exist"}, status=202)
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
    async def test_duplicate_column_names(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok(_dataset([[1, 2]], cols=("id", "id")), status=202)]
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select 1 id, 2 id"}, mock_context
        )
        assert result.result.data["rows"] == [{"id": 1, "id_2": 2}]

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
    async def test_defaults(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"id": 78, "name": "N"})]
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
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
    async def test_empty_description_omitted(self, mock_context):
        mock_context.fetch.side_effect = [_database(), _ok({"id": 79, "name": "N"})]
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1", "description": ""}, mock_context
        )
        assert "description" not in mock_context.fetch.call_args.kwargs["json"]

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
        mock_context.fetch.return_value = _ok(_dataset([[1]]), status=202)
        await metabase.execute_action(action, inputs, mock_context)
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
