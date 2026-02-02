from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio

hackernews = Integration.load()

BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_URL = "https://news.ycombinator.com/item?id="
HN_USER_URL = "https://news.ycombinator.com/user?id="


async def fetch_json(context: ExecutionContext, url: str) -> Optional[Any]:
    """Fetch JSON from a URL, returning None on error."""
    try:
        return await context.fetch(url, method="GET")
    except Exception:
        return None


async def fetch_item(context: ExecutionContext, item_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single item by ID."""
    return await fetch_json(context, f"{BASE_URL}/item/{item_id}.json")


async def fetch_items_batch(context: ExecutionContext, item_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch multiple items concurrently."""
    tasks = [fetch_item(context, item_id) for item_id in item_ids]
    results = await asyncio.gather(*tasks)
    return [item for item in results if item is not None]


def format_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format an item for LLM-friendly output."""
    formatted = {
        "id": item.get("id"),
        "title": item.get("title"),
        "type": item.get("type"),
        "by": item.get("by"),
        "score": item.get("score", 0),
        "descendants": item.get("descendants", 0),
        "hn_url": f"{HN_ITEM_URL}{item.get('id')}",
    }
    
    if item.get("time"):
        formatted["time"] = datetime.fromtimestamp(
            item["time"], tz=timezone.utc
        ).isoformat()
    
    if item.get("url"):
        formatted["url"] = item["url"]
    
    if item.get("text"):
        formatted["text"] = item["text"]
    
    return formatted


def format_comment(item: Dict[str, Any], replies: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Format a comment for LLM-friendly output."""
    if item.get("deleted") or item.get("dead"):
        return None
    
    formatted = {
        "id": item.get("id"),
        "by": item.get("by", "[deleted]"),
        "text": item.get("text", ""),
    }
    
    if item.get("time"):
        formatted["time"] = datetime.fromtimestamp(
            item["time"], tz=timezone.utc
        ).isoformat()
    
    if replies:
        formatted["replies"] = replies
    
    return formatted


async def fetch_comments_recursive(
    context: ExecutionContext,
    comment_ids: List[int],
    limit: int,
    current_depth: int,
    max_depth: int
) -> List[Dict[str, Any]]:
    """Recursively fetch comments up to a certain depth."""
    if not comment_ids or current_depth > max_depth:
        return []
    
    limited_ids = comment_ids[:limit] if current_depth == 1 else comment_ids[:10]
    comments = await fetch_items_batch(context, limited_ids)
    
    result = []
    for comment in comments:
        if comment.get("deleted") or comment.get("dead"):
            continue
        
        replies = []
        if current_depth < max_depth and comment.get("kids"):
            replies = await fetch_comments_recursive(
                context,
                comment["kids"],
                limit,
                current_depth + 1,
                max_depth
            )
        
        formatted = format_comment(comment, replies if replies else None)
        if formatted:
            result.append(formatted)
    
    return result


async def fetch_stories_list(
    context: ExecutionContext,
    endpoint: str,
    limit: int,
    output_key: str = "stories"
) -> Dict[str, Any]:
    """Generic function to fetch a list of stories from an endpoint."""
    story_ids = await fetch_json(context, f"{BASE_URL}/{endpoint}.json")
    
    if not story_ids:
        return {
            output_key: [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "count": 0
        }
    
    limited_ids = story_ids[:min(limit, 100)]
    items = await fetch_items_batch(context, limited_ids)
    
    formatted_items = []
    for item in items:
        if item:
            formatted_items.append(format_item(item))
    
    return {
        output_key: formatted_items,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(formatted_items)
    }


@hackernews.action("get_top_stories")
class GetTopStoriesAction(ActionHandler):
    """Fetch top stories from Hacker News."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "topstories", limit)
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"stories": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_best_stories")
class GetBestStoriesAction(ActionHandler):
    """Fetch best stories from Hacker News."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "beststories", limit)
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"stories": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_new_stories")
class GetNewStoriesAction(ActionHandler):
    """Fetch newest stories from Hacker News."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "newstories", limit)
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"stories": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_ask_hn_stories")
class GetAskHNStoriesAction(ActionHandler):
    """Fetch Ask HN stories."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "askstories", limit)
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"stories": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_show_hn_stories")
class GetShowHNStoriesAction(ActionHandler):
    """Fetch Show HN stories."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "showstories", limit)
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"stories": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_job_stories")
class GetJobStoriesAction(ActionHandler):
    """Fetch job postings from Hacker News."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 30)
            result = await fetch_stories_list(context, "jobstories", limit, output_key="jobs")
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"jobs": [], "count": 0, "error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_story_with_comments")
class GetStoryWithCommentsAction(ActionHandler):
    """Fetch a story with its comments."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            story_id = inputs["story_id"]
            comment_limit = inputs.get("comment_limit", 20)
            comment_depth = inputs.get("comment_depth", 2)
            
            story = await fetch_item(context, story_id)
            
            if not story:
                return ActionResult(
                    data={"error": f"Story with ID {story_id} not found"},
                    cost_usd=0.0
                )
            
            comments = []
            if story.get("kids"):
                comments = await fetch_comments_recursive(
                    context,
                    story["kids"],
                    comment_limit,
                    current_depth=1,
                    max_depth=comment_depth
                )
            
            return ActionResult(
                data={
                    "story": format_item(story),
                    "comments": comments,
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={"error": str(e)},
                cost_usd=0.0
            )


@hackernews.action("get_user_profile")
class GetUserProfileAction(ActionHandler):
    """Fetch a user's public profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            username = inputs["username"]
            
            user = await fetch_json(context, f"{BASE_URL}/user/{username}.json")
            
            if not user:
                return ActionResult(
                    data={"error": f"User '{username}' not found"},
                    cost_usd=0.0
                )
            
            result = {
                "id": user.get("id"),
                "karma": user.get("karma", 0),
                "profile_url": f"{HN_USER_URL}{username}"
            }
            
            if user.get("created"):
                result["created"] = datetime.fromtimestamp(
                    user["created"], tz=timezone.utc
                ).isoformat()
            
            if user.get("about"):
                result["about"] = user["about"]
            
            return ActionResult(data=result, cost_usd=0.0)
        except Exception as e:
            return ActionResult(
                data={"error": str(e)},
                cost_usd=0.0
            )
