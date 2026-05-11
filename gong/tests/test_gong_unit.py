import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("gong_mod", os.path.join(_parent, "gong.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

gong = _mod.gong  # the Integration instance

pytestmark = pytest.mark.unit

BASE_URL = "https://api.gong.io"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    ctx.metadata = {"api_base_url": BASE_URL}
    return ctx


# ---- list_calls ----


class TestListCalls:
    async def test_happy_path_returns_calls(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {
                    "id": "call-1",
                    "title": "Demo Call",
                    "started": "2025-01-15T10:00:00Z",
                    "duration": 3600,
                    "participants": [],
                    "outcome": "won",
                    "isPrivate": False,
                }
            ],
            "hasMore": False,
            "nextCursor": None,
        }

        result = await gong.execute_action("list_calls", {}, mock_context)

        assert result.result.data["calls"][0]["id"] == "call-1"
        assert result.result.data["calls"][0]["title"] == "Demo Call"
        assert result.result.data["has_more"] is False

    async def test_private_calls_filtered_out(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {"id": "call-private", "isPrivate": True, "title": "Private"},
                {
                    "id": "call-public",
                    "isPrivate": False,
                    "title": "Public",
                    "started": "2025-01-15T10:00:00Z",
                },
            ],
            "hasMore": False,
            "nextCursor": None,
        }

        result = await gong.execute_action("list_calls", {}, mock_context)

        ids = [c["id"] for c in result.result.data["calls"]]
        assert "call-private" not in ids
        assert "call-public" in ids

    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = {"calls": [], "hasMore": False, "nextCursor": None}

        await gong.execute_action("list_calls", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{BASE_URL}/v2/calls"

    async def test_date_params_passed_correctly(self, mock_context):
        mock_context.fetch.return_value = {"calls": [], "hasMore": False, "nextCursor": None}

        await gong.execute_action("list_calls", {"from_date": "2025-01-01", "to_date": "2025-01-31"}, mock_context)

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["params"]["fromDateTime"] == "2025-01-01T00:00:00.000Z"
        assert call_kwargs["params"]["toDateTime"] == "2025-01-31T23:59:59.999Z"

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await gong.execute_action("list_calls", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    async def test_calls_sorted_newest_first(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {"id": "old", "started": "2025-01-01T10:00:00Z", "isPrivate": False},
                {"id": "new", "started": "2025-01-15T10:00:00Z", "isPrivate": False},
            ],
            "hasMore": False,
            "nextCursor": None,
        }

        result = await gong.execute_action("list_calls", {}, mock_context)

        calls = result.result.data["calls"]
        assert calls[0]["id"] == "new"
        assert calls[1]["id"] == "old"

    async def test_pagination_cursor_passed(self, mock_context):
        mock_context.fetch.return_value = {"calls": [], "hasMore": False, "nextCursor": None}

        await gong.execute_action("list_calls", {"cursor": "abc123"}, mock_context)

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["params"]["cursor"] == "abc123"


# ---- get_call_transcript ----


class TestGetCallTranscript:
    async def test_happy_path_returns_transcript(self, mock_context):
        # call details -> extensive -> transcript
        mock_context.fetch.side_effect = [
            {"call": {"id": "c1", "isPrivate": False}},
            {
                "calls": [
                    {
                        "parties": [{"speakerId": "s1", "name": "Alice"}],
                    }
                ]
            },
            {
                "callTranscripts": [
                    {
                        "transcript": [
                            {
                                "speakerId": "s1",
                                "sentences": [{"start": 1000, "end": 3000, "text": "Hello world"}],
                            }
                        ]
                    }
                ]
            },
        ]

        result = await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        assert result.result.data["call_id"] == "c1"
        assert len(result.result.data["transcript"]) == 1
        assert result.result.data["transcript"][0]["text"] == "Hello world"
        assert result.result.data["transcript"][0]["speaker_name"] == "Alice"
        assert result.result.data["transcript"][0]["start_time"] == 1.0

    async def test_private_call_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = {"call": {"id": "c1", "isPrivate": True}}

        result = await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "private_call_filtered" in result.result.message

    async def test_request_urls_correct(self, mock_context):
        mock_context.fetch.side_effect = [
            {"call": {"id": "c1", "isPrivate": False}},
            {"calls": []},
            {"callTranscripts": []},
        ]

        await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        calls = mock_context.fetch.call_args_list
        assert calls[0].args[0] == f"{BASE_URL}/v2/calls/c1"
        assert calls[1].args[0] == f"{BASE_URL}/v2/calls/extensive"
        assert calls[2].args[0] == f"{BASE_URL}/v2/calls/transcript"

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message

    async def test_empty_transcript(self, mock_context):
        mock_context.fetch.side_effect = [
            {"call": {"id": "c1", "isPrivate": False}},
            {"calls": []},
            {"callTranscripts": []},
        ]

        result = await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        assert result.result.data["transcript"] == []

    async def test_unknown_speaker_fallback(self, mock_context):
        mock_context.fetch.side_effect = [
            {"call": {"id": "c1", "isPrivate": False}},
            {"calls": []},  # no speaker map
            {
                "callTranscripts": [
                    {
                        "transcript": [
                            {
                                "speakerId": "999",
                                "sentences": [{"start": 0, "end": 1000, "text": "Hi"}],
                            }
                        ]
                    }
                ]
            },
        ]

        result = await gong.execute_action("get_call_transcript", {"call_id": "c1"}, mock_context)

        assert result.result.data["transcript"][0]["speaker_name"] == "Speaker 999"


# ---- get_call_details ----


class TestGetCallDetails:
    async def test_happy_path_returns_call(self, mock_context):
        mock_context.fetch.side_effect = [
            {
                "call": {
                    "id": "c1",
                    "title": "Big Deal Call",
                    "started": "2025-01-15T10:00:00Z",
                    "duration": 1800,
                    "outcome": "won",
                    "isPrivate": False,
                }
            },
            {
                "calls": [
                    {
                        "parties": [{"name": "Bob"}],
                        "crmData": {"accountId": "acc-1"},
                        "outcome": "won",
                    }
                ]
            },
        ]

        result = await gong.execute_action("get_call_details", {"call_id": "c1"}, mock_context)

        assert result.result.data["id"] == "c1"
        assert result.result.data["title"] == "Big Deal Call"
        assert result.result.data["duration"] == 1800
        assert result.result.data["participants"] == [{"name": "Bob"}]

    async def test_private_call_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = {"call": {"id": "c1", "isPrivate": True}}

        result = await gong.execute_action("get_call_details", {"call_id": "c1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "private_call_filtered" in result.result.message

    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = {"call": {"id": "c1", "isPrivate": False, "started": "2025-01-15T10:00:00Z"}}

        await gong.execute_action("get_call_details", {"call_id": "c1"}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0] == f"{BASE_URL}/v2/calls/c1"

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("timeout")

        result = await gong.execute_action("get_call_details", {"call_id": "c1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "timeout" in result.result.message

    async def test_response_shape(self, mock_context):
        mock_context.fetch.side_effect = [
            {
                "call": {
                    "id": "c1",
                    "isPrivate": False,
                    "started": "2025-01-15T10:00:00Z",
                }
            },
            {"calls": []},
        ]

        result = await gong.execute_action("get_call_details", {"call_id": "c1"}, mock_context)

        data = result.result.data
        assert "id" in data
        assert "title" in data
        assert "started" in data
        assert "duration" in data
        assert "participants" in data
        assert "outcome" in data
        assert "crm_data" in data


# ---- search_calls ----


class TestSearchCalls:
    async def test_happy_path_returns_results(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {
                    "id": "c1",
                    "title": "pricing discussion",
                    "started": "2025-01-10T10:00:00Z",
                    "isPrivate": False,
                    "content": {"topics": [], "pointsOfInterest": []},
                }
            ]
        }

        result = await gong.execute_action("search_calls", {"query": "pricing"}, mock_context)

        assert result.result.data["total_count"] == 1
        assert result.result.data["results"][0]["call_id"] == "c1"

    async def test_no_match_returns_empty(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {
                    "id": "c1",
                    "title": "unrelated call",
                    "isPrivate": False,
                    "content": {"topics": [], "pointsOfInterest": []},
                }
            ]
        }

        result = await gong.execute_action("search_calls", {"query": "pricing"}, mock_context)

        assert result.result.data["total_count"] == 0

    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = {"calls": []}

        await gong.execute_action("search_calls", {"query": "test"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{BASE_URL}/v2/calls/extensive"
        assert call_args.kwargs["method"] == "POST"

    async def test_private_calls_filtered(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {"id": "c1", "title": "test call", "isPrivate": True, "content": {}},
            ]
        }

        result = await gong.execute_action("search_calls", {"query": "test"}, mock_context)

        assert result.result.data["total_count"] == 0

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Search failed")

        result = await gong.execute_action("search_calls", {"query": "test"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Search failed" in result.result.message

    async def test_topic_match_included(self, mock_context):
        mock_context.fetch.return_value = {
            "calls": [
                {
                    "id": "c1",
                    "title": "Q1 review",
                    "started": "2025-01-10T10:00:00Z",
                    "isPrivate": False,
                    "content": {
                        "topics": [{"name": "pricing strategy"}],
                        "pointsOfInterest": [],
                    },
                }
            ]
        }

        result = await gong.execute_action("search_calls", {"query": "pricing"}, mock_context)

        assert result.result.data["total_count"] == 1

    async def test_date_filter_applied(self, mock_context):
        mock_context.fetch.return_value = {"calls": []}

        await gong.execute_action(
            "search_calls",
            {"query": "demo", "from_date": "2025-01-01", "to_date": "2025-01-31"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["filter"]["fromDateTime"] == "2025-01-01T00:00:00.000Z"
        assert payload["filter"]["toDateTime"] == "2025-01-31T23:59:59.999Z"


# ---- list_users ----


class TestListUsers:
    async def test_happy_path_returns_users(self, mock_context):
        mock_context.fetch.return_value = {
            "users": [
                {
                    "id": "u1",
                    "name": "Alice",
                    "email": "alice@example.com",
                    "role": "admin",
                    "active": True,
                }
            ],
            "hasMore": False,
            "nextCursor": None,
        }

        result = await gong.execute_action("list_users", {}, mock_context)

        assert result.result.data["users"][0]["id"] == "u1"
        assert result.result.data["users"][0]["name"] == "Alice"
        assert result.result.data["has_more"] is False

    async def test_request_url_and_default_limit(self, mock_context):
        mock_context.fetch.return_value = {"users": [], "hasMore": False, "nextCursor": None}

        await gong.execute_action("list_users", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{BASE_URL}/v2/users"
        assert call_args.kwargs["params"]["limit"] == 100

    async def test_custom_limit_passed(self, mock_context):
        mock_context.fetch.return_value = {"users": [], "hasMore": False, "nextCursor": None}

        await gong.execute_action("list_users", {"limit": 50}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 50

    async def test_cursor_pagination(self, mock_context):
        mock_context.fetch.return_value = {"users": [], "hasMore": True, "nextCursor": "next-page"}

        result = await gong.execute_action("list_users", {"cursor": "page-2"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["cursor"] == "page-2"
        assert result.result.data["next_cursor"] == "next-page"

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await gong.execute_action("list_users", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message

    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = {
            "users": [{"id": "u1", "name": "Bob", "email": "bob@test.com", "role": "rep", "active": True}],
            "hasMore": False,
            "nextCursor": None,
        }

        result = await gong.execute_action("list_users", {}, mock_context)

        user = result.result.data["users"][0]
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "role" in user
        assert "active" in user
