"""Stats NZ Datafinder integration backed by Koordinates WFS/API services.

SECURITY MODEL:
---------------
Datafinder carries the API key in the WFS request *path*
(``…/services;key=<KEY>/wfs/layer-<id>``), not a header. The SDK's
``context.fetch`` logs the full URL on error, which would leak the key.
WFS calls therefore go through ``aiohttp`` directly (see ``_wfs_request``),
and no provider or transport error text is surfaced: it is used only to
classify a failure. REST catalogue/metadata calls use ``context.fetch``
with ``Authorization: Key <KEY>`` because that URL does not contain the key.

TRADE-OFF — no retries or backoff on WFS:
-----------------------------------------
Bypassing ``context.fetch`` also means forgoing the SDK client's request
resilience. This version implements none of its own: one attempt per WFS
request, no exponential backoff, and a fixed ``WFS_REQUEST_TIMEOUT_SECONDS``
timeout. HTTP 429 is mapped to the same retry hint as REST ``RateLimitError``,
but ``Retry-After`` is not parsed. Retrying is the caller's responsibility.
WFS calls set ``allow_redirects=False`` so a 301/302 cannot drop a POST
``cql_filter`` or follow a key-bearing URL off-origin. See README.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, NamedTuple
from urllib.parse import quote, urljoin, urlparse

import aiohttp
from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)
from defusedxml import ElementTree as DefusedET
from pyproj import Geod
from shapely import make_valid
from shapely.affinity import translate
from shapely.errors import ShapelyError
from shapely.geometry import shape

stats_nz_datafinder = Integration.load()

API_BASE_URL = "https://datafinder.stats.govt.nz/services/api/v1"
_DATAFINDER_HOST = "datafinder.stats.govt.nz"
WFS_VERSION = "2.0.0"
WFS_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_GEOMETRY_FIELD = "Shape"
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 10
DEFAULT_AREA_MAX_PAGES = 100
DEFAULT_MISSING_VALUES = [-999, -997]
DEFAULT_MAX_SOURCE_FEATURES = 10_000
OVERLAP_TOLERANCE = 1e-6
MAX_DESCRIPTION_CHARS = 400
GEOJSON_MAX_BYTES = 5 * 1024 * 1024
_AREA_GEOMETRY_TYPES = frozenset({"Polygon", "MultiPolygon"})
_GEOD = Geod(ellps="WGS84")
ADDITIVE_COUNT = "additive_count"
COUNT_UNIT = "count"
UNSCOPED_ERROR = (
    "Provide geometry, file, bbox, or at least one attribute filter. Unscoped national scans are not supported."
)
_UNEXPECTED_ERROR = (
    "The Stats NZ Datafinder integration hit an unexpected error handling this request. "
    "Check your inputs and try again."
)
_CQL_OPERATORS = {
    "eq": "=",
    "neq": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
}
_KEY_IN_TEXT = re.compile(r"(services;key=)[^/\s\"']+", re.IGNORECASE)
_GEOGRAPHY_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9]*_V\d+_00$")
_CODED_FIELD = re.compile(r"^VAR_\d+_\d+$", re.IGNORECASE)


class DatafinderError(Exception):
    """An error whose message this module authored and is safe to surface.

    Only ``DatafinderError`` messages reach the caller from the WFS path:
    request URLs carry the API key, and GeoServer exception reports may echo
    the submitted CQL filter. Provider and transport text is never included.
    """


def _contract_error(
    *,
    message: str,
    error_code: str,
    recovery: str,
    field: str | None = None,
    valid_alternatives: list[str] | None = None,
    retry_safe: bool = False,
) -> str:
    """Build a compact, corrective error message without provider payloads."""
    parts = [message, f"Error code: {error_code}."]
    if field:
        parts.append(f"Affected field: {field}.")
    if valid_alternatives:
        shown = [str(item) for item in valid_alternatives[:8]]
        alternatives = ", ".join(shown)
        if len(valid_alternatives) > 8:
            alternatives += ", …"
        parts.append(f"Valid alternatives: {alternatives}.")
    parts.append(f"Recovery: {recovery}.")
    parts.append("Retrying this request is safe." if retry_safe else "Retrying this request is not safe.")
    return " ".join(parts)


class _WfsResponse(NamedTuple):
    """Minimal response wrapper: the pieces the error/parse helpers need."""

    status: int
    data: Any


class _CollectedFeatures(NamedTuple):
    features: list[Any]
    pages: int
    matched: int | None
    truncated: bool
    duplicate_count: int


def _redact(text: Any) -> str:
    """Strip the API key out of any message before it can be logged/surfaced."""
    return _KEY_IN_TEXT.sub(r"\1<redacted>", str(text or ""))


def _get_api_key(context: ExecutionContext) -> str:
    auth = context.auth or {}
    credentials = auth.get("credentials", {}) if isinstance(auth, dict) else {}
    api_key = credentials.get("api_key") if isinstance(credentials, dict) else None
    if not isinstance(api_key, str) or not api_key.strip():
        raise DatafinderError("A Stats NZ Datafinder API key is required.")
    return api_key


def _headers(context: ExecutionContext) -> dict[str, str]:
    return {"Authorization": f"Key {_get_api_key(context)}"}


def _trusted_datafinder_url(url: str) -> str | None:
    """Return ``url`` only if it is HTTPS on the Datafinder host.

    Relative paths are resolved against ``API_BASE_URL``. Scheme-relative
    hosts (``//example.test/...``) are rejected so ``urljoin`` cannot
    retarget the request. Metadata-supplied attachment URLs are untrusted;
    the API key must not be sent off-origin.
    """
    candidate = url.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if not parsed.scheme:
        if parsed.netloc:
            return None
        candidate = urljoin(f"{API_BASE_URL}/", candidate)
        parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.hostname != _DATAFINDER_HOST:
        return None
    if parsed.port not in (None, 443):
        return None
    return candidate


def _wfs_url(context: ExecutionContext, layer_id: int) -> str:
    """Build Datafinder's documented per-layer key-in-path WFS URL."""
    return f"https://datafinder.stats.govt.nz/services;key={quote(_get_api_key(context), safe='')}/wfs/layer-{layer_id}"


def _parse_wfs_body(text: str, content_type: str) -> Any:
    """Parse a WFS body: JSON payloads → dict, anything else (XML) → str."""
    if "json" in content_type.lower():
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


async def _wfs_request(
    context: ExecutionContext, *, params: dict[str, Any], layer_id: int, method: str = "GET"
) -> _WfsResponse:
    """Issue a GET or POST to the per-layer WFS endpoint with aiohttp directly.

    Deliberately does not use ``context.fetch``: Datafinder puts the API key in
    the URL path, and the SDK's fetch logs the full URL on error. Transport
    failures are re-raised with a fixed message, never the underlying
    exception text (aiohttp builds that from the request URL).

    GetFeature uses POST so a large CQL catchment is not packed into the query
    string (GET URLs 414). GetCapabilities stays GET.
    """
    url = _wfs_url(context, layer_id)
    query = {key: str(value) for key, value in params.items() if value is not None}
    timeout = aiohttp.ClientTimeout(total=WFS_REQUEST_TIMEOUT_SECONDS)
    method = method.upper()

    session = getattr(context, "_session", None)
    if not isinstance(session, aiohttp.ClientSession):
        session = aiohttp.ClientSession()
        context._session = session

    request_kwargs: dict[str, Any] = {
        "timeout": timeout,
        "ssl": True,
        # POST GetFeature puts cql_filter in the body. aiohttp turns 301/302
        # POST into GET with an empty body, which would un-scope the query.
        # The path also carries the API key — do not follow Location.
        "allow_redirects": False,
    }
    if method == "POST":
        request_kwargs["data"] = query
        request = session.post
    else:
        request_kwargs["params"] = query
        request = session.get

    try:
        async with request(url, **request_kwargs) as response:
            text = await response.text()
            content_type = response.headers.get("Content-Type", "")
            return _WfsResponse(status=response.status, data=_parse_wfs_body(text, content_type))
    except asyncio.TimeoutError:
        raise DatafinderError("Datafinder WFS request timed out.") from None
    except aiohttp.ClientError:
        raise DatafinderError(
            "Datafinder WFS request failed: could not reach the Stats NZ Datafinder service."
        ) from None


def _extract_exception_text(xml: str) -> str:
    """Pull the human-readable message out of an OWS/WFS exception report.

    Used only to classify a failure — the returned text may echo the submitted
    CQL filter, so it must never be surfaced.
    """
    for tag in ("ExceptionText", "ServiceException"):
        start = xml.find(f"<ows:{tag}")
        if start == -1:
            start = xml.find(f"<{tag}")
        if start != -1:
            gt = xml.find(">", start)
            end = xml.find("<", gt + 1)
            if gt != -1 and end != -1:
                return xml[gt + 1 : end].strip()
    return xml.strip()[:400]


def _is_unknown_layer_exception(text: str) -> bool:
    low = text.lower()
    return "unknown" in low and ("feature type" in low or "typename" in low or "layer-" in low)


def _check_wfs_response(response: _WfsResponse, *, layer_id: int) -> None:
    """Raise a curated error for non-2xx responses or WFS exception reports.

    Provider error text is used only to classify the failure and is never
    included in the raised message.
    """
    status = response.status
    data = response.data
    is_xml_exception = isinstance(data, str) and ("ExceptionReport" in data or "ServiceException" in data)
    unknown_layer = is_xml_exception and _is_unknown_layer_exception(_extract_exception_text(data))

    if isinstance(status, int) and 200 <= status < 300:
        if unknown_layer:
            raise DatafinderError(
                f"Layer {layer_id} is not available over WFS for the connected API key. "
                "Check that the layer exposes WFS and that the key is authorised to query it."
            )
        if is_xml_exception:
            raise DatafinderError(
                f"Datafinder rejected the WFS request for layer {layer_id}. "
                "Check the geometry, attribute filters, and that the layer exposes WFS."
            )
        return

    if status == 401:
        raise DatafinderError("Datafinder rejected the API key. Check the connected account.")
    if status == 403:
        raise DatafinderError(f"The connected Datafinder API key is not permitted to query layer {layer_id}.")
    if unknown_layer or status == 404:
        raise DatafinderError(
            f"Layer {layer_id} is not available over WFS. "
            "Check the layer id and that the layer exposes WFS for this key."
        )
    if status == 400:
        raise DatafinderError(
            f"Datafinder rejected the WFS request for layer {layer_id}. "
            "Check the geometry, attribute filters, and that the layer exposes WFS."
        )
    if status == 429:
        raise DatafinderError("Datafinder rate-limited this request. Please retry shortly.")
    raise DatafinderError("Datafinder could not complete the request. Please try again later.")


async def _wfs_get_capabilities(context: ExecutionContext, layer_id: int) -> str:
    response = await _wfs_request(
        context,
        params={"service": "WFS", "version": WFS_VERSION, "request": "GetCapabilities"},
        layer_id=layer_id,
    )
    _check_wfs_response(response, layer_id=layer_id)
    if not isinstance(response.data, str):
        raise DatafinderError("Datafinder returned an invalid WFS capabilities response.")
    return response.data


async def _wfs_get_features(
    context: ExecutionContext,
    layer_id: int,
    *,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = await _wfs_request(context, params=params, layer_id=layer_id, method="POST")
    _check_wfs_response(response, layer_id=layer_id)
    data = response.data
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise DatafinderError("Datafinder returned a malformed WFS feature response.")
    return data


def _provider_error(status: int, *, layer_id: int | None = None) -> ActionError:
    if status == 401:
        return ActionError(message="Datafinder rejected the API key. Check the connected account.")
    if status == 403:
        if layer_id is None:
            return ActionError(message="The connected Datafinder API key is not permitted to perform this request.")
        return ActionError(message=f"The connected Datafinder API key is not permitted to query layer {layer_id}.")
    if status == 404:
        if layer_id is None:
            return ActionError(message="Datafinder could not find the requested resource.")
        return ActionError(message=f"Datafinder could not find layer {layer_id}.")
    if status == 400:
        if layer_id is None:
            return ActionError(message="Datafinder rejected this request. Check the inputs and try again.")
        return ActionError(
            message=(
                f"Datafinder rejected the request for layer {layer_id}. "
                "Check the geometry, attribute filters, and that the layer exposes WFS."
            )
        )
    return ActionError(message="Datafinder could not complete the request. Please try again later.")


def _http_action_error(exc: HTTPError, *, layer_id: int | None = None) -> ActionError:
    if isinstance(exc, RateLimitError):
        return ActionError(message="Datafinder rate-limited this request. Please retry shortly.")
    return _provider_error(exc.status, layer_id=layer_id)


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and value.replace("_", "a").isalnum() and not value[0].isdigit()


def _wrap_longitude(lon: float) -> float:
    """Map a longitude onto (-180, 180], keeping +180 as +180."""
    wrapped = (lon + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0 if lon > 0 else -180.0
    return wrapped


def _lon_lat(position: Any, *, allow_unwrapped: bool = False) -> tuple[float, float]:
    if not isinstance(position, list) or len(position) < 2:
        raise DatafinderError("Each GeoJSON position must contain longitude and latitude.")
    lon, lat = position[0], position[1]
    if (
        isinstance(lon, bool)
        or isinstance(lat, bool)
        or not isinstance(lon, (int, float))
        or not isinstance(lat, (int, float))
    ):
        raise DatafinderError("GeoJSON longitude and latitude must be numbers.")
    lon_ok = -360 <= lon <= 360 if allow_unwrapped else -180 <= lon <= 180
    if not lon_ok or not -90 <= lat <= 90:
        raise DatafinderError("GeoJSON coordinates must be WGS84 longitude/latitude values.")
    return float(lon), float(lat)


def _wkt_ring(ring: Any, *, allow_unwrapped: bool = False) -> str:
    if not isinstance(ring, list) or len(ring) < 4:
        raise DatafinderError("Each polygon ring must contain at least four positions.")
    points = [_lon_lat(point, allow_unwrapped=allow_unwrapped) for point in ring]
    if points[0] != points[-1]:
        raise DatafinderError("Each polygon ring must be closed.")
    return "(" + ", ".join(f"{lon:.15g} {lat:.15g}" for lon, lat in points) + ")"


def _wkt_polygon(polygon: Any, *, allow_unwrapped: bool = False) -> str:
    if not isinstance(polygon, list) or not polygon:
        raise DatafinderError("Each polygon must contain an exterior ring.")
    rings = [_wkt_ring(ring, allow_unwrapped=allow_unwrapped) for ring in polygon]
    return "POLYGON(" + ", ".join(rings) + ")"


def _wkt_geometry(geometry: dict[str, Any], *, allow_unwrapped: bool = False) -> str:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        lon, lat = _lon_lat(coordinates, allow_unwrapped=allow_unwrapped)
        return f"POINT({lon:.15g} {lat:.15g})"
    if geometry_type == "Polygon":
        return _wkt_polygon(coordinates, allow_unwrapped=allow_unwrapped)
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise DatafinderError("A MultiPolygon must contain at least one polygon.")
        polygons = [
            _wkt_polygon(polygon, allow_unwrapped=allow_unwrapped).removeprefix("POLYGON") for polygon in coordinates
        ]
        return "MULTIPOLYGON(" + ", ".join(polygons) + ")"
    raise DatafinderError("geometry.type must be Point, Polygon, or MultiPolygon.")


def _bbox_raw(bbox: Any) -> tuple[float, float, float, float]:
    """Validate bbox and return the original [west, south, east, north] values."""
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise DatafinderError("bbox must be [west, south, east, north] in WGS84.")
    values: list[float] = []
    for value in bbox:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DatafinderError("bbox values must be numbers.")
        values.append(float(value))
    west, south, east, north = values
    # Datafinder national extents use unwrapped east ≈ 184.5 (Chatham Islands).
    if not (-360 <= west <= 360 and -360 <= east <= 360 and -90 <= south <= 90 and -90 <= north <= 90):
        raise DatafinderError("bbox must be WGS84 [west, south, east, north].")
    if south >= north:
        raise DatafinderError("bbox requires south < north.")
    if _wrap_longitude(west) == _wrap_longitude(east):
        raise DatafinderError("bbox requires a non-zero longitude span.")
    return west, south, east, north


def _parse_bbox(bbox: Any) -> tuple[float, float, float, float]:
    """Return wrapped [west, south, east, north]. west may be > east (antimeridian)."""
    west, south, east, north = _bbox_raw(bbox)
    return _wrap_longitude(west), south, _wrap_longitude(east), north


def _bbox_rectangle(west: float, south: float, east: float, north: float) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


def _bbox_polygon(bbox: Any) -> dict[str, Any]:
    west, south, east, north = _parse_bbox(bbox)
    if west < east:
        return _bbox_rectangle(west, south, east, north)
    # Crosses 180°: split so GeoJSON rings stay in [-180, 180].
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [[[west, south], [180, south], [180, north], [west, north], [west, south]]],
            [[[-180, south], [east, south], [east, north], [-180, north], [-180, south]]],
        ],
    }


def _unwrapped_bbox_polygon(bbox: Any) -> dict[str, Any] | None:
    """Rectangle in the caller's longitude domain, or None if wrapping did not change it.

    Datafinder layers may store Chatham Islands at lon ≈ 184. A CQL clip that
    only uses wrapped rings (east ≈ -175.5) misses those features. When the
    input uses unwrapped longitudes or already crosses 180°, also send this
    eastward rectangle so INTERSECTS matches native unwrapped coordinates.
    """
    west, south, east, north = _bbox_raw(bbox)
    wrapped_west, wrapped_east = _wrap_longitude(west), _wrap_longitude(east)
    if -180 <= west <= 180 and -180 <= east <= 180 and west < east:
        return None
    east_u = east + 360.0 if east < west else east
    if east_u <= west or east_u - west >= 360.0:
        return None
    if wrapped_west == west and wrapped_east == east_u:
        return None
    return _bbox_rectangle(west, south, east_u, north)


def _unwrap_negative_longitudes(geometry: dict[str, Any]) -> dict[str, Any]:
    """Add 360° only to negative longitudes so mainland NZ and Chatham can coexist."""
    return {"type": geometry["type"], "coordinates": _shift_negative_longitudes(geometry.get("coordinates"))}


def _shift_negative_longitudes(coords: Any) -> Any:
    if isinstance(coords, list) and coords and isinstance(coords[0], (int, float)) and not isinstance(coords[0], bool):
        lon = float(coords[0])
        if lon < 0:
            lon += 360.0
        return [lon, *coords[1:]]
    if isinstance(coords, list):
        return [_shift_negative_longitudes(item) for item in coords]
    return coords


def _geojson_has_negative_longitude(geometry: dict[str, Any]) -> bool:
    stack: list[Any] = [geometry.get("coordinates")]
    while stack:
        item = stack.pop()
        if isinstance(item, list) and item and isinstance(item[0], (int, float)) and not isinstance(item[0], bool):
            if float(item[0]) < 0:
                return True
            continue
        if isinstance(item, list):
            stack.extend(item)
    return False


def _cql_spatial_wkts(spatial_geometry: dict[str, Any] | None, inputs: dict[str, Any]) -> list[str]:
    """WKT clips for CQL INTERSECTS, covering wrapped and unwrapped storage."""
    if not spatial_geometry:
        return []
    wkts: list[str] = []

    def add(geometry: dict[str, Any], *, allow_unwrapped: bool = False) -> None:
        wkt = _wkt_geometry(geometry, allow_unwrapped=allow_unwrapped)
        if wkt not in wkts:
            wkts.append(wkt)

    add(spatial_geometry)
    if inputs.get("bbox"):
        extra = _unwrapped_bbox_polygon(inputs["bbox"])
        if extra is not None:
            add(extra, allow_unwrapped=True)
    elif _geojson_has_negative_longitude(spatial_geometry):
        add(_unwrap_negative_longitudes(spatial_geometry), allow_unwrapped=True)
    return wkts


def _cql_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.15g}"
    return "'" + str(value).replace("'", "''") + "'"


