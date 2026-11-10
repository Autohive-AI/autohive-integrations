import asyncio

import pytest
from autohive_integrations_sdk import HTTPError, ResultType

from metabase.metabase import NO_RETRY, SEGMENT_REVISION_MESSAGE, ArchiveItemAction, RestoreItemAction, metabase
from metabase.tests.conftest import BASE, ok as _ok

pytestmark = pytest.mark.unit


def _not_found():
    return HTTPError(404, "Not found.", "Not found.")


# ---- Sample data ----

SAMPLE_TABLE = {"id": 31, "db_id": 3, "name": "ORDERS", "display_name": "Orders", "schema": "PUBLIC"}
ACTIVE_FILTER = [">", ["field", 120, None], 100]
SAMPLE_SEGMENT = {
    "id": 7,
    "name": "Big orders",
    "description": "Orders over $100",
    "table_id": 31,
    "archived": False,
    "definition": {"source-table": 31, "filter": ACTIVE_FILTER},
}
FULL_QUERY_SEGMENT = {
    "id": 8,
    "name": "Active customers",
    "description": None,
    "table_id": 32,
    "archived": False,
    "definition": {
        "database": 3,
        "type": "query",
        "query": {"source-table": 32, "filter": ["=", ["field", 7, None], "active"]},
    },
}
MBQL5_SEGMENT = {
    "id": 9,
    "name": "Refunded",
    "description": None,
    "table_id": 31,
    "archived": True,
    "definition": {
        "lib/type": "mbql/query",
        "database": 3,
        "stages": [
            {"lib/type": "mbql.stage/mbql", "source-table": 31, "filters": [["=", {}, ["field", {}, 121], "refunded"]]}
        ],
    },
}

SAMPLE_COLLECTION = {"id": 31, "name": "Finance", "description": "Money things", "location": "/28/"}

SIGNUPS_SQL = "select count(*) from signups"
SAMPLE_CARD = {
    "id": 42,
    "name": "Daily signups",
    "database_id": 3,
    "dataset_query": {"database": 3, "type": "native", "native": {"query": SIGNUPS_SQL, "template-tags": {}}},
    "parameters": [],
}
CHURN_CARD = {**SAMPLE_CARD, "id": 43, "name": "Churn"}
REGION_CARD = {
    **SAMPLE_CARD,
    "parameters": [
        {"id": "p1", "type": "category", "target": ["variable", ["template-tag", "region"]], "default": "NZ"}
    ],
}
SAMPLE_DATABASE = {"id": 3, "engine": "postgres"}
OLD_METABASE = {"version": {"tag": "v0.49.25"}}
NEW_METABASE = {"version": {"tag": "v0.56.3"}}
UPGRADES_CARD = {**SAMPLE_CARD, "id": 44, "name": "Upgrades"}
PLAN_FILTER = {"id": "f1", "name": "Plan", "slug": "plan", "type": "string/=", "default": "pro"}
PLAN_TAG_TARGET = ["variable", ["template-tag", "plan"]]
PLAN_FIELD_TARGET = ["dimension", ["field", 88, None]]


def _checks(card=SAMPLE_CARD, sql=SIGNUPS_SQL):
    """Responses for the read-only check of one saved question: GET card, GET database, POST /dataset/native."""
    return [_ok(card), _ok(SAMPLE_DATABASE), _ok({"query": sql})]


def _compiled_parameters(mock_context):
    return [
        c.kwargs["json"]["parameters"]
        for c in mock_context.fetch.call_args_list
        if c.args[0] == f"{BASE}/api/dataset/native"
    ]


def _urls(mock_context):
    return [(c.kwargs["method"], c.args[0]) for c in mock_context.fetch.call_args_list]


def _check_calls(card_id):
    return [
        ("GET", f"{BASE}/api/card/{card_id}"),
        ("GET", f"{BASE}/api/database/3"),
        ("POST", f"{BASE}/api/dataset/native"),
    ]


NEW_ALERT = {
    "id": 40,
    "payload_type": "notification/card",
    "payload": {"card_id": 42, "send_condition": "has_result", "send_once": False},
    "active": True,
    "handlers": [
        {
            "channel_type": "channel/email",
            "recipients": [
                {"type": "notification-recipient/user", "user_id": 5, "user": {"id": 5, "email": "ana@example.com"}},
                {"type": "notification-recipient/raw-value", "details": {"value": "ops@example.com"}},
                {"type": "notification-recipient/user", "user_id": 6},
            ],
        }
    ],
    "subscriptions": [{"type": "notification-subscription/cron", "cron_schedule": "0 0 9 * * ? *"}],
    "created_at": "2026-10-01T00:00:00Z",
    "creator_id": 1,
}
LEGACY_ALERT = {
    "id": 12,
    "card": {"id": 42, "name": "Daily signups", "include_csv": False, "include_xls": False},
    "alert_condition": "goal",
    "alert_above_goal": True,
    "alert_first_only": True,
    "archived": False,
    "channels": [
        {
            "channel_type": "email",
            "schedule_type": "daily",
            "schedule_hour": 9,
            "schedule_day": None,
            "recipients": [{"id": 5, "email": "ana@example.com"}, {"email": "ops@example.com"}],
        }
    ],
}

SUB_DASHBOARD = {
    "id": 9,
    "name": "Growth",
    "dashcards": [
        {"id": 501, "card_id": 42, "card": {"id": 42, "name": "Weekly signups"}},
        {"id": 502, "card_id": None, "card": None, "visualization_settings": {"text": "# Heading"}},
        {"id": 503, "card_id": 43, "card": {"id": 43, "name": "Churn"}},
    ],
}
SLACK_CHANNEL = {
    "id": 71,
    "channel_type": "slack",
    "schedule_type": "daily",
    "schedule_hour": 8,
    "details": {"channel": "#growth"},
    "recipients": [],
}
EMAIL_CHANNEL = {
    "id": 70,
    "channel_type": "email",
    "enabled": True,
    "schedule_type": "weekly",
    "schedule_hour": 7,
    "schedule_day": "fri",
    "schedule_frame": None,
    "recipients": [
        {"id": 5, "email": "ana@example.com", "common_name": "Ana Lee"},
        {"email": "ops@example.com"},
    ],
}
SAMPLE_PULSE = {
    "id": 15,
    "name": "Growth weekly",
    "dashboard_id": 9,
    "archived": False,
    "skip_if_empty": True,
    "channels": [SLACK_CHANNEL, EMAIL_CHANNEL],
}

SAMPLE_USERS = {
    "data": [
        {"id": 5, "common_name": "Ana Lee", "email": "ana@example.com", "is_active": True},
        {"id": 6, "common_name": "Ben Ng", "email": "ben@example.com", "is_active": False},
        {"id": 7, "common_name": "Cy Ito", "email": "cy@example.com"},
    ],
    "total": 23,
    "limit": 50,
    "offset": 0,
}

SAMPLE_EVENT = {
    "id": 90,
    "timeline_id": 4,
    "name": "v2 launch",
    "description": "Big release",
    "timestamp": "2026-11-01T00:00:00Z",
    "archived": False,
    "icon": "star",
    "creator_id": 1,
}
SAMPLE_TIMELINES = [
    {
        "id": 4,
        "name": "Releases",
        "description": None,
        "collection_id": 12,
        "archived": False,
        "events": [SAMPLE_EVENT],
    },
    {"id": 5, "name": "Campaigns", "description": "Marketing", "collection_id": None, "archived": False},
]


# ---- Segments ----


