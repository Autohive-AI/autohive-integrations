# GUIDEcx

[GUIDEcx](https://www.guidecx.com/) is a customer onboarding and implementation platform. Onboarding work is
organised as projects, which contain phases, milestones and tasks, and each project belongs to a customer.

This integration covers onboarding reporting (projects, phases, milestones, tasks), building project structure,
the project team, time tracking, task dependencies, and webhook subscriptions so workflows can react to GUIDEcx
events instead of polling.

## Authentication

The integration uses a single bearer token supplied by the user (auth type `custom`, field `api_token`).

1. Sign in to GUIDEcx as a **workspace admin**. Token creation is admin-gated; Manager and Member roles cannot
   generate one.
2. Go to **Company Settings -> Open API**.
3. Generate a **User-Based Token**. Copy it immediately, it is shown only once.
4. Paste it into the API Token field when connecting the integration in Autohive.

Two token types exist in GUIDEcx. Legacy **Workspace Tokens** are deprecated and only work against API v2; this
integration targets v3 and requires a **User-Based Token**. A token that works in v2 but returns 401 here is
almost always a legacy workspace token.

The token inherits the permissions of the user who owns it, so it can only see the projects that user can see.
Notes posted through `add_task_note` are attributed to that same user.

## Actions

| Action | Description | Key inputs | Key outputs |
|---|---|---|---|
| `list_projects` | Search onboarding projects with optional filters | `status_category`, `customer_id`, `project_manager_id`, `tag`, `updated_after`, `limit`, `offset` | `projects`, `total`, `has_more` |
| `get_project` | Retrieve one project by ID | `project_id` | `project` |
| `list_milestones` | List a project's milestones in display order | `project_id`, `phase_id` | `milestones`, `total`, `has_more` |
| `list_tasks` | Search tasks with optional filters | `project_id`, `milestone_id`, `assignee_id`, `status_category`, `name`, `type_filter` | `tasks`, `total`, `has_more` |
| `update_task` | Update a task's status, due date, assignee or priority | `project_id`, `task_id`, `status`, `end_date`, `assignee_id`, `priority` | `task` |
| `add_task_note` | Post a note to a task's message channel | `task_id`, `content`, `internal_only` | `messages` |
| `get_customer` | Retrieve a customer by ID | `customer_id` | `customer` |
| `list_phases` | List a project's phases in display order | `project_id` | `phases`, `total`, `has_more` |
| `list_project_members` | List the members assigned to a project, with project role | `project_id`, `email`, `project_role` | `members`, `total`, `has_more` |
| `remove_project_member` | Unassign a member from a project's team | `project_id`, `member_id` | `removed`, `member_id` |
| `list_members` | Search workspace members | `email`, `role`, `status` | `members`, `total`, `has_more` |
| `list_roles` | List configured roles | `name` | `roles`, `total`, `has_more` |
| `list_webhooks` | List webhook subscriptions with delivery history | `include_disabled` | `webhooks`, `total`, `has_more` |
| `upsert_webhook` | Create or update a webhook subscription | `event_type`, `url`, `description`, `webhook_id` | `webhook` |
| `delete_webhook` | Delete a webhook subscription | `webhook_id` | `deleted`, `webhook_id` |
| `list_time_categories` | List time categories and billable rates | — | `time_categories`, `total`, `has_more` |
| `list_time_records` | Search logged time | `project_id`, `task_id`, `member_id`, `time_category_id`, `worked_after`, `worked_before` | `time_records`, `total`, `has_more` |
| `log_task_time` | Log hours against a task | `task_id`, `member_id`, `hours_worked`, `date_of_work`, `comment`, `time_category_id` | `time_record` |
| `log_project_time` | Log hours against a project | `project_id`, `member_id`, `hours_worked`, `date_of_work`, `comment`, `time_category_id` | `time_record` |
| `create_project` | Create a project, optionally with an inline customer and a project manager | `name`, `template_id`, `customer_id`, `customer_name`, `customer_domain`, `project_manager_id`, `start_date`, `end_date`, `status`, `tags`, `cash_value` | `project`, `customer_id` |
| `update_project` | Update a project's name, dates, status, tags or contract value | `project_id`, `name`, `start_date`, `end_date`, `status`, `status_explanation`, `tags`, `cash_value` | `project` |
| `create_phase` | Create a phase in a project | `project_id`, `name`, `template_id`, `description`, `placement` | `phase` |
| `create_milestone` | Create a milestone inside a phase | `project_id`, `phase_id`, `name`, `template_id`, `description`, `placement` | `milestone` |
| `create_task` | Create a task under a milestone | `project_id`, `milestone_id`, `name`, `description`, `start_date`, `end_date`, `assignee_id`, `priority`, `responsibility`, `visibility`, `estimated_hours`, `tags`, `placement` | `task` |
| `list_dependencies` | List task dependencies (no pagination) | `project_id`, `parent_id`, `dependent_id` | `dependencies`, `count` |
| `add_dependency` | Make one task depend on another | `parent_id`, `dependent_id` | `dependency` |
| `remove_dependency` | Remove a dependency between two tasks | `parent_id`, `dependent_id` | `removed`, `parent_id`, `dependent_id` |

### Status values

GUIDEcx has two parallel notions of status, and the difference matters when writing filters.

- **`status`** is a workspace-configurable label, for example `Kickoff` or `Awaiting Customer`. Labels differ
  between workspaces, so filtering on them is not portable.
- **`status_category`** is a fixed set that every status label maps to. Prefer it for filtering.
  - Projects: `PENDING`, `IN_PROGRESS`, `DONE`, `LATE`, `CANCELLED`, `ON_HOLD`
  - Tasks: `NOT_STARTED`, `IN_PROGRESS`, `STUCK`, `SIGN_OFF`, `DONE`, `NOT_APPLICABLE`

`update_task` sets `status`, not `status_category`: GUIDEcx derives the category from the label. The label passed
in must be one that exists in the target workspace, and an unknown label is rejected with a clear error
(`these statuses are not valid: [Completed]`) rather than being silently ignored.

In a default workspace the task labels are the title-case form of the categories, verified against a live
workspace:

| Label | Resulting category |
|---|---|
| `Not Started` | `NOT_STARTED` |
| `In Progress` | `IN_PROGRESS` |
| `Stuck` | `STUCK` |
| `Sign Off` | `SIGN_OFF` |
| `Done` | `DONE` |
| `Not Applicable` | `NOT_APPLICABLE` |

`Completed`, `Complete`, `On Hold`, `Blocked` and `Waiting` are **not** valid task labels. Workspaces can rename
these, so read a task via `list_tasks` to see the labels actually in use before hard-coding one.



### Project structure

GUIDEcx nests work three levels deep, and the create actions must be used in that order:

```
project -> phase -> milestone -> task (-> subtask)
```

A task cannot hang directly off a project. `create_task` takes `milestone_id` and sends it as the API's
`parentId`; omitting it fails with `task [0] has an invalid parentId: ""`. So seeding a project from scratch means
`create_project`, then `create_phase`, then `create_milestone`, then `create_task`. Passing a `template_id` to
`create_project` scaffolds the whole tree instead, which is far less work when a suitable template exists.

Creating a project also creates one phase automatically, so `list_phases` on a new project returns one entry
before you add any.

`create_phase`, `create_milestone` and `create_task` accept `placement` (`at_start` or `at_end`, default
`at_end`) to control ordering within the parent. The API also supports positional insertion, which is not exposed
because it requires `sortOrder` values the caller would have to look up first.

### Updating projects

GUIDEcx has no dedicated project-update endpoint. `PATCH /api/v3/projects` is a batch **upsert**: the spec states
that if a project with the given ID exists it is updated, and otherwise a new project is created. A typo or a
stale `project_id` would therefore silently create a duplicate project rather than fail, and v3 has no project
deletion endpoint to undo it.

`update_project` guards against this by looking the ID up first and returning an error unless it matches an
existing project exactly. That costs one extra read per update.

### Webhook event types

`upsert_webhook` restricts `event_type` to the values below. The OpenAPI spec declares this field as a free-form
string and its two examples contradict each other (`task.updated` in the request, `TASK_UPDATED_EVENT` in the
response), so the accepted set was determined empirically against a live workspace. Only lowercase dotted names
are accepted; anything else is rejected with `invalid event types: [...]`.

`project.created`, `project.updated`, `project.deleted`, `task.created`, `task.updated`, `task.deleted`,
`milestone.created`, `milestone.updated`, `milestone.deleted`, `phase.deleted`, `member.created`,
`member.updated`, `message.created`, `message.updated`

Notably absent, and confirmed rejected: `project.completed`, `task.completed`, `milestone.completed`,
`phase.created`, `phase.updated`, `customer.created`, `customer.updated`, `member.deleted`,
`time_record.created`, and any `*.status_changed` form. To react to a completion, subscribe to
`task.updated` or `project.updated` and check `statusCategory` in the payload.

### Pagination

Every list action takes `limit` (default 50, capped at 500) and `offset`, and returns `total`, `limit`, `offset`
and `has_more`. `total` is the count of all records matching the filters, not the size of the current page, so
`has_more` is exact. Page through by increasing `offset` until `has_more` is false.

The 500 cap is the server's, verified against the live API: a larger `limit` is accepted but silently clamped
(`limit=1000` returns `metadata.limit=500`), so the schema rejects anything above it rather than letting a
caller believe they received a full result set.

## API information

- Base URL: `https://api.guidecx.com/api/v3`
- API docs: <https://api.guidecx.com/docs/>
- OpenAPI spec: <https://api.guidecx.com/api/v3/swagger.json>
- Auth header: `Authorization: Bearer <token>`
- Rate limits: `X-RateLimit-Limit` reports **500** requests per window, with `X-RateLimit-Remaining` and
  `X-RateLimit-Reset` alongside it. Exhausting the quota returns `429` with a `Retry-After` header.

### Provider behaviour worth knowing

- **There is no `GET /projects/{id}`.** The v3 API only offers a search endpoint with a repeatable `id` filter, so
  `get_project` performs a single-ID search and unwraps the one result. A missing project comes back as an empty
  list, which the action converts into an error rather than an empty success.
- **Task updates go through a project-scoped batch upsert** (`PATCH /projects/{projectId}/tasks`). This is why
  `update_task` requires `project_id` as well as `task_id`. Fields omitted from the request are left unchanged —
  verified against a live workspace by sending a priority-only update and confirming `name`, `status`,
  `responsibility`, `visibility` and `tags` were all preserved. Despite the endpoint being named "upsert", it does
  not behave as a full replace.
- **Projects created in the classic UI are invisible to the v3 API.** A project created through the classic
  interface returned `total: 0` from `GET /projects`, even when queried by its exact ID, while remaining visible in
  the UI to the same admin user. The same workspace returned members and roles normally. Projects created through
  the GUIDE 2.0 interface appear immediately. If a project is missing from `list_projects` but present in the UI,
  check which interface created it before suspecting the integration.
- **Tasks cannot exist directly under a project.** The hierarchy is phase → milestone → task, and creating a task
  requires `parentId` set to a milestone ID; omitting it fails with `task [0] has an invalid parentId: ""`. This
  matters when seeding test data: a bare project has nowhere to put tasks.
- **Null date fields.** Optional dates (`completedDate`, `endDate`, `forecastedEndDate`, ...) come back as `null`
  rather than being omitted, so every optional field in the output schemas accepts null. A schema declaring these
  as plain strings fails the SDK's output validation as soon as a real record is returned.
- **Notes are "messages"** and are created in bulk (`POST /tasks/{taskId}/messages`). `add_task_note` sends a
  one-item batch. There is no delete-message endpoint in v3, so a posted note cannot be removed via the API.
- **Customer IDs come from `_links.customer`, not a `customerId` field.** Projects carry no `customerId`, but a
  project that has a customer returns `_links.customer` as `/api/v3/customers/{customerId}`, so the ID is the last
  path segment. Projects without a customer omit the link entirely. Note the OpenAPI spec's *example* for this
  field shows a project-scoped `/v3/projects/{id}/customer` path, which does not match what the API actually
  returns.
- **There is no dedicated create-customer endpoint**, but a customer can be created inline by passing a
  `customer` object (`name`, `domain`) to the project batch upsert (`PATCH /projects`). That endpoint also creates
  projects. Neither is exposed as an action here — this integration is deliberately read-plus-task-update.
- **Newly created customers have a zero `createdDate`** (`0001-01-01T00:00:00Z`) rather than the creation time.
  Treat these timestamps as unreliable for customers created via the API.

- **Webhooks use snake_case, everything else uses camelCase.** The webhook endpoints take `include_disabled` and
  return `event_type` / `created_at` / `last_success_at`, unlike the rest of the API. The upsert *request* field is
  camelCase `eventType` while the *response* field is snake_case `event_type` — and the response returns
  `event_type` as `null` even when the upsert succeeded, so do not rely on it to confirm what was subscribed.
- **Boolean query parameters must be sent as strings.** The SDK's `fetch` rejects `bool` query values outright
  ("value should be str, int or float"), so `include_disabled` is serialised as `"true"` / `"false"`.
- **Time records cannot be deleted** through the v3 API, and neither can messages. Anything logged or posted in a
  sandbox is permanent.
- **Rate limit is 500 requests** per window, reported in `X-RateLimit-Limit`.

- **Tags are additive, not a replacement set.** Sending `tags: ["b"]` to a project that already has `["a"]` leaves
  it with `["a", "b"]`; duplicates are ignored. The only way to remove tags is to send an empty array, which clears
  all of them. Omitting the key leaves tags untouched. All three behaviours are verified against a live workspace,
  and the distinction matters in code: an empty array must survive request-body construction rather than being
  dropped as an absent value, or clearing tags becomes impossible.
- **Nothing structural can be deleted.** v3 has no delete endpoint for projects, phases, milestones or tasks, so
  anything created via the API is permanent. Dependencies and webhooks are the only removable resources, and
  `remove_project_member` unassigns rather than deletes. Bear this in mind when testing against a sandbox.
- **`remove_dependency` identifies the dependency by both ends as query parameters**, not by a dependency ID in
  the path — there is no dependency ID in the API at all.
- **`/dependencies` does not paginate.** It is the only search endpoint with no `limit`/`offset` and no `metadata`
  block, so `list_dependencies` returns `count` instead of the usual `total` / `has_more`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `401` on every action | The token is a deprecated legacy workspace token (v2 only), or it has been revoked. Generate a User-Based Token under Company Settings -> Open API. |
| Cannot find the Open API settings page | The signed-in user is not a workspace admin. Token generation is admin-only. |
| `403` on a specific project | The token owner does not have access to that project. Token permissions mirror the owning user's. |
| `list_projects` returns fewer results than expected | A `status` filter is being matched against labels from a different workspace. Use `status_category` instead. |
| `update_task` returns "No update fields provided" | None of `status`, `end_date`, `assignee_id` or `priority` was set. At least one is required. |
| `update_task` returns a 4xx about status | The `status` label does not exist in the target workspace. Read a task from `list_tasks` to see the labels in use. |
| `429` responses | Rate limited. Retry after the interval in the `Retry-After` header. |
| `task [0] has an invalid parentId: ""` | `create_task` was given a `milestone_id` that is not a milestone (a project or phase ID will do this). Use `list_milestones` to get a valid one. |
| `create_project` returns no `customer_id` | The project has no customer. Pass `customer_id` or `customer_name`, or accept that `get_customer` is not usable for it. |

## Testing

Unit tests are mocked and safe to run anywhere:

```bash
pytest guidecx/tests/test_guidecx_unit.py
```

Integration tests call the real API and need `GUIDECX_API_TOKEN` set (see the root `.env.example`). Point them at
a sandbox workspace, never production:

```bash
# read-only
pytest guidecx/tests/test_guidecx_integration.py -m "integration and not destructive"

# updates a real task and posts a real note; requires GUIDECX_TEST_TASK_ID
pytest guidecx/tests/test_guidecx_integration.py -m "integration and destructive"
```

The destructive tests clean up where the API allows it: the task tests restore the original priority and status,
and the webhook lifecycle test deletes the webhook it created (pointing it at `example.com`, which RFC 2606
reserves, so a stray delivery goes nowhere). Two cannot clean up after themselves, because v3 has no
delete endpoint for either resource: the note test posts with `internal_only` set to keep the note off the
customer-facing view, and the time-logging tests log 0.01 hours.
