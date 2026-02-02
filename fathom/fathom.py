from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, Optional
from urllib.parse import quote

fathom = Integration.load()

class FathomAPIClient:
    """Client for interacting with the Fathom API"""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self.base_url = "https://api.fathom.ai/external/v1"

    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None):
        """Make an authenticated request to the Fathom API"""
        url = f"{self.base_url}/{endpoint}"

        headers = {
            "Content-Type": "application/json"
        }

        # Build query string manually for array parameters
        if params and method == "GET":
            query_parts = []
            for key, value in params.items():
                if isinstance(value, list):
                    # For array parameters like recorded_by[], expand into multiple params
                    for item in value:
                        query_parts.append(f"{key}={quote(str(item))}")
                elif value is not None:
                    query_parts.append(f"{key}={quote(str(value))}")

            if query_parts:
                url = f"{url}?{'&'.join(query_parts)}"

            # Pass empty params dict to avoid duplicate query params
            return await self.context.fetch(url, headers=headers)

        # Use the context's fetch method for authenticated requests (OAuth handled by SDK)
        if method == "GET":
            return await self.context.fetch(url, params=params, headers=headers)
        elif method == "POST":
            return await self.context.fetch(url, method="POST", json=data, headers=headers)
        elif method == "PUT":
            return await self.context.fetch(url, method="PUT", json=data, headers=headers)
        elif method == "DELETE":
            return await self.context.fetch(url, method="DELETE", headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

# ---- Action Handlers ----

@fathom.action("list_meetings")
class ListMeetingsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = FathomAPIClient(context)

        # Build query parameters
        params = {}

        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]
        if inputs.get("include_action_items"):
            params["include_action_items"] = inputs["include_action_items"]
        if inputs.get("include_crm_matches"):
            params["include_crm_matches"] = inputs["include_crm_matches"]
        if inputs.get("recorded_by"):
            # Fathom API expects recorded_by[] for array parameters
            params["recorded_by[]"] = inputs["recorded_by"]
        if inputs.get("calendar_invitees_domains"):
            # Fathom API expects calendar_invitees_domains[] for array parameters
            params["calendar_invitees_domains[]"] = inputs["calendar_invitees_domains"]
        if inputs.get("teams"):
            # Fathom API expects teams[] for array parameters
            params["teams[]"] = inputs["teams"]
        if inputs.get("created_after"):
            params["created_after"] = inputs["created_after"]
        if inputs.get("created_before"):
            params["created_before"] = inputs["created_before"]
        if inputs.get("calendar_invitees_domains_type"):
            params["calendar_invitees_domains_type"] = inputs["calendar_invitees_domains_type"]
        if inputs.get("meeting_type"):
            params["meeting_type"] = inputs["meeting_type"]

        try:
            response = await client._make_request("meetings", params=params)

            # Process items to filter out null optional fields
            items = response.get("items", [])
            processed_items = []

            # Fields to exclude when they are null (not in output schema)
            optional_fields = ["transcript", "action_items", "default_summary", "crm_matches"]

            for item in items:
                processed_item = {}
                for key, value in item.items():
                    # Skip optional fields that are null
                    if key in optional_fields and value is None:
                        continue
                    processed_item[key] = value

                processed_items.append(processed_item)

            return ActionResult(
                data={
                    "limit": response.get("limit", 0),
                    "next_cursor": response.get("next_cursor"),
                    "items": processed_items
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "limit": 0,
                    "next_cursor": None,
                    "items": [],
                    "error": str(e)
                },
                cost_usd=0.0
            )

@fathom.action("get_transcript")
class GetTranscriptAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = FathomAPIClient(context)
        recording_id = inputs["recording_id"]

        try:
            response = await client._make_request(f"recordings/{recording_id}/transcript")

            transcript = []
            for segment in response.get("transcript", []):
                # Extract speaker name from speaker object
                speaker = segment.get("speaker", {})
                speaker_name = speaker.get("display_name", "Unknown Speaker")

                transcript.append({
                    "speaker_name": speaker_name,
                    "timestamp": segment.get("timestamp", "00:00:00"),
                    "text": segment.get("text", "")
                })

            return ActionResult(
                data={
                    "recording_id": recording_id,
                    "transcript": transcript
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "recording_id": recording_id,
                    "transcript": [],
                    "error": str(e)
                },
                cost_usd=0.0
            )

@fathom.action("list_teams")
class ListTeamsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = FathomAPIClient(context)

        # Build query parameters
        params = {}
        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]

        try:
            response = await client._make_request("teams", params=params)

            teams = []
            for team in response.get("items", []):
                teams.append({
                    "name": team.get("name", ""),
                    "created_at": team.get("created_at", "")
                })

            return ActionResult(
                data={
                    "limit": response.get("limit"),
                    "next_cursor": response.get("next_cursor"),
                    "teams": teams
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "limit": None,
                    "next_cursor": None,
                    "teams": [],
                    "error": str(e)
                },
                cost_usd=0.0
            )

@fathom.action("list_team_members")
class ListTeamMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = FathomAPIClient(context)

        # Build query parameters
        params = {}
        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]
        if inputs.get("team"):
            params["team"] = inputs["team"]

        try:
            response = await client._make_request("team_members", params=params)

            team_members = []
            for member in response.get("items", []):
                team_members.append({
                    "name": member.get("name", ""),
                    "email": member.get("email", ""),
                    "created_at": member.get("created_at", "")
                })

            return ActionResult(
                data={
                    "limit": response.get("limit"),
                    "next_cursor": response.get("next_cursor"),
                    "team_members": team_members
                },
                cost_usd=0.0
            )
        except Exception as e:
            return ActionResult(
                data={
                    "limit": None,
                    "next_cursor": None,
                    "team_members": [],
                    "error": str(e)
                },
                cost_usd=0.0
            )
