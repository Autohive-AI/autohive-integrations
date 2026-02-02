"""
Facebook Comments actions - Read, reply, hide, and delete comments.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from facebook import facebook
from helpers import GRAPH_API_BASE, get_page_access_token, extract_page_id


def _build_comment_response(comment: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a comment object from the Graph API into a consistent response format."""
    from_data = comment.get("from", {})
    return {
        "id": comment.get("id", ""),
        "message": comment.get("message", ""),
        "from_name": from_data.get("name", ""),
        "from_id": from_data.get("id", ""),
        "created_time": comment.get("created_time", ""),
        "is_hidden": comment.get("is_hidden", False),
        "reply_count": comment.get("comment_count", 0)
    }


@facebook.action("get_comments")
class GetCommentsAction(ActionHandler):
    """
    Retrieve comments on a Facebook Page post.
    
    Returns comment text, author information, timestamps, and reply counts.
    Can optionally include hidden comments.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        post_id = inputs["post_id"]
        limit = min(inputs.get("limit", 25), 100)
        include_hidden = inputs.get("include_hidden", False)
        
        page_id = extract_page_id(post_id)
        page_token = await get_page_access_token(context, page_id)
        
        fields = "id,message,from,created_time,is_hidden,comment_count"
        
        params = {
            "fields": fields,
            "limit": limit,
            "access_token": page_token,
            "summary": "true"
        }
        
        if include_hidden:
            params["filter"] = "stream"
        
        response = await context.fetch(
            f"{GRAPH_API_BASE}/{post_id}/comments",
            method="GET",
            params=params
        )
        
        comments = [_build_comment_response(c) for c in response.get("data", [])]
        total_count = response.get("summary", {}).get("total_count", len(comments))
        
        return ActionResult(data={
            "comments": comments,
            "total_count": total_count
        })


@facebook.action("manage_comment")
class ManageCommentAction(ActionHandler):
    """
    Interact with comments on Page posts.
    
    Supported actions:
    - reply: Post a reply to the comment
    - hide: Hide the comment from public view (still visible to commenter)
    - unhide: Make a hidden comment visible again
    - like: React to the comment as your Page
    - unlike: Remove your Page's reaction from the comment
    """
    
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
                data={
                    "message": message,
                    "access_token": page_token
                }
            )
            return ActionResult(data={
                "success": True,
                "action_taken": "reply",
                "reply_id": response.get("id", "")
            })
            
        elif action in ("hide", "unhide"):
            is_hidden = action == "hide"
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}",
                method="POST",
                data={
                    "is_hidden": str(is_hidden).lower(),
                    "access_token": page_token
                }
            )
            return ActionResult(data={
                "success": True,
                "action_taken": action,
                "is_hidden": is_hidden
            })
        
        elif action == "like":
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}/likes",
                method="POST",
                data={"access_token": page_token}
            )
            return ActionResult(data={
                "success": True,
                "action_taken": "like"
            })
        
        elif action == "unlike":
            await context.fetch(
                f"{GRAPH_API_BASE}/{comment_id}/likes",
                method="DELETE",
                params={"access_token": page_token}
            )
            return ActionResult(data={
                "success": True,
                "action_taken": "unlike"
            })
        
        raise Exception(f"Unknown action: {action}. Use 'reply', 'hide', 'unhide', 'like', or 'unlike'.")


@facebook.action("delete_comment")
class DeleteCommentAction(ActionHandler):
    """
    Permanently delete a comment from a Facebook Page post.
    
    This action cannot be undone. You can only delete comments on
    posts from Pages you manage.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        page_id = inputs["page_id"]
        comment_id = inputs["comment_id"]
        
        page_token = await get_page_access_token(context, page_id)
        
        await context.fetch(
            f"{GRAPH_API_BASE}/{comment_id}",
            method="DELETE",
            params={"access_token": page_token}
        )
        
        return ActionResult(data={
            "success": True,
            "deleted_comment_id": comment_id
        })
