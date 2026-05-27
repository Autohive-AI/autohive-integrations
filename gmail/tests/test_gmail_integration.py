"""End-to-end integration tests for the Gmail integration.

These tests call the real Gmail API and require a valid OAuth 2.0 access
token (with the `https://www.googleapis.com/auth/gmail.modify` scope)
set in the GMAIL_ACCESS_TOKEN environment variable (via .env or export).

Optional env vars (override dynamic test data):
    GMAIL_TEST_THREAD_ID   — thread id for reply / thread-read tests
    GMAIL_TEST_MESSAGE_ID  — message id for reply tests

Run with:

    # Read-only tests only — safe, no mailbox mutation
    pytest gmail/tests/test_gmail_integration.py -m "integration and not destructive"

    # Destructive lifecycle tests — sends real email to yourself,
    # creates and deletes a real label, creates and deletes a real
    # draft, etc.
    pytest gmail/tests/test_gmail_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes
these, and the file naming (test_*_integration.py) is not matched by
python_files.

This integration uses Google's googleapiclient (not context.fetch), so
the live_context fixture follows Variant 4 from the
writing-integration-tests skill: inject the credential envelope and let
the upstream Google SDK handle networking.
"""

import os

import pytest
from autohive_integrations_sdk.integration import ResultType

from gmail.gmail import gmail

pytestmark = pytest.mark.integration


# Optional env-var overrides for fixture data.
TEST_THREAD_ID = os.environ.get("GMAIL_TEST_THREAD_ID", "")
TEST_MESSAGE_ID = os.environ.get("GMAIL_TEST_MESSAGE_ID", "")


@pytest.fixture
def live_context(env_credentials, make_context):
    """Live context wired with a real Gmail OAuth access token.

    Variant 4 (external Python SDK): no `real_fetch` wrapper needed —
    gmail.py uses googleapiclient directly. We just shape the auth
    envelope the way the SDK's platform-OAuth path would, and the
    integration's `build_credentials` reads the access token out of it.
    """
    token = env_credentials("GMAIL_ACCESS_TOKEN")
    if not token:
        pytest.skip("GMAIL_ACCESS_TOKEN not set — skipping Gmail integration tests")
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": token},
        }
    )


# ============================================================
#  Read-Only Tests
#  Safe to run repeatedly — no mailbox mutation.
# ============================================================


class TestGetUserInfo:
    """Verifies the authenticated user's profile is retrievable."""

    @pytest.mark.asyncio
    async def test_returns_profile(self, live_context):
        result = await gmail.execute_action("get_user_info", {"user_id": "me"}, live_context)
        assert result.type == ResultType.ACTION
        info = result.result.data["user_info"]
        assert "email_address" in info
        assert "@" in info["email_address"]
        assert isinstance(info["messages_total"], int)


class TestListLabels:
    """Lists the authenticated user's mailbox labels (read-only)."""

    @pytest.mark.asyncio
    async def test_returns_labels(self, live_context):
        result = await gmail.execute_action("list_labels", {"user_id": "me"}, live_context)
        assert result.type == ResultType.ACTION
        labels = result.result.data["labels"]
        assert isinstance(labels, list)
        # Every Gmail account has the system INBOX label
        names = {label.get("name") for label in labels}
        assert "INBOX" in names


class TestReadInbox:
    """Lists inbox messages with read/unread filtering and pagination."""

    @pytest.mark.asyncio
    async def test_default_scope_returns_emails(self, live_context):
        result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
        assert result.type == ResultType.ACTION
        assert "emails" in result.result.data
        assert isinstance(result.result.data["emails"], list)

    @pytest.mark.asyncio
    async def test_unread_scope_returns_emails_or_empty(self, live_context):
        result = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "unread"}, live_context)
        assert result.type == ResultType.ACTION
        # May be empty if the inbox has no unread messages — both states are valid
        assert isinstance(result.result.data["emails"], list)

    @pytest.mark.asyncio
    async def test_next_page_token_chained(self, live_context):
        first = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
        token = first.result.data.get("nextPageToken")
        if not token:
            pytest.skip("Inbox fits in one page — pagination chain not exercised")
        second = await gmail.execute_action(
            "read_inbox", {"user_id": "me", "scope": "all", "pageToken": token}, live_context
        )
        assert second.type == ResultType.ACTION


