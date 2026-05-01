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

SAMPLE_MESSAGE = {
    "id": "msg_123",
    "type": "email",
    "is_inbound": True,
    "author": None,
    "subject": "Help needed",
    "body": "<p>Hello</p>",
    "created_at": 1700000000,
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


class TestFrontDataParserMessage:
    def test_parse_message_required_fields(self):
        raw = {"id": "msg_1", "type": "email", "is_inbound": True, "author": None}
        result = FrontDataParser.parse_message(raw)
        assert result["id"] == "msg_1"
        assert result["type"] == "email"
        assert result["is_inbound"] is True
        assert result["author"] is None

    def test_parse_message_optional_fields(self):
        raw = {
            "id": "msg_1",
            "type": "email",
            "is_inbound": False,
            "author": {"id": "tea_1"},
            "subject": "Test",
            "body": "<p>Hello</p>",
            "recipients": [{"handle": "x@x.com", "role": "to"}],
            "created_at": 1700000000,
        }
        result = FrontDataParser.parse_message(raw)
        assert result["subject"] == "Test"
        assert result["body"] == "<p>Hello</p>"
        assert result["created_at"] == 1700000000
        assert len(result["recipients"]) == 1


# ---- Messages ----


class TestListConversationMessages:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": [SAMPLE_MESSAGE]}
        )

        result = await front.execute_action(
            "list_conversation_messages", {"conversation_id": "cnv_123"}, mock_context
        )

        assert len(result.result.data["messages"]) == 1
        assert result.result.data["messages"][0]["id"] == "msg_123"

    @pytest.mark.asyncio
    async def test_request_url_and_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": []}
        )

        await front.execute_action(
            "list_conversation_messages",
            {"conversation_id": "cnv_123", "limit": 30},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "conversations/cnv_123/messages" in call_args.args[0]
        assert call_args.kwargs["params"]["limit"] == 30

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": []}
        )

        await front.execute_action(
            "list_conversation_messages",
            {"conversation_id": "cnv_123", "limit": 200},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": []}
        )

        result = await front.execute_action(
            "list_conversation_messages", {"conversation_id": "cnv_123"}, mock_context
        )

        assert result.result.data["messages"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await front.execute_action(
            "list_conversation_messages", {"conversation_id": "cnv_123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetMessage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_MESSAGE
        )

        result = await front.execute_action(
            "get_message", {"message_id": "msg_123"}, mock_context
        )

        assert result.result.data["message"]["id"] == "msg_123"
        assert result.result.data["message"]["type"] == "email"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_MESSAGE
        )

        await front.execute_action(
            "get_message", {"message_id": "msg_123"}, mock_context
        )

        assert (
            mock_context.fetch.call_args.args[0]
            == "https://api2.frontapp.com/messages/msg_123"
        )

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"error": "Message not found"}
        )

        result = await front.execute_action(
            "get_message", {"message_id": "msg_bad"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Message not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection error")

        result = await front.execute_action(
            "get_message", {"message_id": "msg_123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection error" in result.result.message

    @pytest.mark.asyncio
    async def test_response_has_message_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=SAMPLE_MESSAGE
        )

        result = await front.execute_action(
            "get_message", {"message_id": "msg_123"}, mock_context
        )

        assert "message" in result.result.data


class TestCreateMessage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_new123"}
        )

        result = await front.execute_action(
            "create_message",
            {"channel_id": "cha_123", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        assert result.result.data["message_uid"] == "uid_new123"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_new123"}
        )

        await front.execute_action(
            "create_message",
            {"channel_id": "cha_123", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "channels/cha_123/messages" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_includes_recipients(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_new123"}
        )

        await front.execute_action(
            "create_message",
            {
                "channel_id": "cha_123",
                "body": "Hello!",
                "to": ["user@example.com"],
                "cc": ["cc@example.com"],
                "subject": "Test",
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["to"] == ["user@example.com"]
        assert payload["cc"] == ["cc@example.com"]
        assert payload["subject"] == "Test"

    @pytest.mark.asyncio
    async def test_api_error_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"error": "Channel not found"}
        )

        result = await front.execute_action(
            "create_message",
            {"channel_id": "cha_bad", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await front.execute_action(
            "create_message",
            {"channel_id": "cha_123", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


class TestCreateMessageReply:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_abc123"}
        )

        result = await front.execute_action(
            "create_message_reply",
            {"conversation_id": "cnv_123", "body": "Thanks for your message!"},
            mock_context,
        )

        assert result.result.data["message_uid"] == "uid_abc123"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_abc123"}
        )

        await front.execute_action(
            "create_message_reply",
            {"conversation_id": "cnv_123", "body": "Reply here"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "conversations/cnv_123/messages" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_optional_fields_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"message_uid": "uid_abc123"}
        )

        await front.execute_action(
            "create_message_reply",
            {
                "conversation_id": "cnv_123",
                "body": "Reply",
                "to": ["user@example.com"],
                "subject": "Re: Issue",
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["to"] == ["user@example.com"]
        assert payload["subject"] == "Re: Issue"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"error": "Conversation archived"}
        )

        result = await front.execute_action(
            "create_message_reply",
            {"conversation_id": "cnv_123", "body": "Reply"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Conversation archived" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await front.execute_action(
            "create_message_reply",
            {"conversation_id": "cnv_123", "body": "Reply"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDownloadMessageAttachment:
    @pytest.mark.asyncio
    async def test_missing_auth_token_returns_error(self, mock_context):
        mock_context.auth = {"auth_type": "PlatformOauth2", "credentials": {}}

        result = await front.execute_action(
            "download_message_attachment",
            {"attachment_url": "https://api2.frontapp.com/attachments/att_123"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No authentication token" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.auth = {
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": "tok"},
        }  # nosec B105

        result = await front.execute_action(
            "download_message_attachment",
            {"attachment_url": "https://api2.frontapp.com/attachments/att_123"},
            mock_context,
        )

        # aiohttp is not mocked — will throw a real connection error wrapped as ActionError
        assert result.type == ResultType.ACTION_ERROR
