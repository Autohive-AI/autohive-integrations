"""
Humanitix Check In / Check Out actions - Manage ticket check-in status for events.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import HUMANITIX_API_BASE, get_api_headers


@humanitix.action("check_in")
class CheckInAction(ActionHandler):
    """
    Check in a ticket for an event.

    Calls POST /events/{eventId}/tickets/{ticketId}/check-in to mark
    the ticket as checked in. Returns any scanning messages configured
    for the ticket.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_id = inputs["ticket_id"]
        override_location = inputs.get("override_location")

        headers = get_api_headers(context)
        headers["Content-Type"] = "application/json"

        url = f"{HUMANITIX_API_BASE}/events/{event_id}/tickets/{ticket_id}/check-in"
        if override_location:
            url = f"{url}?overrideLocation={override_location}"

        response = await context.fetch(
            url,
            method="POST",
            headers=headers
        )

        scanning_messages = []
        if isinstance(response, dict):
            scanning_messages = response.get("scanningMessages", [])

        return ActionResult(data={"scanning_messages": scanning_messages})


@humanitix.action("check_out")
class CheckOutAction(ActionHandler):
    """
    Check out a ticket for an event.

    Calls POST /events/{eventId}/tickets/{ticketId}/check-out to mark
    the ticket as checked out. Returns any scanning messages configured
    for the ticket.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_id = inputs["ticket_id"]
        override_location = inputs.get("override_location")

        headers = get_api_headers(context)
        headers["Content-Type"] = "application/json"

        url = f"{HUMANITIX_API_BASE}/events/{event_id}/tickets/{ticket_id}/check-out"
        if override_location:
            url = f"{url}?overrideLocation={override_location}"

        response = await context.fetch(
            url,
            method="POST",
            headers=headers
        )

        scanning_messages = []
        if isinstance(response, dict):
            scanning_messages = response.get("scanningMessages", [])

        return ActionResult(data={"scanning_messages": scanning_messages})
