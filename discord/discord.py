"""Discord Integration Actions Module

SECURITY MODEL:
---------------
This integration uses Autohive's registered Discord bot credentials.
The bot token is NOT stored in this source code. It MUST be injected at
deployment time via the DISCORD_BOT_TOKEN environment variable.

The OAuth flow (platform auth) handles adding the bot to the user's server
and provides the guild_id via metadata. The bot token is a static credential
belonging to Autohive's Discord application and is read from the environment
at call time — never committed to source.
"""

from typing import Dict, Any
from urllib.parse import quote
import os
import re

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)

discord = Integration.load()

DISCORD_API_BASE = "https://discord.com/api/v10"

# Discord IDs are snowflakes: decimal integers, currently 17-19 digits, with
# room to grow. Anything else must never reach a URL path.
#
# This matters more here than in most integrations. Every request is made with
# Autohive's *shared* bot token, so the only thing keeping one connection inside
# its own server is _verify_channel_guild. That check validates `channel`, but a
# path segment placed after it can still rewrite the URL: the HTTP client
# resolves dot segments before sending, so a message_id of
#   ../../<other-channel>/messages/<id>
# turns
#   PUT /channels/<authorized>/messages/<crafted>/reactions/<e>/@me
# into
#   PUT /channels/<other-channel>/messages/<id>/reactions/<e>/@me
# reaching a channel in a different guild that the shared bot happens to see.
SNOWFLAKE_PATTERN = re.compile(r"^\d{17,20}$")


def _snowflake(value: Any, field: str) -> str:
    """Return value if it is a Discord snowflake ID, else raise ValueError.

    Use for every caller-supplied value interpolated into a URL path.
    """
    if not isinstance(value, str) or not SNOWFLAKE_PATTERN.match(value):
        raise ValueError(f"'{field}' must be a Discord ID (17-20 digits), got '{value}'.")
    return value


def _get_bot_token() -> str:
    """Read Discord bot token from environment at call time."""
    return os.environ.get("DISCORD_BOT_TOKEN", "")


def _bot_headers() -> Dict[str, str]:
    return {"Authorization": f"Bot {_get_bot_token()}"}


async def _verify_channel_guild(channel_id: str, context: ExecutionContext):
    """Reject any channel outside the guild this connection was authorized for.

    Fails closed: without a guild in the connection metadata there is nothing to
    authorize against, and because every action authenticates with Autohive's
    shared bot token, proceeding would let a workflow reach any channel that bot
    can see in any server.
    """
    allowed_guild = context.metadata.get("guild")
    if not allowed_guild:
        return ActionError(message="No guild ID found in metadata.")

    try:
        channel_id = _snowflake(channel_id, "channel")
    except ValueError as e:
        return ActionError(message=str(e))

    response = await context.fetch(
        f"{DISCORD_API_BASE}/channels/{channel_id}",
        headers=_bot_headers(),
    )
    if response.data.get("guild_id") != allowed_guild:
        return ActionError(message="Unauthorized: channel does not belong to the authorized guild.")
    return None


async def _resolve_reaction_emoji(reaction: str, context: ExecutionContext):
    """Return the reaction emoji encoded the way Discord's reaction routes expect.

    Discord requires the emoji path segment to be URL encoded, and a custom
    emoji to be given as ``name:id`` rather than a bare id, or the request fails
    with ``10014: Unknown Emoji``. Three input shapes are accepted:

    * A Unicode emoji, e.g. ``👍``.
    * A custom emoji already in ``name:id`` form, e.g. ``partyparrot:12345``.
    * A bare custom emoji id, e.g. ``12345``, which the schema documents. The
      name is looked up from the authorized guild's emoji list to build
      ``name:id``, since Discord will not accept the id on its own.

    Returns an ``(encoded_emoji, error)`` pair, where exactly one is set.
    """
    reaction = reaction.strip()
    if not reaction:
        return None, ActionError(message="A reaction emoji is required.")

    # Already name:id, so only encoding is needed.
    if ":" in reaction:
        return quote(reaction, safe=""), None

    # A bare snowflake is a custom emoji id. Resolve its name to build name:id.
    if reaction.isdigit():
        guild_id = context.metadata.get("guild")
        response = await context.fetch(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/emojis",
            headers=_bot_headers(),
        )
        for emoji in response.data or []:
            if emoji.get("id") == reaction:
                return quote(f"{emoji.get('name')}:{reaction}", safe=""), None
        return None, ActionError(
            message=(
                f"Custom emoji {reaction} was not found in this server. Provide a Unicode emoji, "
                "or a custom emoji as name:id."
            )
        )

    return quote(reaction, safe=""), None


