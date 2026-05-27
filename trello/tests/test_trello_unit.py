"""
Unit tests for the Trello integration.

These tests are pure unit tests with mocked ``context.fetch`` and require no
real Trello credentials. They cover the v2 SDK ``FetchResponse``/``ActionError``
contract, the local cap and field-projection behavior of ``list_cards``, and
the ``/search``-backed ``search_cards`` action (including the ``is:open``
injection logic).
"""

from __future__ import annotations

import json
import os
import sys

import pytest
from autohive_integrations_sdk import ActionError, ActionResult, FetchResponse

# Ensure the trello package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from trello.trello import (  # noqa: E402
    AddChecklistItemAction,
    AddCommentAction,
    CreateBoardAction,
    CreateCardAction,
    CreateChecklistAction,
    CreateListAction,
    DeleteCardAction,
    DEFAULT_CARD_FIELDS,
    GetBoardAction,
    GetCardAction,
    GetCardAttachmentsAction,
    GetCurrentMemberAction,
    GetListAction,
    ListBoardsAction,
    ListCardsAction,
    ListListsAction,
    SearchCardsAction,
    UpdateBoardAction,
    UpdateCardAction,
    UpdateListAction,
    _bool_param,
    _clamp_limit,
    _project_card_fields,
    _quote_search_value,
    trello as trello_integration,
)

pytestmark = pytest.mark.unit


AUTH = {"auth_type": "custom", "credentials": {"api_key": "k", "token": "t"}}  # nosec B105

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_response(data, status: int = 200) -> FetchResponse:
    return FetchResponse(status=status, headers={}, data=data)


def _auth_ctx(mock_context):
    mock_context.auth = AUTH
    return mock_context


def _last_call_params(mock_context):
    args, kwargs = mock_context.fetch.call_args
    return kwargs.get("params") or (args[2] if len(args) > 2 else {})


