import os

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType
from estimateone.estimateone import estimateone

pytestmark = pytest.mark.integration


async def test_live_matched_projects():
    values = [os.environ.get(name) for name in ("E1_CLIENT_ID", "E1_CLIENT_SECRET", "E1_COMPANY_ID")]
    if not all(values):
        pytest.skip("E1 partner credentials and a registered test company are required")
    client_id, client_secret, company_id = values
    auth = {"auth_type": "Custom", "credentials": {"client_id": client_id, "client_secret": client_secret}}
    async with ExecutionContext(auth=auth) as context:
        result = await estimateone.execute_action(
            "list_matched_projects", {"company_id": company_id, "limit": 1}, context
        )
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["projects"], list)
