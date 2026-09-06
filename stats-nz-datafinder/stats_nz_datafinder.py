"""Stats NZ Datafinder integration backed by Koordinates WFS/API services."""

from __future__ import annotations

import asyncio
from typing import Any
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
WFS_REQUEST_TIMEOUT_SECONDS = 30
_CQL_OPERATORS = {
    "eq": "=",
    "neq": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
}


def _headers(context: ExecutionContext) -> dict[str, str]:
    credentials = context.auth.get("credentials", {}) if context.auth else {}
    api_key = credentials.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("A Stats NZ Datafinder API key is required.")
    return {"Authorization": f"Key {api_key}"}


class WfsRequestError(Exception):
    """A WFS failure with a safe, status-only error payload."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"WFS request failed with HTTP {status}")


def _wfs_url(context: ExecutionContext, layer_id: int) -> str:
    """Build Datafinder's documented per-layer key-in-path WFS URL without exposing the key."""
    credentials = context.auth.get("credentials", {}) if context.auth else {}
    api_key = credentials.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("A Stats NZ Datafinder API key is required.")
    return f"https://datafinder.stats.govt.nz/services;key={quote(api_key, safe='')}/wfs/layer-{layer_id}"


async def _wfs_request(context: ExecutionContext, params: dict[str, Any], *, layer_id: int) -> Any:
    """Call WFS without allowing its key-bearing URL into SDK error logging."""
    try:
        timeout = aiohttp.ClientTimeout(total=WFS_REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(_wfs_url(context, layer_id), params=params) as response:
                if response.status >= 400:
                    raise WfsRequestError(response.status)
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise WfsRequestError(503) from exc


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and value.replace("_", "a").isalnum() and not value[0].isdigit()


def _lon_lat(position: Any) -> tuple[float, float]:
    if not isinstance(position, list) or len(position) < 2:
        raise ValueError("Each GeoJSON position must contain longitude and latitude.")
    lon, lat = position[0], position[1]
    if (
        isinstance(lon, bool)
        or isinstance(lat, bool)
        or not isinstance(lon, (int, float))
        or not isinstance(lat, (int, float))
    ):
        raise ValueError("GeoJSON longitude and latitude must be numbers.")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("GeoJSON coordinates must be WGS84 longitude/latitude values.")
    return float(lon), float(lat)


def _wkt_ring(ring: Any) -> str:
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError("Each polygon ring must contain at least four positions.")
    points = [_lon_lat(point) for point in ring]
    if points[0] != points[-1]:
        raise ValueError("Each polygon ring must be closed.")
    return "(" + ", ".join(f"{lon:.15g} {lat:.15g}" for lon, lat in points) + ")"


def _wkt_polygon(polygon: Any) -> str:
    if not isinstance(polygon, list) or not polygon:
        raise ValueError("Each polygon must contain an exterior ring.")
    return "POLYGON(" + ", ".join(_wkt_ring(ring) for ring in polygon) + ")"


def _wkt_geometry(geometry: dict[str, Any]) -> str:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return _wkt_polygon(coordinates)
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("A MultiPolygon must contain at least one polygon.")
        polygons = [_wkt_polygon(polygon).removeprefix("POLYGON") for polygon in coordinates]
        return "MULTIPOLYGON(" + ", ".join(polygons) + ")"
    raise ValueError("geometry.type must be Polygon or MultiPolygon.")


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
    return field if _is_identifier(field) else "Shape"


def _build_cql_filter(wkt: str, attribute_filters: list[dict[str, Any]] | None, geometry_field: str) -> str:
    """Build a GeoServer CQL Intersects filter from validated WKT and attribute clauses."""
    spatial = f"INTERSECTS({geometry_field}, SRID=4326;{wkt})"
    clauses: list[str] = []
    for item in attribute_filters or []:
        operator = item.get("operator")
        property_name = item.get("property")
        value = item.get("value")
        if operator not in _CQL_OPERATORS or not _is_identifier(property_name):
            raise ValueError("Each attribute filter needs a valid property and supported operator.")
        if isinstance(value, (dict, list)) or value is None:
            raise ValueError("Attribute filter values must be strings, numbers, or booleans.")
        clauses.append(f"{property_name} {_CQL_OPERATORS[operator]} {_cql_literal(value)}")
    return spatial + "".join(f" AND ({clause})" for clause in clauses)


def _local_feature_type_name(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def _resolve_feature_type(layer_id: int, capability_document: Any) -> str:
    """Return the advertised WFS feature type, falling back to layer-{id}."""
    requested_name = f"layer-{layer_id}"
    if not isinstance(capability_document, str):
        raise ValueError("Datafinder returned an invalid WFS capabilities response.")
    try:
        root = DefusedET.fromstring(capability_document)
    except DefusedET.ParseError as exc:
        raise ValueError("Datafinder returned malformed WFS capabilities.") from exc

    for feature_type in root.findall(".//{*}FeatureType"):
        name = feature_type.findtext("{*}Name")
        if isinstance(name, str) and _local_feature_type_name(name) == requested_name:
            return name
    return requested_name


def _provider_error(layer_id: int, status: int) -> ActionError:
    if status == 401:
        return ActionError("Datafinder rejected the API key. Check the connected account.")
    if status == 403:
        return ActionError(f"The connected Datafinder API key is not permitted to query layer {layer_id}.")
    if status == 400:
        return ActionError(
            f"Datafinder rejected the WFS request for layer {layer_id}. "
            "Check the geometry, attribute filters, and that the layer exposes WFS."
        )
    return ActionError("Datafinder could not complete the request. Please try again later.")


def _vintage(metadata: dict[str, Any]) -> str | None:
    for key in ("collected_at", "published_at", "first_published_at", "updated_at"):
        value = metadata.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None


def _metadata_result(layer_id: int, data: Any) -> dict[str, Any]:
    metadata = data if isinstance(data, dict) else {}
    source_url = f"{API_BASE_URL}/layers/{layer_id}/"
    description = metadata.get("description")
    licence = metadata.get("license")
    attribution = (
        metadata.get("attribution") or metadata.get("source_attribution") or metadata.get("supplier_reference")
    )
    return {
        "layer_id": layer_id,
        "title": metadata.get("title") if isinstance(metadata.get("title"), str) else None,
        "description": description if isinstance(description, str) else None,
        "data_vintage": _vintage(metadata),
        "licence": licence if isinstance(licence, str) else None,
        "attribution": attribution if isinstance(attribution, str) else None,
        "source_url": source_url,
    }


@stats_nz_datafinder.action("get_layer_metadata")
class GetLayerMetadataAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        try:
            response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=_headers(context))
            return ActionResult(data=_metadata_result(layer_id, response.data))
        except ValueError as exc:
            return ActionError(message=str(exc))


@stats_nz_datafinder.action("query_layer_by_geometry")
class QueryLayerByGeometryAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        layer_id = inputs["layer_id"]
        page_size, max_pages = (
            inputs.get("page_size", 1000),
            inputs.get("max_pages", 10),
        )
        try:
            headers = _headers(context)
            wkt = _wkt_geometry(inputs["geometry"])
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            cql_filter = _build_cql_filter(
                wkt, inputs.get("attribute_filters"), _geometry_field(metadata_response.data)
            )
            capabilities = await _wfs_request(
                context,
                {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
                layer_id=layer_id,
            )
            feature_type = _resolve_feature_type(layer_id, capabilities)
            features: list[Any] = []
            matched: int | None = None
            pages = 0
            for page in range(max_pages):
                data = await _wfs_request(
                    context,
                    {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": feature_type,
                        "outputFormat": "json",
                        "srsName": "EPSG:4326",
                        "cql_filter": cql_filter,
                        "count": page_size,
                        "startIndex": page * page_size,
                    },
                    layer_id=layer_id,
                )
                if not isinstance(data, dict) or not isinstance(data.get("features"), list):
                    raise ValueError("Datafinder returned a malformed WFS feature response.")
                features.extend(data["features"])
                pages += 1
                number_matched = data.get("numberMatched")
                if isinstance(number_matched, int):
                    matched = number_matched
                if not data["features"] or (matched is not None and len(features) >= matched):
                    break
                if matched is None and len(data["features"]) < page_size:
                    break
            truncated = matched is not None and len(features) < matched
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
        except ValueError as exc:
            return ActionError(message=str(exc))
        except HTTPError as exc:
            return _provider_error(layer_id, exc.status)
        except WfsRequestError as exc:
            return _provider_error(layer_id, exc.status)
        except RateLimitError:
            return ActionError("Datafinder rate-limited this request. Please retry shortly.")


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
        except ValueError as exc:
            return ActionError(message=str(exc))
