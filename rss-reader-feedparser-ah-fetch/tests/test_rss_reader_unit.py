"""
Unit tests for the RSS Reader integration using mocked fetch.

Run with:
    pytest rss-reader-feedparser-ah-fetch/tests/test_rss_reader_unit.py -m unit
"""

import os
import sys

import pytest
from autohive_integrations_sdk import ResultType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rss_reader import rss_reader  # noqa: E402

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
      <published>2025-01-01T00:00:00Z</published>
    </item>
  </channel>
</rss>
"""


async def test_get_feed_reads_wrapped_credentials(make_context):
    """Production sends the wrapped Custom auth envelope; the handler must
    read basic-auth credentials from context.auth["credentials"], not from
    the top-level auth dict.
    """
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"user_name": "test_user", "password": "test_password"},
        }
    )
    ctx.fetch.return_value = SAMPLE_FEED
    result = await rss_reader.execute_action(
        "get_feed", {"feed_url": "https://example.com/feed", "limit": 10}, ctx
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["feed_title"] == "Test Feed"
    assert len(data["entries"]) == 1
    assert data["entries"][0]["title"] == "Entry One"
    # Basic-auth credentials should have been baked into the fetched URL.
    fetched_url = ctx.fetch.call_args.args[0]
    assert "test_user:test_password@" in fetched_url
