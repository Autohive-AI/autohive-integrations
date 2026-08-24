from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Any, Dict
from urllib.parse import quote, urlparse

karakeep = Integration.load()

BOOKMARK_PAGE_MAX = 100
TAG_PAGE_MAX = 1000
DEFAULT_PAGE_LIMIT = 20


# ---- Helper Functions ----


def _credentials(context: ExecutionContext) -> Dict[str, Any]:
    auth = context.auth or {}
    return auth.get("credentials") or auth


def get_api_key(context: ExecutionContext) -> str:
    api_key = str(_credentials(context).get("api_key") or "").strip()
    if not api_key:
        raise ValueError("api_key is required in auth")
    return api_key


def get_base_url(context: ExecutionContext) -> str:
    base_url = str(_credentials(context).get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("base_url is required in auth")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("base_url must be an https:// URL")
    return base_url


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {get_api_key(context)}",
        "Content-Type": "application/json",
    }


def _path_id(value: Any) -> str:
    return quote(str(value), safe="")


def _page_params(
    inputs: Dict[str, Any],
    default_limit: int = DEFAULT_PAGE_LIMIT,
    max_limit: int = BOOKMARK_PAGE_MAX,
) -> Dict[str, Any]:
    limit = inputs.get("limit")
    if isinstance(limit, int) and limit > 0:
        limit = min(limit, max_limit)
    else:
        limit = default_limit
    params: Dict[str, Any] = {"limit": limit}
    cursor = inputs.get("cursor")
    if cursor:
        params["cursor"] = cursor
    return params


