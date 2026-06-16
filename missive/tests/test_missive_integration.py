"""
Integration tests for the Missive integration.

Run read-only tests (safe):
    pytest missive/tests/test_missive_integration.py -m "integration and not destructive" -v

Run destructive tests (mutates the connected Missive account - use a test account):
    pytest missive/tests/test_missive_integration.py -m "integration and destructive" -v

Requires MISSIVE_API_TOKEN env var (see .env.example).
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk.integration import FetchResponse, ResultType

from missive.missive import missive

pytestmark = pytest.mark.integration

API_TOKEN = os.environ.get("MISSIVE_API_TOKEN", "")
ORG_ID = os.environ.get("MISSIVE_ORG_ID", "")
TEST_EMAIL = os.environ.get("MISSIVE_TEST_EMAIL", "test@example.com")


@pytest.fixture
def live_context():
    if not API_TOKEN:
        pytest.skip("MISSIVE_API_TOKEN not set - skipping integration tests")

    import aiohttp

    async def real_fetch(url, method="GET", headers=None, params=None, json=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"api_token": API_TOKEN}
    return ctx


# ─────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────


class TestConversations:
    async def test_list_conversations_inbox(self, live_context):
        result = await missive.execute_action("list_conversations", {"mailbox": "inbox"}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["conversations"], list)
        print(f"[OK] list_conversations inbox: {len(data['conversations'])} conversations")

    async def test_list_conversations_all(self, live_context):
        result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 5}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["conversations"], list)
        print(f"[OK] list_conversations all: {len(data['conversations'])} conversations")

    async def test_get_conversation(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available to test get_conversation")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action("get_conversation", {"conversation_id": conv_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["conversation"]["id"] == conv_id
        print(f"[OK] get_conversation: {conv_id}")

    async def test_list_conversation_messages(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action("list_conversation_messages", {"conversation_id": conv_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["messages"], list)
        print(f"[OK] list_conversation_messages: {len(data['messages'])} messages")

    async def test_list_conversation_comments(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action("list_conversation_comments", {"conversation_id": conv_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["comments"], list)
        print(f"[OK] list_conversation_comments: {len(data['comments'])} comments")

    async def test_list_conversation_posts(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action("list_conversation_posts", {"conversation_id": conv_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["posts"], list)
        print(f"[OK] list_conversation_posts: {len(data['posts'])} posts")

    async def test_list_conversation_drafts(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action("list_conversation_drafts", {"conversation_id": conv_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["drafts"], list)
        print(f"[OK] list_conversation_drafts: {len(data['drafts'])} drafts")

    @pytest.mark.destructive
    async def test_update_conversation(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available")

        conv_id = conversations[0]["id"]
        result = await missive.execute_action(
            "update_conversation", {"conversation_id": conv_id, "closed": False}, live_context
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True, f"update_conversation failed: {data.get('error')}"
        print(f"[OK] update_conversation: {conv_id}")


# ─────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────


class TestMessages:
    async def test_list_messages(self, live_context):
        conv_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 10}, live_context)
        email_message_id = None
        for conv in conv_result.result.data.get("conversations", []):
            msg_result = await missive.execute_action(
                "list_conversation_messages", {"conversation_id": conv["id"]}, live_context
            )
            for msg in msg_result.result.data.get("messages", []):
                if msg.get("email_message_id"):
                    email_message_id = msg["email_message_id"]
                    break
            if email_message_id:
                break
        if not email_message_id:
            pytest.skip("No email_message_id found in recent messages")
        result = await missive.execute_action("list_messages", {"email_message_id": email_message_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["messages"], list)
        print(f"[OK] list_messages: {len(data['messages'])} messages")

    async def test_get_message(self, live_context):
        conv_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 25}, live_context)
        conversations = conv_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available to find a message")

        messages = []
        for conv in conversations:
            if not conv.get("messages_count", 0):
                continue
            msg_list = await missive.execute_action(
                "list_conversation_messages", {"conversation_id": conv["id"]}, live_context
            )
            if msg_list.type == ResultType.ACTION:
                messages = msg_list.result.data["messages"]
                if messages:
                    break
        if not messages:
            pytest.skip("No messages found in any conversation")

        msg_id = messages[0]["id"]
        result = await missive.execute_action("get_message", {"message_id": msg_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["message"]["id"] == msg_id
        print(f"[OK] get_message: {msg_id}")


# ─────────────────────────────────────────────
# Drafts (destructive)
# ─────────────────────────────────────────────


class TestDrafts:
    @pytest.mark.destructive
    async def test_create_and_delete_draft(self, live_context):
        result = await missive.execute_action(
            "create_draft",
            {
                "channel_id": "email",
                "body": "Integration test draft - safe to delete",
                "to": [{"name": "Shubhank", "address": TEST_EMAIL}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        draft = data["draft"]
        print(f"[OK] create_draft: {draft}")

        if isinstance(draft, dict) and draft.get("id"):
            delete_result = await missive.execute_action("delete_draft", {"draft_id": draft["id"]}, live_context)
            assert delete_result.type == ResultType.ACTION
            assert delete_result.result.data["result"] is True
            print(f"[OK] delete_draft: {draft['id']}")


# ─────────────────────────────────────────────
# Posts (destructive)
# ─────────────────────────────────────────────


class TestPosts:
    @pytest.mark.destructive
    async def test_create_post(self, live_context):
        list_result = await missive.execute_action("list_conversations", {"mailbox": "all", "limit": 2}, live_context)
        conversations = list_result.result.data["conversations"]
        if not conversations:
            pytest.skip("No conversations available for create_post test")

        conv_id = conversations[0]["id"]
        post_id = None
        try:
            result = await missive.execute_action(
                "create_post",
                {"text": "Integration test post - autohive", "conversation_id": conv_id},
                live_context,
            )
            assert result.type == ResultType.ACTION
            data = result.result.data
            assert data["result"] is True
            post = data.get("post") or {}
            post_id = post.get("id") if isinstance(post, dict) else None
            print(f"[OK] create_post in {conv_id}: post={post_id}")
        finally:
            if post_id:
                await live_context.fetch(
                    f"https://public.missiveapp.com/v1/posts/{post_id}",
                    method="DELETE",
                    headers={
                        "Authorization": f"Bearer {live_context.auth.get('api_token', '')}",
                        "Content-Type": "application/json",
                    },
                )


# ─────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────


class TestContacts:
    async def test_list_contacts(self, live_context):
        books_result = await missive.execute_action("list_contact_books", {}, live_context)
        books = books_result.result.data["contact_books"]
        if not books:
            pytest.skip("No contact books available")

        book_id = books[0]["id"]
        result = await missive.execute_action("list_contacts", {"contact_book_id": book_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["contacts"], list)
        print(f"[OK] list_contacts in {book_id}: {len(data['contacts'])} contacts")

    async def test_list_contact_books(self, live_context):
        result = await missive.execute_action("list_contact_books", {}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["contact_books"], list)
        print(f"[OK] list_contact_books: {len(data['contact_books'])} books")

    async def test_list_contact_groups(self, live_context):
        books_result = await missive.execute_action("list_contact_books", {}, live_context)
        books = books_result.result.data["contact_books"]
        if not books:
            pytest.skip("No contact books available")

        book_id = books[0]["id"]
        result = await missive.execute_action("list_contact_groups", {"contact_book_id": book_id}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["contact_groups"], list)
        print(f"[OK] list_contact_groups in {book_id}: {len(data['contact_groups'])} groups")

    @pytest.mark.destructive
    async def test_create_get_update_contact(self, live_context):
        ts = int(time.time())
        books_result = await missive.execute_action("list_contact_books", {}, live_context)
        books = books_result.result.data["contact_books"]
        if not books:
            pytest.skip("No contact books available")
        book_id = books[0]["id"]

        create_result = await missive.execute_action(
            "create_contact",
            {
                "contact_book_id": book_id,
                "contacts": [{"first_name": "AutohiveTest", "last_name": f"Integration{ts}", "kind": "person"}],
            },
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        contacts = create_result.result.data["contacts"]
        assert len(contacts) >= 1
        contact_id = contacts[0]["id"]
        print(f"[OK] create_contact: {contact_id}")

        try:
            get_result = await missive.execute_action("get_contact", {"contact_id": contact_id}, live_context)
            assert get_result.type == ResultType.ACTION
            assert get_result.result.data["contact"]["id"] == contact_id
            print(f"[OK] get_contact: {contact_id}")

            update_result = await missive.execute_action(
                "update_contact",
                {"contact_id": contact_id, "first_name": "AutohiveUpdated"},
                live_context,
            )
            assert update_result.type == ResultType.ACTION
            udata = update_result.result.data
            assert udata["result"] is True, f"update_contact failed: {udata.get('error')}"
            print(f"[OK] update_contact: {contact_id}")
        finally:
            await live_context.fetch(
                f"https://public.missiveapp.com/v1/contacts/{contact_id}",
                method="DELETE",
                headers={
                    "Authorization": f"Bearer {live_context.auth.get('api_token', '')}",
                    "Content-Type": "application/json",
                },
            )


# ─────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────


class TestAnalytics:
    @pytest.mark.destructive
    async def test_create_and_get_analytics_report(self, live_context):
        if not ORG_ID:
            pytest.skip("MISSIVE_ORG_ID not set - skipping analytics test")
        end = int(time.time())
        start = end - 7 * 24 * 3600
        org_id = ORG_ID

        create_result = await missive.execute_action(
            "create_analytics_report",
            {"start": start, "end": end, "organization_id": org_id},
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        data = create_result.result.data
        assert data["result"] is True
        report_id = data["report_id"]
        assert report_id is not None
        print(f"[OK] create_analytics_report: {report_id}")

        get_result = await missive.execute_action("get_analytics_report", {"report_id": report_id}, live_context)
        assert get_result.type == ResultType.ACTION
        report_data = get_result.result.data
        assert report_data["result"] is True
        print(f"[OK] get_analytics_report: {report_data['report']}")
