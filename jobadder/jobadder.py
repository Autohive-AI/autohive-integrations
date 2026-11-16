import base64
import binascii
from typing import Any
from urllib.parse import urlencode, urlparse

import aiohttp
from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, HTTPError, Integration


jobadder = Integration.load()

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
_DOWNLOAD_CHUNK_BYTES = 64 * 1024


def _job_body(inputs: dict[str, Any]) -> dict[str, Any]:
    """Map supplied job fields, preserving explicit nulls, false and zero."""
    fields = {
        "jobTitle": ("job_title", inputs["job_title"]),
        "companyId": ("company_id", inputs.get("company_id")),
        "contactId": ("contact_id", inputs.get("contact_id")),
        "jobDescription": ("job_description", inputs.get("job_description")),
        "statusId": ("status_id", inputs.get("status_id")),
        "userFavourite": ("user_favourite", inputs.get("user_favourite")),
        "category": ("category", inputs.get("category")),
        "location": ("location", inputs.get("location")),
        "workplaceAddressId": ("workplace_address_id", inputs.get("workplace_address_id")),
        "start": ("start", inputs.get("start")),
        "duration": ("duration", inputs.get("duration")),
        "workTypeId": ("work_type_id", inputs.get("work_type_id")),
        "salary": ("salary", inputs.get("salary")),
        "fee": ("fee", inputs.get("fee")),
        "numberOfJobs": ("number_of_jobs", inputs.get("number_of_jobs")),
        "source": ("source", inputs.get("source")),
        "custom": ("custom_fields", inputs.get("custom_fields")),
        "skillTags": ("skill_tags", inputs.get("skill_tags")),
        "ownerUserId": ("owner_user_id", inputs.get("owner_user_id")),
        "recruiterUserId": ("recruiter_user_ids", inputs.get("recruiter_user_ids")),
        "workflowId": ("workflow_id", inputs.get("workflow_id")),
        "workShift": ("work_shift", inputs.get("work_shift")),
        "endDate": ("end_date", inputs.get("end_date")),
    }
    return {provider: value for provider, (field, value) in fields.items() if field in inputs}


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


