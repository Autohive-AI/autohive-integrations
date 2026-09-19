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

import base64
import json

import pytest
from autohive_integrations_sdk import ExecutionContext
from autohive_integrations_sdk.integration import ResultType

from openrouteservice.openrouteservice import openrouteservice

pytestmark = pytest.mark.integration

AUCKLAND_ADDRESS = "1 Queen Street, Auckland"
AUCKLAND_LATITUDE = -36.8485
AUCKLAND_LONGITUDE = 174.7633


@pytest.fixture
async def live_context(env_credentials):
    api_key = env_credentials("OPENROUTESERVICE_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTESERVICE_API_KEY not set — skipping integration tests")

    async with ExecutionContext(auth={"auth_type": "Custom", "credentials": {"api_key": api_key}}) as context:
        yield context


def _require_provider_success(result):
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result.result)
    data = result.result.data
    if data.get("error_type") in {"rate_limit", "quota_exceeded", "quota_or_unauthorized"}:
        pytest.skip(f"OpenRouteService limited this request: {data.get('message')}")
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
        bands = [feature["properties"].get("time_minutes") for feature in data["geojson"]["features"]]
        assert all(isinstance(band, int) for band in bands)
        assert bands == sorted(bands)
        for feature in data["geojson"]["features"]:
            assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert "attribution" in data
        assert "engine_version" in data
        assert "graph_date" in data

    async def test_export_geojson_is_a_platform_file_without_credentials(self, live_context, env_credentials):
        result = await openrouteservice.execute_action(
            "get_isochrone",
            {
                "latitude": AUCKLAND_LATITUDE,
                "longitude": AUCKLAND_LONGITUDE,
                "time_minutes": [5],
                "export_geojson": True,
            },
            live_context,
        )
        data = _require_provider_success(result)
        files = data["files"]
        assert len(files) == 1
        file_obj = files[0]
        assert file_obj["name"] == "isochrones.geojson"
        assert "geo+json" in file_obj["contentType"] or file_obj["contentType"] == "application/json"
        raw = base64.b64decode(file_obj["content"])
        api_key = env_credentials("OPENROUTESERVICE_API_KEY")
        assert api_key.encode("utf-8") not in raw
        assert b"Authorization" not in raw
        exported = json.loads(raw)
        assert exported["type"] == "FeatureCollection"
        assert exported["features"]
        feature = exported["features"][0]
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert feature["properties"]["time_minutes"] == 5


class TestGetTravelTimeMatrix:
    async def test_returns_auckland_driving_pairs_with_ids(self, live_context):
        result = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {
                "origins": [
                    {"id": "queen-st", "latitude": AUCKLAND_LATITUDE, "longitude": AUCKLAND_LONGITUDE},
                ],
                "destinations": [
                    {"id": "britomart", "latitude": -36.8443, "longitude": 174.7674},
                    {"id": "ponsonby", "latitude": -36.8506, "longitude": 174.7464},
                ],
                "include_distance": True,
            },
            live_context,
        )
        data = _require_provider_success(result)

        assert data["profile"] == "driving-car"
        assert data["metrics"] == ["duration", "distance"]
        assert [pair["origin_id"] for pair in data["pairs"]] == ["queen-st", "queen-st"]
        assert [pair["destination_id"] for pair in data["pairs"]] == ["britomart", "ponsonby"]
        for pair in data["pairs"]:
            assert isinstance(pair["duration_seconds"], (int, float))
            assert pair["duration_seconds"] > 0
            assert isinstance(pair["distance_metres"], (int, float))
            assert pair["distance_metres"] > 0
        assert data["origins"][0]["id"] == "queen-st"
        assert data["destinations"][0]["id"] == "britomart"
        assert "attribution" in data
        assert data["files"] == []

    async def test_unreachable_destination_is_null(self, live_context):
        result = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {
                "origins": [
                    {"id": "queen-st", "latitude": AUCKLAND_LATITUDE, "longitude": AUCKLAND_LONGITUDE},
                ],
                "destinations": [
                    {"id": "britomart", "latitude": -36.8443, "longitude": 174.7674},
                    {"id": "ocean", "latitude": 0.0, "longitude": 0.0},
                ],
            },
            live_context,
        )
        data = _require_provider_success(result)
        by_id = {pair["destination_id"]: pair for pair in data["pairs"]}
        assert isinstance(by_id["britomart"]["duration_seconds"], (int, float))
        assert by_id["ocean"]["duration_seconds"] is None
        assert by_id["ocean"]["distance_metres"] is None
        assert data["unreachable_count"] >= 1

    async def test_export_json_is_a_platform_file_without_credentials(self, live_context, env_credentials):
        result = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {
                "origins": [
                    {"id": "queen-st", "latitude": AUCKLAND_LATITUDE, "longitude": AUCKLAND_LONGITUDE},
                ],
                "destinations": [
                    {"id": "britomart", "latitude": -36.8443, "longitude": 174.7674},
                ],
                "export_format": "json",
            },
            live_context,
        )
        data = _require_provider_success(result)
        files = data["files"]
        assert len(files) == 1
        file_obj = files[0]
        assert file_obj["name"] == "travel_time_matrix.json"
        raw = base64.b64decode(file_obj["content"])
        api_key = env_credentials("OPENROUTESERVICE_API_KEY")
        assert api_key.encode("utf-8") not in raw
        assert b"Authorization" not in raw
        exported = json.loads(raw)
        assert exported["pairs"][0]["origin_id"] == "queen-st"
        assert "files" not in exported
