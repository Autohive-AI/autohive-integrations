from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any
import base64

# Create the integration using the config.json
freshdesk = Integration.load()

# Base URL for Freshdesk API v2
FRESHDESK_API_VERSION = "v2"


# ---- Helper Functions ----


def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """
    Build authentication headers for Freshdesk API requests.
    Freshdesk uses Basic Authentication with API key as username and 'X' as password.

    Args:
        context: ExecutionContext containing auth credentials

    Returns:
        Dictionary with Authorization and Content-Type headers
    """
    api_key = context.auth.get("api_key", "")

    # Freshdesk requires Basic Auth with format: api_key:X
    auth_string = f"{api_key}:X"
    auth_bytes = auth_string.encode("ascii")
    base64_auth = base64.b64encode(auth_bytes).decode("ascii")

    return {"Authorization": f"Basic {base64_auth}", "Content-Type": "application/json"}


def get_base_url(context: ExecutionContext) -> str:
    """
    Construct the base URL for Freshdesk API requests.

    Args:
        context: ExecutionContext containing auth credentials with domain

    Returns:
        Base URL string (e.g., https://yourcompany.freshdesk.com/api/v2)
    """
    domain = context.auth.get("domain", "")

    return f"https://{domain}.freshdesk.com/api/{FRESHDESK_API_VERSION}"


# ---- Action Handlers ----


