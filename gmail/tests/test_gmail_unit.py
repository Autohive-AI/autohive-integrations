"""Unit tests for the Gmail integration.

Covers:
- ``append_signature`` helper (text / HTML separators, edge cases).
- Signature wiring in ``SendEmail._create_raw_email`` and
  ``CreateDraft._create_raw_email`` (decode the base64-encoded MIME and assert
  the signature shows up in both the plain-text and HTML parts).
- ``ListSendAsSignatures`` handler — happy path, missing optional fields,
  empty alias list, and the ``signature: null`` → empty-string coercion.
"""

from __future__ import annotations

import base64
from email import message_from_bytes
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from autohive_integrations_sdk.integration import ResultType

from gmail.gmail import CreateDraft, SendEmail, append_signature, gmail

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def decode_raw_message(raw_message: str):
    """Decode the base64url-encoded raw MIME string back into an email Message."""
    return message_from_bytes(base64.urlsafe_b64decode(raw_message.encode()))


def get_part_payload(message, mime_subtype: str) -> str:
    """Walk a (possibly multipart) message and return the decoded payload of
    the first part whose subtype matches ``mime_subtype`` (``"plain"`` or
    ``"html"``)."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_subtype() == mime_subtype and not part.is_multipart():
                return part.get_payload(decode=True).decode("utf-8")
        raise AssertionError(f"No {mime_subtype} part found")
    return message.get_payload(decode=True).decode("utf-8")


def _mock_gmail_service(send_as_response: Dict[str, Any]) -> MagicMock:
    """Mock the Gmail service chain so
    ``service.users().settings().sendAs().list(userId=...).execute()``
    returns ``send_as_response``."""
    service = MagicMock(name="GmailService")
    leaf = MagicMock()
    leaf.execute.return_value = send_as_response
    service.users.return_value.settings.return_value.sendAs.return_value.list.return_value = leaf
    return service


# ---------------------------------------------------------------------------
# append_signature
# ---------------------------------------------------------------------------


class TestAppendSignature:
    def test_text_separator(self):
        result = append_signature("Hello", "Best,\nMe", is_html=False)
        assert result == "Hello\n\n-- \nBest,\nMe"

    def test_html_separator(self):
        result = append_signature("<p>Hi</p>", "<p>Best,<br>Me</p>", is_html=True)
        assert result == "<p>Hi</p><br><br>-- <br><p>Best,<br>Me</p>"

    def test_empty_signature_returns_body_unchanged(self):
        assert append_signature("Hello", "", is_html=False) == "Hello"
        assert append_signature("Hello", "", is_html=True) == "Hello"

    def test_none_signature_returns_body_unchanged(self):
        # Defensive: ``inputs.get("signature", "")`` could pass through ``None``
        # if a caller sends ``"signature": null`` explicitly.
        assert append_signature("Hello", None, is_html=False) == "Hello"

    def test_empty_body_returns_signature_only(self):
        assert append_signature("", "Best,\nMe", is_html=False) == "Best,\nMe"
        assert append_signature("", "<p>Me</p>", is_html=True) == "<p>Me</p>"

    def test_none_body_treated_as_empty(self):
        assert append_signature(None, "Best,\nMe", is_html=False) == "Best,\nMe"

    def test_both_empty_returns_empty(self):
        assert append_signature("", "", is_html=False) == ""


# ---------------------------------------------------------------------------
# Signature wiring on SendEmail / CreateDraft
# ---------------------------------------------------------------------------


class TestSendEmailSignature:
    def test_plain_text_body_includes_signature(self):
        raw = SendEmail()._create_raw_email(
            {
                "to": "alice@example.com",
                "subject": "Hi",
                "body": "Hello Alice",
                "signature": "Best,\nMe",
            }
        )
        body = get_part_payload(decode_raw_message(raw), "plain")
        assert "Hello Alice" in body
        assert "-- " in body
        assert "Best," in body
        assert "Me" in body

    def test_html_body_includes_signature_in_both_parts(self):
        raw = SendEmail()._create_raw_email(
            {
                "to": "alice@example.com",
                "subject": "Hi",
                "body": "<p>Hello Alice</p>",
                "body_format": "html",
                "signature": "<p>Best, <b>Me</b></p>",
            }
        )
        message = decode_raw_message(raw)
        html_part = get_part_payload(message, "html")
        plain_part = get_part_payload(message, "plain")
        assert "Hello Alice" in html_part
        assert "Best" in html_part
        assert "<b>Me</b>" in html_part
        # The plain-text alternative is auto-generated from sanitized HTML, so
        # the signature text should also be reachable there.
        assert "Best" in plain_part

    def test_no_signature_input_leaves_body_unchanged(self):
        raw = SendEmail()._create_raw_email({"to": "alice@example.com", "subject": "Hi", "body": "Hello Alice"})
        body = get_part_payload(decode_raw_message(raw), "plain")
        assert "Hello Alice" in body
        assert "-- " not in body


class TestCreateDraftSignature:
    def test_plain_text_body_includes_signature(self):
        raw = CreateDraft()._create_raw_email(
            {
                "to": ["alice@example.com"],
                "subject": "Draft",
                "body": "Draft body",
                "from": "me@example.com",
                "signature": "Best,\nMe",
            }
        )
        body = get_part_payload(decode_raw_message(raw), "plain")
        assert "Draft body" in body
        assert "-- " in body
        assert "Best," in body

    def test_html_body_includes_signature(self):
        raw = CreateDraft()._create_raw_email(
            {
                "to": ["alice@example.com"],
                "subject": "Draft",
                "body": "<p>Draft body</p>",
                "body_format": "html",
                "from": "me@example.com",
                "signature": "<p>Best, <b>Me</b></p>",
            }
        )
        message = decode_raw_message(raw)
        html_part = get_part_payload(message, "html")
        assert "Draft body" in html_part
        assert "<b>Me</b>" in html_part


# ---------------------------------------------------------------------------
# ListSendAsSignatures
# ---------------------------------------------------------------------------


async def _invoke_list_send_as(inputs: Dict[str, Any], api_response: Dict[str, Any], context: MagicMock):
    with patch("gmail.gmail.build", return_value=_mock_gmail_service(api_response)):
        return await gmail.execute_action("list_send_as_signatures", inputs, context)


@pytest.fixture
def mock_context() -> MagicMock:
    """Minimal ExecutionContext that ``build_credentials`` can read from."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_access_token"},  # nosec B105
    }
    return ctx


