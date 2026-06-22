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
    return {}


def _check_response(response: Any) -> None:
    if response.status < 200 or response.status >= 300:
        data = response.data if isinstance(response.data, dict) else {}
        err = data.get("error", {})
        msg = err.get("message", str(data)) if isinstance(err, dict) else str(data)
        raise RuntimeError(f"Missive error {response.status}: {msg}")


_TEAM_MAILBOXES = {"team_inbox", "team_closed", "team_all"}


@missive.action("list_conversations")
class ListConversationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            mailbox = inputs["mailbox"]
            if mailbox in _TEAM_MAILBOXES:
                team_id = inputs.get("team_id")
                if not team_id:
                    return ActionResult(
                        data={"conversations": [], "result": False, "error": "team_id is required for team mailboxes"},
                        cost_usd=0.0,
                    )
                params: Dict[str, Any] = {mailbox: team_id}
            elif mailbox == "shared_label":
                shared_label_id = inputs.get("shared_label_id")
                if not shared_label_id:
                    return ActionResult(
                        data={
                            "conversations": [],
                            "result": False,
                            "error": "shared_label_id is required for shared_label mailbox",
                        },
                        cost_usd=0.0,
                    )
                params = {mailbox: shared_label_id}
            else:
                params = {mailbox: "true"}

            if (
                sum(1 for f in (inputs.get("email"), inputs.get("domain"), inputs.get("contact_organization_id")) if f)
                > 1
            ):
                return ActionResult(
                    data={
                        "conversations": [],
                        "result": False,
                        "error": "Only one of email, domain, or contact_organization_id may be provided",
                    },
                    cost_usd=0.0,
                )
            if inputs.get("organization_id"):
                params["organization"] = inputs["organization_id"]
            if inputs.get("email"):
                params["email"] = inputs["email"]
            if inputs.get("domain"):
                params["domain"] = inputs["domain"]
            if inputs.get("contact_organization_id"):
                params["contact_organization"] = inputs["contact_organization_id"]
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
            _check_response(response)
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
            _check_response(response)
            conversation = _first(response.data, "conversations")
            return ActionResult(data={"conversation": conversation, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"conversation": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("update_conversation")
class UpdateConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            if (inputs.get("assignee_id") is not None or inputs.get("shared_label_ids") is not None) and not inputs.get(
                "organization_id"
            ):
                return ActionResult(
                    data={
                        "result": False,
                        "error": "organization_id is required when assignee_id or shared_label_ids is provided",
                    },
                    cost_usd=0.0,
                )
            body: Dict[str, Any] = {"id": conversation_id}
            if inputs.get("subject") is not None:
                body["subject"] = inputs["subject"]
            if inputs.get("color") is not None:
                body["color"] = inputs["color"]
            if inputs.get("assignee_id") is not None:
                body["add_assignees"] = [inputs["assignee_id"]]
            if inputs.get("team_id") is not None:
                body["team"] = inputs["team_id"]
            if inputs.get("shared_label_ids") is not None:
                body["add_shared_labels"] = inputs["shared_label_ids"]
            if inputs.get("organization_id") is not None:
                body["organization"] = inputs["organization_id"]
            if inputs.get("closed") is True:
                body["close"] = True
            elif inputs.get("closed") is False:
                body["reopen"] = True
            if inputs.get("snoozed_until") is not None:
                body["snoozed_until"] = inputs["snoozed_until"]

            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}",
                method="PATCH",
                headers=_get_headers(context),
                json={"conversations": [body]},
            )
            _check_response(response)
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("merge_conversations")
class MergeConversationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            conversation_id = inputs["conversation_id"]
            response = await context.fetch(
                f"{BASE_URL}/conversations/{conversation_id}/merge",
                method="POST",
                headers=_get_headers(context),
                json={"target": inputs["target_conversation_id"]},
            )
            _check_response(response)
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
            _check_response(response)
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
            _check_response(response)
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
            _check_response(response)
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
            _check_response(response)
            drafts = response.data.get("drafts", [])
            return ActionResult(data={"drafts": drafts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"drafts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_messages")
class ListMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {"email_message_id": inputs["email_message_id"]}
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/messages",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
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
            _check_response(response)
            message = _first(response.data, "messages")
            return ActionResult(data={"message": message, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"message": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_message")
class CreateMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "account": inputs["account"],
                "from_field": inputs["from_field"],
                "to_fields": inputs["to_fields"],
                "body": inputs["body"],
            }
            if inputs.get("subject"):
                body["subject"] = inputs["subject"]
            if inputs.get("conversation_id"):
                body["conversation"] = inputs["conversation_id"]
            if inputs.get("external_id"):
                body["external_id"] = inputs["external_id"]

            response = await context.fetch(
                f"{BASE_URL}/messages",
                method="POST",
                headers=_get_headers(context),
                json={"messages": body},
            )
            _check_response(response)
            message = response.data.get("message", response.data.get("messages", {}))
            return ActionResult(data={"message": message, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"message": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_draft")
class CreateDraftAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            if inputs.get("assignee_id") is not None and not inputs.get("organization_id"):
                return ActionResult(
                    data={
                        "draft": {},
                        "result": False,
                        "error": "organization_id is required when assignee_id is provided",
                    },
                    cost_usd=0.0,
                )
            body: Dict[str, Any] = {"body": inputs["body"]}
            if inputs.get("from_field") is not None:
                body["from_field"] = inputs["from_field"]
            if inputs.get("subject") is not None:
                body["subject"] = inputs["subject"]
            if inputs.get("conversation_id") is not None:
                body["conversation"] = inputs["conversation_id"]
            if inputs.get("account") is not None:
                body["account"] = inputs["account"]
            if inputs.get("send") is not None:
                body["send"] = inputs["send"]
            if inputs.get("send_at") is not None:
                body["send_at"] = inputs["send_at"]
            if inputs.get("auto_followup") is not None:
                body["auto_followup"] = inputs["auto_followup"]
            if inputs.get("team_id") is not None:
                body["team"] = inputs["team_id"]
            if inputs.get("assignee_id") is not None:
                body["add_assignees"] = [inputs["assignee_id"]]
            if inputs.get("organization_id") is not None:
                body["organization"] = inputs["organization_id"]
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
            _check_response(response)
            draft = response.data.get("draft", response.data.get("drafts", {}))
            return ActionResult(data={"draft": draft, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"draft": {}, "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("delete_draft")
class DeleteDraftAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_id = inputs["draft_id"]
            response = await context.fetch(
                f"{BASE_URL}/drafts/{draft_id}",
                method="DELETE",
                headers=_get_headers(context),
            )
            _check_response(response)
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            if (inputs.get("assignee_id") or inputs.get("shared_label_ids")) and not inputs.get("organization_id"):
                return ActionResult(
                    data={
                        "post": {},
                        "conversation_id": None,
                        "result": False,
                        "error": "organization_id is required when assignee_id or shared_label_ids is provided",
                    },
                    cost_usd=0.0,
                )
            body: Dict[str, Any] = {
                "conversation": inputs["conversation_id"],
                "text": inputs["text"],
                "notification": inputs["notification"],
            }
            if inputs.get("username"):
                body["username"] = inputs["username"]
            if inputs.get("close") is not None:
                body["close"] = inputs["close"]
            if inputs.get("reopen") is not None:
                body["reopen"] = inputs["reopen"]
            if inputs.get("assignee_id"):
                body["add_assignees"] = [inputs["assignee_id"]]
            if inputs.get("team_id"):
                body["team"] = inputs["team_id"]
            if inputs.get("shared_label_ids"):
                body["add_shared_labels"] = inputs["shared_label_ids"]
            if inputs.get("organization_id"):
                body["organization"] = inputs["organization_id"]

            response = await context.fetch(
                f"{BASE_URL}/posts",
                method="POST",
                headers=_get_headers(context),
                json={"posts": body},
            )
            _check_response(response)
            post = response.data.get("posts", {})
            conversation_id = post.get("conversation") if isinstance(post, dict) else None
            return ActionResult(
                data={"post": post, "conversation_id": conversation_id, "result": True},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionResult(
                data={"post": {}, "conversation_id": None, "result": False, "error": str(e)}, cost_usd=0.0
            )


@missive.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("search"):
                params["search"] = inputs["search"]
            if inputs.get("contact_book_id"):
                params["contact_book"] = inputs["contact_book_id"]
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/contacts",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
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
            _check_response(response)
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
            payload = [dict(c, contact_book=contact_book_id) for c in raw]
            response = await context.fetch(
                f"{BASE_URL}/contacts",
                method="POST",
                headers=_get_headers(context),
                json={"contacts": payload},
            )
            _check_response(response)
            contacts = response.data.get("contacts", [])
            return ActionResult(data={"contacts": contacts, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contacts": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            body: Dict[str, Any] = {"id": contact_id}
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
                json={"contacts": [body]},
            )
            _check_response(response)
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
            _check_response(response)
            contact_books = response.data.get("contact_books", [])
            return ActionResult(data={"contact_books": contact_books, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"contact_books": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_contact_groups")
class ListContactGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {
                "contact_book": inputs["contact_book_id"],
                "kind": inputs["kind"],
            }
            if inputs.get("limit"):
                params["limit"] = inputs["limit"]

            response = await context.fetch(
                f"{BASE_URL}/contact_groups",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
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
                body["time_zone"] = inputs["timezone"]
            if inputs.get("team_ids") is not None:
                body["teams"] = inputs["team_ids"]
            if inputs.get("user_ids") is not None:
                body["users"] = inputs["user_ids"]
            if inputs.get("shared_label_ids") is not None:
                body["shared_labels"] = inputs["shared_label_ids"]

            response = await context.fetch(
                f"{BASE_URL}/analytics/reports",
                method="POST",
                headers=_get_headers(context),
                json={"reports": body},
            )
            _check_response(response)
            report_id = response.data.get("reports", {}).get("id") or response.data.get("id")
            if not report_id:
                return ActionResult(
                    data={"report_id": None, "result": False, "error": "report_id not found in response"}, cost_usd=0.0
                )
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
            _check_response(response)
            report = response.data.get("reports", response.data)
            return ActionResult(data={"report": report, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"report": {}, "result": False, "error": str(e)}, cost_usd=0.0)


def _pagination_params(inputs: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if inputs.get("limit"):
        params["limit"] = inputs["limit"]
    if inputs.get("offset"):
        params["offset"] = inputs["offset"]
    return params


@missive.action("list_organizations")
class ListOrganizationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(
                f"{BASE_URL}/organizations",
                method="GET",
                headers=_get_headers(context),
                params=_pagination_params(inputs),
            )
            _check_response(response)
            organizations = response.data.get("organizations", [])
            return ActionResult(data={"organizations": organizations, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"organizations": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_users")
class ListUsersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params = _pagination_params(inputs)
            if inputs.get("organization_id"):
                params["organization"] = inputs["organization_id"]
            response = await context.fetch(
                f"{BASE_URL}/users",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
            users = response.data.get("users", [])
            return ActionResult(data={"users": users, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"users": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_teams")
class ListTeamsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params = _pagination_params(inputs)
            if inputs.get("organization_id"):
                params["organization"] = inputs["organization_id"]
            response = await context.fetch(
                f"{BASE_URL}/teams",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
            teams = response.data.get("teams", [])
            return ActionResult(data={"teams": teams, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"teams": [], "result": False, "error": str(e)}, cost_usd=0.0)


@missive.action("list_shared_labels")
class ListSharedLabelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params = _pagination_params(inputs)
            if inputs.get("organization_id"):
                params["organization"] = inputs["organization_id"]
            response = await context.fetch(
                f"{BASE_URL}/shared_labels",
                method="GET",
                headers=_get_headers(context),
                params=params,
            )
            _check_response(response)
            shared_labels = response.data.get("shared_labels", [])
            return ActionResult(data={"shared_labels": shared_labels, "result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"shared_labels": [], "result": False, "error": str(e)}, cost_usd=0.0)
