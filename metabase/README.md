# Metabase Integration for Autohive

Connects Autohive to a Metabase instance (Metabase Cloud or self-hosted) so agents can explore data, run queries, saved questions and dashboards, build and edit questions, models, metrics, collections and dashboards, and manage alerts, subscriptions, segments and timelines.

## Description

This integration covers the main analyst workflows in Metabase:

- **Explore the data model**: list connected databases, list tables (filtered by schema or name), and read a table's fields, types and foreign keys
- **Find content**: search questions, models, metrics, dashboards, collections and tables, and browse collections
- **Query**: run SQL against any connected database, or run a saved question with filter values. Results come back as rows keyed by column name.
- **Build**: save SQL or query-builder questions, models and metrics, create collections and dashboards, and add questions, text, headings and links to a dashboard
- **Edit**: change existing questions (SQL, chart type, chart settings), dashboards (layout, card titles, tabs, filters and their connections), collections, segments and table or column descriptions; copy questions and dashboards; move items; undo changes from the version history
- **Share and monitor**: run a whole dashboard with filter values, export results, email alerts on a question and scheduled dashboard subscriptions, and timeline events (releases, campaigns) on charts
- **Tidy up**: move items to Metabase's trash and bring them back. Nothing is ever deleted.

Every request runs with the permissions of the API key's group, so the agent can only see and change what that group can.

### Example workflows

- **Answer a data question:** `list_databases`, then `get_database_schema` (with `table_name_contains`) and `get_table` to learn the columns, then `run_sql_query`.
- **Reuse existing reports:** `search` with `models: ["card"]` and the topic, then `get_question` to see its SQL and filters, then `run_question`.
- **Build a dashboard:** `create_collection`, then `create_question` for each chart (e.g. `display: "line"`), then `create_dashboard`, then `add_question_to_dashboard` once per question.
- **Tidy a dashboard:** `get_dashboard`, then `update_dashboard_cards` to move, resize, retitle or remove cards, `add_text_to_dashboard` for section headings, `update_dashboard_tabs` to split it into tabs, and `update_dashboard_filters` to add a date filter connected to each card.
- **Weekly report by email:** `run_dashboard` to check the numbers, `list_users` to find recipients, then `create_subscription` with `frequency: "weekly"`.
- **Undo a bad edit:** `get_revision_history`, then `revert_to_revision` with an earlier `revision_id`.

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

### Optional gateway header

For a reverse proxy that requires a secret header before Metabase authentication, set
**Gateway Header Name** (for example, `X-Gateway-Secret`) and **Gateway Header Secret**.
Leave both empty for normal Metabase connections. The integration sends this header
alongside `x-api-key` on every request, including queries and creates.

Both gateway fields must be supplied together. The name must be an HTTP header token;
it cannot replace `x-api-key`, `Host`, content headers or transport-control headers.
The secret must be printable ASCII without line breaks. `Authorization` is allowed
if your gateway requires it; include its scheme (for example `Bearer ...`) in the value.

The value uses a password field in the same connection credentials as the API key.
This integration does not implement credential storage or encryption; those protections
are provided by Autohive's connection service and must be verified there.
With a gateway header configured, requests never follow redirects or retry automatically.
Use the final HTTPS URL. HTTP errors report status without upstream response bodies,
transport errors use fixed messages, and action errors redact literal credential values.
The integration does not log these headers; customer proxy/server logging is outside its control.
A gateway returning a Google sign-in page still fails: the gateway must actually accept
the supplied secret for machine access.

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
| `limit` / `offset` | integer | No | Paging (default 50, max 200) |

Returns `tables` plus `total`, `limit` and `offset` for paging.

### `get_table`

Returns a table's fields with `base_type`, `semantic_type` (e.g. `type/PK`, `type/FK`) and `foreign_key_target_field_id`. Use it before writing SQL against the table.

### `search`

Searches Metabase content.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | No | Text to search for. Leave empty to list items of the chosen types. |
| `models` | string[] | No | Item types: `card` (saved question), `dataset` (model), `metric`, `dashboard`, `collection`, `table`, `database`, `document`. If this Metabase rejects `metric` (before 0.51) or `document` (before 0.57, and some open-source releases), those types are left out and the result has a `note` saying so. |
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

Returns a saved question: name, type, visualization, database, collection, `native_sql` (when it is a SQL question) and the `parameters` (filters) it accepts. For SQL questions whose filters exist only as template tags, `parameters` is built from those tags, with the `target` that `run_question` needs.

