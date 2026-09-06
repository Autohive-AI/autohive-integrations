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
| `query_layer_by_geometry` | Return GeoJSON features from a layer that intersect a WGS84 Polygon or MultiPolygon. |
| `get_layer_metadata` | Return citation-ready layer metadata (vintage, licence, attribution). |
| `search_layers` | Search public vector layers in the Datafinder catalogue. |

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

## Query Layer by Geometry

`query_layer_by_geometry` converts an RFC 7946 WGS84 `Polygon` or `MultiPolygon`
into a GeoServer CQL `INTERSECTS` filter (`SRID=4326` EWKT) and requests GeoJSON
from Datafinder WFS. It uses the layer's geometry field from metadata, defaulting
to `Shape`. It returns the original feature geometries and properties without
coordinate rounding, plus citation fields from the layer metadata.

Optional `attribute_filters` support `eq`, `neq`, `lt`, `lte`, `gt`, and `gte`,
combined with the geometry filter using `AND`. Property names are restricted to
identifier characters to prevent filter injection. Datafinder's WFS 2.0 endpoint
rejects OGC Filter XML `Intersects` requests (HTTP 400 / `NullPointerException`),
so this action does not use that form.

The action first calls WFS `GetCapabilities` on the layer-specific endpoint and
uses the advertised feature type when present. If that document omits the layer
(or uses a namespaced name such as `kx:layer-123`), the action still queries
`layer-<id>` on the per-layer WFS endpoint rather than treating the omission as
a key-permission failure. It then requests WFS 2.0 pages with `count` and
`startIndex`, up to `page_size × max_pages` features. `truncated` is true when
the WFS `numberMatched` count (or a one-feature probe, when the total is
unknown) shows that the configured page cap stopped retrieval.

Example input:

```json
{
  "layer_id": 12345,
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[174.70, -41.30], [174.80, -41.30], [174.80, -41.20], [174.70, -41.30]]]
  },
  "attribute_filters": [{"property": "population", "operator": "gte", "value": 100}],
  "page_size": 500,
  "max_pages": 10
}
```

## Get Layer Metadata

`get_layer_metadata` returns title, description, a best-available data-vintage
date, licence, supplier/source attribution, and the canonical Datafinder API
URL. Licence objects from the live API are normalised to their title string.

## Search Layers

`search_layers` searches public vector layers in the Datafinder catalogue. It
returns concise layer identifiers, titles, descriptions and, when the server
provides it, the total matched count.

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
- Full geometry is returned as supplied by WFS. The integration intentionally
  does not simplify or round response coordinates.
- Metadata fields are provider-controlled. If a layer does not publish licence
  or attribution, those output fields are `null`.
- Offset paging can shift if Datafinder republishes a layer between requests.
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
