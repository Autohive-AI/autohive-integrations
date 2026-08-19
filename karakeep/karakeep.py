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
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("base_url must be an http(s) URL")
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


# ---- Action Handlers ----


@karakeep.action("create_bookmark")
class CreateBookmarkAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            body: Dict[str, Any] = {"type": "link", "url": inputs["url"]}
            title = inputs.get("title")
            note = inputs.get("note")
            summary = inputs.get("summary")
            if title:
                body["title"] = title
            if note:
                body["note"] = note
            if summary:
                body["summary"] = summary
            archived = inputs.get("archived")
            favourited = inputs.get("favourited")
            if archived is not None:
                body["archived"] = bool(archived)
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
            already_existed = response.status == 200  # 200 = existing URL, 201 = created
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            bookmark_id = _path_id(inputs["bookmark_id"])
            tag_names = [str(t).strip() for t in (inputs["tags"] or []) if str(t).strip()]
            if not tag_names:
                return ActionResult(data={"attached": [], "count": 0}, cost_usd=0.0)
            body = {"tags": [{"tagName": name} for name in tag_names]}
            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks/{bookmark_id}/tags",
                method="POST",
                headers=headers,
                json=body,
            )
            data = response.data or {}
            attached = data.get("attached") or []
            return ActionResult(data={"attached": attached, "count": len(tag_names)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("search_bookmarks")
class SearchBookmarksAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            params: Dict[str, Any] = {"q": inputs["query"]}
            params.update(_page_params(inputs))
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            bookmark_id = _path_id(inputs["bookmark_id"])
            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks/{bookmark_id}",
                method="GET",
                headers=headers,
            )
            return ActionResult(data={"bookmark": response.data or {}}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("list_bookmarks")
class ListBookmarksAction(ActionHandler):
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
            response = await context.fetch(
                f"{base_url}/api/v1/bookmarks",
                method="GET",
                headers=headers,
                params=params,
            )
            return ActionResult(data=_paged_items(response.data or {}, "bookmarks"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@karakeep.action("create_tag")
class CreateTagAction(ActionHandler):
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            params = _page_params(inputs, max_limit=TAG_PAGE_MAX)
            name_contains = inputs.get("name_contains")
            if name_contains:
                params["nameContains"] = str(name_contains).strip()
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
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base_url = get_base_url(context)
            headers = get_auth_headers(context)
            tag_id = _path_id(inputs["tag_id"])
            response = await context.fetch(
                f"{base_url}/api/v1/tags/{tag_id}/bookmarks",
                method="GET",
                headers=headers,
                params=_page_params(inputs),
            )
            return ActionResult(data=_paged_items(response.data or {}, "bookmarks"), cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
