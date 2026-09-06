"""Stats NZ Datafinder integration backed by Koordinates WFS/API services."""

from __future__ import annotations

from typing import Any
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
from xml.etree import ElementTree as ET  # nosec B405: used only to construct XML.

stats_nz_datafinder = Integration.load()

API_BASE_URL = "https://datafinder.stats.govt.nz/services/api/v1"
WFS_URL = "https://datafinder.stats.govt.nz/services/wfs"
_FILTER_NS = "http://www.opengis.net/ogc"
_GML_NS = "http://www.opengis.net/gml"
_OPERATORS = {
    "eq": "PropertyIsEqualTo",
    "neq": "PropertyIsNotEqualTo",
    "lt": "PropertyIsLessThan",
    "lte": "PropertyIsLessThanOrEqualTo",
    "gt": "PropertyIsGreaterThan",
    "gte": "PropertyIsGreaterThanOrEqualTo",
}


def _headers(context: ExecutionContext) -> dict[str, str]:
    credentials = context.auth.get("credentials", {}) if context.auth else {}
    api_key = credentials.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("A Stats NZ Datafinder API key is required.")
    return {"Authorization": f"Key {api_key}"}


def _position(position: Any) -> str:
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
    return f"{lon:.15g},{lat:.15g}"


def _ring_element(parent: ET.Element, ring: Any) -> None:
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError("Each polygon ring must contain at least four positions.")
    positions = [_position(point) for point in ring]
    if positions[0] != positions[-1]:
        raise ValueError("Each polygon ring must be closed.")
    linear_ring = ET.SubElement(parent, f"{{{_GML_NS}}}LinearRing")
    ET.SubElement(linear_ring, f"{{{_GML_NS}}}coordinates").text = " ".join(positions)


def _polygon_element(parent: ET.Element, polygon: Any) -> None:
    if not isinstance(polygon, list) or not polygon:
        raise ValueError("Each polygon must contain an exterior ring.")
    exterior = ET.SubElement(parent, f"{{{_GML_NS}}}outerBoundaryIs")
    _ring_element(exterior, polygon[0])
    for ring in polygon[1:]:
        interior = ET.SubElement(parent, f"{{{_GML_NS}}}innerBoundaryIs")
        _ring_element(interior, ring)


def _build_filter(geometry: dict[str, Any], attribute_filters: list[dict[str, Any]] | None) -> str:
    """Build an OGC Filter XML document without interpolating untrusted XML."""
    feature_filter = ET.Element(f"{{{_FILTER_NS}}}Filter")
    clauses: list[ET.Element] = []
    spatial = ET.Element(f"{{{_FILTER_NS}}}Intersects")
    ET.SubElement(spatial, f"{{{_FILTER_NS}}}PropertyName").text = "GEOMETRY"
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        gml_geometry = ET.SubElement(spatial, f"{{{_GML_NS}}}Polygon", {"srsName": "EPSG:4326"})
        _polygon_element(gml_geometry, coordinates)
    elif geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("A MultiPolygon must contain at least one polygon.")
        gml_geometry = ET.SubElement(spatial, f"{{{_GML_NS}}}MultiPolygon", {"srsName": "EPSG:4326"})
        for polygon in coordinates:
            member = ET.SubElement(gml_geometry, f"{{{_GML_NS}}}polygonMember")
            _polygon_element(member, polygon)
    else:
        raise ValueError("geometry.type must be Polygon or MultiPolygon.")
    clauses.append(spatial)

    for item in attribute_filters or []:
        operator = item.get("operator")
        property_name = item.get("property")
        value = item.get("value")
        if (
            operator not in _OPERATORS
            or not isinstance(property_name, str)
            or not property_name.replace("_", "a").isalnum()
            or property_name[0].isdigit()
        ):
            raise ValueError("Each attribute filter needs a valid property and supported operator.")
        if isinstance(value, (dict, list)) or value is None:
            raise ValueError("Attribute filter values must be strings, numbers, or booleans.")
        comparison = ET.Element(f"{{{_FILTER_NS}}}{_OPERATORS[operator]}")
        ET.SubElement(comparison, f"{{{_FILTER_NS}}}PropertyName").text = property_name
        ET.SubElement(comparison, f"{{{_FILTER_NS}}}Literal").text = (
            str(value).lower() if isinstance(value, bool) else str(value)
        )
        clauses.append(comparison)

    feature_filter.append(clauses[0] if len(clauses) == 1 else _and(clauses))
    return ET.tostring(feature_filter, encoding="unicode")


def _and(clauses: list[ET.Element]) -> ET.Element:
    result = ET.Element(f"{{{_FILTER_NS}}}And")
    for clause in clauses:
        result.append(clause)
    return result


def _resolve_feature_type(layer_id: int, capability_document: Any) -> str:
    """Return the advertised WFS feature type for a permitted Datafinder layer."""
    if not isinstance(capability_document, str):
        raise ValueError("Datafinder returned an invalid WFS capabilities response.")
    try:
        root = DefusedET.fromstring(capability_document)
    except DefusedET.ParseError as exc:
        raise ValueError("Datafinder returned malformed WFS capabilities.") from exc

    requested_name = f"layer-{layer_id}"
    feature_types = root.findall(".//{*}FeatureType")
    for feature_type in feature_types:
        name = feature_type.findtext("{*}Name")
        if name == requested_name or name == f":{requested_name}":
            return name

    raise ValueError(
        f"The connected Datafinder API key cannot query layer {layer_id} through WFS. "
        "Enable its Query Layer Data/WFS permission or use a key that can access this layer."
    )


def _provider_error(layer_id: int, error: HTTPError) -> ActionError:
    if error.status == 401:
        return ActionError("Datafinder rejected the API key. Check the connected account.")
    if error.status == 403:
        return ActionError(f"The connected Datafinder API key is not permitted to query layer {layer_id}.")
    if error.status == 400:
        return ActionError(
            f"Datafinder rejected the WFS request for layer {layer_id}. "
            "Verify the layer is WFS-enabled and that the API key has Query Layer Data/WFS permission."
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
            filter_xml = _build_filter(inputs["geometry"], inputs.get("attribute_filters"))
            metadata_response = await context.fetch(f"{API_BASE_URL}/layers/{layer_id}/", headers=headers)
            metadata = _metadata_result(layer_id, metadata_response.data)
            capabilities_response = await context.fetch(
                WFS_URL,
                headers=headers,
                params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
            )
            feature_type = _resolve_feature_type(layer_id, capabilities_response.data)
            features: list[Any] = []
            matched: int | None = None
            pages = 0
            for page in range(max_pages):
                response = await context.fetch(
                    WFS_URL,
                    headers=headers,
                    params={
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": feature_type,
                        "outputFormat": "application/json",
                        "srsName": "EPSG:4326",
                        "filter": filter_xml,
                        "count": page_size,
                        "startIndex": page * page_size,
                    },
                )
                data = response.data
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
            return _provider_error(layer_id, exc)
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
