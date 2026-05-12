import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from toggl.toggl import toggl

pytestmark = pytest.mark.unit

SAMPLE_TIME_ENTRY = {
    "id": 1234567890,
    "workspace_id": 9876543,
    "description": "Working on feature X",
    "start": "2024-01-15T09:00:00Z",
    "stop": "2024-01-15T10:00:00Z",
    "duration": 3600,
    "project_id": 111222333,
    "billable": False,
    "created_with": "autohive-integrations",
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "api_token": "test_api_token_123",  # nosec B105
        },
    }
    return ctx


class TestCreateTimeEntry:
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        result = await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["id"] == 1234567890
        assert result.result.data["workspace_id"] == 9876543

    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        call_args = mock_context.fetch.call_args
        assert "9876543" in call_args.args[0]
        assert "time_entries" in call_args.args[0]
        assert call_args.kwargs["method"] == "POST"

    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z", "description": "Test task", "billable": True},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["workspace_id"] == 9876543
        assert payload["description"] == "Test task"
        assert payload["billable"] is True
        assert payload["created_with"] == "autohive-integrations"

    async def test_auth_header(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    async def test_missing_api_token_returns_action_error(self, mock_context):
        mock_context.auth = {"credentials": {"api_token": ""}}  # nosec B105

        result = await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "api_token" in result.result.message

    async def test_missing_credentials_returns_action_error(self, mock_context):
        mock_context.auth = {}

        result = await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "api_token" in result.result.message

    async def test_optional_fields_excluded_when_none(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert "stop" not in payload
        assert "project_id" not in payload
        assert "task_id" not in payload
        assert "tags" not in payload

    async def test_with_all_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIME_ENTRY)

        await toggl.execute_action(
            "create_time_entry",
            {
                "workspace_id": 9876543,
                "start": "2024-01-15T09:00:00Z",
                "stop": "2024-01-15T10:00:00Z",
                "duration": 3600,
                "description": "Full entry",
                "project_id": 111,
                "task_id": 222,
                "billable": True,
                "tags": ["work", "dev"],
                "tag_ids": [1, 2],
                "user_id": 333,
            },
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["stop"] == "2024-01-15T10:00:00Z"
        assert payload["duration"] == 3600
        assert payload["project_id"] == 111
        assert payload["task_id"] == 222
        assert payload["tags"] == ["work", "dev"]
        assert payload["tag_ids"] == [1, 2]
        assert payload["user_id"] == 333

    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"id": 999, "workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
        )

        result = await toggl.execute_action(
            "create_time_entry",
            {"workspace_id": 9876543, "start": "2024-01-15T09:00:00Z"},
            mock_context,
        )

        assert "id" in result.result.data
        assert "workspace_id" in result.result.data
