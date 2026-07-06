"""
End-to-end integration tests for the Windcave integration.

These tests call the real Windcave REST API against the UAT (test) environment
and require valid UAT REST API credentials set via WINDCAVE_USERNAME and
WINDCAVE_API_KEY (in .env or exported). Tests that run a direct transaction
also require a stored card token set via WINDCAVE_TEST_CARD_ID — obtain one by
completing a `store_card` session in the UAT environment.

Run the safe, read-only tests:
    pytest windcave/tests/test_windcave_integration.py -m "integration and not destructive"

Run destructive tests (creates real sessions/transactions in the UAT environment):
    pytest windcave/tests/test_windcave_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from windcave import windcave

pytestmark = pytest.mark.integration

TEST_CARD_ID = os.environ.get("WINDCAVE_TEST_CARD_ID", "")


def require_card_id():
    if not TEST_CARD_ID:
        pytest.skip("WINDCAVE_TEST_CARD_ID not set — skipping tests that need a stored card token")


@pytest.fixture
def live_context(env_credentials):
    username = env_credentials("WINDCAVE_USERNAME")
    api_key = env_credentials("WINDCAVE_API_KEY")
    if not username or not api_key:
        pytest.skip("WINDCAVE_USERNAME / WINDCAVE_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                data = await resp.json(content_type=None)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"username": username, "api_key": api_key, "use_test_environment": True}
    return ctx


# ---- Read-Only / Session Creation Tests ----


class TestCreateSession:
    async def test_creates_purchase_session(self, live_context):
        result = await windcave.execute_action(
            "create_session",
            {
                "type": "purchase",
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-{os.getpid()}",
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["session_id"]
        assert data["hpp_url"]
        assert data["result"] is True

    async def test_creates_validate_session_without_amount(self, live_context):
        result = await windcave.execute_action(
            "create_session",
            {
                "type": "validate",
                "currency": "NZD",
                "merchant_reference": f"AH-IT-VALIDATE-{os.getpid()}",
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["session_id"]


class TestGetSession:
    async def test_fetches_session_just_created(self, live_context):
        create_result = await windcave.execute_action(
            "create_session",
            {
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-GET-{os.getpid()}",
            },
            live_context,
        )
        session_id = create_result.result.data["session_id"]

        result = await windcave.execute_action("get_session", {"session_id": session_id}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["session_id"] == session_id
        assert "transactions" in data

    async def test_nonexistent_session_returns_action_error(self, live_context):
        result = await windcave.execute_action(
            "get_session", {"session_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Direct Transaction Tests (require a stored card token) ----


class TestCreateTransaction:
    async def test_creates_purchase_transaction(self, live_context):
        require_card_id()

        result = await windcave.execute_action(
            "create_transaction",
            {
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-TXN-{os.getpid()}",
                "card_id": TEST_CARD_ID,
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"]


class TestGetTransaction:
    async def test_fetches_transaction_just_created(self, live_context):
        require_card_id()

        create_result = await windcave.execute_action(
            "create_transaction",
            {
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-TXN-GET-{os.getpid()}",
                "card_id": TEST_CARD_ID,
            },
            live_context,
        )
        transaction_id = create_result.result.data["transaction_id"]

        result = await windcave.execute_action("get_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"] == transaction_id

    async def test_nonexistent_transaction_returns_action_error(self, live_context):
        result = await windcave.execute_action(
            "get_transaction", {"transaction_id": "00000000-0000-0000-0000-000000000000"}, live_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Destructive Tests (Write Operations) ----
# These create, complete, refund, and void real transactions in the UAT environment.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestRefundTransaction:
    async def test_refunds_a_purchase(self, live_context):
        require_card_id()

        purchase = await windcave.execute_action(
            "create_transaction",
            {
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-REFUND-{os.getpid()}",
                "card_id": TEST_CARD_ID,
            },
            live_context,
        )
        transaction_id = purchase.result.data["transaction_id"]

        result = await windcave.execute_action("refund_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"]


@pytest.mark.destructive
class TestCompleteTransaction:
    async def test_completes_an_auth(self, live_context):
        require_card_id()

        auth = await windcave.execute_action(
            "create_transaction",
            {
                "type": "auth",
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-COMPLETE-{os.getpid()}",
                "card_id": TEST_CARD_ID,
            },
            live_context,
        )
        transaction_id = auth.result.data["transaction_id"]

        result = await windcave.execute_action("complete_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"]


@pytest.mark.destructive
class TestVoidTransaction:
    async def test_voids_an_auth(self, live_context):
        require_card_id()

        auth = await windcave.execute_action(
            "create_transaction",
            {
                "type": "auth",
                "amount": 1.00,
                "currency": "NZD",
                "merchant_reference": f"AH-IT-VOID-{os.getpid()}",
                "card_id": TEST_CARD_ID,
            },
            live_context,
        )
        transaction_id = auth.result.data["transaction_id"]

        result = await windcave.execute_action("void_transaction", {"transaction_id": transaction_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["transaction_id"]
