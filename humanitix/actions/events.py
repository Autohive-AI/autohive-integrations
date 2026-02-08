"""
Humanitix Events action - Retrieve event information.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import get_api_headers, build_url, build_error_result, build_paginated_result


@humanitix.action("get_events")
class GetEventsAction(ActionHandler):
    """
    Retrieve events from your Humanitix account.

    Can fetch a single event by ID or list all events. Returns event details
    including name, dates, venue, and ticket information.

    When event_id is provided, calls GET /events/{eventId} directly.
    Only override_location is supported in this mode; page_size, since,
    and page are ignored.

    When event_id is omitted, calls GET /events with optional query
    parameters for pagination and filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        override_location = inputs.get("override_location")

        headers = get_api_headers(context)
        params = {}
        if override_location:
            params["overrideLocation"] = override_location

        if event_id:
            url = build_url(f"events/{event_id}", params or None)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if error := build_error_result(response): return error

            return ActionResult(data={
                "result": True,
                "event": response
            })
        else:
            page_size = inputs.get("page_size")
            since = inputs.get("since")
            page = inputs.get("page", 1)

            params["page"] = page

            if page_size is not None:
                params["pageSize"] = page_size
            if since:
                params["since"] = since

            url = build_url("events", params)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if error := build_error_result(response): return error

            return build_paginated_result(response, "events", page, page_size)
