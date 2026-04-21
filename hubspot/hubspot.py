"""HubSpot Integration Actions Module"""

from typing import Dict, Any
from datetime import datetime, timezone
import asyncio

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
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


# Contact Management Actions


@hubspot.action("get_contact")
class GetContactActionHandler(ActionHandler):
    """
    Action handler to retrieve a HubSpot contact by email.

    Fetches the contact profile using v3 API.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the get_contact action.

        :param inputs: Dictionary with key "email" and optional "properties".
        :param context: Execution context containing authentication and fetch method.
        :return: Dictionary with contact information.
        """
        email = inputs["email"]
        properties = inputs.get(
            "properties",
            ["email", "firstname", "lastname", "phone", "company", "jobtitle"],
        )

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

        search_response = await context.fetch(
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

            response = await context.fetch(
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

            return ActionResult(
                data={
                    "contact_id": contact_id,
                    "notes": notes,
                    "total": len(notes),
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
        properties = {"hs_note_body": note_body}

        # Add timestamp if provided
        if timestamp:
            properties["hs_timestamp"] = str(timestamp)

        # Build associations array
        associations = []

        # Associate with contact
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

        # Associate with company
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

        # Associate with deal
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

            response = await context.fetch(
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


@hubspot.action("get_contact_emails")
class GetContactEmailsActionHandler(ActionHandler):
    """
    Action handler to retrieve recent email conversations for a HubSpot contact.

    Fetches associated email communications for a specific contact using v4 associations API.
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
            # Get associated emails using v4 associations API
            associations_url = f"https://api.hubapi.com/crm/v4/objects/contacts/{contact_id}/associations/emails"
            associations_response = await context.fetch(associations_url, headers={"Content-Type": "application/json"})
            associations_data = await parse_response(associations_response)

            recent_emails = []
            email_count = 0

            # Get email details for each associated email (limited by email_limit)
            for association in associations_data.get("results", []):
                if email_count >= email_limit:
                    break

                email_id = association["toObjectId"]
                email_url = f"https://api.hubapi.com/crm/v3/objects/emails/{email_id}"
                properties_param = (
                    "hs_email_subject,hs_email_text,hs_timestamp,"
                    "hs_email_direction,hs_email_status,hs_email_from_email,hs_email_to_email"
                )

                try:
                    email_response = await context.fetch(
                        f"{email_url}?properties={properties_param}",
                        headers={"Content-Type": "application/json"},
                    )
                    email_data = await parse_response(email_response)

                    # Convert timestamp to UTC string
                    if (
                        "properties" in email_data
                        and "hs_timestamp" in email_data["properties"]
                        and email_data["properties"]["hs_timestamp"]
                    ):
                        email_data["properties"]["hs_timestamp"] = convert_hubspot_timestamp_to_utc_string(
                            email_data["properties"]["hs_timestamp"]
                        )

                    recent_emails.append(email_data)
                    email_count += 1
                except Exception:  # nosec B112
                    # Skip emails that can't be retrieved
                    continue

            # Sort emails by timestamp (most recent first)
            recent_emails.sort(
                key=lambda x: x.get("properties", {}).get("hs_timestamp", ""),
                reverse=True,
            )

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

        except Exception as e:
            return ActionError(message=f"Failed to retrieve emails: {str(e)}")


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

        url = "https://api.hubapi.com/contacts/v1/contact"

        # Merge properties and additional_properties
        properties = inputs.get("properties", {}).copy()
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
        properties = inputs.get("properties", {}).copy()
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

        query = inputs.get("query", "")
        limit = inputs.get("limit", 100)
        after = inputs.get("after")

        url = "https://api.hubapi.com/crm/v3/objects/contacts/search"

        payload = {"query": query, "limit": limit}

        # Add pagination cursor if provided
        if after:
            payload["after"] = after

        response = await context.fetch(
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

        payload = {"recordIds": [contact_id]}
        response = await context.fetch(
            url,
            method="PUT",
            json=payload,
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

        count = inputs.get("count", 100)
        url = f"https://api.hubapi.com/crm/v3/objects/contacts?limit={count}&sort=createdat"

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
        recent_contacts = await parse_response(response)
        return ActionResult(data={"recent_contacts": recent_contacts}, cost_usd=None)


# Ticket Management Actions


async def get_thread_id_from_ticket(ticket_id: str, context: ExecutionContext) -> str:
    """
    Retrieve the conversation thread ID for a given ticket.

    Fetches the ticket details from HubSpot and extracts the conversation thread ID.

    :param ticket_id: The ID of the ticket.
    :param context: Execution context with fetch utility.
    :return: The conversation thread ID or None if not found.
    """
    ticket_url = (
        f"https://api.hubapi.com/crm/v3/objects/tickets/{ticket_id}?properties=hs_conversations_originating_thread_id"
    )
    ticket_response = await context.fetch(ticket_url, headers={"Content-Type": "application/json"})
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

        url = "https://api.hubapi.com/crm/v3/objects/tickets/search"

        properties = [
            "subject",
            "content",
            "hs_pipeline_stage",
            "hs_ticket_priority",
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

        response = await context.fetch(
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
                    "result": {
                        "success": False,
                        "message": f"No conversation thread found for ticket {ticket_id}",
                    }
                },
                cost_usd=None,
            )

        try:
            conversation_url = f"https://api.hubapi.com/conversations/v3/conversations/threads/{thread_id}/messages"
            conversation_response = await context.fetch(conversation_url, headers={"Content-Type": "application/json"})
            conversation_data = await parse_response(conversation_response)

            if conversation_data.get("results"):
                for message in conversation_data["results"]:
                    message_content = message.get("text")
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
                        }
                    )
        except Exception:  # nosec B110
            pass

        try:
            sorted_conversation = sorted(conversation_results, key=lambda x: x.get("timestamp", ""))
        except Exception:
            sorted_conversation = conversation_results

        return ActionResult(
            data={
                "conversation": {
                    "results": sorted_conversation,
                    "ticket_id": ticket_id,
                    "thread_id": thread_id,
                }
            },
            cost_usd=None,
        )


@hubspot.action("add_ticket_comment")
class AddTicketCommentActionHandler(ActionHandler):
    """
    Action handler to add a comment to a ticket's conversation thread.

    Retrieves the conversation thread ID from the ticket and posts a comment to that thread.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Execute the add_ticket_comment action.

        :param inputs: Dictionary with keys "ticket_id" and "comment".
        :param context: Execution context containing authentication credentials.
        :return: Dictionary with a "result" key indicating success or failure and the thread message details.
        """

        ticket_id = inputs["ticket_id"]
        comment = inputs["comment"]

        # Get the thread ID from the ticket
        thread_id = await get_thread_id_from_ticket(ticket_id, context)
        if not thread_id:
            return ActionResult(
                data={
                    "result": {
                        "success": False,
                        "message": f"No conversation thread found for ticket {ticket_id}",
                    }
                },
                cost_usd=None,
            )

        messages_url = f"https://api.hubapi.com/conversations/v3/conversations/threads/{thread_id}/messages"

        message_payload = {"type": "COMMENT", "text": comment}

        # Send the comment to the conversation thread
        message_response = await context.fetch(
            messages_url,
            method="POST",
            json=message_payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            message_result = await parse_response(message_response)
            return ActionResult(
                data={
                    "result": {
                        "success": True,
                        "message": "Comment added successfully to the thread",
                        "thread_message": message_result,
                    }
                },
                cost_usd=None,
            )
        except Exception as e:
            return ActionError(
                message=f"Failed to add comment to the thread: {str(e)}",
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

            response = await context.fetch(
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

            return ActionResult(
                data={
                    "company_id": company_id,
                    "notes": notes,
                    "total": len(notes),
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
        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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
        payload = {"properties": inputs.get("properties", {})}

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
        payload = {"properties": inputs.get("properties", {})}

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

        :param inputs: Dictionary with keys "query" (search term) and "limit" (maximum number of results).
        :param context: Execution context containing authentication details.
        :return: Parsed JSON response with the search results.
        """

        query = inputs.get("query", "")
        limit = inputs.get("limit", 100)

        url = "https://api.hubapi.com/crm/v3/objects/companies/search"

        payload = {"query": query, "limit": limit}

        response = await context.fetch(
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

        :param inputs: Dictionary with keys "owner_name" (required), "limit" (optional), and "properties" (optional).
        :param context: Execution context containing authentication details.
        :return: Dictionary with companies associated with the specified owner.
        """

        owner_name = inputs["owner_name"]
        limit = inputs.get("limit", 100)
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
            # Step 1: Get all owners from HubSpot
            owners_url = "https://api.hubapi.com/crm/v3/owners/"
            owners_response = await context.fetch(owners_url, headers={"Content-Type": "application/json"})
            owners_data = await parse_response(owners_response)

            # Step 2: Find the owner ID by matching the name
            owner_id = None
            matched_owner = None

            for owner in owners_data.get("results", []):
                # Check both firstName + lastName combination and full name
                first_name = owner.get("firstName", "")
                last_name = owner.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip()

                # Case-insensitive matching
                if (
                    owner_name.lower() == full_name.lower()
                    or owner_name.lower() == first_name.lower()
                    or owner_name.lower() == last_name.lower()
                ):
                    owner_id = owner.get("id")
                    matched_owner = {
                        "id": owner_id,
                        "firstName": first_name,
                        "lastName": last_name,
                        "email": owner.get("email"),
                    }
                    break

            if not owner_id:
                return ActionError(
                    message=f"Owner with name '{owner_name}' not found",
                )

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

            search_response = await context.fetch(
                search_url,
                method="POST",
                json=search_payload,
                headers={"Content-Type": "application/json"},
            )
            search_result = await parse_response(search_response)

            companies = search_result.get("results", [])

            return ActionResult(
                data={
                    "success": True,
                    "owner": matched_owner,
                    "companies": companies,
                    "total": len(companies),
                    "paging": search_result.get("paging"),
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

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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
                    "hubspotDefined": prop.get("hubspotDefined", True),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names (backward compatible)
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", True))

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

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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
                    "hubspotDefined": prop.get("hubspotDefined", True),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", True))

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

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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
                    "hubspotDefined": prop.get("hubspotDefined", True),
                    "description": prop.get("description"),
                    "options": prop.get("options", []),
                }
                for prop in results
            ]
        else:
            # Return just property names
            properties = [prop.get("name") for prop in results if prop.get("name")]

        custom_count = sum(1 for prop in results if not prop.get("hubspotDefined", True))

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

            response = await context.fetch(
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

            return ActionResult(
                data={"deal_id": deal_id, "notes": notes, "total": len(notes)},
                cost_usd=None,
            )

        except Exception as e:
            return ActionError(
                message=f"Failed to retrieve notes for deal {deal_id}: {str(e)}",
            )


async def fetch_transcript(transcript_id: str, context: ExecutionContext):
    """
    Fetch transcript utterances from the HubSpot Calling Transcripts API.
    Google Meet transcripts are stored here, not on the call object properties.
    Returns None if the transcript cannot be fetched.
    """
    try:
        url = f"https://api.hubapi.com/crm/extensions/calling/2026-03/transcripts/{transcript_id}"
        response = await context.fetch(url, method="GET")
        result = await parse_response(response)
        return result.get("transcriptUtterances", [])
    except Exception:
        return None


async def fetch_calls_with_transcripts(association_filter: dict, limit: int, context: ExecutionContext):
    """
    Fetch calls for a given association filter, then enrich each call that has a transcript
    by fetching the full transcript utterances from the transcripts API.
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
    response = await context.fetch(
        url,
        method="POST",
        json=body,
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

    # Fetch transcripts in parallel for calls that have one.
    # Note: hs_call_transcription_id can be null even when a transcript exists (known HubSpot bug).
    # Fallback: when hs_call_has_transcript is true but hs_call_transcription_id is null,
    # try using the call's own ID as the transcript ID — HubSpot often maps them 1:1.
    transcript_tasks = []
    calls_needing_transcripts = []
    for call in calls:
        props = call.get("properties", {})
        transcript_id = props.get("hs_call_transcription_id")
        has_transcript = props.get("hs_call_has_transcript") == "true"

        if transcript_id:
            transcript_tasks.append(fetch_transcript(transcript_id, context))
            calls_needing_transcripts.append(call)
        elif has_transcript:
            # Fallback for HubSpot bug: try the call ID itself as the transcript ID
            transcript_tasks.append(fetch_transcript(call["id"], context))
            calls_needing_transcripts.append(call)

    if transcript_tasks:
        transcripts = await asyncio.gather(*transcript_tasks)
        for call, utterances in zip(calls_needing_transcripts, transcripts):
            if utterances is not None:
                call["transcript"] = utterances

    return calls


async def fetch_meetings(association_filter: dict, limit: int, context: ExecutionContext):
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
    response = await context.fetch(
        url,
        method="POST",
        json=body,
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

    Fetches calls with transcripts (via the Calling Transcripts API) and meetings
    (metadata only) for a specific contact. Google Meet transcripts are stored on
    call records, not meeting records.
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
            calls, meetings = await asyncio.gather(
                fetch_calls_with_transcripts(association_filter, limit, context),
                fetch_meetings(association_filter, limit, context),
            )

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

    Fetches calls with transcripts (via the Calling Transcripts API) and meetings
    (metadata only) for a specific deal. Google Meet transcripts are stored on
    call records, not meeting records.
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
            calls, meetings = await asyncio.gather(
                fetch_calls_with_transcripts(association_filter, limit, context),
                fetch_meetings(association_filter, limit, context),
            )

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
        has_more = True
        after = inputs.get("after")  # Allow starting from specific pagination token
        total_fetched = 0
        # Respect user's limit parameter even when fetch_all is false
        user_limit = inputs.get("limit", 50)
        max_total = inputs.get("max_total", user_limit if not fetch_all else 100)

        url = "https://api.hubapi.com/crm/v3/objects/deals/search"

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

        while has_more and total_fetched < max_total:
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

            # Build single filter group with AND logic (all filters in one group)
            all_filters = []

            # Pipeline filtering
            if inputs.get("pipeline_id"):
                all_filters.append(
                    {
                        "propertyName": "pipeline",
                        "operator": "EQ",
                        "value": inputs["pipeline_id"],
                    }
                )

            # Year filtering to reduce response size
            if inputs.get("year"):
                try:
                    year = int(inputs["year"])
                    # Create start and end of year in UTC milliseconds
                    start_of_year = datetime(year, 1, 1, tzinfo=timezone.utc)
                    end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

                    start_ms = int(start_of_year.timestamp() * 1000)
                    end_ms = int(end_of_year.timestamp() * 1000)

                    all_filters.extend(
                        [
                            {
                                "propertyName": "closedate",
                                "operator": "GTE",
                                "value": str(start_ms),
                            },
                            {
                                "propertyName": "closedate",
                                "operator": "LTE",
                                "value": str(end_ms),
                            },
                        ]
                    )
                except (ValueError, TypeError):
                    pass  # Invalid year, skip filtering

            # Date range filtering with flexible start and end dates
            if inputs.get("start_date") or inputs.get("end_date"):
                try:
                    date_field = inputs.get("date_field", "hs_lastmodifieddate")

                    # Parse and add start date filter if provided
                    if inputs.get("start_date"):
                        start_date = parse_date_string_to_utc(inputs["start_date"])
                        if start_date:
                            start_ms = int(start_date.timestamp() * 1000)
                            all_filters.append(
                                {
                                    "propertyName": date_field,
                                    "operator": "GTE",
                                    "value": str(start_ms),
                                }
                            )

                    # Parse and add end date filter if provided
                    if inputs.get("end_date"):
                        end_date = parse_date_string_to_utc(inputs["end_date"])
                        if end_date:
                            # Set to end of day (23:59:59) for end date
                            end_date = end_date.replace(hour=23, minute=59, second=59)
                            end_ms = int(end_date.timestamp() * 1000)
                            all_filters.append(
                                {
                                    "propertyName": date_field,
                                    "operator": "LTE",
                                    "value": str(end_ms),
                                }
                            )

                except (ValueError, TypeError):
                    pass  # Invalid date format, skip filtering

            # Create single filter group if any filters exist
            if all_filters:
                request_body["filterGroups"] = [{"filters": all_filters}]

            response = await context.fetch(
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

                # Check for more pages
                paging = result.get("paging")
                if paging and paging.get("next") and paging["next"].get("after"):
                    after = paging["next"]["after"]
                    # Continue if fetch_all is True OR if we haven't reached the user's requested limit
                    has_more = fetch_all or total_fetched < max_total
                else:
                    has_more = False

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
            else:
                has_more = False

        # Convert deal dates from UTC timestamps to readable UTC strings
        for deal in deals:
            convert_deal_dates_to_utc(deal)

        # Prepare clear pagination guidance
        has_more_pages = has_more and total_fetched < max_total
        pagination_instructions = ""
        next_page_params = {}

        if has_more_pages:
            pagination_instructions = (
                f"There are more deals available. You retrieved {total_fetched} deals so far. "
                f"To get the next page, use 'get_deals' with the same parameters plus 'after': '{after}'. "
                "Or set 'fetch_all': true to get all remaining deals automatically. "
                "For rate limiting, add 'delay_between_requests': 1.0."
            )
            next_page_params = {
                "action": "get_deals",
                "parameters": {**inputs, "after": after},
                "alternative": {**inputs, "fetch_all": True},
                "rate_limited_alternative": {
                    **inputs,
                    "fetch_all": True,
                    "delay_between_requests": 1.0,
                },
            }
        elif not has_more:
            pagination_instructions = (
                f"You have retrieved all available deals ({total_fetched} total). No more pages available."
            )
        else:
            pagination_instructions = (
                f"Reached the maximum limit of {max_total} deals. There may be more deals available. "
                "To get more, increase 'max_total' or use specific filters to narrow the search. "
                "For comprehensive fetching with rate limiting, use 'fetch_all': true "
                "and 'delay_between_requests': 1.0."
            )

        # Get deduplication stats if available
        deduplication_stats = getattr(context, "_deduplication_stats", None)

        # Build comprehensive result with deduplication info
        final_result = {
            "results": deals,
            "total": len(deals),
            "pagination": {
                "fetched_all_available": not has_more or total_fetched >= max_total,
                "total_fetched": total_fetched,
                "last_after_token": after,
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

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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

            filter_groups = []

            if inputs.get("pipeline_id"):
                filter_groups.append(
                    {
                        "filters": [
                            {
                                "propertyName": "pipeline",
                                "operator": "EQ",
                                "value": inputs["pipeline_id"],
                            }
                        ]
                    }
                )

            # Year filtering to reduce response size
            if inputs.get("year"):
                try:
                    year = int(inputs["year"])
                    # Create start and end of year in UTC milliseconds
                    start_of_year = datetime(year, 1, 1, tzinfo=timezone.utc)
                    end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

                    start_ms = int(start_of_year.timestamp() * 1000)
                    end_ms = int(end_of_year.timestamp() * 1000)

                    filter_groups.append(
                        {
                            "filters": [
                                {
                                    "propertyName": "closedate",
                                    "operator": "GTE",
                                    "value": str(start_ms),
                                },
                                {
                                    "propertyName": "closedate",
                                    "operator": "LTE",
                                    "value": str(end_ms),
                                },
                            ]
                        }
                    )
                except (ValueError, TypeError):
                    pass  # Invalid year, skip filtering

            # Filter by deal stage
            if inputs.get("deal_stage"):
                filter_groups.append(
                    {
                        "filters": [
                            {
                                "propertyName": "dealstage",
                                "operator": "EQ",
                                "value": inputs["deal_stage"],
                            }
                        ]
                    }
                )

            # Instead, we'll fetch all deals and filter by date in post-processing
            # This is more reliable than HubSpot's buggy date range API filtering

            # Filter by amount range
            if inputs.get("min_amount"):
                filter_groups.append(
                    {
                        "filters": [
                            {
                                "propertyName": "amount",
                                "operator": "GTE",
                                "value": str(inputs["min_amount"]),
                            }
                        ]
                    }
                )

            if inputs.get("max_amount"):
                filter_groups.append(
                    {
                        "filters": [
                            {
                                "propertyName": "amount",
                                "operator": "LTE",
                                "value": str(inputs["max_amount"]),
                            }
                        ]
                    }
                )

            if filter_groups:
                request_body["filterGroups"] = filter_groups

            # Add sorting
            if inputs.get("sort_property"):
                sort_direction = "DESCENDING" if inputs.get("sort_direction", "DESC") == "DESC" else "ASCENDING"
                request_body["sorts"] = [
                    {
                        "propertyName": inputs["sort_property"],
                        "direction": sort_direction,
                    }
                ]

            response = await context.fetch(
                url,
                method="POST",
                json=request_body,
                headers={"Content-Type": "application/json"},
            )

            result = await parse_response(response)

            if result and result.get("results"):
                page_deals = result["results"]

                # This bypasses HubSpot's buggy date range API filtering
                if inputs.get("close_date_start") or inputs.get("close_date_end"):
                    filtered_deals = []
                    start_date_obj = (
                        parse_date_string_to_utc(inputs["close_date_start"]) if inputs.get("close_date_start") else None
                    )
                    end_date_obj = (
                        parse_date_string_to_utc(inputs["close_date_end"]) if inputs.get("close_date_end") else None
                    )

                    for deal in page_deals:
                        closedate_str = deal.get("properties", {}).get("closedate")
                        if closedate_str:
                            try:
                                if isinstance(closedate_str, str) and closedate_str.endswith("Z"):
                                    closedate_obj = datetime.fromisoformat(
                                        closedate_str.replace("Z", "+00:00")
                                    ).replace(tzinfo=None)
                                else:
                                    closedate_obj = datetime.fromtimestamp(
                                        int(closedate_str) / 1000,
                                        tz=timezone.utc,
                                    ).replace(tzinfo=None)

                                # Apply precise date filtering
                                include_deal = True
                                if start_date_obj and closedate_obj < start_date_obj:
                                    include_deal = False
                                if end_date_obj and closedate_obj > end_date_obj:
                                    include_deal = False

                                if include_deal:
                                    filtered_deals.append(deal)
                            except (ValueError, TypeError):
                                # Include deals with invalid dates to avoid data loss
                                filtered_deals.append(deal)
                        else:
                            # Include deals without close dates - only include if no date filtering requested
                            if not start_date_obj and not end_date_obj:
                                filtered_deals.append(deal)

                    page_deals = filtered_deals

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
                    after = paging["next"]["after"]
                    # Continue if fetch_all is True OR if we haven't reached the user's requested limit
                    has_more = fetch_all or total_fetched < max_total
                else:
                    has_more = False
            else:
                has_more = False

        # Convert deal dates from UTC timestamps to readable UTC strings
        for deal in deals:
            convert_deal_dates_to_utc(deal)

        return ActionResult(data={"results": deals, "total": len(deals)}, cost_usd=None)


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

        payload = {"properties": inputs.get("properties", {})}

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

        payload = {"properties": inputs.get("properties", {})}

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

        response = await context.fetch(
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

        response = await context.fetch(url, headers={"Content-Type": "application/json"})
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

        # Note: includeFilters is not supported in search endpoint
        # We'll get filters in individual list calls if needed

        response = await context.fetch(
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

        response = await context.fetch(url, params=params)
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

        response = await context.fetch(
            url,
            method="POST",
            json=search_body,
            headers={"Content-Type": "application/json"},
        )

        data = await parse_response(response)
        results = data.get("lists", [])

        return ActionResult(
            data={
                "results": results,
                "total": len(results),
                "has_more": len(results) == inputs.get("count", 20),
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

        while total_retrieved < limit:
            params = {"limit": min(batch_size, limit - total_retrieved)}
            if after_token:
                params["after"] = after_token

            try:
                response = await context.fetch(url, params=params)
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

            except Exception as e:
                if "rate limit" in str(e).lower() or "429" in str(e):
                    # Basic retry with exponential backoff
                    await asyncio.sleep(2)
                    continue
                raise e

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
    """Retrieve all associated objects for a contact using v4 Associations API"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        contact_id = inputs["contact_id"]
        association_types = inputs.get("association_types", ["companies", "deals", "meetings"])
        limit = inputs.get("limit", 100)

        associations = {}
        total_count = 0
        summary = {}

        # Fetch associations for each type in parallel
        for assoc_type in association_types:
            try:
                url = f"https://api.hubapi.com/crm/v4/objects/contacts/{contact_id}/associations/{assoc_type}"
                params = {"limit": limit}

                response = await context.fetch(url, params=params)
                data = await parse_response(response)

                results = data.get("results", [])
                associations[assoc_type] = results
                total_count += len(results)
                summary[f"{assoc_type}_count"] = len(results)

            except Exception:
                # If association type doesn't exist or fails, continue with empty list
                associations[assoc_type] = []
                summary[f"{assoc_type}_count"] = 0

        return ActionResult(
            data={
                "contact_id": contact_id,
                "associations": associations,
                "total_associations": total_count,
                "summary": summary,
            },
            cost_usd=None,
        )


@hubspot.action("get_company_associations")
class GetCompanyAssociationsHandler(ActionHandler):
    """Retrieve all associated objects for a company using v4 Associations API"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        company_id = inputs["company_id"]
        association_types = inputs.get("association_types", ["contacts", "deals", "tickets"])
        limit = inputs.get("limit", 100)

        associations = {}
        total_count = 0
        summary = {}

        # Fetch associations for each type
        for assoc_type in association_types:
            try:
                url = f"https://api.hubapi.com/crm/v4/objects/companies/{company_id}/associations/{assoc_type}"
                params = {"limit": limit}

                response = await context.fetch(url, params=params)
                data = await parse_response(response)

                results = data.get("results", [])
                associations[assoc_type] = results
                total_count += len(results)
                summary[f"{assoc_type}_count"] = len(results)

            except Exception:
                # If association type doesn't exist or fails, continue with empty list
                associations[assoc_type] = []
                summary[f"{assoc_type}_count"] = 0

        return ActionResult(
            data={
                "company_id": company_id,
                "associations": associations,
                "total_associations": total_count,
                "summary": summary,
            },
            cost_usd=None,
        )


@hubspot.action("get_deal_associations")
class GetDealAssociationsHandler(ActionHandler):
    """Retrieve all associated objects for a deal using v4 Associations API"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        deal_id = inputs["deal_id"]
        association_types = inputs.get("association_types", ["contacts", "companies"])
        limit = inputs.get("limit", 100)

        associations = {}
        total_count = 0
        summary = {}

        # Fetch associations for each type
        for assoc_type in association_types:
            try:
                url = f"https://api.hubapi.com/crm/v4/objects/deals/{deal_id}/associations/{assoc_type}"
                params = {"limit": limit}

                response = await context.fetch(url, params=params)
                data = await parse_response(response)

                results = data.get("results", [])
                associations[assoc_type] = results
                total_count += len(results)
                summary[f"{assoc_type}_count"] = len(results)

            except Exception:
                # If association type doesn't exist or fails, continue with empty list
                associations[assoc_type] = []
                summary[f"{assoc_type}_count"] = 0

        return ActionResult(
            data={
                "deal_id": deal_id,
                "associations": associations,
                "total_associations": total_count,
                "summary": summary,
            },
            cost_usd=None,
        )


@hubspot.action("get_list_members")
class GetListMembersHandler(ActionHandler):
    """Retrieve list members with complete contact information"""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        import time

        start_time = time.time()

        list_id = inputs["list_id"]
        limit = inputs.get("limit", 1000)
        contact_properties = inputs.get(
            "contact_properties",
            ["email", "firstname", "lastname", "phone", "company", "jobtitle"],
        )
        include_timestamps = inputs.get("include_membership_timestamps", True)

        total_api_calls = 0

        # Step 1: Get list metadata
        list_url = f"https://api.hubapi.com/crm/v3/lists/{list_id}"
        list_response = await context.fetch(list_url)
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
        after_token = None
        total_retrieved = 0

        # Fetch memberships in batches of 250 (max limit)
        while total_retrieved < limit:
            params = {"limit": min(250, limit - total_retrieved)}
            if after_token:
                params["after"] = after_token

            try:
                response = await context.fetch(memberships_url, params=params)
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

            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    await asyncio.sleep(1)  # Simple rate limit handling
                    continue
                raise e

        # Step 3: Batch fetch contact details
        contact_ids = [m["recordId"] for m in all_memberships]
        membership_timestamps = {m["recordId"]: m["membershipTimestamp"] for m in all_memberships}

        all_contacts = []

        # Process contacts in batches of 100 (max for batch read)
        for i in range(0, len(contact_ids), 100):
            batch_ids = contact_ids[i : i + 100]

            batch_request = {
                "properties": contact_properties,
                "inputs": [{"id": contact_id} for contact_id in batch_ids],
            }

            try:
                contacts_url = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
                contacts_response = await context.fetch(
                    contacts_url,
                    method="POST",
                    json=batch_request,
                    headers={"Content-Type": "application/json"},
                )
                contacts_data = await parse_response(contacts_response)
                total_api_calls += 1

                batch_contacts = contacts_data.get("results", [])
                all_contacts.extend(batch_contacts)

            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                # Continue even if some contacts fail to load
                continue

        # Step 4: Combine data
        members = []
        for contact in all_contacts:
            contact_id = contact.get("id")
            properties = contact.get("properties", {})

            member = {"contact_id": contact_id, "properties": properties}

            # Add standard properties for easy access
            for prop in [
                "email",
                "firstname",
                "lastname",
                "phone",
                "company",
                "jobtitle",
            ]:
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

        return ActionResult(
            data={
                "list_metadata": list_metadata,
                "members": members,
                "total_members": list_metadata["size"],
                "retrieved_count": len(members),
                "performance_stats": performance_stats,
            },
            cost_usd=None,
        )


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
            response = await context.fetch(url, headers={"Content-Type": "application/json"})
            owner = await parse_response(response)

            return ActionResult(data={"owner": owner}, cost_usd=None)

        except Exception as e:
            return ActionError(message=f"Failed to retrieve owner: {str(e)}")


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

        response = await context.fetch(url, params=params)
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

        response = await context.fetch(url, params=params)
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

        response = await context.fetch(url, params=params)
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

        response = await context.fetch(url, params=params)
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

                    response = await context.fetch(base_url, params=params)
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
            response = await context.fetch(url, method="GET")
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
