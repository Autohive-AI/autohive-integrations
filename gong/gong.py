from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult, ConnectedAccountHandler, ConnectedAccountInfo
)
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import json



gong = Integration.load()

class GongAPIClient:
    """Client for interacting with the Gong API"""
    
    def __init__(self, context: ExecutionContext):
        self.context = context
        self.base_url = context.metadata.get("api_base_url")
        if not self.base_url:
            raise ValueError("api_base_url is required in auth context. This should be provided by Gong's OAuth flow as 'api_base_url_for_customer'.")
    
    async def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None):
        """Make an authenticated request to the Gong API"""
        url = f"{self.base_url}/v2/{endpoint}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
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

@gong.action("list_calls")
class ListCallsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = GongAPIClient(context)
        
        # Build query parameters with proper date format
        params = {}
        
        if inputs.get("from_date"):
            # Convert YYYY-MM-DD to datetime format required by Gong
            from datetime import datetime
            from_dt = datetime.strptime(inputs["from_date"], "%Y-%m-%d")
            params["fromDateTime"] = from_dt.strftime("%Y-%m-%dT00:00:00.000Z")
        if inputs.get("to_date"):
            from datetime import datetime
            to_dt = datetime.strptime(inputs["to_date"], "%Y-%m-%d")
            params["toDateTime"] = to_dt.strftime("%Y-%m-%dT23:59:59.999Z")
        if inputs.get("user_ids"):
            params["userIds"] = inputs["user_ids"]
        if inputs.get("limit"):
            params["limit"] = inputs["limit"]
        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]
        
        # Add default date range if none provided (last 30 days)
        if not inputs.get("from_date") and not inputs.get("to_date"):
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            params["fromDateTime"] = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
            params["toDateTime"] = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        
        try:
            response = await client._make_request("calls", params=params)
            
            calls = []
            for call in response.get("calls", []):
                # Filter out private calls
                if bool(call.get("isPrivate", False)):
                    continue
                calls.append({
                    "id": call.get("id"),
                    "title": call.get("title", ""),
                    "started": call.get("started"),
                    "duration": call.get("duration", 0),
                    "participants": call.get("participants", []),
                    "outcome": call.get("outcome", "")
                })
            
            # Sort calls by start time, newest first
            calls.sort(key=lambda x: x.get("started", ""), reverse=True)
            
            return ActionResult(data={
                "calls": calls,
                "has_more": response.get("hasMore", False),
                "next_cursor": response.get("nextCursor")
            })
        except Exception as e:
            return ActionResult(data={
                "calls": [],
                "has_more": False,
                "next_cursor": None,
                "error": str(e)
            })

@gong.action("get_call_transcript")
class GetCallTranscriptAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = GongAPIClient(context)
        call_id = inputs["call_id"]
        
        try:
            response = await client._make_request(f"calls/{call_id}")
            call_data = response.get("call", response)
            
            if bool(call_data.get("isPrivate", False)):
                return ActionResult(data={
                    "call_id": call_id,
                    "transcript": [],
                    "error": "private_call_filtered"
                })

            speaker_map = {}
            
            ext_data = {
                "filter": {
                    "callIds": [call_id],
                    "fromDateTime": "2015-01-01T00:00:00Z"
                },
                "contentSelector": {
                    "exposedFields": {
                        "parties": True
                    }
                }
            }
            
            try:
                ext_response = await client._make_request("calls/extensive", method="POST", data=ext_data)
                ext_calls = ext_response.get("calls", [])
                
                if ext_calls:
                    ext_call = ext_calls[0]
                    participants = ext_call.get("parties", [])
                    
                    for participant in participants:
                        speaker_id = str(participant.get("speakerId") or 
                                       participant.get("userId") or 
                                       participant.get("id") or "")
                        
                        name = (participant.get("name") or 
                               participant.get("title") or
                               f"{participant.get('firstName', '')} {participant.get('lastName', '')}".strip() or
                               participant.get("emailAddress") or
                               participant.get("email") or "")
                        
                        if speaker_id and name:
                            speaker_map[speaker_id] = name
            except Exception as e:
                print(f"Warning: Failed to fetch speaker details: {e}")

            transcript_data = {
                "filter": {
                    "callIds": [call_id],
                    "fromDateTime": "2015-01-01T00:00:00.000Z"
                }
            }
            response = await client._make_request("calls/transcript", method="POST", data=transcript_data)
            
            transcript = []
            call_transcripts = response.get("callTranscripts", [])
            if call_transcripts:
                for segment in call_transcripts[0].get("transcript", []):
                    raw_speaker_id = segment.get("speakerId", "")
                    speaker_id = str(raw_speaker_id) if raw_speaker_id is not None else ""
                    topic = segment.get("topic", "")
                    
                    speaker_name = speaker_map.get(speaker_id, f"Speaker {speaker_id}" if speaker_id else "Unknown Speaker")
                    
                    for sentence in segment.get("sentences", []):
                        transcript.append({
                            "speaker_id": speaker_id,
                            "speaker_name": speaker_name,
                            "start_time": sentence.get("start", 0) / 1000,
                            "end_time": sentence.get("end", 0) / 1000,
                            "text": sentence.get("text", "")
                        })
            
            return ActionResult(data={
                "call_id": call_id,
                "transcript": transcript
            })
        except Exception as e:
            return ActionResult(data={
                "call_id": call_id,
                "transcript": [],
                "error": str(e)
            })

