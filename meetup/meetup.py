# Meetup API Integration
# Provides actions for managing events across multiple Meetup groups

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Any, Dict

from helpers import (
    MEETUP_GQL_URL,
    GET_SELF_QUERY,
    LIST_GROUPS_QUERY,
    GET_GROUP_QUERY,
    LIST_EVENTS_QUERY,
    GET_EVENT_QUERY,
    CREATE_EVENT_MUTATION,
    UPDATE_EVENT_MUTATION,
    DELETE_EVENT_MUTATION,
    PUBLISH_EVENT_MUTATION,
    extract_gql_errors,
)

meetup = Integration.load()


async def _gql(context: ExecutionContext, query: str, variables: Dict[str, Any] | None = None) -> dict:
    """Execute a GraphQL query or mutation against the Meetup API."""
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    return await context.fetch(
        MEETUP_GQL_URL,
        method="POST",
        body=payload,
    )


# ============================================================================
# User Actions
# ============================================================================


@meetup.action("get_self")
class GetSelfAction(ActionHandler):
    """Retrieves the authenticated user's Meetup profile."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await _gql(context, GET_SELF_QUERY)
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            user = response.get("data", {}).get("self")
            return ActionResult(data={"result": True, "user": user}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ============================================================================
# Group Actions
# ============================================================================


@meetup.action("list_groups")
class ListGroupsAction(ActionHandler):
    """Lists all Meetup groups the authenticated user organizes."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            variables = {"first": inputs.get("first", 50)}
            response = await _gql(context, LIST_GROUPS_QUERY, variables)
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            edges = (
                response.get("data", {})
                .get("self", {})
                .get("organizedGroups", {})
                .get("edges", [])
            )
            groups = [edge["node"] for edge in edges if "node" in edge]
            return ActionResult(data={"result": True, "groups": groups}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("get_group")
class GetGroupAction(ActionHandler):
    """Retrieves details of a specific Meetup group by its urlname."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        urlname = inputs.get("urlname")
        if not urlname:
            return ActionResult(data={"result": False, "error": "urlname is required"}, cost_usd=0.0)
        try:
            response = await _gql(context, GET_GROUP_QUERY, {"urlname": urlname})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            group = response.get("data", {}).get("groupByUrlname")
            return ActionResult(data={"result": True, "group": group}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


# ============================================================================
# Event Actions
# ============================================================================


@meetup.action("list_events")
class ListEventsAction(ActionHandler):
    """Lists events for a Meetup group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        urlname = inputs.get("urlname")
        if not urlname:
            return ActionResult(data={"result": False, "error": "urlname is required"}, cost_usd=0.0)
        try:
            variables = {
                "urlname": urlname,
                "first": inputs.get("first", 20),
                "past": inputs.get("past", False),
            }
            response = await _gql(context, LIST_EVENTS_QUERY, variables)
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            edges = (
                response.get("data", {})
                .get("groupByUrlname", {})
                .get("events", {})
                .get("edges", [])
            )
            events = [edge["node"] for edge in edges if "node" in edge]
            return ActionResult(data={"result": True, "events": events}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("get_event")
class GetEventAction(ActionHandler):
    """Retrieves details of a specific Meetup event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        if not event_id:
            return ActionResult(data={"result": False, "error": "event_id is required"}, cost_usd=0.0)
        try:
            response = await _gql(context, GET_EVENT_QUERY, {"eventId": event_id})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            event = response.get("data", {}).get("event")
            return ActionResult(data={"result": True, "event": event}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("create_event")
class CreateEventAction(ActionHandler):
    """Creates a new event (as a draft) in a Meetup group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        group_urlname = inputs.get("group_urlname")
        title = inputs.get("title")
        start_date_time = inputs.get("start_date_time")
        duration = inputs.get("duration")

        if not group_urlname:
            return ActionResult(data={"result": False, "error": "group_urlname is required"}, cost_usd=0.0)
        if not title:
            return ActionResult(data={"result": False, "error": "title is required"}, cost_usd=0.0)
        if not start_date_time:
            return ActionResult(data={"result": False, "error": "start_date_time is required"}, cost_usd=0.0)
        if duration is None:
            return ActionResult(data={"result": False, "error": "duration is required"}, cost_usd=0.0)

        try:
            event_input: Dict[str, Any] = {
                "groupUrlname": group_urlname,
                "title": title,
                "startDateTime": start_date_time,
                "duration": duration * 60,  # API expects seconds
            }
            if inputs.get("description"):
                event_input["description"] = inputs["description"]
            if inputs.get("venue_id"):
                event_input["venueId"] = inputs["venue_id"]
            if inputs.get("how_to_find_us"):
                event_input["howToFindUs"] = inputs["how_to_find_us"]
            if inputs.get("is_online") is not None:
                event_input["isOnline"] = inputs["is_online"]

            response = await _gql(context, CREATE_EVENT_MUTATION, {"input": event_input})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            event = response.get("data", {}).get("createEvent", {}).get("event")
            return ActionResult(data={"result": True, "event": event}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("update_event")
class UpdateEventAction(ActionHandler):
    """Updates an existing Meetup event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        if not event_id:
            return ActionResult(data={"result": False, "error": "event_id is required"}, cost_usd=0.0)
        try:
            event_input: Dict[str, Any] = {"eventId": event_id}
            if inputs.get("title"):
                event_input["title"] = inputs["title"]
            if inputs.get("description"):
                event_input["description"] = inputs["description"]
            if inputs.get("start_date_time"):
                event_input["startDateTime"] = inputs["start_date_time"]
            if inputs.get("duration") is not None:
                event_input["duration"] = inputs["duration"] * 60
            if inputs.get("venue_id"):
                event_input["venueId"] = inputs["venue_id"]
            if inputs.get("how_to_find_us"):
                event_input["howToFindUs"] = inputs["how_to_find_us"]
            if inputs.get("is_online") is not None:
                event_input["isOnline"] = inputs["is_online"]

            response = await _gql(context, UPDATE_EVENT_MUTATION, {"input": event_input})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            event = response.get("data", {}).get("editEvent", {}).get("event")
            return ActionResult(data={"result": True, "event": event}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("delete_event")
class DeleteEventAction(ActionHandler):
    """Deletes (cancels) a Meetup event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        if not event_id:
            return ActionResult(data={"result": False, "error": "event_id is required"}, cost_usd=0.0)
        try:
            response = await _gql(context, DELETE_EVENT_MUTATION, {"input": {"eventId": event_id}})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            return ActionResult(data={"result": True}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)


@meetup.action("publish_event")
class PublishEventAction(ActionHandler):
    """Publishes a draft Meetup event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        event_id = inputs.get("event_id")
        if not event_id:
            return ActionResult(data={"result": False, "error": "event_id is required"}, cost_usd=0.0)
        try:
            response = await _gql(context, PUBLISH_EVENT_MUTATION, {"input": {"eventId": event_id}})
            err = extract_gql_errors(response)
            if err:
                return ActionResult(data={"result": False, "error": err}, cost_usd=0.0)
            event = response.get("data", {}).get("publishEvent", {}).get("event")
            return ActionResult(data={"result": True, "event": event}, cost_usd=0.0)
        except Exception as e:
            return ActionResult(data={"result": False, "error": str(e)}, cost_usd=0.0)
