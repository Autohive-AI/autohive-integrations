"""OpenRouteService geocoding, isochrone, and travel-time matrix actions."""

import base64
import json
import math
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
    """Raised when a 2xx OpenRouteService body is not the expected response shape."""


# api.openrouteservice.org is deprecated; HeiGIT documents geocode as Pelias v1.
GEOCODE_URL = "https://api.heigit.org/pelias/v1/search"
# The current OpenRouteService API Playground uses HeiGIT's OpenRouteService gateway.
# The endpoint returns a GeoJSON FeatureCollection for isochrone requests.
ISOCHRONE_URL_TEMPLATE = "https://api.heigit.org/openrouteservice/v2/isochrones/{profile}"
MATRIX_URL_TEMPLATE = "https://api.heigit.org/openrouteservice/v2/matrix/{profile}"
LOW_CONFIDENCE_THRESHOLD = 0.8
# Isochrones are compute-heavy. The SDK default is 30s with 3 retries; a timeout
# after the provider already billed the request would charge the daily quota again.
ISOCHRONE_TIMEOUT_SECONDS = 90
MATRIX_TIMEOUT_SECONDS = 90
# Public HeiGIT matrix limit is 3500 routes (sources × destinations) per request.
MATRIX_MAX_ROUTES = 3500
MATRIX_MAX_PAIRS = 10000
_BATCHED_METADATA_OMIT = frozenset({"query", "timestamp", "id"})
_POLYGON_TYPES = {"Polygon", "MultiPolygon"}
_RETRY_SAFE_ERRORS = {"rate_limit", "request_failed"}
_ERROR_RECOVERY = {
    "rate_limit": "Wait retry_after_seconds, then retry the same request.",
    "quota_exceeded": "Check the HeiGIT dashboard. Do not retry until the daily window resets.",
    "quota_or_unauthorized": "Check the HeiGIT dashboard and the API key. Do not retry shortly.",
    "authentication": "Update the OpenRouteService API key on this connection.",
    "authorization": "Check the API key is enabled for this service. Do not retry the same request.",
    "invalid_request": "Correct the inputs, then send a new request.",
    "not_found": "Check the coordinates or address. Retrying the same request will not help.",
    "not_acceptable": "This is an integration issue. Do not retry the same request.",
    "provider_error": "Check the request. Retrying may help if the provider is temporarily unavailable.",
    "request_failed": "Retry shortly.",
}
_ISOCHRONE_NO_RETRY = "Do not retry immediately. The isochrone may already have been billed against the daily quota."
_MATRIX_NO_RETRY = "Do not retry immediately. The matrix may already have been billed against the daily quota."
_INVALID_REQUEST_RECOVERY = {
    "address": "Correct the address, then send a new request.",
    "time_minutes": "Correct the coordinates or time bands, then send a new request.",
    "origins": "Correct the origin and destination coordinates, then send a new request.",
    "destinations": "Correct the origin and destination coordinates, then send a new request.",
}
_SNAP_KEYS = ("snapped_latitude", "snapped_longitude", "snapped_distance_metres", "name")


class MissingApiKeyError(ValueError):
    """Raised only when the connection has no usable OpenRouteService API key."""


class MatrixInputError(ValueError):
    """Raised when labelled matrix inputs fail runtime validation."""

    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field


def _api_key(context: ExecutionContext) -> str:
    """Return the configured API key without ever placing it in a URL."""
    credentials = (context.auth or {}).get("credentials", {})
    api_key = credentials.get("api_key", "") if isinstance(credentials, dict) else ""
    if isinstance(api_key, str):
        api_key = api_key.strip()
    if not api_key:
        raise MissingApiKeyError("An OpenRouteService API key is required. Add one to this integration connection.")
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
    recovery: str | None = None,
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
        "recovery": recovery or _ERROR_RECOVERY.get(error_type, "Check the inputs and try again."),
        "retry_safe": (error_type in _RETRY_SAFE_ERRORS) if retry_safe is None else retry_safe,
    }


