# rss-reader.py
from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any
import feedparser

# Create the integration using the config.json
rss_reader = Integration.load()


def build_http_basic_auth_url(url: str, user_name: str, password: str) -> str:
    """
    Build a URL with HTTP basic authentication.
    """
    if url.startswith("http://"):
        protocol = "http://"
        domain_part = url[7:]  # Remove 'http://'
    elif url.startswith("https://"):
        protocol = "https://"
        domain_part = url[8:]  # Remove 'https://'
    else:
        protocol = "http://"
        domain_part = url

    return f"{protocol}{user_name}:{password}@{domain_part}"


def build_api_token_header(api_token: str) -> str:
    """
    Build a header with API token authentication.
    """
    return {"Authorization": f"Bearer {api_token}"}


# ---- Action Handlers ----
@rss_reader.action("get_feed")
class GetFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        feed_url = inputs["feed_url"]
        limit = inputs.get("limit", 10)

        user_name = context.auth.get("user_name")
        password = context.auth.get("password")
        api_token = context.auth.get("api_token")

        # Determine authentication method based on available credentials
        # Variables nned to hold None if keys are missing by using .get() before this block
        if user_name and password:
            # Use HTTP Basic Authentication via the 'auth' parameters
            feed_url = build_http_basic_auth_url(feed_url, user_name, password)
            response = await context.fetch(feed_url)
        elif api_token:
            # Use API Token Authentication via headers
            headers = build_api_token_header(api_token)
            response = await context.fetch(feed_url, headers=headers)
        else:
            # No authentication provided or required
            response = await context.fetch(feed_url)

        # Parse feed
        feed = feedparser.parse(response.data)

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

        return ActionResult(data={"feed_title": feed.feed.get("title", ""), "feed_link": feed.feed.get("link", ""), "entries": entries}, cost_usd=0)
