from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult
from typing import Dict, Any, List
from datetime import datetime, timedelta
import requests
from icalendar import Calendar
import pytz
import re

webcal = Integration.load()


class WebCalendarAPI:
    """Helper class for WebCalendar API operations"""

    @staticmethod
    async def fetch_calendar(context: ExecutionContext, webcal_url: str) -> Calendar:
        """Fetch and parse a webcal URL into a Calendar object"""
        url = webcal_url.replace("webcal://", "https://")

        # Fetch the calendar data
        response = await context.fetch(url)

        # Parse the iCal data
        return Calendar.from_ical(response)

    @staticmethod
    def convert_to_timezone(dt, timezone_str: str):
        """Convert a datetime object to the specified timezone."""
        # Make sure the datetime is timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.utc)

        # Convert to the target timezone
        target_tz = pytz.timezone(timezone_str)
        return dt.astimezone(target_tz)

    @staticmethod
    def extract_event_data(component, timezone_str: str) -> Dict[str, Any]:
        """Extract relevant data from a calendar event component"""
        # Extract start time
        event_start = component.get('dtstart').dt

        # Determine if this is an all-day event
        all_day = False
        if not isinstance(event_start, datetime):
            # It's a date without time (all-day event)
            all_day = True
            # Convert to datetime at midnight
            event_start = datetime.combine(event_start, datetime.min.time())
            event_start = pytz.utc.localize(event_start)
        elif event_start.tzinfo is None:
            # Make naive datetime timezone-aware (assume UTC)
            event_start = event_start.replace(tzinfo=pytz.utc)

        # Extract end time
        if component.get('dtend'):
            event_end = component.get('dtend').dt
            if not isinstance(event_end, datetime):
                # Convert to datetime at midnight
                event_end = datetime.combine(event_end, datetime.min.time())
                event_end = pytz.utc.localize(event_end)
            elif event_end.tzinfo is None:
                # Make naive datetime timezone-aware (assume UTC)
                event_end = event_end.replace(tzinfo=pytz.utc)
        else:
            # If no end time, assume it's the same as start time
            event_end = event_start

        # Convert times to the requested timezone
        event_start_local = WebCalendarAPI.convert_to_timezone(event_start, timezone_str)
        event_end_local = WebCalendarAPI.convert_to_timezone(event_end, timezone_str)

        # Extract attendees if present
        attendees = []
        if component.get('attendee'):
            attendees_raw = component.get('attendee')
            if isinstance(attendees_raw, list):
                for attendee in attendees_raw:
                    attendees.append(str(attendee))
            else:
                attendees.append(str(attendees_raw))

        # Extract organizer if present
        organizer = None
        if component.get('organizer'):
            organizer = str(component.get('organizer'))

        # Extract URL if present
        url = None
        if component.get('url'):
            url = str(component.get('url'))

        # Check if the event is recurring
        recurring = bool(component.get('rrule'))

        # Format the times as strings
        start_time_str = event_start_local.strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = event_end_local.strftime('%Y-%m-%d %H:%M:%S')

        return {
            'summary': str(component.get('summary', '')),
            'description': str(component.get('description', '')) if component.get('description') else None,
            'location': str(component.get('location', '')) if component.get('location') else None,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'all_day': all_day,
            'organizer': organizer,
            'attendees': attendees,
            'url': url,
            'recurring': recurring
        }


