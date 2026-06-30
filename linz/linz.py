"""
Land Information New Zealand (LINZ) Integration

Reads property, title, ownership and parcel data from the LINZ Data Service
(LDS) Web Feature Service (WFS) API.

USE CASE — owners of multiple properties:
-----------------------------------------
The headline action ``find_multi_property_owners`` scans the
"NZ Property Titles Including Owners" layer (``layer-50805``), aggregates the
concatenated ``owners`` field across distinct titles, and returns owners who
appear on more than one title.

LIMITATION — commercial vs residential:
---------------------------------------
LINZ title/ownership data does NOT classify a property as commercial or
residential. That distinction lives in council / Quotable Value (QV) *rating*
data, which is not part of LINZ. This integration therefore surfaces the LINZ
descriptors that exist (``estate_description``, parcel ``appellation`` /
``parcel_intent``) so a downstream agent can make an informed inference, but it
cannot definitively label a property's use type. See README for details.

SECURITY MODEL:
---------------
This integration uses a per-user LINZ Data Service API key (custom auth). The
ownership layer (``layer-50805``) is licensed personal data: each user must
generate their own API key AND accept the LINZ Licence for Personal Data on
their LINZ account before that layer is accessible to the key.
"""

from typing import Any, Dict, List, Optional

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    Integration,
)

linz = Integration.load()

# =============================================================================
# API configuration
# =============================================================================

# The API key is interpolated into the service path, not a query parameter:
#   https://data.linz.govt.nz/services;key=<API_KEY>/wfs
LDS_WFS_URL_TEMPLATE = "https://data.linz.govt.nz/services;key={key}/wfs"  # noqa: E501

# Well-known LDS layers used by the typed actions.
LAYER_TITLES_OWNERS = "layer-50805"  # NZ Property Titles Including Owners (licensed)
LAYER_TITLES = "layer-50804"  # NZ Property Titles (no owner names)
LAYER_PRIMARY_PARCELS = "layer-50772"  # NZ Primary Parcels

WFS_VERSION = "2.0.0"
# LDS caps JSON GetFeature responses; 1000 is a safe per-page size.
DEFAULT_PAGE_SIZE = 1000
# Safety ceiling for the multi-property scan so a broad filter can't run away.
MAX_SCAN_HARD_CAP = 10000

PROPERTY_TYPE_NOTE = (
    "LINZ data does not classify properties as commercial or residential; that "
    "lives in council/QV rating data. Use estate_description and parcel details "
    "to infer property type."
)


# =============================================================================
# Auth
# =============================================================================


def _get_api_key(context: ExecutionContext) -> str:
    """Read the LINZ Data Service API key from auth (flat or nested)."""
    auth = context.auth or {}
    creds = auth.get("credentials", auth) if isinstance(auth, dict) else {}
    key = (creds or {}).get("api_key", "")
    if not key:
        raise ValueError(
            "LINZ Data Service API key is required. Create one at "
            "https://data.linz.govt.nz/my/api/ and ensure it has accepted the "
            "LINZ Licence for Personal Data for ownership layers."
        )
    return key


# =============================================================================
# CQL / layer helpers
# =============================================================================


def _normalize_layer(layer: str) -> str:
    """Accept '50805', 'layer-50805' or 'table-1234' and return a WFS typeName."""
    layer = str(layer).strip()
    if not layer:
        raise ValueError("layer is required")
    if layer.startswith("layer-") or layer.startswith("table-"):
        return layer
    if layer.isdigit():
        return f"layer-{layer}"
    return layer


def _cql_literal(value: str) -> str:
    """Quote a CQL string literal, escaping embedded single quotes."""
    return "'" + str(value).replace("'", "''") + "'"


def _and(clauses: List[str]) -> Optional[str]:
    clauses = [c for c in clauses if c]
    if not clauses:
        return None
    return " AND ".join(f"({c})" for c in clauses)


def _extract_features(collection: Any) -> List[Dict[str, Any]]:
    """Pull the feature list out of a GeoJSON FeatureCollection."""
    if isinstance(collection, dict):
        feats = collection.get("features")
        if isinstance(feats, list):
            return feats
    return []


def _properties(feature: Dict[str, Any]) -> Dict[str, Any]:
    props = feature.get("properties")
    return props if isinstance(props, dict) else {}


# =============================================================================
# WFS client
# =============================================================================


_LICENCE_HINT = (
    "access denied. Verify your API key is valid and that your LINZ account has accepted the "
    "LINZ Licence for Personal Data required to access ownership layers such as layer-50805. "
    "(LINZ reports an inaccessible layer as an 'unknown' feature type.)"
)


