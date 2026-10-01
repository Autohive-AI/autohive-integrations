import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402
from discord.discord import discord  # noqa: E402

pytestmark = pytest.mark.unit

GUILD_ID = "111111111111111111"
CHANNEL_ID = "222222222222222222"
MESSAGE_ID = "333333333333333333"

SAMPLE_CHANNEL = {
    "id": CHANNEL_ID,
    "name": "general",
    "type": 0,
    "position": 0,
    "guild_id": GUILD_ID,
    "flags": 0,
}

SAMPLE_MESSAGE = {
    "id": MESSAGE_ID,
    "channel_id": CHANNEL_ID,
    "content": "hello",
    "author": {"id": "444", "username": "testuser"},
    "timestamp": "2024-01-01T00:00:00.000000+00:00",
}


@pytest.fixture(autouse=True)
def mock_bot_token():
    with patch("discord.discord._get_bot_token", return_value="test_bot_token"):  # nosec B105
        yield


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    ctx.metadata = {"guild": GUILD_ID}
    return ctx


def _channel_response(channel_id=CHANNEL_ID, guild_id=GUILD_ID):
    return FetchResponse(status=200, headers={}, data={"id": channel_id, "guild_id": guild_id})


class TestListChannels:
    @pytest.mark.asyncio
    async def test_returns_channels(self, mock_context):
        channels = [SAMPLE_CHANNEL]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=channels)

        result = await discord.execute_action("list_channels", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["channels"] == channels
        mock_context.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_guild_returns_error(self, mock_context):
        mock_context.metadata = {}

        result = await discord.execute_action("list_channels", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


class TestGetMessageHistory:
    @pytest.mark.asyncio
    async def test_returns_messages(self, mock_context):
        messages = [SAMPLE_MESSAGE]
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data=messages),
        ]

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 10}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["messages"] == messages
        assert result.result.data["has_more"] is False

    @pytest.mark.asyncio
    async def test_has_more_when_full_page(self, mock_context):
        messages = [SAMPLE_MESSAGE] * 10
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data=messages),
        ]

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 10}, mock_context)

        assert result.result.data["has_more"] is True

    @pytest.mark.asyncio
    async def test_unauthorized_channel_returns_error(self, mock_context):
        mock_context.fetch.return_value = _channel_response(guild_id="wrong_guild")

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_sends_message(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data={"id": MESSAGE_ID, "channel_id": CHANNEL_ID}),
        ]

        result = await discord.execute_action("send_message", {"channel": CHANNEL_ID, "text": "hello"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == MESSAGE_ID
        assert result.result.data["channel_id"] == CHANNEL_ID

    @pytest.mark.asyncio
    async def test_send_reply_includes_reference(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data={"id": MESSAGE_ID, "channel_id": CHANNEL_ID}),
        ]

        await discord.execute_action(
            "send_message",
            {"channel": CHANNEL_ID, "text": "reply", "reference_message_id": "999"},
            mock_context,
        )

        call_kwargs = mock_context.fetch.call_args_list[1]
        assert call_kwargs.kwargs["json"]["message_reference"] == {"message_id": "999"}


class TestAddReaction:
    @pytest.mark.asyncio
    async def test_adds_reaction(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "👍"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_alphanumeric_emoji_not_encoded(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "thumbsup"}, mock_context
        )

        url = mock_context.fetch.call_args_list[1].args[0]
        assert "thumbsup" in url


class TestRemoveReaction:
    @pytest.mark.asyncio
    async def test_removes_reaction(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await discord.execute_action(
            "remove_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "👍"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["success"] is True

        call = mock_context.fetch.call_args_list[1]
        assert call.kwargs.get("method") == "DELETE"
