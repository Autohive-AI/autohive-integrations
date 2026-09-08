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

TRADE-OFF — no retries or rate-limit handling on WFS:
-----------------------------------------------------
Bypassing ``context.fetch`` also means forgoing the SDK client's request
resilience. This version implements none of its own: one attempt per WFS
request, no exponential backoff, no ``Retry-After`` handling, and a fixed
``WFS_REQUEST_TIMEOUT_SECONDS`` timeout. Retrying is the caller's
responsibility. See README.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, NamedTuple
from urllib.parse import quote

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
from shapely.geometry import shape

stats_nz_datafinder = Integration.load()

API_BASE_URL = "https://datafinder.stats.govt.nz/services/api/v1"
WFS_VERSION = "2.0.0"
WFS_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_GEOMETRY_FIELD = "Shape"
DEFAULT_PAGE_SIZE = 50
MAX_DESCRIPTION_CHARS = 400
_GEOD = Geod(ellps="WGS84")
UNSCOPED_ERROR = "Provide geometry, bbox, or at least one attribute filter. Unscoped national scans are not supported."
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


class _WfsResponse(NamedTuple):
    """Minimal response wrapper: the pieces the error/parse helpers need."""

    status: int
    data: Any


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

    request_kwargs: dict[str, Any] = {"timeout": timeout, "ssl": True}
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


def _lon_lat(position: Any) -> tuple[float, float]:
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
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise DatafinderError("GeoJSON coordinates must be WGS84 longitude/latitude values.")
    return float(lon), float(lat)


def _wkt_ring(ring: Any) -> str:
    if not isinstance(ring, list) or len(ring) < 4:
        raise DatafinderError("Each polygon ring must contain at least four positions.")
    points = [_lon_lat(point) for point in ring]
    if points[0] != points[-1]:
        raise DatafinderError("Each polygon ring must be closed.")
    return "(" + ", ".join(f"{lon:.15g} {lat:.15g}" for lon, lat in points) + ")"


def _wkt_polygon(polygon: Any) -> str:
    if not isinstance(polygon, list) or not polygon:
        raise DatafinderError("Each polygon must contain an exterior ring.")
    return "POLYGON(" + ", ".join(_wkt_ring(ring) for ring in polygon) + ")"


def _wkt_geometry(geometry: dict[str, Any]) -> str:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        lon, lat = _lon_lat(coordinates)
        return f"POINT({lon:.15g} {lat:.15g})"
    if geometry_type == "Polygon":
        return _wkt_polygon(coordinates)
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise DatafinderError("A MultiPolygon must contain at least one polygon.")
        polygons = [_wkt_polygon(polygon).removeprefix("POLYGON") for polygon in coordinates]
        return "MULTIPOLYGON(" + ", ".join(polygons) + ")"
    raise DatafinderError("geometry.type must be Point, Polygon, or MultiPolygon.")


def _parse_bbox(bbox: Any) -> tuple[float, float, float, float]:
    """Return wrapped [west, south, east, north]. west may be > east (antimeridian)."""
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
    west, east = _wrap_longitude(west), _wrap_longitude(east)
    if west == east:
        raise DatafinderError("bbox requires a non-zero longitude span.")
    return west, south, east, north


def _bbox_polygon(bbox: Any) -> dict[str, Any]:
    west, south, east, north = _parse_bbox(bbox)
    if west < east:
        return {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        }
    # Crosses 180°: split so GeoJSON rings stay in [-180, 180].
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [[[west, south], [180, south], [180, north], [west, north], [west, south]]],
            [[[-180, south], [east, south], [east, north], [-180, north], [-180, south]]],
        ],
    }


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
    spatial_wkt: str | None, attribute_filters: list[dict[str, Any]] | None, geometry_field: str
) -> str:
    """Build a GeoServer CQL filter from an optional spatial WKT and attribute clauses."""
    clauses = _attribute_clauses(attribute_filters)
    if spatial_wkt:
        spatial = f"INTERSECTS({geometry_field}, SRID=4326;{spatial_wkt})"
        return spatial + "".join(f" AND ({clause})" for clause in clauses)
    if not clauses:
        raise DatafinderError(UNSCOPED_ERROR)
    return " AND ".join(f"({clause})" for clause in clauses)


