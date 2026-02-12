# Examples: Good vs Bad Patterns

## Good Example: Merged Get/List (Facebook `get_posts`)

One action handles both fetching a single post and listing posts:

**config.json:**
```json
{
    "get_posts": {
        "display_name": "Get Posts",
        "description": "Retrieve posts from a Facebook Page. Fetch a single post by ID, or list recent posts. Includes message content, media, and engagement metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Facebook Page ID"
                },
                "post_id": {
                    "type": "string",
                    "description": "Optional: Specific post ID to retrieve. If omitted, returns recent posts."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of posts to return (default: 25, max: 100). Only used when listing posts.",
                    "default": 25
                }
            },
            "required": ["page_id"]
        }
    }
}
```

**Implementation:**
```python
@facebook.action("get_posts")
class GetPostsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        page_id = inputs["page_id"]
        post_id = inputs.get("post_id")
        limit = min(inputs.get("limit", 25), 100)
        
        page_token = await get_page_access_token(context, page_id)
        fields = "id,message,created_time,permalink_url,shares,likes.summary(true),comments.summary(true),attachments{type,url,media}"
        
        if post_id:
            response = await context.fetch(
                f"{GRAPH_API_BASE}/{post_id}",
                method="GET",
                params={"fields": fields, "access_token": page_token}
            )
            posts = [_build_post_response(response)]
        else:
            response = await context.fetch(
                f"{GRAPH_API_BASE}/{page_id}/posts",
                method="GET",
                params={"fields": fields, "limit": limit, "access_token": page_token}
            )
            posts = [_build_post_response(p) for p in response.get("data", [])]
        
        return ActionResult(data={"posts": posts})
```

## Good Example: Grouped Mutations (Facebook `manage_comment`)

Multiple related operations in one action:

```python
@facebook.action("manage_comment")
class ManageCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        page_id = inputs["page_id"]
        comment_id = inputs["comment_id"]
        action = inputs["action"]
        message = inputs.get("message")
        
        if action == "reply" and not message:
            raise Exception("message is required for reply action")
        
        page_token = await get_page_access_token(context, page_id)
        
        if action == "reply":
            response = await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}/comments",
                method="POST",
                data={"message": message, "access_token": page_token}
            )
            return ActionResult(data={
                "success": True, "action_taken": "reply",
                "reply_id": response.get("id", "")
            })
            
        elif action in ("hide", "unhide"):
            is_hidden = action == "hide"
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}",
                method="POST",
                data={"is_hidden": str(is_hidden).lower(), "access_token": page_token}
            )
            return ActionResult(data={
                "success": True, "action_taken": action, "is_hidden": is_hidden
            })
        
        elif action == "like":
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}/likes",
                method="POST",
                data={"access_token": page_token}
            )
            return ActionResult(data={"success": True, "action_taken": "like"})
        
        elif action == "unlike":
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}/likes",
                method="DELETE",
                params={"access_token": page_token}
            )
            return ActionResult(data={"success": True, "action_taken": "unlike"})
        
        raise Exception(f"Unknown action: {action}")
```

## Good Example: Reusable Helpers (Humanitix)

DRY helper functions that reduce action code to the essentials:

**helpers.py:**
```python
HUMANITIX_API_BASE = "https://api.humanitix.com/v1"

def get_api_headers(context: ExecutionContext) -> Dict[str, str]:
    credentials = context.auth.get("credentials", {})
    return {"x-api-key": credentials.get("api_key", ""), "Accept": "application/json"}

def build_url(path: str, params: Dict[str, Any] | None = None) -> str:
    safe_path = "/".join(quote(segment, safe="") for segment in path.split("/"))
    url = f"{HUMANITIX_API_BASE}/{safe_path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url

async def fetch_single_resource(context, path, params, result_key) -> ActionResult:
    url = build_url(path, params or None)
    response = await context.fetch(url, method="GET", headers=get_api_headers(context))
    if error := build_error_result(response): return error
    return ActionResult(data={"result": True, result_key: response})

def build_paginated_result(response, key, page, page_size=None) -> ActionResult:
    items = response.get(key, []) if isinstance(response, dict) else []
    is_dict = isinstance(response, dict)
    return ActionResult(data={
        "result": True, key: items,
        "total": response.get("total", len(items)) if is_dict else len(items),
        "page": response.get("page", page) if is_dict else page,
        "pageSize": response.get("pageSize", page_size or 100) if is_dict else (page_size or 100),
    })
```

**Action becomes very clean:**
```python
@humanitix.action("get_events")
class GetEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        override_location = inputs.get("override_location")
        params = {}
        if override_location:
            params["overrideLocation"] = override_location

        if event_id:
            return await fetch_single_resource(context, f"events/{event_id}", params, "event")

        page = inputs.get("page", 1)
        page_size = inputs.get("page_size")
        params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size

        url = build_url("events", params)
        response = await context.fetch(url, method="GET", headers=get_api_headers(context))
        if error := build_error_result(response): return error
        return build_paginated_result(response, "events", page, page_size)
```

## Good Example: Connected Account (Instagram)

```python
@instagram.connected_account()
class InstagramConnectedAccountHandler(ConnectedAccountHandler):
    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        fields = ",".join(["id", "username", "name", "profile_picture_url"])
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/me",
            method="GET",
            params={"fields": fields}
        )
        name = response.get("name", "")
        name_parts = name.split(maxsplit=1) if name else []
        return ConnectedAccountInfo(
            username=response.get("username"),
            first_name=name_parts[0] if len(name_parts) > 0 else None,
            last_name=name_parts[1] if len(name_parts) > 1 else None,
            avatar_url=response.get("profile_picture_url"),
            user_id=response.get("id")
        )
```

