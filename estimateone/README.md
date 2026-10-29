# EstimateOne (E1)

Read supplier Speci-finder matches for lead discovery, opportunity digests, and CRM synchronization.
This integration covers the currently published production Supplier API. E1 does not currently
publish a production Builder API, write operations, or webhooks. It cannot create tenders,
submit quotes, download project documents, or change E1 records.

## Access and authentication

1. Contact support@estimateone.com to onboard Autohive as an API partner. There is no self-service API signup.
2. Obtain customer consent. E1 provisions an application, supplier company registration, assigned user,
   `client_id`, and `client_secret`. Additional companies require E1 registration; changing an input ID
   does not grant access to another supplier account.
3. Enter the client ID and secret in the Autohive connection. Supply the registered numeric company
   account number as `company_id` when running an action.

The integration exchanges credentials at `https://auth.api.estimateone.com/oauth2/token` using OAuth2
client credentials. Every data call supplies a bearer token and `x-e1-client-id`. The sole required
permission is `speci-finder/read`. Tokens expire after one hour; there is no refresh-token flow.
A fresh token is acquired per action execution, retained only in memory, and reacquired once on 401.
There is no process-global token cache shared between customer connections.

## Action

| Action | Inputs | Outputs |
| --- | --- | --- |
| `list_matched_projects` | Required `company_id`; optional `created_since` (RFC 3339 with offset), `cursor`, `limit` (1–100, default 25) | `projects`, `next_cursor`, `has_next_page` |

The project objects preserve E1's response fields, including project details, budgets, matching tenders,
closing dates, matched keywords, consultants, subcontractors, and E1 links when supplied by E1.
Call once per page, passing `next_cursor` as `cursor` until `has_next_page` is false.
Do not use `created_since` as an update cursor: it filters project creation, not tender additions or
changes to existing projects. Perform periodic full reads and reconcile by project/tender IDs downstream.

## Limits and errors

- Production is the only partner environment. E1 supplies test company IDs during onboarding.
- The published rate limit is 100 requests per five minutes per bearer-token/client-ID bucket across API paths.
- Data changes over hours. Prefer hourly/daily polling and cache results downstream.
- 429 has no `Retry-After`; schedule a later attempt with exponential backoff. The action surfaces the
  SDK rate-limit error rather than spinning or retrying indefinitely.
- 401 may mean invalid scope, unpublished permission, or an unregistered company; a single token retry
  does not fix those access problems. Contact E1 onboarding if it persists.
- 400 usually indicates malformed input or a missing client-ID header.
- Empty results may be legitimate: matches depend on the supplier account's configured keywords.

## Testing

`hiveup validate estimateone` and `hiveup test estimateone` run static checks and mocked tests.
For a live read-only smoke test after onboarding:

```bash
export E1_CLIENT_ID=...
export E1_CLIENT_SECRET=...
export E1_COMPANY_ID=...
pytest estimateone/tests/test_estimateone_integration.py -m integration
```

Live calls are skipped without these variables. No live credentials were available during development.

## Official references

- [Overview and supported scope](https://developer.api.estimateone.com/overview.html)
- [Authentication](https://developer.api.estimateone.com/get-started/authentication.html)
- [Authorization](https://developer.api.estimateone.com/get-started/authorization.html)
- [Supplier API](https://developer.api.estimateone.com/reference/supplier-api.html)
- [Environments](https://developer.api.estimateone.com/get-started/environments.html)
- [Rate limits](https://developer.api.estimateone.com/reference/rate-limits.html)

MCP check on 2026-10-29: no published E1 MCP was located in the official developer documentation.
