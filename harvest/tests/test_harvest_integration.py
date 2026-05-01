"""
Integration tests for the Harvest integration.

These tests make real HTTP calls to the Harvest API.
Set HARVEST_ACCESS_TOKEN and HARVEST_ACCOUNT_ID environment variables to run.
"""

import os
import sys
import importlib.util

import pytest
import aiohttp

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("harvest_mod", os.path.join(_parent, "harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

harvest = _mod.harvest

pytestmark = pytest.mark.integration

HARVEST_ACCESS_TOKEN = os.environ.get("HARVEST_ACCESS_TOKEN", "")
HARVEST_ACCOUNT_ID = os.environ.get("HARVEST_ACCOUNT_ID", "")

skip_if_no_creds = pytest.mark.skipif(
    not HARVEST_ACCESS_TOKEN or not HARVEST_ACCOUNT_ID,
    reason="HARVEST_ACCESS_TOKEN and HARVEST_ACCOUNT_ID env vars required",
)


async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
    auth_headers = {
        "Authorization": f"Bearer {HARVEST_ACCESS_TOKEN}",
        "Harvest-Account-Id": HARVEST_ACCOUNT_ID,
        "User-Agent": "AutohiveIntegrations/1.0",
    }
    merged_headers = {**auth_headers, **(headers or {})}
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, json=json, headers=merged_headers, params=params) as resp:
            data = await resp.json(content_type=None)
            return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)


class MockContext:
    def __init__(self):
        self.auth = {
            "credentials": {
                "access_token": HARVEST_ACCESS_TOKEN,
                "account_id": HARVEST_ACCOUNT_ID,
            }
        }
        self.fetch = real_fetch


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_time_entries():
    ctx = MockContext()
    result = await harvest.execute_action("list_time_entries", {"per_page": 5}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "time_entries" in data
    assert "total_entries" in data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_projects():
    ctx = MockContext()
    result = await harvest.execute_action("list_projects", {"per_page": 5}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "projects" in data
    assert "total_entries" in data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_clients():
    ctx = MockContext()
    result = await harvest.execute_action("list_clients", {"per_page": 5}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "clients" in data
    assert "total_entries" in data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_tasks():
    ctx = MockContext()
    result = await harvest.execute_action("list_tasks", {"per_page": 5}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "tasks" in data
    assert "total_entries" in data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_users():
    ctx = MockContext()
    result = await harvest.execute_action("list_users", {"per_page": 5}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "users" in data
    assert "total_entries" in data
