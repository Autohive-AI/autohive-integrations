from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, PollingTriggerHandler
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
google_calendar = Integration.load()
service_endpoint = "https://www.googleapis.com/calendar/v3/"

class CalendarEventParser:
    @staticmethod
    def parse_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Google Calendar event into standardized format."""
        event = {
            "id": raw_event.get('id', ''),
            "summary": raw_event.get('summary', ''),
        }
        
        # Add optional fields if they exist
        if 'description' in raw_event:
            event['description'] = raw_event['description']
        if 'location' in raw_event:
            event['location'] = raw_event['location']
        if 'start' in raw_event:
            event['start'] = raw_event['start']
        if 'end' in raw_event:
            event['end'] = raw_event['end']
        if 'attendees' in raw_event:
            event['attendees'] = raw_event['attendees']
        if 'created' in raw_event:
            event['created'] = raw_event['created']
        if 'updated' in raw_event:
            event['updated'] = raw_event['updated']
        if 'htmlLink' in raw_event:
            event['htmlLink'] = raw_event['htmlLink']
            
        return event

    @staticmethod
    def parse_calendar(raw_calendar: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Google Calendar into standardized format."""
        calendar_data = {
            "id": raw_calendar.get('id', ''),
            "summary": raw_calendar.get('summary', ''),
        }
        
        # Add optional fields if they exist
        if 'description' in raw_calendar:
            calendar_data['description'] = raw_calendar['description']
        if 'primary' in raw_calendar:
            calendar_data['primary'] = raw_calendar['primary']
        if 'accessRole' in raw_calendar:
            calendar_data['accessRole'] = raw_calendar['accessRole']
            
        return calendar_data

# ---- Action Handlers ----

@google_calendar.action("list_calendars")
class ListCalendars(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                service_endpoint + "users/me/calendarList",
                method="GET"
            )
            
            calendars = []
            for raw_calendar in response.get('items', []):
                calendars.append(CalendarEventParser.parse_calendar(raw_calendar))
            
            return {
                "calendars": calendars,
                "result": True
            }
            
        except Exception as e:
            return {
                "calendars": [],
                "result": False,
                "error": str(e)
            }

@google_calendar.action("list_events")
class ListEvents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            calendar_id = inputs['calendar_id']
            
            # Build query parameters
            params = {}
            if 'time_min' in inputs:
                params['timeMin'] = inputs['time_min']
            if 'time_max' in inputs:
                params['timeMax'] = inputs['time_max']
            if 'max_results' in inputs:
                params['maxResults'] = inputs['max_results']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']
            
            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events",
                method="GET",
                params=params
            )
            
            events = []
            for raw_event in response.get('items', []):
                events.append(CalendarEventParser.parse_event(raw_event))
            
            # Prepare response with pagination support
            result = {
                "events": events,
                "result": True
            }
            
            # Add nextPageToken if present
            if 'nextPageToken' in response:
                result['nextPageToken'] = response['nextPageToken']
            
            return result
            
        except Exception as e:
            return {
                "events": [],
                "result": False,
                "error": str(e)
            }

@google_calendar.action("get_event")
class GetEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            calendar_id = inputs['calendar_id']
            event_id = inputs['event_id']
            
            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}",
                method="GET"
            )
            
            return {
                "event": CalendarEventParser.parse_event(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "event": {},
                "result": False,
                "error": str(e)
            }

@google_calendar.action("create_event")
class CreateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            calendar_id = inputs['calendar_id']
            
            # Build event data
            event_data = {
                "summary": inputs['summary']
            }
            
            # Add optional fields
            if 'description' in inputs:
                event_data['description'] = inputs['description']
            if 'location' in inputs:
                event_data['location'] = inputs['location']
            
            # Handle start/end times
            if 'start_datetime' in inputs and 'end_datetime' in inputs:
                event_data['start'] = {'dateTime': inputs['start_datetime']}
                event_data['end'] = {'dateTime': inputs['end_datetime']}
            elif 'start_date' in inputs and 'end_date' in inputs:
                event_data['start'] = {'date': inputs['start_date']}
                event_data['end'] = {'date': inputs['end_date']}
            
            # Handle attendees
            if 'attendees' in inputs and inputs['attendees']:
                event_data['attendees'] = [{'email': email} for email in inputs['attendees']]
            
            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events",
                method="POST",
                json=event_data
            )
            
            return {
                "event": CalendarEventParser.parse_event(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "event": {},
                "result": False,
                "error": str(e)
            }

@google_calendar.action("update_event")
class UpdateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            calendar_id = inputs['calendar_id']
            event_id = inputs['event_id']
            
            # First, get the existing event to preserve fields not being updated
            existing_event = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}",
                method="GET"
            )
            
            # Build updated event data, starting with existing event
            event_data = existing_event.copy()
            
            # Update fields that were provided in inputs
            if 'summary' in inputs:
                event_data['summary'] = inputs['summary']
            if 'description' in inputs:
                event_data['description'] = inputs['description']
            if 'location' in inputs:
                event_data['location'] = inputs['location']
            
            # Handle start/end times
            if 'start_datetime' in inputs and 'end_datetime' in inputs:
                event_data['start'] = {'dateTime': inputs['start_datetime']}
                event_data['end'] = {'dateTime': inputs['end_datetime']}
            elif 'start_date' in inputs and 'end_date' in inputs:
                event_data['start'] = {'date': inputs['start_date']}
                event_data['end'] = {'date': inputs['end_date']}
            
            # Handle attendees
            if 'attendees' in inputs:
                if inputs['attendees']:
                    event_data['attendees'] = [{'email': email} for email in inputs['attendees']]
                else:
                    # Remove attendees if empty list is provided
                    event_data.pop('attendees', None)
            
            response = await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}",
                method="PUT",
                json=event_data
            )
            
            return {
                "event": CalendarEventParser.parse_event(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "event": {},
                "result": False,
                "error": str(e)
            }

@google_calendar.action("delete_event")
class DeleteEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            calendar_id = inputs['calendar_id']
            event_id = inputs['event_id']
            
            await context.fetch(
                service_endpoint + f"calendars/{calendar_id}/events/{event_id}",
                method="DELETE"
            )
            
            return {
                "result": True
            }
            
        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }

# ---- Polling Trigger Handlers ----