def _last_call_url(mock_context):
    args, kwargs = mock_context.fetch.call_args
    return kwargs.get("url") or args[0]


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_actions_match_handlers(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        defined = set(config["actions"].keys())
        registered = set(trello_integration._action_handlers.keys())

        assert defined == registered, (
            f"Mismatch between config actions and registered handlers. "
            f"Missing handlers: {defined - registered}. "
            f"Extra handlers: {registered - defined}."
        )

    def test_version_is_2_1_0(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        assert config["version"] == "2.1.0"

    def test_search_cards_action_present(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        assert "search_cards" in config["actions"]
        props = config["actions"]["search_cards"]["input_schema"]["properties"]
        for key in (
            "card_name",
            "query",
            "board_id",
            "open_only",
            "partial",
            "limit",
            "fields",
            "include_board",
            "include_list",
        ):
            assert key in props, f"search_cards missing input: {key}"

    def test_list_cards_has_limit_and_fields(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        props = config["actions"]["list_cards"]["input_schema"]["properties"]
        assert props["limit"]["default"] == 50
        assert "fields" in props


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_bool_param_defaults(self):
        assert _bool_param(None, default=True) == "true"
        assert _bool_param(None, default=False) == "false"

    @pytest.mark.parametrize(
        "value,expected",
        [
            (True, "true"),
            (False, "false"),
            ("true", "true"),
            ("TRUE", "true"),
            ("false", "false"),
            ("0", "false"),
            ("1", "true"),
            ("yes", "true"),
        ],
    )
    def test_bool_param_coercion(self, value, expected):
        assert _bool_param(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [(0, 1), (1, 1), (50, 50), (1500, 1000), ("abc", 10), (None, 10)],
    )
    def test_clamp_limit(self, value, expected):
        assert _clamp_limit(value, default=10) == expected

    def test_quote_search_value_escapes_quotes(self):
        assert _quote_search_value('he said "hi"') == '"he said \\"hi\\""'

    def test_project_card_fields_passthrough(self):
        cards = [{"id": "1", "name": "x", "desc": "y"}]
        assert _project_card_fields(cards, "all") == cards
        assert _project_card_fields(cards, "") == cards

    def test_project_card_fields_filters(self):
        cards = [{"id": "1", "name": "x", "desc": "y", "due": "z"}]
        result = _project_card_fields(cards, "id,name")
        assert result == [{"id": "1", "name": "x"}]

    def test_project_card_fields_ignores_non_dicts(self):
        cards = [{"id": "1"}, "not-a-dict", 7]
        result = _project_card_fields(cards, "id")
        assert result == [{"id": "1"}, "not-a-dict", 7]


# ---------------------------------------------------------------------------
# Response unwrap / ActionError contract
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_non_2xx_returns_action_error_with_trello_message(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"message": "invalid token"}, status=401)

        result = await GetCurrentMemberAction().execute({}, mock_context)

        assert isinstance(result, ActionError)
        assert "invalid token" in result.message

    @pytest.mark.asyncio
    async def test_non_2xx_falls_back_to_status_when_body_empty(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response(None, status=500)

        result = await GetCurrentMemberAction().execute({}, mock_context)

        assert isinstance(result, ActionError)
        assert "500" in result.message

    @pytest.mark.asyncio
    async def test_fetch_exception_becomes_action_error(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.side_effect = Exception("network down")

        result = await GetCurrentMemberAction().execute({}, mock_context)

        assert isinstance(result, ActionError)
        assert "network down" in result.message


# ---------------------------------------------------------------------------
# Member / Board / List / Card success paths
# ---------------------------------------------------------------------------


class TestMemberAndBoardHandlers:
    @pytest.mark.asyncio
    async def test_get_current_member_success(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "m1", "fullName": "Alice"})

        result = await GetCurrentMemberAction().execute({}, mock_context)

        assert result.data == {"member": {"id": "m1", "fullName": "Alice"}}
        assert _last_call_url(mock_context) == "https://api.trello.com/1/members/me"
        assert _last_call_params(mock_context) == {"key": "k", "token": "t"}  # nosec B105

    @pytest.mark.asyncio
    async def test_create_board_sends_required_and_optional_params(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "b1"})

        result = await CreateBoardAction().execute(
            {
                "name": "My Board",
                "desc": "desc",
                "defaultLists": False,
                "prefs_permissionLevel": "private",
            },
            mock_context,
        )

        assert result.data == {"board": {"id": "b1"}}
        params = _last_call_params(mock_context)
        assert params["name"] == "My Board"
        assert params["desc"] == "desc"
        assert params["defaultLists"] == "false"
        assert params["prefs_permissionLevel"] == "private"
        assert params["key"] == "k"

    @pytest.mark.asyncio
    async def test_get_board_passes_fields(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "b1"})

        await GetBoardAction().execute({"board_id": "b1", "fields": "name,desc"}, mock_context)

        assert _last_call_url(mock_context) == "https://api.trello.com/1/boards/b1"
        assert _last_call_params(mock_context)["fields"] == "name,desc"

    @pytest.mark.asyncio
    async def test_update_board_maps_permission_level_to_slash_param(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "b1"})

        await UpdateBoardAction().execute(
            {"board_id": "b1", "prefs_permissionLevel": "org", "closed": True},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["prefs/permissionLevel"] == "org"
        assert params["closed"] == "true"

    @pytest.mark.asyncio
    async def test_list_boards_returns_count(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([{"id": "b1"}, {"id": "b2"}])

        result = await ListBoardsAction().execute({"filter": "open"}, mock_context)

        assert result.data["count"] == 2
        assert len(result.data["boards"]) == 2


class TestListHandlers:
    @pytest.mark.asyncio
    async def test_create_list_sends_idBoard(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "l1"})

        await CreateListAction().execute({"board_id": "b1", "name": "To Do"}, mock_context)

        params = _last_call_params(mock_context)
        assert params["idBoard"] == "b1"
        assert params["name"] == "To Do"

    @pytest.mark.asyncio
    async def test_get_list_success(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "l1"})

        result = await GetListAction().execute({"list_id": "l1"}, mock_context)

        assert result.data == {"list": {"id": "l1"}}

    @pytest.mark.asyncio
    async def test_update_list_sends_only_provided_fields(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "l1"})

        await UpdateListAction().execute({"list_id": "l1", "name": "Doing"}, mock_context)

        params = _last_call_params(mock_context)
        assert params["name"] == "Doing"
        assert "closed" not in params
        assert "pos" not in params

    @pytest.mark.asyncio
    async def test_list_lists_returns_count(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([{"id": "l1"}])

        result = await ListListsAction().execute({"board_id": "b1"}, mock_context)

        assert result.data == {"lists": [{"id": "l1"}], "count": 1}


class TestCardCrudHandlers:
    @pytest.mark.asyncio
    async def test_create_card_joins_member_and_label_ids(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "c1"})

        await CreateCardAction().execute(
            {
                "list_id": "l1",
                "name": "Bug",
                "idMembers": ["m1", "m2"],
                "idLabels": ["lab1", "lab2"],
            },
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["idList"] == "l1"
        assert params["idMembers"] == "m1,m2"
        assert params["idLabels"] == "lab1,lab2"

    @pytest.mark.asyncio
    async def test_get_card_success(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "c1"})

        result = await GetCardAction().execute({"card_id": "c1"}, mock_context)

        assert result.data == {"card": {"id": "c1"}}

    @pytest.mark.asyncio
    async def test_update_card_due_complete_serialized(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "c1"})

        await UpdateCardAction().execute(
            {"card_id": "c1", "dueComplete": True, "idList": "l9"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["dueComplete"] == "true"
        assert params["idList"] == "l9"

    @pytest.mark.asyncio
    async def test_delete_card_returns_acknowledgement(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response(None, status=200)

        result = await DeleteCardAction().execute({"card_id": "c1"}, mock_context)

        assert result.data == {"deleted": True, "card_id": "c1"}

    @pytest.mark.asyncio
    async def test_delete_card_error_returns_action_error(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"message": "not found"}, status=404)

        result = await DeleteCardAction().execute({"card_id": "c1"}, mock_context)

        assert isinstance(result, ActionError)
        assert "not found" in result.message


# ---------------------------------------------------------------------------
# get_card_attachments behavior
# ---------------------------------------------------------------------------


class TestGetCardAttachments:
    @pytest.mark.asyncio
    async def test_returns_attachments(self, mock_context):
        _auth_ctx(mock_context)
        attachments = [
            {
                "id": "att1",
                "name": "file.pdf",
                "url": "https://example.com/file.pdf",
                "mimeType": "application/pdf",
                "isUpload": True,
            },
            {
                "id": "att2",
                "name": "image.png",
                "url": "https://example.com/image.png",
                "mimeType": "image/png",
                "isUpload": True,
            },
        ]
        mock_context.fetch.return_value = _fetch_response(attachments)

        result = await GetCardAttachmentsAction().execute({"card_id": "c1"}, mock_context)

        assert isinstance(result, ActionResult)
        assert result.data["count"] == 2
        assert result.data["attachments"][0]["id"] == "att1"
        assert result.data["attachments"][1]["name"] == "image.png"

    @pytest.mark.asyncio
    async def test_empty_attachments(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        result = await GetCardAttachmentsAction().execute({"card_id": "c1"}, mock_context)

        assert isinstance(result, ActionResult)
        assert result.data["attachments"] == []
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_forwards_filter_param(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await GetCardAttachmentsAction().execute({"card_id": "c1", "filter": "cover"}, mock_context)

        params = _last_call_params(mock_context)
        assert params["filter"] == "cover"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"message": "not found"}, status=404)

        result = await GetCardAttachmentsAction().execute({"card_id": "bad"}, mock_context)

        assert isinstance(result, ActionError)
        assert "not found" in result.message


# ---------------------------------------------------------------------------
# list_cards behavior
# ---------------------------------------------------------------------------


class TestListCards:
    @pytest.mark.asyncio
    async def test_requires_list_or_board_id(self, mock_context):
        _auth_ctx(mock_context)

        result = await ListCardsAction().execute({}, mock_context)

        assert isinstance(result, ActionError)
        assert "list_id" in result.message and "board_id" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_server_side_limit_and_fields(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute({"list_id": "l1", "limit": 25}, mock_context)

        params = _last_call_params(mock_context)
        # Trello's /cards endpoints DO support server-side limit; we send it.
        assert params["limit"] == 25
        assert params["fields"] == DEFAULT_CARD_FIELDS

    @pytest.mark.asyncio
    async def test_forwards_before_and_since_cursors(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute(
            {"board_id": "b1", "before": "card-xyz", "since": "card-abc"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["before"] == "card-xyz"
        assert params["since"] == "card-abc"

    @pytest.mark.asyncio
    async def test_returns_next_before_cursor_when_full_page(self, mock_context):
        _auth_ctx(mock_context)
        # Limit=3, return exactly 3 cards -> cursor is the min (oldest) id.
        raw = [{"id": f"c{i}", "name": f"c{i}"} for i in range(3)]
        mock_context.fetch.return_value = _fetch_response(raw)

        result = await ListCardsAction().execute({"board_id": "b1", "limit": 3}, mock_context)

        assert result.data["count"] == 3
        assert result.data["next_before"] == "c0"

    @pytest.mark.asyncio
    async def test_cursor_uses_oldest_id_not_last_element(self, mock_context):
        """Cards may arrive in board/list position order, not creation order.

        The cursor must be the lexicographically smallest ID (oldest ObjectId),
        not cards[-1]["id"], which would produce a wrong cursor when cards have
        been manually reordered.
        """
        _auth_ctx(mock_context)
        # Simulate cards in board-position order (not creation order).
        # ObjectId hex: smaller value = earlier creation time.
        # Here "5f900000" is oldest, "63f00000" is newest, "61000000" is middle.
        raw = [
            {"id": "63f00000", "name": "newest"},  # position 1
            {"id": "61000000", "name": "middle"},  # position 2
            {"id": "5f900000", "name": "oldest"},  # position 3 (last element)
        ]
        mock_context.fetch.return_value = _fetch_response(raw)

        result = await ListCardsAction().execute({"board_id": "b1", "limit": 3}, mock_context)

        # Correct: oldest id (min), not last element "5f900000" == last here but
        # the point is we derive it via min(), not index.
        assert result.data["next_before"] == "5f900000"
        # Verify it is NOT the last element's id when order differs.
        reordered_raw = [
            {"id": "5f900000", "name": "oldest"},  # position 1
            {"id": "63f00000", "name": "newest"},  # position 2
            {"id": "61000000", "name": "middle"},  # position 3 (last)
        ]
        mock_context.fetch.return_value = _fetch_response(reordered_raw)
        result2 = await ListCardsAction().execute({"board_id": "b1", "limit": 3}, mock_context)
        # last element is "61000000" but correct cursor is still "5f900000"
        assert result2.data["next_before"] == "5f900000"

    @pytest.mark.asyncio
    async def test_no_next_before_when_partial_page(self, mock_context):
        _auth_ctx(mock_context)
        # Asked for 50, got 2 -> no more results.
        raw = [{"id": "c1"}, {"id": "c2"}]
        mock_context.fetch.return_value = _fetch_response(raw)

        result = await ListCardsAction().execute({"list_id": "l1", "limit": 50}, mock_context)

        assert "next_before" not in result.data

    @pytest.mark.asyncio
    async def test_slices_defensively_if_trello_returns_too_many(self, mock_context):
        _auth_ctx(mock_context)
        # Trello returned 80 even though we asked for 10 — slice locally.
        raw = [{"id": f"c{i}", "name": f"c{i}"} for i in range(80)]
        mock_context.fetch.return_value = _fetch_response(raw)

        result = await ListCardsAction().execute({"board_id": "b1", "limit": 10}, mock_context)

        assert result.data["count"] == 10
        assert len(result.data["cards"]) == 10
        # Next-page cursor is the min (oldest) id in the trimmed page.
        assert result.data["next_before"] == "c0"

    @pytest.mark.asyncio
    async def test_projects_compact_fields_client_side(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response(
            [{"id": "c1", "name": "x", "desc": "should-be-stripped", "extra": "noise"}]
        )

        result = await ListCardsAction().execute(
            {"list_id": "l1", "fields": "id,name"},
            mock_context,
        )

        assert result.data["cards"] == [{"id": "c1", "name": "x"}]

    @pytest.mark.asyncio
    async def test_all_fields_passthrough(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([{"id": "c1", "name": "x", "desc": "kept", "extra": "kept"}])

        result = await ListCardsAction().execute(
            {"list_id": "l1", "fields": "all"},
            mock_context,
        )

        assert result.data["cards"][0]["desc"] == "kept"
        assert result.data["cards"][0]["extra"] == "kept"

    @pytest.mark.asyncio
    async def test_uses_list_endpoint_when_list_id_given(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute({"list_id": "l1"}, mock_context)

        assert _last_call_url(mock_context) == "https://api.trello.com/1/lists/l1/cards"

    @pytest.mark.asyncio
    async def test_uses_board_endpoint_when_board_id_given(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute({"board_id": "b1"}, mock_context)

        assert _last_call_url(mock_context) == "https://api.trello.com/1/boards/b1/cards"

    @pytest.mark.asyncio
    async def test_default_filter_is_open(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute({"board_id": "b1"}, mock_context)

        assert _last_call_params(mock_context)["filter"] == "open"

    @pytest.mark.asyncio
    async def test_filter_and_before_are_both_forwarded(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute(
            {"board_id": "b1", "filter": "closed", "before": "card-zzz"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["filter"] == "closed"
        assert params["before"] == "card-zzz"

    @pytest.mark.asyncio
    async def test_empty_page_yields_no_cursor(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        result = await ListCardsAction().execute({"board_id": "b1"}, mock_context)

        assert result.data["count"] == 0
        assert result.data["cards"] == []
        assert "next_before" not in result.data

    @pytest.mark.asyncio
    async def test_limit_1_full_page_emits_cursor(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([{"id": "only-one"}])

        result = await ListCardsAction().execute({"board_id": "b1", "limit": 1}, mock_context)

        assert result.data["count"] == 1
        assert result.data["next_before"] == "only-one"

    @pytest.mark.asyncio
    async def test_fields_without_id_still_emits_cursor(self, mock_context):
        """User asks for fields='name' (no id); we must still produce next_before.

        The handler must request `id` from Trello internally while preserving
        the user's projection in the returned cards.
        """
        _auth_ctx(mock_context)
        raw = [{"id": f"c{i}", "name": f"n{i}"} for i in range(5)]
        mock_context.fetch.return_value = _fetch_response(raw)

        result = await ListCardsAction().execute(
            {"board_id": "b1", "limit": 5, "fields": "name"},
            mock_context,
        )

        # Internal API request augments fields with id.
        api_fields = _last_call_params(mock_context)["fields"]
        assert "id" in [f.strip() for f in api_fields.split(",")]
        assert "name" in [f.strip() for f in api_fields.split(",")]

        # User projection still applies to returned cards.
        assert result.data["cards"] == [{"name": f"n{i}"} for i in range(5)]
        # Cursor is the min (oldest) id across the page.
        assert result.data["next_before"] == "c0"

    @pytest.mark.asyncio
    async def test_fields_all_passes_through_unchanged(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response([])

        await ListCardsAction().execute({"board_id": "b1", "fields": "all"}, mock_context)

        assert _last_call_params(mock_context)["fields"] == "all"


# ---------------------------------------------------------------------------
# search_cards behavior
# ---------------------------------------------------------------------------


class TestSearchCards:
    @pytest.mark.asyncio
    async def test_requires_card_name_or_query(self, mock_context):
        _auth_ctx(mock_context)

        result = await SearchCardsAction().execute({}, mock_context)

        assert isinstance(result, ActionError)
        assert "card_name" in result.message and "query" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_basic_card_name_search_builds_query(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response(
            {"cards": [{"id": "c1", "name": "Bug"}], "options": {"foo": "bar"}}
        )

        result = await SearchCardsAction().execute({"card_name": "Bug"}, mock_context)

        params = _last_call_params(mock_context)
        assert _last_call_url(mock_context) == "https://api.trello.com/1/search"
        assert params["modelTypes"] == "cards"
        assert params["query"] == 'name:"Bug" is:open'
        assert params["cards_limit"] == 10
        assert params["partial"] == "true"
        assert params["card_board"] == "true"
        assert params["card_list"] == "true"
        assert params["card_members"] == "false"
        assert params["card_attachments"] == "false"

        assert result.data["count"] == 1
        assert result.data["cards"][0]["id"] == "c1"
        assert result.data["options"] == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_quotes_card_name_with_embedded_quote(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute({"card_name": 'he said "hi"'}, mock_context)

        params = _last_call_params(mock_context)
        assert params["query"] == 'name:"he said \\"hi\\"" is:open'

    @pytest.mark.asyncio
    async def test_does_not_append_is_open_when_user_specified_is_closed(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute(
            {"card_name": "foo", "query": "is:closed"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert "is:open" not in params["query"]
        assert "is:closed" in params["query"]

    @pytest.mark.asyncio
    async def test_does_not_append_is_open_when_user_specified_is_archived(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute({"query": "label:red is:archived"}, mock_context)

        params = _last_call_params(mock_context)
        assert "is:open" not in params["query"]

    @pytest.mark.asyncio
    async def test_does_not_append_is_open_when_user_specified_negated_open(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute({"query": "-is:open foo"}, mock_context)

        params = _last_call_params(mock_context)
        assert " is:open" not in params["query"]

    @pytest.mark.asyncio
    async def test_open_only_false_disables_injection(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute(
            {"card_name": "foo", "open_only": False},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert "is:open" not in params["query"]

    @pytest.mark.asyncio
    async def test_scoping_to_board_and_org(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute(
            {"card_name": "x", "board_id": "b1", "organization_id": "o1"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["idBoards"] == "b1"
        assert params["idOrganizations"] == "o1"

    @pytest.mark.asyncio
    async def test_handles_list_response_body(self, mock_context):
        _auth_ctx(mock_context)
        # Some Trello clients have observed list-shaped responses; ensure we cope.
        mock_context.fetch.return_value = _fetch_response([{"id": "c1"}])

        result = await SearchCardsAction().execute({"card_name": "x"}, mock_context)

        assert result.data["count"] == 1
        assert result.data["options"] == {}

    @pytest.mark.asyncio
    async def test_handles_none_body_safely(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response(None, status=200)

        result = await SearchCardsAction().execute({"card_name": "x"}, mock_context)

        assert result.data == {"cards": [], "count": 0, "options": {}}

    @pytest.mark.asyncio
    async def test_non_2xx_returns_action_error(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"message": "unauthorized"}, status=401)

        result = await SearchCardsAction().execute({"card_name": "x"}, mock_context)

        assert isinstance(result, ActionError)
        assert "unauthorized" in result.message

    @pytest.mark.asyncio
    async def test_limit_is_clamped_for_cards_limit(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"cards": []})

        await SearchCardsAction().execute(
            {"card_name": "x", "limit": 9999},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["cards_limit"] == 1000


# ---------------------------------------------------------------------------
# Checklist / comment handlers
# ---------------------------------------------------------------------------


class TestChecklistAndCommentHandlers:
    @pytest.mark.asyncio
    async def test_create_checklist(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "cl1"})

        result = await CreateChecklistAction().execute({"card_id": "c1", "name": "Steps"}, mock_context)

        params = _last_call_params(mock_context)
        assert params["idCard"] == "c1"
        assert params["name"] == "Steps"
        assert result.data == {"checklist": {"id": "cl1"}}

    @pytest.mark.asyncio
    async def test_add_checklist_item_serializes_checked(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "ci1"})

        await AddChecklistItemAction().execute(
            {"checklist_id": "cl1", "name": "Task", "checked": True, "pos": "top"},
            mock_context,
        )

        params = _last_call_params(mock_context)
        assert params["checked"] == "true"
        assert params["pos"] == "top"

    @pytest.mark.asyncio
    async def test_add_comment(self, mock_context):
        _auth_ctx(mock_context)
        mock_context.fetch.return_value = _fetch_response({"id": "ac1"})

        result = await AddCommentAction().execute({"card_id": "c1", "text": "hi"}, mock_context)

        params = _last_call_params(mock_context)
        assert params["text"] == "hi"
        assert result.data == {"comment": {"id": "ac1"}}
