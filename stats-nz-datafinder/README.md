# Stats NZ Datafinder integration

Read-only access to Stats NZ Geographic Data Service layers through
[Datafinder](https://datafinder.stats.govt.nz/)'s Koordinates API and WFS
services. The integration uses a workspace-level API key; the key is never
returned by an action.

Official documentation:

- [Stats NZ Geographic Data Service](https://datafinder.stats.govt.nz/)
- [Datafinder API browser](https://datafinder.stats.govt.nz/services/api/v1/)
- [Koordinates WFS web services](https://help.koordinates.com/query-api-and-web-services/find-and-use-web-services/)
- [Koordinates API](https://help.koordinates.com/api/)

## Actions

| Action | What it does |
|--------|--------------|
| `query_layer_by_geometry` | Query a layer by polygon, point, bbox, and/or attribute filters. Returns compact attribute records. Geometry omitted unless requested. |
| `get_layer_metadata` | Return a short description, field list, vintage, licence, and attribution. |
| `search_layers` | Search public vector layers. Compact cards: id, title, published_at, queryable. |

## Authentication

This integration uses a **per-user Datafinder API key** (custom auth).

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
attribute records**, not a GeoJSON FeatureCollection. Full polygon rings are
the main cause of agent context compaction; geometry is omitted unless
`include_geometry` is true. Default `page_size` is 50.

**How to scope a query** — at least one of these is required (unscoped
national scans are rejected):

| Input | When to use | `overlap_fraction` |
|--------|-------------|--------------------|
| `geometry` Polygon / MultiPolygon | Catchment / isochrone clip | Area of the feature inside the polygon |
| `geometry` Point | "What SA2/meshblock is this school in?" | Always `1.0` — do **not** area-weight a point |
| `bbox` `[west, south, east, north]` | Rough map window without building GeoJSON | Same as a polygon |
| `attribute_filters` | Named-area lookup, e.g. SA2 name `contains` `"Island Bay"` | `1.0` (whole feature) |

`contains` is a case-insensitive substring match (`ILIKE`). Other operators:
`eq`, `neq`, `lt`, `lte`, `gt`, `gte`. Combine filters with a spatial clip
using AND. Do not send `geometry` and `bbox` together.

`overlap_fraction` is an area share of the feature, not a population share.
`total_matched` is the WFS `numberMatched` count when the server reports it.

It uses the layer's geometry field from metadata, defaulting to `Shape`.
Spatial clips become GeoServer CQL `INTERSECTS` with `SRID=4326` EWKT.
Datafinder's WFS 2.0 endpoint rejects OGC Filter XML `Intersects` requests
(HTTP 400 / `NullPointerException`), so this action does not use that form.

The action first calls WFS `GetCapabilities` on the layer-specific endpoint and
uses the advertised feature type when present. If that document omits the layer
(or uses a namespaced name such as `kx:layer-123`), the action still queries
`layer-<id>` on the per-layer WFS endpoint rather than treating the omission as
a key-permission failure. It then requests WFS 2.0 pages with `count` and
`startIndex`, up to `page_size × max_pages` features. When metadata exposes a
usable key (`primary_key_fields`, `id`, or a Stats NZ geography code such as
`SA22023_V1_00`), each page and the truncation probe send the same `sortBy` so
`startIndex` windows do not skip or repeat rows. Duplicate feature ids across
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
  "page_size": 50,
  "max_pages": 1
}
```

## Get Layer Metadata

`get_layer_metadata` returns title, a **short** description (first paragraph,
capped), the non-geometry `fields` list (`name` / `type`, plus `title` when the
API provides one), a best-available data-vintage date, licence, supplier/source
attribution, and the canonical Datafinder API URL. Licence objects from the live
API are normalised to their title string. Census layers often name columns
`VAR_1_1`, `VAR_1_2`, … — the short description is the best in-payload hint for
what those codes mean; lookup attachments are not fetched.

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
- **No `Retry-After` / rate-limit semantics** on WFS. A `429` is returned as a
  generic WFS error.
- **A fixed 30s per-request timeout.**

REST catalogue/metadata calls still go through `context.fetch` and therefore
surface SDK `RateLimitError` as a retry hint. For WFS, retry from the calling
workflow.

## Limits and operational notes

- WFS server-side limits and individual layer permissions apply.
- Geometry is omitted from query results unless `include_geometry` is true.
  Overlap is computed from the WFS geometry and then dropped from the payload.
- Metadata fields are provider-controlled. If a layer does not publish licence
  or attribution, those output fields are `null`.
- Offset paging can shift if Datafinder republishes a layer between requests.
  Without a declared key, WFS also does not guarantee page order.
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
for one.
