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

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)

discord = Integration.load()

DISCORD_API_BASE = "https://discord.com/api/v10"


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

    response = await context.fetch(
        f"{DISCORD_API_BASE}/channels/{channel_id}",
        headers=_bot_headers(),
    )
    if response.data.get("guild_id") != allowed_guild:
        return ActionError(message="Unauthorized: channel does not belong to the authorized guild.")
    return None


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

        limit = inputs.get("limit", 100)
        params = {"limit": limit}
        if inputs.get("before"):
            params["before"] = inputs.get("before")

        response = await context.fetch(
            f"{DISCORD_API_BASE}/channels/{inputs['channel']}/messages",
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

        body = {"content": inputs["text"]}
        if inputs.get("reference_message_id"):
            body["message_reference"] = {"message_id": inputs.get("reference_message_id")}

        response = await context.fetch(
            f"{DISCORD_API_BASE}/channels/{inputs['channel']}/messages",
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

        emoji = inputs["reaction"]
        if not emoji.isalnum():
            emoji = quote(emoji)

        await context.fetch(
            f"{DISCORD_API_BASE}/channels/{inputs['channel']}/messages/{inputs['message_id']}/reactions/{emoji}/@me",
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

        emoji = inputs["reaction"]
        if not emoji.isalnum():
            emoji = quote(emoji)

        await context.fetch(
            f"{DISCORD_API_BASE}/channels/{inputs['channel']}/messages/{inputs['message_id']}/reactions/{emoji}/@me",
            method="DELETE",
            headers=_bot_headers(),
        )
        return ActionResult(data={"success": True}, cost_usd=None)
