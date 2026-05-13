"""Unit tests for the Gmail integration.

Gmail uses Google's googleapiclient (`googleapiclient.discovery.build`)
directly rather than the SDK's `context.fetch`, so these tests mock
the `build` call to return a configured MagicMock service.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk.integration import ResultType

from gmail.gmail import gmail, create_email_message, build_raw_email

pytestmark = pytest.mark.unit


# ============================================================
#  Helpers
# ============================================================


def _make_service():
    """Build a fresh MagicMock that mimics the Google service chain."""
    return MagicMock(name="GmailService")


def _patched_service():
    """Context manager: patches gmail.gmail.build to return a fresh mock service."""
    return patch("gmail.gmail.build")


def _decoded_text(msg):
    """Walk a MIME message and return the concatenated decoded body text."""
    chunks = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            chunks.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(chunks)


# ============================================================
#  Module-level helper tests
# ============================================================


class TestCreateEmailMessage:
    """Tests for the create_email_message helper."""

    def test_plain_text_body(self):
        msg = create_email_message("Hello world", files=None, is_html=False)
        # Plain-text path returns a MIMEText, not multipart, when no files
        assert msg.get_content_type() == "text/plain"
        assert "Hello world" in _decoded_text(msg)

    def test_plain_text_with_attachments_is_multipart(self):
        files = [
            {
                "name": "test.txt",
                "contentType": "text/plain",
                "content": base64.b64encode(b"file contents").decode(),
            }
        ]
        msg = create_email_message("Body", files=files, is_html=False)
        assert msg.is_multipart()
        # First part is the body, second is the attachment
        parts = msg.get_payload()
        assert len(parts) == 2

    def test_html_body_sanitises_script_tag(self):
        body = "<p>Safe</p><script>alert(1)</script><p>Also safe</p>"
        msg = create_email_message(body, files=None, is_html=True)
        rendered = _decoded_text(msg)
        assert "<script>" not in rendered
        assert "Safe" in rendered

    def test_html_body_strips_disallowed_protocol(self):
        body = '<a href="javascript:alert(1)">click</a>'
        msg = create_email_message(body, files=None, is_html=True)
        rendered = _decoded_text(msg)
        assert "javascript:" not in rendered

    def test_html_body_keeps_allowed_tags(self):
        body = "<p><strong>Bold</strong> and <em>italic</em></p>"
        msg = create_email_message(body, files=None, is_html=True)
        rendered = _decoded_text(msg)
        assert "<strong>" in rendered
        assert "<em>" in rendered

    def test_html_body_includes_plain_text_alternative(self):
        body = "<p>HTML body</p>"
        msg = create_email_message(body, files=None, is_html=True)
        # Multipart/alternative with text + html
        assert msg.is_multipart()
        content_types = [p.get_content_type() for p in msg.walk() if p.get_content_type() != "multipart/alternative"]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_html_body_with_attachments_is_mixed_multipart(self):
        files = [
            {
                "name": "a.pdf",
                "contentType": "application/pdf",
                "content": base64.b64encode(b"PDFDATA").decode(),
            }
        ]
        msg = create_email_message("<p>Hello</p>", files=files, is_html=True)
        # Outer container is multipart/mixed; should walk into alternative + attachment
        assert msg.get_content_type() == "multipart/mixed"


def _decode_raw(raw_b64):
    """Decode a base64url-encoded RFC822 payload into an email.Message."""
    import email

    return email.message_from_bytes(base64.urlsafe_b64decode(raw_b64.encode()))


class TestBuildRawEmail:
    """Tests for the shared build_raw_email helper.

    Exercises the helper directly (not through the SDK envelope) so that
    we can cover string-vs-list normalization without tripping the
    config.json input_schema, which constrains some actions to arrays.
    """

    def test_string_recipients_are_not_character_split(self):
        """Regression: passing 'to'/'cc'/'bcc' as a single string used to
        be treated as an iterable of single characters by the inline
        ReplyToThread builder, producing malformed headers like
        'b, o, b, @, e, x, ...'. Both forms must produce a clean header."""
        msg = _decode_raw(
            build_raw_email(
                {
                    "to": "alice@example.com",
                    "cc": "carol@example.com",
                    "bcc": "dan@example.com",
                    "subject": "Hi",
                    "body": "hello",
                },
            )
        )
        assert msg["to"] == "alice@example.com"
        assert msg["cc"] == "carol@example.com"
        assert msg["bcc"] == "dan@example.com"

    def test_list_recipients_are_comma_joined(self):
        msg = _decode_raw(
            build_raw_email(
                {
                    "to": ["alice@example.com", "bob@example.com"],
                    "cc": ["carol@example.com", "dan@example.com"],
                    "subject": "Hi",
                    "body": "hello",
                },
            )
        )
        assert msg["to"] == "alice@example.com, bob@example.com"
        assert msg["cc"] == "carol@example.com, dan@example.com"

    def test_extra_to_is_prepended(self):
        """ReplyToThread uses extra_to to put the original sender first."""
        msg = _decode_raw(
            build_raw_email(
                {"to": ["bob@example.com"], "subject": "x", "body": "y"},
                extra_to=["original@example.com"],
            )
        )
        assert msg["to"] == "original@example.com, bob@example.com"

    def test_subject_override_wins(self):
        msg = _decode_raw(
            build_raw_email(
                {"to": "x@example.com", "subject": "ignored", "body": "b"},
                subject_override="Re: real",
            )
        )
        assert msg["subject"] == "Re: real"

    def test_from_me_sentinel_is_skipped(self):
        msg = _decode_raw(
            build_raw_email(
                {"to": "x@example.com", "subject": "s", "body": "b", "from": "me"},
            )
        )
        assert msg["from"] is None

    def test_threading_headers_default_references_to_in_reply_to(self):
        msg = _decode_raw(
            build_raw_email(
                {"to": "x@example.com", "subject": "s", "body": "b"},
                in_reply_to="<msg-id@example.com>",
            )
        )
        assert msg["In-Reply-To"] == "<msg-id@example.com>"
        assert msg["References"] == "<msg-id@example.com>"

    def test_threading_headers_pass_references_through(self):
        msg = _decode_raw(
            build_raw_email(
                {"to": "x@example.com", "subject": "s", "body": "b"},
                in_reply_to="<new@example.com>",
                references="<old@example.com> <new@example.com>",
            )
        )
        assert msg["References"] == "<old@example.com> <new@example.com>"


# ============================================================
#  Auth & service-build tests
# ============================================================


class TestBuildGmailService:
    """Tests for build_credentials / build_gmail_service via build patching."""

    @pytest.mark.asyncio
    async def test_missing_token_does_not_crash(self, mock_context):
        """A missing access_token must not raise KeyError thanks to the
        hardened lookup; instead the upstream Gmail call fails and is
        returned as ActionError."""
        mock_context.auth = {}  # no credentials
        with _patched_service() as mock_build:
            mock_build.side_effect = Exception("Invalid credentials")
            result = await gmail.execute_action("get_user_info", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Mark / Archive actions (void success)
# ============================================================


class TestMarkEmailsAsRead:
    @pytest.mark.asyncio
    async def test_happy_path_returns_empty_data(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.return_value = None
            result = await gmail.execute_action(
                "mark_emails_as_read", {"user_id": "me", "ids": ["m1", "m2"]}, mock_context
            )
        assert result.type == ResultType.ACTION
        assert result.result.data == {}

    @pytest.mark.asyncio
    async def test_request_uses_remove_unread_label(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            await gmail.execute_action("mark_emails_as_read", {"user_id": "me", "ids": ["m1"]}, mock_context)
        call = service.users().messages().batchModify.call_args
        assert call.kwargs["userId"] == "me"
        assert call.kwargs["body"]["removeLabelIds"] == ["UNREAD"]
        assert call.kwargs["body"]["addLabelIds"] == []
        assert call.kwargs["body"]["ids"] == ["m1"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.side_effect = Exception("HTTP 500")
            result = await gmail.execute_action("mark_emails_as_read", {"user_id": "me", "ids": ["m1"]}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


class TestMarkEmailsAsUnread:
    @pytest.mark.asyncio
    async def test_request_uses_add_unread_label(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action("mark_emails_as_unread", {"user_id": "me", "ids": ["m1"]}, mock_context)
        assert result.type == ResultType.ACTION
        call = service.users().messages().batchModify.call_args
        assert call.kwargs["body"]["addLabelIds"] == ["UNREAD"]
        assert call.kwargs["body"]["removeLabelIds"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.side_effect = Exception("boom")
            result = await gmail.execute_action("mark_emails_as_unread", {"user_id": "me", "ids": ["m1"]}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestArchiveEmails:
    @pytest.mark.asyncio
    async def test_request_removes_inbox_label(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action("archive_emails", {"user_id": "me", "ids": ["m1", "m2"]}, mock_context)
        assert result.type == ResultType.ACTION
        call = service.users().messages().batchModify.call_args
        assert call.kwargs["body"]["removeLabelIds"] == ["INBOX"]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.side_effect = Exception("nope")
            result = await gmail.execute_action("archive_emails", {"user_id": "me", "ids": ["m1"]}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Profile & read actions
# ============================================================


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_returns_profile_fields(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().getProfile().execute.return_value = {
                "emailAddress": "kai@example.com",
                "messagesTotal": 42,
                "threadsTotal": 17,
                "historyId": "12345",
            }
            result = await gmail.execute_action("get_user_info", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION
        info = result.result.data["user_info"]
        assert info["email_address"] == "kai@example.com"
        assert info["messages_total"] == 42
        assert info["history_id"] == "12345"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().getProfile().execute.side_effect = Exception("auth failed")
            result = await gmail.execute_action("get_user_info", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "auth failed" in result.result.message


def _sample_message(msg_id="m1", thread_id="t1", subject="Hello", body="Body text"):
    """Build a minimal Gmail API message payload."""
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "snippet",
        "internalDate": "1700000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
            "parts": [],
        },
    }


class TestReadEmail:
    @pytest.mark.asyncio
    async def test_returns_email_object(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _sample_message()
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert "email" in result.result.data
        assert "files" in result.result.data
        assert result.result.data["email"]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.side_effect = Exception("not found")
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "missing"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestReadInbox:
    @pytest.mark.asyncio
    async def test_returns_emails_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}, {"id": "m2"}]}
            service.users().messages().get().execute.side_effect = [
                _sample_message(msg_id="m1"),
                _sample_message(msg_id="m2"),
            ]
            result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.type == ResultType.ACTION
        assert "emails" in result.result.data
        assert len(result.result.data["emails"]) == 2

    @pytest.mark.asyncio
    async def test_unread_scope_uses_query_filter(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "unread"}, mock_context)
        # Gmail uses the `q` query param ('is:unread in:inbox') rather than
        # the labelIds endpoint to filter unread inbox messages.
        call = service.users().messages().list.call_args
        assert "is:unread" in call.kwargs["q"]
        assert "in:inbox" in call.kwargs["q"]

    @pytest.mark.asyncio
    async def test_next_page_token_propagated(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {
                "messages": [],
                "nextPageToken": "token-abc",
            }
            result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.result.data["nextPageToken"] == "token-abc"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.side_effect = Exception("rate limited")
            result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestReadAllMail:
    @pytest.mark.asyncio
    async def test_returns_emails_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _sample_message()
            result = await gmail.execute_action("read_all_mail", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.type == ResultType.ACTION
        assert len(result.result.data["emails"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.side_effect = Exception("error")
            result = await gmail.execute_action("read_all_mail", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Send / reply actions
# ============================================================


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_returns_message_id_on_success(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().send().execute.return_value = {"id": "sent-1"}
            result = await gmail.execute_action(
                "send_email",
                {"to": ["bob@example.com"], "subject": "Hi", "body": "Hello"},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == "sent-1"

    @pytest.mark.asyncio
    async def test_html_body_sanitised(self, mock_context):
        import email

        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().send().execute.return_value = {"id": "sent-1"}
            await gmail.execute_action(
                "send_email",
                {
                    "to": ["bob@example.com"],
                    "subject": "Hi",
                    "body": "<script>alert(1)</script><p>Safe</p>",
                    "body_format": "html",
                },
                mock_context,
            )
        # Decode the raw email payload sent to Gmail and walk its parts
        call = service.users().messages().send.call_args
        raw_b64 = call.kwargs["body"]["raw"]
        raw_bytes = base64.urlsafe_b64decode(raw_b64.encode())
        msg = email.message_from_bytes(raw_bytes)
        rendered = _decoded_text(msg)
        assert "<script>" not in rendered
        assert "Safe" in rendered

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().send().execute.side_effect = Exception("rejected")
            result = await gmail.execute_action(
                "send_email",
                {"to": ["bob@example.com"], "subject": "Hi", "body": "Hello"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


class TestReplyToThread:
    @pytest.mark.asyncio
    async def test_returns_id_on_success(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            # First the original message is fetched for headers
            service.users().messages().get().execute.return_value = _sample_message()
            service.users().messages().send().execute.return_value = {"id": "reply-1"}
            result = await gmail.execute_action(
                "reply_to_thread",
                {
                    "thread_id": "t1",
                    "message_id": "m1",
                    "body": "Reply body",
                    "to": [],
                    "cc": [],
                },
                mock_context,
            )
        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == "reply-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.side_effect = Exception("bad thread")
            result = await gmail.execute_action(
                "reply_to_thread",
                {
                    "thread_id": "t1",
                    "message_id": "m1",
                    "body": "Reply",
                    "to": [],
                    "cc": [],
                },
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Label actions
# ============================================================


class TestListLabels:
    @pytest.mark.asyncio
    async def test_returns_labels_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().labels().list().execute.return_value = {
                "labels": [
                    {"id": "INBOX", "name": "INBOX", "type": "system"},
                    {"id": "Label_1", "name": "MyLabel", "type": "user"},
                ]
            }
            result = await gmail.execute_action("list_labels", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION
        assert len(result.result.data["labels"]) == 2

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().labels().list().execute.side_effect = Exception("boom")
            result = await gmail.execute_action("list_labels", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateLabel:
    @pytest.mark.asyncio
    async def test_returns_created_label(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().labels().create().execute.return_value = {
                "id": "Label_99",
                "name": "Project X",
                "type": "user",
                "messageListVisibility": "show",
                "labelListVisibility": "labelShow",
            }
            result = await gmail.execute_action("create_label", {"user_id": "me", "name": "Project X"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["label"]["id"] == "Label_99"
        assert result.result.data["label"]["name"] == "Project X"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().labels().create().execute.side_effect = Exception("dup")
            result = await gmail.execute_action("create_label", {"user_id": "me", "name": "X"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestAddLabelsToEmails:
    @pytest.mark.asyncio
    async def test_request_adds_labels(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action(
                "add_labels_to_emails",
                {"user_id": "me", "message_ids": ["m1"], "label_ids": ["Label_1"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        call = service.users().messages().batchModify.call_args
        assert call.kwargs["body"]["addLabelIds"] == ["Label_1"]
        assert call.kwargs["body"]["removeLabelIds"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.side_effect = Exception("err")
            result = await gmail.execute_action(
                "add_labels_to_emails",
                {"user_id": "me", "message_ids": ["m1"], "label_ids": ["L1"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


class TestRemoveLabelsFromEmails:
    @pytest.mark.asyncio
    async def test_request_removes_labels(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action(
                "remove_labels_from_emails",
                {"user_id": "me", "message_ids": ["m1"], "label_ids": ["Label_1"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        call = service.users().messages().batchModify.call_args
        assert call.kwargs["body"]["removeLabelIds"] == ["Label_1"]
        assert call.kwargs["body"]["addLabelIds"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().batchModify().execute.side_effect = Exception("err")
            result = await gmail.execute_action(
                "remove_labels_from_emails",
                {"user_id": "me", "message_ids": ["m1"], "label_ids": ["L1"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


class TestListEmailsByLabel:
    @pytest.mark.asyncio
    async def test_returns_emails_for_label(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _sample_message()
            result = await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": ["MyLabel"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        assert len(result.result.data["emails"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.side_effect = Exception("bad label")
            result = await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": ["MyLabel"]},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Thread actions
# ============================================================


class TestGetThreadEmails:
    @pytest.mark.asyncio
    async def test_returns_thread_emails(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.return_value = {
                "id": "t1",
                "messages": [_sample_message(msg_id="m1"), _sample_message(msg_id="m2")],
            }
            result = await gmail.execute_action("get_thread_emails", {"user_id": "me", "thread_id": "t1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["thread_id"] == "t1"
        assert len(result.result.data["emails"]) == 2

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.side_effect = Exception("not found")
            result = await gmail.execute_action("get_thread_emails", {"user_id": "me", "thread_id": "t1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# ============================================================
#  Draft actions
# ============================================================


class TestCreateDraft:
    @pytest.mark.asyncio
    async def test_returns_draft_id_on_success(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().getProfile().execute.return_value = {"emailAddress": "me@example.com"}
            service.users().drafts().create().execute.return_value = {
                "id": "draft-1",
                "message": {"id": "msg-1", "threadId": "thr-1"},
            }
            result = await gmail.execute_action(
                "create_draft",
                {"to": ["bob@example.com"], "subject": "Draft", "body": "hi"},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        assert result.result.data["draft"]["id"] == "draft-1"

    @pytest.mark.asyncio
    async def test_reply_mode_pulls_original_message_headers(self, mock_context):
        """When thread_id + message_id are passed, the draft is created as a
        reply and the original message is fetched to derive the recipient/subject."""
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().getProfile().execute.return_value = {"emailAddress": "me@example.com"}
            service.users().messages().get().execute.return_value = _sample_message()
            service.users().drafts().create().execute.return_value = {
                "id": "draft-2",
                "message": {"id": "msg-2", "threadId": "t1"},
            }
            result = await gmail.execute_action(
                "create_draft",
                {"thread_id": "t1", "message_id": "m1", "body": "Reply draft"},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        # Verify drafts().create was called with a threadId
        call = service.users().drafts().create.call_args
        assert call.kwargs["body"]["message"]["threadId"] == "t1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().create().execute.side_effect = Exception("err")
            result = await gmail.execute_action(
                "create_draft",
                {"to": ["bob@example.com"], "subject": "S", "body": "B"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateDraft:
    @pytest.mark.asyncio
    async def test_returns_updated_draft(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().getProfile().execute.return_value = {"emailAddress": "me@example.com"}
            service.users().drafts().get().execute.return_value = {
                "id": "draft-1",
                "message": {"threadId": "thr-1", "payload": {"headers": []}},
            }
            service.users().drafts().update().execute.return_value = {
                "id": "draft-1",
                "message": {"id": "msg-1", "threadId": "thr-1"},
            }
            result = await gmail.execute_action(
                "update_draft",
                {"draft_id": "draft-1", "to": ["x@example.com"], "subject": "S", "body": "B"},
                mock_context,
            )
        assert result.type == ResultType.ACTION
        assert result.result.data["draft"]["id"] == "draft-1"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().get().execute.side_effect = Exception("missing")
            result = await gmail.execute_action(
                "update_draft",
                {"draft_id": "x", "to": ["x@example.com"], "subject": "S", "body": "B"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR


class TestListDrafts:
    @pytest.mark.asyncio
    async def test_returns_drafts_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().list().execute.return_value = {
                "drafts": [{"id": "d1", "message": {"id": "m1", "threadId": "t1"}}]
            }
            result = await gmail.execute_action("list_drafts", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION
        assert "drafts" in result.result.data

    @pytest.mark.asyncio
    async def test_next_page_token_propagated(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().list().execute.return_value = {
                "drafts": [],
                "nextPageToken": "tok",
            }
            result = await gmail.execute_action("list_drafts", {"user_id": "me"}, mock_context)
        assert result.result.data["nextPageToken"] == "tok"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().list().execute.side_effect = Exception("err")
            result = await gmail.execute_action("list_drafts", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetDraft:
    @pytest.mark.asyncio
    async def test_returns_draft(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().get().execute.return_value = {
                "id": "draft-1",
                "message": _sample_message(),
            }
            result = await gmail.execute_action("get_draft", {"user_id": "me", "draft_id": "draft-1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert "draft" in result.result.data

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().get().execute.side_effect = Exception("missing")
            result = await gmail.execute_action("get_draft", {"user_id": "me", "draft_id": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestSendDraft:
    @pytest.mark.asyncio
    async def test_returns_sent_message(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().send().execute.return_value = {
                "id": "msg-sent",
                "threadId": "t1",
            }
            result = await gmail.execute_action("send_draft", {"user_id": "me", "draft_id": "draft-1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["message"]["id"] == "msg-sent"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().send().execute.side_effect = Exception("rejected")
            result = await gmail.execute_action("send_draft", {"user_id": "me", "draft_id": "d"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteDraft:
    @pytest.mark.asyncio
    async def test_returns_empty_data_on_success(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().delete().execute.return_value = None
            result = await gmail.execute_action("delete_draft", {"user_id": "me", "draft_id": "draft-1"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().drafts().delete().execute.side_effect = Exception("not found")
            result = await gmail.execute_action("delete_draft", {"user_id": "me", "draft_id": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
