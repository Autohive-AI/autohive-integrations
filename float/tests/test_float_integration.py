"""
Integration tests for the Float integration (read-only actions).

Requires FLOAT_API_KEY set in environment.

Run with:
    pytest float/tests/test_float_integration.py -m integration
"""
import importlib.util
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(_parent)
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["float_mod"] = _mod

float_integration = _mod.float

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("FLOAT_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("FLOAT_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, headers=headers or {}, params=params
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {
        "credentials": {
            "api_key": API_KEY,
            "application_name": os.environ.get("FLOAT_APP_NAME", "Autohive Float Integration"),
            "contact_email": os.environ.get("FLOAT_CONTACT_EMAIL", ""),
        }
    }
    return ctx


@pytest.mark.asyncio
async def test_list_people(live_context):
    result = await float_integration.execute_action("list_people", {}, live_context)
    assert result.result is not None


@pytest.mark.asyncio
async def test_list_projects(live_context):
    result = await float_integration.execute_action("list_projects", {}, live_context)
    assert result.result is not None


@pytest.mark.asyncio
async def test_list_clients(live_context):
    result = await float_integration.execute_action("list_clients", {}, live_context)
    assert result.result is not None


@pytest.mark.asyncio
async def test_list_departments(live_context):
    result = await float_integration.execute_action("list_departments", {}, live_context)
    assert result.result is not None


@pytest.mark.asyncio
async def test_list_roles(live_context):
    result = await float_integration.execute_action("list_roles", {}, live_context)
    assert result.result is not None
