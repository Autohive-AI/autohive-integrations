"""
End-to-end integration tests for the OpenRouteService integration.

These tests call the real OpenRouteService API and require a valid API key
in the OPENROUTESERVICE_API_KEY environment variable (via .env or export).

Create a free key at https://openrouteservice.org/dev/#/signup

All tests here are read-only. Run with:
    pytest openrouteservice/tests/test_openrouteservice_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from openrouteservice.openrouteservice import openrouteservice

pytestmark = pytest.mark.integration

AUCKLAND_ADDRESS = "1 Queen Street, Auckland"
AUCKLAND_LATITUDE = -36.8485
AUCKLAND_LONGITUDE = 174.7633


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("OPENROUTESERVICE_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTESERVICE_API_KEY not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    context = make_context(auth={"auth_type": "Custom", "credentials": {"api_key": api_key}})
    context.fetch.side_effect = real_fetch
    return context


def _require_provider_success(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    data = result.result.data
    if data.get("error_type") == "rate_limit":
        pytest.skip(f"OpenRouteService rate-limited this request: {data.get('message')}")
    if data.get("error_type") == "authorization":
        pytest.skip(f"OpenRouteService denied this endpoint for the configured key: {data.get('message')}")
    assert data.get("result") is True, data.get("message")
    return data


class TestGeocodeAddress:
    async def test_geocodes_a_new_zealand_address(self, live_context):
        result = await openrouteservice.execute_action("geocode_address", {"address": AUCKLAND_ADDRESS}, live_context)
        data = _require_provider_success(result)

        assert data["found"] is True
        assert isinstance(data["address"], str) and data["address"]
        assert isinstance(data["latitude"], (int, float))
        assert isinstance(data["longitude"], (int, float))
        assert -48 <= data["latitude"] <= -34
        assert 166 <= data["longitude"] <= 179
        assert isinstance(data["matches"], list) and data["matches"]

    async def test_geocode_response_shape(self, live_context):
        result = await openrouteservice.execute_action("geocode_address", {"address": AUCKLAND_ADDRESS}, live_context)
        data = _require_provider_success(result)

        for key in (
            "result",
            "found",
            "address",
            "latitude",
            "longitude",
            "confidence",
            "match_type",
            "is_low_confidence",
            "matches",
            "geocoding",
            "error_type",
            "retry_after_seconds",
            "message",
        ):
            assert key in data
        assert data["matches"][0]["feature"]["type"] == "Feature"


class TestGetIsochrone:
    async def test_returns_drive_time_geojson_for_auckland(self, live_context):
        result = await openrouteservice.execute_action(
            "get_isochrone",
            {
                "latitude": AUCKLAND_LATITUDE,
                "longitude": AUCKLAND_LONGITUDE,
                "time_minutes": [10],
            },
            live_context,
        )
        data = _require_provider_success(result)

        assert data["profile"] == "driving-car"
        assert data["time_minutes"] == [10]
        geojson = data["geojson"]
        assert geojson["type"] == "FeatureCollection"
        assert isinstance(geojson.get("features"), list)
        assert geojson["features"]
        assert geojson["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}

    async def test_isochrone_response_shape(self, live_context):
        result = await openrouteservice.execute_action(
            "get_isochrone",
            {
                "latitude": AUCKLAND_LATITUDE,
                "longitude": AUCKLAND_LONGITUDE,
                "time_minutes": [10, 15],
            },
            live_context,
        )
        data = _require_provider_success(result)

        for key in (
            "result",
            "profile",
            "time_minutes",
            "geojson",
            "provider_metadata",
            "error_type",
            "retry_after_seconds",
            "message",
        ):
            assert key in data
        assert data["time_minutes"] == [10, 15]
        assert len(data["geojson"]["features"]) >= 1
