from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler, ActionResult, ActionError
from typing import Dict, Any
import re
from urllib.parse import urlparse

whatsapp = Integration.load()

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


def get_whatsapp_creds(auth: Dict[str, Any]) -> Dict[str, str]:
    """Helper to extract credentials handling multiple naming conventions."""
    creds_source = auth.get("credentials", auth)

    access_token = creds_source.get("access_token") or creds_source.get("accessToken") or creds_source.get("token")

    if not access_token:
        raise ValueError("Missing access_token in auth context.")

    return {"access_token": access_token}


def validate_phone_number(phone: str) -> bool:
    """Validate that the phone number is in E.164 format (with or without + prefix)."""
    pattern = r"^\+?[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone))


def validate_media_url(url: str) -> bool:
    try:
        u = urlparse(url)
        return u.scheme == "https" and bool(u.netloc)
    except Exception:
        return False


def validate_phone_number_id(phone_number_id: str) -> bool:
    """Validate that the phone number ID is a numeric string."""
    return phone_number_id.isdigit()


def _extract_api_error(data: Any) -> str:
    """Pull a human-readable error message out of a Graph API response body."""
    if isinstance(data, dict):
        return data.get("error", {}).get("message", "Unknown error")
    return f"Unexpected response: {data}"


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

        if not validate_phone_number_id(phone_number_id):
            return ActionError(message="Invalid phone number ID. Must be a numeric string.")

        if not validate_phone_number(to):
            return ActionError(message="Invalid phone number format. Use format: +1234567890 or 1234567890")

        try:
            creds = get_whatsapp_creds(context.auth)

            response = await context.fetch(
                f"{GRAPH_API_BASE}/{phone_number_id}/messages",
                method="POST",
                headers={"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to.lstrip("+"),
                    "type": "text",
                    "text": {"body": message},
                },
            )

            data = response.data
            if isinstance(data, dict) and data.get("messages"):
                return ActionResult(data={"message_id": data["messages"][0]["id"]})

            return ActionError(message=_extract_api_error(data))

        except Exception as e:
            return ActionError(message=f"Failed to send message: {str(e)}")


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
        language_code = inputs["language_code"]
        parameters = inputs.get("parameters", [])

        if not validate_phone_number_id(phone_number_id):
            return ActionError(message="Invalid phone number ID. Must be a numeric string.")

        if not validate_phone_number(to):
            return ActionError(message="Invalid phone number format. Use format: +1234567890 or 1234567890")

        try:
            creds = get_whatsapp_creds(context.auth)

            template_payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": "template",
                "template": {"name": template_name, "language": {"code": language_code}},
            }

            if parameters:
                template_payload["template"]["components"] = [
                    {"type": "body", "parameters": [{"type": "text", "text": param} for param in parameters]}
                ]

            response = await context.fetch(
                f"{GRAPH_API_BASE}/{phone_number_id}/messages",
                method="POST",
                headers={"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json"},
                json=template_payload,
            )

            data = response.data
            if isinstance(data, dict) and data.get("messages"):
                return ActionResult(data={"message_id": data["messages"][0]["id"]})

            return ActionError(message=_extract_api_error(data))

        except Exception as e:
            return ActionError(message=f"Failed to send template message: {str(e)}")


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

        if not validate_phone_number_id(phone_number_id):
            return ActionError(message="Invalid phone number ID. Must be a numeric string.")

        if not validate_phone_number(to):
            return ActionError(message="Invalid phone number format. Use format: +1234567890 or 1234567890")

        if not validate_media_url(media_url):
            return ActionError(message="Invalid media URL. Must be a publicly accessible HTTPS URL.")

        try:
            creds = get_whatsapp_creds(context.auth)

            media_payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": media_type,
            }

            media_object: Dict[str, Any] = {"link": media_url}

            if media_type == "document" and filename:
                media_object["filename"] = filename

            if caption and media_type in ["image", "video", "document"]:
                media_object["caption"] = caption

            media_payload[media_type] = media_object

            response = await context.fetch(
                f"{GRAPH_API_BASE}/{phone_number_id}/messages",
                method="POST",
                headers={"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json"},
                json=media_payload,
            )

            data = response.data
            if isinstance(data, dict) and data.get("messages"):
                return ActionResult(data={"message_id": data["messages"][0]["id"]})

            return ActionError(message=_extract_api_error(data))

        except Exception as e:
            return ActionError(message=f"Failed to send media message: {str(e)}")


@whatsapp.action("get_phone_number_health")
class GetPhoneNumberHealthAction(ActionHandler):
    """
    Action to check the status and quality rating of the business phone number.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        phone_number_id = inputs["phone_number_id"]

        if not validate_phone_number_id(phone_number_id):
            return ActionError(message="Invalid phone number ID. Must be a numeric string.")

        try:
            creds = get_whatsapp_creds(context.auth)

            response = await context.fetch(
                f"{GRAPH_API_BASE}/{phone_number_id}",
                method="GET",
                params={"fields": "status,quality_rating"},
                headers={"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json"},
            )

            data = response.data
            if isinstance(data, dict) and "status" in data:
                return ActionResult(
                    data={
                        "status": data.get("status", "UNKNOWN"),
                        "quality_rating": data.get("quality_rating", "UNKNOWN"),
                    }
                )

            return ActionError(message=_extract_api_error(data))

        except Exception as e:
            return ActionError(message=f"Failed to get phone number health: {str(e)}")
