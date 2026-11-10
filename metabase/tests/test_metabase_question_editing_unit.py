import asyncio
import base64
import csv
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autohive_integrations_sdk import HTTPError, ResultType

from metabase.metabase import NO_RETRY, XLSX_CONTENT_TYPE, _download, metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


def _database(engine="postgres"):
    return _ok({"id": 3, "name": "Warehouse", "engine": engine})


SAMPLE_CARD = {
    "id": 42,
    "name": "Weekly signups",
    "description": "Signups per week",
    "type": "question",
    "display": "line",
    "database_id": 3,
    "query_type": "native",
    "collection_id": 4,
    "collection": {"id": 4, "name": "Growth", "slug": "growth"},
    "archived": False,
    "parameters": [],
    "visualization_settings": {"graph.dimensions": ["week"], "graph.metrics": ["signups"], "card.title": "Signups"},
    "dataset_query": {
        "database": 3,
        "type": "native",
        "native": {"query": "select week, count(*) as signups from signups group by week", "template-tags": {}},
    },
}

SAMPLE_COPY = {**SAMPLE_CARD, "id": 77, "name": "Weekly signups - Duplicate"}

SAMPLE_MBQL = {
    "source-table": 12,
    "aggregation": [["count"]],
    "breakout": [["field", 34, {"temporal-unit": "month"}]],
    "filter": [">", ["field", 56, None], 100],
}

SAMPLE_MBQL_CARD = {
    "id": 90,
    "name": "Orders by month",
    "type": "question",
    "display": "table",
    "database_id": 3,
    "query_type": "query",
    "collection_id": None,
    "dataset_query": {"database": 3, "type": "query", "query": SAMPLE_MBQL},
}

SAMPLE_REVISIONS = [
    {
        "id": 501,
        "description": 'renamed this Card from "Signups" to "Weekly signups".',
        "timestamp": "2026-10-30T02:11:09.123Z",
        "user": {"id": 1, "common_name": "Risheet Peri"},
        "is_creation": False,
        "is_reversion": False,
        "most_recent": True,
    },
    {
        "id": 498,
        "description": "created this.",
        "timestamp": "2026-10-01T22:04:51.000Z",
        "user": {"id": 1, "common_name": "Risheet Peri"},
        "is_creation": True,
        "is_reversion": False,
        "most_recent": False,
    },
]

SAVED_EXPORT_CARD = {
    "id": 42,
    "database_id": 3,
    "parameters": [],
    "dataset_query": {"database": 3, "type": "native", "native": {"query": "select id, email from users"}},
}

SAMPLE_FILTERED_CARD = {
    "id": 42,
    "name": "Signups by region",
    "database_id": 3,
    "dataset_query": {
        "database": 3,
        "type": "native",
        "native": {
            "query": "select * from signups where region = {{region}}",
            "template-tags": {"region": {"id": "t1", "name": "region", "display-name": "Region", "type": "text"}},
        },
    },
}
XLSX_BYTES = b"PK\x03\x04 spreadsheet bytes"

SAMPLE_CSV = "id,email\n1,ana@example.com\n2,ben@example.com\n3,cy@example.com\n"


def _export_calls(response, compiled="select id, email from users", card=None):
    """The saved-question check (card, database, expanded SQL) and then the export."""
    return [
        _ok(card or SAVED_EXPORT_CARD),
        _database(),
        _ok({"query": compiled, "params": None}),
        _ok(response),
    ]


def _compiled(sql):
    return _ok({"query": sql, "params": None})


def _saving_check_calls(compiled="select id, email from users", card=None):
    """The check before saving a question's SQL somewhere new (copy, revert, a question built on it): the card, its
    database, then Metabase expands it twice, once with every filter set and once as it runs."""
    return [*_export_calls(None, compiled=compiled, card=card)[:3], _compiled(compiled)]


def _source_check_calls(compiled="select id, email from users", card=None):
    """The check of a saved question a query or revert relies on: the card, its database, its expanded SQL."""
    return _export_calls(None, compiled=compiled, card=card)[:3]


SAMPLE_MBQL5_CARD = {
    "id": 42,
    "name": "Signups by region",
    "database_id": 3,
    "dataset_query": {
        "lib/type": "mbql/query",
        "database": 3,
        "stages": [
            {
                "lib/type": "mbql.stage/native",
                "native": "select * from signups where region = {{region}}",
                "template-tags": [{"id": "t1", "name": "region", "display-name": "Region", "type": "text"}],
            }
        ],
    },
}

SNIPPET_TAG = {"id": "s1", "name": "snippet: totals", "type": "snippet", "snippet-name": "totals", "snippet-id": 7}

SAMPLE_SNIPPET_CARD = {
    "id": 42,
    "name": "Order totals",
    "database_id": 3,
    "dataset_query": {
        "database": 3,
        "type": "native",
        "native": {
            "query": "select * from orders where {{snippet: totals}}",
            "template-tags": {"snippet: totals": SNIPPET_TAG},
        },
    },
}

CARD_HISTORY = [{"id": 510, "most_recent": True}, {"id": 498, "most_recent": False}]


