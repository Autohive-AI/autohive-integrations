from typing import Any, Dict

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext, Integration

missive = Integration.load()

BASE_URL = "https://public.missiveapp.com/v1"


def _get_headers(context: ExecutionContext) -> Dict[str, str]:
    creds = context.auth.get("credentials", context.auth)
    api_token = creds.get("api_token", "")
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


def _first(data: Any, key: str) -> Any:
    items = data.get(key)
    if isinstance(items, list):
        return items[0] if items else {}
    if isinstance(items, dict):
        return items
    return data


_TEAM_MAILBOXES = {"team_inbox", "team_closed", "team_all"}


@missive.action("list_conversations")
class ListConversationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            mailbox = inputs["mailbox"]
            if mailbox in _TEAM_MAILBOXES:
                params: Dict[str, Any] = {mailbox: inputs.get("team_id", "")}
            elif mailbox == "shared_label":
                params = {mailbox: inputs.get("shared_label_id", "")}
            else:
                params = {mailbox: "true"}
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]
            if inputs.get("until"):
                params["until"] = inputs["until"]

            response = await context.fetch(
                f"{BASE_URL}/conversations",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            conversations = response.data.get("conversations", [])
            return ActionResult(data={"conversations": conversations, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"conversations": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("get_conversation")
class GetConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}",
                method="GET",
                headers=_get_headers(context),
            )
            conversation = _first(response.data, "conversations")
            return ActionResult(data={"conversation": conversation, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"conversation": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("update_conversation")
class UpdateConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            body: Dict[str, Any] = {}
            if inputs.get("subject") is not None:
                body["subject"] = inputs["subject"]
            if inputs.get("color") is not None:
                body["color"] = inputs["color"]
            if inputs.get("assignee_id") is not None:
                body["assignee_id"] = inputs["assignee_id"]
            if inputs.get("team_id") is not None:
                body["team_id"] = inputs["team_id"]
            if inputs.get("shared_label_ids") is not None:
                body["shared_label_ids"] = inputs["shared_label_ids"]
            if inputs.get("closed") is not None:
                body["closed"] = inputs["closed"]
            if inputs.get("snoozed_until") is not None:
                body["snoozed_until"] = inputs["snoozed_until"]

            await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}",
                method="PATCH",
                headers=_get_headers(context),
                json={"conversations": body},
            )
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("merge_conversations")
class MergeConversationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/merge",
                method="POST",
                headers=_get_headers(context),
                json={"target_conversation_id": inputs["target_conversation_id"]},
            )
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_conversation_messages")
class ListConversationMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            params: Dict[str, Any] = {}
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/messages",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            messages = response.data.get("messages", [])
            return ActionResult(data={"messages": messages, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"messages": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_conversation_comments")
class ListConversationCommentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/comments",
                method="GET",
                headers=_get_headers(context),
            )
            comments = response.data.get("comments", [])
            return ActionResult(data={"comments": comments, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"comments": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_conversation_posts")
class ListConversationPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/posts",
                method="GET",
                headers=_get_headers(context),
            )
            posts = response.data.get("posts", [])
            return ActionResult(data={"posts": posts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"posts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_conversation_drafts")
class ListConversationDraftsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/drafts",
                method="GET",
                headers=_get_headers(context),
            )
            drafts = response.data.get("drafts", [])
            return ActionResult(data={"drafts": drafts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"drafts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_messages")
class ListMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/messages",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            messages = response.data.get("messages", [])
            return ActionResult(data={"messages": messages, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"messages": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("get_message")
class GetMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]
            response = await context.fetch(
                f"{BASE_URL}/messages/{message_id}",
                method="GET",
                headers=_get_headers(context),
            )
            message = _first(response.data, "messages")
            return ActionResult(data={"message": message, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"message": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_message")
class CreateMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "channel_id": inputs["channel_id"],
                "body": inputs["body"],
                "account": inputs["account"],
                "from_field": inputs["from_field"],
                "to_fields": inputs["to_fields"],
            }
            if inputs.get("subject"):
                body["subject"] = inputs["subject"]
            if inputs.get("conversation_id"):
                body["conversation_id"] = inputs["conversation_id"]
            if inputs.get("external_id"):
                body["external_id"] = inputs["external_id"]

            response = await context.fetch(
                f"{BASE_URL}/messages",
                method="POST",
                headers=_get_headers(context),
                json={"messages": body},
            )
            message = response.data.get("messages", {})
            return ActionResult(data={"message": message, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"message": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_draft")
class CreateDraftAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "channel_id": inputs["channel_id"],
                "body": inputs["body"],
            }
            if inputs.get("subject") is not None:
                body["subject"] = inputs["subject"]
            if inputs.get("conversation_id") is not None:
                body["conversation_id"] = inputs["conversation_id"]
            if inputs.get("send") is not None:
                body["send"] = inputs["send"]
            if inputs.get("send_at") is not None:
                body["send_at"] = inputs["send_at"]
            if inputs.get("auto_followup") is not None:
                body["auto_followup"] = inputs["auto_followup"]
            if inputs.get("team_id") is not None:
                body["team_id"] = inputs["team_id"]
            if inputs.get("assignee_id") is not None:
                body["assignee_id"] = inputs["assignee_id"]
            if inputs.get("to"):
                body["to_fields"] = inputs["to"]
            if inputs.get("cc"):
                body["cc_fields"] = inputs["cc"]
            if inputs.get("bcc"):
                body["bcc_fields"] = inputs["bcc"]

            response = await context.fetch(
                f"{BASE_URL}/drafts",
                method="POST",
                headers=_get_headers(context),
                json={"drafts": body},
            )
            draft = response.data.get("drafts", {})
            return ActionResult(data={"draft": draft, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"draft": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("delete_draft")
class DeleteDraftAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_id = inputs["draft_id"]
            await context.fetch(
                f"{BASE_URL}/drafts/{draft_id}",
                method="DELETE",
                headers=_get_headers(context),
            )
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {"text": inputs["text"]}
            if inputs.get("conversation_id"):
                body["conversation_id"] = inputs["conversation_id"]
            if inputs.get("subject"):
                body["subject"] = inputs["subject"]
            if inputs.get("close") is not None:
                body["close"] = inputs["close"]
            if inputs.get("reopen") is not None:
                body["reopen"] = inputs["reopen"]
            if inputs.get("assignee_id"):
                body["assignee_id"] = inputs["assignee_id"]
            if inputs.get("team_id"):
                body["team_id"] = inputs["team_id"]
            if inputs.get("shared_label_ids"):
                body["shared_label_ids"] = inputs["shared_label_ids"]

            response = await context.fetch(
                f"{BASE_URL}/posts",
                method="POST",
                headers=_get_headers(context),
                json={"posts": body},
            )
            data = response.data
            return ActionResult(
                data={
                    "post": data.get("posts", {}),
                    "conversation": data.get("conversations", {}),
                    "result": True,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(data={"post": {}, "conversation": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("search"):
                params["search"] = inputs["search"]
            if inputs.get("contact_book_id"):
                params["contact_book_id"] = inputs["contact_book_id"]
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/contacts",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            contacts = response.data.get("contacts", [])
            return ActionResult(data={"contacts": contacts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contacts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            response = await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}",
                method="GET",
                headers=_get_headers(context),
            )
            contact = _first(response.data, "contacts")
            return ActionResult(data={"contact": contact, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contact": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_contact")
class CreateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_book_id = inputs["contact_book_id"]
            raw = inputs["contacts"]
            payload = [dict(c, contact_book_id=contact_book_id) for c in raw]
            response = await context.fetch(
                f"{BASE_URL}/contacts",
                method="POST",
                headers=_get_headers(context),
                json={"contacts": payload},
            )
            contacts = response.data.get("contacts", [])
            return ActionResult(data={"contacts": contacts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contacts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            body: Dict[str, Any] = {}
            if inputs.get("first_name") is not None:
                body["first_name"] = inputs["first_name"]
            if inputs.get("last_name") is not None:
                body["last_name"] = inputs["last_name"]
            if inputs.get("job_title") is not None:
                body["job_title"] = inputs["job_title"]
            if inputs.get("notes") is not None:
                body["notes"] = inputs["notes"]
            if inputs.get("infos") is not None:
                body["infos"] = inputs["infos"]

            response = await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}",
                method="PATCH",
                headers=_get_headers(context),
                json={"contacts": body},
            )
            contact = _first(response.data, "contacts")
            return ActionResult(data={"contact": contact, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contact": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_contact_books")
class ListContactBooksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/contact_books",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            contact_books = response.data.get("contact_books", [])
            return ActionResult(data={"contact_books": contact_books, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contact_books": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_contact_groups")
class ListContactGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {"contact_book_id": inputs["contact_book_id"]}
            if inputs.get("kind"):
                params["kind"] = inputs["kind"]
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/contact_groups",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            contact_groups = response.data.get("contact_groups", [])
            return ActionResult(data={"contact_groups": contact_groups, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contact_groups": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_analytics_report")
class CreateAnalyticsReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "start": inputs["start"],
                "end": inputs["end"],
                "organization": inputs["organization_id"],
            }
            if inputs.get("timezone") is not None:
                body["timezone"] = inputs["timezone"]
            if inputs.get("team_ids") is not None:
                body["team_ids"] = inputs["team_ids"]
            if inputs.get("user_ids") is not None:
                body["user_ids"] = inputs["user_ids"]
            if inputs.get("shared_label_ids") is not None:
                body["shared_label_ids"] = inputs["shared_label_ids"]

            response = await context.fetch(
                f"{BASE_URL}/analytics/reports",
                method="POST",
                headers=_get_headers(context),
                json={"reports": body},
            )
            report_id = response.data.get("reports", {}).get("id") or response.data.get("id")
            return ActionResult(data={"report_id": report_id, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"report_id": None, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("get_analytics_report")
class GetAnalyticsReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            report_id = inputs["report_id"]
            response = await context.fetch(
                f"{BASE_URL}/analytics/reports/{report_id}",
                method="GET",
                headers=_get_headers(context),
            )
            report = response.data.get("reports", response.data)
            return ActionResult(data={"report": report, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"report": {}, "result": False, "error": str(e)}, cost_usd=0.0)
