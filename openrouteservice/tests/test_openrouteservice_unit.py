"""Unit tests for OpenRouteService integration actions."""

import base64
import json

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from openrouteservice.openrouteservice import (
    GEOCODE_URL,
    ISOCHRONE_TIMEOUT_SECONDS,
    ISOCHRONE_URL_TEMPLATE,
    MissingApiKeyError,
    _geojson_export_file,
    _match,
    _provider_error,
    openrouteservice,
)

pytestmark = pytest.mark.unit

GEOCODE_RESPONSE = {
    "type": "FeatureCollection",
    "geocoding": {"version": "0.2", "query": {"text": "1 Queen Street, Auckland"}},
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [174.7633, -36.8445]},
            "properties": {"label": "1 Queen Street, Auckland, New Zealand", "confidence": 0.95, "match_type": "exact"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [174.764, -36.845]},
            "properties": {
                "label": "Queen Street, Auckland, New Zealand",
                "confidence": 0.65,
                "match_type": "fallback",
            },
        },
    ],
}

ISOCHRONE_POLYGON = {"type": "Polygon", "coordinates": [[[174.76, -36.84], [174.77, -36.84], [174.76, -36.84]]]}
ISOCHRONE_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"group_index": 0, "value": 600},
            "geometry": ISOCHRONE_POLYGON,
        }
    ],
    "metadata": {
        "service": "isochrones",
        "attribution": "openrouteservice.org, OpenStreetMap contributors",
        "engine": {
            "version": "8.2.0",
            "build_date": "2025-01-02T00:00:00Z",
            "graph_date": "2025-01-01T00:00:00Z",
            "osm_date": "2024-12-15T00:00:00Z",
        },
    },
}


def _isochrone_collection(*minute_bands, metadata=None):
    features = []
    for minutes in minute_bands:
        features.append(
            {
                "type": "Feature",
                "properties": {"group_index": 0, "value": minutes * 60},
                "geometry": ISOCHRONE_POLYGON,
            }
        )
    payload = {"type": "FeatureCollection", "features": features}
    if metadata is not None:
        payload["metadata"] = metadata
    elif ISOCHRONE_RESPONSE.get("metadata"):
        payload["metadata"] = ISOCHRONE_RESPONSE["metadata"]
    return payload


ISOCHRONE_INPUTS = {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [10]}


def _action_data(result):
    assert result.type == ResultType.ACTION
    return result.result.data


class TestMatch:
    def test_prefers_label_and_reads_lon_lat_order(self):
        matched = _match(GEOCODE_RESPONSE["features"][0])

        assert matched["address"] == "1 Queen Street, Auckland, New Zealand"
        assert matched["longitude"] == 174.7633
        assert matched["latitude"] == -36.8445
        assert matched["is_low_confidence"] is False
        assert matched["feature"] == GEOCODE_RESPONSE["features"][0]

    def test_falls_back_to_name_when_label_is_missing(self):
        matched = _match(
            {
                "geometry": {"coordinates": [174.76, -36.84]},
                "properties": {"name": "Queen Street", "confidence": 0.9, "match_type": "exact"},
            }
        )

        assert matched["address"] == "Queen Street"

    def test_incomplete_coordinates_are_null(self):
        matched = _match({"geometry": {"coordinates": [174.76]}, "properties": {"label": "Partial", "confidence": 1}})

        assert matched["latitude"] is None
        assert matched["longitude"] is None

    def test_missing_confidence_is_low_confidence(self):
        matched = _match(
            {
                "geometry": {"coordinates": [174.76, -36.84]},
                "properties": {"label": "Somewhere", "match_type": "fallback"},
            }
        )

        assert matched["confidence"] is None
        assert matched["is_low_confidence"] is True

    def test_null_properties_geometry_and_coordinates_do_not_raise(self):
        matched = _match({"properties": None, "geometry": None})

        assert matched["address"] is None
        assert matched["latitude"] is None
        assert matched["longitude"] is None
        assert matched["confidence"] is None
        assert matched["is_low_confidence"] is True

    def test_null_coordinates_are_treated_as_incomplete(self):
        matched = _match(
            {
                "geometry": {"type": "Point", "coordinates": None},
                "properties": {"label": "No point", "confidence": 1},
            }
        )

        assert matched["address"] == "No point"
        assert matched["latitude"] is None
        assert matched["longitude"] is None

    def test_non_numeric_confidence_is_low_confidence(self):
        matched = _match(
            {
                "geometry": {"coordinates": [174.76, -36.84]},
                "properties": {"label": "Somewhere", "confidence": "high"},
            }
        )

        assert matched["confidence"] is None
        assert matched["is_low_confidence"] is True