def _geometry_field(metadata: Any) -> str:
    data = metadata.get("data") if isinstance(metadata, dict) else None
    field = data.get("geometry_field") if isinstance(data, dict) else None
    return field if _is_identifier(field) else DEFAULT_GEOMETRY_FIELD


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return _cql_literal("%" + escaped + "%")


def _ilike_exact(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return _cql_literal(escaped)


def _attribute_clauses(attribute_filters: list[dict[str, Any]] | None) -> list[str]:
    clauses: list[str] = []
    for item in attribute_filters or []:
        operator = item.get("operator")
        property_name = item.get("property")
        value = item.get("value")
        if not _is_identifier(property_name):
            raise DatafinderError("Each attribute filter needs a valid property and supported operator.")
        if operator == "contains":
            if not isinstance(value, str) or not value:
                raise DatafinderError("contains filters require a non-empty string value.")
            clauses.append(f"{property_name} ILIKE {_like_pattern(value)}")
            continue
        if operator == "ieq":
            if not isinstance(value, str) or not value:
                raise DatafinderError("ieq filters require a non-empty string value.")
            clauses.append(f"{property_name} ILIKE {_ilike_exact(value)}")
            continue
        if operator not in _CQL_OPERATORS:
            raise DatafinderError("Each attribute filter needs a valid property and supported operator.")
        if isinstance(value, (dict, list)) or value is None:
            raise DatafinderError("Attribute filter values must be strings, numbers, or booleans.")
        clauses.append(f"{property_name} {_CQL_OPERATORS[operator]} {_cql_literal(value)}")
    return clauses


def _build_cql_filter(
    spatial_wkt: str | list[str] | None, attribute_filters: list[dict[str, Any]] | None, geometry_field: str
) -> str:
    """Build a GeoServer CQL filter from optional spatial WKT clip(s) and attribute clauses."""
    clauses = _attribute_clauses(attribute_filters)
    if isinstance(spatial_wkt, str):
        spatial_wkts = [spatial_wkt] if spatial_wkt else []
    else:
        spatial_wkts = [wkt for wkt in (spatial_wkt or []) if wkt]
    if spatial_wkts:
        parts = [f"INTERSECTS({geometry_field}, SRID=4326;{wkt})" for wkt in spatial_wkts]
        spatial = parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"
        return spatial + "".join(f" AND ({clause})" for clause in clauses)
    if not clauses:
        raise DatafinderError(UNSCOPED_ERROR)
    return " AND ".join(f"({clause})" for clause in clauses)


def _geojson_contract_error(
    *,
    message: str,
    error_code: str,
    recovery: str,
    field: str = "file",
    valid_alternatives: list[str] | None = None,
) -> DatafinderError:
    return DatafinderError(
        _contract_error(
            message=message,
            error_code=error_code,
            field=field,
            valid_alternatives=valid_alternatives,
            recovery=recovery,
            retry_safe=False,
        )
    )


def _json_values_equal(left: Any, right: Any) -> bool:
    """Compare GeoJSON property values. 30 == 30.0; True does not match 1."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return left == right


def _area_geometry(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    geom_type = value.get("type")
    coordinates = value.get("coordinates")
    if geom_type in _AREA_GEOMETRY_TYPES and coordinates is not None:
        return {"type": geom_type, "coordinates": coordinates}
    return None


def _feature_area_geometry(feature: Any) -> dict[str, Any] | None:
    if not isinstance(feature, dict):
        return None
    if feature.get("type") == "Feature":
        return _area_geometry(feature.get("geometry"))
    return _area_geometry(feature)


def _feature_properties(feature: Any) -> dict[str, Any]:
    if isinstance(feature, dict) and isinstance(feature.get("properties"), dict):
        return feature["properties"]
    return {}


def _read_geojson_file(file_obj: Any) -> Any:
    """Decode a platform file object (`name`, `contentType`, base64 `content`)."""
    if not isinstance(file_obj, dict):
        raise _geojson_contract_error(
            message="file must be a platform file object.",
            error_code="geojson_file_unreadable",
            recovery="Pass a GeoJSON file with name, contentType, and base64 content.",
        )
    content = file_obj.get("content")
    if not isinstance(content, str):
        raise _geojson_contract_error(
            message="The GeoJSON file could not be read.",
            error_code="geojson_file_unreadable",
            recovery="Pass a GeoJSON file with name, contentType, and base64 content.",
        )
    content = "".join(content.split())
    if not content:
        raise _geojson_contract_error(
            message="The GeoJSON file could not be read.",
            error_code="geojson_file_unreadable",
            recovery="Pass a GeoJSON file with name, contentType, and base64 content.",
        )
    padding_needed = len(content) % 4
    if padding_needed:
        content += "=" * (4 - padding_needed)
    max_encoded = (GEOJSON_MAX_BYTES * 4) // 3 + 8
    if len(content) > max_encoded:
        raise _geojson_contract_error(
            message="The GeoJSON file is larger than the 5 MB limit.",
            error_code="geojson_file_unreadable",
            recovery="Use a smaller FeatureCollection or pass a single Polygon/MultiPolygon file.",
        )
    try:
        raw_bytes = base64.b64decode(content, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _geojson_contract_error(
            message="The GeoJSON file could not be read.",
            error_code="geojson_file_unreadable",
            recovery="Pass a GeoJSON file with name, contentType, and base64 content.",
        ) from exc
    if len(raw_bytes) > GEOJSON_MAX_BYTES:
        raise _geojson_contract_error(
            message="The GeoJSON file is larger than the 5 MB limit.",
            error_code="geojson_file_unreadable",
            recovery="Use a smaller FeatureCollection or pass a single Polygon/MultiPolygon file.",
        )
    try:
        raw = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _geojson_contract_error(
            message="The GeoJSON file could not be read.",
            error_code="geojson_file_unreadable",
            recovery="Pass a UTF-8 GeoJSON FeatureCollection, Feature, or Polygon/MultiPolygon file.",
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _geojson_contract_error(
            message="The GeoJSON file is not valid JSON.",
            error_code="invalid_geojson",
            recovery="Pass RFC 7946 GeoJSON (FeatureCollection, Feature, or Polygon/MultiPolygon).",
        ) from exc


def _geojson_features(document: Any) -> tuple[list[Any], bool]:
    if not isinstance(document, dict):
        raise _geojson_contract_error(
            message="The GeoJSON file must be a FeatureCollection, Feature, or Polygon/MultiPolygon.",
            error_code="invalid_geojson",
            recovery="Export the catchment as RFC 7946 GeoJSON.",
        )
    doc_type = document.get("type")
    if doc_type == "FeatureCollection":
        features = document.get("features")
        if not isinstance(features, list) or any(
            not isinstance(item, dict) or item.get("type") != "Feature" for item in features
        ):
            raise _geojson_contract_error(
                message="GeoJSON FeatureCollection.features must be an array of Feature objects.",
                error_code="invalid_geojson",
                recovery="Export a FeatureCollection whose features array contains GeoJSON Features.",
            )
        return features, True
    if doc_type == "Feature":
        return [document], False
    if doc_type in _AREA_GEOMETRY_TYPES:
        return [{"type": "Feature", "geometry": document, "properties": {}}], False
    raise _geojson_contract_error(
        message="The GeoJSON file must be a FeatureCollection, Feature, or Polygon/MultiPolygon.",
        error_code="invalid_geojson",
        recovery="Export the catchment as RFC 7946 GeoJSON.",
        valid_alternatives=["FeatureCollection", "Feature", "Polygon", "MultiPolygon"],
    )


def _selected_area_geometry(feature: Any, *, field: str) -> dict[str, Any]:
    geometry = _feature_area_geometry(feature)
    if geometry is None:
        raise _geojson_contract_error(
            message="The selected GeoJSON feature must be a Polygon or MultiPolygon.",
            error_code="invalid_geometry",
            field=field,
            recovery="Choose a Polygon or MultiPolygon feature, or pass inline geometry.",
            valid_alternatives=["Polygon", "MultiPolygon"],
        )
    return geometry


def _auto_select_area_feature(features: list[Any]) -> tuple[Any, int]:
    eligible = [
        (index, feature) for index, feature in enumerate(features) if _feature_area_geometry(feature) is not None
    ]
    if len(eligible) == 1:
        index, feature = eligible[0]
        return feature, index
    if not eligible:
        raise _geojson_contract_error(
            message="The GeoJSON file does not contain a Polygon or MultiPolygon feature.",
            error_code="invalid_geometry",
            recovery="Pass a file that contains a Polygon or MultiPolygon.",
            valid_alternatives=["Polygon", "MultiPolygon"],
        )
    raise _geojson_contract_error(
        message="The GeoJSON file contains more than one Polygon or MultiPolygon. Select one feature.",
        error_code="ambiguous_geojson_feature",
        recovery="Pass feature_index (original features array) or feature_filter that matches exactly one feature.",
        field="feature_index",
    )


def _select_feature_by_index(features: list[Any], feature_index: Any) -> tuple[Any, int]:
    if type(feature_index) is not int or feature_index < 0 or feature_index >= len(features):
        raise _geojson_contract_error(
            message="feature_index is outside the GeoJSON features array.",
            error_code="geojson_feature_not_found",
            field="feature_index",
            recovery="Pass a 0-based index into the original features array.",
        )
    return features[feature_index], feature_index


def _select_feature_by_filter(features: list[Any], feature_filter: Any) -> tuple[Any, int, dict[str, Any]]:
    if not isinstance(feature_filter, dict):
        raise _geojson_contract_error(
            message="feature_filter must include property and equals.",
            error_code="geojson_feature_not_found",
            field="feature_filter",
            recovery="Pass feature_filter as {property, equals}.",
        )
    prop = feature_filter.get("property")
    if not isinstance(prop, str) or not prop or "equals" not in feature_filter:
        raise _geojson_contract_error(
            message="feature_filter must include property and equals.",
            error_code="geojson_feature_not_found",
            field="feature_filter",
            recovery="Pass feature_filter as {property, equals}.",
        )
    expected = feature_filter["equals"]
    matches: list[tuple[int, Any]] = []
    for index, feature in enumerate(features):
        properties = _feature_properties(feature)
        if prop not in properties:
            continue
        if _json_values_equal(properties[prop], expected):
            matches.append((index, feature))
    if not matches:
        raise _geojson_contract_error(
            message="feature_filter did not match any GeoJSON feature.",
            error_code="geojson_feature_not_found",
            field="feature_filter",
            recovery="Use a property/equals pair that matches exactly one feature in the file.",
        )
    if len(matches) > 1:
        raise _geojson_contract_error(
            message="feature_filter matched more than one GeoJSON feature.",
            error_code="ambiguous_geojson_feature",
            field="feature_filter",
            recovery="Narrow the filter so it matches exactly one feature, or pass feature_index.",
        )
    index, feature = matches[0]
    return feature, index, {prop: _feature_properties(feature)[prop]}


def _resolve_geojson_file(
    file_obj: Any,
    *,
    feature_index: int | None = None,
    feature_filter: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a platform GeoJSON file and return one Polygon/MultiPolygon plus a compact source citation."""
    if feature_index is not None and feature_filter is not None:
        raise _geojson_contract_error(
            message="Provide feature_index or feature_filter, not both.",
            error_code="conflicting_geometry_source",
            field="feature_index",
            recovery="Select the catchment with exactly one of feature_index or feature_filter.",
        )
    document = _read_geojson_file(file_obj)
    features, is_collection = _geojson_features(document)
    matched_properties: dict[str, Any] | None = None
    selector_field = "file"
    if feature_index is not None:
        if not is_collection:
            raise _geojson_contract_error(
                message="feature_index applies only to a GeoJSON FeatureCollection.",
                error_code="geojson_feature_not_found",
                field="feature_index",
                recovery="Omit feature_index for a Feature or bare Polygon, or pass a FeatureCollection.",
            )
        feature, index = _select_feature_by_index(features, feature_index)
        selector_field = "feature_index"
    elif feature_filter is not None:
        if not is_collection:
            raise _geojson_contract_error(
                message="feature_filter applies only to a GeoJSON FeatureCollection.",
                error_code="geojson_feature_not_found",
                field="feature_filter",
                recovery="Omit feature_filter for a Feature or bare Polygon, or pass a FeatureCollection.",
            )
        feature, index, matched_properties = _select_feature_by_filter(features, feature_filter)
        selector_field = "feature_filter"
    else:
        feature, index = _auto_select_area_feature(features)
    geometry = _selected_area_geometry(feature, field=selector_field)
    name = file_obj.get("name") if isinstance(file_obj, dict) else None
    source: dict[str, Any] = {
        "name": name if isinstance(name, str) and name else None,
        "feature_index": index if is_collection else None,
    }
    if matched_properties is not None:
        source["matched_properties"] = matched_properties
    return geometry, source


def _bind_geojson_file(inputs: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (geometry, file source). A platform GeoJSON file is an alternative to inline geometry."""
    file_obj = inputs.get("file")
    geometry = inputs.get("geometry")
    feature_index = inputs.get("feature_index")
    feature_filter = inputs.get("feature_filter")
    if (feature_index is not None or feature_filter is not None) and file_obj is None:
        raise _geojson_contract_error(
            message="feature_index and feature_filter are only valid with file.",
            error_code="conflicting_geometry_source",
            field="feature_index" if feature_index is not None else "feature_filter",
            recovery="Pass file, or omit feature_index and feature_filter.",
        )
    if file_obj is not None:
        if geometry is not None:
            raise _geojson_contract_error(
                message="Provide geometry or file, not both.",
                error_code="conflicting_geometry_source",
                recovery="Pass either inline geometry or a GeoJSON file, not both.",
            )
        return _resolve_geojson_file(file_obj, feature_index=feature_index, feature_filter=feature_filter)
    return geometry, None


def _resolve_query_scope(inputs: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Return (spatial GeoJSON or None, query kind). Reject unconstrained scans."""
    geometry = inputs.get("geometry")
    bbox = inputs.get("bbox")
    filters = inputs.get("attribute_filters") or []
    if geometry is not None and bbox is not None:
        raise DatafinderError(
            _contract_error(
                message="Provide only one spatial source: geometry, file, or bbox.",
                error_code="conflicting_geometry_source",
                recovery="Pass either inline geometry, a GeoJSON file, or bbox — not more than one.",
                retry_safe=False,
            )
        )
    if bbox:
        return _bbox_polygon(bbox), "bbox"
    if geometry:
        kind = geometry.get("type") if isinstance(geometry, dict) else None
        if kind not in ("Point", "Polygon", "MultiPolygon"):
            raise DatafinderError("geometry.type must be Point, Polygon, or MultiPolygon.")
        return geometry, kind
    if filters:
        return None, "attribute"
    raise DatafinderError(UNSCOPED_ERROR)


def _local_feature_type_name(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def _resolve_feature_type(layer_id: int, capability_document: str) -> str:
    """Return the advertised WFS feature type, falling back to layer-{id}."""
    requested_name = f"layer-{layer_id}"
    try:
        root = DefusedET.fromstring(capability_document.encode("utf-8"))
    except DefusedET.ParseError as exc:
        raise DatafinderError("Datafinder returned malformed WFS capabilities.") from exc

    for feature_type in root.findall(".//{*}FeatureType"):
        name = feature_type.findtext("{*}Name")
        if isinstance(name, str) and _local_feature_type_name(name) == requested_name:
            return name
    return requested_name


def _total_matched(collection: dict[str, Any]) -> int | None:
    """Return a numeric match count, or None when the server reports it as unknown."""
    for key in ("numberMatched", "totalFeatures"):
        value = collection.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _short_description(value: Any, *, limit: int = MAX_DESCRIPTION_CHARS) -> str | None:
    """Keep the first paragraph of a catalogue blurb, capped for agent context."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    paragraph = re.split(r"\n\s*\n", text, maxsplit=1)[0]
    paragraph = re.sub(r"\s+", " ", paragraph).strip()
    if len(paragraph) <= limit:
        return paragraph
    clipped = paragraph[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return clipped + "…"


def _fields(metadata: Any) -> list[dict[str, Any]]:
    data = metadata.get("data") if isinstance(metadata, dict) else None
    raw_fields = data.get("fields") if isinstance(data, dict) else None
    geometry_field = _geometry_field(metadata)
    if not isinstance(raw_fields, list):
        return []
    fields: list[dict[str, Any]] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if item.get("type") == "geometry" or name == geometry_field:
            continue
        field: dict[str, Any] = {
            "name": name,
            "type": item.get("type") if isinstance(item.get("type"), str) else None,
        }
        title = item.get("title") or item.get("label")
        if isinstance(title, str) and title.strip():
            field["title"] = title
        measure = item.get("measure")
        if isinstance(measure, str) and measure.strip():
            field["measure"] = measure
        year = item.get("year")
        if isinstance(year, str) and year.strip():
            field["year"] = year
        if _CODED_FIELD.fullmatch(name):
            field["coded"] = True
        fields.append(field)
    return fields


def _is_coded_field(name: Any) -> bool:
    return isinstance(name, str) and bool(_CODED_FIELD.fullmatch(name))


def _requested_attribute_names(
    metadata: Any, *, fields: list[Any] | None, include_coded_fields: bool
) -> list[str] | None:
    """Attribute names to keep. None means 'schema unknown — do not constrain WFS'."""
    schema_names = [field["name"] for field in _fields(metadata) if _is_identifier(field.get("name"))]
    if fields is not None:
        requested = [name for name in fields if _is_identifier(name)]
        if len(requested) != len(fields):
            raise DatafinderError("Each fields entry must be a valid property name.")
        if not requested:
            raise DatafinderError("fields must contain at least one property name.")
        return requested
    if not schema_names:
        return None
    if include_coded_fields:
        return schema_names
    return [name for name in schema_names if not _is_coded_field(name)]


def _project_properties(
    properties: Any, *, fields: list[str] | None, include_coded_fields: bool
) -> tuple[dict[str, Any], int]:
    """Return (projected properties, count of VAR_* keys omitted)."""
    if not isinstance(properties, dict):
        return {}, 0
    coded_keys = [key for key in properties if _is_coded_field(key)]
    if fields is not None:
        allowed = {name for name in fields if _is_identifier(name)}
        kept = {key: value for key, value in properties.items() if key in allowed}
    elif include_coded_fields:
        kept = dict(properties)
    else:
        kept = {key: value for key, value in properties.items() if not _is_coded_field(key)}
    omitted = sum(1 for key in coded_keys if key not in kept)
    return kept, omitted


def _coded_fields_omitted_count(metadata: Any, *, fields: list[str] | None, include_coded_fields: bool) -> int:
    """How many schema VAR_* columns are not in the query output."""
    coded_in_schema = sum(1 for field in _fields(metadata) if _is_coded_field(field.get("name")))
    if include_coded_fields and fields is None:
        return 0
    if fields is not None:
        requested = {name for name in fields if _is_identifier(name)}
        return sum(
            1 for field in _fields(metadata) if _is_coded_field(field.get("name")) and field["name"] not in requested
        )
    return coded_in_schema


def _stable_sort_field(metadata: Any) -> str | None:
    """Return a WFS sortBy value for startIndex paging, or None.

    Composite primary keys become a comma-separated list so the full key orders
    the page, not only the first column. sortBy=id is not a safe default:
    Datafinder geographic layers typically have no ``id`` attribute and an empty
    ``primary_key_fields`` list. A missing field is HTTP 400.
    """
    data = metadata.get("data") if isinstance(metadata, dict) else None
    if not isinstance(data, dict):
        return None
    geometry_field = _geometry_field(metadata)
    raw_pk = data.get("primary_key_fields")
    pk_names: list[str] = []
    if isinstance(raw_pk, str) and raw_pk.strip():
        pk_names = [raw_pk]
    elif isinstance(raw_pk, list):
        pk_names = [name for name in raw_pk if isinstance(name, str)]
    pk_sort = [name for name in pk_names if _is_identifier(name) and name != geometry_field]
    if pk_sort:
        return ",".join(pk_sort)

    names: list[str] = []
    raw_fields = data.get("fields")
    if isinstance(raw_fields, list):
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not _is_identifier(name) or item.get("type") == "geometry" or name == geometry_field:
                continue
            names.append(name)
    for name in names:
        if name.lower() == "id":
            return name
    for name in names:
        if _GEOGRAPHY_CODE.fullmatch(name):
            return name
    return None


def _unique_features(features: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    unique: list[Any] = []
    for feature in features:
        fid = feature.get("id") if isinstance(feature, dict) else None
        if fid is None or isinstance(fid, bool):
            unique.append(feature)
            continue
        try:
            duplicate = fid in seen
        except TypeError:
            unique.append(feature)
            continue
        if duplicate:
            continue
        seen.add(fid)
        unique.append(feature)
    return unique


def _as_shapely(geometry: Any) -> Any | None:
    if not isinstance(geometry, dict) or not geometry.get("type"):
        return None
    try:
        geom = shape(geometry)
    except (TypeError, ValueError):
        return None
    if geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    return geom if not geom.is_empty else None


def _geodesic_area_m2(geom: Any) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    if geom.geom_type == "Polygon":
        area, _perimeter = _GEOD.geometry_area_perimeter(geom)
        return abs(area)
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return sum(_geodesic_area_m2(part) for part in geom.geoms)
    return 0.0


def _longitude_shifted_copies(geom: Any):
    """Yield geom and ±360° longitude copies so wrapped and unwrapped rings match."""
    yield geom
    yield translate(geom, xoff=360.0)
    yield translate(geom, xoff=-360.0)


def _safe_intersection(query_geom: Any, feature_geom: Any) -> Any:
    """Intersect two geometries, repairing once. Raise if GEOS still fails."""
    try:
        return query_geom.intersection(feature_geom)
    except ShapelyError:
        repaired_query = make_valid(query_geom)
        repaired_feature = make_valid(feature_geom)
        try:
            return repaired_query.intersection(repaired_feature)
        except ShapelyError as exc:
            raise DatafinderError("Could not compute overlap for a returned feature.") from exc


def _overlap_pair(
    query_geom: Any, feature_geom: Any, feature_area: float, feature_area_sq_km: float
) -> dict[str, float | None]:
    if query_geom.geom_type in ("Point", "MultiPoint"):
        try:
            intersects = bool(query_geom.intersects(feature_geom))
        except ShapelyError:
            repaired_query = make_valid(query_geom)
            repaired_feature = make_valid(feature_geom)
            try:
                intersects = bool(repaired_query.intersects(repaired_feature))
            except ShapelyError as exc:
                raise DatafinderError("Could not compute overlap for a returned feature.") from exc
        return {
            "overlap_fraction": 1.0 if intersects else 0.0,
            "overlap_area_sq_km": None,
            "feature_area_sq_km": feature_area_sq_km,
        }
    if feature_area <= 0:
        return {
            "overlap_fraction": None,
            "overlap_area_sq_km": None,
            "feature_area_sq_km": 0.0,
        }
    intersection = _safe_intersection(query_geom, feature_geom)
    if intersection is None or intersection.is_empty:
        return {
            "overlap_fraction": 0.0,
            "overlap_area_sq_km": 0.0,
            "feature_area_sq_km": feature_area_sq_km,
        }
    overlap_area = _geodesic_area_m2(intersection)
    return {
        "overlap_fraction": round(overlap_area / feature_area, 4),
        "overlap_area_sq_km": round(overlap_area / 1_000_000, 6),
        "feature_area_sq_km": feature_area_sq_km,
    }


def _overlap_stats(query_geom: Any, feature_geometry: Any) -> dict[str, float | None]:
    """How much of the feature falls inside the query shape.

    Polygon/bbox queries area-weight polygon features. Line/point features have
    no area, so overlap_fraction is left unset rather than reported as 1.0 for
    any intersection. Point queries and attribute-only queries return
    overlap_fraction 1.0 so agents do not zero-out counts for a point.
    Point queries leave overlap_area_sq_km as None: a point has no intersection
    area, and 0.0 would reintroduce the zero-out this path exists to avoid.
    Feature rings stored at lon ≈ 184 are compared after a ±360° shift so they
    still overlap a wrapped WGS84 query.
    """
    empty = {"overlap_fraction": None, "overlap_area_sq_km": None, "feature_area_sq_km": None}
    feature_geom = _as_shapely(feature_geometry)
    if feature_geom is None:
        if query_geom is None:
            return {"overlap_fraction": 1.0, "overlap_area_sq_km": None, "feature_area_sq_km": None}
        return empty
    feature_area = _geodesic_area_m2(feature_geom)
    feature_area_sq_km = round(feature_area / 1_000_000, 6) if feature_area else 0.0
    if query_geom is None:
        return {
            "overlap_fraction": 1.0,
            "overlap_area_sq_km": feature_area_sq_km,
            "feature_area_sq_km": feature_area_sq_km,
        }
    best: dict[str, float | None] | None = None
    for shifted in _longitude_shifted_copies(feature_geom):
        stats = _overlap_pair(query_geom, shifted, feature_area, feature_area_sq_km)
        if best is None:
            best = stats
            continue
        best_frac = best.get("overlap_fraction")
        frac = stats.get("overlap_fraction")
        if frac is not None and (best_frac is None or frac > best_frac):
            best = stats
        if best.get("overlap_fraction") == 1.0:
            break
    return best or empty


def _validate_overlap_fraction(value: float) -> float:
    """Clamp fractions in [0, 1] within OVERLAP_TOLERANCE; fail on clearly absurd values."""
    if value < -OVERLAP_TOLERANCE or value > 1.0 + OVERLAP_TOLERANCE:
        raise DatafinderError(
            _contract_error(
                message=f"Computed overlap fraction {value} is outside [0, 1].",
                error_code="invalid_overlap_fraction",
                field="geometry",
                recovery="Supply a valid WGS84 Polygon or MultiPolygon and query a polygon layer.",
                retry_safe=False,
            )
        )
    return min(1.0, max(0.0, value))


def _raw_overlap_fraction(query_geom: Any, feature_geometry: Any) -> float | None:
    """Unrounded geodesic overlap fraction, or None when the feature has no polygon area."""
    feature_geom = _as_shapely(feature_geometry)
    if query_geom is None or feature_geom is None:
        return None
    feature_area = _geodesic_area_m2(feature_geom)
    if feature_area <= 0:
        return None
    best_frac: float | None = None
    for shifted in _longitude_shifted_copies(feature_geom):
        intersection = _safe_intersection(query_geom, shifted)
        if intersection is None or intersection.is_empty:
            frac = 0.0
        else:
            frac = _geodesic_area_m2(intersection) / feature_area
        if best_frac is None or frac > best_frac:
            best_frac = frac
        if best_frac >= 1.0 - OVERLAP_TOLERANCE:
            break
    return _validate_overlap_fraction(0.0 if best_frac is None else best_frac)


def _measure_source_value(value: Any, missing_values: list[Any]) -> tuple[float | None, str]:
    """Return (numeric value, status). Zero is valid. Sentinels are never coerced to zero."""
    if value is None:
        return None, "unavailable"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, "unavailable"
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return None, "unavailable"
    for sentinel in missing_values:
        if isinstance(sentinel, bool) or not isinstance(sentinel, (int, float)):
            continue
        if number == float(sentinel):
            return None, "suppressed"
    return number, "included"


_GEOGRAPHY_RANK = ("MB", "SA1", "SA2", "SA3", "AU", "TA", "RC")


def _geography_field_rank(name: str) -> tuple[int, str]:
    upper = name.upper()
    for index, prefix in enumerate(_GEOGRAPHY_RANK):
        if upper.startswith(prefix):
            return (index, name)
    return (len(_GEOGRAPHY_RANK), name)


def _unique_geography_field(metadata: Any) -> str | None:
    """Pick one unique geography-code column (sort key, else finest unit)."""
    names = [
        field["name"]
        for field in _fields(metadata)
        if isinstance(field.get("name"), str) and _GEOGRAPHY_CODE.fullmatch(field["name"])
    ]
    if not names:
        return None
    return min(names, key=_geography_field_rank)


def _geography_code(properties: Any, field: str | None = None) -> str | None:
    if not isinstance(properties, dict) or not field:
        return None
    value = properties.get(field)
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    return text or None


def _validate_measures(
    measures: list[Any], metadata: Any, field_rows: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    rows = field_rows if field_rows is not None else _fields(metadata)
    schema_fields = [field["name"] for field in rows if isinstance(field.get("name"), str)]
    schema_set = set(schema_fields)
    if not schema_set:
        raise DatafinderError(
            _contract_error(
                message=(
                    "Layer metadata does not include a field list, so requested Census measures cannot be validated."
                ),
                error_code="unknown_fields",
                field="measures",
                recovery="Call Get Layer Metadata and confirm the layer publishes a field schema.",
                retry_safe=True,
            )
        )
    seen_keys: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(measures or []):
        path = f"measures[{index}]"
        if not isinstance(item, dict):
            raise DatafinderError(
                _contract_error(
                    message="Each measures entry must be an object.",
                    error_code="invalid_measure",
                    field=path,
                    recovery="Pass measures as objects with key, label, field, unit, and aggregation.",
                    retry_safe=False,
                )
            )
        key = item.get("key")
        field = item.get("field")
        label = item.get("label")
        unit = item.get("unit", COUNT_UNIT)
        aggregation = item.get("aggregation")
        if not isinstance(key, str) or not key.strip():
            raise DatafinderError(
                _contract_error(
                    message="Each measure needs a stable non-empty key.",
                    error_code="invalid_measure",
                    field=f"{path}.key",
                    recovery="Set key to a stable identifier such as 'population'.",
                    retry_safe=False,
                )
            )
        if key in seen_keys:
            raise DatafinderError(
                _contract_error(
                    message=f"Measure key '{key}' is duplicated.",
                    error_code="duplicate_measure_key",
                    field=f"{path}.key",
                    recovery="Use a unique key for each measure.",
                    retry_safe=False,
                )
            )
        seen_keys.add(key)
        if not isinstance(label, str) or not label.strip():
            raise DatafinderError(
                _contract_error(
                    message="Each measure needs a human-readable label.",
                    error_code="invalid_measure",
                    field=f"{path}.label",
                    recovery="Set label to a short description of the Census count.",
                    retry_safe=False,
                )
            )
        if not _is_identifier(field):
            raise DatafinderError(
                _contract_error(
                    message="Each measure field must be a valid Datafinder property name.",
                    error_code="invalid_measure",
                    field=f"{path}.field",
                    recovery="Use an exact field name from Get Layer Metadata.",
                    retry_safe=False,
                )
            )
        if field not in schema_set:
            raise DatafinderError(
                _contract_error(
                    message=f"Field '{field}' is not in the current layer metadata.",
                    error_code="unknown_field",
                    field=f"{path}.field",
                    valid_alternatives=schema_fields,
                    recovery="Call Get Layer Metadata and use an exact field name.",
                    retry_safe=False,
                )
            )
        codebook_measure = next((row.get("measure") for row in rows if row.get("name") == field), None)
        coded = _is_coded_field(field)
        measure_name = codebook_measure.strip().lower() if isinstance(codebook_measure, str) else ""
        if measure_name and measure_name != "count":
            raise DatafinderError(
                _contract_error(
                    message=(
                        f"Field '{field}' has codebook measure '{codebook_measure}'. "
                        "Medians, means, rates, percentages, and indexes cannot be area-weighted."
                    ),
                    error_code="non_additive_aggregation",
                    field=f"{path}.field",
                    valid_alternatives=[ADDITIVE_COUNT],
                    recovery="Request only additive Census counts (codebook measure Count).",
                    retry_safe=False,
                )
            )
        if coded and measure_name != "count":
            raise DatafinderError(
                _contract_error(
                    message=(
                        f"Field '{field}' is a coded Census column without a codebook Count classification, "
                        "so it cannot be area-weighted."
                    ),
                    error_code="unclassified_field",
                    field=f"{path}.field",
                    recovery="Call Get Layer Metadata and use a field whose measure is Count.",
                    retry_safe=True,
                )
            )
        if aggregation != ADDITIVE_COUNT:
            raise DatafinderError(
                _contract_error(
                    message=(
                        "Only additive_count aggregation is supported. "
                        "Medians, rates, percentages, and indexes cannot be area-weighted."
                    ),
                    error_code="non_additive_aggregation",
                    field=f"{path}.aggregation",
                    valid_alternatives=[ADDITIVE_COUNT],
                    recovery=(
                        "Request only additive Census counts, or compute rates downstream from two additive counts."
                    ),
                    retry_safe=False,
                )
            )
        if unit != COUNT_UNIT:
            raise DatafinderError(
                _contract_error(
                    message="Only unit 'count' is supported for area-weighted totals.",
                    error_code="unsupported_unit",
                    field=f"{path}.unit",
                    valid_alternatives=[COUNT_UNIT],
                    recovery="Set unit to 'count' for additive Census counts.",
                    retry_safe=False,
                )
            )
        validated.append(
            {
                "key": key,
                "label": label,
                "field": field,
                "unit": unit,
                "aggregation": aggregation,
            }
        )
    return validated


def _duplicate_geography_codes(codes: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for code in codes:
        if code:
            counts[code] = counts.get(code, 0) + 1
    return [code for code, count in counts.items() if count > 1]


def _search_layer(item: dict[str, Any]) -> dict[str, Any]:
    capabilities = item.get("user_capabilities")
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "description": _short_description(item.get("description")),
        "published_at": _string_or_none(item.get("published_at")) or _string_or_none(item.get("first_published_at")),
        "queryable": isinstance(capabilities, list) and "can-spatial-query" in capabilities,
    }


def _record_from_feature(
    feature: Any,
    query_geom: Any,
    *,
    include_geometry: bool,
    fields: list[str] | None = None,
    include_coded_fields: bool = False,
) -> tuple[dict[str, Any], int] | None:
    if not isinstance(feature, dict):
        return None
    properties, omitted = _project_properties(
        feature.get("properties"), fields=fields, include_coded_fields=include_coded_fields
    )
    record: dict[str, Any] = {
        "id": feature.get("id"),
        **_overlap_stats(query_geom, feature.get("geometry")),
        "properties": properties,
    }
    if include_geometry:
        record["geometry"] = feature.get("geometry")
    return record, omitted


def _platform_file(name: str, content_type: str, body: str | bytes) -> dict[str, str]:
    raw = body.encode("utf-8") if isinstance(body, str) else body
    return {
        "name": name,
        "contentType": content_type,
        "content": base64.b64encode(raw).decode("ascii"),
    }


def _geojson_feature_for_export(feature: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    properties = dict(record.get("properties") or {})
    properties["overlap_fraction"] = record.get("overlap_fraction")
    properties["overlap_area_sq_km"] = record.get("overlap_area_sq_km")
    properties["feature_area_sq_km"] = record.get("feature_area_sq_km")
    exported: dict[str, Any] = {
        "type": "Feature",
        "properties": properties,
        "geometry": feature.get("geometry"),
    }
    fid = record.get("id")
    if fid is not None:
        exported["id"] = fid
    return exported


def _query_layer_geojson_file(layer_id: int, features: list[dict[str, Any]]) -> dict[str, str]:
    collection = {"type": "FeatureCollection", "features": features}
    try:
        body = json.dumps(collection, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DatafinderError(
            _contract_error(
                message="The query GeoJSON export could not be serialised.",
                error_code="geojson_export_failed",
                field="export_geojson",
                recovery="Retry the query, or omit export_geojson and inspect records.",
                retry_safe=False,
            )
        ) from exc
    return _platform_file(f"layer-{layer_id}-query.geojson", "application/geo+json", body)


def _vintage(metadata: dict[str, Any]) -> str | None:
    for key in ("collected_at", "published_at", "first_published_at", "updated_at"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None


def _licence(metadata: dict[str, Any]) -> str | None:
    licence = metadata.get("license")
    if isinstance(licence, str) and licence.strip():
        return licence
    if isinstance(licence, dict):
        return _string_or_none(licence.get("title")) or _string_or_none(licence.get("type"))
    return None


def _attribution(metadata: dict[str, Any]) -> str | None:
    for key in ("attribution", "source_attribution"):
        value = _string_or_none(metadata.get(key))
        if value:
            return value
    supplier = metadata.get("supplier_reference")
    if isinstance(supplier, str) and supplier.strip():
        return supplier
    if isinstance(supplier, dict):
        value = _string_or_none(supplier.get("name")) or _string_or_none(supplier.get("title"))
        if value:
            return value
    group = metadata.get("group")
    if isinstance(group, dict):
        return _string_or_none(group.get("name"))
    return None


def _page_url(metadata: dict[str, Any], layer_id: int) -> str:
    for key in ("url_html", "url_canonical"):
        value = metadata.get(key)
        if isinstance(value, str):
            trusted = _trusted_datafinder_url(value)
            if trusted:
                return trusted
    return f"https://datafinder.stats.govt.nz/layer/{layer_id}/"


def _looks_like_file_url(url: str) -> bool:
    """True for a downloadable file path, not a Koordinates JSON resource URL."""
    path = urlparse(url).path.rstrip("/").lower()
    if path.endswith("/download"):
        return True
    filename = path.rsplit("/", 1)[-1]
    return "." in filename


def _attachment_basename(attachment: dict[str, str]) -> str:
    name = (attachment.get("name") or "").lower()
    url = (attachment.get("url") or "").lower()
    return f"{name} {urlparse(url).path}"


def _attachment_name(item: dict[str, Any]) -> str | None:
    document = item.get("document") if isinstance(item.get("document"), dict) else {}
    extension = _string_or_none(document.get("extension"))
    name = (
        _string_or_none(item.get("title"))
        or _string_or_none(document.get("title"))
        or _string_or_none(item.get("name"))
        or _string_or_none(item.get("filename"))
    )
    if name and extension and not name.lower().endswith(f".{extension.lower()}"):
        return f"{name}.{extension}"
    return name


def _attachment_download_url(item: dict[str, Any]) -> str | None:
    """Prefer url_download so agents get the CSV, not the attachment JSON metadata."""
    document = item.get("document") if isinstance(item.get("document"), dict) else {}
    candidates = (
        item.get("url_download"),
        document.get("url_download"),
        item.get("file"),
        item.get("url"),
    )
    for candidate in candidates:
        trusted = _trusted_datafinder_url(_string_or_none(candidate) or "")
        if trusted and _looks_like_file_url(trusted):
            return trusted
    return None


def _attachment_items(payload: Any) -> list[dict[str, str]]:
    items = payload if isinstance(payload, list) else []
    if not items and isinstance(payload, dict) and isinstance(payload.get("results"), list):
        items = payload["results"]
    attachments: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _attachment_name(item)
        url = _attachment_download_url(item)
        if not name and not url:
            continue
        attachment: dict[str, str] = {}
        if name:
            attachment["name"] = name
        if url:
            attachment["url"] = url
        attachments.append(attachment)
        if len(attachments) >= 20:
            break
    return attachments


async def _layer_attachments(context: ExecutionContext, metadata: Any) -> list[dict[str, str]]:
    url = metadata.get("attachments") if isinstance(metadata, dict) else None
    if not isinstance(url, str):
        return []
    trusted = _trusted_datafinder_url(url)
    if not trusted:
        return []
    try:
        response = await context.fetch(trusted, headers=_headers(context))
    except HTTPError as exc:
        if isinstance(exc, RateLimitError):
            raise
        return []
    return _attachment_items(response.data)


CODEBOOK_TIMEOUT_SECONDS = 30
CODEBOOK_MAX_CHARS = 2_000_000
CODEBOOK_MAX_DOWNLOADS = 2


async def _download_https_text(context: ExecutionContext, url: str) -> tuple[str, str]:
    """GET text from HTTPS. Send the API key only to datafinder.stats.govt.nz.

    Attachment downloads 302 to object storage. The key must not follow off-origin.
    Failures return empty strings so metadata still succeeds without the codebook.
    """
    trusted = _trusted_datafinder_url(url)
    if not trusted:
        return "", ""
    session = getattr(context, "_session", None)
    if session is None or not hasattr(session, "get"):
        session = aiohttp.ClientSession()
        context._session = session
    current = trusted
    timeout = aiohttp.ClientTimeout(total=CODEBOOK_TIMEOUT_SECONDS)
    for _ in range(5):
        parsed = urlparse(current)
        if parsed.scheme != "https" or not parsed.hostname:
            return "", ""
        on_datafinder = parsed.hostname == _DATAFINDER_HOST and parsed.port in (None, 443)
        headers = _headers(context) if on_datafinder else {}
        try:
            async with session.get(
                current, headers=headers, timeout=timeout, ssl=True, allow_redirects=False
            ) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        return "", ""
                    current = urljoin(current, location)
                    continue
                if not (200 <= response.status < 300):
                    return "", ""
                content_type = response.headers.get("Content-Type", "")
                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdigit() and int(content_length) > CODEBOOK_MAX_CHARS:
                    return "", ""
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.content.iter_chunked(65_536):
                    total += len(chunk)
                    if total > CODEBOOK_MAX_CHARS:
                        return "", ""
                    chunks.append(chunk)
                try:
                    text = b"".join(chunks).decode("utf-8-sig")
                except UnicodeDecodeError:
                    return "", ""
                return content_type, text
        except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError):
            return "", ""
    return "", ""


def _codebook_field_info(csv_text: str) -> dict[str, dict[str, str]]:
    """Map Column_name -> title/measure/year from a Stats NZ lookup CSV."""
    text = csv_text.lstrip("\ufeff")
    info: dict[str, dict[str, str]] = {}
    try:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if not isinstance(row, dict):
                continue
            name = _string_or_none(row.get("Column_name")) or _string_or_none(row.get("column_name"))
            if not _is_identifier(name):
                continue
            alias = _string_or_none(row.get("Field_name_alias"))
            variable = _string_or_none(row.get("Variable1"))
            category = _string_or_none(row.get("Variable1_category"))
            year = _string_or_none(row.get("Year"))
            measure = _string_or_none(row.get("Measure"))
            if alias:
                title = alias
            elif variable and category:
                title = f"{variable} ({category})"
                if year:
                    title = f"{title}, {year}"
                if measure:
                    title = f"{title}, {measure}"
            elif variable:
                title = variable
            else:
                title = None
            entry: dict[str, str] = {}
            if title:
                entry["title"] = title
            if measure:
                entry["measure"] = measure
            if year:
                entry["year"] = year
            if entry:
                info[name] = entry
    except csv.Error:
        return info
    return info


def _is_csv_codebook(content_type: str, text: str) -> bool:
    low = content_type.lower()
    if "json" in low or "html" in low:
        return False
    header = text.lstrip("\ufeff").split("\n", 1)[0].lower()
    return "csv" in low or "column_name" in header


def _coded_fields_need_measure(fields: list[dict[str, Any]]) -> bool:
    return any(_is_coded_field(field.get("name")) and not str(field.get("measure") or "").strip() for field in fields)


def _merge_codebook_info(fields: list[dict[str, Any]], info: dict[str, dict[str, str]]) -> None:
    for field in fields:
        extra = info.get(field.get("name"))
        if not extra:
            continue
        if extra.get("title") and not field.get("title"):
            field["title"] = extra["title"]
        if extra.get("measure") and not field.get("measure"):
            field["measure"] = extra["measure"]
        if extra.get("year") and not field.get("year"):
            field["year"] = extra["year"]


async def _apply_codebook_titles(
    context: ExecutionContext, fields: list[dict[str, Any]], attachments: list[dict[str, str]]
) -> None:
    """Fill field titles from lookup CSVs. Never fails the action."""
    try:
        ranked = sorted(
            attachments,
            key=lambda item: 0 if "lookup" in _attachment_basename(item) or ".csv" in _attachment_basename(item) else 1,
        )
        downloads = 0
        for attachment in ranked:
            if not _coded_fields_need_measure(fields):
                return
            url = attachment.get("url")
            if not isinstance(url, str) or not _looks_like_file_url(url):
                continue
            if downloads >= CODEBOOK_MAX_DOWNLOADS:
                return
            downloads += 1
            content_type, text = await _download_https_text(context, url)
            if not text or not _is_csv_codebook(content_type, text):
                continue
            info = _codebook_field_info(text)
            if not info:
                continue
            _merge_codebook_info(fields, info)
    except (csv.Error, UnicodeDecodeError, ValueError, OSError):
        return


def _metadata_result(layer_id: int, data: Any, *, attachments: list[dict[str, str]] | None = None) -> dict[str, Any]:
    metadata = data if isinstance(data, dict) else {}
    fields = _fields(metadata)
    return {
        "layer_id": layer_id,
        "title": _string_or_none(metadata.get("title")),
        "description": _short_description(metadata.get("description")),
        "fields": fields,
        "coded_field_count": sum(1 for field in fields if field.get("coded")),
        "data_vintage": _vintage(metadata),
        "licence": _licence(metadata),
        "attribution": _attribution(metadata),
        "page_url": _page_url(metadata, layer_id),
        "source_url": f"{API_BASE_URL}/layers/{layer_id}/",
        "attachments": attachments or [],
    }


def _feature_params(
    *,
    feature_type: str,
    cql_filter: str,
    page_size: int,
    start_index: int,
    sort_by: str | None = None,
    property_names: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "service": "WFS",
        "version": WFS_VERSION,
        "request": "GetFeature",
        "typeNames": feature_type,
        "outputFormat": "json",
        "srsName": "EPSG:4326",
        "cql_filter": cql_filter,
        "count": page_size,
        "startIndex": start_index,
    }
    if sort_by:
        params["sortBy"] = sort_by
    if property_names:
        seen: set[str] = set()
        ordered: list[str] = []
        for name in property_names:
            if name in seen or not _is_identifier(name):
                continue
            seen.add(name)
            ordered.append(name)
        if ordered:
            params["propertyName"] = ",".join(ordered)
    return params


async def _collect_wfs_features(
    context: ExecutionContext,
    layer_id: int,
    *,
    feature_type: str,
    cql_filter: str,
    page_size: int,
    max_pages: int,
    sort_by: str | None,
    property_names: list[str] | None,
    fail_closed: bool = False,
    max_source_features: int | None = None,
) -> _CollectedFeatures:
    """Page WFS GetFeature results. When fail_closed is set, raise instead of returning a partial page set."""
    features: list[Any] = []
    matched: int | None = None
    pages = 0
    start_index = 0
    truncated = False
    raw_count = 0
    for _ in range(max_pages):
        try:
            data = await _wfs_get_features(
                context,
                layer_id,
                params=_feature_params(
                    feature_type=feature_type,
                    cql_filter=cql_filter,
                    page_size=page_size,
                    start_index=start_index,
                    sort_by=sort_by,
                    property_names=property_names,
                ),
            )
        except DatafinderError:
            if fail_closed or not features:
                raise
            truncated = True
            break
        page_features = data["features"]
        page_matched = _total_matched(data)
        if page_matched is not None:
            matched = page_matched
        if fail_closed and max_source_features is not None and matched is not None and matched > max_source_features:
            raise DatafinderError(
                _contract_error(
                    message=(
                        f"Layer {layer_id} has {matched} intersecting features, "
                        f"above max_source_features={max_source_features}."
                    ),
                    error_code="max_source_features_exceeded",
                    field="max_source_features",
                    recovery="Increase max_source_features or use a smaller catchment polygon.",
                    retry_safe=False,
                )
            )
        if not page_features:
            break
        raw_count += len(page_features)
        features.extend(page_features)
        features = _unique_features(features)
        pages += 1
        start_index += len(page_features)
        if fail_closed and max_source_features is not None and len(features) > max_source_features:
            raise DatafinderError(
                _contract_error(
                    message=(
                        f"Layer {layer_id} returned more unique features than "
                        f"max_source_features={max_source_features}."
                    ),
                    error_code="max_source_features_exceeded",
                    field="max_source_features",
                    recovery="Increase max_source_features or use a smaller catchment polygon.",
                    retry_safe=False,
                )
            )
        if matched is not None and len(features) >= matched:
            break
    if not truncated:
        if matched is not None:
            truncated = len(features) < matched
        elif pages >= max_pages:
            try:
                probe = await _wfs_get_features(
                    context,
                    layer_id,
                    params=_feature_params(
                        feature_type=feature_type,
                        cql_filter=cql_filter,
                        page_size=1,
                        start_index=start_index,
                        sort_by=sort_by,
                        property_names=property_names,
                    ),
                )
            except DatafinderError:
                if fail_closed:
                    raise
                truncated = True
            else:
                truncated = bool(probe["features"])
        else:
            truncated = False
    if fail_closed and truncated:
        raise DatafinderError(
            _contract_error(
                message=f"The catchment query did not retrieve every intersecting feature for layer {layer_id}.",
                error_code="incomplete_pagination",
                field="max_pages",
                recovery=(
                    "Increase page_size and max_pages so page_size × max_pages covers every "
                    "intersecting feature, then retry."
                ),
                retry_safe=False,
            )
        )
    return _CollectedFeatures(features, pages, matched, truncated, max(0, raw_count - len(features)))


@stats_nz_datafinder.action("get_layer_metadata")
class GetLayerMetadataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        try:
            response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=_headers(context))
            attachments = await _layer_attachments(context, response.data)
            result = _metadata_result(layer_id, response.data, attachments=attachments)
            await _apply_codebook_titles(context, result["fields"], attachments)
            return ActionResult(data=result)
        except DatafinderError as exc:
            return ActionError(message=_redact(exc))
        except HTTPError as exc:
            return _http_action_error(exc, layer_id=layer_id)
        except Exception:
            return ActionError(message=_UNEXPECTED_ERROR)


@stats_nz_datafinder.action("query_layer_by_geometry")
class QueryLayerByGeometryAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        page_size, max_pages = inputs.get("page_size", DEFAULT_PAGE_SIZE), inputs.get("max_pages", DEFAULT_MAX_PAGES)
        include_geometry = bool(inputs.get("include_geometry"))
        include_coded_fields = bool(inputs.get("include_coded_fields"))
        export_geojson = bool(inputs.get("export_geojson"))
        fields = inputs.get("fields")
        try:
            if inputs.get("file") is not None and inputs.get("bbox") is not None:
                raise _geojson_contract_error(
                    message="Provide only one spatial source: geometry, file, or bbox.",
                    error_code="conflicting_geometry_source",
                    recovery="Pass either inline geometry, a GeoJSON file, or bbox — not more than one.",
                )
            geometry, geometry_source = _bind_geojson_file(inputs)
            headers = _headers(context)
            scoped = dict(inputs)
            if geometry is not None:
                scoped["geometry"] = geometry
            spatial_geometry, _ = _resolve_query_scope(scoped)
            spatial_wkts = _cql_spatial_wkts(spatial_geometry, scoped)
            query_geom = _as_shapely(spatial_geometry) if spatial_geometry else None
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            geometry_field = _geometry_field(metadata_response.data)
            attribute_names = _requested_attribute_names(
                metadata_response.data, fields=fields, include_coded_fields=include_coded_fields
            )
            property_names = None if attribute_names is None else [geometry_field, *attribute_names]
            cql_filter = _build_cql_filter(spatial_wkts, inputs.get("attribute_filters"), geometry_field)
            capabilities = await _wfs_get_capabilities(context, layer_id)
            feature_type = _resolve_feature_type(layer_id, capabilities)
            sort_by = _stable_sort_field(metadata_response.data)
            collected = await _collect_wfs_features(
                context,
                layer_id,
                feature_type=feature_type,
                cql_filter=cql_filter,
                page_size=page_size,
                max_pages=max_pages,
                sort_by=sort_by,
                property_names=property_names,
                fail_closed=export_geojson,
            )
            features = collected.features
            pages = collected.pages
            matched = collected.matched
            truncated = collected.truncated
            records: list[dict[str, Any]] = []
            export_features: list[dict[str, Any]] = []
            row_omitted = 0
            for feature in features:
                projected = _record_from_feature(
                    feature,
                    query_geom,
                    include_geometry=include_geometry,
                    fields=fields,
                    include_coded_fields=include_coded_fields,
                )
                if projected is None:
                    continue
                record, omitted = projected
                records.append(record)
                row_omitted = max(row_omitted, omitted)
                if export_geojson:
                    export_features.append(_geojson_feature_for_export(feature, record))
            coded_fields_omitted = max(
                _coded_fields_omitted_count(
                    metadata_response.data, fields=fields, include_coded_fields=include_coded_fields
                ),
                row_omitted,
            )
            payload: dict[str, Any] = {
                "records": records,
                "record_count": len(records),
                "layer_id": layer_id,
                "retrieved_pages": pages,
                "truncated": truncated,
                "total_matched": matched,
                "coded_fields_omitted": coded_fields_omitted,
                "data_vintage": metadata["data_vintage"],
                "licence": metadata["licence"],
                "attribution": metadata["attribution"],
            }
            if geometry_source:
                payload["geometry_source"] = geometry_source
            if export_geojson:
                payload["files"] = [_query_layer_geojson_file(layer_id, export_features)]
            return ActionResult(data=payload)
        except DatafinderError as exc:
            return ActionError(message=_redact(exc))
        except HTTPError as exc:
            return _http_action_error(exc, layer_id=layer_id)
        except Exception:
            return ActionError(message=_UNEXPECTED_ERROR)


@stats_nz_datafinder.action("query_area_statistics")
class QueryAreaStatisticsAction(ActionHandler):
    """Return compact area-weighted Census totals for a catchment polygon."""

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        page_size = inputs.get("page_size", DEFAULT_PAGE_SIZE)
        max_pages = inputs.get("max_pages", DEFAULT_AREA_MAX_PAGES)
        missing_values = inputs.get("missing_values", DEFAULT_MISSING_VALUES)
        max_source_features = inputs.get("max_source_features", DEFAULT_MAX_SOURCE_FEATURES)
        try:
            geometry, geometry_source = _bind_geojson_file(inputs)
            if geometry is None:
                raise DatafinderError(
                    _contract_error(
                        message="Provide geometry or file.",
                        error_code="missing_geometry",
                        field="geometry",
                        valid_alternatives=["geometry", "file"],
                        recovery="Pass a WGS84 Polygon or MultiPolygon, or a GeoJSON file containing one.",
                        retry_safe=False,
                    )
                )
            if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
                raise DatafinderError(
                    _contract_error(
                        message="geometry must be a WGS84 Polygon or MultiPolygon.",
                        error_code="invalid_geometry",
                        field="geometry",
                        valid_alternatives=["Polygon", "MultiPolygon"],
                        recovery="Pass the isochrone band as a GeoJSON Polygon or MultiPolygon.",
                        retry_safe=False,
                    )
                )
            if not isinstance(missing_values, list) or not missing_values:
                missing_values = list(DEFAULT_MISSING_VALUES)
            headers = _headers(context)
            spatial_geometry, _ = _resolve_query_scope({"geometry": geometry})
            spatial_wkts = _cql_spatial_wkts(spatial_geometry, {"geometry": geometry})
            query_geom = _as_shapely(spatial_geometry)
            if query_geom is None:
                raise DatafinderError(
                    _contract_error(
                        message="The supplied catchment geometry is empty or invalid.",
                        error_code="invalid_geometry",
                        field="geometry",
                        recovery="Supply a closed WGS84 Polygon or MultiPolygon.",
                        retry_safe=False,
                    )
                )
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            attachments = await _layer_attachments(context, metadata_response.data)
            field_rows = _fields(metadata_response.data)
            await _apply_codebook_titles(context, field_rows, attachments)
            measures = _validate_measures(inputs["measures"], metadata_response.data, field_rows)
            geometry_field = _geometry_field(metadata_response.data)
            measure_fields = [item["field"] for item in measures]
            geography_field = _unique_geography_field(metadata_response.data)
            geography_fields = [geography_field] if geography_field else []
            attribute_names = list(dict.fromkeys([*geography_fields, *measure_fields]))
            property_names = [geometry_field, *attribute_names]
            cql_filter = _build_cql_filter(spatial_wkts, None, geometry_field)
            capabilities = await _wfs_get_capabilities(context, layer_id)
            feature_type = _resolve_feature_type(layer_id, capabilities)
            sort_by = _stable_sort_field(metadata_response.data)
            collected = await _collect_wfs_features(
                context,
                layer_id,
                feature_type=feature_type,
                cql_filter=cql_filter,
                page_size=page_size,
                max_pages=max_pages,
                sort_by=sort_by,
                property_names=property_names,
                fail_closed=True,
                max_source_features=max_source_features,
            )
            totals: dict[str, dict[str, Any]] = {
                item["key"]: {
                    "estimated_value": 0.0,
                    "included_feature_count": 0,
                    "unavailable_feature_count": 0,
                }
                for item in measures
            }
            geography_codes: list[str] = []
            included_any = 0
            skipped_no_area = 0
            warnings: list[str] = []
            if not geography_field:
                warnings.append("No geography-code field was found, so duplicate SA1 joins were not checked.")
            for feature in collected.features:
                if not isinstance(feature, dict):
                    raise DatafinderError(
                        _contract_error(
                            message="Datafinder returned a malformed feature.",
                            error_code="partial_provider_failure",
                            field="geometry",
                            recovery="Retry the request. If it persists, choose another layer.",
                            retry_safe=True,
                        )
                    )
                fraction = _raw_overlap_fraction(query_geom, feature.get("geometry"))
                properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
                if fraction is None:
                    skipped_no_area += 1
                    continue
                has_included = False
                for measure in measures:
                    key = measure["key"]
                    if measure["field"] not in properties:
                        number, status = None, "unavailable"
                    else:
                        number, status = _measure_source_value(properties.get(measure["field"]), missing_values)
                    if status == "included" and number is not None:
                        totals[key]["estimated_value"] += number * fraction
                        totals[key]["included_feature_count"] += 1
                        has_included = True
                    else:
                        totals[key]["unavailable_feature_count"] += 1
                code = _geography_code(properties, geography_field)
                if isinstance(code, str) and code:
                    geography_codes.append(code)
                if has_included:
                    included_any += 1
            duplicates = _duplicate_geography_codes(geography_codes)
            if duplicates:
                raise DatafinderError(
                    _contract_error(
                        message="Duplicate geography codes remain after feature-id deduplication.",
                        error_code="duplicate_join",
                        field="geometry",
                        valid_alternatives=duplicates[:8],
                        recovery="Retry the query. If it persists, the layer is not a unique-join Census geography.",
                        retry_safe=False,
                    )
                )
            intersecting = len(collected.features)
            if skipped_no_area:
                warnings.append(f"Excluded {skipped_no_area} feature(s) with no polygon area.")
            results = []
            for measure in measures:
                stats = totals[measure["key"]]
                included = stats["included_feature_count"]
                unavailable = stats["unavailable_feature_count"]
                if included == 0:
                    status = "unavailable"
                    estimated: float | None = None
                    warnings.append(f"Measure '{measure['key']}' had no usable source values in this catchment.")
                elif unavailable > 0:
                    status = "partial"
                    estimated = stats["estimated_value"]
                    warnings.append(
                        f"Measure '{measure['key']}' excluded {unavailable} feature(s) "
                        "with missing or suppressed values."
                    )
                else:
                    status = "ok"
                    estimated = stats["estimated_value"]
                result_row = {
                    "key": measure["key"],
                    "label": measure["label"],
                    "field": measure["field"],
                    "estimated_value": estimated,
                    "unit": measure["unit"],
                    "aggregation": measure["aggregation"],
                    "source_feature_count": intersecting,
                    "included_feature_count": included,
                    "unavailable_feature_count": unavailable,
                    "status": status,
                }
                results.append(result_row)
            statuses = [row["status"] for row in results]
            if statuses and all(status == "unavailable" for status in statuses):
                validation_status = "unavailable"
            elif any(status in {"partial", "unavailable"} for status in statuses):
                validation_status = "partial"
            else:
                validation_status = "ok"
            output: dict[str, Any] = {
                "results": results,
                "geography_summary": {
                    "intersecting_feature_count": intersecting,
                    "included_feature_count": included_any,
                    "duplicate_feature_count": collected.duplicate_count,
                },
                "method": {
                    "area_weighting": (
                        "Additive counts are estimated as the unrounded sum of source_value × overlap_fraction. "
                        "overlap_fraction is the geodesic intersection area divided by the geodesic feature area "
                        "on the WGS84 ellipsoid (pyproj Geod). Areas are not computed in longitude/latitude degrees."
                    ),
                    "projected_crs": "WGS84 geodesic (pyproj Geod, ellps=WGS84); not a planar degree grid",
                    "overlap_tolerance": OVERLAP_TOLERANCE,
                },
                "layer": {
                    "layer_id": layer_id,
                    "title": metadata["title"],
                    "data_vintage": metadata["data_vintage"],
                    "licence": metadata["licence"],
                    "attribution": metadata["attribution"],
                    "catalogue_url": metadata["page_url"],
                },
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "warnings": warnings,
                "validation_status": validation_status,
            }
            if geometry_source:
                output["geometry_source"] = geometry_source
            return ActionResult(data=output)
        except DatafinderError as exc:
            return ActionError(message=_redact(exc))
        except HTTPError as exc:
            return _http_action_error(exc, layer_id=layer_id)
        except Exception:
            return ActionError(message=_UNEXPECTED_ERROR)


@stats_nz_datafinder.action("search_layers")
class SearchLayersAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        page, page_size = inputs.get("page", 1), inputs.get("page_size", 20)
        try:
            response = await context.fetch(
                f"{API_BASE_URL}/layers/",
                headers=_headers(context),
                params={
                    "q": inputs["keyword"],
                    "kind": "vector",
                    "public": "true",
                    "page": page,
                    "page_size": page_size,
                },
            )
            items = response.data if isinstance(response.data, list) else []
            layers = [
                _search_layer(item) for item in items if isinstance(item, dict) and isinstance(item.get("id"), int)
            ]
            total = None
            resource_range = response.headers.get("X-Resource-Range", "") if getattr(response, "headers", None) else ""
            if "/" in resource_range:
                suffix = resource_range.rsplit("/", 1)[1]
                if suffix.isdigit():
                    total = int(suffix)
            return ActionResult(
                data={
                    "layers": layers,
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                }
            )
        except DatafinderError as exc:
            return ActionError(message=_redact(exc))
        except HTTPError as exc:
            return _http_action_error(exc)
        except Exception:
            return ActionError(message=_UNEXPECTED_ERROR)