def _json_headers(inputs: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if inputs.get("allow_duplicates"):
        headers["X-Allow-Duplicates"] = inputs["allow_duplicates"]
    return headers


def _update_action_error(exc: Exception) -> ActionError:
    """Expose JobAdder's duplicate override code from update conflicts."""
    if isinstance(exc, HTTPError) and exc.status == 409:
        override_code = next(
            (value for name, value in exc.headers.items() if name.lower() == "x-allow-duplicates"),
            None,
        )
        if override_code:
            return ActionError(message=f"{exc}. Retry with allow_duplicates={override_code} if intended.")
    return ActionError(message=str(exc))


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

    max_encoded_chars = 4 * ((MAX_ATTACHMENT_BYTES + 2) // 3)
    max_input_chars = max_encoded_chars + max_encoded_chars // 20
    if len(content) > max_input_chars:
        raise ValueError(f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit.")

    normalized_content = "".join(content.split())
    if len(normalized_content) > max_encoded_chars:
        raise ValueError(f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit.")

    try:
        file_bytes = base64.b64decode(normalized_content, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("The uploaded file content is not valid base64.") from exc

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")
    if len(file_bytes) > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB upload limit.")

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


async def _download_attachment(
    context: ExecutionContext,
    path: str,
    accept: str,
) -> tuple[bytes, dict[str, str]]:
    """Download binary content, which ExecutionContext.fetch does not preserve as bytes."""
    url = f"{get_api_base_url(context)}{path}"
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
                if declared_size is not None and declared_size > MAX_ATTACHMENT_BYTES:
                    raise ValueError(
                        f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB download limit."
                    )

            content = bytearray()
            while True:
                remaining = MAX_ATTACHMENT_BYTES + 1 - len(content)
                chunk = await response.content.read(min(_DOWNLOAD_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_ATTACHMENT_BYTES:
                    raise ValueError(
                        f"Attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB download limit."
                    )

            return bytes(content), dict(response.headers)


async def _download_candidate_attachment(
    context: ExecutionContext,
    candidate_id: int,
    attachment_id: int,
    accept: str,
) -> tuple[bytes, dict[str, str]]:
    return await _download_attachment(
        context,
        f"/candidates/{candidate_id}/attachments/{attachment_id}",
        accept,
    )


async def _download_job_attachment(
    context: ExecutionContext,
    job_id: int,
    attachment_id: int,
    accept: str,
) -> tuple[bytes, dict[str, str]]:
    return await _download_attachment(
        context,
        f"/jobs/{job_id}/attachments/{attachment_id}",
        accept,
    )


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


@jobadder.action("update_candidate")
class UpdateCandidateAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            fields = {
                "firstName": ("first_name", inputs.get("first_name")),
                "lastName": ("last_name", inputs.get("last_name")),
                "email": ("email", inputs.get("email")),
                "phone": ("phone", inputs.get("phone")),
                "mobile": ("mobile", inputs.get("mobile")),
                "salutation": ("salutation", inputs.get("salutation")),
                "statusId": ("status_id", inputs.get("status_id")),
                "rating": ("rating", inputs.get("rating")),
                "seeking": ("seeking", inputs.get("seeking")),
                "social": ("social", inputs.get("social")),
                "address": ("address", inputs.get("address")),
                "skillTags": ("skill_tags", inputs.get("skill_tags")),
                "customSkills": ("custom_skills", inputs.get("custom_skills")),
                "dateOfBirth": ("date_of_birth", inputs.get("date_of_birth")),
                "emergencyContact": ("emergency_contact", inputs.get("emergency_contact")),
                "emergencyPhone": ("emergency_phone", inputs.get("emergency_phone")),
                "employment": ("employment", inputs.get("employment")),
                "availability": ("availability", inputs.get("availability")),
                "education": ("education", inputs.get("education")),
                "custom": ("custom_fields", inputs.get("custom_fields")),
                "recruiterUserId": ("recruiter_user_ids", inputs.get("recruiter_user_ids")),
                "summary": ("summary", inputs.get("summary")),
                "unsubscribed": ("unsubscribed", inputs.get("unsubscribed")),
            }
            body = {
                provider_field: value
                for provider_field, (input_field, value) in fields.items()
                if input_field in inputs
            }
            if not body:
                return ActionError(message="Provide at least one candidate field to update.")

            await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}",
                method="PUT",
                headers=_json_headers(inputs),
                json=body,
            )
            return ActionResult(data={"updated": True, "candidate_id": inputs["candidate_id"]})
        except Exception as exc:
            return _update_action_error(exc)


@jobadder.action("list_candidate_statuses")
class ListCandidateStatusesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {
                key: value
                for key, value in {
                    "StatusId": inputs.get("status_ids"),
                    "Name": inputs.get("name"),
                    "Active": _boolean_query_value(inputs.get("active")),
                    "Default": _boolean_query_value(inputs.get("default")),
                }.items()
                if value is not None
            }
            return await _fetch_list(context, "/candidates/lists/status", "statuses", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("set_candidate_status")
class SetCandidateStatusAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body: dict[str, Any] = {"statusId": inputs["status_id"]}
            note = {}
            if "note_type" in inputs:
                note["type"] = inputs.get("note_type")
            if "note_text" in inputs:
                note["text"] = inputs.get("note_text")
            if note:
                body["note"] = note
            await context.fetch(
                f"{get_api_base_url(context)}/candidates/{inputs['candidate_id']}/status",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(
                data={
                    "updated": True,
                    "candidate_id": inputs["candidate_id"],
                    "status_id": inputs["status_id"],
                }
            )
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


@jobadder.action("update_contact")
class UpdateContactAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            fields = {
                "companyId": ("company_id", inputs.get("company_id")),
                "firstName": ("first_name", inputs.get("first_name")),
                "lastName": ("last_name", inputs.get("last_name")),
                "email": ("email", inputs.get("email")),
                "phone": ("phone", inputs.get("phone")),
                "mobile": ("mobile", inputs.get("mobile")),
                "salutation": ("salutation", inputs.get("salutation")),
                "position": ("position", inputs.get("position")),
                "statusId": ("status_id", inputs.get("status_id")),
                "recruiterUserId": ("recruiter_user_ids", inputs.get("recruiter_user_ids")),
                "ownerUserId": ("owner_user_id", inputs.get("owner_user_id")),
                "reportsToContactId": ("reports_to_contact_id", inputs.get("reports_to_contact_id")),
                "officeAddressId": ("office_address_id", inputs.get("office_address_id")),
                "otherEmail": ("other_emails", inputs.get("other_emails")),
                "social": ("social", inputs.get("social")),
                "summary": ("summary", inputs.get("summary")),
                "unsubscribed": ("unsubscribed", inputs.get("unsubscribed")),
                "custom": ("custom_fields", inputs.get("custom_fields")),
            }
            body = {
                provider_field: value
                for provider_field, (input_field, value) in fields.items()
                if input_field in inputs
            }
            if not body:
                return ActionError(message="Provide at least one contact field to update.")

            await context.fetch(
                f"{get_api_base_url(context)}/contacts/{inputs['contact_id']}",
                method="PUT",
                headers=_json_headers(inputs),
                json=body,
            )
            return ActionResult(data={"updated": True, "contact_id": inputs["contact_id"]})
        except Exception as exc:
            return _update_action_error(exc)


@jobadder.action("list_contact_statuses")
class ListContactStatusesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {
                key: value
                for key, value in {
                    "StatusId": inputs.get("status_ids"),
                    "Name": inputs.get("name"),
                    "Active": _boolean_query_value(inputs.get("active")),
                    "Default": _boolean_query_value(inputs.get("default")),
                }.items()
                if value is not None
            }
            return await _fetch_list(context, "/contacts/lists/status", "statuses", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("set_contact_status")
class SetContactStatusAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body: dict[str, Any] = {"statusId": inputs["status_id"]}
            note = {}
            if "note_type" in inputs:
                note["type"] = inputs.get("note_type")
            if "note_text" in inputs:
                note["text"] = inputs.get("note_text")
            if note:
                body["note"] = note
            await context.fetch(
                f"{get_api_base_url(context)}/contacts/{inputs['contact_id']}/status",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(
                data={
                    "updated": True,
                    "contact_id": inputs["contact_id"],
                    "status_id": inputs["status_id"],
                }
            )
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
            params = {
                key: value
                for key, value in {
                    "type": ",".join(inputs["types"]) if inputs.get("types") else None,
                    "latest": _boolean_query_value(inputs.get("latest")),
                    "offset": inputs.get("offset", 0),
                    "limit": inputs.get("limit", 100),
                }.items()
                if value is not None
            }
            return await _fetch_list(
                context,
                f"/jobs/{inputs['job_id']}/attachments",
                "attachments",
                params,
            )
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_attachment_categories")
class ListJobAttachmentCategoriesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            params = {"type": ",".join(inputs["types"])} if inputs.get("types") else None
            return await _fetch_list(context, "/jobs/lists/attachmentcategory", "categories", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("download_job_attachment")
class DownloadJobAttachmentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            content, headers = await _download_job_attachment(
                context,
                inputs["job_id"],
                inputs["attachment_id"],
                inputs.get("accept", "application/octet-stream"),
            )
            content_type = headers.get("Content-Type") or headers.get("content-type") or "application/octet-stream"
            file_name = inputs.get("file_name") or f"job-{inputs['job_id']}-attachment-{inputs['attachment_id']}"
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


@jobadder.action("upload_job_attachment")
class UploadJobAttachmentAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            file_bytes, file_name, content_type = _decode_file(inputs["file"])
            form = aiohttp.FormData()
            form.add_field("fileData", file_bytes, filename=file_name, content_type=content_type)
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/attachments/{inputs['attachment_type']}",
                method="POST",
                data=form,
            )
            return ActionResult(data={"attachment": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("update_job_attachment")
class UpdateJobAttachmentAction(ActionHandler):
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

            await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/attachments/{inputs['attachment_id']}",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"updated": True})
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


@jobadder.action("create_job")
class CreateJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs",
                method="POST",
                headers={"Content-Type": "application/json"},
                json=_job_body(inputs),
            )
            return ActionResult(data={"job": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("update_job")
class UpdateJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=_job_body(inputs),
            )
            return ActionResult(data={"updated": True, "job_id": inputs["job_id"]})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("set_job_status")
class SetJobStatusAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body: dict[str, Any] = {"statusId": inputs["status_id"]}
            note = {}
            if "note_type" in inputs:
                note["type"] = inputs.get("note_type")
            if "note_text" in inputs:
                note["text"] = inputs.get("note_text")
            if note:
                body["note"] = note
            await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/status",
                method="PUT",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"updated": True, "job_id": inputs["job_id"], "status_id": inputs["status_id"]})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("submit_candidate_to_evergreen_job")
class SubmitCandidateToEvergreenJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            fields = {
                "firstName": ("first_name", inputs["first_name"]),
                "lastName": ("last_name", inputs["last_name"]),
                "email": ("email", inputs["email"]),
                "source": ("source", inputs.get("source")),
                "salutation": ("salutation", inputs.get("salutation")),
                "phone": ("phone", inputs.get("phone")),
                "mobile": ("mobile", inputs.get("mobile")),
                "address": ("address", inputs.get("address")),
                "social": ("social", inputs.get("social")),
                "employment": ("employment", inputs.get("employment")),
                "availability": ("availability", inputs.get("availability")),
                "education": ("education", inputs.get("education")),
                "skillTags": ("skill_tags", inputs.get("skill_tags")),
                "screening": ("screening", inputs.get("screening")),
                "custom": ("custom_fields", inputs.get("custom_fields")),
            }
            body = {provider: value for provider, (field, value) in fields.items() if field in inputs}
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/applications/submit",
                method="POST",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"application": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_invoices")
class ListJobInvoicesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/invoices", method="GET"
            )
            # Unlike other lists, this endpoint returns {job, invoices}, not {items}.
            payload = response.data
            return ActionResult(data={"job": payload.get("job") or {}, "invoices": payload.get("invoices") or []})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_invoice")
class GetJobInvoiceAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/invoices/{inputs['invoice_id']}", method="GET"
            )
            # Preserve the provider's invoice, job and links together.
            return ActionResult(data={"invoice": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_rate_card")
class GetJobRateCardAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/ratecard", method="GET"
            )
            return ActionResult(data={"rate_card": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("add_job_rate_card")
class AddJobRateCardAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/ratecard/{inputs['rate_card_id']}", method="POST"
            )
            return ActionResult(data={"rate_card": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("update_job_rate_card")
class UpdateJobRateCardAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/ratecard/{inputs['rate_card_id']}", method="PUT"
            )
            return ActionResult(data={"rate_card": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("remove_job_rate_card")
class RemoveJobRateCardAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            await context.fetch(f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/ratecard", method="DELETE")
            return ActionResult(data={"removed": True, "job_id": inputs["job_id"]})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_sources")
class ListJobSourcesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, "/jobs/lists/source", "sources", {"name": inputs.get("name")})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("create_job_activity")
class CreateJobActivityAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            body: dict[str, Any] = {"activitySettingId": inputs["activity_setting_id"]}
            if "status_id" in inputs:
                body["statusId"] = inputs.get("status_id")
            if "answers" in inputs:
                body["answers"] = inputs.get("answers")
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/activities",
                method="POST",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"activity": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_activity")
class GetJobActivityAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/activities/{inputs['activity_id']}", method="GET"
            )
            return ActionResult(data={"activity": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("search_job_activities")
class SearchJobActivitiesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            created_at = _date_range(inputs.get("created_at_from"), inputs.get("created_at_to"))
            updated_at = _date_range(inputs.get("updated_at_from"), inputs.get("updated_at_to"))
            if not created_at and not updated_at:
                return ActionError(
                    message="Provide at least one date boundary: created_at_from, created_at_to, "
                    "updated_at_from, or updated_at_to. JobAdder requires a CreatedAt or UpdatedAt filter."
                )
            params = _pagination(inputs)
            params.update(
                {
                    "createdAt": created_at,
                    "updatedAt": updated_at,
                    "includeDetails": _boolean_query_value(inputs.get("include_details")),
                }
            )
            return await _fetch_list(context, "/jobs/activities", "activities", params)
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_activity_settings")
class ListJobActivitySettingsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, "/jobs/activitysettings", "activity_settings")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_activity_setting")
class GetJobActivitySettingAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/activitysettings/{inputs['setting_id']}", method="GET"
            )
            return ActionResult(data={"activity_setting": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("create_job_task")
class CreateJobTaskAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            fields = {
                "title": ("title", inputs["title"]),
                "assignees": ("assignee_user_ids", inputs["assignee_user_ids"]),
                "startAt": ("start_at", inputs.get("start_at")),
                "endAt": ("end_at", inputs.get("end_at")),
                "allDay": ("all_day", inputs.get("all_day")),
                "priority": ("priority", inputs.get("priority")),
                "candidates": ("candidate_ids", inputs.get("candidate_ids")),
                "jobs": ("job_ids", inputs.get("job_ids")),
                "placements": ("placement_ids", inputs.get("placement_ids")),
                "companies": ("company_ids", inputs.get("company_ids")),
                "contacts": ("contact_ids", inputs.get("contact_ids")),
                "applications": ("application_ids", inputs.get("application_ids")),
            }
            body = {provider: value for provider, (field, value) in fields.items() if field in inputs}
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/usertasks",
                method="POST",
                headers={"Content-Type": "application/json"},
                json=body,
            )
            return ActionResult(data={"task": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_task")
class GetJobTaskAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/{inputs['job_id']}/usertasks/{inputs['task_id']}", method="GET"
            )
            return ActionResult(data={"task": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_job_custom_fields")
class ListJobCustomFieldsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, "/jobs/fields/custom", "custom_fields")
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("get_job_custom_field")
class GetJobCustomFieldAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{get_api_base_url(context)}/jobs/fields/custom/{inputs['field_id']}", method="GET"
            )
            return ActionResult(data={"custom_field": response.data})
        except Exception as exc:
            return ActionError(message=str(exc))


@jobadder.action("list_deleted_jobs")
class ListDeletedJobsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext):
        try:
            return await _fetch_list(context, "/jobs/deleted", "jobs")
        except Exception as exc:
            return ActionError(message=str(exc))