class TestGeocodeAddress:
    async def test_geocodes_address_with_default_nz_boundary(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=GEOCODE_RESPONSE)

        result = await openrouteservice.execute_action(
            "geocode_address", {"address": "1 Queen Street, Auckland"}, mock_context
        )

        data = _action_data(result)
        assert data["found"] is True
        assert data["address"] == "1 Queen Street, Auckland, New Zealand"
        assert data["longitude"] == 174.7633
        assert data["latitude"] == -36.8445
        assert data["confidence"] == 0.95
        assert data["is_low_confidence"] is False
        assert data["error_type"] is None
        assert data["error_code"] is None
        assert data["field"] is None
        assert data["recovery"] is None
        assert data["retry_safe"] is None
        assert len(data["matches"]) == 2
        assert data["matches"][0]["feature"] == GEOCODE_RESPONSE["features"][0]
        mock_context.fetch.assert_awaited_once_with(
            GEOCODE_URL,
            method="GET",
            headers={"Authorization": "test-key", "Accept": "application/json"},
            params={"text": "1 Queen Street, Auckland", "boundary.country": "NZ"},
        )

    async def test_uses_supplied_country_boundary(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=GEOCODE_RESPONSE)

        await openrouteservice.execute_action(
            "geocode_address", {"address": "Queen Street", "country": "AU"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["params"]["boundary.country"] == "AU"

    async def test_flags_low_confidence_best_match(self, mock_context):
        response = {**GEOCODE_RESPONSE, "features": [GEOCODE_RESPONSE["features"][1]]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await openrouteservice.execute_action("geocode_address", {"address": "Queen Street"}, mock_context)

        data = _action_data(result)
        assert data["is_low_confidence"] is True
        assert data["message"] == "Confirm this match before downstream use."

    async def test_flags_missing_confidence_as_low_confidence(self, mock_context):
        response = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.76, -36.84]},
                    "properties": {"label": "Somewhere", "match_type": "fallback"},
                }
            ],
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await openrouteservice.execute_action("geocode_address", {"address": "Somewhere"}, mock_context)

        assert _action_data(result)["is_low_confidence"] is True

    async def test_returns_found_false_when_provider_returns_no_features(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"type": "FeatureCollection", "features": []}
        )

        result = await openrouteservice.execute_action(
            "geocode_address", {"address": "not a real location"}, mock_context
        )

        data = _action_data(result)
        assert data["result"] is True
        assert data["found"] is False
        assert data["matches"] == []
        assert data["message"] == "No matching address was found."

    async def test_skips_non_dict_features_in_a_valid_collection(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "type": "FeatureCollection",
                "features": ["not-a-feature", GEOCODE_RESPONSE["features"][0], None],
            },
        )
        result = await openrouteservice.execute_action("geocode_address", {"address": "Queen Street"}, mock_context)
        assert len(_action_data(result)["matches"]) == 1

    async def test_features_without_coordinates_are_not_found(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "type": "FeatureCollection",
                "geocoding": {"query": {"text": "Somewhere"}},
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"coordinates": [174.76]},
                        "properties": {"label": "Partial", "confidence": 1},
                    },
                    {"type": "Feature", "geometry": None, "properties": {"label": "Nowhere"}},
                ],
            },
        )

        result = await openrouteservice.execute_action("geocode_address", {"address": "Somewhere"}, mock_context)

        data = _action_data(result)
        assert data["result"] is True
        assert data["found"] is False
        assert data["latitude"] is None
        assert data["longitude"] is None
        assert data["matches"] == []
        assert data["message"] == "No matching address was found."

    async def test_skips_features_without_coordinates_when_a_point_exists(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"coordinates": [174.76]},
                        "properties": {"label": "Partial", "confidence": 1},
                    },
                    GEOCODE_RESPONSE["features"][0],
                ],
            },
        )

        result = await openrouteservice.execute_action("geocode_address", {"address": "Queen Street"}, mock_context)

        data = _action_data(result)
        assert data["found"] is True
        assert data["latitude"] == -36.8445
        assert data["longitude"] == 174.7633
        assert len(data["matches"]) == 1

    @pytest.mark.parametrize(
        "payload",
        [
            ["unexpected"],
            {"features": [GEOCODE_RESPONSE["features"][0]]},
            {"type": "FeatureCollection", "features": "not-a-list"},
        ],
    )
    async def test_rejects_malformed_geocode_response(self, mock_context, payload):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)

        result = await openrouteservice.execute_action("geocode_address", {"address": "Queen Street"}, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert "coordinates" not in data["message"].lower()
        assert "time bands" not in data["message"].lower()

    async def test_rejects_invalid_geocode_inputs(self, mock_context):
        missing = await openrouteservice.execute_action("geocode_address", {}, mock_context)
        assert missing.type == ResultType.VALIDATION_ERROR

        lowercase_country = await openrouteservice.execute_action(
            "geocode_address", {"address": "Auckland", "country": "nz"}, mock_context
        )
        assert lowercase_country.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    def test_uses_heigit_pelias_geocode_endpoint(self):
        assert GEOCODE_URL == "https://api.heigit.org/pelias/v1/search"


class TestGetIsochrone:
    def test_uses_explicit_geojson_provider_endpoint(self):
        assert ISOCHRONE_URL_TEMPLATE == "https://api.heigit.org/openrouteservice/v2/isochrones/{profile}"

    async def test_requests_all_time_bands_once_and_returns_sorted_polygons(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_isochrone_collection(30, 10, 15))

        result = await openrouteservice.execute_action(
            "get_isochrone",
            {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [30, 10, 15, 10]},
            mock_context,
        )

        data = _action_data(result)
        assert data["time_minutes"] == [10, 15, 30]
        assert data["profile"] == "driving-car"
        bands = [feature["properties"]["time_minutes"] for feature in data["geojson"]["features"]]
        assert bands == [10, 15, 30]
        for feature in data["geojson"]["features"]:
            assert feature["geometry"] == ISOCHRONE_POLYGON
            assert feature["properties"]["value"] in {600, 900, 1800}
        assert data["provider_metadata"] == ISOCHRONE_RESPONSE["metadata"]
        assert data["attribution"] == "openrouteservice.org, OpenStreetMap contributors"
        assert data["engine_version"] == "8.2.0"
        assert data["build_date"] == "2025-01-02T00:00:00Z"
        assert data["graph_date"] == "2025-01-01T00:00:00Z"
        assert data["osm_date"] == "2024-12-15T00:00:00Z"
        assert data["files"] == []
        assert data["error_type"] is None
        mock_context.fetch.assert_awaited_once_with(
            ISOCHRONE_URL_TEMPLATE.format(profile="driving-car"),
            method="POST",
            headers={
                "Authorization": "test-key",
                "Accept": "application/json, application/geo+json",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "locations": [[174.7633, -36.8485]],
                "range": [600, 900, 1800],
                "range_type": "time",
                "smoothing": 0,
            },
            timeout=ISOCHRONE_TIMEOUT_SECONDS,
            retry_count=3,
        )

    async def test_parses_geojson_string_response(self, mock_context):
        import json

        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=json.dumps(ISOCHRONE_RESPONSE))

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is True
        assert data["geojson"]["features"][0]["properties"]["time_minutes"] == 10
        assert data["geojson"]["features"][0]["geometry"] == ISOCHRONE_POLYGON

    async def test_rejects_non_geojson_provider_response(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"unexpected": "response"})

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert "coordinates" not in data["message"].lower()
        assert "time bands" not in data["message"].lower()

    @pytest.mark.parametrize(
        "payload",
        [
            {"type": "FeatureCollection"},
            {"type": "FeatureCollection", "features": "not-a-list"},
            {"type": "FeatureCollection", "features": None},
        ],
    )
    async def test_rejects_feature_collection_without_feature_array(self, mock_context, payload):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert "coordinates" not in data["message"].lower()
        assert "time bands" not in data["message"].lower()

    async def test_rejects_non_json_isochrone_string(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data="<html>not json</html>")

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert "<html>" not in data["message"]

    async def test_empty_feature_array_fails_when_bands_are_missing(self, mock_context):
        payload = {"type": "FeatureCollection", "features": [], "metadata": {"service": "isochrones"}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert data["error_code"] == "provider_error"
        assert data["retry_safe"] is False
        assert "10" in data["message"]

    async def test_rejects_invalid_isochrone_inputs(self, mock_context):
        cases = [
            {"longitude": 174.76, "time_minutes": [10]},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": []},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": [0]},
            {"latitude": 91, "longitude": 174.76, "time_minutes": [10]},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": [10], "travel_mode": "cycling-regular"},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": [61]},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": list(range(1, 12))},
        ]
        for inputs in cases:
            result = await openrouteservice.execute_action("get_isochrone", inputs, mock_context)
            assert result.type == ResultType.VALIDATION_ERROR, inputs
        mock_context.fetch.assert_not_called()

    async def test_five_bands_in_one_call(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=_isochrone_collection(5, 10, 15, 20, 30)
        )
        result = await openrouteservice.execute_action(
            "get_isochrone",
            {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [30, 5, 15, 10, 20]},
            mock_context,
        )
        data = _action_data(result)
        assert data["result"] is True
        assert [feature["properties"]["time_minutes"] for feature in data["geojson"]["features"]] == [5, 10, 15, 20, 30]

    async def test_rejects_non_polygon_geometry(self, mock_context):
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"value": 600},
                    "geometry": {"type": "Point", "coordinates": [174.76, -36.84]},
                }
            ],
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)
        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)
        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert "Polygon" in data["message"]

    async def test_export_geojson_returns_platform_file(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ISOCHRONE_RESPONSE)
        result = await openrouteservice.execute_action(
            "get_isochrone", {**ISOCHRONE_INPUTS, "export_geojson": True}, mock_context
        )
        data = _action_data(result)
        assert len(data["files"]) == 1
        file_obj = data["files"][0]
        assert file_obj["name"] == "isochrones.geojson"
        assert file_obj["contentType"] == "application/geo+json"
        exported = json.loads(base64.b64decode(file_obj["content"]))
        assert exported["features"][0]["properties"]["time_minutes"] == 10
        assert exported["features"][0]["geometry"] == ISOCHRONE_POLYGON
        assert "test-key" not in file_obj["content"]
        assert "Authorization" not in file_obj["content"]

    async def test_export_serialization_failure_keeps_geojson(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]

        def boom(_geojson):
            return None

        monkeypatch.setattr(module, "_geojson_export_file", boom)
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ISOCHRONE_RESPONSE)
        result = await openrouteservice.execute_action(
            "get_isochrone", {**ISOCHRONE_INPUTS, "export_geojson": True}, mock_context
        )
        data = _action_data(result)
        assert data["result"] is True
        assert data["geojson"]["features"]
        assert data["files"] == []
        assert "api key" not in (data.get("message") or "").lower()
        assert "api key" not in (data.get("recovery") or "").lower()

    def test_geojson_export_skips_non_finite_values(self):
        payload = {"type": "FeatureCollection", "features": [{"value": float("nan")}]}
        assert _geojson_export_file(payload) is None


