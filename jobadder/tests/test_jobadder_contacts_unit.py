from unittest.mock import AsyncMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import jobadder


pytestmark = pytest.mark.unit


def response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def list_payload(items=None, total_count=0):
    return {
        "items": items or [],
        "totalCount": total_count,
        "links": {"self": "https://au-api.jobadder.com/v2/resource"},
    }


class TestListContacts:
    @pytest.mark.asyncio
    async def test_returns_contacts(self, mock_context):
        contacts = [{"contactId": 51, "firstName": "Morgan", "lastName": "Lee"}]
        mock_context.fetch.return_value = response(list_payload(contacts, 1))

        result = await jobadder.execute_action("list_contacts", {}, mock_context)

        assert result.result.data == {
            "contacts": contacts,
            "total_count": 1,
            "links": {"self": "https://au-api.jobadder.com/v2/resource"},
        }

    @pytest.mark.asyncio
    async def test_maps_company_id_name_and_consultant_filters(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(
            "list_contacts",
            {
                "company_id": 9,
                "name": "Morgan",
                "email": "morgan@example.com",
                "phone": "123",
                "created_by_user_id": 7,
                "status_id": 4,
                "hiring_manager": False,
                "created_at": ">2026-01-01T00:00:00Z",
                "updated_at": "<2026-09-30T23:59:59Z",
                "offset": 20,
                "limit": 50,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/contacts")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "companyId": 9,
            "name": "Morgan",
            "email": "morgan@example.com",
            "phone": "123",
            "createdBy": 7,
            "statusId": 4,
            "hiringManager": "false",
            "createdAt": ">2026-01-01T00:00:00Z",
            "updatedAt": "<2026-09-30T23:59:59Z",
            "offset": 20,
            "limit": 50,
        }

    @pytest.mark.asyncio
    async def test_resolves_company_name_to_company_ids(self, mock_context):
        mock_context.fetch.side_effect = [
            response(list_payload([{"companyId": 9}, {"companyId": 10}], 2)),
            response(list_payload([{"contactId": 51}], 1)),
        ]

        result = await jobadder.execute_action("list_contacts", {"company_name": "Acme"}, mock_context)

        assert result.result.data["contacts"] == [{"contactId": 51}]
        assert mock_context.fetch.await_args_list[0].args[0].endswith("/companies")
        assert mock_context.fetch.await_args_list[0].kwargs["params"] == {
            "name": "Acme",
            "offset": 0,
            "limit": 1000,
        }
        assert mock_context.fetch.await_args_list[1].args[0].endswith("/contacts")
        assert mock_context.fetch.await_args_list[1].kwargs["params"]["companyId"] == [9, 10]

    @pytest.mark.asyncio
    async def test_company_name_with_no_matches_skips_contact_request(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        result = await jobadder.execute_action("list_contacts", {"company_name": "Missing"}, mock_context)

        assert result.result.data == {"contacts": [], "total_count": 0, "links": {}}
        assert mock_context.fetch.await_count == 1

    @pytest.mark.asyncio
    async def test_uses_default_pagination(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())
        await jobadder.execute_action("list_contacts", {}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"] == {"offset": 0, "limit": 100}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("contacts unavailable")
        result = await jobadder.execute_action("list_contacts", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "contacts unavailable" in result.result.message


class TestGetContact:
    @pytest.mark.asyncio
    async def test_returns_contact_and_uses_id(self, mock_context):
        contact = {"contactId": 51, "firstName": "Morgan"}
        mock_context.fetch.return_value = response(contact)

        result = await jobadder.execute_action("get_contact", {"contact_id": 51}, mock_context)

        assert result.result.data["contact"] == contact
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/contacts/51", method="GET")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("contact not found")
        result = await jobadder.execute_action("get_contact", {"contact_id": 51}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListContactNotes:
    @pytest.mark.asyncio
    async def test_returns_notes_from_contact_endpoint(self, mock_context):
        notes = [{"noteId": "11111111-1111-1111-1111-111111111111", "type": "Phone Call"}]
        mock_context.fetch.return_value = response(list_payload(notes, 1))

        result = await jobadder.execute_action("list_contact_notes", {"contact_id": 51}, mock_context)

        assert result.result.data["notes"] == notes
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/contacts/51/notes", method="GET")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("notes unavailable")
        result = await jobadder.execute_action("list_contact_notes", {"contact_id": 51}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListContactActivities:
    @pytest.mark.asyncio
    async def test_maps_contact_activity_filters_and_date_ranges(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(
            "list_contact_activities",
            {
                "contact_id": 51,
                "types": ["Phone Call", "Meeting"],
                "created_at_from": "2026-09-01T00:00:00Z",
                "created_at_to": "2026-09-30T23:59:59Z",
                "updated_at_from": "2026-09-15T00:00:00Z",
                "updated_at_to": "2026-09-30T23:59:59Z",
                "sort": "createdAt",
                "offset": 10,
                "limit": 25,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/notes")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "contactId": 51,
            "type": ["Phone Call", "Meeting"],
            "createdAt": [">2026-09-01T00:00:00Z", "<2026-09-30T23:59:59Z"],
            "updatedAt": [">2026-09-15T00:00:00Z", "<2026-09-30T23:59:59Z"],
            "sort": "createdAt",
            "fields": ["text"],
            "offset": 10,
            "limit": 25,
        }

    @pytest.mark.asyncio
    async def test_defaults_to_newest_first_and_requests_full_text(self, mock_context):
        activities = [{"noteId": "11111111-1111-1111-1111-111111111111", "text": "Called client"}]
        mock_context.fetch.return_value = response(list_payload(activities, 1))

        result = await jobadder.execute_action("list_contact_activities", {"contact_id": 51}, mock_context)

        assert result.result.data["activities"] == activities
        assert mock_context.fetch.call_args.kwargs["params"] == {
            "contactId": 51,
            "sort": "-createdAt",
            "fields": ["text"],
            "offset": 0,
            "limit": 100,
        }

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("activity search failed")
        result = await jobadder.execute_action("list_contact_activities", {"contact_id": 51}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListAllContactActivities:
    @pytest.mark.asyncio
    async def test_searches_notes_for_contacts_and_required_date_range(self, mock_context):
        activities = [{"noteId": "11111111-1111-1111-1111-111111111111", "text": "Met client"}]
        mock_context.fetch.return_value = response(list_payload(activities, 1))

        result = await jobadder.execute_action(
            "list_all_contact_activities",
            {
                "contact_ids": [51, 52],
                "created_at_from": "2026-09-01T00:00:00Z",
                "created_at_to": "2026-09-30T23:59:59Z",
                "limit": 500,
            },
            mock_context,
        )

        assert result.result.data["activities"] == activities
        assert mock_context.fetch.call_args.kwargs["params"] == {
            "contactId": [51, 52],
            "createdAt": [">2026-09-01T00:00:00Z", "<2026-09-30T23:59:59Z"],
            "sort": "-createdAt",
            "fields": ["text"],
            "offset": 0,
            "limit": 500,
        }

    @pytest.mark.asyncio
    async def test_excludes_notes_not_linked_to_requested_contacts(self, mock_context):
        contact_note = {
            "noteId": "11111111-1111-1111-1111-111111111111",
            "contactIds": [51],
            "text": "Met client",
        }
        candidate_note = {
            "noteId": "22222222-2222-2222-2222-222222222222",
            "candidateId": 88,
            "text": "Interviewed candidate",
        }
        provider_notes = [contact_note, candidate_note]

        async def fetch_filtered_notes(_url, *, params, **_kwargs):
            requested_contact_ids = set(params["contactId"])
            filtered_notes = [
                note for note in provider_notes if requested_contact_ids.intersection(note.get("contactIds", []))
            ]
            return response(list_payload(filtered_notes, len(filtered_notes)))

        mock_context.fetch.side_effect = fetch_filtered_notes

        result = await jobadder.execute_action(
            "list_all_contact_activities",
            {
                "contact_ids": [51, 52],
                "created_at_from": "2026-09-01T00:00:00Z",
                "created_at_to": "2026-09-30T23:59:59Z",
            },
            mock_context,
        )

        assert result.result.data["activities"] == [contact_note]
        assert candidate_note not in result.result.data["activities"]

    @pytest.mark.asyncio
    async def test_rejects_unbounded_report(self, mock_context):
        result = await jobadder.execute_action("list_all_contact_activities", {"contact_ids": [51, 52]}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_missing_contact_ids(self, mock_context):
        result = await jobadder.execute_action(
            "list_all_contact_activities",
            {
                "created_at_from": "2026-09-01T00:00:00Z",
                "created_at_to": "2026-09-30T23:59:59Z",
            },
            mock_context,
        )
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("report failed")
        result = await jobadder.execute_action(
            "list_all_contact_activities",
            {
                "contact_ids": [51, 52],
                "created_at_from": "2026-09-01T00:00:00Z",
                "created_at_to": "2026-09-30T23:59:59Z",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


class TestGetNote:
    @pytest.mark.asyncio
    async def test_returns_full_note(self, mock_context):
        note_id = "11111111-1111-1111-1111-111111111111"
        note = {"noteId": note_id, "text": "Full activity text"}
        mock_context.fetch.return_value = response(note)

        result = await jobadder.execute_action("get_note", {"note_id": note_id}, mock_context)

        assert result.result.data["note"] == note
        mock_context.fetch.assert_awaited_once_with(f"https://au-api.jobadder.com/v2/notes/{note_id}", method="GET")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("note not found")
        result = await jobadder.execute_action(
            "get_note", {"note_id": "11111111-1111-1111-1111-111111111111"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestListContactJobs:
    @pytest.mark.asyncio
    async def test_returns_associated_jobs(self, mock_context):
        jobs = [{"jobId": 11, "jobTitle": "Engineer"}]
        mock_context.fetch.return_value = response(list_payload(jobs, 1))

        result = await jobadder.execute_action("list_contact_jobs", {"contact_id": 51}, mock_context)

        assert result.result.data["jobs"] == jobs
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/contacts/51/jobs", method="GET")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("jobs unavailable")
        result = await jobadder.execute_action("list_contact_jobs", {"contact_id": 51}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCompanies:
    @pytest.mark.asyncio
    async def test_list_companies_maps_filters(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(
            "list_companies",
            {
                "name": "Acme",
                "status_id": 3,
                "created_by_user_id": 7,
                "created_at": ">2026-01-01T00:00:00Z",
                "updated_at": "<2026-09-30T23:59:59Z",
                "offset": 5,
                "limit": 10,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/companies")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "name": "Acme",
            "statusId": 3,
            "createdBy": 7,
            "createdAt": ">2026-01-01T00:00:00Z",
            "updatedAt": "<2026-09-30T23:59:59Z",
            "offset": 5,
            "limit": 10,
        }

    @pytest.mark.asyncio
    async def test_get_company_returns_company(self, mock_context):
        company = {"companyId": 9, "name": "Acme"}
        mock_context.fetch.return_value = response(company)

        result = await jobadder.execute_action("get_company", {"company_id": 9}, mock_context)

        assert result.result.data["company"] == company
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/companies/9", method="GET")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action,inputs", [("list_companies", {}), ("get_company", {"company_id": 9})])
    async def test_company_exception_returns_action_error(self, mock_context, action, inputs):
        mock_context.fetch = AsyncMock(side_effect=Exception("companies unavailable"))
        result = await jobadder.execute_action(action, inputs, mock_context)
        assert result.type == ResultType.ACTION_ERROR
