"""
Facebook Insights actions - Analytics for pages and posts.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from facebook import facebook
from helpers import GRAPH_API_BASE, get_page_access_token, extract_page_id


@facebook.action("get_insights")
class GetInsightsAction(ActionHandler):
    """
    Retrieve analytics for a Facebook Page or specific post.
    
    Page insights include:
    - Engagement metrics (reactions, comments, shares)
    - Reach and impressions
    - Follower growth
    - Video views (if applicable)
    
    Post insights include:
    - Post reach and impressions
    - Engagement breakdown
    - Click-through data
    """
    
    DEFAULT_PAGE_METRICS = [
        "page_follows",
        "page_daily_follows_unique",
        "page_daily_unfollows_unique",
        "page_post_engagements",
        "page_video_views",
        "page_media_view"
    ]
    
    DEFAULT_POST_METRICS = [
        "post_engaged_users",
        "post_clicks",
        "post_reactions_by_type_total"
    ]
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        target_type = inputs["target_type"]
        target_id = inputs["target_id"]
        custom_metrics = inputs.get("metrics")
        period = inputs.get("period", "days_28")
        
        if target_type == "page":
            page_id = target_id
            metrics = custom_metrics or self.DEFAULT_PAGE_METRICS
        else:
            page_id = extract_page_id(target_id)
            metrics = custom_metrics or self.DEFAULT_POST_METRICS
        
        page_token = await get_page_access_token(context, page_id)
        
        params = {
            "metric": ",".join(metrics),
            "access_token": page_token
        }
        
        if target_type == "page":
            params["period"] = period
        
        endpoint = f"{GRAPH_API_BASE}/{target_id}/insights"
        
        response = await context.fetch(endpoint, method="GET", params=params)
        
        metrics_data = {}
        for item in response.get("data", []):
            metric_name = item.get("name", "")
            values = item.get("values", [])
            if values:
                metrics_data[metric_name] = values[-1].get("value")
        
        return ActionResult(data={
            "target_type": target_type,
            "target_id": target_id,
            "period": period if target_type == "page" else "lifetime",
            "metrics": metrics_data
        })
