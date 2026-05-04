"""
End-to-end integration tests for the App Business Reviews integration.

These tests call the real SerpApi API and require a valid API key
set in the APP_BUSINESS_REVIEWS_API_KEY environment variable (via .env or export).

Run with:
    pytest app-business-reviews/tests/test_app_business_reviews_integration.py -m integration

Never runs in CI -- the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
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
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": API_KEY}}
    return ctx


# ---- Read-Only Tests ----


class TestSearchAppsIos:
    async def test_returns_apps(self, live_context):
        result = await abr.execute_action(
            "search_apps_ios",
            {"term": "WhatsApp", "country": "us", "num": 3},
            live_context,
        )

        data = result.result.data
        assert "apps" in data
        assert isinstance(data["apps"], list)

    async def test_num_limit_respected(self, live_context):
        result = await abr.execute_action(
            "search_apps_ios",
            {"term": "Instagram", "num": 2},
            live_context,
        )

        data = result.result.data
        assert data["total_results"] <= 2


class TestSearchAppsAndroid:
    async def test_returns_apps(self, live_context):
        result = await abr.execute_action(
            "search_apps_android",
            {"query": "WhatsApp"},
            live_context,
        )

        data = result.result.data
        assert "apps" in data
        assert isinstance(data["apps"], list)

    async def test_limit_respected(self, live_context):
        result = await abr.execute_action(
            "search_apps_android",
            {"query": "Spotify", "limit": 2},
            live_context,
        )

        data = result.result.data
        assert data["total_results"] <= 2


class TestSearchPlacesGoogleMaps:
    async def test_returns_places(self, live_context):
        result = await abr.execute_action(
            "search_places_google_maps",
            {"query": "coffee Sydney"},
            live_context,
        )

        data = result.result.data
        assert "places" in data
        assert isinstance(data["places"], list)

    async def test_location_filters_results(self, live_context):
        result = await abr.execute_action(
            "search_places_google_maps",
            {"query": "pizza", "location": "New York, NY", "num_results": 3},
            live_context,
        )

        data = result.result.data
        assert "places" in data
        assert data["total_results"] <= 3


class TestGetReviewsAppStore:
    async def test_returns_reviews_for_whatsapp(self, live_context):
        # First get a real product ID from search
        search_result = await abr.execute_action("search_apps_ios", {"term": "WhatsApp", "num": 1}, live_context)
        apps = search_result.result.data["apps"]
        if not apps:
            pytest.skip("No iOS apps returned from search")

        product_id = str(apps[0]["id"])

        result = await abr.execute_action(
            "get_reviews_app_store",
            {"product_id": product_id, "max_pages": 1},
            live_context,
        )

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert "product_id" in data

    async def test_auto_resolve_by_app_name(self, live_context):
        result = await abr.execute_action(
            "get_reviews_app_store",
            {"app_name": "WhatsApp", "max_pages": 1},
            live_context,
        )

        data = result.result.data
        assert "reviews" in data
        assert "app_name" in data


class TestGetReviewsGooglePlay:
    async def test_returns_reviews_for_whatsapp(self, live_context):
        result = await abr.execute_action(
            "get_reviews_google_play",
            {"product_id": "com.whatsapp", "max_pages": 1},
            live_context,
        )

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert data["product_id"] == "com.whatsapp"

    async def test_auto_resolve_by_app_name(self, live_context):
        result = await abr.execute_action(
            "get_reviews_google_play",
            {"app_name": "WhatsApp", "max_pages": 1},
            live_context,
        )

        data = result.result.data
        assert "reviews" in data
        assert "product_id" in data


class TestGetReviewsGoogleMaps:
    async def test_returns_reviews_chained_from_search(self, live_context):
        # Get a real place_id from search
        search_result = await abr.execute_action(
            "search_places_google_maps",
            {"query": "Starbucks Sydney", "num_results": 1},
            live_context,
        )
        places = search_result.result.data["places"]
        if not places:
            pytest.skip("No places returned from search")

        place = places[0]
        identifier = {"place_id": place["place_id"]} if place.get("place_id") else {"data_id": place["data_id"]}

        result = await abr.execute_action("get_reviews_google_maps", {**identifier, "max_pages": 1}, live_context)

        data = result.result.data
        assert "reviews" in data
        assert "total_reviews" in data
        assert "business_name" in data

    async def test_response_structure(self, live_context):
        search_result = await abr.execute_action(
            "search_places_google_maps",
            {"query": "McDonald's Melbourne", "num_results": 1},
            live_context,
        )
        places = search_result.result.data["places"]
        if not places:
            pytest.skip("No places returned from search")

        place = places[0]
        identifier = {"place_id": place["place_id"]} if place.get("place_id") else {"data_id": place["data_id"]}

        result = await abr.execute_action("get_reviews_google_maps", {**identifier, "max_pages": 1}, live_context)

        data = result.result.data
        assert "reviews" in data
        assert "average_rating" in data
        assert "place_id" in data