class TestProviderErrors:
    @pytest.mark.parametrize(
        "action, inputs",
        [("geocode_address", {"address": "Auckland"}), ("get_isochrone", ISOCHRONE_INPUTS)],
    )
    async def test_returns_retry_details_for_rate_limit(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RateLimitError(42, 429, "Rate limit exceeded")

        result = await openrouteservice.execute_action(action, inputs, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "rate_limit"
        assert data["error_code"] == "rate_limit"
        assert data["retry_after_seconds"] == 42
        assert data["retry_safe"] is True
        assert "rate limit" in data["message"].lower()
        assert data["recovery"]
        assert "test-key" not in data["message"]

    @pytest.mark.parametrize(
        ("status", "error_type"),
        [
            (401, "authentication"),
            (400, "invalid_request"),
            (404, "not_found"),
            (406, "not_acceptable"),
            (500, "provider_error"),
        ],
    )
    async def test_classifies_http_errors_without_echoing_provider_body(self, mock_context, status, error_type):
        mock_context.fetch.side_effect = HTTPError(status, "provider body containing test-key")

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        assert data["error_type"] == error_type
        assert data["error_code"] == error_type
        if status == 400:
            assert data["field"] == "address"
            assert "time bands" not in data["message"].lower()
            assert "time_minutes" not in data["message"].lower()
            assert "address" in data["recovery"].lower()
            assert "time bands" not in data["recovery"].lower()
        else:
            assert data["field"] is None
        if status == 500:
            assert data["retry_safe"] is True
        assert "test-key" not in data["message"]

    async def test_403_quota_only_body_is_quota_exceeded(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            403,
            '{"error": "Daily quota reached"}',
            {"error": "Daily quota reached"},
        )

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "quota_exceeded"
        assert data["retry_after_seconds"] is None
        assert "exhausted" in data["message"].lower()
        assert "routing profile" not in data["message"].lower()
        assert "daily quota reached" not in data["message"].lower()
        assert "test-key" not in data["message"]

    async def test_403_combined_quota_and_unauthorized_stays_ambiguous(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            403,
            '{"error": "Daily quota reached or API key unauthorized"}',
            {"error": "Daily quota reached or API key unauthorized"},
        )

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        message = data["message"].lower()
        assert data["error_type"] == "quota_or_unauthorized"
        assert data["retry_after_seconds"] is None
        assert "exhausted" not in message
        assert "unauthorized" in message
        assert "daily quota reached or api key unauthorized" not in message
        assert "routing profile" not in message
        assert "test-key" not in data["message"]

    async def test_403_access_disallowed_is_authorization(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(
            403,
            '{"error": "Access to this API has been disallowed"}',
            {"error": "Access to this API has been disallowed"},
        )

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "authorization"
        assert "routing profile" not in data["message"].lower()
        assert "disallowed" not in data["message"].lower()

    async def test_403_without_body_hints_is_not_a_profile_denial(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "provider body containing test-key")

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "quota_or_unauthorized"
        assert "test-key" not in data["message"]
        assert "routing profile" not in data["message"].lower()
        assert "quota" in data["message"].lower()

    async def test_isochrone_400_marks_time_minutes_not_address(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "bad request")

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "invalid_request"
        assert data["field"] is None
        assert "time bands" in data["message"].lower()
        assert "time bands" in data["recovery"].lower()

    async def test_isochrone_5xx_is_not_retry_safe(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "upstream")

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "provider_error"
        assert data["retry_safe"] is False
        assert "try again shortly" not in data["message"].lower()
        assert "do not retry" in data["recovery"].lower() or "quota" in data["recovery"].lower()

    async def test_404_is_not_found_not_retryable(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "not found")

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["error_type"] == "not_found"
        assert "try again shortly" not in data["message"].lower()

    async def test_network_failures_return_generic_request_failed(self, mock_context):
        mock_context.fetch.side_effect = aiohttp.ClientError("dns failed for api.openrouteservice.org")
        client_error = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)
        client_data = _action_data(client_error)
        assert client_data["error_type"] == "request_failed"
        assert client_data["retry_safe"] is True
        assert "dns failed" not in client_data["message"]
        assert "isochrone" not in client_data["recovery"].lower()

        mock_context.fetch.side_effect = TimeoutError("timed out")
        timeout = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)
        timeout_data = _action_data(timeout)
        assert timeout_data["error_type"] == "request_failed"
        assert timeout_data["error_code"] == "request_failed"
        assert timeout_data["retry_safe"] is False
        assert "timed out" not in timeout_data["message"]
        assert "try again shortly" not in timeout_data["message"].lower()
        assert "do not retry" in timeout_data["recovery"].lower() or "quota" in timeout_data["recovery"].lower()

        mock_context.fetch.side_effect = aiohttp.ClientError("connection reset")
        isochrone_network = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)
        assert _action_data(isochrone_network)["retry_safe"] is False

    async def test_missing_api_key_does_not_start_request(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.parametrize("api_key", ["", "   "])
    async def test_blank_api_key_does_not_start_request(self, mock_context, api_key):
        mock_context.auth = {"auth_type": "Custom", "credentials": {"api_key": api_key}}  # nosec B105

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "invalid_request"
        assert data["field"] is None
        assert "time_minutes" not in (data.get("message") or "").lower()
        assert "time bands" not in data["recovery"].lower()
        assert "api key" in data["recovery"].lower()
        mock_context.fetch.assert_not_called()

    def test_non_auth_value_error_does_not_blame_api_key(self):
        result = _provider_error(ValueError("At least one time value is required."))
        data = result.data
        assert data["error_type"] == "invalid_request"
        assert "api key" not in data["recovery"].lower()
        assert "api key" not in data["message"].lower()

    def test_missing_api_key_error_still_blames_connection(self):
        result = _provider_error(MissingApiKeyError("An OpenRouteService API key is required."))
        data = result.data
        assert "api key" in data["recovery"].lower()


MATRIX_ORIGIN = {"id": "home", "latitude": -36.8485, "longitude": 174.7633}
MATRIX_DEST_A = {"id": "work", "latitude": -36.8509, "longitude": 174.7648}
MATRIX_DEST_B = {"id": "shop", "latitude": -36.8524, "longitude": 174.7701}
MATRIX_INPUTS = {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A, MATRIX_DEST_B]}
MATRIX_METADATA = {
    "service": "matrix",
    "attribution": "openrouteservice.org, OpenStreetMap contributors",
    "engine": {
        "version": "8.2.0",
        "build_date": "2025-01-02T00:00:00Z",
        "graph_date": "2025-01-01T00:00:00Z",
        "osm_date": "2024-12-15T00:00:00Z",
    },
}


