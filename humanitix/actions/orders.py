"""
Humanitix Orders action - Retrieve order information for events.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import get_api_headers, build_url, build_error_result, build_paginated_result, fetch_single_resource


@humanitix.action("get_orders")
class GetOrdersAction(ActionHandler):
    """
    Retrieve orders for a specific event.

    Returns order details including buyer information, ticket quantities,
    and payment status. Can fetch a single order by ID or list all orders
    for the event.

    When order_id is provided, calls GET /events/{eventId}/orders/{orderId}
    directly. Only override_location and event_date_id are supported in
    this mode; page_size, since, and page are ignored.

    When order_id is omitted, calls GET /events/{eventId}/orders with
    optional query parameters for pagination and filtering.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        order_id = inputs.get("order_id")
        override_location = inputs.get("override_location")
        event_date_id = inputs.get("event_date_id")

        headers = get_api_headers(context)
        params = {}
        if override_location:
            params["overrideLocation"] = override_location
        if event_date_id:
            params["eventDateId"] = event_date_id

        if order_id:
            return await fetch_single_resource(context, f"events/{event_id}/orders/{order_id}", params, "order")
        else:
            page_size = inputs.get("page_size")
            since = inputs.get("since")
            page = inputs.get("page", 1)

            params["page"] = page

            if page_size is not None:
                params["pageSize"] = page_size
            if since:
                params["since"] = since

            url = build_url(f"events/{event_id}/orders", params)

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if error := build_error_result(response): return error

            return build_paginated_result(response, "orders", page, page_size)
