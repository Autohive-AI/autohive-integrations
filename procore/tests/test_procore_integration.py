import os

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType
from procore.procore import procore

pytestmark = pytest.mark.integration


async def test_live_sandbox_projects():
    token = os.environ.get("PROCORE_ACCESS_TOKEN")
    company_id = os.environ.get("PROCORE_COMPANY_ID")
    if not token or not company_id:
        pytest.skip("A Procore sandbox OAuth access token and company ID are required")
    auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
    async with ExecutionContext(auth=auth) as context:
        result = await procore.execute_action(
            "list_projects",
            {
                "company_id": int(company_id),
                "environment": "sandbox",
                "per_page": 1,
            },
            context,
        )
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["items"], list)
