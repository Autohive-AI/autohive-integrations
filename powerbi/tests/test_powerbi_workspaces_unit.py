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


# ---- Workspaces ----


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "value": [
                    {
                        "id": "ws-1",
                        "name": "My Workspace",
                        "isReadOnly": False,
                        "isOnDedicatedCapacity": False,
                        "type": "Workspace",
                    }
                ]
            },
        )

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.result.data["workspaces"][0]["id"] == "ws-1"
        assert result.result.data["workspaces"][0]["name"] == "My Workspace"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == f"{POWERBI_API_BASE}/groups"

    @pytest.mark.asyncio
    async def test_filter_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {"filter": "type eq 'Workspace'"}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["params"]["$filter"] == "type eq 'Workspace'"

    @pytest.mark.asyncio
    async def test_top_param_passed(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        await powerbi.execute_action("list_workspaces", {"top": 50}, mock_context)

        call_args = mock_context.fetch.call_args
        assert call_args.kwargs["params"]["$top"] == 50

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"value": []})

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.result.data["workspaces"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await powerbi.execute_action("list_workspaces", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        ws = {"id": "ws-1", "name": "Sales", "isReadOnly": False}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ws)

        result = await powerbi.execute_action("get_workspace", {"workspace_id": "ws-1"}, mock_context)

        assert result.result.data["workspace"]["id"] == "ws-1"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await powerbi.execute_action("get_workspace", {"workspace_id": "ws-abc"}, mock_context)

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-abc"

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        ws = {"id": "ws-1", "name": "Sales", "isReadOnly": True, "type": "Workspace"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=ws)

        result = await powerbi.execute_action("get_workspace", {"workspace_id": "ws-1"}, mock_context)

        assert "workspace" in result.result.data
        assert result.result.data["workspace"]["name"] == "Sales"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await powerbi.execute_action("get_workspace", {"workspace_id": "ws-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message
