import base64
import binascii
from pathlib import PurePosixPath
from typing import Dict, Any

import aiohttp
from autohive_integrations_sdk import ActionHandler, ExecutionContext, Integration

# Create the integration using the config.json
powerbi = Integration.load()

# Power BI REST API Base URL
POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
SUPPORTED_IMPORT_EXTENSIONS = {".json", ".pbix", ".rdl", ".xlsx"}
IMPORT_CONTENT_TYPES = {
    ".json": "application/json",
    ".pbix": "application/octet-stream",
    ".rdl": "application/xml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _resolve_import_file(file_obj: Dict[str, Any], display_name: str = None):
    """Validate a hydrated platform file and return its bytes and import metadata."""
    source_name = PurePosixPath((file_obj.get("name") or "").replace("\\", "/")).name
    if not source_name:
        raise ValueError("file 'name' is required")
    if "\r" in source_name or "\n" in source_name:
        raise ValueError("file 'name' cannot contain line breaks")

    extension = PurePosixPath(source_name).suffix.lower()
    if extension not in SUPPORTED_IMPORT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_IMPORT_EXTENSIONS))
        raise ValueError(f"unsupported Power BI import file type '{extension or 'none'}'; use one of: {supported}")

    import_name = (display_name or source_name).strip()
    if not import_name:
        raise ValueError("display_name cannot be empty")
    if "\r" in import_name or "\n" in import_name:
        raise ValueError("display_name cannot contain line breaks")
    if not PurePosixPath(import_name).suffix:
        import_name = f"{import_name}{extension}"
    elif PurePosixPath(import_name).suffix.lower() != extension:
        raise ValueError("display_name must use the same file extension as the uploaded file")

    content_b64 = file_obj.get("content") or ""
    stripped_content = "".join(content_b64.split())
    if not stripped_content:
        raise ValueError("file 'content' is empty; attach a file before running the action")
    try:
        file_bytes = base64.b64decode(stripped_content, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise ValueError("file 'content' is not valid base64-encoded data")

    content_type = IMPORT_CONTENT_TYPES[extension]
    return source_name, import_name, extension, content_type, file_bytes


def _validate_import_options(
    extension: str,
    import_name: str,
    name_conflict: str,
    skip_report: bool,
    override_report_label: bool = None,
    override_model_label: bool = None,
):
    """Enforce the provider restrictions that vary by imported file type."""
    if extension == ".rdl" and name_conflict not in {"Abort", "Overwrite"}:
        raise ValueError("RDL imports support only Abort or Overwrite for name_conflict")
    if extension == ".json":
        if import_name.lower() != "model.json":
            raise ValueError("Power BI JSON imports must use the display name 'model.json'")
        if name_conflict not in {"Abort", "GenerateUniqueName"}:
            raise ValueError("model.json imports support only Abort or GenerateUniqueName for name_conflict")
    elif name_conflict == "GenerateUniqueName":
        raise ValueError("GenerateUniqueName is supported only for model.json imports")
    if skip_report and extension != ".pbix":
        raise ValueError("skip_report is supported only for PBIX imports")
    if extension != ".pbix" and (override_report_label is not None or override_model_label is not None):
        raise ValueError("sensitivity-label overrides are supported only for PBIX imports")


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
            for workspace in response.get("value", []):
                workspaces.append(
                    {
                        "id": workspace.get("id"),
                        "name": workspace.get("name"),
                        "isReadOnly": workspace.get("isReadOnly", False),
                        "isOnDedicatedCapacity": workspace.get("isOnDedicatedCapacity", False),
                        "type": workspace.get("type", "Workspace"),
                    }
                )

            return {"workspaces": workspaces, "result": True}

        except Exception as e:
            return {"workspaces": [], "result": False, "error": str(e)}


@powerbi.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs["workspace_id"]

            response = await context.fetch(f"{POWERBI_API_BASE}/groups/{workspace_id}")

            return {"workspace": response, "result": True}

        except Exception as e:
            return {"workspace": {}, "result": False, "error": str(e)}


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
            for dataset in response.get("value", []):
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

            return {"datasets": datasets, "result": True}

        except Exception as e:
            return {"datasets": [], "result": False, "error": str(e)}


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

            return {"dataset": response, "result": True}

        except Exception as e:
            return {"dataset": {}, "result": False, "error": str(e)}


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
            if hasattr(response, "headers") and "x-ms-request-id" in response.headers:
                request_id = response.headers["x-ms-request-id"]

            return {"result": True, "message": "Dataset refresh initiated successfully", "request_id": request_id}

        except Exception as e:
            return {"result": False, "error": str(e)}


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
            for refresh in response.get("value", []):
                refreshes.append(
                    {
                        "refreshType": refresh.get("refreshType"),
                        "startTime": refresh.get("startTime"),
                        "endTime": refresh.get("endTime"),
                        "status": refresh.get("status"),
                        "requestId": refresh.get("requestId"),
                    }
                )

            return {"refreshes": refreshes, "result": True}

        except Exception as e:
            return {"refreshes": [], "result": False, "error": str(e)}


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
            for report in response.get("value", []):
                reports.append(
                    {
                        "id": report.get("id"),
                        "name": report.get("name"),
                        "webUrl": report.get("webUrl"),
                        "embedUrl": report.get("embedUrl"),
                        "datasetId": report.get("datasetId"),
                    }
                )

            return {"reports": reports, "result": True}

        except Exception as e:
            return {"reports": [], "result": False, "error": str(e)}


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

            return {"report": response, "result": True}

        except Exception as e:
            return {"report": {}, "result": False, "error": str(e)}


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
            for datasource in response.get("value", []):
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

            return {"datasources": datasources, "result": True}

        except Exception as e:
            return {"datasources": [], "result": False, "error": str(e)}


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
            dataset_id = report_response.get("datasetId")

            if not dataset_id:
                return {"result": False, "error": "Report does not have an associated dataset"}

            # Now refresh the dataset
            if workspace_id:
                refresh_url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
            else:
                refresh_url = f"{POWERBI_API_BASE}/datasets/{dataset_id}/refreshes"

            refresh_request = {"notifyOption": notify_option}

            await context.fetch(refresh_url, method="POST", json=refresh_request)

            return {
                "result": True,
                "message": f"Dataset refresh initiated successfully for report '{report_response.get('name')}'",
                "dataset_id": dataset_id,
            }

        except Exception as e:
            return {"result": False, "error": str(e)}


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

            return {
                "id": response.get("id"),
                "name": response.get("name"),
                "webUrl": response.get("webUrl"),
                "embedUrl": response.get("embedUrl"),
                "result": True,
            }

        except Exception as e:
            return {"result": False, "error": str(e)}


@powerbi.action("import_powerbi_file")
class ImportPowerBIFileAction(ActionHandler):
    """Publish a supported Power BI file to My workspace or a named workspace."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            workspace_id = inputs.get("workspace_id")
            source_name, import_name, extension, content_type, file_bytes = _resolve_import_file(
                inputs["file"], inputs.get("display_name")
            )
            default_name_conflict = "Abort" if extension in {".json", ".rdl"} else "Ignore"
            name_conflict = inputs.get("name_conflict", default_name_conflict)
            skip_report = inputs.get("skip_report", False)
            _validate_import_options(
                extension,
                import_name,
                name_conflict,
                skip_report,
                inputs.get("override_report_label"),
                inputs.get("override_model_label"),
            )

            params = {
                "datasetDisplayName": import_name,
                "nameConflict": name_conflict,
            }
            if skip_report:
                params["skipReport"] = True
            if inputs.get("override_report_label") is not None:
                params["overrideReportLabel"] = inputs["override_report_label"]
            if inputs.get("override_model_label") is not None:
                params["overrideModelLabel"] = inputs["override_model_label"]
            if inputs.get("subfolder_object_id"):
                params["subfolderObjectId"] = inputs["subfolder_object_id"]

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/imports"
            else:
                url = f"{POWERBI_API_BASE}/imports"

            form = aiohttp.FormData()
            form.add_field("file", file_bytes, filename=source_name, content_type=content_type)
            response = await context.fetch(url, method="POST", params=params, data=form, timeout=600)

            import_id = response.get("id")
            if not import_id:
                raise ValueError("Power BI import response did not include an import ID")

            return {
                "import_id": import_id,
                "import_state": response.get("importState", "Publishing"),
                "name": response.get("name", import_name),
                "reports": response.get("reports", []),
                "datasets": response.get("datasets", []),
                "result": True,
            }

        except Exception as e:
            return {
                "import_id": "",
                "import_state": "Failed",
                "name": "",
                "reports": [],
                "datasets": [],
                "result": False,
                "error": str(e),
            }


@powerbi.action("get_import_status")
class GetImportStatusAction(ActionHandler):
    """Return publishing state and created content for a Power BI import."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            import_id = inputs["import_id"]
            workspace_id = inputs.get("workspace_id")

            if workspace_id:
                url = f"{POWERBI_API_BASE}/groups/{workspace_id}/imports/{import_id}"
            else:
                url = f"{POWERBI_API_BASE}/imports/{import_id}"

            response = await context.fetch(url)

            result = {
                "import_id": response.get("id", import_id),
                "import_state": response.get("importState", ""),
                "name": response.get("name", ""),
                "reports": response.get("reports", []),
                "datasets": response.get("datasets", []),
                "result": True,
            }
            if response.get("createdDateTime"):
                result["created_date_time"] = response["createdDateTime"]
            if response.get("updatedDateTime"):
                result["updated_date_time"] = response["updatedDateTime"]
            if response.get("error"):
                result["import_error"] = response["error"]
            return result

        except Exception as e:
            return {
                "import_id": inputs.get("import_id", ""),
                "import_state": "Failed",
                "name": "",
                "reports": [],
                "datasets": [],
                "result": False,
                "error": str(e),
            }


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

            return {"export_id": response.get("id"), "result": True, "message": "Export initiated successfully"}

        except Exception as e:
            return {"result": False, "error": str(e)}


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

            return {
                "status": response.get("status"),
                "percentComplete": response.get("percentComplete", 0),
                "result": True,
            }

        except Exception as e:
            return {"status": "Failed", "percentComplete": 0, "result": False, "error": str(e)}


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
            for dashboard in response.get("value", []):
                dashboards.append(
                    {
                        "id": dashboard.get("id"),
                        "displayName": dashboard.get("displayName"),
                        "isReadOnly": dashboard.get("isReadOnly", False),
                        "embedUrl": dashboard.get("embedUrl"),
                    }
                )

            return {"dashboards": dashboards, "result": True}

        except Exception as e:
            return {"dashboards": [], "result": False, "error": str(e)}


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

            return {"dashboard": response, "result": True}

        except Exception as e:
            return {"dashboard": {}, "result": False, "error": str(e)}


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
            for tile in response.get("value", []):
                tiles.append(
                    {
                        "id": tile.get("id"),
                        "title": tile.get("title"),
                        "embedUrl": tile.get("embedUrl"),
                        "datasetId": tile.get("datasetId"),
                        "reportId": tile.get("reportId"),
                    }
                )

            return {"tiles": tiles, "result": True}

        except Exception as e:
            return {"tiles": [], "result": False, "error": str(e)}


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

            return {"results": response.get("results", []), "result": True}

        except Exception as e:
            return {"results": [], "result": False, "error": str(e)}