def _paged_items(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    items = data.get(key) or []
    return {key: items, "count": len(items), "next_cursor": data.get("nextCursor")}


# ---- Bookmark Handlers ----


@karakeep.action("create_bookmark")
class CreateBookmarkAction(ActionHandler):
    """Create a link, text, or asset bookmark."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)

            bookmark_type = str(inputs.get("type") or "link").strip().lower()
            if bookmark_type not in ("link", "text", "asset"):
                raise ValueError(f"type must be one of 'link', 'text', 'asset' (got {bookmark_type!r})")

            body: Dict[str, Any] = {"type": bookmark_type}

            if bookmark_type == "link":
                url = str(inputs.get("url") or "").strip()
                if not url:
                    raise ValueError("url is required when type is 'link'")
                body["url"] = url
            elif bookmark_type == "text":
                text = inputs.get("text")
                if not text or not str(text).strip():
                    raise ValueError("text is required when type is 'text'")
                body["text"] = str(text)
                source_url = inputs.get("source_url")
                if source_url:
                    body["sourceUrl"] = str(source_url)
            elif bookmark_type == "asset":
                asset_type = inputs.get("asset_type")
                asset_id = inputs.get("asset_id")
                if asset_type not in ("image", "pdf"):
                    raise ValueError("asset_type must be 'image' or 'pdf' when type is 'asset'")
                if not asset_id or not str(asset_id).strip():
                    raise ValueError("asset_id is required when type is 'asset'")
                body["assetType"] = asset_type
                body["assetId"] = str(asset_id)
                file_name = inputs.get("file_name")
                if file_name:
                    body["fileName"] = str(file_name)
                source_url = inputs.get("source_url")
                if source_url:
                    body["sourceUrl"] = str(source_url)

            title = inputs.get("title")
            if title:
                body["title"] = title
            note = inputs.get("note")
            if note:
                body["note"] = note
            summary = inputs.get("summary")
            if summary:
                body["summary"] = summary
            archived = inputs.get("archived")
            if archived is not None:
                body["archived"] = bool(archived)
            favourited = inputs.get("favourited")
            if favourited is not None:
                body["favourited"] = bool(favourited)

            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks",
                method="POST",
                headers=headers,
                json=body,
            )
            data = response.data or {}
            bookmark_id = str(data.get("id") or "")
            if not bookmark_id:
                raise ValueError("Karakeep did not return a bookmark id")

            # Karakeep returns 201 on create, 200 when the URL was already
            # bookmarked (documented in the OpenAPI spec for POST /bookmarks).
            # The 200 semantic only applies to type 'link'.
            already_existed = response.status == 200 and bookmark_type == "link"

            return ActionResult(
                data={
                    "bookmark_id": bookmark_id,
                    "bookmark": data,
                    "already_existed": already_existed,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("attach_tags")
class AttachTagsAction(ActionHandler):
    """Attach tags to a bookmark by name or id."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            bookmark_id = _path_id(inputs["bookmark_id"])

            attached_by = inputs.get("attached_by")

            items: list = []
            for name in [str(t).strip() for t in (inputs.get("tags") or []) if str(t).strip()]:
                item: Dict[str, Any] = {"tagName": name}
                if attached_by:
                    item["attachedBy"] = attached_by
                items.append(item)
            for tag_id in [str(t).strip() for t in (inputs.get("tag_ids") or []) if str(t).strip()]:
                item = {"tagId": tag_id}
                if attached_by:
                    item["attachedBy"] = attached_by
                items.append(item)

            if not items:
                return ActionResult(data={"attached": [], "count": 0}, cost_usd=0.0)

            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks/{bookmark_id}/tags",
                method="POST",
                headers=headers,
                json={"tags": items},
            )
            data = response.data or {}
            attached = data.get("attached") or []
            return ActionResult(data={"attached": attached, "count": len(items)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("search_bookmarks")
class SearchBookmarksAction(ActionHandler):
    """Search bookmarks (full-text, semantic, or hybrid)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            params: Dict[str, Any] = {"q": inputs["query"]}
            params.update(_page_params(inputs))
            search_mode = inputs.get("search_mode")
            if search_mode:
                params["searchMode"] = search_mode
            sort_order = inputs.get("sort_order")
            if sort_order:
                params["sortOrder"] = sort_order
            if inputs.get("include_content") is not None:
                params["includeContent"] = "true" if inputs["include_content"] else "false"
            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks/search",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data=_paged_items(response.data or {}, "bookmarks"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("get_bookmark")
class GetBookmarkAction(ActionHandler):
    """Retrieve a bookmark by id."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            bookmark_id = _path_id(inputs["bookmark_id"])
            params: Dict[str, Any] = {}
            if inputs.get("include_content") is not None:
                params["includeContent"] = "true" if inputs["include_content"] else "false"

            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks/{bookmark_id}",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data={"bookmark": response.data or {}}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("list_bookmarks")
class ListBookmarksAction(ActionHandler):
    """List bookmarks with optional filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            params = _page_params(inputs)
            archived = inputs.get("archived")
            favourited = inputs.get("favourited")
            if archived is not None:
                params["archived"] = "true" if archived else "false"
            if favourited is not None:
                params["favourited"] = "true" if favourited else "false"
            sort_order = inputs.get("sort_order")
            if sort_order:
                params["sortOrder"] = sort_order
            if inputs.get("include_content") is not None:
                params["includeContent"] = "true" if inputs["include_content"] else "false"
            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data=_paged_items(response.data or {}, "bookmarks"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Tag Handlers ----


@karakeep.action("create_tag")
class CreateTagAction(ActionHandler):
    """Create a tag by name."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            name = str(inputs["name"] or "").strip()
            if not name:
                raise ValueError("name is required")
            response = await context.fetch(
                f"{base_url}/api/v1/tags",
                method="POST",
                headers=headers,
                json={"name": name},
            )
            data = response.data or {}
            tag_id = str(data.get("id") or "")
            if not tag_id:
                raise ValueError("Karakeep did not return a tag id")
            return ActionResult(
                data={"tag_id": tag_id, "name": data.get("name") or name, "tag": data},
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("list_tags")
class ListTagsAction(ActionHandler):
    """List tags, optionally filtered and sorted."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            params = _page_params(inputs, max_limit=TAG_PAGE_MAX)
            name_contains = inputs.get("name_contains")
            if name_contains:
                params["nameContains"] = str(name_contains).strip()
            sort = inputs.get("sort")
            if sort:
                params["sort"] = sort
            attached_by = inputs.get("attached_by")
            if attached_by:
                params["attachedBy"] = attached_by
            response = await context.fetch(
                f"{base_url}/api/v1/tags",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data=_paged_items(response.data or {}, "tags"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("get_tag_bookmarks")
class GetTagBookmarksAction(ActionHandler):
    """List bookmarks that have a given tag."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            tag_id = _path_id(inputs["tag_id"])
            params = _page_params(inputs)
            sort_order = inputs.get("sort_order")
            if sort_order:
                params["sortOrder"] = sort_order
            if inputs.get("include_content") is not None:
                params["includeContent"] = "true" if inputs["include_content"] else "false"

            response = await context.fetch(
                f"{base_url}/api/v1/tags/{tag_id}/bookmarks",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data=_paged_items(response.data or {}, "bookmarks"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
