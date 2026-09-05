"""Unit tests for OpenRouteService integration actions."""

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from openrouteservice.openrouteservice import (
    GEOCODE_URL,
    ISOCHRONE_URL_TEMPLATE,
    _match,
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

ISOCHRONE_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"group_index": 0, "value": 600},
            "geometry": {"type": "Polygon", "coordinates": [[[174.76, -36.84], [174.77, -36.84], [174.76, -36.84]]]},
        }
    ],
    "metadata": {"service": "isochrones", "engine": {"graph_date": "2025-01-01"}},
}

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
        assert data["error_type"] == "invalid_request"

    async def test_rejects_invalid_geocode_inputs(self, mock_context):
        missing = await openrouteservice.execute_action("geocode_address", {}, mock_context)
        assert missing.type == ResultType.VALIDATION_ERROR

        lowercase_country = await openrouteservice.execute_action(
            "geocode_address", {"address": "Auckland", "country": "nz"}, mock_context
        )
        assert lowercase_country.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


class TestGetIsochrone:
    def test_uses_explicit_geojson_provider_endpoint(self):
        assert ISOCHRONE_URL_TEMPLATE == "https://api.openrouteservice.org/v2/isochrones/{profile}/geojson"

    async def test_requests_all_time_bands_once_and_returns_unmodified_geojson(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ISOCHRONE_RESPONSE)

        result = await openrouteservice.execute_action(
            "get_isochrone",
            {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [30, 10, 15, 10]},
            mock_context,
        )

        data = _action_data(result)
        assert data["time_minutes"] == [10, 15, 30]
        assert data["profile"] == "driving-car"
        assert data["geojson"] is ISOCHRONE_RESPONSE
        assert data["provider_metadata"] is ISOCHRONE_RESPONSE["metadata"]
        assert data["error_type"] is None
        mock_context.fetch.assert_awaited_once_with(
            ISOCHRONE_URL_TEMPLATE.format(profile="driving-car"),
            method="POST",
            headers={"Authorization": "test-key", "Accept": "application/json"},
            json={
                "locations": [[174.7633, -36.8485]],
                "range": [600, 900, 1800],
                "range_type": "time",
            },
        )

    async def test_rejects_non_geojson_provider_response(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"unexpected": "response"})

        result = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)

        data = _action_data(result)
        assert data["result"] is False
        assert data["error_type"] == "invalid_request"

    async def test_rejects_invalid_isochrone_inputs(self, mock_context):
        cases = [
            {"longitude": 174.76, "time_minutes": [10]},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": []},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": [0]},
            {"latitude": 91, "longitude": 174.76, "time_minutes": [10]},
            {"latitude": -36.84, "longitude": 174.76, "time_minutes": [10], "travel_mode": "cycling-regular"},
        ]
        for inputs in cases:
            result = await openrouteservice.execute_action("get_isochrone", inputs, mock_context)
            assert result.type == ResultType.VALIDATION_ERROR, inputs
        mock_context.fetch.assert_not_called()


class TestProviderErrors:
    @pytest.mark.parametrize(
        "action, inputs",
        [("geocode_address", {"address": "Auckland"}), ("get_isochrone", ISOCHRONE_INPUTS)],
    )
    async def test_returns_retry_details_for_rate_limit(self, mock_context, action, inputs):
        mock_context.fetch.side_effect = RateLimitError(42, 429, "Rate limit exceeded")

        result = await openrouteservice.execute_action(action, inputs, mock_context)

        assert _action_data(result) == {
            "result": False,
            "error_type": "rate_limit",
            "retry_after_seconds": 42,
            "message": "OpenRouteService rate limit reached. Try again after the retry interval.",
        }

    @pytest.mark.parametrize(
        ("status", "error_type"),
        [(401, "authentication"), (403, "authorization"), (400, "invalid_request"), (500, "provider_error")],
    )
    async def test_classifies_http_errors_without_echoing_provider_body(self, mock_context, status, error_type):
        mock_context.fetch.side_effect = HTTPError(status, "provider body containing test-key")

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        data = _action_data(result)
        assert data["error_type"] == error_type
        assert "test-key" not in data["message"]

    async def test_network_failures_return_generic_request_failed(self, mock_context):
        mock_context.fetch.side_effect = aiohttp.ClientError("dns failed for api.openrouteservice.org")
        client_error = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)
        client_data = _action_data(client_error)
        assert client_data["error_type"] == "request_failed"
        assert "dns failed" not in client_data["message"]

        mock_context.fetch.side_effect = TimeoutError("timed out")
        timeout = await openrouteservice.execute_action("get_isochrone", ISOCHRONE_INPUTS, mock_context)
        timeout_data = _action_data(timeout)
        assert timeout_data["error_type"] == "request_failed"
        assert "timed out" not in timeout_data["message"]

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
        mock_context.fetch.assert_not_called()
