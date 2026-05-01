import os
import sys
import importlib.util

import pytest

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

from autohive_integrations_sdk import ExecutionContext  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "front_mod", os.path.join(_parent, "front.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

front = _mod.front  # the Integration instance

pytestmark = pytest.mark.integration

# Skip all integration tests if env var is not set
API_TOKEN = os.environ.get("FRONT_API_TOKEN", "")

skip_if_no_creds = pytest.mark.skipif(
    not API_TOKEN,
    reason="FRONT_API_TOKEN env var required for integration tests",
)


@pytest.fixture
def live_context():
    """Real ExecutionContext using env var credentials."""
    auth = {"credentials": {"access_token": API_TOKEN}}  # nosec B105
    return auth


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_inboxes_integration(live_context):
    """Integration test: list inboxes from live Front account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await front.execute_action("list_inboxes", {}, context)
        assert result.result is not None
        assert "inboxes" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_teammates_integration(live_context):
    """Integration test: list teammates from live Front account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await front.execute_action("list_teammates", {}, context)
        assert result.result is not None
        assert "teammates" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_channels_integration(live_context):
    """Integration test: list channels from live Front account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await front.execute_action("list_channels", {}, context)
        assert result.result is not None
        assert "channels" in result.result.data
