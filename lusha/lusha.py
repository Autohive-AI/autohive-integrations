"""Lusha v3 contact and company discovery and enrichment."""

from pathlib import Path
from typing import Any
from urllib.parse import quote

from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    HTTPError,
    Integration,
    RateLimitError,
)

lusha = Integration.load(str(Path(__file__).with_name("config.json")))
BASE_URL = "https://api.lusha.com/v3"


async def request(
    context: ExecutionContext,
    path: str,
    method: str = "POST",
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> ActionResult | ActionError:
    """Preserve billing, per-record failures and async job metadata from one call."""
    api_key = context.auth["credentials"]["api_key"].strip()
    if not api_key:
        return ActionError(message="Provide a non-empty Lusha API key.")
    try:
        response = await context.fetch(
            f"{BASE_URL}/{path}",
            method=method,
            headers={"api_key": api_key, "Accept": "application/json"},
            json=payload,
            params=params,
        )
    except RateLimitError as exc:
        return ActionError(message=f"Lusha rate limit exceeded. Retry after {exc.retry_after} seconds.")
    except HTTPError as exc:
        messages = {
            400: "Lusha rejected the request. Check identifiers, filter values and supported filter combinations.",
            401: "Lusha authentication failed. Check your API key and whether API access is enabled for your user.",
            402: "Insufficient Lusha credits. Check your account balance and plan.",
            403: "Lusha access denied. Check your plan, account permissions and requested reveal fields.",
            404: "Lusha resource not found. For an enrichment job, stop polling and keep the original results.",
            429: "Lusha rate limit exceeded. Wait before retrying.",
            503: "Lusha is temporarily unavailable. Retry later; an enrichment job may still exist.",
        }
        return ActionError(message=messages.get(exc.status, f"Lusha API request failed (HTTP {exc.status})."))
    if not isinstance(response.data, dict):
        return ActionError(message="Lusha returned an unexpected response; expected a JSON object.")
    return ActionResult(data=response.data)


def invalid_identifiers(items: list[dict[str, Any]], entity: str) -> ActionError | None:
    """Check identifier alternatives before spending credits on a batch."""
    for index, item in enumerate(items):
        if entity == "contacts":
            valid = any(item.get(key, "").strip() for key in ("id", "email", "linkedinUrl")) or (
                item.get("firstName", "").strip()
                and item.get("lastName", "").strip()
                and (item.get("companyName", "").strip() or item.get("companyDomain", "").strip())
            )
            hint = "id, email, linkedinUrl, or firstName + lastName + companyName/companyDomain"
        else:
            valid = any(item.get(key, "").strip() for key in ("id", "name", "domain"))
            hint = "id, name or domain"
        if not valid:
            return ActionError(message=f"{entity}[{index}] requires {hint}.")
    return None


@lusha.action("search_contacts")
class SearchContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        contacts = inputs["contacts"]
        error = invalid_identifiers(contacts, "contacts")
        if error:
            return error
        payload = {"contacts": contacts}
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "contacts/search", payload=payload)


@lusha.action("enrich_contacts")
class EnrichContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        ids = inputs["ids"]
        payload = {"ids": ids}
        if "reveal" in inputs:
            payload["reveal"] = inputs.get("reveal")
        if "waterfallEnabled" in inputs:
            payload["waterfallEnabled"] = inputs.get("waterfallEnabled")
        return await request(context, "contacts/enrich", payload=payload)


@lusha.action("search_and_enrich_contacts")
class SearchAndEnrichContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        contacts = inputs["contacts"]
        error = invalid_identifiers(contacts, "contacts")
        if error:
            return error
        payload = {"contacts": contacts}
        if "reveal" in inputs:
            payload["reveal"] = inputs.get("reveal")
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "contacts/search-and-enrich", payload=payload)


@lusha.action("search_companies")
class SearchCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        companies = inputs["companies"]
        error = invalid_identifiers(companies, "companies")
        if error:
            return error
        payload = {"companies": companies}
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "companies/search", payload=payload)


@lusha.action("enrich_companies")
class EnrichCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        ids = inputs["ids"]
        payload = {"ids": ids}
        if "reveal" in inputs:
            payload["reveal"] = inputs.get("reveal")
        return await request(context, "companies/enrich", payload=payload)


@lusha.action("search_and_enrich_companies")
class SearchAndEnrichCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        companies = inputs["companies"]
        error = invalid_identifiers(companies, "companies")
        if error:
            return error
        payload = {"companies": companies}
        if "reveal" in inputs:
            payload["reveal"] = inputs.get("reveal")
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "companies/search-and-enrich", payload=payload)


def has_filter_criteria(value: Any) -> bool:
    """Require a populated criterion; modifiers and empty containers do not narrow a search."""
    if isinstance(value, dict):
        return any(has_filter_criteria(item) for key, item in value.items() if key != "technologiesCondition")
    if isinstance(value, list):
        return any(has_filter_criteria(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


@lusha.action("prospect_contacts")
class ProspectContactsAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        filters = inputs["filters"]
        if not has_filter_criteria(filters):
            return ActionError(message="Provide at least one non-empty include or exclude prospecting criterion.")
        payload = {"filters": filters, "pagination": {"page": inputs.get("page", 0), "size": inputs.get("size", 25)}}
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "contacts/prospecting", payload=payload)


@lusha.action("prospect_companies")
class ProspectCompaniesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        filters = inputs["filters"]
        if not has_filter_criteria(filters):
            return ActionError(message="Provide at least one non-empty include or exclude prospecting criterion.")
        payload = {
            "filters": filters,
            "pagination": {"page": inputs.get("page", 0), "size": inputs.get("size", 25)},
        }
        if "options" in inputs:
            payload["options"] = inputs.get("options")
        return await request(context, "companies/prospecting", payload=payload)


@lusha.action("list_filter_types")
class ListFilterTypesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        return await request(context, f"{inputs['entity']}/prospecting/filters", method="GET")


@lusha.action("get_filter_values")
class GetFilterValuesAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        entity = inputs["entity"]
        filter_type = inputs["filter_type"]
        query = inputs.get("query", "").strip()
        # Discovery may expose new types; leave their validation to Lusha.
        if filter_type in {"locations", "names", "technologies", "jobTitles"} and len(query) < 2:
            return ActionError(message=f"Filter {filter_type} requires a query of at least 2 characters.")
        return await request(
            context,
            f"{entity}/prospecting/filters/{quote(filter_type, safe='')}",
            method="GET",
            params={"query": query} if query else None,
        )


@lusha.action("get_account_usage")
class GetAccountUsageAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        return await request(context, "account/usage", method="GET")


@lusha.action("get_contact_enrichment_job")
class GetContactEnrichmentJobAction(ActionHandler):
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> ActionResult | ActionError:
        job_id = quote(inputs["job_id"], safe="")
        return await request(context, f"contacts/jobs/{job_id}", method="GET")