class TestUpdateQuestion:
    @pytest.mark.asyncio
    async def test_rename_only_sends_name(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_CARD, "name": "Signups by week"})
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "name": "Signups by week"}, mock_context
        )
        assert result.result.data["name"] == "Signups by week"
        assert mock_context.fetch.call_count == 1
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card/42"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {"name": "Signups by week"}
        assert call.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_only_given_fields_sent(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        inputs = {"question_id": 42, "description": "Weekly", "display": "bar", "collection_id": 9}
        await metabase.execute_action("update_question", inputs, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "description": "Weekly",
            "display": "bar",
            "collection_id": 9,
        }

    @pytest.mark.asyncio
    async def test_moving_a_dashboard_question_takes_it_out_of_the_dashboard(self, mock_context):
        in_dashboard = {**SAMPLE_CARD, "dashboard_id": 5}
        mock_context.fetch.side_effect = [_ok(in_dashboard), _ok({**SAMPLE_CARD, "collection_id": 9})]
        result = await metabase.execute_action("update_question", {"question_id": 42, "collection_id": 9}, mock_context)
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args_list[0].kwargs["method"] == "GET"
        assert mock_context.fetch.call_args.kwargs["json"] == {"collection_id": 9, "dashboard_id": None}

    @pytest.mark.asyncio
    async def test_dashboard_question_given_its_own_collection_stays_in_the_dashboard(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_CARD, "dashboard_id": 5})
        await metabase.execute_action("update_question", {"question_id": 42, "collection_id": 4}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"collection_id": 4}

    @pytest.mark.asyncio
    async def test_dashboard_question_renamed_stays_in_the_dashboard(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_CARD, "dashboard_id": 5})
        await metabase.execute_action("update_question", {"question_id": 42, "name": "Renamed"}, mock_context)
        assert mock_context.fetch.call_count == 1
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "Renamed"}

    @pytest.mark.asyncio
    async def test_sql_checked_in_card_dialect(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD), _database("mysql"), _ok(SAMPLE_CARD)]
        sql = "select week, count(*) from signups where region = 'EU' group by week"
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        urls = [c.args[0] for c in mock_context.fetch.call_args_list]
        assert urls == [f"{BASE}/api/card/42", f"{BASE}/api/database/3", f"{BASE}/api/card/42"]
        put = mock_context.fetch.call_args
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["json"] == {
            "dataset_query": {"database": 3, "type": "native", "native": {"query": sql, "template-tags": {}}}
        }

    @pytest.mark.asyncio
    async def test_database_from_dataset_query_when_card_has_no_database_id(self, mock_context):
        card = {**SAMPLE_CARD, "database_id": None}
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(SAMPLE_CARD)]
        await metabase.execute_action("update_question", {"question_id": 42, "sql": "select 1"}, mock_context)
        assert mock_context.fetch.call_args_list[1].args[0] == f"{BASE}/api/database/3"
        assert mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["database"] == 3

    @pytest.mark.asyncio
    async def test_write_sql_refused_without_put(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD), _database()]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "delete from signups"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Only a single read statement" in result.result.message
        assert all(c.kwargs["method"] == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_two_statements_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD), _database()]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "select 1; drop table signups"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_blank_sql_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": "  "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "sql is required" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_visualization_settings_merged_and_null_removes(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD), _ok(SAMPLE_CARD)]
        settings = {"graph.metrics": ["signups", "churned"], "card.title": None, "graph.show_values": True}
        await metabase.execute_action(
            "update_question", {"question_id": 42, "visualization_settings": settings}, mock_context
        )
        assert mock_context.fetch.call_args_list[0].kwargs["method"] == "GET"
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "visualization_settings": {
                "graph.dimensions": ["week"],
                "graph.metrics": ["signups", "churned"],
                "graph.show_values": True,
            }
        }

    @pytest.mark.asyncio
    async def test_visualization_settings_on_card_without_saved_settings(self, mock_context):
        card = {k: v for k, v in SAMPLE_CARD.items() if k != "visualization_settings"}
        mock_context.fetch.side_effect = [_ok(card), _ok(card)]
        await metabase.execute_action(
            "update_question", {"question_id": 42, "visualization_settings": {"card.title": "Signups"}}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {"visualization_settings": {"card.title": "Signups"}}

    @pytest.mark.asyncio
    async def test_sql_and_settings_share_one_get(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD), _database(), _ok(SAMPLE_CARD)]
        inputs = {"question_id": 42, "name": "Signups", "sql": "select 1", "visualization_settings": {}}
        await metabase.execute_action("update_question", inputs, mock_context)
        assert mock_context.fetch.call_count == 3
        assert set(mock_context.fetch.call_args.kwargs["json"]) == {"name", "dataset_query", "visualization_settings"}

    @pytest.mark.asyncio
    async def test_no_changes_is_error(self, mock_context):
        result = await metabase.execute_action("update_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Give a change" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_name_is_not_a_change(self, mock_context):
        result = await metabase.execute_action("update_question", {"question_id": 42, "name": ""}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_summary_output(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        result = await metabase.execute_action("update_question", {"question_id": 42, "display": "bar"}, mock_context)
        data = result.result.data
        assert data["id"] == 42
        assert data["native_sql"] == SAMPLE_CARD["dataset_query"]["native"]["query"]
        assert data["collection"] == {"id": 4, "name": "Growth"}

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("update_question", {"question_id": 404, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action("update_question", {"question_id": 42, "name": "X"}, mock_context)
        assert "Check with get_question" in result.result.message

    @pytest.mark.asyncio
    async def test_string_id_rejected(self, mock_context):
        result = await metabase.execute_action("update_question", {"question_id": "42", "name": "X"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_sql_update_keeps_saved_template_tags(self, mock_context):
        tag = {"id": "t1", "name": "region", "display-name": "Region", "type": "text"}
        card = {
            **SAMPLE_CARD,
            "dataset_query": {
                "database": 3,
                "type": "native",
                "native": {
                    "query": "select * from signups where region = {{region}}",
                    "template-tags": {"region": tag},
                },
            },
        }
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _compiled("select week from signups where region = 'EU'"),
            _ok(card),
        ]
        sql = "select week from signups where region = {{region}}"
        await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        native = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]
        assert native["template-tags"] == {"region": tag}

    @pytest.mark.asyncio
    async def test_filter_sql_checked_after_metabase_expands_it(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_FILTERED_CARD),
            _database(),
            _compiled("select week from signups where region = 'EU'"),
            _ok(SAMPLE_FILTERED_CARD),
        ]
        sql = "select week from signups where region = {{region}}"
        await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        calls = mock_context.fetch.call_args_list
        assert [(c.args[0], c.kwargs["method"]) for c in calls] == [
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card/42", "PUT"),
        ]
        new_query = calls[3].kwargs["json"]["dataset_query"]
        # The region filter has no default, so it is expanded with a stand-in value for the check.
        stand_in = {"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "x"}
        assert calls[2].kwargs["json"] == {**new_query, "parameters": [stand_in], "pretty": False}

    @pytest.mark.asyncio
    async def test_expanded_write_refused_without_put(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_FILTERED_CARD),
            _database(),
            _compiled("select 1; delete from t"),
        ]
        sql = "select * from signups where region = {{region}}"
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Only a single read statement" in result.result.message
        assert mock_context.fetch.call_count == 3
        assert all(c.kwargs["method"] != "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_optional_clause_refused_without_put(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_FILTERED_CARD)]
        sql = "select * from signups where 1 = 1 [[and region = {{region}}]]"
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "optional [[ ]] clauses can't be saved" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_mbql5_update_keeps_stages_and_list_tags(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_MBQL5_CARD),
            _database(),
            _compiled("select week, count(*) from signups where region = 'EU' group by week"),
            _ok(SAMPLE_MBQL5_CARD),
        ]
        sql = "select week, count(*) from signups where region = {{region}} group by week"
        await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        saved = SAMPLE_MBQL5_CARD["dataset_query"]
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "dataset_query": {
                "lib/type": "mbql/query",
                "database": 3,
                "stages": [
                    {
                        "lib/type": "mbql.stage/native",
                        "native": sql,
                        "template-tags": saved["stages"][0]["template-tags"],
                    }
                ],
            }
        }

    @pytest.mark.asyncio
    async def test_mbql5_update_drops_unused_tag(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_MBQL5_CARD), _database(), _ok(SAMPLE_MBQL5_CARD)]
        await metabase.execute_action("update_question", {"question_id": 42, "sql": "select 1"}, mock_context)
        stage = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["stages"][0]
        assert stage["template-tags"] == []
        assert stage["native"] == "select 1"

    @pytest.mark.asyncio
    async def test_mbql5_update_keeps_later_stages(self, mock_context):
        summarize = {"lib/type": "mbql.stage/mbql", "aggregation": [["count", {}]], "breakout": [["field", {}, "week"]]}
        saved = SAMPLE_MBQL5_CARD["dataset_query"]
        card = {**SAMPLE_MBQL5_CARD, "dataset_query": {**saved, "stages": [*saved["stages"], summarize]}}
        mock_context.fetch.side_effect = [_ok(card), _database(), _ok(card)]
        await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "select week from signups"}, mock_context
        )
        stages = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["stages"]
        assert len(stages) == 2
        assert stages[0]["native"] == "select week from signups"
        assert stages[1] == summarize

    @pytest.mark.asyncio
    async def test_snippet_tag_kept(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_SNIPPET_CARD),
            _database(),
            _compiled("select id, total from orders where total > 0"),
            _ok(SAMPLE_SNIPPET_CARD),
        ]
        sql = "select id, total from orders where {{ snippet: totals }}"
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        native = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]
        assert native == {"query": sql, "template-tags": {"snippet: totals": SNIPPET_TAG}}

    @pytest.mark.asyncio
    async def test_new_snippet_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_SNIPPET_CARD), _ok([{"id": 7, "name": "totals"}])]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "select * from orders where {{snippet:other}}"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "no snippet named other" in result.result.message
        calls = mock_context.fetch.call_args_list
        assert [c.args[0] for c in calls] == [f"{BASE}/api/card/42", f"{BASE}/api/native-query-snippet"]
        assert all(c.kwargs["method"] == "GET" for c in calls)

    @pytest.mark.asyncio
    async def test_new_filter_added_with_sql(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_FILTERED_CARD),
            _database(),
            _compiled("select * from signups where region = 'x' and country = 'NZ'"),
            _ok(SAMPLE_FILTERED_CARD),
        ]
        sql = "select * from signups where region = {{region}} and country = {{country}}"
        filters = [{"name": "country", "type": "text", "default": "NZ"}]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": sql, "filters": filters}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        tags = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"]
        assert tags["region"] == SAMPLE_FILTERED_CARD["dataset_query"]["native"]["template-tags"]["region"]
        country = dict(tags["country"])
        country_id = country.pop("id")
        assert isinstance(country_id, str)
        assert country == {
            "name": "country",
            "display-name": "Country",
            "type": "text",
            "required": False,
            "default": "NZ",
        }
        # Only the filter without a default gets a stand-in value.
        params = mock_context.fetch.call_args_list[2].kwargs["json"]["parameters"]
        assert [p["target"][1][1] for p in params] == ["region"]

    @pytest.mark.asyncio
    async def test_listed_existing_filter_keeps_its_id(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_FILTERED_CARD),
            _database(),
            _compiled("select * from signups where region = 'EU'"),
            _ok(SAMPLE_FILTERED_CARD),
        ]
        filters = [{"name": "region", "type": "text", "display_name": "Sales region", "default": "EU"}]
        await metabase.execute_action(
            "update_question",
            {"question_id": 42, "sql": "select * from signups where region = {{region}}", "filters": filters},
            mock_context,
        )
        tag = mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["native"]["template-tags"]["region"]
        assert tag["id"] == "t1"
        assert tag["display-name"] == "Sales region"
        assert tag["default"] == "EU"

    @pytest.mark.asyncio
    async def test_undefined_filter_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "select * from signups where c = {{country}}"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "define it in filters" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_unused_filter_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action(
            "update_question",
            {"question_id": 42, "sql": "select 1", "filters": [{"name": "country", "type": "text"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't used in the SQL" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_required_filter_without_default_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action(
            "update_question",
            {
                "question_id": 42,
                "sql": "select * from signups where c = {{country}}",
                "filters": [{"name": "country", "required": True}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "needs a default" in result.result.message

    @pytest.mark.asyncio
    async def test_field_filter_without_field_id_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action(
            "update_question",
            {
                "question_id": 42,
                "sql": "select * from signups where {{country}}",
                "filters": [{"name": "country", "type": "field"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "needs field_id" in result.result.message

    @pytest.mark.asyncio
    async def test_expanded_write_message_says_not_saved(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_FILTERED_CARD), _database(), _compiled("delete from signups")]
        sql = "select * from signups where region = {{region}}"
        result = await metabase.execute_action("update_question", {"question_id": 42, "sql": sql}, mock_context)
        assert result.result.message.startswith("Not saved.")

    @pytest.mark.asyncio
    async def test_filters_without_sql_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_CARD)]
        result = await metabase.execute_action(
            "update_question",
            {"question_id": 42, "visualization_settings": {"card.title": "X"}, "filters": [{"name": "country"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "filters can only be given together with sql" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_filters_without_sql_refused_on_rename(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_CARD)
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "name": "Signups", "filters": [{"name": "country"}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert all(c.kwargs["method"] != "PUT" for c in mock_context.fetch.call_args_list)


class TestCopyQuestion:
    @pytest.mark.asyncio
    async def test_copy_without_changes(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_COPY)]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.result.data["id"] == 77
        assert mock_context.fetch.call_count == 5
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card/42/copy"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_question_checked_before_copy(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_COPY)]
        await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert [(c.args[0], c.kwargs["method"]) for c in mock_context.fetch.call_args_list] == [
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card/42/copy", "POST"),
        ]

    @staticmethod
    def _filtered_card(sql, **tag):
        query = {
            "database": 3,
            "type": "native",
            "native": {"query": sql, "template-tags": {"p": {"name": "p", **tag}}},
        }
        return {**SAVED_EXPORT_CARD, "dataset_query": query, "parameters": []}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "field_type,value",
        [("type/UUID", ["00000000-0000-0000-0000-000000000000"]), ("type/BigInteger", [1]), ("type/Text", ["x"])],
    )
    async def test_field_filter_stand_in_fits_the_column(self, mock_context, field_type, value):
        # Metabase refuses to expand the SQL when a field filter's value can't be read as the column's type.
        card = self._filtered_card(
            "select * from orders where {{p}}", type="dimension", dimension=["field", 72, None], **{"widget-type": "id"}
        )
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _ok({"id": 72, "base_type": field_type, "effective_type": field_type}),
            _compiled("select * from orders where id = 1"),
            _compiled("select * from orders"),
            _ok(SAMPLE_COPY),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION
        calls = mock_context.fetch.call_args_list
        assert (calls[2].args[0], calls[2].kwargs["method"]) == (f"{BASE}/api/field/72", "GET")
        assert calls[3].kwargs["json"]["parameters"] == [
            {"type": "id", "target": ["dimension", ["template-tag", "p"]], "value": value}
        ]

    @pytest.mark.asyncio
    async def test_failed_expansion_without_optional_filter_refuses_copy(self, mock_context):
        # The form without the optional filter can run, so a failed check of it (a 500, say) leaves it unchecked.
        card = self._filtered_card("select 1 [[ + {{p}} --]] , nextval('audit_seq')", type="number")
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _compiled("select 1 + 1 --, nextval('audit_seq')"),
            HTTPError(500, "Server Error", {"message": "Connection reset"}),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message
        assert all("/copy" not in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sql,tag",
        [
            ("select * from t where x = {{p}}", {"type": "number"}),
            ("select * from t [[where x = {{p}}]]", {"type": "number", "required": True}),
        ],
    )
    async def test_filter_the_sql_needs_doesnt_block_copy(self, mock_context, sql, tag):
        # Without a value Metabase can't expand it at all, and it can't run either; the check with it set covers it.
        mock_context.fetch.side_effect = [
            _ok(self._filtered_card(sql, **tag)),
            _database(),
            _compiled("select * from t where x = 1"),
            HTTPError(500, "Server Error", {"message": "You'll need to pick a value for 'p'"}),
            _ok(SAMPLE_COPY),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/card/42/copy"

    @pytest.mark.asyncio
    async def test_writing_question_not_copied(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls(compiled="delete from users")
        result = await metabase.execute_action("copy_question", {"question_id": 42, "name": "Copy"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert mock_context.fetch.call_count == 3
        assert all("/copy" not in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_defaults_checked_with_and_without(self, mock_context):
        target = ["variable", ["template-tag", "region"]]
        card = {
            **SAVED_EXPORT_CARD,
            "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}],
        }
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _compiled("select id, email from users"),
            _compiled("select id, email from users where region = 'EU'"),
            _compiled("select id, email from users"),
            _ok(SAMPLE_COPY),
        ]
        await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        compiles = [c for c in mock_context.fetch.call_args_list if c.args[0].endswith("/dataset/native")]
        # Every filter set (this SQL has no tags), then with the default, then without it.
        assert [c.kwargs["json"]["parameters"] for c in compiles] == [
            [],
            [{"id": "p1", "type": "category", "target": target, "value": "EU"}],
            [],
        ]

    @pytest.mark.asyncio
    async def test_write_without_default_not_copied(self, mock_context):
        target = ["variable", ["template-tag", "region"]]
        card = {
            **SAVED_EXPORT_CARD,
            "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}],
        }
        mock_context.fetch.side_effect = [
            _ok(card),
            _database(),
            _compiled("select id, email from users"),
            _compiled("select id, email from users where region = 'EU'"),
            _compiled("select 1; delete from users"),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 5
        assert all("/copy" not in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_rename_and_move_copy(self, mock_context):
        renamed = {**SAMPLE_COPY, "name": "Signups (EU)", "collection_id": 9}
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_COPY), _ok(renamed)]
        result = await metabase.execute_action(
            "copy_question", {"question_id": 42, "name": "Signups (EU)", "collection_id": 9}, mock_context
        )
        put = mock_context.fetch.call_args
        assert put.args[0] == f"{BASE}/api/card/77"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["json"] == {"name": "Signups (EU)", "collection_id": 9}
        assert put.kwargs["retry_count"] == NO_RETRY
        assert result.result.data["name"] == "Signups (EU)"
        assert result.result.data["collection_id"] == 9

    @pytest.mark.asyncio
    async def test_only_collection_given(self, mock_context):
        mock_context.fetch.side_effect = [
            *_saving_check_calls(),
            _ok(SAMPLE_COPY),
            _ok({**SAMPLE_COPY, "collection_id": 9}),
        ]
        await metabase.execute_action("copy_question", {"question_id": 42, "collection_id": 9}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"collection_id": 9}

    @pytest.mark.asyncio
    async def test_moving_a_copy_of_a_dashboard_question_takes_it_out_of_the_dashboard(self, mock_context):
        copy = {**SAMPLE_COPY, "dashboard_id": 5}
        mock_context.fetch.side_effect = [
            *_saving_check_calls(),
            _ok(copy),
            _ok({**SAMPLE_COPY, "collection_id": 9}),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42, "collection_id": 9}, mock_context)
        assert result.type == ResultType.ACTION
        put = mock_context.fetch.call_args
        assert put.args[0] == f"{BASE}/api/card/77?delete_old_dashcards=true"
        assert put.kwargs["json"] == {"collection_id": 9, "dashboard_id": None}

    @pytest.mark.asyncio
    async def test_renaming_a_copy_of_a_dashboard_question_keeps_it_in_the_dashboard(self, mock_context):
        copy = {**SAMPLE_COPY, "dashboard_id": 5}
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(copy), _ok({**copy, "name": "EU"})]
        await metabase.execute_action("copy_question", {"question_id": 42, "name": "EU"}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/card/77"
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "EU"}

    @pytest.mark.asyncio
    async def test_empty_name_skips_put(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_COPY)]
        await metabase.execute_action("copy_question", {"question_id": 42, "name": ""}, mock_context)
        assert mock_context.fetch.call_count == 5
        assert all(c.kwargs["method"] != "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_empty_put_response_keeps_copy(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_COPY), _ok({})]
        result = await metabase.execute_action("copy_question", {"question_id": 42, "name": "X"}, mock_context)
        assert result.result.data["id"] == 77

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok({"name": "Weekly signups - Duplicate"})]
        result = await metabase.execute_action("copy_question", {"question_id": 42, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 5

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("copy_question", {"question_id": 404}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), asyncio.TimeoutError()]
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert "Check with search" in result.result.message

    @pytest.mark.asyncio
    async def test_rename_failure_reported(self, mock_context):
        mock_context.fetch.side_effect = [
            *_saving_check_calls(),
            _ok(SAMPLE_COPY),
            HTTPError(403, "Forbidden", "You don't have permissions."),
        ]
        result = await metabase.execute_action("copy_question", {"question_id": 42, "collection_id": 9}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        message = result.result.message
        assert "HTTP 403" in message
        assert "question 77" in message
        assert "update_question" in message
        assert mock_context.fetch.call_count == 6


class TestCreateQueryBuilderQuestion:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_MBQL_CARD)
        result = await metabase.execute_action(
            "create_query_builder_question",
            {"name": "Orders by month", "database_id": 3, "query": SAMPLE_MBQL},
            mock_context,
        )
        data = result.result.data
        assert data["id"] == 90
        assert data["native_sql"] is None
        assert data["query_type"] == "query"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_MBQL_CARD)
        await metabase.execute_action(
            "create_query_builder_question",
            {"name": "Orders by month", "database_id": 3, "query": SAMPLE_MBQL, "collection_id": 4},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "name": "Orders by month",
            "type": "question",
            "display": "table",
            "visualization_settings": {},
            "dataset_query": {"database": 3, "type": "query", "query": SAMPLE_MBQL},
            "collection_id": 4,
        }

    @pytest.mark.asyncio
    async def test_display_and_description(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_MBQL_CARD)
        inputs = {"name": "Orders", "database_id": 3, "query": SAMPLE_MBQL, "display": "bar", "description": "Monthly"}
        await metabase.execute_action("create_query_builder_question", inputs, mock_context)
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["display"] == "bar"
        assert body["description"] == "Monthly"

    @pytest.mark.asyncio
    async def test_saved_question_source(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok(SAMPLE_MBQL_CARD)]
        query = {"source-table": "card__42", "aggregation": [["count"]]}
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Count", "database_id": 3, "query": query}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        assert [(c.args[0], c.kwargs["method"]) for c in mock_context.fetch.call_args_list] == [
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card", "POST"),
        ]
        assert mock_context.fetch.call_args.kwargs["json"]["dataset_query"]["query"] == query

    @pytest.mark.asyncio
    async def test_writing_saved_question_source_refused(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls(compiled="delete from t")
        query = {"source-table": "card__42", "aggregation": [["count"]]}
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Count", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert f"{BASE}/api/card" not in [c.args[0] for c in mock_context.fetch.call_args_list]

    @pytest.mark.asyncio
    async def test_embedded_native_refused(self, mock_context):
        query = {"source-table": 12, "joins": [{"source-query": {"native": "delete from orders"}}]}
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Sneaky", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "can't contain SQL" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key", ["NATIVE", "Native", "NaTiVe"])
    async def test_embedded_native_in_other_case_refused(self, mock_context, key):
        # Metabase reads MBQL keys case-insensitively, so "NATIVE" still runs as SQL.
        query = {"source-table": 12, "joins": [{"source-query": {key: "select nextval('orders_id_seq')"}}]}
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Sneaky", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "can't contain SQL" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_native_as_a_filter_value_allowed(self, mock_context):
        query = {"source-table": 12, "filter": ["=", ["field", 7, None], "NATIVE"]}
        mock_context.fetch.return_value = _ok({"id": 90, "name": "Natives"})
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Natives", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION

    @pytest.mark.asyncio
    async def test_missing_source_table_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_query_builder_question",
            {"name": "Orders", "database_id": 3, "query": {"aggregation": [["count"]]}},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "source-table" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_name_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": " ", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "name is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({"name": "Orders"})
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Orders", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"message": "Table 12 does not exist"})
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Orders", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Table 12 does not exist" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Orders", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert "Check with search" in result.result.message

    @pytest.mark.asyncio
    async def test_query_required(self, mock_context):
        result = await metabase.execute_action(
            "create_query_builder_question", {"name": "Orders", "database_id": 3}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_filter_value_native_allowed(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_MBQL_CARD)
        query = {"source-table": 12, "filter": ["=", ["field", 56, None], "native"]}
        result = await metabase.execute_action(
            "create_query_builder_question",
            {"name": "Native app signups", "database_id": 3, "query": query},
            mock_context,
        )
        assert result.type != ResultType.ACTION_ERROR


class TestCreateModel:
    @pytest.mark.asyncio
    async def test_sql_model(self, mock_context):
        model = {**SAMPLE_CARD, "id": 91, "type": "model", "display": "table"}
        mock_context.fetch.side_effect = [_database(), _ok(model)]
        sql = "select id, email, created_at from users"
        result = await metabase.execute_action(
            "create_model", {"name": "Users", "database_id": 3, "sql": sql}, mock_context
        )
        assert result.result.data["type"] == "model"
        get, post = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/database/3"
        assert post.args[0] == f"{BASE}/api/card"
        assert post.kwargs["retry_count"] == NO_RETRY
        assert post.kwargs["json"] == {
            "name": "Users",
            "type": "model",
            "display": "table",
            "visualization_settings": {},
            "dataset_query": {"database": 3, "type": "native", "native": {"query": sql, "template-tags": {}}},
        }

    @pytest.mark.asyncio
    async def test_sql_filter_refused_even_if_given(self, mock_context):
        # Metabase refuses {{ }} filters in a model, so filters isn't an input and the variable is undefined.
        result = await metabase.execute_action(
            "create_model",
            {"name": "By region", "database_id": 3, "sql": "select * from orders where region = {{region}}"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "A model can't have {{ }} filters (region); save a question for that instead."
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_builder_model(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_MBQL_CARD, "type": "model"})
        await metabase.execute_action(
            "create_model", {"name": "Orders", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert mock_context.fetch.call_count == 1
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["type"] == "model"
        assert body["dataset_query"] == {"database": 3, "type": "query", "query": SAMPLE_MBQL}

    @pytest.mark.asyncio
    async def test_writing_saved_question_source_refused(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls(compiled="delete from t")
        query = {"source-table": "card__42", "breakout": [["field", "region", {"base-type": "type/Text"}]]}
        result = await metabase.execute_action(
            "create_model", {"name": "Regions", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert mock_context.fetch.call_count == 3
        assert f"{BASE}/api/card" not in [c.args[0] for c in mock_context.fetch.call_args_list]

    @pytest.mark.asyncio
    async def test_joined_saved_question_checked(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), _ok({**SAMPLE_MBQL_CARD, "type": "model"})]
        query = {"source-table": 12, "joins": [{"source-table": "card__42", "alias": "Users"}]}
        result = await metabase.execute_action(
            "create_model", {"name": "Orders with users", "database_id": 3, "query": query}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        assert mock_context.fetch.call_args_list[0].args[0] == f"{BASE}/api/card/42"

    @pytest.mark.asyncio
    async def test_both_sql_and_query_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "sql": "select 1", "query": SAMPLE_MBQL}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one of sql or query" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_neither_sql_nor_query_refused(self, mock_context):
        result = await metabase.execute_action("create_model", {"name": "X", "database_id": 3}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one of sql or query" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_sql_refused(self, mock_context):
        mock_context.fetch.side_effect = [_database()]
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "sql": "update users set email = null"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Only a single read statement" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_sql_checked_in_database_dialect(self, mock_context):
        # Backticks name a column in MySQL; in standard SQL they don't parse.
        mock_context.fetch.side_effect = [_database("mysql"), _ok({**SAMPLE_CARD, "type": "model"})]
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "sql": "select `id` from `users`"}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_mbql_with_native_refused(self, mock_context):
        query = {"source-table": 12, "source-query": {"native": {"query": "drop table orders"}}}
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_mbql_without_source_table_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "query": {"aggregation": [["count"]]}}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "source-table" in result.result.message

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = [_database(), HTTPError(403, "Forbidden", "You don't have permissions.")]
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "sql": "select 1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "create_model", {"name": "X", "database_id": 3, "query": SAMPLE_MBQL}, mock_context
        )
        assert "Check with search" in result.result.message


METRIC_QUERY = {"source-table": 12, "aggregation": [["sum", ["field", 78, None]]]}

# Metabase before 0.51 has no metric card type and refuses it with HTTP 400.
CARD_TYPE_REFUSED = HTTPError(400, "Bad Request", {"message": "invalid card type"})


def _version(tag):
    """GET /session/properties, which names the Metabase version."""
    return _ok({"version": {"tag": tag}} if tag else {})


class TestCreateMetric:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        metric = {**SAMPLE_MBQL_CARD, "id": 95, "type": "metric", "display": "scalar"}
        mock_context.fetch.return_value = _ok(metric)
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.result.data["type"] == "metric"
        assert result.result.data["id"] == 95

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_MBQL_CARD, "type": "metric"})
        await metabase.execute_action(
            "create_metric",
            {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY, "description": "Sum of order totals"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "name": "Revenue",
            "type": "metric",
            "display": "scalar",
            "visualization_settings": {},
            "dataset_query": {"database": 3, "type": "query", "query": METRIC_QUERY},
            "description": "Sum of order totals",
        }

    @pytest.mark.asyncio
    async def test_display_override(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_MBQL_CARD, "type": "metric"})
        await metabase.execute_action(
            "create_metric",
            {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY, "display": "line"},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["json"]["display"] == "line"

    @pytest.mark.asyncio
    async def test_two_aggregations_refused(self, mock_context):
        query = {"source-table": 12, "aggregation": [["count"], ["sum", ["field", 78, None]]]}
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one aggregation" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_aggregation_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": {"source-table": 12}}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one aggregation" in result.result.message

    @pytest.mark.asyncio
    async def test_aggregation_not_a_list_refused(self, mock_context):
        query = {"source-table": 12, "aggregation": "count"}
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_native_refused(self, mock_context):
        query = {**METRIC_QUERY, "source-query": {"native": "select 1"}}
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "can't contain SQL" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_source_table_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": {"aggregation": [["count"]]}}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "source-table" in result.result.message

    @pytest.mark.asyncio
    async def test_writing_saved_question_source_refused(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls(compiled="delete from t")
        query = {"source-table": "card__42", "aggregation": [["count"]]}
        result = await metabase.execute_action(
            "create_metric", {"name": "User count", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert mock_context.fetch.call_count == 3
        assert f"{BASE}/api/card" not in [c.args[0] for c in mock_context.fetch.call_args_list]

    @pytest.mark.asyncio
    async def test_400_saves_legacy_table_metric(self, mock_context):
        mock_context.fetch.side_effect = [
            CARD_TYPE_REFUSED,
            _version("v0.49.12"),
            _ok({"id": 7, "name": "Revenue", "description": "Sum of order totals", "archived": False}),
        ]
        query = {**METRIC_QUERY, "filter": [">", ["field", 56, None], 0]}
        result = await metabase.execute_action(
            "create_metric",
            {"name": "Revenue", "database_id": 3, "query": query, "description": "Sum of order totals"},
            mock_context,
        )
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["id"] == 7
        assert data["type"] == "legacy_metric"
        assert data["database_id"] == 3
        assert "metric id, not a question id" in data["note"]
        calls = mock_context.fetch.call_args_list
        assert calls[1].args[0] == f"{BASE}/api/session/properties"
        assert calls[1].kwargs["method"] == "GET"
        legacy = calls[2]
        assert legacy.args[0] == f"{BASE}/api/metric"
        assert legacy.kwargs["method"] == "POST"
        assert legacy.kwargs["retry_count"] == NO_RETRY
        assert legacy.kwargs["json"] == {
            "name": "Revenue",
            "table_id": 12,
            "definition": query,
            "description": "Sum of order totals",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tag", ["v1.49.3", "v0.49.25", "1.49.1"])
    async def test_legacy_fallback_on_old_releases(self, mock_context, tag):
        mock_context.fetch.side_effect = [CARD_TYPE_REFUSED, _version(tag), _ok({"id": 8, "name": "Revenue"})]
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.result.data["type"] == "legacy_metric"
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/metric"

    @pytest.mark.asyncio
    # 0.50 already saves metric questions; its old table metrics moved to /api/legacy-metric.
    @pytest.mark.parametrize("tag", ["v0.50.36", "1.50.1", "v0.51.0", "v0.56.3", "v1.52.1", "v1.51.0", None])
    async def test_400_on_newer_or_unknown_version_reports_original_error(self, mock_context, tag):
        mock_context.fetch.side_effect = [CARD_TYPE_REFUSED, _version(tag)]
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Metabase returned HTTP 400: invalid card type"
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_legacy_metric_refuses_extra_query_parts(self, mock_context):
        mock_context.fetch.side_effect = [CARD_TYPE_REFUSED, _version("v0.49.25")]
        query = {**METRIC_QUERY, "joins": [{"source-table": 13, "alias": "Users"}], "breakout": [["field", 34, None]]}
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "not breakout, joins" in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_400_on_saved_question_source_needs_a_table(self, mock_context):
        mock_context.fetch.side_effect = [*_saving_check_calls(), CARD_TYPE_REFUSED, _version("v0.49.25")]
        query = {"source-table": "card__42", "aggregation": [["count"]]}
        result = await metabase.execute_action(
            "create_metric", {"name": "User count", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message
        assert "built on a table" in result.result.message
        assert f"{BASE}/api/metric" not in [c.args[0] for c in mock_context.fetch.call_args_list]

    @pytest.mark.asyncio
    async def test_legacy_metric_404_reports_original_error(self, mock_context):
        mock_context.fetch.side_effect = [
            CARD_TYPE_REFUSED,
            _version("v0.49.25"),
            HTTPError(404, "Not found", "API endpoint does not exist."),
        ]
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Metabase returned HTTP 400: invalid card type"

    @pytest.mark.asyncio
    async def test_legacy_metric_other_error_surfaces(self, mock_context):
        mock_context.fetch.side_effect = [
            CARD_TYPE_REFUSED,
            _version("v0.49.25"),
            HTTPError(403, "Forbidden", {"message": "You don't have permissions to do that."}),
        ]
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message
        assert "You don't have permissions" in result.result.message
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/metric"

    @pytest.mark.asyncio
    async def test_legacy_metric_without_id(self, mock_context):
        mock_context.fetch.side_effect = [CARD_TYPE_REFUSED, _version("v0.49.25"), _ok({"name": "Revenue"})]
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "did not return a metric id" in result.result.message

    @pytest.mark.asyncio
    async def test_other_http_error_has_no_version_hint(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", "You don't have permissions.")
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert "HTTP 403" in result.result.message
        assert "0.51" not in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "create_metric", {"name": "Revenue", "database_id": 3, "query": METRIC_QUERY}, mock_context
        )
        assert "Check with search" in result.result.message


class TestExportQuestionResults:
    @pytest.mark.asyncio
    async def test_csv_happy_path(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        data = result.result.data
        assert data["format"] == "csv"
        assert data["content"] == SAMPLE_CSV.rstrip("\n")
        assert data["row_count"] == 3
        assert data["truncated"] is False

    @pytest.mark.asyncio
    async def test_saved_question_checked_before_export(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        calls = mock_context.fetch.call_args_list
        assert [(c.args[0], c.kwargs["method"]) for c in calls] == [
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/card/42/query/csv", "POST"),
        ]
        assert calls[2].kwargs["json"] == {**SAVED_EXPORT_CARD["dataset_query"], "parameters": [], "pretty": False}

    @pytest.mark.asyncio
    async def test_export_request_is_a_form(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        params = [{"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "EU"}]
        await metabase.execute_action(
            "export_question_results", {"question_id": 42, "parameters": params}, mock_context
        )
        call = mock_context.fetch.call_args
        assert call.kwargs["data"] == {"parameters": json.dumps(params), "format_rows": "false"}
        assert call.kwargs["content_type"] == "application/x-www-form-urlencoded"
        assert call.kwargs["headers"] == {"x-api-key": "mb_test_api_key"}  # nosec B105
        assert "json" not in call.kwargs
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["timeout"] == 120

    @pytest.mark.asyncio
    async def test_check_calls_keep_json_header(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        compile_call = mock_context.fetch.call_args_list[2]
        assert compile_call.kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_saved_filter_defaults_sent(self, mock_context):
        target = ["variable", ["template-tag", "region"]]
        card = {
            **SAVED_EXPORT_CARD,
            "parameters": [{"id": "p1", "type": "category", "target": target, "default": "EU"}],
        }
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV, card=card)
        await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        sent = json.loads(mock_context.fetch.call_args.kwargs["data"]["parameters"])
        assert sent == [{"id": "p1", "type": "category", "target": target, "value": "EU"}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "body",
        ['{"status": "failed", "error": "Table not found"}', ' {"error": "Table not found", "row_count": 0}'],
    )
    async def test_csv_body_with_json_error(self, mock_context, body):
        # Metabase 0.49 answers a failed CSV export with HTTP 200 and the error as JSON text.
        mock_context.fetch.side_effect = _export_calls(body)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Query failed: Table not found"

    @pytest.mark.asyncio
    async def test_csv_body_failed_without_error_text(self, mock_context):
        mock_context.fetch.side_effect = _export_calls('{"status": "failed"}')
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.result.message == "Query failed: unknown error"

    @pytest.mark.asyncio
    async def test_csv_starting_with_brace_is_still_csv(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("{tag},count\nnew,4\n")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["content"] == "{tag},count\nnew,4"

    @pytest.mark.asyncio
    async def test_csv_trailing_empty_records_kept(self, mock_context):
        # A single-column NULL is a blank line in Metabase's CSV; it is a row, not the end of the file.
        mock_context.fetch.side_effect = _export_calls("name\nAlice\n\n\n")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        data = result.result.data
        assert data["row_count"] == 3
        assert list(csv.reader(io.StringIO(data["content"]))) == [["name"], ["Alice"], [""], [""]]
        assert data["truncated"] is False

    @pytest.mark.asyncio
    async def test_csv_bom_stripped(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("﻿" + SAMPLE_CSV)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.result.data["content"].startswith("id,email")

    @pytest.mark.asyncio
    async def test_csv_max_rows_truncates(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "max_rows": 2}, mock_context
        )
        data = result.result.data
        assert data["content"] == "id,email\n1,ana@example.com\n2,ben@example.com"
        assert data["row_count"] == 2
        assert data["truncated"] is True

    @pytest.mark.asyncio
    async def test_csv_exactly_max_rows_not_truncated(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "max_rows": 3}, mock_context
        )
        assert result.result.data["row_count"] == 3
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_csv_header_only(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("id,email\n")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.result.data["row_count"] == 0
        assert result.result.data["content"] == "id,email"

    @pytest.mark.asyncio
    async def test_csv_windows_line_endings(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("id,email\r\n1,ana@example.com\r\n")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.result.data["content"] == "id,email\n1,ana@example.com"
        assert result.result.data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_csv_long_content_cut_and_truncated(self, mock_context):
        big = "id,note\n" + "".join(f"{i},{'x' * 2000}\n" for i in range(600))
        mock_context.fetch.side_effect = _export_calls(big)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        content = result.result.data["content"]
        # Only whole rows are kept, so the content stops at the last row that fits in 1,000,000 characters.
        assert 1_000_000 - 2010 < len(content) <= 1_000_000
        assert content.splitlines()[-1].endswith("x")
        assert result.result.data["row_count"] == len(content.splitlines()) - 1
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_json_rows(self, mock_context):
        rows = [{"id": i, "email": f"user{i}@example.com"} for i in range(5)]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json", "max_rows": 3}, mock_context
        )
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/card/42/query/json"
        data = result.result.data
        assert data == {"format": "json", "rows": rows[:3], "row_count": 3, "truncated": True}

    @pytest.mark.asyncio
    async def test_json_whole_rows_within_size_budget(self, mock_context):
        # Each row is 400,000+ characters as JSON, so only two fit in the 1,000,000-character budget.
        rows = [{"id": i, "note": "x" * 400_000} for i in range(4)]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json"}, mock_context
        )
        data = result.result.data
        assert data["rows"] == rows[:2]
        assert data["row_count"] == 2
        assert data["truncated"] is True

    @pytest.mark.asyncio
    async def test_json_row_exactly_at_budget_kept(self, mock_context):
        padding = 1_000_000 - 1 - len(json.dumps({"note": ""}))
        rows = [{"note": "x" * padding}]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json"}, mock_context
        )
        assert result.result.data["row_count"] == 1
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_json_row_one_over_budget_dropped(self, mock_context):
        padding = 1_000_000 - len(json.dumps({"note": ""}))
        rows = [{"note": "x" * padding}]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json"}, mock_context
        )
        assert result.result.data == {"format": "json", "rows": [], "row_count": 0, "truncated": True}

    @pytest.mark.asyncio
    async def test_csv_large_cell_parsed(self, mock_context):
        cell = "y" * 200_000
        mock_context.fetch.side_effect = _export_calls(f'id,payload\n1,"{cell}"\n2,small\n')
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["row_count"] == 2
        assert data["content"] == f"id,payload\n1,{cell}\n2,small"
        assert data["truncated"] is False

    @pytest.mark.asyncio
    async def test_csv_oversized_cell_past_max_rows_is_left_out(self, mock_context):
        cell = "y" * 1_000_002
        mock_context.fetch.side_effect = _export_calls(f'id,payload\n1,small\n2,"{cell}"\n')
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "max_rows": 1}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "format": "csv",
            "content": "id,payload\n1,small",
            "row_count": 1,
            "truncated": True,
        }

    @pytest.mark.asyncio
    async def test_csv_oversized_first_cell_truncates(self, mock_context):
        cell = "y" * 1_000_002
        mock_context.fetch.side_effect = _export_calls(f'id,payload\n1,"{cell}"\n')
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {"format": "csv", "content": "id,payload", "row_count": 0, "truncated": True}

    @pytest.mark.asyncio
    async def test_json_all_rows(self, mock_context):
        rows = [{"id": 1, "email": "ana@example.com"}]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json"}, mock_context
        )
        assert result.result.data["rows"] == rows
        assert result.result.data["truncated"] is False

    @pytest.mark.asyncio
    async def test_default_max_rows_is_1000(self, mock_context):
        rows = [{"id": i} for i in range(1500)]
        mock_context.fetch.side_effect = _export_calls(rows)
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "json"}, mock_context
        )
        assert result.result.data["row_count"] == 1000
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_writing_saved_question_refused_before_export(self, mock_context):
        mock_context.fetch.side_effect = _export_calls(SAMPLE_CSV, compiled="delete from users")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert mock_context.fetch.call_count == 3
        assert all("/query/" not in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_html_response_rejected(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("<!DOCTYPE html><html><body>Sign in</body></html>")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't JSON" in result.result.message

    @pytest.mark.asyncio
    async def test_html_tag_response_rejected(self, mock_context):
        mock_context.fetch.side_effect = _export_calls("\n  <html><head><title>Login</title></head></html>")
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_csv_header_starting_with_angle_bracket_accepted(self, mock_context):
        csv_text = "<30 days,accounts\n12,40\n"
        mock_context.fetch.side_effect = _export_calls(csv_text)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["content"] == "<30 days,accounts\n12,40"
        assert result.result.data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_invalid_format_rejected(self, mock_context):
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "format": "parquet"}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_xlsx_file(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls()
        download = AsyncMock(return_value=XLSX_BYTES)
        with patch("metabase.metabase._download", download):
            result = await metabase.execute_action(
                "export_question_results", {"question_id": 42, "format": "xlsx"}, mock_context
            )
        assert result.result.data == {
            "format": "xlsx",
            "file": {
                "name": "question-42.xlsx",
                "contentType": XLSX_CONTENT_TYPE,
                "content": base64.b64encode(XLSX_BYTES).decode("ascii"),
            },
            "row_count": None,
            "truncated": False,
        }
        download.assert_awaited_once_with(
            mock_context, "/card/42/query/xlsx", {"parameters": "[]", "format_rows": "false"}
        )

    @pytest.mark.asyncio
    async def test_xlsx_saved_question_checked_first(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls()
        with patch("metabase.metabase._download", AsyncMock(return_value=XLSX_BYTES)):
            await metabase.execute_action(
                "export_question_results", {"question_id": 42, "format": "xlsx"}, mock_context
            )
        assert [c.args[0] for c in mock_context.fetch.call_args_list] == [
            f"{BASE}/api/card/42",
            f"{BASE}/api/database/3",
            f"{BASE}/api/dataset/native",
        ]

    @pytest.mark.asyncio
    async def test_xlsx_refused_question_not_downloaded(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls(compiled="delete from users")
        download = AsyncMock(return_value=XLSX_BYTES)
        with patch("metabase.metabase._download", download):
            result = await metabase.execute_action(
                "export_question_results", {"question_id": 42, "format": "xlsx"}, mock_context
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        download.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_xlsx_download_error(self, mock_context):
        mock_context.fetch.side_effect = _source_check_calls()
        too_big = AsyncMock(side_effect=ValueError("The Excel file is over 3.5 MB, too big to return."))
        with patch("metabase.metabase._download", too_big):
            result = await metabase.execute_action(
                "export_question_results", {"question_id": 42, "format": "xlsx"}, mock_context
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "over 3.5 MB" in result.result.message

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = [
            *_export_calls(SAMPLE_CSV)[:3],
            HTTPError(500, "Server Error", {"message": "Query timed out"}),
        ]
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout(self, mock_context):
        mock_context.fetch.side_effect = [*_export_calls(SAMPLE_CSV)[:3], asyncio.TimeoutError()]
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "did not respond in time" in result.result.message

    @pytest.mark.asyncio
    async def test_csv_multiline_value_counts_as_one_row(self, mock_context):
        csv_text = 'id,note\n1,"Called twice\nleft voicemail"\n2,ok\n'
        mock_context.fetch.side_effect = _export_calls(csv_text)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.result.data["row_count"] == 2

    @pytest.mark.asyncio
    async def test_csv_row_count_matches_cut_content(self, mock_context):
        big = "id,note\n" + "".join(f"{i},{'x' * 2000}\n" for i in range(600))
        mock_context.fetch.side_effect = _export_calls(big)
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        data = result.result.data
        assert data["row_count"] == len(data["content"].splitlines()) - 1


class TestGetRevisionHistory:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tag", ["v0.49.25", "v1.49.3"])
    async def test_legacy_metric_history_refused(self, mock_context, tag):
        mock_context.fetch.side_effect = [_version(tag)]
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "metric", "item_id": 7}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("On Metabase 0.49 a metric's history")
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/session/properties"
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_metric_history_on_newer_release(self, mock_context):
        mock_context.fetch.side_effect = [_version("v1.53.4"), _ok(SAMPLE_REVISIONS)]
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "metric", "item_id": 7}, mock_context
        )
        assert result.result.data["count"] == 2
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/revision?entity=card&id=7"

    @pytest.mark.asyncio
    async def test_question_history_skips_version_check(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVISIONS)
        await metabase.execute_action("get_revision_history", {"item_type": "question", "item_id": 7}, mock_context)
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_segment_falls_back_on_400(self, mock_context):
        mock_context.fetch.side_effect = [
            HTTPError(400, "Bad Request", {"errors": {"entity": "value must be card or dashboard"}}),
            _ok(SAMPLE_REVISIONS),
        ]
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "segment", "item_id": 3}, mock_context
        )
        assert result.result.data["count"] == 2
        fallback = mock_context.fetch.call_args
        assert fallback.args[0] == f"{BASE}/api/segment/3/revisions"
        assert fallback.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_segment_other_status_not_retried(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "Server Error", "boom")
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "segment", "item_id": 3}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("item_type", ["question", "dashboard"])
    async def test_card_and_dashboard_400_not_retried(self, mock_context, item_type):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"message": "Invalid id"})
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": item_type, "item_id": 3}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_REVISIONS)
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "question", "item_id": 42}, mock_context
        )
        data = result.result.data
        assert data["count"] == 2
        assert data["revisions"][0] == {
            "revision_id": 501,
            "description": SAMPLE_REVISIONS[0]["description"],
            "timestamp": "2026-10-30T02:11:09.123Z",
            "user": "Risheet Peri",
            "is_creation": False,
            "is_reversion": False,
            "most_recent": True,
        }
        assert data["revisions"][1]["is_creation"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "item_type,entity",
        [
            ("question", "card"),
            ("model", "card"),
            ("metric", "card"),
            ("dashboard", "dashboard"),
            ("segment", "segment"),
        ],
    )
    async def test_request_entity(self, mock_context, item_type, entity):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("get_revision_history", {"item_type": item_type, "item_id": 7}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/revision?entity={entity}&id=7"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_wrapped_data_and_missing_user(self, mock_context):
        mock_context.fetch.return_value = _ok({"data": [{"id": 3, "description": "edited", "user": None}]})
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "dashboard", "item_id": 5}, mock_context
        )
        revision = result.result.data["revisions"][0]
        assert revision["revision_id"] == 3
        assert revision["user"] is None
        assert revision["most_recent"] is False

    @pytest.mark.asyncio
    async def test_empty(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "segment", "item_id": 5}, mock_context
        )
        assert result.result.data == {"revisions": [], "count": 0}

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected(self, mock_context):
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "collection", "item_id": 5}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action(
            "get_revision_history", {"item_type": "question", "item_id": 404}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestRevertToRevision:
    @pytest.mark.asyncio
    async def test_legacy_metric_revert_refused(self, mock_context):
        mock_context.fetch.side_effect = [_version("v0.49.25")]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "metric", "item_id": 7, "revision_id": 3}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("On Metabase 0.49 a metric's history")
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(CARD_HISTORY),
            _ok({"id": 502, "description": "reverted to an earlier version."}),
            *_saving_check_calls(),
        ]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "model", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data == {
            "item_type": "model",
            "item_id": 42,
            "new_revision_id": 502,
            "description": "reverted to an earlier version.",
        }

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [
            _version("v0.52.3"),
            _ok(CARD_HISTORY),
            _ok({"id": 502}),
            *_saving_check_calls(),
        ]
        await metabase.execute_action(
            "revert_to_revision", {"item_type": "metric", "item_id": 42, "revision_id": 498}, mock_context
        )
        calls = mock_context.fetch.call_args_list
        assert [(c.args[0], c.kwargs["method"]) for c in calls] == [
            (f"{BASE}/api/session/properties", "GET"),
            (f"{BASE}/api/revision?entity=card&id=42", "GET"),
            (f"{BASE}/api/revision/revert", "POST"),
            (f"{BASE}/api/card/42", "GET"),
            (f"{BASE}/api/database/3", "GET"),
            (f"{BASE}/api/dataset/native", "POST"),
            (f"{BASE}/api/dataset/native", "POST"),
        ]
        revert = calls[2]
        assert revert.kwargs["json"] == {"entity": "card", "id": 42, "revision_id": 498}
        assert revert.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_revert_to_write_sql_is_undone(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(CARD_HISTORY),
            _ok({"id": 511}),
            *_source_check_calls(compiled="delete from t"),
            _ok({"id": 512}),
        ]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("Not reverted")
        undo = mock_context.fetch.call_args
        assert undo.args[0] == f"{BASE}/api/revision/revert"
        assert undo.kwargs["method"] == "POST"
        assert undo.kwargs["json"] == {"entity": "card", "id": 42, "revision_id": 510}
        assert mock_context.fetch.call_count == 6
        assert "SQL is refused" in result.result.message

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "failure, detail",
        [
            (HTTPError(500, "Server Error", {"message": "Unknown column"}), "HTTP 500: Unknown column"),
            (asyncio.TimeoutError(), "did not respond in time"),
        ],
    )
    async def test_check_failure_undoes_revert(self, mock_context, failure, detail):
        mock_context.fetch.side_effect = [
            _ok(CARD_HISTORY),
            _ok({"id": 511}),
            _ok(SAVED_EXPORT_CARD),
            _database(),
            failure,
            _ok({"id": 512}),
        ]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("Not reverted: that version's SQL couldn't be checked")
        assert detail in result.result.message
        undo = mock_context.fetch.call_args
        assert undo.args[0] == f"{BASE}/api/revision/revert"
        assert undo.kwargs["json"] == {"entity": "card", "id": 42, "revision_id": 510}

    @pytest.mark.asyncio
    async def test_check_failure_without_current_revision_not_undone(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok([{"id": 498, "most_recent": False}]),
            _ok({"id": 511}),
            *_source_check_calls(compiled="delete from t"),
        ]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 5
        reverts = [c for c in mock_context.fetch.call_args_list if c.args[0].endswith("/revision/revert")]
        assert len(reverts) == 1

    @pytest.mark.asyncio
    async def test_segment_falls_back_on_400(self, mock_context):
        mock_context.fetch.side_effect = [
            HTTPError(400, "Bad Request", {"errors": {"entity": "value must be card or dashboard"}}),
            _ok({"id": 31, "description": "reverted"}),
        ]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "segment", "item_id": 3, "revision_id": 2}, mock_context
        )
        assert result.result.data["new_revision_id"] == 31
        fallback = mock_context.fetch.call_args
        assert fallback.args[0] == f"{BASE}/api/segment/3/revert"
        assert fallback.kwargs["method"] == "POST"
        assert fallback.kwargs["json"] == {"revision_id": 2}
        assert fallback.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_segment_other_status_not_retried(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "segment", "item_id": 3, "revision_id": 2}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_dashboard_400_not_retried(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad Request", {"message": "Invalid revision"})
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "dashboard", "item_id": 5, "revision_id": 8}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid revision" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_dashboard_entity(self, mock_context):
        mock_context.fetch.side_effect = [_ok([]), _ok({"id": 1, "is_superuser": True}), _ok({"id": 9})]
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "dashboard", "item_id": 5, "revision_id": 8}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        # No subscriptions (an admin key sees them all), so nothing is checked.
        assert [c.args[0] for c in mock_context.fetch.call_args_list] == [
            f"{BASE}/api/pulse?dashboard_id=5&archived=false",
            f"{BASE}/api/user/current",
            f"{BASE}/api/revision/revert",
        ]
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/revision/revert"
        assert call.kwargs["json"] == {"entity": "dashboard", "id": 5, "revision_id": 8}

    @staticmethod
    def _subscribed_dashboard(mock_context, sql):
        async def fetch(url, **kwargs):
            if "/api/pulse" in url:
                return _ok([{"id": 15}])
            if "/api/revision?" in url:
                return _ok([{"id": 20, "most_recent": True}, {"id": 8}])
            if url.endswith("/api/dashboard/5"):
                return _ok({"id": 5, "parameters": [], "dashcards": [{"id": 1, "card_id": 42, "card": {"id": 42}}]})
            if url.endswith("/api/card/42"):
                return _ok({"id": 42, "dataset_query": {"database": 1, "type": "native", "native": {"query": sql}}})
            if url.endswith("/api/database/1"):
                return _ok({"id": 1, "engine": "postgres"})
            if url.endswith("/api/dataset/native"):
                return _ok({"query": sql})
            return _ok({"id": 5})

        mock_context.fetch.side_effect = fetch

    @pytest.mark.asyncio
    async def test_subscribed_dashboard_checked_after_revert(self, mock_context):
        self._subscribed_dashboard(mock_context, "select 1")
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "dashboard", "item_id": 5, "revision_id": 8}, mock_context
        )
        assert result.type == ResultType.ACTION
        reverts = [
            c.kwargs["json"] for c in mock_context.fetch.call_args_list if c.args[0].endswith("/revision/revert")
        ]
        assert reverts == [{"entity": "dashboard", "id": 5, "revision_id": 8}]
        assert any(c.args[0].endswith("/api/dataset/native") for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_subscribed_dashboard_put_back_when_old_version_writes(self, mock_context):
        self._subscribed_dashboard(mock_context, "select nextval('audit_seq')")
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "dashboard", "item_id": 5, "revision_id": 8}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "so the dashboard was put back" in result.result.message
        reverts = [
            c.kwargs["json"] for c in mock_context.fetch.call_args_list if c.args[0].endswith("/revision/revert")
        ]
        assert reverts == [
            {"entity": "dashboard", "id": 5, "revision_id": 8},
            {"entity": "dashboard", "id": 5, "revision_id": 20},
        ]

    @pytest.mark.asyncio
    async def test_segment_makes_no_check_calls(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 4})
        await metabase.execute_action(
            "revert_to_revision", {"item_type": "segment", "item_id": 3, "revision_id": 2}, mock_context
        )
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected(self, mock_context):
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "pulse", "item_id": 5, "revision_id": 8}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_revision_id_required(self, mock_context):
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 5}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", {"message": "Revision 1 not found"})
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 1}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Revision 1 not found" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_history_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert "Check with get_revision_history" in result.result.message


