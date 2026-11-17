"""Optional live tests for LinkedIn Community Management.

Set LINKEDIN_COMMUNITY_ACCESS_TOKEN to a token issued for the Community
Management product with the scopes documented in linkedin-community-management/README.md, then run:

    pytest linkedin-community-management/tests/test_linkedin_community_management_integration.py -m integration
"""

import importlib.util
import os
import sys

import pytest
from autohive_integrations_sdk import ExecutionContext

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location(
    "linkedin_community_management_mod", os.path.join(_parent, "linkedin_community_management.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

linkedin_community_management = _mod.linkedin_community_management

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_context():
    token = os.environ.get("LINKEDIN_COMMUNITY_ACCESS_TOKEN")
    if not token:
        pytest.skip("LINKEDIN_COMMUNITY_ACCESS_TOKEN is not set")
    async with ExecutionContext(
        auth={"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
    ) as context:
        yield context


class TestCommunityManagementReadOnly:
    async def test_profile(self, live_context):
        result = await linkedin_community_management.execute_action("get_profile", {}, live_context)
        assert result.result.data["profile"]["id"]

    async def test_managed_organizations(self, live_context):
        result = await linkedin_community_management.execute_action("list_managed_organizations", {}, live_context)
        assert isinstance(result.result.data["organizations"], list)

    async def test_member_follower_statistics(self, live_context):
        result = await linkedin_community_management.execute_action("get_member_follower_statistics", {}, live_context)
        assert isinstance(result.result.data["statistics"], list)
