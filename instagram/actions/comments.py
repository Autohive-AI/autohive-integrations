"""
Instagram Comments actions - Read, reply, hide, and delete comments.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from instagram import instagram
from helpers import INSTAGRAM_GRAPH_API_BASE


def _build_comment_response(comment: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a comment object from the Graph API into a consistent response format."""
    replies_data = comment.get("replies", {}).get("data", [])
    from_data = comment.get("from", {})
    
    username = comment.get("username") or from_data.get("username", "")
    
    return {
        "id": comment.get("id", ""),
        "text": comment.get("text", ""),
        "username": username,
        "user_id": from_data.get("id", ""),
        "timestamp": comment.get("timestamp", ""),
        "like_count": comment.get("like_count", 0),
        "replies": [
            {
                "id": reply.get("id", ""),
                "text": reply.get("text", ""),
                "username": reply.get("username") or reply.get("from", {}).get("username", ""),
                "user_id": reply.get("from", {}).get("id", ""),
                "timestamp": reply.get("timestamp", "")
            }
            for reply in replies_data
        ]
    }


@instagram.action("get_comments")
class GetCommentsAction(ActionHandler):
    """
    Retrieve comments on an Instagram media object.
    
    Returns comment text, author username, timestamps, and like counts.
    Also includes nested replies.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        media_id = inputs["media_id"]
        limit = min(inputs.get("limit", 25), 100)
        after_cursor = inputs.get("after_cursor")
        
        fields = "id,text,timestamp,username,like_count,from{id,username},replies{id,text,timestamp,username,from{id,username}}"
        
        params = {"fields": fields, "limit": limit}
        if after_cursor:
            params["after"] = after_cursor
        
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{media_id}/comments",
            method="GET",
            params=params
        )
        
        comments = [_build_comment_response(c) for c in response.get("data", [])]
        
        paging = response.get("paging", {})
        cursors = paging.get("cursors", {})
        next_cursor = cursors.get("after") if paging.get("next") else None
        
        return ActionResult(data={
            "comments": comments,
            "total_count": len(comments),
            "next_cursor": next_cursor
        })


@instagram.action("manage_comment")
class ManageCommentAction(ActionHandler):
    """
    Interact with comments on Instagram media.
    
    Supported actions:
    - reply: Post a reply to the comment
    - hide: Hide the comment from public view
    - unhide: Make a hidden comment visible again
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comment_id = inputs["comment_id"]
        action = inputs["action"]
        message = inputs.get("message")
        
        if action == "reply" and not message:
            raise Exception("message is required for reply action")
        
        if action == "reply":
            response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{comment_id}/replies",
                method="POST",
                data={"message": message}
            )
            return ActionResult(data={
                "success": True,
                "action_taken": "reply",
                "reply_id": response.get("id", "")
            })
            
        elif action in ("hide", "unhide"):
            hide_value = action == "hide"
            await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{comment_id}",
                method="POST",
                data={"hide": str(hide_value).lower()}
            )
            return ActionResult(data={
                "success": True,
                "action_taken": action,
                "is_hidden": hide_value
            })
        
        raise Exception(f"Unknown action: {action}. Use 'reply', 'hide', or 'unhide'.")


@instagram.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    """
    Permanently delete a comment from Instagram media.
    
    This action cannot be undone. You can only delete comments on
    media you own or comments that others have left on your media.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        comment_id = inputs["comment_id"]
        
        await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/{comment_id}",
            method="DELETE"
        )
        
        return ActionResult(data={
            "success": True,
            "deleted_comment_id": comment_id
        })
