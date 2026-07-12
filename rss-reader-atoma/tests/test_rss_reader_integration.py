"""
End-to-end integration tests for the unsupported direct-fetch RSS Reader integration.

These tests call a real public RSS feed URL and require no credentials by default.
RSS_READER_TEST_FEED_URL can override the feed used by the read-only tests.

Run with:
    pytest rss-reader-atoma/tests/test_rss_reader_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib.util
import os

import pytest
from autohive_integrations_sdk import ResultType

_INTEGRATION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SPEC = importlib.util.spec_from_file_location(
    "rss_reader_atoma_integration_mod", os.path.join(_INTEGRATION_DIR, "rss_reader.py")
)
rss_reader_module = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(rss_reader_module)

rss_reader = rss_reader_module.rss_reader

pytestmark = pytest.mark.integration

DEFAULT_PUBLIC_FEED_URL = "https://xkcd.com/rss.xml"


def public_feed_url() -> str:
    return os.environ.get("RSS_READER_TEST_FEED_URL", DEFAULT_PUBLIC_FEED_URL)


class TestGetFeedPublic:
    async def test_fetches_public_feed(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {}})

        result = await rss_reader.execute_action("get_feed", {"feed_url": public_feed_url(), "limit": 3}, ctx)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "feed_title" in data
        assert "feed_link" in data
        assert "entries" in data
        assert 0 < len(data["entries"]) <= 3

        entry = data["entries"][0]
        assert "title" in entry
        assert "link" in entry
        assert "description" in entry
        assert "published" in entry
        assert "author" in entry

    async def test_respects_limit_against_public_feed(self, make_context):
        ctx = make_context(auth={"auth_type": "Custom", "credentials": {}})

        result = await rss_reader.execute_action("get_feed", {"feed_url": public_feed_url(), "limit": 1}, ctx)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["entries"]) <= 1
