# Land Information New Zealand (LINZ) Integration

Read New Zealand property, title, ownership and parcel data from the
[LINZ Data Service (LDS)](https://data.linz.govt.nz/) via its Web Feature
Service (WFS) API.

## Overview

This integration queries LDS layers over WFS and exposes typed actions plus a
generic escape hatch:

| Action | What it does |
|--------|--------------|
| `find_multi_property_owners` | **Headline use case.** Finds owners who appear on more than one property title within a scoping filter. |
| `search_property_titles` | Search titles (with owners) by owner name, title number, district or status. |
| `get_title_owners` | Look up the owners and details of a single title by title number. |
| `search_parcels` | Search primary parcels by appellation, title, intent or district. |
| `query_layer` | Run a raw WFS query against any LDS layer or table. |

Layers used:

- `layer-50805` — **NZ Property Titles Including Owners** (licensed personal data; owner names)
- `layer-50772` — NZ Primary Parcels

## Use case: owners of multiple properties

`find_multi_property_owners` scans `layer-50805` within a **scoping filter**
(an `owner_name` such as a surname, and/or a `land_district`), splits the
concatenated `owners` field into individual owners, and aggregates **distinct
titles per owner**. It returns owners holding at least `min_properties` (default
2) titles, sorted by count, with each owner's titles and descriptors.

A scoping filter is **required** — the layer is national and cannot be scanned
in full. Use `max_titles_scanned` (default 2000, max 10000) to bound the scan;
when the result is `truncated`, narrow the filter or raise the cap.

### ⚠️ Commercial vs residential is not available from LINZ

LINZ title/ownership data does **not** classify a property as commercial or
residential. That distinction comes from council / Quotable Value (QV) **rating**
data, which is not part of LINZ. This integration surfaces the descriptors LINZ
does have — `estate_description` on titles, and `appellation` / `parcel_intent`
(tenure type, e.g. *Fee Simple*, *Road*) on parcels — so a downstream agent can
make an informed inference, but it cannot definitively label a property's use
type. To get true commercial/residential classification you would need to add a
council/QV rating data source.

## Authentication

This integration uses a **per-user LINZ Data Service API key** (custom auth).

1. Sign in (or register) at [data.linz.govt.nz](https://data.linz.govt.nz/).
2. Create an API key at <https://data.linz.govt.nz/my/api/>.
3. To read ownership data (`layer-50805`), your LINZ account must accept the
   **LINZ Licence for Personal Data**, and the key must have access to that
   layer. Without it LINZ omits the layer from your key's capabilities and a
   request fails with a `400` "Feature type ... unknown" error — the
   integration maps this to a clear licence hint.

The key is interpolated into the WFS service path:

```
https://data.linz.govt.nz/services;key=<API_KEY>/wfs
```

A per-user key is the correct model because ownership data is licensed personal
data tied to the individual's licence acceptance and Privacy Act 2020
obligations.

## Filtering notes

- Text filters use CQL. The typed actions build `ILIKE` (case-insensitive)
  substring matches for names/appellations and exact `=` matches for districts
  and statuses.
- For `query_layer`, you write raw CQL. **CQL is case-sensitive** for both
  attribute names and values — use `ILIKE` for case-insensitive text matching.
- Geometry is omitted from results by default to save tokens; pass
  `include_geometry: true` on `search_parcels` / `query_layer` to include it.

## Limitations

- The `owners` field is a concatenated string; owner aggregation is best-effort
  string matching (an owner whose stored name contains a comma cannot be
  distinguished from a separator, and there is no normalised owner ID over WFS).
- No commercial/residential classification (see above).
- Scans are bounded by `max_titles_scanned`; very broad filters may truncate.

## Testing

Unit tests (mocked WFS, no network):

```bash
python -m pytest linz/tests/test_linz_unit.py -q
```

Integration tests (real LINZ API — all read-only, no destructive tests). They
require `LINZ_API_KEY`; ownership-layer tests skip automatically when the key
lacks the Personal Data Licence:

```bash
LINZ_API_KEY=... pytest linz/tests/test_linz_integration.py -m "integration and not destructive"
```

Optional env vars: `LINZ_TEST_TITLE_NO` (exercise `get_title_owners` on a known
title) and `LINZ_TEST_LAND_DISTRICT` (scope, defaults to `Otago`).
