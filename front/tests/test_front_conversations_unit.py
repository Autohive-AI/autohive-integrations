import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "front_mod", os.path.join(_parent, "front.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

front = _mod.front  # the Integration instance
FrontDataParser = _mod.FrontDataParser

pytestmark = pytest.mark.unit

# ---- Sample Data ----

SAMPLE_CONVERSATION = {
    "id": "cnv_123",
    "subject": "Help with billing",
    "status": "assigned",
    "assignee": None,
    "recipient": {"handle": "customer@example.com", "name": "John Doe", "role": "from"},
    "tags": [],
    "links": [],
    "scheduled_reminders": [],
    "custom_fields": {},
    "metadata": {},
}


# ---- Fixtures ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Helper Tests ----


class TestFrontDataParserConversation:
    def test_parse_conversation_required_fields(self):
        raw = {"id": "cnv_1", "subject": "Test", "status": "open"}
        result = FrontDataParser.parse_conversation(raw)
        assert result["id"] == "cnv_1"
        assert result["subject"] == "Test"
        assert result["status"] == "open"

    def test_parse_conversation_optional_fields(self):
        raw = {
            "id": "cnv_1",
            "subject": "Test",
            "status": "open",
            "status_id": "status_1",
            "status_category": "open",
            "ticket_ids": ["t1"],
            "created_at": 1700000000,
            "is_private": True,
        }
        result = FrontDataParser.parse_conversation(raw)
        assert result["status_id"] == "status_1"
        assert result["status_category"] == "open"
        assert result["ticket_ids"] == ["t1"]
        assert result["created_at"] == 1700000000
        assert result["is_private"] is True

    def test_parse_conversation_defaults(self):
        raw = {"id": "cnv_1", "subject": "Test", "status": "open"}
        result = FrontDataParser.parse_conversation(raw)
        assert result["tags"] == []
        assert result["links"] == []
        assert result["custom_fields"] == {}
        assert result["metadata"] == {}


# ---- Conversations ----


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_CONVERSATION
        )

        result = await front.execute_action(
            "get_conversation", {"conversation_id": "cnv_123"}, mock_context
        )

        assert result.result.data["conversation"]["id"] == "cnv_123"
        assert result.result.data["conversation"]["subject"] == "Help with billing"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_CONVERSATION
        )

        await front.execute_action(
            "get_conversation", {"conversation_id": "cnv_123"}, mock_context
        )

        assert (
            mock_context.fetch.call_args.args[0]
            == "https://api2.frontapp.com/conversations/cnv_123"
        )

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"error": "Not found"}
        )

        result = await front.execute_action(
            "get_conversation", {"conversation_id": "cnv_bad"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await front.execute_action(
            "get_conversation", {"conversation_id": "cnv_123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message

    @pytest.mark.asyncio
    async def test_response_has_conversation_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_CONVERSATION
        )

        result = await front.execute_action(
            "get_conversation", {"conversation_id": "cnv_123"}, mock_context
        )

        assert "conversation" in result.result.data


class TestUpdateConversation:
    @pytest.mark.asyncio
    async def test_happy_path_with_patch_response(self, mock_context):
        updated_conv = {**SAMPLE_CONVERSATION, "status": "archived"}
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=updated_conv
        )

        result = await front.execute_action(
            "update_conversation",
            {"conversation_id": "cnv_123", "status": "archived"},
            mock_context,
        )

        assert result.result.data["conversation"]["id"] == "cnv_123"

    @pytest.mark.asyncio
    async def test_204_no_content_fetches_conversation(self, mock_context):
        # PATCH returns 204 (data is None), then GET returns the conversation
        mock_context.fetch.side_effect = [
            FetchResponse(status=204, headers={}, data=None),
            FetchResponse(status=200, headers={}, data=SAMPLE_CONVERSATION),
        ]

        result = await front.execute_action(
            "update_conversation",
            {"conversation_id": "cnv_123", "status": "open"},
            mock_context,
        )

        assert result.result.data["conversation"]["id"] == "cnv_123"
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_no_update_fields_returns_error(self, mock_context):
        result = await front.execute_action(
            "update_conversation",
            {"conversation_id": "cnv_123"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No valid update fields" in result.result.message

    @pytest.mark.asyncio
    async def test_request_method_is_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_CONVERSATION
        )

        await front.execute_action(
            "update_conversation",
            {"conversation_id": "cnv_123", "assignee_id": "tea_123"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await front.execute_action(
            "update_conversation",
            {"conversation_id": "cnv_123", "status": "open"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestFindConversation:
    @pytest.mark.asyncio
    async def test_match_by_subject(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": [SAMPLE_CONVERSATION]}
        )

        result = await front.execute_action(
            "find_conversation",
            {"inbox_id": "inb_123", "search_query": "billing"},
            mock_context,
        )

        assert len(result.result.data["conversations"]) == 1
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_match_by_recipient(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": [SAMPLE_CONVERSATION]}
        )

        result = await front.execute_action(
            "find_conversation",
            {"inbox_id": "inb_123", "search_query": "customer@example.com"},
            mock_context,
        )

        assert len(result.result.data["conversations"]) == 1

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": [SAMPLE_CONVERSATION]}
        )

        result = await front.execute_action(
            "find_conversation",
            {"inbox_id": "inb_123", "search_query": "xyz_no_match_xyz"},
            mock_context,
        )

        assert result.result.data["conversations"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action(
            "find_conversation",
            {"inbox_id": "inb_123", "search_query": "billing"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
