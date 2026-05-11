import os
import sys

import pytest

from autohive_integrations_sdk import ExecutionContext

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _get_env(var: str) -> str | None:
    val = os.environ.get(var)
    return val if val else None


@pytest.fixture
def toggl_context():
    """
    Real ExecutionContext wired with Toggl API token from TOGGL_API_TOKEN env var.
    Uses the SDK's built-in HTTP client — no mocking.
    """
    api_token = _get_env("TOGGL_API_TOKEN")
    if not api_token:
        pytest.skip("TOGGL_API_TOKEN not set — skipping integration tests")
    return ExecutionContext(auth={"credentials": {"api_token": api_token}})


@pytest.fixture
def toggl_workspace_id():
    wid = _get_env("TOGGL_WORKSPACE_ID")
    if not wid:
        pytest.skip("TOGGL_WORKSPACE_ID not set — skipping integration tests")
    return int(wid)
