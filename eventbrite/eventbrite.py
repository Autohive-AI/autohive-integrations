# Eventbrite API Integration
# Provides actions for managing events, venues, attendees, orders, and ticket classes

from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any

# Create the integration using the config.json
eventbrite = Integration.load()

BASE_URL = "https://www.eventbriteapi.com/v3"


# ============================================================================
# User Actions
# ============================================================================


@eventbrite.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Retrieves information about the currently authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{BASE_URL}/users/me/",
                method="GET",
            )

            return ActionResult(data={"user": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_organizations")
class ListOrganizationsAction(ActionHandler):
    """Lists all organizations the authenticated user is a member of."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{BASE_URL}/users/me/organizations/",
                method="GET",
            )

            return ActionResult(
                data={
                    "organizations": response.data.get("organizations", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Event Actions
# ============================================================================


@eventbrite.action("get_event")
class GetEventAction(ActionHandler):
    """Retrieves details of a specific event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            params = {}
            expand = inputs.get("expand")
            if expand:
                params["expand"] = ",".join(expand)

            url = f"{BASE_URL}/events/{event_id}/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(data={"event": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_events")
class ListEventsAction(ActionHandler):
    """Lists events for an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        organization_id = inputs["organization_id"]
        if not organization_id:
            return ActionError(message="organization_id is required")

        try:
            params = {}
            if inputs.get("status"):
                params["status"] = inputs.get("status")
            if inputs.get("order_by"):
                params["order_by"] = inputs.get("order_by")
            if inputs.get("time_filter"):
                params["time_filter"] = inputs.get("time_filter")
            if inputs.get("page_size"):
                params["page_size"] = inputs.get("page_size")

            url = f"{BASE_URL}/organizations/{organization_id}/events/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(
                data={
                    "events": response.data.get("events", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("create_event")
class CreateEventAction(ActionHandler):
    """Creates a new event in an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        organization_id = inputs["organization_id"]
        name = inputs["name"]
        start_utc = inputs["start_utc"]
        end_utc = inputs["end_utc"]
        timezone = inputs["timezone"]
        currency = inputs["currency"]

        if not all([organization_id, name, start_utc, end_utc, timezone, currency]):
            return ActionError(message="organization_id, name, start_utc, end_utc, timezone, and currency are required")

        try:
            event_data = {
                "event": {
                    "name": {"html": name},
                    "start": {"timezone": timezone, "utc": start_utc},
                    "end": {"timezone": timezone, "utc": end_utc},
                    "currency": currency,
                }
            }

            # Add optional fields
            if inputs.get("summary"):
                event_data["event"]["summary"] = inputs.get("summary")
            if inputs.get("online_event") is not None:
                event_data["event"]["online_event"] = inputs.get("online_event")
            if inputs.get("venue_id"):
                event_data["event"]["venue_id"] = inputs.get("venue_id")
            if inputs.get("organizer_id"):
                event_data["event"]["organizer_id"] = inputs.get("organizer_id")
            if inputs.get("category_id"):
                event_data["event"]["category_id"] = inputs.get("category_id")
            if inputs.get("listed") is not None:
                event_data["event"]["listed"] = inputs.get("listed")
            if inputs.get("shareable") is not None:
                event_data["event"]["shareable"] = inputs.get("shareable")
            if inputs.get("capacity"):
                event_data["event"]["capacity"] = inputs.get("capacity")

            response = await context.fetch(
                f"{BASE_URL}/organizations/{organization_id}/events/",
                method="POST",
                json=event_data,
            )

            return ActionResult(data={"event": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("update_event")
class UpdateEventAction(ActionHandler):
    """Updates an existing event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            event_data = {"event": {}}

            if inputs.get("name"):
                event_data["event"]["name"] = {"html": inputs.get("name")}
            if inputs.get("summary"):
                event_data["event"]["summary"] = inputs.get("summary")
            if inputs.get("start_utc") and inputs.get("timezone"):
                event_data["event"]["start"] = {
                    "timezone": inputs.get("timezone"),
                    "utc": inputs.get("start_utc"),
                }
            if inputs.get("end_utc") and inputs.get("timezone"):
                event_data["event"]["end"] = {
                    "timezone": inputs.get("timezone"),
                    "utc": inputs.get("end_utc"),
                }
            if inputs.get("currency"):
                event_data["event"]["currency"] = inputs.get("currency")
            if inputs.get("online_event") is not None:
                event_data["event"]["online_event"] = inputs.get("online_event")
            if inputs.get("venue_id"):
                event_data["event"]["venue_id"] = inputs.get("venue_id")
            if inputs.get("listed") is not None:
                event_data["event"]["listed"] = inputs.get("listed")
            if inputs.get("capacity"):
                event_data["event"]["capacity"] = inputs.get("capacity")

            if not event_data["event"]:
                return ActionError(message="No fields to update")

            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/",
                method="POST",
                json=event_data,
            )

            return ActionResult(data={"event": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("delete_event")
class DeleteEventAction(ActionHandler):
    """Deletes an event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            await context.fetch(
                f"{BASE_URL}/events/{event_id}/",
                method="DELETE",
            )

            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("publish_event")
class PublishEventAction(ActionHandler):
    """Publishes a draft event to make it live."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/publish/",
                method="POST",
            )

            return ActionResult(data={"published": response.data.get("published", True)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("unpublish_event")
class UnpublishEventAction(ActionHandler):
    """Unpublishes a live event back to draft status."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/unpublish/",
                method="POST",
            )

            return ActionResult(data={"unpublished": response.data.get("unpublished", True)}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("cancel_event")
class CancelEventAction(ActionHandler):
    """Cancels an event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            await context.fetch(
                f"{BASE_URL}/events/{event_id}/cancel/",
                method="POST",
            )

            return ActionResult(data={"canceled": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("copy_event")
class CopyEventAction(ActionHandler):
    """Creates a copy of an existing event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            copy_data = {}

            if inputs.get("name"):
                copy_data["name"] = inputs.get("name")
            if inputs.get("start_utc"):
                copy_data["start_date"] = inputs.get("start_utc")
            if inputs.get("end_utc"):
                copy_data["end_date"] = inputs.get("end_utc")
            if inputs.get("timezone"):
                copy_data["timezone"] = inputs.get("timezone")

            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/copy/",
                method="POST",
                json=copy_data if copy_data else None,
            )

            return ActionResult(data={"event": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("get_event_description")
class GetEventDescriptionAction(ActionHandler):
    """Retrieves the full HTML description of an event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/description/",
                method="GET",
            )

            return ActionResult(data={"description": response.data.get("description", "")}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Venue Actions
# ============================================================================


@eventbrite.action("get_venue")
class GetVenueAction(ActionHandler):
    """Retrieves details of a specific venue."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        venue_id = inputs["venue_id"]
        if not venue_id:
            return ActionError(message="venue_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/venues/{venue_id}/",
                method="GET",
            )

            return ActionResult(data={"venue": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_venues")
class ListVenuesAction(ActionHandler):
    """Lists venues for an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        organization_id = inputs["organization_id"]
        if not organization_id:
            return ActionError(message="organization_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/organizations/{organization_id}/venues/",
                method="GET",
            )

            return ActionResult(
                data={
                    "venues": response.data.get("venues", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("create_venue")
class CreateVenueAction(ActionHandler):
    """Creates a new venue for an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        organization_id = inputs["organization_id"]
        name = inputs["name"]

        if not organization_id or not name:
            return ActionError(message="organization_id and name are required")

        try:
            venue_data = {"venue": {"name": name, "address": {}}}

            # Add address fields
            if inputs.get("address_1"):
                venue_data["venue"]["address"]["address_1"] = inputs.get("address_1")
            if inputs.get("address_2"):
                venue_data["venue"]["address"]["address_2"] = inputs.get("address_2")
            if inputs.get("city"):
                venue_data["venue"]["address"]["city"] = inputs.get("city")
            if inputs.get("region"):
                venue_data["venue"]["address"]["region"] = inputs.get("region")
            if inputs.get("postal_code"):
                venue_data["venue"]["address"]["postal_code"] = inputs.get("postal_code")
            if inputs.get("country"):
                venue_data["venue"]["address"]["country"] = inputs.get("country")
            if inputs.get("latitude"):
                venue_data["venue"]["address"]["latitude"] = inputs.get("latitude")
            if inputs.get("longitude"):
                venue_data["venue"]["address"]["longitude"] = inputs.get("longitude")

            if inputs.get("capacity"):
                venue_data["venue"]["capacity"] = inputs.get("capacity")

            response = await context.fetch(
                f"{BASE_URL}/organizations/{organization_id}/venues/",
                method="POST",
                json=venue_data,
            )

            return ActionResult(data={"venue": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Order Actions
# ============================================================================


@eventbrite.action("get_order")
class GetOrderAction(ActionHandler):
    """Retrieves details of a specific order."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        order_id = inputs["order_id"]
        if not order_id:
            return ActionError(message="order_id is required")

        try:
            params = {}
            expand = inputs.get("expand")
            if expand:
                params["expand"] = ",".join(expand)

            url = f"{BASE_URL}/orders/{order_id}/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(data={"order": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_orders_by_event")
class ListOrdersByEventAction(ActionHandler):
    """Lists orders for a specific event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            params = {}
            if inputs.get("status"):
                params["status"] = inputs.get("status")
            if inputs.get("changed_since"):
                params["changed_since"] = inputs.get("changed_since")

            url = f"{BASE_URL}/events/{event_id}/orders/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(
                data={
                    "orders": response.data.get("orders", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_orders_by_organization")
class ListOrdersByOrganizationAction(ActionHandler):
    """Lists orders for an organization across all events."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        organization_id = inputs["organization_id"]
        if not organization_id:
            return ActionError(message="organization_id is required")

        try:
            params = {}
            if inputs.get("status"):
                params["status"] = inputs.get("status")
            if inputs.get("changed_since"):
                params["changed_since"] = inputs.get("changed_since")

            url = f"{BASE_URL}/organizations/{organization_id}/orders/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(
                data={
                    "orders": response.data.get("orders", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Attendee Actions
# ============================================================================


@eventbrite.action("get_attendee")
class GetAttendeeAction(ActionHandler):
    """Retrieves details of a specific attendee."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        attendee_id = inputs["attendee_id"]

        if not event_id or not attendee_id:
            return ActionError(message="event_id and attendee_id are required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/attendees/{attendee_id}/",
                method="GET",
            )

            return ActionResult(data={"attendee": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_attendees")
class ListAttendeesAction(ActionHandler):
    """Lists attendees for a specific event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            params = {}
            if inputs.get("status"):
                params["status"] = inputs.get("status")
            if inputs.get("changed_since"):
                params["changed_since"] = inputs.get("changed_since")

            url = f"{BASE_URL}/events/{event_id}/attendees/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(
                data={
                    "attendees": response.data.get("attendees", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Ticket Class Actions
# ============================================================================


@eventbrite.action("get_ticket_class")
class GetTicketClassAction(ActionHandler):
    """Retrieves details of a specific ticket class."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_class_id = inputs["ticket_class_id"]

        if not event_id or not ticket_class_id:
            return ActionError(message="event_id and ticket_class_id are required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/ticket_classes/{ticket_class_id}/",
                method="GET",
            )

            return ActionResult(data={"ticket_class": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("list_ticket_classes")
class ListTicketClassesAction(ActionHandler):
    """Lists ticket classes for a specific event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        if not event_id:
            return ActionError(message="event_id is required")

        try:
            params = {}
            if inputs.get("pos"):
                params["pos"] = inputs.get("pos")

            url = f"{BASE_URL}/events/{event_id}/ticket_classes/"
            if params:
                url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

            response = await context.fetch(url, method="GET")

            return ActionResult(
                data={
                    "ticket_classes": response.data.get("ticket_classes", []),
                    **(
                        {"pagination": response.data["pagination"]}
                        if response.data.get("pagination") is not None
                        else {}
                    ),
                },
                cost_usd=0.0,
            )
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("create_ticket_class")
class CreateTicketClassAction(ActionHandler):
    """Creates a new ticket class for an event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        name = inputs["name"]
        quantity_total = inputs["quantity_total"]

        if not event_id or not name or quantity_total is None:
            return ActionError(message="event_id, name, and quantity_total are required")

        try:
            ticket_class_data = {
                "ticket_class": {
                    "name": name,
                    "quantity_total": quantity_total,
                }
            }

            # Handle free vs paid tickets
            if inputs.get("free"):
                ticket_class_data["ticket_class"]["free"] = True
            elif inputs.get("donation"):
                ticket_class_data["ticket_class"]["donation"] = True
            elif inputs.get("cost"):
                # Cost format: "USD,2500" for $25.00
                cost_parts = inputs.get("cost").split(",")
                if len(cost_parts) == 2:
                    ticket_class_data["ticket_class"]["cost"] = f"{cost_parts[0]},{cost_parts[1]}"

            # Add optional fields
            if inputs.get("description"):
                ticket_class_data["ticket_class"]["description"] = inputs.get("description")
            if inputs.get("minimum_quantity"):
                ticket_class_data["ticket_class"]["minimum_quantity"] = inputs.get("minimum_quantity")
            if inputs.get("maximum_quantity"):
                ticket_class_data["ticket_class"]["maximum_quantity"] = inputs.get("maximum_quantity")
            if inputs.get("sales_start"):
                ticket_class_data["ticket_class"]["sales_start"] = inputs.get("sales_start")
            if inputs.get("sales_end"):
                ticket_class_data["ticket_class"]["sales_end"] = inputs.get("sales_end")
            if inputs.get("hidden") is not None:
                ticket_class_data["ticket_class"]["hidden"] = inputs.get("hidden")

            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/ticket_classes/",
                method="POST",
                json=ticket_class_data,
            )

            return ActionResult(data={"ticket_class": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("update_ticket_class")
class UpdateTicketClassAction(ActionHandler):
    """Updates an existing ticket class."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_class_id = inputs["ticket_class_id"]

        if not event_id or not ticket_class_id:
            return ActionError(message="event_id and ticket_class_id are required")

        try:
            ticket_class_data = {"ticket_class": {}}

            if inputs.get("name"):
                ticket_class_data["ticket_class"]["name"] = inputs.get("name")
            if inputs.get("description"):
                ticket_class_data["ticket_class"]["description"] = inputs.get("description")
            if inputs.get("quantity_total"):
                ticket_class_data["ticket_class"]["quantity_total"] = inputs.get("quantity_total")
            if inputs.get("minimum_quantity"):
                ticket_class_data["ticket_class"]["minimum_quantity"] = inputs.get("minimum_quantity")
            if inputs.get("maximum_quantity"):
                ticket_class_data["ticket_class"]["maximum_quantity"] = inputs.get("maximum_quantity")
            if inputs.get("sales_start"):
                ticket_class_data["ticket_class"]["sales_start"] = inputs.get("sales_start")
            if inputs.get("sales_end"):
                ticket_class_data["ticket_class"]["sales_end"] = inputs.get("sales_end")
            if inputs.get("hidden") is not None:
                ticket_class_data["ticket_class"]["hidden"] = inputs.get("hidden")

            if not ticket_class_data["ticket_class"]:
                return ActionError(message="No fields to update")

            response = await context.fetch(
                f"{BASE_URL}/events/{event_id}/ticket_classes/{ticket_class_id}/",
                method="POST",
                json=ticket_class_data,
            )

            return ActionResult(data={"ticket_class": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("delete_ticket_class")
class DeleteTicketClassAction(ActionHandler):
    """Deletes a ticket class."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs["event_id"]
        ticket_class_id = inputs["ticket_class_id"]

        if not event_id or not ticket_class_id:
            return ActionError(message="event_id and ticket_class_id are required")

        try:
            await context.fetch(
                f"{BASE_URL}/events/{event_id}/ticket_classes/{ticket_class_id}/",
                method="DELETE",
            )

            return ActionResult(data={"deleted": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ============================================================================
# Category Actions
# ============================================================================


@eventbrite.action("list_categories")
class ListCategoriesAction(ActionHandler):
    """Lists all available event categories."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{BASE_URL}/categories/",
                method="GET",
            )

            return ActionResult(data={"categories": response.data.get("categories", [])}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@eventbrite.action("get_category")
class GetCategoryAction(ActionHandler):
    """Retrieves details of a specific category."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        category_id = inputs["category_id"]
        if not category_id:
            return ActionError(message="category_id is required")

        try:
            response = await context.fetch(
                f"{BASE_URL}/categories/{category_id}/",
                method="GET",
            )

            return ActionResult(data={"category": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
