import jwt
import mimetypes
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)

ghost = Integration.load()


# ---- Helpers ----


def _get_base_url(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {})
    url = credentials.get("api_url", "")
    if not url:
        raise ValueError("api_url is required in auth credentials")
    return url.rstrip("/")


def _content_get(
    context: ExecutionContext, endpoint: str, params: Optional[Dict] = None
) -> Dict:
    credentials = context.auth.get("credentials", {})
    content_key = credentials.get("content_api_key", "")
    if not content_key:
        raise ValueError("content_api_key is required in auth credentials")
    base = _get_base_url(context)
    url = f"{base}/ghost/api/content/{endpoint}/"
    all_params = {"key": content_key, **(params or {})}
    response = requests.get(url, params=all_params, timeout=30)
    response.raise_for_status()
    return response.json()


def _make_admin_jwt(context: ExecutionContext) -> str:
    credentials = context.auth.get("credentials", {})
    admin_key = credentials.get("admin_api_key", "")
    if not admin_key:
        raise ValueError("admin_api_key is required in auth credentials")
    if ":" not in admin_key:
        raise ValueError("admin_api_key must be in format id:secret")
    key_id, secret = admin_key.split(":", 1)
    now = datetime.now(tz=timezone.utc)
    token = jwt.encode(
        {"aud": "/admin/", "iat": now, "exp": now + timedelta(minutes=5)},
        bytes.fromhex(secret),
        algorithm="HS256",
        headers={"kid": key_id},
    )
    return token


def _admin_request(
    context: ExecutionContext,
    method: str,
    endpoint: str,
    json: Optional[Dict] = None,
    files: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict:
    base = _get_base_url(context)
    url = f"{base}/ghost/api/admin/{endpoint}/"
    token = _make_admin_jwt(context)
    headers = {"Authorization": f"Ghost {token}"}
    if files:
        response = requests.request(
            method, url, headers=headers, files=files, params=params, timeout=30
        )
    else:
        headers["Content-Type"] = "application/json"
        response = requests.request(
            method, url, headers=headers, json=json, params=params, timeout=30
        )
    response.raise_for_status()
    return response.json() if response.content else {}


def _success(data: Dict[str, Any]) -> ActionResult:
    return ActionResult(data={"result": True, **data})


def _parse_error(e: Exception) -> tuple:
    if isinstance(e, FileNotFoundError):
        return str(e), "FileNotFoundError"
    if isinstance(e, ValueError):
        return str(e), "ValidationError"
    error_msg = str(e)
    error_type = "UnknownError"
    if hasattr(e, "response") and e.response is not None:
        try:
            body = e.response.json()
            errors = body.get("errors", [])
            if errors:
                error_msg = errors[0].get("message", error_msg)
                error_type = errors[0].get("errorType", "UnknownError")
        except Exception:  # nosec B110
            pass
    return error_msg, error_type


def _error(e: Exception) -> ActionResult:
    error_msg, error_type = _parse_error(e)
    return ActionResult(
        data={"result": False, "error": error_msg, "error_type": error_type}
    )


# ---- Content API Actions ----


@ghost.action("get_posts")
class GetPostsAction(ActionHandler):
    """List posts from the Ghost Content API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                k: inputs[k]
                for k in ("limit", "page", "filter", "include")
                if inputs.get(k)
            }
            params.setdefault("limit", 15)
            data = _content_get(context, "posts", params)
            return _success(
                {"posts": data.get("posts", []), "meta": data.get("meta", {})}
            )
        except Exception as e:
            return _error(e)


@ghost.action("get_post")
class GetPostAction(ActionHandler):
    """Get a single post by id or slug."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post_id = inputs.get("id")
            slug = inputs.get("slug")
            if not post_id and not slug:
                raise ValueError("Either 'id' or 'slug' is required")
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            if post_id:
                data = _content_get(context, f"posts/{post_id}", params)
            else:
                data = _content_get(context, f"posts/slug/{slug}", params)
            posts = data.get("posts", [])
            return _success({"post": posts[0] if posts else None})
        except Exception as e:
            return _error(e)


@ghost.action("get_pages")
class GetPagesAction(ActionHandler):
    """List pages from the Ghost Content API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                k: inputs[k] for k in ("limit", "page", "filter") if inputs.get(k)
            }
            params.setdefault("limit", 15)
            data = _content_get(context, "pages", params)
            return _success(
                {"pages": data.get("pages", []), "meta": data.get("meta", {})}
            )
        except Exception as e:
            return _error(e)


@ghost.action("get_page")
class GetPageAction(ActionHandler):
    """Get a single page by id or slug."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page_id = inputs.get("id")
            slug = inputs.get("slug")
            if not page_id and not slug:
                raise ValueError("Either 'id' or 'slug' is required")
            params = {}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            if page_id:
                data = _content_get(context, f"pages/{page_id}", params)
            else:
                data = _content_get(context, f"pages/slug/{slug}", params)
            pages = data.get("pages", [])
            return _success({"page": pages[0] if pages else None})
        except Exception as e:
            return _error(e)


@ghost.action("get_tags")
class GetTagsAction(ActionHandler):
    """List tags."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                k: inputs[k] for k in ("limit", "page", "filter") if inputs.get(k)
            }
            params.setdefault("limit", 15)
            data = _content_get(context, "tags", params)
            return _success(
                {"tags": data.get("tags", []), "meta": data.get("meta", {})}
            )
        except Exception as e:
            return _error(e)


@ghost.action("get_authors")
class GetAuthorsAction(ActionHandler):
    """List authors."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {k: inputs[k] for k in ("limit", "page") if inputs.get(k)}
            params.setdefault("limit", 15)
            data = _content_get(context, "authors", params)
            return _success(
                {"authors": data.get("authors", []), "meta": data.get("meta", {})}
            )
        except Exception as e:
            return _error(e)


@ghost.action("get_settings")
class GetSettingsAction(ActionHandler):
    """Get site-wide settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = _content_get(context, "settings")
            return _success({"settings": data.get("settings", {})})
        except Exception as e:
            return _error(e)


@ghost.action("get_tiers")
class GetTiersAction(ActionHandler):
    """List membership tiers."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            data = _content_get(context, "tiers")
            return _success({"tiers": data.get("tiers", [])})
        except Exception as e:
            return _error(e)


# ---- Admin API Actions ----


@ghost.action("create_post")
class CreatePostAction(ActionHandler):
    """Create a new post via the Ghost Admin API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post = {"title": inputs["title"]}
            for field in [
                "html",
                "lexical",
                "status",
                "tags",
                "authors",
                "feature_image",
                "excerpt",
            ]:
                if inputs.get(field) is not None:
                    post[field] = inputs[field]
            post.setdefault("status", "draft")
            params = {"source": "html"} if inputs.get("html") else None
            data = _admin_request(
                context, "POST", "posts", json={"posts": [post]}, params=params
            )
            posts = data.get("posts", [])
            return _success({"post": posts[0] if posts else None})
        except Exception as e:
            return _error(e)


@ghost.action("update_post")
class UpdatePostAction(ActionHandler):
    """Update an existing post."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post_id = inputs["id"]
            post = {"updated_at": inputs["updated_at"]}
            for field in [
                "title",
                "html",
                "lexical",
                "status",
                "tags",
                "authors",
                "feature_image",
                "excerpt",
            ]:
                if inputs.get(field) is not None:
                    post[field] = inputs[field]
            params = {"source": "html"} if inputs.get("html") else None
            data = _admin_request(
                context,
                "PUT",
                f"posts/{post_id}",
                json={"posts": [post]},
                params=params,
            )
            posts = data.get("posts", [])
            return _success({"post": posts[0] if posts else None})
        except Exception as e:
            return _error(e)


@ghost.action("create_page")
class CreatePageAction(ActionHandler):
    """Create a new page via the Ghost Admin API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            page = {"title": inputs["title"]}
            for field in ["html", "lexical", "status"]:
                if inputs.get(field) is not None:
                    page[field] = inputs[field]
            page.setdefault("status", "draft")
            params = {"source": "html"} if inputs.get("html") else None
            data = _admin_request(
                context, "POST", "pages", json={"pages": [page]}, params=params
            )
            pages = data.get("pages", [])
            return _success({"page": pages[0] if pages else None})
        except Exception as e:
            return _error(e)


@ghost.action("upload_image")
class UploadImageAction(ActionHandler):
    """Upload an image to Ghost."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            file_path = inputs["file_path"]
            purpose = inputs.get("purpose", "image")
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.split("/")[-1].split("\\")[-1], f, mime_type),
                    "purpose": (None, purpose),
                }
                data = _admin_request(context, "POST", "images/upload", files=files)
            images = data.get("images", [])
            return _success({"image": images[0] if images else None})
        except Exception as e:
            return _error(e)


