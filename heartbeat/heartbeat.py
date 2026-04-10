from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, PollingTriggerHandler
)
from typing import Dict, Any, List, Optional

# Create the integration using the config.json
heartbeat = Integration.load()
service_endpoint = "https://api.heartbeat.chat/v0/"

def get_auth_headers(context: ExecutionContext) -> Dict[str, str]:
    """Get authentication headers with bearer token from custom auth."""
    headers = {}
    credentials = context.auth.get("credentials", {})
    api_key = credentials.get("api_key")
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    return headers

class HeartbeatDataParser:
    @staticmethod
    def parse_channel(raw_channel: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Heartbeat channel into standardized format."""
        channel = {
            "id": raw_channel.get('id', ''),
            "name": raw_channel.get('name', ''),
        }
        
        # Add optional fields if they exist
        if 'description' in raw_channel:
            channel['description'] = raw_channel['description']
        if 'channelCategoryID' in raw_channel:
            channel['channelCategoryID'] = raw_channel['channelCategoryID']
        if 'private' in raw_channel:
            channel['private'] = raw_channel['private']
            
        return channel

    @staticmethod
    def parse_thread(raw_thread: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Heartbeat thread into standardized format."""
        thread = {
            "id": raw_thread.get('id', ''),
            "title": raw_thread.get('title', ''),
            "channelID": raw_thread.get('channelID', ''),
            "authorID": raw_thread.get('userID', ''),  # API uses 'userID' field
        }
        
        # Add optional fields if they exist
        if 'content' in raw_thread:
            thread['content'] = raw_thread['content']
        if 'createdAt' in raw_thread:
            thread['createdAt'] = raw_thread['createdAt']
        if 'updatedAt' in raw_thread:
            thread['updatedAt'] = raw_thread['updatedAt']
        if 'url' in raw_thread:
            thread['url'] = raw_thread['url']
        if 'comments' in raw_thread:
            thread['comments'] = raw_thread['comments']
            
        # Add nested user object if it exists
        if 'user' in raw_thread and raw_thread['user']:
            thread['user'] = HeartbeatDataParser.parse_user(raw_thread['user'])
            
        return thread

    @staticmethod
    def parse_user(raw_user: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Heartbeat user into standardized format."""
        user = {
            "id": raw_user.get('id', ''),
            "email": raw_user.get('email', ''),
            "name": raw_user.get('name', ''),
        }
        
        # Add optional fields if they exist
        if 'bio' in raw_user:
            user['bio'] = raw_user['bio']
        if 'avatar' in raw_user:
            user['avatar'] = raw_user['avatar']
        if 'createdAt' in raw_user:
            user['createdAt'] = raw_user['createdAt']
            
        return user

    @staticmethod
    def parse_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Heartbeat event into standardized format."""
        event = {
            "id": raw_event.get('id', ''),
            "title": raw_event.get('title', ''),
            "startTime": raw_event.get('startTime', ''),
        }
        
        # Add optional fields if they exist
        if 'description' in raw_event:
            event['description'] = raw_event['description']
        if 'endTime' in raw_event:
            event['endTime'] = raw_event['endTime']
        if 'location' in raw_event:
            event['location'] = raw_event['location']
        if 'createdAt' in raw_event:
            event['createdAt'] = raw_event['createdAt']
            
        return event

    @staticmethod
    def parse_comment(raw_comment: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Heartbeat comment into standardized format."""
        comment = {
            "id": raw_comment.get('id', ''),
            "content": raw_comment.get('text', ''),  # API uses 'text' field
            "threadID": raw_comment.get('threadID', ''),
            "authorID": raw_comment.get('userID', ''),  # API uses 'userID' field
        }
        
        # Add optional fields if they exist
        if 'parentCommentID' in raw_comment:
            comment['parentID'] = raw_comment['parentCommentID']
        if 'createdAt' in raw_comment:
            comment['createdAt'] = raw_comment['createdAt']
        if 'updatedAt' in raw_comment:
            comment['updatedAt'] = raw_comment['updatedAt']
            
        # Add nested user object if it exists
        if 'user' in raw_comment and raw_comment['user']:
            comment['user'] = HeartbeatDataParser.parse_user(raw_comment['user'])
            
        return comment

# ---- Action Handlers ----

@heartbeat.action("get_heartbeat_channels")
class GetChannels(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                service_endpoint + "channels",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            channels = []
            # Handle both array response and object with items property
            items = response if isinstance(response, list) else response.get('items', response.get('channels', []))
            for raw_channel in items:
                channels.append(HeartbeatDataParser.parse_channel(raw_channel))
            
            return {
                "channels": channels,
                "result": True
            }
            
        except Exception as e:
            return {
                "channels": [],
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_channel")
class GetChannel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            channel_id = inputs['channel_id']
            
            response = await context.fetch(
                service_endpoint + f"channels/{channel_id}",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            return {
                "channel": HeartbeatDataParser.parse_channel(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "channel": {},
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_channel_threads")
class GetChannelThreads(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            channel_id = inputs['channel_id']
            
            response = await context.fetch(
                service_endpoint + f"channels/{channel_id}/threads",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            threads = []
            # Handle both array response and object with items property
            items = response if isinstance(response, list) else response.get('items', response.get('threads', []))
            for raw_thread in items:
                threads.append(HeartbeatDataParser.parse_thread(raw_thread))
            
            return {
                "threads": threads,
                "result": True
            }
            
        except Exception as e:
            return {
                "threads": [],
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_thread")
class GetThread(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            thread_id = inputs['thread_id']
            
            response = await context.fetch(
                service_endpoint + f"threads/{thread_id}",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            return {
                "thread": HeartbeatDataParser.parse_thread(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "thread": {},
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_users")
class GetUsers(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                service_endpoint + "users",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            users = []
            # Handle both array response and object with items property
            items = response if isinstance(response, list) else response.get('items', response.get('users', []))
            for raw_user in items:
                users.append(HeartbeatDataParser.parse_user(raw_user))
            
            return {
                "users": users,
                "result": True
            }
            
        except Exception as e:
            return {
                "users": [],
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_user")
class GetUser(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            user_id = inputs['user_id']
            
            response = await context.fetch(
                service_endpoint + f"users/{user_id}",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            return {
                "user": HeartbeatDataParser.parse_user(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "user": {},
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_events")
class GetEvents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                service_endpoint + "events",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            events = []
            # Handle both array response and object with items property
            items = response if isinstance(response, list) else response.get('items', response.get('events', []))
            for raw_event in items:
                events.append(HeartbeatDataParser.parse_event(raw_event))
            
            return {
                "events": events,
                "result": True
            }
            
        except Exception as e:
            return {
                "events": [],
                "result": False,
                "error": str(e)
            }

@heartbeat.action("get_heartbeat_event")
class GetEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            event_id = inputs['event_id']
            
            response = await context.fetch(
                service_endpoint + f"events/{event_id}",
                method="GET",
                headers=get_auth_headers(context)
            )
            
            return {
                "event": HeartbeatDataParser.parse_event(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "event": {},
                "result": False,
                "error": str(e)
            }

@heartbeat.action("create_heartbeat_comment")
class CreateComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract required inputs
            thread_id = inputs['thread_id']
            content = inputs['content']
            
            # Build request body according to API spec
            request_body = {
                "threadID": thread_id,
                "text": content,
                "parentCommentID": None  # Required field, null for direct replies to thread
            }
            
            # Add optional parent comment ID for replies
            if 'parent_id' in inputs and inputs['parent_id']:
                request_body['parentCommentID'] = inputs['parent_id']
            
            # Add optional user ID to create comment on behalf of another user (admin only)
            if 'user_id' in inputs and inputs['user_id']:
                request_body['userID'] = inputs['user_id']
            
            response = await context.fetch(
                service_endpoint + "comments",
                method="PUT",
                headers=get_auth_headers(context),
                json=request_body
            )
            
            return {
                "comment": HeartbeatDataParser.parse_comment(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "comment": {},
                "result": False,
                "error": str(e)
            }

@heartbeat.action("create_heartbeat_thread")
class CreateThread(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Extract required inputs
            channel_id = inputs['channel_id']
            content = inputs['content']
            
            # Build request body according to API spec
            request_body = {
                "channelID": channel_id,
                "text": content
            }
            
            # Add optional user ID to create thread on behalf of another user (admin only)
            if 'user_id' in inputs and inputs['user_id']:
                request_body['userID'] = inputs['user_id']
            
            response = await context.fetch(
                service_endpoint + "threads",
                method="PUT",
                headers=get_auth_headers(context),
                json=request_body
            )
            
            return {
                "thread": HeartbeatDataParser.parse_thread(response),
                "result": True
            }
            
        except Exception as e:
            return {
                "thread": {},
                "result": False,
                "error": str(e)
            }

# ---- Polling Trigger Handlers ----
