from typing import Dict, Any
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
)

fergus = Integration.load()

BASE_URL = "https://api.fergus.com"


def _auth_headers(api_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _success(data: Dict[str, Any]) -> ActionResult:
    return ActionResult(data={"result": True, **data})


def _error(e: Exception) -> ActionResult:
    return ActionResult(data={"result": False, "error": str(e), "error_type": type(e).__name__})


def _get_token(context: ExecutionContext) -> str:
    token = context.auth.get("credentials", {}).get("api_token")
    if not token:
        raise ValueError("Fergus Personal Access Token is required in auth (field 'api_token').")
    return token


@fergus.action("create_job")
class CreateJob(ActionHandler):
    """Create a new job in Fergus from a work order (MP inbound flow).
    Set is_draft=true to create a draft (only job_type + title required), then call update_job
    and finalise_job once all details are confirmed. For non-draft jobs, description, customer_id
    and site_id are also required by Fergus."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
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
                missing = [
                    f
                    for f in ("customer_id", "site_id")
                    if inputs.get(f) is None
                ] + (["description"] if not inputs.get("description") else [])
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
            return _success({"job": resp})
        except Exception as e:
            return _error(e)


@fergus.action("update_job")
class UpdateJob(ActionHandler):
    """Update a DRAFT job in Fergus. Fergus only allows updating jobs still in draft status.
    Call finalise_job after to make the job active."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
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

            resp = await context.fetch(f"{BASE_URL}/jobs/{job_id}", method="PUT", headers=headers, json=body)
            return _success({"job": resp})
        except Exception as e:
            return _error(e)


@fergus.action("finalise_job")
class FinaliseJob(ActionHandler):
    """Finalise a draft job in Fergus, making it active and ready to assign to a technician."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
            job_id = int(inputs["job_id"])

            resp = await context.fetch(
                f"{BASE_URL}/jobs/{job_id}/finalise",
                method="PUT",
                headers=headers,
                json={},
            )
            return _success({"job": resp})
        except Exception as e:
            return _error(e)


@fergus.action("get_job")
class GetJob(ActionHandler):
    """Get full job details including completion/invoice data for BCTI reporting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
            job_id = int(inputs["job_id"])

            resp = await context.fetch(f"{BASE_URL}/jobs/{job_id}", method="GET", headers=headers)
            return _success({"job": resp})
        except Exception as e:
            return _error(e)


@fergus.action("list_jobs")
class ListJobs(ActionHandler):
    """List jobs with optional filters — use filterJobStatus=Completed/Invoiced for BCTI outbound flow."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": int(inputs.get("page_size") or 10)}
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
            return _success({"jobs": resp})
        except Exception as e:
            return _error(e)


@fergus.action("search_customers")
class SearchCustomers(ActionHandler):
    """Search for customers in Fergus — use to find customer_id before creating a job."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": int(inputs.get("page_size") or 10)}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/customers", method="GET", headers=headers, params=params)
            return _success({"customers": resp})
        except Exception as e:
            return _error(e)


@fergus.action("get_customer")
class GetCustomer(ActionHandler):
    """Get full details of a single customer."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)
            customer_id = int(inputs["customer_id"])

            resp = await context.fetch(f"{BASE_URL}/customers/{customer_id}", method="GET", headers=headers)
            return _success({"customer": resp})
        except Exception as e:
            return _error(e)


@fergus.action("list_sites")
class ListSites(ActionHandler):
    """List sites (job locations) — use to find site_id before creating a job."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            token = _get_token(context)
            headers = _auth_headers(token)

            params: Dict[str, Any] = {"pageSize": int(inputs.get("page_size") or 10)}
            if inputs.get("page_cursor"):
                params["pageCursor"] = inputs["page_cursor"]
            if inputs.get("sort_order"):
                params["sortOrder"] = inputs["sort_order"]
            if inputs.get("search"):
                params["filterSearchText"] = inputs["search"]

            resp = await context.fetch(f"{BASE_URL}/sites", method="GET", headers=headers, params=params)
            return _success({"sites": resp})
        except Exception as e:
            return _error(e)


@fergus.action("list_users")
class ListUsers(ActionHandler):
    """List all users (technicians/staff) — use to find user IDs when assigning jobs."""

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
            return _success({"users": resp})
        except Exception as e:
            return _error(e)
