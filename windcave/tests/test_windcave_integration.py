"""
End-to-end integration tests for the Windcave integration.

These tests call the production Windcave REST API and require valid production
REST API credentials set via WINDCAVE_USERNAME and WINDCAVE_API_KEY (in .env
or exported).

This integration is read-only, so none of these tests create, modify, or delete
data, and there are no destructive tests here.

Run:
    pytest windcave/tests/test_windcave_integration.py -m "integration and not destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave

pytestmark = pytest.mark.integration


def find_card_objects(value):
    """Yield every card object nested in a Windcave response."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() == "card" and isinstance(item, dict):
                yield item
            else:
                yield from find_card_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from find_card_objects(item)


def assert_card_is_redacted(value):
    """Assert that all scalar card values have been removed."""
    if isinstance(value, dict):
        for item in value.values():
            assert_card_is_redacted(item)
    elif isinstance(value, list):
        for item in value:
            assert_card_is_redacted(item)
    else:
        assert value is None or value == "[REDACTED]"


@pytest.fixture
def live_context(env_credentials):
    username = env_credentials("WINDCAVE_USERNAME")
    api_key = env_credentials("WINDCAVE_API_KEY")
    if not username or not api_key:
        pytest.skip("WINDCAVE_USERNAME / WINDCAVE_API_KEY not set — skipping integration tests")

    import aiohttp

    response_statuses: list[int] = []

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                response_statuses.append(resp.status)
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                # Mirror the SDK contract: context.fetch() raises on non-2xx so the
                # action's try/except surfaces an ActionError. Returning a FetchResponse
                # for an error status would let an error body masquerade as success data.
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.response_statuses = response_statuses
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {"username": username, "api_key": api_key},
    }
    return ctx


# ---- Read-Only Transaction Tests ----


class TestGetTransaction:
    async def test_unavailable_transaction_returns_action_error(self, live_context):
        # Production accounts may return 403 or 404 depending on whether the
        # transaction is absent or inaccessible to the authenticated API user.
        result = await windcave.execute_action("get_transaction", {"transaction_id": "0000001c00000000"}, live_context)

        assert result.type == ResultType.ACTION_ERROR
        assert len(live_context.response_statuses) == 1
        assert live_context.response_statuses[0] in {403, 404}

    async def test_malformed_transaction_id_is_rejected_before_fetch(self, live_context):
        result = await windcave.execute_action(
            "get_transaction", {"transaction_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        assert live_context.response_statuses == []

    async def test_fetches_known_transaction(self, live_context, env_credentials):
        # Fetching a real transaction needs an ID from a transaction that already
        # exists in the account. This integration can no longer create one, so
        # supply a known ID via WINDCAVE_TEST_TRANSACTION_ID to exercise the
        # success path.
        transaction_id = env_credentials("WINDCAVE_TEST_TRANSACTION_ID")
        if not transaction_id:
            pytest.skip("WINDCAVE_TEST_TRANSACTION_ID not set — skipping success-path test")

        result = await windcave.execute_action("get_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == transaction_id


# ---- Read-Only Session Tests ----


class TestGetSession:
    async def test_nonexistent_session_returns_action_error(self, live_context):
        result = await windcave.execute_action(
            "get_session", {"session_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert len(live_context.response_statuses) == 1
        assert live_context.response_statuses[0] in {403, 404}

    async def test_fetches_known_session_with_card_data_redacted(self, live_context, env_credentials):
        session_id = env_credentials("WINDCAVE_TEST_SESSION_ID")
        if not session_id:
            pytest.skip("WINDCAVE_TEST_SESSION_ID not set — skipping success-path test")

        result = await windcave.execute_action("get_session", {"session_id": session_id}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["session_id"] == session_id
        assert isinstance(data["transactions"], list)

        cards = list(find_card_objects(data["session"]))
        assert cards, "WINDCAVE_TEST_SESSION_ID must reference a session containing card data"
        for card in cards:
            assert_card_is_redacted(card)
