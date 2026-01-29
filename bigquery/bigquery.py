from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode

# Create the integration using the config.json
bigquery = Integration.load()

# Base URL for BigQuery API v2
BIGQUERY_API_BASE = "https://bigquery.googleapis.com/bigquery/v2"


def parse_rows(schema: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert BigQuery row format to list of dictionaries."""
    if not rows or not schema:
        return []

    fields = schema.get("fields", [])
    parsed_rows = []

    for row in rows:
        parsed_row = {}
        values = row.get("f", [])
        for i, field in enumerate(fields):
            field_name = field.get("name", f"field_{i}")
            if i < len(values):
                value = values[i].get("v")
                # Handle nested/repeated fields
                if field.get("type") == "RECORD" and value:
                    nested_schema = {"fields": field.get("fields", [])}
                    if field.get("mode") == "REPEATED":
                        parsed_row[field_name] = [
                            parse_rows(nested_schema, [{"f": v.get("v", {}).get("f", [])}])[0]
                            if v.get("v") else None
                            for v in value
                        ]
                    else:
                        parsed_row[field_name] = parse_rows(nested_schema, [{"f": value.get("f", [])}])[0] if value else None
                elif field.get("mode") == "REPEATED" and value:
                    parsed_row[field_name] = [v.get("v") for v in value]
                else:
                    parsed_row[field_name] = value
            else:
                parsed_row[field_name] = None
        parsed_rows.append(parsed_row)

    return parsed_rows


def format_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Format schema for cleaner output."""
    if not schema:
        return {}

    fields = schema.get("fields", [])
    formatted_fields = []
    for field in fields:
        formatted_field = {
            "name": field.get("name"),
            "type": field.get("type"),
            "mode": field.get("mode", "NULLABLE")
        }
        if field.get("description"):
            formatted_field["description"] = field["description"]
        if field.get("fields"):
            formatted_field["fields"] = format_schema({"fields": field["fields"]})["fields"]
        formatted_fields.append(formatted_field)

    return {"fields": formatted_fields}


# ---- Query Actions ----

@bigquery.action("run_query")
class RunQueryAction(ActionHandler):
    """Execute a SQL query against BigQuery."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            query = inputs["query"]
            use_legacy_sql = inputs.get("use_legacy_sql", False)
            max_results = inputs.get("max_results", 1000)
            timeout_ms = inputs.get("timeout_ms", 30000)
            dry_run = inputs.get("dry_run", False)

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/queries"

            payload = {
                "query": query,
                "useLegacySql": use_legacy_sql,
                "maxResults": max_results,
                "timeoutMs": timeout_ms,
                "dryRun": dry_run
            }

            response = await context.fetch(
                url,
                method="POST",
                json=payload
            )

            # Handle dry run response
            if dry_run:
                return ActionResult(
                    data={
                        "rows": [],
                        "total_rows": 0,
                        "total_bytes_processed": int(response.get("totalBytesProcessed", 0)),
                        "job_complete": True,
                        "dry_run": True,
                        "result": True
                    },
                    cost_usd=0.0
                )

            # Parse the response
            schema = response.get("schema", {})
            rows = parse_rows(schema, response.get("rows", []))
            job_complete = response.get("jobComplete", False)
            job_reference = response.get("jobReference", {})

            result_data = {
                "rows": rows,
                "total_rows": int(response.get("totalRows", 0)) if response.get("totalRows") else len(rows),
                "schema": format_schema(schema),
                "job_id": job_reference.get("jobId"),
                "job_complete": job_complete,
                "total_bytes_processed": int(response.get("totalBytesProcessed", 0)) if response.get("totalBytesProcessed") else None,
                "cache_hit": response.get("cacheHit"),
                "result": True
            }

            # Add page token if more results available
            if response.get("pageToken"):
                result_data["page_token"] = response["pageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"rows": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("get_query_results")
class GetQueryResultsAction(ActionHandler):
    """Retrieve results from a completed query job."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            job_id = inputs["job_id"]
            max_results = inputs.get("max_results")
            page_token = inputs.get("page_token")
            start_index = inputs.get("start_index")

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/queries/{job_id}"

            params = {}
            if max_results:
                params["maxResults"] = max_results
            if page_token:
                params["pageToken"] = page_token
            if start_index is not None:
                params["startIndex"] = start_index

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            schema = response.get("schema", {})
            rows = parse_rows(schema, response.get("rows", []))

            result_data = {
                "rows": rows,
                "total_rows": int(response.get("totalRows", 0)) if response.get("totalRows") else len(rows),
                "schema": format_schema(schema),
                "job_complete": response.get("jobComplete", False),
                "result": True
            }

            if response.get("pageToken"):
                result_data["page_token"] = response["pageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"rows": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Dataset Actions ----

@bigquery.action("list_datasets")
class ListDatasetsAction(ActionHandler):
    """List all datasets in a project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            max_results = inputs.get("max_results")
            page_token = inputs.get("page_token")
            filter_expr = inputs.get("filter")
            all_datasets = inputs.get("all", False)

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets"

            params = {}
            if max_results:
                params["maxResults"] = max_results
            if page_token:
                params["pageToken"] = page_token
            if filter_expr:
                params["filter"] = filter_expr
            if all_datasets:
                params["all"] = "true"

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            datasets = []
            for ds in response.get("datasets", []):
                dataset_ref = ds.get("datasetReference", {})
                datasets.append({
                    "id": ds.get("id"),
                    "dataset_id": dataset_ref.get("datasetId"),
                    "project_id": dataset_ref.get("projectId"),
                    "friendly_name": ds.get("friendlyName"),
                    "location": ds.get("location"),
                    "labels": ds.get("labels", {})
                })

            result_data = {
                "datasets": datasets,
                "result": True
            }

            if response.get("nextPageToken"):
                result_data["next_page_token"] = response["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"datasets": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("get_dataset")
class GetDatasetAction(ActionHandler):
    """Get metadata for a specific dataset."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}"

            response = await context.fetch(url, method="GET")

            dataset_ref = response.get("datasetReference", {})
            dataset = {
                "id": response.get("id"),
                "dataset_id": dataset_ref.get("datasetId"),
                "project_id": dataset_ref.get("projectId"),
                "friendly_name": response.get("friendlyName"),
                "description": response.get("description"),
                "location": response.get("location"),
                "creation_time": response.get("creationTime"),
                "last_modified_time": response.get("lastModifiedTime"),
                "default_table_expiration_ms": response.get("defaultTableExpirationMs"),
                "default_partition_expiration_ms": response.get("defaultPartitionExpirationMs"),
                "labels": response.get("labels", {}),
                "access": response.get("access", [])
            }

            return ActionResult(
                data={"dataset": dataset, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"dataset": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("create_dataset")
class CreateDatasetAction(ActionHandler):
    """Create a new dataset in the project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            location = inputs.get("location", "US")
            description = inputs.get("description")
            default_table_expiration_ms = inputs.get("default_table_expiration_ms")
            labels = inputs.get("labels", {})

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets"

            payload = {
                "datasetReference": {
                    "projectId": project_id,
                    "datasetId": dataset_id
                },
                "location": location
            }

            if description:
                payload["description"] = description
            if default_table_expiration_ms:
                payload["defaultTableExpirationMs"] = str(default_table_expiration_ms)
            if labels:
                payload["labels"] = labels

            response = await context.fetch(
                url,
                method="POST",
                json=payload
            )

            dataset_ref = response.get("datasetReference", {})
            dataset = {
                "id": response.get("id"),
                "dataset_id": dataset_ref.get("datasetId"),
                "project_id": dataset_ref.get("projectId"),
                "location": response.get("location"),
                "creation_time": response.get("creationTime")
            }

            return ActionResult(
                data={"dataset": dataset, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"dataset": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("delete_dataset")
class DeleteDatasetAction(ActionHandler):
    """Delete a dataset from the project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            delete_contents = inputs.get("delete_contents", False)

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}"

            params = {}
            if delete_contents:
                params["deleteContents"] = "true"

            await context.fetch(
                url,
                method="DELETE",
                params=params if params else None
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Table Actions ----

@bigquery.action("list_tables")
class ListTablesAction(ActionHandler):
    """List all tables in a dataset."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            max_results = inputs.get("max_results")
            page_token = inputs.get("page_token")

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}/tables"

            params = {}
            if max_results:
                params["maxResults"] = max_results
            if page_token:
                params["pageToken"] = page_token

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            tables = []
            for tbl in response.get("tables", []):
                table_ref = tbl.get("tableReference", {})
                tables.append({
                    "id": tbl.get("id"),
                    "table_id": table_ref.get("tableId"),
                    "dataset_id": table_ref.get("datasetId"),
                    "project_id": table_ref.get("projectId"),
                    "type": tbl.get("type"),
                    "friendly_name": tbl.get("friendlyName"),
                    "creation_time": tbl.get("creationTime"),
                    "expiration_time": tbl.get("expirationTime"),
                    "labels": tbl.get("labels", {})
                })

            result_data = {
                "tables": tables,
                "total_items": response.get("totalItems"),
                "result": True
            }

            if response.get("nextPageToken"):
                result_data["next_page_token"] = response["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"tables": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("get_table")
class GetTableAction(ActionHandler):
    """Get metadata and schema for a specific table."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            table_id = inputs["table_id"]

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"

            response = await context.fetch(url, method="GET")

            table_ref = response.get("tableReference", {})
            table = {
                "id": response.get("id"),
                "table_id": table_ref.get("tableId"),
                "dataset_id": table_ref.get("datasetId"),
                "project_id": table_ref.get("projectId"),
                "type": response.get("type"),
                "friendly_name": response.get("friendlyName"),
                "description": response.get("description"),
                "schema": format_schema(response.get("schema", {})),
                "num_rows": response.get("numRows"),
                "num_bytes": response.get("numBytes"),
                "creation_time": response.get("creationTime"),
                "last_modified_time": response.get("lastModifiedTime"),
                "expiration_time": response.get("expirationTime"),
                "location": response.get("location"),
                "streaming_buffer": response.get("streamingBuffer"),
                "time_partitioning": response.get("timePartitioning"),
                "clustering": response.get("clustering"),
                "labels": response.get("labels", {})
            }

            return ActionResult(
                data={"table": table, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"table": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("create_table")
class CreateTableAction(ActionHandler):
    """Create a new table in a dataset."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            table_id = inputs["table_id"]
            schema = inputs["schema"]
            description = inputs.get("description")
            expiration_time = inputs.get("expiration_time")
            time_partitioning = inputs.get("time_partitioning")
            clustering = inputs.get("clustering")
            labels = inputs.get("labels", {})

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}/tables"

            payload = {
                "tableReference": {
                    "projectId": project_id,
                    "datasetId": dataset_id,
                    "tableId": table_id
                },
                "schema": schema
            }

            if description:
                payload["description"] = description
            if expiration_time:
                payload["expirationTime"] = str(expiration_time)
            if time_partitioning:
                payload["timePartitioning"] = time_partitioning
            if clustering:
                payload["clustering"] = clustering
            if labels:
                payload["labels"] = labels

            response = await context.fetch(
                url,
                method="POST",
                json=payload
            )

            table_ref = response.get("tableReference", {})
            table = {
                "id": response.get("id"),
                "table_id": table_ref.get("tableId"),
                "dataset_id": table_ref.get("datasetId"),
                "project_id": table_ref.get("projectId"),
                "schema": format_schema(response.get("schema", {})),
                "creation_time": response.get("creationTime")
            }

            return ActionResult(
                data={"table": table, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"table": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("delete_table")
class DeleteTableAction(ActionHandler):
    """Delete a table from a dataset."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            table_id = inputs["table_id"]

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"

            await context.fetch(url, method="DELETE")

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("insert_rows")
class InsertRowsAction(ActionHandler):
    """Stream rows into a table using the streaming insert API."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]
            table_id = inputs["table_id"]
            rows = inputs["rows"]
            skip_invalid_rows = inputs.get("skip_invalid_rows", False)
            ignore_unknown_values = inputs.get("ignore_unknown_values", False)

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/insertAll"

            # Format rows for BigQuery streaming insert
            formatted_rows = [{"json": row} for row in rows]

            payload = {
                "rows": formatted_rows,
                "skipInvalidRows": skip_invalid_rows,
                "ignoreUnknownValues": ignore_unknown_values
            }

            response = await context.fetch(
                url,
                method="POST",
                json=payload
            )

            insert_errors = response.get("insertErrors", [])
            inserted_count = len(rows) - len(insert_errors)

            # Format errors for output
            formatted_errors = []
            for error in insert_errors:
                formatted_errors.append({
                    "index": error.get("index"),
                    "errors": error.get("errors", [])
                })

            return ActionResult(
                data={
                    "inserted_count": inserted_count,
                    "insert_errors": formatted_errors,
                    "result": len(insert_errors) == 0
                },
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"inserted_count": 0, "insert_errors": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Job Actions ----

@bigquery.action("list_jobs")
class ListJobsAction(ActionHandler):
    """List recent BigQuery jobs in the project."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            max_results = inputs.get("max_results")
            page_token = inputs.get("page_token")
            all_users = inputs.get("all_users", False)
            state_filter = inputs.get("state_filter")
            min_creation_time = inputs.get("min_creation_time")
            max_creation_time = inputs.get("max_creation_time")

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/jobs"

            params = {}
            if max_results:
                params["maxResults"] = max_results
            if page_token:
                params["pageToken"] = page_token
            if all_users:
                params["allUsers"] = "true"
            if state_filter:
                params["stateFilter"] = state_filter
            if min_creation_time:
                params["minCreationTime"] = str(min_creation_time)
            if max_creation_time:
                params["maxCreationTime"] = str(max_creation_time)

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            jobs = []
            for job in response.get("jobs", []):
                job_ref = job.get("jobReference", {})
                status = job.get("status", {})
                statistics = job.get("statistics", {})

                jobs.append({
                    "id": job.get("id"),
                    "job_id": job_ref.get("jobId"),
                    "project_id": job_ref.get("projectId"),
                    "location": job_ref.get("location"),
                    "state": status.get("state"),
                    "error_result": status.get("errorResult"),
                    "creation_time": statistics.get("creationTime"),
                    "start_time": statistics.get("startTime"),
                    "end_time": statistics.get("endTime"),
                    "total_bytes_processed": statistics.get("totalBytesProcessed"),
                    "user_email": job.get("user_email")
                })

            result_data = {
                "jobs": jobs,
                "result": True
            }

            if response.get("nextPageToken"):
                result_data["next_page_token"] = response["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"jobs": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@bigquery.action("get_job")
class GetJobAction(ActionHandler):
    """Get details of a specific job."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            job_id = inputs["job_id"]
            location = inputs.get("location")

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/jobs/{job_id}"

            params = {}
            if location:
                params["location"] = location

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            job_ref = response.get("jobReference", {})
            status = response.get("status", {})
            statistics = response.get("statistics", {})
            configuration = response.get("configuration", {})

            job = {
                "id": response.get("id"),
                "job_id": job_ref.get("jobId"),
                "project_id": job_ref.get("projectId"),
                "location": job_ref.get("location"),
                "state": status.get("state"),
                "error_result": status.get("errorResult"),
                "errors": status.get("errors", []),
                "creation_time": statistics.get("creationTime"),
                "start_time": statistics.get("startTime"),
                "end_time": statistics.get("endTime"),
                "total_bytes_processed": statistics.get("totalBytesProcessed"),
                "total_bytes_billed": statistics.get("query", {}).get("totalBytesBilled"),
                "cache_hit": statistics.get("query", {}).get("cacheHit"),
                "configuration": configuration,
                "user_email": response.get("user_email")
            }

            return ActionResult(
                data={"job": job, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"job": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Project Actions ----

@bigquery.action("list_projects")
class ListProjectsAction(ActionHandler):
    """List all projects the user has access to."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            max_results = inputs.get("max_results")
            page_token = inputs.get("page_token")

            url = f"{BIGQUERY_API_BASE}/projects"

            params = {}
            if max_results:
                params["maxResults"] = max_results
            if page_token:
                params["pageToken"] = page_token

            response = await context.fetch(
                url,
                method="GET",
                params=params if params else None
            )

            projects = []
            for proj in response.get("projects", []):
                project_ref = proj.get("projectReference", {})
                projects.append({
                    "id": proj.get("id"),
                    "project_id": project_ref.get("projectId"),
                    "numeric_id": proj.get("numericId"),
                    "friendly_name": proj.get("friendlyName")
                })

            result_data = {
                "projects": projects,
                "result": True
            }

            if response.get("nextPageToken"):
                result_data["next_page_token"] = response["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionResult(
                data={"projects": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )
