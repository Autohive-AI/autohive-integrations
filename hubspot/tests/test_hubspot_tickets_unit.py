import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- get_recent_tickets ----


class TestGetRecentTickets:
    @pytest.mark.asyncio
    async def test_happy_path_defaults(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": [{"id": "t-1", "properties": {"subject": "Issue A"}}]},
        )

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        data = result.result.data
        assert "tickets" in data
        assert data["tickets"]["results"][0]["id"] == "t-1"

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/tickets/search"
        assert call_kwargs.kwargs["method"] == "POST"
        body = call_kwargs.kwargs["json"]
        assert body["limit"] == 20
        assert body["sorts"] == [{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}]
        assert "filterGroups" not in body

    @pytest.mark.asyncio
    async def test_with_status_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": []},
        )

        await hubspot.execute_action(
            "get_recent_tickets",
            {"status": "1"},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "filterGroups" in body
        filters = body["filterGroups"][0]["filters"]
        assert filters[0]["propertyName"] == "hs_pipeline_stage"
        assert filters[0]["operator"] == "EQ"
        assert filters[0]["value"] == "1"

    @pytest.mark.asyncio
    async def test_custom_sort(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": []},
        )

        await hubspot.execute_action(
            "get_recent_tickets",
            {"sort_property": "createdate", "sort_direction": "ASC", "limit": 5},
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["sorts"] == [{"propertyName": "createdate", "direction": "ASCENDING"}]
        assert body["limit"] == 5

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/tickets/search"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_properties_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        props = mock_context.fetch.call_args.kwargs["json"]["properties"]
        for expected in [
            "subject",
            "content",
            "hs_pipeline_stage",
            "hs_ticket_priority",
            "createdate",
        ]:
            assert expected in props

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_default_sort_direction(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        sorts = mock_context.fetch.call_args.kwargs["json"]["sorts"]
        assert sorts[0]["direction"] == "DESCENDING"

    @pytest.mark.asyncio
    async def test_response_data_structure(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": [{"id": "t-1"}]})

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        data = result.result.data
        assert "tickets" in data
        assert isinstance(data["tickets"], dict)

    @pytest.mark.asyncio
    async def test_sort_direction_asc(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("get_recent_tickets", {"sort_direction": "ASC"}, mock_context)

        sorts = mock_context.fetch.call_args.kwargs["json"]["sorts"]
        assert sorts[0]["direction"] == "ASCENDING"


# ---- get_ticket_conversation ----


TICKET_RESPONSE_WITH_THREAD = FetchResponse(
    status=200,
    headers={},
    data={"properties": {"hs_conversations_originating_thread_id": "thread-123"}},
)

TICKET_RESPONSE_NO_THREAD = FetchResponse(
    status=200,
    headers={},
    data={"properties": {}},
)

CONVERSATION_MESSAGES_RESPONSE = FetchResponse(
    status=200,
    headers={},
    data={
        "results": [
            {
                "text": "Hello",
                "type": "MESSAGE",
                "senders": [{"name": "John"}],
                "createdAt": "2025-01-01T00:00:00Z",
                "id": "msg-1",
            },
            {
                "text": "Follow-up",
                "type": "MESSAGE",
                "senders": [{"name": "Jane"}],
                "createdAt": "2025-01-02T00:00:00Z",
                "id": "msg-2",
            },
        ]
    },
)


class TestGetTicketConversation:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            CONVERSATION_MESSAGES_RESPONSE,
        ]

        result = await hubspot.execute_action(
            "get_ticket_conversation",
            {"ticket_id": "ticket-1"},
            mock_context,
        )

        data = result.result.data
        conv = data["conversation"]
        assert conv["ticket_id"] == "ticket-1"
        assert conv["thread_id"] == "thread-123"
        assert len(conv["results"]) == 2
        # Messages sorted by timestamp
        assert conv["results"][0]["message"] == "Hello"
        assert conv["results"][0]["sender"] == "John"
        assert conv["results"][1]["message"] == "Follow-up"

    @pytest.mark.asyncio
    async def test_no_thread_found(self, mock_context):
        mock_context.fetch.side_effect = [TICKET_RESPONSE_NO_THREAD]

        result = await hubspot.execute_action(
            "get_ticket_conversation",
            {"ticket_id": "ticket-2"},
            mock_context,
        )

        data = result.result.data
        conv = data["conversation"]
        assert conv["results"] == []
        assert conv["ticket_id"] == "ticket-2"
        assert conv["thread_id"] is None
        assert "No conversation thread found" in conv["message"]

    @pytest.mark.asyncio
    async def test_comment_type_shows_private_note(self, mock_context):
        comment_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "text": "Internal note",
                        "type": "COMMENT",
                        "senders": [{"name": "Agent"}],
                        "createdAt": "2025-01-01T00:00:00Z",
                        "id": "msg-3",
                    }
                ]
            },
        )
        mock_context.fetch.side_effect = [TICKET_RESPONSE_WITH_THREAD, comment_response]

        result = await hubspot.execute_action(
            "get_ticket_conversation",
            {"ticket_id": "ticket-3"},
            mock_context,
        )

        messages = result.result.data["conversation"]["results"]
        assert len(messages) == 1
        assert messages[0]["sender"] == "Private Note"
        assert messages[0]["type"] == "COMMENT"

    @pytest.mark.asyncio
    async def test_request_sequence(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            CONVERSATION_MESSAGES_RESPONSE,
        ]

        await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "ticket-1"}, mock_context)

        assert mock_context.fetch.call_count == 2
        ticket_url = mock_context.fetch.call_args_list[0].args[0]
        assert "/crm/v3/objects/tickets/ticket-1" in ticket_url
        conv_url = mock_context.fetch.call_args_list[1].args[0]
        assert "/conversations/v3/conversations/threads/thread-123/messages" in conv_url

    @pytest.mark.asyncio
    async def test_messages_sorted_chronologically(self, mock_context):
        unsorted_response = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "text": "Later",
                        "type": "MESSAGE",
                        "senders": [{"name": "B"}],
                        "createdAt": "2025-01-02T00:00:00Z",
                        "id": "m2",
                    },
                    {
                        "text": "Earlier",
                        "type": "MESSAGE",
                        "senders": [{"name": "A"}],
                        "createdAt": "2025-01-01T00:00:00Z",
                        "id": "m1",
                    },
                ]
            },
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            unsorted_response,
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        msgs = result.result.data["conversation"]["results"]
        assert msgs[0]["message"] == "Earlier"
        assert msgs[1]["message"] == "Later"

    @pytest.mark.asyncio
    async def test_sender_extracted_from_senders(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            CONVERSATION_MESSAGES_RESPONSE,
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        msgs = result.result.data["conversation"]["results"]
        assert msgs[0]["sender"] == "John"
        assert msgs[1]["sender"] == "Jane"

    @pytest.mark.asyncio
    async def test_message_without_text_skipped(self, mock_context):
        response_with_empty = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "text": "Has text",
                        "type": "MESSAGE",
                        "senders": [{"name": "A"}],
                        "createdAt": "2025-01-01T00:00:00Z",
                        "id": "m1",
                    },
                    {
                        "text": None,
                        "type": "MESSAGE",
                        "senders": [{"name": "B"}],
                        "createdAt": "2025-01-02T00:00:00Z",
                        "id": "m2",
                    },
                    {
                        "type": "MESSAGE",
                        "senders": [{"name": "C"}],
                        "createdAt": "2025-01-03T00:00:00Z",
                        "id": "m3",
                    },
                ]
            },
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            response_with_empty,
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        msgs = result.result.data["conversation"]["results"]
        assert len(msgs) == 1
        assert msgs[0]["message"] == "Has text"

    @pytest.mark.asyncio
    async def test_empty_messages(self, mock_context):
        empty_response = FetchResponse(status=200, headers={}, data={"results": []})
        mock_context.fetch.side_effect = [TICKET_RESPONSE_WITH_THREAD, empty_response]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        msgs = result.result.data["conversation"]["results"]
        assert msgs == []

    @pytest.mark.asyncio
    async def test_response_includes_thread_id(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            CONVERSATION_MESSAGES_RESPONSE,
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        conv = result.result.data["conversation"]
        assert conv["thread_id"] == "thread-123"


# ---- add_ticket_comment ----


class TestAddTicketComment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        comment_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "msg-new", "text": "My comment", "type": "COMMENT"},
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            comment_post_response,
        ]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "My comment"},
            mock_context,
        )

        data = result.result.data
        assert data["result"]["success"] is True
        assert data["result"]["message"] == "Comment added successfully to the thread"
        assert data["result"]["thread_message"]["id"] == "msg-new"

        # Verify the POST payload
        post_call = mock_context.fetch.call_args_list[1]
        assert "thread-123/messages" in post_call.args[0]
        assert post_call.kwargs["method"] == "POST"
        assert post_call.kwargs["json"] == {"type": "COMMENT", "text": "My comment"}

    @pytest.mark.asyncio
    async def test_no_thread_found(self, mock_context):
        mock_context.fetch.side_effect = [TICKET_RESPONSE_NO_THREAD]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-2", "comment": "Hello"},
            mock_context,
        )

        data = result.result.data
        assert data["result"]["success"] is False
        assert "No conversation thread found" in data["result"]["message"]

    @pytest.mark.asyncio
    async def test_parse_error_returns_action_error(self, mock_context):
        # The try/except in add_ticket_comment wraps parse_response.
        # Simulate a response whose .data property raises when accessed.
        bad_response = MagicMock()
        type(bad_response).data = property(lambda self: (_ for _ in ()).throw(ValueError("bad data")))
        mock_context.fetch.side_effect = [TICKET_RESPONSE_WITH_THREAD, bad_response]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "Fail"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_request_url_contains_thread_id(self, mock_context):
        comment_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "msg-new", "text": "test", "type": "COMMENT"},
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            comment_post_response,
        ]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "test"}, mock_context)

        post_url = mock_context.fetch.call_args_list[1].args[0]
        assert "thread-123/messages" in post_url

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        comment_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "msg-new", "text": "hello", "type": "COMMENT"},
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            comment_post_response,
        ]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "hello"}, mock_context)

        payload = mock_context.fetch.call_args_list[1].kwargs["json"]
        assert payload["type"] == "COMMENT"
        assert payload["text"] == "hello"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        comment_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "msg-new", "text": "x", "type": "COMMENT"},
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            comment_post_response,
        ]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "x"}, mock_context)

        assert mock_context.fetch.call_args_list[1].kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_response_success_true(self, mock_context):
        comment_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "msg-new", "text": "ok", "type": "COMMENT"},
        )
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            comment_post_response,
        ]

        result = await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "ok"}, mock_context)

        data = result.result.data
        assert data["result"]["success"] is True
        assert "message" in data["result"]
