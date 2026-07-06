# Freshsales Integration for Autohive

Connects Autohive to the [Freshsales](https://www.freshworks.com/crm/sales/) CRM
(Freshworks) to manage contacts, sales accounts, deals, tasks, appointments, and notes.

## Description

This integration covers the core Freshsales CRM objects with full CRUD actions, plus
list-view discovery and global search. Freshsales lists records through *views*
(saved filters): the list actions accept an optional `view_id` and automatically use
the "All Contacts/Accounts/Deals" view when none is given. Use the `list_views` action
to discover other views (e.g. pipeline- or owner-specific ones).

## Setup & Authentication

1. In Freshsales, go to **Personal Settings → API Settings** and copy your **API key**.
2. Note your **bundle alias** — the `yourcompany` part of `yourcompany.myfreshworks.com`.
3. When adding the integration in Autohive, enter both values.

Note: the Freshsales API is included in all plans under a fair-usage policy. Rate
limits are per account per hour and vary by plan; exceeding them returns HTTP 429.

## Actions

| Action | Description |
| ------ | ----------- |
| `create_contact` / `get_contact` / `update_contact` / `delete_contact` / `list_contacts` | Contact CRUD; list supports views, pagination, sorting, and includes |
| `create_account` / `get_account` / `update_account` / `delete_account` / `list_accounts` | Sales account (organization) CRUD |
| `create_deal` / `get_deal` / `update_deal` / `delete_deal` / `list_deals` | Deal CRUD with pipeline/stage support |
| `create_task` / `get_task` / `update_task` / `delete_task` / `list_tasks` | Task CRUD; list filters by open/due_today/due_tomorrow/overdue/completed; set `status: 1` to complete |
| `create_appointment` / `get_appointment` / `update_appointment` / `delete_appointment` / `list_appointments` | Appointment CRUD; list filters by open/completed |
| `create_note` / `update_note` / `delete_note` | Attach notes to contacts, accounts, or deals |
| `list_views` | Discover list views (filters) for contacts, accounts, or deals |
| `search` | Global search across contacts, accounts, and deals |

## Requirements

- Python 3.13+
- autohive-integrations-sdk ~= 2.0.0

## Testing

```bash
# Unit tests (mocked)
pytest freshsales/ -v

# Live integration tests — requires FRESHSALES_API_KEY and FRESHSALES_BUNDLE_ALIAS in .env
pytest freshsales/tests/test_freshsales_integration.py -m integration -v
```
