import pytest
from autohive_integrations_sdk import ResultType

from ..workzappy import workzappy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_list_projects_with_live_credentials(live_auth):
    async with live_auth:
        result = await workzappy.execute_action("list_projects", {}, live_auth)
    assert result.type == ResultType.ACTION, "Check WorkZappy credentials and Get Project List permission."
    assert isinstance(result.result.data["projects"], list)