### `run_question`

Runs a saved question and returns its rows.

Before running, the integration asks Metabase for the exact SQL the question will run (`POST /api/dataset/native`, with the same filter values), so filters, optional `[[ ... ]]` clauses, snippets and the questions it is built on are filled in by Metabase itself, and point-and-click questions come back as the SQL Metabase generates. That SQL is checked the same way `run_sql_query` checks SQL, and the question isn't run if the check fails. Filter defaults saved on the question are sent with the run, so the checked SQL and the run always use the same values. This costs three extra requests per run: the question, the SQL, and the database's engine. A question with a required filter and no value gets Metabase's "pick a value" error, as it would in Metabase.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question_id` | integer | Yes | Question id |
| `parameters` | object[] | No | Filter values in Metabase's format, e.g. `[{"id": "<parameter id>", "type": "category", "target": ["variable", ["template-tag", "region"]], "value": "EU"}]`. Copy `id`, `type` and `target` from `get_question`. |
| `max_rows` | integer | No (default 100, max 2000) | Rows to return |

### `run_sql_query`

Runs SQL in the database's own dialect and returns its rows.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_id` | integer | Yes | Database id |
| `sql` | string | Yes | SQL to run |
| `max_rows` | integer | No (default 100, max 2000) | Rows to return |

Before sending SQL, the integration parses it with [sqlglot](https://github.com/tobymao/sqlglot) in the dialect of the database it will run on (PostgreSQL, MySQL, SQL Server, BigQuery, Snowflake, ClickHouse and others; other databases are read as standard SQL). It looks up the database's engine first, with one extra read request. It sends the SQL only if it is:

- a single `SELECT`, `WITH`, `EXPLAIN`, `SHOW`, `DESCRIBE` or `VALUES` statement
- with no write anywhere inside it, so `WITH x AS (DELETE ...)`, `SELECT ... INTO` and a second SQL Server statement added without a semicolon (`SELECT 1 SHUTDOWN`, `SELECT 1 DELETE t`) are refused. `EXPLAIN` checks the statement it explains, so `EXPLAIN ANALYZE DELETE` is refused.
- with no function that has side effects, such as `nextval()`, `pg_terminate_backend()`, `dblink()`, `load_file()`, ClickHouse `url()` or Oracle `dbms_` packages. Every PostgreSQL `pg_` function is refused except common read-only ones like `pg_size_pretty` or `pg_get_viewdef`.

Because the SQL is parsed, column names, quoted text and comments are not mistaken for writes: `system`, `lock`, `use`, `copy`, `url` or `'delete from the queue'` are fine. SQL the parser can't read for that database is refused, as are MySQL `/*! */` comments (MySQL runs them) and PostgreSQL `U&"..."` names. On MySQL and PostgreSQL, SQL with a backslash must also be safe however the server is set to read quoted text (MySQL `NO_BACKSLASH_ESCAPES` or `ANSI_QUOTES`, PostgreSQL `standard_conforming_strings` off), so double a quote inside text instead of escaping it, and don't end text with a backslash. `create_question` applies the same rule.

**This blocks common writes, not every write.** Connect the database in Metabase with a read-only database user to block all writes. On DuckDB, table names that look like a file, glob or URL (`FROM '/path/file.csv'`, `FROM 'data/*.parquet'`, `FROM 'https://...'`) are refused, as are `glob()`, `parquet_scan()`, `sqlite_scan()`, `st_read()`, and the `postgres_`/`mysql_` scan, query and execute functions. Setting `enable_external_access` to `false` is still recommended. The API key's group also needs permission to write native queries against that database. A query that fails, for example because of a syntax error or a missing table, returns an error with Metabase's message.

#### Query results

`run_question` and `run_sql_query` return:

- `columns`: `name`, `display_name` and `base_type` for each column
- `rows`: one object per row, keyed by column name. Duplicate column names get a `_2`, `_3` suffix.
- `row_count`: rows returned
- `total_row_count`: rows Metabase sent back
- `truncated`: `true` when more rows existed than were returned

### `create_question`

Saves SQL as a question. Inputs: `name`, `database_id` and `sql` (all required), plus `display` (default `table`; also `bar`, `line`, `pie`, `scalar` and others), `description`, `collection_id` and `filters`.

For SQL with filters, write each one as `{{name}}` and define it in `filters`: `name`, `type` (`text`, `number` or `date` for a value put into the SQL, or `field` for a field filter on a column, which needs `field_id` from `get_table` and optionally `widget_type` such as `date/all-options`), and optionally `display_name`, `default` and `required`. For example `where total > {{min_total}} and {{created}}` with `[{"name": "min_total", "type": "number", "default": 100}, {"name": "created", "type": "field", "field_id": 34, "widget_type": "date/all-options"}]`. Snippets (`{{snippet: name}}`) and saved questions (`{{#12}}`) are found automatically. SQL with filters is checked as Metabase expands it, so a write hidden in a snippet is refused. Optional `[[ ]]` clauses are refused, because an expansion without filter values would leave out what they contain.

### `get_dashboard`

Returns a dashboard's name, collection, tabs, filters (`parameters`) and `cards`. Each card has the dashboard card id, question id and name, visualization and grid position.

### `create_dashboard`

Creates an empty dashboard. Inputs: `name` (required), `description` and `collection_id`.

### `add_question_to_dashboard`

Adds a saved question to a dashboard, placed below the existing cards (on the first tab, or on `tab_id`). Existing cards and their settings, including filter connections, are sent back unchanged. Optional `width` (1–24, default 12) and `height` (default 6) are in Metabase grid units; the grid is 24 wide. Returns the new dashboard card id and its position. If the dashboard has a subscription, the question is checked like `run_question` first, because Metabase adds it to the scheduled emails. Metabase only shows other people's subscriptions to admins, so with a non-admin API key every dashboard is treated as having one.

Add cards to the same dashboard one at a time. Metabase has no "add one card" API, so each update replaces the whole card list; two additions running in parallel can overwrite each other.

### Editing dashboards

All of these read the dashboard first and send every card, tab and filter they don't change back as it is. Metabase replaces the whole card list on every update, so change one dashboard at a time: two changes running in parallel can overwrite each other. Card ids (`dashcard_id`) and tab ids come from `get_dashboard`; the grid is 24 columns wide.

#### `update_dashboard`

Changes the dashboard's `name`, `description`, `collection_id` (moves it), `width` (`fixed` or `full`) or `auto_apply_filters` (`false` shows an Apply button). Only the fields given change.

#### `update_dashboard_cards`

Takes `cards`, a list of changes, one per card: `dashcard_id` plus any of `row`, `col`, `width`, `height`, `tab_id`, `title` (the title shown on this dashboard; the question keeps its own name) and `remove` (removes the card; a question saved in a collection is kept, while one saved inside this dashboard, on Metabase 0.54+, goes to the trash with its last card and `restore_item` brings it back). Cards not listed are left as they are; list each card once. A card must fit the grid (`col + width` at most 24).

#### `add_text_to_dashboard`

Adds a `text` card (Markdown), a `heading` or a `link` card (`url`). Placed below the existing cards on the first tab unless `row` or `tab_id` is given.

#### `update_dashboard_tabs`

Takes the full list of `tabs` in order. Tabs with an `id` are kept and renamed, tabs without one are created, and tabs left out are removed. A tab can only be removed once its cards are moved or removed. When a dashboard gets its first tabs, its cards go on the first one; an empty list removes every tab when all cards are on one tab (Metabase 0.49 can't remove the last tab, so there one tab is kept and `note` says so; Metabase shows no tab bar for a single tab).

#### `update_dashboard_filters`

Takes the full list of `filters`. Each has `name` and `type` (for example `date/all-options`, `category`, `string/=`, `number/between`, `boolean/=`; `temporal-unit` needs Metabase 0.50+), plus optional `id` (to keep an existing filter), `default`, `required` (needs a default), `linked_filter_ids` (filters that narrow this one's choices) and `connections`. Each connection names a `dashcard_id` and either a `field_id` (a column, from `get_table`, for query-builder questions) or a `template_tag` (a SQL question's `{{variable}}`); on a combined chart, `question_id` picks which of its questions the connection drives. Filters left out are removed along with their connections; if a subscription sets a value for a removed filter, Metabase turns that subscription off and emails its creator. A kept filter without `connections` keeps its existing ones; given `connections` replace all of them, so list every question it should still drive. Changing a filter's `type` clears its old default and value list. Each filter can be listed once, with one connection per question. A removed filter is also dropped from other filters' `linked_filter_ids`; linking to a filter not in the list is refused. If the dashboard has a subscription, a changed default, type or connection, or a removed filter, is checked first, as `create_subscription` checks it, because the scheduled emails run with it.

#### `copy_dashboard`

Copies a dashboard under a new `name`, into `collection_id` or else the original's collection. With `copy_questions: true` each question is copied too; otherwise the copy shows the same questions. Metabase leaves some questions off the copy (such as ones this API key can't read, or archived ones on newer versions); they are listed in `uncopied_questions` with a `note`.

#### `run_dashboard`

Runs every question on the dashboard (or one `tab_id`) and returns each card's rows (`max_rows` per card, default 20). `filters` sets values by filter id or slug, for example `[{"filter": "date", "value": "past30days"}]`; filters not given use their defaults. Each question's SQL is checked as in `run_question` before it runs. A card that fails, or is refused, reports `error` without stopping the others. At most 25 cards are run. Questions run one after another, so it stops starting new ones after about two minutes, or once about 4 MB of rows is collected (the last card's rows are cut to fit); the rest are counted in `skipped_card_count` with a `skipped_reason`.

### Editing questions, models and metrics

#### `update_question`

Changes a saved question, model or metric: `name`, `description`, `sql`, `display`, `visualization_settings` or `collection_id`. Only the fields given change. New SQL is checked the same way as `create_question`. The question's `{{ }}` filters and snippets are kept when the new SQL still uses them. New filters are defined in `filters`, the same way as in `create_question`. SQL with filters is checked as Metabase expands it, and optional `[[ ]]` clauses are refused. `visualization_settings` are merged into the saved settings, for example `{"graph.dimensions": ["month"], "graph.metrics": ["total"]}`; a setting set to `null` is removed.

#### `copy_question`

Copies a question, model or metric. Optional `name` (default "Copy of …") and `collection_id`.

#### `create_query_builder_question`

Saves a point-and-click question from a query-builder (MBQL) `query`, which people can open and change without SQL, for example `{"source-table": 12, "aggregation": [["count"]], "breakout": [["field", 34, {"temporal-unit": "month"}]]}`. Field ids come from `get_table`; `source-table` can also be `"card__<question id>"`. A query containing SQL is refused, and a query built on saved questions checks their SQL first.

#### `create_model`

Saves a model, a curated table others explore with the query builder, from either `sql` (checked as in `create_question`; snippets `{{snippet: name}}` and saved questions `{{#12}}` work, but Metabase doesn't allow `{{ }}` filters in a model, so make a question for those) or a query-builder `query`.

#### `create_metric`

Saves a metric, an official reusable calculation, from a query-builder `query` with exactly one aggregation. Metabase 0.49 has no metric questions, so there it is saved as a table metric instead (`type: "legacy_metric"`); it must be built on a table, and its id is a metric id, edited under Admin → Table Metadata.

#### `export_question_results`

Runs a saved question and returns its results as CSV text (`content`), JSON `rows`, or an Excel `file` (`format: "xlsx"`: base64 `content`, `name` and `contentType`), for more rows than `run_question` returns. CSV and JSON: `max_rows` default 1,000, max 10,000, and at most 1,000,000 characters of CSV. Excel files hold every row and must be under 3.5 MB. The question is checked as in `run_question`.

#### `get_revision_history` and `revert_to_revision`

List the saved versions of a question, model, metric, dashboard or segment, and put one back to an earlier `revision_id`. The revert is saved as a new version, so it can be undone too. If a question's earlier version has SQL that writes (or can't be checked), it is put straight back and an error is returned. A dashboard with a subscription is checked the same way after a revert, with the old version's filter defaults and connections, because its scheduled emails run with them.

### Segments

`list_segments` (optionally for one `table_id`), `create_segment` and `update_segment` work with segments: named filters on a table, such as "Active customers", that anyone can pick in the query builder. `filter` is a query-builder filter clause, for example `[">", ["field", 12, null], 100]`.

### Organising content

#### `update_collection`

Renames a collection, changes its description, or moves it into `parent_collection_id` (or to the top level with `move_to_root`). A collection in the trash stays there; use `restore_item` to bring it back.

#### `move_items`

Moves `items` (each an `item_type` of `question`, `model`, `metric`, `dashboard` or `collection`, and an `id`) into `collection_id`, or to the top level with `move_to_root`. A question saved inside a dashboard (Metabase 0.53+) is moved out of it. Each item reports its own result, so one failure doesn't stop the rest.

#### `archive_item` and `restore_item`

Move a question, model, metric, dashboard, collection, segment, subscription, timeline or timeline event to Metabase's trash and back, or turn an alert off and on. Archiving a collection archives everything inside it. Nothing is deleted, with one exception: Metabase deletes a question's alerts when the question (or model or metric) is archived, and restoring it doesn't bring them back, so check `list_alerts` first. On Metabase 0.49, `metric` ids are the table metric ids `create_metric` returned. Restoring a subscription first checks the dashboard's questions, because Metabase starts sending it again. A dashboard with subscriptions is restored, then checked (Metabase only lists a dashboard's subscriptions once it's out of the trash), and goes back in the trash if refused. Checks use each subscription's own filter values (Metabase Pro) as well as the dashboard's defaults.

### Alerts and subscriptions

Both send email, so Metabase needs email (SMTP) set up to actually send. Schedules take `frequency` (`hourly`, `daily` or `weekly`), `hour` (0–23, default 8, in Metabase's report timezone) and `day_of_week` for weekly. Recipients are `recipient_user_ids` (from `list_users`) and `recipient_emails`.

#### `list_alerts` and `create_alert`

An alert watches a saved question and emails people when it has results (`has_result`), or when the chart's value goes above (`goal_above`) or below (`goal_below`) its goal line. `send_once` stops it after the first send. Metabase runs the question on the schedule with nobody watching, so it is checked like `run_question` first; `create_subscription` checks every question on the dashboard the same way. On Metabase 0.54+ alerts use the newer notifications API; older versions use the alerts API. Both are handled.

#### `list_subscriptions`, `create_subscription` and `update_subscription`

A subscription emails a whole dashboard on a schedule. `skip_if_empty` skips a send when every question is empty. `update_subscription` changes only the fields given; recipient lists given replace the old ones. A monthly schedule set in Metabase keeps its week of the month when only `hour` or `day_of_week` change. Turn a subscription off with `archive_item`.

#### `list_users`

Lists users (`query` filters by name or email), to find recipient ids. Usually needs an API key in the Administrators group.

### Data descriptions

`update_table` and `update_field` change the name, description (and for columns the semantic type, such as `type/Currency`) that Metabase shows. The database itself is not changed. `sync_database` asks Metabase to pick up new tables and columns, and `rescan_field_values` refreshes the values in filter dropdowns; both run in the background. These need an API key with data-model or admin access.

### Timelines

`list_timelines`, `create_timeline`, `create_timeline_event` and `update_timeline_event` manage event timelines: markers such as releases or campaigns shown on time-series charts in the same collection. `timestamp` is ISO 8601, for example `2026-11-01`.

## Limits

- **2,000 rows per query.** Metabase's API returns at most 2,000 rows for a query that isn't aggregated, and this integration returns at most `max_rows` (max 2,000) of them. For large tables, aggregate in SQL or add a `LIMIT`. `truncated` shows when rows were cut off.
- **Query timeout.** Queries are given 120 seconds and are never retried automatically, so a slow query is not run twice. Slower queries return an error. Creates and dashboard updates are also sent only once. If Metabase saves a create but the response times out, the error tells the agent to check whether it exists before trying again.
- **Deployment: Lambda timeout.** Set the integration's Lambda timeout to about 150 seconds. With the 30 second default, Lambda stops a slow query or saved question before Metabase answers, and the agent gets a generic error instead of the timeout message above.
- **No deletes.** The integration never deletes Metabase content. `archive_item` moves items to Metabase's trash, where they can be restored. Every action that saves or runs SQL refuses common SQL writes (see `run_sql_query`).
- **Exports**: CSV and JSON return at most 10,000 rows; Excel files must be under 3.5 MB (the action result is limited in size).
- **Version differences.** On 0.49, metrics are saved as table metrics. The `temporal-unit` filter type needs 0.50+. Alerts are created through whichever alerts API the instance has.
- **Not covered in this version:** permission changes (groups, members, data and collection permissions), inviting or deactivating users, public sharing links, settings, and bookmarks (they would belong to the API key's user, not a person).

## Troubleshooting

- **HTTP 403** — the API key's group can't see or change that item. Check the group's collection permissions (Curate to edit) and data permissions in Metabase.
- **"Metabase returned a response that isn't JSON"** — the URL points at a login page or proxy, not Metabase. Use the address you open Metabase at.
- **"Saved question N wasn't run"** — the question's SQL looks like a write, or it can only be checked when the key's group can write native queries on that database.
- **Alert or subscription saved but no email arrives** — Metabase needs email (SMTP) set up under Admin → Settings → Email.
- **"The SQL uses {{x}}; define it in filters"** — add the filter to `filters` with its type.

## Alternative: Metabase MCP server

Metabase 0.60+ includes its own MCP server (Admin → AI → MCP). An Autohive plan can register it under **Integrations → Register MCP** with the URL `https://<your-metabase>/api/metabase-mcp` and OAuth sign-in. That registration is private to the plan and uses OAuth, not an API key. Use this integration when you want API-key access that works the same way on any Metabase version from 0.49.

## Requirements

- `autohive-integrations-sdk`
- `sqlglot` (pinned, used to parse SQL before it is sent)
- `aiohttp` (also used by the SDK; sends gateway requests without redirects or error-body logging)

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

# Include destructive tests (creates collections, questions, dashboards, segments, alerts, subscriptions and
# timelines, edits them, then moves them to the trash; also edits a table and column description and restores it)
uv run --with-requirements requirements-test.txt --with-requirements metabase/requirements.txt \
  pytest metabase/tests/test_metabase_integration.py -m "integration and destructive"
```

### Testing a gateway connection

Local unit tests need **no credentials**. They include a loopback fake gateway that
checks GET/POST/PUT headers and JSON bodies, refused redirects, safe errors and no retries.

For a live smoke test, put these values in the ignored repository-root `.env` file
(or export them in your shell); never commit or paste actual secrets:

```dotenv
METABASE_BASE_URL=https://metabase.example.com
METABASE_API_KEY=<Metabase API key>
METABASE_GATEWAY_HEADER_NAME=X-Gateway-Secret
METABASE_GATEWAY_HEADER_VALUE=<gateway secret>
```

Run only the two read-only connection checks (no database, question or dashboard fixtures needed):

```bash
uv run --with-requirements requirements-test.txt --with-requirements metabase/requirements.txt \
  pytest metabase/tests/test_metabase_integration.py -m integration \
  -k "test_get_current_user or test_list_databases"
```

Both should pass with valid credentials. Then repeat with a deliberately wrong gateway secret:
the checks should fail with a safe HTTP error (or a refused redirect). Restore the secret,
use an invalid API key, and confirm Metabase rejects it too. Restore valid credentials afterwards.
Check returned errors and integration logs do not contain either real secret.
For TeamCity using a gateway connection, add the two optional mappings shown in
`tests/teamcity.env`; leave them commented for connections without gateway credentials.

## API Reference

- [Metabase API docs](https://www.metabase.com/docs/latest/api) (your instance also serves its own at `/api/docs`)
- [API keys](https://www.metabase.com/docs/latest/people-and-groups/api-keys)
- Base URL: `{your_metabase}/api/...`
- Authentication: `x-api-key: <api_key>`
- Rate limits: none built in. Self-hosted instances are limited only by their own capacity.

## Version History

- **2.1.0**: 36 new actions for editing and managing existing content: `update_dashboard`, `update_dashboard_cards`, `add_text_to_dashboard`, `update_dashboard_tabs`, `update_dashboard_filters`, `copy_dashboard`, `run_dashboard`, `get_revision_history`, `revert_to_revision`, `update_question`, `copy_question`, `create_query_builder_question`, `create_model`, `create_metric`, `export_question_results` (CSV, JSON or Excel), `list_segments`, `create_segment`, `update_segment`, `update_collection`, `move_items`, `archive_item`, `restore_item`, `list_alerts`, `create_alert`, `list_subscriptions`, `create_subscription`, `update_subscription`, `list_users`, `update_table`, `update_field`, `sync_database`, `rescan_field_values`, `list_timelines`, `create_timeline`, `create_timeline_event`, `update_timeline_event`. `create_question` gains `filters` (define `{{ }}` filters; SQL with filters is checked as Metabase expands it). Checked on Metabase 0.49 and 0.65.
- **2.0.0**: Optional secret gateway header for self-hosted instances, validation, redirect refusal and safe gateway error handling.
- **1.0.0**: Initial release with 15 actions: `get_current_user`, `list_databases`, `get_database_schema`, `get_table`, `search`, `list_collections`, `list_collection_items`, `create_collection`, `get_question`, `run_question`, `run_sql_query`, `create_question`, `get_dashboard`, `create_dashboard`, `add_question_to_dashboard`. HTTPS-only base URL (sub-paths allowed); works with Metabase Cloud and self-hosted 0.49+.