def _extract_exception_text(xml: str) -> str:
    """Pull the human-readable message out of an OWS/WFS exception report."""
    for tag in ("ExceptionText", "ServiceException"):
        start = xml.find(f"<ows:{tag}")
        if start == -1:
            start = xml.find(f"<{tag}")
        if start != -1:
            gt = xml.find(">", start)
            end = xml.find("<", gt + 1)
            if gt != -1 and end != -1:
                return xml[gt + 1 : end].strip()
    return _short(xml)


def _is_unknown_layer_exception(text: str) -> bool:
    """True when LDS reports a feature type as unknown (usually = no licence)."""
    low = text.lower()
    return "unknown" in low and ("feature type" in low or "typename" in low or "layer-" in low)


def _check_wfs_response(response: Any) -> None:
    """Raise a clear error for non-2xx responses or WFS exception reports."""
    status = getattr(response, "status", None)
    data = getattr(response, "data", None)
    is_xml_exception = isinstance(data, str) and ("ExceptionReport" in data or "ServiceException" in data)

    if isinstance(status, int) and 200 <= status < 300:
        # LDS sometimes returns an XML ExceptionReport with a 200 status.
        if is_xml_exception:
            msg = _extract_exception_text(data)
            if _is_unknown_layer_exception(msg):
                raise RuntimeError(f"LINZ WFS: {_LICENCE_HINT} Detail: {msg}")
            raise RuntimeError(f"LINZ WFS exception: {msg}")
        return

    if is_xml_exception:
        msg = _extract_exception_text(data)
        if _is_unknown_layer_exception(msg):
            raise RuntimeError(f"LINZ WFS {status}: {_LICENCE_HINT} Detail: {msg}")
        detail = msg
    else:
        detail = data if isinstance(data, str) else (data.get("message") if isinstance(data, dict) else str(data))

    if status in (401, 403):
        raise RuntimeError(f"LINZ WFS {status}: {_LICENCE_HINT} Detail: {_short(detail)}")
    if status == 404:
        raise RuntimeError(f"LINZ WFS 404: layer not found. Check the layer id. Detail: {_short(detail)}")
    raise RuntimeError(f"LINZ WFS error {status}: {_short(detail)}")


def _short(text: Any, limit: int = 400) -> str:
    s = str(text or "").strip()
    return s if len(s) <= limit else s[:limit] + "…"


def _total_matched(collection: Dict[str, Any]) -> Optional[int]:
    """Return a numeric match count, or None (LDS often returns 'unknown')."""
    for key in ("numberMatched", "totalFeatures"):
        val = collection.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


