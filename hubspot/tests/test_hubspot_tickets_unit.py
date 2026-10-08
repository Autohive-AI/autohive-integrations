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
    async def test_100_tickets_preserves_record_with_null_subject(self, mock_context):
        tickets = [{"id": str(index), "properties": {"subject": f"Ticket {index}"}} for index in range(100)]
        tickets[45]["properties"]["subject"] = None
        response = {"total": 100, "results": tickets, "paging": {"next": {"after": "100"}}}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await hubspot.execute_action("get_recent_tickets", {"limit": 100}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["tickets"] == response
        assert len(result.result.data["tickets"]["results"]) == 100
        assert result.result.data["tickets"]["results"][45]["properties"]["subject"] is None
        assert mock_context.fetch.call_args.kwargs["json"]["limit"] == 100

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "property_name",
        [
            "subject",
            "content",
            "hs_pipeline_stage",
            "hs_ticket_priority",
            "hubspot_owner_id",
            "hs_ticket_category",
            "createdate",
            "hs_lastmodifieddate",
            "hs_object_id",
        ],
    )
    @pytest.mark.parametrize("value", [None, "", "set value"])
    async def test_preserves_nullable_and_empty_property_values(self, mock_context, property_name, value):
        response = {"results": [{"id": "t-1", "properties": {property_name: value}}]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["tickets"] == response

    @pytest.mark.asyncio
    async def test_preserves_ticket_without_subject_property(self, mock_context):
        response = {"results": [{"id": "t-1", "properties": {"content": "No subject provided"}}]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["tickets"] == response
        assert "subject" not in result.result.data["tickets"]["results"][0]["properties"]

    @pytest.mark.asyncio
    async def test_rejects_non_string_non_null_subject(self, mock_context):
        response = {"results": [{"id": "t-1", "properties": {"subject": 123}}]}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response)

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert result.result["source"] == "output"
        assert "subject" in result.result["message"]

    @pytest.mark.asyncio
    async def test_happy_path_defaults(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "results": [
                    {
                        "id": "t-1",
                        "properties": {"subject": "Issue A", "hubspot_owner_id": "owner-123"},
                    }
                ]
            },
        )

        result = await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        data = result.result.data
        assert "tickets" in data
        assert data["tickets"]["results"][0]["id"] == "t-1"
        assert data["tickets"]["results"][0]["properties"]["hubspot_owner_id"] == "owner-123"

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
            data={"associations": {"tickets": {"results": []}}},
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
            data={"associations": {"tickets": {"results": []}}},
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
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == "https://api.hubapi.com/crm/v3/objects/tickets/search"
        assert call_kwargs.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_properties_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        props = mock_context.fetch.call_args.kwargs["json"]["properties"]
        for expected in [
            "subject",
            "content",
            "hs_pipeline_stage",
            "hs_ticket_priority",
            "hubspot_owner_id",
            "createdate",
        ]:
            assert expected in props

    @pytest.mark.asyncio
    async def test_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )

        await hubspot.execute_action("get_recent_tickets", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"]["limit"] == 20

    @pytest.mark.asyncio
    async def test_default_sort_direction(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )

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
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )

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


# ---- get_ticket_conversation: error surfacing, richText fallback and pagination ----


def _messages_page(messages, after=None):
    data = {"results": messages}
    if after:
        data["paging"] = {"next": {"after": after}}
    return FetchResponse(status=200, headers={}, data=data)