@webcal.action("fetch_events")
class FetchEvents(ActionHandler):
    """
    Action that fetches events from a webcal URL within a specified time range.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webcal_url = inputs['webcal_url']
        timezone_str = inputs.get('timezone', 'UTC')
        look_ahead_days = inputs.get('look_ahead_days', 7)

        # Fetch the calendar
        cal = await WebCalendarAPI.fetch_calendar(context, webcal_url)

        # Define the local timezone
        local_timezone = pytz.timezone(timezone_str)

        # Get the current date and the date `look_ahead_days` from now in UTC
        utc_now = datetime.now(pytz.utc)
        utc_look_ahead = utc_now + timedelta(days=look_ahead_days)

        # Convert the current date and look ahead date to the local timezone
        now = WebCalendarAPI.convert_to_timezone(utc_now, timezone_str)
        look_ahead_date = WebCalendarAPI.convert_to_timezone(utc_look_ahead, timezone_str)

        # Extract events happening in the specified range or ongoing
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_start = component.get('dtstart').dt

                # Handle all-day events
                if not isinstance(event_start, datetime):
                    # It's a date without time (all-day event)
                    event_start = datetime.combine(event_start, datetime.min.time())
                    event_start = pytz.utc.localize(event_start)
                elif event_start.tzinfo is None:
                    # Make naive datetime timezone-aware (assume UTC)
                    event_start = event_start.replace(tzinfo=pytz.utc)

                # Get end time
                if component.get('dtend'):
                    event_end = component.get('dtend').dt
                    if not isinstance(event_end, datetime):
                        # Convert to datetime
                        event_end = datetime.combine(event_end, datetime.min.time())
                        event_end = pytz.utc.localize(event_end)
                    elif event_end.tzinfo is None:
                        # Make naive datetime timezone-aware (assume UTC)
                        event_end = event_end.replace(tzinfo=pytz.utc)
                else:
                    # If no end time, assume it's the same as start time
                    event_end = event_start

                # Convert event times to the local timezone
                event_start_local = WebCalendarAPI.convert_to_timezone(event_start, timezone_str)
                event_end_local = WebCalendarAPI.convert_to_timezone(event_end, timezone_str)

                # Check if the event is within the desired time range or ongoing
                if (now <= event_start_local < look_ahead_date) or (event_start_local < now <= event_end_local):
                    # Extract the event data
                    event_data = WebCalendarAPI.extract_event_data(component, timezone_str)
                    events.append(event_data)

        # Return the events
        return ActionResult(
            data={
                'timezone': timezone_str,
                'events': events,
                'result': True
            },
            cost_usd=0.0
        )


@webcal.action("search_events")
class SearchEvents(ActionHandler):
    """
    Action that searches for specific events in a webcal feed based on keywords.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        webcal_url = inputs['webcal_url']
        search_term = inputs['search_term']
        timezone_str = inputs.get('timezone', 'UTC')
        look_ahead_days = inputs.get('look_ahead_days', 30)
        case_sensitive = inputs.get('case_sensitive', False)

        # Fetch the calendar
        cal = await WebCalendarAPI.fetch_calendar(context, webcal_url)

        # Define the local timezone
        local_timezone = pytz.timezone(timezone_str)

        # Get the current date and the date `look_ahead_days` from now in UTC
        utc_now = datetime.now(pytz.utc)
        utc_look_ahead = utc_now + timedelta(days=look_ahead_days)

        # Convert the current date and look ahead date to the local timezone
        now = WebCalendarAPI.convert_to_timezone(utc_now, timezone_str)
        look_ahead_date = WebCalendarAPI.convert_to_timezone(utc_look_ahead, timezone_str)

        # Prepare search term for case-insensitive search if needed
        if not case_sensitive:
            search_pattern = re.compile(re.escape(search_term), re.IGNORECASE)
        else:
            search_pattern = re.compile(re.escape(search_term))

        # Search for events matching the criteria
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_start = component.get('dtstart').dt

                # Handle all-day events
                if not isinstance(event_start, datetime):
                    # It's a date without time (all-day event)
                    event_start = datetime.combine(event_start, datetime.min.time())
                    event_start = pytz.utc.localize(event_start)
                elif event_start.tzinfo is None:
                    # Make naive datetime timezone-aware (assume UTC)
                    event_start = event_start.replace(tzinfo=pytz.utc)

                # Get end time
                if component.get('dtend'):
                    event_end = component.get('dtend').dt
                    if not isinstance(event_end, datetime):
                        # Convert to datetime
                        event_end = datetime.combine(event_end, datetime.min.time())
                        event_end = pytz.utc.localize(event_end)
                    elif event_end.tzinfo is None:
                        # Make naive datetime timezone-aware (assume UTC)
                        event_end = event_end.replace(tzinfo=pytz.utc)
                else:
                    # If no end time, assume it's the same as start time
                    event_end = event_start

                # Convert event times to the local timezone
                event_start_local = WebCalendarAPI.convert_to_timezone(event_start, timezone_str)
                event_end_local = WebCalendarAPI.convert_to_timezone(event_end, timezone_str)

                # Check if the event is within the desired time range or ongoing
                if (now <= event_start_local < look_ahead_date) or (event_start_local < now <= event_end_local):
                    # Extract fields to search in
                    summary = str(component.get('summary', ''))
                    description = str(component.get('description', '')) if component.get('description') else ''
                    location = str(component.get('location', '')) if component.get('location') else ''

                    # Search for the term in each field
                    match_field = None
                    if search_pattern.search(summary):
                        match_field = 'summary'
                    elif search_pattern.search(description):
                        match_field = 'description'
                    elif search_pattern.search(location):
                        match_field = 'location'

                    # If there's a match, add to results
                    if match_field:
                        # Get the event data
                        event_data = WebCalendarAPI.extract_event_data(component, timezone_str)
                        # Add the field where match was found
                        event_data['match_field'] = match_field
                        events.append(event_data)

        # Return the search results
        return ActionResult(
            data={
                'timezone': timezone_str,
                'search_term': search_term,
                'events': events,
                'result': True
            },
            cost_usd=0.0
        )