## Good Example: Data Normalization

Private functions that create consistent response shapes:

```python
def _build_post_response(post: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a post object from the Graph API into a consistent response format."""
    shares = post.get("shares", {})
    likes = post.get("likes", {}).get("summary", {})
    comments = post.get("comments", {}).get("summary", {})
    
    attachments = post.get("attachments", {}).get("data", [])
    media_type = "text"
    media_url = None
    
    if attachments:
        attachment = attachments[0]
        attach_type = attachment.get("type", "")
        if "photo" in attach_type:
            media_type = "photo"
            media_url = attachment.get("media", {}).get("image", {}).get("src")
        elif "video" in attach_type:
            media_type = "video"
            media_url = attachment.get("media", {}).get("source") or attachment.get("url")
        elif "share" in attach_type or attachment.get("url"):
            media_type = "link"
            media_url = attachment.get("url")
    
    return {
        "id": post.get("id", ""),
        "message": post.get("message", ""),
        "created_time": post.get("created_time", ""),
        "permalink_url": post.get("permalink_url", ""),
        "shares_count": shares.get("count", 0),
        "likes_count": likes.get("total_count", 0),
        "comments_count": comments.get("total_count", 0),
        "media_type": media_type,
        "media_url": media_url
    }
```

## Good Example: Multi-File Actions/__init__.py

```python
"""
Facebook integration actions.
Importing this module registers all actions with the facebook integration instance.
"""
from . import pages
from . import posts
from . import comments
from . import insights
```

---

## ❌ Bad Example: Too Many Similar Actions

Don't create separate actions when a parameter would suffice:

```python
# BAD: 6 near-identical action handlers
@hackernews.action("get_top_stories")
class GetTopStoriesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await fetch_stories_list(context, "topstories", inputs.get("limit", 30))

@hackernews.action("get_best_stories")
class GetBestStoriesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await fetch_stories_list(context, "beststories", inputs.get("limit", 30))

@hackernews.action("get_new_stories")
class GetNewStoriesAction(ActionHandler):
    async def execute(self, inputs, context):
        return await fetch_stories_list(context, "newstories", inputs.get("limit", 30))
# ... and 3 more identical handlers
```

**Fix:** One action with a `type` parameter:

```python
# GOOD: Single parameterized action
STORY_TYPES = {
    "top": "topstories",
    "best": "beststories",
    "new": "newstories",
    "ask": "askstories",
    "show": "showstories",
    "jobs": "jobstories",
}

@hackernews.action("get_stories")
class GetStoriesAction(ActionHandler):
    async def execute(self, inputs, context):
        story_type = inputs.get("type", "top")
        endpoint = STORY_TYPES.get(story_type, "topstories")
        limit = inputs.get("limit", 30)
        return await fetch_stories_list(context, endpoint, limit)
```

## ❌ Bad Example: Giant Single File

A 1300+ line single file with everything crammed in:

```python
# BAD: circle.py — 1300+ lines with TipTap converter, 20+ action handlers,
# helper functions, and constants all in one file

class TipTapRenderer(mistune.BaseRenderer):  # 250 lines of rendering code
    ...

def build_auth_headers(context): ...
def build_search_params(inputs, allowed): ...
def handle_api_response(response, empty_data): ...

@circle.action("search_posts")
class SearchPostsAction(ActionHandler): ...

@circle.action("get_post")       # Should be merged with search_posts
class GetPostAction(ActionHandler): ...

# ... 15 more action handlers
```

**Fix:** Split into multi-file structure:

```
circle/
├── circle.py          # Entry point only
├── helpers.py         # Auth headers, search params, response handling, TipTap converter
├── actions/
│   ├── __init__.py
│   ├── posts.py       # search_posts (merged with get_post), create_post, update_post
│   ├── members.py     # search_member, list_members
│   ├── spaces.py      # list_spaces
│   ├── events.py      # list_events
│   ├── comments.py    # add_comment, list_comments
│   ├── tags.py        # list_tags
│   └── groups.py      # space groups, access groups
```

## ❌ Bad Example: Separate Get and List

```json
{
    "get_event": {
        "description": "Get a single event by ID",
        "input_schema": {
            "properties": {
                "event_id": { "type": "string" }
            },
            "required": ["event_id"]
        }
    },
    "list_events": {
        "description": "List all events",
        "input_schema": {
            "properties": {
                "limit": { "type": "integer" }
            }
        }
    }
}
```

**Fix:** Merge into one `get_events` action with optional `event_id`.

## ❌ Bad Example: Vague Descriptions

```json
{
    "get_data": {
        "description": "Gets data from the API"
    },
    "do_thing": {
        "description": "Performs an action"
    }
}
```

**Fix:** Be specific about what, how, and when:

```json
{
    "get_events": {
        "description": "Retrieve events from your account. Fetch a single event by ID, or list all events with pagination. Returns event details including name, dates, venue, and ticket information."
    }
}
```

## ❌ Bad Example: Missing Tests

An integration with no test file or only testing the happy path:

```python
# Only one test for an action with 5 behaviors
async def test_get_posts():
    result = await integration.execute_action("get_posts", {"page_id": "123"}, context)
    assert result is not None  # This tests almost nothing
```

**Fix:** Test every behavior:

```python
async def test_get_posts_list():          # List mode
async def test_get_posts_single():        # Single item mode
async def test_get_posts_empty():         # No results
async def test_get_posts_with_limit():    # Limit parameter
async def test_create_post_text():        # Text post
async def test_create_post_photo():       # Photo post
async def test_create_post_missing_url(): # Validation error
```
