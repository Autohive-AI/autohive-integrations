from typing import Any, Dict
from urllib.request import Request, urlopen

import atoma
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

# Create the integration using the config.json
rss_reader = Integration.load()


def _as_feed_bytes(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    raise ValueError("Feed response must be text or bytes")


def _date_to_string(value: Any) -> str:
    return value.isoformat() if value else ""


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value) or "")


def build_http_basic_auth_url(url: str, user_name: str, password: str) -> str:
    """Build a URL with HTTP basic authentication."""
    if url.startswith("http://"):
        protocol = "http://"
        domain_part = url[7:]
    elif url.startswith("https://"):
        protocol = "https://"
        domain_part = url[8:]
    else:
        protocol = "http://"
        domain_part = url

    return f"{protocol}{user_name}:{password}@{domain_part}"


def redact_secret_values(message: str, *secrets: str | None) -> str:
    """Remove credential values from user-facing error messages."""
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def fetch_feed(feed_url: str) -> bytes:
    """Fetch feed bytes using the standard library for this legacy direct-fetch integration."""
    request = Request(feed_url, headers={"User-Agent": "Autohive RSS Reader/2.0"})
    with urlopen(request, timeout=30) as response:  # nosec B310 - user-provided feed URL is the action input.
        return response.read()


def parse_feed(data: Any) -> Dict[str, Any]:
    """Parse RSS or Atom feed data into the integration's output shape."""
    feed_data = _as_feed_bytes(data)

    try:
        rss_feed = atoma.parse_rss_bytes(feed_data)
        return {
            "feed_title": rss_feed.title or "",
            "feed_link": rss_feed.link or "",
            "entries": [
                {
                    "title": item.title or "",
                    "link": item.link or "",
                    "description": item.description or item.content_encoded or "",
                    "published": _date_to_string(item.pub_date),
                    "author": item.author or "",
                }
                for item in rss_feed.items
            ],
        }
    except Exception as rss_error:
        try:
            atom_feed = atoma.parse_atom_bytes(feed_data)
            feed_link = atom_feed.links[0].href if atom_feed.links else ""
            return {
                "feed_title": _text_value(atom_feed.title),
                "feed_link": feed_link,
                "entries": [
                    {
                        "title": _text_value(entry.title),
                        "link": entry.links[0].href if entry.links else "",
                        "description": _text_value(entry.summary or entry.content),
                        "published": _date_to_string(entry.published or entry.updated),
                        "author": entry.authors[0].name if entry.authors else "",
                    }
                    for entry in atom_feed.entries
                ],
            }
        except Exception as atom_error:
            raise ValueError(f"Failed to parse feed as RSS or Atom: {rss_error}; {atom_error}") from atom_error


# ---- Action Handlers ----
@rss_reader.action("get_feed")
class GetFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        user_name = None
        password = None
        try:
            feed_url = inputs["feed_url"]
            limit = inputs.get("limit", 10)

            creds = context.auth.get("credentials", {}) if context.auth else {}
            user_name = creds.get("user_name")
            password = creds.get("password")
            if user_name and password:
                feed_url = build_http_basic_auth_url(feed_url, user_name, password)

            data = parse_feed(fetch_feed(feed_url))
            data["entries"] = data["entries"][:limit]

            return ActionResult(data=data)
        except Exception as e:
            return ActionError(message=redact_secret_values(str(e), user_name, password))
