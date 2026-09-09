# OpenRouteService Integration

Geocode addresses and generate drive-time catchment polygons through the [OpenRouteService API](https://openrouteservice.org/dev/). The integration is designed for spatial workflows, including New Zealand demographic catchment analysis.

## Setup & authentication

Create a free OpenRouteService API key at the [OpenRouteService developer portal](https://openrouteservice.org/dev/#/signup), then add it as the integration connection's **API Key**. The key is passed only in the `Authorization` header; it is never added to request URLs or returned in action output.

Typical catchment workflow: call `geocode_address` for a place in New Zealand, confirm the match when `is_low_confidence` is true, then pass the returned coordinates to `get_isochrone` with the drive-time bands you need.

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
- `time_minutes` (integer array, required) — one to ten driving-time bands in whole minutes from 1 to 60, for example `[10, 15, 30]`. OpenRouteService rejects longer driving ranges and more than 10 intervals.
- `travel_mode` (optional) — v1 supports `driving-car` only.

**Outputs**

- `geojson` — the **unaltered** GeoJSON FeatureCollection returned by OpenRouteService. The integration also parses a JSON-string response when the provider labels it `application/geo+json`.
- `provider_metadata` — unaltered provider metadata when present.
- `profile` and `time_minutes` — the routing profile and bands requested.

## Errors and rate limits

Provider failures are returned as a successful action payload (`result: false`) rather than an SDK `ActionError`, so a calling skill can read `error_type` and `retry_after_seconds` and decide whether to retry. Check `result` before using coordinates or GeoJSON. Credentials and provider error bodies are never returned.

HeiGIT enforces **two** quotas per API key ([FAQ](https://giscience.github.io/openrouteservice/frequently-asked-questions)):

| Limit | HTTP | `error_type` | What to do |
| --- | --- | --- | --- |
| Minutely (sliding 60s window) | 429 | `rate_limit` | Wait `retry_after_seconds` (from `Retry-After`, default 60) then retry. |
| Daily (24h window from first request, not midnight) | 403 | `quota_exceeded` (quota wording only) or `quota_or_unauthorized` (combined/empty 403) | Do **not** retry shortly. Check the [HeiGIT dashboard](https://openrouteservice.org/dev/#/home). If the type is `quota_or_unauthorized`, also check the API key. |

A 403 is `quota_exceeded` only when the body mentions quota and not an unauthorized key. HeiGIT’s combined wording (`Daily quota reached or API key unauthorized`) is `quota_or_unauthorized` — staff document 403 as either daily quota or a key that is not allowed, and the body does not distinguish them. A 403 that only says access is disallowed is `authorization`. None of these mean the `driving-car` profile is missing.

Other classifications: `authentication` (401), `invalid_request` (400, or a blank API key / empty time bands), `not_found` (404 — no result; retrying will not help), `not_acceptable` (406), `provider_error` (other HTTP, or a 2xx body that is not the expected GeoJSON), `request_failed` (network/timeout after retries).

`get_isochrone` uses a 90-second timeout and does not retry on timeout, so a slow compute that already counted against daily quota is not charged again. Driving-time bands are capped at 60 minutes and 10 intervals because that is the public isochrone limit.

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
