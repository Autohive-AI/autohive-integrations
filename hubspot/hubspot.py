"""HubSpot Integration Actions Module"""

from typing import Any, Callable, Dict
from collections import Counter
from datetime import datetime, timezone
import asyncio
import math
import re

import aiohttp

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    HTTPError,
)

# HubSpot integration with UTC date handling
hubspot = Integration.load()

# All timestamps are handled in UTC format


def parse_date_string_to_utc(date_str):
    """Parse various date formats and return UTC datetime for HubSpot API."""
    if not date_str:
        return None

    date_str_clean = date_str.strip()

    # List of supported date formats
    date_formats = [
        "%Y-%m-%d",  # 2025-08-22
        "%d %b %Y %I:%M %p",  # 22 Aug 2025 3:46 PM
        "%d %b %Y",  # 22 Aug 2025
        "%Y-%m-%d %H:%M:%S",  # 2025-08-22 15:46:00
        "%m/%d/%Y",  # 08/22/2025
        "%d/%m/%Y",  # 22/08/2025
    ]

    parsed_dt = None
    for fmt in date_formats:
        try:
            parsed_dt = datetime.strptime(date_str_clean, fmt)
            break
        except ValueError:
            continue

    if parsed_dt is None:
        raise ValueError(
            f"Unable to parse date '{date_str}'. Supported formats: YYYY-MM-DD, "
            "DD MMM YYYY H:MM PM, DD/MM/YYYY, MM/DD/YYYY. Use explicit dates instead of relative formats."
        )

    # Treat parsed datetime as UTC
    return parsed_dt


def convert_hubspot_timestamp_to_utc_string(timestamp_data):
    """Convert HubSpot timestamp to readable UTC string."""
    if not timestamp_data:
        return None
    try:
        # Handle both millisecond timestamps and ISO date strings
        if isinstance(timestamp_data, str) and timestamp_data.endswith("Z"):
            # ISO date string format like "2025-09-03T23:45:17.790Z"
            utc_dt = datetime.fromisoformat(timestamp_data.replace("Z", "+00:00"))
        else:
            # HubSpot millisecond timestamp
            utc_dt = datetime.fromtimestamp(int(timestamp_data) / 1000, tz=timezone.utc)

        # Return UTC formatted string
        return utc_dt.strftime("%d %b %Y %I:%M %p UTC")
    except (ValueError, TypeError):
        return None


# HubSpot CRM property internal names; default set matches create_task / update_task (hs_* and hubspot_owner_id).
_DEFAULT_HS_TASK_PROPERTY_NAMES = (
    "hs_task_body",
    "hs_task_subject",
    "hs_task_status",
    "hs_task_priority",
    "hs_task_type",
    "hubspot_owner_id",
    "hs_task_reminders",
    "hs_timestamp",
    "hs_createdate",
    "hs_lastmodifieddate",
)

_TASK_TIMESTAMP_FIELDS_READABLE_UTC = (
    "hs_timestamp",
    "hs_createdate",
    "hs_lastmodifieddate",
)


def _apply_readable_utc_to_task_properties(properties: Dict[str, Any]) -> None:
    """Mutate a task properties dict: HubSpot ms / ISO timestamps to readable UTC strings."""
    for field in _TASK_TIMESTAMP_FIELDS_READABLE_UTC:
        if field in properties and properties[field]:
            properties[field] = convert_hubspot_timestamp_to_utc_string(properties[field])


def convert_deal_dates_to_utc(deal):
    """Convert deal date properties from UTC timestamps to readable UTC strings."""
    if not deal or not isinstance(deal, dict):
        return deal

    properties = deal.get("properties", {})
    date_fields = [
        "closedate",
        "createdate",
        "hs_lastmodifieddate",
        "notes_last_contacted",
        "hs_last_sales_activity_timestamp",
        "hs_latest_meeting_activity",
        "hs_last_email_activity",
        "hs_last_call_activity",
        "hs_last_sales_activity_date",
    ]

    for field in date_fields:
        if field in properties and properties[field]:
            utc_date = convert_hubspot_timestamp_to_utc_string(properties[field])
            if utc_date:
                properties[field] = utc_date

    return deal


async def parse_response(response):
    return response.data


def is_rate_limit_error(error: Exception) -> bool:
    """Return whether an exception is a HubSpot 429 response.

    Checks the HTTP status, not the message, so a server error that mentions "429" isn't resent.
    """
    return getattr(error, "status", None) == 429


# Errors from a request that may or may not have reached HubSpot
REQUEST_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, HTTPError)


def _error_text(error: Exception) -> str:
    """Return an error's message, or its type for errors like TimeoutError that have none."""
    return str(error) or type(error).__name__


def _outcome_unknown(error: Exception) -> bool:
    """Return whether HubSpot may still have applied a write that failed with this error."""
    return not isinstance(error, HTTPError) or error.status >= 500


def _property_value(value: Any) -> str:
    """Return a value in HubSpot's string form: "true"/"false", "" to clear, and "a;b" for multi-select options."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ";".join(_property_value(item) for item in value)
    return str(value)


def _unfinished_batch_reason(data: Dict[str, Any]) -> str | None:
    """Return why a HubSpot batch response is not final, or None when it completed."""
    if data.get("status") == "CANCELED":
        return "canceled"
    if data.get("status") in ("PENDING", "PROCESSING"):
        return "is still processing"
    return None


def get_retry_after_seconds(error: Exception, fallback_seconds: int, max_delay_seconds: int = 10) -> int:
    """Return provider-supplied retry delay when available."""
    retry_after = getattr(error, "retry_after", None)
    if retry_after is None:
        return min(fallback_seconds, max_delay_seconds)
    try:
        return min(max(int(retry_after), 0), max_delay_seconds)
    except (TypeError, ValueError):
        return min(fallback_seconds, max_delay_seconds)


async def fetch_with_rate_limit_retries(
    context: ExecutionContext,
    url: str,
    max_retries: int = 3,
    max_total_sleep_seconds: int = 10,
    retry_sleep_budget: Dict[str, int] | None = None,
    resend_on_connection_error: bool = True,
    **kwargs,
):
    """Fetch with a bounded backoff for transient HubSpot 429 responses.

    Pass resend_on_connection_error=False for writes that aren't safe to repeat. The SDK otherwise resends
    the request after a dropped connection or timeout, when HubSpot may already have applied it.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if max_total_sleep_seconds < 0:
        raise ValueError("max_total_sleep_seconds must be >= 0")

    delay_seconds = 1
    if retry_sleep_budget is None:
        retry_sleep_budget = {"remaining": max_total_sleep_seconds}
    retry_sleep_budget["remaining"] = min(
        retry_sleep_budget.get("remaining", max_total_sleep_seconds),
        max_total_sleep_seconds,
    )

    if not resend_on_connection_error:
        # Starting at the SDK's retry limit makes it raise instead of resending
        kwargs["retry_count"] = context.config["max_retries"]

    for attempt in range(max_retries + 1):
        try:
            return await context.fetch(url, **kwargs)
        except Exception as e:
            if attempt == max_retries or not is_rate_limit_error(e):
                raise
            remaining_sleep_seconds = retry_sleep_budget.get("remaining", 0)
            if remaining_sleep_seconds <= 0:
                raise
            sleep_seconds = min(get_retry_after_seconds(e, delay_seconds), remaining_sleep_seconds)
            await asyncio.sleep(sleep_seconds)
            retry_sleep_budget["remaining"] = remaining_sleep_seconds - sleep_seconds
            delay_seconds *= 2


ASSOCIATIONS_API_URL = "https://api.hubapi.com/crm/associations/2026-09"
OBJECTS_API_URL = "https://api.hubapi.com/crm/objects/2026-09"

# HubSpot reads at most 1,000 records' links in one batch request
MAX_ASSOCIATION_READ_INPUTS = 1000

# Requests one links lookup makes before stopping, so a cursor that never ends can't loop forever
MAX_ASSOCIATION_READ_REQUESTS = 20


async def _read_associations(
    context: ExecutionContext,
    from_type: str,
    to_type: str,
    object_ids: list[str],
    retry_sleep_budget: Dict[str, int],
    limit: int | None = None,
) -> tuple[Dict[str, list], set[str]]:
    """Return each record's links to records of to_type, keyed by record ID, and the IDs that have more.

    Follows each record's paging cursor until it has `limit` links, or all of them when limit is None, for up to
    MAX_ASSOCIATION_READ_REQUESTS requests. Each link is HubSpot's {toObjectId, associationTypes: [{category,
    typeId, label}]}. Raises ValueError when HubSpot can't read them.
    """
    links: Dict[str, list] = {str(object_id): [] for object_id in object_ids}
    has_more: set[str] = set()
    pending = [{"id": object_id} for object_id in links]
    for _ in range(MAX_ASSOCIATION_READ_REQUESTS):
        if not pending:
            break
        inputs, pending = pending[:MAX_ASSOCIATION_READ_INPUTS], pending[MAX_ASSOCIATION_READ_INPUTS:]
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{ASSOCIATIONS_API_URL}/{from_type}/{to_type}/batch/read",
                retry_sleep_budget=retry_sleep_budget,
                method="POST",
                json={"inputs": inputs},
                headers={"Content-Type": "application/json"},
            )
        except HTTPError as e:
            # As with HubSpot's object batch reads, a 404 may mean none of these records has a link of this type
            if e.status == 404:
                continue
            raise
        data = await parse_response(response) or {}
        reason = _unfinished_batch_reason(data)
        if reason:
            raise ValueError(f"HubSpot {reason} the linked {to_type} lookup")
        # A record with nothing of this type linked comes back as an OBJECT_NOT_FOUND error and is left out of
        # results; any other error means its links couldn't be read
        for error in data.get("errors", []):
            if error.get("category") != "OBJECT_NOT_FOUND":
                raise ValueError(f"Could not read linked {to_type}: {error.get('message') or error.get('category')}")
        for row in data.get("results", []):
            object_id = str(row["from"]["id"])
            record_links = links.setdefault(object_id, [])
            record_links.extend(row.get("to", []))
            after = ((row.get("paging") or {}).get("next") or {}).get("after")
            if limit is not None and len(record_links) >= limit:
                if after or len(record_links) > limit:
                    has_more.add(object_id)
                del record_links[limit:]
            elif after:
                pending.append({"id": object_id, "after": after})
    # Records still waiting on a page when the request cap was reached
    has_more.update(str(request["id"]) for request in pending)
    return links, has_more


async def _record_associations(
    record_type: str,
    record_id: str,
    inputs: Dict[str, Any],
    default_types: list[str],
    context: ExecutionContext,
) -> Dict[str, Any] | ActionError:
    """Return one record's links to each requested type, for the get_*_associations actions.

    A type HubSpot can't read is reported under "errors" rather than shown as having no links.
    """
    limit = inputs.get("limit", 100)
    retry_sleep_budget = {"remaining": 10}
    associations, summary, has_more, errors = {}, {}, {}, {}
    for association_type in inputs.get("association_types", default_types):
        try:
            links, truncated = await _read_associations(
                context, record_type, association_type, [record_id], retry_sleep_budget, limit
            )
        except (*REQUEST_ERRORS, ValueError) as e:
            errors[association_type] = _error_text(e)
            continue
        associations[association_type] = links[str(record_id)]
        summary[f"{association_type}_count"] = len(associations[association_type])
        has_more[association_type] = str(record_id) in truncated

    if errors and not associations:
        details = "; ".join(f"{association_type}: {message}" for association_type, message in errors.items())
        return ActionError(message=f"Failed to read associations for {record_type} {record_id}: {details}")
    data = {
        "associations": associations,
        "total_associations": sum(len(links) for links in associations.values()),
        "summary": summary,
        "has_more": has_more,
    }
    if errors:
        data["errors"] = errors
    return data


async def _association_labels(
    context: ExecutionContext, from_type: str, to_type: str, retry_sleep_budget: Dict[str, int]
) -> list[Dict[str, Any]]:
    """Return the association types between two object types: [{category, typeId, label}]."""
    response = await fetch_with_rate_limit_retries(
        context,
        f"{ASSOCIATIONS_API_URL}/{from_type}/{to_type}/labels",
        retry_sleep_budget=retry_sleep_budget,
        headers={"Content-Type": "application/json"},
    )
    return (await parse_response(response)).get("results", [])


# Contact Management Actions


@hubspot.action("get_contact")
class GetContactActionHandler(ActionHandler):
    """
    Action handler to retrieve a HubSpot contact by ID or email.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_contact action.

        :param inputs: Dictionary with "contact_id" or "email", and optional "properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with contact information.
        """
        contact_id = inputs.get("contact_id")
        email = inputs.get("email")
        properties = inputs.get(
            "properties",
            ["email", "firstname", "lastname", "phone", "company", "jobtitle"],
        )

        if contact_id:
            try:
                response = await fetch_with_rate_limit_retries(
                    context,
                    f"{OBJECTS_API_URL}/contacts/{contact_id}",
                    params={"properties": ",".join(properties)},
                    headers={"Content-Type": "application/json"},
                )
            except HTTPError as e:
                if e.status == 404:
                    return ActionError(message="Contact not found")
                raise
            return ActionResult(data={"contact": await parse_response(response)}, cost_usd=None)
        if not email:
            return ActionError(message="Give contact_id or email")

        # Get contact by email using v3 search API
        search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        search_body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email,
                        }
                    ]
                }
            ],
            "properties": properties,
            "limit": 1,
        }

        search_response = await fetch_with_rate_limit_retries(
            context,
            search_url,
            method="POST",
            json=search_body,
            headers={"Content-Type": "application/json"},
        )
        search_result = await parse_response(search_response)

        if not search_result.get("results"):
            return ActionError(message="Contact not found")

        contact = search_result["results"][0]

        return ActionResult(data={"contact": contact}, cost_usd=None)


