# Lusha

Connect Autohive workflows to Lusha's v3 API to find business contacts and target companies, reveal contact details and firmographics, and monitor credit usage. Supports one record or batches of up to 100 records through the same actions.

## Authentication

1. Generate an API key in the [Lusha API dashboard](https://dashboard.lusha.com/api/manage-api-keys).
2. Ensure your user has API access enabled by your account administrator and sufficient credits for the selected actions.
3. Enter the key in the integration's **API Key** field in Autohive.

The integration uses custom authentication and sends the key in the `api_key` header. No OAuth scopes or additional credentials are required. Local SDK callers must pass the platform envelope:

```python
auth = {"auth_type": "Custom", "credentials": {"api_key": api_key}}
```

Do not put credentials in action inputs. Secrets belong in your connected account or local, uncommitted `.env`.

## Actions

| Action | Required inputs | Behavior |
| --- | --- | --- |
| `search_contacts` | `contacts` | Find previews using identifiers; returns IDs, data availability and reveal costs. |
| `enrich_contacts` | `ids` | Reveal emails and/or phones for known Lusha contact IDs. |
| `search_and_enrich_contacts` | `contacts` | Find and reveal contact profiles in one request. |
| `search_companies` | `companies` | Find company previews by identifier. |
| `enrich_companies` | `ids` | Reveal firmographics and optional premium fields for company IDs. |
| `search_and_enrich_companies` | `companies` | Find and enrich company profiles in one request. |
| `prospect_contacts` | `filters` | Get one page of contact previews matching contact and/or company ICP filters. |
| `prospect_companies` | `filters` | Get one page of company previews matching company ICP filters. |
| `list_filter_types` | `entity` | Discover filter types and their `requiresQuery` flags. |
| `get_filter_values` | `entity`, `filter_type` | Retrieve accepted values for a discovered filter. |
| `get_account_usage` | None | Get credit balance, account limits, plan information and per-action pricing. |
| `get_contact_enrichment_job` | `job_id` | Retrieve one snapshot of an asynchronous contact waterfall job. |

Action names use snake_case. Batch records, filter objects, options and response fields use Lusha's documented camelCase names. Inputs are validated against `config.json`; unsupported fields are rejected rather than silently ignored.

### Look up and enrich known records

`contacts` contains 1-100 objects. Each requires one of:

- `id`: a Lusha contact ID from an earlier search/prospecting result.
- `email` or `linkedinUrl`.
- `firstName` and `lastName`, plus `companyName` or `companyDomain`.

`companies` contains 1-100 objects, each with `id`, `name` or `domain`. Both record types accept an optional `clientReferenceId` to correlate batch results. Missing identifier combinations are rejected before a request is sent.

```json
{
  "contacts": [
    {"email": "person@example.com", "clientReferenceId": "crm-contact-1"},
    {"firstName": "Alex", "lastName": "Example", "companyDomain": "example.com"}
  ]
}
```

Search actions accept `options.includePartialProfiles`. Search returns previews, not revealed email addresses or phone numbers. Pass selected result IDs to an enrich action, or use a search-and-enrich action with the same identifiers.

```json
{
  "ids": ["contact-id-from-search"],
  "reveal": ["emails"],
  "waterfallEnabled": false
}
```

Contact `reveal` accepts `emails`, `phones`, or both. Omitting it uses Lusha's default of both. `waterfallEnabled` is supported only by `enrich_contacts`: `false` restricts the call to Lusha data. When omitted, Lusha follows your account's Data Waterfall settings. Search-and-enrich contacts also follows account waterfall settings, but does not accept this flag or return a polling job.

Company `reveal` optionally requests `employeesByDepartment`, `employeesByLocation`, `employeesBySeniority`, `competitors`, `estimatedAnnualItSpend`, `monthlyWebsiteTraffic`, `openJobsTotal`, `openJobsByDepartment`, `openJobsByLocation`, `openJobsBySeniority`, `directParent` or `ultimateParent`. Each premium field can incur an additional charge; omitting `reveal` returns base firmographics.

### Prospect for new contacts and companies

First call `list_filter_types` with `entity: "contacts"` or `"companies"`, then `get_filter_values` with the same entity and a returned `filter_type`. Supply `query` when `requiresQuery` is true. Locations, company names and technologies require a search term of 2-256 characters. Values and their shapes vary by filter; the integration preserves the provider response.

Both prospecting actions accept `page` (zero-based, 0-1000, default 0), `size` (10-100, default 25), and `options.includePartialProfiles`.

At least one include or exclude criterion must contain a value. Empty groups, empty lists, empty location/range objects, and `technologiesCondition` alone are rejected before making a credit-consuming request. A numeric range boundary of zero remains valid.

Contact prospecting accepts `filters.contacts` and/or `filters.companies`, each with `include` and `exclude` objects. Contact fields include `names`, `ids`, `jobTitles`, `countries`, `locations`, `seniorityIds`, `departments` and `existingDataPoints`. Use the filter lookup actions for Lusha's accepted IDs and values.

```json
{
  "filters": {
    "contacts": {"include": {"departments": ["Sales"]}},
    "companies": {"include": {"sizes": [{"min": 51, "max": 500}]}}
  },
  "page": 0,
  "size": 25,
  "options": {"includePartialProfiles": true, "maxContactsPerCompany": 2}
}
```

`excludeDnc` and `maxContactsPerCompany` (1-20) are contact-only options. Live testing found that the account rejected `excludeDnc: true` with HTTP 403 while the same request without it succeeded. Its availability should be checked with Lusha support; the integration never removes it automatically. Omit it only if the resulting DNC behavior is suitable for your workflow. The latter limits contacts per company, independently of page size.

Company prospecting requires `filters.companies.include`; `exclude` is optional:

```json
{
  "filters": {
    "companies": {
      "include": {"domains": ["example.com"], "sizes": [{"min": 51, "max": 500}]}
    }
  },
  "page": 0,
  "size": 25
}
```

Company filters supported in both prospecting actions include `names`, `domains`, `ids`, `locations`, `sizes`, `revenues`, `technologies`, `technologiesCondition` (`or`/`and`), `mainIndustriesIds`, `subIndustriesIds`, `sicCodes`, `naicsCodes`, `businessModel`, `companyType`, `linkedinUrls`, `keywords` and `foundedYear`. Location entries accept the fields declared in `config.json`; ranges use `min`/`max`. This release deliberately exposes common ICP filters rather than every advanced provider filter.

Each call fetches exactly one page. The response may report the actual returned `pagination.size`, which can be smaller than the requested size (for example, one matching company for a request capped at ten). Use returned `pagination.page`, `size`, `total` and, when present, `totalGuaranteed`/`totalDescription` to decide whether another page is needed. A non-guaranteed total is not an exact count. Enrich only the chosen IDs to control credit spending.

### Responses, credits and partial failures

Search, enrichment and prospecting actions return Lusha's response object directly, including `requestId`, `results`, `billing` and optional pagination, availability, status and job fields. Records retain their nested data, `clientReferenceId`, `has`, `canReveal`, and individual `error` objects when returned. An HTTP-successful batch can contain failed records; inspect each result before continuing a workflow.

Search/prospecting and enrichment can spend Lusha credits. Search-and-enrich can incur both search and reveal charges. `billing.creditsCharged` records provider credits, not USD; users must maintain sufficient credits in their own Lusha account. These credits are returned in action data and are **not included in Autohive execution-cost tracking**. This integration does not claim a USD cost or enable Autohive billing because provider credit pricing is account-dependent; enabling USD reporting requires an agreed, reliable conversion. Use `get_account_usage` to inspect current plan pricing and balances rather than assuming fixed prices.

`list_filter_types` returns `availableFilters` and optional catalog metadata. `get_filter_values` returns provider `values`, with optional `total` and `truncated`. `get_account_usage` returns `credits`, `rateLimits`, `plan` and `pricing` when provided by Lusha.

### Account restrictions and incomplete enrichment

A successful HTTP response does not guarantee every requested email or phone was returned. `WATERFALL_NOT_IN_PLAN` identifies a plan restriction; the integration preserves the partial response and adds `warnings` explaining the limitation. Live testing found a combined search-and-enrich request missing an email that standalone enrichment returned. The combined endpoint does not accept `waterfallEnabled`; use `search_contacts` and then `enrich_contacts` with `waterfallEnabled: false` when you need Lusha-only data. This is an explicit workflow choice, not an automatic fallback that could spend more credits. It does not guarantee that Lusha has every requested field.

`COMPLIANCE_RESTRICTED` is a provider restriction on an individual contact, not evidence that the whole action is broken. Preserve the per-record error and do not retry it through another endpoint to bypass the restriction. A different permitted test contact can be used for further validation.

The enrichment-job action remains unverified against a live account: the tested plan has no Waterfall entitlement and returned no job ID. Never invent a job ID or treat absence of a job as a pending result.

### Delayed contact waterfall results

If `enrich_contacts` returns `job`, keep the initial results and wait `job.retryAfter` seconds before calling `get_contact_enrichment_job` with its `id` as `job_id`:

- `processing`: wait the returned `retryAfter` before the next call.
- `complete`: merge returned `contacts` by `id` into the original results. The job only includes contacts it covered, not the entire original batch.
- `expired` or `failed`: stop polling and retain the original results. `reason` may explain failure.
- HTTP 404: stop polling; the job is missing, expired or belongs to another account.
- HTTP 503: retry later; it does not mean the job disappeared.

The action does not sleep, poll in a loop or merge records automatically. Polling itself is free; final `creditsCharged` reports only the async phase, separately from the initial response's `billing.creditsCharged`.

## Limits and errors

Lusha documents a default limit of 25 requests/second, shared at account level, and a stricter five requests/minute for usage checks. Your account's hourly/daily quotas also apply. Avoid checking usage before every action.

HTTP failures return `ActionError` with guidance for invalid inputs (400), authentication (401), insufficient credits (402), plan/permission restrictions (403), missing resources (404), rate limits (429) and unavailable services (503). Rate-limit errors include the SDK's retry-after delay. Automatic network retries are disabled for credit-consuming POST requests. If a connection fails or times out, the outcome is uncertain: Lusha may have processed the request and charged credits. Check your account usage and results before retrying manually, as another request may incur additional charges. Read-only GET requests retain the SDK's standard network-error retries. Raw HTTP error bodies are not included in user-facing action errors.

This release covers discovery and enrichment workflows. Tables, webhook management, recommendations, conversations, lookalikes, dedicated signal retrieval, and legacy v2 endpoints are outside its scope.

## Development and tests

Requires Python 3.13+ and keeps `autohive-integrations-sdk~=2.0.1`. Install HiveUp using the [contributor setup](../CONTRIBUTING.md#local-validation), then run from the repository root. Fetch the actual PR target ref first; the example assumes a PR targeting `master`:

```powershell
hiveup test lusha
hiveup validate --base-ref origin/master lusha
```

Unit tests mock `context.fetch` using SDK `FetchResponse` objects and cover every action, request payloads, authentication, validation boundaries, error handling, pagination, partial batches and waterfall states.

For live tests, [prepare a separate environment](../CONTRIBUTING.md#running-integration-tests) with `requirements-test.txt` and `lusha/requirements.txt`. They use the real SDK HTTP client and cover all 12 actions across five files:

| File | Actions |
| --- | --- |
| `tests/test_lusha_integration.py` | Account usage and enrichment job status |
| `tests/test_lusha_contacts_integration.py` | Contact search, enrichment, and combined search/enrichment |
| `tests/test_lusha_companies_integration.py` | Company search, enrichment, and combined search/enrichment |
| `tests/test_lusha_prospecting_integration.py` | Both prospecting actions, plus a separate optional DNC-filter check |
| `tests/test_lusha_filters_integration.py` | Filter type discovery and value lookup for both entity types |

Set `LUSHA_API_KEY` in local `.env` to run account and filter checks. Explicitly set `LUSHA_RUN_PAID_TESTS=1` to authorize credit-consuming tests, and provide `LUSHA_TEST_COMPANY_DOMAIN`. Contact tests require `LUSHA_TEST_CONTACT_ID` or `LUSHA_TEST_CONTACT_EMAIL` for a permitted dedicated-test contact with a known available work email. Standalone contact enrichment always searches the supplied identifier first, then passes the returned ID to enrichment. No contact fixtures are hardcoded into the public repository.

`LUSHA_TEST_ENRICHMENT_JOB_ID` must be a real, unexpired job from the same account. Job tests skip when it is absent. Compliance-restricted contacts, unsupported DNC access, and a combined enrichment result blocked by `WATERFALL_NOT_IN_PLAN` are reported as explicit skips, not successful live verification. Missing emails without that known plan restriction fail the corresponding test.

All variables have blank templates in root `.env.example`. The suite collects 15 live cases, including entity variants; default unit-test runs do not collect them. Both prospecting cases now execute filter discovery, fetch valid values, and pass those values into the bounded prospecting request. Contact prospecting uses discovered seniority IDs; company prospecting uses discovered employee-count ranges. The company enrichment case always chains search to enrichment; the contact case also always chains search to enrichment, whether the supplied identifier is an ID or email.

```powershell
python -m pytest lusha/tests -o python_files=test_*_integration.py -m "integration and not destructive" -v
```

When all fixtures are supplied, a full run makes eleven paid POSTs, plus the free/read-only lookups and job check. Each prospecting request is capped at ten results. Search/enrichment uses one record per request, requests contact emails only, and does not request company premium reveal fields. Actual credit charges depend on the account and returned data.

TeamCity reads `tests/teamcity.env`, not local `.env`. The committed `LUSHA_API_KEY=ah:customAuth:api_key` marker resolves the dedicated test connection for **Lusha API Key**; the actual key stays outside Git. The file enables paid tests against the public `lusha.com` domain. Before running the suite there, connect the dedicated test account and configure a permitted test-contact ID (or provision the email securely with `ah:secret`). The commented job ID is optional and needs a Waterfall-entitled account. Until those fixtures exist, the corresponding scenarios remain skipped or blocked; adding tests cannot supply a missing plan entitlement.

No live API success is claimed until these tests pass with a real account. Mocked fixtures use synthetic records and placeholder credentials.

## References

- [Official API reference and OpenAPI specification](https://docs.lusha.com/openapi.json)
- [Authentication](https://docs.lusha.com/authentication)
- [Search and enrichment](https://docs.lusha.com/enrichment/overview)
- [Contact prospecting](https://docs.lusha.com/prospecting/search-contacts)
- [Company prospecting](https://docs.lusha.com/prospecting/search-companies)
- [Contact filter values](https://docs.lusha.com/filters/contact-filters)
- [Company filter values](https://docs.lusha.com/filters/company-filters)
- [Rate limits](https://docs.lusha.com/rate-limiting)
- [Error reference](https://docs.lusha.com/error-codes)

API contracts checked against Lusha's published v3 documentation and OpenAPI specification on 17 November 2026. The icon is Lusha's [official documentation favicon](https://docs.lusha.com/mintlify-assets/_mintlify/favicons/lusha-14097d0b/bbZyyWQ78WmZY57w/_generated/favicon/android-chrome-192x192.png), resized to the repository's required 512 by 512 pixels.
