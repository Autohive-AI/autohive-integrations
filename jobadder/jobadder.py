import base64
import binascii
from typing import Any
from urllib.parse import urlencode, urlparse

import aiohttp
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration


jobadder = Integration.load()

MAX_CANDIDATE_ATTACHMENT_BYTES = 5 * 1024 * 1024
_DOWNLOAD_CHUNK_BYTES = 64 * 1024


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
    items = payload.get("items") or []
    return ActionResult(
        data={
            key: items,
            "total_count": payload.get("totalCount", len(items)),
            "links": payload.get("links") or {},
        }
    )


def _pagination(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)}


async def _fetch_list(
    context: ExecutionContext,
    path: str,
    key: str,
    params: dict[str, Any] | None = None,
) -> ActionResult:
    response = await _fetch_get(context, f"{get_api_base_url(context)}{path}", params)
    return _list_result(response.data, key)


async def _fetch_get(
    context: ExecutionContext,
    url: str,
    params: dict[str, Any] | None = None,
):
    """GET with OpenAPI form/explode encoding for array query parameters."""
    scalar_params: dict[str, Any] = {}
    array_params: dict[str, list[Any]] = {}
    for key, value in (params or {}).items():
        if isinstance(value, list):
            if value:
                array_params[key] = value
        elif value is not None:
            scalar_params[key] = value

    if array_params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(array_params, doseq=True)}"

    if scalar_params:
        return await context.fetch(url, method="GET", params=scalar_params)
    return await context.fetch(url, method="GET")


def _boolean_query_value(value: bool | None) -> str | None:
    return str(value).lower() if value is not None else None


def _date_range(start: str | None, end: str | None) -> list[str] | None:
    values = []
    if start:
        values.append(f">{start}")
    if end:
        values.append(f"<{end}")
    return values or None


def _note_search_params(
    *,
    contact_id: int | list[int],
    types: list[str] | None = None,
    created_at_from: str | None = None,
    created_at_to: str | None = None,
    updated_at_from: str | None = None,
    updated_at_to: str | None = None,
    sort: str = "-createdAt",
    offset: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "contactId": contact_id,
            "type": types,
            "createdAt": _date_range(created_at_from, created_at_to),
            "updatedAt": _date_range(updated_at_from, updated_at_to),
            "sort": sort,
            "fields": ["text"],
            "offset": offset,
            "limit": limit,
        }.items()
        if value is not None
    }


