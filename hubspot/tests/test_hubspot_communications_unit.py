import asyncio

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from autohive_integrations_sdk import ExecutionContext, FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from hubspot.hubspot import fetch_with_rate_limit_retries, hubspot

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test_token"}}  # nosec B105
    ctx.config = {"max_retries": 3, "timeout": 30}
    return ctx


COMMUNICATIONS_API_URL = "https://api.hubapi.com/crm/v3/objects/communications"
BATCH_CREATE_URL = f"{COMMUNICATIONS_API_URL}/batch/create"
CONTACTS_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"
CONTACTS_UPSERT_URL = "https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert"
CONTACTS_BATCH_READ_URL = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def search_response(*contact_ids):
    return ok({"total": len(contact_ids), "results": [{"id": contact_id} for contact_id in contact_ids]})


def batch_read_response(contacts_by_email, missing=()):
    data = {"results": [{"id": cid, "properties": {"email": email}} for email, cid in contacts_by_email.items()]}
    if missing:
        data["errors"] = [{"category": "OBJECT_NOT_FOUND", "message": "Could not get some CONTACT objects"}]
    return ok(data, status=207 if missing else 200)


@pytest.fixture(autouse=True)
def no_pacing_sleep():
    with patch("hubspot.hubspot.asyncio.sleep", new=AsyncMock()) as sleep:
        yield sleep


def batch_created(*trace_ids, errors=None):
    data = {
        "status": "COMPLETE",
        "results": [{"id": f"comm-{trace_id}", "objectWriteTraceId": trace_id} for trace_id in trace_ids],
    }
    if errors:
        data["errors"] = errors
        data["numErrors"] = len(errors)
    return ok(data, status=207 if errors else 201)


def fetch_calls(mock_context, url):
    return [call for call in mock_context.fetch.call_args_list if call.args[0] == url]


class LostResponseSession:
    """Stands in for the SDK's aiohttp session: the write URL drops its connection, every other URL succeeds."""

    def __init__(self, write_url, other_response):
        self.write_url = write_url
        self.other_response = other_response
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append(url)
        if url == self.write_url:
            raise aiohttp.ServerDisconnectedError()
        response = MagicMock(status=200, ok=True, headers={"Content-Type": "application/json"})
        response.json = AsyncMock(return_value=self.other_response)
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=response)
        context_manager.__aexit__ = AsyncMock(return_value=False)
        return context_manager


@pytest.fixture
def sdk_context():
    """A real SDK ExecutionContext, so its own fetch (and its resend-on-connection-error logic) runs."""
    ctx = ExecutionContext(auth={"auth_type": "PlatformOauth2", "credentials": {"access_token": "test_token"}})  # nosec B105
    # The SDK backs off between resends; skip the wait so a regression fails fast instead of sleeping
    with patch("autohive_integrations_sdk.integration.asyncio.sleep", new=AsyncMock()):
        yield ctx


# ---- Log LinkedIn Messages ----


