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

_spec = importlib.util.spec_from_file_location("front_mod", os.path.join(_parent, "front.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

front = _mod.front  # the Integration instance
FrontDataParser = _mod.FrontDataParser

pytestmark = pytest.mark.unit

# ---- Sample Data ----

SAMPLE_INBOX = {
    "id": "inb_123",
    "name": "Support",
    "address": "support@example.com",
    "type": "smtp",
    "is_private": False,
}

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

SAMPLE_MESSAGE = {
    "id": "msg_123",
    "type": "email",
    "is_inbound": True,
    "author": None,
    "subject": "Help needed",
    "body": "<p>Hello</p>",
    "created_at": 1700000000,
}

SAMPLE_TEAMMATE = {
    "id": "tea_123",
    "email": "agent@example.com",
    "username": "agent1",
    "first_name": "Agent",
    "last_name": "One",
    "is_admin": False,
    "is_available": True,
    "is_blocked": False,
    "type": "user",
    "custom_fields": {},
}

SAMPLE_CHANNEL = {
    "id": "cha_123",
    "name": "Support Email",
    "type": "smtp",
    "address": "support@example.com",
}

SAMPLE_TEMPLATE = {
    "id": "tpl_123",
    "name": "Welcome Template",
    "subject": "Welcome!",
    "body": "<p>Welcome to our service</p>",
    "attachments": [],
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


# ---- Helper Function Tests ----


class TestFrontDataParser:
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


# ---- Inbox Actions ----


class TestGetInbox:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_INBOX)

        result = await front.execute_action("get_inbox", {"inbox_id": "inb_123"}, mock_context)

        assert result.result.data["inbox"]["id"] == "inb_123"
        assert result.result.data["inbox"]["name"] == "Support"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_INBOX)

        await front.execute_action("get_inbox", {"inbox_id": "inb_123"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert call_url == "https://api2.frontapp.com/inboxes/inb_123"

    @pytest.mark.asyncio
    async def test_api_error_in_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"error": "Inbox not found", "_error": {}}
        )

        result = await front.execute_action("get_inbox", {"inbox_id": "inb_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Inbox not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await front.execute_action("get_inbox", {"inbox_id": "inb_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_optional_fields_present(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": "inb_1", "name": "Sales", "address": "sales@x.com", "type": "smtp", "is_private": True},
        )

        result = await front.execute_action("get_inbox", {"inbox_id": "inb_1"}, mock_context)

        inbox = result.result.data["inbox"]
        assert inbox["type"] == "smtp"
        assert inbox["is_private"] is True


# ---- Conversation Actions ----


class TestListInboxConversations:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"_results": [SAMPLE_CONVERSATION]}
        )

        result = await front.execute_action("list_inbox_conversations", {"inbox_id": "inb_123"}, mock_context)

        assert len(result.result.data["conversations"]) == 1
        assert result.result.data["conversations"][0]["id"] == "cnv_123"

    @pytest.mark.asyncio
    async def test_request_url_and_params(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action(
            "list_inbox_conversations",
            {"inbox_id": "inb_123", "status": "open", "limit": 25},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "inboxes/inb_123/conversations" in call_args.args[0]
        params = call_args.kwargs["params"]
        assert params["status"] == "open"
        assert params["limit"] == 25

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_inbox_conversations", {"inbox_id": "inb_123", "limit": 200}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        result = await front.execute_action("list_inbox_conversations", {"inbox_id": "inb_123"}, mock_context)

        assert result.result.data["conversations"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await front.execute_action("list_inbox_conversations", {"inbox_id": "inb_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONVERSATION)

        result = await front.execute_action("get_conversation", {"conversation_id": "cnv_123"}, mock_context)

        assert result.result.data["conversation"]["id"] == "cnv_123"
        assert result.result.data["conversation"]["subject"] == "Help with billing"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONVERSATION)

        await front.execute_action("get_conversation", {"conversation_id": "cnv_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/conversations/cnv_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Not found"})

        result = await front.execute_action("get_conversation", {"conversation_id": "cnv_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await front.execute_action("get_conversation", {"conversation_id": "cnv_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message


# ---- Message Actions ----


class TestListConversationMessages:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_MESSAGE]})

        result = await front.execute_action("list_conversation_messages", {"conversation_id": "cnv_123"}, mock_context)

        assert len(result.result.data["messages"]) == 1
        assert result.result.data["messages"][0]["id"] == "msg_123"

    @pytest.mark.asyncio
    async def test_request_url_and_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action(
            "list_conversation_messages",
            {"conversation_id": "cnv_123", "limit": 30},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "conversations/cnv_123/messages" in call_args.args[0]
        assert call_args.kwargs["params"]["limit"] == 30

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await front.execute_action("list_conversation_messages", {"conversation_id": "cnv_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetMessage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_MESSAGE)

        result = await front.execute_action("get_message", {"message_id": "msg_123"}, mock_context)

        assert result.result.data["message"]["id"] == "msg_123"
        assert result.result.data["message"]["type"] == "email"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_MESSAGE)

        await front.execute_action("get_message", {"message_id": "msg_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/messages/msg_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Message not found"})

        result = await front.execute_action("get_message", {"message_id": "msg_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Message not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection error")

        result = await front.execute_action("get_message", {"message_id": "msg_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection error" in result.result.message


class TestCreateMessageReply:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_abc123"})

        result = await front.execute_action(
            "create_message_reply",
            {"conversation_id": "cnv_123", "body": "Thanks for your message!"},
            mock_context,
        )

        assert result.result.data["message_uid"] == "uid_abc123"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_abc123"})

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
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_abc123"})

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
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Conversation archived"})

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


class TestCreateMessage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_new123"})

        result = await front.execute_action(
            "create_message",
            {"channel_id": "cha_123", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        assert result.result.data["message_uid"] == "uid_new123"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_new123"})

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
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"message_uid": "uid_new123"})

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
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await front.execute_action(
            "create_message",
            {"channel_id": "cha_123", "body": "Hello!", "to": ["user@example.com"]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Forbidden" in result.result.message


# ---- Channel Actions ----


class TestListChannels:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_CHANNEL]})

        result = await front.execute_action("list_channels", {}, mock_context)

        assert len(result.result.data["channels"]) == 1
        assert result.result.data["channels"][0]["id"] == "cha_123"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_channels", {"limit": 20}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api2.frontapp.com/channels"
        assert call_args.kwargs["params"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await front.execute_action("list_channels", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        result = await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert result.result.data["channel"]["id"] == "cha_123"
        assert result.result.data["channel"]["type"] == "smtp"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/channels/cha_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Channel not found"})

        result = await front.execute_action("get_channel", {"channel_id": "cha_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await front.execute_action("get_channel", {"channel_id": "cha_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListInboxChannels:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_CHANNEL]})

        result = await front.execute_action("list_inbox_channels", {"inbox_id": "inb_123"}, mock_context)

        assert len(result.result.data["channels"]) == 1

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_inbox_channels", {"inbox_id": "inb_123", "limit": 10}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "inboxes/inb_123/channels" in call_args.args[0]
        assert call_args.kwargs["params"]["limit"] == 10

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_inbox_channels", {"inbox_id": "inb_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Template Actions ----


class TestListMessageTemplates:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEMPLATE]})

        result = await front.execute_action("list_message_templates", {}, mock_context)

        assert len(result.result.data["templates"]) == 1
        assert result.result.data["templates"][0]["id"] == "tpl_123"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_message_templates", {"limit": 10}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/message_templates"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_message_templates", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetMessageTemplate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEMPLATE)

        result = await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert result.result.data["template"]["id"] == "tpl_123"
        assert result.result.data["template"]["name"] == "Welcome Template"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEMPLATE)

        await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/message_templates/tpl_123"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("get_message_template", {"message_template_id": "tpl_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Update Conversation ----


class TestUpdateConversation:
    @pytest.mark.asyncio
    async def test_happy_path_with_patch_response(self, mock_context):
        updated_conv = {**SAMPLE_CONVERSATION, "status": "archived"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated_conv)

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
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONVERSATION)

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


# ---- Inbox/Teammate Listing ----


class TestListInboxes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"_results": [{"id": "inb_1", "name": "Support", "address": "s@x.com"}]},
        )

        result = await front.execute_action("list_inboxes", {}, mock_context)

        assert len(result.result.data["inboxes"]) == 1
        assert result.result.data["inboxes"][0]["id"] == "inb_1"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_inboxes", {"limit": 10}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/inboxes"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await front.execute_action("list_inboxes", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListTeammates:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("list_teammates", {}, mock_context)

        assert len(result.result.data["teammates"]) == 1
        assert result.result.data["teammates"][0]["email"] == "agent@example.com"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_teammates", {"limit": 20}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/teammates"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_teammates", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetTeammate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEAMMATE)

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert result.result.data["teammate"]["id"] == "tea_123"
        assert result.result.data["teammate"]["email"] == "agent@example.com"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TEAMMATE)

        await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == "https://api2.frontapp.com/teammates/tea_123"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": "Teammate not found"})

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("get_teammate", {"teammate_id": "tea_123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Helper/Finder Actions ----


class TestFindTeammate:
    @pytest.mark.asyncio
    async def test_match_by_email(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "agent@example.com"}, mock_context)

        assert len(result.result.data["teammates"]) == 1
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "nonexistent"}, mock_context)

        assert result.result.data["teammates"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_partial_name_match(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": [SAMPLE_TEAMMATE]})

        result = await front.execute_action("find_teammate", {"search_query": "agent"}, mock_context)

        # Should match first_name "Agent"
        assert len(result.result.data["teammates"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("find_teammate", {"search_query": "john"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestFindInbox:
    @pytest.mark.asyncio
    async def test_match_by_name(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"_results": [{"id": "inb_1", "name": "Support Inbox", "address": "s@x.com"}]},
        )

        result = await front.execute_action("find_inbox", {"inbox_name": "support"}, mock_context)

        assert len(result.result.data["inboxes"]) == 1
        assert result.result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"_results": [{"id": "inb_1", "name": "Support Inbox", "address": "s@x.com"}]},
        )

        result = await front.execute_action("find_inbox", {"inbox_name": "sales"}, mock_context)

        assert result.result.data["inboxes"] == []
        assert result.result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("find_inbox", {"inbox_name": "support"}, mock_context)

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
