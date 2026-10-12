"""Unit tests for the Gmail integration.

Gmail uses Google's googleapiclient (`googleapiclient.discovery.build`)
directly rather than the SDK's `context.fetch`, so these tests mock
the `build` call to return a configured MagicMock service.
"""

import base64
import re
import warnings
from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk.integration import ResultType
from bleach.sanitizer import NoCssSanitizerWarning

from gmail.gmail import (
    gmail,
    create_email_message,
    build_raw_email,
    build_date_clause,
    append_signature,
    compose_messages_query,
    MAX_READ_EMAIL_BODY_CHARS,
    DEFAULT_THREAD_MAX_MESSAGES,
)

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


def _load_config():
    """Load the integration's config.json for schema assertions."""
    import json
    from pathlib import Path

    return json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))


def _html_part(msg):
    """Return the decoded text/html part of a MIME message.

    Style assertions must look at the HTML part alone: ``_decoded_text``
    concatenates every part, and the text/plain alternative is html2text output
    with the markup already stripped.
    """
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    raise AssertionError("message has no text/html part")


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

    @pytest.mark.parametrize(
        "body",
        [
            "<style>@keyframes pulse{0%{color:red}}</style><p>Hi</p>",
            "<STYLE type='text/css'>.a{color:red}</STYLE><p>Hi</p>",
            "<script>fetch('http://evil.test')</script><p>Hi</p>",
            "<p>Hi</p><style>.a{color:red}</style>",
        ],
    )
    def test_html_body_discards_raw_text_element_contents(self, body):
        # bleach.clean(strip=True) drops the tag but keeps its text, so a <style>
        # block would otherwise be printed in the email as literal CSS.
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "keyframes" not in rendered
        assert "color:red" not in rendered
        assert "evil.test" not in rendered
        assert "Hi" in rendered

    def test_html_body_discards_an_unterminated_style_block(self):
        # A real parser treats everything after an unclosed <style> as CSS, so
        # the remainder is dropped rather than emitted as text.
        body = "<p>before</p><style>.a{color:red}"
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "color:red" not in rendered

    def test_html_body_keeps_content_either_side_of_a_style_block(self):
        body = "<p>before</p><style>.a{color:red}</style><p>after</p>"
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "before" in rendered
        assert "after" in rendered
        assert "color:red" not in rendered

    def test_bcc_is_declared_by_every_action_that_supports_it(self):
        """build_raw_email honours `bcc` for all four send/draft actions.

        send_email and reply_to_thread previously read it without declaring it,
        so callers had no way to set a BCC on either.
        """
        config = _load_config()
        for action in ("send_email", "reply_to_thread", "create_draft", "update_draft"):
            props = config["actions"][action]["input_schema"]["properties"]
            assert "bcc" in props, f"{action} reads bcc in code but does not declare it"
            assert props["bcc"]["type"] == "array"

    def test_reply_to_thread_declares_optional_subject(self):
        """The reply handler supports a caller-supplied subject.

        It only derives "Re: <original>" when the input is missing or empty, so
        the override has to be declared or callers can never reach it.
        """
        config = _load_config()
        props = config["actions"]["reply_to_thread"]["input_schema"]["properties"]
        assert "subject" in props
        assert props["subject"]["type"] == "string"
        # Deriving the subject is the documented default, so it stays optional.
        assert "subject" not in config["actions"]["reply_to_thread"]["input_schema"]["required"]

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

    def test_html_body_does_not_warn_about_a_missing_css_sanitizer(self):
        # bleach emits NoCssSanitizerWarning when `style` is allowed without a
        # css_sanitizer, and empties every declaration when it does so.
        with warnings.catch_warnings():
            warnings.simplefilter("error", NoCssSanitizerWarning)
            create_email_message('<p style="color:red">Hello</p>', files=None, is_html=True)

    def test_html_body_preserves_safe_inline_styles(self):
        # The send_email / reply_to_thread / create_draft schemas instruct callers
        # to style tags inline rather than with <style> blocks, so the
        # declarations have to survive sanitization.
        body = '<p style="color:red;font-size:14px">Hello</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "color:red" in rendered
        assert "font-size:14px" in rendered

    def test_html_body_preserves_table_formatting(self):
        body = (
            '<table style="border-collapse:collapse">'
            '<tr><td style="padding:8px;border:1px solid #ccc">cell</td></tr></table>'
        )
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "border-collapse:collapse" in rendered
        assert "padding:8px" in rendered
        assert "border:1px solid #ccc" in rendered

    @pytest.mark.parametrize(
        "declaration",
        [
            "position:fixed",
            "z-index:99",
            "opacity:0",
            "visibility:hidden",
            "float:left",
            "background-image:url(http://tracker.test/x.png)",
            "list-style-image:url(http://tracker.test/x.png)",
            "cursor:url(http://tracker.test/x.png),auto",
        ],
    )
    def test_html_body_drops_css_properties_outside_the_allowlist(self, declaration):
        body = f'<p style="{declaration}">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        prop = declaration.split(":", 1)[0]
        assert prop not in rendered
        assert "text" in rendered

    @pytest.mark.parametrize(
        "declaration",
        [
            # url() on an allowlisted property: bleach's CSSSanitizer allowlists
            # property names only and never inspects the value, so these are
            # rejected by the value-level guard instead.
            "background-color:url(http://tracker.test/x.png)",
            "font-family:url(http://tracker.test/x.png)",
            "width:expression(alert(1))",
            "color:expression(alert(1))",
        ],
    )
    def test_html_body_drops_unsafe_values_on_allowlisted_properties(self, declaration):
        body = f'<p style="{declaration}">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "url(" not in rendered
        assert "expression(" not in rendered
        assert "text" in rendered

    @pytest.mark.parametrize(
        "declaration",
        [
            # CSSSanitizer keeps its own default SVG property allowlist unless
            # allowed_svg_properties is cleared, so these would otherwise survive
            # despite not being in ALLOWED_CSS_PROPERTIES. fill-opacity and
            # stroke-opacity hide content, which `opacity` is excluded for.
            "fill:red",
            "fill-opacity:0",
            "fill-rule:evenodd",
            "stroke:blue",
            "stroke-opacity:0",
            "stroke-width:2",
            "stroke-linecap:round",
            "stroke-linejoin:bevel",
        ],
    )
    def test_html_body_drops_default_svg_css_properties(self, declaration):
        body = f'<p style="{declaration}">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert declaration.split(":", 1)[0] not in rendered
        assert "text" in rendered

    @pytest.mark.parametrize(
        "declaration",
        [
            "box-shadow:0 2px 6px rgba(16,35,59,0.12)",
            "text-shadow:0 1px 0 #ffffff",
        ],
    )
    def test_html_body_preserves_shadow_declarations(self, declaration):
        # Shadows cannot fetch remote content or conceal text, so they are on the
        # allowlist. Outlook ignores them, which degrades gracefully.
        body = f'<p style="{declaration}">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert declaration.split(":", 1)[0] in rendered

    @pytest.mark.parametrize(
        "declaration",
        [
            # Animations and transitions need @keyframes or a selector, neither of
            # which can exist inline, so they are kept off the allowlist rather
            # than preserved as declarations that could never do anything.
            "animation:pulse 2s infinite",
            "animation-name:pulse",
            "transition:color 0.3s ease",
        ],
    )
    def test_html_body_drops_animation_declarations(self, declaration):
        body = f'<p style="{declaration}">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert declaration.split(":", 1)[0] not in rendered
        assert "text" in rendered

    def test_html_body_keeps_safe_declarations_alongside_rejected_ones(self):
        body = '<p style="color:blue;position:absolute;padding:4px">text</p>'
        rendered = _html_part(create_email_message(body, files=None, is_html=True))
        assert "color:blue" in rendered
        assert "padding:4px" in rendered
        assert "position" not in rendered

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