class TestLogLinkedInMessages:
    @pytest.fixture(autouse=True)
    def all_contact_ids_exist(self):
        # The missing-contact check is covered in TestLogLinkedInMessagesContactCheck
        async def every_id_exists(object_type, object_ids, *args):
            return dict.fromkeys(object_ids)

        with patch("hubspot.hubspot._check_object_ids", new=every_id_exists):
            yield

    @pytest.mark.asyncio
    async def test_contact_id_row_is_logged_without_search(self, mock_context):
        mock_context.fetch.return_value = batch_created("0")

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501", "message_body": "Accepted my connection request"}]},
            mock_context,
        )

        data = result.result.data
        assert data["success"] is True
        assert data["logged"] == 1
        assert data["results"][0]["status"] == "logged"
        assert data["results"][0]["contact_id"] == "501"
        assert data["results"][0]["communication_id"] == "comm-0"
        assert mock_context.fetch.call_count == 1
        assert mock_context.fetch.call_args.args[0] == BATCH_CREATE_URL

    @pytest.mark.asyncio
    async def test_payload_matches_hubspot_linkedin_message_shape(self, mock_context):
        mock_context.fetch.return_value = batch_created("0")

        await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {
                        "contact_id": "501",
                        "company_id": "601",
                        "deal_id": "701",
                        "timestamp": 1700000000000,
                    }
                ],
                "default_message_body": "Accepted LinkedIn connection request",
                "hubspot_owner_id": "42",
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "POST"
        batch_input = call.kwargs["json"]["inputs"][0]
        assert batch_input["objectWriteTraceId"] == "0"
        assert batch_input["properties"] == {
            "hs_communication_channel_type": "LINKEDIN_MESSAGE",
            "hs_communication_logged_from": "CRM",
            "hs_communication_body": "Accepted LinkedIn connection request",
            "hs_timestamp": "1700000000000",
            "hubspot_owner_id": "42",
        }
        associations = {
            assoc["to"]["id"]: assoc["types"][0]["associationTypeId"] for assoc in batch_input["associations"]
        }
        assert associations == {"501": 81, "601": 87, "701": 85}
        assert all(
            assoc["types"][0]["associationCategory"] == "HUBSPOT_DEFINED" for assoc in batch_input["associations"]
        )

    @pytest.mark.asyncio
    async def test_timestamp_defaults_to_now_and_owner_is_optional(self, mock_context):
        mock_context.fetch.return_value = batch_created("0")

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501"}], "default_message_body": "Hi"},
            mock_context,
        )

        properties = mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]
        assert properties["hs_timestamp"].isdigit()
        assert "hubspot_owner_id" not in properties

    @pytest.mark.asyncio
    async def test_iso_timestamp_is_sent_as_milliseconds(self, mock_context):
        mock_context.fetch.return_value = batch_created("0")

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501", "timestamp": "2026-10-20T09:30:00Z"}], "default_message_body": "Hi"},
            mock_context,
        )

        properties = mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]
        assert properties["hs_timestamp"] == "1792488600000"

    @pytest.mark.asyncio
    async def test_email_rows_resolved_with_one_batch_read_not_search(self, mock_context):
        mock_context.fetch.side_effect = [
            batch_read_response({"jo@example.com": "900", "al@example.com": "901"}),
            batch_created("0", "1"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"email": " Jo@Example.com "}, {"email": "al@example.com"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert [r["contact_id"] for r in rows] == ["900", "901"]
        assert rows[0]["identifier"] == "email:Jo@Example.com"
        read_calls = fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)
        assert len(read_calls) == 1
        assert read_calls[0].kwargs["json"]["idProperty"] == "email"
        assert read_calls[0].kwargs["json"]["inputs"] == [{"id": "al@example.com"}, {"id": "jo@example.com"}]
        assert fetch_calls(mock_context, CONTACTS_SEARCH_URL) == []

    @pytest.mark.asyncio
    async def test_email_missing_from_batch_read_is_not_found(self, mock_context):
        mock_context.fetch.side_effect = [
            batch_read_response({"jo@example.com": "900"}, missing=["new@example.com"]),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "jo@example.com"}, {"email": "new@example.com"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert [r["status"] for r in result.result.data["results"]] == ["logged", "not_found"]

    @pytest.mark.asyncio
    async def test_additional_email_matches_its_contact(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "results": [
                        {
                            "id": "900",
                            "properties": {"email": "jo@work.com", "hs_additional_emails": "jo@home.com;Jo@Old.com"},
                        }
                    ]
                }
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "jo@old.com"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "logged"
        assert result.result.data["results"][0]["contact_id"] == "900"
        read_call = fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)[0]
        assert read_call.kwargs["json"]["properties"] == ["email", "hs_additional_emails"]

    @pytest.mark.asyncio
    async def test_primary_and_additional_emails_in_same_call_resolve_to_one_contact(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "results": [
                        {"id": "900", "properties": {"email": "jo@work.com", "hs_additional_emails": "jo@home.com"}}
                    ]
                }
            ),
            batch_created("0", "1"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "jo@work.com"}, {"email": "jo@home.com"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert [r["contact_id"] for r in result.result.data["results"]] == ["900", "900"]

    @pytest.mark.asyncio
    async def test_batch_read_404_means_no_email_matched(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "new@example.com"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "not_found"
        assert result.result.data["results"][0]["error"] is None

    @pytest.mark.asyncio
    async def test_name_row_searches_by_first_and_last_name(self, mock_context):
        mock_context.fetch.side_effect = [search_response("901"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"first_name": "Jo", "last_name": "Bloggs"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "logged"
        assert result.result.data["results"][0]["identifier"] == "name:Jo Bloggs"
        filters = fetch_calls(mock_context, CONTACTS_SEARCH_URL)[0].kwargs["json"]["filterGroups"][0]["filters"]
        assert filters == [
            {"propertyName": "firstname", "operator": "EQ", "value": "Jo"},
            {"propertyName": "lastname", "operator": "EQ", "value": "Bloggs"},
        ]

    @pytest.mark.asyncio
    async def test_email_takes_priority_over_name(self, mock_context):
        mock_context.fetch.side_effect = [batch_read_response({"jo@example.com": "900"}), batch_created("0")]

        await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"email": "jo@example.com", "first_name": "Jo", "last_name": "Bloggs"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        assert len(fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)) == 1
        assert fetch_calls(mock_context, CONTACTS_SEARCH_URL) == []

    @pytest.mark.asyncio
    async def test_unknown_person_is_not_found_and_not_logged(self, mock_context):
        mock_context.fetch.return_value = search_response()

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"first_name": "No", "last_name": "Body"}], "default_message_body": "Hi"},
            mock_context,
        )

        data = result.result.data
        assert data["results"][0]["status"] == "not_found"
        assert data["not_found"] == 1
        assert data["success"] is False
        assert fetch_calls(mock_context, BATCH_CREATE_URL) == []

    @pytest.mark.asyncio
    async def test_same_name_contacts_are_ambiguous_with_candidates(self, mock_context):
        mock_context.fetch.return_value = search_response("1", "2")

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"first_name": "Sam", "last_name": "Smith"}], "default_message_body": "Hi"},
            mock_context,
        )

        row = result.result.data["results"][0]
        assert row["status"] == "ambiguous"
        assert row["candidates"] == ["1", "2"]
        assert row["contact_id"] is None
        assert fetch_calls(mock_context, BATCH_CREATE_URL) == []

    @pytest.mark.asyncio
    async def test_row_without_identifier_is_invalid(self, mock_context):
        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"first_name": "Only"}], "default_message_body": "Hi"},
            mock_context,
        )

        row = result.result.data["results"][0]
        assert row["status"] == "invalid"
        assert "first_name and last_name" in row["error"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_contact_id_falls_back_to_email(self, mock_context):
        mock_context.fetch.side_effect = [batch_read_response({"jo@example.com": "900"}), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "  ", "email": "jo@example.com"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["contact_id"] == "900"
        assert len(fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)) == 1

    @pytest.mark.asyncio
    async def test_contact_id_is_trimmed(self, mock_context):
        mock_context.fetch.return_value = batch_created("0")

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": " 501 "}], "default_message_body": "Hi"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["associations"][0]["to"]["id"] == "501"

    @pytest.mark.asyncio
    async def test_row_without_any_body_is_invalid(self, mock_context):
        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501"}]},
            mock_context,
        )

        row = result.result.data["results"][0]
        assert row["status"] == "invalid"
        assert "message_body" in row["error"]
        assert result.result.data["invalid"] == 1
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_row_body_overrides_default(self, mock_context):
        mock_context.fetch.return_value = batch_created("0", "1")

        await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1", "message_body": "Custom"}, {"contact_id": "2"}],
                "default_message_body": "Default",
            },
            mock_context,
        )

        bodies = [
            i["properties"]["hs_communication_body"] for i in mock_context.fetch.call_args.kwargs["json"]["inputs"]
        ]
        assert bodies == ["Custom", "Default"]

    @pytest.mark.asyncio
    async def test_mixed_rows_report_each_outcome_and_batch_only_resolved(self, mock_context):
        mock_context.fetch.side_effect = [
            batch_read_response({"jo@example.com": "900"}),  # row 1 email
            search_response(),  # row 2 name not found
            search_response("1", "2"),  # row 3 ambiguous
            batch_created("0", "1"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {"contact_id": "501"},
                    {"email": "jo@example.com"},
                    {"first_name": "No", "last_name": "Body"},
                    {"first_name": "Sam", "last_name": "Smith"},
                    {},
                ],
                "default_message_body": "Accepted LinkedIn connection request",
            },
            mock_context,
        )

        data = result.result.data
        assert [r["status"] for r in data["results"]] == ["logged", "logged", "not_found", "ambiguous", "invalid"]
        assert [r["row_index"] for r in data["results"]] == [0, 1, 2, 3, 4]
        assert (data["logged"], data["not_found"], data["ambiguous"], data["invalid"], data["failed"]) == (
            2,
            1,
            1,
            1,
            0,
        )
        batch_call = fetch_calls(mock_context, BATCH_CREATE_URL)
        assert len(batch_call) == 1
        assert [i["objectWriteTraceId"] for i in batch_call[0].kwargs["json"]["inputs"]] == ["0", "1"]

    @pytest.mark.asyncio
    async def test_results_mapped_by_trace_id_not_order(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "results": [
                    {"id": "second", "objectWriteTraceId": "1"},
                    {"id": "first", "objectWriteTraceId": "0"},
                ]
            },
            status=201,
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert [r["communication_id"] for r in result.result.data["results"]] == ["first", "second"]

    @pytest.mark.asyncio
    async def test_name_searches_are_paced_under_hubspot_search_limit(self, mock_context, no_pacing_sleep):
        mock_context.fetch.side_effect = [search_response("1"), search_response("2"), search_response("3")] + [
            batch_created("0", "1", "2")
        ]

        await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {"first_name": "A", "last_name": "One"},
                    {"first_name": "B", "last_name": "Two"},
                    {"first_name": "C", "last_name": "Three"},
                ],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        assert len(fetch_calls(mock_context, CONTACTS_SEARCH_URL)) == 3
        # No wait before the first search, then one wait before each following search (<= 4 per second)
        assert [call.args[0] for call in no_pacing_sleep.await_args_list] == [0.25, 0.25]

    @pytest.mark.asyncio
    async def test_repeated_name_is_searched_once(self, mock_context, no_pacing_sleep):
        mock_context.fetch.side_effect = [search_response("1"), batch_created("0", "1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {"first_name": "Jo", "last_name": "Bloggs"},
                    {"first_name": " Jo ", "last_name": "Bloggs"},
                ],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        assert [r["contact_id"] for r in result.result.data["results"]] == ["1", "1"]
        assert len(fetch_calls(mock_context, CONTACTS_SEARCH_URL)) == 1
        no_pacing_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_traced_rows_kept_when_other_results_are_untraced(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "a", "objectWriteTraceId": "0"}, {"id": "b"}], "numErrors": 1}, status=207
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1"}, {"contact_id": "2"}, {"contact_id": "3"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert (rows[0]["status"], rows[0]["communication_id"]) == ("logged", "a")
        assert [r["status"] for r in rows[1:]] == ["failed", "failed"]
        assert all("2 of 3" in r["error"] for r in rows[1:])

    @pytest.mark.asyncio
    async def test_batch_errors_mapped_to_their_own_rows(self, mock_context):
        mock_context.fetch.return_value = batch_created(
            "0",
            errors=[
                {"message": "Owner 9 does not exist", "context": {"objectWriteTraceId": ["1"]}},
                {"message": "Deal 7 does not exist", "context": {"objectWriteTraceId": ["2"]}},
            ],
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1"}, {"contact_id": "2"}, {"contact_id": "3", "deal_id": "7"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert [(r["status"], r["error"]) for r in rows] == [
            ("logged", None),
            ("failed", "Owner 9 does not exist"),
            ("failed", "Deal 7 does not exist"),
        ]

    @pytest.mark.asyncio
    async def test_single_row_created_without_trace_id_keeps_its_id(self, mock_context):
        mock_context.fetch.return_value = ok({"results": [{"id": "a"}]}, status=201)

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        row = result.result.data["results"][0]
        assert (row["status"], row["communication_id"]) == ("logged", "a")

    @pytest.mark.asyncio
    async def test_all_rows_created_without_trace_ids_are_logged(self, mock_context):
        mock_context.fetch.return_value = ok({"results": [{"id": "a"}, {"id": "b"}]}, status=201)

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        data = result.result.data
        assert [(r["status"], r["communication_id"]) for r in data["results"]] == [("logged", None), ("logged", None)]
        assert data["success"] is True
        # HubSpot didn't say which ID is which row, so the IDs are returned instead of dropped
        assert data["unmatched_communication_ids"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_some_rows_created_without_trace_ids_expose_their_ids(self, mock_context):
        mock_context.fetch.return_value = ok({"results": [{"id": "a"}, {"id": "b"}]}, status=207)

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}, {"contact_id": "3"}], "default_message_body": "Hi"},
            mock_context,
        )

        data = result.result.data
        assert [r["status"] for r in data["results"]] == ["failed", "failed", "failed"]
        assert data["unmatched_communication_ids"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_traced_results_leave_no_unmatched_ids(self, mock_context):
        mock_context.fetch.return_value = batch_created("0", "1")

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["unmatched_communication_ids"] == []

    @pytest.mark.asyncio
    async def test_partial_creates_without_trace_ids_warn_against_retrying(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "a"}], "errors": [{"message": "Something went wrong"}], "numErrors": 1}, status=207
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert [r["status"] for r in rows] == ["failed", "failed"]
        assert all("1 of 2" in r["error"] and "before retrying" in r["error"] for r in rows)

    @pytest.mark.asyncio
    async def test_partial_creates_warning_keeps_hubspot_error_text(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "a"}], "errors": [{"message": "Property values were not valid"}]}, status=207
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        error = result.result.data["results"][0]["error"]
        assert "before retrying" in error
        assert "Property values were not valid" in error

    @pytest.mark.asyncio
    async def test_only_unexplained_row_gets_the_untraced_result(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "results": [{"id": "a"}],
                "errors": [{"message": "Deal 7 does not exist", "context": {"objectWriteTraceId": ["1"]}}],
            },
            status=207,
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2", "deal_id": "7"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert (rows[0]["status"], rows[0]["communication_id"]) == ("logged", "a")
        assert rows[1]["error"] == "Deal 7 does not exist"

    @pytest.mark.asyncio
    async def test_unexplained_rows_logged_by_elimination_when_counts_match(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "results": [{"id": "a"}, {"id": "b"}],
                "errors": [{"message": "Deal 7 does not exist", "context": {"objectWriteTraceId": ["2"]}}],
            },
            status=207,
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1"}, {"contact_id": "2"}, {"contact_id": "3", "deal_id": "7"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        data = result.result.data
        # Row 2's error leaves two results for two rows; which ID belongs to which row is still unknown
        assert [(r["status"], r["communication_id"]) for r in data["results"]] == [
            ("logged", None),
            ("logged", None),
            ("failed", None),
        ]
        assert data["results"][2]["error"] == "Deal 7 does not exist"
        assert (data["logged"], data["failed"]) == (2, 1)
        assert data["unmatched_communication_ids"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_partial_batch_marks_missing_rows_failed(self, mock_context):
        mock_context.fetch.return_value = batch_created(
            "0", errors=[{"status": "error", "category": "VALIDATION_ERROR", "message": "Contact 2 does not exist"}]
        )

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        data = result.result.data
        assert data["results"][0]["status"] == "logged"
        assert data["results"][1]["status"] == "failed"
        assert data["results"][1]["error"] == "Contact 2 does not exist"
        assert data["failed"] == 1
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_batch_http_error_fails_every_resolved_row(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "Invalid input")

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        statuses = [(r["status"], r["error"]) for r in result.result.data["results"]]
        assert statuses == [("failed", "HTTP 400: Invalid input")] * 2

    @pytest.mark.asyncio
    async def test_batch_create_is_not_resent_by_the_sdk(self, sdk_context):
        session = LostResponseSession(BATCH_CREATE_URL, {})
        sdk_context._session = session

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, sdk_context
        )

        # HubSpot may have saved a create whose response was lost, so the SDK must not send it again
        assert session.requests.count(BATCH_CREATE_URL) == 1
        row = result.result.data["results"][0]
        assert row["status"] == "failed"
        assert "check the contact's timeline before retrying" in row["error"]

    @pytest.mark.asyncio
    async def test_100_rows_accepted(self, mock_context):
        mock_context.fetch.return_value = batch_created(*[str(i) for i in range(100)])

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": str(i)} for i in range(100)], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert len(mock_context.fetch.call_args.kwargs["json"]["inputs"]) == 100
        assert result.result.data["logged"] == 100
        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [aiohttp.ServerDisconnectedError(), asyncio.TimeoutError(), HTTPError(504, "Gateway timeout")],
    )
    async def test_ambiguous_batch_failure_warns_to_check_before_retrying(self, mock_context, error):
        mock_context.fetch.side_effect = error

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        rows = result.result.data["results"]
        assert [r["status"] for r in rows] == ["failed", "failed"]
        assert all("check the contact's timeline before retrying" in r["error"] for r in rows)
        assert len(fetch_calls(mock_context, BATCH_CREATE_URL)) == 1

    @pytest.mark.asyncio
    async def test_server_error_mentioning_429_is_not_retried(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(500, "Internal error, correlationId 4291-abcd")

        await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        assert len(fetch_calls(mock_context, BATCH_CREATE_URL)) == 1

    @pytest.mark.asyncio
    async def test_search_http_error_fails_only_that_row(self, mock_context):
        mock_context.fetch.side_effect = [HTTPError(500, "Search unavailable"), batch_created("1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"first_name": "Jo", "last_name": "Bloggs"}, {"contact_id": "2"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "failed"
        assert "Contact lookup failed" in rows[0]["error"]
        assert rows[1]["status"] == "logged"

    @pytest.mark.asyncio
    async def test_email_lookup_http_error_fails_email_rows_only(self, mock_context):
        mock_context.fetch.side_effect = [HTTPError(500, "Server error"), batch_created("1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "jo@example.com"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "failed"
        assert "Contact lookup failed" in rows[0]["error"]
        assert rows[1]["status"] == "logged"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [aiohttp.ServerDisconnectedError(), asyncio.TimeoutError()])
    @pytest.mark.parametrize("row", [{"email": "jo@example.com"}, {"first_name": "Jo", "last_name": "Bloggs"}])
    async def test_lookup_connection_error_fails_only_that_row(self, mock_context, row, error):
        mock_context.fetch.side_effect = [error, batch_created("1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [row, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "failed"
        assert rows[0]["error"].startswith("Contact lookup failed: ")
        assert rows[0]["error"] != "Contact lookup failed: "
        assert rows[1]["status"] == "logged"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", ["PENDING", "PROCESSING"])
    async def test_unfinished_batch_warns_to_check_before_retrying(self, mock_context, status):
        mock_context.fetch.return_value = ok({"status": status, "results": []}, status=202)

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert [r["status"] for r in rows] == ["failed", "failed"]
        assert all("still processing" in r["error"] and "before retrying" in r["error"] for r in rows)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", ["PENDING", "PROCESSING", "CANCELED"])
    async def test_unfinished_email_lookup_fails_rows_not_found(self, mock_context, status):
        mock_context.fetch.side_effect = [ok({"status": status, "results": []}, status=202), batch_created("1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"email": "jo@example.com"}, {"contact_id": "2"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "failed"
        assert rows[0]["error"].startswith("Contact lookup failed: HubSpot")
        assert rows[1]["status"] == "logged"

    @pytest.mark.asyncio
    async def test_email_lookup_row_errors_fail_only_those_rows(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "status": "COMPLETE",
                    "results": [{"id": "900", "properties": {"email": "found@example.com"}}],
                    "errors": [
                        {
                            "category": "OBJECT_NOT_FOUND",
                            "message": "Not found",
                            "context": {"ids": ["gone@example.com"]},
                        },
                        {
                            "category": "VALIDATION_ERROR",
                            "message": "Bad email",
                            "context": {"ids": ["Bad@example.com"]},
                        },
                    ],
                },
                status=207,
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {"email": "found@example.com"},
                    {"email": "gone@example.com"},
                    {"email": "bad@example.com"},
                ],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert [r["status"] for r in rows] == ["logged", "not_found", "failed"]
        assert rows[2]["error"] == "Contact lookup failed: Bad email"

    @pytest.mark.asyncio
    async def test_email_lookup_error_without_ids_fails_unmatched_rows(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "results": [{"id": "900", "properties": {"email": "found@example.com"}}],
                    "errors": [{"category": "INTERNAL_ERROR", "message": "Something broke"}],
                },
                status=207,
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"email": "found@example.com"}, {"email": "other@example.com"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert [r["status"] for r in rows] == ["logged", "failed"]
        assert "Something broke" in rows[1]["error"]

    @pytest.mark.asyncio
    async def test_canceled_batch_warns_to_check_before_retrying(self, mock_context):
        mock_context.fetch.return_value = ok({"status": "CANCELED", "results": []})

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        error = result.result.data["results"][0]["error"]
        assert "HubSpot canceled this batch" in error
        assert "before retrying" in error

    @pytest.mark.asyncio
    async def test_comma_separated_additional_email_matches(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "results": [
                        {"id": "900", "properties": {"email": "p@x.com", "hs_additional_emails": "a@x.com,b@x.com"}}
                    ]
                }
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"email": "b@x.com"}], "default_message_body": "Hi"}, mock_context
        )

        assert result.result.data["results"][0]["contact_id"] == "900"

    @pytest.mark.asyncio
    async def test_name_search_asks_for_enough_candidates_to_spot_duplicates(self, mock_context):
        mock_context.fetch.side_effect = [search_response("1"), batch_created("0")]

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"first_name": "Jo", "last_name": "Bloggs"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert fetch_calls(mock_context, CONTACTS_SEARCH_URL)[0].kwargs["json"]["limit"] == 5

    @pytest.mark.asyncio
    async def test_more_than_100_rows_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": str(i)} for i in range(101)], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_messages_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action("log_linkedin_messages", {"messages": []}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR


class TestLogLinkedInMessagesContactCheck:
    @pytest.mark.asyncio
    async def test_missing_contact_id_skipped_so_other_rows_still_log(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "status": "COMPLETE",
                    "results": [{"id": "501"}],
                    "errors": [{"category": "OBJECT_NOT_FOUND", "message": "Not found", "context": {"ids": ["1"]}}],
                },
                status=207,
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501"}, {"contact_id": "1"}], "default_message_body": "Hi"},
            mock_context,
        )

        data = result.result.data
        assert [r["status"] for r in data["results"]] == ["logged", "not_found"]
        read_call, create_call = mock_context.fetch.call_args_list
        assert read_call.args[0] == CONTACTS_BATCH_READ_URL
        assert read_call.kwargs["json"]["inputs"] == [{"id": "501"}, {"id": "1"}]
        assert [i["associations"][0]["to"]["id"] for i in create_call.kwargs["json"]["inputs"]] == ["501"]

    @pytest.mark.asyncio
    async def test_every_contact_id_missing_skips_the_create(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        assert result.result.data["results"][0]["status"] == "not_found"
        assert len(fetch_calls(mock_context, BATCH_CREATE_URL)) == 0

    @pytest.mark.asyncio
    async def test_merged_contact_id_that_resolves_elsewhere_still_logs(self, mock_context):
        # A merged contact's old ID returns the surviving record, so only a named not-found counts as missing
        mock_context.fetch.side_effect = [ok({"status": "COMPLETE", "results": [{"id": "900"}]}), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "501"}], "default_message_body": "Hi"}, mock_context
        )

        assert result.result.data["results"][0]["status"] == "logged"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lookup",
        [
            HTTPError(500, "Server error"),
            ok({"status": "CANCELED", "results": []}),
            ok({"results": [], "errors": [{"category": "RATE_LIMITS", "message": "Slow down"}]}, status=207),
        ],
    )
    async def test_failed_contact_check_fails_id_rows_without_creating(self, mock_context, lookup):
        mock_context.fetch.side_effect = [lookup]

        result = await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        row = result.result.data["results"][0]
        assert row["status"] == "failed"
        assert row["error"].startswith("Contact lookup failed: ")
        assert len(fetch_calls(mock_context, BATCH_CREATE_URL)) == 0

    @pytest.mark.asyncio
    async def test_returned_contact_not_marked_missing_by_an_error_without_ids(self, mock_context):
        mock_context.fetch.side_effect = [
            ok(
                {
                    "status": "COMPLETE",
                    "results": [{"id": "501"}],
                    "errors": [{"category": "OBJECT_NOT_FOUND", "message": "Some not found"}],
                },
                status=207,
            ),
            batch_created("0"),
        ]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501"}, {"contact_id": "9"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert [r["status"] for r in result.result.data["results"]] == ["logged", "not_found"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lookup",
        [
            ok({"status": "CANCELED", "results": [{"id": "501"}]}),
            ok({"results": [{"id": "501"}], "errors": [{"category": "RATE_LIMITS", "message": "Slow"}]}, status=207),
        ],
    )
    async def test_lookup_error_only_fails_contacts_not_returned(self, mock_context, lookup):
        mock_context.fetch.side_effect = [lookup, batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "501"}, {"contact_id": "9"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "logged"
        assert (rows[1]["status"], rows[1]["error"].startswith("Contact lookup failed: ")) == ("failed", True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("contact_id", ["5\u00b2", "\u0663\u0663", "007", "0"])
    async def test_non_plain_number_ids_are_not_sent(self, mock_context, contact_id):
        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": contact_id}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "not_found"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_repeated_contact_id_checked_once(self, mock_context):
        mock_context.fetch.side_effect = [ok({"status": "COMPLETE", "results": [{"id": "1"}]}), batch_created("0", "1")]

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "1"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)[0].kwargs["json"]["inputs"] == [{"id": "1"}]


COMPANIES_BATCH_READ_URL = "https://api.hubapi.com/crm/v3/objects/companies/batch/read"
DEALS_BATCH_READ_URL = "https://api.hubapi.com/crm/v3/objects/deals/batch/read"


def found(*ids):
    return ok({"status": "COMPLETE", "results": [{"id": i} for i in ids]})


def not_found(*ids):
    return ok(
        {
            "status": "COMPLETE",
            "results": [],
            "errors": [{"category": "OBJECT_NOT_FOUND", "message": "Not found", "context": {"ids": list(ids)}}],
        },
        status=207,
    )


class TestLogLinkedInMessagesLinkedRecordCheck:
    @pytest.mark.asyncio
    async def test_missing_company_or_deal_skips_only_that_row(self, mock_context):
        mock_context.fetch.side_effect = [found("1", "2", "3"), not_found("601"), not_found("701"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [
                    {"contact_id": "1"},
                    {"contact_id": "2", "company_id": "601"},
                    {"contact_id": "3", "deal_id": "701"},
                ],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        data = result.result.data
        assert [(r["status"], r["error"]) for r in data["results"]] == [
            ("logged", None),
            ("invalid", "Company 601 does not exist"),
            ("invalid", "Deal 701 does not exist"),
        ]
        assert [call.args[0] for call in mock_context.fetch.call_args_list] == [
            CONTACTS_BATCH_READ_URL,
            COMPANIES_BATCH_READ_URL,
            DEALS_BATCH_READ_URL,
            BATCH_CREATE_URL,
        ]
        assert len(mock_context.fetch.call_args.kwargs["json"]["inputs"]) == 1

    @pytest.mark.asyncio
    async def test_existing_company_and_deal_are_linked(self, mock_context):
        mock_context.fetch.side_effect = [found("1"), found("601"), found("701"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1", "company_id": " 601 ", "deal_id": "701"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "logged"
        associations = mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["associations"]
        assert [a["to"]["id"] for a in associations] == ["1", "601", "701"]

    @pytest.mark.asyncio
    async def test_company_check_error_fails_only_rows_with_a_company(self, mock_context):
        mock_context.fetch.side_effect = [found("1", "2"), HTTPError(500, "Server error"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2", "company_id": "601"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "logged"
        assert (rows[1]["status"], rows[1]["error"]) == ("failed", "Company lookup failed: HTTP 500: Server error")

    @pytest.mark.asyncio
    async def test_deal_check_error_fails_only_rows_with_a_deal(self, mock_context):
        mock_context.fetch.side_effect = [found("1", "2"), HTTPError(503, "Unavailable"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1"}, {"contact_id": "2", "deal_id": "701"}], "default_message_body": "Hi"},
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "logged"
        assert (rows[1]["status"], rows[1]["error"]) == ("failed", "Deal lookup failed: HTTP 503: Unavailable")

    @pytest.mark.asyncio
    async def test_company_not_checked_for_rows_whose_contact_is_missing(self, mock_context):
        mock_context.fetch.side_effect = [not_found("1")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1", "company_id": "601"}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "not_found"
        assert [call.args[0] for call in mock_context.fetch.call_args_list] == [CONTACTS_BATCH_READ_URL]

    @pytest.mark.asyncio
    async def test_rows_without_company_or_deal_skip_those_checks(self, mock_context):
        mock_context.fetch.side_effect = [found("1"), batch_created("0")]

        await hubspot.execute_action(
            "log_linkedin_messages", {"messages": [{"contact_id": "1"}], "default_message_body": "Hi"}, mock_context
        )

        assert [call.args[0] for call in mock_context.fetch.call_args_list] == [
            CONTACTS_BATCH_READ_URL,
            BATCH_CREATE_URL,
        ]

    @pytest.mark.asyncio
    async def test_malformed_ids_never_reach_hubspot(self, mock_context):
        mock_context.fetch.side_effect = [found("1"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1"}, {"contact_id": "abc"}, {"contact_id": "1", "company_id": "acme"}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert [(r["status"], r["error"]) for r in rows] == [
            ("logged", None),
            ("not_found", None),
            ("invalid", "Company acme does not exist"),
        ]
        assert mock_context.fetch.call_args_list[0].kwargs["json"]["inputs"] == [{"id": "1"}]
        assert [call.args[0] for call in mock_context.fetch.call_args_list] == [
            CONTACTS_BATCH_READ_URL,
            BATCH_CREATE_URL,
        ]


class TestLogLinkedInMessagesTimestampCheck:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "timestamp", ["yesterday", "21/10/2026", "2026-13-01", "\u0663\u0663", -1, float("nan"), float("inf")]
    )
    async def test_unreadable_timestamp_marks_only_that_row_invalid(self, mock_context, timestamp):
        mock_context.fetch.side_effect = [found("1", "2"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {
                "messages": [{"contact_id": "1"}, {"contact_id": "2", "timestamp": timestamp}],
                "default_message_body": "Hi",
            },
            mock_context,
        )

        rows = result.result.data["results"]
        assert rows[0]["status"] == "logged"
        assert rows[1]["status"] == "invalid"
        assert "timestamp" in rows[1]["error"]
        assert len(mock_context.fetch.call_args.kwargs["json"]["inputs"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "timestamp", [1700000000000, "1700000000000", "2026-10-21", "2026-10-21T09:30:00Z", "2026-10-21T09:30:00+13:00"]
    )
    async def test_supported_timestamps_are_accepted(self, mock_context, timestamp):
        mock_context.fetch.side_effect = [found("1"), batch_created("0")]

        result = await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1", "timestamp": timestamp}], "default_message_body": "Hi"},
            mock_context,
        )

        assert result.result.data["results"][0]["status"] == "logged"
        assert mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]["hs_timestamp"].isdigit()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            (" 2026-10-20T09:30:00Z ", "1792488600000"),
            ("2026-10-20T09:30:00", "1792488600000"),
            ("2026-10-20T22:30:00+13:00", "1792488600000"),
            (" 1700000000000 ", "1700000000000"),
        ],
    )
    async def test_dates_are_sent_as_utc_milliseconds(self, mock_context, timestamp, expected):
        mock_context.fetch.side_effect = [found("1"), batch_created("0")]

        await hubspot.execute_action(
            "log_linkedin_messages",
            {"messages": [{"contact_id": "1", "timestamp": timestamp}], "default_message_body": "Hi"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]["hs_timestamp"] == expected


# ---- Get / Update / Delete LinkedIn Message ----


class TestGetLinkedInMessage:
    @pytest.mark.asyncio
    async def test_get_returns_communication(self, mock_context):
        communication = {"id": "77", "properties": {"hs_communication_channel_type": "LINKEDIN_MESSAGE"}}
        mock_context.fetch.return_value = ok(communication)

        result = await hubspot.execute_action("get_linkedin_message", {"communication_id": "77"}, mock_context)

        assert result.result.data["communication"] == communication
        assert result.result.data["success"] is True
        assert result.result.data["message"] == "LinkedIn message retrieved successfully"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{COMMUNICATIONS_API_URL}/77"
        assert "hs_communication_body" in call.kwargs["params"]["properties"]
        assert call.kwargs["params"]["associations"] == "contacts,companies,deals"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["get_linkedin_message", "update_linkedin_message", "delete_linkedin_message"])
    @pytest.mark.parametrize("communication_id", ["1/../../contacts/12345", "77?archived=true", "abc", ""])
    async def test_non_numeric_communication_id_rejected_before_any_request(
        self, mock_context, action, communication_id
    ):
        result = await hubspot.execute_action(
            action, {"communication_id": communication_id, "message_body": "x"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action("get_linkedin_message", {"communication_id": "77"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to get LinkedIn message" in result.result.message


class TestUpdateLinkedInMessage:
    @pytest.mark.asyncio
    async def test_update_sends_only_given_properties(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        result = await hubspot.execute_action(
            "update_linkedin_message",
            {"communication_id": "77", "message_body": "Fixed text", "hubspot_owner_id": "42"},
            mock_context,
        )

        assert result.result.data["success"] is True
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{COMMUNICATIONS_API_URL}/77"
        assert call.kwargs["method"] == "PATCH"
        assert call.kwargs["json"] == {"properties": {"hs_communication_body": "Fixed text", "hubspot_owner_id": "42"}}

    @pytest.mark.asyncio
    async def test_update_timestamp_number_sent_as_milliseconds(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "timestamp": 1700000000000}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"properties": {"hs_timestamp": "1700000000000"}}

    @pytest.mark.asyncio
    async def test_update_date_sent_as_utc_milliseconds(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        await hubspot.execute_action(
            "update_linkedin_message",
            {"communication_id": "77", "timestamp": "2026-10-20T22:30:00+13:00"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"properties": {"hs_timestamp": "1792488600000"}}

    @pytest.mark.asyncio
    async def test_update_unreadable_timestamp_rejected_before_calling_hubspot(self, mock_context):
        result = await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "timestamp": "yesterday"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "timestamp must be" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_empty_body_clears_it(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        result = await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "message_body": ""}, mock_context
        )

        assert result.result.data["success"] is True
        assert mock_context.fetch.call_args.kwargs["json"] == {"properties": {"hs_communication_body": ""}}

    @pytest.mark.asyncio
    async def test_update_empty_owner_removes_it(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "hubspot_owner_id": ""}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"properties": {"hubspot_owner_id": ""}}

    @pytest.mark.asyncio
    async def test_update_empty_timestamp_is_not_sent(self, mock_context):
        result = await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "timestamp": ""}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_timestamp_zero_is_sent(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "77"})

        await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "timestamp": 0}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"properties": {"hs_timestamp": "0"}}

    @pytest.mark.asyncio
    async def test_update_without_changes_returns_action_error(self, mock_context):
        result = await hubspot.execute_action("update_linkedin_message", {"communication_id": "77"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action(
            "update_linkedin_message", {"communication_id": "77", "message_body": "x"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 404" in result.result.message


class TestDeleteLinkedInMessage:
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)

        result = await hubspot.execute_action("delete_linkedin_message", {"communication_id": "77"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["communication_id"] == "77"
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{COMMUNICATIONS_API_URL}/77"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_delete_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Not found")

        result = await hubspot.execute_action("delete_linkedin_message", {"communication_id": "77"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Upsert Contacts ----


class TestUpsertContacts:
    @pytest.mark.asyncio
    async def test_upsert_payload_uses_email_as_id_property(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "1", "new": True, "properties": {"email": "jo@example.com"}}]}
        )

        await hubspot.execute_action(
            "upsert_contacts",
            {
                "contacts": [
                    {
                        "email": " Jo@Example.com ",
                        "first_name": "Jo",
                        "last_name": "Bloggs",
                        "properties": {"jobtitle": "CTO", "numemployees": 50, "hs_marketable_status": True},
                    }
                ]
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == CONTACTS_UPSERT_URL
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "inputs": [
                {
                    "id": "jo@example.com",
                    "idProperty": "email",
                    "properties": {
                        "jobtitle": "CTO",
                        "numemployees": "50",
                        "hs_marketable_status": "true",
                        "firstname": "Jo",
                        "lastname": "Bloggs",
                    },
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_new_flag_reports_created_vs_updated(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "results": [
                    {"id": "2", "new": False, "properties": {"email": "old@example.com"}},
                    {"id": "1", "new": True, "properties": {"email": "new@example.com"}},
                ]
            }
        )

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "new@example.com"}, {"email": "old@example.com"}]}, mock_context
        )

        data = result.result.data
        assert [(r["email"], r["status"], r["contact_id"]) for r in data["results"]] == [
            ("new@example.com", "created", "1"),
            ("old@example.com", "updated", "2"),
        ]
        assert (data["created"], data["updated"], data["failed"], data["success"]) == (1, 1, 0, True)

    @pytest.mark.asyncio
    async def test_partial_upsert_marks_missing_rows_failed(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"results": []}),
            ok(
                {
                    "results": [{"id": "1", "new": True, "properties": {"email": "a@example.com"}}],
                    "errors": [{"message": "Property values were not valid"}],
                    "numErrors": 1,
                },
                status=207,
            ),
        ]

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "a@example.com"}, {"email": "b@example.com"}]}, mock_context
        )

        data = result.result.data
        assert (data["results"][0]["status"], data["results"][0]["contact_id"], data["results"][0]["error"]) == (
            "created",
            "1",
            None,
        )
        assert data["results"][1]["status"] == "failed"
        assert data["results"][1]["error"] == "Property values were not valid"
        assert (data["created"], data["updated"], data["failed"]) == (1, 0, 1)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_upsert_results_matched_by_email_ignoring_case(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "results": [
                    {"id": "2", "new": False, "properties": {"email": "old@example.com"}},
                    {"id": "1", "new": True, "properties": {"email": "new@example.com"}},
                ]
            }
        )

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "New@example.com"}, {"email": "old@example.com"}]}, mock_context
        )

        assert [(r["status"], r["contact_id"]) for r in result.result.data["results"]] == [
            ("created", "1"),
            ("updated", "2"),
        ]

    @pytest.mark.asyncio
    async def test_upsert_is_not_resent_by_the_sdk(self, sdk_context):
        session = LostResponseSession(CONTACTS_UPSERT_URL, {"results": []})
        sdk_context._session = session

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, sdk_context)

        # A resend would see the contact this call just created and report it as updated
        assert session.requests.count(CONTACTS_UPSERT_URL) == 1
        assert result.type == ResultType.ACTION_ERROR
        assert "may have saved" in result.result.message

    @pytest.mark.asyncio
    async def test_100_contacts_accepted(self, mock_context):
        emails = [f"{i}@example.com" for i in range(100)]
        mock_context.fetch.side_effect = [
            ok({"results": []}),
            ok({"results": [{"id": str(i), "new": True, "properties": {"email": e}} for i, e in enumerate(emails)]}),
        ]

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": email} for email in emails]}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert len(fetch_calls(mock_context, CONTACTS_UPSERT_URL)[0].kwargs["json"]["inputs"]) == 100
        assert result.result.data["created"] == 100
        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error", [aiohttp.ServerDisconnectedError(), asyncio.TimeoutError(), HTTPError(503, "Unavailable")]
    )
    async def test_ambiguous_upsert_failure_says_outcome_unknown(self, mock_context, error):
        mock_context.fetch.side_effect = [ok({"results": []}), error]

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "may have saved" in result.result.message
        assert len(fetch_calls(mock_context, CONTACTS_UPSERT_URL)) == 1

    @pytest.mark.asyncio
    async def test_list_property_value_sent_as_semicolon_options(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "1", "new": False, "properties": {"email": "a@x.com"}}]}
        )

        await hubspot.execute_action(
            "upsert_contacts",
            {"contacts": [{"email": "a@x.com", "properties": {"hs_buying_role": ["BUDGET_HOLDER", "END_USER"]}}]},
            mock_context,
        )

        properties = mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]
        assert properties["hs_buying_role"] == "BUDGET_HOLDER;END_USER"

    @pytest.mark.asyncio
    async def test_canceled_upsert_rows_fail(self, mock_context):
        mock_context.fetch.side_effect = [ok({"results": []}), ok({"status": "CANCELED", "results": []})]

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, mock_context)

        row = result.result.data["results"][0]
        assert row["status"] == "failed"
        assert "HubSpot canceled this batch" in row["error"]

    @pytest.mark.asyncio
    async def test_upsert_and_read_back_share_one_rate_limit_budget(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"results": []}),
            ok({"results": [{"id": "9", "new": True, "properties": {}}]}),
            ok({"results": [{"id": "9", "properties": {"email": "a@x.com"}}]}),
        ]

        with patch("hubspot.hubspot.fetch_with_rate_limit_retries", wraps=fetch_with_rate_limit_retries) as fetch:
            result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, mock_context)

        # Lookup, upsert, then the read-back that matches the new contact
        assert [call.args[1] for call in fetch.call_args_list] == [
            CONTACTS_BATCH_READ_URL,
            CONTACTS_UPSERT_URL,
            CONTACTS_BATCH_READ_URL,
        ]
        budgets = [call.kwargs["retry_sleep_budget"] for call in fetch.call_args_list]
        assert all(budget is budgets[0] for budget in budgets)
        row = result.result.data["results"][0]
        assert (row["status"], row["contact_id"]) == ("created", "9")

    @pytest.mark.asyncio
    async def test_none_property_value_clears_it(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "1", "new": False, "properties": {"email": "a@example.com"}}]}
        )

        await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "a@example.com", "properties": {"phone": None}}]}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"]["phone"] == ""

    @pytest.mark.asyncio
    async def test_upsert_never_writes_the_identifier_email(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "1", "new": False, "properties": {"email": "a@x.com"}}]}
        )

        await hubspot.execute_action(
            "upsert_contacts",
            {"contacts": [{"email": "a@x.com", "properties": {"email": "other@x.com", "jobtitle": "CTO"}}]},
            mock_context,
        )

        # The address only identifies the contact; writing it could replace the primary email of an alias match
        assert mock_context.fetch.call_args.kwargs["json"]["inputs"][0]["properties"] == {"jobtitle": "CTO"}

    @pytest.mark.asyncio
    async def test_results_without_email_matched_by_reading_contacts_back(self, mock_context):
        mock_context.fetch.side_effect = [
            HTTPError(404, "Not found"),
            ok({"results": [{"id": "9", "new": False, "properties": {"jobtitle": "CTO"}}]}),
            ok(
                {
                    "results": [
                        {"id": "9", "properties": {"email": "primary@x.com", "hs_additional_emails": "alt@x.com"}}
                    ]
                }
            ),
        ]

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "alt@x.com"}]}, mock_context)

        row = result.result.data["results"][0]
        assert (row["status"], row["contact_id"]) == ("updated", "9")
        read_call = fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)[0]
        assert read_call.kwargs["json"]["inputs"] == [{"id": "alt@x.com"}]

    @pytest.mark.asyncio
    async def test_matched_results_skip_the_read_back(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "1", "new": True, "properties": {"email": "a@x.com"}}]}
        )

        await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, mock_context)

        # Only the lookup before the upsert; no read-back after it
        assert len(fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("read_error", [HTTPError(500, "Server error"), aiohttp.ServerDisconnectedError()])
    async def test_unattributable_upsert_result_is_failed_not_updated(self, mock_context, read_error):
        mock_context.fetch.side_effect = [
            ok({"results": []}),
            ok({"results": [{"id": "9", "new": True, "properties": {}}, {"id": "8", "new": False, "properties": {}}]}),
            read_error,
        ]

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "a@x.com"}, {"email": "b@x.com"}]}, mock_context
        )

        rows = result.result.data["results"]
        assert [(r["status"], r["contact_id"]) for r in rows] == [("failed", None), ("failed", None)]
        assert all("retrying is safe" in r["error"] for r in rows)
        assert result.result.data["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("email", ["", "   "])
    async def test_blank_email_rejected_by_schema(self, mock_context, email):
        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": email}]}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_emails_rejected_before_calling_hubspot(self, mock_context):
        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "a@example.com"}, {"email": "A@example.com "}]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "a@example.com" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_emails_of_the_same_contact_rejected_before_upserting(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"results": [{"id": "9", "properties": {"email": "jo@x.com", "hs_additional_emails": "jo@old.com"}}]}
        )

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "jo@x.com"}, {"email": "jo@old.com"}]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "jo@x.com, jo@old.com" in result.result.message
        assert fetch_calls(mock_context, CONTACTS_UPSERT_URL) == []

    @pytest.mark.asyncio
    async def test_existing_contacts_matched_without_a_read_back(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"results": [{"id": "9", "properties": {"email": "jo@x.com"}}]}),
            ok({"results": [{"id": "9", "new": False, "properties": {"jobtitle": "CTO"}}]}),
        ]

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "jo@x.com", "properties": {"jobtitle": "CTO"}}]}, mock_context
        )

        assert (result.result.data["results"][0]["status"], result.result.data["results"][0]["contact_id"]) == (
            "updated",
            "9",
        )
        assert len(fetch_calls(mock_context, CONTACTS_BATCH_READ_URL)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lookup",
        [
            HTTPError(500, "Server error"),
            asyncio.TimeoutError(),
            ok({"status": "CANCELED", "results": []}),
            ok(
                {
                    "results": [],
                    "errors": [{"category": "VALIDATION_ERROR", "message": "Bad", "context": {"ids": ["b@x.com"]}}],
                },
                status=207,
            ),
        ],
    )
    async def test_failed_pre_lookup_aborts_before_upserting(self, mock_context, lookup):
        mock_context.fetch.side_effect = [lookup]

        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": "a@x.com"}, {"email": "b@x.com"}]}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "nothing was written" in result.result.message
        assert fetch_calls(mock_context, CONTACTS_UPSERT_URL) == []

    @pytest.mark.asyncio
    async def test_pre_lookup_with_no_matches_still_upserts(self, mock_context):
        mock_context.fetch.side_effect = [
            HTTPError(404, "Not found"),
            ok({"results": [{"id": "1", "new": True, "properties": {"email": "a@x.com"}}]}),
        ]

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "a@x.com"}]}, mock_context)

        assert result.result.data["results"][0]["status"] == "created"

    @pytest.mark.asyncio
    async def test_row_without_email_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"first_name": "Jo"}]}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_more_than_100_contacts_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action(
            "upsert_contacts", {"contacts": [{"email": f"{i}@example.com"} for i in range(101)]}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_rejected_upsert_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [ok({"results": []}), HTTPError(400, "Invalid email")]

        result = await hubspot.execute_action("upsert_contacts", {"contacts": [{"email": "bad"}]}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to upsert contacts: HTTP 400: Invalid email"
        assert len(fetch_calls(mock_context, CONTACTS_UPSERT_URL)) == 1


# ---- Create Association ----


class TestCreateAssociation:
    @pytest.mark.asyncio
    async def test_links_records_with_default_association(self, mock_context):
        mock_context.fetch.return_value = ok({"status": "COMPLETE", "results": []})

        result = await hubspot.execute_action(
            "create_association",
            {"from_object_type": "contacts", "from_object_id": "1", "to_object_type": "companies", "to_object_id": "2"},
            mock_context,
        )

        assert result.result.data["success"] is True
        call = mock_context.fetch.call_args
        assert call.args[0] == "https://api.hubapi.com/crm/v4/objects/contacts/1/associations/default/companies/2"
        assert call.kwargs["method"] == "PUT"
        # HubSpot answers 415 to this PUT without a JSON content type
        assert call.kwargs["headers"] == {"Content-Type": "application/json"}

    @pytest.mark.asyncio
    async def test_unsupported_object_type_rejected_by_schema(self, mock_context):
        result = await hubspot.execute_action(
            "create_association",
            {"from_object_type": "widgets", "from_object_id": "1", "to_object_type": "companies", "to_object_id": "2"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["from_object_id", "to_object_id"])
    async def test_non_numeric_record_id_rejected_before_any_request(self, mock_context, field):
        inputs = {
            "from_object_type": "contacts",
            "from_object_id": "1",
            "to_object_type": "companies",
            "to_object_id": "2",
        }
        inputs[field] = "1/../../../../../v3/objects/deals/99"

        result = await hubspot.execute_action("create_association", inputs, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "Object not found")

        result = await hubspot.execute_action(
            "create_association",
            {"from_object_type": "contacts", "from_object_id": "1", "to_object_type": "deals", "to_object_id": "9"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "contacts 1" in result.result.message


# ---- Connection errors on single-record actions ----


class TestConnectionErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [aiohttp.ServerDisconnectedError(), asyncio.TimeoutError()])
    @pytest.mark.parametrize(
        "action,inputs",
        [
            ("get_linkedin_message", {"communication_id": "1"}),
            ("update_linkedin_message", {"communication_id": "1", "message_body": "x"}),
            ("delete_linkedin_message", {"communication_id": "1"}),
            (
                "create_association",
                {
                    "from_object_type": "contacts",
                    "from_object_id": "1",
                    "to_object_type": "companies",
                    "to_object_id": "2",
                },
            ),
        ],
    )
    async def test_connection_error_returns_action_error(self, mock_context, action, inputs, error):
        mock_context.fetch.side_effect = error

        result = await hubspot.execute_action(action, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.split(": ", 1)[1]
