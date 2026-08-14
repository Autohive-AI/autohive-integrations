"""
End-to-end integration tests for the RSS Reader integration.

These tests call real RSS feed URLs. The default read-only tests use a public
feed and require no credentials. Optional environment variables can point the
tests at a specific public or Basic Auth protected feed.

Run with:
    pytest rss-reader-atoma-ah-fetch/tests/test_rss_reader_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import importlib.util
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

_INTEGRATION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SPEC = importlib.util.spec_from_file_location(
    "rss_reader_atoma_ah_fetch_integration_mod", os.path.join(_INTEGRATION_DIR, "rss_reader.py")
)
rss_reader_module = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(rss_reader_module)

rss_reader = rss_reader_module.rss_reader

pytestmark = pytest.mark.integration

DEFAULT_PUBLIC_FEED_URL = "https://xkcd.com/rss.xml"


@pytest.fixture
def live_context():
    """Execution context wired to a real HTTP client via aiohttp."""
    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                data = await resp.text()
                if resp.status >= 400:
                    raise Exception(f"HTTP {resp.status}: {data[:200]}")
                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=data,
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"auth_type": "Custom", "credentials": {}}
    return ctx


def public_feed_url() -> str:
    return os.environ.get("RSS_READER_TEST_FEED_URL") or DEFAULT_PUBLIC_FEED_URL


# ---- Read-Only Public Feed Tests ----


class TestGetFeedPublic:
    async def test_fetches_public_feed(self, live_context):
        result = await rss_reader.execute_action("get_feed", {"feed_url": public_feed_url(), "limit": 3}, live_context)

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

    async def test_respects_limit_against_public_feed(self, live_context):
        result = await rss_reader.execute_action("get_feed", {"feed_url": public_feed_url(), "limit": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["entries"]) <= 1


# ---- Optional Basic Auth Feed Test ----


class TestGetFeedBasicAuth:
    async def test_fetches_basic_auth_feed_when_configured(self, live_context, env_credentials):
        feed_url = env_credentials("RSS_READER_BASIC_AUTH_FEED_URL")
        user_name = env_credentials("RSS_READER_BASIC_AUTH_USER_NAME")
        password = env_credentials("RSS_READER_BASIC_AUTH_PASSWORD")
        if not feed_url or not user_name or not password:
            pytest.skip("RSS_READER_BASIC_AUTH_* variables not set")

        live_context.auth = {
            "auth_type": "Custom",
            "credentials": {"user_name": user_name, "password": password},
        }

        result = await rss_reader.execute_action("get_feed", {"feed_url": feed_url, "limit": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert "entries" in result.result.data
        assert len(result.result.data["entries"]) <= 1
