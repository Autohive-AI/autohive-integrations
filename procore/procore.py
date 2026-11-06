"""Procore project, directory, document, RFI, and submittal workflows."""

import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext, FetchResponse, Integration

procore = Integration.load(str(Path(__file__).with_name("config.json")))
API_HOSTS = {"production": "https://api.procore.com", "sandbox": "https://sandbox.procore.com"}


async def api_request(
    context: ExecutionContext,
    environment: str,
    path: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    payload: dict | None = None,
    company_id: int | None = None,
) -> FetchResponse:
    if environment not in API_HOSTS:
        raise ValueError("Unsupported Procore environment.")
    headers = {"Accept": "application/json"}
    if company_id is not None:
        headers["Procore-Company-Id"] = str(company_id)
    return await context.fetch(
        f"{API_HOSTS[environment]}{path}",
        method=method,
        headers=headers,
        params=params,
        json=payload,
    )


def object_result(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Procore returned an unexpected resource response.")
    return data


def page_result(response: FetchResponse, page: int = 1, per_page: int = 100, paged: bool = True) -> dict[str, Any]:
    if not isinstance(response.data, list) or any(not isinstance(item, dict) for item in response.data):
        raise ValueError("Procore returned an unexpected list response.")
    headers = {key.lower(): value for key, value in response.headers.items()}
    total = int(headers["total"]) if "total" in headers else None
    next_page = None
    # Read only the page number. Never follow provider-supplied URLs with bearer credentials.
    for url, relations in re.findall(r'<([^>]+)>;\s*rel="([^"]+)"', headers.get("link", "")):
        if "next" in relations.split():
            values = parse_qs(urlsplit(url).query).get("page", [])
            if not values or not values[0].isdigit():
                raise ValueError("Procore returned an invalid next page.")
            next_page = int(values[0])
            if next_page <= page:
                raise ValueError("Procore returned a non-advancing next page.")
            break
    if "link" not in headers and paged and total is not None:
        if page * per_page < total:
            next_page = page + 1
    return {"items": response.data, "next_page": next_page, "total": total}


@procore.action("list_companies")
class ListCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            "/rest/v1.0/companies",
            method="GET",
        )
        return ActionResult(data=page_result(response, paged=False))


@procore.action("list_projects")
class ListProjectsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        params["company_id"] = inputs["company_id"]
        if "status" in inputs:
            params["filters[by_status]"] = inputs.get("status")
        if "name" in inputs:
            params["filters[name]"] = inputs.get("name")
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            "/rest/v1.1/projects",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_project")
class GetProjectAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params["company_id"] = inputs["company_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("create_project")
class CreateProjectAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        payload = {"project": inputs["project"]}
        payload["company_id"] = inputs["company_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            "/rest/v1.0/projects",
            company_id=inputs["company_id"],
            method="POST",
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("update_project")
class UpdateProjectAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        payload = {"project": inputs["project"]}
        payload["company_id"] = inputs["company_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}",
            company_id=inputs["company_id"],
            method="PATCH",
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_rfis")
class ListRfisAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        if "status" in inputs:
            params["filters[status]"] = inputs.get("status")
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_rfi")
class GetRfiAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis/{inputs['rfi_id']}",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("create_rfi")
class CreateRfiAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        payload = {"rfi": {**inputs["rfi"]}}
        payload["rfi"].setdefault("draft", True)
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis",
            company_id=inputs["company_id"],
            method="POST",
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("update_rfi")
class UpdateRfiAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        payload = {"rfi": inputs["rfi"]}
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis/{inputs['rfi_id']}",
            company_id=inputs["company_id"],
            method="PATCH",
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("recycle_rfi")
class RecycleRfiAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis/{inputs['rfi_id']}/recycle",
            company_id=inputs["company_id"],
            method="PATCH",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("restore_rfi")
class RestoreRfiAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/rfis/{inputs['rfi_id']}/retrieve",
            company_id=inputs["company_id"],
            method="PATCH",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_submittals")
class ListSubmittalsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_submittal")
class GetSubmittalAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals/{inputs['submittal_id']}",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("create_submittal")
class CreateSubmittalAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        if "send_emails" in inputs:
            params["send_emails"] = inputs.get("send_emails")
        payload = {"submittal": inputs["submittal"]}
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals",
            company_id=inputs["company_id"],
            method="POST",
            params=params,
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("update_submittal")
class UpdateSubmittalAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        if "send_emails" in inputs:
            params["send_emails"] = inputs.get("send_emails")
        payload = {"submittal": inputs["submittal"]}
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals/{inputs['submittal_id']}",
            company_id=inputs["company_id"],
            method="PATCH",
            params=params,
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("delete_submittal")
class DeleteSubmittalAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals/{inputs['submittal_id']}",
            company_id=inputs["company_id"],
            method="DELETE",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_submittal_revisions")
class ListSubmittalRevisionsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals/{inputs['submittal_id']}/revisions",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data=page_result(response, paged=False))


@procore.action("get_submittal_workflow")
class GetSubmittalWorkflowAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/submittals/{inputs['submittal_id']}/workflow_data",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_project_users")
class ListProjectUsersAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/users",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_project_user")
class GetProjectUserAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/users/{inputs['user_id']}",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_project_vendors")
class ListProjectVendorsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/vendors",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_project_vendor")
class GetProjectVendorAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.1/projects/{inputs['project_id']}/vendors/{inputs['vendor_id']}",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("list_locations")
class ListLocationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/projects/{inputs['project_id']}/locations",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("list_submittal_types")
class ListSubmittalTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/companies/{inputs['company_id']}/submittal_types",
            company_id=inputs["company_id"],
            method="GET",
        )
        return ActionResult(data=page_result(response, paged=False))


@procore.action("list_submittal_statuses")
class ListSubmittalStatusesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params.update({"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 100)})
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/companies/{inputs['company_id']}/submittal_statuses",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(
            data=page_result(response, page=inputs.get("page", 1), per_page=inputs.get("per_page", 100))
        )


@procore.action("get_document_root")
class GetDocumentRootAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params["project_id"] = inputs["project_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            "/rest/v1.0/folders",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("get_folder")
class GetFolderAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params["project_id"] = inputs["project_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/folders/{inputs['folder_id']}",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("get_file")
class GetFileAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params["project_id"] = inputs["project_id"]
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            f"/rest/v1.0/files/{inputs['file_id']}",
            company_id=inputs["company_id"],
            method="GET",
            params=params,
        )
        return ActionResult(data={"result": object_result(response.data)})


@procore.action("create_folder")
class CreateFolderAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult:
        params = {}
        params["project_id"] = inputs["project_id"]
        payload = {"folder": inputs["folder"]}
        response = await api_request(
            context,
            inputs.get("environment", "production"),
            "/rest/v1.0/folders",
            company_id=inputs["company_id"],
            method="POST",
            params=params,
            payload=payload,
        )
        return ActionResult(data={"result": object_result(response.data)})
