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
| `list_matched_projects` | Required `company_id`; optional `created_since` (RFC 3339 with offset), `cursor`, `limit` (1–100, default 25), `include_tenders` (default false) | `company_id`, compact `projects`, `returned_count`, `total_matching`, `next_cursor`, `has_next_page`, `truncated`, `message` |

Project summaries contain labelled `id`, `name`, `status`, `category`, `address`, `created_at`,
`budget` bounds, and `tender_count`. Missing values are null, never invented zeroes.
`include_tenders=true` adds compact tender IDs, names, types, builder names, and quote deadlines.
Tender bodies, matched keywords, consultants, subcontractors, URLs, and unrelated provider fields are omitted.
`total_matching` is always null because the provider does not report an account-wide total.
`returned_count` counts only this page. `truncated` means more provider pages remain; it never means
part of a record was silently removed. Results exceeding 32 KiB return `ActionError` rather than a partial page.
Retry with a smaller limit or disable tender details. Empty pages include a filter/keyword hint.
Call once per page, passing `next_cursor` as `cursor` until `has_next_page` is false.
Do not use `created_since` as an update cursor: it filters project creation, not tender additions or
changes to existing projects. Perform periodic full reads and reconcile by project/tender IDs downstream.

## Limits and errors

- Production is the only partner environment. E1 supplies test company IDs during onboarding.
- The published rate limit is 100 requests per five minutes per bearer-token/client-ID bucket across API paths.
- Data changes over hours. Prefer hourly/daily polling and cache results downstream.
- 429 has no `Retry-After`; schedule a later attempt with exponential backoff. The action returns
  `ActionError` naming `list_matched_projects` and a conservative 300-second wait rather than retrying indefinitely.
- 401 may mean invalid scope, unpublished permission, or an unregistered company; a single token retry
  does not fix those access problems. Contact E1 onboarding if it persists.
- 400 usually indicates malformed input or a missing client-ID header.
- Empty results may be legitimate: matches depend on the supplier account's configured keywords.

## Error recovery

Expected HTTP, transport, authentication-shape, and malformed/incomplete response failures return
`ActionError` with the action name and a concrete next step. Provider HTTP bodies are retained as
bounded diagnostics after credential and HTML removal. A repeated/non-advancing next cursor fails
instead of trapping an agent in a pagination loop. Invalid `created_since` timestamps fail before
credential exchange. All supported actions are reads, so retry guidance does not risk duplicate writes.
A 401/403 may require the user to restore connection access, company registration, or supplier licence.

## Version history

### 2.0.0

Breaking output change applying the supplied **Building Agent-Friendly Integrations** skill:
raw E1 project/tender payloads are replaced by compact typed summaries, with `projectId` becoming
`projects[].id` and `projectName` becoming `projects[].name`. Budget absence is represented by null bounds.
Existing workflows that read raw provider fields must update those paths; tender details now require
`include_tenders=true`. Existing input names are preserved. Pagination retains `next_cursor` and
`has_next_page`, adding the echoed company ID, returned count, unknown total, continuation flag, and message.
Failures now return actionable `ActionError` instead of unhandled provider exceptions.
No other integration or action was changed.

### 1.0.0

Initial paginated Supplier API integration with provider-shaped project objects.

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
