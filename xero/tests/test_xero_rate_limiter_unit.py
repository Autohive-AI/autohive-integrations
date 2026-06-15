import asyncio
import importlib
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
os.chdir(_parent)

_spec = importlib.util.spec_from_file_location("xero_mod", os.path.join(_parent, "xero.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["xero_mod"] = _mod

from autohive_integrations_sdk import FetchResponse, RateLimitError  # noqa: E402

XeroRateLimiter = _mod.XeroRateLimiter
XeroRateLimitExceededException = _mod.XeroRateLimitExceededException

pytestmark = pytest.mark.unit

TENANT_ID = "test-tenant-id"
TEST_URL = "https://api.xero.com/api.xro/2.0/Contacts"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    return ctx


@pytest.fixture
def limiter():
    return XeroRateLimiter(default_retry_delay=60, max_retries=2, max_wait_time=30)


def _make_fetch_response(data=None, headers=None):
    return FetchResponse(status=200, headers=headers or {}, data=data or {})


def _make_rate_limit_error(retry_after: int = 10):
    return RateLimitError(retry_after, 429, "Rate limit exceeded", "")


# ---- Success path ----


class TestSuccessPath:
    async def test_returns_response_data(self, mock_context, limiter):
        mock_context.fetch.return_value = _make_fetch_response(
            data={"Contacts": [{"ContactID": "c1"}]},
            headers={"X-MinLimit-Remaining": "55", "X-DayLimit-Remaining": "4990"},
        )

        result = await limiter.make_request(mock_context, TEST_URL, TENANT_ID, method="GET")

        assert result == {"Contacts": [{"ContactID": "c1"}]}

    async def test_injects_tenant_header(self, mock_context, limiter):
        mock_context.fetch.return_value = _make_fetch_response()

        await limiter.make_request(
            mock_context, TEST_URL, TENANT_ID, method="GET", headers={"Accept": "application/json"}
        )

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["headers"]["xero-tenant-id"] == TENANT_ID
        assert call_kwargs["headers"]["Accept"] == "application/json"

    async def test_no_rate_limit_headers_still_succeeds(self, mock_context, limiter):
        mock_context.fetch.return_value = _make_fetch_response(data={"ok": True}, headers={})

        result = await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert result == {"ok": True}

    async def test_non_zero_day_remaining_does_not_raise(self, mock_context, limiter):
        mock_context.fetch.return_value = _make_fetch_response(
            data={"ok": True},
            headers={"X-DayLimit-Remaining": "1"},
        )

        result = await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert result == {"ok": True}


class TestSuccessfulDayLimitResponse:
    async def test_returns_data_even_when_day_remaining_is_zero(self, mock_context, limiter):
        # X-DayLimit-Remaining reflects the allowance *after* this successful
        # call, so the response is still valid and must be returned — only a
        # subsequent call should hit a 429. Blocking here would discard data
        # Xero already returned.
        mock_context.fetch.return_value = _make_fetch_response(
            data={"ok": True},
            headers={"X-DayLimit-Remaining": "0"},
        )

        result = await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert result == {"ok": True}


# ---- 429 retry behaviour ----


class TestRateLimitRetry:
    async def test_retries_on_rate_limit_error_within_max_wait(self, mock_context, limiter):
        success_response = _make_fetch_response(data={"ok": True})
        mock_context.fetch.side_effect = [
            _make_rate_limit_error(retry_after=5),
            success_response,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert result == {"ok": True}
        mock_sleep.assert_awaited_once_with(5)
        assert mock_context.fetch.call_count == 2

    async def test_raises_exceeded_when_retry_after_exceeds_max_wait(self, mock_context, limiter):
        # limiter.max_wait_time = 30; retry_after = 60 > 30
        mock_context.fetch.side_effect = _make_rate_limit_error(retry_after=60)

        with pytest.raises(XeroRateLimitExceededException) as exc_info:
            await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert exc_info.value.requested_delay == 60
        assert exc_info.value.max_wait_time == 30
        assert exc_info.value.tenant_id == TENANT_ID

    async def test_raises_last_error_after_all_retries_exhausted(self, mock_context, limiter):
        # max_retries=2 → 3 total attempts, all fail with short retry_after
        rate_limit_err = _make_rate_limit_error(retry_after=5)
        mock_context.fetch.side_effect = [rate_limit_err, rate_limit_err, rate_limit_err]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert mock_context.fetch.call_count == 3

    async def test_non_rate_limit_exception_raises_immediately(self, mock_context, limiter):
        mock_context.fetch.side_effect = ValueError("Bad request")

        with pytest.raises(ValueError, match="Bad request"):
            await limiter.make_request(mock_context, TEST_URL, TENANT_ID)

        assert mock_context.fetch.call_count == 1


# ---- Concurrency limit ----


class TestConcurrencyLimit:
    async def test_semaphore_caps_concurrent_requests(self, mock_context):
        limiter = XeroRateLimiter()

        active = 0
        max_active = 0
        completed = []

        async def slow_fetch(*args, **kwargs):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.05)
                completed.append("done")
                return _make_fetch_response(data={})
            finally:
                active -= 1

        mock_context.fetch.side_effect = slow_fetch

        tasks = [asyncio.create_task(limiter.make_request(mock_context, TEST_URL, TENANT_ID)) for _ in range(7)]
        await asyncio.gather(*tasks)

        # All 7 requests should complete despite the semaphore cap
        assert len(completed) == 7
        # ...but no more than MAX_CONCURRENT_REQUESTS were ever in flight at once,
        # proving the semaphore actually caps concurrency rather than the requests
        # just happening to finish.
        assert max_active <= XeroRateLimiter.MAX_CONCURRENT_REQUESTS

    async def test_semaphore_max_value_is_five(self):
        limiter = XeroRateLimiter()
        sem = limiter._get_semaphore()
        assert sem._value == 5
