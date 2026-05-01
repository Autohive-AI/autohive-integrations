"""
Integration tests for the App Business Reviews integration (SerpApi).

Requires APP_BUSINESS_REVIEWS_API_KEY set in environment or .env file.

Run with:
    pytest app-business-reviews/tests/test_app_business_reviews_integration.py -m integration
"""

import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
os.chdir(_parent)
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("abr_mod", os.path.join(_parent, "app_business_reviews.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

abr = _mod.app_business_reviews

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("APP_BUSINESS_REVIEWS_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("APP_BUSINESS_REVIEWS_API_KEY not set - skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                data = await resp.json()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": API_KEY}}
    return ctx


class TestSearchAppsIos:
    @pytest.mark.asyncio
    async def test_returns_apps(self, live_context):
        result = await abr.execute_action(
            "search_apps_ios",
            {"term": "WhatsApp", "country": "us", "num": 3},
            live_context,
        )

        data = result.result.data
        assert "apps" in data
        assert isinstance(data["apps"], list)


class TestSearchAppsAndroid:
    @pytest.mark.asyncio
    async def test_returns_apps(self, live_context):
        result = await abr.execute_action(
            "search_apps_android",
            {"query": "WhatsApp"},
            live_context,
        )

        data = result.result.data
        assert "apps" in data
        assert isinstance(data["apps"], list)


class TestSearchPlacesGoogleMaps:
    @pytest.mark.asyncio
    async def test_returns_places(self, live_context):
        result = await abr.execute_action(
            "search_places_google_maps",
            {"query": "coffee Sydney"},
            live_context,
        )

        data = result.result.data
        assert "places" in data
        assert isinstance(data["places"], list)
