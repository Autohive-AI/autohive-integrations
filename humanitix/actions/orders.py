"""
Humanitix Orders action - Retrieve order information for events.
"""

from autohive_integrations_sdk import ActionHandler, ActionResult, ExecutionContext
from typing import Dict, Any

from humanitix import humanitix
from helpers import HUMANITIX_API_BASE, get_api_headers, build_error_result


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
            url = f"{HUMANITIX_API_BASE}/events/{event_id}/orders/{order_id}"
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
                "order": response
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
            url = f"{HUMANITIX_API_BASE}/events/{event_id}/orders?{query_string}"

            response = await context.fetch(
                url,
                method="GET",
                headers=headers
            )

            if error := build_error_result(response): return error

            orders = response.get("orders", []) if isinstance(response, dict) else []

            return ActionResult(data={
                "result": True,
                "orders": orders,
                "total": response.get("total", len(orders)) if isinstance(response, dict) else len(orders),
                "page": response.get("page", page) if isinstance(response, dict) else page,
                "pageSize": response.get("pageSize", page_size or 100) if isinstance(response, dict) else (page_size or 100)
            })
