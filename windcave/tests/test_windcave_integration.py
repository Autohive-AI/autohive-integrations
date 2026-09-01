"""
End-to-end integration tests for the Windcave integration.

These tests call the real Windcave REST API and require valid REST API
credentials set via WINDCAVE_USERNAME and WINDCAVE_API_KEY (in .env or
exported).

This integration is read-only — it exposes a single `get_transaction` action —
so none of these tests create, modify, or delete data, and there are no
destructive tests here.

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
    async def test_nonexistent_transaction_returns_action_error(self, live_context):
        # A well-formed but unused Windcave transaction id (16 hex chars). Using a
        # UUID here instead would return 400 "Invalid transaction id" — a malformed
        # input error — rather than exercising the 404 not-found path.
        result = await windcave.execute_action("get_transaction", {"transaction_id": "0000001c00000000"}, live_context)

        assert result.type == ResultType.ACTION_ERROR
        assert live_context.response_statuses == [404]
        assert "Transaction not found" in result.result.message
        assert "Invalid username or key" not in result.result.message

    async def test_malformed_transaction_id_is_rejected_before_fetch(self, live_context):
        result = await windcave.execute_action(
            "get_transaction", {"transaction_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        assert live_context.response_statuses == []

    async def test_fetches_known_transaction(self, live_context):
        # Fetching a real transaction needs an ID from a transaction that already
        # exists in the account. This integration can no longer create one, so
        # supply a known ID via WINDCAVE_TEST_TRANSACTION_ID to exercise the
        # success path.
        import os

        transaction_id = os.environ.get("WINDCAVE_TEST_TRANSACTION_ID", "")
        if not transaction_id:
            pytest.skip("WINDCAVE_TEST_TRANSACTION_ID not set — skipping success-path test")

        result = await windcave.execute_action("get_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == transaction_id
        assert result.result.data["result"] is True
