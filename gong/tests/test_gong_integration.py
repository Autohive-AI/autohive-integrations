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
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("gong_mod", os.path.join(_parent, "gong.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

gong = _mod.gong  # the Integration instance

pytestmark = pytest.mark.integration

BASE_URL = "https://api.gong.io"

# Skip all integration tests if GONG_ACCESS_TOKEN env var is not set
pytest.importorskip  # ensure pytest available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GONG_ACCESS_TOKEN"),
        reason="GONG_ACCESS_TOKEN environment variable not set",
    ),
]


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


# ---- list_calls integration tests ----


class TestListCallsIntegration:
    @pytest.mark.asyncio
    async def test_list_calls_returns_sorted_calls(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "calls": [
                    {
                        "id": "2",
                        "title": "B",
                        "started": "2025-01-02T00:00:00Z",
                        "duration": 5,
                        "participants": [],
                        "outcome": "",
                        "isPrivate": False,
                    },
                    {
                        "id": "1",
                        "title": "A",
                        "started": "2025-01-01T00:00:00Z",
                        "duration": 10,
                        "participants": [],
                        "outcome": "",
                        "isPrivate": False,
                    },
                ],
                "hasMore": False,
                "nextCursor": None,
            },
        )

        result = await gong.execute_action("list_calls", {"limit": 2}, mock_context)

        data = result.result.data
        assert "calls" in data
        assert len(data["calls"]) == 2
        assert data["calls"][0]["id"] == "2"  # sorted newest first

    @pytest.mark.asyncio
    async def test_list_calls_filters_private(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "calls": [
                    {
                        "id": "p1",
                        "title": "Private",
                        "started": "2025-01-03T00:00:00Z",
                        "duration": 1,
                        "isPrivate": True,
                    },
                    {
                        "id": "pub",
                        "title": "Public",
                        "started": "2025-01-02T00:00:00Z",
                        "duration": 2,
                        "isPrivate": False,
                    },
                ],
                "hasMore": False,
                "nextCursor": None,
            },
        )

        result = await gong.execute_action("list_calls", {"limit": 10}, mock_context)
        data = result.result.data
        ids = [c["id"] for c in data["calls"]]
        assert "p1" not in ids
        assert "pub" in ids


# ---- get_call_details integration tests ----


class TestGetCallDetailsIntegration:
    @pytest.mark.asyncio
    async def test_get_call_details_with_extensive(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={
                    "call": {
                        "id": "abc",
                        "title": "Demo",
                        "started": "2025-01-01T00:00:00Z",
                        "duration": 60,
                        "isPrivate": False,
                    }
                },
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "calls": [
                        {
                            "id": "abc",
                            "parties": [{"userId": "u1", "name": "Jane"}],
                            "crmData": {"opp": 123},
                            "outcome": "Won",
                        }
                    ]
                },
            ),
        ]

        result = await gong.execute_action("get_call_details", {"call_id": "abc"}, mock_context)
        data = result.result.data
        assert data["id"] == "abc"
        assert data["title"] == "Demo"
        assert len(data["participants"]) == 1
        assert data["participants"][0]["name"] == "Jane"

    @pytest.mark.asyncio
    async def test_get_call_details_private_returns_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"call": {"id": "x", "isPrivate": True}},
        )

        result = await gong.execute_action("get_call_details", {"call_id": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "private_call_filtered" in result.result.message


# ---- get_call_transcript integration tests ----


class TestGetCallTranscriptIntegration:
    @pytest.mark.asyncio
    async def test_transcript_speaker_mapping(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data={"call": {"id": "xyz", "started": "2025-01-01T00:00:00Z", "isPrivate": False}},
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "calls": [
                        {
                            "parties": [
                                {"speakerId": "1", "name": "Alice"},
                                {"speakerId": "2", "name": "Bob"},
                            ]
                        }
                    ]
                },
            ),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "callTranscripts": [
                        {
                            "transcript": [
                                {
                                    "speakerId": "1",
                                    "sentences": [{"start": 0, "end": 1000, "text": "Hi"}],
                                },
                                {
                                    "speakerId": "2",
                                    "sentences": [{"start": 1000, "end": 2000, "text": "Hello"}],
                                },
                            ]
                        }
                    ]
                },
            ),
        ]

        result = await gong.execute_action("get_call_transcript", {"call_id": "xyz"}, mock_context)
        data = result.result.data
        assert len(data["transcript"]) == 2
        assert data["transcript"][0]["speaker_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_transcript_private_returns_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"call": {"id": "y", "isPrivate": True}},
        )

        result = await gong.execute_action("get_call_transcript", {"call_id": "y"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "private_call_filtered" in result.result.message


# ---- list_users integration tests ----


class TestListUsersIntegration:
    @pytest.mark.asyncio
    async def test_list_users_returns_users(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "users": [
                    {
                        "id": "u1",
                        "name": "Alice",
                        "email": "a@example.com",
                        "role": "admin",
                        "active": True,
                    }
                ],
                "hasMore": False,
                "nextCursor": None,
            },
        )

        result = await gong.execute_action("list_users", {"limit": 1}, mock_context)
        data = result.result.data
        assert data["users"][0]["id"] == "u1"


# ---- search_calls integration tests ----


class TestSearchCallsIntegration:
    @pytest.mark.asyncio
    async def test_search_skips_private_calls(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "calls": [
                    {
                        "id": "priv",
                        "isPrivate": True,
                        "title": "private pricing call",
                        "content": {"pointsOfInterest": [{"action": "demo pricing", "startTime": 0}]},
                    },
                    {
                        "id": "pub",
                        "isPrivate": False,
                        "title": "Public",
                        "started": "2025-01-01T00:00:00Z",
                        "content": {"pointsOfInterest": [{"action": "product demo pricing", "startTime": 10}]},
                    },
                ]
            },
        )

        result = await gong.execute_action("search_calls", {"query": "pricing"}, mock_context)
        data = result.result.data
        ids = [r["call_id"] for r in data["results"]]
        assert "priv" not in ids
        assert "pub" in ids
