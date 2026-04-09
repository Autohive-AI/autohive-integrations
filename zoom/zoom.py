from autohive_integrations_sdk import Integration,ExecutionContext,ActionHandler,ActionResult,ConnectedAccountHandler, ConnectedAccountInfo
from typing import Dict, Any, Optional
from urllib.parse import quote

# Load integration from config.json
zoom = Integration.load()

# ---- Constants ----
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"

# ---- Helper Functions ----

def get_headers() -> Dict[str, str]:
    """Build standard headers for Zoom API requests."""
    return {
        "Content-Type": "application/json"
    }


def encode_meeting_id(meeting_id: str) -> str:
    """
    Encode meeting ID for URL path.
    UUIDs starting with '/' or containing '//' need double URL encoding.
    """
    if meeting_id.startswith('/') or '//' in meeting_id:
        return quote(quote(meeting_id, safe=''), safe='')
    return meeting_id


# ---- API Client Class ----

class ZoomAPIClient:
    """Client for interacting with the Zoom API."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.base_url = ZOOM_API_BASE_URL

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Zoom API.

        Args:
            endpoint: API endpoint path (without base URL)
            method: HTTP method (GET, POST, PATCH, DELETE)
            params: Query parameters
            data: Request body for POST/PATCH requests

        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}/{endpoint}"
        headers = get_headers()

        if method == "GET":
            return await self.context.fetch(url, params=params, headers=headers)
        elif method == "POST":
            return await self.context.fetch(url, method="POST", json=data, headers=headers)
        elif method == "PATCH":
            return await self.context.fetch(url, method="PATCH", json=data, headers=headers)
        elif method == "DELETE":
            response = await self.context.fetch(url, method="DELETE", params=params, headers=headers)
            # DELETE typically returns empty response on success
            return response if response else {"success": True}
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")


# ---- Connected Account Handler ----

@zoom.connected_account()
class ZoomConnectedAccountHandler(ConnectedAccountHandler):
    """Handler to fetch connected Zoom account information."""

    async def get_account_info(self, context: ExecutionContext) -> ConnectedAccountInfo:
        """
        Fetch Zoom user information for the connected account.

        Args:
            context: ExecutionContext containing auth credentials

        Returns:
            ConnectedAccountInfo with user information
        """
        client = ZoomAPIClient(context)

        # Fetch current user info from Zoom API
        user_data = await client._make_request("users/me")

        # Parse name into first/last
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")

        return ConnectedAccountInfo(
            email=user_data.get("email"),
            username=user_data.get("display_name") or f"{first_name} {last_name}".strip(),
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            avatar_url=user_data.get("pic_url"),
            organization=user_data.get("company") or user_data.get("dept"),
            user_id=user_data.get("id")
        )


# ---- Action Handlers ----

@zoom.action("list_meetings")
class ListMeetingsAction(ActionHandler):
    """List all scheduled meetings for a user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")

            params = {
                "type": inputs.get("type", "scheduled"),
                "page_size": min(inputs.get("page_size", 30), 300)
            }

            if inputs.get("next_page_token"):
                params["next_page_token"] = inputs["next_page_token"]

            response = await client._make_request(f"users/{user_id}/meetings", params=params)

            # Transform meetings to consistent format
            meetings = []
            for meeting in response.get("meetings", []):
                meetings.append({
                    "id": meeting.get("id"),
                    "uuid": meeting.get("uuid", ""),
                    "topic": meeting.get("topic", ""),
                    "type": meeting.get("type"),
                    "start_time": meeting.get("start_time", ""),
                    "duration": meeting.get("duration", 0),
                    "timezone": meeting.get("timezone", ""),
                    "join_url": meeting.get("join_url", ""),
                    "created_at": meeting.get("created_at", "")
                })

            return ActionResult(
                data={
                    "meetings": meetings,
                    "next_page_token": response.get("next_page_token"),
                    "page_count": response.get("page_count", 0),
                    "page_size": response.get("page_size", 0),
                    "total_records": response.get("total_records", len(meetings)),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "meetings": [],
                    "next_page_token": None,
                    "page_count": 0,
                    "page_size": 0,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_meeting")
class GetMeetingAction(ActionHandler):
    """Retrieve detailed information about a specific meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            response = await client._make_request(f"meetings/{meeting_id}")

            return ActionResult(
                data={
                    "id": response.get("id"),
                    "uuid": response.get("uuid", ""),
                    "topic": response.get("topic", ""),
                    "type": response.get("type"),
                    "status": response.get("status", ""),
                    "start_time": response.get("start_time", ""),
                    "duration": response.get("duration", 0),
                    "timezone": response.get("timezone", ""),
                    "agenda": response.get("agenda", ""),
                    "created_at": response.get("created_at", ""),
                    "start_url": response.get("start_url", ""),
                    "join_url": response.get("join_url", ""),
                    "password": response.get("password", ""),
                    "host_id": response.get("host_id", ""),
                    "host_email": response.get("host_email", ""),
                    "settings": response.get("settings", {}),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": None,
                    "uuid": "",
                    "topic": "",
                    "type": None,
                    "status": "",
                    "start_time": "",
                    "duration": 0,
                    "timezone": "",
                    "agenda": "",
                    "created_at": "",
                    "start_url": "",
                    "join_url": "",
                    "password": "",
                    "host_id": "",
                    "host_email": "",
                    "settings": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("create_meeting")
class CreateMeetingAction(ActionHandler):
    """Create a new Zoom meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")

            # Build meeting data
            meeting_data = {
                "topic": inputs["topic"],
                "type": inputs.get("type", 2),  # Default to scheduled meeting
                "duration": inputs.get("duration", 60)
            }

            # Add optional fields
            if inputs.get("start_time"):
                meeting_data["start_time"] = inputs["start_time"]

            if inputs.get("timezone"):
                meeting_data["timezone"] = inputs["timezone"]

            if inputs.get("password"):
                meeting_data["password"] = inputs["password"]

            if inputs.get("agenda"):
                meeting_data["agenda"] = inputs["agenda"]

            # Build settings
            settings = {}
            if "waiting_room" in inputs:
                settings["waiting_room"] = inputs["waiting_room"]
            if "join_before_host" in inputs:
                settings["join_before_host"] = inputs["join_before_host"]
            if "mute_upon_entry" in inputs:
                settings["mute_upon_entry"] = inputs["mute_upon_entry"]
            if inputs.get("auto_recording"):
                settings["auto_recording"] = inputs["auto_recording"]

            if settings:
                meeting_data["settings"] = settings

            response = await client._make_request(
                f"users/{user_id}/meetings",
                method="POST",
                data=meeting_data
            )

            return ActionResult(
                data={
                    "id": response.get("id"),
                    "uuid": response.get("uuid", ""),
                    "topic": response.get("topic", ""),
                    "start_time": response.get("start_time", ""),
                    "duration": response.get("duration", 0),
                    "start_url": response.get("start_url", ""),
                    "join_url": response.get("join_url", ""),
                    "password": response.get("password", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": None,
                    "uuid": "",
                    "topic": "",
                    "start_time": "",
                    "duration": 0,
                    "start_url": "",
                    "join_url": "",
                    "password": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("update_meeting")
class UpdateMeetingAction(ActionHandler):
    """Update an existing meeting's details."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            # Build update data
            update_data = {}

            if inputs.get("topic"):
                update_data["topic"] = inputs["topic"]
            if inputs.get("start_time"):
                update_data["start_time"] = inputs["start_time"]
            if inputs.get("duration"):
                update_data["duration"] = inputs["duration"]
            if inputs.get("timezone"):
                update_data["timezone"] = inputs["timezone"]
            if inputs.get("password"):
                update_data["password"] = inputs["password"]
            if inputs.get("agenda"):
                update_data["agenda"] = inputs["agenda"]

            # Build settings updates
            settings = {}
            if "waiting_room" in inputs:
                settings["waiting_room"] = inputs["waiting_room"]
            if "join_before_host" in inputs:
                settings["join_before_host"] = inputs["join_before_host"]
            if "mute_upon_entry" in inputs:
                settings["mute_upon_entry"] = inputs["mute_upon_entry"]
            if inputs.get("auto_recording"):
                settings["auto_recording"] = inputs["auto_recording"]

            if settings:
                update_data["settings"] = settings

            await client._make_request(
                f"meetings/{meeting_id}",
                method="PATCH",
                data=update_data
            )

            return ActionResult(
                data={
                    "meeting_id": inputs["meeting_id"],
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "meeting_id": inputs["meeting_id"],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("delete_meeting")
class DeleteMeetingAction(ActionHandler):
    """Delete a scheduled meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            params = {}
            if inputs.get("occurrence_id"):
                params["occurrence_id"] = inputs["occurrence_id"]
            if "schedule_for_reminder" in inputs:
                params["schedule_for_reminder"] = inputs["schedule_for_reminder"]

            await client._make_request(
                f"meetings/{meeting_id}",
                method="DELETE",
                params=params if params else None
            )

            return ActionResult(
                data={
                    "meeting_id": inputs["meeting_id"],
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "meeting_id": inputs["meeting_id"],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_user")
class GetUserAction(ActionHandler):
    """Get detailed information about a specific user."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")

            response = await client._make_request(f"users/{user_id}")

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "first_name": response.get("first_name", ""),
                    "last_name": response.get("last_name", ""),
                    "email": response.get("email", ""),
                    "type": response.get("type"),
                    "role_name": response.get("role_name", ""),
                    "pmi": response.get("pmi"),
                    "use_pmi": response.get("use_pmi", False),
                    "timezone": response.get("timezone", ""),
                    "dept": response.get("dept", ""),
                    "created_at": response.get("created_at", ""),
                    "last_login_time": response.get("last_login_time", ""),
                    "pic_url": response.get("pic_url", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "first_name": "",
                    "last_name": "",
                    "email": "",
                    "type": None,
                    "role_name": "",
                    "pmi": None,
                    "use_pmi": False,
                    "timezone": "",
                    "dept": "",
                    "created_at": "",
                    "last_login_time": "",
                    "pic_url": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_meeting_participants")
class GetMeetingParticipantsAction(ActionHandler):
    """Get the list of participants who attended a past meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            params = {
                "page_size": min(inputs.get("page_size", 30), 300)
            }

            if inputs.get("next_page_token"):
                params["next_page_token"] = inputs["next_page_token"]

            # Use past meetings endpoint for participants
            response = await client._make_request(
                f"past_meetings/{meeting_id}/participants",
                params=params
            )

            # Transform participants
            participants = []
            for participant in response.get("participants", []):
                participants.append({
                    "id": participant.get("id", ""),
                    "user_id": participant.get("user_id", ""),
                    "name": participant.get("name", ""),
                    "user_email": participant.get("user_email", ""),
                    "join_time": participant.get("join_time", ""),
                    "leave_time": participant.get("leave_time", ""),
                    "duration": participant.get("duration", 0),
                    "attentiveness_score": participant.get("attentiveness_score", "")
                })

            return ActionResult(
                data={
                    "participants": participants,
                    "next_page_token": response.get("next_page_token"),
                    "page_count": response.get("page_count", 0),
                    "page_size": response.get("page_size", 0),
                    "total_records": response.get("total_records", len(participants)),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "participants": [],
                    "next_page_token": None,
                    "page_count": 0,
                    "page_size": 0,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("add_meeting_registrant")
class AddMeetingRegistrantAction(ActionHandler):
    """Register a participant for a scheduled meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            registrant_data = {
                "email": inputs["email"],
                "first_name": inputs["first_name"]
            }

            if inputs.get("last_name"):
                registrant_data["last_name"] = inputs["last_name"]

            response = await client._make_request(
                f"meetings/{meeting_id}/registrants",
                method="POST",
                data=registrant_data
            )

            return ActionResult(
                data={
                    "registrant_id": response.get("registrant_id", ""),
                    "id": response.get("id"),
                    "topic": response.get("topic", ""),
                    "start_time": response.get("start_time", ""),
                    "join_url": response.get("join_url", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "registrant_id": "",
                    "id": None,
                    "topic": "",
                    "start_time": "",
                    "join_url": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Calendar Action Handlers ----

@zoom.action("create_calendar_event")
class CreateCalendarEventAction(ActionHandler):
    """Create a calendar event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")

            event_data = {
                "summary": inputs["summary"],
                "start": inputs["start"],
                "end": inputs["end"]
            }

            if inputs.get("description"):
                event_data["description"] = inputs["description"]
            if inputs.get("location"):
                event_data["location"] = inputs["location"]
            if inputs.get("timezone"):
                event_data["timezone"] = inputs["timezone"]
            if inputs.get("attendees"):
                event_data["attendees"] = inputs["attendees"]
            if inputs.get("reminders"):
                event_data["reminders"] = inputs["reminders"]

            response = await client._make_request(
                f"calendars/{calendar_id}/events",
                method="POST",
                data=event_data
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "summary": response.get("summary", ""),
                    "start": response.get("start", {}),
                    "end": response.get("end", {}),
                    "location": response.get("location", ""),
                    "description": response.get("description", ""),
                    "html_link": response.get("htmlLink", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "summary": "",
                    "start": {},
                    "end": {},
                    "location": "",
                    "description": "",
                    "html_link": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("delete_calendar_event")
class DeleteCalendarEventAction(ActionHandler):
    """Delete a calendar event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")
            event_id = inputs["event_id"]

            await client._make_request(
                f"calendars/{calendar_id}/events/{event_id}",
                method="DELETE"
            )

            return ActionResult(
                data={
                    "event_id": event_id,
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "event_id": inputs.get("event_id", ""),
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("quick_create_calendar_event")
class QuickCreateCalendarEventAction(ActionHandler):
    """Quick create a calendar event using natural language text."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")

            response = await client._make_request(
                f"calendars/{calendar_id}/events/quickAdd",
                method="POST",
                data={"text": inputs["text"]}
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "summary": response.get("summary", ""),
                    "start": response.get("start", {}),
                    "end": response.get("end", {}),
                    "html_link": response.get("htmlLink", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "summary": "",
                    "start": {},
                    "end": {},
                    "html_link": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("update_calendar_metadata")
class UpdateCalendarMetadataAction(ActionHandler):
    """Update a calendar's metadata."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs["calendar_id"]

            update_data = {}
            if inputs.get("summary"):
                update_data["summary"] = inputs["summary"]
            if inputs.get("description"):
                update_data["description"] = inputs["description"]
            if inputs.get("timezone"):
                update_data["timezone"] = inputs["timezone"]

            response = await client._make_request(
                f"calendars/{calendar_id}",
                method="PATCH",
                data=update_data
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "summary": response.get("summary", ""),
                    "description": response.get("description", ""),
                    "timezone": response.get("timezone", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get("calendar_id", ""),
                    "summary": "",
                    "description": "",
                    "timezone": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("update_calendar_setting")
class UpdateCalendarSettingAction(ActionHandler):
    """Update a calendar setting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            setting_id = inputs["setting_id"]

            update_data = {"value": inputs["value"]}

            response = await client._make_request(
                f"calendars/settings/{setting_id}",
                method="PATCH",
                data=update_data
            )

            return ActionResult(
                data={
                    "id": response.get("id", setting_id),
                    "value": response.get("value", inputs["value"]),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get("setting_id", ""),
                    "value": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_calendar_metadata")
class GetCalendarMetadataAction(ActionHandler):
    """View a calendar's metadata."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")

            response = await client._make_request(f"calendars/{calendar_id}")

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "summary": response.get("summary", ""),
                    "description": response.get("description", ""),
                    "timezone": response.get("timezone", ""),
                    "access_role": response.get("accessRole", ""),
                    "primary": response.get("primary", False),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "summary": "",
                    "description": "",
                    "timezone": "",
                    "access_role": "",
                    "primary": False,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_calendar_setting")
class GetCalendarSettingAction(ActionHandler):
    """View a calendar setting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            setting_id = inputs["setting_id"]

            response = await client._make_request(f"calendars/settings/{setting_id}")

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "value": response.get("value", ""),
                    "etag": response.get("etag", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": inputs.get("setting_id", ""),
                    "value": "",
                    "etag": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_calendar_event")
class GetCalendarEventAction(ActionHandler):
    """View a calendar event."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")
            event_id = inputs["event_id"]

            response = await client._make_request(f"calendars/{calendar_id}/events/{event_id}")

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "summary": response.get("summary", ""),
                    "description": response.get("description", ""),
                    "location": response.get("location", ""),
                    "start": response.get("start", {}),
                    "end": response.get("end", {}),
                    "attendees": response.get("attendees", []),
                    "organizer": response.get("organizer", {}),
                    "status": response.get("status", ""),
                    "html_link": response.get("htmlLink", ""),
                    "created": response.get("created", ""),
                    "updated": response.get("updated", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "summary": "",
                    "description": "",
                    "location": "",
                    "start": {},
                    "end": {},
                    "attendees": [],
                    "organizer": {},
                    "status": "",
                    "html_link": "",
                    "created": "",
                    "updated": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("list_calendar_events")
class ListCalendarEventsAction(ActionHandler):
    """View calendar events."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            calendar_id = inputs.get("calendar_id", "primary")

            params = {
                "maxResults": min(inputs.get("max_results", 50), 2500)
            }

            if inputs.get("time_min"):
                params["timeMin"] = inputs["time_min"]
            if inputs.get("time_max"):
                params["timeMax"] = inputs["time_max"]
            if inputs.get("page_token"):
                params["pageToken"] = inputs["page_token"]
            if inputs.get("q"):
                params["q"] = inputs["q"]

            response = await client._make_request(
                f"calendars/{calendar_id}/events",
                params=params
            )

            events = []
            for event in response.get("items", []):
                events.append({
                    "id": event.get("id", ""),
                    "summary": event.get("summary", ""),
                    "start": event.get("start", {}),
                    "end": event.get("end", {}),
                    "location": event.get("location", ""),
                    "status": event.get("status", ""),
                    "html_link": event.get("htmlLink", "")
                })

            return ActionResult(
                data={
                    "events": events,
                    "next_page_token": response.get("nextPageToken"),
                    "time_zone": response.get("timeZone", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "events": [],
                    "next_page_token": None,
                    "time_zone": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("list_calendar_settings")
class ListCalendarSettingsAction(ActionHandler):
    """View calendar settings."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)

            params = {}
            if inputs.get("page_token"):
                params["pageToken"] = inputs["page_token"]
            if inputs.get("max_results"):
                params["maxResults"] = inputs["max_results"]

            response = await client._make_request(
                "calendars/settings",
                params=params if params else None
            )

            settings = []
            for setting in response.get("items", []):
                settings.append({
                    "id": setting.get("id", ""),
                    "value": setting.get("value", ""),
                    "etag": setting.get("etag", "")
                })

            return ActionResult(
                data={
                    "settings": settings,
                    "next_page_token": response.get("nextPageToken"),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "settings": [],
                    "next_page_token": None,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Contacts Action Handler ----

@zoom.action("list_contacts")
class ListContactsAction(ActionHandler):
    """View contacts."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)

            params = {
                "page_size": min(inputs.get("page_size", 50), 1000)
            }

            if inputs.get("next_page_token"):
                params["next_page_token"] = inputs["next_page_token"]
            if inputs.get("type"):
                params["type"] = inputs["type"]
            if inputs.get("search_key"):
                params["search_key"] = inputs["search_key"]

            response = await client._make_request("contacts", params=params)

            contacts = []
            for contact in response.get("contacts", []):
                contacts.append({
                    "id": contact.get("id", ""),
                    "email": contact.get("email", ""),
                    "first_name": contact.get("first_name", ""),
                    "last_name": contact.get("last_name", ""),
                    "phone_number": contact.get("phone_number", ""),
                    "direct_numbers": contact.get("direct_numbers", []),
                    "extension_number": contact.get("extension_number", ""),
                    "presence_status": contact.get("presence_status", ""),
                    "dept": contact.get("dept", ""),
                    "job_title": contact.get("job_title", "")
                })

            return ActionResult(
                data={
                    "contacts": contacts,
                    "next_page_token": response.get("next_page_token"),
                    "total_records": response.get("total_records", len(contacts)),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "contacts": [],
                    "next_page_token": None,
                    "total_records": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Additional Meeting Action Handlers ----

@zoom.action("create_meeting_template")
class CreateMeetingTemplateAction(ActionHandler):
    """Create a meeting template from an existing meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            template_data = {
                "name": inputs["name"],
                "meeting_id": meeting_id
            }

            if inputs.get("save_recurrence"):
                template_data["save_recurrence"] = inputs["save_recurrence"]

            response = await client._make_request(
                f"users/{user_id}/meeting_templates",
                method="POST",
                data=template_data
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "name": response.get("name", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "name": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("create_meeting_invite_links")
class CreateMeetingInviteLinksAction(ActionHandler):
    """Create invite links for a meeting."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            invite_data = {
                "attendees": inputs["attendees"]
            }

            if inputs.get("ttl"):
                invite_data["ttl"] = inputs["ttl"]

            response = await client._make_request(
                f"meetings/{meeting_id}/invite_links",
                method="POST",
                data=invite_data
            )

            attendees = []
            for attendee in response.get("attendees", []):
                attendees.append({
                    "name": attendee.get("name", ""),
                    "join_url": attendee.get("join_url", "")
                })

            return ActionResult(
                data={
                    "attendees": attendees,
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "attendees": [],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_meeting_participant")
class GetMeetingParticipantAction(ActionHandler):
    """View a meeting's participant details."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])
            participant_id = inputs["participant_id"]

            response = await client._make_request(
                f"meetings/{meeting_id}/participants/{participant_id}"
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "user_id": response.get("user_id", ""),
                    "name": response.get("name", ""),
                    "user_email": response.get("user_email", ""),
                    "join_time": response.get("join_time", ""),
                    "leave_time": response.get("leave_time", ""),
                    "duration": response.get("duration", 0),
                    "status": response.get("status", ""),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "user_id": "",
                    "name": "",
                    "user_email": "",
                    "join_time": "",
                    "leave_time": "",
                    "duration": 0,
                    "status": "",
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_past_meeting")
class GetPastMeetingAction(ActionHandler):
    """View a past meeting's details."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            meeting_id = encode_meeting_id(inputs["meeting_id"])

            response = await client._make_request(f"past_meetings/{meeting_id}")

            return ActionResult(
                data={
                    "id": response.get("id"),
                    "uuid": response.get("uuid", ""),
                    "topic": response.get("topic", ""),
                    "type": response.get("type"),
                    "host_id": response.get("host_id", ""),
                    "host_email": response.get("host_email", ""),
                    "start_time": response.get("start_time", ""),
                    "end_time": response.get("end_time", ""),
                    "duration": response.get("duration", 0),
                    "total_minutes": response.get("total_minutes", 0),
                    "participants_count": response.get("participants_count", 0),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": None,
                    "uuid": "",
                    "topic": "",
                    "type": None,
                    "host_id": "",
                    "host_email": "",
                    "start_time": "",
                    "end_time": "",
                    "duration": 0,
                    "total_minutes": 0,
                    "participants_count": 0,
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


# ---- Additional User Action Handlers ----

@zoom.action("get_meeting_template_detail")
class GetMeetingTemplateDetailAction(ActionHandler):
    """Get user's meeting template detail."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")
            template_id = inputs["template_id"]

            response = await client._make_request(
                f"users/{user_id}/meeting_templates/{template_id}"
            )

            return ActionResult(
                data={
                    "id": response.get("id", ""),
                    "name": response.get("name", ""),
                    "type": response.get("type"),
                    "topic": response.get("topic", ""),
                    "duration": response.get("duration", 0),
                    "timezone": response.get("timezone", ""),
                    "agenda": response.get("agenda", ""),
                    "settings": response.get("settings", {}),
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "id": "",
                    "name": "",
                    "type": None,
                    "topic": "",
                    "duration": 0,
                    "timezone": "",
                    "agenda": "",
                    "settings": {},
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )


@zoom.action("get_user_permissions")
class GetUserPermissionsAction(ActionHandler):
    """View a user's permissions."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            client = ZoomAPIClient(context)
            user_id = inputs.get("user_id", "me")

            response = await client._make_request(f"users/{user_id}/permissions")

            permissions = response.get("permissions", [])

            return ActionResult(
                data={
                    "permissions": permissions,
                    "result": True
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "permissions": [],
                    "result": False,
                    "error": str(e)
                },
                cost_usd=0.0
            )