class TestQuestionEditingFixes:
    @pytest.mark.asyncio
    async def test_update_question_refuses_a_new_filter(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_FILTERED_CARD), _ok({"id": 3, "engine": "postgres"})]
        result = await metabase.execute_action(
            "update_question", {"question_id": 42, "sql": "select * from t where c = {{country}}"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "{{country}}" in result.result.message
        assert all(c.kwargs["method"] == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_csv_quoted_line_break_kept_whole_when_cut(self, mock_context):
        mock_context.fetch.side_effect = _export_calls('id,note\n1,"a\nb"\n2,ok\n3,x\n')
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "max_rows": 1}, mock_context
        )
        assert result.result.data["content"] == 'id,note\n1,"a\nb"'
        assert result.result.data["row_count"] == 1
        assert result.result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_export_error_object_is_an_error(self, mock_context):
        mock_context.fetch.side_effect = _export_calls({"status": "failed", "error": "Table not found"})
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Table not found" in result.result.message


class _FakeResponse:
    def __init__(self, status=200, content_type=XLSX_CONTENT_TYPE, chunks=(XLSX_BYTES,), text="", rest=b""):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._chunks = chunks
        self._text = text
        self.content = MagicMock()
        self.content.iter_chunked = self._iter_chunked
        self.content.read = AsyncMock(return_value=rest)

    async def _iter_chunked(self, size):
        for chunk in self._chunks:
            yield chunk

    async def text(self, errors="strict"):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _fake_aiohttp(response):
    session = _FakeSession(response)
    return session, patch("metabase.metabase.aiohttp.ClientSession", MagicMock(return_value=session))


FORM = {"parameters": "[]", "format_rows": "false"}


class TestDownload:
    @pytest.mark.asyncio
    async def test_returns_bytes(self, mock_context):
        session, patched = _fake_aiohttp(_FakeResponse(chunks=(b"PK\x03\x04", b"rest")))
        with patched:
            content = await _download(mock_context, "/card/42/query/xlsx", FORM)
        assert content == b"PK\x03\x04rest"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        session, patched = _fake_aiohttp(_FakeResponse())
        with patched:
            await _download(mock_context, "/card/42/query/xlsx", FORM)
        url, kwargs = session.posts[0]
        assert url == f"{BASE}/api/card/42/query/xlsx"
        assert kwargs["data"] == FORM
        assert kwargs["headers"] == {"x-api-key": "mb_test_api_key"}  # nosec B105
        assert kwargs["allow_redirects"] is False
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_over_size_limit(self, mock_context):
        chunk = b"x" * 1_000_000
        session, patched = _fake_aiohttp(_FakeResponse(chunks=(chunk, chunk, chunk, chunk)))
        with patched, pytest.raises(ValueError, match="over 3.5 MB"):
            await _download(mock_context, "/card/42/query/xlsx", FORM)

    @pytest.mark.asyncio
    async def test_json_body_is_a_failed_query(self, mock_context):
        response = _FakeResponse(content_type="application/json", text='{"error": "Table not found"}')
        session, patched = _fake_aiohttp(response)
        with patched, pytest.raises(ValueError, match="Query failed: .*Table not found"):
            await _download(mock_context, "/card/42/query/xlsx", FORM)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [403, 500])
    async def test_error_status(self, mock_context, status):
        session, patched = _fake_aiohttp(_FakeResponse(status=status, text='{"message": "Denied"}'))
        with patched, pytest.raises(HTTPError) as caught:
            await _download(mock_context, "/card/42/query/xlsx", FORM)
        assert caught.value.status == status
        assert caught.value.response_data == {"message": "Denied"}

    @pytest.mark.asyncio
    async def test_redirect_refused(self, mock_context):
        session, patched = _fake_aiohttp(_FakeResponse(status=302, text=""))
        with patched, pytest.raises(ValueError, match="Metabase redirected"):
            await _download(mock_context, "/card/42/query/xlsx", FORM)

    @pytest.mark.asyncio
    async def test_long_error_body_parsed_in_full(self, mock_context):
        body = json.dumps({"message": "Denied", "stacktrace": ["frame"] * 300})
        session, patched = _fake_aiohttp(_FakeResponse(status=500, text=body))
        with patched, pytest.raises(HTTPError) as caught:
            await _download(mock_context, "/card/42/query/xlsx", FORM)
        assert caught.value.response_data["message"] == "Denied"
        assert len(caught.value.message) <= 500

    @pytest.mark.asyncio
    async def test_json_error_under_spreadsheet_type(self, mock_context):
        # Metabase 0.49 sends a failed export's error as JSON with the spreadsheet content type.
        response = _FakeResponse(chunks=(b'{"error": "Table ',), rest=b'not found", "status": "failed"}')
        session, patched = _fake_aiohttp(response)
        with patched, pytest.raises(ValueError, match="Query failed: Table not found"):
            await _download(mock_context, "/card/42/query/xlsx", FORM)

    @pytest.mark.asyncio
    async def test_error_status_with_text_body(self, mock_context):
        session, patched = _fake_aiohttp(_FakeResponse(status=502, text="Bad gateway"))
        with patched, pytest.raises(HTTPError) as caught:
            await _download(mock_context, "/card/42/query/xlsx", FORM)
        assert caught.value.response_data == "Bad gateway"


