# OpenRouteService Integration

Geocode addresses, generate drive-time catchment polygons, and calculate road-network travel-time matrices through the [OpenRouteService API](https://openrouteservice.org/dev/). The integration is designed for spatial workflows, including New Zealand demographic catchment analysis.

## Setup & authentication

Create a free OpenRouteService API key at the [OpenRouteService developer portal](https://openrouteservice.org/dev/#/signup), then add it as the integration connection's **API Key**. The key is passed only in the `Authorization` header; it is never added to request URLs or returned in action output.

Typical catchment workflow: call `geocode_address` for a place in New Zealand, confirm the match when `is_low_confidence` is true, then pass the returned coordinates to `get_isochrone` with the drive-time bands you need. `get_travel_time_matrix` is a labelled origin–destination table only; it does not select facilities or apply demographic rules.

## Actions

### `geocode_address`

Finds an address or place through HeiGIT Pelias (`GET https://api.heigit.org/pelias/v1/search`) and defaults the country boundary to `NZ`.

**Inputs**

- `address` (string, required) — address or place name to search for.
- `country` (string, optional) — ISO 3166-1 alpha-2 country boundary; defaults to `NZ`.

**Outputs**

- Best match: `address`, `latitude`, `longitude`, `confidence`, and `match_type`. `found` is true only when at least one feature has numeric coordinates; features without a point are omitted from `matches`.
- `is_low_confidence` — true when the provider score is lower than 0.8 (or absent); confirm these matches before using them downstream.
- `matches` — provider matches that include a point, retaining the original feature in each item.
- `geocoding` — provider geocoding metadata.

### `get_isochrone`

Generates one or more drive-time bands in a single request through the current HeiGIT OpenRouteService API gateway, requesting JSON or GeoJSON as documented by the API Playground.

**Inputs**

- `latitude`, `longitude` (number, required) — origin point in WGS84 coordinates.
- `time_minutes` (integer array, required) — one to ten driving-time bands in whole minutes from 1 to 60, for example `[5, 10, 15, 30]`. Catchment workflows typically send one to five bands in one call. OpenRouteService rejects longer driving ranges and more than 10 intervals.
- `travel_mode` (optional) — v1 supports `driving-car` only.
- `export_geojson` (optional, default false) — if true, also return the FeatureCollection as a platform file object.

**Outputs**

- `geojson` — a GeoJSON FeatureCollection. The request sets HeiGIT `smoothing` to `0` so polygons are not generalised. Each feature includes a stable `time_minutes` property. Features are sorted in ascending time-band order. The integration parses a JSON-string response when the provider labels it `application/geo+json`.
- `provider_metadata` — unaltered provider metadata when present.
- `profile` and `time_minutes` — the routing profile and requested bands (deduplicated, ascending).
- `attribution`, `engine_version`, `build_date`, `graph_date`, `osm_date` — copied from provider metadata when supplied.
- `files` — empty unless `export_geojson` is true. The SDK has no separate artifact API. Files go on `ActionResult.data["files"]` as `{name, contentType, content}` (standard base64), the same Autohive platform channel as Gmail and doc-maker. Autohive materialises that as a tool-output path such as `/tool-outputs/isochrones.geojson`; agents see the path, not the base64. The file never includes the API key.

### `get_travel_time_matrix`

Returns driving durations, and optional distances, for every labelled origin–destination pair through `POST https://api.heigit.org/openrouteservice/v2/matrix/{profile}`.

**Inputs**

- `origins`, `destinations` (array, required) — each item is `{id, latitude, longitude}`. IDs are caller-defined strings and must be unique within origins and within destinations. The same id may appear once as an origin and once as a destination. Each list is at most 10,000 items. The product `origins × destinations` must be at most 10,000 pairs or the action returns `invalid_request` (schema `maxItems` applies to each list separately).
- `travel_mode` (optional) — v1 supports `driving-car` only.
- `include_distance` (optional, default false) — if true, also return road-network distances in metres.
- `export_format` (optional) — `json` or `csv`. If omitted, return the compact result only.

The action accepts at most 10,000 origin–destination pairs. OpenRouteService allows 3,500 routes per HTTP call; larger matrices are split automatically, then reassembled and checked so each pair appears exactly once.

**Outputs**

- `pairs` — origin-major, destination-minor objects with `origin_id`, `destination_id`, unrounded `duration_seconds`, and `distance_metres` (null when distance was not requested or the route is unreachable). Unreachable, unsnappable, infinite, or NaN values are `null`, not `0`. A true zero-time route stays `0`.
- `origins` / `destinations` — requested coordinates in input order, plus provider snapping (`snapped_latitude`, `snapped_longitude`, `snapped_distance_metres`, optional street `name`) when supplied.
- `unreachable_count` — number of pairs whose duration is null.
- `warnings` — provider warning objects when the matrix body or metadata includes them; otherwise `[]`. Live HeiGIT Matrix typically omits this field. Unreachable routes are `null` durations in `pairs`, not warning entries.
- `provider_metadata`, `attribution`, `engine_version`, `build_date`, `graph_date`, `osm_date` — copied from provider metadata when supplied.
- `files` — empty unless `export_format` is set. JSON is the compact payload without `files` or credentials. CSV columns are `origin_id,destination_id,duration_seconds,distance_metres` with empty cells for nulls. IDs that start with `=`, `+`, `-`, or `@` are prefixed with `'` in the CSV only, so spreadsheets do not treat them as formulas; compact JSON keeps the original IDs. Serialization failure omits `files` and still returns the compact result.

## Errors and rate limits

Provider failures are returned as a successful action payload (`result: false`) rather than an SDK `ActionError`, so a calling skill can read `error_type` / `error_code`, `retry_safe`, `recovery`, and `retry_after_seconds` and decide whether to retry. Check `result` before using coordinates, GeoJSON, or matrix pairs. Credentials, HTML error pages, stack traces, and provider error bodies are never returned.

`error_type` `rate_limit` (HTTP 429) is retry-safe after `retry_after_seconds` when no provider call in that action has already succeeded. Daily quota (`quota_exceeded`) and ambiguous 403 (`quota_or_unauthorized`) are **not** retry-safe. A `get_travel_time_matrix` 429 after an earlier batch succeeded is `rate_limit` with `retry_safe: false`.

HeiGIT enforces **two** quotas per API key ([FAQ](https://giscience.github.io/openrouteservice/frequently-asked-questions)):

| Limit | HTTP | `error_type` | What to do |
| --- | --- | --- | --- |
| Minutely (sliding 60s window) | 429 | `rate_limit` | If `retry_safe` is true, wait `retry_after_seconds` (from `Retry-After`, default 60) then retry. If `retry_safe` is false (matrix after a billed batch), do not retry the same request. |
| Daily (24h window from first request, not midnight) | 403 | `quota_exceeded` (quota wording only) or `quota_or_unauthorized` (combined/empty 403) | Do **not** retry shortly. Check the [HeiGIT dashboard](https://openrouteservice.org/dev/#/home). If the type is `quota_or_unauthorized`, also check the API key. |

A 403 is `quota_exceeded` only when the body mentions quota and not an unauthorized key. HeiGIT’s combined wording (`Daily quota reached or API key unauthorized`) is `quota_or_unauthorized` — staff document 403 as either daily quota or a key that is not allowed, and the body does not distinguish them. A 403 that only says access is disallowed is `authorization`. None of these mean the `driving-car` profile is missing.

Other classifications: `authentication` (401), `invalid_request` (400, a blank API key, empty time bands, duplicate matrix ids, or more than 10,000 matrix pairs), `not_found` (404 — no result; retrying will not help), `not_acceptable` (406), `provider_error` (other HTTP, or a 2xx body that is not the expected shape). `request_failed` is a network failure after the SDK retry budget. `get_isochrone` maps a timeout to `request_failed` with `retry_safe: false`. `get_travel_time_matrix` maps a timeout to `error_type` `timeout` with `retry_safe: false`. Schema rejections (missing fields, empty arrays, unsupported `travel_mode`) are SDK validation errors, not `result: false`.

`get_isochrone` uses a 90-second timeout and does not retry on timeout, so a slow compute that already counted against daily quota is not charged again. `get_travel_time_matrix` uses the same 90-second timeout per batch. A mid-batch rate limit after a successful batch is `rate_limit` with `retry_safe: false` (earlier batches may already have been billed). A rate limit on the first batch stays retry-safe. A mid-batch provider failure returns no partial matrix. A geocode network failure stays `retry_safe: true`. Driving-time bands are capped at 60 minutes and 10 intervals because that is the public isochrone limit.

## Testing

Unit tests (mocked, CI default):

```bash
pytest openrouteservice/
python ../autohive-integrations-tooling/scripts/validate_integration.py openrouteservice
python ../autohive-integrations-tooling/scripts/check_code.py openrouteservice
```

Live API tests are read-only. They skip unless `OPENROUTESERVICE_API_KEY` is set (see the repo-root `.env.example`):

```bash
pytest openrouteservice/tests/test_openrouteservice_integration.py -m "integration and not destructive"
```

The live suite includes a GeoJSON file-export round trip (`export_geojson: true`) and a small Auckland travel-time matrix, including an unreachable pair and optional JSON export.
