"""
Instagram Account actions - Account information retrieval.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from instagram import instagram
from helpers import INSTAGRAM_GRAPH_API_BASE


@instagram.action("get_account")
class GetAccountAction(ActionHandler):
    """
    Retrieve Instagram Business/Creator account details.
    
    Returns profile information including username, bio, follower counts,
    and other account metadata.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        fields = ",".join([
            "id",
            "username", 
            "name",
            "biography",
            "followers_count",
            "follows_count",
            "media_count",
            "profile_picture_url",
            "website"
        ])
        
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/me",
            method="GET",
            params={"fields": fields}
        )
        
        return ActionResult(data={
            "id": response.get("id", ""),
            "username": response.get("username", ""),
            "name": response.get("name", ""),
            "biography": response.get("biography", ""),
            "followers_count": response.get("followers_count", 0),
            "following_count": response.get("follows_count", 0),
            "media_count": response.get("media_count", 0),
            "profile_picture_url": response.get("profile_picture_url", ""),
            "website": response.get("website", "")
        })