def _record_note_params(
    *,
    types: list[str] | None = None,
    references: list[str] | None = None,
    created_at_from: str | None = None,
    created_at_to: str | None = None,
    updated_at_from: str | None = None,
    updated_at_to: str | None = None,
    sort: str = "-createdAt",
    offset: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """Build the common query supported by record-specific note endpoints."""
    return {
        key: value
        for key, value in {
            "type": types,
            "reference": references,
            "createdAt": _date_range(created_at_from, created_at_to),
            "updatedAt": _date_range(updated_at_from, updated_at_to),
            "sort": sort,
            "fields": ["text"],
            "offset": offset,
            "limit": limit,
        }.items()
        if value is not None
    }


def _decode_file(file: dict[str, Any]) -> tuple[bytes, str, str]:
    """Decode an Autohive file object and return bytes, filename, and MIME type."""
    content = file.get("content")
    if not isinstance(content, str) or not content:
        raise ValueError("The uploaded file must include non-empty base64 content.")

    max_encoded_chars = 4 * ((MAX_CANDIDATE_ATTACHMENT_BYTES + 2) // 3)
    max_input_chars = max_encoded_chars + max_encoded_chars // 20
    if len(content) > max_input_chars:
        raise ValueError(
            f"Candidate attachment exceeds the {MAX_CANDIDATE_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit."
        )

    normalized_content = "".join(content.split())
    if len(normalized_content) > max_encoded_chars:
        raise ValueError(
            f"Candidate attachment exceeds the {MAX_CANDIDATE_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit."
        )

    try:
        file_bytes = base64.b64decode(normalized_content, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("The uploaded file content is not valid base64.") from exc

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")
    if len(file_bytes) > MAX_CANDIDATE_ATTACHMENT_BYTES:
        raise ValueError(
            f"Candidate attachment exceeds the {MAX_CANDIDATE_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit."
        )

    file_name = file.get("name")
    if not isinstance(file_name, str) or not file_name:
        raise ValueError("The uploaded file must include a name.")

    content_type = file.get("contentType") or "application/octet-stream"
    return file_bytes, file_name, content_type


def _access_token(context: ExecutionContext) -> str:
    credentials = (context.auth or {}).get("credentials") or {}
    token = credentials.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("JobAdder access token is missing. Please reconnect the account.")
    return token


async def _download_candidate_attachment(
    context: ExecutionContext,
    candidate_id: int,
    attachment_id: int,
    accept: str,
) -> tuple[bytes, dict[str, str]]:
    """Download binary content, which ExecutionContext.fetch does not preserve as bytes."""
    url = f"{get_api_base_url(context)}/candidates/{candidate_id}/attachments/{attachment_id}"
    headers = {"Authorization": f"Bearer {_access_token(context)}", "Accept": accept}
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers, ssl=True) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"JobAdder attachment download failed with HTTP {response.status}.")

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > MAX_CANDIDATE_ATTACHMENT_BYTES:
                    raise ValueError(
                        f"Candidate attachment exceeds the {MAX_CANDIDATE_ATTACHMENT_BYTES // (1024 * 1024)} MiB "
                        "download limit."
                    )

            content = bytearray()
            while True:
                remaining = MAX_CANDIDATE_ATTACHMENT_BYTES + 1 - len(content)
                chunk = await response.content.read(min(_DOWNLOAD_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_CANDIDATE_ATTACHMENT_BYTES:
                    raise ValueError(
                        f"Candidate attachment exceeds the {MAX_CANDIDATE_ATTACHMENT_BYTES // (1024 * 1024)} MiB "
                        "download limit."
                    )

            return bytes(content), dict(response.headers)


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
                        "active": _boolean_query_value(inputs.get("active")),
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


@jobadder.action("list_contacts")
class ListContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            company_id: int | list[int] | None = inputs.get("company_id")
            if company_id is None and inputs.get("company_name"):
                company_response = await context.fetch(
                    f"{get_api_base_url(context)}/companies",
                    method="GET",
                    params={"name": inputs["company_name"], "offset": 0, "limit": 1000},
                )
                company_payload = company_response.data if isinstance(company_response.data, dict) else {}
                company_id = [
                    company["companyId"]
                    for company in company_payload.get("items") or []
                    if isinstance(company, dict) and isinstance(company.get("companyId"), int)
                ]
                if not company_id:
                    return ActionResult(data={"contacts": [], "total_count": 0, "links": {}})

            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "name": inputs.get("name"),
                        "email": inputs.get("email"),
                        "phone": inputs.get("phone"),
                        "companyId": company_id,
                        "createdBy": inputs.get("created_by_user_id"),
                        "statusId": inputs.get("status_id"),
                        "hiringManager": _boolean_query_value(inputs.get("hiring_manager")),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                    }.items()
                    if value is not None
                }
            )

            response = await _fetch_get(context, f"{get_api_base_url(context)}/contacts", params)
            return _list_result(response.data, "contacts")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_contact")
class GetContactAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{get_api_base_url(context)}/contacts/{inputs['contact_id']}", method="GET")
            return ActionResult(data={"contact": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_contact_notes")
class ListContactNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/contacts/{inputs['contact_id']}/notes",
                "notes",
                _record_note_params(
                    types=inputs.get("types"),
                    references=inputs.get("references"),
                    created_at_from=inputs.get("created_at_from"),
                    created_at_to=inputs.get("created_at_to"),
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_contact_activities")
class ListContactActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _note_search_params(
                contact_id=inputs["contact_id"],
                types=inputs.get("types"),
                created_at_from=inputs.get("created_at_from"),
                created_at_to=inputs.get("created_at_to"),
                updated_at_from=inputs.get("updated_at_from"),
                updated_at_to=inputs.get("updated_at_to"),
                sort=inputs.get("sort", "-createdAt"),
                offset=inputs.get("offset", 0),
                limit=inputs.get("limit", 100),
            )
            response = await _fetch_get(context, f"{get_api_base_url(context)}/notes", params)
            return _list_result(response.data, "activities")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_all_contact_activities")
class ListAllContactActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await _fetch_get(
                context,
                f"{get_api_base_url(context)}/notes",
                _note_search_params(
                    contact_id=inputs["contact_ids"],
                    types=inputs.get("types"),
                    created_at_from=inputs["created_at_from"],
                    created_at_to=inputs["created_at_to"],
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
            return _list_result(response.data, "activities")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_note")
class GetNoteAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(f"{get_api_base_url(context)}/notes/{inputs['note_id']}", method="GET")
            return ActionResult(data={"note": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_note_types")
class ListCandidateNoteTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"name": inputs["name"]} if inputs.get("name") else None
            return await _fetch_list(context, "/candidates/lists/notetype", "note_types", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_contact_note_types")
class ListContactNoteTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"name": inputs["name"]} if inputs.get("name") else None
            return await _fetch_list(context, "/contacts/lists/notetype", "note_types", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_note_types")
class ListJobNoteTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"name": inputs["name"]} if inputs.get("name") else None
            return await _fetch_list(context, "/jobs/lists/notetype", "note_types", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placement_note_types")
class ListPlacementNoteTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"name": inputs["name"]} if inputs.get("name") else None
            return await _fetch_list(context, "/placements/lists/notetype", "note_types", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_note_types")
class ListCompanyNoteTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"name": inputs["name"]} if inputs.get("name") else None
            return await _fetch_list(context, "/companies/lists/notetype", "note_types", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_contact_jobs")
class ListContactJobsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/contacts/{inputs['contact_id']}/jobs", method="GET"
            )
            return _list_result(response.data, "jobs")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_companies")
class ListCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = _pagination(inputs)
            params.update(
                {
                    key: value
                    for key, value in {
                        "name": inputs.get("name"),
                        "statusId": inputs.get("status_id"),
                        "createdBy": inputs.get("created_by_user_id"),
                        "createdAt": inputs.get("created_at"),
                        "updatedAt": inputs.get("updated_at"),
                    }.items()
                    if value is not None
                }
            )
            response = await context.fetch(f"{get_api_base_url(context)}/companies", method="GET", params=params)
            return _list_result(response.data, "companies")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_company")
class GetCompanyAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/companies/{inputs['company_id']}", method="GET"
            )
            return ActionResult(data={"company": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_applications")
class ListCandidateApplicationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/candidates/{inputs['candidate_id']}/applications",
                "applications",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_active_applications")
class ListCandidateActiveApplicationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/candidates/{inputs['candidate_id']}/applications/active",
                "applications",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_placements")
class ListCandidatePlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/candidates/{inputs['candidate_id']}/placements", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_approved_placements")
class ListCandidateApprovedPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/candidates/{inputs['candidate_id']}/placements/approved", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_attachments")
class ListCandidateAttachmentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {
                key: value
                for key, value in {
                    "type": inputs.get("types"),
                    "category": inputs.get("categories"),
                    "latest": _boolean_query_value(inputs.get("latest")),
                    "offset": inputs.get("offset", 0),
                    "limit": inputs.get("limit", 100),
                }.items()
                if value is not None
            }
            return await _fetch_list(
                context,
                f"/candidates/{inputs['candidate_id']}/attachments",
                "attachments",
                params,
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_attachment_categories")
class ListCandidateAttachmentCategoriesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"type": inputs["types"]} if inputs.get("types") else None
            return await _fetch_list(context, "/candidates/lists/attachmentcategory", "categories", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("download_candidate_attachment")
class DownloadCandidateAttachmentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            content, headers = await _download_candidate_attachment(
                context,
                inputs["candidate_id"],
                inputs["attachment_id"],
                inputs.get("accept", "application/octet-stream"),
            )
            content_type = headers.get("Content-Type") or headers.get("content-type") or "application/octet-stream"
            file_name = inputs.get("file_name") or (
                f"candidate-{inputs['candidate_id']}-attachment-{inputs['attachment_id']}"
            )
            return ActionResult(
                data={
                    "file": {
                        "name": file_name,
                        "contentType": content_type.split(";", 1)[0],
                        "content": base64.b64encode(content).decode("ascii"),
                    }
                }
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("upload_candidate_attachment")
class UploadCandidateAttachmentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            file_bytes, file_name, content_type = _decode_file(inputs["file"])
            form = aiohttp.FormData()
            form.add_field("fileData", file_bytes, filename=file_name, content_type=content_type)
            response = await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}/attachments/{inputs['attachment_type']}",
                method="POST",
                data=form,
            )
            return ActionResult(data={"attachment": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("update_candidate_attachment")
class UpdateCandidateAttachmentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body = {
                key: value
                for key, value in {
                    "type": inputs.get("type"),
                    "category": inputs.get("category"),
                    "expiry": inputs.get("expiry"),
                }.items()
                if key in inputs
            }
            if not body:
                return ActionError(message="Provide at least one of type, category, or expiry.")

            response = await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}/attachments/{inputs['attachment_id']}",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"attachment": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_skills")
class ListCandidateSkillsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/candidates/{inputs['candidate_id']}/skills", "skills")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_candidate_availability")
class GetCandidateAvailabilityAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}/availability", method="GET"
            )
            return ActionResult(data={"availability": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_candidate_notes")
class ListCandidateNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/candidates/{inputs['candidate_id']}/notes",
                "notes",
                _record_note_params(
                    types=inputs.get("types"),
                    references=inputs.get("references"),
                    created_at_from=inputs.get("created_at_from"),
                    created_at_to=inputs.get("created_at_to"),
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_applications")
class ListJobApplicationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/jobs/{inputs['job_id']}/applications",
                "applications",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_active_applications")
class ListJobActiveApplicationsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/jobs/{inputs['job_id']}/applications/active",
                "applications",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_placements")
class ListJobPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/jobs/{inputs['job_id']}/placements", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_approved_placements")
class ListJobApprovedPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/jobs/{inputs['job_id']}/placements/approved", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_attachments")
class ListJobAttachmentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/jobs/{inputs['job_id']}/attachments",
                "attachments",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_notes")
class ListJobNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/jobs/{inputs['job_id']}/notes",
                "notes",
                _record_note_params(
                    types=inputs.get("types"),
                    references=inputs.get("references"),
                    created_at_from=inputs.get("created_at_from"),
                    created_at_to=inputs.get("created_at_to"),
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_activities")
class ListJobActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/jobs/{inputs['job_id']}/activities", "activities")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_application_attachments")
class ListApplicationAttachmentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/applications/{inputs['application_id']}/attachments",
                "attachments",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_application_notes")
class ListApplicationNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/applications/{inputs['application_id']}/notes",
                "notes",
                {"fields": ["text"], "offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_application_activities")
class ListApplicationActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/applications/{inputs['application_id']}/activities", "activities")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placement_attachments")
class ListPlacementAttachmentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/placements/{inputs['placement_id']}/attachments",
                "attachments",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placement_notes")
class ListPlacementNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/placements/{inputs['placement_id']}/notes",
                "notes",
                _record_note_params(
                    types=inputs.get("types"),
                    references=inputs.get("references"),
                    created_at_from=inputs.get("created_at_from"),
                    created_at_to=inputs.get("created_at_to"),
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placement_timesheets")
class ListPlacementTimesheetsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"period": _date_range(inputs.get("period_from"), inputs.get("period_to"))}
            return await _fetch_list(
                context,
                f"/placements/{inputs['placement_id']}/timesheets",
                "timesheets",
                {key: value for key, value in params.items() if value is not None},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_placement_activities")
class ListPlacementActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/placements/{inputs['placement_id']}/activities", "activities")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_contacts")
class ListCompanyContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/companies/{inputs['company_id']}/contacts", "contacts")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_addresses")
class ListCompanyAddressesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/companies/{inputs['company_id']}/addresses", "addresses")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_jobs")
class ListCompanyJobsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/companies/{inputs['company_id']}/jobs",
                "jobs",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_active_jobs")
class ListCompanyActiveJobsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/companies/{inputs['company_id']}/jobs/active",
                "jobs",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_placements")
class ListCompanyPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/companies/{inputs['company_id']}/placements", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_approved_placements")
class ListCompanyApprovedPlacementsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, f"/companies/{inputs['company_id']}/placements/approved", "placements")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_attachments")
class ListCompanyAttachmentsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/companies/{inputs['company_id']}/attachments",
                "attachments",
                {"offset": inputs.get("offset", 0), "limit": inputs.get("limit", 100)},
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_company_notes")
class ListCompanyNotesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(
                context,
                f"/companies/{inputs['company_id']}/notes",
                "notes",
                _record_note_params(
                    types=inputs.get("types"),
                    references=inputs.get("references"),
                    created_at_from=inputs.get("created_at_from"),
                    created_at_to=inputs.get("created_at_to"),
                    updated_at_from=inputs.get("updated_at_from"),
                    updated_at_to=inputs.get("updated_at_to"),
                    sort=inputs.get("sort", "-createdAt"),
                    offset=inputs.get("offset", 0),
                    limit=inputs.get("limit", 100),
                ),
            )
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
                        "active": _boolean_query_value(inputs.get("active")),
                        "rejected": _boolean_query_value(inputs.get("rejected")),
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
                        "approved": _boolean_query_value(inputs.get("approved")),
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
