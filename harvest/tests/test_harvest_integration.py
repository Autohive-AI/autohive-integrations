"""
Live integration tests for the Harvest integration.

Requires HARVEST_ACCESS_TOKEN and HARVEST_ACCOUNT_ID set in the environment.

For a Harvest OAuth token the account ID is the numeric prefix before ".at." in
the token string. E.g. for "4121875.at.xxx..." the account ID is "4121875".

Safe read-only run:
    pytest harvest/tests/test_harvest_integration.py -m "integration and not destructive"

Including destructive (create/update/delete time entries):
    pytest harvest/tests/test_harvest_integration.py -m "integration"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from harvest.harvest import harvest

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("HARVEST_ACCESS_TOKEN")
    account_id = env_credentials("HARVEST_ACCOUNT_ID")
    if not access_token:
        pytest.skip("HARVEST_ACCESS_TOKEN not set — skipping integration tests")
    if not account_id:
        pytest.skip("HARVEST_ACCOUNT_ID not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Harvest-Account-Id": account_id,
            "User-Agent": "AutohiveIntegrations/1.0",
        }
        merged_headers = {**auth_headers, **(headers or {})}
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, headers=merged_headers, params=params, **kwargs
            ) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token, "account_id": account_id},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    return ctx


# ---------------------------------------------------------------------------
# Read-only
# ---------------------------------------------------------------------------


async def test_list_time_entries(live_context):
    result = await harvest.execute_action("list_time_entries", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "time_entries" in data
    assert "total_entries" in data


async def test_list_projects(live_context):
    result = await harvest.execute_action("list_projects", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "projects" in data
    assert "total_entries" in data


async def test_get_project(live_context):
    projects = (await harvest.execute_action("list_projects", {"per_page": 1}, live_context)).result.data.get("projects", [])
    if not projects:
        pytest.skip("No projects in account")
    result = await harvest.execute_action("get_project", {"project_id": projects[0]["id"]}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "id" in data
    assert "name" in data


async def test_list_clients(live_context):
    result = await harvest.execute_action("list_clients", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "clients" in data
    assert "total_entries" in data


async def test_list_tasks(live_context):
    result = await harvest.execute_action("list_tasks", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "tasks" in data
    assert "total_entries" in data


async def test_list_users(live_context):
    result = await harvest.execute_action("list_users", {"per_page": 5}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "users" in data
    assert "total_entries" in data


# ---------------------------------------------------------------------------
# Destructive — create/update/delete a time entry lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.destructive
async def test_create_update_stop_delete_time_entry(live_context):
    # Need a project and task to create a time entry
    projects = (await harvest.execute_action("list_projects", {"per_page": 1}, live_context)).result.data.get("projects", [])
    if not projects:
        pytest.skip("No projects in account")
    tasks = (await harvest.execute_action("list_tasks", {"per_page": 1}, live_context)).result.data.get("tasks", [])
    if not tasks:
        pytest.skip("No tasks in account")

    project_id = projects[0]["id"]
    task_id = tasks[0]["id"]

    # Create
    create_result = await harvest.execute_action(
        "create_time_entry",
        {"project_id": project_id, "task_id": task_id, "spent_date": "2026-01-01", "hours": 1.0},
        live_context,
    )
    assert create_result.type == ResultType.ACTION
    entry_id = create_result.result.data["id"]
    assert entry_id

    # Update
    update_result = await harvest.execute_action(
        "update_time_entry",
        {"time_entry_id": entry_id, "hours": 2.0},
        live_context,
    )
    assert update_result.type == ResultType.ACTION

    # Stop (only works on running timers, may return error — that's fine)
    await harvest.execute_action("stop_time_entry", {"time_entry_id": entry_id}, live_context)

    # Delete
    delete_result = await harvest.execute_action(
        "delete_time_entry", {"time_entry_id": entry_id}, live_context
    )
    assert delete_result.type == ResultType.ACTION
