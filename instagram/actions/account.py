from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from instagram import instagram
from helpers import INSTAGRAM_GRAPH_API_BASE


@instagram.action("get_account")
class GetAccountAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        fields = ",".join([
            "id", "username", "name", "biography",
            "followers_count", "follows_count", "media_count",
            "profile_picture_url", "website",
        ])
        response = await context.fetch(
            f"{INSTAGRAM_GRAPH_API_BASE}/me", method="GET", params={"fields": fields}
        )
        data = response.data
        return ActionResult(data={
            "id": data.get("id", ""),
            "username": data.get("username", ""),
            "name": data.get("name", ""),
            "biography": data.get("biography", ""),
            "followers_count": data.get("followers_count", 0),
            "following_count": data.get("follows_count", 0),
            "media_count": data.get("media_count", 0),
            "profile_picture_url": data.get("profile_picture_url", ""),
            "website": data.get("website", ""),
        })
