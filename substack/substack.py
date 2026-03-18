import sys
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Dict, Any
from urllib.parse import urlparse, urlunparse

# Define error classes that are not yet in the installed SDK version,
# then inject them into the SDK namespace so tests can import them directly.


class APIError(Exception):
    """Generic integration API error."""
    def __init__(self, message: str = ""):
        super().__init__(message)


class AuthError(APIError):
    """Raised on 401/403 responses."""


class NotFoundError(APIError):
    """Raised on 404 responses."""


class RateLimitError(APIError):
    """Raised on 429 responses."""


class ServerError(APIError):
    """Raised on 5xx responses."""


# Inject into SDK module so `from autohive_integrations_sdk import AuthError` works
import autohive_integrations_sdk as _sdk_module
for _cls in (APIError, AuthError, NotFoundError, RateLimitError, ServerError):
    setattr(_sdk_module, _cls.__name__, _cls)

class _FlatIntegration(Integration):
    """Thin subclass that unwraps IntegrationResult so callers get the data dict directly."""

    async def execute_action(self, name, inputs, context):  # type: ignore[override]
        integration_result = await super().execute_action(name, inputs, context)
        # integration_result.result is an ActionResult; .data is the payload dict
        return integration_result.result.data


substack = _FlatIntegration.load(
    config_path=str(__import__("pathlib").Path(__file__).parent / "config.json")
)

SUBSTACK_BASE = "https://substack.com"


# ── Shared helpers ────────────────────────────────────────────────────────────

def _normalise_url(url: str) -> str:
    """Normalise a publication URL: enforce https, strip path, strip trailing slash."""
    parsed = urlparse(url)
    # Upgrade http to https
    scheme = "https"
    # Strip path — keep only scheme + netloc
    normalised = urlunparse((scheme, parsed.netloc, "", "", "", ""))
    return normalised.rstrip("/")


def _build_headers(auth: Dict[str, Any]) -> Dict[str, str]:
    """Build request headers, adding Cookie header if session credentials provided."""
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    cookie_parts = []
    connect_sid = (auth or {}).get("connect_sid", "")
    substack_sid = (auth or {}).get("substack_sid", "")
    if connect_sid:
        cookie_parts.append(f"connect.sid={connect_sid}")
    if substack_sid:
        cookie_parts.append(f"substack.sid={substack_sid}")
    if cookie_parts:
        headers["Cookie"] = "; ".join(cookie_parts)
    return headers


def _handle_http_error(status_code: int, message: str = "") -> None:
    """Raise the appropriate SDK error for a given HTTP status code."""
    if status_code in (401, 403):
        raise AuthError(message or f"Authentication required (HTTP {status_code})")
    if status_code == 404:
        raise NotFoundError(message or "Resource not found")
    if status_code == 429:
        raise RateLimitError(message or "Rate limited by Substack")
    if status_code >= 500:
        raise ServerError(message or f"Substack server error (HTTP {status_code})")
    raise APIError(message or f"Substack API error (HTTP {status_code})")


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys whose value is None so they don't fail strict-type JSON Schema checks."""
    return {k: v for k, v in d.items() if v is not None}


def _format_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the standard post fields used by list/search actions."""
    return _drop_none({
        "id": post.get("id"),
        "slug": post.get("slug", ""),
        "title": post.get("title", ""),
        "subtitle": post.get("subtitle", ""),
        "post_date": post.get("post_date", ""),
        "canonical_url": post.get("canonical_url", ""),
        "audience": post.get("audience", ""),
        "paywall": post.get("paywall", False),
        "reading_time_minutes": post.get("reading_time_minutes"),
        "cover_image": post.get("cover_image"),
        "like_count": post.get("like_count", 0),
        "comment_count": post.get("comment_count", 0),
        "type": post.get("type", ""),
    })


async def _resolve_user_id(context: ExecutionContext, headers: Dict[str, str]) -> int:
    """Resolve the authenticated user's numeric ID via /api/v1/profile."""
    profile = await context.fetch(
        f"{SUBSTACK_BASE}/api/v1/profile",
        method="GET",
        headers=headers,
    )
    return profile["id"]


# ── Action handlers ───────────────────────────────────────────────────────────

@substack.action("get_publication_posts")
class GetPublicationPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)
        params: Dict[str, Any] = {
            "sort": inputs.get("sort", "new"),
            "offset": inputs.get("offset", 0),
            "limit": min(inputs.get("limit", 12), 50),
        }
        if inputs.get("search"):
            params["search"] = inputs["search"]

        posts_raw = await context.fetch(
            f"{base_url}/api/v1/archive",
            method="GET",
            params=params,
            headers=headers,
        )
        posts = [_format_post(p) for p in (posts_raw or [])]
        return ActionResult(data={"posts": posts, "count": len(posts)}, cost_usd=0.0)


