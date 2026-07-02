# Power BI Integration for Autohive

Connects Autohive to Power BI services for managing workspaces, datasets, reports, and dashboards through the Power BI REST API.

## Description

This integration provides comprehensive access to Power BI services, enabling users to manage and interact with Power BI workspaces, datasets, reports, and dashboards through a unified interface.

Key capabilities include managing workspaces, refreshing datasets, creating and cloning reports, exporting reports, querying data with DAX, and accessing dashboard tiles. The integration supports operations on both "My workspace" and specific workspaces.

## Setup & Authentication

This integration uses Power BI OAuth2 authentication through the Autohive platform. Users need to connect their Power BI account (Microsoft 365/Azure AD) to authorize the integration.

**Authentication Method:** Platform OAuth2 (Power BI)

Required Power BI API permissions:
- `offline_access` — Required for refresh tokens (keeps the connection authorized long-term)
- `Dataset.ReadWrite.All` — Read and write all datasets
- `Report.ReadWrite.All` — Read and write all reports
- `Dashboard.Read.All` — Read all dashboards
- `Workspace.ReadWrite.All` — Read and write all workspaces
- `Content.Create` — Create Power BI content
- `Tenant.ReadWrite.All` — Tenant-level read/write access
- `Item.ReadWrite.All` — Required for Fabric API report creation

## Actions

### `list_workspaces`

Get a list of all Power BI workspaces the user has access to.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `filter` | string | No | OData filter expression |
| `top` | integer | No | Maximum number of workspaces to return (default: 100) |

| Output | Type | Description |
|--------|------|-------------|
| `workspaces` | array | List of workspace objects with id, name, isReadOnly, isOnDedicatedCapacity, type |

---

### `get_workspace`

Get details of a specific Power BI workspace.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_id` | string | Yes | The workspace ID |

| Output | Type | Description |
|--------|------|-------------|
| `workspace` | object | Workspace details |

---

### `list_datasets`

Get a list of datasets in a workspace or My workspace.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `datasets` | array | List of dataset objects with id, name, configuredBy, isRefreshable, etc. |

---

### `get_dataset`

Get details of a specific dataset.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | string | Yes | The dataset ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `dataset` | object | Dataset details |

---

### `refresh_dataset`

Trigger a refresh for a Power BI dataset. Supports basic and enhanced refresh options.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | string | Yes | The dataset ID to refresh |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |
| `notify_option` | string | No | `NoNotification`, `MailOnFailure`, or `MailOnCompletion` |
| `type` | string | No | `Full`, `ClearValues`, `Calculate`, `DataOnly`, `Automatic`, or `Defragment` |
| `commit_mode` | string | No | `Transactional` or `PartialBatch` |
| `max_parallelism` | integer | No | Maximum threads for parallel processing |
| `retry_count` | integer | No | Retry attempts before failing |
| `objects` | array | No | Tables/partitions for selective refresh (each with `table` and optional `partition`) |
| `apply_refresh_policy` | boolean | No | Whether to apply incremental refresh policy |
| `effective_date` | string | No | Override date for incremental refresh (ISO 8601) |
| `timeout` | string | No | Timeout in HH:MM:SS format (max 24 hours including retries) |

| Output | Type | Description |
|--------|------|-------------|
| `message` | string | Confirmation message |
| `request_id` | string | The refresh request ID for tracking |

> Enhanced refresh parameters are not supported on Shared capacities.

---

### `get_refresh_history`

Get the refresh history for a dataset.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | string | Yes | The dataset ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |
| `top` | integer | No | Maximum records to return (default: 10) |

| Output | Type | Description |
|--------|------|-------------|
| `refreshes` | array | Refresh records with refreshType, startTime, endTime, status, requestId |

---

### `list_reports`

Get a list of reports in a workspace or My workspace.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `reports` | array | List of report objects with id, name, webUrl, embedUrl, datasetId |

---

### `get_report`

Get details of a specific report.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `report` | object | Report details |

---

### `get_report_datasources`

Get data sources connected to a specific report.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `datasources` | array | Data sources with datasourceType, datasourceId, gatewayId, name, connectionString, connectionDetails |

---

### `refresh_report`

Refresh the dataset associated with a Power BI report.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID whose dataset should be refreshed |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |
| `notify_option` | string | No | `NoNotification` or `MailOnFailure` (default: NoNotification) |

| Output | Type | Description |
|--------|------|-------------|
| `message` | string | Confirmation message |
| `dataset_id` | string | The ID of the dataset that was refreshed |

---

### `clone_report`

Clone a Power BI report to the same or a different workspace.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID to clone |
| `name` | string | Yes | Name for the cloned report |
| `workspace_id` | string | No | Source workspace ID (defaults to My workspace) |
| `target_workspace_id` | string | No | Target workspace ID (defaults to source workspace) |
| `target_dataset_id` | string | No | Target dataset ID for the cloned report |

| Output | Type | Description |
|--------|------|-------------|
| `id` | string | ID of the cloned report |
| `name` | string | Name of the cloned report |
| `webUrl` | string | Web URL to access the cloned report |
| `embedUrl` | string | Embed URL for the cloned report |

---

### `export_report`

Export a Power BI report to PDF, PPTX, or PNG. Returns an export ID — poll `get_export_status` to monitor progress.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID to export |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |
| `format` | string | No | `PDF`, `PPTX`, or `PNG` (default: PDF) |

| Output | Type | Description |
|--------|------|-------------|
| `export_id` | string | ID of the export operation |
| `message` | string | Confirmation message |

---

### `get_export_status`

Get the status of a report export operation.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `report_id` | string | Yes | The report ID |
| `export_id` | string | Yes | The export ID returned by `export_report` |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `status` | string | Export status: `Running`, `Succeeded`, or `Failed` |
| `percentComplete` | integer | Completion percentage (0–100) |

---

### `list_dashboards`

Get a list of dashboards in a workspace or My workspace.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `dashboards` | array | List of dashboard objects with id, displayName, isReadOnly, embedUrl |

---

### `get_dashboard`

Get details of a specific dashboard.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboard_id` | string | Yes | The dashboard ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `dashboard` | object | Dashboard details |

