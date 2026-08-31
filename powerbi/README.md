# Power BI Integration for Autohive

Connects Autohive to Power BI services for managing workspaces, datasets, reports, and dashboards through the Power BI REST API.

## Description

This integration provides comprehensive access to Power BI services, enabling users to manage and interact with Power BI workspaces, datasets, reports, and dashboards through a unified interface. It interacts with the Power BI REST API to deliver seamless integration with Power BI's analytics and reporting capabilities.

Key capabilities include managing workspaces, refreshing datasets, cloning, importing, and exporting reports, querying data with DAX, and accessing dashboard tiles. The integration supports operations on both "My workspace" and specific workspaces, providing flexible access to Power BI content.

## Report Creation Workflows

The integration supports two server-side report creation workflows:

1. **Create from an existing template:** use `clone_report`, optionally setting `target_dataset_id` to bind the copy to another compatible semantic model.
2. **Publish a prepared report or data file:** use `import_powerbi_file` with a `.pbix`, `.rdl`, `.xlsx`, or `model.json` file, then poll `get_import_status` until the import is `Succeeded` or `Failed`.

Power BI's standard REST API does not author arbitrary interactive pages and visuals from a natural-language prompt. Microsoft's server-side API for publishing editable report definitions is the Microsoft Fabric Create Report API, which accepts PBIR/PBIR-Legacy definition parts. That endpoint uses the separate Fabric API OAuth audience, so the existing Power BI connection cannot call it with the same access token. A complete "requirements to interactive dashboard" feature therefore also needs a PBIR generation layer and multi-resource OAuth support; this integration does not pretend that importing a source document alone creates a designed dashboard.

## Setup & Authentication

This integration uses Power BI OAuth2 authentication through the Autohive platform. Users need to connect their Power BI account (Microsoft 365/Azure AD) to authorize the integration.

**Authentication Method:** Platform OAuth2 (Power BI)

Required Power BI API permissions:
- `Dataset.Read.All` - Read all datasets
- `Dataset.ReadWrite.All` - Read and write all datasets
- `Report.Read.All` - Read all reports
- `Report.ReadWrite.All` - Read and write all reports
- `Dashboard.Read.All` - Read all dashboards
- `Workspace.Read.All` - Read all workspaces
- `Workspace.ReadWrite.All` - Read and write all workspaces
- `Content.Create` - Create Power BI content

**Authentication Fields:**

The integration uses platform-level OAuth2 authentication, so no manual configuration of authentication fields is required. Users simply need to authorize their Microsoft 365/Azure AD account through the Autohive platform.

## Actions

### Action: `list_workspaces`

*   **Description:** Get a list of all Power BI workspaces the user has access to
*   **Inputs:**
    *   `filter`: Optional OData filter expression
    *   `top`: Maximum number of workspaces to return (default: 100)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `workspaces`: List of workspace objects with id, name, and properties
    *   `error`: Error message if operation failed

### Action: `get_workspace`

*   **Description:** Get details of a specific Power BI workspace
*   **Inputs:**
    *   `workspace_id`: The workspace ID
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `workspace`: Workspace object with detailed information
    *   `error`: Error message if operation failed

### Action: `list_datasets`

*   **Description:** Get a list of datasets in a workspace or My workspace
*   **Inputs:**
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `datasets`: List of dataset objects with id, name, and refresh properties
    *   `error`: Error message if operation failed

### Action: `get_dataset`

*   **Description:** Get details of a specific dataset
*   **Inputs:**
    *   `dataset_id`: The dataset ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `dataset`: Dataset object with detailed information
    *   `error`: Error message if operation failed

### Action: `refresh_dataset`

*   **Description:** Trigger a refresh for a Power BI dataset with support for enhanced refresh options
*   **Inputs:**
    *   `dataset_id`: The dataset ID to refresh (required)
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
    *   `notify_option`: Mail notification options - "NoNotification", "MailOnFailure", or "MailOnCompletion" (optional)
    *   `type`: The type of processing - "Full", "ClearValues", "Calculate", "DataOnly", "Automatic", or "Defragment" (optional)
    *   `commit_mode`: Commit mode - "Transactional" or "PartialBatch" (optional)
    *   `max_parallelism`: Maximum number of threads for parallel processing (optional)
    *   `retry_count`: Number of retry attempts before failing (optional)
    *   `objects`: Array of tables/partitions to refresh selectively (optional, each with `table` and optional `partition`)
    *   `apply_refresh_policy`: Whether to apply incremental refresh policy (optional boolean)
    *   `effective_date`: Override date for incremental refresh policy in ISO 8601 format (optional)
    *   `timeout`: Timeout in HH:MM:SS format, e.g., "05:00:00" for 5 hours (optional)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `message`: Success or error message
    *   `request_id`: The refresh request ID for tracking
    *   `error`: Error message if operation failed
