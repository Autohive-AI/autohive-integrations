from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

# Create the integration using the config.json
google_chat = Integration.load()

# ---- Helper Functions ----

def build_credentials(context: ExecutionContext) -> Credentials:
    """Build Google credentials from ExecutionContext."""
    try:
        access_token = context.auth['credentials']['access_token']
    except (KeyError, TypeError) as e:
        print(f"Debug - context.auth type: {type(context.auth)}")
        print(f"Debug - context.auth content: {context.auth}")
        raise ValueError(f"No access token found in authentication context: {e}")

    creds = Credentials(
        token=access_token,
        token_uri='https://oauth2.googleapis.com/token'
    )
    return creds

def build_chat_service(context: ExecutionContext):
    """Build Google Chat service client."""
    credentials = build_credentials(context)
    return build('chat', 'v1', credentials=credentials)

def handle_api_error(error: Exception) -> Dict[str, Any]:
    """Handle API errors consistently."""
    if isinstance(error, HttpError):
        return {
            "result": False,
            "error": f"Google Chat API error: {str(error)}"
        }
    return {
        "result": False,
        "error": str(error)
    }

def format_space(space: Dict[str, Any]) -> Dict[str, Any]:
    """Format a space object for consistent output."""
    formatted = {
        "name": space.get('name', ''),
        "space_type": space.get('spaceType', 'UNKNOWN')
    }

    if 'displayName' in space:
        formatted["display_name"] = space['displayName']
    if 'singleUserBotDm' in space:
        formatted["single_user_bot_dm"] = space['singleUserBotDm']
    if 'threaded' in space:
        formatted["threaded"] = space['threaded']
    if 'spaceThreadingState' in space:
        formatted["space_thread_state"] = space['spaceThreadingState']
    if 'spaceDetails' in space:
        formatted["space_details"] = space['spaceDetails']
    if 'spaceHistoryState' in space:
        formatted["space_history_state"] = space['spaceHistoryState']
    if 'importMode' in space:
        formatted["import_mode"] = space['importMode']
    if 'createTime' in space:
        formatted["create_time"] = space['createTime']
    if 'adminInstalled' in space:
        formatted["admin_installed"] = space['adminInstalled']

    return formatted

