import asyncio
import importlib.util
import os
import sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("xero_mod", os.path.join(_parent, "xero.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

xero = _mod.xero
XeroRateLimiter = _mod.XeroRateLimiter
XeroRateLimitExceededException = _mod.XeroRateLimitExceededException

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


class FakeRateLimitError(Exception):
    """Mimics an HTTP 429 error from context.fetch with a Retry-After header."""

    def __init__(self, retry_after=None):
        super().__init__("429 Too Many Requests")
        self.headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}


SAMPLE_CONNECTIONS = [
    {"tenantId": "tenant-001", "tenantName": "Acme Corp", "tenantType": "ORGANISATION"},
]


# ---- Connected Account ----


class TestConnectedAccount:
    @pytest.mark.asyncio
    async def test_returns_populated_account_info(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONNECTIONS)

        result = await xero.get_connected_account(mock_context)

        assert result.type == ResultType.CONNECTED_ACCOUNT
        assert result.result.username == "Acme Corp"
        assert result.result.user_id == "tenant-001"

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_placeholder_instead_of_crashing(self, mock_context):
        # Reproduces the Raygun "Unhandled" Lambda crash: an exception raised
        # by context.fetch (e.g., revoked/expired token, 5xx outage) used to
        # propagate out of the handler and crash the Lambda. Handler must
        # absorb it and return a valid placeholder ConnectedAccountInfo.
        mock_context.fetch.side_effect = Exception("401 Unauthorized")

        result = await xero.get_connected_account(mock_context)

        assert result.type == ResultType.CONNECTED_ACCOUNT
        assert result.result.username == "Unknown Organization"

    @pytest.mark.asyncio
    async def test_cancelled_error_returns_placeholder(self, mock_context):
        # CancelledError is a BaseException, so a bare `except Exception`
        # would let it slip through and crash the Lambda.
        mock_context.fetch.side_effect = asyncio.CancelledError()

        result = await xero.get_connected_account(mock_context)

        assert result.type == ResultType.CONNECTED_ACCOUNT
        assert result.result.username == "Unknown Organization"


# ---- Rate limiter sleep budget ----


class TestRateLimiterSleepBudget:
    def test_defaults_fit_inside_lambda_timeout(self):
        # The Lambda is killed after 30s. The cumulative sleep budget plus the
        # default per-retry delay must leave headroom for the requests
        # themselves; max_wait_time is the cumulative cap.
        limiter = XeroRateLimiter()
        assert limiter.max_wait_time <= 15
        assert limiter.default_retry_delay <= limiter.max_wait_time

    @pytest.mark.asyncio
    async def test_delay_over_budget_fails_fast_without_sleeping(self, mock_context):
        # A Retry-After of 60s used to put the Lambda to sleep past its 30s
        # lifetime ("Unhandled" crash). It must now raise immediately.
        mock_context.fetch.side_effect = FakeRateLimitError(retry_after=60)
        limiter = XeroRateLimiter()

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(XeroRateLimitExceededException):
                await limiter.make_request(mock_context, "https://api.xero.com/test", "t-001")

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cumulative_budget_enforced_across_retries(self, mock_context):
        # Each individual delay fits the budget, but the running total must
        # not: 8s sleeps, then 8 + 8 > 10s budget -> fail fast.
        mock_context.fetch.side_effect = FakeRateLimitError(retry_after=8)
        limiter = XeroRateLimiter(max_wait_time=10)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with pytest.raises(XeroRateLimitExceededException):
                await limiter.make_request(mock_context, "https://api.xero.com/test", "t-001")

        mock_sleep.assert_awaited_once_with(8)

    @pytest.mark.asyncio
    async def test_short_delay_retries_and_succeeds(self, mock_context):
        # Happy path: one 429 with a small Retry-After, then success.
        mock_context.fetch.side_effect = [
            FakeRateLimitError(retry_after=2),
            FetchResponse(status=200, headers={}, data={"ok": True}),
        ]
        limiter = XeroRateLimiter()

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await limiter.make_request(mock_context, "https://api.xero.com/test", "t-001")

        assert result == {"ok": True}
        mock_sleep.assert_awaited_once_with(2)

    @pytest.mark.asyncio
    async def test_missing_retry_after_uses_safe_default(self, mock_context):
        # No Retry-After header -> the default delay must be small enough to
        # fit the budget (the old default was 60s, which killed the Lambda).
        mock_context.fetch.side_effect = [
            FakeRateLimitError(),
            FetchResponse(status=200, headers={}, data={"ok": True}),
        ]
        limiter = XeroRateLimiter()

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await limiter.make_request(mock_context, "https://api.xero.com/test", "t-001")

        assert result == {"ok": True}
        mock_sleep.assert_awaited_once_with(limiter.default_retry_delay)
        assert limiter.default_retry_delay <= limiter.max_wait_time

    @pytest.mark.asyncio
    async def test_cancelled_error_converted_to_timeout(self, mock_context):
        # Cooperative cancellation reaching the coroutine must surface as a
        # regular exception (caught by the actions' `except Exception`)
        # instead of escaping the Lambda as "Unhandled".
        mock_context.fetch.side_effect = asyncio.CancelledError()
        limiter = XeroRateLimiter()

        with pytest.raises(TimeoutError, match="cancelled"):
            await limiter.make_request(mock_context, "https://api.xero.com/test", "t-001")


# ---- Action-level cancellation ----


class TestActionCancellation:
    @pytest.mark.asyncio
    async def test_action_returns_action_error_when_request_cancelled(self, mock_context):
        # End-to-end: cancellation inside make_request becomes a clean
        # ActionError from the action, not an unhandled crash.
        mock_context.fetch.side_effect = asyncio.CancelledError()

        result = await xero.execute_action("get_accounts", {"tenant_id": "t-001"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "cancelled" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_attach_file_cancellation_returns_action_error(self, mock_context):
        # Cancellation during the raw file download (outside the rate
        # limiter) must also be caught by the action itself.
        with patch.object(_mod, "_resolve_file_bytes", new=AsyncMock(side_effect=asyncio.CancelledError())):
            result = await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "file": {"name": "test.pdf", "contentType": "application/pdf", "url": "https://example.com/f"},
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "cancelled" in result.result.message.lower()


# ---- Direct aiohttp timeout cap ----


class TestHttpTimeout:
    def test_http_timeout_is_below_lambda_timeout(self):
        # Direct aiohttp downloads (PDF/attachments/file URLs) must time out
        # before the 30s Lambda kill; aiohttp's default is 300s.
        assert _mod.HTTP_TIMEOUT.total < 30


# ---- Empty-string required inputs ----


_SAMPLE_FILE = {"name": "test.pdf", "contentType": "application/pdf", "content": "Zm9v"}


class TestEmptyStringValidation:
    # The schemas mark these fields required but set no `minLength`, so an
    # empty string passes schema validation and reaches the handler. The
    # handler's `if not value: raise ValueError(...)` used to fire *before*
    # the try block; since the SDK's execute_action only converts
    # ValidationError, that ValueError escaped as an "Unhandled" Lambda crash.
    # The checks now live inside the try, so an empty required string must
    # come back as a clean ActionError.
    @pytest.mark.parametrize(
        "action_name,inputs",
        [
            ("get_invoice_pdf", {"tenant_id": "t-001", "invoice_id": ""}),
            ("attach_file_to_invoice", {"tenant_id": "", "invoice_id": "inv-001", "file": _SAMPLE_FILE}),
            ("attach_file_to_bill", {"tenant_id": "t-001", "bill_id": "", "file": _SAMPLE_FILE}),
            (
                "get_attachment_content",
                {"tenant_id": "t-001", "endpoint": "Invoices", "guid": "g-001", "file_name": ""},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_empty_required_string_returns_action_error(self, mock_context, action_name, inputs):
        result = await xero.execute_action(action_name, inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "is required" in result.result.message
        # Validation must short-circuit before any network call is attempted.
        mock_context.fetch.assert_not_awaited()
