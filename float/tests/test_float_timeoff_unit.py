import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

float_integration = _mod.float

pytestmark = pytest.mark.unit

SAMPLE_TIMEOFF = {
    "timeoff_id": 200,
    "people_id": 123,
    "timeoff_type_id": 1,
    "start_date": "2025-02-01",
    "end_date": "2025-02-05",
    "hours": 8.0,
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {
            "api_key": "test_api_key",  # nosec B105
            "application_name": "Test App",
            "contact_email": "test@example.com",
        }
    }
    return ctx


# ---- List Time Off ----


class TestListTimeOff:
    @pytest.mark.asyncio
    async def test_list_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TIMEOFF])

        result = await float_integration.execute_action("list_time_off", {}, mock_context)

        assert result.result.data[0]["timeoff_id"] == 200

    @pytest.mark.asyncio
    async def test_list_time_off_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_time_off", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/timeoffs")

    @pytest.mark.asyncio
    async def test_list_time_off_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await float_integration.execute_action("list_time_off", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message


# ---- Get Time Off ----


class TestGetTimeOff:
    @pytest.mark.asyncio
    async def test_get_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIMEOFF)

        result = await float_integration.execute_action("get_time_off", {"timeoff_id": 200}, mock_context)

        assert result.result.data["timeoff_id"] == 200

    @pytest.mark.asyncio
    async def test_get_time_off_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIMEOFF)

        await float_integration.execute_action("get_time_off", {"timeoff_id": 200}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/timeoffs/200")

    @pytest.mark.asyncio
    async def test_get_time_off_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_time_off", {"timeoff_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Create Time Off ----


class TestCreateTimeOff:
    @pytest.mark.asyncio
    async def test_create_time_off_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201, headers={}, data={**SAMPLE_TIMEOFF, "timeoff_id": 300}
        )

        result = await float_integration.execute_action(
            "create_time_off",
            {
                "people_id": 123,
                "timeoff_type_id": 1,
                "start_date": "2025-02-01",
                "end_date": "2025-02-05",
                "hours": 8.0,
            },
            mock_context,
        )

        assert result.result.data["timeoff_id"] == 300

    @pytest.mark.asyncio
    async def test_create_time_off_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_TIMEOFF)

        await float_integration.execute_action(
            "create_time_off",
            {
                "people_id": 123,
                "timeoff_type_id": 1,
                "start_date": "2025-02-01",
                "end_date": "2025-02-05",
                "hours": 8.0,
                "full_day": True,
            },
            mock_context,
        )

        body = mock_context.fetch.call_args.kwargs.get("json", {})
        assert body["people_id"] == 123
        assert body["full_day"] is True

    @pytest.mark.asyncio
    async def test_create_time_off_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Conflict")

        result = await float_integration.execute_action(
            "create_time_off",
            {"people_id": 1, "timeoff_type_id": 1, "start_date": "2025-01-01", "end_date": "2025-01-02", "hours": 8},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Update Time Off ----


class TestUpdateTimeOff:
    @pytest.mark.asyncio
    async def test_update_time_off_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIMEOFF)

        await float_integration.execute_action("update_time_off", {"timeoff_id": 200, "hours": 4.0}, mock_context)

        assert mock_context.fetch.call_args.kwargs.get("method") == "PATCH"

    @pytest.mark.asyncio
    async def test_update_time_off_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update error")

        result = await float_integration.execute_action("update_time_off", {"timeoff_id": 200}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Delete Time Off ----


class TestDeleteTimeOff:
    @pytest.mark.asyncio
    async def test_delete_time_off_success(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_time_off", {"timeoff_id": 200}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_time_off_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete failed")

        result = await float_integration.execute_action("delete_time_off", {"timeoff_id": 200}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
