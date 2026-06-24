# ProjectWorks

[ProjectWorks](https://www.projectworks.com) is a professional services automation (PSA) platform covering projects, resourcing, timesheets, leave, invoicing, and expenses. This integration provides read access to the core ProjectWorks entities.

## Auth Setup

ProjectWorks uses HTTP Basic authentication with an API account (the Consumer Key/Secret pair — **not** your normal login).

1. Log in to ProjectWorks and go to **Profile icon → Admin → API Accounts**
2. Click **+** to create a new API account, then **Add** to generate it
3. Open **Three Dots → Details** and copy the **Consumer Key** and **Consumer Secret**
4. Paste them into the **Consumer Key** and **Consumer Secret** fields when connecting

> **Note:** The Consumer Secret is shown only once at creation and cannot be retrieved later. If you lose it, create a new API account.

## Actions

### Read

| Action | Description | Key Inputs | Key Outputs |
|---|---|---|---|
| `list_users` | List users/employees | `email`, `name`, `modified_since_date` | `users[]` |
| `get_user` | Get a single user | `user_id` | `user` |
| `list_clients` | List clients/companies | `office_id`, `name`, `modified_since_date` | `clients[]` |
| `get_client` | Get a single client | `client_id` | `client` |
| `list_projects` | List projects | `client_id`, `user_id`, `project_number` | `projects[]` |
| `get_project` | Get a single project | `project_id` | `project` |
| `list_modules` | List project modules | `project_id`, `name` | `modules[]` |
| `get_module` | Get a single module | `module_id` | `module` |
| `list_tasks` | List tasks | `project_id`, `module_id`, `user_id` | `tasks[]` |
| `get_task` | Get a single task | `task_id` | `task` |
| `list_resources` | List resourcing bookings | `project_id`, `user_id`, `start_date`, `end_date` | `resources[]` |
| `get_resource` | Get a single booking | `resource_id` | `resource` |
| `list_timesheets` | List timesheet entries | `user_id`, `task_id`, `date` | `timesheets[]` |
| `list_leaves` | List leave requests | `user_id`, `type_id`, `status_id` | `leaves[]` |
| `get_leave` | Get a single leave request | `leave_id` | `leave` |
| `list_invoices` | List invoices | `client_id`, `project_id`, `status_id` | `invoices[]` |
| `get_invoice` | Get a single invoice | `invoice_id` | `invoice` |
| `list_expense_claims` | List expense claims | `user_id`, `project_id`, `is_billable` | `expense_claims[]` |
| `get_expense_claim` | Get a single expense claim | `expense_claim_id` | `expense_claim` |
| `list_offices` | List offices | `name` | `offices[]` |

All `list_*` actions accept `page` (default 1) and `page_size` (default 100) for pagination. Many also accept `modified_since_date` (ISO 8601) for incremental syncing.

### Write

`create_*` returns the full created record (including its new ID). `update_*` on clients, projects, modules, tasks, and users is a **partial update** (PATCH — send only the fields you want changed); leave and expense-claim updates are **full replacements** (PUT — all required fields must be supplied). `delete_*` returns `{ <id>, deleted: true }`.

| Action | Description | Required Inputs |
|---|---|---|
| `create_client` / `update_client` / `delete_client` | Manage clients | create: `client_name`, `account_manager_id`, `office_id` |
| `create_project` / `update_project` / `delete_project` | Manage projects | create: `project_name`, `office_id`, `client_id`, `project_type_id`, `project_status_id`, `currency_id`, `project_manager_id`, `account_manager_id`, `task_self_service_mode_id` |
| `create_module` / `update_module` / `delete_module` | Manage modules | create: `project_id`, `module_name` |
| `create_task` / `update_task` / `delete_task` | Manage tasks | create: `module_id`, `task_name` |
| `create_user` / `update_user` / `delete_user` | Manage users | create: `email`, `first_name`, `last_name` |
| `create_leave` / `update_leave` / `delete_leave` | Manage leave | create: `user_id`, `status_id`, `days` |
| `create_expense_claim` / `update_expense_claim` / `delete_expense_claim` | Manage expense claims | create: `user_id`, `project_id`, `module_id`, `expense_claim_type_id`, `is_reimbursable`, `is_processed`, `date`, `amount`, `currency_id`, `tax_type_id` |
| `create_timesheet` / `update_timesheet` / `delete_timesheet` | Manage time entries | create: `user_id`, `task_id`, `date`, `minutes` |

#### Sub-resource updates

| Action | Description | Required Inputs |
|---|---|---|
| `update_project_user` | Set a user's rate card / rate on a project | `project_id`, `user_id` |
| `update_task_user` | Create/replace a user's task assignment (hours, rate) | `task_id`, `user_id` |
| `update_task_placeholder` | Create/replace a placeholder (unassigned role) on a task | `task_id` |
| `update_user_roles` | Replace a user's set of role IDs | `user_id`, `user_role_ids` |
| `update_user_leave_balances` | Replace a user's leave balances | `user_id`, `balances` |
| `update_user_postings` | Create an employment posting for a user | `user_id`, `start_date`, `is_billable`, `recoverable`, `rate`, `office_id`, `location_id`, `team_id`, `position_id`, `agreement_type_id`, `currency_id` |
| `set_custom_fields` | Create/update custom-field data on any entity | `entity_type` (`client`/`project`/`module`/`task`/`user`), `entity_id`, `fields` |

> Reference IDs (office, currency, project/task type, status, etc.) come from the corresponding `list_*` actions or your ProjectWorks configuration. Array inputs use the API's field names:
> - `create_leave` → `days`: `[{ "date": ISO8601, "typeID": int, "hours": number }]`
> - `update_user_leave_balances` → `balances`: `[{ "leaveTypeID": int, "balance": number, "unit": "Hours"|"Days" }]`
> - `update_user_postings` → `capacity_days`: `[{ "dayOfWeekID": int, "hours": number }]`
> - `set_custom_fields` → `fields`: `[{ "fieldID": int, "value": str, "multiSelectValues": [str] }]`

## API Info

- **Base URL:** `https://api.projectworksapp.com/api/v1`
- **Docs:** https://api.projectworksapp.com/docs/
- **OpenAPI spec:** https://api.projectworksapp.com/openapi/v1.json
- **Auth:** HTTP Basic — Consumer Key (username) + Consumer Secret (password)
- **Pagination:** `page` / `pageSize`; list endpoints return a bare JSON array
- **Dates:** ISO 8601 date-time (UTC), e.g. `2026-06-24T00:00:00Z`

## Running Tests

```bash
# Unit tests (mocked, no credentials)
pytest projectworks/

# Integration tests — read-only (safe default; set PROJECTWORKS_CONSUMER_KEY/SECRET first)
pytest projectworks/tests/test_projectworks_integration.py -m "integration and not destructive"

# Destructive tests — creates/updates/deletes a real timesheet entry on the connected account
pytest projectworks/tests/test_projectworks_integration.py -m "integration and destructive"
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Invalid Consumer Key/Secret, or using your web login | Use an API account's Consumer Key/Secret from Admin → API Accounts |
| `403 Forbidden` | API account lacks permission for the resource | Check the API account's role/permissions in ProjectWorks |
| Empty result list | Filters too narrow, or beyond the last page | Loosen filters; page until a partial (< `page_size`) page is returned |
