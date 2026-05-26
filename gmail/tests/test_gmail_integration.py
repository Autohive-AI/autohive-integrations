"""End-to-end integration tests for the Gmail integration.

The integration uses Google's ``googleapiclient`` Python SDK directly rather
than ``context.fetch``, so this file follows **Variant 4 — External Python SDK**:
build an ``ExecutionContext`` with a real OAuth token and let the upstream SDK
make HTTP calls itself.

Required environment variables (loaded from project ``.env``):
    GMAIL_ACCESS_TOKEN              — required; OAuth token with the
                                       ``gmail.modify`` scope
    GMAIL_TEST_RECIPIENT            — optional; email address to send to in
                                       destructive send tests (defaults to the
                                       authenticated user)

Run with:
    pytest gmail/tests/test_gmail_integration.py -m "integration and not destructive"
    pytest gmail/tests/test_gmail_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter ``-m unit`` excludes these.
"""

from __future__ import annotations

import os

import pytest

from autohive_integrations_sdk.integration import ResultType

from gmail.gmail import gmail

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def live_context(env_credentials, make_context):
    """Variant 4 — External SDK: hand the OAuth token to the integration via
    ``context.auth`` and let ``googleapiclient`` do its own networking."""
    access_token = env_credentials("GMAIL_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("GMAIL_ACCESS_TOKEN not set — skipping integration tests")
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )


def _ok(envelope):
    """Assert the envelope wraps a successful ActionResult and return its data."""
    assert envelope.type != ResultType.ACTION_ERROR, getattr(envelope.result, "message", "") or "unexpected ActionError"
    return envelope.result.data


# ---------------------------------------------------------------------------
# Read-Only Tests
# ---------------------------------------------------------------------------


class TestGetUserInfo:
    async def test_get_user_info(self, live_context):
        envelope = await gmail.execute_action(
            "get_user_info",
            {"user_id": "me"},
            live_context,
        )
        data = _ok(envelope)
        assert data["user_info"]["email_address"]


class TestReadInbox:
    async def test_read_inbox(self, live_context):
        envelope = await gmail.execute_action(
            "read_inbox",
            {"user_id": "me", "scope": "all"},
            live_context,
        )
        data = _ok(envelope)
        assert "emails" in data
        assert isinstance(data["emails"], list)


class TestListLabels:
    async def test_list_labels(self, live_context):
        envelope = await gmail.execute_action(
            "list_labels",
            {"user_id": "me"},
            live_context,
        )
        data = _ok(envelope)
        assert isinstance(data["labels"], list)
        # Every Gmail account has at least the INBOX system label.
        names = {label["name"] for label in data["labels"]}
        assert "INBOX" in names


class TestListSendAsSignatures:
    """Read-only — lists the user's send-as addresses and the signature bound
    as the new-mail default on each one. Important limitation: the Gmail API
    only exposes the bound default, not the user's full signatures library."""

    async def test_list_send_as_signatures(self, live_context):
        envelope = await gmail.execute_action(
            "list_send_as_signatures",
            {"user_id": "me"},
            live_context,
        )
        data = _ok(envelope)
        assert "signatures" in data
        assert isinstance(data["signatures"], list)
        # At minimum the primary inbox address comes back.
        assert len(data["signatures"]) >= 1
        primary = next((s for s in data["signatures"] if s["is_primary"]), None)
        assert primary is not None
        # Every entry must have the required fields with the right types.
        for entry in data["signatures"]:
            assert isinstance(entry["send_as_email"], str)
            assert entry["send_as_email"]
            assert isinstance(entry["is_primary"], bool)
            assert isinstance(entry["is_default"], bool)
            assert isinstance(entry["signature"], str)


# ---------------------------------------------------------------------------
# Bad-input tests — clean ActionError translation
# ---------------------------------------------------------------------------


class TestActionErrorTranslation:
    async def test_read_email_with_bad_id_returns_action_error(self, live_context):
        envelope = await gmail.execute_action(
            "read_email",
            {"user_id": "me", "email_id": "definitely-not-a-real-id"},
            live_context,
        )
        assert envelope.type == ResultType.ACTION_ERROR


# ---------------------------------------------------------------------------
# Destructive Tests (Write Operations)
# Only run with: pytest -m "integration and destructive"
#
# Recommended: run these against a throwaway Google account. The send tests
# default to sending to the authenticated user, so the email lands in the
# same inbox we're testing from.
# ---------------------------------------------------------------------------


def _recipient() -> str:
    return os.environ.get("GMAIL_TEST_RECIPIENT", "")


@pytest.mark.destructive
class TestSendEmail:
    async def test_send_plain_text(self, live_context):
        recipient = _recipient()
        if not recipient:
            pytest.skip("GMAIL_TEST_RECIPIENT not set — skipping send tests")
        envelope = await gmail.execute_action(
            "send_email",
            {
                "to": [recipient],
                "subject": "autohive-test send",
                "body": "Hello from autohive-test",
                # "signature": "Best,\nYour Name",
            },
            live_context,
        )
        data = _ok(envelope)
        assert data["id"]


@pytest.mark.destructive
class TestReplyToThread:
    """Reply to an existing thread. Skipped unless GMAIL_TEST_THREAD_ID and
    GMAIL_TEST_MESSAGE_ID are provided — replies are only sensible against a
    known thread you own."""

    async def test_reply_to_thread(self, live_context):
        thread_id = os.environ.get("GMAIL_TEST_THREAD_ID", "")
        message_id = os.environ.get("GMAIL_TEST_MESSAGE_ID", "")
        if not (thread_id and message_id):
            pytest.skip("GMAIL_TEST_THREAD_ID / GMAIL_TEST_MESSAGE_ID not set")
        envelope = await gmail.execute_action(
            "reply_to_thread",
            {
                "user_id": "me",
                "thread_id": thread_id,
                "message_id": message_id,
                "body": "autohive-test reply",
                # "signature": "Best,\nYour Name",
            },
            live_context,
        )
        data = _ok(envelope)
        assert data["id"]


@pytest.mark.destructive
class TestCreateDraftReply:
    """Draft a reply on an existing thread, then delete it."""

    async def test_create_then_delete_draft_reply(self, live_context):
        thread_id = os.environ.get("GMAIL_TEST_THREAD_ID", "")
        message_id = os.environ.get("GMAIL_TEST_MESSAGE_ID", "")
        if not (thread_id and message_id):
            pytest.skip("GMAIL_TEST_THREAD_ID / GMAIL_TEST_MESSAGE_ID not set")
        create_env = await gmail.execute_action(
            "create_draft",
            {
                "user_id": "me",
                "thread_id": thread_id,
                "message_id": message_id,
                "body": "autohive-test draft reply",
                # "signature": "Best,\nYour Name",
            },
            live_context,
        )
        data = _ok(create_env)
        draft_id = data["draft"]["id"]
        assert draft_id

        delete_env = await gmail.execute_action(
            "delete_draft",
            {"user_id": "me", "draft_id": draft_id},
            live_context,
        )
        _ok(delete_env)
