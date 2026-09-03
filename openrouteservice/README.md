# OpenRouteService Integration

Geocode addresses and generate drive-time catchment polygons through the [OpenRouteService API](https://openrouteservice.org/dev/). The integration is designed for spatial workflows, including New Zealand demographic catchment analysis.

## Setup & authentication

Create a free OpenRouteService API key at the [OpenRouteService developer portal](https://openrouteservice.org/dev/#/signup), then add it as the integration connection's **API Key**. The key is passed only in the `Authorization` header; it is never added to request URLs or returned in action output.

Typical catchment workflow: call `geocode_address` for a place in New Zealand, confirm the match when `is_low_confidence` is true, then pass the returned coordinates to `get_isochrone` with the drive-time bands you need.

## Actions

### `geocode_address`

Finds an address or place and defaults the country boundary to `NZ`.

**Inputs**

- `address` (string, required) — address or place name to search for.
- `country` (string, optional) — ISO 3166-1 alpha-2 country boundary; defaults to `NZ`.

**Outputs**

- Best match: `address`, `latitude`, `longitude`, `confidence`, and `match_type`.
- `is_low_confidence` — true when the provider score is lower than 0.8 (or absent); confirm these matches before using them downstream.
- `matches` — all provider matches, retaining the original feature in each item.
- `geocoding` — provider geocoding metadata.

### `get_isochrone`

Generates one or more drive-time bands in a single request.

**Inputs**

- `latitude`, `longitude` (number, required) — origin point in WGS84 coordinates.
- `time_minutes` (integer array, required) — one or more travel-time bands, for example `[10, 15, 30]`.
- `travel_mode` (optional) — v1 supports `driving-car` only.

**Outputs**

- `geojson` — the **unaltered** GeoJSON FeatureCollection returned by OpenRouteService.
- `provider_metadata` — unaltered provider metadata when present.
- `profile` and `time_minutes` — the routing profile and bands requested.

## Errors and rate limits

A free-tier rate limit is returned as `result: false`, `error_type: "rate_limit"`, and `retry_after_seconds`, allowing a calling skill to ask the user to retry later. Authentication, authorization, invalid-request, and general provider failures are similarly classified without exposing API keys.

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