class TestAppendSignature:
    """Tests for the append_signature helper."""

    def test_text_separator(self):
        assert append_signature("Hello", "Best,\nMe", is_html=False) == "Hello\n\n-- \nBest,\nMe"

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


class TestBuildRawEmailSignature:
    """End-to-end signature wiring through build_raw_email — every send/reply/
    draft handler funnels through this helper, so a single point of coverage
    here proves signatures land on all four actions."""

    def test_plain_text_body_includes_signature(self):
        msg = _decode_raw(
            build_raw_email(
                {
                    "to": "alice@example.com",
                    "subject": "Hi",
                    "body": "Hello Alice",
                    "signature": "Best,\nMe",
                }
            )
        )
        rendered = _decoded_text(msg)
        assert "Hello Alice" in rendered
        assert "-- " in rendered
        assert "Best," in rendered

    def test_html_body_includes_signature_in_html_part(self):
        msg = _decode_raw(
            build_raw_email(
                {
                    "to": "alice@example.com",
                    "subject": "Hi",
                    "body": "<p>Hello Alice</p>",
                    "body_format": "html",
                    "signature": "<p>Best, <b>Me</b></p>",
                }
            )
        )
        # Walk multipart, find the text/html part specifically.
        html_payload = next(
            part.get_payload(decode=True).decode("utf-8")
            for part in msg.walk()
            if part.get_content_type() == "text/html"
        )
        assert "Hello Alice" in html_payload
        assert "<b>Me</b>" in html_payload

    def test_no_signature_input_leaves_body_unchanged(self):
        msg = _decode_raw(build_raw_email({"to": "alice@example.com", "subject": "Hi", "body": "Hello Alice"}))
        rendered = _decoded_text(msg)
        assert "Hello Alice" in rendered
        assert "-- " not in rendered


