from typing import Any, Dict

import atoma
import defusedxml.ElementTree as ET
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

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


def build_api_token_header(api_token: str) -> Dict[str, str]:
    """
    Build a header with API token authentication.
    """
    return {"Authorization": f"Bearer {api_token}"}


def redact_secret_values(message: str, *secrets: str | None) -> str:
    """Remove credential values from user-facing error messages."""
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


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


def _atom_link(links: list[Any]) -> str:
    for link in links:
        if getattr(link, "rel", None) in (None, "alternate"):
            return link.href
    return links[0].href if links else ""


def _xml_text(element: Any, path: str, namespaces: Dict[str, str]) -> str:
    child = element.find(path, namespaces)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _rss_item_metadata(data: bytes) -> list[Dict[str, str]]:
    """Read namespaced RSS 2.0 item metadata that Atoma does not expose."""
    namespaces = {
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    try:
        root = ET.fromstring(data)
    except Exception:
        return []

    return [
        {
            "author": _xml_text(item, "dc:creator", namespaces),
            "published": _xml_text(item, "dc:date", namespaces),
        }
        for item in root.findall("./channel/item")
    ]


def parse_rss1_feed(data: bytes) -> Dict[str, Any]:
    """Parse RSS 1.0/RDF feed data into the integration's output shape."""
    namespaces = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rss": "http://purl.org/rss/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }
    root = ET.fromstring(data)

    if root.tag != f"{{{namespaces['rdf']}}}RDF":
        raise ValueError("Feed is not RSS 1.0/RDF")

    channel = root.find("rss:channel", namespaces)
    if channel is None:
        raise ValueError("RSS 1.0/RDF feed is missing a channel")

    return {
        "feed_title": _xml_text(channel, "rss:title", namespaces),
        "feed_link": _xml_text(channel, "rss:link", namespaces),
        "entries": [
            {
                "title": _xml_text(item, "rss:title", namespaces),
                "link": _xml_text(item, "rss:link", namespaces),
                "description": _xml_text(item, "rss:description", namespaces)
                or _xml_text(item, "content:encoded", namespaces),
                "published": _xml_text(item, "dc:date", namespaces),
                "author": _xml_text(item, "dc:creator", namespaces),
            }
            for item in root.findall("rss:item", namespaces)
        ],
    }


def parse_feed(data: Any) -> Dict[str, Any]:
    """Parse RSS or Atom feed data into the integration's output shape."""
    feed_data = _as_feed_bytes(data)

    try:
        rss_feed = atoma.parse_rss_bytes(feed_data)
        item_metadata = _rss_item_metadata(feed_data)
        return {
            "feed_title": rss_feed.title or "",
            "feed_link": rss_feed.link or "",
            "entries": [
                {
                    "title": item.title or "",
                    "link": item.link or "",
                    "description": item.description or item.content_encoded or "",
                    "published": _date_to_string(item.pub_date)
                    or (item_metadata[index]["published"] if index < len(item_metadata) else ""),
                    "author": item.author or (item_metadata[index]["author"] if index < len(item_metadata) else ""),
                }
                for index, item in enumerate(rss_feed.items)
            ],
        }
    except Exception as rss_error:
        try:
            return parse_rss1_feed(feed_data)
        except Exception as rss1_error:
            try:
                atom_feed = atoma.parse_atom_bytes(feed_data)
            except Exception as atom_error:
                raise ValueError(
                    f"Failed to parse feed as RSS 2.0, RSS 1.0/RDF, or Atom: {rss_error}; {rss1_error}; {atom_error}"
                ) from atom_error

            feed_link = _atom_link(atom_feed.links)
            return {
                "feed_title": _text_value(atom_feed.title),
                "feed_link": feed_link,
                "entries": [
                    {
                        "title": _text_value(entry.title),
                        "link": _atom_link(entry.links),
                        "description": _text_value(entry.summary or entry.content),
                        "published": _date_to_string(entry.published or entry.updated),
                        "author": entry.authors[0].name if entry.authors else "",
                    }
                    for entry in atom_feed.entries
                ],
            }


# ---- Action Handlers ----
@rss_reader.action("get_feed")
class GetFeedAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        user_name = None
        password = None
        api_token = None
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

            data = parse_feed(response.data)
            data["entries"] = data["entries"][:limit]

            return ActionResult(data=data)
        except Exception as e:
            return ActionError(message=redact_secret_values(str(e), user_name, password, api_token))
