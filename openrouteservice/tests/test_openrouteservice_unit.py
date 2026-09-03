"""Unit tests for OpenRouteService integration actions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from openrouteservice.openrouteservice import (
    GEOCODE_URL,
    ISOCHRONE_URL_TEMPLATE,
    openrouteservice,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {"auth_type": "Custom", "credentials": {"api_key": "test-key"}}  # nosec B105
    return context


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


class TestGeocodeAddress:
    async def test_geocodes_address_with_default_nz_boundary(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=GEOCODE_RESPONSE)

        result = await openrouteservice.execute_action(
            "geocode_address", {"address": "1 Queen Street, Auckland"}, mock_context
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["found"] is True
        assert data["address"] == "1 Queen Street, Auckland, New Zealand"
        assert data["longitude"] == 174.7633
        assert data["latitude"] == -36.8445
        assert data["confidence"] == 0.95
        assert data["is_low_confidence"] is False
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

        assert result.result.data["is_low_confidence"] is True
        assert result.result.data["message"] == "Confirm this match before downstream use."

    async def test_returns_found_false_when_provider_returns_no_features(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"type": "FeatureCollection", "features": []}
        )

        result = await openrouteservice.execute_action(
            "geocode_address", {"address": "not a real location"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["found"] is False
        assert result.result.data["matches"] == []


class TestGetIsochrone:
    async def test_requests_all_time_bands_once_and_returns_unmodified_geojson(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ISOCHRONE_RESPONSE)

        result = await openrouteservice.execute_action(
            "get_isochrone",
            {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [30, 10, 15, 10]},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["time_minutes"] == [10, 15, 30]
        assert result.result.data["geojson"] is ISOCHRONE_RESPONSE
        assert result.result.data["provider_metadata"] is ISOCHRONE_RESPONSE["metadata"]
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

        result = await openrouteservice.execute_action(
            "get_isochrone", {"latitude": -36.8485, "longitude": 174.7633, "time_minutes": [10]}, mock_context
        )

        assert result.result.data["result"] is False
        assert result.result.data["error_type"] == "invalid_request"


class TestProviderErrors:
    async def test_returns_retry_details_for_rate_limit(self, mock_context):
        mock_context.fetch.side_effect = RateLimitError(42, 429, "Rate limit exceeded")

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        assert result.result.data == {
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

        assert result.result.data["error_type"] == error_type
        assert "test-key" not in result.result.data["message"]

    async def test_missing_api_key_does_not_start_request(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await openrouteservice.execute_action("geocode_address", {"address": "Auckland"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()