@freshdesk.action("list_companies")
class ListCompaniesAction(ActionHandler):
    """
    List all companies in the Freshdesk account.
    Companies represent organizations associated with contacts.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract pagination parameters
            page = inputs.get("page", 1)
            per_page = inputs.get("per_page", 30)

            # Build query parameters
            params = {"page": page, "per_page": per_page}

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Make API request
            url = f"{base_url}/companies"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            # Response is a list of companies
            companies = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"companies": companies, "total": len(companies)})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("create_company")
class CreateCompanyAction(ActionHandler):
    """
    Create a new company in the Freshdesk account.
    Company name is required, other fields are optional.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Build request body
            body = {"name": inputs["name"]}

            # Add optional fields if provided
            if inputs.get("description"):
                body["description"] = inputs.get("description")

            if inputs.get("domains"):
                body["domains"] = inputs.get("domains")

            if inputs.get("note"):
                body["note"] = inputs.get("note")

            if inputs.get("custom_fields"):
                body["custom_fields"] = inputs.get("custom_fields")

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Make API request
            url = f"{base_url}/companies"
            response = await context.fetch(url, method="POST", headers=headers, json=body)

            return ActionResult(data={"company": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("get_company")
class GetCompanyAction(ActionHandler):
    """
    Get details of a specific company by its ID.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract company ID
            company_id = inputs["company_id"]

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Make API request
            url = f"{base_url}/companies/{company_id}"
            response = await context.fetch(url, method="GET", headers=headers)

            return ActionResult(data={"company": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("update_company")
class UpdateCompanyAction(ActionHandler):
    """
    Update an existing company's information.
    Only updates the fields provided in the input.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract company ID
            company_id = inputs["company_id"]

            # Build request body with only provided fields
            body = {}

            if inputs.get("name"):
                body["name"] = inputs.get("name")

            if inputs.get("description"):
                body["description"] = inputs.get("description")

            if inputs.get("domains"):
                body["domains"] = inputs.get("domains")

            if inputs.get("note"):
                body["note"] = inputs.get("note")

            if inputs.get("custom_fields"):
                body["custom_fields"] = inputs.get("custom_fields")

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Make API request
            url = f"{base_url}/companies/{company_id}"
            response = await context.fetch(url, method="PUT", headers=headers, json=body)

            return ActionResult(data={"company": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("delete_company")
class DeleteCompanyAction(ActionHandler):
    """
    Delete a company from the Freshdesk account.
    This action cannot be undone.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract company ID
            company_id = inputs["company_id"]

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Make API request
            url = f"{base_url}/companies/{company_id}"
            await context.fetch(url, method="DELETE", headers=headers)

            return ActionResult(data={"deleted": True})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("search_companies")
class SearchCompaniesAction(ActionHandler):
    """
    Search for companies by name using autocomplete.
    The search is case insensitive but requires complete words (no substring matching).
    For example, 'Acme Corporation' can be found with 'acme', 'Ac', 'Corporation',
    or 'Co', but not 'cme' or 'orporation'.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract search keyword
            name = inputs["name"]

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Build query parameters
            params = {"name": name}

            # Make API request to autocomplete endpoint
            url = f"{base_url}/companies/autocomplete"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            # Extract companies from response
            body = response.data
            companies = body.get("companies", []) if isinstance(body, dict) else []

            return ActionResult(data={"companies": companies, "total": len(companies)})

        except Exception as e:
            return ActionError(message=str(e))


# ---- Ticket Handlers ----


@freshdesk.action("create_ticket")
class CreateTicketAction(ActionHandler):
    """Create a new support ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"subject": inputs["subject"], "email": inputs["email"]}

            if inputs.get("description"):
                body["description"] = inputs.get("description")
            if inputs.get("priority") is not None:
                body["priority"] = inputs.get("priority")
            if inputs.get("status") is not None:
                body["status"] = inputs.get("status")
            if inputs.get("source") is not None:
                body["source"] = inputs.get("source")
            if inputs.get("name"):
                body["name"] = inputs.get("name")
            if inputs.get("company_id") is not None:
                body["company_id"] = inputs.get("company_id")
            if inputs.get("tags"):
                body["tags"] = inputs.get("tags")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/tickets", method="POST", headers=headers, json=body)

            return ActionResult(data={"ticket": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("list_tickets")
class ListTicketsAction(ActionHandler):
    """List all tickets with pagination."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 30)}

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/tickets", method="GET", headers=headers, params=params)

            tickets = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"tickets": tickets, "total": len(tickets)})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("get_ticket")
class GetTicketAction(ActionHandler):
    """Get details of a specific ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/tickets/{ticket_id}", method="GET", headers=headers)

            return ActionResult(data={"ticket": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("update_ticket")
class UpdateTicketAction(ActionHandler):
    """Update an existing ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]
            body = {}

            if inputs.get("subject"):
                body["subject"] = inputs.get("subject")
            if inputs.get("description"):
                body["description"] = inputs.get("description")
            if inputs.get("priority") is not None:
                body["priority"] = inputs.get("priority")
            if inputs.get("status") is not None:
                body["status"] = inputs.get("status")
            if inputs.get("tags"):
                body["tags"] = inputs.get("tags")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/tickets/{ticket_id}", method="PUT", headers=headers, json=body)

            return ActionResult(data={"ticket": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("delete_ticket")
class DeleteTicketAction(ActionHandler):
    """Delete a ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            await context.fetch(f"{base_url}/tickets/{ticket_id}", method="DELETE", headers=headers)

            return ActionResult(data={"deleted": True})

        except Exception as e:
            return ActionError(message=str(e))


# ---- Contact Handlers ----


@freshdesk.action("create_contact")
class CreateContactAction(ActionHandler):
    """Create a new contact."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {"name": inputs["name"], "email": inputs["email"]}

            if inputs.get("phone"):
                body["phone"] = inputs.get("phone")
            if inputs.get("mobile"):
                body["mobile"] = inputs.get("mobile")
            if inputs.get("company_id") is not None:
                body["company_id"] = inputs.get("company_id")
            if inputs.get("job_title"):
                body["job_title"] = inputs.get("job_title")
            if inputs.get("description"):
                body["description"] = inputs.get("description")
            if inputs.get("tags"):
                body["tags"] = inputs.get("tags")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/contacts", method="POST", headers=headers, json=body)

            return ActionResult(data={"contact": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("list_contacts")
class ListContactsAction(ActionHandler):
    """List all contacts with pagination."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"page": inputs.get("page", 1), "per_page": inputs.get("per_page", 30)}

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/contacts", method="GET", headers=headers, params=params)

            contacts = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"contacts": contacts, "total": len(contacts)})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("get_contact")
class GetContactAction(ActionHandler):
    """Get details of a specific contact."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            contact_id = inputs["contact_id"]

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(f"{base_url}/contacts/{contact_id}", method="GET", headers=headers)

            return ActionResult(data={"contact": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("update_contact")
class UpdateContactAction(ActionHandler):
    """Update an existing contact."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            contact_id = inputs["contact_id"]
            body = {}

            if inputs.get("name"):
                body["name"] = inputs.get("name")
            if inputs.get("email"):
                body["email"] = inputs.get("email")
            if inputs.get("phone"):
                body["phone"] = inputs.get("phone")
            if inputs.get("mobile"):
                body["mobile"] = inputs.get("mobile")
            if inputs.get("job_title"):
                body["job_title"] = inputs.get("job_title")
            if inputs.get("description"):
                body["description"] = inputs.get("description")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(
                f"{base_url}/contacts/{contact_id}", method="PUT", headers=headers, json=body
            )

            return ActionResult(data={"contact": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("delete_contact")
class DeleteContactAction(ActionHandler):
    """Soft delete a contact."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            contact_id = inputs["contact_id"]

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            await context.fetch(f"{base_url}/contacts/{contact_id}", method="DELETE", headers=headers)

            return ActionResult(data={"deleted": True})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("search_contacts")
class SearchContactsAction(ActionHandler):
    """
    Search for contacts by name using autocomplete.
    The search is case insensitive but requires complete words (no substring matching).
    For example, 'John Jonz' can be found with 'john', 'Joh', 'Jonz', or 'jon',
    but not 'hn' or 'nz'.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract search term
            term = inputs["term"]

            # Get auth headers and base URL
            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            # Build query parameters
            params = {"term": term}

            # Make API request to autocomplete endpoint
            url = f"{base_url}/contacts/autocomplete"
            response = await context.fetch(url, method="GET", headers=headers, params=params)

            # Response is directly an array of contacts
            contacts = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"contacts": contacts, "total": len(contacts)})

        except Exception as e:
            return ActionError(message=str(e))


# ---- Conversation Handlers ----


@freshdesk.action("list_conversations")
class ListConversationsAction(ActionHandler):
    """List all conversations for a ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(
                f"{base_url}/tickets/{ticket_id}/conversations", method="GET", headers=headers
            )

            conversations = response.data if isinstance(response.data, list) else []

            return ActionResult(data={"conversations": conversations})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("create_note")
class CreateNoteAction(ActionHandler):
    """Add a private note to a ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]
            body = {"body": inputs["body"], "private": True}

            if inputs.get("notify_emails"):
                body["notify_emails"] = inputs.get("notify_emails")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(
                f"{base_url}/tickets/{ticket_id}/notes", method="POST", headers=headers, json=body
            )

            return ActionResult(data={"conversation": response.data})

        except Exception as e:
            return ActionError(message=str(e))


@freshdesk.action("create_reply")
class CreateReplyAction(ActionHandler):
    """Add a public reply to a ticket."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            ticket_id = inputs["ticket_id"]
            body = {"body": inputs["body"]}

            if inputs.get("from_email"):
                body["from_email"] = inputs.get("from_email")

            headers = get_auth_headers(context)
            base_url = get_base_url(context)

            response = await context.fetch(
                f"{base_url}/tickets/{ticket_id}/reply", method="POST", headers=headers, json=body
            )

            return ActionResult(data={"conversation": response.data})

        except Exception as e:
            return ActionError(message=str(e))
