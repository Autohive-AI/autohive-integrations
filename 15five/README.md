# 15Five Integration for Autohive

Connects Autohive to the [15Five](https://www.15five.com/) Public API for reading performance management data — users, groups, departments, people attributes, objectives (OKRs), check-ins, priorities, pulses, review cycles, and 1-on-1s — and creating High Fives, custom people attributes/values, objectives, and priorities.

## Description

This integration is primarily **read-only**: 39 of its 44 actions retrieve existing 15Five data. The remaining 5 write actions (`create_high_five`, `create_attribute`, `create_attribute_value`, `create_objectives`, `create_priorities`) cover everything 15Five's Public API supports creating — it does not support updating or deleting most resources, or creating check-ins, groups, reviews, or vacations via the API.

## Setup & Authentication

This integration uses **Custom Authentication** with a 15Five API access token and your company's workspace subdomain.

### Required Authentication Fields

- **`subdomain`**: The subdomain of your 15Five workspace, e.g. `acme` for `https://acme.15five.com`.
- **`api_key`**: A 15Five API access token, sent as a Bearer token on every request.

### Setup Steps

1. In 15Five, go to **Settings -> Features -> Integrations -> Public API**.
2. Create a new API key (only company admins can view/manage API keys).
3. Add the 15Five integration in Autohive.
4. Enter your workspace `subdomain` and the `api_key` you generated.

### Rate Limits

15Five enforces a rate limit of 5 requests per second per IP address; exceeding it returns HTTP 429.

## Actions

### Users
- **`list_users`** — List users, filterable by email, employee ID, name, location, active/admin status, and creation/update date ranges.
- **`get_user`** — Retrieve a single user by ID.

### Groups, Group Types & Departments
- **`list_groups`** / **`get_group`** — List/retrieve company groups (teams, custom groups), optionally filtered by name.
- **`list_group_types`** / **`get_group_type`** — List/retrieve group types (e.g. "Departments", "Teams").
- **`list_departments`** / **`get_department`** — List/retrieve company departments.

### Feature Status
- **`get_feature_status`** — Retrieve which optional features (Pulse, demographic attributes) are enabled for the company.

### People Attributes
- **`list_attributes`** / **`get_attribute`** / **`create_attribute`** — List, retrieve, or create custom people attribute definitions (`text` or `date` datatype).
- **`list_attribute_values`** / **`get_attribute_value`** / **`create_attribute_value`** — List, retrieve, or set a value for a people attribute on a user.

### Objectives (OKRs)
- **`list_objectives`** / **`get_objective`** — List/retrieve objectives, filterable by user, parent, department, scope, state, status color, and date ranges. `get_objective` includes nested `key_results`.
- **`create_objectives`** — Create one or more objectives (optionally with nested key results) in a single request.
- **`list_objective_history`** / **`get_objective_history`** — List change history across all objectives, or for a single objective.
- **`list_key_results`** — List the key results belonging to one objective. 15Five has no standalone key-results-list endpoint, so this reads them off the objective's own record.

### High Fives
- **`list_high_fives`** / **`get_high_five`** — List/retrieve High Five recognition posts, filterable by report, receiver, and creation date range.
- **`create_high_five`** — Post a new High Five. `text` should include an `@mention` of the recipient(s) and/or their email(s); `creator_id` is the posting user's ID.

### Check-in Reports, Answers & Questions
- **`list_reports`** / **`get_report`** — List/retrieve check-in reports, filterable by user and due-date range. `get_report` returns the full payload (questions, answers, comments, goals, accomplishments); `list_reports` returns only summary fields.
- **`list_answers`** / **`get_answer`** — List/retrieve individual check-in answers.
- **`list_questions`** / **`get_question`** — List/retrieve check-in question templates.

### Priorities & Pulse
- **`list_priorities`** / **`create_priorities`** — List or create one or more check-in priorities. This 15Five endpoint is **not paginated**.
- **`list_pulses`** / **`get_pulse`** — List/retrieve submitted employee Pulse (engagement) scores. Requires the Pulse feature to be enabled (see `get_feature_status`).

### Review Cycles
- **`list_review_cycles`** / **`get_review_cycle`** — List/retrieve performance review cycles.
- **`list_review_cycle_participants`** — List a cycle's participants.
- **`list_review_cycle_results_answers`** — Retrieve a cycle's submitted questions and answers.
- **`list_review_cycle_results_performance_measurements`** — Retrieve a cycle's calculated performance measurements.
- **`list_reviews`** — List individual reviews (with answers) within a cycle.

### 1-on-1s
- **`list_one_on_ones`** / **`get_one_on_one`** — List/retrieve 1-on-1 meetings, filterable by type, draft status, group, user, and date ranges.

### Vacations & Security Audit
- **`list_vacations`** — List recorded user vacations.
- **`list_security_audit`** — List security audit log events.

All list actions return `{ count, next, previous, <resource>s }`, mirroring 15Five's own page-number pagination — pass `page` to fetch subsequent pages. The `list_priorities` endpoint is an exception: 15Five returns it as a bare, unpaginated array.

## Testing

### Unit Tests

Run mocked unit tests (no network calls, no credentials needed):

```bash
pytest 15five/tests/test_fifteenfive_unit.py -v
```

### Integration Tests

Integration tests call the real 15Five API and require credentials. Set these in your local `.env` (see the repository root `.env.example`):

```bash
FIFTEENFIVE_SUBDOMAIN=
FIFTEENFIVE_API_KEY=
# Optional - only needed for destructive tests (create_high_five, create_attribute_value,
# create_objectives, create_priorities)
FIFTEENFIVE_TEST_CREATOR_ID=
```

Run the read-only tests (safe — this is the default you should use):

```bash
pytest 15five/tests/test_fifteenfive_integration.py -m "integration and not destructive"
```

The write actions create real, company-visible data (a High Five, a people attribute/value, an objective, or a priority), so their tests are marked `destructive` and excluded from the command above. Only run them deliberately, with `FIFTEENFIVE_TEST_CREATOR_ID` set to a real user ID in your test workspace:

```bash
pytest 15five/tests/test_fifteenfive_integration.py -m "integration and destructive"
```

## Notes

- 15Five's Public API is largely read-only. It does not support creating, updating, or deleting check-ins, groups, reviews, or vacations — those must be managed in the 15Five UI. The 5 `create_*` actions above are the only write endpoints it exposes.
- **No `get_vacation` action**: 15Five's API has no "get a single vacation by ID" endpoint — only list, create, update, and delete-by-ID. Use `list_vacations` and filter client-side if you need a specific record.
- `list_priorities` is not paginated — 15Five returns it as a bare array, unlike every other list action in this integration.
- `list_key_results` is a convenience wrapper: it calls `get_objective` under the hood and returns just the `key_results` field, since 15Five has no standalone key-results endpoint.
