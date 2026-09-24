from typing import Any
from urllib.parse import urlparse

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration


jobadder = Integration.load()


def get_api_base_url(context: ExecutionContext) -> str:
    """Return and validate the tenant API URL supplied by JobAdder OAuth."""
    metadata = context.metadata or {}
    api_url = metadata.get("api")
    if not isinstance(api_url, str) or not api_url:
        raise ValueError("JobAdder API URL is missing. Please reconnect the account.")
    api_url = api_url.rstrip("/")

    parsed = urlparse(api_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (hostname == "jobadder.com" or hostname.endswith(".jobadder.com")):
        raise ValueError("JobAdder API URL must be an HTTPS URL on jobadder.com. Please reconnect the account.")

    return api_url


def _list_result(data: Any, key: str) -> ActionResult:
    payload = data if isinstance(data, dict) else {}
    return ActionResult(
        data={
            key: payload.get("items", []),
            "total_count": payload.get("totalCount", 0),
            "links": payload.get("links", {}),
        }
    )


def _pagination(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)}


@jobadder.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{get_api_base_url(context)}/users/current", method="GET")
            return ActionResult(data={"user": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_jobs")
class ListJobsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "jobTitle": inputs.get("job_title"),
                        "company.name": inputs.get("company_name"),
                        "companyId": inputs.get("company_id"),
                        "statusId": inputs.get("status_id"),
                        "active": inputs.get("active"),
                        "ownerUserId": inputs.get("owner_user_id"),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                        "sort": inputs.get("sort"),
                    }.items()
                    if value is not None
                }
            )

            response = await context.fetch(f"{get_api_base_url(context)}/jobs", method="GET", params=params)
            return _list_result(response.data, "jobs")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job")
class GetJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{get_api_base_url(context)}/jobs/{inputs['job_id']}", method="GET")
            return ActionResult(data={"job": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidates")
class ListCandidatesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "name": inputs.get("name"),
                        "email": inputs.get("email"),
                        "phone": inputs.get("phone"),
                        "keywords": inputs.get("keywords"),
                        "statusId": inputs.get("status_id"),
                        "recruiterUserId": inputs.get("recruiter_user_id"),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                        "sort": inputs.get("sort"),
                    }.items()
                    if value is not None
                }
            )

            response = await context.fetch(f"{get_api_base_url(context)}/candidates", method="GET", params=params)
            return _list_result(response.data, "candidates")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_candidate")
class GetCandidateAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}", method="GET"
            )
            return ActionResult(data={"candidate": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("create_candidate")
class CreateCandidateAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "firstName": inputs.get("first_name"),
                    "lastName": inputs.get("last_name"),
                    "email": inputs.get("email"),
                    "phone": inputs.get("phone"),
                    "mobile": inputs.get("mobile"),
                    "salutation": inputs.get("salutation"),
                    "statusId": inputs.get("status_id"),
                    "rating": inputs.get("rating"),
                    "source": inputs.get("source"),
                    "seeking": inputs.get("seeking"),
                    "social": inputs.get("social"),
                    "address": inputs.get("address"),
                    "skillTags": inputs.get("skill_tags"),
                    "employment": inputs.get("employment"),
                    "availability": inputs.get("availability"),
                    "education": inputs.get("education"),
                    "custom": inputs.get("custom_fields"),
                    "recruiterUserId": inputs.get("recruiter_user_ids"),
                }.items()
                if value is not None
            }
            headers = {"Content-Type": "application/json"}
            if inputs.get("allow_duplicates"):
                headers["X-Allow-Duplicates"] = inputs["allow_duplicates"]

            response = await context.fetch(
                f"{get_api_base_url(context)}/candidates", method="POST", headers=headers, json=body
            )
            return ActionResult(data={"candidate": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_applications")
class ListApplicationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "candidateId": inputs.get("candidate_id"),
                        "jobId": inputs.get("job_id"),
                        "statusId": inputs.get("status_id"),
                        "jobTitle": inputs.get("job_title"),
                        "active": inputs.get("active"),
                        "rejected": inputs.get("rejected"),
                        "keywords": inputs.get("keywords"),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                        "sort": inputs.get("sort"),
                    }.items()
                    if value is not None
                }
            )

            response = await context.fetch(f"{get_api_base_url(context)}/applications", method="GET", params=params)
            return _list_result(response.data, "applications")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_application")
class GetApplicationAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/applications/{inputs['application_id']}", method="GET"
            )
            return ActionResult(data={"application": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("add_candidates_to_job")
class AddCandidatesToJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body: dict[str, Any] = {"candidateId": inputs["candidate_ids"]}
            if inputs.get("source") is not None:
                body["source"] = inputs["source"]

            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/applications",
                method="POST",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return _list_result(response.data, "applications")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placements")
class ListPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "candidateId": inputs.get("candidate_id"),
                        "jobId": inputs.get("job_id"),
                        "companyId": inputs.get("company_id"),
                        "statusId": inputs.get("status_id"),
                        "approved": inputs.get("approved"),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                    }.items()
                    if value is not None
                }
            )

            response = await context.fetch(f"{get_api_base_url(context)}/placements", method="GET", params=params)
            return _list_result(response.data, "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_placement")
class GetPlacementAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/placements/{inputs['placement_id']}", method="GET"
            )
            return ActionResult(data={"placement": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))
