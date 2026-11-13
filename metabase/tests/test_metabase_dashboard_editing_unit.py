import asyncio
import json
import re
import sys

import pytest
from autohive_integrations_sdk import HTTPError, ResultType

from metabase.metabase import NO_RETRY, metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


SQL_DATASET_QUERY = {
    "database": 1,
    "type": "native",
    "native": {
        "query": "select region, count(*) from orders where {{region}} and {{category}} group by 1",
        "template-tags": {
            "region": {"name": "region", "display-name": "Region", "type": "text"},
            "category": {"name": "category", "display-name": "Category", "type": "dimension"},
        },
    },
}
MBQL_DATASET_QUERY = {"database": 1, "type": "query", "query": {"source-table": 3, "aggregation": [["count"]]}}

SQL_DASHCARD = {
    "id": 501,
    "card_id": 42,
    "card": {"id": 42, "name": "Orders by region", "display": "bar", "dataset_query": SQL_DATASET_QUERY},
    "dashboard_id": 9,
    "dashboard_tab_id": 11,
    "row": 0,
    "col": 0,
    "size_x": 12,
    "size_y": 6,
    "series": [],
    "parameter_mappings": [{"parameter_id": "p1", "card_id": 42, "target": ["variable", ["template-tag", "region"]]}],
    "visualization_settings": {"graph.dimensions": ["region"]},
    "created_at": "2026-10-01T00:00:00Z",
    "entity_id": "abc",
}
TEXT_DASHCARD = {
    "id": 502,
    "card_id": None,
    "card": None,
    "dashboard_tab_id": 11,
    "row": 6,
    "col": 0,
    "size_x": 24,
    "size_y": 2,
    "series": [],
    "parameter_mappings": [],
    "visualization_settings": {"text": "## Notes"},
}
MBQL_DASHCARD = {
    "id": 503,
    "card_id": 43,
    "card": {"id": 43, "name": "Order count", "display": "scalar", "dataset_query": MBQL_DATASET_QUERY},
    "dashboard_tab_id": 12,
    "row": 0,
    "col": 0,
    "size_x": 6,
    "size_y": 6,
    "series": [{"id": 44, "name": "Refund count", "display": "scalar"}],
    "parameter_mappings": [{"parameter_id": "p2", "card_id": 43, "target": ["dimension", ["field", 8, None]]}],
    "visualization_settings": {},
}
RESTRICTED_LINK_DASHCARD = {
    "id": 504,
    "card_id": None,
    "card": None,
    "dashboard_tab_id": 12,
    "row": 6,
    "col": 0,
    "size_x": 8,
    "size_y": 1,
    "series": [],
    "parameter_mappings": [],
    "visualization_settings": {"link": {"entity": {"restricted": True}}},
}
SAMPLE_TABS = [
    {"id": 11, "name": "Overview", "position": 0, "entity_id": "t1"},
    {"id": 12, "name": "Details", "position": 1, "entity_id": "t2"},
]
TABS_FOR_PUT = [{"id": 11, "name": "Overview"}, {"id": 12, "name": "Details"}]
SAMPLE_PARAMETERS = [
    {
        "id": "p1",
        "name": "Region",
        "slug": "region",
        "type": "string/=",
        "sectionId": "string",
        "default": ["West"],
        "values_query_type": "list",
    },
    {"id": "p2", "name": "Category", "slug": "category", "type": "category", "sectionId": "category"},
]
SAMPLE_DASHBOARD = {
    "id": 9,
    "name": "Sales",
    "description": "Weekly sales",
    "collection_id": 4,
    "width": "fixed",
    "auto_apply_filters": True,
    "archived": False,
    "tabs": SAMPLE_TABS,
    "parameters": SAMPLE_PARAMETERS,
    "dashcards": [SQL_DASHCARD, TEXT_DASHCARD, MBQL_DASHCARD, RESTRICTED_LINK_DASHCARD],
}
UNTABBED_DASHBOARD = {
    **SAMPLE_DASHBOARD,
    "tabs": [],
    "dashcards": [{**SQL_DASHCARD, "dashboard_tab_id": None}, {**TEXT_DASHCARD, "dashboard_tab_id": None}],
}


def _put_body(mock_context):
    return mock_context.fetch.call_args_list[-1].kwargs["json"]


def _put_dashcard(mock_context, dashcard_id):
    return next(dc for dc in _put_body(mock_context)["dashcards"] if dc["id"] == dashcard_id)


# ---- Dashboard details ----


class TestUpdateDashboard:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_DASHBOARD, "name": "Sales (weekly)"})
        result = await metabase.execute_action(
            "update_dashboard", {"dashboard_id": 9, "name": "Sales (weekly)"}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["name"] == "Sales (weekly)"
        assert result.result.data["tabs"] == TABS_FOR_PUT
        assert [c["dashcard_id"] for c in result.result.data["cards"]] == [501, 502, 503, 504]

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_DASHBOARD)
        await metabase.execute_action(
            "update_dashboard",
            {"dashboard_id": 9, "description": "Q4", "collection_id": 7, "width": "full", "auto_apply_filters": False},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/dashboard/9"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["json"] == {
            "description": "Q4",
            "collection_id": 7,
            "width": "full",
            "auto_apply_filters": False,
        }
        assert call.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_nothing_to_change(self, mock_context):
        result = await metabase.execute_action("update_dashboard", {"dashboard_id": 9}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_description_clears_it(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_DASHBOARD, "description": None})
        await metabase.execute_action("update_dashboard", {"dashboard_id": 9, "description": ""}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"description": None}

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("update_dashboard", {"dashboard_id": 9, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message
        assert "permissions" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action("update_dashboard", {"dashboard_id": 9, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with get_dashboard" in result.result.message


# ---- Dashboard cards ----


class TestUpdateDashboardCards:
    @pytest.mark.asyncio
    async def test_same_card_twice_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards",
            {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 0}, {"dashcard_id": 501, "remove": True}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "listed once" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_move_and_resize(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards",
            {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 2, "col": 12, "width": 12, "height": 4}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        moved = _put_dashcard(mock_context, 501)
        assert (moved["row"], moved["col"], moved["size_x"], moved["size_y"]) == (2, 12, 12, 4)

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 3}]}, mock_context
        )
        get, put = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/dashboard/9"
        assert get.kwargs["method"] == "GET"
        assert put.args[0] == f"{BASE}/api/dashboard/9"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["retry_count"] == NO_RETRY
        assert put.kwargs["json"]["tabs"] == TABS_FOR_PUT
        assert [dc["id"] for dc in put.kwargs["json"]["dashcards"]] == [501, 502, 503, 504]

    @pytest.mark.asyncio
    async def test_unchanged_cards_sent_back_without_read_only_fields(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 502, "row": 7}]}, mock_context
        )
        sql = _put_dashcard(mock_context, 501)
        assert "card" not in sql and "created_at" not in sql and "entity_id" not in sql
        assert sql["parameter_mappings"] == SQL_DASHCARD["parameter_mappings"]
        assert _put_dashcard(mock_context, 503)["series"] == [{"id": 44}]

    @pytest.mark.asyncio
    async def test_restricted_link_settings_not_sent_back(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 1}]}, mock_context
        )
        link = _put_dashcard(mock_context, 504)
        assert "visualization_settings" not in link
        assert link["size_x"] == 8

    @pytest.mark.asyncio
    async def test_unknown_dashcard(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 999, "row": 1}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "999" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_card_outside_grid(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "col": 20}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "24-column grid" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_widening_past_grid_edge(self, mock_context):
        placed = {**SAMPLE_DASHBOARD, "dashcards": [{**SQL_DASHCARD, "col": 12}]}
        mock_context.fetch.side_effect = [_ok(placed)]
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "width": 16}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "24-column grid" in result.result.message

    @pytest.mark.asyncio
    async def test_move_to_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "tab_id": 12}]}, mock_context
        )
        assert _put_dashcard(mock_context, 501)["dashboard_tab_id"] == 12

    @pytest.mark.asyncio
    async def test_unknown_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "tab_id": 99}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "tab_id 99" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_title_kept_with_other_settings(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards",
            {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "title": "Orders by sales region"}]},
            mock_context,
        )
        assert _put_dashcard(mock_context, 501)["visualization_settings"] == {
            "graph.dimensions": ["region"],
            "card.title": "Orders by sales region",
        }

    @pytest.mark.asyncio
    async def test_title_on_restricted_link_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_cards",
            {"dashboard_id": 9, "cards": [{"dashcard_id": 504, "title": "Docs"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "can't be retitled" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_remove_drops_card(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 502, "remove": True}]}, mock_context
        )
        assert [dc["id"] for dc in _put_body(mock_context)["dashcards"]] == [501, 503, 504]

    @pytest.mark.asyncio
    async def test_untabbed_dashboard_sends_no_tabs(self, mock_context):
        mock_context.fetch.side_effect = [_ok(UNTABBED_DASHBOARD), _ok(UNTABBED_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 2}]}, mock_context
        )
        assert "tabs" not in _put_body(mock_context)

    @pytest.mark.asyncio
    async def test_http_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 999, "cards": [{"dashcard_id": 501, "row": 1}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "update_dashboard_cards", {"dashboard_id": 9, "cards": [{"dashcard_id": 501, "row": 1}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with get_dashboard" in result.result.message


class TestAddTextToDashboard:
    @staticmethod
    def _updated(new_id=505):
        return {**SAMPLE_DASHBOARD, "dashcards": SAMPLE_DASHBOARD["dashcards"] + [{"id": new_id, "card_id": None}]}

    @pytest.mark.asyncio
    async def test_text_card_below_first_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "## Q4 notes"}, mock_context
        )
        assert result.result.data == {
            "dashboard_id": 9,
            "dashcard_id": 505,
            "kind": "text",
            "row": 8,
            "col": 0,
            "size_x": 24,
            "size_y": 3,
        }
        new = _put_body(mock_context)["dashcards"][-1]
        assert new["id"] == -1
        assert new["card_id"] is None
        assert new["dashboard_tab_id"] == 11
        assert new["visualization_settings"]["text"] == "## Q4 notes"
        assert new["visualization_settings"]["virtual_card"]["display"] == "text"

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "heading", "text": "Revenue"}, mock_context
        )
        put = mock_context.fetch.call_args_list[1]
        assert put.args[0] == f"{BASE}/api/dashboard/9"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["retry_count"] == NO_RETRY
        assert put.kwargs["json"]["tabs"] == TABS_FOR_PUT
        assert [dc["id"] for dc in put.kwargs["json"]["dashcards"]] == [501, 502, 503, 504, -1]

    @pytest.mark.asyncio
    async def test_heading_defaults(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "heading", "text": "Revenue"}, mock_context
        )
        assert (result.result.data["size_x"], result.result.data["size_y"]) == (24, 1)
        assert (
            _put_body(mock_context)["dashcards"][-1]["visualization_settings"]["virtual_card"]["display"] == "heading"
        )

    @pytest.mark.asyncio
    async def test_link_card_on_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_text_to_dashboard",
            {"dashboard_id": 9, "kind": "link", "url": "https://example.com/runbook", "tab_id": 12},
            mock_context,
        )
        assert (result.result.data["row"], result.result.data["size_x"], result.result.data["size_y"]) == (7, 8, 1)
        new = _put_body(mock_context)["dashcards"][-1]
        assert new["dashboard_tab_id"] == 12
        assert new["visualization_settings"]["link"] == {"url": "https://example.com/runbook"}
        assert "text" not in new["visualization_settings"]

    @pytest.mark.asyncio
    async def test_explicit_position(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_text_to_dashboard",
            {"dashboard_id": 9, "kind": "text", "text": "Hi", "row": 0, "col": 12, "width": 12, "height": 4},
            mock_context,
        )
        assert result.result.data["row"] == 0
        new = _put_body(mock_context)["dashcards"][-1]
        assert (new["row"], new["col"], new["size_x"], new["size_y"]) == (0, 12, 12, 4)

    @pytest.mark.asyncio
    async def test_untabbed_dashboard(self, mock_context):
        mock_context.fetch.side_effect = [_ok(UNTABBED_DASHBOARD), _ok(UNTABBED_DASHBOARD)]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "Hi"}, mock_context
        )
        assert result.result.data["row"] == 8
        assert result.result.data["dashcard_id"] is None
        body = _put_body(mock_context)
        assert "tabs" not in body
        assert "dashboard_tab_id" not in body["dashcards"][-1]

    @pytest.mark.asyncio
    async def test_link_needs_url(self, mock_context):
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "link", "text": "Docs"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "url is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_text_needs_text(self, mock_context):
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "   "}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "text is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "Hi", "tab_id": 99}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "tab_id 99" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_default_width_outside_grid(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "Hi", "col": 12}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "24-column grid" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "add_text_to_dashboard", {"dashboard_id": 9, "kind": "text", "text": "Hi"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with get_dashboard" in result.result.message


