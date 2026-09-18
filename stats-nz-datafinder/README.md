# Stats NZ Datafinder integration

Read-only access to Stats NZ Geographic Data Service layers through
[Datafinder](https://datafinder.stats.govt.nz/)'s Koordinates API and WFS
services. Actions never return the API key.

Official documentation:

- [Stats NZ Geographic Data Service](https://datafinder.stats.govt.nz/)
- [Datafinder API browser](https://datafinder.stats.govt.nz/services/api/v1/)
- [Koordinates WFS web services](https://help.koordinates.com/query-api-and-web-services/find-and-use-web-services/)
- [Koordinates API](https://help.koordinates.com/api/)

## Actions

| Action | What it does |
|--------|--------------|
| `query_area_statistics` | Area-weight explicitly configured additive Census counts for a Polygon/MultiPolygon catchment (inline geometry or a GeoJSON file). Returns compact totals, not raw SA1 records. |
| `query_layer_by_geometry` | Query a layer by polygon, point, bbox, a Polygon/MultiPolygon GeoJSON file, and/or attribute filters. Returns compact attribute records. Census `VAR_*` columns are omitted unless requested. `export_geojson` returns all retrieved features as a platform GeoJSON file after a complete query. |
| `get_layer_metadata` | Return a short description, field list (`coded` flags `VAR_*` columns, titles/measure/year from the lookup codebook when present), catalogue page URL, and codebook **download** links. |
| `search_layers` | Search public vector layers. Compact cards: id, title, published_at, queryable. |

## Authentication

A Stats NZ Datafinder API key is required. Actions never return the key.

1. Sign in (or register) at [datafinder.stats.govt.nz](https://datafinder.stats.govt.nz/).
2. Create an API key at <https://datafinder.stats.govt.nz/my/api/>.
3. Enable the scopes needed to query layer data through WFS and to read public layer details.

Catalogue and layer-metadata calls use `Authorization: Key <API_KEY>`. Datafinder
WFS requires the documented per-layer key-in-path form
(`/services;key=<API_KEY>/wfs/layer-<id>`). The integration makes those WFS
requests directly and never returns or logs a key-bearing URL. It does not use
the site-wide `/wfs` capabilities document, which is too large to fetch
reliably and often omits Census layers even when they are WFS-enabled.

aiohttp builds its error strings from the request URL, which carries the **key**,
and GeoServer exception reports may echo the submitted CQL filter. No provider
or transport error text is ever surfaced: it is used only to classify the
failure. Unit tests assert that a sentinel API key is absent from transport
errors, XML exception reports, non-2xx bodies, and the final `ActionError`.

## Query Layer

`query_layer_by_geometry` queries a layer through WFS and returns **flat
attribute records**, not a GeoJSON FeatureCollection. Geometry is omitted
unless `include_geometry` is true. Census `VAR_*` columns are omitted unless
you pass `fields` (preferred) or `include_coded_fields`. Default `page_size`
is 50 (maximum 200).

**Suggested agent sequence**

1. `search_layers` to pick a `layer_id` (prefer a named geography such as SA2
   over “totals by topic” dumps when you only need a few measures).
2. `get_layer_metadata` for field names. `coded_field_count` is the number of
   `VAR_*` columns; `page_url` is the catalogue page. When Datafinder publishes a
   lookup table, `attachments[].url` is the **file download** URL (not the JSON
   metadata endpoint) and matching `fields[].title` / `measure` / `year` are
   filled from that CSV. Use `measure` `Count` only with Query Area Statistics;
   skip Median and Mean.
3. `query_layer_by_geometry` with a scope **and** `fields` set to the columns
   you will actually use (geography code/name plus the `VAR_*` measures).
4. Named-area lookup uses `ieq` on the name field, not `contains`.

**How to scope a query** — at least one of these is required (unscoped
national scans are rejected):

| Input | When to use | `overlap_fraction` |
|--------|-------------|--------------------|
| `geometry` Polygon / MultiPolygon | Catchment / isochrone clip | Area of the feature inside the polygon |
| `file` | Large Polygon/MultiPolygon catchment from a platform GeoJSON file (`name`, `contentType`, base64 `content`). Point files are rejected. | Same as the selected Polygon / MultiPolygon |
| `geometry` Point | "What SA2/meshblock is this school in?" | Always `1.0` — do **not** area-weight a point |
| `bbox` `[west, south, east, north]` | Rough map window without building GeoJSON. Unwrapped longitudes (Datafinder east ≈ 184.5) and boxes that cross 180° are accepted. CQL matches both wrapped and unwrapped layer coordinates so Chatham Islands are not dropped | Same as a polygon |
| `attribute_filters` | Named-area lookup. Use `ieq` for an exact SA2/SA1 name | `1.0` (whole feature) |

`ieq` is a case-insensitive exact match. `contains` is a substring match
(`ILIKE %value%`) — `contains` `"Wellington Central"` also matches
**Mount Wellington Central**. Other operators: `eq`, `neq`, `lt`, `lte`,
`gt`, `gte`. Combine filters with a spatial clip using AND. Do not send more
than one of `geometry`, `file`, and `bbox`.

`export_geojson: true` returns a platform file
(`name`, `contentType`, base64 `content`) named
`layer-<id>-query.geojson` after the query completes. The FeatureCollection
includes every retrieved page, original WGS84 geometries (no simplification),
requested attributes, and `overlap_fraction` / `overlap_area_sq_km` /
`feature_area_sq_km`. Null, `-997`, and `-999` are preserved. The export
feature count matches `record_count`. Incomplete pagination fails closed
instead of writing a partial file. Compact JSON records still omit geometry
unless `include_geometry` is true.

A GeoJSON file may be a FeatureCollection, a Feature, or a bare
Polygon/MultiPolygon. If the file contains exactly one Polygon or
MultiPolygon, that feature is used. If it contains more than one eligible
area feature, pass `feature_index` (0-based index into the **original**
`features` array, including points and lines) or `feature_filter`
`{ "property": "time_minutes", "equals": 30 }`. `feature_filter` matches the
original array, including points and lines — two hits are ambiguous even if
only one is a polygon. The selected feature must be a Polygon or MultiPolygon;
otherwise the action fails before querying. Numeric `30` matches `30.0`; the
string `"30"` does not match the number `30`. File size is capped at 5 MB decoded.
When a file is used, the compact
`geometry_source` citation (`name`, `feature_index`, and matched properties
when a filter was used) is included; coordinates are not echoed.

`overlap_fraction` is an area share of the feature, not a population share.
It is `null` for line or point features under a polygon/bbox clip — those have
no area, so a 1.0 on any intersection would overstate overlap.
`total_matched` is the WFS `numberMatched` count when the server reports it.

It uses the layer's geometry field from metadata, defaulting to `Shape`.
Spatial clips become GeoServer CQL `INTERSECTS` with `SRID=4326` EWKT.
GetFeature is POST form-encoded KVP so a large catchment `cql_filter` is not
stuffed into a GET URL (which would 414). GetCapabilities stays GET.
Datafinder's WFS 2.0 endpoint rejects OGC Filter XML `Intersects` requests
(HTTP 400 / `NullPointerException`), so this action does not use that form.

A bbox may use Datafinder-style unwrapped longitudes (the national extent uses
east ≈ 184.5 for the Chatham Islands). After wrapping to WGS84, a box that
crosses 180° is sent as a MultiPolygon clip **and** as the original unwrapped
rectangle, combined with OR, so INTERSECTS matches layers that store Chatham
at lon ≈ 184 as well as layers that wrap to ≈ -176. GeoJSON `geometry`
coordinates must already be in [-180, 180] per RFC 7946; a clip that uses a
negative longitude also sends a +360° copy for the same reason. Overlap is
computed against ±360° copies of each feature ring.

The action first calls WFS `GetCapabilities` on the layer-specific endpoint and
uses the advertised feature type when present. If that document omits the layer
(or uses a namespaced name such as `kx:layer-123`), the action still queries
`layer-<id>` on the per-layer WFS endpoint rather than treating the omission as
a key-permission failure. It then requests WFS 2.0 pages with `count` and
`startIndex`, up to `page_size × max_pages` features. When metadata exposes a
usable key (`primary_key_fields` including composite keys, `id`, or a Stats NZ
geography code such as `SA22023_V1_00`), each page and the truncation probe send
the same `sortBy` so `startIndex` windows do not skip or repeat rows. Duplicate feature ids across
pages are dropped. If the layer has no such field, pages are unordered.
`truncated` is true when the WFS `numberMatched` count (or a one-feature probe,
when the total is unknown) shows that the configured page cap stopped retrieval.

Example input:

```json
{
  "layer_id": 119479,
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[174.70, -41.30], [174.80, -41.30], [174.80, -41.20], [174.70, -41.30]]]
  },
  "fields": ["SA22023_V1_00", "SA22023_V1_00_NAME", "VAR_1_1"],
  "page_size": 50,
  "max_pages": 1
}
```

`coded_fields_omitted` is the number of `VAR_*` columns not returned. Pass those
names in `fields` on a follow-up query if you need them.

## Query Area Statistics

`query_area_statistics` is the catchment-reporting action. Agents should use it
instead of `query_layer_by_geometry` when the workflow needs **totals**, not
every SA1 row. A 10-minute Wellington drive-time polygon can intersect hundreds
of SA1s; this action area-weights configured additive counts in integration
code and returns a compact result.

**Suggested catchment sequence**

1. OpenRouteService `geocode_address` then `get_isochrone` for 5/10/15/30-minute bands (`export_geojson: true` if the polygon is too large to inline).
2. `search_layers` / `get_layer_metadata` to pick a Census SA1 layer and exact `VAR_*` field names.
3. `query_area_statistics` once per isochrone band with those fields. Prefer `file` plus `feature_filter: {"property": "time_minutes", "equals": 10}` over inlining the polygon.
4. Compute rates or percentages in the report from two additive counts if needed.

**Inputs**

- `layer_id` and a WGS84 Polygon or MultiPolygon, either as inline `geometry` or as `file` (same selection rules as Query Layer). Do not send both.
- `measures` — bounded list of additive counts. Each item has `key`, `label`,
  `field` (exact Datafinder name), `unit` (`count`), and `aggregation`
  (`additive_count`). Compute rates or percentages in the report from two counts.
- `missing_values` — default `[-999, -997]` (confidential and not available).
  Those sentinels, plus null, absent, and non-numeric values, are **unavailable**.
  They are never converted to zero. Numeric zero is a valid count.
- `page_size` / `max_pages` — same bounds as Query Layer. This action defaults
  `max_pages` to 100 and **fails closed** if pagination is incomplete.
- `max_source_features` — safety cap (default 10 000). Exceeding it fails closed.

Example file input:

```json
{
  "layer_id": 120766,
  "file": {
    "name": "catchments.geojson",
    "contentType": "application/geo+json",
    "content": "<base64 GeoJSON>"
  },
  "feature_filter": {"property": "time_minutes", "equals": 30},
  "measures": [
    {
      "key": "population",
      "label": "Usually resident population",
      "field": "VAR_1_3",
      "unit": "count",
      "aggregation": "additive_count"
    }
  ]
}
```

**Behaviour**

- Validates every requested field against current layer metadata.
- Rejects non-additive aggregations (medians, rates, percentages, indexes).
  Coded `VAR_*` fields must have codebook measure `Count`; if the codebook
  cannot classify a field, the action fails closed.
- Queries every intersecting feature, deduplicates by feature id, and fails on
  duplicate geography-code joins.
- Contribution = unrounded `source_value × overlap_fraction`.
- Overlap uses the existing WGS84 **geodesic** area method (`pyproj Geod`), not
  planar degrees. Fractions must fall in `[0, 1]` within a documented
  floating-point tolerance of `1e-6`.
- Default JSON is compact: totals, geography summary, method, layer citation,
  warnings, `validation_status`. No raw features or geometry. File-backed
  queries add `geometry_source` (`name`, `feature_index`, matched properties)
  without echoing coordinates.
- `validation_status` is `ok` only when every measure is fully included. It is
  `partial` if any measure has suppressed/missing values, and `unavailable` if
  no measure had a usable source value. Per-measure `status` is still on each
  result row.

**Errors**

Failures return `ActionError` with a compact corrective message: human-readable
text, a stable `Error code`, affected field, bounded valid alternatives when
known, recovery action, and whether retrying the same request is safe. Provider
bodies, HTML, stack traces, and API keys are never included.

## Get Layer Metadata

`get_layer_metadata` returns title, a **short** description (first paragraph,
capped), the non-geometry `fields` list (`name` / `type`; `coded` is true for
Census `VAR_*` columns), `coded_field_count`, `page_url` (the catalogue page,
not the API JSON), codebook **download** links when Datafinder publishes a
lookup, a best-available data-vintage date, licence, supplier/source
attribution, and the canonical Datafinder API URL. Licence objects from the live
API are normalised to their title string. Census layers often name columns
`VAR_1_1`, `VAR_1_2`, … with no labels in the layer schema. When a lookup CSV
is attached, the action downloads it (following off-origin redirects **without**
the API key) and copies `title`, `measure`, and `year` onto matching fields.
`attachments[].url` is the file `url_download` path, not the JSON attachment
metadata endpoint. `page_url` and attachment file URLs are returned only when
they are HTTPS on `datafinder.stats.govt.nz`; off-origin catalogue or file links
are dropped (the attachment name is kept). Do not area-weight fields whose
`measure` is Median or Mean.

## Search Layers

`search_layers` searches public vector layers. The catalogue list payload has
no field schema and usually no description, so the action returns compact
cards: `id`, `title`, `published_at`, `queryable` (true when the key can
spatial-query the layer), and a short description when the server sends one.
Pick a `layer_id`, then call `get_layer_metadata` for fields.

## ⚠️ No retries, backoff or rate-limit handling on WFS

WFS calls use `aiohttp` directly rather than the SDK's `context.fetch`, because
`context.fetch` logs the full request URL on error and Datafinder carries the
API key in that URL. The trade-off is that WFS requests do **not** inherit the
SDK client's request-resilience behaviour:

- **No automatic retries.** Every WFS call makes a single attempt.
- **No exponential backoff.**
- **No `Retry-After` parsing** on WFS. A `429` is returned with the same
  retry hint as REST `RateLimitError` (`Datafinder rate-limited this request.
  Please retry shortly.`) but the caller must retry.
- **Redirects are not followed.** A 301/302 would otherwise turn POST
  GetFeature into a GET with no `cql_filter` (an unscoped page) and could
  follow a key-bearing URL.
- **A fixed 30s per-request timeout.**

REST catalogue/metadata calls still go through `context.fetch` and therefore
surface SDK `RateLimitError` as a retry hint. For WFS, retry from the calling
workflow.

## Limits and operational notes

- WFS server-side limits and individual layer permissions apply.
- Overlap uses `shapely` and `pyproj` (GEOS/PROJ wheels). Install from
  `requirements.txt` on a platform that provides those wheels.
- Geometry is omitted from query results unless `include_geometry` is true.
  Overlap is computed from the WFS geometry and then dropped from the payload.
- Census `VAR_*` columns are omitted from query records unless listed in
  `fields` or `include_coded_fields` is true. `coded_fields_omitted` reports
  how many were dropped.
- Metadata fields are provider-controlled. If a layer does not publish licence
  or attribution, those output fields are `null`.
- Offset paging can shift if Datafinder republishes a layer between requests.
  Without a declared key, WFS also does not guarantee page order. The next
  `startIndex` is the number of features already returned, not `page × page_size`,
  so a short server page does not skip rows.
- If a later WFS page fails after some records were retrieved, those records
  are returned with `truncated` true rather than discarded.
- All operations are read-only.

## Testing

Unit tests (mocked HTTP, no network):

```bash
python -m pytest stats-nz-datafinder/tests/test_stats_nz_datafinder_unit.py -q
```

Integration tests (real Datafinder API — all read-only). They require
`STATS_NZ_DATAFINDER_API_KEY` and skip when it is unset:

```bash
STATS_NZ_DATAFINDER_API_KEY=... pytest stats-nz-datafinder/tests/test_stats_nz_datafinder_integration.py -m "integration and not destructive"
```

Optional: `STATS_NZ_DATAFINDER_TEST_LAYER_ID` pins `get_layer_metadata` and
`query_layer_by_geometry` to a known public vector layer instead of searching
for one. Query Area Statistics live tests use Census SA1 layer 120766.