*   **Notes:**
    *   Enhanced refresh (with parameters beyond `notify_option`) is not supported for Shared capacities
    *   For Shared capacities, maximum of 8 refresh requests per day
    *   For Premium capacities, refresh limits depend on available resources
    *   Selective refresh using `objects` parameter allows refreshing specific tables or partitions
    *   Use `timeout` to control long-running refreshes (max 24 hours including retries)

### Action: `get_refresh_history`

*   **Description:** Get the refresh history for a dataset
*   **Inputs:**
    *   `dataset_id`: The dataset ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
    *   `top`: Maximum number of refresh records to return (default: 10)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `refreshes`: List of refresh records with status, start time, and end time
    *   `error`: Error message if operation failed

### Action: `list_reports`

*   **Description:** Get a list of reports in a workspace or My workspace
*   **Inputs:**
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `reports`: List of report objects with id, name, webUrl, and embedUrl
    *   `error`: Error message if operation failed

### Action: `get_report`

*   **Description:** Get details of a specific report
*   **Inputs:**
    *   `report_id`: The report ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `report`: Report object with detailed information
    *   `error`: Error message if operation failed

### Action: `get_report_datasources`

*   **Description:** Get a list of data sources for a specific paginated report (RDL)
*   **Inputs:**
    *   `report_id`: The report ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `datasources`: List of data source objects with datasourceType, datasourceId, gatewayId, name, connectionString, and connectionDetails
    *   `error`: Error message if operation failed

### Action: `refresh_report`

*   **Description:** Refresh the dataset associated with a Power BI report
*   **Inputs:**
    *   `report_id`: The report ID whose dataset should be refreshed
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
    *   `notify_option`: Notification option - "NoNotification" or "MailOnFailure" (default: NoNotification)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `message`: Success or error message
    *   `dataset_id`: The ID of the dataset that was refreshed
    *   `error`: Error message if operation failed

### Action: `clone_report`

*   **Description:** Clone a Power BI report to the same or different workspace
*   **Inputs:**
    *   `report_id`: The report ID to clone
    *   `name`: Name for the cloned report
    *   `workspace_id`: Source workspace ID (optional, defaults to My workspace)
    *   `target_workspace_id`: Target workspace ID (optional, defaults to source workspace)
    *   `target_dataset_id`: Target dataset ID for the cloned report (optional)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `id`: ID of the cloned report
    *   `name`: Name of the cloned report
    *   `webUrl`: Web URL to access the cloned report
    *   `embedUrl`: Embed URL for the cloned report
    *   `error`: Error message if operation failed

### Action: `import_powerbi_file`

*   **Description:** Publish a PBIX report, RDL paginated report, Excel workbook, or `model.json` dataflow file
*   **Inputs:**
    *   `file`: Attached or generated file with base64 `content`, `name`, and optional `contentType`
    *   `workspace_id`: Destination workspace ID (optional, defaults to My workspace)
    *   `display_name`: Optional imported content name; the source extension is appended when omitted
    *   `name_conflict`: Optional conflict behavior. RDL supports `Abort` or `Overwrite`; `model.json` supports `Abort` or `GenerateUniqueName`
    *   `skip_report`: Import only the semantic model (PBIX only)
    *   `override_report_label`: Override an existing report sensitivity label when republishing
    *   `override_model_label`: Override an existing semantic model sensitivity label when republishing
    *   `subfolder_object_id`: Optional destination workspace subfolder object ID
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `import_id`: Import operation ID for status checks
    *   `import_state`: Initial import state
    *   `reports`: Reports returned for a synchronously completed import
    *   `datasets`: Semantic models returned for a synchronously completed import
    *   `error`: Error message if operation failed

### Action: `get_import_status`