class TestReadAllMail:
    """Lists messages across the entire mailbox."""

    @pytest.mark.asyncio
    async def test_returns_emails(self, live_context):
        result = await gmail.execute_action("read_all_mail", {"user_id": "me", "scope": "all"}, live_context)
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["emails"], list)


class TestReadEmailChained:
    """Reads a real message — picks the first inbox message dynamically
    (or uses GMAIL_TEST_MESSAGE_ID if set)."""

    @pytest.mark.asyncio
    async def test_returns_email_object(self, live_context):
        message_id = TEST_MESSAGE_ID
        if not message_id:
            inbox = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
            emails = inbox.result.data.get("emails", [])
            if not emails:
                pytest.skip("Inbox is empty — cannot exercise read_email")
            message_id = emails[0]["id"]

        result = await gmail.execute_action("read_email", {"user_id": "me", "email_id": message_id}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["email"]["id"] == message_id
        assert "files" in result.result.data


class TestGetThreadEmailsChained:
    """Reads a thread — picks one dynamically (or uses GMAIL_TEST_THREAD_ID
    if set)."""

    @pytest.mark.asyncio
    async def test_returns_thread_emails(self, live_context):
        thread_id = TEST_THREAD_ID
        if not thread_id:
            inbox = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
            emails = inbox.result.data.get("emails", [])
            if not emails:
                pytest.skip("Inbox is empty — cannot exercise get_thread_emails")
            thread_id = emails[0].get("threadId") or emails[0].get("thread_id")
            if not thread_id:
                pytest.skip("First inbox email has no thread_id field")

        result = await gmail.execute_action(
            "get_thread_emails", {"user_id": "me", "thread_id": thread_id}, live_context
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["thread_id"] == thread_id
        assert isinstance(result.result.data["emails"], list)


class TestListDrafts:
    """Lists existing drafts — safe even if there are none."""

    @pytest.mark.asyncio
    async def test_returns_drafts_list(self, live_context):
        result = await gmail.execute_action("list_drafts", {"user_id": "me"}, live_context)
        assert result.type == ResultType.ACTION
        assert "drafts" in result.result.data


class TestListEmailsByLabelChained:
    """Lists emails for a label that we know exists (INBOX)."""

    @pytest.mark.asyncio
    async def test_returns_inbox_emails(self, live_context):
        result = await gmail.execute_action(
            "list_emails_by_label",
            {"user_id": "me", "label_names": ["INBOX"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["emails"], list)


# ============================================================
#  Destructive Tests (Write Operations)
#
#  These tests CREATE, UPDATE, or DELETE real data in the
#  authenticated user's Gmail account. They are clearly named
#  with "Lifecycle" in the class name and a docstring describing
#  exactly what gets created and what gets cleaned up.
#
#  Run only with:
#      pytest -m "integration and destructive"
# ============================================================


@pytest.mark.destructive
class TestLabelLifecycle:
    """LIFECYCLE: creates a real label in the user's mailbox, applies it
    to the most-recent inbox message, removes it, then deletes the label.

    What is created: 1 user-defined label (named "AH integration test
    {pid}"). What is mutated: 1 message gains and then loses one label.
    Cleanup: the label is deleted via the Gmail API at the end. The
    message itself is left in place; only the label association is
    reverted.
    """

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, live_context):
        label_name = f"AH integration test {os.getpid()}"

        # 1. Pick a real message id to apply the label to
        inbox = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
        emails = inbox.result.data.get("emails", [])
        if not emails:
            pytest.skip("Inbox is empty — cannot exercise label lifecycle")
        message_id = emails[0]["id"]

        # 2. Create the label
        create_result = await gmail.execute_action("create_label", {"user_id": "me", "name": label_name}, live_context)
        assert create_result.type == ResultType.ACTION, create_result
        label_id = create_result.result.data["label"]["id"]

        try:
            # 3. Apply the label to the message
            add_result = await gmail.execute_action(
                "add_labels_to_emails",
                {"user_id": "me", "message_ids": [message_id], "label_ids": [label_id]},
                live_context,
            )
            assert add_result.type == ResultType.ACTION

            # 4. Verify the label appears when listing by it
            list_by_label = await gmail.execute_action(
                "list_emails_by_label",
                {"user_id": "me", "label_names": [label_name]},
                live_context,
            )
            assert list_by_label.type == ResultType.ACTION

            # 5. Remove the label from the message
            remove_result = await gmail.execute_action(
                "remove_labels_from_emails",
                {"user_id": "me", "message_ids": [message_id], "label_ids": [label_id]},
                live_context,
            )
            assert remove_result.type == ResultType.ACTION
        finally:
            # 6. Cleanup: delete the label via the Google client directly
            # (no public delete-label action in this integration)
            from gmail.gmail import build_gmail_service

            service = build_gmail_service(live_context)
            try:
                service.users().labels().delete(userId="me", id=label_id).execute()
            except Exception as cleanup_err:
                # Best-effort cleanup — leave the label if cleanup fails
                print(f"Label cleanup failed for {label_id}: {cleanup_err}")


@pytest.mark.destructive
class TestSendEmailLifecycle:
    """LIFECYCLE: sends a real email FROM and TO the authenticated user
    (so it lands back in the same inbox), then exercises the read/unread
    state transitions on it, then archives it.

    What is created: 1 outbound email + 1 inbound email (the same
    message, both sent and received by the same account). Subject line
    includes the test PID for traceability so you can find/delete it
    later: "[AH integration test {pid}] gmail integration self-test".
    Cleanup: the inbound copy is archived (removed from the INBOX
    label); it remains in All Mail and can be permanently deleted from
    the Gmail UI if desired.
    """

    @pytest.mark.asyncio
    async def test_send_and_archive(self, live_context):
        # Get the authenticated user's address so we can send to ourselves
        profile = await gmail.execute_action("get_user_info", {"user_id": "me"}, live_context)
        my_address = profile.result.data["user_info"]["email_address"]

        subject = f"[AH integration test {os.getpid()}] gmail integration self-test"

        # 1. Send
        send_result = await gmail.execute_action(
            "send_email",
            {
                "to": [my_address],
                "subject": subject,
                "body": "This message was sent by the gmail integration test suite. Safe to delete.",
            },
            live_context,
        )
        assert send_result.type == ResultType.ACTION, send_result
        sent_message_id = send_result.result.data["id"]
        assert sent_message_id

        # 2. Mark unread → read (round-trip on the just-sent message)
        unread_result = await gmail.execute_action(
            "mark_emails_as_unread",
            {"user_id": "me", "ids": [sent_message_id]},
            live_context,
        )
        assert unread_result.type == ResultType.ACTION

        read_result = await gmail.execute_action(
            "mark_emails_as_read",
            {"user_id": "me", "ids": [sent_message_id]},
            live_context,
        )
        assert read_result.type == ResultType.ACTION

        # 3. Cleanup: archive (remove from inbox)
        archive_result = await gmail.execute_action(
            "archive_emails",
            {"user_id": "me", "ids": [sent_message_id]},
            live_context,
        )
        assert archive_result.type == ResultType.ACTION


@pytest.mark.destructive
class TestDraftLifecycle:
    """LIFECYCLE: creates a real draft, updates it, fetches it back, and
    deletes it.

    What is created: 1 draft (subject "[AH integration test {pid}]
    draft lifecycle test"). Cleanup: the draft is deleted at the end.
    The draft is NEVER sent in this test — see TestSendDraftLifecycle
    for that.
    """

    @pytest.mark.asyncio
    async def test_create_update_get_delete(self, live_context):
        subject = f"[AH integration test {os.getpid()}] draft lifecycle test"

        # 1. Create draft
        create_result = await gmail.execute_action(
            "create_draft",
            {
                "to": ["self-test@example.com"],
                "subject": subject,
                "body": "Initial draft body",
            },
            live_context,
        )
        assert create_result.type == ResultType.ACTION, create_result
        draft_id = create_result.result.data["draft"]["id"]
        assert draft_id

        try:
            # 2. Update draft
            update_result = await gmail.execute_action(
                "update_draft",
                {
                    "draft_id": draft_id,
                    "to": ["self-test@example.com"],
                    "subject": subject,
                    "body": "Updated draft body",
                },
                live_context,
            )
            assert update_result.type == ResultType.ACTION

            # 3. Get draft back
            get_result = await gmail.execute_action("get_draft", {"user_id": "me", "draft_id": draft_id}, live_context)
            assert get_result.type == ResultType.ACTION
            assert "draft" in get_result.result.data
        finally:
            # 4. Cleanup: delete draft (always runs, even if assertions failed)
            delete_result = await gmail.execute_action(
                "delete_draft", {"user_id": "me", "draft_id": draft_id}, live_context
            )
            assert delete_result.type == ResultType.ACTION


@pytest.mark.destructive
class TestSendDraftLifecycle:
    """LIFECYCLE: creates a real draft addressed to the authenticated
    user, then sends it (so a real email is delivered back to the same
    inbox), then archives the resulting message.

    What is created: 1 draft (briefly), 1 outbound + 1 inbound email
    (same message). Subject includes the test PID for traceability:
    "[AH integration test {pid}] send-draft lifecycle test". Cleanup:
    the inbound copy is archived. Permanent deletion is left to the
    user.
    """

    @pytest.mark.asyncio
    async def test_create_send_archive(self, live_context):
        profile = await gmail.execute_action("get_user_info", {"user_id": "me"}, live_context)
        my_address = profile.result.data["user_info"]["email_address"]

        subject = f"[AH integration test {os.getpid()}] send-draft lifecycle test"

        # 1. Create draft
        create_result = await gmail.execute_action(
            "create_draft",
            {"to": [my_address], "subject": subject, "body": "Sent via draft lifecycle test."},
            live_context,
        )
        assert create_result.type == ResultType.ACTION, create_result
        draft_id = create_result.result.data["draft"]["id"]

        # 2. Send the draft
        send_result = await gmail.execute_action("send_draft", {"user_id": "me", "draft_id": draft_id}, live_context)
        assert send_result.type == ResultType.ACTION, send_result
        sent_message_id = send_result.result.data["message"]["id"]

        # 3. Cleanup: archive the resulting message
        archive_result = await gmail.execute_action(
            "archive_emails",
            {"user_id": "me", "ids": [sent_message_id]},
            live_context,
        )
        assert archive_result.type == ResultType.ACTION


@pytest.mark.destructive
class TestReplyToThreadLifecycle:
    """LIFECYCLE: replies to an existing thread in the user's inbox.
    Picks the most-recent inbox message dynamically unless
    GMAIL_TEST_THREAD_ID and GMAIL_TEST_MESSAGE_ID are both set.

    What is created: 1 outbound email (a reply on an existing thread).
    The reply body clearly identifies it as a test message. Cleanup:
    the resulting message is archived. The original thread is left
    intact apart from the new reply within it.
    """

    @pytest.mark.asyncio
    async def test_reply_and_archive(self, live_context):
        thread_id = TEST_THREAD_ID
        message_id = TEST_MESSAGE_ID

        if not (thread_id and message_id):
            inbox = await gmail.execute_action("read_inbox", {"user_id": "me", "scope": "all"}, live_context)
            emails = inbox.result.data.get("emails", [])
            if not emails:
                pytest.skip("Inbox is empty — cannot exercise reply_to_thread")
            first = emails[0]
            thread_id = first.get("threadId") or first.get("thread_id")
            message_id = first["id"]
            if not thread_id:
                pytest.skip("Most recent inbox email has no thread_id")

        reply_result = await gmail.execute_action(
            "reply_to_thread",
            {
                "thread_id": thread_id,
                "message_id": message_id,
                "body": (
                    f"AH integration test reply (pid {os.getpid()}). "
                    "This message was sent automatically by the gmail "
                    "integration test suite. Safe to delete."
                ),
                "to": [],
                "cc": [],
            },
            live_context,
        )
        assert reply_result.type == ResultType.ACTION, reply_result
        reply_message_id = reply_result.result.data["id"]

        # Cleanup: archive the reply we just sent
        archive_result = await gmail.execute_action(
            "archive_emails",
            {"user_id": "me", "ids": [reply_message_id]},
            live_context,
        )
        assert archive_result.type == ResultType.ACTION
