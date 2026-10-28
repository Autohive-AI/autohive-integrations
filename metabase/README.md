# Metabase Integration for Autohive

Connects Autohive to a Metabase instance (Metabase Cloud or self-hosted) so agents can explore data, run queries and saved questions, and build questions, collections and dashboards.

## Description

This integration covers the main analyst workflows in Metabase:

- **Explore the data model**: list connected databases, list tables (filtered by schema or name), and read a table's fields, types and foreign keys
- **Find content**: search questions, models, metrics, dashboards, collections and tables, and browse collections
- **Query**: run SQL against any connected database, or run a saved question with filter values. Results come back as rows keyed by column name.
- **Build**: save SQL as a question, create collections and dashboards, and add questions to a dashboard

Every request runs with the permissions of the API key's group, so the agent can only see and change what that group can.

### Example workflows

- **Answer a data question:** `list_databases`, then `get_database_schema` (with `table_name_contains`) and `get_table` to learn the columns, then `run_sql_query`.
- **Reuse existing reports:** `search` with `models: ["card"]` and the topic, then `get_question` to see its SQL and filters, then `run_question`.
- **Build a dashboard:** `create_collection`, then `create_question` for each chart (e.g. `display: "line"`), then `create_dashboard`, then `add_question_to_dashboard` once per question.

## Setup & Authentication

Works with Metabase Cloud and self-hosted Metabase, open source or paid, version **0.49 or later** (the first version with API keys). When connecting in Autohive, the user enters:

1. **Metabase URL**: the address you open Metabase at, for example `https://yourcompany.metabaseapp.com` or `https://metabase.example.com`. If Metabase is served from a sub-path, include it, for example `https://example.com/metabase`. A trailing `/` or `/api` is removed automatically.
2. **API Key**: an admin creates one in Metabase under **Admin → Settings → Authentication → API keys**. Each key belongs to one group and gets that group's data and collection permissions. Create a dedicated group for the agent and give it only the databases and collections it should use. Give the key the Administrators group only if the agent really needs admin access.

### HTTPS is required

Only `https://` URLs are accepted, because the API key is sent on every request. Metabase Cloud is always HTTPS. A self-hosted instance must sit behind HTTPS, for example a reverse proxy (Caddy, nginx, Traefik) or a tunnel (Cloudflare Tunnel, Tailscale Funnel). It must also be reachable from the internet so Autohive can connect to it.

### Authentication Fields

| Field | Format | Used For |
|-------|--------|----------|
| `base_url` | Metabase URL (https required, sub-path allowed) | All actions |
| `api_key` | Metabase API key | All actions, sent as the `x-api-key` header |

## Actions

### `get_current_user`

Returns the Metabase user the API key acts as: id, name, admin flag, group ids and personal collection id. Use it to check the connection works.

### `list_databases`

Lists connected databases with `id`, `name`, `engine`, `description` and `is_sample`. The ids are used by `get_database_schema`, `run_sql_query` and `create_question`.

### `get_database_schema`

Lists the tables in a database.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_id` | integer | Yes | Database id |
| `schema` | string | No | Only tables in this schema (case-insensitive) |
| `table_name_contains` | string | No | Only tables whose name contains this text |
| `include_fields` | boolean | No (default `false`) | Include each table's fields. On a large warehouse this can be a lot of data, so filter first. |

### `get_table`

Returns a table's fields with `base_type`, `semantic_type` (e.g. `type/PK`, `type/FK`) and `foreign_key_target_field_id`. Use it before writing SQL against the table.

### `search`

Searches Metabase content.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | No | Text to search for. Leave empty to list items of the chosen types. |
| `models` | string[] | No | Item types: `card` (saved question), `dataset` (model), `metric`, `dashboard`, `collection`, `table`, `database`, `document` |
| `archived` | boolean | No | Search trashed items instead |
| `limit` / `offset` | integer | No | Paging (default 50, max 200) |

Returns `results` plus `total`, `limit` and `offset` for paging.

### `list_collections`

Lists collections with `id`, `name`, `parent_id` and `location`. Personal collections are left out unless `include_personal` is `true`. Set `archived: true` to list trashed collections.

### `list_collection_items`

Lists what is inside a collection: questions, models, metrics, dashboards and sub-collections. `collection_id` defaults to `root` (the top level). Use `models` to filter by item type, and `limit` / `offset` to page.

### `create_collection`

Creates a collection. Inputs: `name` (required), `description`, and `parent_collection_id` to nest it inside another collection.

### `get_question`

Returns a saved question: name, type, visualization, database, collection, `native_sql` (when it is a SQL question) and the `parameters` (filters) it accepts.

### `run_question`

Runs a saved question and returns its rows.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question_id` | integer | Yes | Question id |
| `parameters` | object[] | No | Filter values in Metabase's format, e.g. `[{"type": "category", "target": ["variable", ["template-tag", "region"]], "value": "EU"}]` |
| `max_rows` | integer | No (default 100, max 2000) | Rows to return |