@gong.action("get_call_details")
class GetCallDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = GongAPIClient(context)
        call_id = inputs["call_id"]
        
        try:
            response = await client._make_request(f"calls/{call_id}")
            call = response.get("call", response)
            
            if bool(call.get("isPrivate", False)):
                return ActionResult(data={
                    "id": call_id,
                    "title": "",
                    "started": "",
                    "duration": 0,
                    "participants": [],
                    "outcome": "",
                    "crm_data": {},
                    "error": "private_call_filtered"
                })

            participants = []
            crm_data = call.get("crmData", {})
            
            started_str = call.get("started")
            if started_str:
                try:
                    extensive_data = {
                        "filter": {
                            "callIds": [call_id],
                            "fromDateTime": "2015-01-01T00:00:00Z"
                        },
                        "contentSelector": {
                            "context": "Extended",
                            "exposedFields": {
                                "parties": True,
                                "content": {
                                    "callOutcome": True
                                }
                            }
                        }
                    }
                    
                    if started_str:
                         extensive_data["filter"]["fromDateTime"] = "2015-01-01T00:00:00Z" 
                    
                    ext_response = await client._make_request("calls/extensive", method="POST", data=extensive_data)
                    ext_calls = ext_response.get("calls", [])
                    if ext_calls:
                        ext_call = ext_calls[0]
                        participants = ext_call.get("parties", [])
                        crm_data = ext_call.get("crmData", crm_data)
                        if not call.get("outcome"):
                            call["outcome"] = ext_call.get("outcome", "")
                except Exception as e:
                    print(f"Warning: Failed to fetch extensive details: {e}")

            return ActionResult(data={
                "id": call.get("id", call_id),
                "title": call.get("title", "Unknown Call"),
                "started": call.get("started", ""),
                "duration": call.get("duration", 0),
                "participants": participants,
                "outcome": call.get("outcome", ""),
                "crm_data": crm_data
            })
        except Exception as e:
            return ActionResult(data={
                "id": call_id,
                "title": "",
                "started": "",
                "duration": 0,
                "participants": [],
                "outcome": "",
                "crm_data": {},
                "error": str(e)
            })

@gong.action("search_calls")
class SearchCallsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = GongAPIClient(context)
        
        # Use calls/extensive endpoint with proper JSON structure
        data = {
            "filter": {
                "fromDateTime": None,
                "toDateTime": None
            },
            "contentSelector": {
                "context": "Extended",
                "exposedFields": {
                    "content": {
                        "topics": True,
                        "pointsOfInterest": True
                    }
                }
            }
        }
        
        if inputs.get("from_date"):
            from datetime import datetime
            from_dt = datetime.strptime(inputs["from_date"], "%Y-%m-%d")
            data["filter"]["fromDateTime"] = from_dt.strftime("%Y-%m-%dT00:00:00.000Z")
        else:
            # Default to last 30 days if no date provided
            from datetime import datetime, timedelta
            start_date = datetime.now() - timedelta(days=30)
            data["filter"]["fromDateTime"] = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
            
        if inputs.get("to_date"):
            from datetime import datetime
            to_dt = datetime.strptime(inputs["to_date"], "%Y-%m-%d")
            data["filter"]["toDateTime"] = to_dt.strftime("%Y-%m-%dT23:59:59.999Z")
        else:
            # Default to now if no end date provided
            from datetime import datetime
            data["filter"]["toDateTime"] = datetime.now().strftime("%Y-%m-%dT23:59:59.999Z")
        
        try:
            response = await client._make_request("calls/extensive", method="POST", data=data)
            
            # Filter calls based on search query in content
            query = inputs["query"].lower()
            results = []
            
            for call in response.get("calls", []):
                # Skip private calls
                if bool(call.get("isPrivate", False)):
                    continue
                # Check if query appears in call content/highlights/topics
                content_match = False
                matched_segments = []
                
                # Check various content fields for the search query
                content_fields = call.get("content", {})
                
                # Let's try to match the original logic as much as possible but with valid API request structure.
                topics = content_fields.get("topics", [])
                
                # Since I requested pointsOfInterest, let's use that if highlights is empty
                points_of_interest = content_fields.get("pointsOfInterest", [])
                
                # Search in points_of_interest (assuming it has text field)
                for poi in points_of_interest:
                     if query in poi.get("action", "").lower() or query in poi.get("concept", "").lower():
                        content_match = True
                        matched_segments.append({
                            "text": f"{poi.get('action', '')} {poi.get('concept', '')}",
                            "start_time": poi.get("startTime", 0)
                        })

                # Search in topics
                for topic in topics:
                    if query in topic.get("name", "").lower():
                         content_match = True
                
                # Fallback to simple title search if nothing else
                if query in call.get("title", "").lower():
                    content_match = True

                if content_match:
                    results.append({
                        "call_id": call.get("id"),
                        "title": call.get("title", ""),
                        "started": call.get("started"),
                        "relevance_score": len(matched_segments) + (1 if query in call.get("title", "").lower() else 0), 
                        "matched_segments": matched_segments
                    })
            
            return ActionResult(data={
                "results": results,
                "total_count": len(results)
            })
        except Exception as e:
            return ActionResult(data={
                "results": [],
                "total_count": 0,
                "error": str(e)
            })

@gong.action("list_users")
class ListUsersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        client = GongAPIClient(context)
        
        params = {
            "limit": inputs.get("limit", 100)
        }
        
        if inputs.get("cursor"):
            params["cursor"] = inputs["cursor"]
        
        try:
            response = await client._make_request("users", params=params)
            
            users = []
            for user in response.get("users", []):
                users.append({
                    "id": user.get("id"),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "role": user.get("role", ""),
                    "active": user.get("active", True)
                })
            
            return ActionResult(data={
                "users": users,
                "has_more": response.get("hasMore", False),
                "next_cursor": response.get("nextCursor")
            })
        except Exception as e:
            return ActionResult(data={
                "users": [],
                "has_more": False,
                "next_cursor": None,
                "error": str(e)
            })
