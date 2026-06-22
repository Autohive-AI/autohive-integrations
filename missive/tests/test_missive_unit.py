"""
Unit tests for the Missive integration using mocked fetch.
"""

import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType

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


def make_err_ctx(status, message):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=err(status, message))
    ctx.auth = {"api_token": "test_token"}  # nosec B105
    return ctx


def ok_data(result):
    """Assert an ActionResult success and return its data dict."""
    assert result.type == ResultType.ACTION, getattr(result.result, "message", result)
    return result.result.data


def error_message(result):
    """Assert an ActionError and return its message."""
    assert result.type == ResultType.ACTION_ERROR
    return result.result.message


# =============================================================================
# CONVERSATIONS
# =============================================================================


async def test_list_conversations():
    ctx = make_ctx({"conversations": [{"id": "c1", "latest_message_subject": "Hello"}]})
    result = await missive.execute_action("list_conversations", {"mailbox": "all"}, ctx)
    data = ok_data(result)
    assert isinstance(data["conversations"], list)
    assert data["conversations"][0]["id"] == "c1"


async def test_get_conversation():
    ctx = make_ctx({"conversations": [{"id": "c1", "latest_message_subject": "Hello"}]})
    result = await missive.execute_action("get_conversation", {"conversation_id": "c1"}, ctx)
    data = ok_data(result)
    assert data["conversation"]["id"] == "c1"


async def test_update_conversation():
    ctx = make_ctx({})
    result = await missive.execute_action("update_conversation", {"conversation_id": "c1", "closed": True}, ctx)
    data = ok_data(result)
    assert data["conversation_id"] == "c1"


async def test_merge_conversations():
    ctx = make_ctx({})
    result = await missive.execute_action(
        "merge_conversations",
        {"conversation_id": "c1", "target_conversation_id": "c2"},
        ctx,
    )
    data = ok_data(result)
    assert data["conversation_id"] == "c1"


async def test_list_conversation_messages():
    ctx = make_ctx({"messages": [{"id": "m1"}]})
    result = await missive.execute_action("list_conversation_messages", {"conversation_id": "c1"}, ctx)
    data = ok_data(result)
    assert len(data["messages"]) == 1


async def test_list_conversation_comments():
    ctx = make_ctx({"comments": [{"id": "cm1"}]})
    result = await missive.execute_action("list_conversation_comments", {"conversation_id": "c1"}, ctx)
    data = ok_data(result)
    assert isinstance(data["comments"], list)


async def test_list_conversation_posts():
    ctx = make_ctx({"posts": [{"id": "p1"}]})
    result = await missive.execute_action("list_conversation_posts", {"conversation_id": "c1"}, ctx)
    data = ok_data(result)
    assert isinstance(data["posts"], list)


async def test_list_conversation_drafts():
    ctx = make_ctx({"drafts": [{"id": "d1"}]})
    result = await missive.execute_action("list_conversation_drafts", {"conversation_id": "c1"}, ctx)
    data = ok_data(result)
    assert isinstance(data["drafts"], list)


# =============================================================================
# MESSAGES
# =============================================================================


async def test_list_messages():
    ctx = make_ctx({"messages": [{"id": "m1"}]})
    result = await missive.execute_action("list_messages", {"email_message_id": "<test@example.com>"}, ctx)
    data = ok_data(result)
    assert isinstance(data["messages"], list)


async def test_get_message():
    ctx = make_ctx({"messages": [{"id": "m1", "body": "Hi"}]})
    result = await missive.execute_action("get_message", {"message_id": "m1"}, ctx)
    data = ok_data(result)
    assert data["message"]["id"] == "m1"


async def test_create_message():
    ctx = make_ctx({"messages": {"id": "m1"}})
    result = await missive.execute_action(
        "create_message",
        {
            "account": "acct1",
            "from_field": {"name": "Bot", "username": "bot"},
            "to_fields": [{"name": "User", "username": "user"}],
            "body": "Hello",
        },
        ctx,
    )
    ok_data(result)


async def test_create_draft():
    ctx = make_ctx({"drafts": {"id": "dr1"}})
    result = await missive.execute_action("create_draft", {"body": "Draft body"}, ctx)
    ok_data(result)


async def test_delete_draft():
    ctx = make_ctx({})
    result = await missive.execute_action("delete_draft", {"draft_id": "dr1"}, ctx)
    data = ok_data(result)
    assert data["draft_id"] == "dr1"