def format_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Format a message object for consistent output."""
    formatted = {
        "name": message.get('name', ''),
        "create_time": message.get('createTime', ''),
        "sender": message.get('sender', {})
    }

    if 'text' in message:
        formatted["text"] = message['text']
    if 'formattedText' in message:
        formatted["formatted_text"] = message['formattedText']
    if 'lastUpdateTime' in message:
        formatted["last_update_time"] = message['lastUpdateTime']
    if 'deleteTime' in message:
        formatted["delete_time"] = message['deleteTime']
    if 'thread' in message:
        formatted["thread"] = message['thread']
    if 'space' in message:
        formatted["space"] = message['space']
    if 'argumentText' in message:
        formatted["argument_text"] = message['argumentText']
    if 'slashCommand' in message:
        formatted["slash_command"] = message['slashCommand']
    if 'attachment' in message:
        formatted["attachment"] = message['attachment']
    if 'annotations' in message:
        formatted["annotations"] = message['annotations']

    return formatted

def format_member(membership: Dict[str, Any]) -> Dict[str, Any]:
    """Format a membership object for consistent output."""
    formatted = {
        "name": membership.get('name', ''),
        "state": membership.get('state', 'UNKNOWN')
    }

    if 'member' in membership:
        formatted["member"] = membership['member']
    if 'role' in membership:
        formatted["role"] = membership['role']
    if 'createTime' in membership:
        formatted["create_time"] = membership['createTime']
    if 'deleteTime' in membership:
        formatted["delete_time"] = membership['deleteTime']

    return formatted

def format_reaction(reaction: Dict[str, Any]) -> Dict[str, Any]:
    """Format a reaction object for consistent output."""
    return {
        "name": reaction.get('name', ''),
        "user": reaction.get('user', {}),
        "emoji": reaction.get('emoji', {})
    }

# ---- Action Handlers ----

@google_chat.action("list_spaces")
class ListSpaces(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)

            # Build request parameters
            params = {}
            if 'page_size' in inputs:
                params['pageSize'] = inputs['page_size']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']
            if 'filter' in inputs:
                params['filter'] = inputs['filter']

            request = service.spaces().list(**params)
            response = request.execute()

            spaces = []
            for space in response.get('spaces', []):
                spaces.append(format_space(space))

            result = {
                "spaces": spaces,
                "result": True
            }

            if 'nextPageToken' in response:
                result["next_page_token"] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "spaces": [],
                **handle_api_error(e)
            }

@google_chat.action("get_space")
class GetSpace(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            space_name = inputs['space_name']

            request = service.spaces().get(name=space_name)
            response = request.execute()

            return {
                "space": format_space(response),
                "result": True
            }

        except Exception as e:
            return {
                "space": {},
                **handle_api_error(e)
            }

@google_chat.action("create_space")
class CreateSpace(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)

            space_body = {
                "displayName": inputs['display_name'],
                "spaceType": inputs.get('space_type', 'SPACE')
            }

            if 'space_details' in inputs:
                space_body['spaceDetails'] = inputs['space_details']

            request = service.spaces().create(body=space_body)
            response = request.execute()

            return {
                "space": format_space(response),
                "result": True
            }

        except Exception as e:
            return {
                "space": {},
                **handle_api_error(e)
            }

@google_chat.action("send_message")
class SendMessage(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            space_name = inputs['space_name']

            message_body = {
                "text": inputs['text']
            }

            params = {
                "parent": space_name,
                "body": message_body
            }

            if 'thread_key' in inputs:
                params['threadKey'] = inputs['thread_key']
            if 'message_id' in inputs:
                params['messageId'] = inputs['message_id']
            if 'message_reply_option' in inputs:
                params['messageReplyOption'] = inputs['message_reply_option']

            request = service.spaces().messages().create(**params)
            response = request.execute()

            return {
                "message": format_message(response),
                "result": True
            }

        except Exception as e:
            return {
                "message": {},
                **handle_api_error(e)
            }

@google_chat.action("list_messages")
class ListMessages(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            space_name = inputs['space_name']

            params = {"parent": space_name}

            if 'page_size' in inputs:
                params['pageSize'] = inputs['page_size']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']
            if 'filter' in inputs:
                params['filter'] = inputs['filter']
            if 'order_by' in inputs:
                params['orderBy'] = inputs['order_by']
            if 'show_deleted' in inputs:
                params['showDeleted'] = inputs['show_deleted']

            request = service.spaces().messages().list(**params)
            response = request.execute()

            messages = []
            for message in response.get('messages', []):
                messages.append(format_message(message))

            result = {
                "messages": messages,
                "result": True
            }

            if 'nextPageToken' in response:
                result["next_page_token"] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "messages": [],
                **handle_api_error(e)
            }

@google_chat.action("get_message")
class GetMessage(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            message_name = inputs['message_name']

            request = service.spaces().messages().get(name=message_name)
            response = request.execute()

            return {
                "message": format_message(response),
                "result": True
            }

        except Exception as e:
            return {
                "message": {},
                **handle_api_error(e)
            }

@google_chat.action("update_message")
class UpdateMessage(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            message_name = inputs['message_name']

            message_body = {
                "text": inputs['text']
            }

            params = {
                "name": message_name,
                "body": message_body,
                "updateMask": inputs.get('update_mask', 'text')
            }

            request = service.spaces().messages().patch(**params)
            response = request.execute()

            return {
                "message": format_message(response),
                "result": True
            }

        except Exception as e:
            return {
                "message": {},
                **handle_api_error(e)
            }

@google_chat.action("delete_message")
class DeleteMessage(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            message_name = inputs['message_name']

            params = {"name": message_name}
            if 'force' in inputs:
                params['force'] = inputs['force']

            request = service.spaces().messages().delete(**params)
            request.execute()

            return {"result": True}

        except Exception as e:
            return handle_api_error(e)

@google_chat.action("list_members")
class ListMembers(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            space_name = inputs['space_name']

            params = {"parent": space_name}

            if 'page_size' in inputs:
                params['pageSize'] = inputs['page_size']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']
            if 'filter' in inputs:
                params['filter'] = inputs['filter']

            request = service.spaces().members().list(**params)
            response = request.execute()

            members = []
            for membership in response.get('memberships', []):
                members.append(format_member(membership))

            result = {
                "members": members,
                "result": True
            }

            if 'nextPageToken' in response:
                result["next_page_token"] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "members": [],
                **handle_api_error(e)
            }

@google_chat.action("add_reaction")
class AddReaction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            message_name = inputs['message_name']

            reaction_body = {
                "emoji": inputs['emoji']
            }

            request = service.spaces().messages().reactions().create(
                parent=message_name,
                body=reaction_body
            )
            response = request.execute()

            return {
                "reaction": format_reaction(response),
                "result": True
            }

        except Exception as e:
            return {
                "reaction": {},
                **handle_api_error(e)
            }

@google_chat.action("list_reactions")
class ListReactions(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            message_name = inputs['message_name']

            params = {"parent": message_name}

            if 'page_size' in inputs:
                params['pageSize'] = inputs['page_size']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']
            if 'filter' in inputs:
                params['filter'] = inputs['filter']

            request = service.spaces().messages().reactions().list(**params)
            response = request.execute()

            reactions = []
            for reaction in response.get('reactions', []):
                reactions.append(format_reaction(reaction))

            result = {
                "reactions": reactions,
                "result": True
            }

            if 'nextPageToken' in response:
                result["next_page_token"] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "reactions": [],
                **handle_api_error(e)
            }

@google_chat.action("remove_reaction")
class RemoveReaction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            reaction_name = inputs['reaction_name']

            request = service.spaces().messages().reactions().delete(name=reaction_name)
            request.execute()

            return {"result": True}

        except Exception as e:
            return handle_api_error(e)

@google_chat.action("find_direct_message")
class FindDirectMessage(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_chat_service(context)
            user_name = inputs['user_name']

            request = service.spaces().findDirectMessage(name=user_name)
            response = request.execute()

            return {
                "space": format_space(response),
                "result": True
            }

        except Exception as e:
            return {
                "space": {},
                **handle_api_error(e)
            }
