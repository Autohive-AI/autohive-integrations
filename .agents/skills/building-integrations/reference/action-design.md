# Action Design Reference

## Core Philosophy

Actions should be designed for the **user** (human or AI agent), not the API. A user thinks in terms of tasks ("get my posts", "manage a comment"), not API endpoints.

## Rule 1: Merge Get-One and Get-Many

If an API has separate endpoints for fetching a single item and listing items, **combine them into one action** with an optional ID parameter.

### ✅ Good: Merged Action

```json
{
    "get_events": {
        "display_name": "Get Events",
        "description": "Retrieve events from your account. Fetch a single event by ID, or list all events. Returns event details including name, dates, venue, and ticket information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "Optional: Specific event ID to retrieve. If provided, fetches that single event directly. If omitted, returns a paginated list of events."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to return (default: 25, max: 100). Only used when listing events.",
                    "default": 25
                }
            },
            "required": []
        }
    }
}
```

Implementation pattern:

```python
@my_integration.action("get_events")
class GetEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        
        if event_id:
            # Single item fetch
            response = await context.fetch(f"{API_BASE}/events/{event_id}", ...)
            return ActionResult(data={"event": response})
        
        # List fetch
        limit = min(inputs.get("limit", 25), 100)
        response = await context.fetch(f"{API_BASE}/events", params={"limit": limit}, ...)
        return ActionResult(data={"events": response.get("data", [])})
```

### ❌ Bad: Separate Actions

```json
{
    "get_event": { "description": "Get a single event by ID" },
    "list_events": { "description": "List all events" }
}
```

This wastes action slots and confuses users about which to use.

## Rule 2: Group Related Mutations

When multiple API endpoints perform related operations on the same resource, combine them into one action with an `action` enum parameter.

### ✅ Good: Grouped Mutations

```json
{
    "manage_comment": {
        "display_name": "Manage Comment",
        "description": "Interact with comments on your posts. Reply, hide/unhide, or like/unlike comments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "comment_id": {
                    "type": "string",
                    "description": "The comment ID to manage"
                },
                "action": {
                    "type": "string",
                    "enum": ["reply", "hide", "unhide", "like", "unlike"],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Required for 'reply' action: Your reply text"
                }
            },
            "required": ["comment_id", "action"]
        }
    }
}
```

### ❌ Bad: Separate Mutation Actions

```json
{
    "reply_to_comment": { ... },
    "hide_comment": { ... },
    "unhide_comment": { ... },
    "like_comment": { ... },
    "unlike_comment": { ... }
}
```

**When to keep separate:** Create/Update/Delete are typically separate actions because they have very different input schemas and semantics. Destructive actions like `delete_post` should be their own action for clarity and safety.

## Rule 3: Avoid Redundant Actions

If multiple API endpoints return the same type of data with minor filtering differences, combine them with a parameter.

### ✅ Good: Parameterized

```json
{
    "get_stories": {
        "display_name": "Get Stories",
        "description": "Fetch stories from Hacker News. Choose the type: top (trending), best (highest voted), new (latest), ask (Ask HN), show (Show HN), or jobs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["top", "best", "new", "ask", "show", "jobs"],
                    "description": "Type of stories to fetch (default: top)",
                    "default": "top"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum stories to return (1-100, default: 30)"
                }
            }
        }
    }
}
```

### ❌ Bad: Six Near-Identical Actions

```json
{
    "get_top_stories": { ... },
    "get_best_stories": { ... },
    "get_new_stories": { ... },
    "get_ask_hn_stories": { ... },
    "get_show_hn_stories": { ... },
    "get_job_stories": { ... }
}
```

## Rule 4: Pagination Support

For any action that returns lists, support pagination:

- **Cursor-based** (preferred): Use `after_cursor`/`next_cursor` parameters
- **Page-based**: Use `page` and `page_size` parameters
- Always cap the maximum (e.g., `min(inputs.get("limit", 25), 100)`)
- Always return pagination metadata in the response

```python
# Cursor-based pagination
return ActionResult(data={
    "items": items,
    "next_cursor": cursors.get("after") if paging.get("next") else None
})

# Page-based pagination
return ActionResult(data={
    "result": True,
    "items": items,
    "total": response.get("total", len(items)),
    "page": page,
    "pageSize": page_size,
})
```

