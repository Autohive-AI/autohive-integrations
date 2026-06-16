"""
Unit tests for the Missive integration using mocked fetch.
"""

import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

from missive.missive import missive  # noqa: E402

pytestmark = pytest.mark.unit


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def err(status=401, message="Unauthorized"):
    return FetchResponse(status=status, headers={}, data={"error": {"message": message}})


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    return ctx


# =============================================================================
# CONVERSATIONS
# =============================================================================


async def test_list_conversations():
    ctx = make_ctx({"conversations": [{"id": "c1", "latest_message_subject": "Hello"}]})
    result = await missive.execute_action("list_conversations", {"mailbox": "all"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["conversations"], list)
    assert data["conversations"][0]["id"] == "c1"


async def test_get_conversation():
    ctx = make_ctx({"conversations": [{"id": "c1", "latest_message_subject": "Hello"}]})
    result = await missive.execute_action("get_conversation", {"conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["conversation"]["id"] == "c1"


async def test_update_conversation():
    ctx = make_ctx({})
    result = await missive.execute_action("update_conversation", {"conversation_id": "c1", "closed": True}, ctx)
    data = result.result.data
    assert data["result"] is True


async def test_merge_conversations():
    ctx = make_ctx({})
    result = await missive.execute_action(
        "merge_conversations",
        {"conversation_id": "c1", "target_conversation_id": "c2"},
        ctx,
    )
    data = result.result.data
    assert data["result"] is True


async def test_list_conversation_messages():
    ctx = make_ctx({"messages": [{"id": "m1"}]})
    result = await missive.execute_action("list_conversation_messages", {"conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert len(data["messages"]) == 1


async def test_list_conversation_comments():
    ctx = make_ctx({"comments": [{"id": "cm1"}]})
    result = await missive.execute_action("list_conversation_comments", {"conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["comments"], list)


async def test_list_conversation_posts():
    ctx = make_ctx({"posts": [{"id": "p1"}]})
    result = await missive.execute_action("list_conversation_posts", {"conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["posts"], list)


async def test_list_conversation_drafts():
    ctx = make_ctx({"drafts": [{"id": "d1"}]})
    result = await missive.execute_action("list_conversation_drafts", {"conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["drafts"], list)


# =============================================================================
# MESSAGES
# =============================================================================


async def test_list_messages():
    ctx = make_ctx({"messages": [{"id": "m1"}]})
    result = await missive.execute_action("list_messages", {"email_message_id": "<test@example.com>"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["messages"], list)


async def test_get_message():
    ctx = make_ctx({"messages": [{"id": "m1", "body": "Hi"}]})
    result = await missive.execute_action("get_message", {"message_id": "m1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["message"]["id"] == "m1"


async def test_create_message():
    ctx = make_ctx({"messages": {"id": "m1"}})
    result = await missive.execute_action(
        "create_message",
        {
            "channel_id": "ch1",
            "account": "acct1",
            "from_field": {"name": "Bot", "username": "bot"},
            "to_fields": [{"name": "User", "username": "user"}],
            "body": "Hello",
        },
        ctx,
    )
    data = result.result.data
    assert data["result"] is True


async def test_create_draft():
    ctx = make_ctx({"drafts": {"id": "dr1"}})
    result = await missive.execute_action("create_draft", {"channel_id": "ch1", "body": "Draft body"}, ctx)
    data = result.result.data
    assert data["result"] is True


async def test_delete_draft():
    ctx = make_ctx({})
    result = await missive.execute_action("delete_draft", {"draft_id": "dr1"}, ctx)
    data = result.result.data
    assert data["result"] is True


async def test_create_post():
    ctx = make_ctx({"posts": {"id": "post1"}, "conversations": {"id": "c1"}})
    result = await missive.execute_action("create_post", {"text": "Hello team", "conversation_id": "c1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert "post" in data
    assert "conversation" in data


# =============================================================================
# CONTACTS
# =============================================================================


async def test_list_contacts():
    ctx = make_ctx({"contacts": [{"id": "ct1", "first_name": "Alice"}]})
    result = await missive.execute_action("list_contacts", {"contact_book_id": "cb1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["contacts"][0]["id"] == "ct1"


async def test_get_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    result = await missive.execute_action("get_contact", {"contact_id": "ct1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["contact"]["id"] == "ct1"


async def test_create_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    result = await missive.execute_action(
        "create_contact",
        {"contact_book_id": "cb1", "contacts": [{"first_name": "Alice", "last_name": "Smith", "kind": "person"}]},
        ctx,
    )
    data = result.result.data
    assert data["result"] is True
    assert len(data["contacts"]) == 1


async def test_update_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1", "first_name": "Bob"}]})
    result = await missive.execute_action("update_contact", {"contact_id": "ct1", "first_name": "Bob"}, ctx)
    data = result.result.data
    assert data["result"] is True


async def test_list_contact_books():
    ctx = make_ctx({"contact_books": [{"id": "cb1", "name": "Main"}]})
    result = await missive.execute_action("list_contact_books", {}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["contact_books"], list)


async def test_list_contact_groups():
    ctx = make_ctx({"contact_groups": [{"id": "cg1"}]})
    result = await missive.execute_action("list_contact_groups", {"contact_book_id": "cb1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert isinstance(data["contact_groups"], list)


# =============================================================================
# ANALYTICS
# =============================================================================


async def test_create_analytics_report():
    ctx = make_ctx({"reports": {"id": "ar1"}})
    result = await missive.execute_action(
        "create_analytics_report",
        {"start": 1700000000, "end": 1700086400, "organization_id": "org1"},
        ctx,
    )
    data = result.result.data
    assert data["result"] is True
    assert data["report_id"] == "ar1"


async def test_get_analytics_report():
    ctx = make_ctx({"reports": {"id": "ar1", "status": "completed"}})
    result = await missive.execute_action("get_analytics_report", {"report_id": "ar1"}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["report"]["id"] == "ar1"


# =============================================================================
# REQUEST-SHAPE TESTS (write actions)
# =============================================================================


@pytest.mark.asyncio
async def test_create_draft_request_shape():
    ctx = make_ctx({"drafts": {"id": "dr1"}})
    await missive.execute_action(
        "create_draft",
        {
            "channel_id": "ch1",
            "body": "Hello",
            "subject": "Test subject",
            "conversation_id": "conv1",
            "team_id": "team1",
            "assignee_id": "user1",
            "to": [{"name": "Alice", "address": "alice@example.com"}],
        },
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["drafts"]
    assert payload["channel"] == {"id": "ch1"}
    assert payload["body"] == "Hello"
    assert payload["subject"] == "Test subject"
    assert payload["conversation"] == {"id": "conv1"}
    assert payload["team"] == {"id": "team1"}
    assert payload["add_assignees"] == [{"id": "user1"}]
    assert payload["to_fields"] == [{"name": "Alice", "address": "alice@example.com"}]
    assert "channel_id" not in payload
    assert "conversation_id" not in payload
    assert "team_id" not in payload
    assert "assignee_id" not in payload


@pytest.mark.asyncio
async def test_create_post_request_shape():
    ctx = make_ctx({"posts": {"id": "p1"}, "conversations": {"id": "c1"}})
    await missive.execute_action(
        "create_post",
        {"text": "Hello team", "conversation_id": "c1", "close": True},
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["posts"]
    assert payload["conversation"] == "c1"
    assert payload["text"] == "Hello team"
    assert payload["close"] is True


@pytest.mark.asyncio
async def test_update_conversation_request_shape():
    ctx = make_ctx({})
    await missive.execute_action(
        "update_conversation",
        {"conversation_id": "c1", "closed": True, "assignee_id": "u1"},
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    conversations = kwargs["json"]["conversations"]
    assert len(conversations) == 1
    body = conversations[0]
    assert body["id"] == "c1"
    assert body["close"] is True
    assert body["add_assignees"] == ["u1"]


@pytest.mark.asyncio
async def test_create_contact_request_shape():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    await missive.execute_action(
        "create_contact",
        {
            "contact_book_id": "cb1",
            "contacts": [{"first_name": "Alice", "last_name": "Smith", "kind": "person"}],
        },
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["contacts"]
    assert payload[0]["contact_book"] == "cb1"
    assert payload[0]["first_name"] == "Alice"


# =============================================================================
# ERROR-PATH TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_conversations_non2xx_returns_error():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=err(401, "Unauthorized"))
    ctx.auth = {"api_token": "bad_token"}  # nosec B105
    result = await missive.execute_action("list_conversations", {"mailbox": "all"}, ctx)
    assert result.result.data["result"] is False
    assert "401" in result.result.data["error"] or "Unauthorized" in result.result.data["error"]


@pytest.mark.asyncio
async def test_create_draft_non2xx_returns_error():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=err(422, "Invalid channel"))
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    result = await missive.execute_action("create_draft", {"channel_id": "bad", "body": "Hi"}, ctx)
    assert result.result.data["result"] is False
    assert "Invalid channel" in result.result.data["error"]


@pytest.mark.asyncio
async def test_create_contact_non2xx_returns_error():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=err(403, "Forbidden"))
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    result = await missive.execute_action(
        "create_contact",
        {"contact_book_id": "cb1", "contacts": [{"first_name": "Alice", "kind": "person"}]},
        ctx,
    )
    assert result.result.data["result"] is False
    assert "Forbidden" in result.result.data["error"]


@pytest.mark.asyncio
async def test_update_conversation_non2xx_returns_error():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=err(404, "Not found"))
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    result = await missive.execute_action("update_conversation", {"conversation_id": "bad"}, ctx)
    assert result.result.data["result"] is False
    assert "Not found" in result.result.data["error"]
