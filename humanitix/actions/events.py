"""
Humanitix Events action - Retrieve event information.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import HUMANITIX_API_BASE, get_api_headers


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
            url = f"{HUMANITIX_API_BASE}/events/{event_id}"
            if params:
                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{url}?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if isinstance(response, dict) and "statusCode" in response:
                return ActionResult(data={
                    "result": False,
                    "statusCode": response.get("statusCode"),
                    "error": response.get("error", ""),
                    "message": response.get("message", "")
                })

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

            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{HUMANITIX_API_BASE}/events?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if isinstance(response, dict) and "statusCode" in response:
                return ActionResult(data={
                    "result": False,
                    "statusCode": response.get("statusCode"),
                    "error": response.get("error", ""),
                    "message": response.get("message", "")
                })

            events = response.get("events", []) if isinstance(response, dict) else []

            return ActionResult(data={
                "result": True,
                "events": events,
                "total": response.get("total", len(events)) if isinstance(response, dict) else len(events),
                "page": response.get("page", page) if isinstance(response, dict) else page,
                "pageSize": response.get("pageSize", page_size or 100) if isinstance(response, dict) else (page_size or 100)
            })
