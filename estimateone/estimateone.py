"""E1 Supplier API: customer-authorized Speci-finder opportunity retrieval."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import ClientError

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, HTTPError, Integration

estimateone = Integration.load(str(Path(__file__).with_name("config.json")))
AUTH_URL = "https://auth.api.estimateone.com/oauth2/token"
API_URL = "https://api.estimateone.com/api/tender/supplier/v1/companies"


async def get_token(context: ExecutionContext) -> str:
    credentials = context.auth["credentials"]
    response = await context.fetch(
        AUTH_URL,
        method="POST",
        content_type="application/x-www-form-urlencoded",
        data={
            "grant_type": "client_credentials",
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        },
    )
    if not isinstance(response.data, dict) or not isinstance(response.data.get("access_token"), str):
        raise ValueError("E1 authentication returned no access token.")
    if not response.data["access_token"]:
        raise ValueError("E1 authentication returned an empty access token.")
    return response.data["access_token"]


MAX_RESULT_BYTES = 32 * 1024


def optional_text(value: Any) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("Unexpected project or tender text field.")
    return value


def compact_project(project: dict[str, Any], include_tenders: bool) -> dict[str, Any]:
    if not isinstance(project, dict) or not isinstance(project.get("projectId"), str):
        raise ValueError("Project is missing its projectId.")
    tenders = project.get("tenders")
    if not isinstance(tenders, list):
        raise ValueError("Project is missing its tender list.")
    budget = project.get("budget")
    if budget is None:
        budget = {}
    if not isinstance(budget, dict):
        raise ValueError("Project budget has an invalid shape.")
    for bound in ("low", "high"):
        value = budget.get(bound)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("Project budget has a non-numeric bound.")
    summary = {
        "id": project["projectId"],
        "name": optional_text(project.get("projectName")),
        "status": optional_text(project.get("status")),
        "category": optional_text(project.get("category")),
        "address": optional_text(project.get("address")),
        "created_at": optional_text(project.get("createdAt")),
        "budget": {"low": budget.get("low"), "high": budget.get("high")},
        "tender_count": len(tenders),
        "tenders": [],
    }
    if include_tenders:
        for tender in tenders:
            if not isinstance(tender, dict) or not isinstance(tender.get("id"), str):
                raise ValueError("Tender is missing its ID.")
            builder = tender.get("builder")
            if builder is None:
                builder = {}
            if not isinstance(builder, dict):
                raise ValueError("Tender builder has an invalid shape.")
            summary["tenders"].append(
                {
                    "id": tender["id"],
                    "name": optional_text(tender.get("name")),
                    "type": optional_text(tender.get("type")),
                    "builder": {"name": optional_text(builder.get("name"))},
                    "quotes_due_at": optional_text(tender.get("quotesDueAt")),
                }
            )
    return summary


def provider_error_body(body: Any, secrets: list[str]) -> str:
    """Keep bounded provider diagnostics without credentials or HTML."""

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: scrub(item)
                for key, item in value.items()
                if not any(
                    word in key.lower() for word in ("token", "secret", "password", "authorization", "client_id")
                )
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, str):
            if "<" in value or ">" in value:
                return "[HTML response omitted]"
            for secret in secrets:
                if secret:
                    value = value.replace(secret, "[redacted]")
            return re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", value)
        return value

    text = json.dumps(scrub(body), ensure_ascii=False) if body is not None else "No provider body supplied."
    return text if len(text) <= 2000 else text[:2000] + " [provider diagnostics truncated]"


def request_error(error: HTTPError, company_id: str, secrets: list[str], authenticating: bool = False) -> ActionError:
    if error.status == 429:
        guidance = (
            "Retrying this read is safe. Wait at least 300 seconds (E1's five-minute rate window), "
            "then call list_matched_projects again with the same company_id, cursor, and filters."
        )
    elif error.status in (401, 403) or (authenticating and error.status == 400):
        guidance = (
            "The user must fix the E1 connection, company registration, or Supplier API licence. "
            "Do not keep retrying. After access is restored, call list_matched_projects again "
            "with the registered company_id."
        )
    elif error.status == 400:
        guidance = (
            "Retrying the read is safe after correcting the input. Call list_matched_projects "
            "without cursor to restart the listing; use the same company_id and created_since "
            "when continuing with a cursor returned by that call."
        )
    else:
        guidance = (
            "Retrying this read is safe. Call list_matched_projects again with the same company_id "
            "and filters after 60 seconds; ask the user to check E1 access if the failure persists."
        )
    return ActionError(
        message=(
            f"list_matched_projects failed for company_id={company_id}: E1 HTTP {error.status}. "
            f"{guidance} Provider body: {provider_error_body(error.response_data, secrets)}"
        )
    )


@estimateone.action("list_matched_projects")
class ListMatchedProjectsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        company_id = inputs["company_id"]
        if not company_id.isascii() or not company_id.isdigit():
            return ActionError(
                message="Invalid company_id. Call list_matched_projects with the numeric supplier "
                "Account # supplied during E1 onboarding; no provider call was made. Retrying is safe."
            )
        created_since = inputs.get("created_since")
        if created_since:
            try:
                if not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", created_since
                ):
                    raise ValueError("Missing timestamp or offset.")
                datetime.fromisoformat(created_since.upper())
            except ValueError:
                return ActionError(
                    message="Invalid created_since. Call list_matched_projects with an RFC 3339 "
                    "timestamp including time and UTC offset, or omit created_since. "
                    "No provider call was made; retrying is safe."
                )
        limit = inputs.get("limit", 25)
        include_tenders = inputs.get("include_tenders", False)
        cursor = inputs.get("cursor")
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if created_since:
            params["createdSince"] = created_since
        credentials = context.auth["credentials"]
        secrets = [credentials["client_id"], credentials["client_secret"]]
        authenticating = True
        try:
            token = await get_token(context)
            secrets.append(token)
            authenticating = False
            headers = {
                "Authorization": f"Bearer {token}",
                "x-e1-client-id": context.auth["credentials"]["client_id"],
                "Accept": "application/json",
            }
            try:
                response = await context.fetch(
                    f"{API_URL}/{company_id}/speci-finder/results", headers=headers, params=params
                )
            except HTTPError as error:
                if error.status != 401:
                    raise
                authenticating = True
                token = await get_token(context)
                secrets.append(token)
                authenticating = False
                headers["Authorization"] = f"Bearer {token}"
                response = await context.fetch(
                    f"{API_URL}/{company_id}/speci-finder/results", headers=headers, params=params
                )
            body = response.data
            if not isinstance(body, dict) or not isinstance(body.get("data"), list):
                raise ValueError("Invalid project list.")
            metadata = body.get("_metadata")
            if not isinstance(metadata, dict) or not isinstance(metadata.get("hasNextPage"), bool):
                raise ValueError("Invalid pagination metadata.")
            next_cursor = metadata.get("nextCursor")
            if next_cursor is not None and not isinstance(next_cursor, str):
                raise ValueError("Invalid pagination cursor.")
            more = metadata["hasNextPage"]
            if more and (not next_cursor or next_cursor == cursor):
                raise ValueError("Pagination did not supply an advancing cursor.")
            if len(body["data"]) > limit:
                raise ValueError("Provider returned more projects than the requested limit.")
            projects = [compact_project(project, include_tenders) for project in body["data"]]
            message = "No more pages."
            if more:
                message = (
                    "More matches remain. Narrow new-project discovery with created_since, "
                    "or continue with next_cursor."
                )
            if not projects:
                message = (
                    "No live matches in this page. Call list_matched_projects without created_since to broaden "
                    "the listing."
                    if created_since
                    else "No live matches. Ask the user to check the supplier account's Speci-finder keywords."
                )
                if more:
                    message += " E1 reports another page; continue with next_cursor."
            data = {
                "company_id": company_id,
                "projects": projects,
                "returned_count": len(projects),
                "total_matching": None,
                "next_cursor": next_cursor if more else None,
                "has_next_page": more,
                "truncated": more,
                "message": message,
            }
            if len(json.dumps(data).encode("utf-8")) > MAX_RESULT_BYTES:
                return ActionError(
                    message="list_matched_projects exceeded the 32 KiB response limit; no partial page "
                    "was returned. Call list_matched_projects with include_tenders=false and a smaller "
                    "limit (minimum 1), keeping the same company_id, cursor, and filters. Retrying is safe."
                )
            return ActionResult(data=data)
        except HTTPError as error:
            return request_error(error, company_id, secrets, authenticating)
        except (TimeoutError, ClientError):
            return ActionError(
                message="list_matched_projects could not complete the E1 connection. Retrying this read is safe: call "
                "list_matched_projects again with the same company_id, cursor, and filters after 60 seconds."
            )
        except ValueError:
            return ActionError(
                message="E1 returned an invalid or incomplete response to list_matched_projects. "
                "No partial page was returned. Retrying this read is safe: call list_matched_projects "
                "again with the same company_id and filters after 60 seconds; ask the user to contact "
                "E1 support if it persists."
            )
