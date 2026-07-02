import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("powerbi_mod", os.path.join(_parent, "powerbi.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

powerbi = _mod.powerbi

pytestmark = pytest.mark.unit

POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Datasets ----


class TestListDatasets:
    @pytest.mark.asyncio
    async def test_happy_path_no_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "value": [{"id": "ds-1", "name": "Sales DS", "configuredBy": "user@test.com", "isRefreshable": True}]
            },
        )

        result = await powerbi.execute_action("list_datasets", {}, mock_context)

        assert result.result.data["datasets"][0]["id"] == "ds-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_datasets", {"workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_datasets", {}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/datasets"

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("list_datasets", {}, mock_context)

        assert result.result.data["datasets"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await powerbi.execute_action("list_datasets", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetDataset:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        ds = {"id": "ds-1", "name": "Sales"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ds)

        result = await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["dataset"]["id"] == "ds-1"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/datasets/ds-1"

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        ds = {"id": "ds-1", "name": "Sales", "isRefreshable": True}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ds)

        result = await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert "dataset" in result.result.data
        assert result.result.data["dataset"]["name"] == "Sales"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestRefreshDataset:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["message"] == "Dataset refresh initiated successfully"

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_default_notify_option(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["notifyOption"] == "NoNotification"

    @pytest.mark.asyncio
    async def test_notify_option_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action(
            "refresh_dataset", {"dataset_id": "ds-1", "notify_option": "MailOnFailure"}, mock_context
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["notifyOption"] == "MailOnFailure"

    @pytest.mark.asyncio
    async def test_request_id_from_headers(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={"x-ms-request-id": "req-123"}, data=None)

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["request_id"] == "req-123"

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data=None)

        await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/refreshes"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await powerbi.execute_action("refresh_dataset", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetRefreshHistory:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"value": [{"refreshType": "Full", "status": "Completed", "startTime": "2024-01-01T00:00:00Z"}]},
        )

        result = await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["refreshes"][0]["refreshType"] == "Full"

    @pytest.mark.asyncio
    async def test_top_param_sent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1", "top": 5}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 5

    @pytest.mark.asyncio
    async def test_default_top_is_10(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["$top"] == 10

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action(
            "get_refresh_history", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/refreshes"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await powerbi.execute_action("get_refresh_history", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