@hubspot.action("get_contact_notes")
class GetContactNotesActionHandler(ActionHandler):
    """
    Action handler to retrieve notes associated with a HubSpot contact.

    Fetches all notes for a specific contact using the CRM search API with association filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_contact_notes action.

        :param inputs: Dictionary with key "contact_id" and optional "limit" and "properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with notes for the contact.
        """
        contact_id = inputs["contact_id"]
        limit = min(inputs.get("limit", 100), 200)  # Max 200 per HubSpot API
        properties = inputs.get(
            "properties",
            [
                "hs_note_body",
                "hs_timestamp",
                "hubspot_owner_id",
                "hs_createdate",
                "hs_lastmodifieddate",
            ],
        )

        try:
            # Use search API to find notes associated with this contact
            search_url = "https://api.hubapi.com/crm/v3/objects/notes/search"
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "associations.contact",
                                "operator": "EQ",
                                "value": contact_id,
                            }
                        ]
                    }
                ],
                "properties": properties,
                "limit": limit,
                "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
            }
            if inputs.get("after"):
                search_body["after"] = inputs["after"]

            response = await fetch_with_rate_limit_retries(
                context,
                search_url,
                method="POST",
                json=search_body,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            notes = result.get("results", [])

            # Convert timestamps to UTC strings
            for note in notes:
                if "properties" in note:
                    props = note["properties"]
                    for timestamp_field in [
                        "hs_timestamp",
                        "hs_createdate",
                        "hs_lastmodifieddate",
                    ]:
                        if timestamp_field in props and props[timestamp_field]:
                            props[timestamp_field] = convert_hubspot_timestamp_to_utc_string(props[timestamp_field])

            after = ((result.get("paging") or {}).get("next") or {}).get("after")
            return ActionResult(
                data={
                    "contact_id": contact_id,
                    "notes": notes,
                    "total": len(notes),
                    "total_matching": result.get("total", len(notes)),
                    "has_more": after is not None,
                    "after": after,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve notes: {str(e)}")


@hubspot.action("create_note")
class CreateNoteActionHandler(ActionHandler):
    """
    Action handler to create a note and associate it with a HubSpot contact, company, or deal.

    Creates a new note using the CRM API and associates it with specified CRM objects.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the create_note action.

        :param inputs: Dictionary with "note_body" and "associations" (contact_id, company_id, or deal_id).
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the created note information.
        """
        note_body = inputs["note_body"]
        timestamp = inputs.get("timestamp")  # Optional custom timestamp in milliseconds

        # Build the note properties
        properties = {
            "hs_note_body": note_body,
            "hs_timestamp": str(timestamp or int(datetime.now(timezone.utc).timestamp() * 1000)),
        }

        # Build associations array
        associations = []

        # Allow direct associations payload (HubSpot-native format)
        if inputs.get("associations"):
            associations.extend(inputs["associations"])

        # Associate with contact (convenience shorthand)
        if inputs.get("contact_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["contact_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 202,
                        }
                    ],
                }
            )

        # Associate with company (convenience shorthand)
        if inputs.get("company_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["company_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 190,
                        }
                    ],
                }
            )

        # Associate with deal (convenience shorthand)
        if inputs.get("deal_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["deal_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 214,
                        }
                    ],
                }
            )

        try:
            url = "https://api.hubapi.com/crm/v3/objects/notes"
            payload = {"properties": properties, "associations": associations}

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                method="POST",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            return ActionResult(
                data={
                    "note": result,
                    "success": True,
                    "message": "Note created successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to create note: {str(e)}")


@hubspot.action("update_note")
class UpdateNoteActionHandler(ActionHandler):
    """
    Action handler to update an existing note in HubSpot.

    Updates the note body or other properties of an existing note.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the update_note action.

        :param inputs: Dictionary with "note_id" and "note_body" or other properties to update.
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the updated note information.
        """
        note_id = inputs["note_id"]

        # Build properties to update
        properties = {}

        if inputs.get("note_body"):
            properties["hs_note_body"] = inputs["note_body"]

        if inputs.get("timestamp"):
            properties["hs_timestamp"] = str(inputs["timestamp"])

        # Allow additional properties to be updated
        if inputs.get("additional_properties"):
            properties.update(inputs["additional_properties"])

        if not properties:
            return ActionError(message="No properties provided to update")

        try:
            url = f"https://api.hubapi.com/crm/v3/objects/notes/{note_id}"
            payload = {"properties": properties}

            response = await context.fetch(
                url,
                method="PATCH",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            return ActionResult(
                data={
                    "note": result,
                    "success": True,
                    "message": "Note updated successfully",
                    "updated_properties": properties,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to update note: {str(e)}")


@hubspot.action("delete_note")
class DeleteNoteActionHandler(ActionHandler):
    """
    Action handler to delete a note from HubSpot.

    Permanently deletes a note by its ID.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the delete_note action.

        :param inputs: Dictionary with "note_id".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary indicating success or failure.
        """
        note_id = inputs["note_id"]

        try:
            url = f"https://api.hubapi.com/crm/v3/objects/notes/{note_id}"

            await context.fetch(
                url,
                method="DELETE",
                headers={"Content-Type": "application/json"},
            )

            # DELETE returns 204 No Content on success
            return ActionResult(
                data={
                    "success": True,
                    "message": f"Note {note_id} deleted successfully",
                    "note_id": note_id,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to delete note: {str(e)}")


# Communications (LinkedIn messages)

COMMUNICATIONS_API_URL = "https://api.hubapi.com/crm/v3/objects/communications"
CONTACTS_SEARCH_API_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"
CONTACTS_BATCH_READ_API_URL = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
CONTACTS_BATCH_UPSERT_API_URL = "https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert"

# HubSpot-defined association type IDs from a communication to other records
COMMUNICATION_TO_CONTACT_ASSOCIATION_ID = 81
COMMUNICATION_TO_COMPANY_ASSOCIATION_ID = 87
COMMUNICATION_TO_DEAL_ASSOCIATION_ID = 85

# Number of matching contacts returned as candidates when a name or email is ambiguous
CONTACT_MATCH_LIMIT = 5

# HubSpot allows 5 CRM search requests per second per account; space name searches to stay under it
NAME_SEARCH_INTERVAL_SECONDS = 0.25


def _hubspot_defined_association(record_id: Any, association_type_id: int) -> Dict[str, Any]:
    return {
        "to": {"id": str(record_id)},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type_id}],
    }


def _linked_id(row: Dict[str, Any], field: str) -> str:
    return str(row.get(field) or "").strip()


# hs_timestamp must fall between 1970 and the end of year 9999
MAX_TIMESTAMP_MS = 253402300800000
TIMESTAMP_FORMAT_HINT = "Unix milliseconds or an ISO 8601 date such as 2026-10-21T09:30:00Z"


def _timestamp_ms(timestamp: Any) -> str | None:
    """Return a timestamp as Unix milliseconds (now when empty), or None if it can't be read.

    Dates are converted here rather than sent as text, so HubSpot never sees a format it might reject
    along with the whole batch. Plain digits are milliseconds; a date without a time zone is read as UTC.
    """
    if timestamp is None or timestamp == "":
        return str(int(datetime.now(timezone.utc).timestamp() * 1000))
    if isinstance(timestamp, bool):
        return None
    if isinstance(timestamp, int):
        milliseconds = timestamp
    elif isinstance(timestamp, float):
        if not math.isfinite(timestamp):
            return None
        milliseconds = int(timestamp)
    else:
        text = str(timestamp).strip()
        if re.fullmatch(r"[0-9]+", text):
            # Anything longer than MAX_TIMESTAMP_MS is out of range, and huge digit strings can't be converted
            if len(text) > len(str(MAX_TIMESTAMP_MS)):
                return None
            milliseconds = int(text)
        else:
            try:
                parsed = datetime.fromisoformat(re.sub(r"[zZ]$", "+00:00", text))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            milliseconds = int(parsed.timestamp() * 1000)
    return str(milliseconds) if 0 <= milliseconds < MAX_TIMESTAMP_MS else None


def _row_identifier(row: Dict[str, Any]) -> tuple[str, Any, str] | None:
    """Return (kind, lookup key, label) for how a message row identifies its contact, or None.

    kind is "contact_id", "email" (key is the lowercased email) or "name" (key is (first, last)).
    """
    contact_id = (row.get("contact_id") or "").strip()
    if contact_id:
        return "contact_id", contact_id, f"contact_id:{contact_id}"
    email = (row.get("email") or "").strip()
    if email:
        return "email", email.lower(), f"email:{email}"
    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    if first_name and last_name:
        return "name", (first_name, last_name), f"name:{first_name} {last_name}"
    return None


def _status_counts(results: list[Dict[str, Any]], statuses: tuple[str, ...]) -> Dict[str, int]:
    counts = Counter(result["status"] for result in results)
    return {status: counts[status] for status in statuses}


def _match_batch_results(
    data: Dict[str, Any],
    trace_ids: list[str],
    missing_message: str,
    trace_id_for: Callable[[Dict[str, Any]], str | None] | None = None,
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Match a HubSpot batch response to its input rows.

    Returns ({trace_id: returned item}, {trace_id: error}) so every trace ID lands in exactly one.
    Results are matched on the echoed objectWriteTraceId, or on trace_id_for(item) when HubSpot
    doesn't echo it. Errors are matched via context.objectWriteTraceId. If some results still
    can't be attributed: when every row came back they all count as done (with an empty item);
    otherwise the unmatched rows fail with a warning, because a blind retry could duplicate the
    rows that did succeed.
    """
    items = data.get("results", [])
    trace_id_set = set(trace_ids)
    items_by_trace = {}
    leftover_items = []
    for item in items:
        trace_id = item.get("objectWriteTraceId") or (trace_id_for(item) if trace_id_for else None)
        if trace_id in trace_id_set:
            items_by_trace[trace_id] = item
        else:
            leftover_items.append(item)

    messages_by_trace: Dict[str, list[str]] = {}
    unmapped = []
    for error in data.get("errors", []):
        message = error.get("message", "")
        error_trace_ids = (error.get("context") or {}).get("objectWriteTraceId") or []
        for trace_id in error_trace_ids:
            messages_by_trace.setdefault(str(trace_id), []).append(message)
        if not error_trace_ids:
            unmapped.append(message)
    warnings = []
    reason = _unfinished_batch_reason(data)
    if reason:
        # An unfinished or canceled batch may have written some rows, so a retry could write them twice
        warnings.append(f"HubSpot {reason} this batch; check HubSpot before retrying")

    # When the leftover results match the rows with no result or error of their own, those rows all succeeded.
    # A single pair can only belong together; otherwise which ID is which row is unknown, so the item is empty.
    leftover_trace_ids = [t for t in trace_ids if t not in items_by_trace and t not in messages_by_trace]
    if leftover_items and len(leftover_items) == len(leftover_trace_ids):
        only_item = leftover_items[0] if len(leftover_items) == 1 else {}
        items_by_trace.update({trace_id: only_item for trace_id in leftover_trace_ids})
    elif leftover_items:
        warnings.insert(
            0,
            f"HubSpot completed {len(items)} of {len(trace_ids)} rows without saying which; "
            "check HubSpot before retrying",
        )
    batch_error = "; ".join(warnings + unmapped) or None

    errors_by_trace = {
        trace_id: "; ".join(messages_by_trace.get(trace_id, [])) or batch_error or missing_message
        for trace_id in trace_ids
        if trace_id not in items_by_trace
    }
    return items_by_trace, errors_by_trace


async def _find_contact_ids_by_email(
    emails: list[str], context: ExecutionContext, retry_sleep_budget: Dict[str, int]
) -> tuple[Dict[str, str], Dict[str, str]]:
    """Return ({lowercased email: contact ID}, {email: lookup error}) for the given emails using one batch read.

    Batch read looks contacts up by their unique email directly, so it doesn't depend on the
    search index (which can lag behind newly created contacts) or the search rate limit.
    """
    try:
        response = await fetch_with_rate_limit_retries(
            context,
            CONTACTS_BATCH_READ_API_URL,
            retry_sleep_budget=retry_sleep_budget,
            method="POST",
            json={
                "idProperty": "email",
                "inputs": [{"id": email} for email in emails],
                "properties": ["email", "hs_additional_emails"],
                "propertiesWithHistory": [],
            },
            headers={"Content-Type": "application/json"},
        )
    except HTTPError as e:
        # HubSpot answers 404 when none of the emails match a contact
        if e.status == 404:
            return {}, {}
        raise
    data = await parse_response(response) or {}
    contact_ids_by_email = {}
    for contact in data.get("results", []):
        properties = contact.get("properties") or {}
        # A contact can be found by an additional email, which HubSpot returns in hs_additional_emails
        additional_emails = re.split(r"[;,]", properties.get("hs_additional_emails") or "")
        for address in [properties.get("email") or "", *additional_emails]:
            if address.strip():
                contact_ids_by_email[address.strip().lower()] = str(contact["id"])

    # Only OBJECT_NOT_FOUND means a contact is missing; an unfinished batch or any other error is a failed lookup
    unmatched = [email for email in emails if email not in contact_ids_by_email]
    errors_by_email: Dict[str, str] = {}
    reason = _unfinished_batch_reason(data)
    if reason:
        errors_by_email.update({email: f"HubSpot {reason} the lookup" for email in unmatched})
    for error in data.get("errors", []):
        if error.get("category") == "OBJECT_NOT_FOUND":
            continue
        error_emails = [str(i).lower() for i in (error.get("context") or {}).get("ids") or []] or unmatched
        for email in error_emails:
            if email in unmatched:
                errors_by_email[email] = error.get("message") or "HubSpot could not look up this email"
    return contact_ids_by_email, errors_by_email


async def _check_object_ids(
    object_type: str, object_ids: list[str], context: ExecutionContext, retry_sleep_budget: Dict[str, int]
) -> Dict[str, str | None]:
    """Return {ID: None if it exists, "missing", or a lookup error} for one object type using one batch read.

    HubSpot rejects a whole batch create when one association points at a missing record, so
    missing IDs are found first and only those rows are skipped.
    """
    # HubSpot record IDs are plain numbers; a malformed ID could fail the whole lookup, so it is never sent
    checked: Dict[str, str | None] = {i: "missing" for i in object_ids if not re.fullmatch(r"[1-9][0-9]*", i)}
    to_read = [object_id for object_id in object_ids if object_id not in checked]
    if not to_read:
        return checked
    try:
        response = await fetch_with_rate_limit_retries(
            context,
            f"https://api.hubapi.com/crm/v3/objects/{object_type}/batch/read",
            retry_sleep_budget=retry_sleep_budget,
            method="POST",
            json={"inputs": [{"id": object_id} for object_id in to_read], "properties": []},
            headers={"Content-Type": "application/json"},
        )
        data = await parse_response(response) or {}
    except HTTPError as e:
        # HubSpot answers 404 when none of the IDs match a record
        if e.status == 404:
            return {**checked, **dict.fromkeys(to_read, "missing")}
        return {**checked, **dict.fromkeys(to_read, _error_text(e))}
    except REQUEST_ERRORS as e:
        return {**checked, **dict.fromkeys(to_read, _error_text(e))}

    # Returned IDs exist. Of the rest, only IDs HubSpot names as not found are missing:
    # a merged record's old ID still resolves, under the surviving record's ID
    returned = {str(item.get("id")) for item in data.get("results", [])}
    unreturned = [object_id for object_id in to_read if object_id not in returned]
    checked.update(dict.fromkeys(to_read))
    reason = _unfinished_batch_reason(data)
    if reason:
        checked.update(dict.fromkeys(unreturned, f"HubSpot {reason} the lookup"))
    for error in data.get("errors", []):
        error_ids = [str(i) for i in (error.get("context") or {}).get("ids") or []] or unreturned
        for object_id in error_ids:
            if object_id in unreturned:
                is_missing = error.get("category") == "OBJECT_NOT_FOUND"
                checked[object_id] = "missing" if is_missing else error.get("message") or "HubSpot lookup failed"
    return checked


async def _find_contact_ids_by_name(
    first_name: str, last_name: str, context: ExecutionContext, retry_sleep_budget: Dict[str, int]
) -> list[str]:
    """Return the IDs of contacts whose first and last name exactly match."""
    filters = [
        {"propertyName": "firstname", "operator": "EQ", "value": first_name},
        {"propertyName": "lastname", "operator": "EQ", "value": last_name},
    ]
    response = await fetch_with_rate_limit_retries(
        context,
        CONTACTS_SEARCH_API_URL,
        retry_sleep_budget=retry_sleep_budget,
        method="POST",
        json={"filterGroups": [{"filters": filters}], "properties": ["email"], "limit": CONTACT_MATCH_LIMIT},
        headers={"Content-Type": "application/json"},
    )
    data = await parse_response(response) or {}
    return [str(contact["id"]) for contact in data.get("results", [])]


# (row field, CRM object type, communication association type ID) for records a message can also link to
LINKED_RECORD_TYPES = (
    ("company_id", "companies", COMMUNICATION_TO_COMPANY_ASSOCIATION_ID),
    ("deal_id", "deals", COMMUNICATION_TO_DEAL_ASSOCIATION_ID),
)


def _build_communication_input(
    row: Dict[str, Any], row_index: int, contact_id: str, body: str, timestamp_ms: str, owner_id: Any
) -> Dict[str, Any]:
    properties = {
        "hs_communication_channel_type": "LINKEDIN_MESSAGE",
        "hs_communication_logged_from": "CRM",
        "hs_communication_body": body,
        "hs_timestamp": timestamp_ms,
    }
    if owner_id:
        properties["hubspot_owner_id"] = str(owner_id)

    associations = [_hubspot_defined_association(contact_id, COMMUNICATION_TO_CONTACT_ASSOCIATION_ID)]
    for field, _, association_type_id in LINKED_RECORD_TYPES:
        if _linked_id(row, field):
            associations.append(_hubspot_defined_association(_linked_id(row, field), association_type_id))

    return {"properties": properties, "associations": associations, "objectWriteTraceId": str(row_index)}


@hubspot.action("log_linkedin_messages")
class LogLinkedInMessagesActionHandler(ActionHandler):
    """
    Action handler to log LinkedIn messages on HubSpot contacts in bulk.

    Each row is matched to exactly one existing contact by contact ID, email, or first and last name.
    Rows that match no contact, or more than one, are reported and not logged. Matched rows are
    created in a single Communications batch create call.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        default_body = (inputs.get("default_message_body") or "").strip()
        owner_id = inputs.get("hubspot_owner_id")
        # One rate-limit retry budget for the whole action, so repeated 429s can't stall it per request
        retry_sleep_budget = {"remaining": 10}

        results = []
        pending = []  # (row, result, body, timestamp_ms, kind, key) for rows that passed validation
        for row_index, row in enumerate(inputs["messages"]):
            identifier = _row_identifier(row)
            body = (row.get("message_body") or "").strip() or default_body
            timestamp_ms = _timestamp_ms(row.get("timestamp"))
            result = {
                "row_index": row_index,
                "identifier": identifier[2] if identifier else None,
                "status": None,
                "contact_id": None,
                "communication_id": None,
                "candidates": [],
                "error": None,
            }
            results.append(result)

            if identifier is None:
                result["status"] = "invalid"
                result["error"] = "Provide contact_id, email, or both first_name and last_name"
            elif not body:
                result["status"] = "invalid"
                result["error"] = "Provide message_body for this row or default_message_body"
            elif timestamp_ms is None:
                # HubSpot would reject the whole batch over one unreadable timestamp
                result["status"] = "invalid"
                result["error"] = f"timestamp must be {TIMESTAMP_FORMAT_HINT} (1970 to 9999)"
            else:
                pending.append((row, result, body, timestamp_ms, identifier[0], identifier[1]))

        # Each lookup maps (kind, key) to its matching contact IDs, or to an error message. The kind keeps an
        # email that looks like an ID from sharing another row's contact ID result
        matches: Dict[tuple[str, Any], list[str] | str] = {}
        emails = sorted({key for _, _, _, _, kind, key in pending if kind == "email"})
        if emails:
            try:
                contact_ids_by_email, errors_by_email = await _find_contact_ids_by_email(
                    emails, context, retry_sleep_budget
                )
                for email in emails:
                    if email in contact_ids_by_email:
                        matches[("email", email)] = [contact_ids_by_email[email]]
                    elif email in errors_by_email:
                        matches[("email", email)] = f"Contact lookup failed: {errors_by_email[email]}"
                    else:
                        matches[("email", email)] = []
            except REQUEST_ERRORS as e:
                matches.update({("email", email): f"Contact lookup failed: {_error_text(e)}" for email in emails})

        direct_ids = list(dict.fromkeys(key for _, _, _, _, kind, key in pending if kind == "contact_id"))
        for contact_id, problem in (
            await _check_object_ids("contacts", direct_ids, context, retry_sleep_budget)
        ).items():
            if problem is None:
                matches[("contact_id", contact_id)] = [contact_id]
            else:
                matches[("contact_id", contact_id)] = (
                    [] if problem == "missing" else f"Contact lookup failed: {problem}"
                )

        names = list(dict.fromkeys(key for _, _, _, _, kind, key in pending if kind == "name"))
        for index, (first_name, last_name) in enumerate(names):
            if index:
                await asyncio.sleep(NAME_SEARCH_INTERVAL_SECONDS)
            try:
                matches[("name", (first_name, last_name))] = await _find_contact_ids_by_name(
                    first_name, last_name, context, retry_sleep_budget
                )
            except REQUEST_ERRORS as e:
                matches[("name", (first_name, last_name))] = f"Contact lookup failed: {_error_text(e)}"

        matched = []  # (row, result, body, timestamp_ms) for rows matched to exactly one contact
        for row, result, body, timestamp_ms, kind, key in pending:
            contact_ids = matches[(kind, key)]
            if isinstance(contact_ids, str):
                result["status"] = "failed"
                result["error"] = contact_ids
            elif not contact_ids:
                result["status"] = "not_found"
            elif len(contact_ids) > 1:
                result["status"] = "ambiguous"
                result["candidates"] = contact_ids
            else:
                result["contact_id"] = contact_ids[0]
                matched.append((row, result, body, timestamp_ms))

        # A missing company or deal would also make HubSpot reject the whole batch, so check matched rows' ones
        linked_problems = {}
        for field, object_type, _ in LINKED_RECORD_TYPES:
            linked_ids = list(dict.fromkeys(_linked_id(row, field) for row, *_ in matched if _linked_id(row, field)))
            checked = await _check_object_ids(object_type, linked_ids, context, retry_sleep_budget)
            linked_problems.update({(field, object_id): problem for object_id, problem in checked.items()})

        batch_inputs = []
        for row, result, body, timestamp_ms in matched:
            problems = [
                (field, _linked_id(row, field), linked_problems[(field, _linked_id(row, field))])
                for field, _, _ in LINKED_RECORD_TYPES
                if _linked_id(row, field) and linked_problems[(field, _linked_id(row, field))]
            ]
            if problems:
                field, object_id, problem = problems[0]
                label = "Company" if field == "company_id" else "Deal"
                if problem == "missing":
                    result["status"] = "invalid"
                    result["error"] = f"{label} {object_id} does not exist"
                else:
                    result["status"] = "failed"
                    result["error"] = f"{label} lookup failed: {problem}"
            else:
                batch_inputs.append(
                    _build_communication_input(
                        row, result["row_index"], result["contact_id"], body, timestamp_ms, owner_id
                    )
                )

        returned_items: list[Dict[str, Any]] = []
        if batch_inputs:
            trace_ids = [batch_input["objectWriteTraceId"] for batch_input in batch_inputs]
            try:
                response = await fetch_with_rate_limit_retries(
                    context,
                    f"{COMMUNICATIONS_API_URL}/batch/create",
                    retry_sleep_budget=retry_sleep_budget,
                    resend_on_connection_error=False,
                    method="POST",
                    json={"inputs": batch_inputs},
                    headers={"Content-Type": "application/json"},
                )
                data = await parse_response(response) or {}
                returned_items = data.get("results", [])
                created_by_row, errors_by_row = _match_batch_results(
                    data, trace_ids, "HubSpot did not return a created message for this row"
                )
            except REQUEST_ERRORS as e:
                error = _error_text(e)
                if _outcome_unknown(e):
                    error = (
                        f"{error}; HubSpot may have logged this message, check the contact's timeline before retrying"
                    )
                created_by_row, errors_by_row = {}, {trace_id: error for trace_id in trace_ids}

            for trace_id in trace_ids:
                result = results[int(trace_id)]
                if trace_id in created_by_row:
                    result["status"] = "logged"
                    created_id = created_by_row[trace_id].get("id")
                    result["communication_id"] = str(created_id) if created_id else None
                else:
                    result["status"] = "failed"
                    result["error"] = errors_by_row[trace_id]

        # IDs HubSpot created but didn't tie to a row, so they can still be read, updated or deleted
        attached_ids = {result["communication_id"] for result in results if result["communication_id"]}
        unmatched_ids = [str(item["id"]) for item in returned_items if item.get("id")]
        counts = _status_counts(results, ("logged", "not_found", "ambiguous", "invalid", "failed"))
        return ActionResult(
            data={
                "results": results,
                **counts,
                "unmatched_communication_ids": [i for i in unmatched_ids if i not in attached_ids],
                "success": counts["logged"] == len(results),
            },
            cost_usd=None,
        )


@hubspot.action("get_linkedin_message")
class GetLinkedInMessageActionHandler(ActionHandler):
    """Action handler to read a logged LinkedIn message (communication) by ID."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        communication_id = inputs["communication_id"]
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{COMMUNICATIONS_API_URL}/{communication_id}",
                params={
                    "properties": "hs_communication_channel_type,hs_communication_body,hs_timestamp,hubspot_owner_id",
                    "associations": "contacts,companies,deals",
                },
            )
            return ActionResult(
                data={
                    "communication": await parse_response(response),
                    "success": True,
                    "message": "LinkedIn message retrieved successfully",
                },
                cost_usd=None,
            )
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to get LinkedIn message: {_error_text(e)}")


@hubspot.action("update_linkedin_message")
class UpdateLinkedInMessageActionHandler(ActionHandler):
    """Action handler to update the body, timestamp, or owner of a logged LinkedIn message."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        communication_id = inputs["communication_id"]

        # An empty string clears the body or owner in HubSpot, so check presence rather than truthiness
        properties = {}
        if inputs.get("message_body") is not None:
            properties["hs_communication_body"] = inputs["message_body"]
        if inputs.get("timestamp") not in (None, ""):
            properties["hs_timestamp"] = _timestamp_ms(inputs["timestamp"])
            if properties["hs_timestamp"] is None:
                return ActionError(message=f"timestamp must be {TIMESTAMP_FORMAT_HINT} (1970 to 9999)")
        if inputs.get("hubspot_owner_id") is not None:
            properties["hubspot_owner_id"] = str(inputs["hubspot_owner_id"])

        if not properties:
            return ActionError(message="Provide message_body, timestamp, or hubspot_owner_id to update")

        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{COMMUNICATIONS_API_URL}/{communication_id}",
                method="PATCH",
                json={"properties": properties},
                headers={"Content-Type": "application/json"},
            )
            return ActionResult(
                data={
                    "communication": await parse_response(response),
                    "success": True,
                    "message": "LinkedIn message updated successfully",
                    "updated_properties": properties,
                },
                cost_usd=None,
            )
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to update LinkedIn message: {_error_text(e)}")


@hubspot.action("delete_linkedin_message")
class DeleteLinkedInMessageActionHandler(ActionHandler):
    """Action handler to delete (archive) a logged LinkedIn message."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        communication_id = inputs["communication_id"]
        try:
            await fetch_with_rate_limit_retries(
                context, f"{COMMUNICATIONS_API_URL}/{communication_id}", method="DELETE"
            )
            return ActionResult(
                data={
                    "success": True,
                    "message": f"LinkedIn message {communication_id} deleted successfully",
                    "communication_id": communication_id,
                },
                cost_usd=None,
            )
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to delete LinkedIn message: {_error_text(e)}")


@hubspot.action("create_task")
class CreateTaskActionHandler(ActionHandler):
    """
    Action handler to create a task and associate it with a HubSpot contact, company, or deal.

    Creates a new task using the CRM API and associates it with specified CRM objects.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the create_task action.

        :param inputs: Dictionary with HubSpot task fields and associations.
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the created task information.
        """
        # Required by input_schema; missing keys are rejected by the runner before execute.
        timestamp = inputs["hs_timestamp"]

        # Build the task properties
        properties = {"hs_timestamp": str(timestamp)}

        if inputs.get("hs_task_body"):
            properties["hs_task_body"] = inputs.get("hs_task_body")
        if inputs.get("hs_task_subject"):
            properties["hs_task_subject"] = inputs.get("hs_task_subject")
        if inputs.get("hs_task_status"):
            properties["hs_task_status"] = inputs.get("hs_task_status")
        if inputs.get("hs_task_priority"):
            properties["hs_task_priority"] = inputs.get("hs_task_priority")
        if inputs.get("hs_task_type"):
            properties["hs_task_type"] = inputs.get("hs_task_type")
        if inputs.get("hubspot_owner_id"):
            properties["hubspot_owner_id"] = str(inputs.get("hubspot_owner_id"))
        if inputs.get("hs_task_reminders"):
            properties["hs_task_reminders"] = str(inputs.get("hs_task_reminders"))

        # Build associations array
        associations = []

        # Allow direct associations payload (HubSpot-native format)
        if inputs.get("associations"):
            associations.extend(inputs["associations"])

        # Associate with contact
        if inputs.get("contact_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["contact_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 204,
                        }
                    ],
                }
            )

        # Associate with company
        if inputs.get("company_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["company_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 192,
                        }
                    ],
                }
            )

        # Associate with deal
        if inputs.get("deal_id"):
            associations.append(
                {
                    "to": {"id": str(inputs["deal_id"])},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 216,
                        }
                    ],
                }
            )

        try:
            url = "https://api.hubapi.com/crm/v3/objects/tasks"
            payload = {"properties": properties, "associations": associations}

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                method="POST",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            return ActionResult(
                data={
                    "task": result,
                    "success": True,
                    "message": "Task created successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to create task: {str(e)}")


@hubspot.action("update_task")
class UpdateTaskActionHandler(ActionHandler):
    """
    Action handler to update an existing task in HubSpot.

    Updates the task body or other properties of an existing task.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the update_task action.

        :param inputs: Dictionary with "hs_object_id" and HubSpot task properties to update.
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the updated task information.
        """
        hs_object_id = inputs["hs_object_id"]

        # Build properties to update
        properties = {}

        if inputs.get("hs_task_body"):
            properties["hs_task_body"] = inputs.get("hs_task_body")

        if inputs.get("hs_timestamp"):
            properties["hs_timestamp"] = str(inputs.get("hs_timestamp"))

        if inputs.get("hs_task_subject"):
            properties["hs_task_subject"] = inputs.get("hs_task_subject")
        if inputs.get("hs_task_status"):
            properties["hs_task_status"] = inputs.get("hs_task_status")
        if inputs.get("hs_task_priority"):
            properties["hs_task_priority"] = inputs.get("hs_task_priority")
        if inputs.get("hs_task_type"):
            properties["hs_task_type"] = inputs.get("hs_task_type")
        if inputs.get("hubspot_owner_id"):
            properties["hubspot_owner_id"] = str(inputs.get("hubspot_owner_id"))
        if inputs.get("hs_task_reminders"):
            properties["hs_task_reminders"] = str(inputs.get("hs_task_reminders"))

        # Allow additional properties to be updated
        if inputs.get("additional_properties"):
            properties.update(inputs["additional_properties"])

        if not properties:
            return ActionError(message="No properties provided to update")

        try:
            url = f"https://api.hubapi.com/crm/v3/objects/tasks/{hs_object_id}"
            payload = {"properties": properties}

            response = await context.fetch(
                url,
                method="PATCH",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            return ActionResult(
                data={
                    "task": result,
                    "success": True,
                    "message": "Task updated successfully",
                    "updated_properties": properties,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to update task: {str(e)}")


@hubspot.action("delete_task")
class DeleteTaskActionHandler(ActionHandler):
    """
    Action handler to delete a task from HubSpot.

    Permanently deletes a task by its ID.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the delete_task action.

        :param inputs: Dictionary with "hs_object_id" (HubSpot task record ID).
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary indicating success or failure.
        """
        hs_object_id = inputs["hs_object_id"]

        try:
            url = f"https://api.hubapi.com/crm/v3/objects/tasks/{hs_object_id}"

            await context.fetch(
                url,
                method="DELETE",
                headers={"Content-Type": "application/json"},
            )

            # DELETE returns 204 No Content on success
            return ActionResult(
                data={
                    "success": True,
                    "message": f"Task {hs_object_id} deleted successfully",
                    "hs_object_id": hs_object_id,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to delete task: {str(e)}")


@hubspot.action("get_task")
class GetTaskActionHandler(ActionHandler):
    """
    Action handler to retrieve a task from HubSpot.

    Fetches a single task by ID from the CRM objects API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_task action.

        :param inputs: Dictionary with "hs_object_id" and optional "hs_task_properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the retrieved task information.
        """
        hs_object_id = inputs["hs_object_id"]
        hs_task_properties = inputs.get("hs_task_properties", _DEFAULT_HS_TASK_PROPERTY_NAMES)

        try:
            url = f"https://api.hubapi.com/crm/v3/objects/tasks/{hs_object_id}"
            params = {
                "properties": ",".join(hs_task_properties),
                "associations": "contacts,companies,deals",
            }

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                params=params,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            task_props = result.get("properties", {})
            _apply_readable_utc_to_task_properties(task_props)

            return ActionResult(
                data={
                    "task": result,
                    "success": True,
                    "message": "Task retrieved successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve task: {str(e)}")


TASKS_SEARCH_API_URL = "https://api.hubapi.com/crm/v3/objects/tasks/search"

# list_tasks inputs that need the CRM search API; without them it lists every task in ID order
_TASK_SEARCH_INPUTS = (
    "owner_id",
    "owner_email",
    "status",
    "exclude_completed",
    "priority",
    "task_type",
    "due_after",
    "due_before",
    "query",
    "contact_id",
    "company_id",
    "deal_id",
    "sort_direction",
)

# HubSpot rejects a filter group with more than 6 filters
MAX_SEARCH_FILTERS_PER_GROUP = 6


def _due_date_filter(input_name: str, operator: str, value: Any) -> Dict[str, Any]:
    """Return an hs_timestamp filter, raising ValueError when the date can't be read."""
    milliseconds = _timestamp_ms(value)
    if milliseconds is None:
        raise ValueError(f"{input_name} must be {TIMESTAMP_FORMAT_HINT}, got {value!r}")
    return {"propertyName": "hs_timestamp", "operator": operator, "value": milliseconds}


def _task_search_filters(inputs: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Return list_tasks' search filters other than the owner; they're ANDed in one filter group.

    Raises ValueError for a due date that can't be read.
    """
    filters = []
    # Enumeration values are case-sensitive, so these are sent as given (e.g. NOT_STARTED)
    if inputs.get("status"):
        filters.append({"propertyName": "hs_task_status", "operator": "IN", "values": inputs["status"]})
    if inputs.get("exclude_completed"):
        filters.append({"propertyName": "hs_task_status", "operator": "NEQ", "value": "COMPLETED"})
    if inputs.get("priority"):
        filters.append({"propertyName": "hs_task_priority", "operator": "IN", "values": inputs["priority"]})
    if inputs.get("task_type"):
        filters.append({"propertyName": "hs_task_type", "operator": "IN", "values": inputs["task_type"]})
    if inputs.get("due_after"):
        filters.append(_due_date_filter("due_after", "GTE", inputs["due_after"]))
    if inputs.get("due_before"):
        filters.append(_due_date_filter("due_before", "LT", inputs["due_before"]))
    if inputs.get("contact_id"):
        filters.append({"propertyName": "associations.contact", "operator": "EQ", "value": str(inputs["contact_id"])})
    if inputs.get("company_id"):
        filters.append({"propertyName": "associations.company", "operator": "EQ", "value": str(inputs["company_id"])})
    if inputs.get("deal_id"):
        filters.append({"propertyName": "associations.deal", "operator": "EQ", "value": str(inputs["deal_id"])})
    return filters


async def _task_associations(
    context: ExecutionContext, task_ids: list[str], retry_sleep_budget: Dict[str, int]
) -> Dict[str, Dict[str, Any]]:
    """Return each task's associated contacts, companies and deals, keyed by task ID.

    The search API doesn't return associations, so this fills the same associations.<type>.results[].id
    shape that listing tasks returns, leaving out types with nothing linked as listing does.
    """
    associations: Dict[str, Dict[str, Any]] = {task_id: {} for task_id in task_ids}
    for object_type in ("contacts", "companies", "deals"):
        links, _ = await _read_associations(context, "tasks", object_type, task_ids, retry_sleep_budget)
        for task_id, linked in links.items():
            if linked:
                associations[task_id][object_type] = {"results": [{"id": str(link["toObjectId"])} for link in linked]}
    return associations


async def _search_tasks(inputs: Dict[str, Any], filters: list[Dict[str, Any]], context: ExecutionContext):
    """Run list_tasks through the CRM search API, adding the owner filter and each task's linked records."""
    owner_id = inputs.get("owner_id")
    owner_email = inputs.get("owner_email")
    filter_count = len(filters) + bool(owner_id or owner_email)
    if filter_count > MAX_SEARCH_FILTERS_PER_GROUP:
        return ActionError(
            message=(
                f"HubSpot allows at most {MAX_SEARCH_FILTERS_PER_GROUP} task filters per search; "
                f"{filter_count} were given. Remove some filters and try again."
            )
        )

    retry_sleep_budget = {"remaining": 10}
    if not owner_id and owner_email:
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                "https://api.hubapi.com/crm/v3/owners/",
                retry_sleep_budget=retry_sleep_budget,
                params={"email": owner_email},
                headers={"Content-Type": "application/json"},
            )
            owners = (await parse_response(response)).get("results", [])
        except Exception as e:
            return ActionError(message=f"Failed to look up owner {owner_email}: {str(e)}")
        if not owners:
            return ActionError(message=f"No HubSpot owner has the email {owner_email}")
        owner_id = owners[0]["id"]
    if owner_id:
        filters = [{"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(owner_id)}, *filters]

    payload = {
        "limit": inputs.get("limit", 100),
        "properties": list(inputs.get("hs_task_properties", _DEFAULT_HS_TASK_PROPERTY_NAMES)),
        "sorts": [{"propertyName": "hs_timestamp", "direction": inputs.get("sort_direction", "ASCENDING")}],
    }
    if filters:
        payload["filterGroups"] = [{"filters": filters}]
    if inputs.get("query"):
        payload["query"] = inputs["query"]
    if inputs.get("after"):
        payload["after"] = inputs["after"]

    try:
        response = await fetch_with_rate_limit_retries(
            context,
            TASKS_SEARCH_API_URL,
            retry_sleep_budget=retry_sleep_budget,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)
        tasks = result.get("results", [])

        if tasks and inputs.get("include_associations", False):
            associations = await _task_associations(context, [str(task["id"]) for task in tasks], retry_sleep_budget)
            for task in tasks:
                task["associations"] = associations[str(task["id"])]
    except Exception as e:
        return ActionError(message=f"Failed to search tasks: {str(e)}")

    for task in tasks:
        _apply_readable_utc_to_task_properties(task.get("properties", {}))

    return ActionResult(
        data={
            "tasks": tasks,
            "total": len(tasks),
            "total_matching": result.get("total", len(tasks)),
            "paging": result.get("paging"),
            "success": True,
            "message": "Tasks retrieved successfully",
        },
        cost_usd=None,
    )


@hubspot.action("list_tasks")
class ListTasksActionHandler(ActionHandler):
    """
    Action handler to retrieve tasks from HubSpot.

    Lists every task in ID order, or searches when filters (owner, status, due date, linked record, text) are given.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the list_tasks action.

        :param inputs: Dictionary with optional "limit", "after", "hs_task_properties" and search filters.
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with the retrieved tasks and paging metadata.
        """
        if any(inputs.get(name) for name in _TASK_SEARCH_INPUTS):
            try:
                filters = _task_search_filters(inputs)
            except ValueError as e:
                return ActionError(message=str(e))
            return await _search_tasks(inputs, filters, context)

        # Listing returns at most 100 tasks a page; searching allows 200
        limit = min(inputs.get("limit", 100), 100)
        after = inputs.get("after")
        hs_task_properties = inputs.get("hs_task_properties", _DEFAULT_HS_TASK_PROPERTY_NAMES)

        try:
            url = "https://api.hubapi.com/crm/v3/objects/tasks"
            params = {
                "limit": limit,
                "properties": ",".join(hs_task_properties),
            }
            if inputs.get("include_associations", False):
                params["associations"] = "contacts,companies,deals"
            if after:
                params["after"] = after

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                params=params,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)
            tasks = result.get("results", [])

            for task in tasks:
                _apply_readable_utc_to_task_properties(task.get("properties", {}))

            return ActionResult(
                data={
                    "tasks": tasks,
                    "total": len(tasks),
                    "paging": result.get("paging"),
                    "success": True,
                    "message": "Tasks retrieved successfully",
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve tasks: {str(e)}")


@hubspot.action("get_contact_emails")
class GetContactEmailsActionHandler(ActionHandler):
    """
    Action handler to retrieve a HubSpot contact's most recent logged emails, newest first.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_contact_emails action.

        :param inputs: Dictionary with key "contact_id" and optional "email_limit".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with recent emails for the contact.
        """
        contact_id = inputs["contact_id"]
        email_limit = inputs.get("email_limit", 5)

        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{OBJECTS_API_URL}/emails/search",
                method="POST",
                json={
                    "filterGroups": [
                        {
                            "filters": [
                                {"propertyName": "associations.contact", "operator": "EQ", "value": str(contact_id)}
                            ]
                        }
                    ],
                    "properties": [
                        "hs_email_subject",
                        "hs_email_text",
                        "hs_timestamp",
                        "hs_email_direction",
                        "hs_email_status",
                        "hs_email_from_email",
                        "hs_email_to_email",
                    ],
                    "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
                    "limit": email_limit,
                },
                headers={"Content-Type": "application/json"},
            )
            recent_emails = (await parse_response(response)).get("results", [])
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to retrieve emails: {_error_text(e)}")

        for email in recent_emails:
            properties = email.get("properties") or {}
            if properties.get("hs_timestamp"):
                properties["hs_timestamp"] = convert_hubspot_timestamp_to_utc_string(properties["hs_timestamp"])

        return ActionResult(
            data={
                "contact_id": contact_id,
                "recent_emails": recent_emails,
                "email_summary": {
                    "total_emails_retrieved": len(recent_emails),
                    "email_limit_applied": email_limit,
                },
            },
            cost_usd=None,
        )


@hubspot.action("create_contact")
class CreateContactActionHandler(ActionHandler):
    """
    Action handler to create a new HubSpot contact.

    Sends a POST request to the HubSpot API with the provided contact properties.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the create_contact action.

        :param inputs: Dictionary with a key "properties" containing contact fields.
        :param context: Execution context with authentication details.
        :return: Dictionary with a "contact" key mapping to the created contact data.
        """

        url = "https://api.hubapi.com/crm/v3/objects/contacts"

        # Merge properties and additional_properties
        properties = inputs["properties"].copy()
        additional_properties = inputs.get("additional_properties", {})
        properties.update(additional_properties)

        payload = {"properties": properties}
        response = await context.fetch(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)
        return ActionResult(
            data={"contact": result, "created_properties": properties},
            cost_usd=None,
        )


@hubspot.action("upsert_contacts")
class UpsertContactsActionHandler(ActionHandler):
    """
    Action handler to create or update up to 100 contacts in one call, matched on email.

    Uses the CRM batch upsert endpoint with email as the unique ID property, so existing contacts are
    updated instead of duplicated.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        contacts = inputs["contacts"]

        emails = [contact["email"].strip().lower() for contact in contacts]
        duplicates = sorted(email for email, count in Counter(emails).items() if count > 1)
        if duplicates:
            return ActionError(message=f"Each email can appear only once per call. Duplicates: {', '.join(duplicates)}")
        # HubSpot rejects objectWriteTraceId on email-keyed upserts, so rows are matched by email or contact ID
        row_key_by_email = {email: str(row_index) for row_index, email in enumerate(emails)}
        # One rate-limit retry budget for the upsert and the lookups that match its results
        retry_sleep_budget = {"remaining": 10}

        # Look the emails up first: two rows can be one contact when one is that contact's additional email.
        # Without a complete lookup that can't be ruled out, so nothing is written
        not_checked = "Could not check the emails before upserting, so nothing was written; retrying is safe"
        try:
            existing_ids_by_email, lookup_errors = await _find_contact_ids_by_email(emails, context, retry_sleep_budget)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"{not_checked}: {_error_text(e)}")
        if lookup_errors:
            details = "; ".join(f"{email}: {error}" for email, error in lookup_errors.items())
            return ActionError(message=f"{not_checked}: {details}")
        emails_by_contact_id: Dict[str, list[str]] = {}
        for email in emails:
            if email in existing_ids_by_email:
                emails_by_contact_id.setdefault(existing_ids_by_email[email], []).append(email)
        shared = [", ".join(group) for group in emails_by_contact_id.values() if len(group) > 1]
        if shared:
            return ActionError(
                message=f"These emails belong to the same HubSpot contact, pass only one of each: {' | '.join(shared)}"
            )
        row_key_by_contact_id = {
            contact_id: row_key_by_email[group[0]] for contact_id, group in emails_by_contact_id.items()
        }

        batch_inputs = []
        for contact, email in zip(contacts, emails):
            properties = {key: _property_value(value) for key, value in (contact.get("properties") or {}).items()}
            # The email only identifies the contact. Writing it could make an additional email the primary one
            properties.pop("email", None)
            if contact.get("first_name"):
                properties["firstname"] = contact["first_name"]
            if contact.get("last_name"):
                properties["lastname"] = contact["last_name"]
            batch_inputs.append(
                {
                    "id": email,
                    "idProperty": "email",
                    "properties": properties,
                }
            )

        try:
            response = await fetch_with_rate_limit_retries(
                context,
                CONTACTS_BATCH_UPSERT_API_URL,
                retry_sleep_budget=retry_sleep_budget,
                # A resend would see contacts this call created and report them as updated
                resend_on_connection_error=False,
                method="POST",
                json={"inputs": batch_inputs},
                headers={"Content-Type": "application/json"},
            )
        except REQUEST_ERRORS as e:
            message = f"Failed to upsert contacts: {_error_text(e)}"
            if _outcome_unknown(e):
                message += "; HubSpot may have saved some of them, and retrying is safe"
            return ActionError(message=message)

        def row_key_for(item: Dict[str, Any]) -> str | None:
            email = ((item.get("properties") or {}).get("email") or "").lower()
            return row_key_by_email.get(email) or row_key_by_contact_id.get(str(item.get("id")))

        data = await parse_response(response) or {}
        # New contacts may come back without their email, so read them back by email to match on contact ID
        if any(row_key_for(item) is None for item in data.get("results", [])):
            try:
                contact_ids_by_email, _ = await _find_contact_ids_by_email(emails, context, retry_sleep_budget)
            except REQUEST_ERRORS:
                contact_ids_by_email = {}  # unmatched rows are reported as unattributed below
            row_key_by_contact_id.update(
                {
                    contact_id: row_key_by_email[address]
                    for address, contact_id in contact_ids_by_email.items()
                    if address in row_key_by_email
                }
            )

        upserted_by_row, errors_by_row = _match_batch_results(
            data,
            list(row_key_by_email.values()),
            "HubSpot did not return a contact for this row",
            trace_id_for=row_key_for,
        )

        results = []
        for email, row_key in row_key_by_email.items():
            result = {"row_index": int(row_key), "email": email, "status": "failed", "contact_id": None, "error": None}
            upserted = upserted_by_row.get(row_key)
            if upserted is None:
                result["error"] = errors_by_row[row_key]
            elif not upserted:
                result["error"] = "HubSpot didn't say which contact this row matched; retrying is safe"
            else:
                result["status"] = "created" if upserted.get("new") else "updated"
                result["contact_id"] = str(upserted["id"]) if upserted.get("id") else None
            results.append(result)

        counts = _status_counts(results, ("created", "updated", "failed"))
        return ActionResult(
            data={"results": results, **counts, "success": counts["failed"] == 0},
            cost_usd=None,
        )


@hubspot.action("update_contact")
class UpdateContactActionHandler(ActionHandler):
    """
    Action handler to update an existing HubSpot contact.

    Updates the contact details using the contact ID and the provided properties.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the update_contact action.

        :param inputs: Dictionary with keys "contact_id" and "properties" for updating the contact.
        :param context: Execution context including authentication credentials.
        :return: Dictionary with a "contact" key mapping to the updated contact data.
        """

        contact_id = inputs["contact_id"]

        # Use v3 API endpoint
        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"

        # Merge properties and additional_properties
        properties = inputs["properties"].copy()
        additional_properties = inputs.get("additional_properties", {})
        properties.update(additional_properties)

        payload = {"properties": properties}
        response = await context.fetch(
            url,
            method="PATCH",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)
        return ActionResult(
            data={"contact": result, "updated_properties": properties},
            cost_usd=None,
        )


@hubspot.action("search_contacts")
class SearchContactsActionHandler(ActionHandler):
    """
    Action handler to search for HubSpot contacts.

    Uses a query string and a limit to search for contacts through HubSpot's CRM API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the search_contacts action.

        :param inputs: Dictionary with keys "query" (search term) and "limit" (max results).
        :param context: Execution context including authentication information.
        :return: Parsed JSON response containing search results.
        """

        query = inputs["query"]
        limit = inputs.get("limit", 100)
        after = inputs.get("after")

        url = "https://api.hubapi.com/crm/v3/objects/contacts/search"

        payload = {"query": query, "limit": limit}

        # Add pagination cursor if provided
        if after:
            payload["after"] = after

        response = await fetch_with_rate_limit_retries(
            context,
            url=url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        parsed_response = await parse_response(response)

        return ActionResult(data=parsed_response, cost_usd=None)


@hubspot.action("add_contact_to_list")
class AddContactToListActionHandler(ActionHandler):
    """
    Action handler to add a contact to a specific HubSpot list using v3 Lists API.

    Uses the provided list ID and contact ID to add the contact to the list.
    Works with MANUAL or SNAPSHOT list types only (DYNAMIC lists manage membership automatically).
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the add_contact_to_list action.

        :param inputs: Dictionary with keys "list_id" and "contact_id" (v3 contact ID).
        :param context: Execution context with authentication details.
        :return: Dictionary with a "result" key containing the API response.
        """

        list_id = inputs["list_id"]
        contact_id = inputs["contact_id"]

        # Use v3 Lists API endpoint
        url = f"https://api.hubapi.com/crm/v3/lists/{list_id}/memberships/add"

        # HubSpot expects the request body to be a JSON array of record IDs.
        payload = [contact_id]
        response = await context.fetch(
            url,
            method="PUT",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)
        return ActionResult(data={"result": result}, cost_usd=None)


@hubspot.action("remove_contact_from_list")
class RemoveContactFromListActionHandler(ActionHandler):
    """Remove a contact from a manual or snapshot HubSpot list."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """Remove the supplied contact ID from the supplied list ID."""
        list_id = inputs["list_id"]
        contact_id = inputs["contact_id"]

        url = f"https://api.hubapi.com/crm/lists/2026-03/{list_id}/memberships/remove"
        response = await context.fetch(
            url,
            method="PUT",
            json=[contact_id],
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)
        return ActionResult(data={"result": result}, cost_usd=None)


@hubspot.action("get_recent_contacts")
class GetRecentContactsActionHandler(ActionHandler):
    """
    Action handler to retrieve recent HubSpot contacts.

    Retrieves a list of recently created contacts sorted by their creation time.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_recent_contacts action.

        :param inputs: Dictionary with key "count" specifying the maximum number of contacts.
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with a "recent_contacts" key containing recent contact data.
        """

        limit = inputs.get("limit", 100)

        # Listing contacts can't sort, so it returns the oldest first; search sorts by creation date
        response = await fetch_with_rate_limit_retries(
            context,
            CONTACTS_SEARCH_API_URL,
            method="POST",
            json={"sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}], "limit": limit},
            headers={"Content-Type": "application/json"},
        )
        recent_contacts = await parse_response(response)
        return ActionResult(data={"recent_contacts": recent_contacts}, cost_usd=None)


# Ticket Management Actions


# Conversation message pages read for one ticket
MAX_CONVERSATION_PAGES = 20


async def get_thread_id_from_ticket(ticket_id: str, context: ExecutionContext) -> str:
    """
    Retrieve the conversation thread ID for a given ticket.

    Fetches the ticket details from HubSpot and extracts the conversation thread ID.

    :param ticket_id: The ID of the ticket.
    :param context: Execution context with fetch utility.
    :return: The conversation thread ID or None if not found.
    """
    ticket_url = f"{OBJECTS_API_URL}/tickets/{ticket_id}?properties=hs_conversations_originating_thread_id"
    ticket_response = await fetch_with_rate_limit_retries(
        context,
        ticket_url,
        headers={"Content-Type": "application/json"},
    )
    ticket_data = await parse_response(ticket_response)
    return ticket_data.get("properties", {}).get("hs_conversations_originating_thread_id")


@hubspot.action("get_recent_tickets")
class GetRecentTicketsActionHandler(ActionHandler):
    """
    Action handler to retrieve recent tickets from HubSpot.

    Retrieves tickets based on provided limit, sorting property, and direction.
    Can also filter tickets by status if provided.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_recent_tickets action.

        :param inputs: Dictionary with keys "limit", "sort_property", "sort_direction", and optionally "status".
        :param context: Execution context containing authentication details.
        :return: Dictionary with a "tickets" key containing ticket search results.
        """

        limit = inputs.get("limit", 20)
        sort_property = inputs.get("sort_property", "hs_lastmodifieddate")

        sort_direction_map = {"DESC": "DESCENDING", "ASC": "ASCENDING"}
        sort_direction = sort_direction_map.get(inputs.get("sort_direction", "DESC"), "DESCENDING")

        url = f"{OBJECTS_API_URL}/tickets/search"

        properties = [
            "subject",
            "content",
            "hs_pipeline_stage",
            "hs_ticket_priority",
            "hubspot_owner_id",
            "createdate",
            "hs_lastmodifieddate",
            "hs_ticket_category",
        ]

        # Prepare the request body
        request_body = {
            "limit": limit,
            "properties": properties,
            "sorts": [{"propertyName": sort_property, "direction": sort_direction}],
        }

        if inputs.get("status"):
            request_body["filterGroups"] = [
                {
                    "filters": [
                        {
                            "propertyName": "hs_pipeline_stage",
                            "operator": "EQ",
                            "value": inputs["status"],
                        }
                    ]
                }
            ]

        response = await fetch_with_rate_limit_retries(
            context,
            url,
            method="POST",
            json=request_body,
            headers={"Content-Type": "application/json"},
        )

        tickets = await parse_response(response)

        return ActionResult(data={"tickets": tickets}, cost_usd=None)


@hubspot.action("get_ticket_conversation")
class GetTicketConversationActionHandler(ActionHandler):
    """
    Action handler to retrieve the conversation thread for a specific ticket.

    Retrieves the thread ID for the ticket, then fetches and sorts the conversation messages.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_ticket_conversation action.

        :param inputs: Dictionary with key "ticket_id" identifying the ticket.
        :param context: Execution context including authentication and fetch utilities.
        :return: Dictionary with a "conversation" key containing sorted conversation messages and the ticket ID.
        """

        ticket_id = inputs["ticket_id"]

        conversation_results = []

        # Retrieve the correct thread ID using the helper function.
        thread_id = await get_thread_id_from_ticket(ticket_id, context)
        if not thread_id:
            return ActionResult(
                data={
                    "conversation": {
                        "results": [],
                        "ticket_id": ticket_id,
                        "thread_id": None,
                        "message": f"No conversation thread found for ticket {ticket_id}",
                    }
                },
                cost_usd=None,
            )

        conversation_url = f"https://api.hubapi.com/conversations/v3/conversations/threads/{thread_id}/messages"
        retry_sleep_budget = {"remaining": 10}
        after = None
        for _ in range(MAX_CONVERSATION_PAGES):
            try:
                conversation_response = await fetch_with_rate_limit_retries(
                    context,
                    conversation_url,
                    retry_sleep_budget=retry_sleep_budget,
                    params={"after": after} if after else None,
                    headers={"Content-Type": "application/json"},
                )
                conversation_data = await parse_response(conversation_response)
            except REQUEST_ERRORS as e:
                return ActionError(
                    message=f"Failed to read the conversation for ticket {ticket_id} (thread {thread_id}): "
                    f"{_error_text(e)}"
                )

            for message in conversation_data.get("results", []):
                message_content = message.get("text") or message.get("richText")
                if not message_content:
                    continue

                message_type = message.get("type", "")
                if message_type == "COMMENT":
                    sender = "Private Note"
                else:
                    sender = None
                    if message.get("senders") and len(message["senders"]) > 0:
                        sender_info = message["senders"][0]
                        sender = sender_info.get("name", "Unknown Sender")

                conversation_results.append(
                    {
                        "sender": sender,
                        "message": message_content,
                        "timestamp": message.get("createdAt"),
                        "message_id": message.get("id"),
                        "type": message_type,
                        **({"rich_text": message["richText"]} if message.get("richText") else {}),
                    }
                )

            after = ((conversation_data.get("paging") or {}).get("next") or {}).get("after")
            if not after:
                break

        try:
            sorted_conversation = sorted(conversation_results, key=lambda x: x.get("timestamp", ""))
        except Exception:
            sorted_conversation = conversation_results

        conversation = {"results": sorted_conversation, "ticket_id": ticket_id, "thread_id": thread_id}
        if after:
            conversation["message"] = f"Showing the first {MAX_CONVERSATION_PAGES} pages of a longer conversation"
        return ActionResult(data={"conversation": conversation}, cost_usd=None)


@hubspot.action("add_ticket_comment")
class AddTicketCommentActionHandler(ActionHandler):
    """
    Action handler to add an internal note to a ticket.

    Creates a CRM note and associates it with the ticket. HubSpot does not
    expose a stable ticket comments endpoint under the Conversations thread
    route for this use case, so ticket comments are represented as CRM notes.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the add_ticket_comment action.

        :param inputs: Dictionary with keys "ticket_id" and "comment".
        :param context: Execution context containing authentication credentials.
        :return: Dictionary with a "result" key indicating success or failure and the note details.
        """

        ticket_id = inputs["ticket_id"]
        comment = inputs["comment"]

        notes_url = "https://api.hubapi.com/crm/v3/objects/notes"
        note_payload = {
            "properties": {
                "hs_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "hs_note_body": comment,
            },
            "associations": [
                {
                    "to": {"id": str(ticket_id)},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 228,
                        }
                    ],
                }
            ],
        }

        try:
            note_response = await context.fetch(
                notes_url,
                method="POST",
                json=note_payload,
                headers={"Content-Type": "application/json"},
            )
            note_result = await parse_response(note_response)
        except Exception as e:
            return ActionError(message=f"Failed to add note to ticket {ticket_id}: {str(e)}")

        note_id = note_result.get("id") if isinstance(note_result, dict) else None
        if not note_id:
            return ActionError(message=f"Failed to add note to ticket {ticket_id}: note was created without an id")

        verification_url = f"https://api.hubapi.com/crm/v3/objects/notes/{note_id}"

        try:
            verification_response = await fetch_with_rate_limit_retries(
                context,
                verification_url,
                method="GET",
                params={"associations": "ticket"},
                headers={"Content-Type": "application/json"},
            )
            verification_result = await parse_response(verification_response)
        except Exception as e:
            return ActionError(
                message=(
                    f"Failed to verify note {note_id} is visible through ticket {ticket_id}: {str(e)}. "
                    f"The created note {note_id} was not deleted because verification failed before "
                    "the ticket association could be checked."
                )
            )

        association_results = verification_result.get("associations", {}).get("tickets", {}).get(
            "results", []
        ) or verification_result.get("associations", {}).get("ticket", {}).get("results", [])
        if not any(str(association.get("id")) == str(ticket_id) for association in association_results):
            cleanup_error = None
            try:
                await context.fetch(
                    f"https://api.hubapi.com/crm/v3/objects/notes/{note_id}",
                    method="DELETE",
                    headers={"Content-Type": "application/json"},
                )
            except Exception as cleanup_exception:
                cleanup_error = str(cleanup_exception)

            cleanup_message = f" The created note {note_id} was deleted to avoid leaving an orphaned note."
            if cleanup_error:
                cleanup_message = f" Cleanup of orphaned note {note_id} also failed: {cleanup_error}"

            return ActionError(
                message=(
                    f"Failed to verify note {note_id} is visible through ticket {ticket_id}: "
                    f"note is not discoverable through the ticket association.{cleanup_message}"
                )
            )

        return ActionResult(
            data={
                "result": {
                    "success": True,
                    "message": "Note added successfully to the ticket",
                    "visibility": "internal_note",
                    "note": note_result,
                    "verification": verification_result,
                }
            },
            cost_usd=None,
        )


# Company Management Actions


@hubspot.action("get_company_notes")
class GetCompanyNotesActionHandler(ActionHandler):
    """
    Action handler to retrieve notes associated with a HubSpot company.

    Fetches all notes for a specific company using the CRM search API with association filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_company_notes action.

        :param inputs: Dictionary with key "company_id" and optional "limit" and "properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with notes for the company.
        """
        company_id = inputs["company_id"]
        limit = min(inputs.get("limit", 100), 200)  # Max 200 per HubSpot API
        properties = inputs.get(
            "properties",
            [
                "hs_note_body",
                "hs_timestamp",
                "hubspot_owner_id",
                "hs_createdate",
                "hs_lastmodifieddate",
            ],
        )

        try:
            # Use search API to find notes associated with this company
            search_url = "https://api.hubapi.com/crm/v3/objects/notes/search"
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "associations.company",
                                "operator": "EQ",
                                "value": company_id,
                            }
                        ]
                    }
                ],
                "properties": properties,
                "limit": limit,
                "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
            }
            if inputs.get("after"):
                search_body["after"] = inputs["after"]

            response = await fetch_with_rate_limit_retries(
                context,
                search_url,
                method="POST",
                json=search_body,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            notes = result.get("results", [])

            # Convert timestamps to UTC strings
            for note in notes:
                if "properties" in note:
                    props = note["properties"]
                    for timestamp_field in [
                        "hs_timestamp",
                        "hs_createdate",
                        "hs_lastmodifieddate",
                    ]:
                        if timestamp_field in props and props[timestamp_field]:
                            props[timestamp_field] = convert_hubspot_timestamp_to_utc_string(props[timestamp_field])

            after = ((result.get("paging") or {}).get("next") or {}).get("after")
            return ActionResult(
                data={
                    "company_id": company_id,
                    "notes": notes,
                    "total": len(notes),
                    "total_matching": result.get("total", len(notes)),
                    "has_more": after is not None,
                    "after": after,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(
                message=f"Failed to retrieve notes for company {company_id}: {str(e)}",
            )


@hubspot.action("get_company")
class GetCompanyActionHandler(ActionHandler):
    """
    Action handler to retrieve a company by its ID.

    Fetches the company details including multiple properties like name, domain, phone, etc.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_company action.

        :param inputs: Dictionary with keys "company_id" and optional "properties" array.
        :param context: Execution context including authentication information.
        :return: Dictionary with a "company" key containing the company data.
        """

        company_id = inputs["company_id"]
        properties = inputs.get("properties")

        url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}"

        # Use custom properties if provided, otherwise use standard properties
        if properties:
            properties_param = ",".join(properties)
        else:
            # Standard company properties
            properties_param = (
                "name,domain,phone,address,city,state,country,zip,"
                "industry,description,website,annualrevenue,numberofemployees,founded"
            )

        url += f"?properties={properties_param}"
        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        company = await parse_response(response)

        return ActionResult(data={"company": company}, cost_usd=None)


@hubspot.action("create_company")
class CreateCompanyActionHandler(ActionHandler):
    """
    Action handler to create a new company in HubSpot.

    Sends a POST request with the provided company properties to create a new company record.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the create_company action.

        :param inputs: Dictionary with a key "properties" containing company fields.
        :param context: Execution context with authentication details.
        :return: Dictionary with a "company" key mapping to the created company data.
        """

        url = "https://api.hubapi.com/crm/v3/objects/companies"

        # Transform properties to HubSpot format
        payload = {"properties": inputs["properties"]}

        response = await context.fetch(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)

        return ActionResult(data={"company": result}, cost_usd=None)


@hubspot.action("update_company")
class UpdateCompanyActionHandler(ActionHandler):
    """
    Action handler to update an existing company record in HubSpot.

    Uses the company ID and provided properties to update the company information.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the update_company action.

        :param inputs: Dictionary with keys "company_id" and "properties".
        :param context: Execution context with authentication credentials.
        :return: Dictionary with a "company" key containing the updated company data.
        """

        company_id = inputs["company_id"]

        url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}"

        # Transform properties to HubSpot format
        payload = {"properties": inputs["properties"]}

        response = await context.fetch(
            url,
            method="PATCH",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)

        return ActionResult(data={"company": result}, cost_usd=None)


@hubspot.action("search_companies")
class SearchCompaniesActionHandler(ActionHandler):
    """
    Action handler to search for companies in HubSpot.

    Uses a query and a limit to search for companies via HubSpot's CRM API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the search_companies action.

        :param inputs: Dictionary with keys "query" (search term), "limit" (results per page) and "after".
        :param context: Execution context containing authentication details.
        :return: Parsed JSON response with the search results.
        """

        query = inputs["query"]
        limit = inputs.get("limit", 100)

        url = "https://api.hubapi.com/crm/v3/objects/companies/search"

        payload = {"query": query, "limit": limit}
        if inputs.get("after"):
            payload["after"] = inputs["after"]

        response = await fetch_with_rate_limit_retries(
            context,
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        result = await parse_response(response)

        return ActionResult(data=result, cost_usd=None)


@hubspot.action("search_companies_by_owner_name")
class SearchCompaniesByOwnerNameActionHandler(ActionHandler):
    """
    Action handler to search for companies by owner name in HubSpot.

    First retrieves the owner ID by name from the Owners API, then searches
    for companies associated with that owner using the Companies Search API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the search_companies_by_owner_name action.

        :param inputs: Dictionary with an owner ID, email or name, plus optional paging and properties.
        :param context: Execution context containing authentication details.
        :return: Dictionary with companies associated with the specified owner.
        """

        owner_name = inputs.get("owner_name", "")
        owner_id = inputs.get("owner_id")
        owner_email = inputs.get("owner_email")
        if not (owner_id or owner_email or owner_name.strip()):
            return ActionError(message="Provide an owner_id, owner_email or owner_name")
        limit = inputs.get("limit", 100)
        after = inputs.get("after")
        properties = inputs.get(
            "properties",
            [
                "name",
                "domain",
                "phone",
                "city",
                "state",
                "country",
                "industry",
                "numberofemployees",
                "annualrevenue",
                "hubspot_owner_id",
            ],
        )

        try:
            # Step 1: Find the owner by full name, or by first or last name when no full name matches
            retry_sleep_budget = {"remaining": 10}
            if owner_id:
                # Reuse the ID returned on the first page instead of reading the owner directory again.
                matches, read_every_owner = [{"id": owner_id}], True
            else:
                owners, read_every_owner = await _list_owners(context, retry_sleep_budget, email=owner_email)
                wanted = owner_name.strip().casefold()
                matches = (
                    owners
                    if owner_email
                    else (
                        [owner for owner in owners if _owner_name(owner).casefold() == wanted]
                        or [
                            owner
                            for owner in owners
                            if wanted
                            in ((owner.get("firstName") or "").casefold(), (owner.get("lastName") or "").casefold())
                        ]
                    )
                )

            if not matches:
                if not read_every_owner:
                    return ActionError(
                        message=(
                            f"Owner with name '{owner_name}' not found in the first {MAX_OWNER_PAGES * 100} owners. "
                            "Use search_owners to find the owner ID, then search_crm_objects with hubspot_owner_id."
                        ),
                    )
                return ActionError(
                    message=f"Owner with email '{owner_email}' not found"
                    if owner_email
                    else f"Owner with name '{owner_name}' not found"
                )
            if len(matches) > 1:
                candidates = ", ".join(
                    f"{_owner_name(owner)} ({owner.get('email') or owner.get('id')})" for owner in matches
                )
                return ActionError(
                    message=f"More than one owner matches '{owner_name}': {candidates}. Use the owner's full name."
                )

            owner_id = matches[0].get("id")
            matched_owner = {
                "id": owner_id,
                "firstName": matches[0].get("firstName"),
                "lastName": matches[0].get("lastName"),
                "email": matches[0].get("email"),
            }

            # Step 3: Search for companies with this owner ID
            search_url = "https://api.hubapi.com/crm/v3/objects/companies/search"
            search_payload = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "hubspot_owner_id",
                                "operator": "EQ",
                                "value": str(owner_id),
                            }
                        ]
                    }
                ],
                "properties": properties,
                "limit": limit,
            }
            if after:
                search_payload["after"] = after

            search_response = await fetch_with_rate_limit_retries(
                context,
                search_url,
                retry_sleep_budget=retry_sleep_budget,
                method="POST",
                json=search_payload,
                headers={"Content-Type": "application/json"},
            )
            search_result = await parse_response(search_response)

            companies = search_result.get("results", [])
            paging = search_result.get("paging")
            has_more = bool(paging and paging.get("next", {}).get("after"))

            return ActionResult(
                data={
                    "success": True,
                    "owner": matched_owner,
                    "companies": companies,
                    "total": len(companies),
                    "page_total": len(companies),
                    "has_more": has_more,
                    "paging": paging,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(
                message=f"Failed to search companies by owner name: {str(e)}",
            )


@hubspot.action("get_company_properties")
class GetCompanyPropertiesActionHandler(ActionHandler):
    """Retrieve all available company properties including custom properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        include_details = inputs.get("include_details", False)
        url = "https://api.hubapi.com/crm/v3/properties/companies"

        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        properties_data = await parse_response(response)

        results = properties_data.get("results", [])

        if include_details:
            # Return full property details
            properties = [
                {
                    "name": prop.get("name"),
                    "label": prop.get("label"),
                    "type": prop.get("type"),
                    "fieldType": prop.get("fieldType"),
                    "groupName": prop.get("groupName"),
                    "hubspotDefined": prop.get("hubspotDefined", False),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names (backward compatible)
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", False))

        return ActionResult(
            data={
                "properties": properties,
                "total_properties": len(properties),
                "custom_properties_count": custom_count,
            },
            cost_usd=None,
        )


@hubspot.action("get_deal_properties")
class GetDealPropertiesActionHandler(ActionHandler):
    """Retrieve all available deal properties including custom properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        include_details = inputs.get("include_details", False)
        url = "https://api.hubapi.com/crm/v3/properties/deals"

        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        properties_data = await parse_response(response)

        results = properties_data.get("results", [])

        if include_details:
            # Return full property details
            properties = [
                {
                    "name": prop.get("name"),
                    "label": prop.get("label"),
                    "type": prop.get("type"),
                    "fieldType": prop.get("fieldType"),
                    "groupName": prop.get("groupName"),
                    "hubspotDefined": prop.get("hubspotDefined", False),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", False))

        return ActionResult(
            data={
                "properties": properties,
                "total_properties": len(properties),
                "custom_properties_count": custom_count,
            },
            cost_usd=None,
        )


@hubspot.action("get_contact_properties")
class GetContactPropertiesActionHandler(ActionHandler):
    """Retrieve all available contact properties including custom properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        include_details = inputs.get("include_details", False)
        url = "https://api.hubapi.com/crm/v3/properties/contacts"

        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        properties_data = await parse_response(response)

        results = properties_data.get("results", [])

        if include_details:
            # Return full property details
            properties = [
                {
                    "name": prop.get("name"),
                    "label": prop.get("label"),
                    "type": prop.get("type"),
                    "fieldType": prop.get("fieldType"),
                    "groupName": prop.get("groupName"),
                    "hubspotDefined": prop.get("hubspotDefined", False),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", False))

        return ActionResult(
            data={
                "properties": properties,
                "total_properties": len(properties),
                "custom_properties_count": custom_count,
            },
            cost_usd=None,
        )


# Deal Management Actions


@hubspot.action("get_deal_notes")
class GetDealNotesActionHandler(ActionHandler):
    """
    Action handler to retrieve notes associated with a HubSpot deal.

    Fetches all notes for a specific deal using the CRM search API with association filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_deal_notes action.

        :param inputs: Dictionary with key "deal_id" and optional "limit" and "properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with notes for the deal.
        """
        deal_id = inputs["deal_id"]
        limit = min(inputs.get("limit", 100), 200)  # Max 200 per HubSpot API
        properties = inputs.get(
            "properties",
            [
                "hs_note_body",
                "hs_timestamp",
                "hubspot_owner_id",
                "hs_createdate",
                "hs_lastmodifieddate",
            ],
        )

        try:
            # Use search API to find notes associated with this deal
            search_url = "https://api.hubapi.com/crm/v3/objects/notes/search"
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "associations.deal",
                                "operator": "EQ",
                                "value": deal_id,
                            }
                        ]
                    }
                ],
                "properties": properties,
                "limit": limit,
                "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
            }
            if inputs.get("after"):
                search_body["after"] = inputs["after"]

            response = await fetch_with_rate_limit_retries(
                context,
                search_url,
                method="POST",
                json=search_body,
                headers={"Content-Type": "application/json"},
            )
            result = await parse_response(response)

            notes = result.get("results", [])

            # Convert timestamps to UTC strings
            for note in notes:
                if "properties" in note:
                    props = note["properties"]
                    for timestamp_field in [
                        "hs_timestamp",
                        "hs_createdate",
                        "hs_lastmodifieddate",
                    ]:
                        if timestamp_field in props and props[timestamp_field]:
                            props[timestamp_field] = convert_hubspot_timestamp_to_utc_string(props[timestamp_field])

            after = ((result.get("paging") or {}).get("next") or {}).get("after")
            return ActionResult(
                data={
                    "deal_id": deal_id,
                    "notes": notes,
                    "total": len(notes),
                    "total_matching": result.get("total", len(notes)),
                    "has_more": after is not None,
                    "after": after,
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(
                message=f"Failed to retrieve notes for deal {deal_id}: {str(e)}",
            )


# Transcripts fetched at once for one calls lookup; more trips HubSpot's rate limit
MAX_PARALLEL_TRANSCRIPT_FETCHES = 5


async def fetch_transcript(
    transcript_id: str,
    context: ExecutionContext,
    retry_sleep_budget: Dict[str, int] | None = None,
):
    """
    Fetch transcript utterances from the HubSpot Calling Transcripts API.
    Google Meet transcripts are stored here, not on the call object properties.
    Raises the request error when the transcript can't be fetched.
    """
    url = f"https://api.hubapi.com/crm/extensions/calling/2026-03/transcripts/{transcript_id}"
    response = await fetch_with_rate_limit_retries(
        context,
        url,
        retry_sleep_budget=retry_sleep_budget,
        method="GET",
    )
    result = await parse_response(response)
    if not isinstance(result, dict):
        raise ValueError("HubSpot returned an unreadable transcript")
    return result.get("transcriptUtterances", [])


async def _add_transcript(
    call: Dict[str, Any],
    transcript_id: str | None,
    context: ExecutionContext,
    retry_sleep_budget: Dict[str, int] | None,
    slots: asyncio.Semaphore,
) -> None:
    """Add a call's transcript utterances as "transcript", or why they couldn't be read as "transcript_error"."""
    async with slots:
        try:
            call["transcript"] = await fetch_transcript(transcript_id or call["id"], context, retry_sleep_budget)
        except (*REQUEST_ERRORS, ValueError) as e:
            # Without a transcript ID the call ID is only a guess, so a 404 for it means no transcript was found
            if transcript_id or getattr(e, "status", None) != 404:
                call["transcript_error"] = _error_text(e)


async def fetch_calls_with_transcripts(
    association_filter: dict,
    limit: int,
    context: ExecutionContext,
    retry_sleep_budget: Dict[str, int] | None = None,
    include_transcripts: bool = False,
):
    """
    Fetch calls for an association filter, optionally enriching them with full transcripts.
    """
    call_properties = [
        "hs_call_title",
        "hs_call_duration",
        "hs_call_status",
        "hs_call_direction",
        "hs_call_has_transcript",
        "hs_call_transcription_id",
        "hs_timestamp",
        "hs_createdate",
        "hs_lastmodifieddate",
        "hubspot_owner_id",
    ]

    url = "https://api.hubapi.com/crm/v3/objects/calls/search"
    body = {
        "filterGroups": [{"filters": [association_filter]}],
        "properties": call_properties,
        "limit": limit,
        "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
    }
    response = await fetch_with_rate_limit_retries(
        context,
        url,
        method="POST",
        json=body,
        retry_sleep_budget=retry_sleep_budget,
        headers={"Content-Type": "application/json"},
    )
    result = await parse_response(response)
    calls = result.get("results", [])

    # Convert timestamps
    for call in calls:
        if "properties" in call:
            for field in [
                "hs_timestamp",
                "hs_createdate",
                "hs_lastmodifieddate",
            ]:
                if call["properties"].get(field):
                    call["properties"][field] = convert_hubspot_timestamp_to_utc_string(call["properties"][field])

    if not include_transcripts:
        return calls

    # Fetch transcripts in parallel for calls that have one.
    # Note: hs_call_transcription_id can be null even when a transcript exists (known HubSpot bug).
    # Fallback: when hs_call_has_transcript is true but hs_call_transcription_id is null,
    # try using the call's own ID as the transcript ID — HubSpot often maps them 1:1.
    slots = asyncio.Semaphore(MAX_PARALLEL_TRANSCRIPT_FETCHES)
    transcript_tasks = []
    for call in calls:
        props = call.get("properties", {})
        transcript_id = props.get("hs_call_transcription_id")
        has_transcript = props.get("hs_call_has_transcript") == "true"

        # Without a transcript ID, fall back to the call ID (HubSpot bug workaround)
        if transcript_id or has_transcript:
            transcript_tasks.append(_add_transcript(call, transcript_id, context, retry_sleep_budget, slots))

    await asyncio.gather(*transcript_tasks)
    return calls


async def fetch_meetings(
    association_filter: dict,
    limit: int,
    context: ExecutionContext,
    retry_sleep_budget: Dict[str, int] | None = None,
):
    """
    Fetch meetings for a given association filter.
    Note: Google Meet transcripts are stored on call records, not meeting records.
    Meetings contain metadata (title, time, location) only.
    """
    meeting_properties = [
        "hs_meeting_title",
        "hs_meeting_start_time",
        "hs_meeting_end_time",
        "hs_meeting_location",
        "hs_timestamp",
        "hs_createdate",
        "hs_lastmodifieddate",
        "hubspot_owner_id",
    ]

    url = "https://api.hubapi.com/crm/v3/objects/meetings/search"
    body = {
        "filterGroups": [{"filters": [association_filter]}],
        "properties": meeting_properties,
        "limit": limit,
        "sorts": [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
    }
    response = await fetch_with_rate_limit_retries(
        context,
        url,
        method="POST",
        json=body,
        retry_sleep_budget=retry_sleep_budget,
        headers={"Content-Type": "application/json"},
    )
    result = await parse_response(response)
    meetings = result.get("results", [])

    for meeting in meetings:
        if "properties" in meeting:
            for field in [
                "hs_timestamp",
                "hs_createdate",
                "hs_lastmodifieddate",
                "hs_meeting_start_time",
                "hs_meeting_end_time",
            ]:
                if meeting["properties"].get(field):
                    meeting["properties"][field] = convert_hubspot_timestamp_to_utc_string(meeting["properties"][field])

    return meetings


@hubspot.action("get_contact_calls_and_meetings")
class GetContactCallsAndMeetingsActionHandler(ActionHandler):
    """
    Action handler to retrieve calls and meetings associated with a HubSpot contact.

    Fetches call and meeting metadata for a contact, with transcripts only when requested.
    Google Meet transcripts are stored on call records, not meeting records.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        contact_id = inputs["contact_id"]
        limit = min(inputs.get("limit", 50), 100)

        association_filter = {
            "propertyName": "associations.contact",
            "operator": "EQ",
            "value": contact_id,
        }

        try:
            retry_sleep_budget = {"remaining": 10}
            calls = await fetch_calls_with_transcripts(
                association_filter, limit, context, retry_sleep_budget, inputs.get("include_transcripts", False)
            )
            meetings = await fetch_meetings(association_filter, limit, context, retry_sleep_budget)

            return ActionResult(
                data={
                    "contact_id": contact_id,
                    "calls": calls,
                    "meetings": meetings,
                    "total_calls": len(calls),
                    "total_meetings": len(meetings),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve calls and meetings for contact {contact_id}: {str(e)}")


@hubspot.action("get_deal_calls_and_meetings")
class GetDealCallsAndMeetingsActionHandler(ActionHandler):
    """
    Action handler to retrieve calls and meetings associated with a HubSpot deal.

    Fetches call and meeting metadata for a deal, with transcripts only when requested.
    Google Meet transcripts are stored on call records, not meeting records.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        deal_id = inputs["deal_id"]
        limit = min(inputs.get("limit", 50), 100)

        association_filter = {
            "propertyName": "associations.deal",
            "operator": "EQ",
            "value": deal_id,
        }

        try:
            retry_sleep_budget = {"remaining": 10}
            calls = await fetch_calls_with_transcripts(
                association_filter, limit, context, retry_sleep_budget, inputs.get("include_transcripts", False)
            )
            meetings = await fetch_meetings(association_filter, limit, context, retry_sleep_budget)

            return ActionResult(
                data={
                    "deal_id": deal_id,
                    "calls": calls,
                    "meetings": meetings,
                    "total_calls": len(calls),
                    "total_meetings": len(meetings),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve calls and meetings for deal {deal_id}: {str(e)}")


@hubspot.action("get_deals")
class GetDealsActionHandler(ActionHandler):
    """
    Action handler to retrieve deals from HubSpot.

    Fetches deals with comprehensive properties including close dates, deal stages,
    amounts, and associated contacts/companies for pipeline analysis.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_deals action.

        :param inputs: Dictionary with optional keys "limit", "pipeline_id", "year".
        :param context: Execution context containing authentication information.
        :return: Dictionary with a "deals" key containing deals data.
        """

        fetch_all = inputs.get("fetch_all", False)  # Default to single page to prevent context overflow
        limit_per_page = min(inputs.get("limit", 50), 100)  # HubSpot max is 100
        sort_property = inputs.get("sort_property", "hs_lastmodifieddate")
        sort_direction = "DESCENDING" if inputs.get("sort_direction", "DESC") == "DESC" else "ASCENDING"
        delay_between_requests = inputs.get(
            "delay_between_requests", 0
        )  # Default to 0 (no delay) for backward compatibility

        deals = []
        unique_deal_ids = set()  # For deduplication
        after = inputs.get("after")  # Allow starting from specific pagination token
        total_fetched = 0
        # Respect user's limit parameter even when fetch_all is false
        user_limit = inputs.get("limit", 50)
        max_total = inputs.get("max_total", user_limit if not fetch_all else 100)

        url = "https://api.hubapi.com/crm/v3/objects/deals/search"
        retry_sleep_budget = {"remaining": 10}

        # Use custom properties if provided, otherwise use standard properties
        properties = inputs.get(
            "properties",
            [
                "dealname",
                "amount",
                "closedate",
                "dealstage",
                "pipeline",
                "dealtype",
                "hs_deal_stage_probability",
                "createdate",
                "hs_lastmodifieddate",
                "hubspot_owner_id",
                "hs_analytics_source",
                "hs_deal_amount_calculation_preference",
                "notes_last_contacted",
                "hs_last_sales_activity_timestamp",
                "hs_last_sales_activity_type",
                "hs_latest_meeting_activity",
                "hs_last_email_activity",
                "hs_last_call_activity",
            ],
        )

        # Build single filter group with AND logic (all filters in one group)
        all_filters = []

        # Pipeline filtering
        if inputs.get("pipeline_id"):
            all_filters.append({"propertyName": "pipeline", "operator": "EQ", "value": inputs["pipeline_id"]})

        # Year filtering to reduce response size
        if inputs.get("year"):
            start_ms = int(datetime(inputs["year"], 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            end_ms = int(datetime(inputs["year"], 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
            all_filters.append({"propertyName": "closedate", "operator": "GTE", "value": str(start_ms)})
            all_filters.append({"propertyName": "closedate", "operator": "LTE", "value": str(end_ms)})

        # Date range filtering with flexible start and end dates
        date_field = inputs.get("date_field", "hs_lastmodifieddate")
        try:
            # The parsed dates are naive; they're UTC, not the server's local time
            if inputs.get("start_date"):
                start_date = parse_date_string_to_utc(inputs["start_date"]).replace(tzinfo=timezone.utc)
                start_ms = int(start_date.timestamp() * 1000)
                all_filters.append({"propertyName": date_field, "operator": "GTE", "value": str(start_ms)})
            if inputs.get("end_date"):
                # Set to end of day (23:59:59) for end date
                end_date = parse_date_string_to_utc(inputs["end_date"]).replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                end_ms = int(end_date.timestamp() * 1000)
                all_filters.append({"propertyName": date_field, "operator": "LTE", "value": str(end_ms)})
        except ValueError as e:
            # Searching without the date filter would return deals outside the requested range
            return ActionError(message=str(e))

        next_after = None
        while total_fetched < max_total:
            # Add delay between requests to avoid rate limits (skip on first request)
            if total_fetched > 0 and delay_between_requests > 0:
                await asyncio.sleep(delay_between_requests)

            request_body = {
                "limit": min(limit_per_page, max_total - total_fetched),
                "properties": properties,
                "sorts": [{"propertyName": sort_property, "direction": sort_direction}],
            }

            # Add after token for pagination
            if after:
                request_body["after"] = after

            # Create single filter group if any filters exist
            if all_filters:
                request_body["filterGroups"] = [{"filters": all_filters}]

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                retry_sleep_budget=retry_sleep_budget,
                method="POST",
                json=request_body,
                headers={"Content-Type": "application/json"},
            )

            result = await parse_response(response)
            page_deals = (result or {}).get("results") or []

            # Deduplicate deals by ID
            new_deals = []
            for deal in page_deals:
                deal_id = deal.get("id")
                if deal_id and deal_id not in unique_deal_ids:
                    unique_deal_ids.add(deal_id)
                    new_deals.append(deal)

            deals.extend(new_deals)
            total_fetched += len(new_deals)

            # Log deduplication info if duplicates were found
            duplicates_removed = len(page_deals) - len(new_deals)
            if duplicates_removed > 0:
                # Store deduplication info for debugging
                if not hasattr(context, "_deduplication_stats"):
                    context._deduplication_stats = {
                        "pages_with_duplicates": 0,
                        "total_duplicates_removed": 0,
                    }
                context._deduplication_stats["pages_with_duplicates"] += 1
                context._deduplication_stats["total_duplicates_removed"] += duplicates_removed

            # HubSpot only returns a cursor when there's another page
            next_after = (((result or {}).get("paging") or {}).get("next") or {}).get("after")
            if not next_after or not page_deals:
                next_after = None
                break
            after = next_after

        # Convert deal dates from UTC timestamps to readable UTC strings
        for deal in deals:
            convert_deal_dates_to_utc(deal)

        # Prepare clear pagination guidance
        has_more_pages = next_after is not None
        pagination_instructions = ""
        next_page_params = {}

        if has_more_pages:
            limit_note = (
                f"Stopped at the maximum of {max_total} deals; increase 'max_total' (up to 5000) to get more at once. "
                if total_fetched >= max_total and fetch_all
                else ""
            )
            pagination_instructions = (
                f"There are more deals available. You retrieved {total_fetched} deals so far. {limit_note}"
                f"To get the next page, use 'get_deals' with the same parameters plus 'after': '{next_after}'. "
                "Or set 'fetch_all': true to get the remaining deals automatically, up to 'max_total'. "
                "For rate limiting, add 'delay_between_requests': 1.0."
            )
            next_page_params = {
                "action": "get_deals",
                "parameters": {**inputs, "after": next_after},
                "alternative": {**inputs, "after": next_after, "fetch_all": True},
                "rate_limited_alternative": {
                    **inputs,
                    "after": next_after,
                    "fetch_all": True,
                    "delay_between_requests": 1.0,
                },
            }
        else:
            pagination_instructions = (
                f"You have retrieved all available deals ({total_fetched} total). No more pages available."
            )

        # Get deduplication stats if available
        deduplication_stats = getattr(context, "_deduplication_stats", None)

        # Build comprehensive result with deduplication info
        final_result = {
            "results": deals,
            "total": len(deals),
            "pagination": {
                "fetched_all_available": not has_more_pages,
                "total_fetched": total_fetched,
                "last_after_token": next_after,
                "has_more_pages": has_more_pages,
                "current_page_size": len(deals),
                "pagination_instructions": pagination_instructions,
                "next_page_params": next_page_params,
            },
            "deduplication": {
                "enabled": True,
                "unique_deals_count": len(unique_deal_ids),
                "duplicates_removed": deduplication_stats["total_duplicates_removed"] if deduplication_stats else 0,
                "pages_with_duplicates": deduplication_stats["pages_with_duplicates"] if deduplication_stats else 0,
            },
        }

        return ActionResult(data=final_result, cost_usd=None)


@hubspot.action("get_deal")
class GetDealActionHandler(ActionHandler):
    """
    Action handler to retrieve a specific deal by its ID.

    Fetches detailed deal information including all relevant properties
    and associations with contacts and companies.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_deal action.

        :param inputs: Dictionary with key "deal_id" for the target deal.
        :param context: Execution context including authentication information.
        :return: Dictionary with a "deal" key containing the deal data.
        """

        deal_id = inputs["deal_id"]

        # Use custom properties if provided, otherwise use standard properties
        properties = inputs.get(
            "properties",
            [
                "dealname",
                "amount",
                "closedate",
                "dealstage",
                "pipeline",
                "dealtype",
                "hs_deal_stage_probability",
                "createdate",
                "hs_lastmodifieddate",
                "hubspot_owner_id",
                "hs_analytics_source",
                "hs_deal_amount_calculation_preference",
                "description",
                "notes_last_contacted",
                "hs_last_sales_activity_timestamp",
                "hs_last_sales_activity_type",
                "hs_latest_meeting_activity",
                "hs_last_email_activity",
                "hs_last_call_activity",
            ],
        )

        properties_param = ",".join(properties)
        url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties={properties_param}"

        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        deal = await parse_response(response)

        # Convert deal dates from UTC timestamps to readable UTC strings
        convert_deal_dates_to_utc(deal)

        return ActionResult(data={"deal": deal}, cost_usd=None)


@hubspot.action("search_deals")
class SearchDealsActionHandler(ActionHandler):
    """
    Action handler to search for deals using advanced filters and text queries.

    Implements comprehensive pagination, UTC date handling, pipeline filtering,
    and deduplication as per HubSpot best practices. Supports text-based search across deal names
    and filtering by deal stage, amount ranges, close date ranges, and other criteria.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the search_deals action with comprehensive pagination and filtering.

        :param inputs: Dictionary with optional filtering criteria including "query" for text search,
                      "pipeline_id" for pipeline filtering, "year" for year-based filtering,
                      and "fetch_all" for complete pagination.
        :param context: Execution context containing authentication details.
        :return: Parsed JSON response containing filtered deals with comprehensive pagination.
        """

        fetch_all = inputs.get("fetch_all", False)  # Default to single page to prevent context overflow
        limit_per_page = min(inputs.get("limit", 50), 100)  # HubSpot max is 100

        deals = []
        unique_deal_ids = set()  # For deduplication
        has_more = True
        after = inputs.get("after")  # Allow starting from specific pagination token
        next_after = None  # HubSpot's cursor for the page after the last one fetched
        total_fetched = 0
        # Respect user's limit parameter even when fetch_all is false
        user_limit = inputs.get("limit", 50)
        max_total = inputs.get("max_total", user_limit if not fetch_all else 100)

        url = "https://api.hubapi.com/crm/v3/objects/deals/search"

        query = inputs.get("query", "")

        # Use custom properties if provided, otherwise use standard properties
        properties = inputs.get(
            "properties",
            [
                "dealname",
                "amount",
                "closedate",
                "dealstage",
                "pipeline",
                "dealtype",
                "hs_deal_stage_probability",
                "createdate",
                "hs_lastmodifieddate",
                "hubspot_owner_id",
                "hs_analytics_source",
            ],
        )

        # Apply close-date bounds in HubSpot, including the intersection with an optional year.
        try:
            start_date = parse_date_string_to_utc(inputs.get("close_date_start"))
            end_date = parse_date_string_to_utc(inputs.get("close_date_end"))
            if inputs.get("year"):
                year = int(inputs["year"])
                year_start = datetime(year, 1, 1)
                year_end = datetime(year, 12, 31, 23, 59, 59)
                start_date = max(start_date, year_start) if start_date else year_start
                end_date = min(end_date, year_end) if end_date else year_end
            if start_date and end_date and start_date > end_date:
                return ActionError(message="The close-date start must be at or before the close-date end")
        except ValueError as e:
            return ActionError(message=str(e))

        while has_more and total_fetched < max_total:
            request_body = {
                "limit": min(limit_per_page, max_total - total_fetched),
                "properties": properties,
            }

            # Add after token for pagination
            if after:
                request_body["after"] = after

            # Add text query for deal name search
            if query:
                request_body["query"] = query

            # All filters share one group so HubSpot ANDs them; separate groups would be ORed
            filters = []

            if inputs.get("pipeline_id"):
                filters.append({"propertyName": "pipeline", "operator": "EQ", "value": inputs["pipeline_id"]})

            if start_date:
                filters.append(
                    {
                        "propertyName": "closedate",
                        "operator": "GTE",
                        "value": str(int(start_date.replace(tzinfo=timezone.utc).timestamp() * 1000)),
                    }
                )
            if end_date:
                filters.append(
                    {
                        "propertyName": "closedate",
                        "operator": "LTE",
                        "value": str(int(end_date.replace(tzinfo=timezone.utc).timestamp() * 1000)),
                    }
                )

            if inputs.get("deal_stage"):
                filters.append({"propertyName": "dealstage", "operator": "EQ", "value": inputs["deal_stage"]})

            if inputs.get("min_amount") is not None:
                filters.append({"propertyName": "amount", "operator": "GTE", "value": str(inputs["min_amount"])})

            if inputs.get("max_amount") is not None:
                filters.append({"propertyName": "amount", "operator": "LTE", "value": str(inputs["max_amount"])})

            if filters:
                request_body["filterGroups"] = [{"filters": filters}]

            # Add sorting
            if inputs.get("sort_property"):
                sort_direction = "DESCENDING" if inputs.get("sort_direction", "DESC") == "DESC" else "ASCENDING"
                request_body["sorts"] = [
                    {
                        "propertyName": inputs["sort_property"],
                        "direction": sort_direction,
                    }
                ]

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                method="POST",
                json=request_body,
                headers={"Content-Type": "application/json"},
            )

            result = await parse_response(response)

            if result and result.get("results"):
                page_deals = result["results"]

                # Deduplicate deals by ID
                new_deals = []
                for deal in page_deals:
                    deal_id = deal.get("id")
                    if deal_id and deal_id not in unique_deal_ids:
                        unique_deal_ids.add(deal_id)
                        new_deals.append(deal)

                deals.extend(new_deals)
                total_fetched += len(new_deals)

                # Log deduplication info if duplicates were found
                duplicates_removed = len(page_deals) - len(new_deals)
                if duplicates_removed > 0:
                    # Store deduplication info for debugging
                    if not hasattr(context, "_search_deduplication_stats"):
                        context._search_deduplication_stats = {
                            "pages_with_duplicates": 0,
                            "total_duplicates_removed": 0,
                        }
                    context._search_deduplication_stats["pages_with_duplicates"] += 1
                    context._search_deduplication_stats["total_duplicates_removed"] += duplicates_removed

                # Check for more pages
                paging = result.get("paging")
                if paging and paging.get("next") and paging["next"].get("after"):
                    after = next_after = paging["next"]["after"]
                    # Extra pages are opt-in; always return the next cursor.
                    has_more = fetch_all and total_fetched < max_total
                else:
                    next_after = None
                    has_more = False
            else:
                next_after = None
                has_more = False

        # Convert deal dates from UTC timestamps to readable UTC strings
        for deal in deals:
            convert_deal_dates_to_utc(deal)

        return ActionResult(
            data={
                "results": deals,
                "total": len(deals),
                "total_matching": result.get("total", len(deals)),
                "pagination": {
                    "has_more_pages": next_after is not None,
                    "current_page_size": len(deals),
                    "after": next_after,
                },
            },
            cost_usd=None,
        )


@hubspot.action("create_deal")
class CreateDealActionHandler(ActionHandler):
    """
    Action handler to create a new deal in HubSpot.

    Sends a POST request with the provided deal properties to create a new deal record.
    Optionally associates the deal with contacts or companies.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the create_deal action.

        :param inputs: Dictionary with "properties" and optional "associations".
        :param context: Execution context with authentication details.
        :return: Dictionary with a "deal" key mapping to the created deal data.
        """

        url = "https://api.hubapi.com/crm/v3/objects/deals"

        payload = {"properties": inputs["properties"]}

        if inputs.get("associations"):
            payload["associations"] = inputs["associations"]

        response = await context.fetch(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)

        return ActionResult(data={"deal": result}, cost_usd=None)


@hubspot.action("update_deal")
class UpdateDealActionHandler(ActionHandler):
    """
    Action handler to update an existing deal in HubSpot.

    Uses the deal ID and provided properties to update the deal information.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the update_deal action.

        :param inputs: Dictionary with keys "deal_id" and "properties".
        :param context: Execution context with authentication credentials.
        :return: Dictionary with a "deal" key containing the updated deal data.
        """

        deal_id = inputs["deal_id"]

        url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}"

        payload = {"properties": inputs["properties"]}

        response = await context.fetch(
            url,
            method="PATCH",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        result = await parse_response(response)

        return ActionResult(data={"deal": result}, cost_usd=None)


@hubspot.action("get_recent_deals")
class GetRecentDealsActionHandler(ActionHandler):
    """
    Action handler to retrieve recently created or modified deals from HubSpot.

    Fetches deals based on provided limit, sorting property, and direction.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_recent_deals action.

        :param inputs: Dictionary with optional keys "limit", "sort_property", "sort_direction".
        :param context: Execution context containing authentication details.
        :return: Dictionary with a "deals" key containing recent deals data.
        """

        limit = inputs.get("limit", 100)
        sort_property = inputs.get("sort_property", "createdate")

        sort_direction_map = {"DESC": "DESCENDING", "ASC": "ASCENDING"}
        sort_direction = sort_direction_map.get(inputs.get("sort_direction", "DESC"), "DESCENDING")

        url = "https://api.hubapi.com/crm/v3/objects/deals/search"

        properties = [
            "dealname",
            "amount",
            "closedate",
            "dealstage",
            "pipeline",
            "dealtype",
            "hs_deal_stage_probability",
            "createdate",
            "hs_lastmodifieddate",
            "hubspot_owner_id",
        ]

        request_body = {
            "limit": limit,
            "properties": properties,
            "sorts": [{"propertyName": sort_property, "direction": sort_direction}],
        }

        response = await fetch_with_rate_limit_retries(
            context,
            url,
            method="POST",
            json=request_body,
            headers={"Content-Type": "application/json"},
        )

        deals = await parse_response(response)

        # Convert deal dates from UTC timestamps to readable UTC strings
        results = deals["results"] if deals.get("results") else []
        for deal in results:
            convert_deal_dates_to_utc(deal)

        return ActionResult(data={"deals": results}, cost_usd=None)


@hubspot.action("get_deal_pipelines")
class GetDealPipelinesActionHandler(ActionHandler):
    """
    Action handler to retrieve all deal pipelines and their stages from HubSpot.

    Fetches the complete list of deal pipelines with their corresponding stages,
    which is useful for understanding deal flow and stage management.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_deal_pipelines action.

        :param inputs: Dictionary (no required inputs for this action).
        :param context: Execution context containing authentication information.
        :return: Dictionary with a "pipelines" key containing list of all deal pipelines and stages.
        """

        url = "https://api.hubapi.com/crm/v3/pipelines/deals"

        response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
        pipelines_data = await parse_response(response)

        return ActionResult(data={"pipelines": pipelines_data.get("results", [])}, cost_usd=None)


@hubspot.action("get_lists")
class GetListsHandler(ActionHandler):
    """Retrieve all available lists/segments from HubSpot with filtering options"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        # Use search endpoint which is more reliable for getting all lists
        url = "https://api.hubapi.com/crm/v3/lists/search"

        # Build request body
        search_body = {
            "count": 500,  # Maximum allowed
            "offset": 0,
        }

        # Add optional parameters
        if inputs.get("list_ids"):
            search_body["listIds"] = inputs["list_ids"]
        if inputs.get("processing_types"):
            search_body["processingTypes"] = inputs["processing_types"]

        # The search endpoint can't return filter definitions; get_list does

        response = await fetch_with_rate_limit_retries(
            context,
            url,
            method="POST",
            json=search_body,
            headers={"Content-Type": "application/json"},
        )
        data = await parse_response(response)

        lists = data.get("lists", [])
        total = data.get("total", len(lists))
        has_more = data.get("hasMore", False)

        # If there are more results, we could implement pagination here
        # For now, return the first 500 lists

        return ActionResult(
            data={
                "lists": lists,
                "total_lists": len(lists),
                "total_available": total,
                "has_more": has_more,
            },
            cost_usd=None,
        )


@hubspot.action("get_list")
class GetListHandler(ActionHandler):
    """Retrieve detailed information about a specific list by ID"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs["list_id"]
        include_filters = inputs.get("include_filters", True)

        url = f"https://api.hubapi.com/crm/v3/lists/{list_id}"
        params = {}
        if include_filters:
            params["includeFilters"] = "true"

        response = await fetch_with_rate_limit_retries(context, url, params=params)
        data = await parse_response(response)

        return ActionResult(data={"list": data.get("list", {})}, cost_usd=None)


@hubspot.action("search_lists")
class SearchListsHandler(ActionHandler):
    """Search for lists by name and other criteria with pagination"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        url = "https://api.hubapi.com/crm/v3/lists/search"

        search_body = {}
        if inputs.get("query"):
            search_body["query"] = inputs["query"]
        if inputs.get("count"):
            search_body["count"] = inputs["count"]
        if inputs.get("offset"):
            search_body["offset"] = inputs["offset"]
        if inputs.get("processing_types"):
            search_body["processingTypes"] = inputs["processing_types"]

        response = await fetch_with_rate_limit_retries(
            context,
            url,
            method="POST",
            json=search_body,
            headers={"Content-Type": "application/json"},
        )

        data = await parse_response(response)
        results = data.get("lists", [])
        has_more = bool(data.get("hasMore"))

        return ActionResult(
            data={
                "results": results,
                "total": len(results),
                "total_matching": data.get("total", len(results)),
                "has_more": has_more,
                # HubSpot documents the response offset both as the next page's and as this page's start, so
                # take whichever is further on
                "next_offset": max(data.get("offset") or 0, (inputs.get("offset") or 0) + len(results))
                if has_more
                else None,
            },
            cost_usd=None,
        )


@hubspot.action("get_list_memberships")
class GetListMembershipsHandler(ActionHandler):
    """Get raw list member IDs and timestamps without contact details"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        list_id = inputs["list_id"]
        limit = inputs.get("limit", 1000)
        batch_size = min(inputs.get("batch_size", 250), 250)  # Max 250 per API call

        url = f"https://api.hubapi.com/crm/v3/lists/{list_id}/memberships"

        all_memberships = []
        after_token = None
        total_retrieved = 0
        retry_sleep_budget = {"remaining": 10}

        while total_retrieved < limit:
            params = {"limit": min(batch_size, limit - total_retrieved)}
            if after_token:
                params["after"] = after_token

            response = await fetch_with_rate_limit_retries(
                context,
                url,
                retry_sleep_budget=retry_sleep_budget,
                params=params,
            )
            data = await parse_response(response)

            batch_memberships = data.get("results", [])
            all_memberships.extend(batch_memberships)
            total_retrieved += len(batch_memberships)

            # Check for more pages
            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after_token = next_page.get("after")

            if not after_token or len(batch_memberships) == 0:
                break

        return ActionResult(
            data={
                "list_id": list_id,
                "memberships": all_memberships,
                "total_memberships": len(all_memberships),
                "has_more": after_token is not None,
            },
            cost_usd=None,
        )


@hubspot.action("get_contact_associations")
class GetContactAssociationsHandler(ActionHandler):
    """Retrieve a contact's linked records, with association labels"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        contact_id = inputs["contact_id"]
        data = await _record_associations("contacts", contact_id, inputs, ["companies", "deals", "meetings"], context)
        if isinstance(data, ActionError):
            return data
        return ActionResult(data={"contact_id": contact_id, **data}, cost_usd=None)


@hubspot.action("get_company_associations")
class GetCompanyAssociationsHandler(ActionHandler):
    """Retrieve a company's linked records, with association labels"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        company_id = inputs["company_id"]
        data = await _record_associations("companies", company_id, inputs, ["contacts", "deals", "tickets"], context)
        if isinstance(data, ActionError):
            return data
        return ActionResult(data={"company_id": company_id, **data}, cost_usd=None)


@hubspot.action("get_deal_associations")
class GetDealAssociationsHandler(ActionHandler):
    """Retrieve a deal's linked records, with association labels"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        deal_id = inputs["deal_id"]
        data = await _record_associations("deals", deal_id, inputs, ["contacts", "companies"], context)
        if isinstance(data, ActionError):
            return data
        return ActionResult(data={"deal_id": deal_id, **data}, cost_usd=None)


@hubspot.action("get_association_labels")
class GetAssociationLabelsHandler(ActionHandler):
    """List the association types, including custom labels, that can link two object types"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        from_type = inputs["from_object_type"]
        to_type = inputs["to_object_type"]
        try:
            labels = await _association_labels(context, from_type, to_type, {"remaining": 10})
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to list {from_type} to {to_type} association labels: {_error_text(e)}")
        return ActionResult(data={"labels": labels, "total": len(labels)}, cost_usd=None)


@hubspot.action("create_association")
class CreateAssociationHandler(ActionHandler):
    """Link two CRM records with HubSpot's default association type, or with a named label"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        from_type = inputs["from_object_type"]
        from_id = inputs["from_object_id"]
        to_type = inputs["to_object_type"]
        to_id = inputs["to_object_id"]
        label = inputs.get("label")
        association_type_id = inputs.get("association_type_id")
        records = f"{from_type} {from_id} with {to_type} {to_id}"
        message = f"Associated {records}"
        url = f"{OBJECTS_API_URL}/{from_type}/{from_id}/associations"
        retry_sleep_budget = {"remaining": 10}

        try:
            if label or association_type_id is not None:
                types = await _association_labels(context, from_type, to_type, retry_sleep_budget)
                if association_type_id is not None:
                    match = next((t for t in types if t.get("typeId") == association_type_id), None)
                    wanted = f"type ID {association_type_id}"
                else:
                    match = next((t for t in types if (t.get("label") or "").casefold() == label.casefold()), None)
                    wanted = f"label {label!r}"
                if match is None:
                    available = ", ".join(f"{t['label']} ({t['typeId']})" for t in types if t.get("label")) or "none"
                    return ActionError(
                        message=f"No {from_type} to {to_type} association has the {wanted}. Labels: {available}"
                    )
                message += f" as {match.get('label') or match['typeId']}"
                links, unfinished = await _read_associations(context, from_type, to_type, [from_id], retry_sleep_budget)
                if unfinished:
                    return ActionError(message="Cannot safely add a label: existing association labels are incomplete")
                association_types = {}
                for link in links.get(str(from_id), []):
                    if str(link["toObjectId"]) == str(to_id):
                        for existing in link.get("associationTypes", []):
                            association_types[(existing["category"], existing["typeId"])] = {
                                "associationCategory": existing["category"],
                                "associationTypeId": existing["typeId"],
                            }
                association_types[(match["category"], match["typeId"])] = {
                    "associationCategory": match["category"],
                    "associationTypeId": match["typeId"],
                }
                response = await fetch_with_rate_limit_retries(
                    context,
                    f"{url}/{to_type}/{to_id}",
                    retry_sleep_budget=retry_sleep_budget,
                    method="PUT",
                    json=list(association_types.values()),
                    headers={"Content-Type": "application/json"},
                )
            else:
                response = await fetch_with_rate_limit_retries(
                    context,
                    f"{url}/default/{to_type}/{to_id}",
                    retry_sleep_budget=retry_sleep_budget,
                    method="PUT",
                    # HubSpot rejects this bodyless PUT with 415 unless it's marked as JSON
                    headers={"Content-Type": "application/json"},
                )
        except (*REQUEST_ERRORS, ValueError) as e:
            return ActionError(message=f"Failed to associate {records}: {_error_text(e)}")

        return ActionResult(
            data={
                "success": True,
                "message": message,
                "response": await parse_response(response),
            },
            cost_usd=None,
        )


@hubspot.action("get_list_members")
class GetListMembersHandler(ActionHandler):
    """Retrieve a bounded set of list members with optional contact details."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        import time

        start_time = time.time()

        list_id = inputs["list_id"]
        limit = inputs.get("limit", 50)
        contact_properties = inputs.get(
            "contact_properties",
            ["email", "firstname", "lastname", "phone", "company", "jobtitle"],
        )
        include_timestamps = inputs.get("include_membership_timestamps", True)
        include_contact_details = inputs.get("include_contact_details", True)

        total_api_calls = 0
        retry_sleep_budget = {"remaining": 10}

        # Step 1: Get list metadata
        list_url = f"https://api.hubapi.com/crm/v3/lists/{list_id}"
        list_response = await fetch_with_rate_limit_retries(
            context,
            list_url,
            retry_sleep_budget=retry_sleep_budget,
        )
        list_data = await parse_response(list_response)
        total_api_calls += 1

        list_info = list_data.get("list", {})
        list_metadata = {
            "list_id": list_info.get("listId", list_id),
            "name": list_info.get("name", ""),
            "size": list_info.get("size", 0),
            "processing_type": list_info.get("processingType", ""),
            "object_type_id": list_info.get("objectTypeId", ""),
        }

        # Step 2: Get member IDs with timestamps
        memberships_url = f"https://api.hubapi.com/crm/v3/lists/{list_id}/memberships"
        all_memberships = []
        after_token = inputs.get("after")
        total_retrieved = 0

        # Fetch memberships in batches of 250 (max limit)
        while total_retrieved < limit:
            params = {"limit": min(250, limit - total_retrieved)}
            if after_token:
                params["after"] = after_token

            response = await fetch_with_rate_limit_retries(
                context,
                memberships_url,
                retry_sleep_budget=retry_sleep_budget,
                params=params,
            )
            data = await parse_response(response)
            total_api_calls += 1

            batch_memberships = data.get("results", [])
            all_memberships.extend(batch_memberships)
            total_retrieved += len(batch_memberships)

            # Check pagination
            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after_token = next_page.get("after")

            if not after_token or len(batch_memberships) == 0:
                break

        # Step 3: Batch fetch contact details
        contact_ids = [m["recordId"] for m in all_memberships]
        membership_timestamps = {m["recordId"]: m["membershipTimestamp"] for m in all_memberships}

        all_contacts = []
        failed_contact_ids = []
        batch_errors = []

        # Process contacts in batches of 100 (max for batch read)
        detail_ids = contact_ids if include_contact_details else []
        for i in range(0, len(detail_ids), 100):
            batch_ids = contact_ids[i : i + 100]

            batch_request = {
                "properties": contact_properties,
                "inputs": [{"id": contact_id} for contact_id in batch_ids],
            }

            try:
                contacts_url = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
                contacts_response = await fetch_with_rate_limit_retries(
                    context,
                    contacts_url,
                    retry_sleep_budget=retry_sleep_budget,
                    method="POST",
                    json=batch_request,
                    headers={"Content-Type": "application/json"},
                )
                contacts_data = await parse_response(contacts_response)
                total_api_calls += 1

                batch_contacts = contacts_data.get("results", [])
                all_contacts.extend(batch_contacts)
                returned_ids = {str(contact["id"]) for contact in batch_contacts}
                missing_ids = [contact_id for contact_id in batch_ids if str(contact_id) not in returned_ids]
                failed_contact_ids.extend(missing_ids)
                if missing_ids:
                    batch_errors.append("Contact batch did not return IDs: " + ", ".join(map(str, missing_ids)))
                for error in contacts_data.get("errors", []):
                    batch_errors.append(error.get("message") or error.get("category") or "Contact batch failed")
                reason = _unfinished_batch_reason(contacts_data)
                if reason:
                    batch_errors.append(f"HubSpot {reason} the contact lookup")

            except REQUEST_ERRORS as e:
                # Keep the members that loaded, and name the ones that didn't rather than dropping them
                failed_contact_ids.extend(batch_ids)
                batch_errors.append(_error_text(e))
                continue

        if not include_contact_details:
            all_contacts = [{"id": contact_id} for contact_id in contact_ids]

        # Step 4: Combine data
        members = []
        for contact in all_contacts:
            contact_id = contact.get("id")
            properties = contact.get("properties", {})

            member = {"contact_id": contact_id}

            if include_contact_details:
                member["properties"] = properties
                # Preserve the convenient top-level fields for existing workflows.
                for prop in ("email", "firstname", "lastname", "phone", "company", "jobtitle"):
                    member[prop] = properties.get(prop)

            # Add membership timestamp if requested
            if include_timestamps and contact_id in membership_timestamps:
                member["membership_timestamp"] = membership_timestamps[contact_id]

            members.append(member)

        # Performance stats
        end_time = time.time()
        execution_time = end_time - start_time
        performance_stats = {
            "total_api_calls": total_api_calls,
            "execution_time_seconds": round(execution_time, 2),
            "members_per_second": round(len(members) / execution_time, 2) if execution_time > 0 else 0,
        }

        result = {
            "list_metadata": list_metadata,
            "members": members,
            "total_members": list_metadata["size"],
            "retrieved_count": len(members),
            "has_more": after_token is not None,
            "after": after_token,
            "performance_stats": performance_stats,
        }
        if failed_contact_ids:
            result["failed_contact_ids"] = failed_contact_ids
        if batch_errors:
            result["errors"] = batch_errors
        return ActionResult(data=result, cost_usd=None)


@hubspot.action("get_owner")
class GetOwnerActionHandler(ActionHandler):
    """
    Action handler to retrieve a HubSpot owner by their ID.

    Fetches owner details including name, email, and team information.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_owner action.

        :param inputs: Dictionary with key "owner_id".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with owner information.
        """
        owner_id = inputs["owner_id"]

        url = f"https://api.hubapi.com/crm/v3/owners/{owner_id}"

        try:
            response = await fetch_with_rate_limit_retries(context, url, headers={"Content-Type": "application/json"})
            owner = await parse_response(response)

            return ActionResult(data={"owner": owner}, cost_usd=None)

        except Exception as e:
            return ActionError(message=f"Failed to retrieve owner: {str(e)}")


# ==================== Any CRM Object ====================

OWNERS_API_URL = "https://api.hubapi.com/crm/owners/2026-09"
ACCOUNT_DETAILS_API_URL = "https://api.hubapi.com/account-info/2026-09/details"
PROPERTIES_API_URL = "https://api.hubapi.com/crm/properties/2026-09"

# Owner pages read when matching by name, 100 owners each
MAX_OWNER_PAGES = 20

# HubSpot's limits on one search: filter groups, and filters across all groups
MAX_SEARCH_FILTER_GROUPS = 5
MAX_SEARCH_FILTERS = 18

# The associations.<type> search pseudo-property names the linked record's type in the singular
ASSOCIATION_FILTER_TYPES = {"contacts": "contact", "companies": "company", "deals": "deal", "tickets": "ticket"}

# Object types with a record page in HubSpot, and the type ID their page URLs use
RECORD_PAGE_TYPE_IDS = {"contacts": "0-1", "companies": "0-2", "deals": "0-3", "tickets": "0-5"}

# Linked records returned per type for each record get_crm_objects reads
MAX_LINKS_PER_RECORD = 100


async def _list_owners(
    context: ExecutionContext, retry_sleep_budget: Dict[str, int], email: str | None = None
) -> tuple[list[Dict[str, Any]], bool]:
    """Return active HubSpot owners, only those with the email when one is given, and whether every page was read."""
    owners, after = [], None
    for _ in range(MAX_OWNER_PAGES):
        params = {"limit": 100}
        if email:
            params["email"] = email
        if after:
            params["after"] = after
        response = await fetch_with_rate_limit_retries(
            context,
            OWNERS_API_URL,
            retry_sleep_budget=retry_sleep_budget,
            params=params,
            headers={"Content-Type": "application/json"},
        )
        data = await parse_response(response)
        owners.extend(data.get("results", []))
        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        if not after:
            return owners, True
    return owners, False


def _owner_name(owner: Dict[str, Any]) -> str:
    """Return an owner's full name; HubSpot leaves firstName or lastName null for some owners."""
    return f"{owner.get('firstName') or ''} {owner.get('lastName') or ''}".strip()


def _search_filter(search_filter: Dict[str, Any]) -> Dict[str, Any]:
    """Return a search filter with its values in HubSpot's string form."""
    normalized = {"propertyName": search_filter["propertyName"], "operator": search_filter["operator"]}
    for field in ("value", "highValue"):
        if field in search_filter:
            normalized[field] = _property_value(search_filter[field])
    if "values" in search_filter:
        normalized["values"] = [_property_value(value) for value in search_filter["values"]]
    return normalized


def _search_filter_groups(inputs: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Return search_crm_objects' filter groups, raising ValueError for ones HubSpot would reject."""
    if inputs.get("filters") and inputs.get("filter_groups"):
        raise ValueError("Give filters or filter_groups, not both")
    if inputs.get("filters"):
        groups = [inputs["filters"]]
    else:
        groups = [group["filters"] for group in inputs.get("filter_groups", [])]
    groups = [[_search_filter(search_filter) for search_filter in group] for group in groups]

    associated_with = inputs.get("associated_with")
    if associated_with:
        # Every group needs the link filter, since a record matching any group is returned
        link_filter = {
            "propertyName": f"associations.{ASSOCIATION_FILTER_TYPES[associated_with['object_type']]}",
            "operator": "EQ",
            "value": str(associated_with["id"]),
        }
        groups = [[link_filter, *group] for group in groups] or [[link_filter]]

    if len(groups) > MAX_SEARCH_FILTER_GROUPS:
        raise ValueError(f"HubSpot allows at most {MAX_SEARCH_FILTER_GROUPS} filter groups; {len(groups)} were given")
    for group in groups:
        if len(group) > MAX_SEARCH_FILTERS_PER_GROUP:
            raise ValueError(
                f"HubSpot allows at most {MAX_SEARCH_FILTERS_PER_GROUP} filters in a group; one has {len(group)}"
            )
    filter_count = sum(len(group) for group in groups)
    if filter_count > MAX_SEARCH_FILTERS:
        raise ValueError(f"HubSpot allows at most {MAX_SEARCH_FILTERS} filters in a search; {filter_count} were given")
    return [{"filters": group} for group in groups]


def _record_page_type_id(object_type: str) -> str | None:
    """Return the type ID in a record's HubSpot page URL, or None for types without record pages."""
    if re.fullmatch(r"2-[0-9]+", object_type) or object_type in RECORD_PAGE_TYPE_IDS.values():
        return object_type
    return RECORD_PAGE_TYPE_IDS.get(object_type.lower())


async def _add_record_urls(
    context: ExecutionContext, object_type: str, records: list[Dict[str, Any]], retry_sleep_budget: Dict[str, int]
) -> None:
    """Make sure each record has its HubSpot page as "url", when the object type has record pages.

    The 2026-09 API can return url itself; it's only built, from the account's domain and ID, when missing.
    """
    missing = [record for record in records if not record.get("url")]
    type_id = _record_page_type_id(object_type)
    if type_id is None or not missing:
        return
    response = await fetch_with_rate_limit_retries(
        context,
        ACCOUNT_DETAILS_API_URL,
        retry_sleep_budget=retry_sleep_budget,
        headers={"Content-Type": "application/json"},
    )
    account = await parse_response(response)
    # EU-hosted accounts use app-eu1.hubspot.com
    base_url = f"https://{account.get('uiDomain') or 'app.hubspot.com'}/contacts/{account['portalId']}/record/{type_id}"
    for record in missing:
        record["url"] = f"{base_url}/{record['id']}"


@hubspot.action("search_crm_objects")
class SearchCrmObjectsHandler(ActionHandler):
    """Search any CRM object type with HubSpot's filters, text query, sort and paging"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        object_type = inputs["object_type"]
        try:
            filter_groups = _search_filter_groups(inputs)
        except ValueError as e:
            return ActionError(message=str(e))

        payload: Dict[str, Any] = {"limit": inputs.get("limit", 100)}
        if filter_groups:
            payload["filterGroups"] = filter_groups
        if inputs.get("query"):
            payload["query"] = inputs["query"]
        if inputs.get("properties"):
            payload["properties"] = inputs["properties"]
        if inputs.get("sort_property"):
            payload["sorts"] = [
                {"propertyName": inputs["sort_property"], "direction": inputs.get("sort_direction", "ASCENDING")}
            ]
        if inputs.get("after"):
            payload["after"] = inputs["after"]

        retry_sleep_budget = {"remaining": 10}
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{OBJECTS_API_URL}/{object_type}/search",
                retry_sleep_budget=retry_sleep_budget,
                method="POST",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            data = await parse_response(response)
            results = data.get("results", [])
            if inputs.get("include_urls"):
                await _add_record_urls(context, object_type, results, retry_sleep_budget)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to search {object_type}: {_error_text(e)}")

        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        return ActionResult(
            data={
                "results": results,
                "count": len(results),
                "total": data.get("total", len(results)),
                "has_more": after is not None,
                "after": after,
            },
            cost_usd=None,
        )


@hubspot.action("get_crm_objects")
class GetCrmObjectsHandler(ActionHandler):
    """Read up to 100 records of any CRM object type by ID or unique property, with optional linked records"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        object_type = inputs["object_type"]
        ids = [str(object_id) for object_id in inputs["ids"]]
        payload: Dict[str, Any] = {
            "inputs": [{"id": object_id} for object_id in ids],
            "properties": list(inputs.get("properties", [])),
            "propertiesWithHistory": [],
        }
        if inputs.get("id_property"):
            payload["idProperty"] = inputs["id_property"]
            if payload["properties"] and inputs["id_property"] not in payload["properties"]:
                payload["properties"].append(inputs["id_property"])

        retry_sleep_budget = {"remaining": 10}
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{OBJECTS_API_URL}/{object_type}/batch/read",
                retry_sleep_budget=retry_sleep_budget,
                method="POST",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            data = await parse_response(response) or {}
        except HTTPError as e:
            if e.status != 404:
                return ActionError(message=f"Failed to read {object_type}: {_error_text(e)}")
            # HubSpot answers 404 when none of the IDs match a record
            data = {"results": [], "errors": [{"category": "OBJECT_NOT_FOUND", "context": {"ids": ids}}]}
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to read {object_type}: {_error_text(e)}")

        reason = _unfinished_batch_reason(data)
        if reason:
            return ActionError(message=f"HubSpot {reason} the {object_type} lookup")
        results = data.get("results", [])
        not_found, errors = [], []
        for error in data.get("errors", []):
            if error.get("category") == "OBJECT_NOT_FOUND":
                not_found.extend(str(object_id) for object_id in (error.get("context") or {}).get("ids") or [])
            else:
                errors.append(error.get("message") or error.get("category"))

        try:
            record_ids = [str(record["id"]) for record in results]
            for to_type in inputs.get("associations", []) if results else []:
                links, has_more = await _read_associations(
                    context, object_type, to_type, record_ids, retry_sleep_budget, MAX_LINKS_PER_RECORD
                )
                for record in results:
                    record.setdefault("associations", {})[to_type] = links.get(str(record["id"]), [])
                    if str(record["id"]) in has_more:
                        record.setdefault("associations_with_more", []).append(to_type)
            if inputs.get("include_urls"):
                await _add_record_urls(context, object_type, results, retry_sleep_budget)
        except (*REQUEST_ERRORS, ValueError) as e:
            return ActionError(message=f"Read {len(results)} {object_type} but not their links: {_error_text(e)}")

        output = {"results": results, "total": len(results), "not_found": not_found}
        if errors:
            output["errors"] = errors
        return ActionResult(data=output, cost_usd=None)


@hubspot.action("get_object_properties")
class GetObjectPropertiesHandler(ActionHandler):
    """List the properties of any CRM object type, optionally only those whose name or label matches"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        object_type = inputs["object_type"]
        query = (inputs.get("query") or "").casefold()
        include_details = inputs.get("include_details", False)
        try:
            response = await fetch_with_rate_limit_retries(
                context, f"{PROPERTIES_API_URL}/{object_type}", headers={"Content-Type": "application/json"}
            )
            results = (await parse_response(response)).get("results", [])
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to list {object_type} properties: {_error_text(e)}")

        if query:
            results = [
                prop
                for prop in results
                if query in (prop.get("name") or "").casefold() or query in (prop.get("label") or "").casefold()
            ]
        pipelines = None
        pipeline_fields = {"deals": ("pipeline", "dealstage"), "tickets": ("hs_pipeline", "hs_pipeline_stage")}
        fields = pipeline_fields.get(object_type)
        if (
            include_details
            and fields
            and any(
                prop.get("externalOptions") and prop.get("name") in fields and not prop.get("options")
                for prop in results
            )
        ):
            try:
                response = await fetch_with_rate_limit_retries(
                    context, f"https://api.hubapi.com/crm/pipelines/2026-09/{object_type}"
                )
                pipelines = (await parse_response(response)).get("results", [])
            except REQUEST_ERRORS as e:
                return ActionError(message=f"Failed to read {object_type} pipeline options: {_error_text(e)}")
        properties = []
        for prop in results:
            summary = {"name": prop.get("name"), "label": prop.get("label"), "type": prop.get("type")}
            if include_details:
                summary.update(
                    {
                        "fieldType": prop.get("fieldType"),
                        "groupName": prop.get("groupName"),
                        "description": prop.get("description"),
                        "hubspotDefined": prop.get("hubspotDefined", False),
                        # The value is what filters and updates use; the label is what HubSpot shows
                        "options": [
                            {"label": option.get("label"), "value": option.get("value")}
                            for option in prop.get("options") or []
                        ],
                    }
                )
            if pipelines is not None and prop.get("externalOptions") and not prop.get("options"):
                if prop.get("name") == fields[0]:
                    summary["options"] = [{"label": row["label"], "value": row["id"]} for row in pipelines]
                elif prop.get("name") == fields[1]:
                    summary["options"] = [
                        {"label": stage["label"], "value": stage["id"], "pipeline_id": row["id"]}
                        for row in pipelines
                        for stage in row.get("stages", [])
                    ]
            properties.append(summary)

        return ActionResult(data={"properties": properties, "total": len(properties)}, cost_usd=None)


@hubspot.action("search_owners")
class SearchOwnersHandler(ActionHandler):
    """Find HubSpot owners (users who can own records) by email or name, or list them all"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        email = inputs.get("email")
        name = (inputs.get("name") or "").casefold()
        try:
            owners, complete = await _list_owners(context, {"remaining": 10}, email=email)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to list owners: {_error_text(e)}")

        if name:
            owners = [owner for owner in owners if name in _owner_name(owner).casefold()]
        return ActionResult(
            data={
                "owners": [
                    {
                        "id": owner.get("id"),
                        "email": owner.get("email"),
                        "firstName": owner.get("firstName"),
                        "lastName": owner.get("lastName"),
                        "userId": owner.get("userId"),
                        "teams": owner.get("teams", []),
                    }
                    for owner in owners
                ],
                "total": len(owners),
                # A portal with more owners than were read may have other matches
                "complete": complete,
            },
            cost_usd=None,
        )


@hubspot.action("get_account_details")
class GetAccountDetailsHandler(ActionHandler):
    """Return the connected HubSpot account's ID, time zone, currency and app domain"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await fetch_with_rate_limit_retries(
                context, ACCOUNT_DETAILS_API_URL, headers={"Content-Type": "application/json"}
            )
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to read account details: {_error_text(e)}")
        return ActionResult(data={"account": await parse_response(response)}, cost_usd=None)


# ==================== Marketing Emails ====================


@hubspot.action("get_marketing_emails")
class GetMarketingEmailsHandler(ActionHandler):
    """
    Retrieve a list of marketing emails with optional filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        limit = inputs.get("limit", 50)
        after = inputs.get("after")
        archived = inputs.get("archived", False)

        url = "https://api.hubapi.com/marketing/v3/emails"
        params = {"limit": min(limit, 100), "archived": str(archived).lower()}

        if after:
            params["after"] = after
        if inputs.get("is_published") is not None:
            params["isPublished"] = str(inputs["is_published"]).lower()

        response = await fetch_with_rate_limit_retries(context, url, params=params)
        data = await parse_response(response)

        emails = []
        for email in data.get("results", []):
            emails.append(
                {
                    "id": email.get("id"),
                    "name": email.get("name"),
                    "subject": email.get("subject"),
                    "type": email.get("type"),
                    "state": email.get("state"),
                    "created_at": email.get("createdAt"),
                    "updated_at": email.get("updatedAt"),
                }
            )

        result = {"emails": emails, "total": len(emails)}

        if data.get("paging"):
            result["paging"] = data.get("paging")

        return ActionResult(data=result, cost_usd=None)


# ==================== Campaigns ====================


@hubspot.action("get_campaigns")
class GetCampaignsHandler(ActionHandler):
    """
    Retrieve a list of marketing campaigns using HubSpot v3 Campaigns API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        limit = inputs.get("limit", 50)
        after = inputs.get("after")
        name_filter = inputs.get("name")
        sort = inputs.get("sort", "-updatedAt")

        url = "https://api.hubapi.com/marketing/v3/campaigns"
        params = {
            "limit": min(limit, 100),
            "properties": "hs_name,hs_start_date,hs_end_date,hs_campaign_status,hs_notes,hs_owner",
            "sort": sort,
        }

        if after:
            params["after"] = after

        if name_filter:
            params["name"] = name_filter

        response = await fetch_with_rate_limit_retries(context, url, params=params)
        data = await parse_response(response)

        campaigns = []
        for campaign in data.get("results", []):
            properties = campaign.get("properties", {})
            campaigns.append(
                {
                    "id": campaign.get("id"),
                    "name": properties.get("hs_name"),
                    "start_date": properties.get("hs_start_date"),
                    "end_date": properties.get("hs_end_date"),
                    "status": properties.get("hs_campaign_status"),
                    "notes": properties.get("hs_notes"),
                    "owner": properties.get("hs_owner"),
                    "created_at": campaign.get("createdAt"),
                    "updated_at": campaign.get("updatedAt"),
                }
            )

        result = {
            "campaigns": campaigns,
            "total": data.get("total", len(campaigns)),
        }

        if data.get("paging"):
            result["paging"] = data.get("paging")

        return ActionResult(data=result, cost_usd=None)


@hubspot.action("get_campaign")
class GetCampaignHandler(ActionHandler):
    """
    Retrieve a specific marketing campaign by ID with full details using HubSpot v3 Campaigns API.
    Optionally include asset metrics by providing date range.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        campaign_id = inputs["campaign_id"]
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")

        # Build properties list for detailed campaign info
        properties = (
            "hs_name,hs_start_date,hs_end_date,hs_campaign_status,hs_notes,hs_owner,"
            "hs_audience,hs_currency_code,hs_utm,hs_color_hex,hs_budget_items_sum_amount,hs_spend_items_sum_amount"
        )

        url = f"https://api.hubapi.com/marketing/v3/campaigns/{campaign_id}"
        params = {"properties": properties}

        # Add date range for metrics if provided
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await fetch_with_rate_limit_retries(context, url, params=params)
        data = await parse_response(response)

        properties_data = data.get("properties", {})

        campaign = {
            "id": data.get("id"),
            "name": properties_data.get("hs_name"),
            "start_date": properties_data.get("hs_start_date"),
            "end_date": properties_data.get("hs_end_date"),
            "status": properties_data.get("hs_campaign_status"),
            "notes": properties_data.get("hs_notes"),
            "owner": properties_data.get("hs_owner"),
            "audience": properties_data.get("hs_audience"),
            "currency_code": properties_data.get("hs_currency_code"),
            "utm": properties_data.get("hs_utm"),
            "color_hex": properties_data.get("hs_color_hex"),
            "budget_total": properties_data.get("hs_budget_items_sum_amount"),
            "spend_total": properties_data.get("hs_spend_items_sum_amount"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
            "assets": data.get("assets", {}),
        }

        return ActionResult(data={"campaign": campaign}, cost_usd=None)


@hubspot.action("get_campaign_assets")
class GetCampaignAssetsHandler(ActionHandler):
    """
    Retrieve campaign assets (landing pages, emails, forms, etc.) with performance metrics.
    Uses HubSpot v3 Campaigns API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        campaign_id = inputs["campaign_id"]
        asset_type = inputs["asset_type"]
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")
        limit = inputs.get("limit", 50)
        after = inputs.get("after")

        url = f"https://api.hubapi.com/marketing/v3/campaigns/{campaign_id}/assets/{asset_type}"
        params = {"limit": min(limit, 100)}

        # Add date range for metrics
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if after:
            params["after"] = after

        response = await fetch_with_rate_limit_retries(context, url, params=params)
        data = await parse_response(response)

        assets = []
        for asset in data.get("results", []):
            asset_data = {
                "id": asset.get("id"),
                "name": asset.get("name"),
                "metrics": asset.get("metrics", {}),
            }
            assets.append(asset_data)

        result = {
            "campaign_id": campaign_id,
            "asset_type": asset_type,
            "assets": assets,
            "total": len(assets),
        }

        if data.get("paging"):
            result["paging"] = data.get("paging")

        return ActionResult(data=result, cost_usd=None)


@hubspot.action("get_campaign_performance")
class GetCampaignPerformanceHandler(ActionHandler):
    """
    Retrieve comprehensive campaign performance metrics across all asset types.
    Aggregates data from landing pages, emails, forms, and blog posts.
    Properly paginates through all assets to ensure complete metrics.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        campaign_id = inputs["campaign_id"]
        start_date = inputs.get("start_date")
        end_date = inputs.get("end_date")

        # Asset types with their available metrics
        asset_types = {
            "LANDING_PAGE": [
                "VIEWS",
                "SUBMISSIONS",
                "CONTACTS_FIRST_TOUCH",
                "CONTACTS_LAST_TOUCH",
                "CUSTOMERS",
            ],
            "MARKETING_EMAIL": ["SENT", "OPEN", "CLICKS"],
            "FORM": ["VIEWS", "SUBMISSIONS", "CONVERSION_RATE"],
            "BLOG_POST": [
                "VIEWS",
                "SUBMISSIONS",
                "CONTACTS_FIRST_TOUCH",
                "CONTACTS_LAST_TOUCH",
            ],
        }

        # Map asset type to response key
        key_map = {
            "LANDING_PAGE": "landing_pages",
            "MARKETING_EMAIL": "marketing_emails",
            "FORM": "forms",
            "BLOG_POST": "blog_posts",
        }

        performance = {
            "campaign_id": campaign_id,
            "date_range": {"start_date": start_date, "end_date": end_date},
            "assets": {
                "landing_pages": {"assets": [], "totals": {}},
                "marketing_emails": {"assets": [], "totals": {}},
                "forms": {"assets": [], "totals": {}},
                "blog_posts": {"assets": [], "totals": {}},
            },
        }
        retry_sleep_budget = {"remaining": 10}

        # Fetch each asset type with pagination
        for asset_type, metrics in asset_types.items():
            base_url = f"https://api.hubapi.com/marketing/v3/campaigns/{campaign_id}/assets/{asset_type}"

            try:
                assets_list = []
                totals = {metric.lower(): 0 for metric in metrics}
                after = None
                max_pages = 10  # Safety limit to prevent infinite loops

                for page in range(max_pages):
                    params = {"limit": 100}

                    if start_date:
                        params["startDate"] = start_date
                    if end_date:
                        params["endDate"] = end_date
                    if after:
                        params["after"] = after

                    response = await fetch_with_rate_limit_retries(
                        context,
                        base_url,
                        retry_sleep_budget=retry_sleep_budget,
                        params=params,
                    )
                    data = await parse_response(response)

                    for asset in data.get("results", []):
                        asset_metrics = asset.get("metrics", {})
                        assets_list.append(
                            {
                                "id": asset.get("id"),
                                "name": asset.get("name"),
                                "metrics": asset_metrics,
                            }
                        )

                        # Aggregate metrics
                        for metric in metrics:
                            metric_lower = metric.lower()
                            value = asset_metrics.get(metric, 0)
                            if value and isinstance(value, (int, float)):
                                totals[metric_lower] += value

                    # Check for more pages
                    paging = data.get("paging", {})
                    next_page = paging.get("next", {})
                    after = next_page.get("after")

                    if not after:
                        break  # No more pages

                performance["assets"][key_map[asset_type]] = {
                    "assets": assets_list,
                    "count": len(assets_list),
                    "totals": totals,
                }

            except Exception as e:
                # If asset type has no data or errors, continue
                performance["assets"][key_map[asset_type]] = {
                    "assets": [],
                    "count": 0,
                    "totals": {},
                    "error": str(e),
                }

        # Calculate summary
        performance["summary"] = {
            "total_landing_page_views": performance["assets"]["landing_pages"]["totals"].get("views", 0),
            "total_landing_page_submissions": performance["assets"]["landing_pages"]["totals"].get("submissions", 0),
            "total_landing_page_contacts": performance["assets"]["landing_pages"]["totals"].get(
                "contacts_first_touch", 0
            ),
            "total_emails_sent": performance["assets"]["marketing_emails"]["totals"].get("sent", 0),
            "total_email_opens": performance["assets"]["marketing_emails"]["totals"].get("open", 0),
            "total_email_clicks": performance["assets"]["marketing_emails"]["totals"].get("clicks", 0),
            "total_form_submissions": performance["assets"]["forms"]["totals"].get("submissions", 0),
            "total_blog_views": performance["assets"]["blog_posts"]["totals"].get("views", 0),
        }

        return ActionResult(data=performance, cost_usd=None)


@hubspot.action("get_call_transcript")
class GetCallTranscriptActionHandler(ActionHandler):
    """
    Action handler to retrieve structured transcript utterances for a HubSpot call.

    Fetches the full transcript from the HubSpot Calling Transcripts API, returning
    each utterance with its speaker ID and timestamp. Use this when you need the
    structured speaker/timestamp breakdown rather than the plain-text hs_call_body
    property on the call record.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        transcript_id = inputs["transcript_id"]

        try:
            url = f"https://api.hubapi.com/crm/extensions/calling/2026-03/transcripts/{transcript_id}"
            response = await fetch_with_rate_limit_retries(context, url, method="GET")
            result = await parse_response(response)

            utterances = result.get("transcriptUtterances", [])

            return ActionResult(
                data={
                    "transcript_id": transcript_id,
                    "utterances": utterances,
                    "total_utterances": len(utterances),
                },
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(message=f"Failed to retrieve transcript for {transcript_id}: {str(e)}")


@hubspot.action("get_current_user")
class GetCurrentUserHandler(ActionHandler):
    """Resolve the user who authorized the shared connection, using platform-provided metadata."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        metadata = context.metadata
        email = metadata.get("connected_user")
        if not isinstance(email, str) or not email.strip():
            return ActionError(
                message="Connected-user identity is unavailable. Reconnect HubSpot, "
                "or use Search Owners with your email."
            )
        try:
            owners, complete = await _list_owners(context, {"remaining": 10}, email=email)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to resolve the connected user's owner: {_error_text(e)}")
        owners = [owner for owner in owners if (owner.get("email") or "").casefold() == email.casefold()]
        if not complete or len(owners) > 1:
            return ActionError(message="Could not uniquely resolve the connected user's owner")
        return ActionResult(
            data={"email": email, "owner": owners[0] if owners else None, "portal_id": metadata.get("hub_id")},
            cost_usd=None,
        )


@hubspot.action("get_object_schemas")
class GetObjectSchemasHandler(ActionHandler):
    """Discover custom object type IDs and their schemas."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await fetch_with_rate_limit_retries(
                context, "https://api.hubapi.com/crm-object-schemas/2026-09/schemas"
            )
            data = await parse_response(response)
        except REQUEST_ERRORS as e:
            return ActionError(
                message=f"Failed to list custom object schemas (requires crm.schemas.custom.read): {_error_text(e)}"
            )
        return ActionResult(data={"schemas": data.get("results", [])}, cost_usd=None)


@hubspot.action("create_ticket")
class CreateTicketHandler(ActionHandler):
    """Create a support ticket with a subject, pipeline stage and optional properties."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        properties = {
            **inputs.get("properties", {}),
            "subject": inputs["subject"],
            "hs_pipeline_stage": inputs["hs_pipeline_stage"],
        }
        if inputs.get("hs_pipeline"):
            properties["hs_pipeline"] = inputs["hs_pipeline"]
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{OBJECTS_API_URL}/tickets",
                method="POST",
                json={"properties": properties},
                headers={"Content-Type": "application/json"},
                resend_on_connection_error=False,
            )
            ticket = await parse_response(response)
        except REQUEST_ERRORS as e:
            if _outcome_unknown(e):
                return ActionError(
                    message="Ticket creation outcome is unknown. Check HubSpot before retrying to avoid duplicates."
                )
            return ActionError(message=f"Failed to create ticket: {_error_text(e)}")
        return ActionResult(data={"ticket": ticket}, cost_usd=None)


@hubspot.action("update_ticket")
class UpdateTicketHandler(ActionHandler):
    """Update only the supplied ticket properties; an empty string clears a property."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await fetch_with_rate_limit_retries(
                context,
                f"{OBJECTS_API_URL}/tickets/{inputs['ticket_id']}",
                method="PATCH",
                json={"properties": inputs["properties"]},
                headers={"Content-Type": "application/json"},
            )
            ticket = await parse_response(response)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to update ticket: {_error_text(e)}")
        return ActionResult(data={"ticket": ticket}, cost_usd=None)


@hubspot.action("search_conversations")
class SearchConversationsHandler(ActionHandler):
    """Retrieve a page of inbox threads with HubSpot's native filters."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        params = {"limit": inputs.get("limit", 100), "sort": "id", "association": "TICKET"}
        filters = {
            "after": inputs.get("after"),
            "inboxId": inputs.get("inbox_id"),
            "associatedContactId": inputs.get("contact_id"),
            "associatedTicketId": inputs.get("ticket_id"),
            "threadStatus": inputs.get("status"),
        }
        params.update({key: value for key, value in filters.items() if value})
        if "archived" in inputs:
            params["archived"] = "true" if inputs.get("archived") else "false"
        try:
            response = await fetch_with_rate_limit_retries(
                context, "https://api.hubapi.com/conversations/v3/conversations/threads", params=params
            )
            data = await parse_response(response)
        except REQUEST_ERRORS as e:
            return ActionError(message=f"Failed to search conversations: {_error_text(e)}")
        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        return ActionResult(
            data={
                "results": data.get("results", []),
                "paging": data.get("paging", {}),
                "has_more": after is not None,
                "after": str(after) if after is not None else None,
            },
            cost_usd=None,
        )
