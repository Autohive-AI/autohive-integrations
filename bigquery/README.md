# Google BigQuery Integration

Google BigQuery integration for serverless data warehouse operations, SQL queries, and dataset management.

## Overview

BigQuery is Google Cloud's fully managed, serverless data warehouse that enables scalable analysis over petabytes of data. This integration provides comprehensive access to BigQuery's capabilities including:

- **Query Execution**: Run SQL queries with standard or legacy SQL dialect
- **Dataset Management**: Create, list, get, and delete datasets
- **Table Operations**: Full CRUD operations for tables with schema management
- **Data Streaming**: Insert rows using the streaming insert API
- **Job Management**: Monitor and retrieve query job results

## Authentication

This integration uses Google OAuth2 platform authentication. You'll need to authorize with the following scope:

- `https://www.googleapis.com/auth/bigquery` - Full access to BigQuery

## Actions

### Query Operations

| Action | Description |
|--------|-------------|
| `run_query` | Execute a SQL query against BigQuery with optional dry run |
| `get_query_results` | Retrieve results from a completed query job with pagination |

### Dataset Management

| Action | Description |
|--------|-------------|
| `list_datasets` | List all datasets in a project |
| `get_dataset` | Get metadata for a specific dataset |
| `create_dataset` | Create a new dataset with location and labels |
| `delete_dataset` | Delete a dataset (optionally with all contents) |

### Table Operations

| Action | Description |
|--------|-------------|
| `list_tables` | List all tables in a dataset |
| `get_table` | Get table metadata and schema |
| `create_table` | Create a new table with schema, partitioning, and clustering |
| `delete_table` | Delete a table |
| `insert_rows` | Stream rows into a table using streaming insert |

### Job Management

| Action | Description |
|--------|-------------|
| `list_jobs` | List recent BigQuery jobs with filtering |
| `get_job` | Get details of a specific job |

### Project Discovery

| Action | Description |
|--------|-------------|
| `list_projects` | List all projects the user has access to |

## Example Usage

### Run a SQL Query

```python
inputs = {
    "project_id": "my-gcp-project",
    "query": """
        SELECT name, SUM(number) as total
        FROM `bigquery-public-data.usa_names.usa_1910_current`
        WHERE state = 'CA'
        GROUP BY name
        ORDER BY total DESC
        LIMIT 10
    """,
    "max_results": 100
}

result = await bigquery.execute_action("run_query", inputs, context)

for row in result["rows"]:
    print(f"{row['name']}: {row['total']}")
```

### Dry Run to Estimate Query Cost

```python
inputs = {
    "project_id": "my-gcp-project",
    "query": "SELECT * FROM `my-dataset.large_table`",
    "dry_run": True
}

result = await bigquery.execute_action("run_query", inputs, context)
bytes_processed = result["total_bytes_processed"]
estimated_cost = (bytes_processed / (1024**4)) * 5  # $5 per TB
print(f"Estimated cost: ${estimated_cost:.4f}")
```

### Create a Dataset

```python
inputs = {
    "project_id": "my-gcp-project",
    "dataset_id": "analytics_data",
    "location": "US",
    "description": "Analytics data warehouse",
    "labels": {
        "environment": "production",
        "team": "data-engineering"
    }
}

result = await bigquery.execute_action("create_dataset", inputs, context)
print(f"Created dataset: {result['dataset']['dataset_id']}")
```

### Create a Table with Schema

```python
inputs = {
    "project_id": "my-gcp-project",
    "dataset_id": "analytics_data",
    "table_id": "user_events",
    "schema": {
        "fields": [
            {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "user_id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "event_type", "type": "STRING", "mode": "NULLABLE"},
            {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "properties", "type": "JSON", "mode": "NULLABLE"}
        ]
    },
    "time_partitioning": {
        "type": "DAY",
        "field": "event_timestamp"
    },
    "clustering": {
        "fields": ["user_id", "event_type"]
    }
}

result = await bigquery.execute_action("create_table", inputs, context)
```

### Stream Data into a Table

```python
inputs = {
    "project_id": "my-gcp-project",
    "dataset_id": "analytics_data",
    "table_id": "user_events",
    "rows": [
        {
            "event_id": "evt_001",
            "user_id": "user_123",
            "event_type": "page_view",
            "event_timestamp": "2024-01-15T10:30:00Z"
        },
        {
            "event_id": "evt_002",
            "user_id": "user_456",
            "event_type": "purchase",
            "event_timestamp": "2024-01-15T10:31:00Z"
        }
    ]
}

result = await bigquery.execute_action("insert_rows", inputs, context)
print(f"Inserted {result['inserted_count']} rows")
```

### Handle Large Query Results with Pagination

```python
# Initial query
inputs = {
    "project_id": "my-gcp-project",
    "query": "SELECT * FROM `my-dataset.large_table`",
    "max_results": 1000
}

result = await bigquery.execute_action("run_query", inputs, context)
all_rows = result["rows"]

# Fetch remaining pages
while result.get("page_token"):
    result = await bigquery.execute_action(
        "get_query_results",
        {
            "project_id": "my-gcp-project",
            "job_id": result["job_id"],
            "page_token": result["page_token"],
            "max_results": 1000
        },
        context
    )
    all_rows.extend(result["rows"])

print(f"Total rows retrieved: {len(all_rows)}")
```

### Monitor Job Status

```python
# List recent jobs
inputs = {
    "project_id": "my-gcp-project",
    "max_results": 10,
    "state_filter": "running"
}

result = await bigquery.execute_action("list_jobs", inputs, context)
for job in result["jobs"]:
    print(f"Job {job['job_id']}: {job['state']}")
```

## Data Types

BigQuery supports the following data types for table schemas:

| Type | Description |
|------|-------------|
| `STRING` | Variable-length character data |
| `BYTES` | Variable-length binary data |
| `INTEGER` / `INT64` | 64-bit signed integer |
| `FLOAT` / `FLOAT64` | Double-precision floating-point |
| `BOOLEAN` / `BOOL` | True or false |
| `TIMESTAMP` | Absolute point in time with microsecond precision |
| `DATE` | Calendar date |
| `TIME` | Time of day |
| `DATETIME` | Date and time without timezone |
| `GEOGRAPHY` | Geographic point, line, or polygon |
| `NUMERIC` / `BIGNUMERIC` | Precise numeric values |
| `JSON` | JSON data (semi-structured) |
| `RECORD` / `STRUCT` | Nested fields |

Field modes: `NULLABLE` (default), `REQUIRED`, `REPEATED` (array)

## Resources

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax)
- [BigQuery REST API](https://cloud.google.com/bigquery/docs/reference/rest)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [Public Datasets](https://cloud.google.com/bigquery/public-data)