*   **Description:** Check an import operation and return the created reports and semantic models
*   **Inputs:**
    *   `import_id`: Import operation ID returned by `import_powerbi_file`
    *   `workspace_id`: The workspace used for the import (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `import_state`: `Publishing`, `Succeeded`, or `Failed`
    *   `reports`: Reports created by the import
    *   `datasets`: Semantic models created by the import
    *   `import_error`: Provider failure details when the import failed
    *   `error`: Error message if the status request failed

### Action: `export_report`

*   **Description:** Export a Power BI report to PDF, PPTX, or PNG format
*   **Inputs:**
    *   `report_id`: The report ID to export
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
    *   `format`: Export format - "PDF", "PPTX", or "PNG" (default: PDF)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `export_id`: ID of the export operation
    *   `message`: Success or error message
    *   `error`: Error message if operation failed

### Action: `get_export_status`

*   **Description:** Get the status of a report export operation
*   **Inputs:**
    *   `report_id`: The report ID
    *   `export_id`: The export ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `status`: Export status (Running, Succeeded, Failed)
    *   `percentComplete`: Percentage of completion (0-100)
    *   `error`: Error message if operation failed

### Action: `list_dashboards`

*   **Description:** Get a list of dashboards in a workspace or My workspace
*   **Inputs:**
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `dashboards`: List of dashboard objects with id, displayName, and embedUrl
    *   `error`: Error message if operation failed

### Action: `get_dashboard`

*   **Description:** Get details of a specific dashboard
*   **Inputs:**
    *   `dashboard_id`: The dashboard ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `dashboard`: Dashboard object with detailed information
    *   `error`: Error message if operation failed

### Action: `get_dashboard_tiles`

*   **Description:** Get tiles from a specific dashboard
*   **Inputs:**
    *   `dashboard_id`: The dashboard ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `tiles`: List of tile objects with id, title, embedUrl, and related IDs
    *   `error`: Error message if operation failed

### Action: `execute_queries`

*   **Description:** Execute DAX queries against a dataset
*   **Inputs:**
    *   `dataset_id`: The dataset ID
    *   `workspace_id`: The workspace ID (optional, defaults to My workspace)
    *   `queries`: List of query objects, each containing a DAX query string
*   **Outputs:**
    *   `result`: Boolean indicating success/failure
    *   `results`: List of query result objects
    *   `error`: Error message if operation failed

## Requirements

*   `autohive_integrations_sdk`

## Usage Examples

**Example 1: List all workspaces**

```json
{
  "top": 50
}
```

**Example 2: Basic dataset refresh with email notification on failure**

```json
{
  "dataset_id": "cfafbeb1-8037-4d0c-896e-a46fb27ff229",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "notify_option": "MailOnFailure"
}
```

**Example 2b: Enhanced dataset refresh with selective table refresh**

```json
{
  "dataset_id": "cfafbeb1-8037-4d0c-896e-a46fb27ff229",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "type": "Full",
  "commit_mode": "Transactional",
  "objects": [
    {
      "table": "Sales",
      "partition": "2024-Q4"
    },
    {
      "table": "Customers"
    }
  ],
  "timeout": "05:00:00",
  "retry_count": 2,
  "max_parallelism": 4
}
```

**Example 3: Clone a report to a different workspace**

```json
{
  "report_id": "5b218778-e7a5-4d73-8187-f10824047715",
  "name": "Sales Report - Q4 Copy",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "target_workspace_id": "3d9b93c6-7b6d-4801-a491-1738910904fd",
  "target_dataset_id": "cfafbeb1-8037-4d0c-896e-a46fb27ff229"
}
```

**Example 4: Export a report to PDF**

```json
{
  "report_id": "5b218778-e7a5-4d73-8187-f10824047715",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "format": "PDF"
}
```

**Example 5: Execute a DAX query**

```json
{
  "dataset_id": "cfafbeb1-8037-4d0c-896e-a46fb27ff229",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "queries": [
    {
      "query": "EVALUATE TOPN(10, Sales)"
    }
  ]
}
```

**Example 6: Get dashboard tiles**

```json
{
  "dashboard_id": "69ffaa6c-b36d-4d01-96f5-1ed67c64d4af",
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48"
}
```

**Example 7: Import a generated PBIX file**

Attach the file through Autohive's file input and run:

```json
{
  "file": {
    "content": "<base64 supplied by the platform>",
    "name": "Quarterly Sales.pbix",
    "contentType": "application/octet-stream"
  },
  "workspace_id": "f089354e-8366-4e18-aea3-4cb4a3a50b48",
  "name_conflict": "CreateOrOverwrite"
}
```

Use the returned `import_id` with `get_import_status`. Do not ask the model to paste a large file as base64; attach or generate the file so the platform hydrates the file input.

## Testing

To run the mocked unit tests from the repository root:

```bash
pytest powerbi/tests/test_powerbi_unit.py -m unit
```

## Additional Notes

- All workspace-related actions support both "My workspace" (default) and specific workspaces by providing the `workspace_id` parameter
- Dataset refresh operations are asynchronous - use `get_refresh_history` to check the status
- Report export operations are also asynchronous - use `get_export_status` to monitor progress
- Report imports can be asynchronous - use `get_import_status` to monitor progress
- DAX queries require appropriate permissions and the dataset must support query operations
- The integration uses the Power BI REST API v1.0
- Files between 1 GB and 10 GB require Power BI's Premium-capacity temporary upload workflow, which is not exposed by `import_powerbi_file`

## Official API Documentation

- [Post Import In Group](https://learn.microsoft.com/en-us/rest/api/power-bi/imports/post-import-in-group)
- [Get Import In Group](https://learn.microsoft.com/en-us/rest/api/power-bi/imports/get-import-in-group)
- [Clone Report In Group](https://learn.microsoft.com/en-us/rest/api/power-bi/reports/clone-report-in-group)
- [Microsoft Fabric Create Report](https://learn.microsoft.com/en-us/rest/api/fabric/report/items/create-report)
- [Microsoft Fabric report definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/report-definition)