async def test_create_post():
    ctx = make_ctx({"posts": {"id": "post1", "conversation": "c1"}})
    result = await missive.execute_action(
        "create_post",
        {"text": "Hello team", "conversation_id": "c1", "notification": {"title": "t", "body": "b"}},
        ctx,
    )
    data = ok_data(result)
    assert data["post"]["id"] == "post1"
    assert data["conversation_id"] == "c1"


# =============================================================================
# CONTACTS
# =============================================================================


async def test_list_contacts():
    ctx = make_ctx({"contacts": [{"id": "ct1", "first_name": "Alice"}]})
    result = await missive.execute_action("list_contacts", {"contact_book_id": "cb1"}, ctx)
    data = ok_data(result)
    assert data["contacts"][0]["id"] == "ct1"
    assert ctx.fetch.call_args.kwargs["params"]["contact_book"] == "cb1"


async def test_get_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    result = await missive.execute_action("get_contact", {"contact_id": "ct1"}, ctx)
    data = ok_data(result)
    assert data["contact"]["id"] == "ct1"


async def test_create_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    result = await missive.execute_action(
        "create_contact",
        {"contact_book_id": "cb1", "contacts": [{"first_name": "Alice", "last_name": "Smith"}]},
        ctx,
    )
    data = ok_data(result)
    assert len(data["contacts"]) == 1


async def test_update_contact():
    ctx = make_ctx({"contacts": [{"id": "ct1", "first_name": "Bob"}]})
    result = await missive.execute_action("update_contact", {"contact_id": "ct1", "first_name": "Bob"}, ctx)
    ok_data(result)


async def test_list_contact_books():
    ctx = make_ctx({"contact_books": [{"id": "cb1", "name": "Main"}]})
    result = await missive.execute_action("list_contact_books", {}, ctx)
    data = ok_data(result)
    assert isinstance(data["contact_books"], list)


async def test_list_contact_groups():
    ctx = make_ctx({"contact_groups": [{"id": "cg1"}]})
    result = await missive.execute_action("list_contact_groups", {"contact_book_id": "cb1", "kind": "group"}, ctx)
    data = ok_data(result)
    assert isinstance(data["contact_groups"], list)
    params = ctx.fetch.call_args.kwargs["params"]
    assert params["contact_book"] == "cb1"
    assert params["kind"] == "group"


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
    data = ok_data(result)
    assert data["report_id"] == "ar1"


async def test_get_analytics_report():
    ctx = make_ctx({"reports": {"id": "ar1", "status": "completed"}})
    result = await missive.execute_action("get_analytics_report", {"report_id": "ar1"}, ctx)
    data = ok_data(result)
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
            "body": "Hello",
            "subject": "Test subject",
            "conversation_id": "conv1",
            "team_id": "team1",
            "assignee_id": "user1",
            "organization_id": "org1",
            "account": "acc1",
            "to": [{"name": "Alice", "address": "alice@example.com"}],
        },
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["drafts"]
    assert payload["body"] == "Hello"
    assert payload["subject"] == "Test subject"
    assert payload["conversation"] == "conv1"
    assert payload["team"] == "team1"
    assert payload["add_assignees"] == ["user1"]
    assert payload["organization"] == "org1"
    assert payload["account"] == "acc1"
    assert payload["to_fields"] == [{"name": "Alice", "address": "alice@example.com"}]
    assert "channel_id" not in payload
    assert "channel" not in payload
    assert "conversation_id" not in payload
    assert "team_id" not in payload
    assert "assignee_id" not in payload


