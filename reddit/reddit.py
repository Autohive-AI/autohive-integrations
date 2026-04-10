from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
import urllib.parse

# Create the integration using the config.json
reddit = Integration.load()

# ---- Action Handlers ----

@reddit.action("search_subreddit")
class SearchSubredditAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        subreddit = inputs["subreddit"]
        query = inputs.get("query", "")
        sort = inputs.get("sort", "relevance")
        time_filter = inputs.get("time_filter", "all")
        limit = inputs.get("limit", 25)
        
        # Build search URL
        if query:
            url = f"https://oauth.reddit.com/r/{subreddit}/search"
            params = {
                "q": query,
                "sort": sort,
                "restrict_sr": "true",
                "limit": limit
            }
            if sort == "top":
                params["t"] = time_filter
        else:
            # Just get posts from subreddit without search
            url = f"https://oauth.reddit.com/r/{subreddit}/{sort}"
            params = {"limit": limit}
            if sort == "top":
                params["t"] = time_filter
        
        try:
            response = await context.fetch(
                url,
                method="GET",
                params=params,
                headers={"User-Agent": "AutohiveIntegration/1.0"}
            )
            
            posts = []
            if "data" in response and "children" in response["data"]:
                for post_data in response["data"]["children"]:
                    post = post_data["data"]
                    posts.append({
                        "id": post["id"],
                        "title": post["title"],
                        "selftext": post.get("selftext", ""),
                        "url": post["url"],
                        "author": post["author"],
                        "score": post["score"],
                        "num_comments": post["num_comments"],
                        "created_utc": post["created_utc"],
                        "permalink": f"https://reddit.com{post['permalink']}"
                    })
            
            return {"posts": posts}
            
        except Exception as e:
            raise Exception(f"Failed to search subreddit: {str(e)}")


@reddit.action("post_comment")
class PostCommentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        parent_id = inputs["parent_id"]
        text = inputs["text"]
        
        try:
            response = await context.fetch(
                "https://oauth.reddit.com/api/comment",
                method="POST",
                data={
                    "parent": parent_id,
                    "text": text,
                    "api_type": "json"
                },
                headers={
                    "User-Agent": "AutohiveIntegration/1.0",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            if response.get("json", {}).get("errors"):
                errors = response["json"]["errors"]
                raise Exception(f"Reddit API error: {errors}")
            
            comment_data = response["json"]["data"]["things"][0]["data"]
            
            return {
                "comment_id": comment_data["id"],
                "permalink": f"https://reddit.com{comment_data['permalink']}",
                "success": True
            }
            
        except Exception as e:
            return {
                "comment_id": "",
                "permalink": "",
                "success": False,
                "error": str(e)
            }
