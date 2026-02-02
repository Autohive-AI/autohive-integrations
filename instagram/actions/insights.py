"""
Instagram Insights actions - Analytics for accounts and media.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from instagram import instagram
from helpers import INSTAGRAM_GRAPH_API_BASE, get_instagram_account_id


@instagram.action("get_insights")
class GetInsightsAction(ActionHandler):
    """
    Retrieve advanced analytics for an Instagram account or specific media.
    
    Use this for detailed performance metrics beyond basic like/comment
    counts. For simple engagement counts, use Get Posts instead.
    
    Account insights include:
    - Reach and impressions
    - Profile views
    - Follower demographics
    - Content interactions (likes, comments, shares, saves)
    
    Media insights include:
    - Reach and impressions  
    - Saves and shares
    - Video views and watch time (for Reels)
    - Story navigation and profile activity
    
    Note: Story insights are only available for 24 hours after posting.
    """
    
    DEFAULT_ACCOUNT_METRICS = [
        "reach",
        "profile_views",
        "accounts_engaged",
        "total_interactions",
        "likes",
        "comments",
        "shares",
        "saves",
        "follows_and_unfollows"
    ]
    
    DEFAULT_MEDIA_METRICS_FEED = [
        "reach",
        "likes", 
        "comments",
        "shares",
        "saved",
        "total_interactions",
        "views"
    ]
    
    DEFAULT_MEDIA_METRICS_REELS = [
        "reach",
        "likes",
        "comments", 
        "shares",
        "saved",
        "total_interactions",
        "views",
        "ig_reels_avg_watch_time",
        "ig_reels_video_view_total_time"
    ]
    
    DEFAULT_MEDIA_METRICS_STORY = [
        "reach",
        "views",
        "navigation",
        "profile_activity",
        "shares",
        "follows"
    ]
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        target_type = inputs["target_type"]
        target_id = inputs.get("target_id")
        custom_metrics = inputs.get("metrics")
        period = inputs.get("period", "days_28")
        
        if target_type == "account":
            account_id = await get_instagram_account_id(context)
            metrics = custom_metrics or self.DEFAULT_ACCOUNT_METRICS
            
            params = {
                "metric": ",".join(metrics),
                "period": period,
                "metric_type": "total_value"
            }
            
            endpoint = f"{INSTAGRAM_GRAPH_API_BASE}/{account_id}/insights"
            
        else:
            if not target_id:
                raise Exception("target_id is required for media insights")
            
            media_response = await context.fetch(
                f"{INSTAGRAM_GRAPH_API_BASE}/{target_id}",
                method="GET",
                params={"fields": "media_product_type"}
            )
            media_product_type = media_response.get("media_product_type", "FEED")
            
            if media_product_type == "REELS":
                metrics = custom_metrics or self.DEFAULT_MEDIA_METRICS_REELS
            elif media_product_type == "STORY":
                metrics = custom_metrics or self.DEFAULT_MEDIA_METRICS_STORY
            else:
                metrics = custom_metrics or self.DEFAULT_MEDIA_METRICS_FEED
            
            params = {"metric": ",".join(metrics)}
            endpoint = f"{INSTAGRAM_GRAPH_API_BASE}/{target_id}/insights"
        
        response = await context.fetch(endpoint, method="GET", params=params)
        
        metrics_data = {}
        for item in response.get("data", []):
            metric_name = item.get("name", "")
            
            total_value = item.get("total_value", {})
            if total_value:
                metrics_data[metric_name] = total_value.get("value", total_value)
            else:
                values = item.get("values", [])
                if values:
                    metrics_data[metric_name] = values[-1].get("value")
        
        return ActionResult(data={
            "target_type": target_type,
            "target_id": target_id if target_type == "media" else "account",
            "period": period if target_type == "account" else "lifetime",
            "metrics": metrics_data
        })
