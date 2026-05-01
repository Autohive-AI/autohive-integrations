import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(_parent)
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("heartbeat_mod", os.path.join(_parent, "heartbeat.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["heartbeat_mod"] = _mod

heartbeat = _mod.heartbeat  # the Integration instance
HeartbeatDataParser = _mod.HeartbeatDataParser

pytestmark = pytest.mark.unit

SAMPLE_CHANNEL = {
    "id": "ch-1",
    "name": "General",
    "description": "General channel",
    "private": False,
}
SAMPLE_THREAD = {
    "id": "th-1",
    "title": "Hello World",
    "channelID": "ch-1",
    "userID": "u-1",
    "content": "This is a thread",
    "createdAt": "2024-01-01T00:00:00Z",
    "url": "https://heartbeat.chat/thread/th-1",
}
SAMPLE_USER = {
    "id": "u-1",
    "email": "alice@example.com",
    "name": "Alice",
    "bio": "Engineer",
}
SAMPLE_EVENT = {
    "id": "ev-1",
    "title": "Community Meetup",
    "startTime": "2024-06-01T10:00:00Z",
    "endTime": "2024-06-01T11:00:00Z",
    "location": "Online",
}
SAMPLE_COMMENT = {
    "id": "cm-1",
    "text": "Nice thread!",
    "threadID": "th-1",
    "userID": "u-1",
    "createdAt": "2024-01-02T00:00:00Z",
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test-api-key"}}  # nosec B105
    return ctx


# ---- Parser Unit Tests ----


class TestHeartbeatDataParser:
    def test_parse_channel_minimal(self):
        result = HeartbeatDataParser.parse_channel({"id": "ch-1", "name": "Test"})
        assert result["id"] == "ch-1"
        assert result["name"] == "Test"
        assert "description" not in result

    def test_parse_channel_full(self):
        result = HeartbeatDataParser.parse_channel(SAMPLE_CHANNEL)
        assert result["id"] == "ch-1"
        assert result["description"] == "General channel"
        assert result["private"] is False

    def test_parse_thread_maps_userid_to_authorid(self):
        result = HeartbeatDataParser.parse_thread(SAMPLE_THREAD)
        assert result["authorID"] == "u-1"
        assert result["channelID"] == "ch-1"
        assert result["title"] == "Hello World"

    def test_parse_thread_with_nested_user(self):
        raw = dict(SAMPLE_THREAD)
        raw["user"] = SAMPLE_USER
        result = HeartbeatDataParser.parse_thread(raw)
        assert "user" in result
        assert result["user"]["email"] == "alice@example.com"

    def test_parse_user_minimal(self):
        result = HeartbeatDataParser.parse_user({"id": "u-1", "email": "x@x.com", "name": "X"})
        assert result["id"] == "u-1"
        assert result["email"] == "x@x.com"

    def test_parse_event_maps_fields(self):
        result = HeartbeatDataParser.parse_event(SAMPLE_EVENT)
        assert result["id"] == "ev-1"
        assert result["startTime"] == "2024-06-01T10:00:00Z"
        assert result["location"] == "Online"

    def test_parse_comment_maps_text_to_content(self):
        result = HeartbeatDataParser.parse_comment(SAMPLE_COMMENT)
        assert result["content"] == "Nice thread!"
        assert result["authorID"] == "u-1"
        assert result["threadID"] == "th-1"


# ---- get_heartbeat_channels ----


class TestGetChannels:
    @pytest.mark.asyncio
    async def test_returns_channels_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_CHANNEL])

        result = await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        assert result.result.data["channels"][0]["id"] == "ch-1"
        assert result.result.data["channels"][0]["name"] == "General"

    @pytest.mark.asyncio
    async def test_handles_object_response_with_items(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"items": [SAMPLE_CHANNEL]})

        result = await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        assert len(result.result.data["channels"]) == 1

    @pytest.mark.asyncio
    async def test_handles_object_response_with_channels_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"channels": [SAMPLE_CHANNEL]})

        result = await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        assert len(result.result.data["channels"]) == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.heartbeat.chat/v0/channels"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_auth_header_set(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers.get("Authorization") == "Bearer test-api-key"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_channels(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        result = await heartbeat.execute_action("get_heartbeat_channels", {}, mock_context)

        assert result.result.data["channels"] == []


