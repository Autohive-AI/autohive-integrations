"""
Humanitix Tickets action - Retrieve ticket information for events.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import HUMANITIX_API_BASE, get_api_headers, build_error_result


@humanitix.action("get_tickets")
class GetTicketsAction(ActionHandler):
    """
    Retrieve tickets for a specific event.

    Returns ticket details including attendee information, ticket type,
    and check-in status. Can fetch a single ticket by ID or list all
    tickets for the event.

    When ticket_id is provided, calls GET /events/{eventId}/tickets/{ticketId}
    directly. Only override_location is supported in this mode; page_size,
    since, status, event_date_id, and page are ignored.

    When ticket_id is omitted, calls GET /events/{eventId}/tickets with
    optional query parameters for pagination and filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_id = inputs.get("ticket_id")
        override_location = inputs.get("override_location")

        headers = get_api_headers(context)
        params = {}
        if override_location:
            params["overrideLocation"] = override_location

        if ticket_id:
            url = f"{HUMANITIX_API_BASE}/events/{event_id}/tickets/{ticket_id}"
            if params:
                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{url}?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if error := build_error_result(response): return error

            return ActionResult(data={
                "result": True,
                "ticket": response
            })
        else:
            event_date_id = inputs.get("event_date_id")
            page_size = inputs.get("page_size")
            since = inputs.get("since")
            status = inputs.get("status")
            page = inputs.get("page", 1)

            params["page"] = page

            if event_date_id:
                params["eventDateId"] = event_date_id
            if page_size is not None:
                params["pageSize"] = page_size
            if since:
                params["since"] = since
            if status:
                params["status"] = status

            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{HUMANITIX_API_BASE}/events/{event_id}/tickets?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            tickets = response.get("tickets", []) if isinstance(response, dict) else []

            return ActionResult(data={
                "result": True,
                "tickets": tickets,
                "total": response.get("total", len(tickets)) if isinstance(response, dict) else len(tickets),
                "page": response.get("page", page) if isinstance(response, dict) else page,
                "pageSize": response.get("pageSize", page_size or 100) if isinstance(response, dict) else (page_size or 100)
            })