# ---- Dashboard tabs ----


LAST_TAB_ERROR = HTTPError(400, "Bad Request", {"message": "This dashboard has tab, makes sure every card has a tab"})


class TestUpdateDashboardTabs:
    @pytest.mark.asyncio
    async def test_rename_and_add(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_tabs",
            {
                "dashboard_id": 9,
                "tabs": [{"id": 11, "name": "Summary"}, {"id": 12, "name": "Details"}, {"name": "Raw data"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert _put_body(mock_context)["tabs"] == [
            {"id": 11, "name": "Summary"},
            {"id": 12, "name": "Details"},
            {"id": -3, "name": "Raw data"},
        ]

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(SAMPLE_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_tabs",
            {"dashboard_id": 9, "tabs": [{"id": 12, "name": "Details"}, {"id": 11, "name": "Overview"}]},
            mock_context,
        )
        put = mock_context.fetch.call_args_list[1]
        assert put.args[0] == f"{BASE}/api/dashboard/9"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["retry_count"] == NO_RETRY
        assert [t["id"] for t in put.kwargs["json"]["tabs"]] == [12, 11]
        assert [dc["dashboard_tab_id"] for dc in put.kwargs["json"]["dashcards"]] == [11, 11, 12, 12]

    @pytest.mark.asyncio
    async def test_unknown_tab_id(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": [{"id": 99, "name": "Extra"}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Tab 99" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_removing_tab_with_cards_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": [{"id": 11, "name": "Overview"}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "[503, 504]" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_removing_empty_tab(self, mock_context):
        on_first_tab = {**SAMPLE_DASHBOARD, "dashcards": [SQL_DASHCARD, TEXT_DASHCARD]}
        mock_context.fetch.side_effect = [_ok(on_first_tab), _ok(on_first_tab)]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": [{"id": 11, "name": "Overview"}]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert _put_body(mock_context)["tabs"] == [{"id": 11, "name": "Overview"}]

    @pytest.mark.asyncio
    async def test_first_tabs_take_every_card(self, mock_context):
        mock_context.fetch.side_effect = [_ok(UNTABBED_DASHBOARD), _ok(UNTABBED_DASHBOARD)]
        await metabase.execute_action(
            "update_dashboard_tabs",
            {"dashboard_id": 9, "tabs": [{"name": "Overview"}, {"name": "Details"}]},
            mock_context,
        )
        body = _put_body(mock_context)
        assert body["tabs"] == [{"id": -1, "name": "Overview"}, {"id": -2, "name": "Details"}]
        assert [dc["dashboard_tab_id"] for dc in body["dashcards"]] == [-1, -1]

    @pytest.mark.asyncio
    async def test_removing_every_tab(self, mock_context):
        on_first_tab = {**SAMPLE_DASHBOARD, "dashcards": [SQL_DASHCARD, TEXT_DASHCARD]}
        mock_context.fetch.side_effect = [_ok(on_first_tab), _ok(UNTABBED_DASHBOARD)]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION
        body = _put_body(mock_context)
        assert body["tabs"] == []
        assert [dc["dashboard_tab_id"] for dc in body["dashcards"]] == [None, None]

    @pytest.mark.asyncio
    async def test_removing_every_tab_with_cards_on_two_tabs_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "more than one tab" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_blank_tab_name(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD)]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": [{"id": 11, "name": "  "}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "tab name is required" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": TABS_FOR_PUT}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with get_dashboard" in result.result.message

    # Metabase 0.49 refuses to remove a dashboard's last tab.

    @pytest.mark.asyncio
    async def test_last_tab_fallback_keeps_cards_tab(self, mock_context):
        on_details = {**SAMPLE_DASHBOARD, "dashcards": [MBQL_DASHCARD, RESTRICTED_LINK_DASHCARD]}
        kept = {**on_details, "tabs": [SAMPLE_TABS[1]]}
        mock_context.fetch.side_effect = [_ok(on_details), LAST_TAB_ERROR, _ok(kept)]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION
        get, first_put, retry = mock_context.fetch.call_args_list
        assert get.kwargs["method"] == "GET"
        assert first_put.kwargs["json"]["tabs"] == []
        assert retry.args[0] == f"{BASE}/api/dashboard/9"
        assert retry.kwargs["method"] == "PUT"
        assert retry.kwargs["retry_count"] == NO_RETRY
        assert retry.kwargs["json"]["tabs"] == [{"id": 12, "name": "Details"}]
        assert [dc["dashboard_tab_id"] for dc in retry.kwargs["json"]["dashcards"]] == [12, 12]
        assert [dc["id"] for dc in retry.kwargs["json"]["dashcards"]] == [503, 504]

    @pytest.mark.asyncio
    async def test_last_tab_fallback_note(self, mock_context):
        on_details = {**SAMPLE_DASHBOARD, "dashcards": [MBQL_DASHCARD]}
        kept = {**on_details, "tabs": [SAMPLE_TABS[1]]}
        mock_context.fetch.side_effect = [_ok(on_details), LAST_TAB_ERROR, _ok(kept)]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        data = result.result.data
        assert data["tabs"] == [{"id": 12, "name": "Details"}]
        assert data["cards"][0]["dashcard_id"] == 503
        assert "one tab was kept" in data["note"]
        assert "shows no tab bar" in data["note"]

    @pytest.mark.asyncio
    async def test_last_tab_fallback_without_cards_keeps_first_tab(self, mock_context):
        empty = {**SAMPLE_DASHBOARD, "dashcards": []}
        mock_context.fetch.side_effect = [_ok(empty), LAST_TAB_ERROR, _ok({**empty, "tabs": [SAMPLE_TABS[0]]})]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert "note" in result.result.data
        assert _put_body(mock_context) == {"dashcards": [], "tabs": [{"id": 11, "name": "Overview"}]}

    @pytest.mark.asyncio
    async def test_last_tab_fallback_failure_surfaces(self, mock_context):
        on_details = {**SAMPLE_DASHBOARD, "dashcards": [MBQL_DASHCARD]}
        mock_context.fetch.side_effect = [
            _ok(on_details),
            LAST_TAB_ERROR,
            HTTPError(403, "Forbidden", {"message": "You don't have permissions to do that."}),
        ]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_other_400_not_retried(self, mock_context):
        on_details = {**SAMPLE_DASHBOARD, "dashcards": [MBQL_DASHCARD]}
        mock_context.fetch.side_effect = [
            _ok(on_details),
            HTTPError(400, "Bad Request", {"errors": {"tabs": "value must be an array of tabs"}}),
        ]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_non_400_not_retried(self, mock_context):
        on_details = {**SAMPLE_DASHBOARD, "dashcards": [MBQL_DASHCARD]}
        mock_context.fetch.side_effect = [
            _ok(on_details),
            HTTPError(500, "Server Error", {"message": "This dashboard has tab, makes sure every card has a tab"}),
        ]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_not_retried_when_tabs_given(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), LAST_TAB_ERROR]
        result = await metabase.execute_action(
            "update_dashboard_tabs", {"dashboard_id": 9, "tabs": TABS_FOR_PUT}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message
        assert "note" not in result.result.message
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_not_retried_when_dashboard_had_no_tabs(self, mock_context):
        mock_context.fetch.side_effect = [_ok(UNTABBED_DASHBOARD), LAST_TAB_ERROR]
        result = await metabase.execute_action("update_dashboard_tabs", {"dashboard_id": 9, "tabs": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "every card has a tab" in result.result.message
        assert mock_context.fetch.call_count == 2


# ---- Dashboard filters ----

REGION_FILTER = {"id": "p1", "name": "Region", "type": "string/="}
CATEGORY_FILTER = {"id": "p2", "name": "Category", "type": "category"}


RETURNS_DATASET_QUERY = {
    "database": 1,
    "type": "native",
    "native": {
        "query": "select region, count(*) from returns where {{return_region}} group by 1",
        "template-tags": {"return_region": {"name": "return_region", "type": "text"}},
    },
}
COMBINED_SQL_DASHCARD = {
    **SQL_DASHCARD,
    "series": [{"id": 47, "name": "Returns by region", "display": "bar", "dataset_query": RETURNS_DATASET_QUERY}],
    "inline_parameters": ["p1", "p2"],
}
COMBINED_DASHBOARD = {**SAMPLE_DASHBOARD, "dashcards": [COMBINED_SQL_DASHCARD, TEXT_DASHCARD, MBQL_DASHCARD]}


class TestUpdateDashboardFilters:
    async def _run(
        self, mock_context, filters, dashboard=SAMPLE_DASHBOARD, pulses=(), sql="select region from orders", admin=True
    ):
        async def fetch(url, **kwargs):
            if "/api/pulse" in url:
                return _ok(list(pulses))
            if url.endswith("/api/user/current"):
                return _ok({"id": 1, "is_superuser": admin})
            if "/api/card/" in url:
                return _ok({"id": int(url.rsplit("/", 1)[1]), "dataset_query": SQL_DATASET_QUERY})
            if url.endswith("/api/database/1"):
                return _ok(SAMPLE_DATABASE)
            if url.endswith("/api/dataset/native"):
                return _ok({"query": sql(kwargs["json"]) if callable(sql) else sql})
            return _ok(dashboard)

        mock_context.fetch.side_effect = fetch
        return await metabase.execute_action(
            "update_dashboard_filters", {"dashboard_id": 9, "filters": filters}, mock_context
        )

    @pytest.mark.asyncio
    async def test_same_filter_twice_refused(self, mock_context):
        result = await self._run(mock_context, [REGION_FILTER, {**REGION_FILTER, "name": "Area"}])
        assert result.type == ResultType.ACTION_ERROR
        assert "p1 is listed twice" in result.result.message
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_type_change_drops_old_value_settings(self, mock_context):
        listed = {
            **SAMPLE_PARAMETERS[0],
            "values_source_type": "static-list",
            "values_source_config": {"values": ["West", "East"]},
            "temporal_units": ["month"],
        }
        dashboard = {**SAMPLE_DASHBOARD, "parameters": [listed, SAMPLE_PARAMETERS[1]]}
        await self._run(mock_context, [{**REGION_FILTER, "type": "date/single"}, CATEGORY_FILTER], dashboard=dashboard)
        param = _put_body(mock_context)["parameters"][0]
        for key in ("default", "values_source_type", "values_source_config", "temporal_units"):
            assert key not in param
        assert param["values_query_type"] == "list"

    @pytest.mark.asyncio
    async def test_same_type_keeps_value_settings(self, mock_context):
        listed = {
            **SAMPLE_PARAMETERS[0],
            "values_source_type": "static-list",
            "values_source_config": {"values": ["W"]},
        }
        dashboard = {**SAMPLE_DASHBOARD, "parameters": [listed, SAMPLE_PARAMETERS[1]]}
        await self._run(mock_context, [{**REGION_FILTER, "name": "Area"}, CATEGORY_FILTER], dashboard=dashboard)
        param = _put_body(mock_context)["parameters"][0]
        assert param["values_source_type"] == "static-list"
        assert param["default"] == ["West"]

    @pytest.mark.asyncio
    async def test_unchanged_defaults_skip_subscription_lookup(self, mock_context):
        await self._run(mock_context, [REGION_FILTER, CATEGORY_FILTER])
        assert not any("/api/pulse" in c.args[0] for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_new_default_without_subscriptions_runs_no_check(self, mock_context):
        result = await self._run(mock_context, [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER])
        assert result.type == ResultType.ACTION
        assert f"{BASE}/api/pulse?dashboard_id=9&archived=false" in [
            c.args[0] for c in mock_context.fetch.call_args_list
        ]
        assert _calls_to(mock_context, "/dataset/native") == []

    @pytest.mark.asyncio
    async def test_new_default_checked_with_non_admin_key(self, mock_context):
        # A non-admin key only sees its own subscriptions, so an empty list still gets the check.
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER],
            admin=False,
            sql="select 1, nextval('audit_seq')",
        )
        assert result.type == ResultType.ACTION_ERROR
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_removed_filter_checked_for_subscriptions(self, mock_context):
        result = await self._run(
            mock_context, [CATEGORY_FILTER], pulses=[{"id": 15}], sql="select 1, nextval('audit_seq')"
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_new_default_checked_for_subscriptions(self, mock_context):
        result = await self._run(
            mock_context, [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER], pulses=[{"id": 15}]
        )
        assert result.type == ResultType.ACTION
        native = _calls_to(mock_context, "/dataset/native")
        assert native
        assert {
            "id": "p1",
            "type": "string/=",
            "target": ["variable", ["template-tag", "region"]],
            "value": ["East"],
        } in (native[0].kwargs["json"]["parameters"])
        assert mock_context.fetch.call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_default_that_turns_on_a_write_is_refused(self, mock_context):
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER],
            pulses=[{"id": 15}],
            sql="select 1, nextval('audit_seq')",
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_subscription_own_value_that_turns_on_a_write_is_refused(self, mock_context):
        # Metabase Pro lets a subscription send with its own filter values instead of the defaults.
        def sql(body):
            values = [p.get("value") for p in body["parameters"]]
            return "select 1, nextval('audit_seq')" if ["North"] in values else "select region from orders"

        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER],
            pulses=[{"id": 15}, {"id": 16, "parameters": [{"id": "p1", "type": "string/=", "value": ["North"]}]}],
            sql=sql,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_defaults_still_checked_when_seen_subscription_has_own_values(self, mock_context):
        # A non-admin key doesn't see other people's subscriptions, which send with the defaults.
        def sql(body):
            values = [p.get("value") for p in body["parameters"]]
            return "select 1, nextval('audit_seq')" if ["East"] in values else "select region from orders"

        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER],
            pulses=[{"id": 16, "parameters": [{"id": "p1", "type": "string/=", "value": ["North"]}]}],
            sql=sql,
            admin=False,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_subscriptions_without_own_values_checked_once(self, mock_context):
        filters = [{**REGION_FILTER, "default": ["East"]}, CATEGORY_FILTER]
        await self._run(mock_context, filters, pulses=[{"id": 15}])
        one = len(_calls_to(mock_context, "/dataset/native"))
        mock_context.fetch.reset_mock()
        await self._run(mock_context, filters, pulses=[{"id": 15}, {"id": 16}])
        assert one
        assert len(_calls_to(mock_context, "/dataset/native")) == one

    @pytest.mark.asyncio
    async def test_type_change_with_same_default_checked_for_subscriptions(self, mock_context):
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "type": "string/contains", "default": ["West"]}, CATEGORY_FILTER],
            pulses=[{"id": 15}],
            sql="select 1, nextval('audit_seq')",
        )
        assert result.type == ResultType.ACTION_ERROR
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_new_connections_checked_for_subscriptions(self, mock_context):
        await self._run(
            mock_context,
            [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "template_tag": "region"}]}],
            pulses=[{"id": 15}],
        )
        assert _calls_to(mock_context, "/dataset/native")

    @pytest.mark.asyncio
    async def test_removed_linked_filter_dropped_from_links(self, mock_context):
        linked = {
            **SAMPLE_DASHBOARD,
            "parameters": [SAMPLE_PARAMETERS[0], {**SAMPLE_PARAMETERS[1], "filteringParameters": ["p1"]}],
        }
        result = await self._run(mock_context, [CATEGORY_FILTER], dashboard=linked)
        assert result.type == ResultType.ACTION
        assert _put_body(mock_context)["parameters"][0]["filteringParameters"] == []

    @pytest.mark.asyncio
    async def test_link_to_unknown_filter_refused(self, mock_context):
        result = await self._run(mock_context, [{**CATEGORY_FILTER, "linked_filter_ids": ["p1"]}])
        assert result.type == ResultType.ACTION_ERROR
        assert "linked to p1" in result.result.message
        assert not any(c.kwargs.get("method") == "PUT" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_link_to_kept_filter_kept(self, mock_context):
        await self._run(mock_context, [REGION_FILTER, {**CATEGORY_FILTER, "linked_filter_ids": ["p1"]}])
        assert _put_body(mock_context)["parameters"][1]["filteringParameters"] == ["p1"]

    @pytest.mark.asyncio
    async def test_kept_filters_keep_mappings(self, mock_context):
        result = await self._run(mock_context, [REGION_FILTER, CATEGORY_FILTER])
        assert result.type == ResultType.ACTION
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == SQL_DASHCARD["parameter_mappings"]
        assert _put_dashcard(mock_context, 503)["parameter_mappings"] == MBQL_DASHCARD["parameter_mappings"]

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        await self._run(mock_context, [REGION_FILTER, CATEGORY_FILTER])
        put = mock_context.fetch.call_args_list[1]
        assert put.args[0] == f"{BASE}/api/dashboard/9"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["retry_count"] == NO_RETRY
        assert put.kwargs["json"]["tabs"] == TABS_FOR_PUT
        assert [p["id"] for p in put.kwargs["json"]["parameters"]] == ["p1", "p2"]
        assert "visualization_settings" not in _put_dashcard(mock_context, 504)

    @pytest.mark.asyncio
    async def test_existing_settings_kept(self, mock_context):
        await self._run(mock_context, [{**REGION_FILTER, "name": "Sales region"}])
        param = _put_body(mock_context)["parameters"][0]
        assert param["name"] == "Sales region"
        assert param["slug"] == "sales_region"
        assert param["default"] == ["West"]
        assert param["values_query_type"] == "list"

    @pytest.mark.asyncio
    async def test_removed_filter_drops_its_mappings(self, mock_context):
        await self._run(mock_context, [CATEGORY_FILTER])
        assert [p["id"] for p in _put_body(mock_context)["parameters"]] == ["p2"]
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == []
        assert _put_dashcard(mock_context, 503)["parameter_mappings"] == MBQL_DASHCARD["parameter_mappings"]

    @pytest.mark.asyncio
    async def test_connections_replace_mappings(self, mock_context):
        await self._run(
            mock_context, [{**REGION_FILTER, "connections": [{"dashcard_id": 503, "field_id": 7}]}, CATEGORY_FILTER]
        )
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == []
        assert _put_dashcard(mock_context, 503)["parameter_mappings"] == [
            MBQL_DASHCARD["parameter_mappings"][0],
            {"parameter_id": "p1", "card_id": 43, "target": ["dimension", ["field", 7, None]]},
        ]

    @pytest.mark.asyncio
    async def test_empty_connections_disconnect(self, mock_context):
        await self._run(mock_context, [{**REGION_FILTER, "connections": []}])
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == []

    @pytest.mark.asyncio
    async def test_text_template_tag_is_variable(self, mock_context):
        await self._run(
            mock_context, [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "template_tag": "region"}]}]
        )
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == [
            {"parameter_id": "p1", "card_id": 42, "target": ["variable", ["template-tag", "region"]]}
        ]

    @pytest.mark.asyncio
    async def test_field_filter_template_tag_is_dimension(self, mock_context):
        await self._run(
            mock_context, [{**CATEGORY_FILTER, "connections": [{"dashcard_id": 501, "template_tag": "category"}]}]
        )
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == [
            {"parameter_id": "p2", "card_id": 42, "target": ["dimension", ["template-tag", "category"]]}
        ]

    @pytest.mark.asyncio
    async def test_unknown_template_tag(self, mock_context):
        result = await self._run(
            mock_context, [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "template_tag": "country"}]}]
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "no SQL filter named country" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_needs_field_or_tag(self, mock_context):
        result = await self._run(mock_context, [{**REGION_FILTER, "connections": [{"dashcard_id": 503}]}])
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one of field_id or template_tag" in result.result.message

    @pytest.mark.asyncio
    async def test_connection_with_both_field_and_tag(self, mock_context):
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "field_id": 7, "template_tag": "region"}]}],
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one of field_id or template_tag" in result.result.message

    @pytest.mark.asyncio
    async def test_two_connections_to_one_question_refused(self, mock_context):
        # Metabase applies only one of them, so the other column would silently stay unfiltered.
        result = await self._run(
            mock_context,
            [
                {
                    **REGION_FILTER,
                    "connections": [{"dashcard_id": 503, "field_id": 7}, {"dashcard_id": 503, "field_id": 8}],
                }
            ],
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "connected to card 503 twice" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_to_text_card_refused(self, mock_context):
        result = await self._run(
            mock_context, [{**REGION_FILTER, "connections": [{"dashcard_id": 502, "field_id": 7}]}]
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Card 502 is not a question card" in result.result.message

    @pytest.mark.asyncio
    async def test_required_without_default_refused(self, mock_context):
        result = await self._run(mock_context, [{**CATEGORY_FILTER, "required": True}])
        assert result.type == ResultType.ACTION_ERROR
        assert "needs a default value" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_required_with_default(self, mock_context):
        await self._run(mock_context, [{**CATEGORY_FILTER, "required": True, "default": ["Gizmo"]}])
        param = _put_body(mock_context)["parameters"][0]
        assert param["required"] is True
        assert param["default"] == ["Gizmo"]

    @pytest.mark.asyncio
    async def test_unknown_filter_id(self, mock_context):
        result = await self._run(mock_context, [{"id": "zz99", "name": "Country", "type": "location/country"}])
        assert result.type == ResultType.ACTION_ERROR
        assert "Filter zz99" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_new_filter_gets_id_and_slug(self, mock_context):
        await self._run(
            mock_context,
            [
                REGION_FILTER,
                {
                    "name": "Order date",
                    "type": "date/all-options",
                    "default": "past30days",
                    "linked_filter_ids": ["p1"],
                    "connections": [{"dashcard_id": 503, "field_id": 12}],
                },
            ],
        )
        new = _put_body(mock_context)["parameters"][1]
        assert re.fullmatch(r"[0-9a-f]{8}", new["id"])
        assert new["id"] not in ("p1", "p2")
        assert new["slug"] == "order_date"
        assert new["sectionId"] == "date"
        assert new["default"] == "past30days"
        assert new["filteringParameters"] == ["p1"]
        assert _put_dashcard(mock_context, 503)["parameter_mappings"] == [
            {"parameter_id": new["id"], "card_id": 43, "target": ["dimension", ["field", 12, None]]}
        ]

    @pytest.mark.asyncio
    async def test_names_with_same_slug_refused(self, mock_context):
        result = await self._run(mock_context, [REGION_FILTER, {"name": "region", "type": "string/="}])
        assert result.type == ResultType.ACTION_ERROR
        assert "same name" in result.result.message
        assert mock_context.fetch.call_count == 1
        assert [c.kwargs["method"] for c in mock_context.fetch.call_args_list] == ["GET"]

    @pytest.mark.asyncio
    async def test_names_differing_by_punctuation_refused(self, mock_context):
        result = await self._run(
            mock_context,
            [{"name": "Order date", "type": "date/single"}, {"name": "Order-Date!", "type": "date/range"}],
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "same name" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_renaming_into_free_slug_allowed(self, mock_context):
        result = await self._run(mock_context, [{**REGION_FILTER, "name": "Sales region"}, CATEGORY_FILTER])
        assert result.type == ResultType.ACTION
        assert [p["slug"] for p in _put_body(mock_context)["parameters"]] == ["sales_region", "category"]

    @pytest.mark.asyncio
    async def test_series_question_connected_by_template_tag(self, mock_context):
        await self._run(
            mock_context,
            [
                {
                    **REGION_FILTER,
                    "connections": [
                        {"dashcard_id": 501, "template_tag": "region"},
                        {"dashcard_id": 501, "question_id": 47, "template_tag": "return_region"},
                    ],
                }
            ],
            COMBINED_DASHBOARD,
        )
        assert _put_dashcard(mock_context, 501)["parameter_mappings"] == [
            {"parameter_id": "p1", "card_id": 42, "target": ["variable", ["template-tag", "region"]]},
            {"parameter_id": "p1", "card_id": 47, "target": ["variable", ["template-tag", "return_region"]]},
        ]

    @pytest.mark.asyncio
    async def test_series_question_connected_by_field(self, mock_context):
        await self._run(
            mock_context,
            [CATEGORY_FILTER | {"connections": [{"dashcard_id": 503, "question_id": 44, "field_id": 21}]}],
        )
        assert _put_dashcard(mock_context, 503)["parameter_mappings"] == [
            {"parameter_id": "p2", "card_id": 44, "target": ["dimension", ["field", 21, None]]}
        ]

    @pytest.mark.asyncio
    async def test_own_question_id_accepted(self, mock_context):
        await self._run(
            mock_context,
            [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "question_id": 42, "template_tag": "region"}]}],
            COMBINED_DASHBOARD,
        )
        assert _put_dashcard(mock_context, 501)["parameter_mappings"][0]["card_id"] == 42

    @pytest.mark.asyncio
    async def test_series_tag_looked_up_in_series_query(self, mock_context):
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "question_id": 47, "template_tag": "region"}]}],
            COMBINED_DASHBOARD,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "no SQL filter named region" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_question_not_on_card_refused(self, mock_context):
        result = await self._run(
            mock_context,
            [{**REGION_FILTER, "connections": [{"dashcard_id": 501, "question_id": 43, "field_id": 7}]}],
            COMBINED_DASHBOARD,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Question 43 isn't shown on card 501" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_boolean_filter_kept(self, mock_context):
        # Dashboards can have Boolean filters, which must be listed again to keep them.
        result = await self._run(mock_context, [{"name": "Active", "type": "boolean/=", "default": [True]}])
        assert result.type == ResultType.ACTION
        param = _put_body(mock_context)["parameters"][0]
        assert (param["type"], param["sectionId"], param["default"]) == ("boolean/=", "boolean", [True])

    @pytest.mark.asyncio
    async def test_type_change_drops_old_default(self, mock_context):
        await self._run(mock_context, [{**REGION_FILTER, "type": "string/contains"}])
        param = _put_body(mock_context)["parameters"][0]
        assert param["type"] == "string/contains"
        assert "default" not in param
        assert param["values_query_type"] == "list"

    @pytest.mark.asyncio
    async def test_type_change_with_new_default(self, mock_context):
        await self._run(mock_context, [{**REGION_FILTER, "type": "string/contains", "default": ["We"]}])
        assert _put_body(mock_context)["parameters"][0]["default"] == ["We"]

    @pytest.mark.asyncio
    async def test_type_change_of_required_filter_needs_default(self, mock_context):
        required = {**SAMPLE_DASHBOARD, "parameters": [{**SAMPLE_PARAMETERS[0], "required": True}]}
        result = await self._run(mock_context, [{**REGION_FILTER, "type": "string/contains"}], required)
        assert result.type == ResultType.ACTION_ERROR
        assert "needs a default value" in result.result.message

    @pytest.mark.asyncio
    async def test_non_latin_names_get_distinct_slugs(self, mock_context):
        result = await self._run(
            mock_context, [{"name": "日付", "type": "date/single"}, {"name": "地域", "type": "string/="}]
        )
        assert result.type == ResultType.ACTION
        assert [p["slug"] for p in _put_body(mock_context)["parameters"]] == ["日付", "地域"]

    @pytest.mark.asyncio
    async def test_accented_name_not_folded_into_unaccented(self, mock_context):
        result = await self._run(
            mock_context, [{"name": "Région", "type": "string/="}, {"name": "R gion", "type": "string/="}]
        )
        assert result.type == ResultType.ACTION
        assert [p["slug"] for p in _put_body(mock_context)["parameters"]] == ["région", "r_gion"]

    @pytest.mark.asyncio
    async def test_removed_filter_leaves_inline_parameters(self, mock_context):
        await self._run(mock_context, [CATEGORY_FILTER], COMBINED_DASHBOARD)
        assert _put_dashcard(mock_context, 501)["inline_parameters"] == ["p2"]

    @pytest.mark.asyncio
    async def test_kept_filters_keep_inline_parameters(self, mock_context):
        await self._run(mock_context, [REGION_FILTER, CATEGORY_FILTER], COMBINED_DASHBOARD)
        assert _put_dashcard(mock_context, 501)["inline_parameters"] == ["p1", "p2"]

    @pytest.mark.asyncio
    async def test_timeout_says_check_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "update_dashboard_filters", {"dashboard_id": 9, "filters": [REGION_FILTER]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with get_dashboard" in result.result.message


# ---- Copying dashboards ----


class TestCopyDashboard:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_DASHBOARD),
            _ok({"id": 70, "name": "Sales (copy)", "collection_id": 4, "dashcards": []}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context
        )
        assert result.result.data == {"id": 70, "name": "Sales (copy)", "collection_id": 4}

    @pytest.mark.asyncio
    async def test_questions_left_off_the_copy_are_reported(self, mock_context):
        uncopied = [
            {"id": 42, "name": "Secret revenue", "archived": False},
            {"id": 43, "name": None},
            {"id": 42, "name": "Secret revenue"},
        ]
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_DASHBOARD),
            _ok({"id": 70, "name": "Sales (copy)", "collection_id": 4, "uncopied": uncopied}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["uncopied_questions"] == [{"id": 42, "name": "Secret revenue"}, {"id": 43, "name": None}]
        assert data["note"].startswith("Metabase left 2 question(s) off the copy")

    @pytest.mark.asyncio
    async def test_full_copy_has_no_uncopied_questions_or_note(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_DASHBOARD),
            _ok({"id": 70, "name": "Sales (copy)", "uncopied": []}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context
        )
        assert "uncopied_questions" not in result.result.data
        assert "note" not in result.result.data

    @pytest.mark.asyncio
    async def test_request_keeps_original_collection(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok({"id": 70, "name": "Sales (copy)"})]
        await metabase.execute_action("copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context)
        get, post = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/dashboard/9"
        assert get.kwargs["method"] == "GET"
        assert post.args[0] == f"{BASE}/api/dashboard/9/copy"
        assert post.kwargs["method"] == "POST"
        assert post.kwargs["json"] == {"is_deep_copy": False, "name": "Sales (copy)", "collection_id": 4}
        assert post.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_original_at_top_level_sends_no_collection(self, mock_context):
        top_level = {**SAMPLE_DASHBOARD, "collection_id": None}
        mock_context.fetch.side_effect = [_ok(top_level), _ok({"id": 70, "name": "Sales (copy)"})]
        await metabase.execute_action("copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context)
        assert mock_context.fetch.call_count == 2
        assert mock_context.fetch.call_args.kwargs["json"] == {"is_deep_copy": False, "name": "Sales (copy)"}

    @pytest.mark.asyncio
    async def test_copy_into_collection_skips_get(self, mock_context):
        mock_context.fetch.side_effect = [_ok({"id": 71, "name": "Sales 2027", "collection_id": 8})]
        await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales 2027", "description": "Next year", "collection_id": 8},
            mock_context,
        )
        assert mock_context.fetch.call_count == 1
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/dashboard/9/copy"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "is_deep_copy": False,
            "name": "Sales 2027",
            "description": "Next year",
            "collection_id": 8,
        }

    @pytest.mark.asyncio
    async def test_deep_copy_checks_every_question_first(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SERIES_DASHBOARD),
            *_copy_check(42),
            *_copy_check(46),
            *_copy_check(43),
            _ok({"id": 71, "name": "Sales 2027", "collection_id": 8}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales 2027", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.result.data == {"id": 71, "name": "Sales 2027", "collection_id": 8}
        urls = [c.args[0] for c in mock_context.fetch.call_args_list]
        assert urls[0] == f"{BASE}/api/dashboard/9"
        assert [u for u in urls if "/api/card/" in u] == [
            f"{BASE}/api/card/42",
            f"{BASE}/api/card/46",
            f"{BASE}/api/card/43",
        ]
        assert len(_calls_to(mock_context, "/dataset/native")) == 6
        post = mock_context.fetch.call_args
        assert post.args[0] == f"{BASE}/api/dashboard/9/copy"
        assert post.kwargs["json"] == {"is_deep_copy": True, "name": "Sales 2027", "collection_id": 8}
        assert post.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_deep_copy_skips_questions_the_key_cant_read(self, mock_context):
        # Metabase shows an unreadable question as just its id and leaves it out of the copy.
        dashcards = [*SERIES_DASHBOARD["dashcards"][:1], {**SERIES_DASHBOARD["dashcards"][1], "card": {"id": 43}}]
        mock_context.fetch.side_effect = [
            _ok({**SERIES_DASHBOARD, "dashcards": dashcards}),
            *_copy_check(42),
            *_copy_check(46),
            _ok({"id": 71, "name": "Sales 2027", "uncopied": [{"id": 43}]}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales 2027", "copy_questions": True}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert f"{BASE}/api/card/43" not in [c.args[0] for c in mock_context.fetch.call_args_list]
        assert result.result.data["uncopied_questions"] == [{"id": 43, "name": None}]

    @pytest.mark.asyncio
    async def test_deep_copy_checks_every_filter_then_dashboard_defaults(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SERIES_DASHBOARD),
            *_copy_check(42),
            *_copy_check(46),
            *_copy_check(43),
            _ok({"id": 71, "name": "Sales (copy)", "collection_id": 4}),
        ]
        await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)", "copy_questions": True}, mock_context
        )
        natives = [c.kwargs["json"]["parameters"] for c in _calls_to(mock_context, "/dataset/native")]
        region_west = {"id": "p1", "type": "string/=", "target": REGION_TARGET, "value": ["West"]}
        # Question 42: every filter set (Region from the dashboard default, a stand-in for Category), then the default.
        assert natives[0] == [region_west, CATEGORY_STAND_IN]
        assert natives[1] == [region_west]
        # Series 46 is connected to Category, which has no default: stand-ins for both, then no filters.
        assert natives[2] == [REGION_STAND_IN, CATEGORY_STAND_IN]
        assert natives[3] == []
        assert mock_context.fetch.call_args.kwargs["json"]["collection_id"] == 4

    @pytest.mark.asyncio
    async def test_deep_copy_checks_repeated_question_once(self, mock_context):
        repeated = {**SERIES_DASHBOARD, "dashcards": [SERIES_DASHBOARD["dashcards"][0]] * 2}
        mock_context.fetch.side_effect = [
            _ok(repeated),
            *_copy_check(42),
            *_copy_check(46),
            _ok({"id": 71, "name": "Sales (copy)"}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales (copy)", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert len(_calls_to(mock_context, "/api/card/42")) == 1
        assert len(_calls_to(mock_context, "/api/card/46")) == 1

    @pytest.mark.asyncio
    async def test_deep_copy_refused_for_write_series(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SERIES_DASHBOARD),
            *_copy_check(42),
            _ok(_card(46)),
            _ok(SAMPLE_DATABASE),
            _ok({"query": "delete from returns"}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales (copy)", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 46 wasn't run" in result.result.message
        assert _calls_to(mock_context, "/copy") == []
        assert mock_context.fetch.call_count == 8

    @pytest.mark.asyncio
    async def test_deep_copy_refused_when_write_only_in_optional_clause(self, mock_context):
        # Only the expansion with every filter set reaches the write; the plain check sees a select.
        mock_context.fetch.side_effect = [
            _ok(ONE_QUESTION_DASHBOARD),
            _ok(_card(43)),
            _ok(SAMPLE_DATABASE),
            _ok({"query": "select 1; update orders set status = 'void'"}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales (copy)", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 43 wasn't run" in result.result.message
        assert _calls_to(mock_context, "/copy") == []

    @pytest.mark.asyncio
    async def test_deep_copy_not_blocked_by_required_filter_without_default(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(ONE_QUESTION_DASHBOARD),
            _ok(_card(43)),
            _ok(SAMPLE_DATABASE),
            _ok(SELECT_SQL),
            HTTPError(
                400, "Bad Request", {"message": "You'll need to pick a value for 'Category' before this query can run."}
            ),
            _ok({"id": 71, "name": "Sales (copy)", "collection_id": 8}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales (copy)", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == 71
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/dashboard/9/copy"

    @pytest.mark.asyncio
    async def test_deep_copy_stand_in_expansion_error_blocks_copy(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(ONE_QUESTION_DASHBOARD),
            _ok(_card(43)),
            _ok(SAMPLE_DATABASE),
            HTTPError(400, "Bad Request", {"message": "Invalid parameter value"}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard",
            {"dashboard_id": 9, "name": "Sales (copy)", "collection_id": 8, "copy_questions": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message
        assert _calls_to(mock_context, "/copy") == []

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action("copy_dashboard", {"dashboard_id": 9, "name": "  "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok({"name": "Sales (copy)"})]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "Sales (copy)"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "did not return a dashboard id" in result.result.message

    @pytest.mark.asyncio
    async def test_original_not_found(self, mock_context):
        mock_context.fetch.side_effect = [HTTPError(404, "Not found.", "Not found.")]
        result = await metabase.execute_action("copy_dashboard", {"dashboard_id": 999, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_copy_http_error(self, mock_context):
        mock_context.fetch.side_effect = [
            HTTPError(403, "Forbidden", {"message": "You don't have permissions to do that."}),
        ]
        result = await metabase.execute_action(
            "copy_dashboard", {"dashboard_id": 9, "name": "X", "collection_id": 8}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_timeout_says_search_before_retrying(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), asyncio.TimeoutError()]
        result = await metabase.execute_action("copy_dashboard", {"dashboard_id": 9, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Check with search" in result.result.message
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"


# ---- Running dashboards ----

REGION_TARGET = ["variable", ["template-tag", "region"]]
CATEGORY_TARGET = ["dimension", ["field", 8, None]]
RUN_DASHBOARD = {
    "id": 9,
    "name": "Sales",
    "tabs": SAMPLE_TABS,
    "parameters": SAMPLE_PARAMETERS,
    "dashcards": [
        {
            "id": 601,
            "card_id": 42,
            "card": {"id": 42, "name": "Orders by region"},
            "dashboard_tab_id": 11,
            "parameter_mappings": [{"parameter_id": "p1", "card_id": 42, "target": REGION_TARGET}],
        },
        {"id": 602, "card_id": None, "card": None, "dashboard_tab_id": 11, "parameter_mappings": []},
        {
            "id": 603,
            "card_id": 43,
            "card": {"id": 43, "name": "Order count"},
            "dashboard_tab_id": 12,
            "parameter_mappings": [{"parameter_id": "p2", "card_id": 43, "target": CATEGORY_TARGET}],
        },
        {
            "id": 604,
            "card_id": 45,
            "action_id": 5,
            "card": {"id": 45, "name": "Refund order"},
            "dashboard_tab_id": 12,
            "parameter_mappings": [],
        },
    ],
}
SAMPLE_DATABASE = {"id": 1, "engine": "postgres"}
SELECT_SQL = {"query": "select region, count(*) from orders where region = 'West' group by 1"}
SAMPLE_QUERY_RESULT = {
    "status": "completed",
    "data": {
        "cols": [
            {"name": "region", "display_name": "Region", "base_type": "type/Text"},
            {"name": "count", "display_name": "Count", "base_type": "type/Integer"},
        ],
        "rows": [["West", 12], ["East", 9], ["North", 4]],
    },
}


SERIES_TARGET = ["dimension", ["field", 15, None]]
SERIES_DASHBOARD = {
    "id": 9,
    "name": "Sales",
    "collection_id": 4,
    "tabs": SAMPLE_TABS,
    "parameters": SAMPLE_PARAMETERS,
    "dashcards": [
        {
            "id": 801,
            "card_id": 42,
            "card": {"id": 42, "name": "Orders by region"},
            "series": [{"id": 46, "name": "Returns by region", "display": "bar"}],
            "dashboard_tab_id": 11,
            "parameter_mappings": [
                {"parameter_id": "p1", "card_id": 42, "target": REGION_TARGET},
                {"parameter_id": "p2", "card_id": 46, "target": SERIES_TARGET},
            ],
        },
        {"id": 802, "card_id": 43, "card": {"id": 43, "name": "Order count"}, "dashboard_tab_id": 11},
        {"id": 803, "card_id": None, "card": None, "dashboard_tab_id": 11, "parameter_mappings": []},
        {"id": 804, "card_id": 45, "action_id": 5, "card": {"id": 45, "name": "Refund order"}},
    ],
}


def _card(card_id):
    return {"id": card_id, "database_id": 1, "dataset_query": SQL_DATASET_QUERY, "parameters": []}


def _card_run(card_id, compiled=SELECT_SQL, result=SAMPLE_QUERY_RESULT):
    """Responses for one question: GET card, GET database, POST /dataset/native, POST dashcard query."""
    return [_ok(_card(card_id)), _ok(SAMPLE_DATABASE), _ok(compiled), _ok(result)]


def _copy_check(card_id, compiled=SELECT_SQL):
    """Responses for checking one question before a deep copy: GET card, GET database, POST /dataset/native with
    every filter set, POST /dataset/native with the dashboard defaults."""
    return [_ok(_card(card_id)), _ok(SAMPLE_DATABASE), _ok(compiled), _ok(compiled)]


REGION_STAND_IN = {"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "x"}
CATEGORY_STAND_IN = {"type": "category", "target": ["dimension", ["template-tag", "category"]], "value": ["x"]}
ONE_QUESTION_DASHBOARD = {**SERIES_DASHBOARD, "dashcards": [SERIES_DASHBOARD["dashcards"][1]]}


def _calls_to(mock_context, suffix):
    return [c for c in mock_context.fetch.call_args_list if c.args[0].endswith(suffix)]


class TestRunDashboard:
    @pytest.mark.asyncio
    async def test_runs_question_cards(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        data = result.result.data
        assert data["dashboard_id"] == 9
        assert data["card_count"] == 2
        assert data["skipped_card_count"] == 0
        assert [c["dashcard_id"] for c in data["cards"]] == [601, 603]
        assert data["cards"][0]["card_name"] == "Orders by region"
        assert data["cards"][0]["rows"][0] == {"region": "West", "count": 12}
        assert data["cards"][0]["row_count"] == 3

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        urls = [c.args[0] for c in mock_context.fetch.call_args_list]
        assert urls == [
            f"{BASE}/api/dashboard/9",
            f"{BASE}/api/card/42",
            f"{BASE}/api/database/1",
            f"{BASE}/api/dataset/native",
            f"{BASE}/api/dashboard/9/dashcard/601/card/42/query",
            f"{BASE}/api/card/43",
            f"{BASE}/api/database/1",
            f"{BASE}/api/dataset/native",
            f"{BASE}/api/dashboard/9/dashcard/603/card/43/query",
        ]
        query = mock_context.fetch.call_args_list[4]
        assert query.kwargs["method"] == "POST"
        assert query.kwargs["retry_count"] == NO_RETRY
        assert query.kwargs["timeout"] == 120
        native = mock_context.fetch.call_args_list[3]
        assert native.kwargs["method"] == "POST"
        assert native.kwargs["json"]["native"] == SQL_DATASET_QUERY["native"]
        assert native.kwargs["json"]["pretty"] is False

    @pytest.mark.asyncio
    async def test_defaults_applied_and_sent(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        native_42, native_43 = _calls_to(mock_context, "/dataset/native")
        assert native_42.kwargs["json"]["parameters"] == [
            {"id": "p1", "type": "string/=", "target": REGION_TARGET, "value": ["West"]}
        ]
        assert native_43.kwargs["json"]["parameters"] == []
        query_42, query_43 = _calls_to(mock_context, "/query")
        assert query_42.kwargs["json"] == {"parameters": [{"id": "p1", "type": "string/=", "value": ["West"]}]}
        assert query_43.kwargs["json"] == {"parameters": []}

    @pytest.mark.asyncio
    async def test_filter_by_slug(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        await metabase.execute_action(
            "run_dashboard", {"dashboard_id": 9, "filters": [{"filter": "category", "value": ["Gizmo"]}]}, mock_context
        )
        native_43 = _calls_to(mock_context, "/dataset/native")[1]
        assert native_43.kwargs["json"]["parameters"] == [
            {"id": "p2", "type": "category", "target": CATEGORY_TARGET, "value": ["Gizmo"]}
        ]
        query_43 = _calls_to(mock_context, "/query")[1]
        assert query_43.kwargs["json"] == {"parameters": [{"id": "p2", "type": "category", "value": ["Gizmo"]}]}

    @pytest.mark.asyncio
    async def test_filter_by_id_overrides_default(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        await metabase.execute_action(
            "run_dashboard", {"dashboard_id": 9, "filters": [{"filter": "p1", "value": ["East"]}]}, mock_context
        )
        query_42 = _calls_to(mock_context, "/query")[0]
        assert query_42.kwargs["json"] == {"parameters": [{"id": "p1", "type": "string/=", "value": ["East"]}]}

    @pytest.mark.asyncio
    async def test_unknown_filter(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD)]
        result = await metabase.execute_action(
            "run_dashboard", {"dashboard_id": 9, "filters": [{"filter": "country", "value": "NZ"}]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "No filter country" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_text_and_action_cards_skipped(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert _calls_to(mock_context, "/dashcard/602/card/None/query") == []
        assert _calls_to(mock_context, "/api/card/45") == []
        assert mock_context.fetch.call_count == 9

    @pytest.mark.asyncio
    async def test_stops_starting_questions_near_the_lambda_timeout(self, mock_context, monkeypatch):
        loop = asyncio.get_running_loop()
        clock = [1000.0]
        monkeypatch.setattr(loop, "time", lambda: clock[0])
        responses = iter([_ok(RUN_DASHBOARD), *_card_run(42)])

        async def fetch(url, **kwargs):
            if url.endswith("/query"):
                clock[0] += 130  # The first question took 130 of the 135 seconds.
            return next(responses)

        mock_context.fetch.side_effect = fetch
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        data = result.result.data
        assert [c["card_id"] for c in data["cards"]] == [42]
        assert data["skipped_card_count"] == 1
        assert "run_question" in data["skipped_reason"]
        assert _calls_to(mock_context, "/api/card/43") == []

    @pytest.mark.asyncio
    async def test_slow_check_stopped_at_the_deadline(self, mock_context, monkeypatch):
        monkeypatch.setattr(sys.modules["metabase.metabase"], "DASHBOARD_RUN_SECONDS", 0.2)
        monkeypatch.setattr(sys.modules["metabase.metabase"], "MIN_DASHBOARD_CARD_SECONDS", 0.05)
        responses = iter([_ok(RUN_DASHBOARD)])

        async def fetch(url, **kwargs):
            if "/api/card/" in url:
                await asyncio.sleep(10)  # Metabase hangs on the check's first request.
            return next(responses)

        mock_context.fetch.side_effect = fetch
        result = await asyncio.wait_for(
            metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context), timeout=2
        )
        data = result.result.data
        assert "error" in data["cards"][0]
        assert data["skipped_card_count"] == 1

    @pytest.mark.asyncio
    async def test_query_timeout_shrinks_to_time_left(self, mock_context, monkeypatch):
        loop = asyncio.get_running_loop()
        clock = [1000.0]
        monkeypatch.setattr(loop, "time", lambda: clock[0])
        responses = iter([_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)])

        async def fetch(url, **kwargs):
            if url.endswith("/query"):
                clock[0] += 60
            return next(responses)

        mock_context.fetch.side_effect = fetch
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert [c.kwargs["timeout"] for c in _calls_to(mock_context, "/query")] == [120, 75]

    @pytest.mark.asyncio
    async def test_query_timeout_never_rounds_to_zero(self, mock_context, monkeypatch):
        loop = asyncio.get_running_loop()
        clock = [1000.0]
        monkeypatch.setattr(loop, "time", lambda: clock[0])
        responses = iter([_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)])

        async def fetch(url, **kwargs):
            if url.endswith("/dataset/native"):
                clock[0] += 134.6  # The check left under a second for the query.
            return next(responses)

        mock_context.fetch.side_effect = fetch
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert _calls_to(mock_context, "/query")[0].kwargs["timeout"] == 1

    @pytest.mark.asyncio
    async def test_rows_cut_to_the_response_size_limit(self, mock_context, monkeypatch):
        monkeypatch.setattr(sys.modules["metabase.metabase"], "MAX_DASHBOARD_RESULT_CHARS", 900)
        wide = {
            **SAMPLE_QUERY_RESULT,
            "data": {**SAMPLE_QUERY_RESULT["data"], "rows": [["x" * 100, n] for n in range(9)]},
        }
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42, result=wide)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9, "max_rows": 9}, mock_context)
        data = result.result.data
        card = data["cards"][0]
        assert 0 < card["row_count"] < 9
        assert card["row_count"] == len(card["rows"])
        assert card["truncated"] is True
        assert card["total_row_count"] == 9
        assert len(json.dumps(card)) <= 900
        # The size limit is used up, so the next question isn't run.
        assert data["card_count"] == 1
        assert data["skipped_card_count"] == 1
        assert "skipped_reason" in data

    @pytest.mark.asyncio
    async def test_no_skipped_reason_when_everything_ran(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(42), *_card_run(43)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert "skipped_reason" not in result.result.data

    @pytest.mark.asyncio
    async def test_one_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(43)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9, "tab_id": 12}, mock_context)
        assert [c["dashcard_id"] for c in result.result.data["cards"]] == [603]
        assert mock_context.fetch.call_count == 5

    @pytest.mark.asyncio
    async def test_write_sql_card_reports_error_and_others_run(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(RUN_DASHBOARD),
            _ok(_card(42)),
            _ok(SAMPLE_DATABASE),
            _ok({"query": "delete from orders where region = 'West'"}),
            *_card_run(43),
        ]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert result.type == ResultType.ACTION
        first, second = result.result.data["cards"]
        assert "Saved question 42 wasn't run" in first["error"]
        assert "rows" not in first
        assert second["row_count"] == 3
        assert [c.args[0] for c in _calls_to(mock_context, "/query")] == [
            f"{BASE}/api/dashboard/9/dashcard/603/card/43/query"
        ]

    @pytest.mark.asyncio
    async def test_failed_card_query_reports_error(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(RUN_DASHBOARD),
            *_card_run(42)[:3],
            HTTPError(400, "Bad Request", {"error": 'relation "orders" does not exist'}),
            *_card_run(43),
        ]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        first, second = result.result.data["cards"]
        assert "HTTP 400" in first["error"]
        assert "does not exist" in first["error"]
        assert "error" not in second

    @pytest.mark.asyncio
    async def test_at_most_25_cards(self, mock_context):
        many = {
            "id": 9,
            "parameters": [],
            "dashcards": [
                {"id": 700 + i, "card_id": 100 + i, "card": {"name": f"Q{i}"}, "parameter_mappings": []}
                for i in range(26)
            ],
        }
        responses = [_ok(many)]
        for i in range(25):
            responses.extend(_card_run(100 + i))
        mock_context.fetch.side_effect = responses
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert result.result.data["card_count"] == 25
        assert result.result.data["skipped_card_count"] == 1
        assert _calls_to(mock_context, "/api/card/125") == []
        assert mock_context.fetch.call_count == 101
        assert result.result.data["skipped_reason"].startswith("Only 25 cards are run at a time")

    @pytest.mark.asyncio
    async def test_max_rows_trims(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD), *_card_run(43)]
        result = await metabase.execute_action(
            "run_dashboard", {"dashboard_id": 9, "tab_id": 12, "max_rows": 1}, mock_context
        )
        card = result.result.data["cards"][0]
        assert card["rows"] == [{"region": "West", "count": 12}]
        assert card["row_count"] == 1
        assert card["total_row_count"] == 3
        assert card["truncated"] is True

    @pytest.mark.asyncio
    async def test_series_run_with_their_own_mappings(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SERIES_DASHBOARD), *_card_run(42), *_card_run(46), *_card_run(43)]
        result = await metabase.execute_action(
            "run_dashboard", {"dashboard_id": 9, "filters": [{"filter": "category", "value": ["Gizmo"]}]}, mock_context
        )
        cards = result.result.data["cards"]
        assert [(c["dashcard_id"], c["card_id"], c["card_name"]) for c in cards] == [
            (801, 42, "Orders by region"),
            (801, 46, "Returns by region"),
            (802, 43, "Order count"),
        ]
        assert all("error" not in c for c in cards)
        native_42, native_46, _ = _calls_to(mock_context, "/dataset/native")
        assert native_42.kwargs["json"]["parameters"] == [
            {"id": "p1", "type": "string/=", "target": REGION_TARGET, "value": ["West"]}
        ]
        assert native_46.kwargs["json"]["parameters"] == [
            {"id": "p2", "type": "category", "target": SERIES_TARGET, "value": ["Gizmo"]}
        ]
        query_42, query_46, query_43 = _calls_to(mock_context, "/query")
        assert query_46.args[0] == f"{BASE}/api/dashboard/9/dashcard/801/card/46/query"
        assert query_46.kwargs["retry_count"] == NO_RETRY
        assert query_42.kwargs["json"] == {"parameters": [{"id": "p1", "type": "string/=", "value": ["West"]}]}
        assert query_46.kwargs["json"] == {"parameters": [{"id": "p2", "type": "category", "value": ["Gizmo"]}]}
        assert query_43.kwargs["json"] == {"parameters": []}

    @pytest.mark.asyncio
    async def test_mapping_without_card_id_belongs_to_own_question(self, mock_context):
        unlabelled = {
            **SERIES_DASHBOARD,
            "dashcards": [
                {
                    **SERIES_DASHBOARD["dashcards"][0],
                    "parameter_mappings": [{"parameter_id": "p1", "target": REGION_TARGET}],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(unlabelled), *_card_run(42), *_card_run(46)]
        await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        query_42, query_46 = _calls_to(mock_context, "/query")
        assert query_42.kwargs["json"] == {"parameters": [{"id": "p1", "type": "string/=", "value": ["West"]}]}
        assert query_46.kwargs["json"] == {"parameters": []}

    @pytest.mark.asyncio
    async def test_series_write_refused_and_others_run(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SERIES_DASHBOARD),
            *_card_run(42),
            _ok(_card(46)),
            _ok(SAMPLE_DATABASE),
            _ok({"query": "delete from returns where region = 'West'"}),
            *_card_run(43),
        ]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert result.type == ResultType.ACTION
        main, series, other = result.result.data["cards"]
        assert main["row_count"] == 3
        assert series["card_id"] == 46
        assert "Saved question 46 wasn't run" in series["error"]
        assert other["row_count"] == 3
        assert _calls_to(mock_context, "/card/46/query") == []

    @pytest.mark.asyncio
    async def test_series_count_toward_limit(self, mock_context):
        combined = {
            "id": 9,
            "parameters": [],
            "dashcards": [
                {
                    "id": 900 + i,
                    "card_id": 200 + i,
                    "card": {"name": f"Q{i}"},
                    "series": [{"id": 300 + i, "name": f"S{i}"}],
                    "parameter_mappings": [],
                }
                for i in range(13)
            ],
        }
        responses = [_ok(combined)]
        for i in range(12):
            responses.extend(_card_run(200 + i) + _card_run(300 + i))
        responses.extend(_card_run(212))
        mock_context.fetch.side_effect = responses
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        data = result.result.data
        assert data["card_count"] == 25
        assert data["skipped_card_count"] == 1
        assert data["cards"][-1]["card_id"] == 212
        assert _calls_to(mock_context, "/api/card/312") == []
        assert mock_context.fetch.call_count == 101

    @pytest.mark.asyncio
    async def test_unknown_tab(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9, "tab_id": 99}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "tab_id 99" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_dashboard_not_found(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestRunDashboardChecks:
    @pytest.mark.asyncio
    async def test_unknown_tab_rejected(self, mock_context):
        mock_context.fetch.side_effect = [_ok(RUN_DASHBOARD)]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9, "tab_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "tab_id 999" in result.result.message

    @pytest.mark.asyncio
    async def test_question_defaults_also_checked_without_them(self, mock_context):
        """A dashboard run skips the question's saved filter defaults, so the SQL is checked without them too, and
        a question that only writes when its default is left out is refused."""
        card = {
            **_card(42),
            "parameters": [
                {"id": "t1", "type": "number/=", "target": ["variable", ["template-tag", "n"]], "default": 5}
            ],
        }
        dashboard = {**RUN_DASHBOARD, "dashcards": [RUN_DASHBOARD["dashcards"][0]]}
        mock_context.fetch.side_effect = [
            _ok(dashboard),
            _ok(card),
            _ok(SAMPLE_DATABASE),
            _ok({"query": "select 1 /* 5 */"}),
            _ok({"query": "select 1; delete from orders"}),
        ]
        result = await metabase.execute_action("run_dashboard", {"dashboard_id": 9}, mock_context)
        assert "wasn't run" in result.result.data["cards"][0]["error"]
        with_default, without_default = _calls_to(mock_context, "/dataset/native")
        assert [p["id"] for p in with_default.kwargs["json"]["parameters"]] == ["p1", "t1"]
        assert [p["id"] for p in without_default.kwargs["json"]["parameters"]] == ["p1"]
        assert _calls_to(mock_context, "/query") == []
