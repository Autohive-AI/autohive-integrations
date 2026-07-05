# Freshsales CRM Integration — Design Spec

**Date:** 2026-07-06
**Status:** Approved
**Branch:** `rp/freshsales-integration`

## Goal

Add a new `freshsales/` integration to the autohive-integrations monorepo covering the
Freshsales CRM ([freshworks.com/crm/sales](https://www.freshworks.com/crm/sales/)) core
objects — Contacts, Sales Accounts, Deals — plus productivity objects — Tasks,
Appointments, Notes — with full CRUD, view-based listing, and global search.

It is a **separate integration** from the existing `freshdesk/` one: different Freshworks
product, different API key, different domain, different auth header format. This matches
repo precedent (one integration per product, e.g. the per-product Google integrations).

## API reference (verified official)

- Docs: <https://developers.freshworks.com/crm/api/> — Freshworks' official developer portal.
- Base URL: `https://{bundle_alias}.myfreshworks.com/crm/sales/api`
- Auth: `Authorization: Token token={api_key}` (API key from Personal Settings → API Settings)
- Pagination: `page` param, 25 records per page default; `sort` / `sort_type` on list views
- Rate limit: per-account per-hour, plan-dependent (baseline ~1,000 req/h); HTTP 429 when exceeded
- Cost: Freshsales does not charge per API call — no `cost_usd` billing; `supports_billing` omitted

### The view quirk

Contacts, Sales Accounts, and Deals have **no plain list endpoint**. Listing requires a
view id: `GET /api/contacts/filters` returns available views ("All Contacts" etc.), then
`GET /api/contacts/view/{view_id}` returns records. Tasks and Appointments list normally
via `GET /api/tasks?filter=...`. Notes have no list/get endpoints at all.

## Architecture

Single-file integration mirroring `freshdesk/freshdesk.py` (Approach 1 of 3 considered;
generic entity actions and a multi-module client were rejected as off-pattern for this repo).

```
freshsales/
  config.json          # custom auth + 30 action schemas
  freshsales.py        # all handlers + two module-level helpers
  __init__.py
  requirements.txt     # autohive-integrations-sdk~=2.0.0
  icon.png             # 512×512 Freshsales logo (source from Freshworks public brand assets)
  README.md
  tests/
    __init__.py
    conftest.py                      # SDK 2.x mock_context override (clickup pattern)
    test_freshsales_unit.py
    test_freshsales_integration.py   # live tests, .env-gated, auto-skip without creds
```

Root `README.md` gains a Freshsales row (CI-enforced for new integrations).

### Auth

`config.json` uses `"auth": {"type": "custom"}` with two fields:

- `api_key` — string, `format: password`
- `bundle_alias` — string; the `yourcompany` in `yourcompany.myfreshworks.com`

Module-level helpers (Freshdesk parity):

- `get_auth_headers(context)` → `{"Authorization": f"Token token={api_key}", "Content-Type": "application/json"}`.
  Credentials are read from `context.auth["credentials"]` (platform-wrapped envelope).
- `get_base_url(context)` → `https://{bundle_alias}.myfreshworks.com/crm/sales/api`.
  Normalizes input: strips `https://`, trailing slashes, and a `.myfreshworks.com` suffix
  if the user pastes a full domain instead of the bare alias.

## Actions (30)

| Resource | Actions | Endpoint / notes |
|---|---|---|
| Contacts | `create_contact`, `get_contact`, `update_contact`, `delete_contact`, `list_contacts` | `/api/contacts`; create requires first_name or last_name plus email or mobile_number; `get` supports `include` (owner, sales_accounts, deals, …) |
| Accounts | `create_account`, `get_account`, `update_account`, `delete_account`, `list_accounts` | `/api/sales_accounts`; create requires `name`; action names use "account" for UX |
| Deals | `create_deal`, `get_deal`, `update_deal`, `delete_deal`, `list_deals` | `/api/deals`; create requires `name` + `amount` |
| Tasks | `create_task`, `get_task`, `update_task`, `delete_task`, `list_tasks` | `/api/tasks`; create requires title, due_date, targetable_type, targetable_id; list takes `filter` (open/completed/overdue); update covers mark-as-done |
| Appointments | `create_appointment`, `get_appointment`, `update_appointment`, `delete_appointment`, `list_appointments` | `/api/appointments`; create requires title, from_date, end_date, targetable_type, targetable_id; list takes `filter` |
| Notes | `create_note`, `update_note`, `delete_note` | `/api/notes`; create requires description, targetable_type, targetable_id; API has no get/list |
| Cross | `list_views` (entity enum: contacts/accounts/deals), `search` (q + optional entities) | `/api/{resource}/filters`; `/api/search?q=...&include=...` |

### View auto-resolution

`list_contacts` / `list_accounts` / `list_deals` take an **optional** `view_id`:

- provided → `GET /api/{resource}/view/{view_id}` directly
- omitted → `GET /api/{resource}/filters`, select the "All …" view (fallback: first view),
  then list. Two API calls, zero-config agent UX.

List actions expose `page`, `sort`, `sort_type`, and `include` where the API supports them.

## Handler pattern

One `ActionHandler` class per action registered with `@freshsales.action("name")`.
Body: `try/except` → `ActionResult(data={...})` on success, `ActionError(message=...)` on
failure. Request bodies use Freshsales' entity-wrapped shape (e.g. `{"contact": {...}}`) —
exact per-resource shapes confirmed against the official docs during implementation.
SDK 2.x: `context.fetch(...)` returns `FetchResponse`; read `.data`.

## Error handling

- API errors surface verbatim in `ActionError.message` (including 429 rate-limit responses).
- Required-field validation is declared in `config.json` schemas and enforced by the SDK;
  handlers do not re-validate.
- Optional inputs use `inputs.get(...)` and are only added to request bodies when present.

## Testing

**Unit** (`test_freshsales_unit.py`, runs by default via `pytest freshsales/`):

- Mocked `context.fetch` via local `tests/conftest.py` wrapping returns in
  `SimpleNamespace(data=...)` (clickup pattern).
- Coverage: happy path per action; auth-header and base-URL construction including
  bundle-alias normalization; view auto-resolution (filters → view call sequence);
  error paths; `test_actions_match_handlers` config↔code sync.
- All credentials are obvious fakes; `# nosec` where bandit flags test strings.
  **Public repo: no real keys, domains, or account data anywhere in committed files.**

**Integration** (`test_freshsales_integration.py`, run explicitly with `-m integration`):

- Reads `FRESHSALES_API_KEY` + `FRESHSALES_BUNDLE_ALIAS` from `.env` (gitignored);
  `pytest.skip()` when absent.
- Live create→get→update→delete lifecycles on temp records with cleanup in `finally`;
  read-only list/search/views checks.

**Validation pipeline before push** (tooling repo cloned as sibling):

```bash
python ../autohive-integrations-tooling/scripts/validate_integration.py freshsales
python ../autohive-integrations-tooling/scripts/check_code.py freshsales
pytest freshsales/ -v
ruff check --fix --config ../autohive-integrations-tooling/ruff.toml freshsales
ruff format --config ../autohive-integrations-tooling/ruff.toml freshsales
```

## Process decisions

- Branch: stay on `rp/freshsales-integration` (user's choice; deviates from the
  `<type>/<issue>/<desc>` convention knowingly).
- Create a GitHub issue for PR reference before implementation.
- Conventional commits: `feat(freshsales): ...`; PR title likewise. One integration per PR.
- No force-push.

## Out of scope

Sales Activities, Products (CPQ), Marketing Lists, Phone Calls, bulk_upsert/bulk_destroy,
clone/forget endpoints, webhooks. Can be follow-up PRs if needed.