## Rule 5: Error Handling

Actions should handle errors gracefully and return structured error information.

### Pattern 1: Exception-based (for platform/OAuth auth)

```python
@my_integration.action("get_posts")
class GetPostsAction(ActionHandler):
    async def execute(self, inputs, context):
        page_token = await get_page_access_token(context, inputs["page_id"])
        
        response = await context.fetch(
            f"{API_BASE}/{page_id}/posts",
            method="GET",
            params={"access_token": page_token}
        )
        
        return ActionResult(data={"posts": response.get("data", [])})
```

Exceptions from `context.fetch` or helper functions will propagate to the SDK, which handles them.

### Pattern 2: Result-based (for custom/API key auth)

```python
@my_integration.action("get_events")
class GetEventsAction(ActionHandler):
    async def execute(self, inputs, context):
        response = await context.fetch(url, method="GET", headers=get_api_headers(context))
        
        # Check for API error
        if error := build_error_result(response):
            return error
        
        return build_paginated_result(response, "events", page, page_size)
```

## Rule 6: Data Normalization

Use private helper functions to normalize API responses into consistent formats:

```python
def _build_post_response(post: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a post object from the API into a consistent response format."""
    return {
        "id": post.get("id", ""),
        "message": post.get("message", ""),
        "created_time": post.get("created_time", ""),
        "permalink_url": post.get("permalink_url", ""),
        "likes_count": post.get("likes", {}).get("summary", {}).get("total_count", 0),
        "comments_count": post.get("comments", {}).get("summary", {}).get("total_count", 0),
    }
```

This ensures:
- Consistent field names regardless of API quirks
- Safe `.get()` access with defaults
- Clean output for both AI agents and human users

## Rule 7: Input Validation

Validate inputs at the start of the action handler:

```python
async def execute(self, inputs, context):
    action = inputs["action"]
    message = inputs.get("message")
    
    if action == "reply" and not message:
        raise Exception("message is required for reply action")
    
    if media_type in ("photo", "video") and not media_url:
        raise Exception(f"media_url is required for {media_type} posts")
```

## Rule 8: Description Writing

Action descriptions are read by both AI agents and humans deciding whether to activate an action. They must be:

1. **Specific** — Say exactly what the action does
2. **Behavioral** — Explain how optional parameters change behavior
3. **Contextual** — Mention relevant constraints or notes

### ✅ Good Descriptions

```
"Retrieve posts from a Facebook Page. Fetch a single post by ID, or list recent posts. Includes message content, media, and engagement metrics."

"Retrieve advanced analytics beyond basic like/comment counts. Account metrics: reach, impressions, profile views, follower demographics. Post metrics: reach, saves, shares, video watch time."

"Interact with comments on your Page posts. Reply, hide/unhide, or like/unlike comments."
```

### ❌ Bad Descriptions

```
"Gets posts"
"Manages comments"
"Fetches data from the API"
```

## Rule 9: When to Create vs Update vs Delete Separately

- **Create** — Always a separate action (different input shape)
- **Update** — Usually separate from Create (requires an ID + partial fields)
- **Delete** — ALWAYS a separate action (destructive, needs explicit user intent)
- **Read (get/list)** — Merge into one action with optional ID
- **Moderate/Manage** — Group related state changes (hide/unhide, like/unlike, reply)

## Rule 10: Insights and Analytics

When an API separates basic metrics (returned with list endpoints) from advanced analytics (separate insights endpoint), create a dedicated `get_insights` action:

```json
{
    "get_insights": {
        "description": "Retrieve analytics for a page or post. Page metrics: follows, engagements, video views. Post metrics: engaged users, clicks, reactions.",
        "input_schema": {
            "properties": {
                "target_type": {
                    "type": "string",
                    "enum": ["page", "post"],
                    "description": "Type of insights"
                },
                "target_id": {
                    "type": "string",
                    "description": "The page or post ID"
                },
                "metrics": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Specific metrics. Defaults to common metrics if omitted."
                },
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "days_28"],
                    "description": "Time period (default: days_28). Ignored for post insights."
                }
            },
            "required": ["target_type", "target_id"]
        }
    }
}
```
