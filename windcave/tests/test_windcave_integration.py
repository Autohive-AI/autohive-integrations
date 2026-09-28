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
from autohive_integrations_sdk import HTTPError
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave
from windcave.windcave import CARD_FIELDS

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


def assert_card_fields_are_redacted(value):
    """Check objects and standalone card fields throughout the full output."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in CARD_FIELDS:
                assert_card_is_redacted(item)
            else:
                assert_card_fields_are_redacted(item)
    elif isinstance(value, list):
        for item in value:
            assert_card_fields_are_redacted(item)


@pytest.fixture
def live_context(env_credentials, monkeypatch):
    username = env_credentials("WINDCAVE_USERNAME")
    api_key = env_credentials("WINDCAVE_API_KEY")
    if not username or not api_key:
        pytest.skip("WINDCAVE_USERNAME / WINDCAVE_API_KEY not set — skipping integration tests")

    import importlib

    module = importlib.import_module("windcave.windcave")
    direct_request = module._windcave_request
    response_statuses: list[int] = []

    async def observed_request(*args, **kwargs):
        # Exercise the production direct transport; observe only safe status data.
        try:
            response = await direct_request(*args, **kwargs)
        except HTTPError as error:
            response_statuses.append(error.status)
            raise
        response_statuses.append(response.status)
        return response

    monkeypatch.setattr(module, "_windcave_request", observed_request)
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="unused_sdk_fetch")
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
        assert_card_fields_are_redacted(result.result.data)


# ---- Read-Only Session Tests ----


class TestGetSession:
    async def test_nonexistent_session_returns_action_error(self, live_context):
        result = await windcave.execute_action(
            "get_session", {"session_id": "00000000000000000000000000000000"}, live_context
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
        assert_card_fields_are_redacted(data)

        cards = list(find_card_objects(data["session"]))
        assert cards, "WINDCAVE_TEST_SESSION_ID must reference a session containing card data"
        for card in cards:
            assert_card_is_redacted(card)
