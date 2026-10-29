import asyncio

import pytest
from unittest.mock import MagicMock
from autohive_integrations_sdk import HTTPError

from metabase.metabase import (
    _card_summary,
    _clamp,
    _ensure_read_only_sql,
    _error_message,
    _page,
    _query_result,
    _unique_names,
    _with_query,
    get_auth_headers,
    get_base_url,
)

pytestmark = pytest.mark.unit


def _ctx(credentials):
    ctx = MagicMock()
    ctx.auth = {"auth_type": "Custom", "credentials": credentials}
    return ctx


class TestGetBaseUrl:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("https://metabase.test", "https://metabase.test"),
            ("https://metabase.test/", "https://metabase.test"),
            ("  https://metabase.test  ", "https://metabase.test"),
            ("https://metabase.test/api", "https://metabase.test"),
            ("https://metabase.test/api/", "https://metabase.test"),
            ("https://example.com/metabase", "https://example.com/metabase"),
            ("https://example.com/metabase/api", "https://example.com/metabase"),
        ],
    )
    def test_normalises(self, raw, expected):
        assert get_base_url(_ctx({"base_url": raw, "api_key": "k"})) == expected  # nosec B105

    @pytest.mark.parametrize(
        "raw, message",
        [
            ("", "base_url is required"),
            ("http://metabase.test", "https://"),
            ("metabase.test", "https://"),
            ("https://user:pw@metabase.test", "username or password"),
            ("https://metabase.test?x=1", "query string"),
            ("https://metabase.test#frag", "query string or fragment"),
        ],
    )
    def test_rejects(self, raw, message):
        with pytest.raises(ValueError, match=message):
            get_base_url(_ctx({"base_url": raw, "api_key": "k"}))  # nosec B105

    def test_flat_auth_shape_supported(self):
        ctx = MagicMock()
        ctx.auth = {"base_url": "https://metabase.test", "api_key": "k"}  # nosec B105
        assert get_base_url(ctx) == "https://metabase.test"


class TestAuthHeaders:
    def test_uses_x_api_key(self):
        headers = get_auth_headers(_ctx({"base_url": "https://m.test", "api_key": " mb_key "}))  # nosec B105
        assert headers == {"x-api-key": "mb_key", "Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="api_key is required"):
            get_auth_headers(_ctx({"base_url": "https://m.test"}))


class TestErrorMessage:
    def test_http_error_with_error_field(self):
        err = HTTPError(400, "raw", {"error": "relation does not exist", "status": "failed"})
        assert _error_message(err) == "Metabase returned HTTP 400: relation does not exist"

    def test_http_error_with_message_field(self):
        err = HTTPError(403, "raw", {"message": "You don't have permissions to do that."})
        assert "HTTP 403" in _error_message(err)
        assert "permissions" in _error_message(err)

    def test_http_error_plain_text(self):
        assert _error_message(HTTPError(401, "Unauthenticated", "Unauthenticated")) == (
            "Metabase returned HTTP 401: Unauthenticated"
        )

    def test_long_error_page_truncated(self):
        message = _error_message(HTTPError(502, "<html>" + "x" * 5000, "<html>" + "x" * 5000))
        assert message.startswith("Metabase returned HTTP 502: <html>")
        assert len(message) == 500

    def test_timeout(self):
        assert "did not respond in time" in _error_message(asyncio.TimeoutError())

    def test_other_exception(self):
        assert _error_message(ValueError("boom")) == "boom"


class TestPagingHelpers:
    @pytest.mark.parametrize(
        "value, expected",
        [(None, 50), (0, 50), (-3, 50), (True, 50), ("10", 50), (10, 10), (200, 200), (500, 200)],
    )
    def test_clamp(self, value, expected):
        assert _clamp(value, 50, 200) == expected

    def test_page_defaults(self):
        assert _page({}) == {"limit": 50, "offset": 0}

    def test_page_values(self):
        assert _page({"limit": 5, "offset": 10}) == {"limit": 5, "offset": 10}

    def test_page_negative_offset(self):
        assert _page({"offset": -1})["offset"] == 0

    def test_with_query_repeats_keys(self):
        url = _with_query("https://m.test/api/search", [("q", "rev"), ("models", "card"), ("models", "dashboard")])
        assert url == "https://m.test/api/search?q=rev&models=card&models=dashboard"

    def test_with_query_drops_none(self):
        assert _with_query("https://m.test/x", [("q", None)]) == "https://m.test/x"


class TestQueryResult:
    def test_rows_become_objects(self):
        data = {
            "status": "completed",
            "data": {"cols": [{"name": "a", "display_name": "A", "base_type": "type/Integer"}], "rows": [[1], [2]]},
        }
        result = _query_result(data, 100)
        assert result["rows"] == [{"a": 1}, {"a": 2}]
        assert result["columns"] == [{"name": "a", "display_name": "A", "base_type": "type/Integer"}]
        assert result["row_count"] == 2
        assert result["truncated"] is False

    def test_max_rows_truncates(self):
        data = {"status": "completed", "data": {"cols": [{"name": "a"}], "rows": [[i] for i in range(5)]}}
        result = _query_result(data, 2)
        assert result["row_count"] == 2
        assert result["total_row_count"] == 5
        assert result["truncated"] is True

    def test_metabase_row_limit_flag(self):
        data = {"status": "completed", "data": {"cols": [{"name": "a"}], "rows": [[1]], "rows_truncated": 2000}}
        assert _query_result(data, 100)["truncated"] is True

    def test_failed_status_raises(self):
        with pytest.raises(ValueError, match="Query failed: bad sql"):
            _query_result({"status": "failed", "error": "bad sql"}, 100)

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="unexpected"):
            _query_result("oops", 100)

    def test_unique_names(self):
        assert _unique_names([{"name": "id"}, {"name": "id"}, {"display_name": "X"}, {}]) == [
            "id",
            "id_2",
            "X",
            "column_4",
        ]


