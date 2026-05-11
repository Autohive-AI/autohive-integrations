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

SAMPLE_PROJECT = {
    "project_id": 10,
    "name": "Acme Website",
    "active": True,
    "client_id": 5,
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


# ---- List Projects ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_projects_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[{"project_id": 10, "name": "Acme Website", "active": 1, "client_id": 5}],
        )

        result = await float_integration.execute_action("list_projects", {}, mock_context)

        assert result.result.data[0]["project_id"] == 10

    @pytest.mark.asyncio
    async def test_list_projects_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_projects", {}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/projects")

    @pytest.mark.asyncio
    async def test_list_projects_active_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await float_integration.execute_action("list_projects", {"active": False}, mock_context)

        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert params.get("active") == 0

    @pytest.mark.asyncio
    async def test_list_projects_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await float_integration.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- Get Project ----


class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_project_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        result = await float_integration.execute_action("get_project", {"project_id": 10}, mock_context)

        assert result.result.data["project_id"] == 10

    @pytest.mark.asyncio
    async def test_get_project_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        await float_integration.execute_action("get_project", {"project_id": 10}, mock_context)

        url = mock_context.fetch.call_args.kwargs.get("url", "")
        assert url.endswith("/projects/10")

    @pytest.mark.asyncio
    async def test_get_project_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await float_integration.execute_action("get_project", {"project_id": 999}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Create Project ----


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_project_happy_path(self, mock_context):
        created = {**SAMPLE_PROJECT, "project_id": 20}
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=created)

        result = await float_integration.execute_action("create_project", {"name": "New Project"}, mock_context)

        assert result.result.data["project_id"] == 20

    @pytest.mark.asyncio
    async def test_create_project_request_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PROJECT)

        await float_integration.execute_action(
            "create_project", {"name": "New Project", "client_id": 5, "active": 1}, mock_context
        )

        body = mock_context.fetch.call_args.kwargs.get("json", {})
        assert body["name"] == "New Project"
        assert body["client_id"] == 5

    @pytest.mark.asyncio
    async def test_create_project_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Create failed")

        result = await float_integration.execute_action("create_project", {"name": "X"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Create failed" in result.result.message


# ---- Update Project ----


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_update_project_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PROJECT)

        await float_integration.execute_action("update_project", {"project_id": 10, "name": "Updated"}, mock_context)

        assert mock_context.fetch.call_args.kwargs.get("method") == "PATCH"

    @pytest.mark.asyncio
    async def test_update_project_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Update failed")

        result = await float_integration.execute_action("update_project", {"project_id": 10}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Delete Project ----


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_delete_project_success_message(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await float_integration.execute_action("delete_project", {"project_id": 10}, mock_context)

        assert result.result.data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_project_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Delete failed")

        result = await float_integration.execute_action("delete_project", {"project_id": 10}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
