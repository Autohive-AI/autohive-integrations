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


class TestGuildAuthorizationFailsClosed:
    """Without a guild in metadata there is nothing to authorize against.

    Every action authenticates with Autohive's shared bot token, so proceeding
    would let a workflow reach any channel that bot can see in any server.
    """

    @pytest.mark.parametrize(
        "action,inputs",
        [
            ("get_message_history", {"channel": CHANNEL_ID}),
            ("send_message", {"channel": CHANNEL_ID, "text": "hello"}),
            ("add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "👍"}),
            ("remove_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "👍"}),
        ],
    )
    @pytest.mark.asyncio
    async def test_missing_guild_returns_error(self, mock_context, action, inputs):
        mock_context.metadata = {}

        result = await discord.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.parametrize("empty", [None, ""])
    @pytest.mark.asyncio
    async def test_empty_guild_returns_error(self, mock_context, empty):
        mock_context.metadata = {"guild": empty}

        result = await discord.execute_action("send_message", {"channel": CHANNEL_ID, "text": "hi"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()


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
    async def test_unicode_emoji_is_encoded(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "👍"}, mock_context
        )

        url = mock_context.fetch.call_args_list[1].args[0]
        assert "%F0%9F%91%8D" in url
        assert "👍" not in url


class TestReactionEmojiFormats:
    """Discord needs the emoji path segment URL encoded, and custom emoji as name:id.

    A bare id fails with 10014: Unknown Emoji, so the id is resolved to name:id
    against the authorized guild's emoji list.
    """

    @pytest.mark.asyncio
    async def test_name_id_pair_is_encoded_without_lookup(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await discord.execute_action(
            "add_reaction",
            {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "partyparrot:555"},
            mock_context,
        )

        url = mock_context.fetch.call_args_list[1].args[0]
        assert "partyparrot%3A555" in url
        # Channel verification plus the reaction call, so no emoji lookup.
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_bare_custom_emoji_id_is_resolved_to_name_id(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data=[{"id": "555", "name": "partyparrot"}]),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "555"}, mock_context
        )

        assert result.type == ResultType.ACTION
        lookup_url = mock_context.fetch.call_args_list[1].args[0]
        assert lookup_url.endswith(f"/guilds/{GUILD_ID}/emojis")
        assert "partyparrot%3A555" in mock_context.fetch.call_args_list[2].args[0]

    @pytest.mark.asyncio
    async def test_unknown_custom_emoji_id_returns_error(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data=[{"id": "999", "name": "other"}]),
        ]

        result = await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "555"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_blank_reaction_returns_error(self, mock_context):
        mock_context.fetch.return_value = _channel_response()

        result = await discord.execute_action(
            "add_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "   "}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_remove_reaction_resolves_bare_id(self, mock_context):
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=200, headers={}, data=[{"id": "555", "name": "partyparrot"}]),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await discord.execute_action(
            "remove_reaction", {"channel": CHANNEL_ID, "message_id": MESSAGE_ID, "reaction": "555"}, mock_context
        )

        assert result.type == ResultType.ACTION
        call = mock_context.fetch.call_args_list[2]
        assert "partyparrot%3A555" in call.args[0]
        assert call.kwargs.get("method") == "DELETE"


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


# =============================================================================
# PATH SAFETY
#
# Every request uses Autohive's shared bot token, so _verify_channel_guild is
# the only thing keeping a connection inside its own server. A caller-supplied
# value that reaches a URL path can move the request to a different channel
# after that check has already passed, which would cross the guild boundary
# into another customer's server.
# =============================================================================

OTHER_CHANNEL = "999999999999999999"
TRAVERSAL_MESSAGE_ID = f"../../{OTHER_CHANNEL}/messages/888888888888888888"


class TestPathSafety:
    def test_url_library_really_does_rewrite_the_path(self):
        """The risk, pinned. Without this the validation looks like paranoia."""
        from yarl import URL

        crafted = URL(
            f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages/{TRAVERSAL_MESSAGE_ID}/reactions/X/@me"
        )
        assert crafted.path == f"/api/v10/channels/{OTHER_CHANNEL}/messages/888888888888888888/reactions/X/@me"
        assert CHANNEL_ID not in crafted.path

    def test_snowflake_accepts_real_ids(self):
        from discord.discord import _snowflake

        for value in (GUILD_ID, CHANNEL_ID, MESSAGE_ID, "1" * 20):
            assert _snowflake(value, "channel") == value

    @pytest.mark.parametrize(
        "value",
        [
            TRAVERSAL_MESSAGE_ID,
            "../../../guilds/111111111111111111/members/222222222222222222",
            "",
            "   ",
            "not-an-id",
            "1234",  # too short to be a snowflake
            "1" * 21,  # too long
            "123456789012345678/../999",
            None,
            12345678901234567,  # int, not str
        ],
    )
    def test_snowflake_rejects_everything_else(self, value):
        from discord.discord import _snowflake

        with pytest.raises(ValueError, match="must be a Discord ID"):
            _snowflake(value, "message_id")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["add_reaction", "remove_reaction"])
    async def test_reaction_refuses_a_traversal_message_id(self, action, mock_context):
        """The guild check passes for the channel, then the path is rewritten."""
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        result = await discord.execute_action(
            action,
            {"channel": CHANNEL_ID, "message_id": TRAVERSAL_MESSAGE_ID, "reaction": "👍"},
            mock_context,
        )

        assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
        sent = [str(c.args[0]) if c.args else "" for c in mock_context.fetch.call_args_list]
        assert not any(OTHER_CHANNEL in url for url in sent), f"request escaped the guild: {sent}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action,inputs",
        [
            ("get_message_history", {"channel": "../guilds/999999999999999999"}),
            ("send_message", {"channel": "../guilds/999999999999999999", "text": "hi"}),
            ("add_reaction", {"channel": "../x", "message_id": MESSAGE_ID, "reaction": "👍"}),
        ],
    )
    async def test_actions_refuse_a_traversal_channel(self, action, inputs, mock_context):
        mock_context.fetch.side_effect = [_channel_response(), FetchResponse(status=200, headers={}, data={})]

        result = await discord.execute_action(action, inputs, mock_context)

        assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)

    @pytest.mark.asyncio
    async def test_reaction_emoji_cannot_escape_its_segment(self, mock_context):
        """quote() keeps '/' unescaped by default, so safe='' is required."""
        mock_context.fetch.side_effect = [
            _channel_response(),
            FetchResponse(status=204, headers={}, data=None),
        ]

        await discord.execute_action(
            "add_reaction",
            {
                "channel": CHANNEL_ID,
                "message_id": MESSAGE_ID,
                "reaction": f"../../{OTHER_CHANNEL}/messages/777777777777777777",
            },
            mock_context,
        )

        sent = [str(c.args[0]) if c.args else "" for c in mock_context.fetch.call_args_list]
        assert not any(OTHER_CHANNEL in url and "%2F" not in url for url in sent), f"emoji segment escaped: {sent}"