@discord.action("list_channels")
class ListChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        guild_id = context.metadata.get("guild")
        if not guild_id:
            return ActionError(message="No guild ID found in metadata.")

        response = await context.fetch(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/channels",
            headers=_bot_headers(),
        )
        return ActionResult(data={"channels": response.data}, cost_usd=None)


@discord.action("get_message_history")
class GetMessageHistoryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        err = await _verify_channel_guild(inputs["channel"], context)
        if err:
            return err

        try:
            channel = _snowflake(inputs["channel"], "channel")
        except ValueError as e:
            return ActionError(message=str(e))

        limit = inputs.get("limit", 100)
        params = {"limit": limit}
        if inputs.get("before"):
            params["before"] = inputs.get("before")

        response = await context.fetch(
            f"{DISCORD_API_BASE}/channels/{channel}/messages",
            params=params,
            headers=_bot_headers(),
        )
        messages = response.data
        return ActionResult(data={"messages": messages, "has_more": len(messages) == limit}, cost_usd=None)


@discord.action("send_message")
class SendMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        err = await _verify_channel_guild(inputs["channel"], context)
        if err:
            return err

        try:
            channel = _snowflake(inputs["channel"], "channel")
        except ValueError as e:
            return ActionError(message=str(e))

        body = {"content": inputs["text"]}
        if inputs.get("reference_message_id"):
            body["message_reference"] = {"message_id": inputs.get("reference_message_id")}

        response = await context.fetch(
            f"{DISCORD_API_BASE}/channels/{channel}/messages",
            method="POST",
            json=body,
            headers=_bot_headers(),
        )
        return ActionResult(data={"id": response.data["id"], "channel_id": response.data["channel_id"]}, cost_usd=None)


@discord.action("add_reaction")
class AddReactionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        err = await _verify_channel_guild(inputs["channel"], context)
        if err:
            return err

        try:
            channel = _snowflake(inputs["channel"], "channel")
            message_id = _snowflake(inputs["message_id"], "message_id")
        except ValueError as e:
            return ActionError(message=str(e))

        emoji, err = await _resolve_reaction_emoji(inputs["reaction"], context)
        if err:
            return err

        await context.fetch(
            f"{DISCORD_API_BASE}/channels/{channel}/messages/{message_id}/reactions/{emoji}/@me",
            method="PUT",
            headers=_bot_headers(),
        )
        return ActionResult(data={"success": True}, cost_usd=None)


@discord.action("remove_reaction")
class RemoveReactionAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        err = await _verify_channel_guild(inputs["channel"], context)
        if err:
            return err

        try:
            channel = _snowflake(inputs["channel"], "channel")
            message_id = _snowflake(inputs["message_id"], "message_id")
        except ValueError as e:
            return ActionError(message=str(e))

        emoji, err = await _resolve_reaction_emoji(inputs["reaction"], context)
        if err:
            return err

        await context.fetch(
            f"{DISCORD_API_BASE}/channels/{channel}/messages/{message_id}/reactions/{emoji}/@me",
            method="DELETE",
            headers=_bot_headers(),
        )
        return ActionResult(data={"success": True}, cost_usd=None)
