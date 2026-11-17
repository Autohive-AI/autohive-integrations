"""Optional live checks; explicitly invoked and excluded from default CI tests."""

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType

from lusha.lusha import lusha

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_context(env_credentials):
    api_key = env_credentials("LUSHA_API_KEY")
    if not api_key:
        pytest.skip("LUSHA_API_KEY is not set")
    async with ExecutionContext(auth={"auth_type": "Custom", "credentials": {"api_key": api_key}}) as context:
        yield context


async def test_account_usage(live_context):
    result = await lusha.execute_action("get_account_usage", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["credits"]["remaining"], (int, float))


async def test_company_search(live_context, env_credentials):
    # Setting this optional domain explicitly opts into a credit-consuming lookup.
    domain = env_credentials("LUSHA_TEST_COMPANY_DOMAIN")
    if not domain:
        pytest.skip("Set LUSHA_TEST_COMPANY_DOMAIN to opt into a credit-consuming company lookup")
    result = await lusha.execute_action("search_companies", {"companies": [{"domain": domain}]}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["results"], list)
    assert len(result.result.data["results"]) == 1
    assert result.result.data["results"][0].get("id")