class TestBuildDateClause:
    """Tests for the build_date_clause helper that translates ISO 8601 bounds
    into Gmail's ``after:<unix> before:<unix>`` search-syntax fragment."""

    def test_bare_date_after_only(self):
        # 2024-01-01 00:00 UTC == 1704067200 seconds since the epoch.
        assert build_date_clause(after="2024-01-01") == "after:1704067200"

    def test_bare_date_before_only(self):
        assert build_date_clause(before="2024-01-01") == "before:1704067200"

    def test_full_datetime_with_z_suffix(self):
        # 2024-01-01T12:00:00Z == 1704067200 + 43200 = 1704110400.
        assert build_date_clause(after="2024-01-01T12:00:00Z") == "after:1704110400"

    def test_full_datetime_with_offset(self):
        assert build_date_clause(after="2024-01-01T12:00:00+00:00") == "after:1704110400"

    def test_naive_datetime_treated_as_utc(self):
        # No timezone in input — must be interpreted as UTC, not local.
        assert build_date_clause(after="2024-01-01T12:00:00") == "after:1704110400"

    def test_both_bounds_after_first(self):
        result = build_date_clause(after="2024-01-01", before="2024-02-01")
        assert result == "after:1704067200 before:1706745600"

    def test_empty_inputs_return_empty(self):
        assert build_date_clause() == ""
        assert build_date_clause(after="", before="") == ""
        assert build_date_clause(after=None, before=None) == ""

    def test_malformed_input_raises_value_error(self):
        with pytest.raises(ValueError, match="after"):
            build_date_clause(after="not a date")
        with pytest.raises(ValueError, match="before"):
            build_date_clause(before="2024-13-99")


class TestComposeMessagesQuery:
    """Shared composer for the three list-action ``q`` values. Verifies the
    AND-join order (base → date → raw) and empty-fragment dropping."""

    def test_base_only(self):
        assert compose_messages_query("in:inbox", {}) == "in:inbox"

    def test_base_plus_after(self):
        assert compose_messages_query("in:inbox", {"after": "2024-01-01"}) == "in:inbox after:1704067200"

    def test_base_plus_raw_q(self):
        assert compose_messages_query("in:inbox", {"q": "has:attachment"}) == "in:inbox has:attachment"

    def test_all_three_fragments_in_order(self):
        result = compose_messages_query(
            "is:unread in:inbox",
            {"after": "2024-01-01", "before": "2024-02-01", "q": "has:attachment"},
        )
        assert result == "is:unread in:inbox after:1704067200 before:1706745600 has:attachment"

    def test_empty_base_with_filters(self):
        # ``read_all_mail`` scope="all" passes ``base_clause=""`` — date and raw
        # should still slot in without a leading space.
        assert compose_messages_query("", {"after": "2024-01-01"}) == "after:1704067200"

    def test_all_empty_returns_empty_string(self):
        # All-empty case lets ``read_all_mail`` drop the ``q`` kwarg entirely.
        assert compose_messages_query("", {}) == ""

    def test_malformed_after_propagates_value_error(self):
        with pytest.raises(ValueError, match="after"):
            compose_messages_query("in:inbox", {"after": "not a date"})


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


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode()


def _html_only_message(html):
    """A multipart/alternative message whose only body part is text/html."""
    message = _sample_message()
    message["payload"] = {
        "headers": message["payload"]["headers"],
        "mimeType": "multipart/alternative",
        "body": {"size": 0},
        "parts": [{"mimeType": "text/html", "body": {"data": _b64(html)}}],
    }
    return message


def _metadata_get_calls(service):
    """messages.get calls made with arguments (excludes the bare chain setup calls)."""
    return [c for c in service.users().messages().get.call_args_list if c.kwargs]


def _assert_metadata_gets(service, expected_ids):
    calls = _metadata_get_calls(service)
    assert [c.kwargs["id"] for c in calls] == expected_ids
    for c in calls:
        assert c.kwargs["format"] == "metadata"
        assert c.kwargs["metadataHeaders"] == ["Subject", "From", "To", "Cc", "Date"]


def _metadata_message(msg_id="m1", thread_id="t1", subject="Hello"):
    """A ``format=metadata`` response: headers only, no body data or parts."""
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "snippet",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
            ],
        },
    }


_MARKER_RE = re.compile(
    r"\n\n\[Body truncated: (?P<remaining>\d+) more characters\. "
    r"Call read_email again with body_offset=(?P<offset>\d+) to continue\.\]$"
)


async def _read_body(mock_context, message, body_offset=None):
    """Run read_email once against ``message``; return (body, result)."""
    inputs = {"user_id": "me", "email_id": "m1"}
    if body_offset is not None:
        inputs["body_offset"] = body_offset
    with _patched_service() as mock_build:
        service = _make_service()
        mock_build.return_value = service
        service.users().messages().get().execute.return_value = message
        result = await gmail.execute_action("read_email", inputs, mock_context)
    assert result.type == ResultType.ACTION
    return result.result.data["email"]["body"], result


async def _read_all_chunks(mock_context, message):
    """Follow truncation markers from offset 0; return (reassembled body, call count)."""
    parts, offset, calls = [], 0, 0
    while True:
        body, _ = await _read_body(mock_context, message, body_offset=offset)
        calls += 1
        match = _MARKER_RE.search(body)
        if not match:
            parts.append(body)
            return "".join(parts), calls
        chunk = body[: match.start()]
        assert offset + len(chunk) == int(match.group("offset"))
        parts.append(chunk)
        offset = int(match.group("offset"))


