from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
import json
import base64
import aiohttp
import io

# Create the integration using the config.json
front = Integration.load()

# Front API Base URL
FRONT_API_BASE = "https://api2.frontapp.com"

# ---- Utility Classes ----

class FrontDataParser:
    @staticmethod
    def parse_conversation(raw_conversation: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Front conversation into standardized format."""
        # Required fields
        conversation = {
            "id": raw_conversation.get('id', ''),
            "subject": raw_conversation.get('subject', ''),
            "status": raw_conversation.get('status', ''),
        }

        # Add optional status fields
        if 'status_id' in raw_conversation:
            conversation['status_id'] = raw_conversation['status_id']
        if 'status_category' in raw_conversation:
            conversation['status_category'] = raw_conversation['status_category']
        if 'ticket_ids' in raw_conversation:
            conversation['ticket_ids'] = raw_conversation['ticket_ids']

        # Add optional fields if they exist (these may be None/null which is valid)
        conversation['assignee'] = raw_conversation.get('assignee')
        conversation['recipient'] = raw_conversation.get('recipient')
        conversation['tags'] = raw_conversation.get('tags', [])
        conversation['links'] = raw_conversation.get('links', [])
        conversation['scheduled_reminders'] = raw_conversation.get('scheduled_reminders', [])
        conversation['custom_fields'] = raw_conversation.get('custom_fields', {})
        conversation['metadata'] = raw_conversation.get('metadata', {})

        if 'created_at' in raw_conversation:
            conversation['created_at'] = raw_conversation['created_at']
        if 'waiting_since' in raw_conversation:
            conversation['waiting_since'] = raw_conversation['waiting_since']
        if 'is_private' in raw_conversation:
            conversation['is_private'] = raw_conversation['is_private']

        return conversation

    @staticmethod
    def parse_message(raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw Front message into standardized format."""
        message = {
            "id": raw_message.get('id', ''),
            "type": raw_message.get('type', ''),
            "is_inbound": raw_message.get('is_inbound', False),
            "author": raw_message.get('author'),  # Can be None for external messages
        }

        # Add optional fields if they exist
        if 'recipients' in raw_message:
            message['recipients'] = raw_message['recipients']
        if 'subject' in raw_message:
            message['subject'] = raw_message['subject']
        if 'body' in raw_message:
            message['body'] = raw_message['body']
        if 'created_at' in raw_message:
            message['created_at'] = raw_message['created_at']

        return message

# ---- Action Handlers ----

@front.action("get_inbox")
class GetInboxAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            inbox_id = inputs["inbox_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/inboxes/{inbox_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "inbox": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse inbox
            inbox = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "address": response.get("address", ""),
            }

            # Add optional fields
            if 'type' in response:
                inbox['type'] = response['type']
            if 'send_as' in response:
                inbox['send_as'] = response['send_as']
            if 'is_private' in response:
                inbox['is_private'] = response['is_private']

            return {
                "inbox": inbox,
                "result": True
            }

        except Exception as e:
            return {
                "inbox": {},
                "result": False,
                "error": f"Error getting inbox: {str(e)}"
            }

@front.action("list_inbox_conversations")
class ListInboxConversationsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            inbox_id = inputs["inbox_id"]

            # Build query parameters
            params = {}
            if inputs.get("status"):
                params["status"] = inputs["status"]
            if inputs.get("tag_id"):
                params["tag_id"] = inputs["tag_id"]

            limit = inputs.get("limit", 50)
            params["limit"] = min(limit, 100)

            # Make API call to inbox-specific conversations endpoint
            response = await context.fetch(
                f"{FRONT_API_BASE}/inboxes/{inbox_id}/conversations",
                params=params
            )

            # Check for API errors
            if "error" in response:
                return {
                    "conversations": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse conversations
            conversations = []
            raw_conversations = response.get("_results", [])

            for raw_conv in raw_conversations:
                conversations.append(FrontDataParser.parse_conversation(raw_conv))

            return {
                "conversations": conversations,
                "result": True
            }

        except Exception as e:
            return {
                "conversations": [],
                "result": False,
                "error": f"Error listing inbox conversations: {str(e)}"
            }

@front.action("get_conversation")
class GetConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            conversation_id = inputs["conversation_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/conversations/{conversation_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "conversation": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse conversation - Front returns conversation data directly
            conversation = FrontDataParser.parse_conversation(response)

            return {
                "conversation": conversation,
                "result": True
            }

        except Exception as e:
            return {
                "conversation": {},
                "result": False,
                "error": f"Error getting conversation: {str(e)}"
            }

@front.action("list_conversation_messages")
class ListConversationMessagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            conversation_id = inputs["conversation_id"]
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/conversations/{conversation_id}/messages",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "messages": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse messages
            messages = []
            raw_messages = response.get("_results", [])

            for raw_msg in raw_messages:
                messages.append(FrontDataParser.parse_message(raw_msg))

            return {
                "messages": messages,
                "result": True
            }

        except Exception as e:
            return {
                "messages": [],
                "result": False,
                "error": f"Error listing conversation messages: {str(e)}"
            }

@front.action("create_message_reply")
class CreateMessageReplyAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Reply to an existing conversation in Front.

        ATTACHMENTS: Each attachment must have {filename, content, content_type}
        - filename: "file.pdf"
        - content: Base64-encoded file content (use download_message_attachment to get this)
        - content_type: MIME type like "application/pdf" or "image/jpeg"
        """
        try:
            conversation_id = inputs["conversation_id"]

            # Build message payload for reply
            message_data = {
                "body": inputs["body"]
            }

            # Add optional fields
            if inputs.get("to"):
                message_data["to"] = inputs["to"]
            if inputs.get("cc"):
                message_data["cc"] = inputs["cc"]
            if inputs.get("bcc"):
                message_data["bcc"] = inputs["bcc"]
            if inputs.get("sender_name"):
                message_data["sender_name"] = inputs["sender_name"]
            if inputs.get("subject"):
                message_data["subject"] = inputs["subject"]
            if inputs.get("author_id"):
                message_data["author_id"] = inputs["author_id"]
            if inputs.get("channel_id"):
                message_data["channel_id"] = inputs["channel_id"]
            if inputs.get("text"):
                message_data["text"] = inputs["text"]
            if inputs.get("quote_body"):
                message_data["quote_body"] = inputs["quote_body"]
            if inputs.get("signature_id"):
                message_data["signature_id"] = inputs["signature_id"]
            if inputs.get("should_add_default_signature") is not None:
                message_data["should_add_default_signature"] = inputs["should_add_default_signature"]

            # Check if we have files uploaded in conversation (like Google Slides)
            files = inputs.get("files", [])
            file_obj = inputs.get("file")  # Single file

            # Convert uploaded files to attachment format
            attachments = []
            if file_obj:
                files = [file_obj]

            if files:
                for f in files:
                    attachments.append({
                        "filename": f.get("name", "attachment"),
                        "content": f.get("content", ""),
                        "content_type": f.get("contentType", "application/octet-stream")
                    })

            if attachments:
                # Use multipart/form-data for attachments
                response = await self._send_reply_with_attachments(
                    context, conversation_id, message_data, attachments
                )
            else:
                # Use JSON for messages without attachments
                response = await context.fetch(
                    f"{FRONT_API_BASE}/conversations/{conversation_id}/messages",
                    method="POST",
                    json=message_data
                )

            # Check for API errors
            if "error" in response:
                return {
                    "message_uid": "",
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Front returns message_uid for async processing
            return {
                "message_uid": response.get("message_uid", ""),
                "result": True
            }

        except Exception as e:
            return {
                "message_uid": "",
                "result": False,
                "error": f"Error creating message reply: {str(e)}"
            }

    async def _send_reply_with_attachments(
        self, context: ExecutionContext, conversation_id: str,
        message_data: Dict[str, Any], attachments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send reply with attachments using multipart/form-data"""
        # Get auth token from context
        auth_token = None
        if context.auth and "credentials" in context.auth:
            auth_token = context.auth["credentials"].get("access_token")

        if not auth_token:
            raise Exception("No authentication token available")

        # Build multipart form data
        form = aiohttp.FormData()

        # Add body field - convert plain text newlines to HTML if needed
        body_content = message_data['body']

        # If body doesn't contain HTML tags, convert newlines to <br> for proper rendering
        if '<' not in body_content and '>' not in body_content:
            # Plain text - convert newlines to HTML breaks
            body_content = body_content.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')

        form.add_field('body', body_content)

        # Add optional fields (for replies)
        if 'to' in message_data:
            for recipient in message_data['to']:
                form.add_field('to[]', recipient)
        if 'cc' in message_data:
            for recipient in message_data['cc']:
                form.add_field('cc[]', recipient)
        if 'bcc' in message_data:
            for recipient in message_data['bcc']:
                form.add_field('bcc[]', recipient)
        if 'subject' in message_data:
            form.add_field('subject', message_data['subject'])
        if 'author_id' in message_data:
            form.add_field('author_id', message_data['author_id'])
        if 'sender_name' in message_data:
            form.add_field('sender_name', message_data['sender_name'])
        if 'channel_id' in message_data:
            form.add_field('channel_id', message_data['channel_id'])
        if 'text' in message_data:
            form.add_field('text', message_data['text'])
        if 'quote_body' in message_data:
            form.add_field('quote_body', message_data['quote_body'])
        if 'signature_id' in message_data:
            form.add_field('signature_id', message_data['signature_id'])
        if 'should_add_default_signature' in message_data:
            form.add_field('should_add_default_signature', str(message_data['should_add_default_signature']).lower())

        # Add each attachment as binary file
        for idx, attachment in enumerate(attachments):
            filename = attachment.get("filename", f"attachment_{idx}")
            content_b64 = attachment.get("content", "")
            content_type = attachment.get("content_type", "application/octet-stream")

            # Validate content exists
            if not content_b64:
                raise Exception(f"Attachment '{filename}' has no content provided")

            # Clean up base64 string (remove whitespace/newlines that might be present)
            content_b64_cleaned = content_b64.strip().replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '')

            # Check length before and after cleaning
            original_length = len(content_b64)
            cleaned_length = len(content_b64_cleaned)

            # Base64 must be multiple of 4 (accounting for padding)
            # If it's not, check if adding padding would make it valid
            padding_needed = cleaned_length % 4
            if padding_needed != 0:
                content_b64_cleaned += '=' * (4 - padding_needed)

            # Validate minimum size - a small file should be at least 100 chars in base64
            # PDFs and images should be much larger (typically thousands of chars)
            if cleaned_length < 100:
                raise Exception(
                    f"Attachment '{filename}' has suspiciously short base64 content "
                    f"({cleaned_length} characters after cleaning from {original_length} original). "
                    f"This suggests the content may be truncated or incomplete. "
                    f"Expected at least 100 characters for a valid file."
                )

            # Decode base64 content
            try:
                file_bytes = base64.b64decode(content_b64_cleaned, validate=True)
            except Exception as e:
                raise Exception(
                    f"Failed to decode attachment '{filename}': {str(e)}. "
                    f"Content length: {cleaned_length} chars. "
                    f"Make sure the content is valid base64-encoded data."
                )

            # Validate file is not empty after decoding
            if not file_bytes or len(file_bytes) == 0:
                raise Exception(f"Attachment '{filename}' decoded to empty content")

            # Log file size for debugging
            file_size = len(file_bytes)

            # Wrap bytes in BytesIO to create file-like object (like open('file', 'rb'))
            file_obj = io.BytesIO(file_bytes)
            file_obj.seek(0)  # Ensure we're at the beginning of the stream

            # Add file to form data - Front expects 'attachments[]' for multiple files
            form.add_field(
                'attachments[]',
                file_obj,
                filename=filename,
                content_type=content_type
            )

        # Send request with aiohttp
        url = f"{FRONT_API_BASE}/conversations/{conversation_id}/messages"
        headers = {
            "Authorization": f"Bearer {auth_token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, headers=headers) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {error_text}"}

                return await resp.json()

@front.action("get_message")
class GetMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            message_id = inputs["message_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/messages/{message_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "message": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse message
            message = FrontDataParser.parse_message(response)

            return {
                "message": message,
                "result": True
            }

        except Exception as e:
            return {
                "message": {},
                "result": False,
                "error": f"Error getting message: {str(e)}"
            }

@front.action("download_message_attachment")
class DownloadMessageAttachmentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Download a message attachment and return base64-encoded content.

        WORKFLOW: Call get_message first to get attachment URL from message.attachments[].url,
        then pass that URL to this action. Returns base64 content ready for create_message attachments.
        """
        try:
            attachment_url = inputs["attachment_url"]

            # Get auth token from context
            auth_token = None
            if context.auth and "credentials" in context.auth:
                auth_token = context.auth["credentials"].get("access_token")

            if not auth_token:
                raise Exception("No authentication token available")

            # Download attachment from Front's download endpoint
            headers = {"Authorization": f"Bearer {auth_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment_url, headers=headers) as resp:
                    if resp.status >= 400:
                        error_text = await resp.text()
                        return {
                            "file": {},
                            "result": False,
                            "error": f"HTTP {resp.status}: {error_text}"
                        }

                    # Read complete file content as binary
                    file_bytes = await resp.read()

                    # Extract content type from response
                    content_type = resp.headers.get('content-type', 'application/octet-stream')

                    # Extract filename from Content-Disposition header or URL
                    filename = "attachment"
                    content_disposition = resp.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"\'')
                    else:
                        from urllib.parse import urlparse
                        url_path = urlparse(attachment_url).path
                        if url_path:
                            filename = url_path.split('/')[-1] or "attachment"

                    # Encode to base64 for JSON transport and attachment forwarding
                    content_b64 = base64.b64encode(file_bytes).decode('utf-8')

                    return {
                        "file": {
                            "content": content_b64,  # Use this in create_message attachments
                            "name": filename,
                            "contentType": content_type,
                            "size": len(file_bytes)
                        },
                        "result": True
                    }

        except Exception as e:
            return {
                "file": {},
                "result": False,
                "error": f"Error downloading attachment: {str(e)}"
            }

@front.action("create_message")
class CreateMessageAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Create a new message in Front (starts a new conversation).

        ATTACHMENTS: Each attachment must have {filename, content, content_type}
        - filename: "file.pdf"
        - content: Base64-encoded file content (use download_message_attachment to get this)
        - content_type: MIME type like "application/pdf" or "image/jpeg"
        """
        try:
            channel_id = inputs["channel_id"]

            # Build message payload for new message
            message_data = {
                "body": inputs["body"],
                "to": inputs["to"]
            }

            # Add optional fields
            if inputs.get("cc"):
                message_data["cc"] = inputs["cc"]
            if inputs.get("bcc"):
                message_data["bcc"] = inputs["bcc"]
            if inputs.get("subject"):
                message_data["subject"] = inputs["subject"]
            if inputs.get("author_id"):
                message_data["author_id"] = inputs["author_id"]
            if inputs.get("sender_name"):
                message_data["sender_name"] = inputs["sender_name"]
            if inputs.get("text"):
                message_data["text"] = inputs["text"]
            if inputs.get("signature_id"):
                message_data["signature_id"] = inputs["signature_id"]
            if inputs.get("should_add_default_signature") is not None:
                message_data["should_add_default_signature"] = inputs["should_add_default_signature"]

            # Check if we have files uploaded in conversation (like Google Slides)
            files = inputs.get("files", [])
            file_obj = inputs.get("file")  # Single file

            # Convert uploaded files to attachment format
            attachments = []
            if file_obj:
                files = [file_obj]

            if files:
                for f in files:
                    attachments.append({
                        "filename": f.get("name", "attachment"),
                        "content": f.get("content", ""),
                        "content_type": f.get("contentType", "application/octet-stream")
                    })

            if attachments:
                # Use multipart/form-data for attachments
                response = await self._send_with_attachments(
                    context, channel_id, message_data, attachments
                )
            else:
                # Use JSON for messages without attachments
                response = await context.fetch(
                    f"{FRONT_API_BASE}/channels/{channel_id}/messages",
                    method="POST",
                    json=message_data
                )

            # Check for API errors
            if "error" in response:
                return {
                    "message_uid": "",
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Front returns message_uid for async processing
            return {
                "message_uid": response.get("message_uid", ""),
                "result": True
            }

        except Exception as e:
            return {
                "message_uid": "",
                "result": False,
                "error": f"Error creating message: {str(e)}"
            }

    async def _send_with_attachments(
        self, context: ExecutionContext, channel_id: str,
        message_data: Dict[str, Any], attachments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send message with attachments using multipart/form-data"""
        # Get auth token from context
        auth_token = None
        if context.auth and "credentials" in context.auth:
            auth_token = context.auth["credentials"].get("access_token")

        if not auth_token:
            raise Exception("No authentication token available")

        # Build multipart form data
        form = aiohttp.FormData()

        # Add body field - convert plain text newlines to HTML if needed
        body_content = message_data['body']

        # If body doesn't contain HTML tags, convert newlines to <br> for proper rendering
        if '<' not in body_content and '>' not in body_content:
            # Plain text - convert newlines to HTML breaks
            body_content = body_content.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')

        form.add_field('body', body_content)

        # Add 'to' recipients as array
        if 'to' in message_data:
            for recipient in message_data['to']:
                form.add_field('to[]', recipient)

        # Add optional fields
        if 'cc' in message_data:
            for recipient in message_data['cc']:
                form.add_field('cc[]', recipient)
        if 'bcc' in message_data:
            for recipient in message_data['bcc']:
                form.add_field('bcc[]', recipient)
        if 'subject' in message_data:
            form.add_field('subject', message_data['subject'])
        if 'author_id' in message_data:
            form.add_field('author_id', message_data['author_id'])
        if 'sender_name' in message_data:
            form.add_field('sender_name', message_data['sender_name'])
        if 'text' in message_data:
            form.add_field('text', message_data['text'])
        if 'signature_id' in message_data:
            form.add_field('signature_id', message_data['signature_id'])
        if 'should_add_default_signature' in message_data:
            form.add_field('should_add_default_signature', str(message_data['should_add_default_signature']).lower())

        # Add each attachment as binary file
        for idx, attachment in enumerate(attachments):
            filename = attachment.get("filename", f"attachment_{idx}")
            content_b64 = attachment.get("content", "")
            content_type = attachment.get("content_type", "application/octet-stream")

            # Validate content exists
            if not content_b64:
                raise Exception(f"Attachment '{filename}' has no content provided")

            # Clean up base64 string (remove whitespace/newlines that might be present)
            content_b64_cleaned = content_b64.strip().replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '')

            # Check length before and after cleaning
            original_length = len(content_b64)
            cleaned_length = len(content_b64_cleaned)

            # Base64 must be multiple of 4 (accounting for padding)
            # If it's not, check if adding padding would make it valid
            padding_needed = cleaned_length % 4
            if padding_needed != 0:
                content_b64_cleaned += '=' * (4 - padding_needed)

            # Validate minimum size - a small file should be at least 100 chars in base64
            # PDFs and images should be much larger (typically thousands of chars)
            if cleaned_length < 100:
                raise Exception(
                    f"Attachment '{filename}' has suspiciously short base64 content "
                    f"({cleaned_length} characters after cleaning from {original_length} original). "
                    f"This suggests the content may be truncated or incomplete. "
                    f"Expected at least 100 characters for a valid file."
                )

            # Decode base64 content
            try:
                file_bytes = base64.b64decode(content_b64_cleaned, validate=True)
            except Exception as e:
                raise Exception(
                    f"Failed to decode attachment '{filename}': {str(e)}. "
                    f"Content length: {cleaned_length} chars. "
                    f"Make sure the content is valid base64-encoded data."
                )

            # Validate file is not empty after decoding
            if not file_bytes or len(file_bytes) == 0:
                raise Exception(f"Attachment '{filename}' decoded to empty content")

            # Log file size for debugging
            file_size = len(file_bytes)

            # Wrap bytes in BytesIO to create file-like object (like open('file', 'rb'))
            file_obj = io.BytesIO(file_bytes)
            file_obj.seek(0)  # Ensure we're at the beginning of the stream

            # Add file to form data - Front expects 'attachments[]' for multiple files
            form.add_field(
                'attachments[]',
                file_obj,
                filename=filename,
                content_type=content_type
            )

        # Send request with aiohttp
        url = f"{FRONT_API_BASE}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bearer {auth_token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, headers=headers) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {error_text}"}

                return await resp.json()

@front.action("list_channels")
class ListChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/channels",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "channels": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse channels
            channels = []
            raw_channels = response.get("_results", [])

            for raw_channel in raw_channels:
                channel = {
                    "id": raw_channel.get("id", ""),
                    "name": raw_channel.get("name", ""),
                    "type": raw_channel.get("types", raw_channel.get("type", "")),  # Front API uses "types" field
                }
                # Add optional fields
                if 'address' in raw_channel:
                    channel['address'] = raw_channel['address']
                if 'send_as' in raw_channel:
                    channel['send_as'] = raw_channel['send_as']
                if 'settings' in raw_channel:
                    channel['settings'] = raw_channel['settings']

                channels.append(channel)

            return {
                "channels": channels,
                "result": True
            }

        except Exception as e:
            return {
                "channels": [],
                "result": False,
                "error": f"Error listing channels: {str(e)}"
            }

@front.action("list_inbox_channels")
class ListInboxChannelsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            inbox_id = inputs["inbox_id"]
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/inboxes/{inbox_id}/channels",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "channels": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse channels
            channels = []
            raw_channels = response.get("_results", [])

            for raw_channel in raw_channels:
                channel = {
                    "id": raw_channel.get("id", ""),
                    "name": raw_channel.get("name", ""),
                    "type": raw_channel.get("types", raw_channel.get("type", "")),  # Front API uses "types" field
                }
                # Add optional fields
                if 'address' in raw_channel:
                    channel['address'] = raw_channel['address']
                if 'send_as' in raw_channel:
                    channel['send_as'] = raw_channel['send_as']
                if 'settings' in raw_channel:
                    channel['settings'] = raw_channel['settings']

                channels.append(channel)

            return {
                "channels": channels,
                "result": True
            }

        except Exception as e:
            return {
                "channels": [],
                "result": False,
                "error": f"Error listing inbox channels: {str(e)}"
            }

@front.action("get_channel")
class GetChannelAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            channel_id = inputs["channel_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/channels/{channel_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "channel": {
                        "id": "",
                        "name": "",
                        "type": ""
                    },
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse channel - Note: Front API returns "types" but we standardize to "type"
            channel = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "type": response.get("types", response.get("type", "")),  # Front API uses "types" field
            }

            # Add optional fields
            if 'address' in response:
                channel['address'] = response['address']
            if 'send_as' in response:
                channel['send_as'] = response['send_as']
            if 'is_private' in response:
                channel['is_private'] = response['is_private']
            if 'settings' in response:
                channel['settings'] = response['settings']

            return {
                "channel": channel,
                "result": True
            }

        except Exception as e:
            return {
                "channel": {
                    "id": "",
                    "name": "",
                    "type": ""
                },
                "result": False,
                "error": f"Error getting channel: {str(e)}"
            }

@front.action("list_message_templates")
class ListMessageTemplatesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/message_templates",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "templates": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse templates
            templates = []
            raw_templates = response.get("_results", [])

            for raw_template in raw_templates:
                template = {
                    "id": raw_template.get("id", ""),
                    "name": raw_template.get("name", ""),
                    "subject": raw_template.get("subject", ""),
                    "body": raw_template.get("body", ""),
                    "attachments": raw_template.get("attachments", []),
                    "metadata": raw_template.get("metadata", {})
                }

                templates.append(template)

            return {
                "templates": templates,
                "result": True
            }

        except Exception as e:
            return {
                "templates": [],
                "result": False,
                "error": f"Error listing message templates: {str(e)}"
            }

@front.action("get_message_template")
class GetMessageTemplateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            template_id = inputs["message_template_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/message_templates/{template_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "template": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse template
            template = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "subject": response.get("subject", ""),
                "body": response.get("body", ""),
                "attachments": response.get("attachments", []),
                "metadata": response.get("metadata", {})
            }

            return {
                "template": template,
                "result": True
            }

        except Exception as e:
            return {
                "template": {},
                "result": False,
                "error": f"Error getting message template: {str(e)}"
            }

@front.action("update_conversation")
class UpdateConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            conversation_id = inputs["conversation_id"]

            # Build update payload
            update_data = {}

            # Use 'in' to check if key exists, allows None values (for unassigning)
            if "assignee_id" in inputs:
                update_data["assignee_id"] = inputs["assignee_id"]
            if "inbox_id" in inputs and inputs["inbox_id"]:
                update_data["inbox_id"] = inputs["inbox_id"]
            if "status" in inputs and inputs["status"]:
                update_data["status"] = inputs["status"]
            if "status_id" in inputs and inputs["status_id"]:
                update_data["status_id"] = inputs["status_id"]
            if "tags" in inputs and inputs["tags"]:
                update_data["tag_ids"] = inputs["tags"]
            if "custom_fields" in inputs and inputs["custom_fields"]:
                update_data["custom_fields"] = inputs["custom_fields"]

            if not update_data:
                return {
                    "conversation": {},
                    "result": False,
                    "error": "No valid update fields provided"
                }

            # Update conversation
            response = await context.fetch(
                f"{FRONT_API_BASE}/conversations/{conversation_id}",
                method="PATCH",
                json=update_data
            )

            # Front API may return None for successful PATCH (HTTP 204 No Content)
            # In that case, fetch the updated conversation
            if response is None:
                # Fetch the updated conversation to return
                get_response = await context.fetch(
                    f"{FRONT_API_BASE}/conversations/{conversation_id}"
                )

                if get_response is None or "error" in get_response:
                    return {
                        "conversation": {},
                        "result": False,
                        "error": f"Update may have succeeded but failed to fetch updated conversation: {get_response.get('error', 'Unknown error') if get_response else 'No response'}"
                    }

                conversation = FrontDataParser.parse_conversation(get_response)
                return {
                    "conversation": conversation,
                    "result": True
                }

            # Check for API errors in response
            if "error" in response:
                return {
                    "conversation": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse response conversation
            conversation = FrontDataParser.parse_conversation(response)

            return {
                "conversation": conversation,
                "result": True
            }

        except Exception as e:
            return {
                "conversation": {},
                "result": False,
                "error": f"Error updating conversation: {str(e)}"
            }

@front.action("list_inboxes")
class ListInboxesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/inboxes",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "inboxes": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse inboxes
            inboxes = []
            raw_inboxes = response.get("_results", [])

            for raw_inbox in raw_inboxes:
                inbox = {
                    "id": raw_inbox.get("id", ""),
                    "name": raw_inbox.get("name", ""),
                    "address": raw_inbox.get("address", ""),
                }
                # Add optional fields
                if 'type' in raw_inbox:
                    inbox['type'] = raw_inbox['type']
                if 'send_as' in raw_inbox:
                    inbox['send_as'] = raw_inbox['send_as']

                inboxes.append(inbox)

            return {
                "inboxes": inboxes,
                "result": True
            }

        except Exception as e:
            return {
                "inboxes": [],
                "result": False,
                "error": f"Error listing inboxes: {str(e)}"
            }

@front.action("list_teammates")
class ListTeammatesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            limit = inputs.get("limit", 50)

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/teammates",
                params={"limit": min(limit, 100)}
            )

            # Check for API errors
            if "error" in response:
                return {
                    "teammates": [],
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse teammates
            teammates = []
            raw_teammates = response.get("_results", [])

            for raw_teammate in raw_teammates:
                teammate = {
                    "id": raw_teammate.get("id", ""),
                    "email": raw_teammate.get("email", ""),
                    "username": raw_teammate.get("username", ""),
                    "first_name": raw_teammate.get("first_name", ""),
                    "last_name": raw_teammate.get("last_name", ""),
                    "is_admin": raw_teammate.get("is_admin", False),
                    "is_available": raw_teammate.get("is_available", True),
                    "is_blocked": raw_teammate.get("is_blocked", False),
                    "type": raw_teammate.get("type", "user"),
                    "custom_fields": raw_teammate.get("custom_fields", {})
                }

                teammates.append(teammate)

            return {
                "teammates": teammates,
                "result": True
            }

        except Exception as e:
            return {
                "teammates": [],
                "result": False,
                "error": f"Error listing teammates: {str(e)}"
            }

@front.action("get_teammate")
class GetTeammateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            teammate_id = inputs["teammate_id"]

            # Make API call
            response = await context.fetch(
                f"{FRONT_API_BASE}/teammates/{teammate_id}"
            )

            # Check for API errors
            if "error" in response:
                return {
                    "teammate": {},
                    "result": False,
                    "error": f"API request failed: {response.get('error', 'Unknown error')}"
                }

            # Parse teammate
            teammate = {
                "id": response.get("id", ""),
                "email": response.get("email", ""),
                "username": response.get("username", ""),
                "first_name": response.get("first_name", ""),
                "last_name": response.get("last_name", ""),
                "is_admin": response.get("is_admin", False),
                "is_available": response.get("is_available", True),
                "is_blocked": response.get("is_blocked", False),
                "type": response.get("type", "user"),
                "custom_fields": response.get("custom_fields", {})
            }

            return {
                "teammate": teammate,
                "result": True
            }

        except Exception as e:
            return {
                "teammate": {},
                "result": False,
                "error": f"Error getting teammate: {str(e)}"
            }

# ---- Helper Actions for Name-Based Lookups ----

@front.action("find_teammate")
class FindTeammateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Find teammates by searching name or email (client-side filtering).
        This is a helper function since Front API doesn't support search.
        """
        try:
            search_query = inputs["search_query"].lower()

            # Use the existing list_teammates action
            list_action = ListTeammatesAction()
            list_result = await list_action.execute({"limit": 100}, context)

            if not list_result["result"]:
                return {
                    "teammates": [],
                    "result": False,
                    "error": f"Failed to fetch teammates: {list_result.get('error', 'Unknown error')}"
                }

            # Filter teammates by search query (case-insensitive partial match)
            teammates = list_result["teammates"]
            matching_teammates = []

            for teammate in teammates:
                # Search in first_name, last_name, username, email
                first_name = (teammate.get("first_name") or "").lower()
                last_name = (teammate.get("last_name") or "").lower()
                full_name = f"{first_name} {last_name}".strip()
                username = (teammate.get("username") or "").lower()
                email = (teammate.get("email") or "").lower()

                # Check if search query matches any field
                if (search_query in first_name or
                    search_query in last_name or
                    search_query in full_name or
                    search_query in username or
                    search_query in email):
                    matching_teammates.append(teammate)

            return {
                "teammates": matching_teammates,
                "result": True,
                "count": len(matching_teammates)
            }

        except Exception as e:
            return {
                "teammates": [],
                "result": False,
                "error": f"Error finding teammate: {str(e)}"
            }

@front.action("find_inbox")
class FindInboxAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Find inboxes by searching name (client-side filtering).
        This is a helper function since Front API doesn't support search.
        """
        try:
            inbox_name = inputs["inbox_name"].lower()

            # Use the existing list_inboxes action
            list_action = ListInboxesAction()
            list_result = await list_action.execute({"limit": 100}, context)

            if not list_result["result"]:
                return {
                    "inboxes": [],
                    "result": False,
                    "error": f"Failed to fetch inboxes: {list_result.get('error', 'Unknown error')}"
                }

            # Filter inboxes by name (case-insensitive partial match)
            inboxes = list_result["inboxes"]
            matching_inboxes = []

            for inbox in inboxes:
                name = (inbox.get("name") or "").lower()

                # Check if search query matches name
                if inbox_name in name:
                    matching_inboxes.append(inbox)

            return {
                "inboxes": matching_inboxes,
                "result": True,
                "count": len(matching_inboxes)
            }

        except Exception as e:
            return {
                "inboxes": [],
                "result": False,
                "error": f"Error finding inbox: {str(e)}"
            }

@front.action("find_conversation")
class FindConversationAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        """
        Find conversations by searching recipient or subject (client-side filtering).
        This is a helper function since Front API doesn't support search.
        """
        try:
            inbox_id = inputs["inbox_id"]
            search_query = inputs["search_query"].lower()

            # Use the existing list_inbox_conversations action
            list_action = ListInboxConversationsAction()
            list_result = await list_action.execute({
                "inbox_id": inbox_id,
                "limit": 100
            }, context)

            if not list_result["result"]:
                return {
                    "conversations": [],
                    "result": False,
                    "error": f"Failed to fetch conversations: {list_result.get('error', 'Unknown error')}"
                }

            # Filter conversations by search query (case-insensitive partial match)
            conversations = list_result["conversations"]
            matching_conversations = []

            for conversation in conversations:
                # Search in subject
                subject = (conversation.get("subject") or "").lower()

                # Search in recipient fields (handle, name, email)
                recipient = conversation.get("recipient") or {}
                recipient_handle = (recipient.get("handle") or "").lower()
                recipient_name = (recipient.get("name") or "").lower()
                # Some recipients may have email in handle or other fields
                recipient_str = f"{recipient_handle} {recipient_name}".lower()

                # Check if search query matches any field
                if (search_query in subject or
                    search_query in recipient_handle or
                    search_query in recipient_name or
                    search_query in recipient_str):
                    matching_conversations.append(conversation)

            return {
                "conversations": matching_conversations,
                "result": True,
                "count": len(matching_conversations)
            }

        except Exception as e:
            return {
                "conversations": [],
                "result": False,
                "error": f"Error finding conversation: {str(e)}"
            }


