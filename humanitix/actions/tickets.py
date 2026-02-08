"""
Humanitix Tickets action - Retrieve ticket information for events.
"""

from autohive_integrations_sdk import ActionHandler, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import get_api_headers, build_url, build_paginated_result, fetch_single_resource


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

        params = {}
        if override_location:
            params["overrideLocation"] = override_location

        if ticket_id:
            return await fetch_single_resource(context, f"events/{event_id}/tickets/{ticket_id}", params, "ticket")

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

        url = build_url(f"events/{event_id}/tickets", params)

        response = await context.fetch(
            url,
            method="GET",
            headers=get_api_headers(context)
        )

        return build_paginated_result(response, "tickets", page, page_size)