def _resolve_query_scope(inputs: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Return (spatial GeoJSON or None, query kind). Reject unconstrained scans."""
    geometry = inputs.get("geometry")
    bbox = inputs.get("bbox")
    filters = inputs.get("attribute_filters") or []
    if geometry and bbox:
        raise DatafinderError("Provide geometry or bbox, not both.")
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
    if fields:
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
    if fields:
        allowed = {name for name in fields if _is_identifier(name)}
        kept = {key: value for key, value in properties.items() if key in allowed}
    elif include_coded_fields:
        kept = dict(properties)
    else:
        kept = {key: value for key, value in properties.items() if not _is_coded_field(key)}
    omitted = sum(1 for key in coded_keys if key not in kept)
    return kept, omitted


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


def _overlap_stats(query_geom: Any, feature_geometry: Any) -> dict[str, float | None]:
    """How much of the feature falls inside the query shape.

    Polygon/bbox queries area-weight polygon features. Line/point features have
    no area, so overlap_fraction is left unset rather than reported as 1.0 for
    any intersection. Point queries and attribute-only queries return
    overlap_fraction 1.0 so agents do not zero-out counts for a point.
    Point queries leave overlap_area_sq_km as None: a point has no intersection
    area, and 0.0 would reintroduce the zero-out this path exists to avoid.
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
    if query_geom.geom_type in ("Point", "MultiPoint"):
        intersects = bool(query_geom.intersects(feature_geom))
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
    try:
        intersection = query_geom.intersection(feature_geom)
    except Exception:
        return empty
    overlap_area = _geodesic_area_m2(intersection)
    return {
        "overlap_fraction": round(overlap_area / feature_area, 4),
        "overlap_area_sq_km": round(overlap_area / 1_000_000, 6),
        "feature_area_sq_km": feature_area_sq_km,
    }


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
    return (
        _string_or_none(metadata.get("url_html"))
        or _string_or_none(metadata.get("url_canonical"))
        or f"https://datafinder.stats.govt.nz/layer/{layer_id}/"
    )


def _attachment_items(payload: Any) -> list[dict[str, str]]:
    items = payload if isinstance(payload, list) else []
    attachments: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (
            _string_or_none(item.get("title"))
            or _string_or_none(item.get("name"))
            or _string_or_none(item.get("filename"))
        )
        url = _string_or_none(item.get("url")) or _string_or_none(item.get("file"))
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
    if not isinstance(url, str) or not url.strip():
        return []
    try:
        response = await context.fetch(url, headers=_headers(context))
    except HTTPError:
        return []
    return _attachment_items(response.data)


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


@stats_nz_datafinder.action("get_layer_metadata")
class GetLayerMetadataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        try:
            response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=_headers(context))
            attachments = await _layer_attachments(context, response.data)
            return ActionResult(data=_metadata_result(layer_id, response.data, attachments=attachments))
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
        page_size, max_pages = inputs.get("page_size", DEFAULT_PAGE_SIZE), inputs.get("max_pages", 10)
        include_geometry = bool(inputs.get("include_geometry"))
        include_coded_fields = bool(inputs.get("include_coded_fields"))
        fields = inputs.get("fields")
        try:
            headers = _headers(context)
            spatial_geometry, _ = _resolve_query_scope(inputs)
            spatial_wkt = _wkt_geometry(spatial_geometry) if spatial_geometry else None
            query_geom = _as_shapely(spatial_geometry) if spatial_geometry else None
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            geometry_field = _geometry_field(metadata_response.data)
            attribute_names = _requested_attribute_names(
                metadata_response.data, fields=fields, include_coded_fields=include_coded_fields
            )
            property_names = None if attribute_names is None else [geometry_field, *attribute_names]
            cql_filter = _build_cql_filter(spatial_wkt, inputs.get("attribute_filters"), geometry_field)
            capabilities = await _wfs_get_capabilities(context, layer_id)
            feature_type = _resolve_feature_type(layer_id, capabilities)
            sort_by = _stable_sort_field(metadata_response.data)
            features: list[Any] = []
            matched: int | None = None
            pages = 0
            last_page_full = False
            truncated = False
            for page in range(max_pages):
                try:
                    data = await _wfs_get_features(
                        context,
                        layer_id,
                        params=_feature_params(
                            feature_type=feature_type,
                            cql_filter=cql_filter,
                            page_size=page_size,
                            start_index=page * page_size,
                            sort_by=sort_by,
                            property_names=property_names,
                        ),
                    )
                except DatafinderError:
                    if not features:
                        raise
                    truncated = True
                    break
                page_features = data["features"]
                features.extend(page_features)
                features = _unique_features(features)
                pages += 1
                last_page_full = len(page_features) >= page_size
                page_matched = _total_matched(data)
                if page_matched is not None:
                    matched = page_matched
                if not page_features or (matched is not None and len(features) >= matched):
                    break
                if matched is None and not last_page_full:
                    break
            if not truncated:
                if matched is not None:
                    truncated = len(features) < matched
                elif pages >= max_pages and last_page_full:
                    try:
                        probe = await _wfs_get_features(
                            context,
                            layer_id,
                            params=_feature_params(
                                feature_type=feature_type,
                                cql_filter=cql_filter,
                                page_size=1,
                                start_index=pages * page_size,
                                sort_by=sort_by,
                                property_names=property_names,
                            ),
                        )
                    except DatafinderError:
                        truncated = True
                    else:
                        truncated = len(_unique_features(features + probe["features"])) > len(features)
                else:
                    truncated = False
            records: list[dict[str, Any]] = []
            coded_fields_omitted = 0
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
                if omitted > coded_fields_omitted:
                    coded_fields_omitted = omitted
            if not fields and not include_coded_fields and metadata["coded_field_count"]:
                coded_fields_omitted = metadata["coded_field_count"]
            return ActionResult(
                data={
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
            )
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