def _snap(lon, lat, distance, name=None):
    item = {"location": [lon, lat], "snapped_distance": distance}
    if name is not None:
        item["name"] = name
    return item


def _matrix_provider_body(
    durations,
    *,
    distances=None,
    sources=None,
    destinations=None,
    metadata=None,
    warnings=None,
):
    body = {"durations": durations, "metadata": MATRIX_METADATA if metadata is None else metadata}
    if distances is not None:
        body["distances"] = distances
    if sources is not None:
        body["sources"] = sources
    if destinations is not None:
        body["destinations"] = destinations
    if warnings is not None:
        body["warnings"] = warnings
    return body


class TestGetTravelTimeMatrix:
    async def test_returns_labelled_unrounded_pairs_in_input_order(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body(
                [[312.45, 480.125], [12.5, 0.0]],
                sources=[
                    _snap(174.76331, -36.84852, 4.2, "Queen Street"),
                    _snap(174.76201, -36.84901, 1.0, "Depot Street"),
                ],
                destinations=[
                    _snap(174.76481, -36.85091, 6.5, "Work Street"),
                    _snap(174.77012, -36.85241, 3.1, "Shop Street"),
                ],
            ),
        )
        # Two origins so row order is visible; reuse dest B as a second origin.
        inputs = {
            "origins": [MATRIX_ORIGIN, {"id": "depot", "latitude": -36.8490, "longitude": 174.7620}],
            "destinations": [MATRIX_DEST_A, MATRIX_DEST_B],
        }

        result = await openrouteservice.execute_action("get_travel_time_matrix", inputs, mock_context)

        data = _action_data(result)
        assert data["result"] is True
        assert data["profile"] == "driving-car"
        assert data["metrics"] == ["duration"]
        assert [pair["origin_id"] for pair in data["pairs"]] == ["home", "home", "depot", "depot"]
        assert [pair["destination_id"] for pair in data["pairs"]] == ["work", "shop", "work", "shop"]
        assert [pair["duration_seconds"] for pair in data["pairs"]] == [312.45, 480.125, 12.5, 0.0]
        assert [pair["distance_metres"] for pair in data["pairs"]] == [None, None, None, None]
        assert data["origins"][0]["id"] == "home"
        assert data["origins"][0]["snapped_latitude"] == -36.84852
        assert data["origins"][0]["snapped_longitude"] == 174.76331
        assert data["origins"][0]["snapped_distance_metres"] == 4.2
        assert data["origins"][0]["name"] == "Queen Street"
        assert data["files"] == []
        assert data["error_type"] is None
        request = mock_context.fetch.await_args
        assert request.args[0] == "https://api.heigit.org/openrouteservice/v2/matrix/driving-car"
        assert request.kwargs["method"] == "POST"
        assert request.kwargs["headers"]["Authorization"] == "test-key"
        assert "test-key" not in request.args[0]
        payload = request.kwargs["json"]
        assert payload["locations"] == [
            [174.7633, -36.8485],
            [174.7620, -36.8490],
            [174.7648, -36.8509],
            [174.7701, -36.8524],
        ]
        assert payload["sources"] == ["0", "1"]
        assert payload["destinations"] == ["2", "3"]
        assert payload["metrics"] == ["duration"]
        assert payload["resolve_locations"] is True
        assert payload["units"] == "m"
        assert "options" not in payload

    async def test_unreachable_and_non_finite_routes_are_null_not_zero(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body([[None, 0.0, float("inf"), float("nan")]]),
        )
        inputs = {
            "origins": [MATRIX_ORIGIN],
            "destinations": [
                MATRIX_DEST_A,
                MATRIX_DEST_B,
                {"id": "far", "latitude": -36.86, "longitude": 174.78},
                {"id": "none", "latitude": -36.87, "longitude": 174.79},
            ],
        }

        data = _action_data(await openrouteservice.execute_action("get_travel_time_matrix", inputs, mock_context))

        assert [pair["duration_seconds"] for pair in data["pairs"]] == [None, 0.0, None, None]
        assert data["unreachable_count"] == 3

    async def test_include_distance_returns_unrounded_metres(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body([[448.82]], distances=[[3210.4]]),
        )

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {
                    "origins": [MATRIX_ORIGIN],
                    "destinations": [MATRIX_DEST_A],
                    "include_distance": True,
                },
                mock_context,
            )
        )

        assert data["metrics"] == ["duration", "distance"]
        assert data["pairs"][0]["duration_seconds"] == 448.82
        assert data["pairs"][0]["distance_metres"] == 3210.4
        assert mock_context.fetch.await_args.kwargs["json"]["metrics"] == ["duration", "distance"]

    async def test_returns_provider_warnings_and_engine_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body(
                [[12.0]],
                warnings=[{"code": 1, "message": "One or more locations could not be routed"}],
            ),
        )

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A]},
                mock_context,
            )
        )

        assert data["warnings"] == [{"code": 1, "message": "One or more locations could not be routed"}]
        assert data["attribution"] == "openrouteservice.org, OpenStreetMap contributors"
        assert data["engine_version"] == "8.2.0"
        assert data["build_date"] == "2025-01-02T00:00:00Z"
        assert data["graph_date"] == "2025-01-01T00:00:00Z"
        assert data["osm_date"] == "2024-12-15T00:00:00Z"
        assert data["provider_metadata"]["service"] == "matrix"

    async def test_duplicate_and_blank_ids_are_invalid_request(self, mock_context):
        duplicate = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {"origins": [MATRIX_ORIGIN, {**MATRIX_ORIGIN, "latitude": -36.85}], "destinations": [MATRIX_DEST_A]},
            mock_context,
        )
        duplicate_data = _action_data(duplicate)
        assert duplicate_data["result"] is False
        assert duplicate_data["error_type"] == "invalid_request"
        assert duplicate_data["field"] == "origins"
        assert "home" in duplicate_data["message"]

        blank = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {"origins": [{**MATRIX_ORIGIN, "id": "  "}], "destinations": [MATRIX_DEST_A]},
            mock_context,
        )
        blank_data = _action_data(blank)
        assert blank_data["result"] is False
        assert blank_data["error_type"] == "invalid_request"
        assert blank_data["field"] == "origins"
        mock_context.fetch.assert_not_called()

    async def test_pair_count_over_cap_is_invalid_request(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]
        monkeypatch.setattr(module, "MATRIX_MAX_PAIRS", 3)

        result = await openrouteservice.execute_action(
            "get_travel_time_matrix",
            {
                "origins": [MATRIX_ORIGIN, {"id": "depot", "latitude": -36.849, "longitude": 174.762}],
                "destinations": [MATRIX_DEST_A, MATRIX_DEST_B],
            },
            mock_context,
        )

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "invalid_request"
        assert "3" in data["message"]
        mock_context.fetch.assert_not_called()

    async def test_schema_rejects_invalid_matrix_inputs(self, mock_context):
        cases = [
            {"destinations": [MATRIX_DEST_A]},
            {"origins": [MATRIX_ORIGIN]},
            {"origins": [], "destinations": [MATRIX_DEST_A]},
            {"origins": [MATRIX_ORIGIN], "destinations": []},
            {"origins": [{**MATRIX_ORIGIN, "id": ""}], "destinations": [MATRIX_DEST_A]},
            {"origins": [{**MATRIX_ORIGIN, "latitude": 91}], "destinations": [MATRIX_DEST_A]},
            {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A], "travel_mode": "cycling-regular"},
            {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A], "export_format": "xlsx"},
        ]
        for inputs in cases:
            result = await openrouteservice.execute_action("get_travel_time_matrix", inputs, mock_context)
            assert result.type == ResultType.VALIDATION_ERROR, inputs
        mock_context.fetch.assert_not_called()

    async def test_splits_oversize_requests_and_reassembles_unique_pairs(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]
        monkeypatch.setattr(module, "MATRIX_MAX_ROUTES", 2)
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data=_matrix_provider_body(
                    [[10.5, 20.25]],
                    sources=[_snap(174.7633, -36.8485, 1.0)],
                    destinations=[_snap(174.7648, -36.8509, 2.0), _snap(174.7701, -36.8524, 3.0)],
                ),
            ),
            FetchResponse(
                status=200,
                headers={},
                data=_matrix_provider_body(
                    [[30.5, 40.25]],
                    sources=[_snap(174.7620, -36.8490, 1.5)],
                    destinations=[_snap(174.7648, -36.8509, 2.0), _snap(174.7701, -36.8524, 3.0)],
                ),
            ),
        ]
        inputs = {
            "origins": [MATRIX_ORIGIN, {"id": "depot", "latitude": -36.8490, "longitude": 174.7620}],
            "destinations": [MATRIX_DEST_A, MATRIX_DEST_B],
        }

        data = _action_data(await openrouteservice.execute_action("get_travel_time_matrix", inputs, mock_context))

        assert mock_context.fetch.await_count == 2
        first_payload = mock_context.fetch.await_args_list[0].kwargs["json"]
        second_payload = mock_context.fetch.await_args_list[1].kwargs["json"]
        assert first_payload["locations"] == [[174.7633, -36.8485], [174.7648, -36.8509], [174.7701, -36.8524]]
        assert first_payload["sources"] == ["0"]
        assert first_payload["destinations"] == ["1", "2"]
        assert second_payload["locations"][0] == [174.7620, -36.8490]
        assert [pair["origin_id"] for pair in data["pairs"]] == ["home", "home", "depot", "depot"]
        assert [pair["duration_seconds"] for pair in data["pairs"]] == [10.5, 20.25, 30.5, 40.25]
        assert data["origins"][0]["id"] == "home"
        assert data["origins"][1]["id"] == "depot"
        assert data["destinations"][0]["id"] == "work"

    async def test_conflicting_origin_snaps_across_batches_are_provider_error(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]
        monkeypatch.setattr(module, "MATRIX_MAX_ROUTES", 1)
        mock_context.fetch.side_effect = [
            FetchResponse(
                status=200,
                headers={},
                data=_matrix_provider_body(
                    [[1.0]],
                    sources=[_snap(174.7633, -36.8485, 1.0)],
                    destinations=[_snap(174.7648, -36.8509, 2.0)],
                ),
            ),
            FetchResponse(
                status=200,
                headers={},
                data=_matrix_provider_body(
                    [[2.0]],
                    sources=[_snap(174.7999, -36.8999, 80.0)],
                    destinations=[_snap(174.7701, -36.8524, 3.0)],
                ),
            ),
        ]

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A, MATRIX_DEST_B]},
                mock_context,
            )
        )

        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert data["retry_safe"] is False

    async def test_duplicate_pair_from_provider_is_rejected(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body([[1.0, 2.0, 3.0]]),
        )

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A, MATRIX_DEST_B]},
                mock_context,
            )
        )

        assert data["result"] is False
        assert data["error_type"] == "provider_error"

    async def test_export_json_and_csv_are_platform_files_without_credentials(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=_matrix_provider_body([[None, 12.5]], distances=[[None, 100.25]]),
        )
        inputs = {
            "origins": [MATRIX_ORIGIN],
            "destinations": [MATRIX_DEST_A, MATRIX_DEST_B],
            "include_distance": True,
        }

        json_data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix", {**inputs, "export_format": "json"}, mock_context
            )
        )
        json_file = json_data["files"][0]
        assert json_file["name"] == "travel_time_matrix.json"
        assert json_file["contentType"] == "application/json"
        exported = json.loads(base64.b64decode(json_file["content"]))
        assert exported["pairs"][0]["duration_seconds"] is None
        assert "files" not in exported
        assert "test-key" not in json_file["content"]
        assert "Authorization" not in json_file["content"]

        csv_data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix", {**inputs, "export_format": "csv"}, mock_context
            )
        )
        csv_file = csv_data["files"][0]
        assert csv_file["name"] == "travel_time_matrix.csv"
        assert csv_file["contentType"] == "text/csv"
        csv_text = base64.b64decode(csv_file["content"]).decode("utf-8")
        assert "test-key" not in csv_text
        lines = [line for line in csv_text.strip().splitlines() if line]
        assert lines[0] == "origin_id,destination_id,duration_seconds,distance_metres"
        assert lines[1] == "home,work,,"
        assert "home,shop,12.5,100.25" in lines[2]

    async def test_export_serialization_failure_keeps_compact_result(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]
        monkeypatch.setattr(module, "_matrix_export_file", lambda *_args, **_kwargs: None)
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=_matrix_provider_body([[9.0]]))

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A], "export_format": "json"},
                mock_context,
            )
        )

        assert data["result"] is True
        assert data["pairs"][0]["duration_seconds"] == 9.0
        assert data["files"] == []

    async def test_timeout_is_distinct_and_not_retry_safe(self, mock_context):
        mock_context.fetch.side_effect = TimeoutError("timed out")

        data = _action_data(
            await openrouteservice.execute_action("get_travel_time_matrix", MATRIX_INPUTS, mock_context)
        )

        assert data["result"] is False
        assert data["error_type"] == "timeout"
        assert data["error_code"] == "timeout"
        assert data["retry_safe"] is False
        assert "timed out" not in data["message"]
        assert "try again shortly" not in data["message"].lower()
        assert "isochrone" not in data["message"].lower()
        assert "isochrone" not in data["recovery"].lower()

    async def test_rate_limit_after_a_successful_batch_fails_closed(self, mock_context, monkeypatch):
        import sys

        module = sys.modules["openrouteservice.openrouteservice"]
        monkeypatch.setattr(module, "MATRIX_MAX_ROUTES", 1)
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=_matrix_provider_body([[1.0]])),
            RateLimitError(30, 429, "Rate limit exceeded"),
        ]

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A, MATRIX_DEST_B]},
                mock_context,
            )
        )

        assert data["result"] is False
        assert data["error_type"] == "rate_limit"
        assert data["retry_safe"] is True
        assert "pairs" not in data or data.get("pairs") in (None, [])

    async def test_matrix_400_does_not_blame_time_minutes(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "bad request")

        data = _action_data(
            await openrouteservice.execute_action("get_travel_time_matrix", MATRIX_INPUTS, mock_context)
        )

        assert data["error_type"] == "invalid_request"
        assert data["field"] == "origins"
        assert "time bands" not in data["message"].lower()
        assert "time_minutes" not in data["message"].lower()
        assert "origin" in data["message"].lower()

    async def test_matrix_5xx_is_not_retry_safe(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "upstream")

        data = _action_data(
            await openrouteservice.execute_action("get_travel_time_matrix", MATRIX_INPUTS, mock_context)
        )

        assert data["error_type"] == "provider_error"
        assert data["retry_safe"] is False
        assert "try again shortly" not in data["message"].lower()
        assert "isochrone" not in data["recovery"].lower()

    async def test_missing_durations_are_provider_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": MATRIX_METADATA})

        data = _action_data(
            await openrouteservice.execute_action(
                "get_travel_time_matrix",
                {"origins": [MATRIX_ORIGIN], "destinations": [MATRIX_DEST_A]},
                mock_context,
            )
        )

        assert data["result"] is False
        assert data["error_type"] == "provider_error"
        assert data["retry_safe"] is False
