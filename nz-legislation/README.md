# New Zealand Legislation

Read-only access to the [New Zealand Legislation Data API](https://api.legislation.govt.nz/docs/) operated by the Parliamentary Counsel Office (PCO). Search legislation, inspect a work's version history, retrieve canonical version metadata, and find matching provisions in official XML source documents.

The API uses a three-tier model:

- **Work** — an enduring piece of legislation, such as an Act or Bill.
- **Version** — a consolidation date or Bill stage for a work.
- **Format** — an available HTML, PDF, XML, or original-scan representation of a version.

## Setup and authentication

This integration uses a personal or organisation-specific API key in the `X-Api-Key` request header.

1. Request a key by emailing [contact@pco.govt.nz](mailto:contact@pco.govt.nz).
2. Create an Autohive connection and enter the key in **API key**.

Keep the key confidential. The [API terms of use](https://www.legislation.govt.nz/learn-more/legislation-data/api-terms-of-use/) prohibit sharing a key with another person or organisation.

## Requirements

- Python 3.13 or later
- `autohive-integrations-sdk~=2.0.1`
- `aiohttp~=3.12` for downloading XML documents
- A New Zealand Legislation API key

## Actions

| Action | Purpose |
|---|---|
| `search_legislation` | Search or browse legislation works with the API's complete documented filter set |
| `list_versions` | List a page of versions and formats available for a work |
| `get_version` | Get canonical metadata and format links for one version |
| `get_version_provision` | Retrieve provisions by exact section label or source provision ID |
| `search_version_xml` | Search an official XML source document for matching provisions |

### `search_legislation`

Searches titles or legislative content. If `search_term` is omitted, the action browses using the supplied filters. It returns one page at a time; increment `page` while `has_next_page` is `true`.

**Inputs**

- `search_term` (string, optional) — Query processed using Elasticsearch simple-query-string syntax. Stemming is enabled; wrap a phrase in double quotes to disable stemming for that phrase.
- `search_field` (`title` or `content`, optional) — Field to search.
- `page` (integer, optional, default `1`) — Page number.
- `per_page` (integer, optional, default `20`, maximum `100`) — Page size.
- `legislation_status` (optional) — `in_force`, `not_in_force`, or `no_value`.
- `legislation_type` (optional) — `act`, `amendment_paper`, `bill`, or `secondary_legislation`.
- `act_type`, `act_classification`, `act_status` (optional) — Require `legislation_type=act`.
- `instrument_type_group`, `instrument_status`, `instrument_classification` (optional) — Require `legislation_type=secondary_legislation`.
- `bill_type`, `bill_status` (optional) — Require `legislation_type=bill`.
- `administering_agencies` (string, optional) — Exact agency name from the [agency list](https://www.legislation.govt.nz/browse/agencies).
- `sort_by` (optional) — `title_asc`, `title_desc`, `year_asc`, `year_desc`, or `most_recently_updated`.
- `publisher` (optional) — `Agency` or `Parliamentary Counsel Office`.

**Outputs**

- `works` — Matching works with publishing source, classifications, status, agencies, and `latest_matching_version`.
- `page`, `per_page`, `total`, `has_next_page` — Pagination state.
- `rate_limit` — Advisory snapshot of the daily key quota: limit, remaining requests, and UTC Unix reset timestamp. Concurrent requests may consume quota after the snapshot.

For content searches, `latest_matching_version` means the newest version containing the match. It can be older than the work's newest version. Check `is_latest_version` before treating it as current law.

Example input:

```json
{
  "search_term": "\"New Zealand Bill of Rights Act\"",
  "search_field": "title",
  "legislation_type": "act",
  "per_page": 10
}
```

### `list_versions`

Lists one page of versions exposed for a work. Increment `page` while `has_next_page` is `true`.

The provider's version 0 OpenAPI document currently omits the `page` and `per_page` request parameters for this endpoint, although the live endpoint accepts them and returns matching pagination metadata. The integration validates that the response honours the requested page rather than silently returning duplicate data. This behaviour remains dependent on the provider's beta API.

**Inputs**

- `work_id` (string, required) — Identifier from `search_legislation`, such as `act_public_1990_109`.
- `sort` (`asc` or `desc`, optional, default `desc`) — Version date order.
- `page` (integer, optional, default `1`) — Page number.
- `per_page` (integer, optional, default `20`, maximum `100`) — Page size.

**Outputs**

- `work_id` — Requested work.
- `versions` — Version metadata and available format links.
- `page`, `per_page`, `count`, `total`, `has_next_page` — Pagination state.
- `rate_limit` — Daily quota state.

Example input:

```json
{
  "work_id": "act_public_1990_109",
  "sort": "desc",
  "page": 1,
  "per_page": 20
}
```

### `get_version`

Gets one version's title, identifiers, status, classification, administering agencies, and format links.

**Input**

- `version_id` (string, required) — Identifier from search or version listing, such as `act_public_1990_109_en_2022-08-30`.

**Outputs**

- `version` — Canonical version metadata and available formats.
- `rate_limit` — Daily quota state.

Example input:

```json
{
  "version_id": "act_public_1990_109_en_2022-08-30"
}
```

### `get_version_provision`

Downloads the canonical, date-specific XML source once and returns provisions matching an exact section label or source provision ID. Use this after `search_version_xml` identifies a relevant section or provision. A section label can occur more than once in a document, such as in schedules, so the action returns all exact matches in document order, up to 20. Use `provision_id` when one exact source provision is required.

**Inputs**

- `version_id` (string, required) — Version to retrieve.
- `section` (string, conditionally required) — Exact provision label, such as `35`, `231`, or `30A`.
- `provision_id` (string, conditionally required) — Exact source ID returned by XML search, such as `DLM434650`.

Provide exactly one of `section` or `provision_id`.

**Outputs**

- `version_id`, `source_url` — Requested version and canonical official XML URL.
- `section`, `provision_id` — The exact selector used.
- `provisions` — Matching provisions with source ID, label, heading, normalised text, and truncation state.
- `returned_matches`, `total_matches`, `has_more_matches` — Result counts and whether more than 20 exact matches exist.
- `document_bytes` — Size of the single downloaded XML document.

```json
{
  "version_id": "act_public_1990_109_en_2022-08-30",
  "section": "21"
}
```

### `search_version_xml`

Derives the version's canonical, date-specific XML URL from the documented six-part version identifier, downloads the complete document once with a normal HTTP GET authenticated by `X-Api-Key`, and returns provisions containing the case-insensitive search term. The XML request must return `200 OK`; redirects are not followed.

**Inputs**

- `version_id` (string, required) — Version to search.
- `search_term` (string, required) — Case-insensitive text to find within complete provisions.
- `max_results` (integer, optional, default `10`, range `1`–`20`) — Maximum matching provisions to return.

**Outputs**

- `version_id`, `source_url` — Requested version and its canonical official XML URL.
- `search_term` — The requested term.
- `matches` — Matching provisions in document order, including each provision's source ID, label, heading, normalised text, and whether exceptionally long text was truncated.
- `returned_matches`, `total_matches`, `has_more_matches` — Result counts and whether `max_results` omitted additional matches.
- `document_bytes` — Size of the downloaded XML document.

Each XML action invocation makes one authenticated XML request with no preliminary metadata request. There is no byte-offset continuation or Range request. Documents larger than 25 MiB are rejected rather than buffered without a limit. XML is not available for every record, particularly some agency-published secondary legislation and scan-only historical material.

Example input:

```json
{
  "version_id": "act_public_1990_109_en_2022-08-30",
  "search_term": "unreasonable search or seizure",
  "max_results": 10
}
```

## Provider behaviour and limitations

- The API is currently version 0 (beta), so metadata and query behaviour may change before version 1.
- The API reflects published legislation but is not legal advice. Users are responsible for how they use and represent the data.
- PCO-drafted legislation normally advertises `html`, `pdf`, and `xml` formats. Converted pre-2008 enacted Acts may also advertise `pdf_original_scan`. Agency-drafted secondary legislation varies by record and may provide only HTML or PDF links on an agency website.
- Agency-published secondary-legislation records collected through the pilot service may be incomplete or inaccurate.
- Identifiers containing `~` are ephemeral fallback identifiers and may change when the PCO receives better source data.
- Default daily limit: 10,000 requests per API key, reset at midnight New Zealand time. Higher limits may be arranged with the provider. Successful API responses expose an advisory quota snapshot and the reset as a UTC Unix timestamp; the values are not a quota reservation.
- Burst limit: 2,000 requests per IP address per five minutes. This limit is shared by every request using the same outbound IP address. A burst-limit response is HTTP 403; wait five minutes before retrying.
- The integration does not proactively throttle or automatically retry quota errors. A local limiter could not correctly coordinate the daily key quota or shared-IP limit across concurrent distributed workers.
- The service may be unavailable during maintenance or outages and does not guarantee error-free or complete responses.

## Error handling

- **Invalid API key** — Check the connection key; the provider returns HTTP 401.
- **Daily quota exceeded** — Wait until the quota resets at midnight New Zealand time; the provider returns HTTP 429.
- **Burst limit reached** — Wait five minutes before retrying; the provider returns HTTP 403.
- **Work or version not found** — Re-run search and use the returned identifier. Ephemeral identifiers can change.
- **XML unavailable** — The official website returns not found when the requested version has no XML representation; use the formats from `search_legislation`, `list_versions`, or `get_version` to choose HTML or PDF instead.

## Testing

Install dependencies and run unit tests:

```bash
source .venv/bin/activate
uv pip install -r nz-legislation/requirements.txt
pytest nz-legislation/ -v
```

For live read-only tests, place the key in the repository root `.env`:

```bash
NZ_LEGISLATION_API_KEY=your-key
```

Then run:

```bash
pytest nz-legislation/tests/test_nz_legislation_integration.py -m "integration and not destructive"
```

The integration provides no write actions, so all live tests are non-destructive.

## Official resources

- [Developer API overview](https://www.legislation.govt.nz/learn-more/legislation-data/developer-api/)
- [OpenAPI documentation](https://api.legislation.govt.nz/docs/)
- [API terms of use](https://www.legislation.govt.nz/learn-more/legislation-data/api-terms-of-use/)
- [XML data and schema guide](https://www.legislation.govt.nz/learn-more/legislation-data/xml-data/)