---

### `get_dashboard_tiles`

Get tiles from a specific dashboard.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dashboard_id` | string | Yes | The dashboard ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |

| Output | Type | Description |
|--------|------|-------------|
| `tiles` | array | Tile objects with id, title, embedUrl, datasetId, reportId |

---

### `execute_queries`

Execute DAX queries against a dataset.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_id` | string | Yes | The dataset ID |
| `workspace_id` | string | No | Workspace ID (defaults to My workspace) |
| `queries` | array | Yes | List of query objects, each with a `query` string (DAX) |

| Output | Type | Description |
|--------|------|-------------|
| `results` | array | Query result objects |

---

### `create_report`

Create a new Power BI report in a Fabric workspace bound to an existing dataset. Pages and visuals are specified declaratively — the report is built and published automatically via the Microsoft Fabric REST API.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `display_name` | string | Yes | Name for the new report |
| `workspace_id` | string | Yes | The Fabric workspace ID |
| `dataset_id` | string | Yes | The dataset (semantic model) ID to bind the report to |
| `pages` | array | Yes | Pages to include. Each page has `name` and `visuals`. |

Each visual in `pages[].visuals`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | `table`, `bar`, `line`, `card`, `pie`, `column`, `scatter`, `area`, `donut`, or `matrix` |
| `table` | string | Yes | Source table name in the dataset |
| `columns` | array | Yes | Column/measure names. For charts: first item is the category axis, rest are Y-axis measures. |
| `title` | string | No | Visual title |
| `x`, `y` | number | No | Position in pixels (auto-laid out if omitted) |
| `width`, `height` | number | No | Size in pixels (default 600×350) |

| Output | Type | Description |
|--------|------|-------------|
| `id` | string | ID of the created report |
| `display_name` | string | Name of the created report |
| `workspace_id` | string | Workspace where the report was created |
| `web_url` | string | URL to open the report in Power BI |

## Testing

Install dependencies and run unit tests:

```bash
cd powerbi
pip install -r requirements.txt -t dependencies
python -m pytest tests/test_powerbi_*_unit.py -v
```

Unit tests are split by domain: `test_powerbi_workspaces_unit.py`, `test_powerbi_datasets_unit.py`, `test_powerbi_reports_unit.py`, `test_powerbi_dashboards_unit.py`, and `test_powerbi_queries_unit.py`.

Run integration tests against the live API (requires credentials in `.env`):

```bash
# Read-only tests only
pytest powerbi/tests/test_powerbi_integration.py -m "integration and not destructive"

# Include destructive tests (triggers real refreshes and creates a real report)
pytest powerbi/tests/test_powerbi_integration.py -m "integration and destructive"
```

See `.env.example` for the environment variables required for integration tests.

## Notes

- All workspace-scoped actions accept an optional `workspace_id`; omitting it targets "My workspace"
- Dataset refresh and report export are asynchronous — use `get_refresh_history` / `get_export_status` to poll progress
- `create_report` uses the Microsoft Fabric REST API (`api.fabric.microsoft.com/v1`) rather than the standard Power BI REST API
- DAX queries require the dataset to have query execution enabled and appropriate permissions
