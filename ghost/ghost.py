import jwt
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)

ghost = Integration.load()


def _get_base_url(context: ExecutionContext) -> str:
    url = context.auth.get("api_url", "")
    if not url:
        raise ValueError("api_url is required in auth")
    return url.rstrip("/")


def _content_headers(context: ExecutionContext) -> tuple:
    """Returns (base_url, params_with_key)."""
    content_key = context.auth.get("content_api_key", "")
    if not content_key:
        raise ValueError("content_api_key is required in auth")
    base = _get_base_url(context)
    return base, content_key


def _make_admin_jwt(context: ExecutionContext) -> str:
    admin_key = context.auth.get("admin_api_key", "")
    if not admin_key:
        raise ValueError("admin_api_key is required in auth")
    if ":" not in admin_key:
        raise ValueError("admin_api_key must be in format id:secret")
    key_id, secret = admin_key.split(":", 1)
    now = datetime.now(tz=timezone.utc)
    return jwt.encode(
        {"aud": "/admin/", "iat": now, "exp": now + timedelta(minutes=5)},
        bytes.fromhex(secret),
        algorithm="HS256",
        headers={"kid": key_id},
    )


def _admin_headers(context: ExecutionContext) -> tuple:
    """Returns (base_url, headers)."""
    base = _get_base_url(context)
    token = _make_admin_jwt(context)
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
    }
    return base, headers


# ---- Content API Actions ----