@pytest.mark.asyncio
async def test_create_message_request_shape():
    ctx = make_ctx({"messages": {"id": "m1"}})
    await missive.execute_action(
        "create_message",
        {
            "account": "acct1",
            "from_field": {"id": "12345", "username": "@bot", "name": "Bot"},
            "to_fields": [{"id": "54321", "username": "@user", "name": "User"}],
            "body": "Hello",
            "conversation_id": "conv1",
        },
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["messages"]
    assert payload["account"] == "acct1"
    assert payload["from_field"] == {"id": "12345", "username": "@bot", "name": "Bot"}
    assert payload["to_fields"] == [{"id": "54321", "username": "@user", "name": "User"}]
    assert payload["body"] == "Hello"
    assert payload["conversation"] == "conv1"
    assert "channel_id" not in payload
    assert "conversation_id" not in payload


@pytest.mark.asyncio
async def test_create_post_request_shape():
    ctx = make_ctx({"posts": {"id": "p1", "conversation": "c1"}})
    await missive.execute_action(
        "create_post",
        {
            "text": "Hello team",
            "conversation_id": "c1",
            "notification": {"title": "t", "body": "b"},
            "close": True,
            "assignee_id": "user1",
            "team_id": "team1",
            "shared_label_ids": ["label1", "label2"],
            "organization_id": "org1",
        },
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    payload = kwargs["json"]["posts"]
    assert payload["conversation"] == "c1"
    assert payload["text"] == "Hello team"
    assert payload["notification"] == {"title": "t", "body": "b"}
    assert payload["close"] is True
    assert payload["add_assignees"] == ["user1"]
    assert payload["team"] == "team1"
    assert payload["add_shared_labels"] == ["label1", "label2"]
    assert payload["organization"] == "org1"
    assert "assignee_id" not in payload
    assert "team_id" not in payload
    assert "shared_label_ids" not in payload


@pytest.mark.asyncio
async def test_create_post_requires_org_for_assignment():
    ctx = make_ctx({"posts": {"id": "p1"}})
    result = await missive.execute_action(
        "create_post",
        {
            "text": "Hi",
            "conversation_id": "c1",
            "notification": {"title": "t", "body": "b"},
            "assignee_id": "u1",
        },
        ctx,
    )
    assert "organization_id" in error_message(result)
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_update_conversation_request_shape():
    ctx = make_ctx({})
    await missive.execute_action(
        "update_conversation",
        {"conversation_id": "c1", "closed": True, "assignee_id": "u1", "organization_id": "org1"},
        ctx,
    )
    _, kwargs = ctx.fetch.call_args
    conversations = kwargs["json"]["conversations"]
    assert len(conversations) == 1
    body = conversations[0]
    assert body["id"] == "c1"
    assert body["close"] is True
    assert "reopen" not in body
    assert body["add_assignees"] == ["u1"]
    assert body["organization"] == "org1"


@pytest.mark.asyncio
async def test_update_conversation_closed_false_reopens():
    ctx = make_ctx({})
    await missive.execute_action("update_conversation", {"conversation_id": "c1", "closed": False}, ctx)
    body = ctx.fetch.call_args.kwargs["json"]["conversations"][0]
    assert body["reopen"] is True
    assert "close" not in body


@pytest.mark.asyncio
async def test_update_conversation_requires_org_for_assignment():
    ctx = make_ctx({})
    result = await missive.execute_action(
        "update_conversation",
        {"conversation_id": "c1", "assignee_id": "u1"},
        ctx,
    )
    assert "organization_id" in error_message(result)
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_analytics_report_request_shape():
    ctx = make_ctx({"reports": {"id": "ar1"}})
    await missive.execute_action(
        "create_analytics_report",
        {
            "start": 1,
            "end": 2,
            "organization_id": "org1",
            "timezone": "America/New_York",
            "team_ids": ["t1"],
            "user_ids": ["u1"],
            "shared_label_ids": ["l1"],
        },
        ctx,
    )
    payload = ctx.fetch.call_args.kwargs["json"]["reports"]
    assert payload["organization"] == "org1"
    assert payload["time_zone"] == "America/New_York"
    assert payload["teams"] == ["t1"]
    assert payload["users"] == ["u1"]
    assert payload["shared_labels"] == ["l1"]
    assert "timezone" not in payload
    assert "team_ids" not in payload
    assert "user_ids" not in payload
    assert "shared_label_ids" not in payload


@pytest.mark.asyncio
async def test_create_contact_request_shape():
    ctx = make_ctx({"contacts": [{"id": "ct1"}]})
    await missive.execute_action(
        "create_contact",
        {
            "contact_book_id": "cb1",
            "contacts": [{"first_name": "Alice", "last_name": "Smith"}],
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
    ctx = make_err_ctx(401, "Unauthorized")
    result = await missive.execute_action("list_conversations", {"mailbox": "all"}, ctx)
    message = error_message(result)
    assert "401" in message or "Unauthorized" in message


@pytest.mark.asyncio
async def test_create_draft_non2xx_returns_error():
    ctx = make_err_ctx(422, "Invalid channel")
    result = await missive.execute_action("create_draft", {"body": "Hi"}, ctx)
    assert "Invalid channel" in error_message(result)


@pytest.mark.asyncio
async def test_create_contact_non2xx_returns_error():
    ctx = make_err_ctx(403, "Forbidden")
    result = await missive.execute_action(
        "create_contact",
        {"contact_book_id": "cb1", "contacts": [{"first_name": "Alice"}]},
        ctx,
    )
    assert "Forbidden" in error_message(result)


@pytest.mark.asyncio
async def test_list_contacts_non2xx_returns_error():
    ctx = make_err_ctx(400, "Required parameter missing: 'contact_book'")
    result = await missive.execute_action("list_contacts", {"contact_book_id": "bad"}, ctx)
    assert "contact_book" in error_message(result)


@pytest.mark.asyncio
async def test_update_conversation_non2xx_returns_error():
    ctx = make_err_ctx(404, "Not found")
    result = await missive.execute_action("update_conversation", {"conversation_id": "bad"}, ctx)
    assert "Not found" in error_message(result)


@pytest.mark.asyncio
async def test_merge_conversations_non2xx_returns_error():
    ctx = make_err_ctx(404, "Not found")
    result = await missive.execute_action(
        "merge_conversations",
        {"conversation_id": "c1", "target_conversation_id": "c2"},
        ctx,
    )
    assert "Not found" in error_message(result)


@pytest.mark.asyncio
async def test_delete_draft_non2xx_returns_error():
    ctx = make_err_ctx(404, "Not found")
    result = await missive.execute_action("delete_draft", {"draft_id": "bad"}, ctx)
    assert "Not found" in error_message(result)


@pytest.mark.asyncio
async def test_get_message_non2xx_returns_error():
    ctx = make_err_ctx(404, "The resource you're trying to access doesn't exist")
    result = await missive.execute_action("get_message", {"message_id": "bad"}, ctx)
    assert "404" in error_message(result)


# =============================================================================
# DIRECTORY / ID DISCOVERY
# =============================================================================


async def test_list_organizations():
    ctx = make_ctx({"organizations": [{"id": "o1", "name": "Acme"}]})
    result = await missive.execute_action("list_organizations", {}, ctx)
    data = ok_data(result)
    assert data["organizations"][0]["id"] == "o1"


async def test_list_users():
    ctx = make_ctx({"users": [{"id": "u1", "name": "Sarah", "email": "sarah@acme.com"}]})
    result = await missive.execute_action("list_users", {"organization_id": "o1"}, ctx)
    data = ok_data(result)
    assert data["users"][0]["id"] == "u1"
    assert ctx.fetch.call_args.kwargs["params"]["organization"] == "o1"


async def test_list_teams():
    ctx = make_ctx({"teams": [{"id": "t1", "name": "Support"}]})
    result = await missive.execute_action("list_teams", {}, ctx)
    data = ok_data(result)
    assert data["teams"][0]["id"] == "t1"


async def test_list_shared_labels():
    ctx = make_ctx({"shared_labels": [{"id": "l1", "name": "Escalated"}]})
    result = await missive.execute_action("list_shared_labels", {"organization_id": "o1"}, ctx)
    data = ok_data(result)
    assert data["shared_labels"][0]["id"] == "l1"
    assert ctx.fetch.call_args.kwargs["params"]["organization"] == "o1"


@pytest.mark.asyncio
async def test_list_conversations_email_filter_request_shape():
    ctx = make_ctx({"conversations": []})
    await missive.execute_action(
        "list_conversations",
        {"mailbox": "all", "email": "jane@acme.com", "organization_id": "o1"},
        ctx,
    )
    params = ctx.fetch.call_args.kwargs["params"]
    assert params["all"] == "true"
    assert params["email"] == "jane@acme.com"
    assert params["organization"] == "o1"


@pytest.mark.asyncio
async def test_list_conversations_contact_filters_mutually_exclusive():
    ctx = make_ctx({"conversations": []})
    result = await missive.execute_action(
        "list_conversations",
        {"mailbox": "all", "email": "jane@acme.com", "domain": "acme.com"},
        ctx,
    )
    message = error_message(result).lower()
    assert "mutually" in message or "only one" in message
    ctx.fetch.assert_not_called()
