from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any

# Create the integration
calendly = Integration.load()

# Base URL for Calendly API v2
CALENDLY_API_BASE_URL = "https://api.calendly.com"

# Note: Authentication is handled automatically by the platform OAuth integration.
# The context.fetch method automatically includes the OAuth token in requests.
#
# Calendly OAuth does not use traditional scopes - access is determined by
# the user's subscription level (free, standard, teams, enterprise).
# Webhooks require a paid plan (Standard or higher).


# ---- User Handlers ----

@calendly.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    """Get information about the currently authenticated user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/users/me",
                method="GET"
            )

            user = response.get("resource", response)

            return ActionResult(
                data={"user": user, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_user")
class GetUserAction(ActionHandler):
    """Get information about a specific user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_uuid = inputs["user_uuid"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/users/{user_uuid}",
                method="GET"
            )

            user = response.get("resource", response)

            return ActionResult(
                data={"user": user, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"user": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Event Type Handlers ----

@calendly.action("list_event_types")
class ListEventTypesAction(ActionHandler):
    """List all event types for a user or organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["user", "organization", "active", "sort", "count", "page_token"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/event_types",
                method="GET",
                params=params if params else None
            )

            event_types = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"event_types": event_types, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"event_types": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_event_type")
class GetEventTypeAction(ActionHandler):
    """Get details of a specific event type."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_type_uuid = inputs["event_type_uuid"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/event_types/{event_type_uuid}",
                method="GET"
            )

            event_type = response.get("resource", response)

            return ActionResult(
                data={"event_type": event_type, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"event_type": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Scheduled Event Handlers ----

@calendly.action("list_scheduled_events")
class ListScheduledEventsAction(ActionHandler):
    """List scheduled events for a user or organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["user", "organization", "invitee_email", "status",
                        "min_start_time", "max_start_time", "sort", "count", "page_token"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/scheduled_events",
                method="GET",
                params=params if params else None
            )

            events = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"events": events, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"events": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_scheduled_event")
class GetScheduledEventAction(ActionHandler):
    """Get details of a specific scheduled event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_uuid = inputs["event_uuid"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/scheduled_events/{event_uuid}",
                method="GET"
            )

            event = response.get("resource", response)

            return ActionResult(
                data={"event": event, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"event": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("cancel_scheduled_event")
class CancelScheduledEventAction(ActionHandler):
    """Cancel a scheduled event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_uuid = inputs["event_uuid"]

            body = {}
            if inputs.get("reason"):
                body["reason"] = inputs["reason"]

            await context.fetch(
                f"{CALENDLY_API_BASE_URL}/scheduled_events/{event_uuid}/cancellation",
                method="POST",
                json=body if body else None
            )

            return ActionResult(
                data={"canceled": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"canceled": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Invitee Handlers ----

@calendly.action("list_event_invitees")
class ListEventInviteesAction(ActionHandler):
    """List all invitees for a scheduled event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_uuid = inputs["event_uuid"]

            params = {}
            for key in ["status", "sort", "email", "count", "page_token"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/scheduled_events/{event_uuid}/invitees",
                method="GET",
                params=params if params else None
            )

            invitees = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"invitees": invitees, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"invitees": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_invitee")
class GetInviteeAction(ActionHandler):
    """Get details of a specific invitee."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_uuid = inputs["event_uuid"]
            invitee_uuid = inputs["invitee_uuid"]

            # Calendly API v2 requires invitees to be accessed through the scheduled event endpoint
            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/scheduled_events/{event_uuid}/invitees/{invitee_uuid}",
                method="GET"
            )

            invitee = response.get("resource", response)

            return ActionResult(
                data={"invitee": invitee, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"invitee": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Availability Handlers ----

@calendly.action("get_event_type_available_times")
class GetEventTypeAvailableTimesAction(ActionHandler):
    """Get available time slots for an event type (max 7 days)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "event_type": inputs["event_type"],
                "start_time": inputs["start_time"],
                "end_time": inputs["end_time"]
            }

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/event_type_available_times",
                method="GET",
                params=params
            )

            available_times = response.get("collection", [])

            return ActionResult(
                data={"available_times": available_times, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"available_times": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_user_busy_times")
class GetUserBusyTimesAction(ActionHandler):
    """Get busy time slots for a user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "user": inputs["user"],
                "start_time": inputs["start_time"],
                "end_time": inputs["end_time"]
            }

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/user_busy_times",
                method="GET",
                params=params
            )

            busy_times = response.get("collection", [])

            return ActionResult(
                data={"busy_times": busy_times, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"busy_times": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("list_user_availability_schedules")
class ListUserAvailabilitySchedulesAction(ActionHandler):
    """List availability schedules for a user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"user": inputs["user"]}

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/user_availability_schedules",
                method="GET",
                params=params
            )

            schedules = response.get("collection", [])

            return ActionResult(
                data={"availability_schedules": schedules, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"availability_schedules": [], "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Organization Handlers ----

@calendly.action("list_organization_memberships")
class ListOrganizationMembershipsAction(ActionHandler):
    """List all members of an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["organization", "user", "email", "count", "page_token"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/organization_memberships",
                method="GET",
                params=params if params else None
            )

            memberships = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"memberships": memberships, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"memberships": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Webhook Handlers ----

@calendly.action("list_webhooks")
class ListWebhooksAction(ActionHandler):
    """List webhook subscriptions."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {}
            for key in ["organization", "user", "scope", "count", "page_token"]:
                if inputs.get(key) is not None:
                    params[key] = inputs[key]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/webhook_subscriptions",
                method="GET",
                params=params if params else None
            )

            webhooks = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"webhooks": webhooks, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhooks": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_webhook")
class GetWebhookAction(ActionHandler):
    """Get details of a specific webhook subscription."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            webhook_uuid = inputs["webhook_uuid"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/webhook_subscriptions/{webhook_uuid}",
                method="GET"
            )

            webhook = response.get("resource", response)

            return ActionResult(
                data={"webhook": webhook, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhook": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("create_webhook")
class CreateWebhookAction(ActionHandler):
    """Create a webhook subscription (requires paid plan)."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            body = {
                "url": inputs["url"],
                "events": inputs["events"],
                "organization": inputs["organization"],
                "scope": inputs["scope"]
            }

            if inputs.get("user"):
                body["user"] = inputs["user"]
            if inputs.get("signing_key"):
                body["signing_key"] = inputs["signing_key"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/webhook_subscriptions",
                method="POST",
                json=body
            )

            webhook = response.get("resource", response)

            return ActionResult(
                data={"webhook": webhook, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"webhook": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("delete_webhook")
class DeleteWebhookAction(ActionHandler):
    """Delete a webhook subscription."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            webhook_uuid = inputs["webhook_uuid"]

            await context.fetch(
                f"{CALENDLY_API_BASE_URL}/webhook_subscriptions/{webhook_uuid}",
                method="DELETE"
            )

            return ActionResult(
                data={"deleted": True, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"deleted": False, "result": False, "error": str(e)},
                cost_usd=0.0
            )


# ---- Routing Form Handlers ----

@calendly.action("list_routing_forms")
class ListRoutingFormsAction(ActionHandler):
    """List routing forms for an organization."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {"organization": inputs["organization"]}
            if inputs.get("count"):
                params["count"] = inputs["count"]
            if inputs.get("page_token"):
                params["page_token"] = inputs["page_token"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/routing_forms",
                method="GET",
                params=params
            )

            routing_forms = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"routing_forms": routing_forms, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"routing_forms": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("get_routing_form")
class GetRoutingFormAction(ActionHandler):
    """Get details of a specific routing form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            routing_form_uuid = inputs["routing_form_uuid"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/routing_forms/{routing_form_uuid}",
                method="GET"
            )

            routing_form = response.get("resource", response)

            return ActionResult(
                data={"routing_form": routing_form, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"routing_form": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )


@calendly.action("list_routing_form_submissions")
class ListRoutingFormSubmissionsAction(ActionHandler):
    """List submissions for a routing form."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Calendly API expects 'form' parameter, not 'routing_form'
            params = {"form": inputs["routing_form"]}
            if inputs.get("count"):
                params["count"] = inputs["count"]
            if inputs.get("page_token"):
                params["page_token"] = inputs["page_token"]

            response = await context.fetch(
                f"{CALENDLY_API_BASE_URL}/routing_form_submissions",
                method="GET",
                params=params
            )

            submissions = response.get("collection", [])
            pagination = response.get("pagination", {})

            return ActionResult(
                data={"submissions": submissions, "pagination": pagination, "result": True},
                cost_usd=0.0
            )

        except Exception as e:
            return ActionResult(
                data={"submissions": [], "pagination": {}, "result": False, "error": str(e)},
                cost_usd=0.0
            )
