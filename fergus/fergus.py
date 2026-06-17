from typing import Dict, Any
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)

fergus = Integration.load()

BASE_URL = "https://api.fergus.com"


def _auth_headers(api_token: str, include_content_type: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _get_token(context: ExecutionContext) -> str:
    token = context.auth.get("credentials", {}).get("api_token")
    if not token:
        raise ValueError("Fergus Personal Access Token is required in auth (field 'api_token').")
    return token


@fergus.action("create_job")
class CreateJob(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token, include_content_type=True)
            is_draft = inputs.get("is_draft", False)

            body: Dict[str, Any] = {
                "jobType": inputs["job_type"],
                "title": inputs["title"],
            }

            if is_draft:
                body["isDraft"] = True
                if inputs.get("description"):
                    body["description"] = inputs["description"]
                if inputs.get("customer_id") is not None:
                    body["customerId"] = int(inputs["customer_id"])
                if inputs.get("site_id") is not None:
                    body["siteId"] = int(inputs["site_id"])
                if inputs.get("customer_reference"):
                    body["customerReference"] = inputs["customer_reference"]
            else:
                missing = [f for f in ("customer_id", "site_id") if inputs.get(f) is None] + (
                    ["description"] if not inputs.get("description") else []
                )
                if missing:
                    raise ValueError(
                        f"Fields required for non-draft jobs: {', '.join(missing)}. "
                        "Set is_draft=true to create a draft without these fields."
                    )
                body["description"] = inputs["description"]
                body["customerId"] = int(inputs["customer_id"])
                body["siteId"] = int(inputs["site_id"])
                if inputs.get("customer_reference"):
                    body["customerReference"] = inputs["customer_reference"]

            resp = await context.fetch(f"{BASE_URL}/jobs", method="POST", headers=headers, json=body)
            return ActionResult(data={"job": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("update_job")
class UpdateJob(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token, include_content_type=True)
            job_id = int(inputs["job_id"])

            body: Dict[str, Any] = {}
            if inputs.get("job_type"):
                body["jobType"] = inputs["job_type"]
            if inputs.get("title"):
                body["title"] = inputs["title"]
            if inputs.get("description"):
                body["description"] = inputs["description"]
            if inputs.get("customer_id") is not None:
                body["customerId"] = int(inputs["customer_id"])
            if inputs.get("site_id") is not None:
                body["siteId"] = int(inputs["site_id"])
            if inputs.get("customer_reference"):
                body["customerReference"] = inputs["customer_reference"]

            if not body:
                raise ValueError("At least one field must be provided to update a job.")

            resp = await context.fetch(f"{BASE_URL}/jobs/{job_id}", method="PUT", headers=headers, json=body)
            return ActionResult(data={"job": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("finalise_job")
class FinaliseJob(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token, include_content_type=True)
            job_id = int(inputs["job_id"])

            resp = await context.fetch(
                f"{BASE_URL}/jobs/{job_id}/finalise",
                method="PUT",
                headers=headers,
                json={},
            )
            return ActionResult(data={"job": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("get_job")
class GetJob(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
            job_id = int(inputs["job_id"])

            resp = await context.fetch(f"{BASE_URL}/jobs/{job_id}", method="GET", headers=headers)
            return ActionResult(data={"job": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("list_jobs")
class ListJobs(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": max(1, int(inputs.get("page_size") or 10))}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("status"):
                params["filterJobStatus"] = inputs["status"]
            if inputs.get("job_type"):
                params["filterJobType"] = inputs["job_type"]
            if inputs.get("customer_id") is not None:
                params["filterCustomerId"] = int(inputs["customer_id"])
            if inputs.get("site_id") is not None:
                params["filterSiteId"] = int(inputs["site_id"])
            if inputs.get("job_number"):
                params["filterJobNo"] = inputs["job_number"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/jobs", method="GET", headers=headers, params=params)
            return ActionResult(data={"jobs": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("search_customers")
class SearchCustomers(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": max(1, int(inputs.get("page_size") or 10))}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/customers", method="GET", headers=headers, params=params)
            return ActionResult(data={"customers": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("get_customer")
class GetCustomer(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
            customer_id = int(inputs["customer_id"])

            resp = await context.fetch(f"{BASE_URL}/customers/{customer_id}", method="GET", headers=headers)
            return ActionResult(data={"customer": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("list_sites")
class ListSites(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": max(1, int(inputs.get("page_size") or 10))}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/sites", method="GET", headers=headers, params=params)
            return ActionResult(data={"sites": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@fergus.action("list_users")
class ListUsers(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": int(inputs.get("page_size") or 50)}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/users", method="GET", headers=headers, params=params)
            return ActionResult(data={"users": resp.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