def _provider_error(
    error: Exception,
    *,
    invalid_request_field: str | None = None,
    retry_safe_on_request_failed: bool = True,
    retry_safe_on_provider_error: bool = True,
    request_failed_message: str | None = None,
    no_retry_recovery: str | None = None,
) -> ActionResult:
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
            elif invalid_request_field == "origins":
                message = (
                    "OpenRouteService rejected the request. Check the supplied origin and destination coordinates."
                )
            else:
                message = (
                    "OpenRouteService rejected the request. "
                    "Check the supplied coordinates, time bands, or other inputs."
                )
            recovery = _INVALID_REQUEST_RECOVERY.get(invalid_request_field or "")
            if not recovery:
                recovery = (
                    "Correct the coordinates or time bands if those were wrong, then send a new request."
                    if not retry_safe_on_request_failed
                    else _ERROR_RECOVERY["invalid_request"]
                )
            return ActionResult(
                data=_error_payload(error_type, message, field=field, recovery=recovery),
                cost_usd=0.0,
            )
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
            error_type = "provider_error"
            field = None
            if retry_safe_on_provider_error:
                message = f"OpenRouteService returned HTTP {error.status}. Try again shortly."
            else:
                message = f"OpenRouteService returned HTTP {error.status}."
        retry_safe = retry_safe_on_provider_error if error_type == "provider_error" else None
        recovery = None
        if error_type == "provider_error" and not retry_safe_on_provider_error:
            recovery = no_retry_recovery or _ISOCHRONE_NO_RETRY
        return ActionResult(
            data=_error_payload(error_type, message, field=field, retry_safe=retry_safe, recovery=recovery),
            cost_usd=0.0,
        )

    if isinstance(error, ProviderResponseError):
        return ActionResult(
            data=_error_payload(
                "provider_error",
                str(error),
                retry_safe=retry_safe_on_provider_error,
                recovery=None if retry_safe_on_provider_error else (no_retry_recovery or _ISOCHRONE_NO_RETRY),
            ),
            cost_usd=0.0,
        )

    if isinstance(error, MissingApiKeyError):
        return ActionResult(
            data=_error_payload(
                "invalid_request",
                str(error),
                field=None,
                recovery="Add a valid OpenRouteService API key to this connection.",
            ),
            cost_usd=0.0,
        )

    if isinstance(error, ValueError):
        return ActionResult(
            data=_error_payload(
                "invalid_request",
                str(error),
                field=invalid_request_field,
                recovery=_INVALID_REQUEST_RECOVERY.get(invalid_request_field or "", _ERROR_RECOVERY["invalid_request"]),
            ),
            cost_usd=0.0,
        )

    if retry_safe_on_request_failed:
        message = "OpenRouteService could not complete this request. Try again shortly."
        recovery = _ERROR_RECOVERY["request_failed"]
    else:
        message = request_failed_message or "OpenRouteService could not complete this isochrone request."
        recovery = no_retry_recovery or _ISOCHRONE_NO_RETRY
    return ActionResult(
        data=_error_payload(
            "request_failed",
            message,
            retry_safe=retry_safe_on_request_failed,
            recovery=recovery,
        ),
        cost_usd=0.0,
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _idle_error_fields(*, message: str | None = None) -> dict[str, Any]:
    return {
        "error_type": None,
        "error_code": None,
        "retry_after_seconds": None,
        "message": message,
        "field": None,
        "valid_alternatives": None,
        "recovery": None,
        "retry_safe": None,
    }


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


def _geojson_export_file(geojson: dict[str, Any]) -> dict[str, str] | None:
    """Return a platform file, or None if the GeoJSON cannot be serialized."""
    try:
        return _platform_file(
            "isochrones.geojson",
            "application/geo+json",
            json.dumps(geojson, allow_nan=False),
        )
    except (TypeError, ValueError):
        return None


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _labelled_locations(raw: Any, *, field: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise MatrixInputError(f"{field} must be a list of labelled coordinates.", field)
    seen: set[str] = set()
    points: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise MatrixInputError(
                f"Each {field} entry must be an object with id, latitude, and longitude.",
                field,
            )
        ident = item.get("id")
        if not isinstance(ident, str) or not ident.strip():
            raise MatrixInputError(f"Each {field} entry needs a non-empty id.", field)
        if ident in seen:
            raise MatrixInputError(f"Duplicate {field} id '{ident}'.", field)
        seen.add(ident)
        latitude = _numeric_coordinate(item.get("latitude"))
        longitude = _numeric_coordinate(item.get("longitude"))
        if latitude is None or longitude is None or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise MatrixInputError(f"Each {field} entry needs valid WGS84 latitude and longitude.", field)
        points.append({"id": ident, "latitude": latitude, "longitude": longitude})
    if not points:
        raise MatrixInputError(f"At least one {field} entry is required.", field)
    return points


def _matrix_route_batches(origin_count: int, destination_count: int) -> list[tuple[int, int, int, int]]:
    max_routes = MATRIX_MAX_ROUTES
    if origin_count < 1 or destination_count < 1:
        raise MatrixInputError("At least one origin and one destination are required.", "origins")
    if origin_count * destination_count <= max_routes:
        return [(0, origin_count, 0, destination_count)]
    batches: list[tuple[int, int, int, int]] = []
    if destination_count <= max_routes:
        origin_chunk = max(1, max_routes // destination_count)
        for origin_start in range(0, origin_count, origin_chunk):
            batches.append((origin_start, min(origin_start + origin_chunk, origin_count), 0, destination_count))
        return batches
    if origin_count <= max_routes:
        destination_chunk = max(1, max_routes // origin_count)
        for destination_start in range(0, destination_count, destination_chunk):
            batches.append(
                (0, origin_count, destination_start, min(destination_start + destination_chunk, destination_count))
            )
        return batches
    destination_chunk = min(destination_count, max_routes)
    origin_chunk = max(1, max_routes // destination_chunk)
    for origin_start in range(0, origin_count, origin_chunk):
        for destination_start in range(0, destination_count, destination_chunk):
            batches.append(
                (
                    origin_start,
                    min(origin_start + origin_chunk, origin_count),
                    destination_start,
                    min(destination_start + destination_chunk, destination_count),
                )
            )
    return batches


def _snaps_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in _SNAP_KEYS:
        first = left.get(key)
        second = right.get(key)
        if first is None or second is None:
            continue
        if isinstance(first, float) and isinstance(second, float):
            if abs(first - second) > 1e-6:
                return True
        elif first != second:
            return True
    return False


def _merge_snap(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return incoming
    if _snaps_conflict(existing, incoming):
        raise ProviderResponseError("OpenRouteService returned conflicting snapped locations for the same id.")
    merged = dict(existing)
    for key in _SNAP_KEYS:
        if merged.get(key) is None:
            merged[key] = incoming.get(key)
    return merged


def _snap_record(point: dict[str, Any], provider_item: Any) -> dict[str, Any]:
    record = {
        "id": point["id"],
        "latitude": point["latitude"],
        "longitude": point["longitude"],
        "snapped_latitude": None,
        "snapped_longitude": None,
        "snapped_distance_metres": None,
        "name": None,
    }
    if provider_item is None:
        return record
    if not isinstance(provider_item, dict):
        raise ProviderResponseError("OpenRouteService returned a snapped location that is not an object.")
    location = provider_item.get("location")
    if isinstance(location, (list, tuple)) and len(location) >= 2:
        record["snapped_longitude"] = _finite_or_none(location[0])
        record["snapped_latitude"] = _finite_or_none(location[1])
    record["snapped_distance_metres"] = _finite_or_none(provider_item.get("snapped_distance"))
    name = provider_item.get("name")
    record["name"] = name.strip() if isinstance(name, str) and name.strip() else None
    return record


def _as_matrix_body(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise ProviderResponseError("OpenRouteService returned a non-JSON matrix response.") from None
    if not isinstance(value, dict):
        raise ProviderResponseError("OpenRouteService returned an unexpected matrix response.")
    return value


def _require_grid(name: str, value: Any, row_count: int, column_count: int) -> list[list[Any]]:
    if not isinstance(value, list) or len(value) != row_count:
        raise ProviderResponseError(
            f"OpenRouteService returned a {name} matrix that does not match the requested origins and destinations."
        )
    grid: list[list[Any]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != column_count:
            raise ProviderResponseError(
                f"OpenRouteService returned a {name} matrix that does not match the requested origins and destinations."
            )
        grid.append(row)
    return grid


def _optional_snap_list(name: str, value: Any, count: int) -> list[Any] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != count:
        raise ProviderResponseError(f"OpenRouteService returned {name} that do not match the requested locations.")
    return value


def _parse_matrix_batch(
    body: dict[str, Any],
    origin_chunk: list[dict[str, Any]],
    destination_chunk: list[dict[str, Any]],
    include_distance: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Any]:
    durations = _require_grid("duration", body.get("durations"), len(origin_chunk), len(destination_chunk))
    distances = None
    if include_distance:
        distances = _require_grid("distance", body.get("distances"), len(origin_chunk), len(destination_chunk))
    source_snaps = _optional_snap_list("sources", body.get("sources"), len(origin_chunk))
    destination_snaps = _optional_snap_list("destinations", body.get("destinations"), len(destination_chunk))
    pairs: list[dict[str, Any]] = []
    origins_out: list[dict[str, Any]] = []
    for index, origin in enumerate(origin_chunk):
        provider_source = source_snaps[index] if source_snaps is not None else None
        origins_out.append(_snap_record(origin, provider_source))
        distance_row = distances[index] if distances is not None else None
        for dest_index, destination in enumerate(destination_chunk):
            pairs.append(
                {
                    "origin_id": origin["id"],
                    "destination_id": destination["id"],
                    "duration_seconds": _finite_or_none(durations[index][dest_index]),
                    "distance_metres": _finite_or_none(distance_row[dest_index]) if distance_row is not None else None,
                }
            )
    destinations_out = []
    for dest_index, destination in enumerate(destination_chunk):
        provider_dest = destination_snaps[dest_index] if destination_snaps is not None else None
        destinations_out.append(_snap_record(destination, provider_dest))
    return pairs, origins_out, destinations_out, body.get("metadata")


def _matrix_request_payload(
    origin_chunk: list[dict[str, Any]],
    destination_chunk: list[dict[str, Any]],
    include_distance: bool,
) -> dict[str, Any]:
    locations = [[point["longitude"], point["latitude"]] for point in origin_chunk + destination_chunk]
    origin_count = len(origin_chunk)
    destination_count = len(destination_chunk)
    return {
        "locations": locations,
        "sources": [str(index) for index in range(origin_count)],
        "destinations": [str(index) for index in range(origin_count, origin_count + destination_count)],
        "metrics": ["duration", "distance"] if include_distance else ["duration"],
        "resolve_locations": True,
        "units": "m",
    }


def _matrix_export_file(compact: dict[str, Any]) -> dict[str, str] | None:
    try:
        return _platform_file(
            "travel_time_matrix.json",
            "application/json",
            json.dumps(compact, allow_nan=False),
        )
    except (TypeError, ValueError):
        return None


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
                        **_idle_error_fields(message="No matching address was found."),
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
                    **_idle_error_fields(
                        message="Confirm this match before downstream use." if best["is_low_confidence"] else None
                    ),
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
                "smoothing": 0,
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
                exported = _geojson_export_file(normalized)
                if exported is not None:
                    files.append(exported)
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
            return _provider_error(
                error,
                retry_safe_on_request_failed=False,
                retry_safe_on_provider_error=False,
            )


async def _execute_travel_time_matrix(inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
    origins = _labelled_locations(inputs["origins"], field="origins")
    destinations = _labelled_locations(inputs["destinations"], field="destinations")
    include_distance = bool(inputs.get("include_distance", False))
    export_format = inputs.get("export_format")
    profile = inputs.get("travel_mode", "driving-car")
    pair_count = len(origins) * len(destinations)
    if pair_count > MATRIX_MAX_PAIRS:
        raise MatrixInputError(
            f"Origin-destination pairs must be at most {MATRIX_MAX_PAIRS}. This request has {pair_count}.",
            "origins",
        )

    pair_map: dict[tuple[str, str], dict[str, Any]] = {}
    origin_snaps: dict[str, dict[str, Any]] = {}
    destination_snaps: dict[str, dict[str, Any]] = {}
    provider_metadata: Any = None
    billed_batch = False
    batches = _matrix_route_batches(len(origins), len(destinations))

    for origin_start, origin_end, destination_start, destination_end in batches:
        origin_chunk = origins[origin_start:origin_end]
        destination_chunk = destinations[destination_start:destination_end]
        payload = _matrix_request_payload(origin_chunk, destination_chunk, include_distance)
        try:
            response = await context.fetch(
                MATRIX_URL_TEMPLATE.format(profile=profile),
                method="POST",
                headers=_isochrone_headers(context),
                json=payload,
                timeout=MATRIX_TIMEOUT_SECONDS,
                retry_count=_fetch_retry_count(context),
            )
        except RateLimitError as error:
            if not billed_batch:
                raise
            return ActionResult(
                data=_error_payload(
                    "rate_limit",
                    "OpenRouteService rate limit reached after part of this matrix request was billed.",
                    retry_after_seconds=error.retry_after,
                    retry_safe=False,
                    recovery=_MATRIX_NO_RETRY,
                ),
                cost_usd=0.0,
            )
        body = _as_matrix_body(response.data)
        batch_pairs, batch_origins, batch_destinations, metadata = _parse_matrix_batch(
            body, origin_chunk, destination_chunk, include_distance
        )
        if provider_metadata is None and metadata is not None:
            provider_metadata = metadata
        for pair in batch_pairs:
            key = (pair["origin_id"], pair["destination_id"])
            if key in pair_map:
                raise ProviderResponseError("OpenRouteService returned duplicate origin-destination pairs.")
            pair_map[key] = pair
        for record in batch_origins:
            origin_snaps[record["id"]] = _merge_snap(origin_snaps.get(record["id"]), record)
        for record in batch_destinations:
            destination_snaps[record["id"]] = _merge_snap(destination_snaps.get(record["id"]), record)
        billed_batch = True

    expected = [(origin["id"], destination["id"]) for origin in origins for destination in destinations]
    if set(pair_map) != set(expected):
        raise ProviderResponseError("OpenRouteService did not return a duration for every origin-destination pair.")
    pairs = [pair_map[key] for key in expected]
    compact_origins = [origin_snaps[origin["id"]] for origin in origins]
    compact_destinations = [destination_snaps[destination["id"]] for destination in destinations]
    if len(batches) > 1 and isinstance(provider_metadata, dict):
        provider_metadata = {
            key: value for key, value in provider_metadata.items() if key not in _BATCHED_METADATA_OMIT
        }
    engine = _engine_fields(provider_metadata)
    compact = {
        "profile": profile,
        "metrics": ["duration", "distance"] if include_distance else ["duration"],
        "origins": compact_origins,
        "destinations": compact_destinations,
        "pairs": pairs,
        "unreachable_count": sum(1 for pair in pairs if pair["duration_seconds"] is None),
        "provider_metadata": provider_metadata,
        "attribution": engine["attribution"],
        "engine_version": engine["engine_version"],
        "build_date": engine["build_date"],
        "graph_date": engine["graph_date"],
        "osm_date": engine["osm_date"],
    }
    files: list[dict[str, str]] = []
    if export_format == "json":
        exported = _matrix_export_file(compact)
        if exported is not None:
            files.append(exported)
    return ActionResult(
        data={
            "result": True,
            **compact,
            "files": files,
            **_idle_error_fields(),
        },
        cost_usd=0.0,
    )


@openrouteservice.action("get_travel_time_matrix")
class GetTravelTimeMatrix(ActionHandler):
    """Return road-network durations for labelled origin and destination coordinates."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            return await _execute_travel_time_matrix(inputs, context)
        except TimeoutError:
            return ActionResult(
                data=_error_payload(
                    "timeout",
                    "OpenRouteService did not complete this matrix request in time.",
                    retry_safe=False,
                    recovery=_MATRIX_NO_RETRY,
                ),
                cost_usd=0.0,
            )
        except (
            RateLimitError,
            HTTPError,
            ProviderResponseError,
            ValueError,
            aiohttp.ClientError,
        ) as error:
            field = error.field if isinstance(error, MatrixInputError) else "origins"
            return _provider_error(
                error,
                invalid_request_field=field,
                retry_safe_on_request_failed=False,
                retry_safe_on_provider_error=False,
                request_failed_message="OpenRouteService could not complete this matrix request.",
                no_retry_recovery=_MATRIX_NO_RETRY,
            )
