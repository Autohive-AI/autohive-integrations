from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any, List

# Create the integration using the config.json
bigquery = Integration.load()

# Base URL for BigQuery API v2
BIGQUERY_API_BASE = "https://bigquery.googleapis.com/bigquery/v2"

# Maximum number of rows that can be retrieved in a single request
# This limit protects infrastructure from excessive memory usage
MAX_RESULTS_LIMIT = 10000


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
                            parse_rows(nested_schema, [{"f": v.get("v", {}).get("f", [])}])[0] if v.get("v") else None
                            for v in value
                        ]
                    else:
                        parsed_row[field_name] = (
                            parse_rows(nested_schema, [{"f": value.get("f", [])}])[0] if value else None
                        )
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
        formatted_field = {"name": field.get("name"), "type": field.get("type"), "mode": field.get("mode", "NULLABLE")}
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
            # Note: The query is provided by the user and executed as-is. This is
            # intentional for a data warehouse integration where users need full SQL
            # capabilities. BigQuery handles query execution securely on their end.
            query = inputs["query"]
            use_legacy_sql = inputs.get("use_legacy_sql", False)
            max_results = min(inputs.get("max_results", 1000), MAX_RESULTS_LIMIT)
            timeout_ms = inputs.get("timeout_ms", 30000)
            dry_run = inputs.get("dry_run", False)
            location = inputs.get("location")

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/queries"

            payload = {
                "query": query,
                "useLegacySql": use_legacy_sql,
                "maxResults": max_results,
                "timeoutMs": timeout_ms,
                "dryRun": dry_run,
            }

            if location:
                payload["location"] = location

            response = await context.fetch(url, method="POST", json=payload)
            body = response.data

            # Handle dry run response
            if dry_run:
                return ActionResult(
                    data={
                        "rows": [],
                        "total_rows": 0,
                        "total_bytes_processed": int(body.get("totalBytesProcessed", 0)),
                        "job_complete": True,
                        "dry_run": True,
                    },
                    cost_usd=0.0,
                )

            # Surface a query that completed but failed at runtime. BigQuery can
            # return HTTP 200 with an `errors` list instead of an error status.
            # That list can also carry non-fatal warnings on a successful query,
            # so only treat it as a failure when the job completed with no result
            # set (no schema and no rows) to return.
            errors = body.get("errors")
            if body.get("jobComplete") and errors and not body.get("rows") and not body.get("schema"):
                first = errors[0] if isinstance(errors, list) and errors else {}
                return ActionError(message=first.get("message") or str(errors))

            # Parse the response
            schema = body.get("schema", {})
            rows = parse_rows(schema, body.get("rows", []))
            job_complete = body.get("jobComplete", False)
            job_reference = body.get("jobReference", {})

            result_data = {
                "rows": rows,
                "total_rows": int(body.get("totalRows", 0)) if body.get("totalRows") else len(rows),
                "schema": format_schema(schema),
                "job_id": job_reference.get("jobId"),
                "job_complete": job_complete,
                "total_bytes_processed": (
                    int(body.get("totalBytesProcessed", 0)) if body.get("totalBytesProcessed") else None
                ),
                "cache_hit": body.get("cacheHit"),
            }

            # Add page token if more results available
            if body.get("pageToken"):
                result_data["page_token"] = body["pageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                params["maxResults"] = min(max_results, MAX_RESULTS_LIMIT)
            if page_token:
                params["pageToken"] = page_token
            if start_index is not None:
                params["startIndex"] = start_index

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            # Surface a query that completed but failed at runtime. BigQuery can
            # return HTTP 200 with an `errors` list instead of an error status.
            # That list can also carry non-fatal warnings on a successful query,
            # so only treat it as a failure when the job completed with no result
            # set (no schema and no rows) to return.
            errors = body.get("errors")
            if body.get("jobComplete") and errors and not body.get("rows") and not body.get("schema"):
                first = errors[0] if isinstance(errors, list) and errors else {}
                return ActionError(message=first.get("message") or str(errors))

            schema = body.get("schema", {})
            rows = parse_rows(schema, body.get("rows", []))

            result_data = {
                "rows": rows,
                "total_rows": int(body.get("totalRows", 0)) if body.get("totalRows") else len(rows),
                "schema": format_schema(schema),
                "job_complete": body.get("jobComplete", False),
            }

            if body.get("pageToken"):
                result_data["page_token"] = body["pageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            datasets = []
            for ds in body.get("datasets", []):
                dataset_ref = ds.get("datasetReference", {})
                datasets.append(
                    {
                        "id": ds.get("id"),
                        "dataset_id": dataset_ref.get("datasetId"),
                        "project_id": dataset_ref.get("projectId"),
                        "friendly_name": ds.get("friendlyName"),
                        "location": ds.get("location"),
                        "labels": ds.get("labels", {}),
                    }
                )

            result_data = {"datasets": datasets}

            if body.get("nextPageToken"):
                result_data["next_page_token"] = body["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@bigquery.action("get_dataset")
class GetDatasetAction(ActionHandler):
    """Get metadata for a specific dataset."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            project_id = inputs["project_id"]
            dataset_id = inputs["dataset_id"]

            url = f"{BIGQUERY_API_BASE}/projects/{project_id}/datasets/{dataset_id}"

            response = await context.fetch(url, method="GET")
            body = response.data

            dataset_ref = body.get("datasetReference", {})
            dataset = {
                "id": body.get("id"),
                "dataset_id": dataset_ref.get("datasetId"),
                "project_id": dataset_ref.get("projectId"),
                "friendly_name": body.get("friendlyName"),
                "description": body.get("description"),
                "location": body.get("location"),
                "creation_time": body.get("creationTime"),
                "last_modified_time": body.get("lastModifiedTime"),
                "default_table_expiration_ms": body.get("defaultTableExpirationMs"),
                "default_partition_expiration_ms": body.get("defaultPartitionExpirationMs"),
                "labels": body.get("labels", {}),
                "access": body.get("access", []),
            }

            return ActionResult(data={"dataset": dataset}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            payload = {"datasetReference": {"projectId": project_id, "datasetId": dataset_id}, "location": location}

            if description:
                payload["description"] = description
            if default_table_expiration_ms:
                payload["defaultTableExpirationMs"] = str(default_table_expiration_ms)
            if labels:
                payload["labels"] = labels

            response = await context.fetch(url, method="POST", json=payload)
            body = response.data

            dataset_ref = body.get("datasetReference", {})
            dataset = {
                "id": body.get("id"),
                "dataset_id": dataset_ref.get("datasetId"),
                "project_id": dataset_ref.get("projectId"),
                "location": body.get("location"),
                "creation_time": body.get("creationTime"),
            }

            return ActionResult(data={"dataset": dataset}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            await context.fetch(url, method="DELETE", params=params if params else None)

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            tables = []
            for tbl in body.get("tables", []):
                table_ref = tbl.get("tableReference", {})
                tables.append(
                    {
                        "id": tbl.get("id"),
                        "table_id": table_ref.get("tableId"),
                        "dataset_id": table_ref.get("datasetId"),
                        "project_id": table_ref.get("projectId"),
                        "type": tbl.get("type"),
                        "friendly_name": tbl.get("friendlyName"),
                        "creation_time": tbl.get("creationTime"),
                        "expiration_time": tbl.get("expirationTime"),
                        "labels": tbl.get("labels", {}),
                    }
                )

            result_data = {"tables": tables, "total_items": body.get("totalItems")}

            if body.get("nextPageToken"):
                result_data["next_page_token"] = body["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
            body = response.data

            table_ref = body.get("tableReference", {})
            table = {
                "id": body.get("id"),
                "table_id": table_ref.get("tableId"),
                "dataset_id": table_ref.get("datasetId"),
                "project_id": table_ref.get("projectId"),
                "type": body.get("type"),
                "friendly_name": body.get("friendlyName"),
                "description": body.get("description"),
                "schema": format_schema(body.get("schema", {})),
                "num_rows": body.get("numRows"),
                "num_bytes": body.get("numBytes"),
                "creation_time": body.get("creationTime"),
                "last_modified_time": body.get("lastModifiedTime"),
                "expiration_time": body.get("expirationTime"),
                "location": body.get("location"),
                "streaming_buffer": body.get("streamingBuffer"),
                "time_partitioning": body.get("timePartitioning"),
                "clustering": body.get("clustering"),
                "labels": body.get("labels", {}),
            }

            return ActionResult(data={"table": table}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                "tableReference": {"projectId": project_id, "datasetId": dataset_id, "tableId": table_id},
                "schema": schema,
            }

            if description:
                payload["description"] = description
            if expiration_time:
                payload["expirationTime"] = str(expiration_time)
            if time_partitioning:
                # Convert snake_case keys to camelCase for BigQuery API
                tp = {}
                if "type" in time_partitioning:
                    tp["type"] = time_partitioning["type"]
                if "field" in time_partitioning:
                    tp["field"] = time_partitioning["field"]
                if "expiration_ms" in time_partitioning:
                    tp["expirationMs"] = str(time_partitioning["expiration_ms"])
                payload["timePartitioning"] = tp
            if clustering:
                payload["clustering"] = clustering
            if labels:
                payload["labels"] = labels

            response = await context.fetch(url, method="POST", json=payload)
            body = response.data

            table_ref = body.get("tableReference", {})
            table = {
                "id": body.get("id"),
                "table_id": table_ref.get("tableId"),
                "dataset_id": table_ref.get("datasetId"),
                "project_id": table_ref.get("projectId"),
                "schema": format_schema(body.get("schema", {})),
                "creation_time": body.get("creationTime"),
            }

            return ActionResult(data={"table": table}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            return ActionResult(data={"deleted": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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
                "ignoreUnknownValues": ignore_unknown_values,
            }

            response = await context.fetch(url, method="POST", json=payload)
            body = response.data

            insert_errors = body.get("insertErrors", [])

            # Format errors for output
            formatted_errors = []
            for error in insert_errors:
                formatted_errors.append({"index": error.get("index"), "errors": error.get("errors", [])})

            def _first_error_detail():
                first = formatted_errors[0].get("errors") if formatted_errors else []
                if first and isinstance(first[0], dict):
                    return first[0].get("message")
                return None

            # insertAll returns HTTP 200 even when rows are rejected, so any
            # insertErrors entry must be inspected rather than treated as success.
            if insert_errors:
                if not skip_invalid_rows:
                    # With skipInvalidRows=false (the default) BigQuery fails the
                    # ENTIRE request if any row is invalid — zero rows are written,
                    # even though only some rows carry insertErrors entries. Surface
                    # that as a failure rather than a misleading partial success.
                    detail = _first_error_detail()
                    message = (
                        f"BigQuery rejected the insert; no rows were written "
                        f"({len(formatted_errors)} of {len(rows)} row(s) reported errors)"
                    )
                    if detail:
                        message += f": {detail}"
                    return ActionError(message=message)

                # skip_invalid_rows=True: valid rows are inserted and invalid ones
                # skipped, so a partial insert is meaningful. Count unique failed row
                # indices (a single row can carry multiple errors).
                failed_row_indices = set(error.get("index") for error in insert_errors)
                inserted_count = len(rows) - len(failed_row_indices)
                if inserted_count == 0:
                    detail = _first_error_detail()
                    message = f"BigQuery rejected all {len(rows)} row(s)"
                    if detail:
                        message += f": {detail}"
                    return ActionError(message=message)
                return ActionResult(
                    data={
                        "inserted_count": inserted_count,
                        "insert_errors": formatted_errors,
                    },
                    cost_usd=0.0,
                )

            return ActionResult(
                data={
                    "inserted_count": len(rows),
                    "insert_errors": [],
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


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

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            jobs = []
            for job in body.get("jobs", []):
                job_ref = job.get("jobReference", {})
                status = job.get("status", {})
                statistics = job.get("statistics", {})

                jobs.append(
                    {
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
                        # Note: user_email is snake_case in BigQuery API (exception to camelCase convention)
                        "user_email": job.get("user_email"),
                    }
                )

            result_data = {"jobs": jobs}

            if body.get("nextPageToken"):
                result_data["next_page_token"] = body["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            job_ref = body.get("jobReference", {})
            status = body.get("status", {})
            statistics = body.get("statistics", {})
            configuration = body.get("configuration", {})

            job = {
                "id": body.get("id"),
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
                # Note: user_email is snake_case in BigQuery API (exception to camelCase convention)
                "user_email": body.get("user_email"),
            }

            return ActionResult(data={"job": job}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


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

            response = await context.fetch(url, method="GET", params=params if params else None)
            body = response.data

            projects = []
            for proj in body.get("projects", []):
                project_ref = proj.get("projectReference", {})
                projects.append(
                    {
                        "id": proj.get("id"),
                        "project_id": project_ref.get("projectId"),
                        "numeric_id": proj.get("numericId"),
                        "friendly_name": proj.get("friendlyName"),
                    }
                )

            result_data = {"projects": projects}

            if body.get("nextPageToken"):
                result_data["next_page_token"] = body["nextPageToken"]

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))
