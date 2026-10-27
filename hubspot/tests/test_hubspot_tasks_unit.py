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


TASKS_API_URL = "https://api.hubapi.com/crm/v3/objects/tasks"

SAMPLE_TASK_RESPONSE = {
    "id": "23456",
    "properties": {
        "hs_task_body": "Test task content",
        "hs_timestamp": "1700000000000",
        "hs_createdate": "2025-01-15T10:00:00.000Z",
    },
}


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_with_contact_association(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        result = await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Follow up tomorrow",
                "hs_timestamp": 1700000000000,
                "contact_id": "501",
            },
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["task"] == SAMPLE_TASK_RESPONSE

        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.args[0] == TASKS_API_URL
        assert call_kwargs.kwargs["method"] == "POST"
        payload = call_kwargs.kwargs["json"]
        assert payload["properties"]["hs_task_body"] == "Follow up tomorrow"
        assert payload["associations"][0]["to"]["id"] == "501"

    @pytest.mark.asyncio
    async def test_create_task_multiple_associations(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Multi-assoc task",
                "hs_timestamp": 1700000000000,
                "contact_id": "100",
                "company_id": "200",
                "deal_id": "300",
            },
            mock_context,
        )

        associations = mock_context.fetch.call_args.kwargs["json"]["associations"]
        assert len(associations) == 3
        assert [a["types"][0]["associationTypeId"] for a in associations] == [
            204,
            192,
            216,
        ]

    @pytest.mark.asyncio
    async def test_create_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Will fail",
                "hs_timestamp": 1700000000000,
                "contact_id": "501",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to create task" in result.result.message

    @pytest.mark.asyncio
    async def test_create_task_with_direct_associations_object(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        await hubspot.execute_action(
            "create_task",
            {
                "hs_task_body": "Task with direct associations",
                "hs_timestamp": 1700000000000,
                "associations": [
                    {
                        "to": {"id": "501"},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 204,
                            }
                        ],
                    }
                ],
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["associations"][0]["to"]["id"] == "501"
        assert payload["associations"][0]["types"][0]["associationTypeId"] == 204

    @pytest.mark.asyncio
    async def test_create_task_without_timestamp_returns_validation_error(self, mock_context):
        result = await hubspot.execute_action("create_task", {"hs_task_body": "No timestamp"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "hs_timestamp" in result.result["message"]
        mock_context.fetch.assert_not_called()


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_task_body(self, mock_context):
        updated_response = {
            "id": "23456",
            "properties": {"hs_task_body": "Updated content"},
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated_response)

        result = await hubspot.execute_action(
            "update_task",
            {"hs_object_id": "23456", "hs_task_body": "Updated content"},
            mock_context,
        )

        assert result.result.data["success"] is True
        assert result.result.data["task"] == updated_response
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_update_task_additional_properties(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        result = await hubspot.execute_action(
            "update_task",
            {
                "hs_object_id": "23456",
                "hs_task_body": "Body",
                "additional_properties": {"hs_task_priority": "HIGH"},
            },
            mock_context,
        )

        props = mock_context.fetch.call_args.kwargs["json"]["properties"]
        assert props["hs_task_body"] == "Body"
        assert props["hs_task_priority"] == "HIGH"
        assert result.result.data["updated_properties"]["hs_task_priority"] == "HIGH"

    @pytest.mark.asyncio
    async def test_update_task_no_properties_returns_action_error(self, mock_context):
        result = await hubspot.execute_action("update_task", {"hs_object_id": "23456"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "No properties provided to update"
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action(
            "update_task",
            {"hs_object_id": "23456", "hs_task_body": "Will fail"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to update task" in result.result.message


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await hubspot.execute_action("delete_task", {"hs_object_id": "23456"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["hs_object_id"] == "23456"
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_delete_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action("delete_task", {"hs_object_id": "99999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to delete task" in result.result.message


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_task_success(self, mock_context):
        response_data = {
            "id": "23456",
            "properties": {
                "hs_task_body": "Task body",
                "hs_timestamp": "1700000000000",
                "hs_createdate": "1700000000000",
                "hs_lastmodifieddate": "1700000100000",
            },
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await hubspot.execute_action("get_task", {"hs_object_id": "23456"}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["task"]["id"] == "23456"
        assert mock_context.fetch.call_args.args[0] == f"{TASKS_API_URL}/23456"
        params = mock_context.fetch.call_args.kwargs["params"]
        assert "properties" in params
        # Default property set matches create_task / update_task fields
        assert "hs_task_type" in params["properties"]
        assert "hubspot_owner_id" in params["properties"]
        assert "hs_task_reminders" in params["properties"]

    @pytest.mark.asyncio
    async def test_get_task_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await hubspot.execute_action("get_task", {"hs_object_id": "bad-id"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve task" in result.result.message


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_context):
        response_data = {
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "hs_task_body": "Task 1",
                        "hs_timestamp": "1700000000000",
                    },
                },
                {
                    "id": "2",
                    "properties": {
                        "hs_task_body": "Task 2",
                        "hs_timestamp": "1700000100000",
                    },
                },
            ],
            "paging": {"next": {"after": "abc123"}},
        }
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=response_data)

        result = await hubspot.execute_action("list_tasks", {"limit": 2}, mock_context)

        assert result.result.data["success"] is True
        assert result.result.data["total"] == 2
        assert len(result.result.data["tasks"]) == 2
        assert result.result.data["paging"]["next"]["after"] == "abc123"
        assert mock_context.fetch.call_args.args[0] == TASKS_API_URL
        list_params = mock_context.fetch.call_args.kwargs["params"]
        assert list_params["limit"] == 2
        assert "hs_task_type" in list_params["properties"]
        assert "hubspot_owner_id" in list_params["properties"]
        assert "hs_task_reminders" in list_params["properties"]

    @pytest.mark.asyncio
    async def test_list_tasks_default_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("list_tasks", {}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_list_tasks_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await hubspot.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to retrieve tasks" in result.result.message


TASKS_SEARCH_URL = f"{TASKS_API_URL}/search"
OWNERS_URL = "https://api.hubapi.com/crm/v3/owners/"


def _association_batch_response(rows):
    """v4 association batch read body: rows of (task ID, [linked record IDs])."""
    return {
        "status": "COMPLETE",
        "results": [
            {
                "from": {"id": task_id},
                "to": [
                    {
                        "toObjectId": int(linked_id),
                        "associationTypes": [{"category": "HUBSPOT_DEFINED", "typeId": 204, "label": None}],
                    }
                    for linked_id in linked_ids
                ],
            }
            for task_id, linked_ids in rows
        ],
    }


SEARCH_RESPONSE = {
    "total": 412,
    "results": [
        {
            "id": "11",
            "properties": {"hs_task_subject": "Call Acme", "hs_timestamp": "2026-10-26T20:00:00Z"},
        },
        {
            "id": "12",
            "properties": {"hs_task_subject": "Send quote", "hs_timestamp": "1793131200000"},
        },
    ],
    "paging": {"next": {"after": "2"}},
}


def _search_then_associations(contacts_rows, companies_rows, deals_rows, search_response=SEARCH_RESPONSE):
    return [
        FetchResponse(status=200, headers={}, data=search_response),
        FetchResponse(status=207, headers={}, data=_association_batch_response(contacts_rows)),
        FetchResponse(status=200, headers={}, data=_association_batch_response(companies_rows)),
        FetchResponse(status=200, headers={}, data=_association_batch_response(deals_rows)),
    ]


class TestListTasksSearch:
    @pytest.mark.asyncio
    async def test_owner_open_and_due_filters_search_by_due_date(self, mock_context):
        mock_context.fetch.side_effect = _search_then_associations([("11", ["501"])], [], [])

        result = await hubspot.execute_action(
            "list_tasks",
            {
                "owner_id": "77",
                "exclude_completed": True,
                "due_before": "2026-10-28T00:00:00+13:00",
                "limit": 50,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        search_call = mock_context.fetch.call_args_list[0]
        assert search_call.args[0] == TASKS_SEARCH_URL
        assert search_call.kwargs["method"] == "POST"
        payload = search_call.kwargs["json"]
        assert payload["filterGroups"] == [
            {
                "filters": [
                    {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "77"},
                    {"propertyName": "hs_task_status", "operator": "NEQ", "value": "COMPLETED"},
                    # Local midnight in New Zealand (UTC+13) is 11:00 UTC the day before
                    {"propertyName": "hs_timestamp", "operator": "LT", "value": "1793098800000"},
                ]
            }
        ]
        assert payload["sorts"] == [{"propertyName": "hs_timestamp", "direction": "ASCENDING"}]
        assert payload["limit"] == 50
        assert "hs_task_subject" in payload["properties"]
        assert "after" not in payload
        assert "query" not in payload

        data = result.result.data
        assert data["total"] == 2
        assert data["total_matching"] == 412
        assert data["paging"] == {"next": {"after": "2"}}
        assert data["tasks"][0]["properties"]["hs_timestamp"] == "26 Oct 2026 08:00 PM UTC"
        assert data["tasks"][1]["properties"]["hs_timestamp"] == "27 Oct 2026 08:00 PM UTC"

    @pytest.mark.asyncio
    async def test_search_results_include_linked_records(self, mock_context):
        mock_context.fetch.side_effect = _search_then_associations(
            [("11", ["501", "502"])], [("12", ["601"])], [("11", ["701"])]
        )

        result = await hubspot.execute_action("list_tasks", {"owner_id": "77"}, mock_context)

        association_calls = mock_context.fetch.call_args_list[1:]
        assert [call.args[0] for call in association_calls] == [
            "https://api.hubapi.com/crm/associations/2026-09/tasks/contacts/batch/read",
            "https://api.hubapi.com/crm/associations/2026-09/tasks/companies/batch/read",
            "https://api.hubapi.com/crm/associations/2026-09/tasks/deals/batch/read",
        ]
        for call in association_calls:
            assert call.kwargs["method"] == "POST"
            assert call.kwargs["json"] == {"inputs": [{"id": "11"}, {"id": "12"}]}

        tasks = {task["id"]: task for task in result.result.data["tasks"]}
        assert tasks["11"]["associations"] == {
            "contacts": {"results": [{"id": "501"}, {"id": "502"}]},
            "deals": {"results": [{"id": "701"}]},
        }
        assert tasks["12"]["associations"] == {"companies": {"results": [{"id": "601"}]}}

    @pytest.mark.asyncio
    async def test_status_priority_type_and_linked_record_filters(self, mock_context):
        mock_context.fetch.side_effect = _search_then_associations([], [], [])

        await hubspot.execute_action(
            "list_tasks",
            {
                "status": ["NOT_STARTED", "WAITING"],
                "priority": ["HIGH"],
                "task_type": ["CALL"],
                "due_after": 1793098800000,
                "deal_id": "900",
                "sort_direction": "DESCENDING",
                "after": "200",
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args_list[0].kwargs["json"]
        assert payload["filterGroups"][0]["filters"] == [
            {"propertyName": "hs_task_status", "operator": "IN", "values": ["NOT_STARTED", "WAITING"]},
            {"propertyName": "hs_task_priority", "operator": "IN", "values": ["HIGH"]},
            {"propertyName": "hs_task_type", "operator": "IN", "values": ["CALL"]},
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": "1793098800000"},
            {"propertyName": "associations.deal", "operator": "EQ", "value": "900"},
        ]
        assert payload["sorts"] == [{"propertyName": "hs_timestamp", "direction": "DESCENDING"}]
        assert payload["after"] == "200"

    @pytest.mark.asyncio
    async def test_text_query_alone_searches_without_filters(self, mock_context):
        mock_context.fetch.side_effect = _search_then_associations([], [], [])

        await hubspot.execute_action("list_tasks", {"query": "renewal"}, mock_context)

        payload = mock_context.fetch.call_args_list[0].kwargs["json"]
        assert payload["query"] == "renewal"
        assert "filterGroups" not in payload

    @pytest.mark.asyncio
    async def test_no_matches_skips_association_lookup(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"total": 0, "results": []})

        result = await hubspot.execute_action("list_tasks", {"owner_id": "77"}, mock_context)

        assert result.result.data["tasks"] == []
        assert result.result.data["total_matching"] == 0
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_owner_email_is_resolved_to_owner_id(self, mock_context):
        owners = {"results": [{"id": "77", "email": "jd@example.com"}]}
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=owners),
            *_search_then_associations([], [], []),
        ]

        result = await hubspot.execute_action(
            "list_tasks", {"owner_email": "jd@example.com", "exclude_completed": True}, mock_context
        )

        assert result.type == ResultType.ACTION
        owner_call = mock_context.fetch.call_args_list[0]
        assert owner_call.args[0] == OWNERS_URL
        assert owner_call.kwargs["params"] == {"email": "jd@example.com"}
        filters = mock_context.fetch.call_args_list[1].kwargs["json"]["filterGroups"][0]["filters"]
        assert filters[0] == {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "77"}

    @pytest.mark.asyncio
    async def test_owner_id_takes_precedence_over_owner_email(self, mock_context):
        mock_context.fetch.side_effect = _search_then_associations([], [], [])

        await hubspot.execute_action("list_tasks", {"owner_id": "5", "owner_email": "jd@example.com"}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0] == TASKS_SEARCH_URL
        filters = mock_context.fetch.call_args_list[0].kwargs["json"]["filterGroups"][0]["filters"]
        assert filters == [{"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "5"}]

    @pytest.mark.asyncio
    async def test_unknown_owner_email_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await hubspot.execute_action("list_tasks", {"owner_email": "nobody@example.com"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "No HubSpot owner has the email nobody@example.com"
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_unreadable_due_date_returns_action_error(self, mock_context):
        result = await hubspot.execute_action("list_tasks", {"due_before": "next tuesday"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "due_before must be Unix milliseconds or an ISO 8601 date" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_more_than_six_filters_returns_action_error(self, mock_context):
        result = await hubspot.execute_action(
            "list_tasks",
            {
                "owner_id": "77",
                "exclude_completed": True,
                "priority": ["HIGH"],
                "task_type": ["CALL"],
                "due_after": "2026-10-01",
                "due_before": "2026-11-01",
                "contact_id": "501",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "at most 6 task filters" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_status_value_is_rejected(self, mock_context):
        result = await hubspot.execute_action("list_tasks", {"status": ["OPEN"]}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("400 Bad Request")

        result = await hubspot.execute_action("list_tasks", {"owner_id": "77"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to search tasks: 400 Bad Request"

    @pytest.mark.asyncio
    async def test_association_failure_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SEARCH_RESPONSE),
            Exception("403 Forbidden"),
        ]

        result = await hubspot.execute_action("list_tasks", {"owner_id": "77"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "Failed to search tasks: 403 Forbidden"

    @pytest.mark.asyncio
    async def test_paging_cursor_alone_keeps_listing(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await hubspot.execute_action("list_tasks", {"after": "abc123", "exclude_completed": False}, mock_context)

        assert mock_context.fetch.call_args.args[0] == TASKS_API_URL
        assert mock_context.fetch.call_args.kwargs["params"]["after"] == "abc123"


class TestCreateTaskOptionalBody:
    @pytest.mark.asyncio
    async def test_create_task_without_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TASK_RESPONSE)

        result = await hubspot.execute_action(
            "create_task",
            {"hs_task_subject": "Call back", "hs_timestamp": 1700000000000},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        properties = mock_context.fetch.call_args.kwargs["json"]["properties"]
        assert properties == {"hs_timestamp": "1700000000000", "hs_task_subject": "Call back"}
