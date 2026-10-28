"""Live HubSpot tests need explicit permission before any write can reach the network."""

from unittest.mock import MagicMock, patch

import pytest
from hubspot.tests.test_hubspot_integration import live_context

pytestmark = pytest.mark.unit


def request_for(*, destructive=False, opt_in=False):
    request = MagicMock()
    request.node.get_closest_marker.return_value = object() if destructive else None
    request.config.getoption.return_value = opt_in
    return request


def test_destructive_live_test_skips_before_reading_credentials_without_opt_in():
    credentials = MagicMock()
    with pytest.raises(pytest.skip.Exception, match="run-hubspot-destructive"):
        live_context.__wrapped__(request_for(destructive=True), credentials)
    credentials.assert_not_called()


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
async def test_unmarked_live_test_blocks_mutation_before_opening_http_session(method):
    context = live_context.__wrapped__(request_for(), lambda _: "fake-test-token")
    with patch("aiohttp.ClientSession") as session:
        with pytest.raises(AssertionError, match="Read-only test blocked"):
            await context.fetch("https://api.hubapi.com/crm/objects/2026-09/contacts/1", method=method)
        session.assert_not_called()


def test_destructive_live_test_can_prepare_context_only_after_explicit_opt_in():
    credentials = MagicMock(return_value="fake-test-token")
    context = live_context.__wrapped__(request_for(destructive=True, opt_in=True), credentials)
    credentials.assert_called_once_with("HUBSPOT_ACCESS_TOKEN")
    context.fetch.assert_not_called()
