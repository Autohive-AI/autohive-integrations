import asyncio
import base64
import json
import uuid

from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any

# Create the integration using the config.json
powerbi = Integration.load()

# Power BI REST API Base URL
POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"

# Microsoft Fabric REST API Base URL (used for report creation)
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"

# ---- Action Handlers ----


@powerbi.action("list_workspaces")
class ListWorkspacesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}

            if inputs.get("filter"):
                params["$filter"] = inputs["filter"]

            if inputs.get("top"):
                params["$top"] = inputs["top"]

            response = await context.fetch(f"{POWERBI_API_BASE}/groups", params=params)

            workspaces = []
            for workspace in response.data.get("value", []):
                workspaces.append(
                    {
                        "id": workspace.get("id"),
                        "name": workspace.get("name"),
                        "isReadOnly": workspace.get("isReadOnly", False),
                        "isOnDedicatedCapacity": workspace.get("isOnDedicatedCapacity", False),
                        "type": workspace.get("type", "Workspace"),
                    }
                )

            return ActionResult(data={"workspaces": workspaces}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs["workspace_id"]

            response = await context.fetch(f"{POWERBI_API_BASE}/groups/{workspace_id}")

            return ActionResult(data={"workspace": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("list_datasets")
class ListDatasetsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets"
            else:
                url = f"{POWERBI_API_BASE}/datasets"

            response = await context.fetch(url)

            datasets = []
            for dataset in response.data.get("value", []):
                datasets.append(
                    {
                        "id": dataset.get("id"),
                        "name": dataset.get("name"),
                        "configuredBy": dataset.get("configuredBy"),
                        "isRefreshable": dataset.get("isRefreshable", False),
                        "isEffectiveIdentityRequired": dataset.get("isEffectiveIdentityRequired", False),
                        "isEffectiveIdentityRolesRequired": dataset.get("isEffectiveIdentityRolesRequired", False),
                        "isOnPremGatewayRequired": dataset.get("isOnPremGatewayRequired", False),
                    }
                )

            return ActionResult(data={"datasets": datasets}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_dataset")
class GetDatasetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dataset_id = inputs["dataset_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}"
            else:
                url = f"{POWERBI_API_BASE}/datasets/{dataset_id}"

            response = await context.fetch(url)

            return ActionResult(data={"dataset": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("refresh_dataset")
class RefreshDatasetAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dataset_id = inputs["dataset_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
            else:
                url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/refreshes"

            # Build refresh request with all optional parameters
            refresh_request = {}

            # Basic refresh parameter
            if inputs.get("notify_option"):
                refresh_request["notifyOption"] = inputs["notify_option"]

            # Enhanced refresh parameters
            if inputs.get("type"):
                refresh_request["type"] = inputs["type"]

            if inputs.get("commit_mode"):
                refresh_request["commitMode"] = inputs["commit_mode"]

            if inputs.get("max_parallelism") is not None:
                refresh_request["maxParallelism"] = inputs["max_parallelism"]

            if inputs.get("retry_count") is not None:
                refresh_request["retryCount"] = inputs["retry_count"]

            if inputs.get("objects"):
                refresh_request["objects"] = inputs["objects"]

            if inputs.get("apply_refresh_policy") is not None:
                refresh_request["applyRefreshPolicy"] = inputs["apply_refresh_policy"]

            if inputs.get("effective_date"):
                refresh_request["effectiveDate"] = inputs["effective_date"]

            if inputs.get("timeout"):
                refresh_request["timeout"] = inputs["timeout"]

            # If no parameters specified, default to basic refresh with NoNotification
            if not refresh_request:
                refresh_request["notifyOption"] = "NoNotification"

            response = await context.fetch(url, method="POST", json=refresh_request)

            # Extract request ID from response headers if available
            request_id = None
            if response.headers and "x-ms-request-id" in response.headers:
                request_id = response.headers["x-ms-request-id"]

            return ActionResult(
                data={"message": "Dataset refresh initiated successfully", "request_id": request_id},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_refresh_history")
class GetRefreshHistoryAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dataset_id = inputs["dataset_id"]
            workspace_id = inputs.get("workspace_id")
            top = inputs.get("top", 10)

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
            else:
                url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/refreshes"

            params = {"$top": top}

            response = await context.fetch(url, params=params)

            refreshes = []
            for refresh in response.data.get("value", []):
                refreshes.append(
                    {
                        "refreshType": refresh.get("refreshType"),
                        "startTime": refresh.get("startTime"),
                        "endTime": refresh.get("endTime"),
                        "status": refresh.get("status"),
                        "requestId": refresh.get("requestId"),
                    }
                )

            return ActionResult(data={"refreshes": refreshes}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("list_reports")
class ListReportsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports"
            else:
                url = f"{POWERBI_API_BASE}/reports"

            response = await context.fetch(url)

            reports = []
            for report in response.data.get("value", []):
                reports.append(
                    {
                        "id": report.get("id"),
                        "name": report.get("name"),
                        "webUrl": report.get("webUrl"),
                        "embedUrl": report.get("embedUrl"),
                        "datasetId": report.get("datasetId"),
                    }
                )

            return ActionResult(data={"reports": reports}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_report")
class GetReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}"
            else:
                url = f"{POWERBI_API_BASE}/reports/{report_id}"

            response = await context.fetch(url)

            return ActionResult(data={"report": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_report_datasources")
class GetReportDatasourcesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}/datasources"
            else:
                url = f"{POWERBI_API_BASE}/reports/{report_id}/datasources"

            response = await context.fetch(url)

            datasources = []
            for datasource in response.data.get("value", []):
                ds_data = {
                    "datasourceType": datasource.get("datasourceType"),
                    "datasourceId": datasource.get("datasourceId"),
                    "gatewayId": datasource.get("gatewayId"),
                    "name": datasource.get("name"),
                    "connectionString": datasource.get("connectionString"),
                }

                # Add connection details if present
                if datasource.get("connectionDetails"):
                    ds_data["connectionDetails"] = datasource.get("connectionDetails")

                datasources.append(ds_data)

            return ActionResult(data={"datasources": datasources}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("refresh_report")
class RefreshReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            workspace_id = inputs.get("workspace_id")
            notify_option = inputs.get("notify_option", "NoNotification")

            # First, get the report to find its dataset ID
            if workspace_id:
                report_url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}"
            else:
                report_url = f"{POWERBI_API_BASE}/reports/{report_id}"

            report_response = await context.fetch(report_url)
            report_data = report_response.data
            dataset_id = report_data.get("datasetId")

            if not dataset_id:
                return ActionError(message="Report does not have an associated dataset")

            # Now refresh the dataset
            if workspace_id:
                refresh_url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
            else:
                refresh_url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/refreshes"

            refresh_request = {"notifyOption": notify_option}

            await context.fetch(refresh_url, method="POST", json=refresh_request)

            return ActionResult(
                data={
                    "message": f"Dataset refresh initiated successfully for report '{report_data.get('name')}'",
                    "dataset_id": dataset_id,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("clone_report")
class CloneReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            name = inputs["name"]
            workspace_id = inputs.get("workspace_id")
            target_workspace_id = inputs.get("target_workspace_id")
            target_dataset_id = inputs.get("target_dataset_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}/Clone"
            else:
                url = f"{POWERBI_API_BASE}/reports/{report_id}/Clone"

            clone_request = {"name": name}

            if target_workspace_id:
                clone_request["targetWorkspaceId"] = target_workspace_id

            if target_dataset_id:
                clone_request["targetModelId"] = target_dataset_id

            response = await context.fetch(url, method="POST", json=clone_request)

            return ActionResult(
                data={
                    "id": response.data.get("id"),
                    "name": response.data.get("name"),
                    "webUrl": response.data.get("webUrl"),
                    "embedUrl": response.data.get("embedUrl"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("export_report")
class ExportReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            workspace_id = inputs.get("workspace_id")
            export_format = inputs.get("format", "PDF")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}/ExportTo"
            else:
                url = f"{POWERBI_API_BASE}/reports/{report_id}/ExportTo"

            export_request = {"format": export_format}

            response = await context.fetch(url, method="POST", json=export_request)

            return ActionResult(
                data={"export_id": response.data.get("id"), "message": "Export initiated successfully"},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_export_status")
class GetExportStatusAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            export_id = inputs["export_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/reports/{report_id}/exports/{export_id}"
            else:
                url = f"{POWERBI_API_BASE}/reports/{report_id}/exports/{export_id}"

            response = await context.fetch(url)

            return ActionResult(
                data={
                    "status": response.data.get("status"),
                    "percentComplete": response.data.get("percentComplete", 0),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("list_dashboards")
class ListDashboardsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/dashboards"
            else:
                url = f"{POWERBI_API_BASE}/dashboards"

            response = await context.fetch(url)

            dashboards = []
            for dashboard in response.data.get("value", []):
                dashboards.append(
                    {
                        "id": dashboard.get("id"),
                        "displayName": dashboard.get("displayName"),
                        "isReadOnly": dashboard.get("isReadOnly", False),
                        "embedUrl": dashboard.get("embedUrl"),
                    }
                )

            return ActionResult(data={"dashboards": dashboards}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_dashboard")
class GetDashboardAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dashboard_id = inputs["dashboard_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/dashboards/{dashboard_id}"
            else:
                url = f"{POWERBI_API_BASE}/dashboards/{dashboard_id}"

            response = await context.fetch(url)

            return ActionResult(data={"dashboard": response.data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("get_dashboard_tiles")
class GetDashboardTilesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dashboard_id = inputs["dashboard_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/dashboards/{dashboard_id}/tiles"
            else:
                url = f"{POWERBI_API_BASE}/dashboards/{dashboard_id}/tiles"

            response = await context.fetch(url)

            tiles = []
            for tile in response.data.get("value", []):
                tiles.append(
                    {
                        "id": tile.get("id"),
                        "title": tile.get("title"),
                        "embedUrl": tile.get("embedUrl"),
                        "datasetId": tile.get("datasetId"),
                        "reportId": tile.get("reportId"),
                    }
                )

            return ActionResult(data={"tiles": tiles}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("execute_queries")
class ExecuteQueriesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dataset_id = inputs["dataset_id"]
            workspace_id = inputs.get("workspace_id")
            queries = inputs["queries"]

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
            else:
                url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/executeQueries"

            query_request = {"queries": queries, "serializerSettings": {"includeNulls": True}}

            response = await context.fetch(url, method="POST", json=query_request)

            return ActionResult(data={"results": response.data.get("results", [])}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


def _find_by_unbracketed_name(row: dict, *candidates: str):
    """DAX EVALUATE results key each column as e.g. "[Name]" - match ignoring brackets."""
    for key, value in row.items():
        if key.strip("[]") in candidates:
            return value
    return None


async def _discover_schema_via_dax(context: ExecutionContext, workspace_id: str, dataset_id: str) -> dict:
    """Try INFO.TABLES()/INFO.COLUMNS() - only works on newer semantic model formats."""
    if workspace_id:
        url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
    else:
        url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/executeQueries"

    async def run_dax_query(dax: str) -> list:
        request = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
        response = await context.fetch(url, method="POST", json=request)
        results = response.data.get("results", [])
        if not results:
            return []
        tables = results[0].get("tables", [])
        return tables[0].get("rows", []) if tables else []

    table_rows = await run_dax_query("EVALUATE INFO.TABLES()")

    tables = []
    for row in table_rows:
        table_id = _find_by_unbracketed_name(row, "ID")
        table_name = _find_by_unbracketed_name(row, "Name")
        if table_name is None:
            continue
        tables.append({"id": table_id, "name": table_name, "columns": []})

    try:
        column_rows = await run_dax_query("EVALUATE INFO.COLUMNS()")
    except Exception:
        # Tables discovered but column metadata unavailable - still useful on its own.
        return {"tables": tables, "columns_available": False}

    columns_by_table_id = {}
    for row in column_rows:
        table_id = _find_by_unbracketed_name(row, "TableID")
        column_name = _find_by_unbracketed_name(row, "ExplicitName", "InferredName", "Name")
        if table_id is None or column_name is None:
            continue
        columns_by_table_id.setdefault(table_id, []).append(column_name)

    for table in tables:
        table["columns"] = columns_by_table_id.get(table["id"], [])

    return {"tables": tables, "columns_available": True}


async def _discover_schema_via_scanner(context: ExecutionContext, workspace_id: str, dataset_id: str) -> dict:
    """Fall back to the Admin Metadata Scanning API, which works regardless of semantic
    model format/DAX introspection support. Requires Tenant.Read.All/Tenant.ReadWrite.All
    (already in this integration's scopes) and, in most tenants, admin-level access."""
    scan_request = await context.fetch(
        f"{POWERBI_API_BASE}/admin/workspaces/getInfo",
        method="POST",
        params={"datasetSchema": "true", "datasetExpressions": "true", "lineage": "true"},
        json={"workspaces": [workspace_id]},
    )
    scan_id = scan_request.data.get("id")
    if not scan_id:
        raise RuntimeError("Admin metadata scan did not return a scan ID")

    status_url = f"{POWERBI_API_BASE}/admin/workspaces/scanStatus/{scan_id}"
    for _ in range(10):
        status_response = await context.fetch(status_url)
        status = status_response.data.get("status")
        if status == "Succeeded":
            break
        if status in ("Failed", "NotFound"):
            raise RuntimeError(f"Admin metadata scan {status.lower()}")
        await asyncio.sleep(2)
    else:
        raise RuntimeError("Admin metadata scan did not complete in time")

    result = await context.fetch(f"{POWERBI_API_BASE}/admin/workspaces/scanResult/{scan_id}")
    for workspace in result.data.get("workspaces", []):
        for dataset in workspace.get("datasets", []):
            if dataset.get("id") != dataset_id:
                continue
            tables = []
            for table in dataset.get("tables", []):
                columns = [c.get("name") for c in table.get("columns", []) if c.get("name")]
                columns += [m.get("name") for m in table.get("measures", []) if m.get("name")]
                tables.append({"id": None, "name": table.get("name"), "columns": columns})
            return {"tables": tables, "columns_available": True}

    raise RuntimeError("Dataset not found in admin metadata scan result")


@powerbi.action("get_dataset_schema")
class GetDatasetSchemaAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            dataset_id = inputs["dataset_id"]
            workspace_id = inputs.get("workspace_id")

            try:
                schema = await _discover_schema_via_dax(context, workspace_id, dataset_id)
                return ActionResult(data=schema, cost_usd=0.0)
            except Exception as dax_error:
                if not workspace_id:
                    return ActionError(
                        message=(
                            "This dataset does not support DAX schema introspection "
                            f"(INFO.TABLES() failed: {dax_error}), and the admin metadata scan fallback "
                            "requires a workspace_id (it doesn't work for My workspace). Pass workspace_id, "
                            "or use clone_report to build on an existing report's dataset bindings instead."
                        )
                    )

                try:
                    schema = await _discover_schema_via_scanner(context, workspace_id, dataset_id)
                    return ActionResult(data=schema, cost_usd=0.0)
                except Exception as scanner_error:
                    return ActionError(
                        message=(
                            "This dataset does not support DAX schema introspection "
                            f"(INFO.TABLES() failed: {dax_error}), and the admin metadata scan fallback also "
                            f"failed ({scanner_error}). The scanner fallback needs Tenant.Read.All/"
                            "Tenant.ReadWrite.All (already requested) plus tenant admin API access, which "
                            "this account may not have. Use clone_report to build on an existing report's "
                            "dataset bindings instead, or check the exact table/column names in Power BI "
                            "Desktop."
                        )
                    )

        except Exception as e:
            return ActionError(message=str(e))


# ---- Helpers for create_report ----


def _to_base64(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode("utf-8")).decode("utf-8")


_VISUAL_TYPE_MAP = {
    "table": "tableEx",
    "bar": "barChart",
    "bar_chart": "barChart",
    "line": "lineChart",
    "line_chart": "lineChart",
    "card": "card",
    "pie": "pieChart",
    "pie_chart": "pieChart",
    "column": "columnChart",
    "column_chart": "columnChart",
    "scatter": "scatterChart",
    "area": "areaChart",
    "donut": "donutChart",
    "matrix": "pivotTable",
}


def _build_visual_json(visual_id: str, spec: dict, x: float, y: float, width: float, height: float) -> dict:
    pbi_type = _VISUAL_TYPE_MAP.get(spec.get("type", "table").lower(), spec.get("type", "tableEx"))
    table = spec.get("table", "")
    columns = spec.get("columns", [])
    title = spec.get("title", "")

    # PBIR uses query.queryState with per-bucket projections (not prototypeQuery)
    query_state = {}

    if pbi_type in ("tableEx", "pivotTable"):
        query_state["Values"] = {
            "projections": [
                {
                    "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
                    "queryRef": f"{table}.{col}",
                    "active": True,
                }
                for col in columns
            ]
        }

    elif pbi_type == "card":
        if columns:
            col = columns[0]
            query_state["Values"] = {
                "projections": [
                    {
                        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
                        "queryRef": f"{table}.{col}",
                    }
                ]
            }

    else:
        # Charts: first column, category axis; remaining columns, Y axis (measures)
        if columns:
            cat = columns[0]
            query_state["Category"] = {
                "projections": [
                    {
                        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": cat}},
                        "queryRef": f"{table}.{cat}",
                        "active": True,
                    }
                ]
            }
            y_projections = [
                {
                    "field": {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
                    "queryRef": f"{table}.{col}",
                }
                for col in columns[1:]
            ]
            if y_projections:
                query_state["Y"] = {"projections": y_projections}

    visual_obj: dict = {
        "visualType": pbi_type,
        "query": {"queryState": query_state},
    }
    if title:
        visual_obj["display"] = {"title": {"text": title}}

    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": visual_id,
        "position": {"x": x, "y": y, "z": 1000, "width": width, "height": height, "tabOrder": 1000},
        "visual": visual_obj,
    }


def _build_report_parts(dataset_id: str, display_name: str, pages: list) -> list:
    parts = []

    # .platform: Fabric item metadata required by the API
    parts.append(
        {
            "path": ".platform",
            "payload": _to_base64(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                    "metadata": {"type": "Report", "displayName": display_name},
                    "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
                }
            ),
            "payloadType": "InlineBase64",
        }
    )

    # definition.pbir: v2.0.0 schema, just connectionString with semanticmodelid
    parts.append(
        {
            "path": "definition.pbir",
            "payload": _to_base64(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                    "version": "4.0",
                    "datasetReference": {
                        "byConnection": {
                            "connectionString": f"semanticmodelid={dataset_id}",
                        }
                    },
                }
            ),
            "payloadType": "InlineBase64",
        }
    )

    # definition/report.json: report-level settings and theme
    parts.append(
        {
            "path": "definition/report.json",
            "payload": _to_base64(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
                    "themeCollection": {
                        "baseTheme": {
                            "name": "CY24SU10",
                            "reportVersionAtImport": {"visual": "2.5.0", "report": "3.1.0", "page": "2.3.0"},
                            "type": "SharedResources",
                        }
                    },
                }
            ),
            "payloadType": "InlineBase64",
        }
    )

    # definition/version.json: required by the Fabric report import workload. This file has
    # been through two failed attempts already:
    #   1. No file at all -> "Cannot find file 'version.json'"
    #   2. $schema pointing at ".../definition/version/1.0.0/schema.json" -> "Can't resolve
    #      schema '1.0.0'" (that schema version doesn't exist server-side)
    #   3. No $schema property at all -> "Can't find '$schema' property in 'version.json'"
    #      ($schema is mandatory, just not at version 1.0.0)
    # Every other schema-versioned part in this package that Fabric accepts without
    # complaint uses version "2.0.0" (.platform, definition.pbir, page.json, visual.json) -
    # only report.json differs (3.1.0). Trying "2.0.0" here as the next best guess.
    parts.append(
        {
            "path": "definition/version.json",
            "payload": _to_base64(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/version/2.0.0/schema.json",
                    "version": "2.0.0",
                }
            ),
            "payloadType": "InlineBase64",
        }
    )

    page_ids = []
    page_parts = []

    grid_cols = 2
    visual_width = 600.0
    visual_height = 350.0
    padding = 20.0

    for page_spec in pages:
        page_id = uuid.uuid4().hex[:20]
        page_ids.append(page_id)

        visual_parts = []
        for i, visual_spec in enumerate(page_spec.get("visuals", [])):
            visual_id = uuid.uuid4().hex[:20]
            col = i % grid_cols
            row = i // grid_cols
            x = float(visual_spec.get("x", col * (visual_width + padding) + padding))
            y = float(visual_spec.get("y", row * (visual_height + padding) + padding))
            width = float(visual_spec.get("width", visual_width))
            height = float(visual_spec.get("height", visual_height))

            visual_parts.append(
                {
                    "path": f"definition/pages/{page_id}/visuals/{visual_id}/visual.json",
                    "payload": _to_base64(_build_visual_json(visual_id, visual_spec, x, y, width, height)),
                    "payloadType": "InlineBase64",
                }
            )

        page_parts.append(
            {
                "path": f"definition/pages/{page_id}/page.json",
                "payload": _to_base64(
                    {
                        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                        "name": page_id,
                        "displayName": page_spec.get("name", "Page 1"),
                        "displayOption": "FitToPage",
                        "height": 720,
                        "width": 1280,
                    }
                ),
                "payloadType": "InlineBase64",
            }
        )
        page_parts.extend(visual_parts)

    parts.append(
        {
            "path": "definition/pages/pages.json",
            "payload": _to_base64(
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
                    "pageOrder": page_ids,
                }
            ),
            "payloadType": "InlineBase64",
        }
    )
    parts.extend(page_parts)

    return parts


@powerbi.action("get_report_definition")
class GetReportDefinitionAction(ActionHandler):
    """
    Fetch the raw PBIR file parts (.platform, definition.pbir, report.json, version.json,
    pages, visuals) of an existing report via the Fabric getDefinition API. Diagnostic tool
    for reverse-engineering the exact format Fabric expects when create_report's generated
    package gets rejected - rather than guessing at undocumented schema versions, pull the
    ground truth from a report Fabric already accepted.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            report_id = inputs["report_id"]
            workspace_id = inputs["workspace_id"]

            url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/reports/{report_id}/getDefinition"
            response = await context.fetch(url, method="POST")

            if response.status == 202:
                operation_url = response.headers.get("Location") or response.headers.get("location")
                if not operation_url:
                    return ActionError(message="Fabric API returned 202 Accepted with no Location header to poll.")

                for _ in range(15):
                    op_response = await context.fetch(operation_url)
                    op_data = op_response.data or {}
                    status = op_data.get("status")
                    if status == "Succeeded":
                        break
                    if status in ("Failed", "Cancelled"):
                        error = op_data.get("error", {})
                        return ActionError(
                            message=f"Get report definition {status.lower()}: {error.get('message', 'unknown error')}"
                        )
                    await asyncio.sleep(2)
                else:
                    return ActionError(message="Get report definition did not complete in time.")

                result_response = await context.fetch(f"{operation_url}/result")
                data = result_response.data or {}
            else:
                data = response.data or {}

            raw_parts = data.get("definition", {}).get("parts", [])
            decoded_parts = []
            for part in raw_parts:
                payload = part.get("payload", "")
                try:
                    content = base64.b64decode(payload).decode("utf-8")
                except Exception:
                    content = None
                decoded_parts.append({"path": part.get("path"), "content": content})

            return ActionResult(data={"parts": decoded_parts}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@powerbi.action("create_report")
class CreateReportAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            display_name = inputs["display_name"]
            workspace_id = inputs["workspace_id"]
            dataset_id = inputs["dataset_id"]
            pages = inputs["pages"]

            parts = _build_report_parts(dataset_id, display_name, pages)

            url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/reports"
            response = await context.fetch(
                url,
                method="POST",
                json={
                    "displayName": display_name,
                    "definition": {"parts": parts},
                },
            )

            # Fabric API returns the created item directly on 201, or 202 Accepted with a
            # Location header pointing at a long-running operation to poll. Don't assume
            # context.fetch resolves 202s for us - poll it ourselves and fetch the result.
            if response.status == 202:
                operation_url = response.headers.get("Location") or response.headers.get("location")
                if not operation_url:
                    return ActionError(
                        message="Fabric API returned 202 Accepted with no Location header to poll for the created report."
                    )

                for _ in range(15):
                    op_response = await context.fetch(operation_url)
                    op_data = op_response.data or {}
                    status = op_data.get("status")
                    if status == "Succeeded":
                        break
                    if status in ("Failed", "Cancelled"):
                        error = op_data.get("error", {})
                        return ActionError(
                            message=f"Fabric report creation {status.lower()}: {error.get('message', 'unknown error')}"
                        )
                    await asyncio.sleep(2)
                else:
                    return ActionError(message="Fabric report creation did not complete in time.")

                result_response = await context.fetch(f"{operation_url}/result")
                data = result_response.data or {}
            else:
                data = response.data or {}

            if not data.get("id"):
                return ActionError(
                    message=(
                        "Report creation request completed but returned no report ID - the operation may "
                        "not have finished successfully."
                    )
                )

            return ActionResult(
                data={
                    "id": data.get("id"),
                    "display_name": data.get("displayName"),
                    "workspace_id": data.get("workspaceId"),
                    "web_url": data.get("webUrl"),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))
