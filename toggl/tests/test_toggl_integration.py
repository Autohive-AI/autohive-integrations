"""
Live integration tests for the Toggl Track integration.

Requires TOGGL_API_TOKEN set in the environment.
Requires TOGGL_WORKSPACE_ID set in the environment.

Run with:
    pytest toggl/tests/test_toggl_integration.py -m "integration" -o "addopts=--import-mode=importlib --tb=short"
"""

import pytest
from autohive_integrations_sdk.integration import ResultType

from toggl.toggl import toggl

pytestmark = pytest.mark.integration


@pytest.mark.destructive
async def test_create_time_entry(toggl_context, toggl_workspace_id):
    async with toggl_context as ctx:
        result = await toggl.execute_action(
            "create_time_entry",
            {
                "workspace_id": toggl_workspace_id,
                "start": "2026-01-01T10:00:00Z",
                "stop": "2026-01-01T11:00:00Z",
                "duration": 3600,
                "description": "Autohive integration test — safe to delete",
            },
            ctx,
        )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "id" in data
    assert data["workspace_id"] == toggl_workspace_id
