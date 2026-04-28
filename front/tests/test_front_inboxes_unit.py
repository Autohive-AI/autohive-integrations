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

pytestmark = pytest.mark.unit

# ---- Sample Data ----

SAMPLE_INBOX = {
    "id": "inb_123",
    "name": "Support",
    "address": "support@example.com",
    "type": "smtp",
    "is_private": False,
}

SAMPLE_CHANNEL = {
    "id": "cha_123",
    "name": "Support Email",
    "type": "smtp",
    "address": "support@example.com",
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


# ---- Inboxes ----


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
    async def test_limit_param_sent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        await front.execute_action("list_inboxes", {"limit": 10}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["limit"] == 10

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        result = await front.execute_action("list_inboxes", {}, mock_context)

        assert result.result.data["inboxes"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await front.execute_action("list_inboxes", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


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
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"_results": []})

        result = await front.execute_action("list_inbox_channels", {"inbox_id": "inb_123"}, mock_context)

        assert result.result.data["channels"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("list_inbox_channels", {"inbox_id": "inb_123"}, mock_context)

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
    async def test_case_insensitive_match(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"_results": [{"id": "inb_1", "name": "SUPPORT", "address": "s@x.com"}]},
        )

        result = await front.execute_action("find_inbox", {"inbox_name": "support"}, mock_context)

        assert len(result.result.data["inboxes"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Error")

        result = await front.execute_action("find_inbox", {"inbox_name": "support"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
