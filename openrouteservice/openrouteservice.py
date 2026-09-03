"""OpenRouteService geocoding and drive-time isochrone actions."""

from typing import Any

import aiohttp
from autohive_integrations_sdk import (
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)

openrouteservice = Integration.load()

GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ISOCHRONE_URL_TEMPLATE = "https://api.openrouteservice.org/v2/isochrones/{profile}"
LOW_CONFIDENCE_THRESHOLD = 0.8


def _api_key(context: ExecutionContext) -> str:
    """Return the configured API key without ever placing it in a URL."""
    credentials = (context.auth or {}).get("credentials", {})
    api_key = credentials.get("api_key", "") if isinstance(credentials, dict) else ""
    if not api_key:
        raise ValueError("An OpenRouteService API key is required. Add one to this integration connection.")
    return api_key


def _headers(context: ExecutionContext) -> dict[str, str]:
    return {"Authorization": _api_key(context), "Accept": "application/json"}


def _provider_error(error: Exception) -> ActionResult:
    """Return safe, actionable provider errors without exposing request credentials."""
    if isinstance(error, RateLimitError):
        return ActionResult(
            data={
                "result": False,
                "error_type": "rate_limit",
                "retry_after_seconds": error.retry_after,
                "message": "OpenRouteService rate limit reached. Try again after the retry interval.",
            },
            cost_usd=0.0,
        )

    if isinstance(error, HTTPError):
        if error.status == 401:
            message = "OpenRouteService rejected the API key. Check the integration connection."
            error_type = "authentication"
        elif error.status == 403:
            message = "OpenRouteService denied access to this endpoint or routing profile."
            error_type = "authorization"
        elif error.status == 400:
            message = "OpenRouteService rejected the request. Check the supplied coordinates or time bands."
            error_type = "invalid_request"
        else:
            message = f"OpenRouteService returned HTTP {error.status}. Try again shortly."
            error_type = "provider_error"
        return ActionResult(
            data={"result": False, "error_type": error_type, "retry_after_seconds": None, "message": message},
            cost_usd=0.0,
        )

    if isinstance(error, ValueError):
        return ActionResult(
            data={"result": False, "error_type": "invalid_request", "retry_after_seconds": None, "message": str(error)},
            cost_usd=0.0,
        )

    return ActionResult(
        data={
            "result": False,
            "error_type": "request_failed",
            "retry_after_seconds": None,
            "message": "OpenRouteService could not complete this request. Try again shortly.",
        },
        cost_usd=0.0,
    )


def _match(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coordinates = geometry.get("coordinates", [])
    longitude = coordinates[0] if len(coordinates) >= 2 else None
    latitude = coordinates[1] if len(coordinates) >= 2 else None
    confidence = properties.get("confidence")
    return {
        "address": properties.get("label") or properties.get("name"),
        "latitude": latitude,
        "longitude": longitude,
        "confidence": confidence,
        "match_type": properties.get("match_type"),
        "is_low_confidence": confidence is None or confidence < LOW_CONFIDENCE_THRESHOLD,
        "feature": feature,
    }


@openrouteservice.action("geocode_address")
class GeocodeAddress(ActionHandler):
    """Geocode an address, defaulting the geographic boundary to New Zealand."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(
                GEOCODE_URL,
                method="GET",
                headers=_headers(context),
                params={"text": inputs["address"], "boundary.country": inputs.get("country", "NZ")},
            )
            data = response.data if isinstance(response.data, dict) else {}
            matches = [_match(feature) for feature in data.get("features", []) if isinstance(feature, dict)]
            if not matches:
                return ActionResult(
                    data={
                        "result": True,
                        "found": False,
                        "address": None,
                        "latitude": None,
                        "longitude": None,
                        "confidence": None,
                        "match_type": None,
                        "is_low_confidence": None,
                        "matches": [],
                        "geocoding": data.get("geocoding"),
                        "error_type": None,
                        "retry_after_seconds": None,
                        "message": "No matching address was found.",
                    },
                    cost_usd=0.0,
                )

            best = matches[0]
            return ActionResult(
                data={
                    "result": True,
                    "found": True,
                    "address": best["address"],
                    "latitude": best["latitude"],
                    "longitude": best["longitude"],
                    "confidence": best["confidence"],
                    "match_type": best["match_type"],
                    "is_low_confidence": best["is_low_confidence"],
                    "matches": matches,
                    "geocoding": data.get("geocoding"),
                    "error_type": None,
                    "retry_after_seconds": None,
                    "message": "Confirm this match before downstream use." if best["is_low_confidence"] else None,
                },
                cost_usd=0.0,
            )
        except (RateLimitError, HTTPError, ValueError, aiohttp.ClientError, TimeoutError) as error:
            return _provider_error(error)


@openrouteservice.action("get_isochrone")
class GetIsochrone(ActionHandler):
    """Request unmodified GeoJSON isochrones for one origin and multiple time bands."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            profile = inputs.get("travel_mode", "driving-car")
            time_minutes: list[int] = sorted(set(inputs["time_minutes"]))
            if not time_minutes:
                raise ValueError("At least one time value is required.")

            payload = {
                "locations": [[inputs["longitude"], inputs["latitude"]]],
                "range": [minutes * 60 for minutes in time_minutes],
                "range_type": "time",
            }
            response = await context.fetch(
                ISOCHRONE_URL_TEMPLATE.format(profile=profile),
                method="POST",
                headers=_headers(context),
                json=payload,
            )
            geojson = response.data
            if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
                raise ValueError("OpenRouteService returned an unexpected isochrone response.")

            return ActionResult(
                data={
                    "result": True,
                    "profile": profile,
                    "time_minutes": time_minutes,
                    "geojson": geojson,
                    "provider_metadata": geojson.get("metadata"),
                    "error_type": None,
                    "retry_after_seconds": None,
                    "message": None,
                },
                cost_usd=0.0,
            )
        except (RateLimitError, HTTPError, ValueError, aiohttp.ClientError, TimeoutError) as error:
            return _provider_error(error)