class TestGetTicketConversationReliability:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", ["HTTP 500: Internal Server Error", "HTTP 403: Missing scopes"])
    async def test_messages_api_error_returns_action_error(self, mock_context, error):
        mock_context.fetch.side_effect = [TICKET_RESPONSE_WITH_THREAD, Exception(error)]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "t1" in result.result.message
        assert error in result.result.message

    @pytest.mark.asyncio
    async def test_thread_lookup_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [Exception("HTTP 404: Not Found")]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "missing"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "missing" in result.result.message
        assert "HTTP 404" in result.result.message

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", [None, "", "   "])
    async def test_rich_text_used_when_plain_text_missing(self, mock_context, text):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            _messages_page(
                [
                    {
                        "id": "email-1",
                        "type": "MESSAGE",
                        "text": text,
                        "richText": "<div>Hi team,</div><div>Our APM traces have <b>flatlined</b> &amp; stopped.</div>",
                        "direction": "INCOMING",
                        "createdAt": "2026-10-05T16:24:56Z",
                        "senders": [
                            {
                                "actorId": "V-1",
                                "name": "Edmond",
                                "deliveryIdentifier": {"type": "HS_EMAIL_ADDRESS", "value": "edmond@example.com"},
                            }
                        ],
                    }
                ]
            ),
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        assert result.type == ResultType.ACTION
        msg = result.result.data["conversation"]["results"][0]
        assert msg["message"] == "Hi team,\nOur APM traces have flatlined & stopped."
        assert msg["direction"] == "INCOMING"
        assert msg["sender"] == "Edmond"

    @pytest.mark.asyncio
    async def test_follows_pagination_and_sorts_across_pages(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            _messages_page(
                [{"id": "m2", "type": "MESSAGE", "text": "Second", "createdAt": "2026-10-02T00:00:00Z"}],
                after="cursor-1",
            ),
            _messages_page([{"id": "m1", "type": "MESSAGE", "text": "First", "createdAt": "2026-10-01T00:00:00Z"}]),
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        conv = result.result.data["conversation"]
        assert [m["message"] for m in conv["results"]] == ["First", "Second"]
        first_params = mock_context.fetch.call_args_list[1].kwargs["params"]
        second_params = mock_context.fetch.call_args_list[2].kwargs["params"]
        assert "after" not in first_params
        assert second_params["after"] == "cursor-1"

    @pytest.mark.asyncio
    async def test_reads_past_ten_pages(self, mock_context):
        pages = [
            _messages_page(
                [{"id": f"m{i}", "type": "MESSAGE", "text": f"Message {i}", "createdAt": f"{i:02d}"}],
                after=f"cursor-{i}" if i < 10 else None,
            )
            for i in range(11)
        ]
        mock_context.fetch.side_effect = [TICKET_RESPONSE_WITH_THREAD, *pages]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["conversation"]["results"]) == 11
        assert result.result.data["conversation"]["results"][-1]["message"] == "Message 10"

    @pytest.mark.asyncio
    async def test_later_page_failure_returns_error_instead_of_partial_conversation(self, mock_context):
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            _messages_page([{"id": "m1", "type": "MESSAGE", "text": "Hello"}], after="cursor-1"),
            Exception("HTTP 500: Internal Server Error"),
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message

    @pytest.mark.asyncio
    async def test_rate_limit_on_messages_is_retried(self, mock_context, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", sleep_mock)
        mock_context.fetch.side_effect = [
            TICKET_RESPONSE_WITH_THREAD,
            Exception("HTTP 429: Rate limit exceeded"),
            _messages_page([{"id": "m1", "type": "MESSAGE", "text": "Hi", "createdAt": "1"}]),
        ]

        result = await hubspot.execute_action("get_ticket_conversation", {"ticket_id": "t1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["conversation"]["results"][0]["message"] == "Hi"
        sleep_mock.assert_awaited_once_with(1)


class TestHtmlToText:
    def test_strips_tags_and_unescapes_entities(self):
        from hubspot.hubspot import html_to_text

        assert html_to_text("<p>Hello&nbsp;there</p><p>Line&nbsp;2<br>Line 3</p>") == "Hello there\nLine 2\nLine 3"

    def test_drops_style_blocks_and_handles_empty(self):
        from hubspot.hubspot import html_to_text

        assert html_to_text("<style>p{color:red}</style><div>Body</div>") == "Body"
        assert html_to_text("") == ""


# ---- add_ticket_comment ----


class TestAddTicketComment:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "My comment"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": [{"id": "ticket-1"}, {"id": "t1"}]}}}
        )
        mock_context.fetch.side_effect = [note_post_response, verification_response]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "My comment"},
            mock_context,
        )

        data = result.result.data
        assert data["result"]["success"] is True
        assert data["result"]["message"] == "Note added successfully to the ticket"
        assert data["result"]["visibility"] == "internal_note"
        assert data["result"]["note"]["id"] == "note-new"

        post_call = mock_context.fetch.call_args_list[0]
        assert post_call.args[0] == "https://api.hubapi.com/crm/v3/objects/notes"
        assert post_call.kwargs["method"] == "POST"
        payload = post_call.kwargs["json"]
        assert payload["properties"]["hs_note_body"] == "My comment"
        assert isinstance(payload["properties"]["hs_timestamp"], int)
        assert payload["associations"][0]["to"]["id"] == "ticket-1"
        assert payload["associations"][0]["types"][0] == {
            "associationCategory": "HUBSPOT_DEFINED",
            "associationTypeId": 228,
        }

        verification_call = mock_context.fetch.call_args_list[1]
        assert verification_call.args[0] == "https://api.hubapi.com/crm/v3/objects/notes/note-new"
        assert verification_call.kwargs["method"] == "GET"
        assert verification_call.kwargs["params"] == {"associations": "ticket"}

    @pytest.mark.asyncio
    async def test_parse_error_returns_action_error(self, mock_context):
        bad_response = MagicMock()
        type(bad_response).data = property(lambda self: (_ for _ in ()).throw(ValueError("bad data")))
        mock_context.fetch.side_effect = [bad_response]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "Fail"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_request_url_is_notes_api(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "test"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": [{"id": "ticket-1"}, {"id": "t1"}]}}}
        )
        mock_context.fetch.side_effect = [note_post_response, verification_response]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "test"}, mock_context)

        post_url = mock_context.fetch.call_args_list[0].args[0]
        assert post_url == "https://api.hubapi.com/crm/v3/objects/notes"

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "hello"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": [{"id": "ticket-1"}, {"id": "t1"}]}}}
        )
        mock_context.fetch.side_effect = [note_post_response, verification_response]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "hello"}, mock_context)

        payload = mock_context.fetch.call_args_list[0].kwargs["json"]
        assert payload["properties"]["hs_note_body"] == "hello"
        assert payload["associations"][0]["to"]["id"] == "t1"
        assert payload["associations"][0]["types"][0]["associationTypeId"] == 228

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "x"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": [{"id": "ticket-1"}, {"id": "t1"}]}}}
        )
        mock_context.fetch.side_effect = [note_post_response, verification_response]

        await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "x"}, mock_context)

        assert mock_context.fetch.call_args_list[0].kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_response_success_true(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "ok"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": [{"id": "ticket-1"}, {"id": "t1"}]}}}
        )
        mock_context.fetch.side_effect = [note_post_response, verification_response]

        result = await hubspot.execute_action("add_ticket_comment", {"ticket_id": "t1", "comment": "ok"}, mock_context)

        data = result.result.data
        assert data["result"]["success"] is True
        assert "message" in data["result"]
        assert data["result"]["verification"]["associations"]["tickets"]["results"]

    @pytest.mark.asyncio
    async def test_note_create_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [ValueError("note create failed")]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "orphan"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to add note to ticket ticket-1" in result.result.message

    @pytest.mark.asyncio
    async def test_association_false_positive_deletes_orphaned_note(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "orphan"}},
        )
        verification_response = FetchResponse(
            status=200, headers={}, data={"associations": {"tickets": {"results": []}}}
        )
        mock_context.fetch.side_effect = [
            note_post_response,
            verification_response,
            FetchResponse(status=204, headers={}, data={}),
        ]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "orphan"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to verify note note-new is visible through ticket ticket-1" in result.result.message
        assert "note is not discoverable through the ticket association" in result.result.message
        assert mock_context.fetch.call_args_list[2].args[0] == "https://api.hubapi.com/crm/v3/objects/notes/note-new"
        assert mock_context.fetch.call_args_list[2].kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_verification_rate_limit_does_not_delete_created_note(self, mock_context, monkeypatch):
        mock_sleep = AsyncMock()
        monkeypatch.setattr("hubspot.hubspot.asyncio.sleep", mock_sleep)
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"id": "note-new", "properties": {"hs_note_body": "rate limited"}},
        )
        rate_limit_error = Exception("HTTP 429: Rate limit exceeded")
        mock_context.fetch.side_effect = [
            note_post_response,
            rate_limit_error,
            rate_limit_error,
            rate_limit_error,
            rate_limit_error,
        ]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "rate limited"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "was not deleted because verification failed" in result.result.message
        assert all(call.kwargs.get("method") != "DELETE" for call in mock_context.fetch.call_args_list)
        assert mock_sleep.await_count == 3

    @pytest.mark.asyncio
    async def test_missing_note_id_returns_action_error(self, mock_context):
        note_post_response = FetchResponse(
            status=200,
            headers={},
            data={"properties": {"hs_note_body": "missing id"}},
        )
        mock_context.fetch.side_effect = [note_post_response]

        result = await hubspot.execute_action(
            "add_ticket_comment",
            {"ticket_id": "ticket-1", "comment": "missing id"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "note was created without an id" in result.result.message
