"""
Live integration tests for the Front integration.

Requires FRONT_ACCESS_TOKEN set in the environment or project .env.

Safe read-only run:
    pytest front/tests/test_front_integration.py -m "integration and not destructive"

Including destructive (send messages):
    pytest front/tests/test_front_integration.py -m "integration"
"""

import json as _json
from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from front.front import front

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("FRONT_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("FRONT_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params, **kwargs) as resp:
                text = await resp.text()
                data = _json.loads(text) if text.strip() else {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    return ctx


# ---------------------------------------------------------------------------
# Helpers — fetch live IDs to drive chained tests
# ---------------------------------------------------------------------------


async def _get_first_inbox_id(live_context):
    result = await front.execute_action("list_inboxes", {"limit": 1}, live_context)
    inboxes = result.result.data.get("inboxes", [])
    return inboxes[0]["id"] if inboxes else None


async def _get_first_conversation_id(inbox_id, live_context):
    result = await front.execute_action("list_inbox_conversations", {"inbox_id": inbox_id, "limit": 1}, live_context)
    if result.type != ResultType.ACTION:
        return None
    convs = result.result.data.get("conversations", [])
    return convs[0]["id"] if convs else None


async def _get_first_message_id(conversation_id, live_context):
    result = await front.execute_action(
        "list_conversation_messages", {"conversation_id": conversation_id, "limit": 1}, live_context
    )
    msgs = result.result.data.get("messages", [])
    return msgs[0]["id"] if msgs else None


async def _get_first_channel_id(live_context):
    result = await front.execute_action("list_channels", {"limit": 1}, live_context)
    channels = result.result.data.get("channels", [])
    return channels[0]["id"] if channels else None


async def _get_first_teammate_id(live_context):
    result = await front.execute_action("list_teammates", {"limit": 1}, live_context)
    teammates = result.result.data.get("teammates", [])
    return teammates[0]["id"] if teammates else None


async def _get_first_template_id(live_context):
    result = await front.execute_action("list_message_templates", {"limit": 1}, live_context)
    templates = result.result.data.get("templates", [])
    return templates[0]["id"] if templates else None


# ---------------------------------------------------------------------------
# Inboxes
# ---------------------------------------------------------------------------


async def test_list_inboxes(live_context):
    result = await front.execute_action("list_inboxes", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "inboxes" in result.result.data
    assert isinstance(result.result.data["inboxes"], list)


async def test_get_inbox(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    result = await front.execute_action("get_inbox", {"inbox_id": inbox_id}, live_context)
    assert result.type == ResultType.ACTION
    inbox = result.result.data["inbox"]
    assert "id" in inbox
    assert "name" in inbox


async def test_find_inbox(live_context):
    result = await front.execute_action("find_inbox", {"inbox_name": ""}, live_context)
    assert result.type == ResultType.ACTION
    assert "inboxes" in result.result.data
    assert "count" in result.result.data


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


async def test_list_inbox_conversations(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    result = await front.execute_action("list_inbox_conversations", {"inbox_id": inbox_id, "limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "conversations" in result.result.data
    assert isinstance(result.result.data["conversations"], list)


async def test_get_conversation(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    conversation_id = await _get_first_conversation_id(inbox_id, live_context)
    if not conversation_id:
        pytest.skip("No conversations in account")
    result = await front.execute_action("get_conversation", {"conversation_id": conversation_id}, live_context)
    assert result.type == ResultType.ACTION
    conv = result.result.data["conversation"]
    assert "id" in conv
    assert "subject" in conv
    assert "status" in conv


async def test_find_conversation(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    result = await front.execute_action("find_conversation", {"inbox_id": inbox_id, "search_query": ""}, live_context)
    assert result.type == ResultType.ACTION
    assert "conversations" in result.result.data
    assert "count" in result.result.data


@pytest.mark.destructive
async def test_update_conversation(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    conversation_id = await _get_first_conversation_id(inbox_id, live_context)
    if not conversation_id:
        pytest.skip("No conversations in account")
    # Just toggle status to its current value (safe no-op effectively)
    result = await front.execute_action(
        "update_conversation", {"conversation_id": conversation_id, "status": "open"}, live_context
    )
    assert result.type == ResultType.ACTION


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


async def test_list_conversation_messages(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    conversation_id = await _get_first_conversation_id(inbox_id, live_context)
    if not conversation_id:
        pytest.skip("No conversations in account")
    result = await front.execute_action(
        "list_conversation_messages", {"conversation_id": conversation_id, "limit": 5}, live_context
    )
    assert result.type == ResultType.ACTION
    assert "messages" in result.result.data
    assert isinstance(result.result.data["messages"], list)


async def test_get_message(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    conversation_id = await _get_first_conversation_id(inbox_id, live_context)
    if not conversation_id:
        pytest.skip("No conversations in account")
    message_id = await _get_first_message_id(conversation_id, live_context)
    if not message_id:
        pytest.skip("No messages in account")
    result = await front.execute_action("get_message", {"message_id": message_id}, live_context)
    assert result.type == ResultType.ACTION
    msg = result.result.data["message"]
    assert "id" in msg
    assert "type" in msg


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


async def test_list_channels(live_context):
    result = await front.execute_action("list_channels", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "channels" in result.result.data
    assert isinstance(result.result.data["channels"], list)


async def test_get_channel(live_context):
    channel_id = await _get_first_channel_id(live_context)
    if not channel_id:
        pytest.skip("No channels in account")
    result = await front.execute_action("get_channel", {"channel_id": channel_id}, live_context)
    assert result.type == ResultType.ACTION
    channel = result.result.data["channel"]
    assert "id" in channel
    assert "name" in channel


async def test_list_inbox_channels(live_context):
    inbox_id = await _get_first_inbox_id(live_context)
    if not inbox_id:
        pytest.skip("No inboxes in account")
    result = await front.execute_action("list_inbox_channels", {"inbox_id": inbox_id, "limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "channels" in result.result.data
    assert isinstance(result.result.data["channels"], list)


# ---------------------------------------------------------------------------
# Teammates
# ---------------------------------------------------------------------------


async def test_list_teammates(live_context):
    result = await front.execute_action("list_teammates", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "teammates" in result.result.data
    assert isinstance(result.result.data["teammates"], list)


async def test_get_teammate(live_context):
    teammate_id = await _get_first_teammate_id(live_context)
    if not teammate_id:
        pytest.skip("No teammates in account")
    result = await front.execute_action("get_teammate", {"teammate_id": teammate_id}, live_context)
    assert result.type == ResultType.ACTION
    teammate = result.result.data["teammate"]
    assert "id" in teammate
    assert "email" in teammate


async def test_find_teammate(live_context):
    result = await front.execute_action("find_teammate", {"search_query": ""}, live_context)
    assert result.type == ResultType.ACTION
    assert "teammates" in result.result.data
    assert "count" in result.result.data


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------


async def test_list_message_templates(live_context):
    result = await front.execute_action("list_message_templates", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert "templates" in result.result.data
    assert isinstance(result.result.data["templates"], list)


async def test_get_message_template(live_context):
    template_id = await _get_first_template_id(live_context)
    if not template_id:
        pytest.skip("No message templates in account")
    result = await front.execute_action("get_message_template", {"message_template_id": template_id}, live_context)
    assert result.type == ResultType.ACTION
    template = result.result.data["template"]
    assert "id" in template
    assert "name" in template
