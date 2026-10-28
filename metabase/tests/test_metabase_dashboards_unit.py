import pytest
from autohive_integrations_sdk import HTTPError, ResultType

from metabase.metabase import metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


EXISTING_DASHCARD = {
    "id": 501,
    "card_id": 42,
    "card": {"id": 42, "name": "Weekly signups", "display": "line"},
    "dashboard_id": 9,
    "dashboard_tab_id": None,
    "row": 0,
    "col": 0,
    "size_x": 12,
    "size_y": 6,
    "series": [],
    "parameter_mappings": [{"parameter_id": "p1", "card_id": 42, "target": ["variable", ["template-tag", "x"]]}],
    "visualization_settings": {"graph.dimensions": ["week"]},
    "created_at": "2026-10-01T00:00:00Z",
    "entity_id": "abc",
}
TEXT_DASHCARD = {
    "id": 502,
    "card_id": None,
    "card": None,
    "row": 6,
    "col": 0,
    "size_x": 24,
    "size_y": 2,
    "series": [],
    "parameter_mappings": [],
    "visualization_settings": {"text": "# Heading"},
}
SAMPLE_DASHBOARD = {
    "id": 9,
    "name": "Growth",
    "description": "KPIs",
    "collection_id": 4,
    "archived": False,
    "tabs": [],
    "parameters": [{"id": "p1", "name": "Region", "slug": "region", "type": "string/="}],
    "dashcards": [EXISTING_DASHCARD, TEXT_DASHCARD],
}


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_DASHBOARD)
        result = await metabase.execute_action("get_dashboard", {"dashboard_id": 9}, mock_context)
        data = result.result.data
        assert data["name"] == "Growth"
        assert data["parameters"] == [{"id": "p1", "name": "Region", "slug": "region", "type": "string/="}]
        assert data["cards"][0] == {
            "dashcard_id": 501,
            "card_id": 42,
            "card_name": "Weekly signups",
            "display": "line",
            "row": 0,
            "col": 0,
            "size_x": 12,
            "size_y": 6,
            "dashboard_tab_id": None,
        }

    @pytest.mark.asyncio
    async def test_text_card_has_no_question(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_DASHBOARD)
        result = await metabase.execute_action("get_dashboard", {"dashboard_id": 9}, mock_context)
        assert result.result.data["cards"][1]["card_id"] is None
        assert result.result.data["cards"][1]["card_name"] is None

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_DASHBOARD)
        await metabase.execute_action("get_dashboard", {"dashboard_id": 9}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/dashboard/9"
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action("get_dashboard", {"dashboard_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateDashboard:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 60, "name": "Agent KPIs", "collection_id": 4})
        result = await metabase.execute_action(
            "create_dashboard", {"name": "Agent KPIs", "description": "d", "collection_id": 4}, mock_context
        )
        assert result.result.data == {"id": 60, "name": "Agent KPIs", "collection_id": 4}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/dashboard"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"name": "Agent KPIs", "description": "d", "collection_id": 4}

    @pytest.mark.asyncio
    async def test_minimal_body(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 61, "name": "X"})
        await metabase.execute_action("create_dashboard", {"name": "X"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "X"}

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action("create_dashboard", {"name": ""}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({"name": "X"})
        result = await metabase.execute_action("create_dashboard", {"name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestAddQuestionToDashboard:
    @staticmethod
    def _updated(new_card_id=77, new_dashcard_id=503):
        new = {"id": new_dashcard_id, "card_id": new_card_id, "row": 8, "col": 0, "size_x": 12, "size_y": 6}
        return {**SAMPLE_DASHBOARD, "dashcards": [EXISTING_DASHCARD, TEXT_DASHCARD, new]}

    @pytest.mark.asyncio
    async def test_keeps_existing_cards_and_places_below(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77}, mock_context
        )
        assert result.type == ResultType.ACTION
        put = mock_context.fetch.call_args_list[1]
        assert put.args[0] == f"{BASE}/api/dashboard/9"
        assert put.kwargs["method"] == "PUT"
        dashcards = put.kwargs["json"]["dashcards"]
        assert [dc["id"] for dc in dashcards] == [501, 502, -1]
        # existing cards are sent back with their settings, without read-only fields
        assert dashcards[0]["parameter_mappings"] == EXISTING_DASHCARD["parameter_mappings"]
        assert dashcards[0]["visualization_settings"] == {"graph.dimensions": ["week"]}
        assert "card" not in dashcards[0] and "created_at" not in dashcards[0] and "entity_id" not in dashcards[0]
        assert dashcards[2] == {
            "id": -1,
            "card_id": 77,
            "row": 8,
            "col": 0,
            "size_x": 12,
            "size_y": 6,
            "series": [],
            "parameter_mappings": [],
            "visualization_settings": {},
        }
        assert "tabs" not in put.kwargs["json"]

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_DASHBOARD), _ok(self._updated())]
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77}, mock_context
        )
        assert result.result.data == {
            "dashboard_id": 9,
            "dashcard_id": 503,
            "card_id": 77,
            "row": 8,
            "col": 0,
            "size_x": 12,
            "size_y": 6,
            "card_count": 3,
        }

    @pytest.mark.asyncio
    async def test_empty_dashboard_starts_at_top(self, mock_context):
        empty = {**SAMPLE_DASHBOARD, "dashcards": []}
        mock_context.fetch.side_effect = [_ok(empty), _ok({**empty, "dashcards": [{"id": 1, "card_id": 77}]})]
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77, "width": 24, "height": 4}, mock_context
        )
        new = mock_context.fetch.call_args_list[1].kwargs["json"]["dashcards"][0]
        assert (new["row"], new["size_x"], new["size_y"]) == (0, 24, 4)
        assert result.result.data["dashcard_id"] == 1

    @pytest.mark.asyncio
    async def test_tabs_default_to_first_tab(self, mock_context):
        tabbed = {
            **SAMPLE_DASHBOARD,
            "tabs": [{"id": 11, "name": "Overview", "position": 0}, {"id": 12, "name": "Detail", "position": 1}],
            "dashcards": [
                {**EXISTING_DASHCARD, "dashboard_tab_id": 11},
                {**TEXT_DASHCARD, "dashboard_tab_id": 12, "row": 20},
            ],
        }
        mock_context.fetch.side_effect = [_ok(tabbed), _ok(tabbed)]
        await metabase.execute_action("add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77}, mock_context)
        body = mock_context.fetch.call_args_list[1].kwargs["json"]
        new = body["dashcards"][-1]
        assert new["dashboard_tab_id"] == 11
        assert new["row"] == 6  # only cards on tab 11 count
        assert body["tabs"] == [{"id": 11, "name": "Overview"}, {"id": 12, "name": "Detail"}]

    @pytest.mark.asyncio
    async def test_explicit_tab(self, mock_context):
        tabbed = {
            **SAMPLE_DASHBOARD,
            "tabs": [{"id": 11, "name": "Overview"}, {"id": 12, "name": "Detail"}],
            "dashcards": [{**EXISTING_DASHCARD, "dashboard_tab_id": 11}],
        }
        mock_context.fetch.side_effect = [_ok(tabbed), _ok(tabbed)]
        await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77, "tab_id": 12}, mock_context
        )
        new = mock_context.fetch.call_args_list[1].kwargs["json"]["dashcards"][-1]
        assert (new["dashboard_tab_id"], new["row"]) == (12, 0)

    @pytest.mark.asyncio
    async def test_dashboard_not_found_skips_put(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found.", "Not found.")
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 999, "question_id": 77}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_put_error(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_DASHBOARD),
            HTTPError(400, "x", {"message": "Card 77 does not exist"}),
        ]
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Card 77 does not exist" in result.result.message

    @pytest.mark.asyncio
    async def test_width_over_grid_rejected(self, mock_context):
        result = await metabase.execute_action(
            "add_question_to_dashboard", {"dashboard_id": 9, "question_id": 77, "width": 30}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