P_TARGET = ["variable", ["template-tag", "p"]]

# A question whose write only appears when its optional clause is filled in.
OPTIONAL_WRITE_CARD = {
    "id": 42,
    "name": "Cleanup",
    "database_id": 3,
    "parameters": [],
    "dataset_query": {
        "database": 3,
        "type": "native",
        "native": {
            "query": "select 1 [[; delete from t where x = {{p}}]]",
            "template-tags": {"p": {"id": "t1", "name": "p", "display-name": "P", "type": "text"}},
        },
    },
}


def _route(mock_context, when_set, when_unset="select 1", card=OPTIONAL_WRITE_CARD):
    """Answer like Metabase: the expanded SQL depends on whether filter p is set (by its real target)."""

    async def fetch(url, method="GET", **kwargs):
        if url.endswith("/dataset/native"):
            is_set = any(isinstance(p, dict) and p.get("target") == P_TARGET for p in kwargs["json"]["parameters"])
            answer = when_set if is_set else when_unset
            if isinstance(answer, Exception):
                raise answer
            return _compiled(answer)
        if "/query/" in url:
            return _ok("x\n1\n")
        if "/revision?" in url:
            return _ok(CARD_HISTORY)
        if url.endswith("/revision/revert"):
            return _ok({"id": 600})
        if url.endswith("/copy"):
            return _ok(SAMPLE_COPY)
        if "/card/" in url:
            return _ok(card)
        if "/database/" in url:
            return _database()
        raise AssertionError(url)

    mock_context.fetch.side_effect = fetch


