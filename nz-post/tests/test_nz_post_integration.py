"""Read-only live tests; run explicitly after NZ Post grants application access.

pytest nz-post/tests/test_nz_post_integration.py -m integration -v
"""

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType

from nz_post import _token_cache, nz_post

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_context(env_credentials):
    if not env_credentials("NZPOST_CLIENT_ID") or not env_credentials("NZPOST_CLIENT_SECRET"):
        pytest.skip("NZPOST_CLIENT_ID and NZPOST_CLIENT_SECRET are required")
    _token_cache.clear()
    async with ExecutionContext(auth={}) as context:
        yield context
    _token_cache.clear()


async def test_search_and_get_address(live_context):
    result = await nz_post.execute_action("search_addresses", {"query": "151 Victoria", "count": 5}, live_context)
    assert result.type == ResultType.ACTION
    matches = result.result.data["addresses"]
    assert matches, "Expected a match for the documented address fragment"
    result = await nz_post.execute_action("get_address", {"address_id": str(matches[0]["address_id"])}, live_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["success"] is True
    assert result.result.data["address"]["postcode"]


async def test_check_address_and_postal_details(live_context):
    result = await nz_post.execute_action(
        "check_address",
        {"address_line_1": "8 Waterloo Quay", "address_line_2": "Pipitea", "address_line_3": "Wellington", "count": 5},
        live_context,
    )
    assert result.type == ResultType.ACTION
    matches = result.result.data["addresses"]
    assert matches, "Expected an address match for the documented example"
    assert "MatchScore" in matches[0]
    result = await nz_post.execute_action("get_postal_address_details", {"dpid": str(matches[0]["DPID"])}, live_context)
    assert result.type == ResultType.ACTION
    details = result.result.data["details"]
    if isinstance(details, list):
        assert details, "Expected postal details for the selected DPID"
        details = details[0]
    assert details["Postcode"]


async def test_search_partial_addresses(live_context):
    result = await nz_post.execute_action("search_partial_addresses", {"query": "willis", "count": 5}, live_context)
    assert result.type == ResultType.ACTION
    suggestions = result.result.data["addresses"]
    assert suggestions, "Expected suggestions for the documented example"
    assert "FullPartial" in suggestions[0]
    assert "UniqueId" in suggestions[0]
