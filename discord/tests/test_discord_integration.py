"""
End-to-end integration tests for the Discord integration.

These tests call the real Discord REST API v10. The integration authenticates
with Autohive's bot token, which it reads from DISCORD_BOT_TOKEN itself, so the
live context here only needs to perform real HTTP and supply the connection
metadata the platform would normally provide.

Required environment (via .env or export):
    DISCORD_BOT_TOKEN    bot token for a Discord application
    DISCORD_GUILD_ID     server the bot has been installed into
    DISCORD_CHANNEL_ID   text channel in that server the bot can read

The bot needs View Channels and Read Message History for the read-only tests,
plus Send Messages and Add Reactions for the destructive ones.

Run the safe, read-only tests with:
    pytest discord/tests/test_discord_integration.py -m "integration and not destructive"

The destructive tests post real messages and reactions to DISCORD_CHANNEL_ID.
Run them deliberately, never as part of a review pass:
    pytest discord/tests/test_discord_integration.py -m "integration and destructive"

Never runs in CI: the default marker filter (-m unit) excludes these, and
python_files does not match test_*_integration.py.
"""

import json as _json
import os

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, ResultType

from discord.discord import discord

pytestmark = pytest.mark.integration

GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")


def require_channel_id():
    if not CHANNEL_ID:
        pytest.skip("DISCORD_CHANNEL_ID not set")


@pytest.fixture
def live_context(env_credentials):
    """Real HTTP against Discord, with the guild the platform would inject.

    The integration builds its own Authorization header from DISCORD_BOT_TOKEN,
    so this fixture deliberately does not inject credentials. It only checks the
    token is present so the tests skip rather than fail with 401s.
    """
    if not env_credentials("DISCORD_BOT_TOKEN"):
        pytest.skip("DISCORD_BOT_TOKEN not set — skipping integration tests")
    if not GUILD_ID:
        pytest.skip("DISCORD_GUILD_ID not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        # aiohttp rejects non-string query values, and the integration passes
        # limit as a number.
        query = {k: str(v) for k, v in (params or {}).items()}
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=query) as resp:
                body = await resp.text()
                # Reaction endpoints answer 204 with an empty body.
                data = _json.loads(body) if body else None
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {}
    ctx.metadata = {"guild": GUILD_ID}
    return ctx


# ---- Read-Only Tests ----


class TestListChannels:
    async def test_returns_channels(self, live_context):
        result = await discord.execute_action("list_channels", {}, live_context)

        assert result.type == ResultType.ACTION
        channels = result.result.data["channels"]
        assert isinstance(channels, list)
        assert len(channels) > 0, "the connected guild should expose at least one channel"

    async def test_channels_have_expected_structure(self, live_context):
        result = await discord.execute_action("list_channels", {}, live_context)

        channel = result.result.data["channels"][0]
        for key in ("id", "name", "type", "position", "guild_id"):
            assert key in channel, f"channel payload missing {key}"

    async def test_channels_belong_to_authorized_guild(self, live_context):
        result = await discord.execute_action("list_channels", {}, live_context)

        guild_ids = {c["guild_id"] for c in result.result.data["channels"]}
        assert guild_ids == {GUILD_ID}

    async def test_missing_guild_returns_error(self, live_context):
        live_context.metadata = {}

        result = await discord.execute_action("list_channels", {}, live_context)

        assert result.type == ResultType.ACTION_ERROR
        live_context.fetch.assert_not_called()


class TestGetMessageHistory:
    async def test_returns_messages(self, live_context):
        require_channel_id()

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 5}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert isinstance(data["messages"], list)
        assert isinstance(data["has_more"], bool)

    async def test_messages_have_expected_structure(self, live_context):
        require_channel_id()

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 5}, live_context)

        messages = result.result.data["messages"]
        if not messages:
            pytest.skip("no messages in DISCORD_CHANNEL_ID to inspect")

        message = messages[0]
        for key in ("id", "channel_id", "content", "author", "timestamp"):
            assert key in message, f"message payload missing {key}"
        assert message["channel_id"] == CHANNEL_ID

    async def test_limit_is_respected(self, live_context):
        require_channel_id()

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 2}, live_context)

        assert len(result.result.data["messages"]) <= 2

    async def test_before_pages_backwards(self, live_context):
        require_channel_id()

        first = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID, "limit": 1}, live_context)
        newest = first.result.data["messages"]
        if not newest:
            pytest.skip("no messages in DISCORD_CHANNEL_ID to page from")

        cursor = newest[0]["id"]
        older = await discord.execute_action(
            "get_message_history", {"channel": CHANNEL_ID, "limit": 1, "before": cursor}, live_context
        )

        assert older.type == ResultType.ACTION
        returned = {m["id"] for m in older.result.data["messages"]}
        assert cursor not in returned, "before cursor should be excluded from the page"

    async def test_channel_outside_authorized_guild_returns_error(self, live_context):
        """The guild check should reject a channel that is not in the connected server."""
        require_channel_id()
        live_context.metadata = {"guild": "000000000000000000"}

        result = await discord.execute_action("get_message_history", {"channel": CHANNEL_ID}, live_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Destructive Tests (Write Operations) ----
# These post real messages and reactions to DISCORD_CHANNEL_ID.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestSendMessage:
    async def test_sends_message(self, live_context):
        require_channel_id()

        result = await discord.execute_action(
            "send_message",
            {"channel": CHANNEL_ID, "text": f"Autohive integration test {os.getpid()}"},
            live_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["id"]
        assert data["channel_id"] == CHANNEL_ID

    async def test_sends_threaded_reply(self, live_context):
        require_channel_id()

        parent = await discord.execute_action(
            "send_message",
            {"channel": CHANNEL_ID, "text": f"Autohive reply parent {os.getpid()}"},
            live_context,
        )
        parent_id = parent.result.data["id"]

        reply = await discord.execute_action(
            "send_message",
            {
                "channel": CHANNEL_ID,
                "text": f"Autohive threaded reply {os.getpid()}",
                "reference_message_id": parent_id,
            },
            live_context,
        )

        assert reply.type == ResultType.ACTION
        assert reply.result.data["id"] != parent_id


@pytest.mark.destructive
class TestReactionLifecycle:
    """End-to-end workflow: post a message, react to it, then remove the reaction."""

    async def test_add_then_remove_reaction(self, live_context):
        require_channel_id()

        posted = await discord.execute_action(
            "send_message",
            {"channel": CHANNEL_ID, "text": f"Autohive reaction target {os.getpid()}"},
            live_context,
        )
        message_id = posted.result.data["id"]

        added = await discord.execute_action(
            "add_reaction",
            {"channel": CHANNEL_ID, "message_id": message_id, "reaction": "👍"},
            live_context,
        )
        assert added.type == ResultType.ACTION
        assert added.result.data["success"] is True

        removed = await discord.execute_action(
            "remove_reaction",
            {"channel": CHANNEL_ID, "message_id": message_id, "reaction": "👍"},
            live_context,
        )
        assert removed.type == ResultType.ACTION
        assert removed.result.data["success"] is True