def _compile_calls(mock_context):
    return [c for c in mock_context.fetch.call_args_list if c.args[0].endswith("/dataset/native")]


class TestSavedQuestionCheck:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "param",
        [
            {"id": "t1", "type": "category", "value": "EU"},
            {"id": "t1", "type": "category", "target": ["variable", ["template-tag", "decoy"]], "value": "EU"},
        ],
    )
    async def test_run_by_id_checked_with_real_target(self, mock_context, param):
        _route(mock_context, when_set="select 1; delete from t where x = 'EU'")
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "parameters": [param]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert _compile_calls(mock_context)[0].kwargs["json"]["parameters"][0]["target"] == P_TARGET
        assert all("/query/" not in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_run_by_id_sends_real_target(self, mock_context):
        _route(mock_context, when_set="select 1 where x = 'EU'")
        decoy = {"id": "t1", "type": "category", "target": ["variable", ["template-tag", "decoy"]], "value": "EU"}
        result = await metabase.execute_action(
            "export_question_results", {"question_id": 42, "parameters": [decoy]}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        sent = json.loads(mock_context.fetch.call_args.kwargs["data"]["parameters"])
        assert sent == [{**decoy, "target": P_TARGET}]

    @pytest.mark.asyncio
    async def test_copy_refused_when_optional_clause_writes(self, mock_context):
        _route(mock_context, when_set="select 1; delete from t where x = 'x'")
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42 wasn't run" in result.result.message
        assert all("/copy" not in c.args[0] for c in mock_context.fetch.call_args_list)
        stand_in = _compile_calls(mock_context)[0].kwargs["json"]["parameters"]
        assert stand_in == [{"type": "category", "target": P_TARGET, "value": "x"}]

    @pytest.mark.asyncio
    async def test_revert_undone_when_optional_clause_writes(self, mock_context):
        _route(mock_context, when_set="select 1; delete from t where x = 'x'")
        result = await metabase.execute_action(
            "revert_to_revision", {"item_type": "question", "item_id": 42, "revision_id": 498}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "SQL is refused" in result.result.message
        reverts = [c for c in mock_context.fetch.call_args_list if c.args[0].endswith("/revision/revert")]
        assert [c.kwargs["json"]["revision_id"] for c in reverts] == [498, 510]

    @pytest.mark.asyncio
    async def test_create_on_question_with_optional_write_refused(self, mock_context):
        _route(mock_context, when_set="select 1; delete from t where x = 'x'")
        query = {"source-table": "card__42", "aggregation": [["count"]]}
        result = await metabase.execute_action(
            "create_model", {"name": "Counts", "database_id": 3, "query": query}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert f"{BASE}/api/card" not in [c.args[0] for c in mock_context.fetch.call_args_list]

    @pytest.mark.asyncio
    async def test_copy_required_filter_without_default(self, mock_context):
        # Metabase can't expand a question whose required filter has no value, so the plain expansion fails.
        card = {
            **OPTIONAL_WRITE_CARD,
            "dataset_query": {
                "database": 3,
                "type": "native",
                "native": {
                    "query": "select * from t where x = {{p}}",
                    "template-tags": {"p": {"id": "t1", "name": "p", "type": "text", "required": True}},
                },
            },
        }
        _route(
            mock_context,
            when_set="select * from t where x = 'x'",
            when_unset=HTTPError(500, "Server Error", {"message": "missing required parameter"}),
            card=card,
        )
        result = await metabase.execute_action("copy_question", {"question_id": 42}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["id"] == 77
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/card/42/copy"

    @pytest.mark.asyncio
    async def test_run_does_not_ignore_expansion_error(self, mock_context):
        _route(mock_context, when_set="select 1", when_unset=HTTPError(500, "Server Error", {"message": "boom"}))
        result = await metabase.execute_action("export_question_results", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message
