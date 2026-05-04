"""
Unit tests for the Float integration using mocked fetch.
"""

import importlib.util
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["float_mod"] = _mod

float_integration = _mod.float

pytestmark = pytest.mark.unit

TEST_AUTH = {"credentials": {"api_key": "test_key"}}


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def err(status, msg):
    return FetchResponse(status=status, headers={}, data={"message": msg})


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = TEST_AUTH
    return ctx


@pytest.mark.asyncio
async def test_list_people_returns_data():
    ctx = make_ctx([{"people_id": 1, "name": "Alice"}])
    result = await float_integration.execute_action("list_people", {}, ctx)
    assert result.result.data == [{"people_id": 1, "name": "Alice"}]
    ctx.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_list_people_with_filters():
    ctx = make_ctx([])
    await float_integration.execute_action("list_people", {"active": True, "page": 1, "per_page": 10}, ctx)
    call_kwargs = ctx.fetch.call_args
    params = call_kwargs.kwargs.get("params", {})
    assert params.get("active") == 1
    assert params.get("page") == 1
    assert params.get("per-page") == 10


@pytest.mark.asyncio
async def test_get_person_required_param():
    ctx = make_ctx({"people_id": 42, "name": "Bob"})
    result = await float_integration.execute_action("get_person", {"people_id": 42}, ctx)
    assert result.result.data == {"people_id": 42, "name": "Bob"}
    url = ctx.fetch.call_args.kwargs.get("url", ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else "")
    assert "42" in str(url)


@pytest.mark.asyncio
async def test_list_projects_returns_data():
    ctx = make_ctx([{"project_id": 1, "name": "Project A"}])
    result = await float_integration.execute_action("list_projects", {}, ctx)
    assert result.result.data == [{"project_id": 1, "name": "Project A"}]


@pytest.mark.asyncio
async def test_list_tasks_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_tasks", {}, ctx)
    assert result.result.data == []
    ctx.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_list_clients_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_clients", {}, ctx)
    assert result.result.data == []


@pytest.mark.asyncio
async def test_list_departments_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_departments", {}, ctx)
    assert result.result.data == []


@pytest.mark.asyncio
async def test_list_roles_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_roles", {}, ctx)
    assert result.result.data == []


@pytest.mark.asyncio
async def test_auth_headers_use_api_key():
    ctx = make_ctx({})
    await float_integration.execute_action("list_people", {}, ctx)
    headers = ctx.fetch.call_args.kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer test_key"


@pytest.mark.asyncio
async def test_delete_person_success():
    ctx = make_ctx({"success": True})
    result = await float_integration.execute_action("delete_person", {"people_id": 99}, ctx)
    assert result.result.data["success"] is True


@pytest.mark.asyncio
async def test_create_person_required_name():
    ctx = make_ctx({"people_id": 1, "name": "New Person"})
    result = await float_integration.execute_action("create_person", {"name": "New Person"}, ctx)
    assert result.result.data["name"] == "New Person"


@pytest.mark.asyncio
async def test_list_time_off_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_time_off", {}, ctx)
    assert result.result.data == []


@pytest.mark.asyncio
async def test_list_logged_time_no_params():
    ctx = make_ctx([])
    result = await float_integration.execute_action("list_logged_time", {}, ctx)
    assert result.result.data == []