EXPECTED_PARSED_SAMPLE = {
    "id": "m1",
    "thread_id": "t1",
    "subject": "Hello",
    "from": "sender@example.com",
    "to": "me@example.com",
    "cc": [],
    "date": "Mon, 1 Jan 2024 10:00:00 +0000",
    "snippet": "snippet",
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

    @pytest.mark.asyncio
    async def test_html_only_body_is_converted_to_text(self, mock_context):
        html = (
            "<html><body><h1>Big news</h1>"
            "<p>Hello <b>there</b>, <a href='https://example.com'>read more</a>.</p>"
            "<img src='https://t.example.com/p.gif'></body></html>"
        )
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _html_only_message(html)
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        body = result.result.data["email"]["body"]
        assert "Big news" in body
        assert "Hello **there**" in body
        assert "https://example.com" in body
        assert "<" not in body and ">" not in body
        assert "p.gif" not in body

    @pytest.mark.asyncio
    async def test_plain_text_part_preferred_over_html(self, mock_context):
        message = _sample_message()
        message["payload"] = {
            "headers": message["payload"]["headers"],
            "mimeType": "multipart/alternative",
            "body": {"size": 0},
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>html version</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("plain version")}},
            ],
        }
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = message
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        assert result.result.data["email"]["body"] == "plain version"

    @pytest.mark.asyncio
    async def test_long_body_truncated_with_marker(self, mock_context):
        body = "a" * (MAX_READ_EMAIL_BODY_CHARS + 1234)
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _sample_message(body=body)
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        returned = result.result.data["email"]["body"]
        assert returned == "a" * MAX_READ_EMAIL_BODY_CHARS + (
            f"\n\n[Body truncated: 1234 more characters. "
            f"Call read_email again with body_offset={MAX_READ_EMAIL_BODY_CHARS} to continue.]"
        )

    @pytest.mark.asyncio
    async def test_long_html_body_truncated_after_conversion(self, mock_context):
        html = "<p>" + "word " * (MAX_READ_EMAIL_BODY_CHARS // 2) + "</p>"
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _html_only_message(html)
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        returned = result.result.data["email"]["body"]
        head, marker = returned.split("\n\n[Body truncated: ")
        assert len(head) == MAX_READ_EMAIL_BODY_CHARS
        assert "<p>" not in head
        assert marker.endswith(f"Call read_email again with body_offset={MAX_READ_EMAIL_BODY_CHARS} to continue.]")

    @pytest.mark.asyncio
    async def test_body_at_cap_is_not_truncated(self, mock_context):
        body = "a" * MAX_READ_EMAIL_BODY_CHARS
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _sample_message(body=body)
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        assert result.result.data["email"]["body"] == body

    @pytest.mark.asyncio
    async def test_short_body_has_no_marker(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().get().execute.return_value = _sample_message(body="Short body")
            result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": "m1"}, mock_context)
        assert result.result.data["email"]["body"] == "Short body"

    @pytest.mark.asyncio
    async def test_chunks_reassemble_full_plain_body(self, mock_context):
        # A decision at the very end must be recoverable by following the markers.
        body = "".join(str(i % 10) for i in range(MAX_READ_EMAIL_BODY_CHARS * 2 + 500)) + " DECISION: ship it"
        reassembled, calls = await _read_all_chunks(mock_context, _sample_message(body=body))
        assert reassembled == body
        assert calls == 3

    @pytest.mark.asyncio
    async def test_chunks_reassemble_full_html_body(self, mock_context):
        html = "".join(f"<p>Paragraph {i} of the newsletter.</p>" for i in range(2000)) + "<p>FINAL LINE</p>"
        first, _ = await _read_body(mock_context, _html_only_message(html))
        total = MAX_READ_EMAIL_BODY_CHARS + int(_MARKER_RE.search(first).group("remaining"))
        reassembled, calls = await _read_all_chunks(mock_context, _html_only_message(html))
        assert len(reassembled) == total
        assert reassembled.endswith("FINAL LINE")
        assert reassembled.count("Paragraph 1999 of") == 1
        assert calls > 1

    @pytest.mark.asyncio
    async def test_offset_past_end_returns_empty_body(self, mock_context):
        body, _ = await _read_body(mock_context, _sample_message(body="Short body"), body_offset=500)
        assert body == ""

    @pytest.mark.asyncio
    async def test_negative_offset_reads_from_start(self, mock_context):
        body, _ = await _read_body(mock_context, _sample_message(body="Short body"), body_offset=-5)
        assert body == "Short body"


class TestReadInbox:
    @pytest.mark.asyncio
    async def test_returns_emails_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}, {"id": "m2"}]}
            service.users().messages().get().execute.side_effect = [
                _metadata_message(msg_id="m1"),
                _metadata_message(msg_id="m2"),
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

    @pytest.mark.asyncio
    async def test_after_only_appends_date_clause(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_inbox",
                {"user_id": "me", "scope": "all", "after": "2024-01-01"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        # Scope clause first, then date clause, no raw q.
        assert call.kwargs["q"] == "in:inbox after:1704067200"

    @pytest.mark.asyncio
    async def test_before_only(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_inbox",
                {"user_id": "me", "scope": "all", "before": "2024-02-01"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "in:inbox before:1706745600"

    @pytest.mark.asyncio
    async def test_raw_q_appended_to_scope(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_inbox",
                {"user_id": "me", "scope": "unread", "q": "has:attachment"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "is:unread in:inbox has:attachment"

    @pytest.mark.asyncio
    async def test_combined_scope_date_and_raw_q(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_inbox",
                {
                    "user_id": "me",
                    "scope": "unread",
                    "after": "2024-01-01",
                    "before": "2024-02-01",
                    "q": "has:attachment",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        # Order: scope, date, raw.
        assert call.kwargs["q"] == "is:unread in:inbox after:1704067200 before:1706745600 has:attachment"

    @pytest.mark.asyncio
    async def test_malformed_after_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action(
                "read_inbox",
                {"user_id": "me", "scope": "all", "after": "not a date"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "after" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_default_max_results_is_25(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        assert service.users().messages().list.call_args.kwargs["maxResults"] == 25

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "requested, sent", [(10, 10), (100, 100), (250, 250), (500, 500), (0, 1), (-5, 1), (501, 500), (1000, 500)]
    )
    async def test_max_results_passed_through_and_clamped(self, mock_context, requested, sent):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_inbox", {"user_id": "me", "scope": "all", "maxResults": requested}, mock_context
            )
        assert service.users().messages().list.call_args.kwargs["maxResults"] == sent

    @pytest.mark.asyncio
    async def test_page_token_passed_with_max_results(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [], "nextPageToken": "next"}
            result = await gmail.execute_action(
                "read_inbox", {"user_id": "me", "scope": "all", "pageToken": "tok", "maxResults": 5}, mock_context
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["pageToken"] == "tok"
        assert call.kwargs["maxResults"] == 5
        assert result.result.data["nextPageToken"] == "next"

    @pytest.mark.asyncio
    async def test_fetches_metadata_only_and_output_unchanged(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _metadata_message()
            result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        _assert_metadata_gets(service, ["m1"])
        assert result.result.data["emails"] == [EXPECTED_PARSED_SAMPLE]

    @pytest.mark.asyncio
    async def test_metadata_response_without_headers_is_listed(self, mock_context):
        # payload.headers might be absent when none of the requested headers exist.
        message = _metadata_message()
        del message["payload"]["headers"]
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = message
            result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["emails"] == [
            {**EXPECTED_PARSED_SAMPLE, "subject": "", "from": "", "to": "", "date": ""}
        ]


class TestReadAllMail:
    @pytest.mark.asyncio
    async def test_returns_emails_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _metadata_message()
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

    @pytest.mark.asyncio
    async def test_no_filters_omits_q_entirely(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_all_mail",
                {"user_id": "me", "scope": "all"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        # scope=all with no date/q → preserve existing behavior: no ``q`` kwarg.
        assert "q" not in call.kwargs

    @pytest.mark.asyncio
    async def test_after_only(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_all_mail",
                {"user_id": "me", "scope": "all", "after": "2024-01-01"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "after:1704067200"

    @pytest.mark.asyncio
    async def test_combined_scope_date_and_raw_q(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_all_mail",
                {
                    "user_id": "me",
                    "scope": "read",
                    "after": "2024-01-01",
                    "q": "from:alice@example.com",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "-is:unread after:1704067200 from:alice@example.com"

    @pytest.mark.asyncio
    async def test_include_spam_trash_passthrough_preserved(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_all_mail",
                {
                    "user_id": "me",
                    "scope": "all",
                    "include_spam_trash": True,
                    "after": "2024-01-01",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "after:1704067200"
        assert call.kwargs["includeSpamTrash"] is True

    @pytest.mark.asyncio
    async def test_malformed_before_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action(
                "read_all_mail",
                {"user_id": "me", "scope": "all", "before": "not a date"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "before" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_default_max_results_is_25(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action("read_all_mail", {"user_id": "me", "scope": "all"}, mock_context)
        assert service.users().messages().list.call_args.kwargs["maxResults"] == 25

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "requested, sent", [(10, 10), (100, 100), (250, 250), (500, 500), (0, 1), (-5, 1), (501, 500), (1000, 500)]
    )
    async def test_max_results_passed_through_and_clamped(self, mock_context, requested, sent):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "read_all_mail", {"user_id": "me", "scope": "all", "maxResults": requested}, mock_context
            )
        assert service.users().messages().list.call_args.kwargs["maxResults"] == sent

    @pytest.mark.asyncio
    async def test_page_token_passed_with_max_results(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [], "nextPageToken": "next"}
            result = await gmail.execute_action(
                "read_all_mail",
                {"user_id": "me", "scope": "all", "pageToken": "tok", "maxResults": 5},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["pageToken"] == "tok"
        assert call.kwargs["maxResults"] == 5
        assert result.result.data["nextPageToken"] == "next"

    @pytest.mark.asyncio
    async def test_fetches_metadata_only_and_output_unchanged(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _metadata_message()
            result = await gmail.execute_action("read_all_mail", {"user_id": "me", "scope": "all"}, mock_context)
        _assert_metadata_gets(service, ["m1"])
        assert result.result.data["emails"] == [EXPECTED_PARSED_SAMPLE]


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
            service.users().messages().get().execute.return_value = _metadata_message()
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

    @pytest.mark.asyncio
    async def test_single_label_with_after(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": "Work", "after": "2024-01-01"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        # Default behavior pins to inbox unless include_archived=True.
        assert call.kwargs["q"] == "label:Work in:inbox after:1704067200"

    @pytest.mark.asyncio
    async def test_multiple_labels_with_date_range(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {
                    "user_id": "me",
                    "label_names": ["Work", "STARRED"],
                    "after": "2024-01-01",
                    "before": "2024-02-01",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "label:Work label:STARRED in:inbox after:1704067200 before:1706745600"

    @pytest.mark.asyncio
    async def test_include_archived_drops_inbox_clause(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {
                    "user_id": "me",
                    "label_names": "Work",
                    "include_archived": True,
                    "after": "2024-01-01",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "label:Work after:1704067200"

    @pytest.mark.asyncio
    async def test_explicit_inbox_label_avoids_double_inbox_clause(self, mock_context):
        # Existing behavior: when the user explicitly asks for INBOX, the
        # handler does NOT append ``in:inbox`` again. Confirm date still slots in.
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": "INBOX", "after": "2024-01-01"},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "label:INBOX after:1704067200"

    @pytest.mark.asyncio
    async def test_combined_label_date_and_raw_q(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {
                    "user_id": "me",
                    "label_names": "Work",
                    "after": "2024-01-01",
                    "q": "from:alice@example.com",
                },
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["q"] == "label:Work in:inbox after:1704067200 from:alice@example.com"

    @pytest.mark.asyncio
    async def test_malformed_after_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            result = await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": "Work", "after": "not a date"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "after" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_default_max_results_is_25(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label", {"user_id": "me", "label_names": ["MyLabel"]}, mock_context
            )
        assert service.users().messages().list.call_args.kwargs["maxResults"] == 25

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "requested, sent", [(10, 10), (100, 100), (250, 250), (500, 500), (0, 1), (-5, 1), (501, 500), (1000, 500)]
    )
    async def test_max_results_passed_through_and_clamped(self, mock_context, requested, sent):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": []}
            await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": ["MyLabel"], "maxResults": requested},
                mock_context,
            )
        assert service.users().messages().list.call_args.kwargs["maxResults"] == sent

    @pytest.mark.asyncio
    async def test_page_token_passed_with_max_results(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [], "nextPageToken": "next"}
            result = await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": ["MyLabel"], "pageToken": "tok", "maxResults": 5},
                mock_context,
            )
        call = service.users().messages().list.call_args
        assert call.kwargs["pageToken"] == "tok"
        assert call.kwargs["maxResults"] == 5
        assert result.result.data["nextPageToken"] == "next"

    @pytest.mark.asyncio
    async def test_fetches_metadata_only_and_output_unchanged(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
            service.users().messages().get().execute.return_value = _metadata_message()
            result = await gmail.execute_action(
                "list_emails_by_label", {"user_id": "me", "label_names": ["MyLabel"]}, mock_context
            )
        _assert_metadata_gets(service, ["m1"])
        assert result.result.data["emails"] == [EXPECTED_PARSED_SAMPLE]


# ============================================================
#  Thread actions
# ============================================================


def _thread_messages(count):
    """``count`` metadata messages m0..m{count-1}, received one second apart."""
    messages = []
    for i in range(count):
        message = _metadata_message(msg_id=f"m{i}")
        message["internalDate"] = str(1700000000000 + i * 1000)
        messages.append(message)
    return messages


def _thread_token(i):
    """The nextPageToken that points at message m{i} from ``_thread_messages``."""
    return f"t1:{1700000000000 + i * 1000}:m{i}"


async def _walk_thread(mock_context, current_messages, **inputs):
    """Follow nextPageToken from the newest batch; return each batch's ids.

    ``current_messages`` is called before every request, so a test can change
    the thread between batches.
    """
    batches, token = [], None
    while True:
        extra = {"pageToken": token} if token else {}
        data, _ = await _get_thread(mock_context, current_messages(), **inputs, **extra)
        batches.append([e["id"] for e in data["emails"]])
        token = data.get("nextPageToken")
        if not token:
            return batches


async def _get_thread(mock_context, messages, **inputs):
    """Run get_thread_emails against ``messages``; return (data, service)."""
    with _patched_service() as mock_build:
        service = _make_service()
        mock_build.return_value = service
        service.users().threads().get().execute.return_value = {"id": "t1", "messages": messages}
        result = await gmail.execute_action(
            "get_thread_emails", {"user_id": "me", "thread_id": "t1", **inputs}, mock_context
        )
    assert result.type == ResultType.ACTION
    return result.result.data, service


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
        assert result.result.data["total_messages"] == 2
        assert "nextPageToken" not in result.result.data

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.side_effect = Exception("not found")
            result = await gmail.execute_action("get_thread_emails", {"user_id": "me", "thread_id": "t1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_fetches_thread_as_metadata(self, mock_context):
        _, service = await _get_thread(mock_context, _thread_messages(2))
        call = service.users().threads().get.call_args
        assert call.kwargs == {
            "userId": "me",
            "id": "t1",
            "format": "metadata",
            "metadataHeaders": ["Subject", "From", "To", "Cc", "Date"],
        }

    @pytest.mark.asyncio
    async def test_default_returns_newest_batch_in_chronological_order(self, mock_context):
        data, _ = await _get_thread(mock_context, _thread_messages(30))
        assert [e["id"] for e in data["emails"]] == [f"m{i}" for i in range(5, 30)]
        assert len(data["emails"]) == DEFAULT_THREAD_MAX_MESSAGES
        assert data["total_messages"] == 30
        assert data["nextPageToken"] == _thread_token(5)

    @pytest.mark.asyncio
    async def test_following_tokens_returns_every_message_once(self, mock_context):
        messages = _thread_messages(11)
        batches = await _walk_thread(mock_context, lambda: messages, max_messages=3)
        assert batches == [["m8", "m9", "m10"], ["m5", "m6", "m7"], ["m2", "m3", "m4"], ["m0", "m1"]]

    @pytest.mark.asyncio
    async def test_reply_arriving_between_batches_does_not_repeat_messages(self, mock_context):
        messages = _thread_messages(6)
        first, _ = await _get_thread(mock_context, messages, max_messages=2)
        assert [e["id"] for e in first["emails"]] == ["m4", "m5"]
        messages = _thread_messages(7)  # reply m6 arrives
        second, _ = await _get_thread(mock_context, messages, max_messages=2, pageToken=first["nextPageToken"])
        assert [e["id"] for e in second["emails"]] == ["m2", "m3"]
        assert second["total_messages"] == 7

    @pytest.mark.asyncio
    async def test_deleting_returned_message_between_batches_does_not_skip(self, mock_context):
        messages = _thread_messages(6)
        first, _ = await _get_thread(mock_context, messages, max_messages=2)
        remaining = [m for m in messages if m["id"] != "m5"]
        second, _ = await _get_thread(mock_context, remaining, max_messages=2, pageToken=first["nextPageToken"])
        assert [e["id"] for e in second["emails"]] == ["m2", "m3"]

    @pytest.mark.asyncio
    async def test_deleting_boundary_message_between_batches_does_not_skip(self, mock_context):
        messages = _thread_messages(6)
        first, _ = await _get_thread(mock_context, messages, max_messages=2)
        assert first["nextPageToken"] == _thread_token(4)
        remaining = [m for m in messages if m["id"] != "m4"]
        second, _ = await _get_thread(mock_context, remaining, max_messages=2, pageToken=first["nextPageToken"])
        assert [e["id"] for e in second["emails"]] == ["m2", "m3"]

    @pytest.mark.asyncio
    async def test_messages_with_same_internal_date_are_split_by_id(self, mock_context):
        messages = _thread_messages(3)
        for message in messages:
            message["internalDate"] = "1700000000000"
        batches = await _walk_thread(mock_context, lambda: [messages[2], messages[0], messages[1]], max_messages=1)
        assert batches == [["m2"], ["m1"], ["m0"]]

    @pytest.mark.asyncio
    async def test_orders_by_internal_date_not_gmail_order_or_date_header(self, mock_context):
        # Gmail order is shuffled and the Date headers mix unparseable, naive and
        # aware values, which the previous Date-header sort could not compare.
        messages = _thread_messages(3)
        dates = ["not a date", "Mon, 1 Jan 2024 10:00:00", "Mon, 1 Jan 2024 10:00:00 +0000"]
        for message, date in zip(messages, dates):
            for header in message["payload"]["headers"]:
                if header["name"] == "Date":
                    header["value"] = date
        data, _ = await _get_thread(mock_context, [messages[2], messages[0], messages[1]])
        assert [e["id"] for e in data["emails"]] == ["m0", "m1", "m2"]

    @pytest.mark.asyncio
    async def test_token_older_than_every_message_returns_no_emails(self, mock_context):
        data, _ = await _get_thread(mock_context, _thread_messages(4), pageToken="t1:1:m0")
        assert data["emails"] == []
        assert data["total_messages"] == 4
        assert "nextPageToken" not in data

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "token",
        ["garbage", "1700000000000:m1", "t1:abc:m1", "t1:1700000000000:", "t1::m1", "t1:-5:m1", "t1:\u00b2:m1"],
    )
    async def test_malformed_token_returns_action_error(self, mock_context, token):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.return_value = {"id": "t1", "messages": _thread_messages(2)}
            result = await gmail.execute_action(
                "get_thread_emails", {"user_id": "me", "thread_id": "t1", "pageToken": token}, mock_context
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid pageToken" in result.result.message

    @pytest.mark.asyncio
    async def test_token_from_another_thread_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.return_value = {"id": "t1", "messages": _thread_messages(2)}
            result = await gmail.execute_action(
                "get_thread_emails",
                {"user_id": "me", "thread_id": "t1", "pageToken": "t2:1700000000000:m0"},
                mock_context,
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "belongs to a different thread, not 't1'" in result.result.message

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token", ["x" * 500, "x" * 500 + ":1700000000000:m0"])
    async def test_long_invalid_token_is_shortened_in_error(self, mock_context, token):
        # The second token is well-formed but for another thread, so it fails the thread check.
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().threads().get().execute.return_value = {"id": "t1", "messages": _thread_messages(2)}
            result = await gmail.execute_action(
                "get_thread_emails", {"user_id": "me", "thread_id": "t1", "pageToken": token}, mock_context
            )
        assert result.type == ResultType.ACTION_ERROR
        assert "x" * 64 + "..." in result.result.message
        assert "x" * 65 not in result.result.message

    @pytest.mark.asyncio
    async def test_walk_survives_reply_and_deletion_mid_walk(self, mock_context):
        # m0..m9 in batches of 3. After the first batch a reply m10 arrives and the
        # already-returned m8 is deleted; after the second, the unread m2 is deleted.
        thread = _thread_messages(11)
        calls = {"n": 0}

        def current():
            calls["n"] += 1
            if calls["n"] == 1:
                return [m for m in thread if m["id"] != "m10"]
            if calls["n"] == 2:
                return [m for m in thread if m["id"] != "m8"]
            return [m for m in thread if m["id"] not in ("m8", "m2")]

        batches = await _walk_thread(mock_context, current, max_messages=3)
        assert batches == [["m7", "m8", "m9"], ["m4", "m5", "m6"], ["m0", "m1", "m3"]]
        seen = [i for batch in batches for i in batch]
        assert len(seen) == len(set(seen))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("requested, returned", [(0, 1), (-5, 1), (100, 100), (101, 100), (1000, 100)])
    async def test_max_messages_is_clamped(self, mock_context, requested, returned):
        data, _ = await _get_thread(mock_context, _thread_messages(120), max_messages=requested)
        assert len(data["emails"]) == returned
        assert data["nextPageToken"] == _thread_token(120 - returned)


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


# ============================================================
#  Send-as signature listing
# ============================================================


class TestListSendAsSignatures:
    """Lists the signature currently bound as the new-mail default on each
    of the user's send-as addresses. The Gmail API does not expose the full
    saved-signatures library — only this per-address default."""

    @pytest.mark.asyncio
    async def test_happy_path_two_aliases(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.return_value = {
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
            result = await gmail.execute_action("list_send_as_signatures", {"user_id": "me"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert len(data["signatures"]) == 2

        primary = data["signatures"][0]
        assert primary["send_as_email"] == "me@example.com"
        assert primary["display_name"] == "Me"
        assert primary["is_primary"] is True
        assert primary["is_default"] is True
        assert primary["signature"] == "<p>Primary sig</p>"
        assert primary["reply_to_address"] == "reply@example.com"

        alias = data["signatures"][1]
        assert alias["is_primary"] is False
        assert alias["is_default"] is False

    @pytest.mark.asyncio
    async def test_missing_optional_fields_default_to_empty(self, mock_context):
        # Gmail omits ``displayName``, ``replyToAddress``, ``signature`` etc.
        # when they're not configured. Confirm we surface defaults rather than
        # ``None`` or ``KeyError``.
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.return_value = {
                "sendAs": [
                    {
                        "sendAsEmail": "me@example.com",
                        "isPrimary": True,
                        "isDefault": True,
                    }
                ]
            }
            result = await gmail.execute_action("list_send_as_signatures", {"user_id": "me"}, mock_context)

        assert result.type == ResultType.ACTION
        entry = result.result.data["signatures"][0]
        assert entry["display_name"] == ""
        assert entry["signature"] == ""
        assert entry["reply_to_address"] == ""
        assert entry["is_primary"] is True
        assert entry["is_default"] is True

    @pytest.mark.asyncio
    async def test_empty_send_as_list(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.return_value = {}
            result = await gmail.execute_action("list_send_as_signatures", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION
        assert result.result.data == {"signatures": []}

    @pytest.mark.asyncio
    async def test_null_signature_becomes_empty_string(self, mock_context):
        # Gmail can return ``"signature": null`` for a send-as that has no
        # default signature bound. The handler must coerce to ``""`` — not the
        # string ``"None"``, and not leave it as ``None``.
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.return_value = {
                "sendAs": [
                    {
                        "sendAsEmail": "me@example.com",
                        "isPrimary": True,
                        "isDefault": True,
                        "signature": None,
                    }
                ]
            }
            result = await gmail.execute_action("list_send_as_signatures", {"user_id": "me"}, mock_context)
        entry = result.result.data["signatures"][0]
        assert entry["signature"] == ""
        assert entry["signature"] != "None"

    @pytest.mark.asyncio
    async def test_defaults_user_id_to_me(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.return_value = {"sendAs": []}
            await gmail.execute_action("list_send_as_signatures", {}, mock_context)
        call = service.users().settings().sendAs().list.call_args
        assert call.kwargs == {"userId": "me"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with _patched_service() as mock_build:
            service = _make_service()
            mock_build.return_value = service
            service.users().settings().sendAs().list().execute.side_effect = Exception("403")
            result = await gmail.execute_action("list_send_as_signatures", {"user_id": "me"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "403" in result.result.message