class TestListSegments:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_SEGMENT, FULL_QUERY_SEGMENT])
        result = await metabase.execute_action("list_segments", {}, mock_context)
        data = result.result.data
        assert data["count"] == 2
        assert data["segments"][0] == {
            "id": 7,
            "name": "Big orders",
            "description": "Orders over $100",
            "table_id": 31,
            "archived": False,
            "filter": ACTIVE_FILTER,
        }

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_segments", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/segment"
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_filters_by_table(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_SEGMENT, FULL_QUERY_SEGMENT, MBQL5_SEGMENT])
        result = await metabase.execute_action("list_segments", {"table_id": 31}, mock_context)
        assert [s["id"] for s in result.result.data["segments"]] == [7, 9]

    @pytest.mark.asyncio
    async def test_full_query_definition_filter(self, mock_context):
        mock_context.fetch.return_value = _ok([FULL_QUERY_SEGMENT])
        result = await metabase.execute_action("list_segments", {}, mock_context)
        assert result.result.data["segments"][0]["filter"] == ["=", ["field", 7, None], "active"]

    @pytest.mark.asyncio
    async def test_mbql5_stage_filters(self, mock_context):
        mock_context.fetch.return_value = _ok([MBQL5_SEGMENT])
        result = await metabase.execute_action("list_segments", {}, mock_context)
        segment = result.result.data["segments"][0]
        assert segment["filter"] == [["=", {}, ["field", {}, 121], "refunded"]]
        assert segment["archived"] is True

    @pytest.mark.asyncio
    async def test_missing_definition(self, mock_context):
        mock_context.fetch.return_value = _ok([{"id": 10, "name": "Odd", "table_id": 31}])
        result = await metabase.execute_action("list_segments", {}, mock_context)
        assert result.result.data["segments"][0]["filter"] is None

    @pytest.mark.asyncio
    async def test_empty(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        result = await metabase.execute_action("list_segments", {}, mock_context)
        assert result.result.data == {"segments": [], "count": 0}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("list_segments", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message


class TestCreateSegment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        created = {**FULL_QUERY_SEGMENT, "id": 11, "name": "Big orders", "table_id": 31}
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), _ok(created)]
        result = await metabase.execute_action(
            "create_segment",
            {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER, "description": "Orders over $100"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == 11

    @pytest.mark.asyncio
    async def test_request_sends_inner_query_first(self, mock_context):
        # Metabase 0.49 saves a full query too, but then the segment matches no rows.
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), _ok({**SAMPLE_SEGMENT, "id": 11})]
        await metabase.execute_action(
            "create_segment",
            {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER, "description": "Orders over $100"},
            mock_context,
        )
        get, post = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/table/31"
        assert get.kwargs["method"] == "GET"
        assert post.args[0] == f"{BASE}/api/segment"
        assert post.kwargs["method"] == "POST"
        assert post.kwargs["retry_count"] == NO_RETRY
        assert post.kwargs["json"] == {
            "name": "Big orders",
            "table_id": 31,
            "definition": {"source-table": 31, "filter": ACTIVE_FILTER},
            "description": "Orders over $100",
        }

    @pytest.mark.asyncio
    async def test_full_query_sent_when_metabase_needs_it(self, mock_context):
        needs_type = HTTPError(400, "Query must include :lib/type or :type", "Query must include :lib/type or :type")
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), needs_type, _ok({**SAMPLE_SEGMENT, "id": 11})]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.result.data["id"] == 11
        first, second = [c.kwargs["json"]["definition"] for c in mock_context.fetch.call_args_list[1:]]
        assert first == {"source-table": 31, "filter": ACTIVE_FILTER}
        assert second == {"database": 3, "type": "query", "query": {"source-table": 31, "filter": ACTIVE_FILTER}}

    @pytest.mark.asyncio
    async def test_other_400_not_retried_on_old_metabase(self, mock_context):
        # 0.50 and earlier save a full query they can't read, so only the full-query refusal is retried.
        bad = HTTPError(400, "Bad", {"errors": {"name": "too long"}})
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), bad, _ok(OLD_METABASE)]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert [c.args[0] for c in mock_context.fetch.call_args_list].count(f"{BASE}/api/segment") == 1

    @pytest.mark.asyncio
    async def test_hidden_400_on_newer_metabase_sends_full_query(self, mock_context):
        # A gateway hides Metabase's reason, so on 0.51+ any 400 is taken as the full-query refusal.
        hidden = HTTPError(400, "Request failed. Check gateway and Metabase access.", {})
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_TABLE),
            hidden,
            _ok({"version": {"tag": "v0.65.2"}}),
            _ok({**SAMPLE_SEGMENT, "id": 11}),
        ]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.result.data["id"] == 11
        assert mock_context.fetch.call_args.kwargs["json"]["definition"]["type"] == "query"

    @pytest.mark.asyncio
    async def test_hidden_400_with_unknown_version_not_retried(self, mock_context):
        hidden = HTTPError(400, "Request failed. Check gateway and Metabase access.", {})
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), hidden, _ok({})]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_description_optional(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), _ok({**SAMPLE_SEGMENT, "id": 11})]
        await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert "description" not in mock_context.fetch.call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action(
            "create_segment", {"name": "  ", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_filter_rejected(self, mock_context):
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": []}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "filter clause" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_compound_filter_accepted(self, mock_context):
        compound = ["and", ACTIVE_FILTER, ["=", ["field", 13, None], "active"]]
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), _ok({**SAMPLE_SEGMENT, "id": 11})]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big active", "table_id": 31, "filter": compound}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["json"]["definition"]["filter"] == compound

    @pytest.mark.asyncio
    async def test_list_of_clauses_refused(self, mock_context):
        result = await metabase.execute_action(
            "create_segment",
            {"name": "Big orders", "table_id": 31, "filter": [ACTIVE_FILTER, ["=", ["field", 13, None], "active"]]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "one query-builder filter clause" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_mbql5_filter_from_list_segments_refused(self, mock_context):
        mbql5 = ["=", {"lib/uuid": "6f1c"}, ["field", {"lib/uuid": "9a2e"}, 121], "refunded"]
        result = await metabase.execute_action(
            "create_segment", {"name": "Refunded", "table_id": 31, "filter": mbql5}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "0.57+" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_list_filter_rejected(self, mock_context):
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": "total > 100"}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SAMPLE_TABLE),
            HTTPError(400, "Bad", {"errors": {"definition": "bad"}}),
            _ok(OLD_METABASE),
        ]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message

    @pytest.mark.asyncio
    async def test_table_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 999, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_says_check_first(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert "may still have saved" in result.result.message
        assert "list_segments" in result.result.message

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_TABLE), _ok({"name": "Big orders"})]
        result = await metabase.execute_action(
            "create_segment", {"name": "Big orders", "table_id": 31, "filter": ACTIVE_FILTER}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateSegment:
    @pytest.mark.asyncio
    async def test_rename(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_SEGMENT, "name": "Large orders"})
        result = await metabase.execute_action(
            "update_segment", {"segment_id": 7, "name": "Large orders"}, mock_context
        )
        assert result.result.data["name"] == "Large orders"
        call = mock_context.fetch.call_args
        assert mock_context.fetch.call_count == 1
        assert call.args[0] == f"{BASE}/api/segment/7"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"name": "Large orders", "revision_message": SEGMENT_REVISION_MESSAGE}

    @pytest.mark.asyncio
    async def test_filter_reads_segment_then_table(self, mock_context):
        new_filter = [">", ["field", 120, None], 500]
        mock_context.fetch.side_effect = [_ok(SAMPLE_SEGMENT), _ok(SAMPLE_TABLE), _ok(SAMPLE_SEGMENT)]
        await metabase.execute_action("update_segment", {"segment_id": 7, "filter": new_filter}, mock_context)
        seg_get, table_get, put = mock_context.fetch.call_args_list
        assert seg_get.args[0] == f"{BASE}/api/segment/7"
        assert seg_get.kwargs["method"] == "GET"
        assert table_get.args[0] == f"{BASE}/api/table/31"
        assert put.kwargs["json"] == {
            "definition": {"source-table": 31, "filter": new_filter},
            "revision_message": SEGMENT_REVISION_MESSAGE,
        }

    @pytest.mark.asyncio
    async def test_filter_full_query_when_metabase_needs_it(self, mock_context):
        new_filter = [">", ["field", 120, None], 500]
        needs_type = HTTPError(400, "Query must include :lib/type or :type")
        mock_context.fetch.side_effect = [_ok(SAMPLE_SEGMENT), _ok(SAMPLE_TABLE), needs_type, _ok(SAMPLE_SEGMENT)]
        result = await metabase.execute_action("update_segment", {"segment_id": 7, "filter": new_filter}, mock_context)
        assert result.type == ResultType.ACTION
        put = mock_context.fetch.call_args
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["json"]["definition"]["type"] == "query"

    @pytest.mark.asyncio
    async def test_description_and_name(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_SEGMENT)
        await metabase.execute_action(
            "update_segment", {"segment_id": 7, "name": "Big", "description": "Over $100"}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "name": "Big",
            "description": "Over $100",
            "revision_message": SEGMENT_REVISION_MESSAGE,
        }

    @pytest.mark.asyncio
    async def test_nothing_given(self, mock_context):
        result = await metabase.execute_action("update_segment", {"segment_id": 7}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_name_counts_as_nothing(self, mock_context):
        result = await metabase.execute_action("update_segment", {"segment_id": 7, "name": ""}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_list_filter_rejected(self, mock_context):
        result = await metabase.execute_action(
            "update_segment", {"segment_id": 7, "filter": {"total": 100}}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_filter_rejected_before_put(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_SEGMENT)
        result = await metabase.execute_action("update_segment", {"segment_id": 7, "filter": []}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert all(c.kwargs["method"] == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_mbql5_filter_refused_before_table_read(self, mock_context):
        mock_context.fetch.return_value = _ok(MBQL5_SEGMENT)
        result = await metabase.execute_action(
            "update_segment",
            {"segment_id": 9, "filter": MBQL5_SEGMENT["definition"]["stages"][0]["filters"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert _urls(mock_context) == [("GET", f"{BASE}/api/segment/9")]

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("update_segment", {"segment_id": 999, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


# ---- Organising content ----


class TestUpdateCollection:
    @pytest.mark.asyncio
    async def test_rename(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_COLLECTION, "name": "Finance team"})
        result = await metabase.execute_action(
            "update_collection", {"collection_id": 31, "name": "Finance team"}, mock_context
        )
        assert result.result.data == {
            "id": 31,
            "name": "Finance team",
            "description": "Money things",
            "parent_id": 28,
            "location": "/28/",
        }
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/collection/31"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"name": "Finance team"}

    @pytest.mark.asyncio
    async def test_move_into_parent(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_COLLECTION, "location": "/28/44/"})
        result = await metabase.execute_action(
            "update_collection", {"collection_id": 31, "parent_collection_id": 44}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {"parent_id": 44}
        assert result.result.data["parent_id"] == 44

    @pytest.mark.asyncio
    async def test_move_to_root_sends_null(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_COLLECTION, "location": "/"})
        result = await metabase.execute_action(
            "update_collection", {"collection_id": 31, "move_to_root": True}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {"parent_id": None}
        assert result.result.data["parent_id"] is None

    @pytest.mark.asyncio
    async def test_move_to_root_and_parent_refused(self, mock_context):
        result = await metabase.execute_action(
            "update_collection", {"collection_id": 31, "parent_collection_id": 44, "move_to_root": True}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("extra", [{}, {"move_to_root": False}])
    async def test_nothing_given(self, mock_context, extra):
        result = await metabase.execute_action("update_collection", {"collection_id": 31, **extra}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("update_collection", {"collection_id": 31, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "permissions" in result.result.message


class TestMoveItems:
    @pytest.mark.asyncio
    async def test_moves_each_item(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok({"id": 42, "dashboard_id": None}),
            _ok({"id": 42}),
            _ok({"id": 43}),
            _ok({"id": 43}),
            _ok(NEW_METABASE),
            _ok({"id": 44}),
            _ok({"id": 44}),
            _ok({"id": 9}),
            _ok({"id": 31}),
        ]
        items = [
            {"item_type": "question", "id": 42},
            {"item_type": "model", "id": 43},
            {"item_type": "metric", "id": 44},
            {"item_type": "dashboard", "id": 9},
            {"item_type": "collection", "id": 31},
        ]
        result = await metabase.execute_action("move_items", {"items": items, "collection_id": 12}, mock_context)
        data = result.result.data
        assert data["moved_count"] == 5
        assert data["failed_count"] == 0
        assert data["items"][0] == {"item_type": "question", "id": 42, "moved": True}
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/card/42"),
            ("PUT", f"{BASE}/api/card/42"),
            ("GET", f"{BASE}/api/card/43"),
            ("PUT", f"{BASE}/api/card/43"),
            ("GET", f"{BASE}/api/session/properties"),
            ("GET", f"{BASE}/api/card/44"),
            ("PUT", f"{BASE}/api/card/44"),
            ("PUT", f"{BASE}/api/dashboard/9"),
            ("PUT", f"{BASE}/api/collection/31"),
        ]
        puts = [c for c in mock_context.fetch.call_args_list if c.kwargs["method"] == "PUT"]
        assert [c.kwargs["json"] for c in puts] == [
            {"collection_id": 12},
            {"collection_id": 12},
            {"collection_id": 12},
            {"collection_id": 12},
            {"parent_id": 12},
        ]
        assert all(c.kwargs["retry_count"] == NO_RETRY for c in puts)

    @pytest.mark.asyncio
    async def test_question_saved_in_dashboard_leaves_it(self, mock_context):
        mock_context.fetch.side_effect = [_ok({"id": 42, "dashboard_id": 9}), _ok({"id": 42})]
        result = await metabase.execute_action(
            "move_items", {"items": [{"item_type": "question", "id": 42}], "collection_id": 12}, mock_context
        )
        assert result.result.data["moved_count"] == 1
        assert mock_context.fetch.call_args.kwargs["json"] == {"collection_id": 12, "dashboard_id": None}

    @pytest.mark.asyncio
    async def test_dashboard_question_moved_to_root(self, mock_context):
        mock_context.fetch.side_effect = [_ok({"id": 42, "dashboard_id": 9}), _ok({"id": 42})]
        await metabase.execute_action(
            "move_items", {"items": [{"item_type": "question", "id": 42}], "move_to_root": True}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {"collection_id": None, "dashboard_id": None}

    @pytest.mark.asyncio
    async def test_dashboards_and_collections_not_read_first(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 1})
        items = [{"item_type": "dashboard", "id": 9}, {"item_type": "collection", "id": 31}]
        await metabase.execute_action("move_items", {"items": items, "collection_id": 12}, mock_context)
        assert [method for method, _ in _urls(mock_context)] == ["PUT", "PUT"]

    @pytest.mark.asyncio
    async def test_legacy_metric_refused_others_move(self, mock_context):
        mock_context.fetch.side_effect = [_ok(OLD_METABASE), _ok({"id": 9})]
        items = [{"item_type": "metric", "id": 3}, {"item_type": "dashboard", "id": 9}]
        result = await metabase.execute_action("move_items", {"items": items, "collection_id": 12}, mock_context)
        data = result.result.data
        assert data["moved_count"] == 1
        assert data["failed_count"] == 1
        assert data["items"][0]["moved"] is False
        assert "belong to a table" in data["items"][0]["error"]
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/session/properties"),
            ("PUT", f"{BASE}/api/dashboard/9"),
        ]

    @pytest.mark.asyncio
    async def test_card_read_failure_reported_per_item(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok({"id": 9})]
        items = [{"item_type": "question", "id": 999}, {"item_type": "dashboard", "id": 9}]
        result = await metabase.execute_action("move_items", {"items": items, "collection_id": 12}, mock_context)
        data = result.result.data
        assert data["items"][0]["moved"] is False
        assert "HTTP 404" in data["items"][0]["error"]
        assert data["items"][1]["moved"] is True
        assert [method for method, _ in _urls(mock_context)] == ["GET", "PUT"]

    @pytest.mark.asyncio
    async def test_one_failure_others_still_move(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok({"id": 42}),
            _ok({"id": 42}),
            _ok({"id": 50}),
            HTTPError(403, "Forbidden", {"message": "You don't have permissions."}),
            _ok({"id": 9}),
        ]
        items = [
            {"item_type": "question", "id": 42},
            {"item_type": "question", "id": 50},
            {"item_type": "dashboard", "id": 9},
        ]
        result = await metabase.execute_action("move_items", {"items": items, "collection_id": 12}, mock_context)
        data = result.result.data
        assert result.type == ResultType.ACTION
        assert data["moved_count"] == 2
        assert data["failed_count"] == 1
        assert data["items"][1]["moved"] is False
        assert "HTTP 403" in data["items"][1]["error"]
        assert data["items"][2]["moved"] is True
        assert mock_context.fetch.call_count == 5

    @pytest.mark.asyncio
    async def test_move_to_root_sends_null(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 1})
        items = [{"item_type": "dashboard", "id": 9}, {"item_type": "collection", "id": 31}]
        await metabase.execute_action("move_items", {"items": items, "move_to_root": True}, mock_context)
        assert [c.kwargs["json"] for c in mock_context.fetch.call_args_list] == [
            {"collection_id": None},
            {"parent_id": None},
        ]

    @pytest.mark.asyncio
    async def test_collection_id_and_move_to_root_refused(self, mock_context):
        result = await metabase.execute_action(
            "move_items",
            {"items": [{"item_type": "question", "id": 42}], "collection_id": 12, "move_to_root": True},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("extra", [{}, {"move_to_root": False}])
    async def test_no_target(self, mock_context, extra):
        result = await metabase.execute_action(
            "move_items", {"items": [{"item_type": "question", "id": 42}], **extra}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "move_to_root" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_item_type_rejected_by_schema(self, mock_context):
        result = await metabase.execute_action(
            "move_items", {"items": [{"item_type": "segment", "id": 7}], "collection_id": 12}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_items(self, mock_context):
        result = await metabase.execute_action("move_items", {"items": [], "collection_id": 12}, mock_context)
        assert result.result.data == {"items": [], "moved_count": 0, "failed_count": 0}
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_per_item(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "move_items", {"items": [{"item_type": "question", "id": 42}], "collection_id": 12}, mock_context
        )
        assert result.result.data["failed_count"] == 1
        assert "did not respond in time" in result.result.data["items"][0]["error"]


class TestArchiveItem:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "item_type,path",
        [
            ("question", "card"),
            ("model", "card"),
            ("metric", "card"),
            ("dashboard", "dashboard"),
            ("collection", "collection"),
            ("timeline", "timeline"),
            ("timeline_event", "timeline-event"),
        ],
    )
    async def test_path_per_item_type(self, mock_context, item_type, path):
        mock_context.fetch.return_value = _ok({"id": 42, "archived": True})
        result = await metabase.execute_action("archive_item", {"item_type": item_type, "item_id": 42}, mock_context)
        assert result.result.data == {"item_type": item_type, "item_id": 42, "archived": True}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/{path}/42"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"archived": True}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("skip", [True, False])
    async def test_subscription_keeps_skip_if_empty(self, mock_context, skip):
        # Metabase resets skip_if_empty when an update leaves it out; archiving runs no SQL check.
        pulse = {**SAMPLE_PULSE, "skip_if_empty": skip}
        mock_context.fetch.side_effect = [_ok(pulse), _ok({**pulse, "archived": True})]
        result = await metabase.execute_action(
            "archive_item", {"item_type": "subscription", "item_id": 15}, mock_context
        )
        assert result.result.data == {"item_type": "subscription", "item_id": 15, "archived": True}
        assert _urls(mock_context) == [("GET", f"{BASE}/api/pulse/15"), ("PUT", f"{BASE}/api/pulse/15")]
        put = mock_context.fetch.call_args
        assert put.kwargs["retry_count"] == NO_RETRY
        assert put.kwargs["json"] == {"archived": True, "skip_if_empty": skip}

    @pytest.mark.asyncio
    async def test_segment_adds_revision_message(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 7, "archived": True})
        await metabase.execute_action("archive_item", {"item_type": "segment", "item_id": 7}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/segment/7"
        assert call.kwargs["json"] == {"archived": True, "revision_message": SEGMENT_REVISION_MESSAGE}

    @pytest.mark.asyncio
    async def test_metric_on_old_metabase_uses_metric_path(self, mock_context):
        mock_context.fetch.side_effect = [_ok(OLD_METABASE), _ok({"id": 3, "archived": True})]
        result = await metabase.execute_action("archive_item", {"item_type": "metric", "item_id": 3}, mock_context)
        assert result.type == ResultType.ACTION
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/session/properties"),
            ("PUT", f"{BASE}/api/metric/3"),
        ]
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "archived": True,
            "revision_message": SEGMENT_REVISION_MESSAGE,
        }

    @pytest.mark.asyncio
    async def test_metric_on_new_metabase_uses_card(self, mock_context):
        mock_context.fetch.side_effect = [_ok(NEW_METABASE), _ok({"id": 44, "archived": True})]
        await metabase.execute_action("archive_item", {"item_type": "metric", "item_id": 44}, mock_context)
        assert _urls(mock_context)[-1] == ("PUT", f"{BASE}/api/card/44")
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": True}

    @pytest.mark.asyncio
    async def test_question_does_not_read_version(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 42, "archived": True})
        await metabase.execute_action("archive_item", {"item_type": "question", "item_id": 42}, mock_context)
        assert _urls(mock_context) == [("PUT", f"{BASE}/api/card/42")]

    @pytest.mark.asyncio
    async def test_dashboard_subscription_notification_refused(self, mock_context):
        not_card = {**NEW_ALERT, "payload_type": "notification/dashboard"}
        mock_context.fetch.return_value = _ok(not_card)
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't a question alert" in result.result.message
        assert _urls(mock_context) == [("GET", f"{BASE}/api/notification/40")]

    @pytest.mark.asyncio
    async def test_missing_alert_on_both_apis(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _not_found()]
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 77}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "There's no alert 77." in result.result.message
        assert _urls(mock_context) == [("GET", f"{BASE}/api/notification/77"), ("PUT", f"{BASE}/api/alert/77")]

    @pytest.mark.asyncio
    async def test_legacy_alert_other_error_surfaces(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), HTTPError(403, "Forbidden", {"message": "No access."})]
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 12}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message

    @pytest.mark.asyncio
    async def test_alert_new_metabase_turns_notification_off(self, mock_context):
        mock_context.fetch.side_effect = [_ok(NEW_ALERT), _ok({**NEW_ALERT, "active": False})]
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert result.result.data == {"item_type": "alert", "item_id": 40, "archived": True}
        get, put = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/notification/40"
        assert get.kwargs["method"] == "GET"
        assert put.args[0] == f"{BASE}/api/notification/40"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["retry_count"] == NO_RETRY
        # The id is sent: without it Metabase 0.54-0.63 deletes the alert instead of updating it.
        assert put.kwargs["json"] == {
            "id": 40,
            "payload_type": NEW_ALERT["payload_type"],
            "payload": NEW_ALERT["payload"],
            "handlers": NEW_ALERT["handlers"],
            "subscriptions": NEW_ALERT["subscriptions"],
            "active": False,
        }

    @pytest.mark.asyncio
    async def test_alert_legacy_metabase(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok({**LEGACY_ALERT, "archived": True})]
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 12}, mock_context)
        assert result.type == ResultType.ACTION
        put = mock_context.fetch.call_args_list[1]
        assert put.args[0] == f"{BASE}/api/alert/12"
        assert put.kwargs["method"] == "PUT"
        assert put.kwargs["json"] == {"archived": True}

    @pytest.mark.asyncio
    async def test_alert_other_error_not_retried_on_legacy(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("archive_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected_by_schema(self, mock_context):
        result = await metabase.execute_action("archive_item", {"item_type": "pulse", "item_id": 1}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected_by_handler(self, mock_context):
        result = await ArchiveItemAction().execute({"item_type": "pulse", "item_id": 1}, mock_context)
        assert "item_type must be one of" in result.message
        assert "alert" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("archive_item", {"item_type": "dashboard", "item_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestArchiveMetricOn050:
    @pytest.mark.asyncio
    async def test_metric_question_archived_as_a_card(self, mock_context):
        # 0.50 saves metrics as questions, so the id create_metric returned is a question id.
        mock_context.fetch.side_effect = [_ok({"version": {"tag": "v0.50.36"}}), _ok({"id": 27, "archived": True})]
        await metabase.execute_action("archive_item", {"item_type": "metric", "item_id": 27}, mock_context)
        assert _urls(mock_context)[-1] == ("PUT", f"{BASE}/api/card/27")
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": True}


class TestRestoreItem:
    @pytest.mark.asyncio
    async def test_question(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 42, "archived": False})
        result = await metabase.execute_action("restore_item", {"item_type": "question", "item_id": 42}, mock_context)
        assert result.result.data == {"item_type": "question", "item_id": 42, "archived": False}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/card/42"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"archived": False}

    @pytest.mark.asyncio
    async def test_subscription_checks_every_question_then_restores(self, mock_context):
        archived = {**SAMPLE_PULSE, "archived": True}
        mock_context.fetch.side_effect = [
            _ok(archived),
            _ok(SUB_DASHBOARD),
            *_checks(),
            *_checks(CHURN_CARD),
            _ok(SAMPLE_PULSE),
        ]
        result = await metabase.execute_action(
            "restore_item", {"item_type": "subscription", "item_id": 15}, mock_context
        )
        assert result.result.data == {"item_type": "subscription", "item_id": 15, "archived": False}
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/pulse/15"),
            ("GET", f"{BASE}/api/dashboard/9"),
            *_check_calls(42),
            *_check_calls(43),
            ("PUT", f"{BASE}/api/pulse/15"),
        ]
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": False, "skip_if_empty": True}

    @pytest.mark.asyncio
    async def test_subscription_with_write_sql_stays_off(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok({**SAMPLE_PULSE, "archived": True}),
            _ok(SUB_DASHBOARD),
            *_checks(),
            *_checks(CHURN_CARD, sql="select nextval('audit_seq')"),
        ]
        result = await metabase.execute_action(
            "restore_item", {"item_type": "subscription", "item_id": 15}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 43" in result.result.message
        assert ("PUT", f"{BASE}/api/pulse/15") not in _urls(mock_context)

    @pytest.mark.asyncio
    async def test_timeline_event_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 90})
        await metabase.execute_action("restore_item", {"item_type": "timeline_event", "item_id": 90}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/timeline-event/90"

    @pytest.mark.asyncio
    async def test_segment_adds_revision_message(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 7})
        await metabase.execute_action("restore_item", {"item_type": "segment", "item_id": 7}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "archived": False,
            "revision_message": SEGMENT_REVISION_MESSAGE,
        }

    @pytest.mark.asyncio
    async def test_metric_on_old_metabase_uses_metric_path(self, mock_context):
        mock_context.fetch.side_effect = [_ok(OLD_METABASE), _ok({"id": 3, "archived": False})]
        await metabase.execute_action("restore_item", {"item_type": "metric", "item_id": 3}, mock_context)
        assert _urls(mock_context)[-1] == ("PUT", f"{BASE}/api/metric/3")
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "archived": False,
            "revision_message": SEGMENT_REVISION_MESSAGE,
        }

    @pytest.mark.asyncio
    async def test_metric_on_new_metabase_uses_card(self, mock_context):
        mock_context.fetch.side_effect = [_ok(NEW_METABASE), _ok({"id": 44})]
        await metabase.execute_action("restore_item", {"item_type": "metric", "item_id": 44}, mock_context)
        assert _urls(mock_context)[-1] == ("PUT", f"{BASE}/api/card/44")
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": False}

    @pytest.mark.asyncio
    async def test_non_question_notification_refused(self, mock_context):
        mock_context.fetch.return_value = _ok({**NEW_ALERT, "payload_type": "notification/system-event"})
        result = await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't a question alert" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_missing_alert_on_both_apis(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _not_found()]
        result = await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 77}, mock_context)
        assert "There's no alert 77." in result.result.message

    @pytest.mark.asyncio
    async def test_alert_new_metabase_turns_notification_on(self, mock_context):
        inactive = {**NEW_ALERT, "active": False}
        mock_context.fetch.side_effect = [_ok(inactive), *_checks(), _ok(NEW_ALERT)]
        await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/notification/40"),
            *_check_calls(42),
            ("PUT", f"{BASE}/api/notification/40"),
        ]
        put = mock_context.fetch.call_args
        assert put.kwargs["json"]["active"] is True
        assert put.kwargs["json"]["id"] == 40
        assert "created_at" not in put.kwargs["json"]
        assert "creator_id" not in put.kwargs["json"]

    @pytest.mark.asyncio
    async def test_alert_legacy_metabase(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok(LEGACY_ALERT), *_checks(), _ok(LEGACY_ALERT)]
        await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 12}, mock_context)
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/notification/12"),
            ("GET", f"{BASE}/api/alert/12"),
            *_check_calls(42),
            ("PUT", f"{BASE}/api/alert/12"),
        ]
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": False}

    @pytest.mark.asyncio
    async def test_alert_with_write_sql_stays_off(self, mock_context):
        inactive = {**NEW_ALERT, "active": False}
        mock_context.fetch.side_effect = [_ok(inactive), *_checks(sql="select nextval('audit_seq')")]
        result = await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 40}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert ("PUT", f"{BASE}/api/notification/40") not in _urls(mock_context)

    @pytest.mark.asyncio
    async def test_legacy_alert_with_write_sql_stays_off(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok(LEGACY_ALERT), *_checks(sql="delete from t")]
        result = await metabase.execute_action("restore_item", {"item_type": "alert", "item_id": 12}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert ("PUT", f"{BASE}/api/alert/12") not in _urls(mock_context)

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected_by_schema(self, mock_context):
        result = await metabase.execute_action("restore_item", {"item_type": "table", "item_id": 1}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_item_type_rejected_by_handler(self, mock_context):
        result = await RestoreItemAction().execute({"item_type": "table", "item_id": 1}, mock_context)
        assert "item_type must be one of" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "Server error", "boom")
        result = await metabase.execute_action("restore_item", {"item_type": "dashboard", "item_id": 9}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


# ---- Alerts ----


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_new_metabase(self, mock_context):
        mock_context.fetch.return_value = _ok([NEW_ALERT])
        result = await metabase.execute_action("list_alerts", {}, mock_context)
        assert result.result.data == {
            "alerts": [
                {
                    "id": 40,
                    "question_id": 42,
                    "condition": "has_result",
                    "send_once": False,
                    "active": True,
                    "schedule": "0 0 9 * * ? *",
                    "recipients": ["ana@example.com", "ops@example.com", 6],
                }
            ],
            "count": 1,
        }

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_alerts", {"question_id": 42, "include_inactive": True}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == (
            f"{BASE}/api/notification?payload_type=notification%2Fcard&include_inactive=true&card_id=42"
        )
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_request_defaults(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_alerts", {}, mock_context)
        assert mock_context.fetch.call_args.args[0] == (
            f"{BASE}/api/notification?payload_type=notification%2Fcard&include_inactive=false"
        )

    @pytest.mark.asyncio
    async def test_legacy_fallback_on_404(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok([LEGACY_ALERT])]
        result = await metabase.execute_action("list_alerts", {}, mock_context)
        assert mock_context.fetch.call_count == 2
        legacy_get = mock_context.fetch.call_args_list[1]
        assert legacy_get.args[0] == f"{BASE}/api/alert?archived=false"
        assert result.result.data["alerts"] == [
            {
                "id": 12,
                "question_id": 42,
                "condition": "goal_above",
                "send_once": True,
                "active": True,
                "schedule": "daily 9",
                "recipients": ["ana@example.com", "ops@example.com"],
            }
        ]

    @pytest.mark.asyncio
    async def test_legacy_include_inactive_reads_active_and_archived(self, mock_context):
        archived = {**LEGACY_ALERT, "id": 14, "archived": True}
        mock_context.fetch.side_effect = [_not_found(), _ok([LEGACY_ALERT]), _ok([archived])]
        result = await metabase.execute_action("list_alerts", {"include_inactive": True}, mock_context)
        assert [c.args[0] for c in mock_context.fetch.call_args_list[1:]] == [
            f"{BASE}/api/alert?archived=false",
            f"{BASE}/api/alert?archived=true",
        ]
        alerts = result.result.data["alerts"]
        assert [(a["id"], a["active"]) for a in alerts] == [(12, True), (14, False)]
        assert result.result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_legacy_archived_read_error_surfaces(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), _ok([LEGACY_ALERT]), HTTPError(500, "Server error", "boom")]
        result = await metabase.execute_action("list_alerts", {"include_inactive": True}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message

    @pytest.mark.asyncio
    async def test_legacy_weekly_schedule_includes_day(self, mock_context):
        weekly = {
            **LEGACY_ALERT,
            "channels": [{**LEGACY_ALERT["channels"][0], "schedule_type": "weekly", "schedule_day": "fri"}],
        }
        mock_context.fetch.side_effect = [_not_found(), _ok([weekly])]
        result = await metabase.execute_action("list_alerts", {}, mock_context)
        assert result.result.data["alerts"][0]["schedule"] == "weekly fri 9"

    @pytest.mark.asyncio
    async def test_legacy_filters_by_question(self, mock_context):
        other = {**LEGACY_ALERT, "id": 13, "card": {"id": 77}}
        mock_context.fetch.side_effect = [_not_found(), _ok([LEGACY_ALERT, other])]
        result = await metabase.execute_action("list_alerts", {"question_id": 77}, mock_context)
        assert [a["id"] for a in result.result.data["alerts"]] == [13]

    @pytest.mark.asyncio
    async def test_legacy_conditions(self, mock_context):
        rows = {**LEGACY_ALERT, "id": 1, "alert_condition": "rows", "alert_above_goal": None}
        below = {**LEGACY_ALERT, "id": 2, "alert_above_goal": False, "archived": True}
        hourly = {**LEGACY_ALERT, "id": 3, "channels": [{"schedule_type": "hourly", "schedule_hour": None}]}
        mock_context.fetch.side_effect = [_not_found(), _ok([rows, below, hourly])]
        alerts = (await metabase.execute_action("list_alerts", {}, mock_context)).result.data["alerts"]
        assert alerts[0]["condition"] == "has_result"
        assert alerts[1]["condition"] == "goal_below"
        assert alerts[1]["active"] is False
        assert alerts[2]["schedule"] == "hourly"
        assert alerts[2]["recipients"] == []

    @pytest.mark.asyncio
    async def test_new_inactive_alert(self, mock_context):
        mock_context.fetch.return_value = _ok([{**NEW_ALERT, "active": False, "subscriptions": []}])
        alert = (await metabase.execute_action("list_alerts", {}, mock_context)).result.data["alerts"][0]
        assert alert["active"] is False
        assert alert["schedule"] is None

    @pytest.mark.asyncio
    async def test_new_filters_by_question(self, mock_context):
        other = {**NEW_ALERT, "id": 41, "payload": {"card_id": 77, "send_condition": "goal_above"}}
        mock_context.fetch.return_value = _ok([NEW_ALERT, other])
        result = await metabase.execute_action("list_alerts", {"question_id": 77}, mock_context)
        assert [a["id"] for a in result.result.data["alerts"]] == [41]

    @pytest.mark.asyncio
    async def test_other_error_surfaces(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("list_alerts", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_legacy_error_surfaces(self, mock_context):
        mock_context.fetch.side_effect = [_not_found(), HTTPError(500, "Server error", "boom")]
        result = await metabase.execute_action("list_alerts", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


class TestCreateAlert:
    @pytest.mark.asyncio
    async def test_new_metabase_body(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _ok(NEW_ALERT)]
        result = await metabase.execute_action(
            "create_alert",
            {
                "question_id": 42,
                "hour": 9,
                "recipient_user_ids": [5],
                "recipient_emails": ["ops@example.com"],
            },
            mock_context,
        )
        assert result.result.data["id"] == 40
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/notification"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "payload_type": "notification/card",
            "payload": {"card_id": 42, "send_condition": "has_result", "send_once": False},
            "handlers": [
                {
                    "channel_type": "channel/email",
                    "recipients": [
                        {"type": "notification-recipient/user", "user_id": 5},
                        {"type": "notification-recipient/raw-value", "details": {"value": "ops@example.com"}},
                    ],
                }
            ],
            "subscriptions": [{"type": "notification-subscription/cron", "cron_schedule": "0 0 9 * * ? *"}],
        }

    @pytest.mark.asyncio
    async def test_checks_question_before_creating(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _ok(NEW_ALERT)]
        await metabase.execute_action("create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context)
        assert _urls(mock_context) == [*_check_calls(42), ("POST", f"{BASE}/api/notification")]
        compile_call = mock_context.fetch.call_args_list[2]
        assert compile_call.kwargs["json"] == {**SAMPLE_CARD["dataset_query"], "parameters": [], "pretty": False}

    @pytest.mark.asyncio
    async def test_card_defaults_checked_with_and_without(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(REGION_CARD), _ok({"query": SIGNUPS_SQL}), _ok(NEW_ALERT)]
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        compiles = [c for c in mock_context.fetch.call_args_list if c.args[0] == f"{BASE}/api/dataset/native"]
        assert [c.kwargs["json"]["parameters"] for c in compiles] == [
            [{"id": "p1", "type": "category", "target": ["variable", ["template-tag", "region"]], "value": "NZ"}],
            [],
        ]

    @pytest.mark.asyncio
    async def test_write_sql_refused(self, mock_context):
        mock_context.fetch.side_effect = _checks(sql="delete from t")
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 42" in result.result.message
        assert _urls(mock_context) == _check_calls(42)

    @pytest.mark.asyncio
    async def test_write_sql_refused_on_old_metabase_too(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(sql="delete from t"), _not_found(), _ok(LEGACY_ALERT)]
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        posts = [url for method, url in _urls(mock_context) if method == "POST"]
        assert posts == [f"{BASE}/api/dataset/native"]

    @pytest.mark.asyncio
    async def test_question_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action(
            "create_alert", {"question_id": 999, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "schedule,cron",
        [
            ({"frequency": "hourly", "hour": 9}, "0 0 * * * ? *"),
            ({"frequency": "daily", "hour": 9}, "0 0 9 * * ? *"),
            ({"frequency": "weekly", "hour": 7, "day_of_week": "fri"}, "0 0 7 ? * FRI *"),
            ({}, "0 0 8 * * ? *"),
            ({"frequency": "weekly"}, "0 0 8 ? * MON *"),
        ],
    )
    async def test_cron_schedules(self, mock_context, schedule, cron):
        mock_context.fetch.side_effect = [*_checks(), _ok(NEW_ALERT)]
        await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5], **schedule}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"]["subscriptions"][0]["cron_schedule"] == cron

    @pytest.mark.asyncio
    async def test_goal_condition_and_send_once(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _ok(NEW_ALERT)]
        await metabase.execute_action(
            "create_alert",
            {"question_id": 42, "condition": "goal_below", "send_once": True, "recipient_user_ids": [5]},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["json"]["payload"] == {
            "card_id": 42,
            "send_condition": "goal_below",
            "send_once": True,
        }

    @pytest.mark.asyncio
    async def test_legacy_fallback_on_404(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _not_found(), _ok(LEGACY_ALERT)]
        result = await metabase.execute_action(
            "create_alert",
            {
                "question_id": 42,
                "condition": "goal_above",
                "send_once": True,
                "frequency": "weekly",
                "hour": 7,
                "day_of_week": "fri",
                "recipient_user_ids": [5],
                "recipient_emails": ["ops@example.com"],
            },
            mock_context,
        )
        assert result.result.data["id"] == 12
        assert _urls(mock_context)[3:] == [("POST", f"{BASE}/api/notification"), ("POST", f"{BASE}/api/alert")]
        legacy = mock_context.fetch.call_args
        assert legacy.kwargs["retry_count"] == NO_RETRY
        assert legacy.kwargs["json"] == {
            "card": {"id": 42, "include_csv": False, "include_xls": False},
            "alert_condition": "goal",
            "alert_above_goal": True,
            "alert_first_only": True,
            "channels": [
                {
                    "enabled": True,
                    "channel_type": "email",
                    "schedule_type": "weekly",
                    "schedule_hour": 7,
                    "schedule_day": "fri",
                    "schedule_frame": None,
                    "recipients": [{"id": 5}, {"email": "ops@example.com"}],
                }
            ],
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "condition,alert_condition,above",
        [("has_result", "rows", None), ("goal_above", "goal", True), ("goal_below", "goal", False)],
    )
    async def test_legacy_conditions(self, mock_context, condition, alert_condition, above):
        mock_context.fetch.side_effect = [*_checks(), _not_found(), _ok(LEGACY_ALERT)]
        await metabase.execute_action(
            "create_alert", {"question_id": 42, "condition": condition, "recipient_user_ids": [5]}, mock_context
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["alert_condition"] == alert_condition
        assert body["alert_above_goal"] is above
        assert body["alert_first_only"] is False

    @pytest.mark.asyncio
    async def test_legacy_hourly_has_no_hour_or_day(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _not_found(), _ok(LEGACY_ALERT)]
        await metabase.execute_action(
            "create_alert",
            {"question_id": 42, "frequency": "hourly", "hour": 9, "recipient_user_ids": [5]},
            mock_context,
        )
        channel = mock_context.fetch.call_args.kwargs["json"]["channels"][0]
        assert channel["schedule_type"] == "hourly"
        assert channel["schedule_hour"] is None
        assert channel["schedule_day"] is None

    @pytest.mark.asyncio
    async def test_other_error_does_not_fall_back(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), HTTPError(400, "Bad", {"message": "Card has no goal line"})]
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "condition": "goal_above", "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "goal line" in result.result.message
        assert _urls(mock_context)[-1] == ("POST", f"{BASE}/api/notification")
        assert mock_context.fetch.call_count == 4

    @pytest.mark.asyncio
    async def test_recipients_required(self, mock_context):
        result = await metabase.execute_action("create_alert", {"question_id": 42}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "recipient" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_emails_do_not_count(self, mock_context):
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_emails": ["  ", ""]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_bad_day_of_week_rejected(self, mock_context):
        result = await metabase.execute_action(
            "create_alert",
            {"question_id": 42, "frequency": "weekly", "day_of_week": "someday", "recipient_user_ids": [5]},
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_bad_condition_rejected(self, mock_context):
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "condition": "changes", "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_says_check_first(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context
        )
        assert "may still have saved" in result.result.message
        assert "list_alerts" in result.result.message
        assert mock_context.fetch.call_count == 4

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [*_checks(), _ok({"payload_type": "notification/card"})]
        result = await metabase.execute_action(
            "create_alert", {"question_id": 42, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "alert id" in result.result.message


# ---- Subscriptions ----


class TestListSubscriptions:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok([SAMPLE_PULSE])
        result = await metabase.execute_action("list_subscriptions", {}, mock_context)
        assert result.result.data == {
            "subscriptions": [
                {
                    "id": 15,
                    "name": "Growth weekly",
                    "dashboard_id": 9,
                    "archived": False,
                    "skip_if_empty": True,
                    "frequency": "weekly",
                    "hour": 7,
                    "day_of_week": "fri",
                    "recipients": ["ana@example.com", "ops@example.com"],
                }
            ],
            "count": 1,
        }

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_subscriptions", {"dashboard_id": 9, "archived": True}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/pulse?dashboard_id=9&archived=true"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_request_defaults(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_subscriptions", {"archived": False}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/pulse"

    @pytest.mark.asyncio
    async def test_slack_only_subscription(self, mock_context):
        mock_context.fetch.return_value = _ok([{**SAMPLE_PULSE, "channels": [SLACK_CHANNEL]}])
        sub = (await metabase.execute_action("list_subscriptions", {}, mock_context)).result.data["subscriptions"][0]
        assert sub["frequency"] is None
        assert sub["recipients"] == []

    @pytest.mark.asyncio
    async def test_recipient_falls_back_to_id(self, mock_context):
        channel = {**EMAIL_CHANNEL, "recipients": [{"id": 8}, {"id": 9, "common_name": "Dee Roy"}]}
        mock_context.fetch.return_value = _ok([{**SAMPLE_PULSE, "channels": [channel]}])
        sub = (await metabase.execute_action("list_subscriptions", {}, mock_context)).result.data["subscriptions"][0]
        assert sub["recipients"] == [8, "Dee Roy"]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("list_subscriptions", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateSubscription:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription",
            {
                "dashboard_id": 9,
                "frequency": "weekly",
                "hour": 7,
                "day_of_week": "fri",
                "recipient_user_ids": [5],
                "recipient_emails": ["ops@example.com"],
                "skip_if_empty": True,
            },
            mock_context,
        )
        assert result.result.data["id"] == 15
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/dashboard/9"),
            *_check_calls(42),
            *_check_calls(43),
            ("POST", f"{BASE}/api/pulse"),
        ]
        post = mock_context.fetch.call_args
        assert post.kwargs["retry_count"] == NO_RETRY
        assert post.kwargs["json"] == {
            "name": "Growth",
            "dashboard_id": 9,
            "cards": [
                {"id": 42, "dashboard_card_id": 501, "include_csv": False, "include_xls": False},
                {"id": 43, "dashboard_card_id": 503, "include_csv": False, "include_xls": False},
            ],
            "channels": [
                {
                    "enabled": True,
                    "channel_type": "email",
                    "schedule_type": "weekly",
                    "schedule_hour": 7,
                    "schedule_day": "fri",
                    "schedule_frame": None,
                    "recipients": [{"id": 5}, {"email": "ops@example.com"}],
                }
            ],
            "skip_if_empty": True,
        }

    @pytest.mark.asyncio
    async def test_defaults(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "create_subscription",
            {"dashboard_id": 9, "name": "Morning growth", "recipient_user_ids": [5]},
            mock_context,
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "Morning growth"
        assert body["skip_if_empty"] is False
        channel = body["channels"][0]
        assert channel["schedule_type"] == "daily"
        assert channel["schedule_hour"] == 8
        assert channel["schedule_day"] is None

    @pytest.mark.asyncio
    async def test_repeated_card_checked_once(self, mock_context):
        twice = {
            **SUB_DASHBOARD,
            "dashcards": [
                {"id": 501, "card_id": 42, "card": {"id": 42}},
                {"id": 504, "card_id": 42, "card": {"id": 42}},
            ],
        }
        mock_context.fetch.side_effect = [_ok(twice), *_checks(), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/dashboard/9"),
            *_check_calls(42),
            ("POST", f"{BASE}/api/pulse"),
        ]
        # Both dashboard cards are still sent.
        assert [c["dashboard_card_id"] for c in mock_context.fetch.call_args.kwargs["json"]["cards"]] == [501, 504]

    @pytest.mark.asyncio
    async def test_write_sql_refused(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD, sql="delete from t")]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 43" in result.result.message
        assert ("POST", f"{BASE}/api/pulse") not in _urls(mock_context)
        assert mock_context.fetch.call_count == 7

    @pytest.mark.asyncio
    async def test_card_defaults_checked_with_and_without(self, mock_context):
        one_card = {**SUB_DASHBOARD, "dashcards": [SUB_DASHBOARD["dashcards"][0]]}
        mock_context.fetch.side_effect = [
            _ok(one_card),
            *_checks(REGION_CARD),
            _ok({"query": SIGNUPS_SQL}),
            _ok(SAMPLE_PULSE),
        ]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        compiles = [c for c in mock_context.fetch.call_args_list if c.args[0] == f"{BASE}/api/dataset/native"]
        assert len(compiles) == 2
        assert compiles[1].kwargs["json"]["parameters"] == []

    @pytest.mark.asyncio
    async def test_series_question_write_refused(self, mock_context):
        combined = {
            **SUB_DASHBOARD,
            "dashcards": [{"id": 501, "card_id": 42, "card": {"id": 42}, "series": [{"id": 44, "name": "Upgrades"}]}],
        }
        mock_context.fetch.side_effect = [
            _ok(combined),
            *_checks(),
            *_checks(UPGRADES_CARD, sql="delete from t"),
        ]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 44" in result.result.message
        assert _urls(mock_context) == [("GET", f"{BASE}/api/dashboard/9"), *_check_calls(42), *_check_calls(44)]

    @pytest.mark.asyncio
    async def test_series_question_checked_but_not_sent_as_card(self, mock_context):
        combined = {
            **SUB_DASHBOARD,
            "dashcards": [{"id": 501, "card_id": 42, "card": {"id": 42}, "series": [{"id": 44, "name": "Upgrades"}]}],
        }
        mock_context.fetch.side_effect = [_ok(combined), *_checks(), *_checks(UPGRADES_CARD), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["json"]["cards"] == [
            {"id": 42, "dashboard_card_id": 501, "include_csv": False, "include_xls": False}
        ]

    @pytest.mark.asyncio
    async def test_dashboard_default_sent_with_check(self, mock_context):
        # The default can switch on an optional [[ ]] clause, so the SQL checked must be compiled with it.
        filtered = {
            **SUB_DASHBOARD,
            "parameters": [PLAN_FILTER],
            "dashcards": [
                {
                    "id": 501,
                    "card_id": 42,
                    "card": {"id": 42},
                    "parameter_mappings": [{"parameter_id": "f1", "target": PLAN_TAG_TARGET}],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(filtered), *_checks(), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert _compiled_parameters(mock_context) == [
            [{"id": "f1", "type": "string/=", "target": PLAN_TAG_TARGET, "value": "pro"}]
        ]

    @pytest.mark.asyncio
    async def test_default_that_turns_sql_into_write_refused(self, mock_context):
        filtered = {
            **SUB_DASHBOARD,
            "parameters": [PLAN_FILTER],
            "dashcards": [
                {
                    "id": 501,
                    "card_id": 42,
                    "card": {"id": 42},
                    "parameter_mappings": [{"parameter_id": "f1", "card_id": 42, "target": PLAN_TAG_TARGET}],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(filtered), *_checks(sql="select 1; delete from t")]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert ("POST", f"{BASE}/api/pulse") not in _urls(mock_context)
        assert _compiled_parameters(mock_context)[0][0]["value"] == "pro"

    @pytest.mark.asyncio
    async def test_filter_without_default_sends_nothing(self, mock_context):
        no_default = {**PLAN_FILTER, "default": None}
        filtered = {
            **SUB_DASHBOARD,
            "parameters": [no_default],
            "dashcards": [
                {
                    "id": 501,
                    "card_id": 42,
                    "card": {"id": 42},
                    "parameter_mappings": [{"parameter_id": "f1", "card_id": 42, "target": PLAN_TAG_TARGET}],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(filtered), *_checks(), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert _compiled_parameters(mock_context) == [[]]

    @pytest.mark.asyncio
    async def test_series_question_uses_its_own_mappings(self, mock_context):
        combined = {
            **SUB_DASHBOARD,
            "parameters": [PLAN_FILTER],
            "dashcards": [
                {
                    "id": 501,
                    "card_id": 42,
                    "card": {"id": 42},
                    "series": [{"id": 44, "name": "Upgrades"}],
                    "parameter_mappings": [
                        {"parameter_id": "f1", "card_id": 42, "target": PLAN_TAG_TARGET},
                        {"parameter_id": "f1", "card_id": 44, "target": PLAN_FIELD_TARGET},
                    ],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(combined), *_checks(), *_checks(UPGRADES_CARD), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert _compiled_parameters(mock_context) == [
            [{"id": "f1", "type": "string/=", "target": PLAN_TAG_TARGET, "value": "pro"}],
            [{"id": "f1", "type": "string/=", "target": PLAN_FIELD_TARGET, "value": "pro"}],
        ]

    @pytest.mark.asyncio
    async def test_series_without_mapping_gets_no_values(self, mock_context):
        # A mapping without card_id belongs to the card's own question, not to the extra series.
        combined = {
            **SUB_DASHBOARD,
            "parameters": [PLAN_FILTER],
            "dashcards": [
                {
                    "id": 501,
                    "card_id": 42,
                    "card": {"id": 42},
                    "series": [{"id": 44, "name": "Upgrades"}],
                    "parameter_mappings": [{"parameter_id": "f1", "target": PLAN_TAG_TARGET}],
                }
            ],
        }
        mock_context.fetch.side_effect = [_ok(combined), *_checks(), *_checks(UPGRADES_CARD), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert _compiled_parameters(mock_context) == [
            [{"id": "f1", "type": "string/=", "target": PLAN_TAG_TARGET, "value": "pro"}],
            [],
        ]

    @pytest.mark.asyncio
    async def test_same_question_and_values_checked_once(self, mock_context):
        mapping = [{"parameter_id": "f1", "target": PLAN_TAG_TARGET}]
        twice = {
            **SUB_DASHBOARD,
            "parameters": [PLAN_FILTER],
            "dashcards": [
                {"id": 501, "card_id": 42, "card": {"id": 42}, "parameter_mappings": mapping},
                {"id": 504, "card_id": 42, "card": {"id": 42}, "parameter_mappings": mapping},
                {"id": 505, "card_id": 43, "card": {"id": 43}, "series": [{"id": 42}], "parameter_mappings": []},
            ],
        }
        mock_context.fetch.side_effect = [
            _ok(twice),
            *_checks(),
            *_checks(CHURN_CARD),
            *_checks(),
            _ok(SAMPLE_PULSE),
        ]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        # 42 with the default once, 43 once, then 42 again as a series with no values: a different check.
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/dashboard/9"),
            *_check_calls(42),
            *_check_calls(43),
            *_check_calls(42),
            ("POST", f"{BASE}/api/pulse"),
        ]
        assert _compiled_parameters(mock_context)[2] == []

    @pytest.mark.asyncio
    async def test_action_cards_not_checked(self, mock_context):
        with_action = {
            **SUB_DASHBOARD,
            "dashcards": [
                {"id": 506, "card_id": 42, "action_id": 7, "card": {"id": 42}},
                {"id": 503, "card_id": 43, "card": {"id": 43}},
            ],
        }
        mock_context.fetch.side_effect = [_ok(with_action), *_checks(CHURN_CARD), _ok(SAMPLE_PULSE)]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        assert _urls(mock_context) == [
            ("GET", f"{BASE}/api/dashboard/9"),
            *_check_calls(43),
            ("POST", f"{BASE}/api/pulse"),
        ]

    @pytest.mark.asyncio
    async def test_no_question_cards(self, mock_context):
        text_only = {**SUB_DASHBOARD, "dashcards": [SUB_DASHBOARD["dashcards"][1]]}
        mock_context.fetch.return_value = _ok(text_only)
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "no questions" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_recipients_required(self, mock_context):
        mock_context.fetch.return_value = _ok(SUB_DASHBOARD)
        result = await metabase.execute_action("create_subscription", {"dashboard_id": 9}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "recipient" in result.result.message
        assert all(c.kwargs["method"] == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_dashboard_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 999, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_timeout_says_check_first(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), asyncio.TimeoutError()]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert "may still have saved" in result.result.message
        assert "list_subscriptions" in result.result.message
        assert mock_context.fetch.call_count == 8

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok(SUB_DASHBOARD),
            *_checks(),
            *_checks(CHURN_CARD),
            _ok({"name": "Growth"}),
        ]
        result = await metabase.execute_action(
            "create_subscription", {"dashboard_id": 9, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "subscription id" in result.result.message


class TestUpdateSubscription:
    @pytest.mark.asyncio
    async def test_name_only_keeps_flags(self, mock_context):
        # Metabase resets archived and skip_if_empty when an update leaves them out.
        mock_context.fetch.side_effect = [_ok(SAMPLE_PULSE), _ok({**SAMPLE_PULSE, "name": "Growth (Fri)"})]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "name": "Growth (Fri)"}, mock_context
        )
        assert result.result.data["name"] == "Growth (Fri)"
        assert _urls(mock_context) == [("GET", f"{BASE}/api/pulse/15"), ("PUT", f"{BASE}/api/pulse/15")]
        call = mock_context.fetch.call_args
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"archived": False, "skip_if_empty": True, "name": "Growth (Fri)"}

    @pytest.mark.asyncio
    async def test_rename_archived_stays_archived(self, mock_context):
        archived = {**SAMPLE_PULSE, "archived": True, "skip_if_empty": False}
        mock_context.fetch.side_effect = [_ok(archived), _ok(archived)]
        await metabase.execute_action("update_subscription", {"subscription_id": 15, "name": "Old"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": True, "skip_if_empty": False, "name": "Old"}

    @pytest.mark.asyncio
    async def test_schedule_change_on_slack_only_subscription(self, mock_context):
        slack_only = {**SAMPLE_PULSE, "channels": [SLACK_CHANNEL]}
        mock_context.fetch.side_effect = [_ok(slack_only), _ok(slack_only)]
        result = await metabase.execute_action("update_subscription", {"subscription_id": 15, "hour": 9}, mock_context)
        assert result.type == ResultType.ACTION
        channels = mock_context.fetch.call_args.kwargs["json"]["channels"]
        assert channels == [{**SLACK_CHANNEL, "schedule_hour": 9, "schedule_day": None, "schedule_frame": None}]

    @pytest.mark.asyncio
    async def test_recipients_on_slack_only_subscription_add_email(self, mock_context):
        slack_only = {**SAMPLE_PULSE, "channels": [SLACK_CHANNEL]}
        mock_context.fetch.side_effect = [
            _ok(slack_only),
            _ok(SUB_DASHBOARD),
            *_checks(),
            *_checks(CHURN_CARD),
            _ok(slack_only),
        ]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION
        # The new email channel starts sending, so every question is checked first.
        assert _urls(mock_context)[1:8] == [("GET", f"{BASE}/api/dashboard/9"), *_check_calls(42), *_check_calls(43)]
        channels = mock_context.fetch.call_args.kwargs["json"]["channels"]
        assert channels[0] == SLACK_CHANNEL
        assert channels[1]["channel_type"] == "email"
        assert channels[1]["recipients"] == [{"id": 5}]
        assert channels[1]["schedule_hour"] == 8

    @pytest.mark.asyncio
    async def test_new_email_channel_with_writing_question_refused(self, mock_context):
        paused = {**SAMPLE_PULSE, "channels": [{**SLACK_CHANNEL, "enabled": False}]}
        mock_context.fetch.side_effect = [
            _ok(paused),
            _ok(SUB_DASHBOARD),
            *_checks(),
            *_checks(CHURN_CARD, sql="select nextval('audit_seq')"),
        ]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_user_ids": [5]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Saved question 43" in result.result.message
        assert ("PUT", f"{BASE}/api/pulse/15") not in _urls(mock_context)

    @pytest.mark.asyncio
    async def test_every_other_channel_kept_including_extra_email(self, mock_context):
        # Metabase deletes channels left out of the update, so a second email channel is sent back untouched.
        second = {**EMAIL_CHANNEL, "id": 72, "recipients": [{"email": "cfo@example.com"}]}
        pulse = {**SAMPLE_PULSE, "channels": [SLACK_CHANNEL, EMAIL_CHANNEL, second]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action("update_subscription", {"subscription_id": 15, "hour": 10}, mock_context)
        channels = mock_context.fetch.call_args.kwargs["json"]["channels"]
        assert channels == [SLACK_CHANNEL, second, {**EMAIL_CHANNEL, "schedule_hour": 10}]

    @pytest.mark.asyncio
    async def test_skip_if_empty_false_sent(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PULSE), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "skip_if_empty": False}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {"archived": False, "skip_if_empty": False}
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_no_change_refused_without_calls(self, mock_context):
        result = await metabase.execute_action("update_subscription", {"subscription_id": 15}, mock_context)
        assert "at least one change" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_hour_merges_with_existing_channel(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PULSE), _ok(SAMPLE_PULSE)]
        await metabase.execute_action("update_subscription", {"subscription_id": 15, "hour": 10}, mock_context)
        get, put = mock_context.fetch.call_args_list
        assert get.args[0] == f"{BASE}/api/pulse/15"
        assert get.kwargs["method"] == "GET"
        channels = put.kwargs["json"]["channels"]
        assert channels[0] == SLACK_CHANNEL
        # Recipients and the enabled flag are sent back as they were; only the hour changes.
        assert channels[1] == {**EMAIL_CHANNEL, "schedule_hour": 10}
        assert channels[1]["id"] == 70

    @pytest.mark.asyncio
    async def test_recipients_replace_only_given_kind(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PULSE), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_emails": ["cfo@example.com"]}, mock_context
        )
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][1]
        assert email["recipients"] == [{"id": 5}, {"email": "cfo@example.com"}]
        assert email["schedule_type"] == "weekly"
        assert email["schedule_day"] == "fri"

    @pytest.mark.asyncio
    async def test_weekly_to_daily_drops_day(self, mock_context):
        mock_context.fetch.side_effect = [_ok(SAMPLE_PULSE), _ok(SAMPLE_PULSE)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "frequency": "daily"}, mock_context
        )
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][1]
        assert email["schedule_type"] == "daily"
        assert email["schedule_hour"] == 7
        assert email["schedule_day"] is None

    @pytest.mark.asyncio
    async def test_hourly_to_daily_defaults_hour_8(self, mock_context):
        hourly = {**EMAIL_CHANNEL, "schedule_type": "hourly", "schedule_hour": None, "schedule_day": None}
        pulse = {**SAMPLE_PULSE, "channels": [hourly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "frequency": "daily"}, mock_context
        )
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][0]
        assert email["schedule_hour"] == 8

    @pytest.mark.asyncio
    async def test_removing_every_recipient_rejected(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_PULSE)
        result = await metabase.execute_action(
            "update_subscription",
            {"subscription_id": 15, "recipient_user_ids": [], "recipient_emails": []},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "recipient" in result.result.message
        assert all(c.kwargs["method"] == "GET" for c in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_bad_day_of_week_rejected(self, mock_context):
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "day_of_week": "funday"}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_nothing_given(self, mock_context):
        result = await metabase.execute_action("update_subscription", {"subscription_id": 15}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one change" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("update_subscription", {"subscription_id": 999, "hour": 9}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_slack_only_gets_new_email_channel(self, mock_context):
        pulse = {**SAMPLE_PULSE, "channels": [SLACK_CHANNEL]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), _ok(pulse)]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_emails": ["cfo@example.com"]}, mock_context
        )
        assert result.type == ResultType.ACTION
        channels = mock_context.fetch.call_args.kwargs["json"]["channels"]
        assert channels == [
            SLACK_CHANNEL,
            {
                "enabled": True,
                "channel_type": "email",
                "schedule_type": "daily",
                "schedule_hour": 8,
                "schedule_day": None,
                "schedule_frame": None,
                "recipients": [{"email": "cfo@example.com"}],
            },
        ]

    @pytest.mark.asyncio
    async def test_monthly_kept_when_only_name_and_recipients_change(self, mock_context):
        monthly = {**EMAIL_CHANNEL, "schedule_type": "monthly", "schedule_day": "mon", "schedule_frame": "first"}
        pulse = {**SAMPLE_PULSE, "channels": [monthly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action(
            "update_subscription",
            {"subscription_id": 15, "name": "Monthly growth", "recipient_user_ids": [5, 6]},
            mock_context,
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "Monthly growth"
        assert body["channels"] == [{**monthly, "recipients": [{"id": 5}, {"id": 6}, {"email": "ops@example.com"}]}]

    @pytest.mark.asyncio
    async def test_monthly_hour_change_keeps_monthly(self, mock_context):
        monthly = {**EMAIL_CHANNEL, "schedule_type": "monthly", "schedule_day": "mon", "schedule_frame": "first"}
        pulse = {**SAMPLE_PULSE, "channels": [monthly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action("update_subscription", {"subscription_id": 15, "hour": 10}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"]["channels"] == [{**monthly, "schedule_hour": 10}]

    @pytest.mark.asyncio
    async def test_monthly_day_change_keeps_monthly(self, mock_context):
        monthly = {**EMAIL_CHANNEL, "schedule_type": "monthly", "schedule_day": "mon", "schedule_frame": "first"}
        pulse = {**SAMPLE_PULSE, "channels": [monthly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "day_of_week": "wed"}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"]["channels"] == [{**monthly, "schedule_day": "wed"}]

    @pytest.mark.asyncio
    async def test_monthly_converted_when_frequency_given(self, mock_context):
        monthly = {**EMAIL_CHANNEL, "schedule_type": "monthly", "schedule_day": "mon", "schedule_frame": "first"}
        pulse = {**SAMPLE_PULSE, "channels": [monthly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "frequency": "weekly", "day_of_week": "thu"}, mock_context
        )
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][0]
        assert email["schedule_type"] == "weekly"
        assert email["schedule_day"] == "thu"
        assert email["schedule_hour"] == 7
        assert email["schedule_frame"] is None

    @pytest.mark.asyncio
    async def test_new_email_channel_copies_other_schedule(self, mock_context):
        slack = {**SLACK_CHANNEL, "schedule_type": "weekly", "schedule_hour": 7, "schedule_day": "fri"}
        pulse = {**SAMPLE_PULSE, "channels": [slack]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), _ok(pulse)]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_emails": ["cfo@example.com"]}, mock_context
        )
        assert result.type == ResultType.ACTION
        channels = mock_context.fetch.call_args.kwargs["json"]["channels"]
        assert channels[0] == slack
        assert channels[1] == {
            "enabled": True,
            "channel_type": "email",
            "schedule_type": "weekly",
            "schedule_hour": 7,
            "schedule_day": "fri",
            "schedule_frame": None,
            "recipients": [{"email": "cfo@example.com"}],
        }

    @pytest.mark.asyncio
    async def test_new_email_channel_uses_given_schedule(self, mock_context):
        slack = {**SLACK_CHANNEL, "schedule_type": "weekly", "schedule_hour": 7, "schedule_day": "fri"}
        pulse = {**SAMPLE_PULSE, "channels": [slack]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(SUB_DASHBOARD), *_checks(), *_checks(CHURN_CARD), _ok(pulse)]
        result = await metabase.execute_action(
            "update_subscription",
            {"subscription_id": 15, "frequency": "daily", "hour": 6, "recipient_user_ids": [5]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][1]
        assert email["schedule_type"] == "daily"
        assert email["schedule_hour"] == 6
        assert email["schedule_day"] is None
        assert email["recipients"] == [{"id": 5}]

    @pytest.mark.asyncio
    async def test_monthly_subscription_recipients_change(self, mock_context):
        monthly = {**EMAIL_CHANNEL, "schedule_type": "monthly", "schedule_day": "mon", "schedule_frame": "first"}
        pulse = {**SAMPLE_PULSE, "channels": [monthly]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        result = await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_emails": ["cfo@example.com"]}, mock_context
        )
        assert result.type == ResultType.ACTION
        email = mock_context.fetch.call_args.kwargs["json"]["channels"][0]
        assert email["schedule_type"] == "monthly"
        assert email["schedule_frame"] == "first"


# ---- Users ----


class TestListUsers:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_USERS)
        result = await metabase.execute_action("list_users", {}, mock_context)
        data = result.result.data
        assert data["users"][0] == {"id": 5, "name": "Ana Lee", "email": "ana@example.com", "is_active": True}
        assert data["users"][1]["is_active"] is False
        assert data["users"][2]["is_active"] is True
        assert data["count"] == 3
        assert data["total"] == 23
        assert data["limit"] == 50
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_USERS)
        await metabase.execute_action("list_users", {}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/user?limit=50&offset=0"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_query_and_paging(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_USERS)
        result = await metabase.execute_action(
            "list_users", {"query": " ana@example ", "limit": 10, "offset": 20}, mock_context
        )
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/user?query=ana%40example&limit=10&offset=20"
        assert result.result.data["limit"] == 10
        assert result.result.data["offset"] == 20

    @pytest.mark.asyncio
    async def test_blank_query_omitted(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_USERS)
        await metabase.execute_action("list_users", {"query": "   "}, mock_context)
        assert "query=" not in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_plain_list_response(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_USERS["data"][:2])
        result = await metabase.execute_action("list_users", {}, mock_context)
        assert result.result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_limit_over_max_rejected(self, mock_context):
        result = await metabase.execute_action("list_users", {"limit": 500}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_forbidden(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("list_users", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "permissions" in result.result.message


# ---- Data descriptions ----


class TestUpdateTable:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_TABLE, "description": "All orders"})
        result = await metabase.execute_action(
            "update_table", {"table_id": 31, "display_name": "Orders", "description": "All orders"}, mock_context
        )
        assert result.result.data == {
            "id": 31,
            "schema": "PUBLIC",
            "name": "ORDERS",
            "display_name": "Orders",
            "description": "All orders",
        }
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/table/31"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"display_name": "Orders", "description": "All orders"}

    @pytest.mark.asyncio
    async def test_description_only(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TABLE)
        await metabase.execute_action("update_table", {"table_id": 31, "description": "All orders"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"description": "All orders"}

    @pytest.mark.asyncio
    async def test_nothing_given(self, mock_context):
        result = await metabase.execute_action("update_table", {"table_id": 31, "display_name": ""}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("update_table", {"table_id": 999, "description": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestUpdateField:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        field = {
            "id": 120,
            "name": "TOTAL",
            "display_name": "Order total",
            "base_type": "type/Float",
            "semantic_type": "type/Currency",
            "description": "Total incl. tax",
            "fk_target_field_id": None,
        }
        mock_context.fetch.return_value = _ok(field)
        result = await metabase.execute_action(
            "update_field",
            {
                "field_id": 120,
                "display_name": "Order total",
                "description": "Total incl. tax",
                "semantic_type": "type/Currency",
            },
            mock_context,
        )
        assert result.result.data["semantic_type"] == "type/Currency"
        assert result.result.data["display_name"] == "Order total"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/field/120"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "display_name": "Order total",
            "description": "Total incl. tax",
            "semantic_type": "type/Currency",
        }

    @pytest.mark.asyncio
    async def test_semantic_type_only(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 120})
        await metabase.execute_action("update_field", {"field_id": 120, "semantic_type": "type/Email"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"semantic_type": "type/Email"}

    @pytest.mark.asyncio
    async def test_keeps_existing_conversion(self, mock_context):
        mock_context.fetch.side_effect = [
            _ok({"id": 120, "coercion_strategy": "Coercion/UNIXSeconds->DateTime"}),
            _ok({"id": 120}),
        ]
        await metabase.execute_action("update_field", {"field_id": 120, "description": "Signed up"}, mock_context)
        assert mock_context.fetch.call_args_list[0].kwargs["method"] == "GET"
        # Read with the same permission the edit needs, so metadata-only admins aren't refused.
        assert mock_context.fetch.call_args_list[0].kwargs["params"] == {"include_editable_data_model": "true"}
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "description": "Signed up",
            "coercion_strategy": "Coercion/UNIXSeconds->DateTime",
        }

    @pytest.mark.asyncio
    async def test_nothing_given(self, mock_context):
        result = await metabase.execute_action("update_field", {"field_id": 120}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Bad", {"errors": {"semantic_type": "invalid"}})
        result = await metabase.execute_action(
            "update_field", {"field_id": 120, "semantic_type": "type/Nope"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 400" in result.result.message


class TestSyncDatabase:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"status": "ok"})
        result = await metabase.execute_action("sync_database", {"database_id": 3}, mock_context)
        assert result.result.data == {"database_id": 3, "started": True}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/database/3/sync_schema"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("sync_database", {"database_id": 999}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    async def test_non_json_response(self, mock_context):
        mock_context.fetch.return_value = _ok("<html>Sign in</html>")
        result = await metabase.execute_action("sync_database", {"database_id": 3}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "isn't JSON" in result.result.message


class TestRescanFieldValues:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"status": "ok"})
        result = await metabase.execute_action("rescan_field_values", {"database_id": 3}, mock_context)
        assert result.result.data == {"database_id": 3, "started": True}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/database/3/rescan_values"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("rescan_field_values", {"database_id": 3}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "permissions" in result.result.message


# ---- Timelines ----


class TestListTimelines:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TIMELINES)
        result = await metabase.execute_action("list_timelines", {}, mock_context)
        data = result.result.data
        assert data["count"] == 2
        assert data["timelines"][0] == {
            "id": 4,
            "name": "Releases",
            "description": None,
            "collection_id": 12,
            "archived": False,
            "events": [
                {
                    "id": 90,
                    "timeline_id": 4,
                    "name": "v2 launch",
                    "description": "Big release",
                    "timestamp": "2026-11-01T00:00:00Z",
                    "archived": False,
                }
            ],
        }
        assert data["timelines"][1]["events"] == []

    @pytest.mark.asyncio
    async def test_request(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_timelines", {}, mock_context)
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/timeline?include=events"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_archived(self, mock_context):
        mock_context.fetch.return_value = _ok([])
        await metabase.execute_action("list_timelines", {"archived": True}, mock_context)
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/timeline?include=events&archived=true"

    @pytest.mark.asyncio
    async def test_filters_by_collection_client_side(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TIMELINES)
        result = await metabase.execute_action("list_timelines", {"collection_id": 12}, mock_context)
        assert [t["id"] for t in result.result.data["timelines"]] == [4]
        assert mock_context.fetch.call_args.args[0] == f"{BASE}/api/timeline?include=events"

    @pytest.mark.asyncio
    async def test_no_match(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_TIMELINES)
        result = await metabase.execute_action("list_timelines", {"collection_id": 99}, mock_context)
        assert result.result.data == {"timelines": [], "count": 0}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "Server error", "boom")
        result = await metabase.execute_action("list_timelines", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateTimeline:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 4, "name": "Releases", "collection_id": 12, "icon": "bell"})
        result = await metabase.execute_action(
            "create_timeline",
            {"name": "Releases", "collection_id": 12, "description": "Product releases", "icon": "bell"},
            mock_context,
        )
        assert result.result.data == {"id": 4, "name": "Releases", "collection_id": 12}
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/timeline"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "name": "Releases",
            "icon": "bell",
            "description": "Product releases",
            "collection_id": 12,
        }

    @pytest.mark.asyncio
    async def test_minimal_body(self, mock_context):
        mock_context.fetch.return_value = _ok({"id": 5, "name": "Campaigns", "collection_id": None})
        await metabase.execute_action("create_timeline", {"name": "Campaigns"}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "Campaigns", "icon": "star"}

    @pytest.mark.asyncio
    async def test_blank_name(self, mock_context):
        result = await metabase.execute_action("create_timeline", {"name": " "}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_bad_icon_rejected(self, mock_context):
        result = await metabase.execute_action("create_timeline", {"name": "Releases", "icon": "rocket"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_says_check_first(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action("create_timeline", {"name": "Releases"}, mock_context)
        assert "may still have saved" in result.result.message
        assert "list_timelines" in result.result.message

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({"name": "Releases"})
        result = await metabase.execute_action("create_timeline", {"name": "Releases"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "Forbidden", {"message": "You don't have permissions."})
        result = await metabase.execute_action("create_timeline", {"name": "Releases"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 403" in result.result.message


class TestCreateTimelineEvent:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_EVENT)
        result = await metabase.execute_action(
            "create_timeline_event",
            {
                "timeline_id": 4,
                "name": "v2 launch",
                "timestamp": "2026-11-01T09:30:00Z",
                "description": "Big release",
                "time_matters": True,
                "timezone": "Pacific/Auckland",
                "icon": "balloons",
            },
            mock_context,
        )
        assert result.result.data["id"] == 90
        assert result.result.data["timeline_id"] == 4
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/timeline-event"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {
            "timeline_id": 4,
            "name": "v2 launch",
            "timestamp": "2026-11-01T09:30:00Z",
            "timezone": "Pacific/Auckland",
            "time_matters": True,
            "icon": "balloons",
            "description": "Big release",
        }

    @pytest.mark.asyncio
    async def test_defaults(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_EVENT)
        await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 4, "name": "v2 launch", "timestamp": "2026-11-01"}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "timeline_id": 4,
            "name": "v2 launch",
            "timestamp": "2026-11-01",
            "timezone": "UTC",
            "time_matters": False,
            "icon": "star",
        }

    @pytest.mark.asyncio
    async def test_blank_timestamp(self, mock_context):
        result = await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 4, "name": "v2 launch", "timestamp": " "}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "timestamp" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_timestamp(self, mock_context):
        result = await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 4, "name": "v2 launch"}, mock_context
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_says_check_first(self, mock_context):
        mock_context.fetch.side_effect = asyncio.TimeoutError()
        result = await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 4, "name": "v2 launch", "timestamp": "2026-11-01"}, mock_context
        )
        assert "may still have saved" in result.result.message
        assert "list_timelines" in result.result.message

    @pytest.mark.asyncio
    async def test_no_id_returned(self, mock_context):
        mock_context.fetch.return_value = _ok({"name": "v2 launch"})
        result = await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 4, "name": "v2 launch", "timestamp": "2026-11-01"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_timeline_not_found(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action(
            "create_timeline_event", {"timeline_id": 999, "name": "v2 launch", "timestamp": "2026-11-01"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestUpdateTimelineEvent:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = _ok({**SAMPLE_EVENT, "name": "v2.0 launch"})
        result = await metabase.execute_action(
            "update_timeline_event", {"event_id": 90, "name": "v2.0 launch"}, mock_context
        )
        assert result.result.data["name"] == "v2.0 launch"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{BASE}/api/timeline-event/90"
        assert call.kwargs["method"] == "PUT"
        assert call.kwargs["retry_count"] == NO_RETRY
        assert call.kwargs["json"] == {"name": "v2.0 launch"}

    @pytest.mark.asyncio
    async def test_all_fields(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_EVENT)
        await metabase.execute_action(
            "update_timeline_event",
            {
                "event_id": 90,
                "description": "Moved",
                "timestamp": "2026-11-02T10:00:00Z",
                "timezone": "Pacific/Auckland",
                "time_matters": True,
            },
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["json"] == {
            "description": "Moved",
            "timestamp": "2026-11-02T10:00:00Z",
            "timezone": "Pacific/Auckland",
            "time_matters": True,
        }

    @pytest.mark.asyncio
    async def test_time_matters_false_sent(self, mock_context):
        mock_context.fetch.return_value = _ok(SAMPLE_EVENT)
        await metabase.execute_action("update_timeline_event", {"event_id": 90, "time_matters": False}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"time_matters": False}

    @pytest.mark.asyncio
    async def test_nothing_given(self, mock_context):
        result = await metabase.execute_action("update_timeline_event", {"event_id": 90}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "at least one change" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = _not_found()
        result = await metabase.execute_action("update_timeline_event", {"event_id": 999, "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestSubscriptionAndAlertFixes:
    @pytest.mark.asyncio
    async def test_disabled_email_channel_stays_disabled(self, mock_context):
        pulse = {**SAMPLE_PULSE, "channels": [{**EMAIL_CHANNEL, "enabled": False}]}
        mock_context.fetch.side_effect = [_ok(pulse), _ok(pulse)]
        await metabase.execute_action(
            "update_subscription", {"subscription_id": 15, "recipient_emails": ["cfo@example.com"]}, mock_context
        )
        assert mock_context.fetch.call_args.kwargs["json"]["channels"][0]["enabled"] is False

    @pytest.mark.asyncio
    async def test_old_metabase_inactive_alerts_listed_with_active_ones(self, mock_context):
        active = {"id": 1, "card": {"id": 42}, "alert_condition": "rows", "archived": False, "channels": []}
        archived = {**active, "id": 2, "archived": True}
        mock_context.fetch.side_effect = [
            HTTPError(404, "API endpoint does not exist.", "API endpoint does not exist."),
            _ok([active]),
            _ok([archived]),
        ]
        result = await metabase.execute_action("list_alerts", {"include_inactive": True}, mock_context)
        assert [a["id"] for a in result.result.data["alerts"]] == [1, 2]
        assert [a["active"] for a in result.result.data["alerts"]] == [True, False]
        urls = [c.args[0] for c in mock_context.fetch.call_args_list[1:]]
        assert urls == [f"{BASE}/api/alert?archived=false", f"{BASE}/api/alert?archived=true"]