# ---- get_heartbeat_channel ----


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_returns_channel(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        result = await heartbeat.execute_action("get_heartbeat_channel", {"channel_id": "ch-1"}, mock_context)

        assert result.result.data["channel"]["id"] == "ch-1"
        assert result.result.data["channel"]["name"] == "General"

    @pytest.mark.asyncio
    async def test_request_url_includes_channel_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CHANNEL)

        await heartbeat.execute_action("get_heartbeat_channel", {"channel_id": "ch-99"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.heartbeat.chat/v0/channels/ch-99"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await heartbeat.execute_action("get_heartbeat_channel", {"channel_id": "ch-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- get_heartbeat_channel_threads ----


class TestGetChannelThreads:
    @pytest.mark.asyncio
    async def test_returns_threads_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_THREAD])

        result = await heartbeat.execute_action("get_heartbeat_channel_threads", {"channel_id": "ch-1"}, mock_context)

        assert len(result.result.data["threads"]) == 1
        assert result.result.data["threads"][0]["id"] == "th-1"

    @pytest.mark.asyncio
    async def test_request_url_includes_channel_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await heartbeat.execute_action("get_heartbeat_channel_threads", {"channel_id": "ch-42"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.heartbeat.chat/v0/channels/ch-42/threads"

    @pytest.mark.asyncio
    async def test_handles_threads_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"threads": [SAMPLE_THREAD]})

        result = await heartbeat.execute_action("get_heartbeat_channel_threads", {"channel_id": "ch-1"}, mock_context)

        assert len(result.result.data["threads"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await heartbeat.execute_action("get_heartbeat_channel_threads", {"channel_id": "ch-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message


# ---- get_heartbeat_thread ----


class TestGetThread:
    @pytest.mark.asyncio
    async def test_returns_thread(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        result = await heartbeat.execute_action("get_heartbeat_thread", {"thread_id": "th-1"}, mock_context)

        assert result.result.data["thread"]["id"] == "th-1"
        assert result.result.data["thread"]["title"] == "Hello World"

    @pytest.mark.asyncio
    async def test_request_url_includes_thread_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        await heartbeat.execute_action("get_heartbeat_thread", {"thread_id": "th-99"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.heartbeat.chat/v0/threads/th-99"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await heartbeat.execute_action("get_heartbeat_thread", {"thread_id": "th-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_heartbeat_users ----


class TestGetUsers:
    @pytest.mark.asyncio
    async def test_returns_users_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_USER])

        result = await heartbeat.execute_action("get_heartbeat_users", {}, mock_context)

        assert len(result.result.data["users"]) == 1
        assert result.result.data["users"][0]["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await heartbeat.execute_action("get_heartbeat_users", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.heartbeat.chat/v0/users"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_handles_users_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"users": [SAMPLE_USER]})

        result = await heartbeat.execute_action("get_heartbeat_users", {}, mock_context)

        assert len(result.result.data["users"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await heartbeat.execute_action("get_heartbeat_users", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- get_heartbeat_user ----


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        result = await heartbeat.execute_action("get_heartbeat_user", {"user_id": "u-1"}, mock_context)

        assert result.result.data["user"]["id"] == "u-1"
        assert result.result.data["user"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_request_url_includes_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_USER)

        await heartbeat.execute_action("get_heartbeat_user", {"user_id": "u-42"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.heartbeat.chat/v0/users/u-42"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("User not found")

        result = await heartbeat.execute_action("get_heartbeat_user", {"user_id": "u-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "User not found" in result.result.message


# ---- get_heartbeat_events ----


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_returns_events_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_EVENT])

        result = await heartbeat.execute_action("get_heartbeat_events", {}, mock_context)

        assert len(result.result.data["events"]) == 1
        assert result.result.data["events"][0]["title"] == "Community Meetup"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await heartbeat.execute_action("get_heartbeat_events", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.heartbeat.chat/v0/events"
        assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_handles_events_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"events": [SAMPLE_EVENT]})

        result = await heartbeat.execute_action("get_heartbeat_events", {}, mock_context)

        assert len(result.result.data["events"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Fetch error")

        result = await heartbeat.execute_action("get_heartbeat_events", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_heartbeat_event ----


class TestGetEvent:
    @pytest.mark.asyncio
    async def test_returns_event(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_EVENT)

        result = await heartbeat.execute_action("get_heartbeat_event", {"event_id": "ev-1"}, mock_context)

        assert result.result.data["event"]["id"] == "ev-1"
        assert result.result.data["event"]["startTime"] == "2024-06-01T10:00:00Z"

    @pytest.mark.asyncio
    async def test_request_url_includes_event_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_EVENT)

        await heartbeat.execute_action("get_heartbeat_event", {"event_id": "ev-99"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert url == "https://api.heartbeat.chat/v0/events/ev-99"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Event not found")

        result = await heartbeat.execute_action("get_heartbeat_event", {"event_id": "ev-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Event not found" in result.result.message


# ---- create_heartbeat_comment ----


class TestCreateComment:
    @pytest.mark.asyncio
    async def test_creates_comment(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT)

        result = await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "Nice thread!"},
            mock_context,
        )

        assert result.result.data["comment"]["id"] == "cm-1"
        assert result.result.data["comment"]["content"] == "Nice thread!"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT)

        await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "Hello"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.heartbeat.chat/v0/comments"
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_request_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT)

        await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "Hello"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["threadID"] == "th-1"
        assert payload["text"] == "Hello"
        assert payload["parentCommentID"] is None

    @pytest.mark.asyncio
    async def test_with_parent_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT)

        await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "Reply", "parent_id": "cm-0"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["parentCommentID"] == "cm-0"

    @pytest.mark.asyncio
    async def test_with_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_COMMENT)

        await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "As user", "user_id": "u-99"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["userID"] == "u-99"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create failed")

        result = await heartbeat.execute_action(
            "create_heartbeat_comment",
            {"thread_id": "th-1", "content": "Hello"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Create failed" in result.result.message


# ---- create_heartbeat_thread ----


class TestCreateThread:
    @pytest.mark.asyncio
    async def test_creates_thread(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        result = await heartbeat.execute_action(
            "create_heartbeat_thread",
            {"channel_id": "ch-1", "content": "Hello World"},
            mock_context,
        )

        assert result.result.data["thread"]["id"] == "th-1"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        await heartbeat.execute_action(
            "create_heartbeat_thread",
            {"channel_id": "ch-1", "content": "Hello"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == "https://api.heartbeat.chat/v0/threads"
        assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_request_payload_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        await heartbeat.execute_action(
            "create_heartbeat_thread",
            {"channel_id": "ch-1", "content": "Hello"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["channelID"] == "ch-1"
        assert payload["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_with_user_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_THREAD)

        await heartbeat.execute_action(
            "create_heartbeat_thread",
            {"channel_id": "ch-1", "content": "As user", "user_id": "u-99"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["userID"] == "u-99"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Thread create error")

        result = await heartbeat.execute_action(
            "create_heartbeat_thread",
            {"channel_id": "ch-1", "content": "Hello"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Thread create error" in result.result.message
