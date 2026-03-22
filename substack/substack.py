from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)
from typing import Dict, Any
from urllib.parse import urlparse, urlunparse

substack = Integration.load()

SUBSTACK_BASE = "https://substack.com"


# ── Shared helpers ────────────────────────────────────────────────────────────


def _normalise_url(url: str) -> str:
    """Normalise a publication URL: enforce https, strip path, strip trailing slash."""
    parsed = urlparse(url)
    normalised = urlunparse(("https", parsed.netloc, "", "", "", ""))
    return normalised.rstrip("/")


def _build_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }


# HTTP errors (4xx/5xx) are raised automatically by context.fetch before
# returning the decoded response body to action handlers — no manual error
# handling is needed here.


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _format_post(post: Dict[str, Any]) -> Dict[str, Any]:
    return _drop_none(
        {
            # id has no default — if the API returns null, the key is omitted.
            # This matches the output schema where id is optional.
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
        }
    )


# ── Action handlers ───────────────────────────────────────────────────────────


@substack.action("get_publication_posts")
class GetPublicationPostsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers()
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
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        slug = inputs["slug"]
        headers = _build_headers()

        post = await context.fetch(
            f"{base_url}/api/v1/posts/{slug}",
            method="GET",
            headers=headers,
        )
        result = _drop_none(
            {
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
            }
        )
        return ActionResult(data=result, cost_usd=0.0)


@substack.action("search_publications")
class SearchPublicationsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        headers = _build_headers()
        params = {
            "query": inputs["query"],
            "page": inputs.get("page", 0),
            # Substack's publication search endpoint supports up to 100 results
            # per page (vs 50 for post-level endpoints).
            "limit": min(inputs.get("limit", 10), 100),
        }

        response = await context.fetch(
            f"{SUBSTACK_BASE}/api/v1/publication/search",
            method="GET",
            params=params,
            headers=headers,
        )
        pubs_raw = (
            response.get("publications", []) if isinstance(response, dict) else response
        )
        pubs = [
            _drop_none(
                {
                    "id": p.get("id"),
                    "name": p.get("name", ""),
                    "subdomain": p.get("subdomain", ""),
                    "custom_domain": p.get("custom_domain"),
                    "logo_url": p.get("logo_url"),
                    "description": p.get("description", ""),
                    "subscriber_count": p.get("subscriber_count"),
                }
            )
            for p in pubs_raw
        ]
        more = response.get("more", False) if isinstance(response, dict) else False
        return ActionResult(data={"publications": pubs, "more": more}, cost_usd=0.0)


@substack.action("search_posts")
class SearchPostsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        headers = _build_headers()
        # /api/v1/posts/search does not exist — Substack treats "search" as a slug
        # and returns 404. The archive endpoint supports keyword search via the
        # "search" param and is the correct way to filter posts by keyword.
        params = {
            "search": inputs["query"],
            "sort": "new",
            "offset": inputs.get("offset", 0),
            "limit": min(inputs.get("limit", 10), 50),
        }

        posts_raw = await context.fetch(
            f"{base_url}/api/v1/archive",
            method="GET",
            params=params,
            headers=headers,
        )
        posts = [_format_post(p) for p in (posts_raw or [])]
        return ActionResult(data={"posts": posts, "count": len(posts)}, cost_usd=0.0)


@substack.action("get_post_comments")
class GetPostCommentsAction(ActionHandler):
    async def execute(
        self, inputs: Dict[str, Any], context: ExecutionContext
    ) -> ActionResult:
        base_url = _normalise_url(inputs["publication_url"])
        post_id = inputs["post_id"]
        headers = _build_headers()
        params = {
            "sort": inputs.get("sort", "best"),
            # Substack expects the string "true"/"false" for this query param.
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
        return ActionResult(
            data={"comments": comments, "count": len(comments)}, cost_usd=0.0
        )
