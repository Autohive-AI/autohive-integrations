"""
End-to-end integration tests for the WhatsApp Business integration.

These tests call the real WhatsApp Cloud (Facebook Graph) API and require a
valid access token plus a business phone number ID set in the environment.

Required env vars:
    WHATSAPP_ACCESS_TOKEN   — Meta access token with WhatsApp messaging perms
    WHATSAPP_PHONE_NUMBER_ID — Phone number ID of the business sender
    WHATSAPP_RECIPIENT_PHONE — (destructive only) E.164 recipient number
    WHATSAPP_TEMPLATE_NAME   — (destructive only) approved template name
    WHATSAPP_TEMPLATE_LANG   — (destructive only) approved-template locale, default "en_US" (matches Meta's stock hello_world template). Must match the locale the template was approved in.
    WHATSAPP_MEDIA_URL       — (destructive only) public HTTPS image URL

Run read-only tests (safe — recommended default):
    pytest whatsapp/tests/test_whatsapp_integration.py -m "integration and not destructive"

Run destructive tests (sends real messages — use deliberately):
    pytest whatsapp/tests/test_whatsapp_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from whatsapp.whatsapp import whatsapp as whatsapp_integration

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
RECIPIENT_PHONE = os.environ.get("WHATSAPP_RECIPIENT_PHONE", "")
TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "hello_world")
TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en_US")
MEDIA_URL = os.environ.get("WHATSAPP_MEDIA_URL", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("WHATSAPP_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=headers or {}) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": ACCESS_TOKEN},
    }
    return ctx


def require_phone_number_id():
    if not PHONE_NUMBER_ID:
        pytest.skip("WHATSAPP_PHONE_NUMBER_ID not set")


def require_recipient():
    if not RECIPIENT_PHONE:
        pytest.skip("WHATSAPP_RECIPIENT_PHONE not set — skipping destructive test")


def require_media_url():
    if not MEDIA_URL:
        pytest.skip("WHATSAPP_MEDIA_URL not set — skipping destructive media test")


# =============================================================================
# READ-ONLY TESTS
# =============================================================================


class TestGetPhoneNumberHealth:
    async def test_returns_status_and_quality(self, live_context):
        require_phone_number_id()
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": PHONE_NUMBER_ID},
            live_context,
        )
        data = result.result.data
        assert "status" in data
        assert "quality_rating" in data
        assert isinstance(data["status"], str)
        assert isinstance(data["quality_rating"], str)

    async def test_invalid_phone_number_id_returns_action_error(self, live_context):
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": "not-numeric"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message

    async def test_nonexistent_phone_number_id_returns_action_error(self, live_context):
        # Numeric but unknown — Graph API should respond with an "Object does not exist" error.
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": "999999999999999999"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# INPUT VALIDATION — exercise validation paths against the live fixture
# These do NOT mutate state and do NOT make network calls (they short-circuit
# in the handler before fetch), so they are safe to run with read-only marker.
# =============================================================================


class TestSendMessageValidation:
    async def test_invalid_phone_number_returns_action_error(self, live_context):
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": "not-a-phone", "message": "Hi", "phone_number_id": PHONE_NUMBER_ID or "1"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number format" in result.result.message

    async def test_invalid_phone_number_id_returns_action_error(self, live_context):
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": "+1234567890", "message": "Hi", "phone_number_id": "abc"},
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message


class TestSendMediaMessageValidation:
    async def test_invalid_media_url_returns_action_error(self, live_context):
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": "+1234567890",
                "media_type": "image",
                "media_url": "http://insecure.example.com/img.png",  # not https
                "phone_number_id": PHONE_NUMBER_ID or "1",
            },
            live_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid media URL" in result.result.message


# =============================================================================
# DESTRUCTIVE TESTS — send real messages to the account in RECIPIENT_PHONE
# Only run with: pytest -m "integration and destructive"
# =============================================================================


@pytest.mark.destructive
class TestSendMessage:
    async def test_sends_text_message(self, live_context):
        require_phone_number_id()
        require_recipient()

        result = await whatsapp_integration.execute_action(
            "send_message",
            {
                "to": RECIPIENT_PHONE,
                "message": f"Integration test message (pid={os.getpid()})",
                "phone_number_id": PHONE_NUMBER_ID,
            },
            live_context,
        )
        data = result.result.data
        assert "message_id" in data
        assert data["message_id"]


@pytest.mark.destructive
class TestSendTemplateMessage:
    async def test_sends_template(self, live_context):
        require_phone_number_id()
        require_recipient()

        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": RECIPIENT_PHONE,
                "template_name": TEMPLATE_NAME,
                "language_code": TEMPLATE_LANG,
                "phone_number_id": PHONE_NUMBER_ID,
            },
            live_context,
        )
        data = result.result.data
        assert "message_id" in data
        assert data["message_id"]


@pytest.mark.destructive
class TestSendMediaMessage:
    async def test_sends_image(self, live_context):
        require_phone_number_id()
        require_recipient()
        require_media_url()

        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": RECIPIENT_PHONE,
                "media_type": "image",
                "media_url": MEDIA_URL,
                "caption": f"Integration test image (pid={os.getpid()})",
                "phone_number_id": PHONE_NUMBER_ID,
            },
            live_context,
        )
        data = result.result.data
        assert "message_id" in data
        assert data["message_id"]