class TestListSendAsSignatures:
    async def test_happy_path_two_aliases(self, mock_context):
        api_response = {
            "sendAs": [
                {
                    "sendAsEmail": "me@example.com",
                    "displayName": "Me",
                    "isPrimary": True,
                    "isDefault": True,
                    "signature": "<p>Primary sig</p>",
                    "replyToAddress": "reply@example.com",
                },
                {
                    "sendAsEmail": "support@example.com",
                    "displayName": "Support",
                    "isPrimary": False,
                    "isDefault": False,
                    "signature": "<p>Support sig</p>",
                    "replyToAddress": "",
                },
            ]
        }

        envelope = await _invoke_list_send_as({"user_id": "me"}, api_response, mock_context)

        assert envelope.type != ResultType.ACTION_ERROR
        data = envelope.result.data
        assert data["result"] is True
        assert len(data["signatures"]) == 2

        primary = data["signatures"][0]
        assert primary["send_as_email"] == "me@example.com"
        assert primary["display_name"] == "Me"
        assert primary["is_primary"] is True
        assert primary["is_default"] is True
        assert primary["signature"] == "<p>Primary sig</p>"
        assert primary["reply_to_address"] == "reply@example.com"

        alias = data["signatures"][1]
        assert alias["send_as_email"] == "support@example.com"
        assert alias["is_primary"] is False
        assert alias["is_default"] is False

    async def test_missing_optional_fields_default_to_empty(self, mock_context):
        # Gmail omits ``displayName``, ``replyToAddress``, ``signature`` etc.
        # when they are not configured. Confirm we surface defaults rather
        # than ``None`` or ``KeyError``.
        api_response = {
            "sendAs": [
                {
                    "sendAsEmail": "me@example.com",
                    "isPrimary": True,
                    "isDefault": True,
                }
            ]
        }

        envelope = await _invoke_list_send_as({"user_id": "me"}, api_response, mock_context)

        assert envelope.type != ResultType.ACTION_ERROR
        entry = envelope.result.data["signatures"][0]
        assert entry["display_name"] == ""
        assert entry["signature"] == ""
        assert entry["reply_to_address"] == ""
        # Required booleans should still come through truthfully.
        assert entry["is_primary"] is True
        assert entry["is_default"] is True

    async def test_empty_send_as_list(self, mock_context):
        envelope = await _invoke_list_send_as({"user_id": "me"}, {}, mock_context)
        assert envelope.type != ResultType.ACTION_ERROR
        assert envelope.result.data == {"signatures": [], "result": True}

    async def test_null_signature_becomes_empty_string(self, mock_context):
        # Gmail can return ``"signature": null`` for a send-as that has no
        # default signature bound. The handler must coerce to ``""`` — not the
        # string ``"None"``, and not leave it as ``None``.
        api_response = {
            "sendAs": [
                {
                    "sendAsEmail": "me@example.com",
                    "isPrimary": True,
                    "isDefault": True,
                    "signature": None,
                }
            ]
        }

        envelope = await _invoke_list_send_as({"user_id": "me"}, api_response, mock_context)

        assert envelope.type != ResultType.ACTION_ERROR
        entry = envelope.result.data["signatures"][0]
        assert entry["signature"] == ""
        assert entry["signature"] != "None"

    async def test_defaults_user_id_to_me(self, mock_context):
        # No ``user_id`` in inputs → handler should default to "me".
        captured_kwargs: Dict[str, Any] = {}

        service = MagicMock(name="GmailService")
        leaf = MagicMock()
        leaf.execute.return_value = {"sendAs": []}

        def list_(**kwargs):
            captured_kwargs.update(kwargs)
            return leaf

        service.users.return_value.settings.return_value.sendAs.return_value.list.side_effect = list_

        with patch("gmail.gmail.build", return_value=service):
            envelope = await gmail.execute_action("list_send_as_signatures", {}, mock_context)

        assert envelope.type != ResultType.ACTION_ERROR
        assert captured_kwargs == {"userId": "me"}
