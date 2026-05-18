"""
Unit tests for the WhatsApp Business integration using mocked fetch.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from whatsapp.whatsapp import (
    whatsapp as whatsapp_integration,
    get_whatsapp_creds,
    validate_phone_number,
    validate_phone_number_id,
    validate_media_url,
    _extract_api_error,
)

pytestmark = pytest.mark.unit


VALID_PHONE = "+1234567890"
VALID_PHONE_NO_PLUS = "1234567890"
VALID_PHONE_NUMBER_ID = "1234567890123456"
ACCESS_TOKEN = "test_access_token"  # nosec B105


_NO_RESPONSE = object()


def make_ctx(response_data=_NO_RESPONSE, *, auth=None, status=200):
    ctx = MagicMock(name="ExecutionContext")
    if response_data is _NO_RESPONSE:
        ctx.fetch = AsyncMock()
    else:
        ctx.fetch = AsyncMock(return_value=FetchResponse(status=status, headers={}, data=response_data))
    ctx.auth = (
        auth if auth is not None else {"auth_type": "PlatformOauth2", "credentials": {"access_token": ACCESS_TOKEN}}
    )
    return ctx


# =============================================================================
# HELPERS — get_whatsapp_creds
# =============================================================================


class TestGetWhatsappCreds:
    def test_credentials_nested(self):
        creds = get_whatsapp_creds({"credentials": {"access_token": "abc"}})  # nosec B105
        assert creds == {"access_token": "abc"}  # nosec B105

    def test_credentials_flat(self):
        creds = get_whatsapp_creds({"access_token": "abc"})  # nosec B105
        assert creds == {"access_token": "abc"}  # nosec B105

    def test_credentials_camelcase(self):
        creds = get_whatsapp_creds({"accessToken": "abc"})  # nosec B105
        assert creds == {"access_token": "abc"}  # nosec B105

    def test_credentials_token_alias(self):
        creds = get_whatsapp_creds({"token": "abc"})  # nosec B105
        assert creds == {"access_token": "abc"}  # nosec B105

    def test_missing_raises(self):
        with pytest.raises(ValueError, match="Missing access_token"):
            get_whatsapp_creds({"credentials": {}})

    def test_empty_auth_raises(self):
        with pytest.raises(ValueError, match="Missing access_token"):
            get_whatsapp_creds({})

    def test_empty_string_token_raises(self):
        with pytest.raises(ValueError, match="Missing access_token"):
            get_whatsapp_creds({"access_token": ""})  # nosec B105

    def test_snake_case_wins_over_camel_case(self):
        # When both are present, snake_case takes priority (first in `or` chain)
        creds = get_whatsapp_creds({"access_token": "snake", "accessToken": "camel"})  # nosec B105
        assert creds == {"access_token": "snake"}  # nosec B105

    def test_camel_case_wins_over_token(self):
        creds = get_whatsapp_creds({"accessToken": "camel", "token": "tok"})  # nosec B105
        assert creds == {"access_token": "camel"}  # nosec B105


# =============================================================================
# HELPERS — _extract_api_error
# =============================================================================


class TestExtractApiError:
    def test_dict_with_nested_error_message(self):
        assert _extract_api_error({"error": {"message": "Bad request"}}) == "Bad request"

    def test_dict_with_error_object_missing_message(self):
        assert _extract_api_error({"error": {}}) == "Unknown error"

    def test_dict_without_error_key(self):
        assert _extract_api_error({"foo": "bar"}) == "Unknown error"

    def test_empty_dict(self):
        assert _extract_api_error({}) == "Unknown error"

    def test_string_response(self):
        assert _extract_api_error("oops") == "Unexpected response: oops"

    def test_none_response(self):
        assert _extract_api_error(None) == "Unexpected response: None"

    def test_list_response(self):
        assert _extract_api_error([1, 2]) == "Unexpected response: [1, 2]"


# =============================================================================
# HELPERS — validators
# =============================================================================


class TestValidatePhoneNumber:
    @pytest.mark.parametrize(
        "phone, expected",
        [
            ("+1234567890", True),
            ("1234567890", True),
            ("+44123456789", True),
            ("12", True),  # min length: 2 digits
            ("123456789012345", True),  # max length: 15 digits total
            ("+123456789012345", True),  # max with plus
            ("1234567890123456", False),  # 16 digits — too long
            ("+1", False),  # 1 digit — too short
            ("0123456789", False),  # leading zero
            ("+0123456789", False),
            ("abc123", False),
            ("", False),
            ("+", False),
            ("+1 234 567 890", False),  # spaces
            ("+1-234-567-890", False),  # dashes
            ("++1234567890", False),  # double plus
        ],
    )
    def test_validate_phone_number(self, phone, expected):
        assert validate_phone_number(phone) is expected


class TestValidatePhoneNumberId:
    @pytest.mark.parametrize(
        "pid, expected",
        [
            ("1234567890", True),
            ("0", True),
            ("12345678901234567890", True),
            ("abc", False),
            ("123a", False),
            ("-123", False),
            ("", False),
            (" ", False),
        ],
    )
    def test_validate_phone_number_id(self, pid, expected):
        assert validate_phone_number_id(pid) is expected


class TestValidateMediaUrl:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://example.com/image.png", True),
            ("https://cdn.example.com/path/to/file.pdf?v=1", True),
            ("https://example.com:8443/image.png", True),  # with port
            ("https://example.com", True),  # no path, still valid
            ("HTTPS://example.com/image.png", True),  # urlparse normalises scheme to lowercase
            ("http://example.com/image.png", False),  # not https
            ("ftp://example.com/image.png", False),
            ("file:///local/path.png", False),
            ("/local/path/image.png", False),
            ("example.com/image.png", False),
            ("https://", False),  # missing netloc
            ("", False),
        ],
    )
    def test_validate_media_url(self, url, expected):
        assert validate_media_url(url) is expected

    def test_none_triggers_except_branch(self):
        # urlparse(None) raises TypeError — exercise the defensive except in validate_media_url
        assert validate_media_url(None) is False

    def test_non_string_triggers_except_branch(self):
        # urlparse on a non-string-like value also raises and should return False
        assert validate_media_url(12345) is False


# =============================================================================
# SEND MESSAGE
# =============================================================================


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_success_returns_message_id(self):
        ctx = make_ctx({"messages": [{"id": "wamid.ABC123"}]})
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.ABC123"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        call = ctx.fetch.call_args
        assert call.args[0] == f"https://graph.facebook.com/v18.0/{VALID_PHONE_NUMBER_ID}/messages"
        assert call.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_payload_strips_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS
        assert payload["messaging_product"] == "whatsapp"
        assert payload["type"] == "text"
        assert payload["text"] == {"body": "Hi"}

    @pytest.mark.asyncio
    async def test_request_authorization_header(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        headers = ctx.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_invalid_phone_number_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": "abc", "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number format" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_phone_number_id_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": "abc"},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_response_returns_action_error(self):
        ctx = make_ctx({"error": {"message": "Recipient phone number not in allowed list"}}, status=400)
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Recipient phone number not in allowed list" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx()
        ctx.fetch.side_effect = Exception("Connection refused")
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_access_token_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]}, auth={"credentials": {}})
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Missing access_token" in result.result.message

    @pytest.mark.asyncio
    async def test_happy_path_without_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "wamid.NOPLUS"}]})
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE_NO_PLUS, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.NOPLUS"
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS  # lstrip is a no-op when no '+'

    @pytest.mark.asyncio
    async def test_empty_messages_list_returns_action_error(self):
        ctx = make_ctx({"messages": []})  # API returned 200 but no messages
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unknown error" in result.result.message

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_action_error(self):
        ctx = make_ctx("Internal Server Error")  # string body
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unexpected response" in result.result.message

    @pytest.mark.asyncio
    async def test_error_object_without_message_returns_unknown_error(self):
        ctx = make_ctx({"error": {}}, status=400)
        result = await whatsapp_integration.execute_action(
            "send_message",
            {"to": VALID_PHONE, "message": "Hi", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unknown error" in result.result.message


# =============================================================================
# SEND TEMPLATE MESSAGE
# =============================================================================


class TestSendTemplateMessage:
    @pytest.mark.asyncio
    async def test_success_returns_message_id(self):
        ctx = make_ctx({"messages": [{"id": "wamid.TMPL"}]})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": VALID_PHONE,
                "template_name": "hello_world",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
                "language_code": "en_US",
            },
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.TMPL"

    @pytest.mark.asyncio
    async def test_payload_structure(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": VALID_PHONE,
                "template_name": "hello_world",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
                "language_code": "en_US",
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["type"] == "template"
        assert payload["template"]["name"] == "hello_world"
        assert payload["template"]["language"]["code"] == "en_US"
        assert "components" not in payload["template"]

    @pytest.mark.asyncio
    async def test_payload_with_parameters(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": VALID_PHONE,
                "template_name": "order_update",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
                "parameters": ["Alice", "ORD-42"],
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        components = payload["template"]["components"]
        assert len(components) == 1
        assert components[0]["type"] == "body"
        assert components[0]["parameters"] == [
            {"type": "text", "text": "Alice"},
            {"type": "text", "text": "ORD-42"},
        ]

    @pytest.mark.asyncio
    async def test_default_language_code_is_en(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": VALID_PHONE,
                "template_name": "hello",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["template"]["language"]["code"] == "en"

    @pytest.mark.asyncio
    async def test_invalid_phone_number_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": "bad", "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number format" in result.result.message

    @pytest.mark.asyncio
    async def test_invalid_phone_number_id_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": "abc"},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message

    @pytest.mark.asyncio
    async def test_api_error_response_returns_action_error(self):
        ctx = make_ctx({"error": {"message": "Template not found"}}, status=404)
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "missing", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Template not found" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx()
        ctx.fetch.side_effect = Exception("Boom")
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Boom" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_and_method(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        call = ctx.fetch.call_args
        assert call.args[0] == f"https://graph.facebook.com/v18.0/{VALID_PHONE_NUMBER_ID}/messages"
        assert call.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_authorization_header(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        headers = ctx.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_strips_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS

    @pytest.mark.asyncio
    async def test_explicit_empty_parameters_no_components(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_template_message",
            {
                "to": VALID_PHONE,
                "template_name": "hello",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
                "parameters": [],
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "components" not in payload["template"]

    @pytest.mark.asyncio
    async def test_missing_access_token_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]}, auth={"credentials": {}})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Missing access_token" in result.result.message

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_action_error(self):
        ctx = make_ctx("Service Unavailable")
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unexpected response" in result.result.message

    @pytest.mark.asyncio
    async def test_empty_messages_list_returns_action_error(self):
        ctx = make_ctx({"messages": []})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_happy_path_without_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "wamid.TMPL"}]})
        result = await whatsapp_integration.execute_action(
            "send_template_message",
            {"to": VALID_PHONE_NO_PLUS, "template_name": "hello", "phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.TMPL"
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS


# =============================================================================
# SEND MEDIA MESSAGE
# =============================================================================


VALID_MEDIA_URL = "https://example.com/image.png"


class TestSendMediaMessage:
    @pytest.mark.asyncio
    async def test_image_success(self):
        ctx = make_ctx({"messages": [{"id": "wamid.IMG"}]})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.IMG"

    @pytest.mark.asyncio
    async def test_image_payload(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["type"] == "image"
        assert payload["image"] == {"link": VALID_MEDIA_URL}

    @pytest.mark.asyncio
    async def test_image_with_caption(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "caption": "Look at this",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["image"]["caption"] == "Look at this"

    @pytest.mark.asyncio
    async def test_document_with_filename(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "document",
                "media_url": "https://example.com/doc.pdf",
                "filename": "invoice.pdf",
                "caption": "Your invoice",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["document"]["filename"] == "invoice.pdf"
        assert payload["document"]["caption"] == "Your invoice"
        assert payload["document"]["link"] == "https://example.com/doc.pdf"

    @pytest.mark.asyncio
    async def test_audio_does_not_get_caption(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "audio",
                "media_url": "https://example.com/clip.mp3",
                "caption": "Ignored for audio",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "caption" not in payload["audio"]

    @pytest.mark.asyncio
    async def test_video_with_caption(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "video",
                "media_url": "https://example.com/clip.mp4",
                "caption": "Watch this",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["video"]["caption"] == "Watch this"

    @pytest.mark.asyncio
    async def test_invalid_media_url_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": "http://insecure.example.com/img.png",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid media URL" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_phone_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": "bad",
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number format" in result.result.message

    @pytest.mark.asyncio
    async def test_invalid_phone_number_id_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": "abc",
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"error": {"message": "Media URL inaccessible"}}, status=400)
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Media URL inaccessible" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx()
        ctx.fetch.side_effect = Exception("Network down")
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Network down" in result.result.message

    @pytest.mark.asyncio
    async def test_request_url_and_method(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        call = ctx.fetch.call_args
        assert call.args[0] == f"https://graph.facebook.com/v18.0/{VALID_PHONE_NUMBER_ID}/messages"
        assert call.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_authorization_header(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        headers = ctx.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"

    @pytest.mark.asyncio
    async def test_strips_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS

    @pytest.mark.asyncio
    async def test_document_without_filename(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "document",
                "media_url": "https://example.com/doc.pdf",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "filename" not in payload["document"]
        assert payload["document"]["link"] == "https://example.com/doc.pdf"

    @pytest.mark.asyncio
    async def test_image_without_caption(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "caption" not in payload["image"]

    @pytest.mark.asyncio
    async def test_empty_caption_not_added(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "caption": "",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "caption" not in payload["image"]

    @pytest.mark.asyncio
    async def test_audio_payload(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "audio",
                "media_url": "https://example.com/clip.mp3",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["type"] == "audio"
        assert payload["audio"]["link"] == "https://example.com/clip.mp3"

    @pytest.mark.asyncio
    async def test_video_payload(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "video",
                "media_url": "https://example.com/clip.mp4",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["type"] == "video"
        assert payload["video"]["link"] == "https://example.com/clip.mp4"

    @pytest.mark.asyncio
    async def test_filename_only_added_for_documents(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]})
        await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "filename": "should-be-ignored.png",
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        payload = ctx.fetch.call_args.kwargs["json"]
        assert "filename" not in payload["image"]

    @pytest.mark.asyncio
    async def test_missing_access_token_returns_action_error(self):
        ctx = make_ctx({"messages": [{"id": "m1"}]}, auth={"credentials": {}})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Missing access_token" in result.result.message

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_action_error(self):
        ctx = make_ctx(None)
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unexpected response" in result.result.message

    @pytest.mark.asyncio
    async def test_empty_messages_list_returns_action_error(self):
        ctx = make_ctx({"messages": []})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_happy_path_without_plus_prefix(self):
        ctx = make_ctx({"messages": [{"id": "wamid.IMG"}]})
        result = await whatsapp_integration.execute_action(
            "send_media_message",
            {
                "to": VALID_PHONE_NO_PLUS,
                "media_type": "image",
                "media_url": VALID_MEDIA_URL,
                "phone_number_id": VALID_PHONE_NUMBER_ID,
            },
            ctx,
        )
        assert result.result.data["message_id"] == "wamid.IMG"
        payload = ctx.fetch.call_args.kwargs["json"]
        assert payload["to"] == VALID_PHONE_NO_PLUS


# =============================================================================
# GET PHONE NUMBER HEALTH
# =============================================================================


class TestGetPhoneNumberHealth:
    @pytest.mark.asyncio
    async def test_success_returns_status_and_quality(self):
        ctx = make_ctx({"status": "CONNECTED", "quality_rating": "GREEN"})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        data = result.result.data
        assert data["status"] == "CONNECTED"
        assert data["quality_rating"] == "GREEN"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self):
        ctx = make_ctx({"status": "CONNECTED"})
        await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        call = ctx.fetch.call_args
        assert call.args[0] == f"https://graph.facebook.com/v18.0/{VALID_PHONE_NUMBER_ID}"
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"]["fields"] == "status,quality_rating"

    @pytest.mark.asyncio
    async def test_quality_rating_defaults_to_unknown(self):
        ctx = make_ctx({"status": "CONNECTED"})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.result.data["quality_rating"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_invalid_phone_number_id_returns_action_error(self):
        ctx = make_ctx({"status": "CONNECTED"})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": "not-a-number"},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid phone number ID" in result.result.message
        ctx.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self):
        ctx = make_ctx({"error": {"message": "Object does not exist"}}, status=404)
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Object does not exist" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self):
        ctx = make_ctx()
        ctx.fetch.side_effect = Exception("Timeout")
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message

    @pytest.mark.asyncio
    async def test_request_authorization_header(self):
        ctx = make_ctx({"status": "CONNECTED", "quality_rating": "GREEN"})
        await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        headers = ctx.fetch.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_missing_access_token_returns_action_error(self):
        ctx = make_ctx({"status": "CONNECTED"}, auth={"credentials": {}})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Missing access_token" in result.result.message

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_action_error(self):
        ctx = make_ctx("Server unavailable")
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unexpected response" in result.result.message

    @pytest.mark.asyncio
    async def test_response_without_status_returns_action_error(self):
        # Graph API can return {} or some other dict without status — should be ActionError
        ctx = make_ctx({"foo": "bar"})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "Unknown error" in result.result.message

    @pytest.mark.asyncio
    async def test_disconnected_status_propagates(self):
        ctx = make_ctx({"status": "DISCONNECTED", "quality_rating": "RED"})
        result = await whatsapp_integration.execute_action(
            "get_phone_number_health",
            {"phone_number_id": VALID_PHONE_NUMBER_ID},
            ctx,
        )
        data = result.result.data
        assert data["status"] == "DISCONNECTED"
        assert data["quality_rating"] == "RED"
