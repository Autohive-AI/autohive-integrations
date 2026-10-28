import pytest
from unittest.mock import MagicMock
from autohive_integrations_sdk import HTTPError

from metabase.metabase import (
    _card_summary,
    _clamp,
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
