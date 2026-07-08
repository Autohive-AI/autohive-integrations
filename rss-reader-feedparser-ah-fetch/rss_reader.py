import feedparser
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration
from typing import Any, Dict

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
        try:
            feed_url = inputs["feed_url"]
            limit = inputs.get("limit", 10)

            creds = context.auth["credentials"]
            user_name = creds.get("user_name")
            password = creds.get("password")
            api_token = creds.get("api_token")

            # Determine authentication method based on available credentials.
            if user_name and password:
                feed_url = build_http_basic_auth_url(feed_url, user_name, password)
                response = await context.fetch(feed_url)
            elif api_token:
                headers = build_api_token_header(api_token)
                response = await context.fetch(feed_url, headers=headers)
            else:
                response = await context.fetch(feed_url)

            feed = feedparser.parse(response.data)

            if hasattr(feed, "bozo_exception"):
                raise ValueError(f"Failed to parse feed [{feed_url}] with error: {feed.bozo_exception}")

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

            return ActionResult(
                data={
                    "feed_title": feed.feed.get("title", ""),
                    "feed_link": feed.feed.get("link", ""),
                    "entries": entries,
                }
            )
        except Exception as e:
            return ActionError(message=str(e))
