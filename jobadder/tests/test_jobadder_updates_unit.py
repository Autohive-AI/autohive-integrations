import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import jobadder


pytestmark = pytest.mark.unit


def response(data=None, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def list_payload(items=None, total=0):
    return {
        "items": items or [],
        "totalCount": total,
        "links": {"self": "https://au-api.jobadder.com/v2/example"},
    }


class TestUpdateCandidate:
    async def test_maps_supplied_fields_and_returns_candidate_id(self, mock_context):
        mock_context.fetch.return_value = response()

        result = await jobadder.execute_action(
            "update_candidate",
            {
                "candidate_id": 21,
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@example.com",
                "status_id": 8,
                "unsubscribed": False,
                "allow_duplicates": "override-code",
            },
            mock_context,
        )

        assert result.result.data == {"updated": True, "candidate_id": 21}
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/candidates/21",
            method="PUT",
            headers={"Content-Type": "application/json", "X-Allow-Duplicates": "override-code"},
            json={
                "firstName": "John",
                "lastName": "Smith",
                "email": "john.smith@example.com",
                "statusId": 8,
                "unsubscribed": False,
            },
        )

    async def test_preserves_explicit_null_to_clear_field(self, mock_context):
        mock_context.fetch.return_value = response()

        await jobadder.execute_action("update_candidate", {"candidate_id": 21, "email": None}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"] == {"email": None}

    async def test_rejects_empty_update_before_fetch(self, mock_context):
        result = await jobadder.execute_action("update_candidate", {"candidate_id": 21}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "at least one candidate field" in result.result.message
        mock_context.fetch.assert_not_awaited()

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("candidate update failed")

        result = await jobadder.execute_action(
            "update_candidate", {"candidate_id": 21, "first_name": "John"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "candidate update failed" in result.result.message


class TestUpdateContact:
    async def test_maps_supplied_fields_and_returns_contact_id(self, mock_context):
        mock_context.fetch.return_value = response()

        result = await jobadder.execute_action(
            "update_contact",
            {
                "contact_id": 51,
                "company_id": 9,
                "first_name": "Morgan",
                "last_name": "Lee",
                "email": "morgan.lee@example.com",
                "status_id": 4,
                "custom_fields": [{"fieldId": 7, "value": "Enriched"}],
            },
            mock_context,
        )

        assert result.result.data == {"updated": True, "contact_id": 51}
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/contacts/51",
            method="PUT",
            headers={"Content-Type": "application/json"},
            json={
                "companyId": 9,
                "firstName": "Morgan",
                "lastName": "Lee",
                "email": "morgan.lee@example.com",
                "statusId": 4,
                "custom": [{"fieldId": 7, "value": "Enriched"}],
            },
        )

    async def test_preserves_false_and_explicit_null(self, mock_context):
        mock_context.fetch.return_value = response()

        await jobadder.execute_action(
            "update_contact", {"contact_id": 51, "summary": None, "unsubscribed": False}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"summary": None, "unsubscribed": False}

    async def test_rejects_empty_update_before_fetch(self, mock_context):
        result = await jobadder.execute_action("update_contact", {"contact_id": 51}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "at least one contact field" in result.result.message
        mock_context.fetch.assert_not_awaited()

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("contact update failed")

        result = await jobadder.execute_action("update_contact", {"contact_id": 51, "email": "x@y.nz"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "contact update failed" in result.result.message


@pytest.mark.parametrize(
    "action,path",
    [
        ("list_candidate_statuses", "/candidates/lists/status"),
        ("list_contact_statuses", "/contacts/lists/status"),
    ],
)
class TestListStatuses:
    async def test_maps_filters_and_returns_statuses(self, mock_context, action, path):
        statuses = [{"statusId": 8, "name": "Inactive", "active": False}]
        mock_context.fetch.return_value = response(list_payload(statuses, 1))

        result = await jobadder.execute_action(
            action,
            {"status_ids": [8, 9], "name": "Inactive", "active": False, "default": False},
            mock_context,
        )

        assert result.result.data == {
            "statuses": statuses,
            "total_count": 1,
            "links": {"self": "https://au-api.jobadder.com/v2/example"},
        }
        call = mock_context.fetch.call_args
        assert call.args[0] == f"https://au-api.jobadder.com/v2{path}?StatusId=8&StatusId=9"
        assert call.kwargs == {
            "method": "GET",
            "params": {"Name": "Inactive", "Active": "false", "Default": "false"},
        }

    async def test_omits_empty_filters(self, mock_context, action, path):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(action, {}, mock_context)

        mock_context.fetch.assert_awaited_once_with(f"https://au-api.jobadder.com/v2{path}", method="GET")

    async def test_exception_returns_action_error(self, mock_context, action, path):
        mock_context.fetch.side_effect = Exception(f"{path} unavailable")

        result = await jobadder.execute_action(action, {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unavailable" in result.result.message


@pytest.mark.parametrize(
    "action,id_field,record_id,path",
    [
        ("set_candidate_status", "candidate_id", 21, "/candidates/21/status"),
        ("set_contact_status", "contact_id", 51, "/contacts/51/status"),
    ],
)
class TestSetStatus:
    async def test_sets_status_and_returns_ids(self, mock_context, action, id_field, record_id, path):
        mock_context.fetch.return_value = response()

        result = await jobadder.execute_action(action, {id_field: record_id, "status_id": 8}, mock_context)

        assert result.result.data == {"updated": True, id_field: record_id, "status_id": 8}
        mock_context.fetch.assert_awaited_once_with(
            f"https://au-api.jobadder.com/v2{path}",
            method="PUT",
            headers={"Content-Type": "application/json"},
            json={"statusId": 8},
        )

    async def test_exception_returns_action_error(self, mock_context, action, id_field, record_id, path):
        mock_context.fetch.side_effect = Exception(f"{path} failed")

        result = await jobadder.execute_action(action, {id_field: record_id, "status_id": 8}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "failed" in result.result.message