async def _wfs_get_features(
    context: ExecutionContext,
    type_name: str,
    *,
    cql_filter: Optional[str] = None,
    count: Optional[int] = None,
    start_index: Optional[int] = None,
    sort_by: Optional[str] = None,
    srs_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Issue a WFS 2.0.0 GetFeature request and return the GeoJSON collection."""
    url = LDS_WFS_URL_TEMPLATE.format(key=_get_api_key(context))
    params: Dict[str, Any] = {
        "service": "WFS",
        "version": WFS_VERSION,
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "json",
    }
    if cql_filter:
        params["cql_filter"] = cql_filter
    if count is not None:
        params["count"] = count
    if start_index is not None:
        params["startIndex"] = start_index
    if sort_by:
        params["sortBy"] = sort_by
    if srs_name:
        params["srsName"] = srs_name

    response = await context.fetch(url, method="GET", params=params)
    _check_wfs_response(response)

    data = response.data
    if isinstance(data, str):
        raise RuntimeError(f"LINZ WFS returned a non-JSON response: {_short(data)}")
    return data if isinstance(data, dict) else {"features": []}


async def _wfs_collect(
    context: ExecutionContext,
    type_name: str,
    *,
    cql_filter: Optional[str],
    max_records: int,
    sort_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Page through GetFeature results up to ``max_records`` features.

    Returns ``{"features": [...], "scanned": N, "truncated": bool}``.
    """
    max_records = min(max(int(max_records), 1), MAX_SCAN_HARD_CAP)
    collected: List[Dict[str, Any]] = []
    start_index = 0
    truncated = False

    while len(collected) < max_records:
        page_size = min(DEFAULT_PAGE_SIZE, max_records - len(collected))
        collection = await _wfs_get_features(
            context,
            type_name,
            cql_filter=cql_filter,
            count=page_size,
            start_index=start_index,
            sort_by=sort_by,
        )
        features = _extract_features(collection)
        collected.extend(features)

        if len(features) < page_size:
            break  # last page
        start_index += page_size
        if len(collected) >= max_records:
            # There may be more matches than we scanned.
            truncated = True
            break

    return {"features": collected, "scanned": len(collected), "truncated": truncated}


def _strip_geometry(feature: Dict[str, Any], include_geometry: bool) -> Dict[str, Any]:
    """Return a feature dict, optionally dropping the (large) geometry."""
    props = _properties(feature)
    if include_geometry:
        return {"id": feature.get("id"), "geometry": feature.get("geometry"), **props}
    return {"id": feature.get("id"), **props}


# =============================================================================
# Owner-name parsing for the multi-property use case
# =============================================================================


def _split_owners(owners_value: Any) -> List[str]:
    """Split the LDS concatenated ``owners`` string into individual names.

    LDS renders multiple owners comma-separated, e.g.
    ``"JOHN DAVID SMITH, JANE MARY SMITH"`` or ``"ACME PROPERTIES LIMITED"``.
    This is best-effort: an owner whose stored name contains a comma cannot be
    distinguished from a separator.
    """
    if not owners_value:
        return []
    if isinstance(owners_value, list):
        parts = [str(p) for p in owners_value]
    else:
        parts = str(owners_value).split(",")
    return [p.strip() for p in parts if p and p.strip()]


def _owner_key(name: str) -> str:
    """Normalise an owner name for grouping (case/whitespace-insensitive)."""
    return " ".join(name.upper().split())


# =============================================================================
# Action: search_property_titles
# =============================================================================


@linz.action("search_property_titles")
class SearchPropertyTitlesAction(ActionHandler):
    """Search NZ property titles (with owners) by owner name, title, or district."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            clauses: List[str] = []
            if inputs.get("owner_name"):
                clauses.append(f"owners ILIKE {_cql_literal('%' + inputs['owner_name'] + '%')}")
            if inputs.get("title_no"):
                clauses.append(f"title_no = {_cql_literal(inputs['title_no'])}")
            if inputs.get("land_district"):
                clauses.append(f"land_district = {_cql_literal(inputs['land_district'])}")
            if inputs.get("status"):
                clauses.append(f"status = {_cql_literal(inputs['status'])}")

            extra = inputs.get("cql_filter")
            if extra:
                clauses.append(extra)

            cql = _and(clauses)
            if not cql:
                return ActionError(
                    message="Provide at least one filter (owner_name, title_no, land_district, status or cql_filter)."
                )

            limit = inputs.get("limit") or 100
            collection = await _wfs_get_features(
                context,
                LAYER_TITLES_OWNERS,
                cql_filter=cql,
                count=limit,
                start_index=inputs.get("start_index"),
            )
            features = _extract_features(collection)
            titles = [_strip_geometry(f, include_geometry=False) for f in features]

            return ActionResult(
                data={
                    "titles": titles,
                    "count": len(titles),
                    "total_matched": _total_matched(collection),
                    "note": PROPERTY_TYPE_NOTE,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# Action: get_title_owners
# =============================================================================


@linz.action("get_title_owners")
class GetTitleOwnersAction(ActionHandler):
    """Get the owners and details of a single title by title number."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            title_no = inputs["title_no"]  # required by schema

            collection = await _wfs_get_features(
                context,
                LAYER_TITLES_OWNERS,
                cql_filter=f"title_no = {_cql_literal(title_no)}",
                count=10,
            )
            features = _extract_features(collection)
            if not features:
                return ActionError(message=f"No title found for title_no '{title_no}'.")

            props = _properties(features[0])
            owners = _split_owners(props.get("owners"))
            return ActionResult(
                data={
                    "title_no": props.get("title_no", title_no),
                    "owners": owners,
                    "number_owners": props.get("number_owners"),
                    "estate_description": props.get("estate_description"),
                    "land_district": props.get("land_district"),
                    "status": props.get("status"),
                    "type": props.get("type"),
                    "guarantee_status": props.get("guarantee_status"),
                    "issue_date": props.get("issue_date"),
                    "note": PROPERTY_TYPE_NOTE,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# Action: find_multi_property_owners (headline use case)
# =============================================================================


@linz.action("find_multi_property_owners")
class FindMultiPropertyOwnersAction(ActionHandler):
    """Find owners who appear on more than one property title.

    Scans the NZ Property Titles Including Owners layer within a scoping filter,
    splits the concatenated ``owners`` field, and aggregates distinct titles per
    owner. Returns owners holding at least ``min_properties`` titles.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            owner_name = inputs.get("owner_name")
            land_district = inputs.get("land_district")
            extra = inputs.get("cql_filter")

            # Require a scoping filter — the layer is national and cannot be
            # scanned in full.
            if not (owner_name or land_district or extra):
                return ActionError(
                    message=(
                        "A scoping filter is required: provide owner_name (e.g. a surname) and/or "
                        "land_district and/or cql_filter. Scanning all of New Zealand is not supported."
                    )
                )

            clauses: List[str] = []
            if owner_name:
                clauses.append(f"owners ILIKE {_cql_literal('%' + owner_name + '%')}")
            if land_district:
                clauses.append(f"land_district = {_cql_literal(land_district)}")
            if inputs.get("status"):
                clauses.append(f"status = {_cql_literal(inputs['status'])}")
            if extra:
                clauses.append(extra)

            min_properties = int(inputs.get("min_properties") or 2)
            if min_properties < 1:
                min_properties = 1
            max_scan = int(inputs.get("max_titles_scanned") or 2000)

            scan = await _wfs_collect(
                context,
                LAYER_TITLES_OWNERS,
                cql_filter=_and(clauses),
                max_records=max_scan,
            )

            # Aggregate distinct titles per owner.
            owners_index: Dict[str, Dict[str, Any]] = {}
            for feature in scan["features"]:
                props = _properties(feature)
                title_no = props.get("title_no")
                title_record = {
                    "title_no": title_no,
                    "land_district": props.get("land_district"),
                    "estate_description": props.get("estate_description"),
                    "type": props.get("type"),
                    "status": props.get("status"),
                    "number_owners": props.get("number_owners"),
                }
                names = _split_owners(props.get("owners"))
                for name in names:
                    # If owner_name was given, only aggregate matching owners so
                    # co-owners on the same title don't pollute the result.
                    if owner_name and owner_name.upper() not in name.upper():
                        continue
                    key = _owner_key(name)
                    entry = owners_index.setdefault(key, {"owner_name": name, "_titles": {}})
                    if title_no is not None:
                        entry["_titles"][title_no] = title_record

            results = []
            for entry in owners_index.values():
                titles = list(entry["_titles"].values())
                if len(titles) >= min_properties:
                    results.append(
                        {
                            "owner_name": entry["owner_name"],
                            "property_count": len(titles),
                            "titles": titles,
                        }
                    )
            results.sort(key=lambda r: r["property_count"], reverse=True)

            return ActionResult(
                data={
                    "owners": results,
                    "owner_count": len(results),
                    "titles_scanned": scan["scanned"],
                    "truncated": scan["truncated"],
                    "min_properties": min_properties,
                    "note": PROPERTY_TYPE_NOTE
                    + (
                        " Results truncated at max_titles_scanned — increase it or narrow the filter for completeness."
                        if scan["truncated"]
                        else ""
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# Action: search_parcels
# =============================================================================


@linz.action("search_parcels")
class SearchParcelsAction(ActionHandler):
    """Search NZ primary parcels by appellation, title, intent or district."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            clauses: List[str] = []
            if inputs.get("appellation"):
                clauses.append(f"appellation ILIKE {_cql_literal('%' + inputs['appellation'] + '%')}")
            if inputs.get("title_no"):
                clauses.append(f"titles ILIKE {_cql_literal('%' + inputs['title_no'] + '%')}")
            if inputs.get("parcel_intent"):
                clauses.append(f"parcel_intent = {_cql_literal(inputs['parcel_intent'])}")
            if inputs.get("land_district"):
                clauses.append(f"land_district = {_cql_literal(inputs['land_district'])}")
            if inputs.get("cql_filter"):
                clauses.append(inputs["cql_filter"])

            cql = _and(clauses)
            if not cql:
                return ActionError(
                    message=(
                        "Provide at least one filter (appellation, title_no, "
                        "parcel_intent, land_district or cql_filter)."
                    )
                )

            include_geometry = bool(inputs.get("include_geometry"))
            limit = inputs.get("limit") or 100
            collection = await _wfs_get_features(
                context,
                LAYER_PRIMARY_PARCELS,
                cql_filter=cql,
                count=limit,
                start_index=inputs.get("start_index"),
            )
            features = _extract_features(collection)
            parcels = [_strip_geometry(f, include_geometry=include_geometry) for f in features]

            return ActionResult(
                data={
                    "parcels": parcels,
                    "count": len(parcels),
                    "total_matched": _total_matched(collection),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# =============================================================================
# Action: query_layer (generic escape hatch)
# =============================================================================


@linz.action("query_layer")
class QueryLayerAction(ActionHandler):
    """Run a raw WFS GetFeature query against any LDS layer or table.

    Power-user escape hatch for layers/tables not covered by the typed actions
    (e.g. street addresses, geodetic marks, the owner-centric ownership tables).
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            layer = inputs["layer"]  # required by schema

            include_geometry = bool(inputs.get("include_geometry"))
            limit = inputs.get("limit") or 100
            collection = await _wfs_get_features(
                context,
                _normalize_layer(layer),
                cql_filter=inputs.get("cql_filter"),
                count=limit,
                start_index=inputs.get("start_index"),
                sort_by=inputs.get("sort_by"),
                srs_name=inputs.get("srs_name"),
            )
            features = _extract_features(collection)
            records = [_strip_geometry(f, include_geometry=include_geometry) for f in features]

            return ActionResult(
                data={
                    "records": records,
                    "count": len(records),
                    "total_matched": _total_matched(collection),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))
