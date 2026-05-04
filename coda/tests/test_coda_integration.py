"""
Integration tests for the Coda integration (read-only actions).

Requires CODA_API_KEY set in environment or .env file.

Run with:
    pytest coda/tests/test_coda_integration.py -m integration
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("coda_mod_integration", os.path.join(_parent, "coda.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

coda = _mod.coda

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("CODA_API_KEY", "")


@pytest.fixture
def live_context():
    if not API_KEY:
        pytest.skip("CODA_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                data = await resp.json()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_token": API_KEY}}  # nosec B105
    return ctx


class TestListDocsLive:
    async def test_returns_docs_list(self, live_context):
        result = await coda.execute_action("list_docs", {}, live_context)

        data = result.result.data
        assert "docs" in data
        assert isinstance(data["docs"], list)

    async def test_filter_by_query(self, live_context):
        result = await coda.execute_action("list_docs", {"query": "test"}, live_context)

        data = result.result.data
        assert "docs" in data

    async def test_is_owner_filter(self, live_context):
        result = await coda.execute_action("list_docs", {"is_owner": True}, live_context)

        data = result.result.data
        assert "docs" in data
