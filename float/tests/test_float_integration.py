"""
End-to-end integration tests for the Float integration.

These tests call the real Float API and require a valid API key
set in the FLOAT_API_KEY environment variable (via .env or export).

Run (safe, read-only):
    pytest float/tests/test_float_integration.py -m "integration and not destructive"

Run (destructive — creates/updates/deletes real data):
    pytest float/tests/test_float_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("float_mod", os.path.join(_parent, "float.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

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
            async with session.request(method, url, json=json, headers=headers, params=params) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"api_key": API_KEY}}
    return ctx


# ---- People ----


class TestListPeople:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_people", {}, live_context)
        assert result.result_type == "ActionResult"
        assert isinstance(result.result.data, list)

    async def test_respects_per_page(self, live_context):
        result = await float_integration.execute_action("list_people", {"per_page": 2}, live_context)
        assert len(result.result.data) <= 2


class TestGetPerson:
    async def test_returns_person(self, live_context):
        list_result = await float_integration.execute_action("list_people", {"per_page": 1}, live_context)
        people = list_result.result.data
        if not people:
            pytest.skip("No people in account")
        person_id = people[0]["people_id"]

        result = await float_integration.execute_action("get_person", {"people_id": person_id}, live_context)
        data = result.result.data
        assert data["people_id"] == person_id
        assert "name" in data


# ---- Projects ----


class TestListProjects:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_projects", {}, live_context)
        assert result.result_type == "ActionResult"
        assert isinstance(result.result.data, list)


# ---- Time Off ----


class TestListTimeOff:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_time_off", {}, live_context)
        assert result.result_type == "ActionResult"
        assert isinstance(result.result.data, list)


class TestListTimeOffTypes:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_time_off_types", {}, live_context)
        data = result.result.data
        assert isinstance(data, list)
        assert len(data) > 0
        assert "timeoff_type_id" in data[0]


# ---- Logged Time ----


class TestListLoggedTime:
    async def test_returns_list(self, live_context):
        result = await float_integration.execute_action("list_logged_time", {}, live_context)
        assert result.result_type == "ActionResult"
        assert isinstance(result.result.data, list)


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestCreateTimeOff:
    """Verifies create_time_off sends people_ids as an array (not people_id integer)."""

    async def test_creates_time_off(self, live_context):
        people_result = await float_integration.execute_action("list_people", {"per_page": 1}, live_context)
        people = people_result.result.data
        if not people:
            pytest.skip("No people in account")
        person_id = people[0]["people_id"]

        types_result = await float_integration.execute_action("list_time_off_types", {}, live_context)
        timeoff_types = types_result.result.data
        if not timeoff_types:
            pytest.skip("No time off types in account")
        timeoff_type_id = timeoff_types[0]["timeoff_type_id"]

        result = await float_integration.execute_action(
            "create_time_off",
            {
                "people_id": person_id,
                "timeoff_type_id": timeoff_type_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-01",
                "hours": 8,
            },
            live_context,
        )
        assert result.result_type == "ActionResult"
        data = result.result.data
        assert "timeoff_id" in data
        assert person_id in data.get("people_ids", [])

        # Cleanup — delete the created entry so it doesn't linger in the account
        await float_integration.execute_action("delete_time_off", {"timeoff_id": data["timeoff_id"]}, live_context)


@pytest.mark.destructive
class TestLoggedTimeLifecycle:
    """Verifies create and update return an object (not a raw array) after unwrapping."""

    async def test_create_update_get_delete(self, live_context):
        people_result = await float_integration.execute_action("list_people", {"per_page": 1}, live_context)
        people = people_result.result.data
        if not people:
            pytest.skip("No people in account")
        person_id = people[0]["people_id"]

        projects_result = await float_integration.execute_action("list_projects", {"per_page": 1}, live_context)
        projects = projects_result.result.data
        if not projects:
            pytest.skip("No projects in account")
        project_id = projects[0]["project_id"]

        # Create — must return a dict, not an array
        create_result = await float_integration.execute_action(
            "create_logged_time",
            {"people_id": person_id, "project_id": project_id, "date": "2026-07-01", "hours": 3},
            live_context,
        )
        assert create_result.result_type == "ActionResult"
        created = create_result.result.data
        assert isinstance(created, dict), "Expected dict — array unwrap fix missing in create_logged_time"
        assert "logged_time_id" in created
        logged_time_id = created["logged_time_id"]

        # Update — must also return a dict, not an array
        update_result = await float_integration.execute_action(
            "update_logged_time",
            {"logged_time_id": logged_time_id, "hours": 5},
            live_context,
        )
        assert update_result.result_type == "ActionResult"
        updated = update_result.result.data
        assert isinstance(updated, dict), "Expected dict — array unwrap fix missing in update_logged_time"
        assert updated["hours"] == 5

        # Get — returns object directly (no fix needed, verify it still works)
        get_result = await float_integration.execute_action(
            "get_logged_time", {"logged_time_id": logged_time_id}, live_context
        )
        assert get_result.result_type == "ActionResult"
        assert get_result.result.data["logged_time_id"] == logged_time_id

        # Delete (cleanup)
        delete_result = await float_integration.execute_action(
            "delete_logged_time", {"logged_time_id": logged_time_id}, live_context
        )
        assert delete_result.result_type == "ActionResult"
        assert delete_result.result.data["success"] is True
