import asyncio
from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk import ExecutionContext, HTTPError, ResultType

from metabase.metabase import NO_RETRY, metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


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
                    "name": "Region",
                    "type": "category",
                    "default": None,
                    "target": target,
                    "value": "EU",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_no_parameters_sends_empty_body(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([]), status=202)
        await metabase.execute_action("run_question", {"question_id": 42}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {}

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
        mock_context.fetch.return_value = _ok(
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
        )
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select 1 as a, 'x' as b"}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["rows"] == [{"a": 1, "b": "x"}]
        assert result.result.data["columns"][1]["base_type"] == "type/Text"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([]), status=202)
        await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "  select 1  "}, mock_context)
        call = mock_context.fetch.call_args
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
        mock_context.fetch.side_effect = HTTPError(
            400, "raw", {"status": "failed", "error": 'ERROR: relation "nope" does not exist'}
        )
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "select * from nope"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert 'relation "nope" does not exist' in result.result.message

    @pytest.mark.asyncio
    async def test_write_sql_never_sent(self, mock_context):
        result = await metabase.execute_action(
            "run_sql_query", {"database_id": 3, "sql": "delete from users"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "read-only" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_question_rejects_write_sql(self, mock_context):
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "drop table users"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_sql(self, mock_context):
        result = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "   "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_rows_capped_at_2000(self, mock_context):
        mock_context.fetch.return_value = _ok(_dataset([[i] for i in range(2000)]), status=202)
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
        mock_context.fetch.return_value = _ok(_dataset([[1, 2]], cols=("id", "id")), status=202)
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
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_CARD, "id": 77, "name": "New"})
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
        mock_context.fetch.return_value = _ok({"id": 78, "name": "N"})
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
        mock_context.fetch.side_effect = HTTPError(403, "x", {"message": "You don't have permissions to do that."})
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({"name": "N"})
        result = await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "did not return a question id" in result.result.message

    @pytest.mark.asyncio
    async def test_empty_description_omitted(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 79, "name": "N"})
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1", "description": ""}, mock_context
        )
        assert "description" not in mock_context.fetch.call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_mbql5_response_sql_returned(self, mock_context):
        mock_context.fetch.return_value = _ok(
            {
                "id": 80,
                "name": "N",
                "database_id": 3,
                "dataset_query": {"database": 3, "stages": [{"native": "select 1"}]},
            }
        )
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
        mock_context.fetch.return_value = _ok({"id": 1, "name": "N"})
        await metabase.execute_action(
            "create_question", {"name": "N", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_timed_out_query_sent_once_through_sdk(self, mock_context):
        context = ExecutionContext(auth=mock_context.auth)
        context._session = MagicMock()
        context._session.request.side_effect = asyncio.TimeoutError
        with patch("asyncio.sleep") as sleep:
            result = await metabase.execute_action("run_sql_query", {"database_id": 3, "sql": "select 1"}, context)
        assert result.type == ResultType.ACTION_ERROR
        assert context._session.request.call_count == 1
        sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_question_keeps_retries(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        await metabase.execute_action("get_question", {"question_id": 42}, mock_context)
        assert "retry_count" not in mock_context.fetch.call_args.kwargs
