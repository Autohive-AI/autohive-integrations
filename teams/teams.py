from typing import Any, Dict

from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult

teams = Integration.load()

BASE_URL = "https://graph.microsoft.com/v1.0"


def _headers(context: ExecutionContext) -> Dict[str, str]:
    token = context.auth.get("credentials", {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _parse_message(msg: Dict) -> Dict:
    sender = msg.get("from") or {}
    user = sender.get("user") or {}
    return {
        "id": msg.get("id", ""),
        "body": (msg.get("body") or {}).get("content", ""),
        "from": user.get("displayName", ""),
        "created_at": msg.get("createdDateTime", ""),
    }


@teams.action("list_teams")
class ListTeamsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(
                f"{BASE_URL}/me/joinedTeams",
                method="GET",
                headers=_headers(context),
            )
            items = response.get("value", [])
            return ActionResult(
                data={
                    "result": True,
                    "teams": [
                        {
                            "id": t.get("id", ""),
                            "display_name": t.get("displayName", ""),
                            "description": t.get("description", ""),
                        }
                        for t in items
                    ],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("get_team")
class GetTeamAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(
                data={
                    "result": True,
                    "team": {
                        "id": response.get("id", ""),
                        "display_name": response.get("displayName", ""),
                        "description": response.get("description", ""),
                        "web_url": response.get("webUrl", ""),
                    },
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("list_channels")
class ListChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels",
                method="GET",
                headers=_headers(context),
            )
            items = response.get("value", [])
            return ActionResult(
                data={
                    "result": True,
                    "channels": [
                        {
                            "id": c.get("id", ""),
                            "display_name": c.get("displayName", ""),
                            "description": c.get("description", ""),
                            "membership_type": c.get("membershipType", "standard"),
                        }
                        for c in items
                    ],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("get_channel")
class GetChannelAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            channel_id = inputs.get("channel_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels/{channel_id}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(
                data={
                    "result": True,
                    "channel": {
                        "id": response.get("id", ""),
                        "display_name": response.get("displayName", ""),
                        "description": response.get("description", ""),
                        "membership_type": response.get("membershipType", "standard"),
                        "web_url": response.get("webUrl", ""),
                    },
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("create_channel")
class CreateChannelAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            body: Dict[str, Any] = {
                "displayName": inputs.get("display_name", ""),
                "membershipType": inputs.get("membership_type", "standard"),
            }
            if inputs.get("description"):
                body["description"] = inputs["description"]

            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels",
                method="POST",
                headers=_headers(context),
                body=body,
            )
            return ActionResult(
                data={
                    "result": True,
                    "channel": {
                        "id": response.get("id", ""),
                        "display_name": response.get("displayName", ""),
                    },
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("list_messages")
class ListMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            channel_id = inputs.get("channel_id", "")
            limit = min(int(inputs.get("limit", 20)), 50)
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels/{channel_id}/messages",
                method="GET",
                headers=_headers(context),
                params={"$top": limit},
            )
            items = response.get("value", [])
            return ActionResult(
                data={"result": True, "messages": [_parse_message(m) for m in items]},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("get_message")
class GetMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            channel_id = inputs.get("channel_id", "")
            message_id = inputs.get("message_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels/{channel_id}/messages/{message_id}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(
                data={"result": True, "message": _parse_message(response)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("send_channel_message")
class SendChannelMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            channel_id = inputs.get("channel_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/channels/{channel_id}/messages",
                method="POST",
                headers=_headers(context),
                body={"body": {"content": inputs.get("message", "")}},
            )
            return ActionResult(
                data={"result": True, "message_id": response.get("id", "")},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("list_members")
class ListMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/members",
                method="GET",
                headers=_headers(context),
            )
            items = response.get("value", [])
            return ActionResult(
                data={
                    "result": True,
                    "members": [
                        {
                            "id": m.get("id", ""),
                            "user_id": m.get("userId", ""),
                            "display_name": m.get("displayName", ""),
                            "email": m.get("email", ""),
                            "roles": m.get("roles", []),
                        }
                        for m in items
                    ],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("add_member")
class AddMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            user_id = inputs.get("user_id", "")
            role = inputs.get("role", "member")
            roles = ["owner"] if role == "owner" else []

            body: Dict[str, Any] = {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": roles,
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users/{user_id}",
            }
            response = await context.fetch(
                f"{BASE_URL}/teams/{team_id}/members",
                method="POST",
                headers=_headers(context),
                body=body,
            )
            return ActionResult(
                data={"result": True, "membership_id": response.get("id", "")},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("remove_member")
class RemoveMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            team_id = inputs.get("team_id", "")
            membership_id = inputs.get("membership_id", "")
            await context.fetch(
                f"{BASE_URL}/teams/{team_id}/members/{membership_id}",
                method="DELETE",
                headers=_headers(context),
            )
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("list_chats")
class ListChatsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(
                f"{BASE_URL}/me/chats",
                method="GET",
                headers=_headers(context),
            )
            items = response.get("value", [])
            return ActionResult(
                data={
                    "result": True,
                    "chats": [
                        {
                            "id": c.get("id", ""),
                            "topic": c.get("topic", ""),
                            "chat_type": c.get("chatType", ""),
                        }
                        for c in items
                    ],
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("list_chat_messages")
class ListChatMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            chat_id = inputs.get("chat_id", "")
            limit = min(int(inputs.get("limit", 20)), 50)
            response = await context.fetch(
                f"{BASE_URL}/chats/{chat_id}/messages",
                method="GET",
                headers=_headers(context),
                params={"$top": limit},
            )
            items = response.get("value", [])
            return ActionResult(
                data={"result": True, "messages": [_parse_message(m) for m in items]},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@teams.action("send_chat_message")
class SendChatMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            chat_id = inputs.get("chat_id", "")
            response = await context.fetch(
                f"{BASE_URL}/chats/{chat_id}/messages",
                method="POST",
                headers=_headers(context),
                body={"body": {"content": inputs.get("message", "")}},
            )
            return ActionResult(
                data={"result": True, "message_id": response.get("id", "")},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
