"""
Humanitix Check In / Check Out actions - Manage ticket check-in status for events.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import get_api_headers, build_url, build_error_result


async def _toggle_check(inputs: Dict[str, Any], context: ExecutionContext, action: str) -> ActionResult:
    event_id = inputs["event_id"]
    ticket_id = inputs["ticket_id"]
    override_location = inputs.get("override_location")

    headers = get_api_headers(context)
    headers["Content-Type"] = "application/json"

    params = {"overrideLocation": override_location} if override_location else None
    url = build_url(f"events/{event_id}/tickets/{ticket_id}/{action}", params)

    response = await context.fetch(
        url,
        method="POST",
        headers=headers
    )

    if error := build_error_result(response): return error

    return ActionResult(data={
        "result": True,
        "scanningMessages": response.get("scanningMessages", []) if isinstance(response, dict) else []
    })


@humanitix.action("check_in")
class CheckInAction(ActionHandler):
    """
    Check in a ticket for an event.

    Calls POST /events/{eventId}/tickets/{ticketId}/check-in to mark
    the ticket as checked in. Returns any scanning messages configured
    for the ticket.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        return await _toggle_check(inputs, context, "check-in")


@humanitix.action("check_out")
class CheckOutAction(ActionHandler):
    """
    Check out a ticket for an event.

    Calls POST /events/{eventId}/tickets/{ticketId}/check-out to mark
    the ticket as checked out. Returns any scanning messages configured
    for the ticket.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        return await _toggle_check(inputs, context, "check-out")