class TestUniqueNamesCollision:
    def test_generated_suffix_never_reuses_a_real_name(self):
        assert _unique_names([{"name": "id"}, {"name": "id"}, {"name": "id_2"}]) == ["id", "id_3", "id_2"]

    def test_rows_keep_every_column(self):
        data = {
            "status": "completed",
            "data": {"cols": [{"name": "id"}, {"name": "id"}, {"name": "id_2"}], "rows": [[1, 2, 3]]},
        }
        assert _query_result(data, 10)["rows"] == [{"id": 1, "id_3": 2, "id_2": 3}]


class TestCardSummary:
    def test_legacy_native_sql(self):
        card = {
            "id": 1,
            "name": "Q",
            "dataset_query": {"database": 3, "type": "native", "native": {"query": "select 1"}},
        }
        summary = _card_summary(card)
        assert summary["native_sql"] == "select 1"
        assert summary["database_id"] == 3

    def test_mbql5_native_sql(self):
        card = {
            "id": 1,
            "name": "Q",
            "database_id": 3,
            "dataset_query": {"lib/type": "mbql/query", "database": 3, "stages": [{"native": "select 2"}]},
        }
        assert _card_summary(card)["native_sql"] == "select 2"

    def test_gui_question_has_no_sql(self):
        card = {"id": 1, "name": "Q", "dataset_query": {"stages": [{"source-table": 5}]}}
        assert _card_summary(card)["native_sql"] is None

    def test_filters_from_mbql5_template_tags_when_parameters_empty(self):
        card = {
            "id": 1,
            "name": "Q",
            "parameters": [],
            "dataset_query": {
                "stages": [
                    {
                        "native": "select 1",
                        "template-tags": [
                            {
                                "id": "t1",
                                "name": "date",
                                "display-name": "Date",
                                "type": "dimension",
                                "widget-type": "date/all-options",
                                "dimension": ["field", {}, 5],
                            },
                            {
                                "id": "t2",
                                "name": "region",
                                "display-name": "Region",
                                "type": "text",
                                "required": True,
                                "default": "EU",
                            },
                        ],
                    }
                ]
            },
        }
        assert _card_summary(card)["parameters"] == [
            {
                "id": "t1",
                "slug": "date",
                "name": "Date",
                "type": "date/all-options",
                "widget_type": "date/all-options",
                "required": False,
                "default": None,
                "target": ["dimension", ["template-tag", "date"]],
            },
            {
                "id": "t2",
                "slug": "region",
                "name": "Region",
                "type": "text",
                "widget_type": None,
                "required": True,
                "default": "EU",
                "target": ["variable", ["template-tag", "region"]],
            },
        ]

    def test_filters_from_legacy_template_tags(self):
        card = {
            "id": 1,
            "name": "Q",
            "dataset_query": {
                "type": "native",
                "native": {"query": "select 1", "template-tags": {"n": {"id": "t", "name": "n", "type": "number"}}},
            },
        }
        params = _card_summary(card)["parameters"]
        assert [(p["slug"], p["target"]) for p in params] == [("n", ["variable", ["template-tag", "n"]])]

    def test_explicit_parameters_win(self):
        card = {
            "id": 1,
            "name": "Q",
            "parameters": [{"id": "p1", "slug": "region"}],
            "dataset_query": {
                "stages": [{"native": "x", "template-tags": [{"id": "p1", "name": "region", "type": "text"}]}]
            },
        }
        assert _card_summary(card)["parameters"] == [{"id": "p1", "slug": "region"}]

    def test_template_tags_missing_from_explicit_parameters_are_added(self):
        card = {
            "id": 1,
            "name": "Q",
            "parameters": [{"id": "p1", "slug": "region"}],
            "dataset_query": {
                "stages": [
                    {
                        "native": "x",
                        "template-tags": [
                            {"id": "p1", "name": "region", "type": "text"},
                            {"id": "p2", "name": "cutoff", "type": "date", "required": True},
                        ],
                    }
                ]
            },
        }
        params = _card_summary(card)["parameters"]
        assert [p["slug"] for p in params] == ["region", "cutoff"]
        assert params[1]["required"] is True

    def test_template_tag_matched_by_slug_is_not_duplicated(self):
        card = {
            "id": 1,
            "name": "Q",
            "parameters": [{"id": "p1", "slug": "region"}],
            "dataset_query": {"stages": [{"native": "x", "template-tags": [{"name": "region", "type": "text"}]}]},
        }
        assert _card_summary(card)["parameters"] == [{"id": "p1", "slug": "region"}]

    def test_template_tag_without_id_kept_when_explicit_parameter_has_no_id(self):
        card = {
            "id": 1,
            "name": "Q",
            "parameters": [{"slug": "region"}],
            "dataset_query": {"native": {"query": "x", "template-tags": {"n": {"name": "n", "type": "number"}}}},
        }
        assert [p["slug"] for p in _card_summary(card)["parameters"]] == ["region", "n"]

    def test_temporal_unit_tag_targets_dimension(self):
        card = {
            "id": 1,
            "name": "Q",
            "dataset_query": {
                "stages": [
                    {
                        "native": "x",
                        "template-tags": [{"id": "t", "name": "unit", "type": "temporal-unit", "default": "month"}],
                    }
                ]
            },
        }
        param = _card_summary(card)["parameters"][0]
        assert (param["type"], param["target"]) == ("temporal-unit", ["dimension", ["template-tag", "unit"]])

    def test_field_filter_without_widget_type_uses_category(self):
        card = {
            "id": 1,
            "name": "Q",
            "dataset_query": {
                "stages": [
                    {
                        "native": "x",
                        "template-tags": [
                            {"id": "t", "name": "region", "type": "dimension", "dimension": ["field", {}, 7]}
                        ],
                    }
                ]
            },
        }
        param = _card_summary(card)["parameters"][0]
        assert (param["type"], param["target"]) == ("category", ["dimension", ["template-tag", "region"]])

    def test_variable_widget_type_preferred(self):
        card = {
            "id": 1,
            "name": "Q",
            "dataset_query": {
                "stages": [
                    {
                        "native": "x",
                        "template-tags": [{"id": "t", "name": "n", "type": "number", "widget-type": "number/="}],
                    }
                ]
            },
        }
        assert _card_summary(card)["parameters"][0]["type"] == "number/="