@ghost.action("create_member")
class CreateMemberAction(ActionHandler):
    """Create a new member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            member = {"email": inputs["email"]}
            for field in ["name", "labels", "newsletters", "note"]:
                if inputs.get(field) is not None:
                    member[field] = inputs[field]
            data = _admin_request(
                context, "POST", "members", json={"members": [member]}
            )
            members = data.get("members", [])
            return _success({"member": members[0] if members else None})
        except Exception as e:
            return _error(e)


@ghost.action("update_member")
class UpdateMemberAction(ActionHandler):
    """Update an existing member."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            member_id = inputs["id"]
            member = {}
            for field in ["email", "name", "labels", "newsletters", "note"]:
                if inputs.get(field) is not None:
                    member[field] = inputs[field]
            data = _admin_request(
                context, "PUT", f"members/{member_id}", json={"members": [member]}
            )
            members = data.get("members", [])
            return _success({"member": members[0] if members else None})
        except Exception as e:
            return _error(e)


@ghost.action("send_newsletter")
class SendNewsletterAction(ActionHandler):
    """Trigger email delivery of a published post to subscribers."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            post_id = inputs["post_id"]
            updated_at = inputs["updated_at"]
            newsletter_slug = inputs["newsletter_slug"]
            post = {"status": "published", "updated_at": updated_at}
            params = {"newsletter": newsletter_slug}
            data = _admin_request(
                context,
                "PUT",
                f"posts/{post_id}",
                json={"posts": [post]},
                params=params,
            )
            posts = data.get("posts", [])
            return _success({"post": posts[0] if posts else None})
        except Exception as e:
            return _error(e)
