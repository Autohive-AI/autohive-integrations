"""OpenRouteService geocoding and drive-time isochrone actions."""

import base64
import json
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


class ProviderResponseError(Exception):
    """Raised when a 2xx OpenRouteService body is not the expected GeoJSON shape."""


# api.openrouteservice.org is deprecated; HeiGIT documents geocode as Pelias v1.
GEOCODE_URL = "https://api.heigit.org/pelias/v1/search"
# The current OpenRouteService API Playground uses HeiGIT's OpenRouteService gateway.
# The endpoint returns a GeoJSON FeatureCollection for isochrone requests.
ISOCHRONE_URL_TEMPLATE = "https://api.heigit.org/openrouteservice/v2/isochrones/{profile}"
LOW_CONFIDENCE_THRESHOLD = 0.8
# Isochrones are compute-heavy. The SDK default is 30s with 3 retries; a timeout
# after the provider already billed the request would charge the daily quota again.
ISOCHRONE_TIMEOUT_SECONDS = 90
_POLYGON_TYPES = {"Polygon", "MultiPolygon"}
_RETRY_SAFE_ERRORS = {"rate_limit", "request_failed"}
_ERROR_RECOVERY = {
    "rate_limit": "Wait retry_after_seconds, then retry the same request.",
    "quota_exceeded": "Check the HeiGIT dashboard. Do not retry until the daily window resets.",
    "quota_or_unauthorized": "Check the HeiGIT dashboard and the API key. Do not retry shortly.",
    "authentication": "Update the OpenRouteService API key on this connection.",
    "authorization": "Check the API key is enabled for this service. Do not retry the same request.",
    "invalid_request": "Correct the coordinates or time bands, then send a new request.",
    "not_found": "Check the coordinates or address. Retrying the same request will not help.",
    "not_acceptable": "This is an integration issue. Do not retry the same request.",
    "provider_error": "Check the request. Retrying may help if the provider is temporarily unavailable.",
    "request_failed": "Retry shortly. A timeout after isochrone compute should not be retried immediately.",
}


def _api_key(context: ExecutionContext) -> str:
    """Return the configured API key without ever placing it in a URL."""
    credentials = (context.auth or {}).get("credentials", {})
    api_key = credentials.get("api_key", "") if isinstance(credentials, dict) else ""
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        raise ValueError("An OpenRouteService API key is required. Add one to this integration connection.")
    return api_key


def _headers(context: ExecutionContext) -> dict[str, str]:
    return {"Authorization": _api_key(context), "Accept": "application/json"}


def _isochrone_headers(context: ExecutionContext) -> dict[str, str]:
    """Return the media types shown by the current OpenRouteService API Playground."""
    return {
        "Authorization": _api_key(context),
        "Accept": "application/json, application/geo+json",
        "Content-Type": "application/json; charset=utf-8",
    }


