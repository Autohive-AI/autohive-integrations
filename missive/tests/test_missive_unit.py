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
    result = await missive.execute_action("list_messages", {}, ctx)
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
    result = await missive.execute_action("list_contacts", {}, ctx)
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
        {"contact_book_id": "cb1", "contacts": [{"first_name": "Alice", "last_name": "Smith"}]},
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
