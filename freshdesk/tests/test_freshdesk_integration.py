import os
import sys
import importlib.util

import pytest

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

from autohive_integrations_sdk import ExecutionContext  # noqa: E402

_spec = importlib.util.spec_from_file_location("freshdesk_mod", os.path.join(_parent, "freshdesk.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

freshdesk = _mod.freshdesk  # the Integration instance

pytestmark = pytest.mark.integration

# Skip all integration tests if env vars are not set
API_KEY = os.environ.get("FRESHDESK_API_KEY", "")
DOMAIN = os.environ.get("FRESHDESK_DOMAIN", "")

skip_if_no_creds = pytest.mark.skipif(
    not API_KEY or not DOMAIN,
    reason="FRESHDESK_API_KEY and FRESHDESK_DOMAIN env vars required for integration tests",
)


@pytest.fixture
def live_context():
    """Real ExecutionContext using env var credentials."""
    auth = {"credentials": {"api_key": API_KEY, "domain": DOMAIN}}  # nosec B105
    return auth


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_companies_integration(live_context):
    """Integration test: list companies from live Freshdesk account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await freshdesk.execute_action("list_companies", {"per_page": 5}, context)
        assert result.result is not None
        assert "companies" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_tickets_integration(live_context):
    """Integration test: list tickets from live Freshdesk account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await freshdesk.execute_action("list_tickets", {"per_page": 5}, context)
        assert result.result is not None
        assert "tickets" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_contacts_integration(live_context):
    """Integration test: list contacts from live Freshdesk account."""
    async with ExecutionContext(auth=live_context) as context:
        result = await freshdesk.execute_action("list_contacts", {"per_page": 5}, context)
        assert result.result is not None
        assert "contacts" in result.result.data