class TestReadOnlySql:
    @pytest.mark.parametrize(
        "sql",
        [
            "select 1",
            "  SELECT * FROM t",
            "with x as (select 1) select * from x",
            "with x as (select last_update, deleted_at from t) select * from x",
            "with x as (select 'delete' as action) select * from x",
            "select 'insert into' as label, intomark from t",
            "-- note\nselect 1",
            "/* hi */ select 1",
            "(select 1) union (select 2)",
            "explain select 1",
            "explain (format json) select 1",
            "explain select analyze_count from t",
            "show tables",
            "describe t",
            "values (1)",
            "select 1;",
            "select ';' as separator",
            "select 'it''s; fine'",
            'select 1 as "a;b"',
            "select 1 /* explain; only */",
            "select 1; -- trailing note",
            "select 1 -- note; with semicolon\nfrom t",
        ],
    )
    def test_allowed(self, sql):
        assert _ensure_read_only_sql(sql) == sql

    @pytest.mark.parametrize(
        "sql",
        [
            "update t set a = 1",
            "DELETE FROM t",
            "insert into t values (1)",
            "drop table t",
            "-- select\ntruncate t",
            "/* select */ alter table t add c int",
            "grant all on t to x",
            "create table x as select 1",
            "select 1; drop table t",
            "select ';'; drop table t",
            "select 1 /* ; */; delete from t",
            "select 'a\\''; drop table t; -- '",
            "select 'a\\'; drop table t; --'",
            "EXPLAIN ANALYZE DELETE FROM users",
            "explain analyse update t set a = 1",
            "explain (analyze, buffers) insert into t values (1)",
            "explain (ANALYZE true) select 1",
            "explain /* x */ analyze delete from t",
            "/* note */ (explain analyze delete from t)",
            "/* outer /* inner */ SELECT 1 */ DELETE FROM users",
            "select 1 /* a /* b */ c */",
            "WITH removed AS (DELETE FROM users RETURNING *) SELECT * FROM removed",
            "with x as (update t set a = 1 returning a) select * from x",
            "with x as (insert into t values (1) returning *) select 1",
            "with x as (select 1) merge into t using x on true when matched then delete",
            "SELECT * INTO backup FROM users",
            "select a into temp t2 from t",
            "with x as (select 1 as a) select a into t2 from x",
        ],
    )
    def test_rejected(self, sql):
        with pytest.raises(ValueError, match="read-only"):
            _ensure_read_only_sql(sql)
