"""
Land Information New Zealand (LINZ) Integration

Reads property, title, ownership and parcel data from the LINZ Data Service
(LDS) Web Feature Service (WFS) API.

USE CASE — owners of multiple properties:
-----------------------------------------
The headline action ``find_multi_property_owners`` scans the
"NZ Property Title Owners" layer (``layer-50806``) — one row per distinct
(owner, title) pair — aggregates distinct titles per owner, and returns owners
who appear on more than one title. Owner names come from a per-row field, never
from splitting the aggregated ``owners`` display string on ``layer-50805``
(LINZ builds that string with ``string_agg(DISTINCT owner, ', ')`` over
unescaped free-text names, so a comma inside a real name is indistinguishable
from the separator). Title descriptors (``estate_description``, ``type``) are
enriched from ``layer-50805`` afterwards.

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

from defusedxml import ElementTree as DefusedET

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
LAYER_TITLE_OWNERS = "layer-50806"  # NZ Property Title Owners: one row per (owner, title) (licensed)
TABLE_TITLE_OWNERS_LIST = "table-51564"  # NZ Property Titles Owners List: normalised owner records (licensed)
LAYER_TITLES = "layer-50804"  # NZ Property Titles (no owner names)
LAYER_PRIMARY_PARCELS = "layer-50772"  # NZ Primary Parcels

WFS_VERSION = "2.0.0"
# LDS caps JSON GetFeature responses; 1000 is a safe per-page size.
DEFAULT_PAGE_SIZE = 1000
# Safety ceiling for the multi-property scan so a broad filter can't run away.
MAX_SCAN_HARD_CAP = 10000
# Hard cap on limit for the single-request list actions (aligned with the LDS
# page size) — enforced at runtime as well as in the input schemas.
MAX_QUERY_LIMIT = 1000
# Hard cap for list_available_layers; the capabilities document is already in
# memory, so this only bounds response size.
MAX_LAYER_LIST_LIMIT = 2000
# Titles per detail-enrichment request (title_no IN (...) keeps the URL short).
TITLE_DETAIL_CHUNK = 200

# Fields requested when scanning layer-50806 — excludes the (large) title
# geometry, which LDS omits when propertyName is set.
OWNER_SCAN_FIELDS = "owner,title_no,title_status,land_district,part_ownership"

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


def _bounded_limit(value: Any, default: int, maximum: int) -> int:
    """Clamp a user-supplied limit to [1, maximum]; None falls back to default."""
    limit = default if value is None else int(value)
    return min(max(limit, 1), maximum)


def _bounded_start_index(value: Any) -> Optional[int]:
    """Clamp a user-supplied start index to >= 0 (None passes through)."""
    if value is None:
        return None
    return max(int(value), 0)


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
    property_name: Optional[str] = None,
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
    if property_name:
        params["propertyName"] = property_name

    response = await context.fetch(url, method="GET", params=params)
    _check_wfs_response(response)

    data = response.data
    if isinstance(data, str):
        raise RuntimeError(f"LINZ WFS returned a non-JSON response: {_short(data)}")
    return data if isinstance(data, dict) else {"features": []}


async def _wfs_get_capabilities(context: ExecutionContext) -> str:
    """Fetch the WFS GetCapabilities document (XML) for the user's key."""
    url = LDS_WFS_URL_TEMPLATE.format(key=_get_api_key(context))
    params = {"service": "WFS", "version": WFS_VERSION, "request": "GetCapabilities"}
    response = await context.fetch(url, method="GET", params=params)
    _check_wfs_response(response)
    data = response.data
    if not isinstance(data, str):
        raise RuntimeError(f"LINZ WFS GetCapabilities returned an unexpected response: {_short(data)}")
    return data


