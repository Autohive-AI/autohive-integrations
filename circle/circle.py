from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any, List, Optional
import mistune

circle = Integration.load()

CIRCLE_API_BASE = "https://app.circle.so/api/admin/v2"


# ---- TipTap Converter ----


class TipTapRenderer(mistune.BaseRenderer):
    """Single-pass renderer that emits TipTap/ProseMirror JSON directly."""

    NAME = "tiptap"

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.options = {
            "allow_images": False,
            "allow_tables": False,
            "allow_underline": False,
            "unsupported_policy": "degrade",
        }
        if options:
            self.options.update(options)

    def _marks(self, state) -> List[Dict[str, Any]]:
        return state.env.setdefault("marks", [])

    def _with_mark(self, state, mark: Dict[str, Any]):
        class MarkContext:
            def __init__(self, marks, mark):
                self.marks = marks
                self.mark = mark

            def __enter__(self):
                self.marks.append(self.mark)
                return self

            def __exit__(self, *args):
                self.marks.pop()

        return MarkContext(self._marks(state), mark)

    def _text_node(self, text: str, state) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        node = {"type": "text", "text": text}
        if self._marks(state):
            node["marks"] = list(self._marks(state))
        return node

    def _normalize_inline(self, nodes: List[Any]) -> List[Dict[str, Any]]:
        out = []
        for n in nodes or []:
            if not n:
                continue
            if out and out[-1].get("type") == "text" and n.get("type") == "text":
                if out[-1].get("marks", []) == n.get("marks", []):
                    out[-1]["text"] += n["text"]
                    continue
            out.append(n)
        return out

    def _wrap_inline_in_paragraph(self, children: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not children:
            return [{"type": "paragraph", "content": []}]
        block_types = {
            "paragraph",
            "heading",
            "bulletList",
            "orderedList",
            "blockquote",
            "codeBlock",
            "horizontalRule",
        }
        has_block = any(c.get("type") in block_types for c in children)
        if has_block:
            return children
        return [{"type": "paragraph", "content": self._normalize_inline(children)}]

    def _render_children(self, token, state) -> List[Any]:
        children = token.get("children")
        if not children:
            return []
        result = []
        for child in children:
            rendered = self.render_token(child, state)
            if rendered is not None:
                if isinstance(rendered, list):
                    result.extend(rendered)
                else:
                    result.append(rendered)
        return result

    def paragraph(self, token, state):
        children = self._normalize_inline(self._render_children(token, state))
        return {"type": "paragraph", "content": children}

    def heading(self, token, state):
        level = token["attrs"]["level"]
        children = self._normalize_inline(self._render_children(token, state))
        return {"type": "heading", "attrs": {"level": level}, "content": children}

    def list(self, token, state):
        ordered = token["attrs"].get("ordered", False)
        children = self._render_children(token, state)
        list_type = "orderedList" if ordered else "bulletList"
        return {"type": list_type, "content": [c for c in children if c]}

    def list_item(self, token, state):
        children = self._render_children(token, state)
        children = [c for c in children if c]
        return {"type": "listItem", "content": self._wrap_inline_in_paragraph(children)}

    def block_quote(self, token, state):
        children = self._render_children(token, state)
        return {"type": "blockquote", "content": [c for c in children if c]}

    def block_code(self, token, state):
        info = (token.get("attrs", {}) or {}).get("info") or ""
        lang = (info.strip().split() or [None])[0] or None
        content = [{"type": "text", "text": token["raw"]}] if token.get("raw") else []
        node = {"type": "codeBlock"}
        if lang:
            node["attrs"] = {"language": lang}
        node["content"] = content
        return node

    def thematic_break(self, token, state):
        return {"type": "horizontalRule"}

    def strong(self, token, state):
        with self._with_mark(state, {"type": "bold"}):
            return self._render_children(token, state)

    def emphasis(self, token, state):
        with self._with_mark(state, {"type": "italic"}):
            return self._render_children(token, state)

    def strikethrough(self, token, state):
        with self._with_mark(state, {"type": "strike"}):
            return self._render_children(token, state)

    def codespan(self, token, state):
        with self._with_mark(state, {"type": "code"}):
            return [self._text_node(token["raw"], state)]

    def link(self, token, state):
        attrs = {"href": token["attrs"]["url"]}
        title = token["attrs"].get("title")
        if title:
            attrs["title"] = title
        with self._with_mark(state, {"type": "link", "attrs": attrs}):
            return self._render_children(token, state)

    def image(self, token, state):
        attrs = token.get("attrs", {})
        if self.options["allow_images"]:
            node = {"type": "image", "attrs": {"src": attrs.get("url", ""), "alt": attrs.get("alt", "")}}
            if attrs.get("title"):
                node["attrs"]["title"] = attrs["title"]
            return node
        alt = attrs.get("alt", "")
        return self._text_node(alt, state) if alt else None

    def linebreak(self, token, state):
        return {"type": "hardBreak"}

    def softbreak(self, token, state):
        return {"type": "hardBreak"}

    def text(self, token, state):
        return self._text_node(token["raw"], state)

    def blank_line(self, token, state):
        return None

    def table(self, token, state):
        rows = []

        def extract_text(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    return node.get("text", node.get("raw", ""))
                children = node.get("children", [])
                return "".join(extract_text(ch) for ch in children)
            return ""

        for section in token.get("children", []):
            for row in section.get("children", []):
                if row.get("type") == "table_row":
                    cells = []
                    for cell in row.get("children", []):
                        cell_text = extract_text(cell)
                        cells.append(cell_text.strip())
                    rows.append(" | ".join(cells))

        content = []
        for i, line in enumerate(rows):
            if i:
                content.append({"type": "hardBreak"})
            content.append({"type": "text", "text": line})

        return {"type": "paragraph", "content": content} if content else None

    def table_head(self, token, state):
        return token

    def table_body(self, token, state):
        return token

    def table_row(self, token, state):
        return token

    def table_cell(self, token, state):
        return token

    def block_html(self, token, state):
        policy = self.options["unsupported_policy"]
        raw = token.get("raw", "")
        if policy == "codeblock":
            return {"type": "codeBlock", "content": [{"type": "text", "text": raw}]}
        elif policy == "degrade":
            import re

            text = re.sub(r"<[^>]+>", "", raw).strip()
            return {"type": "paragraph", "content": [{"type": "text", "text": text}]} if text else None
        return None

    def inline_html(self, token, state):
        return self.block_html(token, state)

    def block_text(self, token, state):
        return self._render_children(token, state)

    def block_error(self, token, state):
        return self._render_children(token, state)

    def render_tokens(self, tokens, state):
        content = []
        for tok in tokens:
            rendered = self.render_token(tok, state)
            if rendered is not None:
                if isinstance(rendered, list):
                    content.extend([r for r in rendered if r and isinstance(r, dict)])
                elif isinstance(rendered, dict):
                    content.append(rendered)
        return {"type": "doc", "content": content}


def text_to_tiptap_body(text: str) -> Dict[str, Any]:
    md = mistune.create_markdown(
        renderer=TipTapRenderer(
            {
                "allow_images": False,
                "allow_tables": False,
                "allow_underline": False,
                "unsupported_policy": "degrade",
            }
        ),
        plugins=["strikethrough", "table", "url"],
    )
    return md(text)


# ---- Utility Functions ----


def build_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    api_token = context.auth.get("credentials", {}).get("api_token") or context.auth.get("api_token")
    if not api_token:
        raise ValueError("Circle API token is required in auth (field 'api_token').")
    return {"Authorization": f"Token {api_token}", "Content-Type": "application/json"}


def build_search_params(inputs: Dict[str, Any], allowed_params: List[str]) -> Dict[str, Any]:
    return {key: inputs[key] for key in allowed_params if key in inputs and inputs[key] is not None}


def _check_api_error(data: Dict[str, Any]) -> None:
    if "error" in data:
        error_msg = data.get("error", "Unknown error")
        if isinstance(error_msg, str) and len(error_msg) > 500:
            error_msg = (
                "API request failed. Received HTML error page instead of JSON. Check endpoint URL and authentication."
            )
        raise ValueError(f"API request failed: {error_msg}")


# ---- Post Actions ----


@circle.action("search_posts")
class SearchPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("query", "space_id", "tag", "status", "per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 10)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/posts", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"posts": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("get_post")
class GetPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/posts/{inputs['post_id']}", headers=headers)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"post": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            tiptap_doc = text_to_tiptap_body(inputs["body"])
            post_data: Dict[str, Any] = {
                "space_id": inputs["space_id"],
                "name": inputs["name"],
                "tiptap_body": {"body": tiptap_doc},
                "status": inputs.get("status", "published"),
                "is_pinned": inputs.get("is_pinned", False),
                "is_comments_enabled": inputs.get("is_comments_enabled", True),
            }
            if inputs.get("user_email"):
                post_data["user_email"] = inputs["user_email"]
            resp = await context.fetch(f"{CIRCLE_API_BASE}/posts", headers=headers, method="POST", json=post_data)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"post": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("update_post")
class UpdatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            post_id = inputs["post_id"]
            update_data: Dict[str, Any] = {}
            if inputs.get("name") is not None:
                update_data["name"] = inputs.get("name")
            if inputs.get("body") is not None:
                update_data["tiptap_body"] = {"body": text_to_tiptap_body(inputs.get("body"))}
            if inputs.get("status") is not None:
                update_data["status"] = inputs.get("status")
            if inputs.get("is_pinned") is not None:
                update_data["is_pinned"] = inputs.get("is_pinned")
            resp = await context.fetch(
                f"{CIRCLE_API_BASE}/posts/{post_id}", headers=headers, method="PUT", json=update_data
            )
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"post": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Member Actions ----


@circle.action("search_member_by_email")
class SearchMemberByEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(
                f"{CIRCLE_API_BASE}/community_members/search",
                headers=headers,
                params={"email": inputs["email"]},
            )
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"member": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("list_members")
class ListMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("status", "per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 10)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/community_members", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"members": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("get_member")
class GetMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/community_members/{inputs['member_id']}", headers=headers)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"member": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Space Actions ----


@circle.action("search_spaces")
class SearchSpacesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("query", "space_type", "per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 10)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/spaces", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"spaces": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("get_space")
class GetSpaceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/spaces/{inputs['space_id']}", headers=headers)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"space": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Event Actions ----


@circle.action("search_events")
class SearchEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("query", "time_filter", "space_id", "per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 10)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/events", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"events": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("get_event")
class GetEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/events/{inputs['event_id']}", headers=headers)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"event": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Comment Actions ----


@circle.action("create_comment")
class CreateCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(
                f"{CIRCLE_API_BASE}/comments",
                headers=headers,
                method="POST",
                json={"post_id": inputs["post_id"], "body": inputs["body"]},
            )
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"comment": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("get_post_comments")
class GetPostCommentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(
                f"{CIRCLE_API_BASE}/comments",
                headers=headers,
                params={"post_id": inputs["post_id"], "per_page": inputs.get("per_page", 20)},
            )
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"comments": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Community Actions ----


@circle.action("get_community_info")
class GetCommunityInfoAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/community", headers=headers)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"community": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Member Tag Actions ----


@circle.action("add_member_tags")
class AddMemberTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            user_email = inputs["user_email"]
            results = []
            for tag_id in inputs["member_tag_ids"]:
                resp = await context.fetch(
                    f"{CIRCLE_API_BASE}/tagged_members",
                    headers=headers,
                    method="POST",
                    json={"user_email": user_email, "member_tag_id": tag_id},
                )
                data = resp.data
                _check_api_error(data)
                results.append(data)
            return ActionResult(
                data={"member": results[0] if results else {}, "tags_added": len(results)}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("remove_member_tags")
class RemoveMemberTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            user_email = inputs["user_email"]
            removed_count = 0
            for tag_id in inputs["member_tag_ids"]:
                await context.fetch(
                    f"{CIRCLE_API_BASE}/tagged_members",
                    headers=headers,
                    method="DELETE",
                    params={"user_email": user_email, "member_tag_id": tag_id},
                )
                removed_count += 1
            return ActionResult(data={"tags_removed": removed_count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Member Space Group Actions ----


@circle.action("add_member_to_space_groups")
class AddMemberToSpaceGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            email = inputs["email"]
            results = []
            for group_id in inputs["space_group_ids"]:
                resp = await context.fetch(
                    f"{CIRCLE_API_BASE}/space_group_members",
                    headers=headers,
                    method="POST",
                    json={"email": email, "space_group_id": group_id},
                )
                data = resp.data
                _check_api_error(data)
                results.append(data)
            return ActionResult(
                data={"member": results[0] if results else {}, "groups_added": len(results)}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("remove_member_from_space_groups")
class RemoveMemberFromSpaceGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            email = inputs["email"]
            removed_count = 0
            for group_id in inputs["space_group_ids"]:
                await context.fetch(
                    f"{CIRCLE_API_BASE}/space_group_members",
                    headers=headers,
                    method="DELETE",
                    params={"email": email, "space_group_id": group_id},
                )
                removed_count += 1
            return ActionResult(data={"groups_removed": removed_count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Tag and Space Group Listing Actions ----


@circle.action("list_tags")
class ListTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 100)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/member_tags", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(data={"tags": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("list_space_groups")
class ListSpaceGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 100)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/space_groups", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(
                data={"space_groups": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("list_access_groups")
class ListAccessGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            params: Dict[str, Any] = {}
            for key in ("per_page", "page"):
                if inputs.get(key) is not None:
                    params[key] = inputs.get(key)
            params.setdefault("per_page", 100)
            resp = await context.fetch(f"{CIRCLE_API_BASE}/access_groups", headers=headers, params=params)
            data = resp.data
            _check_api_error(data)
            return ActionResult(
                data={"access_groups": data.get("records", []), "count": data.get("count", 0)}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("add_member_to_access_groups")
class AddMemberToAccessGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            email = inputs["email"]
            results = []
            for group_id in inputs["access_group_ids"]:
                resp = await context.fetch(
                    f"{CIRCLE_API_BASE}/access_groups/{group_id}/community_members",
                    headers=headers,
                    method="POST",
                    json={"email": email},
                )
                data = resp.data
                _check_api_error(data)
                results.append(data)
            return ActionResult(
                data={"member": results[0] if results else {}, "groups_added": len(results)}, cost_usd=0.0
            )
        except Exception as e:
            return ActionError(message=str(e))


@circle.action("remove_member_from_access_groups")
class RemoveMemberFromAccessGroupsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_auth_headers(context)
            email = inputs["email"]
            removed_count = 0
            for group_id in inputs["access_group_ids"]:
                await context.fetch(
                    f"{CIRCLE_API_BASE}/access_groups/{group_id}/community_members",
                    headers=headers,
                    method="DELETE",
                    params={"email": email},
                )
                removed_count += 1
            return ActionResult(data={"groups_removed": removed_count}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