### `run_sql_query`

Runs SQL in the database's own dialect and returns its rows.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_id` | integer | Yes | Database id |
| `sql` | string | Yes | SQL to run |
| `max_rows` | integer | No (default 100, max 2000) | Rows to return |

The API key's group needs permission to write native queries against that database. A query that fails, for example because of a syntax error or a missing table, returns an error with Metabase's message.

#### Query results

`run_question` and `run_sql_query` return:

- `columns`: `name`, `display_name` and `base_type` for each column
- `rows`: one object per row, keyed by column name. Duplicate column names get a `_2`, `_3` suffix.
- `row_count`: rows returned
- `total_row_count`: rows Metabase sent back
- `truncated`: `true` when more rows existed than were returned

### `create_question`

Saves SQL as a question. Inputs: `name`, `database_id` and `sql` (all required), plus `display` (default `table`; also `bar`, `line`, `pie`, `scalar` and others), `description` and `collection_id`.

### `get_dashboard`

Returns a dashboard's name, collection, tabs, filters (`parameters`) and `cards`. Each card has the dashboard card id, question id and name, visualization and grid position.

### `create_dashboard`

Creates an empty dashboard. Inputs: `name` (required), `description` and `collection_id`.

### `add_question_to_dashboard`

Adds a saved question to a dashboard, placed below the existing cards (on the first tab, or on `tab_id`). Existing cards and their settings, including filter connections, are sent back unchanged. Optional `width` (1–24, default 12) and `height` (default 6) are in Metabase grid units; the grid is 24 wide. Returns the new dashboard card id and its position.

## Limits

- **2,000 rows per query.** Metabase's API returns at most 2,000 rows for a query that isn't aggregated, and this integration returns at most `max_rows` (max 2,000) of them. For large tables, aggregate in SQL or add a `LIMIT`. `truncated` shows when rows were cut off.
- **Query timeout.** Queries are given 120 seconds and are never retried automatically, so a slow query is not run twice. Slower queries return an error. Creates and dashboard updates are also sent only once.
- **No deletes.** The integration never deletes or archives content.
- **Not covered in this version:** alerts and subscriptions, building queries with Metabase's GUI query builder (MBQL), exporting results, and editing existing questions.

## Alternative: Metabase MCP server

Metabase 0.60+ includes its own MCP server (Admin → AI → MCP). An Autohive plan can register it under **Integrations → Register MCP** with the URL `https://<your-metabase>/api/metabase-mcp` and OAuth sign-in. That registration is private to the plan and uses OAuth, not an API key. Use this integration when you want API-key access that works the same way on any Metabase version from 0.49.

## Requirements

- `autohive-integrations-sdk`

## Testing

```bash
cd autohive-integrations
uv run --with-requirements requirements-test.txt --with-requirements metabase/requirements.txt pytest metabase/tests/
```

Live tests call a real Metabase instance. Set `METABASE_BASE_URL` (https:// only) and `METABASE_API_KEY`:

```bash
# METABASE_BASE_URL=https://metabase.example.com
# METABASE_API_KEY=mb_...
```

The read-only tests need a key that can see at least one SQL database, saved question and dashboard. They run `select 1` and a few read requests.

```bash
# Read-only integration tests (default — safe to run against any instance)
uv run --with-requirements requirements-test.txt --with-requirements metabase/requirements.txt \
  pytest metabase/tests/test_metabase_integration.py -m "integration and not destructive"

# Include destructive tests (creates a collection, question and dashboard, then moves them to the trash)
uv run --with-requirements requirements-test.txt --with-requirements metabase/requirements.txt \
  pytest metabase/tests/test_metabase_integration.py -m "integration and destructive"
```

## API Reference

- [Metabase API docs](https://www.metabase.com/docs/latest/api) (your instance also serves its own at `/api/docs`)
- [API keys](https://www.metabase.com/docs/latest/people-and-groups/api-keys)
- Base URL: `{your_metabase}/api/...`
- Authentication: `x-api-key: <api_key>`
- Rate limits: none built in. Self-hosted instances are limited only by their own capacity.

## Version History

- **1.0.0**: Initial release with 15 actions: `get_current_user`, `list_databases`, `get_database_schema`, `get_table`, `search`, `list_collections`, `list_collection_items`, `create_collection`, `get_question`, `run_question`, `run_sql_query`, `create_question`, `get_dashboard`, `create_dashboard`, `add_question_to_dashboard`. HTTPS-only base URL (sub-paths allowed); works with Metabase Cloud and self-hosted 0.49+.