def _parse_capabilities_layers(xml_text: str) -> List[Dict[str, Any]]:
    """Extract the FeatureType entries a key can query from GetCapabilities.

    Matches elements by local name so namespace prefixes don't matter, and
    strips the ``data.linz.govt.nz:`` prefix from layer ids.
    """
    # fromstring rejects str input carrying an XML encoding declaration.
    root = DefusedET.fromstring(xml_text.encode("utf-8"))
    layers: List[Dict[str, Any]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "FeatureType":
            continue
        entry: Dict[str, Any] = {"id": None, "title": None}
        for child in element:
            tag = child.tag.rsplit("}", 1)[-1]
            text = (child.text or "").strip()
            if tag == "Name":
                entry["id"] = text.rsplit(":", 1)[-1] or None
            elif tag == "Title":
                entry["title"] = text or None
        if entry["id"]:
            layers.append(entry)
    return layers


async def _wfs_collect(
    context: ExecutionContext,
    type_name: str,
    *,
    cql_filter: Optional[str],
    max_records: int,
    sort_by: Optional[str] = None,
    property_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Page through GetFeature results up to ``max_records`` features.

    Returns ``{"features": [...], "scanned": N, "truncated": bool}``.
    ``truncated`` is True only when matching records were actually omitted:
    a full final page alone doesn't prove more matches exist, so the server's
    numeric match count is consulted, falling back to probing for one record
    past the cap.
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
            property_name=property_name,
        )
        features = _extract_features(collection)
        collected.extend(features)

        if len(features) < page_size:
            break  # last page
        start_index += page_size
        if len(collected) >= max_records:
            total = _total_matched(collection)
            if total is not None:
                truncated = total > len(collected)
            else:
                # LDS reported an unknown total — probe one record past the
                # cap to see whether anything was actually omitted.
                probe = await _wfs_get_features(
                    context,
                    type_name,
                    cql_filter=cql_filter,
                    count=1,
                    start_index=len(collected),
                    sort_by=sort_by,
                    property_name=property_name,
                )
                truncated = bool(_extract_features(probe))
            break

    return {"features": collected, "scanned": len(collected), "truncated": truncated}


def _strip_geometry(feature: Dict[str, Any], include_geometry: bool) -> Dict[str, Any]:
    """Return a feature dict, optionally dropping the (large) geometry."""
    props = _properties(feature)
    if include_geometry:
        return {"id": feature.get("id"), "geometry": feature.get("geometry"), **props}
    return {"id": feature.get("id"), **props}


# =============================================================================
# Owner-name helpers
# =============================================================================


def _owner_display_name(props: Dict[str, Any]) -> Optional[str]:
    """Build an owner's display name from a normalised owners-list row.

    Mirrors how LINZ constructs owner names for its aggregated layers: the
    corporate name as-is, or ``prime_other_names + prime_surname`` for
    individuals.
    """
    corporate = props.get("corporate_name")
    if corporate and str(corporate).strip():
        return str(corporate).strip()
    parts = [props.get("prime_other_names"), props.get("prime_surname")]
    name = " ".join(str(p).strip() for p in parts if p and str(p).strip())
    return name or None


def _split_owners(owners_value: Any) -> List[str]:
    """Split the LDS concatenated ``owners`` display string into names.

    LAST-RESORT FALLBACK ONLY: LINZ builds ``owners`` by comma-joining
    unescaped free-text names, so an owner whose stored name contains a comma
    cannot be distinguished from a separator. Prefer the per-row sources
    (``layer-50806`` / ``table-51564``) wherever they are accessible.
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

            limit = _bounded_limit(inputs.get("limit"), 100, MAX_QUERY_LIMIT)
            collection = await _wfs_get_features(
                context,
                LAYER_TITLES_OWNERS,
                cql_filter=cql,
                count=limit,
                start_index=_bounded_start_index(inputs.get("start_index")),
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
    """Get the owners and details of a single title by title number.

    Title details come from ``layer-50805``. Owner names come from the
    normalised owners list (``table-51564``) — one record per registered
    owner, no comma-splitting. Only when that table yields nothing (e.g. a key
    without access to it) does the action fall back to best-effort splitting
    of the aggregated ``owners`` display string, flagged via ``owners_exact``.
    """

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

            try:
                rows_collection = await _wfs_get_features(
                    context,
                    TABLE_TITLE_OWNERS_LIST,
                    cql_filter=f"title_no = {_cql_literal(title_no)}",
                    count=DEFAULT_PAGE_SIZE,
                )
                owner_rows = _extract_features(rows_collection)
            except RuntimeError:
                owner_rows = []  # key can't reach the normalised table

            owners: List[str] = []
            owner_details: List[Dict[str, Any]] = []
            seen_keys = set()
            for row in owner_rows:
                row_props = _properties(row)
                name = _owner_display_name(row_props)
                if not name:
                    continue
                owner_details.append(
                    {
                        "owner_name": name,
                        "owner_type": row_props.get("owner_type"),
                        "estate_share": row_props.get("estate_share"),
                        "prime_surname": row_props.get("prime_surname"),
                        "prime_other_names": row_props.get("prime_other_names"),
                        "corporate_name": row_props.get("corporate_name"),
                        "name_suffix": row_props.get("name_suffix"),
                    }
                )
                key = _owner_key(name)
                if key not in seen_keys:
                    seen_keys.add(key)
                    owners.append(name)

            owners_exact = bool(owners)
            if not owners_exact:
                owners = _split_owners(props.get("owners"))

            return ActionResult(
                data={
                    "title_no": props.get("title_no", title_no),
                    "owners": owners,
                    "owners_exact": owners_exact,
                    "owner_details": owner_details,
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


async def _enrich_title_details(context: ExecutionContext, results: List[Dict[str, Any]]) -> None:
    """Merge estate_description/type from layer-50805 into title records.

    The owner scan runs against layer-50806, which doesn't carry estate
    descriptors; look them up per distinct title in chunked ``title_no IN``
    queries (geometry excluded) and fill the records in place.
    """
    title_nos = sorted({t["title_no"] for owner in results for t in owner["titles"]})
    details: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(title_nos), TITLE_DETAIL_CHUNK):
        chunk = title_nos[i : i + TITLE_DETAIL_CHUNK]
        in_list = ", ".join(_cql_literal(t) for t in chunk)
        collection = await _wfs_get_features(
            context,
            LAYER_TITLES_OWNERS,
            cql_filter=f"title_no IN ({in_list})",
            count=len(chunk),
            property_name="title_no,estate_description,type",
        )
        for feature in _extract_features(collection):
            props = _properties(feature)
            if props.get("title_no"):
                details[props["title_no"]] = props
    for owner in results:
        for title_record in owner["titles"]:
            detail = details.get(title_record["title_no"])
            if detail:
                title_record["estate_description"] = detail.get("estate_description")
                title_record["type"] = detail.get("type")


@linz.action("find_multi_property_owners")
class FindMultiPropertyOwnersAction(ActionHandler):
    """Find owners who appear on more than one property title.

    Scans the NZ Property Title Owners layer (``layer-50806``, one row per
    distinct owner/title pair) within a scoping filter and aggregates distinct
    titles per owner. Owner names are exact per-row values — never parsed out
    of the aggregated ``owners`` display string, whose unescaped commas can't
    be split reliably. Returns owners holding at least ``min_properties``
    titles, with estate descriptors enriched from ``layer-50805``.
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
                clauses.append(f"owner ILIKE {_cql_literal('%' + owner_name + '%')}")
            if land_district:
                clauses.append(f"land_district = {_cql_literal(land_district)}")
            if inputs.get("status"):
                clauses.append(f"title_status = {_cql_literal(inputs['status'])}")
            if extra:
                clauses.append(extra)

            min_properties = int(inputs.get("min_properties") or 2)
            if min_properties < 1:
                min_properties = 1
            max_scan = int(inputs.get("max_titles_scanned") or 2000)
            include_title_details = inputs.get("include_title_details")
            if include_title_details is None:
                include_title_details = True

            scan = await _wfs_collect(
                context,
                LAYER_TITLE_OWNERS,
                cql_filter=_and(clauses),
                max_records=max_scan,
                property_name=OWNER_SCAN_FIELDS,
            )

            # Aggregate distinct titles per owner. Each scanned row is one
            # (owner, title) pair, so no name splitting or client-side owner
            # re-filtering is needed — the CQL filter already matched the
            # per-row owner field.
            owners_index: Dict[str, Dict[str, Any]] = {}
            for feature in scan["features"]:
                props = _properties(feature)
                name = (props.get("owner") or "").strip()
                title_no = props.get("title_no")
                if not name or title_no is None:
                    continue
                key = _owner_key(name)
                entry = owners_index.setdefault(key, {"owner_name": name, "_titles": {}})
                entry["_titles"][title_no] = {
                    "title_no": title_no,
                    "land_district": props.get("land_district"),
                    "status": props.get("title_status"),
                    "part_ownership": props.get("part_ownership"),
                    "estate_description": None,
                    "type": None,
                }

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

            if results and include_title_details:
                await _enrich_title_details(context, results)

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
            limit = _bounded_limit(inputs.get("limit"), 100, MAX_QUERY_LIMIT)
            collection = await _wfs_get_features(
                context,
                LAYER_PRIMARY_PARCELS,
                cql_filter=cql,
                count=limit,
                start_index=_bounded_start_index(inputs.get("start_index")),
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
            limit = _bounded_limit(inputs.get("limit"), 100, MAX_QUERY_LIMIT)
            collection = await _wfs_get_features(
                context,
                _normalize_layer(layer),
                cql_filter=inputs.get("cql_filter"),
                count=limit,
                start_index=_bounded_start_index(inputs.get("start_index")),
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


# =============================================================================
# Action: list_available_layers (works with any valid key — also a diagnostic)
# =============================================================================


_NO_LAYERS_HINT = (
    "Your API key is valid but cannot see any layers, so every data action will fail with "
    "'Feature type ... unknown'. Edit the key (or create a new one) at "
    "https://data.linz.govt.nz/my/api/ and enable the query/web-services (WFS) scope, or remove "
    "its layer restrictions. Ownership layers such as layer-50805 additionally require accepting "
    "the LINZ Licence for Personal Data on your LINZ account."
)

DEFAULT_LAYER_LIST_LIMIT = 500


@linz.action("list_available_layers")
class ListAvailableLayersAction(ActionHandler):
    """List the LDS layers the user's API key can query, via GetCapabilities.

    GetCapabilities succeeds for any valid key regardless of layer permissions,
    so this action doubles as a connection diagnostic: an empty list means the
    key lacks the query/WFS scope (or all layer permissions), not that the
    request was malformed.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            xml_text = await _wfs_get_capabilities(context)
            layers = _parse_capabilities_layers(xml_text)

            available_ids = {layer["id"] for layer in layers}
            integration_layers = {
                layer_id: layer_id in available_ids
                for layer_id in (
                    LAYER_TITLES_OWNERS,
                    LAYER_TITLE_OWNERS,
                    TABLE_TITLE_OWNERS_LIST,
                    LAYER_TITLES,
                    LAYER_PRIMARY_PARCELS,
                )
            }

            name_contains = inputs.get("name_contains")
            if name_contains:
                needle = str(name_contains).lower()
                layers = [
                    layer
                    for layer in layers
                    if needle in (layer["id"] or "").lower() or needle in (layer["title"] or "").lower()
                ]

            limit = _bounded_limit(inputs.get("limit"), DEFAULT_LAYER_LIST_LIMIT, MAX_LAYER_LIST_LIMIT)
            truncated = len(layers) > limit

            if not available_ids:
                note = _NO_LAYERS_HINT
            elif not all(integration_layers.values()):
                missing = [layer_id for layer_id, ok in integration_layers.items() if not ok]
                note = (
                    f"The key cannot access {', '.join(missing)}, used by this integration's typed "
                    "actions. For the ownership datasets (layer-50805, layer-50806, table-51564) "
                    "accept the LINZ Licence for Personal Data; otherwise check the key's layer "
                    "permissions at https://data.linz.govt.nz/my/api/."
                )
            else:
                note = "The key can access all layers used by this integration's typed actions."

            return ActionResult(
                data={
                    "layers": layers[:limit],
                    "count": min(len(layers), limit),
                    "total_available": len(available_ids),
                    "truncated": truncated,
                    "integration_layers": integration_layers,
                    "note": note,
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))
