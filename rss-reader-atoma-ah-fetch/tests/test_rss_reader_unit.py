import importlib.util
import os

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

_INTEGRATION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SPEC = importlib.util.spec_from_file_location(
    "rss_reader_atoma_ah_fetch_mod", os.path.join(_INTEGRATION_DIR, "rss_reader.py")
)
rss_reader_module = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(rss_reader_module)

build_api_token_header = rss_reader_module.build_api_token_header
build_http_basic_auth_url = rss_reader_module.build_http_basic_auth_url
parse_feed = rss_reader_module.parse_feed
redact_secret_values = rss_reader_module.redact_secret_values
rss_reader = rss_reader_module.rss_reader

pytestmark = pytest.mark.unit

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Entry One</title>
      <link>https://example.com/1</link>
      <description>First entry</description>
      <pubDate>Wed, 01 Jan 2025 00:00:00 GMT</pubDate>
      <author>Alice</author>
    </item>
    <item>
      <title>Entry Two</title>
      <link>https://example.com/2</link>
      <description>Second entry</description>
      <pubDate>Thu, 02 Jan 2025 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>feed-1</id>
  <title>Atom Feed</title>
  <link href="https://example.com/atom" />
  <updated>2025-01-01T00:00:00Z</updated>
  <entry>
    <id>entry-1</id>
    <title>Atom Entry</title>
    <link href="https://example.com/atom/1" />
    <summary>Atom entry summary</summary>
    <updated>2025-01-03T00:00:00Z</updated>
    <author><name>Bob</name></author>
  </entry>
</feed>
"""


def custom_auth(credentials: dict[str, str]) -> dict[str, object]:
    return {"auth_type": "Custom", "credentials": credentials}


def feed_response(data: str = SAMPLE_FEED) -> FetchResponse:
    return FetchResponse(status=200, headers={}, data=data)


def test_build_http_basic_auth_url_with_https():
    assert build_http_basic_auth_url("https://example.com/feed", "user", "pass") == "https://user:pass@example.com/feed"


def test_build_http_basic_auth_url_adds_default_http_scheme():
    assert build_http_basic_auth_url("example.com/feed", "user", "pass") == "http://user:pass@example.com/feed"


def test_build_api_token_header():
    assert build_api_token_header("test-token") == {"Authorization": "Bearer test-token"}  # nosec B105


def test_redact_secret_values():
    message = "Request failed for https://user:secret@example.com/feed with token test-token"

    redacted = redact_secret_values(message, "user", "secret", "test-token")  # nosec B105

    assert "user" not in redacted
    assert "secret" not in redacted
    assert "test-token" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_parse_feed_supports_atom():
    assert parse_feed(SAMPLE_ATOM_FEED) == {
        "feed_title": "Atom Feed",
        "feed_link": "https://example.com/atom",
        "entries": [
            {
                "title": "Atom Entry",
                "link": "https://example.com/atom/1",
                "description": "Atom entry summary",
                "published": "2025-01-03T00:00:00+00:00",
                "author": "Bob",
            }
        ],
    }


@pytest.mark.asyncio
async def test_get_feed_without_auth(make_context):
    ctx = make_context(auth=custom_auth({}))
    ctx.fetch.return_value = feed_response()

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION
    assert result.result.data == {
        "feed_title": "Test Feed",
        "feed_link": "https://example.com",
        "entries": [
            {
                "title": "Entry One",
                "link": "https://example.com/1",
                "description": "First entry",
                "published": "2025-01-01T00:00:00+00:00",
                "author": "Alice",
            },
            {
                "title": "Entry Two",
                "link": "https://example.com/2",
                "description": "Second entry",
                "published": "2025-01-02T00:00:00+00:00",
                "author": "",
            },
        ],
    }
    ctx.fetch.assert_awaited_once_with("https://example.com/feed")


@pytest.mark.asyncio
async def test_get_feed_respects_limit(make_context):
    ctx = make_context(auth=custom_auth({}))
    ctx.fetch.return_value = feed_response()

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed", "limit": 1}, ctx)

    assert result.type == ResultType.ACTION
    assert len(result.result.data["entries"]) == 1
    assert result.result.data["entries"][0]["title"] == "Entry One"


@pytest.mark.asyncio
async def test_get_feed_uses_basic_auth_url(make_context):
    ctx = make_context(auth=custom_auth({"user_name": "test_user", "password": "test_password"}))  # nosec B105
    ctx.fetch.return_value = feed_response()

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION
    ctx.fetch.assert_awaited_once_with("https://test_user:test_password@example.com/feed")


@pytest.mark.asyncio
async def test_get_feed_uses_bearer_token_header(make_context):
    ctx = make_context(auth=custom_auth({"api_token": "test_token"}))  # nosec B105
    ctx.fetch.return_value = feed_response()

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION
    ctx.fetch.assert_awaited_once_with(
        "https://example.com/feed",
        headers={"Authorization": "Bearer test_token"},
    )


@pytest.mark.asyncio
async def test_get_feed_prefers_basic_auth_over_bearer_token(make_context):
    ctx = make_context(
        auth=custom_auth(
            {
                "user_name": "test_user",
                "password": "test_password",  # nosec B105
                "api_token": "test_token",  # nosec B105
            }
        )
    )
    ctx.fetch.return_value = feed_response()

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION
    ctx.fetch.assert_awaited_once_with("https://test_user:test_password@example.com/feed")


@pytest.mark.asyncio
async def test_get_feed_returns_action_error_for_fetch_exception(make_context):
    ctx = make_context(auth=custom_auth({}))
    ctx.fetch.side_effect = Exception("Network error")

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION_ERROR
    assert "Network error" in result.result.message


@pytest.mark.asyncio
async def test_get_feed_returns_action_error_for_parse_failure(make_context):
    ctx = make_context(auth=custom_auth({}))
    ctx.fetch.return_value = feed_response("not xml")

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION_ERROR
    assert "Failed to parse feed" in result.result.message


@pytest.mark.asyncio
async def test_get_feed_parse_error_does_not_leak_basic_auth_credentials(make_context):
    ctx = make_context(auth=custom_auth({"user_name": "test_user", "password": "test_password"}))  # nosec B105
    ctx.fetch.return_value = feed_response("not xml")

    result = await rss_reader.execute_action("get_feed", {"feed_url": "https://example.com/feed"}, ctx)

    assert result.type == ResultType.ACTION_ERROR
    assert "Failed to parse feed" in result.result.message
    assert "test_user" not in result.result.message
    assert "test_password" not in result.result.message
