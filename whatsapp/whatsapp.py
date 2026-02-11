from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any
import re
import os

whatsapp = Integration.load()

def get_whatsapp_creds(auth: Dict[str, Any]) -> Dict[str, str]:
    """Helper to extract credentials handling multiple naming conventions."""
    # Check if credentials are nested under 'credentials' key (common in some SDK versions)
    creds_source = auth.get("credentials", auth)
    
    access_token = creds_source.get("access_token") or creds_source.get("accessToken") or creds_source.get("token")
    
    if not access_token:
        keys = list(auth.keys())
        raise ValueError(f"Missing access_token in auth context. Available keys: {keys}")
        
    return {
        "access_token": access_token
    }

def validate_phone_number(phone: str) -> bool:
    """Validate that the phone number is in E.164 format."""
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone))

def validate_media_url(url: str) -> bool:
    """Validate that the media URL is a valid HTTPS URL."""
    return url.startswith("https://")

# ---- Action Handlers ----

@whatsapp.action("send_message")
class SendMessageAction(ActionHandler):
    """
    Action to send a text message to a WhatsApp user.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        to = inputs["to"]
        message = inputs["message"]
        phone_number_id = inputs["phone_number_id"]
        
        # Validate phone number format to ensure it meets E.164 standards
        if not validate_phone_number(to):
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": "Invalid phone number format. Use format: +1234567890"
            })
        
        try:
            creds = get_whatsapp_creds(context.auth)
            
            # Call WhatsApp Business API endpoint for sending messages
            response = await context.fetch(
                f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {creds['access_token']}",
                    "Content-Type": "application/json"
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to.lstrip('+'), # WhatsApp API requires phone numbers without the '+' prefix
                    "type": "text",
                    "text": {"body": message}
                }
            )
            
            # Check for successful response containing message ID
            if "messages" in response and response["messages"]:
                message_id = response["messages"][0]["id"]
                return ActionResult(data={
                    "message_id": message_id,
                    "success": True
                })
            else:
                # Handle API errors or unexpected response structure
                return ActionResult(data={
                    "message_id": "",
                    "success": False,
                    "error": response.get("error", {}).get("message", "Unknown error")
                })
                
        except Exception as e:
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": f"Failed to send message: {str(e)}"
            })


@whatsapp.action("send_template_message")
class SendTemplateMessageAction(ActionHandler):
    """
    Action to send a pre-approved template message.
    Templates are required for business-initiated conversations.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        to = inputs["to"]
        template_name = inputs["template_name"]
        phone_number_id = inputs["phone_number_id"]
        language_code = inputs.get("language_code", "en")
        parameters = inputs.get("parameters", [])
        
        # Validate phone number format
        if not validate_phone_number(to):
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": "Invalid phone number format. Use format: +1234567890"
            })
        
        try:
            creds = get_whatsapp_creds(context.auth)
            
            # Build template message payload
            template_payload = {
                "messaging_product": "whatsapp",
                "to": to.lstrip('+'),
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code}
                }
            }
            
            # Add parameters if provided (for variable substitution in the template)
            if parameters:
                template_payload["template"]["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in parameters]
                }]
            
            # Send the request
            response = await context.fetch(
                f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {creds['access_token']}",
                    "Content-Type": "application/json"
                },
                json=template_payload
            )
            
            if "messages" in response and response["messages"]:
                message_id = response["messages"][0]["id"]
                return ActionResult(data={
                    "message_id": message_id,
                    "success": True
                })
            else:
                return ActionResult(data={
                    "message_id": "",
                    "success": False,
                    "error": response.get("error", {}).get("message", "Unknown error")
                })
                
        except Exception as e:
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": f"Failed to send template message: {str(e)}"
            })


@whatsapp.action("send_media_message")
class SendMediaMessageAction(ActionHandler):
    """
    Action to send media (images, documents, audio, video) to a user.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        to = inputs["to"]
        media_type = inputs["media_type"]
        media_url = inputs["media_url"]
        phone_number_id = inputs["phone_number_id"]
        caption = inputs.get("caption", "")
        filename = inputs.get("filename", "")
        
        # Validate phone number format
        if not validate_phone_number(to):
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": "Invalid phone number format. Use format: +1234567890"
            })
            
        # Validate media URL
        if not validate_media_url(media_url):
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": "Invalid media URL. Must be a publicly accessible HTTPS URL."
            })
        
        try:
            creds = get_whatsapp_creds(context.auth)

            # Build basic media message payload
            media_payload = {
                "messaging_product": "whatsapp",
                "to": to.lstrip('+'),
                "type": media_type
            }
            
            # Configure media object based on type
            media_object = {"link": media_url}
            
            # Add filename for documents
            if media_type == "document" and filename:
                media_object["filename"] = filename
            
            # Add caption if supported for the media type
            if caption and media_type in ["image", "video", "document"]:
                media_object["caption"] = caption
                
            media_payload[media_type] = media_object
            
            # Send the request
            response = await context.fetch(
                f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {creds['access_token']}",
                    "Content-Type": "application/json"
                },
                json=media_payload
            )
            
            if "messages" in response and response["messages"]:
                message_id = response["messages"][0]["id"]
                return ActionResult(data={
                    "message_id": message_id,
                    "success": True
                })
            else:
                return ActionResult(data={
                    "message_id": "",
                    "success": False,
                    "error": response.get("error", {}).get("message", "Unknown error")
                })
                
        except Exception as e:
            return ActionResult(data={
                "message_id": "",
                "success": False,
                "error": f"Failed to send media message: {str(e)}"
            })


@whatsapp.action("get_phone_number_health")
class GetPhoneNumberHealthAction(ActionHandler):
    """
    Action to check the status and quality rating of the business phone number.
    """
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        phone_number_id = inputs["phone_number_id"]
        
        try:
            creds = get_whatsapp_creds(context.auth)

            # Get phone number status and quality rating from Graph API
            response = await context.fetch(
                f"https://graph.facebook.com/v18.0/{phone_number_id}",
                method="GET",
                params={"fields": "status,quality_rating"},
                headers={
                    "Authorization": f"Bearer {creds['access_token']}",
                    "Content-Type": "application/json"
                }
            )
            
            if "status" in response:
                return ActionResult(data={
                    "status": response.get("status", "UNKNOWN"),
                    "quality_rating": response.get("quality_rating", "UNKNOWN"),
                    "success": True
                })
            else:
                return ActionResult(data={
                    "status": "UNKNOWN",
                    "quality_rating": "UNKNOWN",
                    "success": False,
                    "error": response.get("error", {}).get("message", "Unknown error")
                })
                
        except Exception as e:
            return ActionResult(data={
                "status": "UNKNOWN",
                "quality_rating": "UNKNOWN",
                "success": False,
                "error": f"Failed to get phone number health: {str(e)}"
            })
