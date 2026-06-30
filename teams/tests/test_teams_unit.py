import importlib
import pytest
from unittest.mock import MagicMock, patch

from . import context  # noqa: F401 — adds parent dir to sys.path
from teams import teams

# teams/__init__.py re-exports `teams` (Integration object), so `teams.teams`
# resolves to that object, not the submodule. Get the actual module for patching.
_mod = importlib.import_module("teams.teams")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

CREDS = {
    "TeamId": "team-123",
    "GroupId": "group-456",
    "TenantId": "tenant-789",
    "ServiceUrl": "https://smba.trafficmanager.net/au/",
    "SetupChannelId": "chan-setup",
}


def _ctx(creds=None, agent_name="Test Agent"):
    ctx = MagicMock()
    ctx.auth = {"credentials": creds if creds is not None else CREDS}
    ctx.metadata = {"agent_name": agent_name}
    return ctx


def _make_channel(channel_id, name):
    ch = MagicMock()
    ch.id = channel_id
    ch.name = name
    return ch


def _channels_result(*channels):
    result = MagicMock()
    result.conversations = list(channels)
    return result


# ---------------------------------------------------------------------------
# list_channels
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_channels_returns_all_channels():
    channels_result = _channels_result(
        _make_channel("ch-1", "general"),
        _make_channel("ch-2", "announcements"),
    )
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("list_channels", {}, _ctx())

    assert result.result.data["channels"] == [
        {"id": "ch-1", "name": "general"},
        {"id": "ch-2", "name": "announcements"},
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_channels_uses_general_for_null_name():
    channels_result = _channels_result(_make_channel("ch-1", None))
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("list_channels", {}, _ctx())

    assert result.result.data["channels"][0]["name"] == "general"


# ---------------------------------------------------------------------------
# search_channels
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_channels_filters_by_query():
    channels_result = _channels_result(
        _make_channel("ch-1", "general"),
        _make_channel("ch-2", "announcements"),
        _make_channel("ch-3", "general-archive"),
    )
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("search_channels", {"query": "general"}, _ctx())

    names = [c["name"] for c in result.result.data["channels"]]
    assert "general" in names
    assert "general-archive" in names
    assert "announcements" not in names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_channels_case_insensitive():
    channels_result = _channels_result(_make_channel("ch-1", "General"))
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("search_channels", {"query": "general"}, _ctx())

    assert len(result.result.data["channels"]) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_channels_missing_credentials_raises():
    ctx = _ctx(creds={})
    with pytest.raises(ValueError, match="TeamId and ServiceUrl"):
        await teams.execute_action("search_channels", {"query": "x"}, ctx)


# ---------------------------------------------------------------------------
# get_channel_by_name
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_by_name_found():
    channels_result = _channels_result(
        _make_channel("ch-1", "general"),
        _make_channel("ch-2", "dev"),
    )
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("get_channel_by_name", {"channel_name": "dev"}, _ctx())

    assert result.result.data["found"] is True
    assert result.result.data["channel"]["id"] == "ch-2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_by_name_not_found():
    channels_result = _channels_result(_make_channel("ch-1", "general"))
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("get_channel_by_name", {"channel_name": "missing"}, _ctx())

    assert result.result.data["found"] is False
    assert result.result.data["channel"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_by_name_case_insensitive():
    channels_result = _channels_result(_make_channel("ch-1", "General"))
    mock_client = MagicMock()
    mock_client.teams.get_teams_channels.return_value = channels_result

    with patch.object(_mod, "create_teams_connector_client", return_value=mock_client):
        result = await teams.execute_action("get_channel_by_name", {"channel_name": "general"}, _ctx())

    assert result.result.data["found"] is True


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_message_success():
    mock_client = MagicMock()
    mock_client.conversations.send_to_conversation.return_value = None

    with patch.object(_mod, "create_connector_client", return_value=mock_client):
        result = await teams.execute_action(
            "send_message",
            {"channel_id": "ch-1", "message": "Hello"},
            _ctx(agent_name="My Agent"),
        )

    assert result.result.data["success"] is True
    call_args = mock_client.conversations.send_to_conversation.call_args
    activity = call_args[0][1]
    assert "My Agent" in activity.text
    assert "Hello" in activity.text


# ---------------------------------------------------------------------------
# get_channel_messages
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_messages_returns_messages():
    api_response = {
        "value": [
            {
                "id": "msg-1",
                "createdDateTime": "2026-05-06T00:00:00Z",
                "from": {"user": {"displayName": "Alice"}},
                "body": {"content": "Hello world"},
                "replyToId": None,
            }
        ]
    }
    with patch.object(_mod, "graph_get", return_value=api_response):
        result = await teams.execute_action("get_channel_messages", {"channel_id": "ch-1"}, _ctx())

    assert len(result.result.data["messages"]) == 1
    msg = result.result.data["messages"][0]
    assert msg["id"] == "msg-1"
    assert msg["from"] == "Alice"
    assert msg["text"] == "Hello world"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_messages_missing_credentials_raises():
    ctx = _ctx(creds={})
    with pytest.raises(ValueError, match="GroupId and TenantId"):
        await teams.execute_action("get_channel_messages", {"channel_id": "ch-1"}, ctx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_messages_respects_limit():
    with patch.object(_mod, "graph_get", return_value={"value": []}) as mock_get:
        await teams.execute_action("get_channel_messages", {"channel_id": "ch-1", "limit": 10}, _ctx())

    _, kwargs = mock_get.call_args
    assert kwargs.get("params", {}).get("$top") == 10


# ---------------------------------------------------------------------------
# get_message_replies
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_message_replies_returns_replies():
    api_response = {
        "value": [
            {
                "id": "reply-1",
                "createdDateTime": "2026-05-06T01:00:00Z",
                "from": {"user": {"displayName": "Bob"}},
                "body": {"content": "Got it"},
            }
        ]
    }
    with patch.object(_mod, "graph_get", return_value=api_response):
        result = await teams.execute_action(
            "get_message_replies",
            {"channel_id": "ch-1", "message_id": "msg-1"},
            _ctx(),
        )

    assert result.result.data["count"] == 1
    assert result.result.data["replies"][0]["from"] == "Bob"
    assert result.result.data["replies"][0]["text"] == "Got it"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_message_replies_missing_credentials_raises():
    ctx = _ctx(creds={})
    with pytest.raises(ValueError, match="GroupId and TenantId"):
        await teams.execute_action("get_message_replies", {"channel_id": "ch-1", "message_id": "msg-1"}, ctx)


# ---------------------------------------------------------------------------
# reply_to_message
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reply_to_message_success():
    mock_client = MagicMock()
    mock_client.conversations.send_to_conversation.return_value = None

    with patch.object(_mod, "create_connector_client", return_value=mock_client):
        result = await teams.execute_action(
            "reply_to_message",
            {"channel_id": "ch-1", "message_id": "msg-1", "reply": "Thanks!"},
            _ctx(agent_name="Bot"),
        )

    assert result.result.data["success"] is True
    call_args = mock_client.conversations.send_to_conversation.call_args
    conv_id, activity = call_args[0]
    assert conv_id == "ch-1;messageid=msg-1"
    assert "Bot" in activity.text
    assert "Thanks!" in activity.text


# ---------------------------------------------------------------------------
# Additional credential validation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_by_name_missing_credentials_raises():
    ctx = _ctx(creds={})
    with pytest.raises(ValueError, match="TeamId and ServiceUrl"):
        await teams.execute_action("get_channel_by_name", {"channel_name": "general"}, ctx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_message_appends_agent_attribution():
    mock_client = MagicMock()
    mock_client.conversations.send_to_conversation.return_value = None

    with patch.object(_mod, "create_connector_client", return_value=mock_client):
        await teams.execute_action("send_message", {"channel_id": "ch-1", "message": "Hi"}, _ctx(agent_name="Ops Bot"))

    activity = mock_client.conversations.send_to_conversation.call_args[0][1]
    assert "Ops Bot" in activity.text
    assert "Hi" in activity.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_channel_messages_empty_response():
    with patch.object(_mod, "graph_get", return_value={"value": []}):
        result = await teams.execute_action("get_channel_messages", {"channel_id": "ch-1"}, _ctx())

    assert result.result.data["messages"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_message_replies_credentials_validated_by_handler():
    ctx = _ctx(creds={})
    with pytest.raises(ValueError, match="GroupId and TenantId"):
        await teams.execute_action("get_message_replies", {"channel_id": "ch-1", "message_id": "msg-1"}, ctx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reply_to_message_appends_agent_attribution():
    mock_client = MagicMock()
    mock_client.conversations.send_to_conversation.return_value = None

    with patch.object(_mod, "create_connector_client", return_value=mock_client):
        await teams.execute_action(
            "reply_to_message",
            {"channel_id": "ch-1", "message_id": "msg-1", "reply": "Done"},
            _ctx(agent_name="Deploy Bot"),
        )

    _conv_id, activity = mock_client.conversations.send_to_conversation.call_args[0]
    assert "Deploy Bot" in activity.text
    assert "Done" in activity.text
