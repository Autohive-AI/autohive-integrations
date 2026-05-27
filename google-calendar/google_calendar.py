from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
    FetchResponse,
)
from typing import Dict, Any

# Create the integration using the config.json
google_calendar = Integration.load()
service_endpoint = "https://www.googleapis.com/calendar/v3/"


def _unwrap(response: FetchResponse) -> Dict:
    """Raise RuntimeError on non-2xx; otherwise return response body as a dict."""
    if response.status < 200 or response.status >= 300:
        body = response.data
        if isinstance(body, dict):
            msg = body.get("message") or body.get("error") or str(body)
        elif isinstance(body, str) and body.strip():
            msg = body.strip()
        else:
            msg = f"Google Calendar API returned HTTP {response.status}"
        raise RuntimeError(msg)
    return response.data or {}


class CalendarEventParser:
    @staticmethod
    def parse_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "id": raw_event.get("id", ""),
            "summary": raw_event.get("summary", ""),
        }
        for field in (
            "description",
            "location",
            "start",
            "end",
            "attendees",
            "created",
            "updated",
            "htmlLink",
            "recurringEventId",
            "originalStartTime",
        ):
            if field in raw_event:
                event[field] = raw_event[field]
        return event

    @staticmethod
    def parse_calendar(raw_calendar: Dict[str, Any]) -> Dict[str, Any]:
        calendar_data = {
            "id": raw_calendar.get("id", ""),
            "summary": raw_calendar.get("summary", ""),
        }
        for field in ("description", "primary", "accessRole"):
            if field in raw_calendar:
                calendar_data[field] = raw_calendar[field]
        return calendar_data


# ---- Action Handlers ----


@google_calendar.action("list_calendars")
class ListCalendars(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(service_endpoint + "users/me/calendarList", method="GET")
            data = _unwrap(response)

            calendars = [CalendarEventParser.parse_calendar(c) for c in data.get("items", [])]
            return ActionResult(data={"calendars": calendars})

        except Exception as e:
            return ActionError(message=str(e))


@google_calendar.action("list_events")
class ListEvents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            calendar_id = inputs["calendar_id"]

            params: Dict[str, Any] = {
                # Expand recurring event instances so each occurrence is returned individually
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            if inputs.get("time_min") is not None:
                params["timeMin"] = inputs["time_min"]
            if inputs.get("time_max") is not None:
                params["timeMax"] = inputs["time_max"]
            if inputs.get("max_results") is not None:
                params["maxResults"] = inputs["max_results"]
            if inputs.get("page_token") is not None:
                params["pageToken"] = inputs["page_token"]
            if inputs.get("query") is not None:
                params["q"] = inputs["query"]

            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events", method="GET", params=params
            )
            data = _unwrap(response)

            events = [CalendarEventParser.parse_event(e) for e in data.get("items", [])]
            result: Dict[str, Any] = {"events": events}
            if "nextPageToken" in data:
                result["nextPageToken"] = data["nextPageToken"]

            return ActionResult(data=result)

        except Exception as e:
            return ActionError(message=str(e))


@google_calendar.action("get_event")
class GetEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            calendar_id = inputs["calendar_id"]
            event_id = inputs["event_id"]

            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}", method="GET"
            )
            data = _unwrap(response)

            return ActionResult(data={"event": CalendarEventParser.parse_event(data)})

        except Exception as e:
            return ActionError(message=str(e))


@google_calendar.action("create_event")
class CreateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            calendar_id = inputs["calendar_id"]

            event_data: Dict[str, Any] = {"summary": inputs["summary"]}

            if inputs.get("description") is not None:
                event_data["description"] = inputs["description"]
            if inputs.get("location") is not None:
                event_data["location"] = inputs["location"]

            if inputs.get("start_datetime") is not None and inputs.get("end_datetime") is not None:
                timezone = inputs.get("timezone", "UTC")
                event_data["start"] = {"dateTime": inputs["start_datetime"], "timeZone": timezone}
                event_data["end"] = {"dateTime": inputs["end_datetime"], "timeZone": timezone}
            elif inputs.get("start_date") is not None and inputs.get("end_date") is not None:
                event_data["start"] = {"date": inputs["start_date"]}
                event_data["end"] = {"date": inputs["end_date"]}

            if inputs.get("attendees"):
                event_data["attendees"] = [{"email": email} for email in inputs["attendees"]]

            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events", method="POST", json=event_data
            )
            data = _unwrap(response)

            return ActionResult(data={"event": CalendarEventParser.parse_event(data)})

        except Exception as e:
            return ActionError(message=str(e))


@google_calendar.action("update_event")
class UpdateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            calendar_id = inputs["calendar_id"]
            event_id = inputs["event_id"]

            # Fetch existing event first to preserve unmodified fields
            existing_response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}", method="GET"
            )
            event_data = dict(_unwrap(existing_response))

            if inputs.get("summary") is not None:
                event_data["summary"] = inputs["summary"]
            if inputs.get("description") is not None:
                event_data["description"] = inputs["description"]
            if inputs.get("location") is not None:
                event_data["location"] = inputs["location"]

            if inputs.get("start_datetime") is not None and inputs.get("end_datetime") is not None:
                timezone = inputs.get("timezone", event_data.get("start", {}).get("timeZone", "UTC"))
                event_data["start"] = {"dateTime": inputs["start_datetime"], "timeZone": timezone}
                event_data["end"] = {"dateTime": inputs["end_datetime"], "timeZone": timezone}
            elif inputs.get("start_date") is not None and inputs.get("end_date") is not None:
                event_data["start"] = {"date": inputs["start_date"]}
                event_data["end"] = {"date": inputs["end_date"]}

            if "attendees" in inputs:
                if inputs.get("attendees"):
                    event_data["attendees"] = [{"email": email} for email in inputs["attendees"]]
                else:
                    event_data.pop("attendees", None)

            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}", method="PUT", json=event_data
            )
            data = _unwrap(response)

            return ActionResult(data={"event": CalendarEventParser.parse_event(data)})

        except Exception as e:
            return ActionError(message=str(e))


@google_calendar.action("delete_event")
class DeleteEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            calendar_id = inputs["calendar_id"]
            event_id = inputs["event_id"]

            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}", method="DELETE"
            )
            # DELETE returns 204 No Content on success
            if response.status not in (200, 204):
                body = response.data
                msg = (body.get("message") or body.get("error") or str(body)) if isinstance(body, dict) else str(body)
                raise RuntimeError(msg)

            return ActionResult(data={"deleted": True})

        except Exception as e:
            return ActionError(message=str(e))


# ---- Polling Trigger Handlers ----
