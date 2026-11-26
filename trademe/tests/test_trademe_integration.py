"""Read-only live tests. Sandbox credentials are required in root .env."""

import pytest
from autohive_integrations_sdk import ExecutionContext
from autohive_integrations_sdk.integration import ResultType

from trademe.trademe import trademe

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_context(env_credentials):
    credentials = {
        name: env_credentials(variable)
        for name, variable in {
            "consumer_key": "TRADEME_CONSUMER_KEY",
            "consumer_secret": "TRADEME_CONSUMER_SECRET",  # nosec B105 - environment variable name
            "access_token": "TRADEME_ACCESS_TOKEN",  # nosec B105 - environment variable name
            "access_token_secret": "TRADEME_ACCESS_TOKEN_SECRET",  # nosec B105 - environment variable name
        }.items()
    }
    if not all(credentials.values()):
        pytest.skip("Trade Me sandbox credentials are missing. See trademe/README.md.")
    credentials["environment"] = "sandbox"
    async with ExecutionContext(auth={"auth_type": "Custom", "credentials": credentials}) as context:
        yield context


async def test_profile(live_context):
    result = await trademe.execute_action("get_profile", {}, live_context)
    assert result.type == ResultType.ACTION
    assert "SellingCount" in result.result.data["profile"]


@pytest.mark.parametrize("action", ["list_selling_items", "list_sold_items", "list_unsold_items"])
async def test_seller_lists(action, live_context):
    result = await trademe.execute_action(action, {"page": 1, "rows": 2}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["items"], list)
    assert result.result.data["page"] == 1
    assert result.result.data["total_count"] >= 0


async def test_owned_listing(live_context, env_credentials):
    listing_id = env_credentials("TRADEME_TEST_LISTING_ID")
    if not listing_id:
        pytest.skip("Set TRADEME_TEST_LISTING_ID to a listing owned by the sandbox member.")
    result = await trademe.execute_action("get_selling_listing", {"listing_id": int(listing_id)}, live_context)
    assert result.type == ResultType.ACTION
    assert "Title" in result.result.data["listing"]