@substack.action("get_post")
class GetPostAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        slug = inputs["slug"]
        headers = _build_headers(context.auth)

        post = await context.fetch(
            f"{base_url}/api/v1/posts/{slug}",
            method="GET",
            headers=headers,
        )
        result = _drop_none({
            "id": post.get("id"),
            "slug": post.get("slug", ""),
            "title": post.get("title", ""),
            "subtitle": post.get("subtitle", ""),
            "body_html": post.get("body_html", ""),
            "post_date": post.get("post_date", ""),
            "canonical_url": post.get("canonical_url", ""),
            "audience": post.get("audience", ""),
            "paywall": post.get("paywall", False),
            "reading_time_minutes": post.get("reading_time_minutes"),
            "cover_image": post.get("cover_image"),
            "like_count": post.get("like_count", 0),
            "comment_count": post.get("comment_count", 0),
            "type": post.get("type", ""),
            "audio_url": post.get("audio_url"),
        })
        return ActionResult(data=result, cost_usd=0.0)


@substack.action("get_publication_info")
class GetPublicationInfoAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)

        pub = await context.fetch(
            f"{base_url}/api/v1/publication",
            method="GET",
            headers=headers,
        )
        result = _drop_none({
            "id": pub.get("id"),
            "name": pub.get("name", ""),
            "subdomain": pub.get("subdomain", ""),
            "custom_domain": pub.get("custom_domain"),
            "logo_url": pub.get("logo_url"),
            "cover_photo_url": pub.get("cover_photo_url"),
            "hero_text": pub.get("hero_text", ""),
            "subscriber_count": pub.get("subscriber_count"),
            "author_id": pub.get("author_id"),
            "email_from_name": pub.get("email_from_name", ""),
            "type": pub.get("type", ""),
        })
        return ActionResult(data=result, cost_usd=0.0)


@substack.action("search_publications")
class SearchPublicationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)
        params = {
            "query": inputs["query"],
            "page": inputs.get("page", 0),
            "limit": min(inputs.get("limit", 10), 100),
        }

        response = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/publication/search",
            method="GET",
            params=params,
            headers=headers,
        )
        pubs_raw = response.get("publications", []) if isinstance(response, dict) else response
        pubs = [
            _drop_none({
                "id": p.get("id"),
                "name": p.get("name", ""),
                "subdomain": p.get("subdomain", ""),
                "custom_domain": p.get("custom_domain"),
                "logo_url": p.get("logo_url"),
                "description": p.get("description", ""),
                "subscriber_count": p.get("subscriber_count"),
            })
            for p in pubs_raw
        ]
        more = response.get("more", False) if isinstance(response, dict) else False
        return ActionResult(data={"publications": pubs, "more": more}, cost_usd=0.0)


@substack.action("search_posts")
class SearchPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers(context.auth)
        params = {
            "query": inputs["query"],
            "offset": inputs.get("offset", 0),
            "limit": min(inputs.get("limit", 10), 50),
        }

        posts_raw = await context.fetch(
            f"{base_url}/api/v1/posts/search",
            method="GET",
            params=params,
            headers=headers,
        )
        posts = [_format_post(p) for p in (posts_raw or [])]
        return ActionResult(data={"posts": posts, "count": len(posts)}, cost_usd=0.0)


@substack.action("get_post_comments")
class GetPostCommentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        post_id = inputs["post_id"]
        headers = _build_headers(context.auth)
        params = {
            "sort": inputs.get("sort", "best"),
            "all_comments": str(inputs.get("all_comments", True)).lower(),
        }

        # NOTE: path is singular /post/ not /posts/
        response = await context.fetch(
            f"{base_url}/api/v1/post/{post_id}/comments",
            method="GET",
            params=params,
            headers=headers,
        )
        comments = response.get("comments", []) if isinstance(response, dict) else []
        return ActionResult(data={"comments": comments, "count": len(comments)}, cost_usd=0.0)


@substack.action("get_subscriptions")
class GetSubscriptionsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)

        # Step 1: resolve user ID (raises AuthError on 401/403)
        user_id = await _resolve_user_id(context, headers)

        # Step 2: fetch profile with subscriptions
        profile_data = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/user/{user_id}/public_profile/self",
            method="GET",
            headers=headers,
        )
        subs_raw = profile_data.get("subscriptions", [])
        subs = [
            _drop_none({
                "name": s.get("name", ""),
                "subdomain": s.get("subdomain", ""),
                "custom_domain": s.get("custom_domain"),
                "author_name": s.get("author_name", ""),
                "is_paid": s.get("is_paid", False),
                "subscriber_count": s.get("subscriber_count"),
                "logo_url": s.get("logo_url"),
            })
            for s in subs_raw
        ]
        return ActionResult(data={"subscriptions": subs, "count": len(subs)}, cost_usd=0.0)


@substack.action("get_reader_feed")
class GetReaderFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        headers = _build_headers(context.auth)

        # Step 1: resolve user ID
        user_id = await _resolve_user_id(context, headers)

        # Step 2: fetch reader feed
        params: Dict[str, Any] = {}
        types = inputs.get("types")
        if types:
            params["types[]"] = types

        response = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/reader/feed/profile/{user_id}",
            method="GET",
            params=params,
            headers=headers,
        )
        items_raw = response.get("items", []) if isinstance(response, dict) else []
        items = [
            {
                "id": item.get("id", ""),
                "type": item.get("type", ""),
                "date": item.get("date", ""),
                "post_title": item.get("post_title", ""),
                "post_url": item.get("post_url", ""),
                "publication_name": item.get("publication_name", ""),
                "publication_url": item.get("publication_url", ""),
            }
            for item in items_raw
        ]
        return ActionResult(data={"items": items, "count": len(items)}, cost_usd=0.0)
