"""
Facebook Pages actions - Page discovery and listing.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from facebook import facebook
from helpers import GRAPH_API_BASE


@facebook.action("list_pages")
class ListPagesAction(ActionHandler):
    """
    Discover all Facebook Pages the authenticated user can manage.
    
    This is typically the first action used to identify available pages
    before performing other operations.
    """
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        response = await context.fetch(
            f"{GRAPH_API_BASE}/me/accounts",
            method="GET",
            params={"fields": "id,name,category,followers_count"}
        )
        
        pages = [
            {
                "id": page.get("id", ""),
                "name": page.get("name", ""),
                "category": page.get("category", ""),
                "followers_count": page.get("followers_count", 0)
            }
            for page in response.get("data", [])
        ]
        
        return ActionResult(data={"pages": pages})