@ghost.action("get_posts")
class GetPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            params: Dict[str, Any] = {k: inputs[k] for k in ("limit", "page", "filter", "include") if inputs.get(k)}
            params.setdefault("limit", 15)
            params["key"] = content_key
            resp = await context.fetch(f"{base}/ghost/api/content/posts/", method="GET", params=params)
            data = resp.data
            return ActionResult(data={"posts": data.get("posts", []), "meta": data.get("meta", {})}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_post")
class GetPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            post_id = inputs.get("id")
            slug = inputs.get("slug")
            if not post_id and not slug:
                raise ValueError("Either 'id' or 'slug' is required")
            params: Dict[str, Any] = {"key": content_key}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            if post_id:
                endpoint = f"{base}/ghost/api/content/posts/{post_id}/"
            else:
                endpoint = f"{base}/ghost/api/content/posts/slug/{slug}/"
            resp = await context.fetch(endpoint, method="GET", params=params)
            posts = resp.data.get("posts", [])
            return ActionResult(data={"post": posts[0] if posts else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_pages")
class GetPagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            params: Dict[str, Any] = {k: inputs[k] for k in ("limit", "page", "filter") if inputs.get(k)}
            params.setdefault("limit", 15)
            params["key"] = content_key
            resp = await context.fetch(f"{base}/ghost/api/content/pages/", method="GET", params=params)
            data = resp.data
            return ActionResult(data={"pages": data.get("pages", []), "meta": data.get("meta", {})}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_page")
class GetPageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            page_id = inputs.get("id")
            slug = inputs.get("slug")
            if not page_id and not slug:
                raise ValueError("Either 'id' or 'slug' is required")
            params: Dict[str, Any] = {"key": content_key}
            if inputs.get("include"):
                params["include"] = inputs["include"]
            if page_id:
                endpoint = f"{base}/ghost/api/content/pages/{page_id}/"
            else:
                endpoint = f"{base}/ghost/api/content/pages/slug/{slug}/"
            resp = await context.fetch(endpoint, method="GET", params=params)
            pages = resp.data.get("pages", [])
            return ActionResult(data={"page": pages[0] if pages else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_tags")
class GetTagsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            params: Dict[str, Any] = {k: inputs[k] for k in ("limit", "page", "filter") if inputs.get(k)}
            params.setdefault("limit", 15)
            params["key"] = content_key
            resp = await context.fetch(f"{base}/ghost/api/content/tags/", method="GET", params=params)
            data = resp.data
            return ActionResult(data={"tags": data.get("tags", []), "meta": data.get("meta", {})}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_authors")
class GetAuthorsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            params: Dict[str, Any] = {k: inputs[k] for k in ("limit", "page") if inputs.get(k)}
            params.setdefault("limit", 15)
            params["key"] = content_key
            resp = await context.fetch(f"{base}/ghost/api/content/authors/", method="GET", params=params)
            data = resp.data
            return ActionResult(
                data={"authors": data.get("authors", []), "meta": data.get("meta", {})},
                cost_usd=0.0,
            )
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_settings")
class GetSettingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            resp = await context.fetch(
                f"{base}/ghost/api/content/settings/",
                method="GET",
                params={"key": content_key},
            )
            return ActionResult(data={"settings": resp.data.get("settings", {})}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("get_tiers")
class GetTiersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, content_key = _content_headers(context)
            resp = await context.fetch(
                f"{base}/ghost/api/content/tiers/",
                method="GET",
                params={"key": content_key},
            )
            return ActionResult(data={"tiers": resp.data.get("tiers", [])}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


# ---- Admin API Actions ----


@ghost.action("create_post")
class CreatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            post: Dict[str, Any] = {"title": inputs["title"]}
            for field in ("html", "lexical", "status", "tags", "authors", "feature_image", "excerpt"):
                if inputs.get(field) is not None:
                    post[field] = inputs[field]
            post.setdefault("status", "draft")
            params = {"source": "html"} if inputs.get("html") else None
            resp = await context.fetch(
                f"{base}/ghost/api/admin/posts/",
                method="POST",
                headers=headers,
                json={"posts": [post]},
                params=params,
            )
            posts = resp.data.get("posts", [])
            return ActionResult(data={"post": posts[0] if posts else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("update_post")
class UpdatePostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            post_id = inputs["id"]
            post: Dict[str, Any] = {"updated_at": inputs["updated_at"]}
            for field in ("title", "html", "lexical", "status", "tags", "authors", "feature_image", "excerpt"):
                if inputs.get(field) is not None:
                    post[field] = inputs[field]
            params = {"source": "html"} if inputs.get("html") else None
            resp = await context.fetch(
                f"{base}/ghost/api/admin/posts/{post_id}/",
                method="PUT",
                headers=headers,
                json={"posts": [post]},
                params=params,
            )
            posts = resp.data.get("posts", [])
            return ActionResult(data={"post": posts[0] if posts else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("create_page")
class CreatePageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            page: Dict[str, Any] = {"title": inputs["title"]}
            for field in ("html", "lexical", "status"):
                if inputs.get(field) is not None:
                    page[field] = inputs[field]
            page.setdefault("status", "draft")
            params = {"source": "html"} if inputs.get("html") else None
            resp = await context.fetch(
                f"{base}/ghost/api/admin/pages/",
                method="POST",
                headers=headers,
                json={"pages": [page]},
                params=params,
            )
            pages = resp.data.get("pages", [])
            return ActionResult(data={"page": pages[0] if pages else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("upload_image")
class UploadImageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            # Remove Content-Type so multipart boundary is set automatically
            headers.pop("Content-Type", None)
            file_path = inputs["file_path"]
            purpose = inputs.get("purpose", "image")
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            with open(file_path, "rb") as f:
                file_data = f.read()
            filename = file_path.replace("\\", "/").split("/")[-1]
            files = {
                "file": (filename, file_data, mime_type),
                "purpose": (None, purpose),
            }
            resp = await context.fetch(
                f"{base}/ghost/api/admin/images/upload/",
                method="POST",
                headers=headers,
                files=files,
            )
            images = resp.data.get("images", [])
            return ActionResult(data={"image": images[0] if images else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("create_member")
class CreateMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            member: Dict[str, Any] = {"email": inputs["email"]}
            for field in ("name", "labels", "newsletters", "note"):
                if inputs.get(field) is not None:
                    member[field] = inputs[field]
            resp = await context.fetch(
                f"{base}/ghost/api/admin/members/",
                method="POST",
                headers=headers,
                json={"members": [member]},
            )
            members = resp.data.get("members", [])
            return ActionResult(data={"member": members[0] if members else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("update_member")
class UpdateMemberAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            member_id = inputs["id"]
            member: Dict[str, Any] = {}
            for field in ("email", "name", "labels", "newsletters", "note"):
                if inputs.get(field) is not None:
                    member[field] = inputs[field]
            resp = await context.fetch(
                f"{base}/ghost/api/admin/members/{member_id}/",
                method="PUT",
                headers=headers,
                json={"members": [member]},
            )
            members = resp.data.get("members", [])
            return ActionResult(data={"member": members[0] if members else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e


@ghost.action("send_newsletter")
class SendNewsletterAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            base, headers = _admin_headers(context)
            post_id = inputs["post_id"]
            post: Dict[str, Any] = {
                "status": "published",
                "updated_at": inputs["updated_at"],
            }
            resp = await context.fetch(
                f"{base}/ghost/api/admin/posts/{post_id}/",
                method="PUT",
                headers=headers,
                json={"posts": [post]},
                params={"newsletter": inputs["newsletter_slug"]},
            )
            posts = resp.data.get("posts", [])
            return ActionResult(data={"post": posts[0] if posts else None}, cost_usd=0.0)
        except ActionError:
            raise
        except Exception as e:
            raise ActionError(message=str(e)) from e
