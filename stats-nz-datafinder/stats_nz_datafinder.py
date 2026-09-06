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
from defusedxml import ElementTree as DefusedET

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)

stats_nz_datafinder = Integration.load()

API_BASE_URL = "https://datafinder.stats.govt.nz/services/api/v1"
WFS_VERSION = "2.0.0"
WFS_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_GEOMETRY_FIELD = "Shape"
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


async def _wfs_request(context: ExecutionContext, *, params: dict[str, Any], layer_id: int) -> _WfsResponse:
    """Issue a GET to the per-layer WFS endpoint with aiohttp directly.

    Deliberately does not use ``context.fetch``: Datafinder puts the API key in
    the URL path, and the SDK's fetch logs the full URL on error. Transport
    failures are re-raised with a fixed message, never the underlying
    exception text (aiohttp builds that from the request URL).
    """
    url = _wfs_url(context, layer_id)
    query = {key: str(value) for key, value in params.items() if value is not None}
    timeout = aiohttp.ClientTimeout(total=WFS_REQUEST_TIMEOUT_SECONDS)

    session = getattr(context, "_session", None)
    if not isinstance(session, aiohttp.ClientSession):
        session = aiohttp.ClientSession()
        context._session = session

    try:
        async with session.get(url, params=query, timeout=timeout, ssl=True) as response:
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
    response = await _wfs_request(context, params=params, layer_id=layer_id)
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
    if geometry_type == "Polygon":
        return _wkt_polygon(coordinates)
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise DatafinderError("A MultiPolygon must contain at least one polygon.")
        polygons = [_wkt_polygon(polygon).removeprefix("POLYGON") for polygon in coordinates]
        return "MULTIPOLYGON(" + ", ".join(polygons) + ")"
    raise DatafinderError("geometry.type must be Polygon or MultiPolygon.")


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


def _build_cql_filter(wkt: str, attribute_filters: list[dict[str, Any]] | None, geometry_field: str) -> str:
    """Build a GeoServer CQL Intersects filter from validated WKT and attribute clauses."""
    spatial = f"INTERSECTS({geometry_field}, SRID=4326;{wkt})"
    clauses: list[str] = []
    for item in attribute_filters or []:
        operator = item.get("operator")
        property_name = item.get("property")
        value = item.get("value")
        if operator not in _CQL_OPERATORS or not _is_identifier(property_name):
            raise DatafinderError("Each attribute filter needs a valid property and supported operator.")
        if isinstance(value, (dict, list)) or value is None:
            raise DatafinderError("Attribute filter values must be strings, numbers, or booleans.")
        clauses.append(f"{property_name} {_CQL_OPERATORS[operator]} {_cql_literal(value)}")
    return spatial + "".join(f" AND ({clause})" for clause in clauses)


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


def _metadata_result(layer_id: int, data: Any) -> dict[str, Any]:
    metadata = data if isinstance(data, dict) else {}
    return {
        "layer_id": layer_id,
        "title": _string_or_none(metadata.get("title")),
        "description": metadata.get("description") if isinstance(metadata.get("description"), str) else None,
        "data_vintage": _vintage(metadata),
        "licence": _licence(metadata),
        "attribution": _attribution(metadata),
        "source_url": f"{API_BASE_URL}/layers/{layer_id}/",
    }


def _feature_params(
    *,
    feature_type: str,
    cql_filter: str,
    page_size: int,
    start_index: int,
) -> dict[str, Any]:
    return {
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


@stats_nz_datafinder.action("get_layer_metadata")
class GetLayerMetadataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        try:
            response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=_headers(context))
            return ActionResult(data=_metadata_result(layer_id, response.data))
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
        page_size, max_pages = inputs.get("page_size", 1000), inputs.get("max_pages", 10)
        try:
            headers = _headers(context)
            wkt = _wkt_geometry(inputs["geometry"])
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            cql_filter = _build_cql_filter(
                wkt, inputs.get("attribute_filters"), _geometry_field(metadata_response.data)
            )
            capabilities = await _wfs_get_capabilities(context, layer_id)
            feature_type = _resolve_feature_type(layer_id, capabilities)
            features: list[Any] = []
            matched: int | None = None
            pages = 0
            last_page_full = False
            for page in range(max_pages):
                data = await _wfs_get_features(
                    context,
                    layer_id,
                    params=_feature_params(
                        feature_type=feature_type,
                        cql_filter=cql_filter,
                        page_size=page_size,
                        start_index=page * page_size,
                    ),
                )
                page_features = data["features"]
                features.extend(page_features)
                pages += 1
                last_page_full = len(page_features) >= page_size
                page_matched = _total_matched(data)
                if page_matched is not None:
                    matched = page_matched
                if not page_features or (matched is not None and len(features) >= matched):
                    break
                if matched is None and not last_page_full:
                    break
            if matched is not None:
                truncated = len(features) < matched
            elif pages >= max_pages and last_page_full:
                probe = await _wfs_get_features(
                    context,
                    layer_id,
                    params=_feature_params(
                        feature_type=feature_type,
                        cql_filter=cql_filter,
                        page_size=1,
                        start_index=len(features),
                    ),
                )
                truncated = bool(probe["features"])
            else:
                truncated = False
            return ActionResult(
                data={
                    "feature_collection": {
                        "type": "FeatureCollection",
                        "features": features,
                    },
                    "layer_id": layer_id,
                    "retrieved_pages": pages,
                    "truncated": truncated,
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
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "description": item.get("description"),
                }
                for item in items
                if isinstance(item, dict) and isinstance(item.get("id"), int)
            ]
            total = None
            resource_range = response.headers.get("X-Resource-Range", "") if getattr(response, "headers", None) else ""
            if "/" in resource_range:
                try:
                    total = int(resource_range.rsplit("/", 1)[1])
                except ValueError:
                    pass
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
