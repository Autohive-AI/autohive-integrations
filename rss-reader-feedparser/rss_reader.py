# rss-reader.py
from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler
from typing import Dict, Any
import feedparser

# Create the integration using the config.json
rss_reader = Integration.load()


# ---- Action Handlers ----
@rss_reader.action("get_feed")
class GetFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        feed_url = inputs["feed_url"]
        limit = inputs.get("limit", 10)

        # Parse feed
        feed = feedparser.parse(feed_url)

        # Check for parsing errors
        if hasattr(feed, "bozo_exception"):
            raise Exception(f"Failed to parse feed [{feed_url}] with error: {str(feed.bozo_exception)}")

        # Extract entries
        entries = []
        for entry in feed.entries[:limit]:
            entries.append(
                {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "description": entry.get("description", ""),
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                }
            )

        return {"feed_title": feed.feed.get("title", ""), "feed_link": feed.feed.get("link", ""), "entries": entries}
