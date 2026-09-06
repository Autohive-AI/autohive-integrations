# Stats NZ Datafinder integration

Queries Stats NZ Datafinder (Koordinates) vector layers for catchment and demographic workflows. It uses a workspace-level API key; the key is never returned by an action.

## Setup and permissions

Create a Datafinder API key and connect it using the integration's **API key** field. The key must be authorised to:

- query layer data through WFS;
- read the relevant public layer details and catalogue entries.

The catalogue and layer-metadata API calls use `Authorization: Key <API_KEY>`. Datafinder WFS requires the documented key-in-path form (`/services;key=<API_KEY>/wfs`); the integration makes those WFS requests directly and never returns or logs a key-bearing URL.

## Actions

### Query Layer by Geometry

`query_layer_by_geometry` converts an RFC 7946 WGS84 `Polygon` or `MultiPolygon` into an OGC WFS `Intersects` filter and requests GeoJSON from Datafinder WFS. It returns the original feature geometries and properties without coordinate rounding, plus citation fields from the layer metadata.

Optional `attribute_filters` support `eq`, `neq`, `lt`, `lte`, `gt`, and `gte`, combined with the geometry filter using `AND`. They are encoded as OGC Filter XML; property names are restricted to identifier characters to prevent filter injection.

The action first calls WFS `GetCapabilities` with the connected API key and resolves the layer’s advertised feature type. If the layer is absent, it returns an actionable permission/configuration error rather than forwarding Datafinder’s raw XML response. It then requests WFS 2.0 pages with `count` and `startIndex`, up to `page_size × max_pages` features. `truncated` is true when the WFS `numberMatched` count shows that the configured page cap stopped retrieval. Datafinder must expose WFS 2.0 pagination for the selected layer; validate this against a real connected account before production rollout.

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

### Get Layer Metadata

`get_layer_metadata` returns title, description, a best-available data-vintage date, licence, supplier/source attribution, and the canonical Datafinder API URL.

### Search Layers

`search_layers` searches public vector layers in the Datafinder catalogue. It returns concise layer identifiers, titles, descriptions and, when the server provides it, the total matched count.

## Limits and operational notes

- WFS server-side limits and individual layer permissions apply.
- Full geometry is returned as supplied by WFS. The integration intentionally does not simplify or round response coordinates.
- Metadata fields are provider-controlled. If a layer does not publish licence or attribution, those output fields are `null`.
- All operations are read-only.

## Development

Run structural/config checks, unit tests, then package with the current HiveUp CLI:

```sh
hiveup check structure stats-nz-datafinder
hiveup validate stats-nz-datafinder
hiveup test stats-nz-datafinder
hiveup package stats-nz-datafinder
```
