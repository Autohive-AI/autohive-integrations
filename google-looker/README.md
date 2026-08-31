# Google Looker Integration

Access Looker dashboards, LookML models, analytical query results, SQL Runner, and database connection metadata through the Looker API 4.0.

## Action safety

| Action | Looker operation | Classification |
|---|---|---|
| `list_dashboards` | `GET /dashboards` | Read-only |
| `get_dashboard` | `GET /dashboards/{dashboard_id}` | Read-only |
| `execute_lookml_query` | `POST /queries/run/{result_format}` | Analytical read; can consume database compute and populate Looker-managed caches or derived tables |
| `list_models` | `GET /lookml_models` | Read-only |
| `get_model` | `GET /lookml_models/{lookml_model_name}` | Read-only |
| `execute_sql_query` | `POST /sql_queries`, then `POST /sql_queries/{slug}/run/{result_format}` | Potentially destructive |
| `list_connections` | `GET /connections` | Read-only metadata |

> [!WARNING]
> Looker SQL Runner permits DDL and DML statements. `execute_sql_query` can create, alter, or drop schema objects and insert, update, or delete data when the selected database credentials allow it. Use a dedicated Looker API user and read-only database credentials for agent workflows.

## Authentication

Create an API key for a least-privilege Looker user:

1. In Looker, open **Admin > Users** and select the API user.
2. Create an API key to obtain a Client ID and Client Secret.
3. Configure the integration with:
   - `base_url`: HTTPS origin of the Looker instance, such as `https://company.cloud.looker.com`. Do not include `/api/4.0` or another path.
   - `client_id`: Looker API key client ID.
   - `client_secret`: Looker API key client secret.

API requests execute with the permissions and model access of the Looker user associated with the key. Avoid credentials belonging to an administrator.

### Permissions

Grant only the permissions needed for the enabled workflows:

- Dashboard discovery: `see_user_dashboards` and/or `see_lookml_dashboards`, plus the appropriate folder and model access.
- LookML model queries: `access_data`, `see_looks`, and `explore` for the relevant model set.
- SQL Runner: `use_sql_runner`, which depends on `see_lookml`, plus access to the relevant model/connection.
- Database safety: configure the underlying database user as read-only. Looker does not restrict which SQL commands SQL Runner can execute.

See [Looker API authentication](https://cloud.google.com/looker/docs/api-auth), [Looker roles and permissions](https://cloud.google.com/looker/docs/admin-panel-users-roles), and [SQL Runner database changes](https://cloud.google.com/looker/docs/sql-runner-manage-db).

## Actions

### `list_dashboards`

Returns all active dashboards visible to the API user.

Inputs:

- `fields` (optional): Comma-separated Looker response projection.

Output: `dashboards`, an array of dashboard objects.

Looker's `GET /dashboards` endpoint does not support pagination. Use `fields` to reduce each returned dashboard object when only a projection is needed.

### `get_dashboard`

Returns one dashboard.

Inputs:

- `dashboard_id` (required): Dashboard identifier returned by `list_dashboards`.
- `fields` (optional): Comma-separated Looker response projection.

Output: `dashboard`, the dashboard object.

### `execute_lookml_query`

Runs a query inline against a LookML model and Explore. It does not create an immutable saved-query object first.

Inputs:

- `model` (required): LookML model name.
- `explore` (required): Explore name, sent to Looker as `view`.
- `dimensions` and `measures` (optional): Fully qualified LookML field names. They are combined into the API `fields` array.
- `filters` (optional): Map of field names to Looker filter expressions.
- `sorts` (optional): Looker sort expressions.
- `limit` (optional): Positive row count, or `-1` for unlimited results when permissions permit.
- `result_format` (optional): `json`, `json_bi`, `json_detail`, `csv`, `txt`, `html`, `md`, or `sql`. Default: `json`.
- `apply_formatting` and `apply_vis` (optional): Apply Looker formatting or visualization settings.

Output: `query_results`, returned as a string. JSON results are JSON-encoded.

Binary formats such as XLSX, PNG, and JPG are intentionally excluded because the Autohive SDK fetch layer currently exposes non-JSON responses as text.

### `list_models`

Returns LookML models visible to the API user.

Inputs:

- `fields` (optional): Comma-separated response projection.
- `limit` and `offset` (optional): Server-side result window.
- `exclude_empty` (optional): Exclude models without Explores.
- `exclude_hidden` (optional): Exclude hidden Explores.
- `include_internal` (optional): Include built-in models such as System Activity.
- `include_self_service` (optional): Include self-service models.

Output: `models`, an array of LookML model objects.

### `get_model`

Returns one LookML model.

Inputs:

- `model_name` (required): LookML model name.
- `fields` (optional): Comma-separated response projection.

Output: `model`, the LookML model object.

### `execute_sql_query`

Creates and runs a SQL Runner query.

Inputs:

- `sql` (required): SQL statement. The integration does not claim to make arbitrary SQL read-only.
- Exactly one of `connection_name` or `model_name` (required): Selects the database connection.
- `vis_config` (optional): Opaque Looker visualization configuration.
- `result_format` (optional): `inline_json`, `json`, `json_detail`, `json_fe`, `json_bi`, `csv`, `html`, `md`, `txt`, `gsxml`, `sql`, or `json_label`. Default: `json`.
- `download` (optional): `true` or `false`; controls download-oriented response headers.

Outputs:

- `slug`: Identifier of the SQL Runner query created by Looker.
- `query_results`: Result returned as a string. JSON results are JSON-encoded.

The action excludes binary XLSX output because the SDK fetch layer handles non-JSON responses as text.

### `list_connections`

Returns database connections visible to the API user.

Input: `fields` (optional), a comma-separated response projection.

Output: `connections`, an array of connection objects.

## Development and testing

Install dependencies and run the mocked unit suite from the repository root:

```bash
python -m pip install -r requirements-test.txt -r google-looker/requirements.txt
python -m pytest google-looker/tests/test_google_looker_unit.py -q
hiveup validate google-looker
```

Live tests use these environment variables:

```text
LOOKER_BASE_URL
LOOKER_CLIENT_ID
LOOKER_CLIENT_SECRET
LOOKER_TEST_DASHBOARD_ID
LOOKER_TEST_MODEL_NAME
LOOKER_TEST_EXPLORE_NAME
LOOKER_TEST_QUERY_FIELD
LOOKER_RUN_SQL_TESTS
```

Run read-only and analytical tests:

```bash
python -m pytest google-looker/tests/test_google_looker_integration.py -m "integration and not destructive" -q
```

The SQL Runner test uses only `SELECT 1`, but it creates Looker SQL Runner query metadata and is therefore separately opt-in. Set `LOOKER_RUN_SQL_TESTS=true`, confirm the selected model uses read-only database credentials, then run:

```bash
python -m pytest google-looker/tests/test_google_looker_integration.py -m "integration and destructive" -q
```

## Official API reference

- [Get all dashboards](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Dashboard/all_dashboards)
- [Get dashboard](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Dashboard/dashboard)
- [Run inline query](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Query/run_inline_query)
- [Get all LookML models](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/LookmlModel/all_lookml_models)
- [Get LookML model](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/LookmlModel/lookml_model)
- [Create SQL Runner query](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Query/create_sql_query)
- [Run SQL Runner query](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Query/run_sql_query)
- [Get all connections](https://cloud.google.com/looker/docs/reference/looker-api/latest/methods/Connection/all_connections)