def _fetch_retry_count(context: ExecutionContext) -> int:
    """Return max_retries so context.fetch does not retry this attempt."""
    config = getattr(context, "config", None)
    if isinstance(config, dict):
        try:
            return max(int(config.get("max_retries", 0) or 0), 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _provider_body_text(error: HTTPError) -> str:
    """Lowercased provider body for classification only — never returned to callers."""
    parts = [str(error.message or "")]
    data = error.response_data
    if isinstance(data, dict):
        nested = data.get("error")
        if isinstance(nested, str):
            parts.append(nested)
        elif isinstance(nested, dict):
            parts.append(json.dumps(nested))
        message = data.get("message")
        if isinstance(message, str):
            parts.append(message)
    elif isinstance(data, str):
        parts.append(data)
    return " ".join(parts).lower()


def _mentions_authorization(body: str) -> bool:
    return "disallowed" in body or "unauthorized" in body or "invalid api key" in body or "invalid key" in body


def _classify_forbidden(error: HTTPError) -> tuple[str, str]:
    """Classify HeiGIT HTTP 403. Staff document 403 as daily quota or an unauthorized key."""
    body = _provider_body_text(error)
    mentions_quota = "quota" in body
    mentions_auth = _mentions_authorization(body)
    if mentions_quota and not mentions_auth:
        return (
            "quota_exceeded",
            (
                "OpenRouteService daily quota is exhausted. Check the HeiGIT dashboard; "
                "the 24-hour window resets from first use, not midnight."
            ),
        )
    if mentions_auth and not mentions_quota:
        return (
            "authorization",
            "OpenRouteService denied access. Check the API key and that it is enabled for this service.",
        )
    return (
        "quota_or_unauthorized",
        (
            "OpenRouteService returned HTTP 403. This is the daily quota limit or an unauthorized API key. "
            "Check the HeiGIT dashboard before changing the connection."
        ),
    )


def _error_payload(
    error_type: str,
    message: str,
    *,
    retry_after_seconds: int | None = None,
    field: str | None = None,
    valid_alternatives: list[Any] | None = None,
    retry_safe: bool | None = None,
) -> dict[str, Any]:
    """Compact corrective error. Never includes provider bodies, HTML, or credentials."""
    return {
        "result": False,
        "error_type": error_type,
        "error_code": error_type,
        "retry_after_seconds": retry_after_seconds,
        "message": message,
        "field": field,
        "valid_alternatives": valid_alternatives or [],
        "recovery": _ERROR_RECOVERY.get(error_type, "Check the inputs and try again."),
        "retry_safe": (error_type in _RETRY_SAFE_ERRORS) if retry_safe is None else retry_safe,
    }


def _provider_error(error: Exception, *, invalid_request_field: str | None = None) -> ActionResult:
    """Return safe, actionable provider errors without exposing request credentials."""
    if isinstance(error, RateLimitError):
        return ActionResult(
            data=_error_payload(
                "rate_limit",
                "OpenRouteService rate limit reached. Try again after the retry interval.",
                retry_after_seconds=error.retry_after,
            ),
            cost_usd=0.0,
        )

    if isinstance(error, HTTPError):
        if error.status == 401:
            message = "OpenRouteService rejected the API key. Check the integration connection."
            error_type = "authentication"
            field = None
        elif error.status == 403:
            error_type, message = _classify_forbidden(error)
            field = None
        elif error.status == 400:
            error_type = "invalid_request"
            field = invalid_request_field
            if invalid_request_field == "address":
                message = "OpenRouteService rejected the request. Check the supplied address."
            elif invalid_request_field == "time_minutes":
                message = "OpenRouteService rejected the request. Check the supplied coordinates or time bands."
            else:
                message = "OpenRouteService rejected the request. Check the inputs and try again."
        elif error.status == 404:
            message = (
                "OpenRouteService found no result for this request. "
                "Check the coordinates or address; retrying will not help."
            )
            error_type = "not_found"
            field = None
        elif error.status == 406:
            message = (
                "OpenRouteService rejected the requested response format. Check the API endpoint and Accept header."
            )
            error_type = "not_acceptable"
            field = None
        else:
            message = f"OpenRouteService returned HTTP {error.status}. Try again shortly."
            error_type = "provider_error"
            field = None
        return ActionResult(data=_error_payload(error_type, message, field=field), cost_usd=0.0)

    if isinstance(error, ProviderResponseError):
        return ActionResult(data=_error_payload("provider_error", str(error)), cost_usd=0.0)

    if isinstance(error, ValueError):
        return ActionResult(
            data=_error_payload("invalid_request", str(error), field=None),
            cost_usd=0.0,
        )

    return ActionResult(
        data=_error_payload(
            "request_failed",
            "OpenRouteService could not complete this request. Try again shortly.",
        ),
        cost_usd=0.0,
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _band_minutes(properties: dict[str, Any]) -> int | None:
    """Stable whole-minute band from feature properties. ORS stores `value` in seconds."""
    existing = properties.get("time_minutes")
    if isinstance(existing, int) and not isinstance(existing, bool) and existing >= 1:
        return existing
    value = properties.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    minutes = float(value) / 60.0
    rounded = round(minutes)
    if abs(minutes - rounded) > 1e-9 or rounded < 1:
        return None
    return int(rounded)


def _engine_fields(metadata: Any) -> dict[str, str | None]:
    meta = _as_dict(metadata)
    engine = _as_dict(meta.get("engine"))
    return {
        "attribution": _string_or_none(meta.get("attribution")),
        "engine_version": _string_or_none(engine.get("version")),
        "build_date": _string_or_none(engine.get("build_date")),
        "graph_date": _string_or_none(engine.get("graph_date")),
        "osm_date": _string_or_none(engine.get("osm_date")) or _string_or_none(meta.get("osm_date")),
    }


def _platform_file(name: str, content_type: str, body: str | bytes) -> dict[str, str]:
    raw = body.encode("utf-8") if isinstance(body, str) else body
    return {
        "name": name,
        "contentType": content_type,
        "content": base64.b64encode(raw).decode("ascii"),
    }


def _normalize_isochrone_geojson(geojson: dict[str, Any], requested_minutes: list[int]) -> dict[str, Any]:
    """Copy the FeatureCollection, add time_minutes, keep exact geometry, sort ascending."""
    normalized: list[dict[str, Any]] = []
    for feature in geojson.get("features") or []:
        if not isinstance(feature, dict):
            raise ProviderResponseError("OpenRouteService returned an isochrone feature that is not an object.")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in _POLYGON_TYPES:
            raise ProviderResponseError(
                "OpenRouteService returned an isochrone feature that is not a Polygon or MultiPolygon."
            )
        properties = dict(_as_dict(feature.get("properties")))
        band = _band_minutes(properties)
        if band is None:
            raise ProviderResponseError("OpenRouteService returned an isochrone feature without a whole-minute band.")
        properties["time_minutes"] = band
        copied = dict(feature)
        copied["geometry"] = geometry
        copied["properties"] = properties
        normalized.append(copied)
    normalized.sort(key=lambda item: (item["properties"]["time_minutes"], str(item.get("id") or "")))
    present = {item["properties"]["time_minutes"] for item in normalized}
    missing = [minutes for minutes in requested_minutes if minutes not in present]
    if missing:
        raise ProviderResponseError(
            "OpenRouteService did not return a polygon for every requested time band. "
            f"Missing minutes: {', '.join(str(item) for item in missing)}."
        )
    result = {"type": "FeatureCollection", "features": normalized}
    if "bbox" in geojson:
        result["bbox"] = geojson["bbox"]
    if "metadata" in geojson:
        result["metadata"] = geojson["metadata"]
    return result


def _numeric_coordinate(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _match(feature: dict[str, Any]) -> dict[str, Any]:
    properties = _as_dict(feature.get("properties"))
    geometry = _as_dict(feature.get("geometry"))
    coordinates = geometry.get("coordinates")
    if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
        longitude = _numeric_coordinate(coordinates[0])
        latitude = _numeric_coordinate(coordinates[1])
    else:
        longitude = None
        latitude = None
    confidence = properties.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = None
    return {
        "address": properties.get("label") or properties.get("name"),
        "latitude": latitude,
        "longitude": longitude,
        "confidence": confidence,
        "match_type": properties.get("match_type"),
        "is_low_confidence": confidence is None or confidence < LOW_CONFIDENCE_THRESHOLD,
        "feature": feature,
    }


def _has_point(match: dict[str, Any]) -> bool:
    return match.get("latitude") is not None and match.get("longitude") is not None


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
            data = response.data
            features = data.get("features") if isinstance(data, dict) else None
            if not isinstance(data, dict) or data.get("type") != "FeatureCollection" or not isinstance(features, list):
                raise ProviderResponseError("OpenRouteService returned an unexpected geocode response.")
            matches = []
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                match = _match(feature)
                if _has_point(match):
                    matches.append(match)
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
        except (
            RateLimitError,
            HTTPError,
            ProviderResponseError,
            ValueError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            return _provider_error(error, invalid_request_field="address")


@openrouteservice.action("get_isochrone")
class GetIsochrone(ActionHandler):
    """Request drive-time polygons for one origin and one or more minute bands."""

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
                headers=_isochrone_headers(context),
                json=payload,
                timeout=ISOCHRONE_TIMEOUT_SECONDS,
                retry_count=_fetch_retry_count(context),
            )
            geojson = response.data
            # The SDK parses application/json automatically, but some provider responses
            # use application/geo+json and arrive as a JSON string instead.
            if isinstance(geojson, str):
                try:
                    geojson = json.loads(geojson)
                except json.JSONDecodeError:
                    raise ProviderResponseError("OpenRouteService returned a non-JSON isochrone response.") from None
            if (
                not isinstance(geojson, dict)
                or geojson.get("type") != "FeatureCollection"
                or not isinstance(geojson.get("features"), list)
            ):
                raise ProviderResponseError("OpenRouteService returned an unexpected isochrone response.")

            normalized = _normalize_isochrone_geojson(geojson, time_minutes)
            engine = _engine_fields(normalized.get("metadata"))
            files: list[dict[str, str]] = []
            if inputs.get("export_geojson"):
                files.append(
                    _platform_file(
                        "isochrones.geojson",
                        "application/geo+json",
                        json.dumps(normalized, allow_nan=False),
                    )
                )
            return ActionResult(
                data={
                    "result": True,
                    "profile": profile,
                    "time_minutes": time_minutes,
                    "geojson": normalized,
                    "provider_metadata": normalized.get("metadata"),
                    "attribution": engine["attribution"],
                    "engine_version": engine["engine_version"],
                    "build_date": engine["build_date"],
                    "graph_date": engine["graph_date"],
                    "osm_date": engine["osm_date"],
                    "files": files,
                    "error_type": None,
                    "error_code": None,
                    "retry_after_seconds": None,
                    "message": None,
                    "field": None,
                    "valid_alternatives": None,
                    "recovery": None,
                    "retry_safe": None,
                },
                cost_usd=0.0,
            )
        except (
            RateLimitError,
            HTTPError,
            ProviderResponseError,
            ValueError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            return _provider_error(error, invalid_request_field="time_minutes")
