from typing import Any, Dict, List

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    Integration,
)

kajabi = Integration.load()

BASE_URL = "https://api.kajabi.com/v1"


def _headers(context: ExecutionContext) -> Dict[str, str]:
    api_key = context.auth.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }


def _extract(resource: Dict) -> Dict:
    if not resource:
        return {}
    out: Dict[str, Any] = {"id": resource.get("id")}
    out.update(resource.get("attributes", {}))
    return out


def _extract_list(data: Dict) -> List[Dict]:
    return [_extract(r) for r in data.get("data", [])]


def _total(data: Dict) -> int:
    meta = data.get("meta", {})
    page = meta.get("page", {})
    return page.get("total-count", len(data.get("data", [])))


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@kajabi.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("search"):
                params["filter[search]"] = inputs["search"]
            if inputs.get("page"):
                params["page[number]"] = inputs["page"]
            if inputs.get("page_size"):
                params["page[size]"] = inputs["page_size"]
            if inputs.get("sort"):
                params["sort"] = inputs["sort"]

            resp = await context.fetch(
                f"{BASE_URL}/contacts",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            data = resp.data
            return ActionResult(
                data={"contacts": _extract_list(data), "total": _total(data)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            resp = await context.fetch(
                f"{BASE_URL}/contacts/{inputs['contact_id']}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("create_contact")
class CreateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            attrs: Dict[str, Any] = {
                "name": inputs["name"],
                "email": inputs["email"],
            }
            if inputs.get("phone_number"):
                attrs["phone_number"] = inputs["phone_number"]
            if inputs.get("subscribed") is not None:
                attrs["subscribed"] = inputs["subscribed"]

            body = {"data": {"type": "contacts", "attributes": attrs}}
            resp = await context.fetch(
                f"{BASE_URL}/contacts",
                method="POST",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            attrs: Dict[str, Any] = {}
            if inputs.get("name"):
                attrs["name"] = inputs["name"]
            if inputs.get("email"):
                attrs["email"] = inputs["email"]
            if inputs.get("phone_number"):
                attrs["phone_number"] = inputs["phone_number"]
            if inputs.get("subscribed") is not None:
                attrs["subscribed"] = inputs["subscribed"]

            body = {"data": {"type": "contacts", "id": contact_id, "attributes": attrs}}
            resp = await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}",
                method="PATCH",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("delete_contact")
class DeleteContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            await context.fetch(
                f"{BASE_URL}/contacts/{inputs['contact_id']}",
                method="DELETE",
                headers=_headers(context),
            )
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Contact Tags
# ---------------------------------------------------------------------------


@kajabi.action("list_contact_tags")
class ListContactTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("name_contains"):
                params["filter[name_cont]"] = inputs["name_contains"]
            if inputs.get("page"):
                params["page[number]"] = inputs["page"]
            if inputs.get("page_size"):
                params["page[size]"] = inputs["page_size"]

            resp = await context.fetch(
                f"{BASE_URL}/contact_tags",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            data = resp.data
            return ActionResult(
                data={"tags": _extract_list(data), "total": _total(data)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("get_contact_tag")
class GetContactTagAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            resp = await context.fetch(
                f"{BASE_URL}/contact_tags/{inputs['tag_id']}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("add_tag_to_contact")
class AddTagToContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            tag_data = [{"type": "contact_tags", "id": tid} for tid in inputs["tag_ids"]]
            body = {"data": tag_data}
            await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}/relationships/tags",
                method="POST",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data={"added": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("remove_tag_from_contact")
class RemoveTagFromContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            tag_data = [{"type": "contact_tags", "id": tid} for tid in inputs["tag_ids"]]
            body = {"data": tag_data}
            await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}/relationships/tags",
                method="DELETE",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data={"removed": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Contact Notes
# ---------------------------------------------------------------------------


@kajabi.action("list_contact_notes")
class ListContactNotesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("contact_id"):
                params["filter[contact_id]"] = inputs["contact_id"]
            if inputs.get("page"):
                params["page[number]"] = inputs["page"]
            if inputs.get("page_size"):
                params["page[size]"] = inputs["page_size"]

            resp = await context.fetch(
                f"{BASE_URL}/contact_notes",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            data = resp.data
            return ActionResult(
                data={"notes": _extract_list(data), "total": _total(data)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("get_contact_note")
class GetContactNoteAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            resp = await context.fetch(
                f"{BASE_URL}/contact_notes/{inputs['note_id']}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("create_contact_note")
class CreateContactNoteAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body = {
                "data": {
                    "type": "contact_notes",
                    "attributes": {"body": inputs["body"]},
                    "relationships": {"contact": {"data": {"type": "contacts", "id": inputs["contact_id"]}}},
                }
            }
            resp = await context.fetch(
                f"{BASE_URL}/contact_notes",
                method="POST",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("update_contact_note")
class UpdateContactNoteAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            note_id = inputs["note_id"]
            body = {
                "data": {
                    "type": "contact_notes",
                    "id": note_id,
                    "attributes": {"body": inputs["body"]},
                }
            }
            resp = await context.fetch(
                f"{BASE_URL}/contact_notes/{note_id}",
                method="PATCH",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("delete_contact_note")
class DeleteContactNoteAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            await context.fetch(
                f"{BASE_URL}/contact_notes/{inputs['note_id']}",
                method="DELETE",
                headers=_headers(context),
            )
            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Contact Offers
# ---------------------------------------------------------------------------


@kajabi.action("list_contact_offers")
class ListContactOffersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            resp = await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}/relationships/offers",
                method="GET",
                headers=_headers(context),
            )
            data = resp.data
            offers = [{"id": r.get("id")} for r in data.get("data", [])]
            return ActionResult(data={"offers": offers}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("grant_offer_to_contact")
class GrantOfferToContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            body: Dict[str, Any] = {"data": [{"type": "offers", "id": inputs["offer_id"]}]}
            if inputs.get("send_welcome_email") is not None:
                body["meta"] = {"send_customer_welcome_email": inputs["send_welcome_email"]}
            await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}/relationships/offers",
                method="POST",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data={"granted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("revoke_offer_from_contact")
class RevokeOfferFromContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_id = inputs["contact_id"]
            body = {"data": [{"type": "offers", "id": inputs["offer_id"]}]}
            await context.fetch(
                f"{BASE_URL}/contacts/{contact_id}/relationships/offers",
                method="DELETE",
                headers=_headers(context),
                json=body,
            )
            return ActionResult(data={"revoked": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


@kajabi.action("list_courses")
class ListCoursesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("title_contains"):
                params["filter[title_cont]"] = inputs["title_contains"]
            if inputs.get("page"):
                params["page[number]"] = inputs["page"]
            if inputs.get("page_size"):
                params["page[size]"] = inputs["page_size"]

            resp = await context.fetch(
                f"{BASE_URL}/courses",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            data = resp.data
            return ActionResult(
                data={"courses": _extract_list(data), "total": _total(data)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("get_course")
class GetCourseAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            resp = await context.fetch(
                f"{BASE_URL}/courses/{inputs['course_id']}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Blog Posts
# ---------------------------------------------------------------------------


@kajabi.action("list_blog_posts")
class ListBlogPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {}
            if inputs.get("title_contains"):
                params["filter[title_cont]"] = inputs["title_contains"]
            if inputs.get("page"):
                params["page[number]"] = inputs["page"]
            if inputs.get("page_size"):
                params["page[size]"] = inputs["page_size"]

            resp = await context.fetch(
                f"{BASE_URL}/blog_posts",
                method="GET",
                headers=_headers(context),
                params=params,
            )
            data = resp.data
            return ActionResult(
                data={"posts": _extract_list(data), "total": _total(data)},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@kajabi.action("get_blog_post")
class GetBlogPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            resp = await context.fetch(
                f"{BASE_URL}/blog_posts/{inputs['post_id']}",
                method="GET",
                headers=_headers(context),
            )
            return ActionResult(data=_extract(resp.data.get("data", {})), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
