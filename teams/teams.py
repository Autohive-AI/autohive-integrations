from typing import Dict, Any, Optional
import os

import requests
from botbuilder.schema import Activity
from botframework.connector import ConnectorClient
from botframework.connector.auth import MicrosoftAppCredentials
from botframework.connector.teams import TeamsConnectorClient

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)


def _get_credentials() -> Dict[str, str]:
    """Read Teams bot credentials from environment variables at call time.

    Accepts the TEAMS_BOT_APP_ID/TEAMS_BOT_APP_PASSWORD names, falling back to
    the MicrosoftAppId/MicrosoftAppPassword names provisioned via AWS SSM.
    """
    app_id = os.environ.get("TEAMS_BOT_APP_ID") or os.environ.get("MicrosoftAppId")
    app_password = os.environ.get("TEAMS_BOT_APP_PASSWORD") or os.environ.get("MicrosoftAppPassword")
    if not app_id or not app_password:
        raise EnvironmentError(
            "Teams bot credentials are not configured: set TEAMS_BOT_APP_ID/TEAMS_BOT_APP_PASSWORD "
            "(or MicrosoftAppId/MicrosoftAppPassword) in the environment"
        )
    return {"app_id": app_id, "app_password": app_password}


teams = Integration.load()

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def get_graph_token(tenant_id: str) -> str:
    creds = _get_credentials()
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": creds["app_id"],
            "client_secret": creds["app_password"],
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def graph_get(tenant_id: str, path: str, params: Optional[Dict] = None) -> Dict:
    token = get_graph_token(tenant_id)
    resp = requests.get(
        f"{GRAPH_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def graph_post(tenant_id: str, path: str, body: Dict) -> Dict:
    token = get_graph_token(tenant_id)
    resp = requests.post(
        f"{GRAPH_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def create_connector_client(service_url: str) -> ConnectorClient:
    creds = _get_credentials()
    credentials = MicrosoftAppCredentials(app_id=creds["app_id"], password=creds["app_password"])
    return ConnectorClient(credentials, base_url=service_url)


def create_teams_connector_client(service_url: str) -> TeamsConnectorClient:
    creds = _get_credentials()
    credentials = MicrosoftAppCredentials(app_id=creds["app_id"], password=creds["app_password"])
    return TeamsConnectorClient(credentials, base_url=service_url)


# ---- Action Handlers ----
@teams.action("list_channels")
class ListChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        team_id = credentials.get("TeamId")
        service_url = credentials.get("ServiceUrl")

        if not team_id or not service_url:
            raise ValueError("TeamId and ServiceUrl must be present in credentials")

        teams_client = create_teams_connector_client(service_url)
        channels_result = teams_client.teams.get_teams_channels(team_id)

        channels = [{"id": channel.id, "name": channel.name or "general"} for channel in channels_result.conversations]

        return ActionResult(data={"channels": channels}, cost_usd=0.0)


@teams.action("search_channels")
class SearchChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        team_id = credentials.get("TeamId")
        service_url = credentials.get("ServiceUrl")
        query = inputs["query"]

        if not team_id or not service_url:
            raise ValueError("TeamId and ServiceUrl must be present in credentials")

        teams_client = create_teams_connector_client(service_url)
        channels_result = teams_client.teams.get_teams_channels(team_id)

        channels = []
        for channel in channels_result.conversations:
            channel_name = channel.name or "general"
            if query.lower() in channel_name.lower():
                channels.append({"id": channel.id, "name": channel_name})

        return ActionResult(data={"channels": channels, "has_more": False}, cost_usd=0.0)


@teams.action("get_channel_by_name")
class GetChannelByNameAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        team_id = credentials.get("TeamId")
        service_url = credentials.get("ServiceUrl")
        channel_name = inputs["channel_name"]

        if not team_id or not service_url:
            raise ValueError("TeamId and ServiceUrl must be present in credentials")

        teams_client = create_teams_connector_client(service_url)
        channels_result = teams_client.teams.get_teams_channels(team_id)

        for channel in channels_result.conversations:
            current_name = channel.name or "general"
            if current_name.lower() == channel_name.lower():
                return ActionResult(
                    data={
                        "found": True,
                        "channel": {"id": channel.id, "name": current_name},
                    },
                    cost_usd=0.0,
                )

        return ActionResult(data={"found": False, "channel": None}, cost_usd=0.0)


@teams.action("send_message")
class SendMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        channel_id = inputs["channel_id"]
        message = inputs["message"]

        agent_name = context.metadata.get("agent_name", "Unknown Agent")
        message_with_attribution = f"{message}\n\n\nSent from {agent_name} agent"

        credentials = context.auth.get("credentials", {})
        service_url = credentials.get("ServiceUrl", "")

        connector_client = create_connector_client(service_url)

        activity = Activity(
            type="message",
            text=message_with_attribution,
            channel_id=channel_id,
        )

        connector_client.conversations.send_to_conversation(channel_id, activity)

        return ActionResult(data={"success": True, "message": "Message sent successfully"}, cost_usd=0.0)


@teams.action("get_channel_messages")
class GetChannelMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        group_id = credentials.get("GroupId")
        tenant_id = credentials.get("TenantId")
        channel_id = inputs["channel_id"]
        limit = inputs.get("limit", 20)

        if not group_id or not tenant_id:
            raise ValueError("GroupId and TenantId must be present in credentials")

        result = graph_get(
            tenant_id,
            f"/teams/{group_id}/channels/{channel_id}/messages",
            params={"$top": min(limit, 50)},
        )

        messages = []
        for msg in result.get("value", []):
            body = msg.get("body", {})
            from_info = msg.get("from", {}) or {}
            user_info = from_info.get("user", {}) or {}
            messages.append(
                {
                    "id": msg.get("id"),
                    "created_at": msg.get("createdDateTime"),
                    "from": user_info.get("displayName", "Unknown"),
                    "text": body.get("content", ""),
                    "has_replies": bool(msg.get("replies")),
                }
            )

        return ActionResult(data={"messages": messages}, cost_usd=0.0)


@teams.action("get_message_replies")
class GetMessageRepliesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        group_id = credentials.get("GroupId")
        tenant_id = credentials.get("TenantId")
        channel_id = inputs["channel_id"]
        message_id = inputs["message_id"]

        if not group_id or not tenant_id:
            raise ValueError("GroupId and TenantId must be present in credentials")

        result = graph_get(
            tenant_id,
            f"/teams/{group_id}/channels/{channel_id}/messages/{message_id}/replies",
        )

        replies = []
        for msg in result.get("value", []):
            body = msg.get("body", {})
            from_info = msg.get("from", {}) or {}
            user_info = from_info.get("user", {}) or {}
            replies.append(
                {
                    "id": msg.get("id"),
                    "created_at": msg.get("createdDateTime"),
                    "from": user_info.get("displayName", "Unknown"),
                    "text": body.get("content", ""),
                }
            )

        return ActionResult(data={"replies": replies, "count": len(replies)}, cost_usd=0.0)


@teams.action("reply_to_message")
class ReplyToMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        credentials = context.auth.get("credentials", {})
        service_url = credentials.get("ServiceUrl", "")
        channel_id = inputs["channel_id"]
        message_id = inputs["message_id"]
        reply = inputs["reply"]

        agent_name = context.metadata.get("agent_name", "Unknown Agent")
        reply_with_attribution = f"{reply}\n\n\nSent from {agent_name} agent"

        connector_client = create_connector_client(service_url)

        # Teams requires the conversation ID to include the message ID to post
        # into the correct thread rather than sending a new top-level message.
        thread_conversation_id = f"{channel_id};messageid={message_id}"

        activity = Activity(
            type="message",
            text=reply_with_attribution,
        )

        connector_client.conversations.send_to_conversation(thread_conversation_id, activity)

        return ActionResult(data={"success": True}, cost_usd=0.0)
