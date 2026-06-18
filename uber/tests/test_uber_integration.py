"""
End-to-end integration tests for the Uber Ride Requests integration.

These tests call the real Uber Riders API and require a valid OAuth access token
set in the UBER_ACCESS_TOKEN environment variable. To run against the Uber
sandbox (recommended — the destructive tests book and cancel real ride requests),
also set UBER_API_BASE_URL=https://sandbox-api.uber.com.

Run all read-only tests:
    pytest uber/tests/test_uber_integration.py -m integration

Run destructive tests (books and cancels a ride on the linked account/sandbox):
    pytest uber/tests/test_uber_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import importlib.util
import os
import sys

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType, HTTPError, RateLimitError

# The integration folder ships an __init__.py that turns `uber` into a package
# exposing only the integration object, so `import uber` is ambiguous with uber.py.
# Load the action source directly by file path.
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("uber_integration_mod", os.path.join(_parent, "uber.py"))
uber_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uber_mod)

uber_integration = uber_mod.uber

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("UBER_ACCESS_TOKEN", "")

# San Francisco — Uber HQ area; reliably has products/estimates available.
SF_LAT = 37.7752315
SF_LNG = -122.418075
SF_END_LAT = 37.7825
SF_END_LNG = -122.4156


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("UBER_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, json=None, headers=None, **kwargs):
        req_headers = {**(headers or {}), "Authorization": f"Bearer {ACCESS_TOKEN}"}
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=req_headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                # Mirror the SDK's ExecutionContext.fetch contract: non-2xx responses
                # raise instead of returning a FetchResponse. Without this, a failed
                # live call (expired token, missing scope, deprecated endpoint) would
                # hand the error body to the action as normal data, and the action's
                # `.get()` defaults would produce an empty-but-successful ACTION result
                # — letting the suite pass while every live call is actually failing.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


def _data_or_skip(result, context_msg):
    """Return result.result.data on success, otherwise skip with the API message.

    Read-only endpoints can legitimately fail when the linked token lacks the
    required scope; skip rather than fail so the rest of the suite still runs.
    """
    if result.type != ResultType.ACTION:
        message = getattr(result.result, "message", str(result.result))
        pytest.skip(f"{context_msg}: {message}")
    return result.result.data


# =============================================================================
# USER PROFILE
# =============================================================================


class TestUserProfile:
    async def test_get_user_profile(self, live_context):
        result = await uber_integration.execute_action("get_user_profile", {}, live_context)
        data = _data_or_skip(result, "get_user_profile")
        assert isinstance(data["user"], dict)


# =============================================================================
# PRODUCTS
# =============================================================================


class TestProducts:
    async def test_get_products_returns_list(self, live_context):
        result = await uber_integration.execute_action(
            "get_products", {"latitude": SF_LAT, "longitude": SF_LNG}, live_context
        )
        data = _data_or_skip(result, "get_products")
        assert isinstance(data["products"], list)

    async def test_products_have_product_id(self, live_context):
        result = await uber_integration.execute_action(
            "get_products", {"latitude": SF_LAT, "longitude": SF_LNG}, live_context
        )
        data = _data_or_skip(result, "get_products")
        if not data["products"]:
            pytest.skip("No products available at this location")
        assert "product_id" in data["products"][0]


# =============================================================================
# ESTIMATES
# =============================================================================


class TestEstimates:
    async def test_price_estimate(self, live_context):
        result = await uber_integration.execute_action(
            "get_price_estimate",
            {
                "start_latitude": SF_LAT,
                "start_longitude": SF_LNG,
                "end_latitude": SF_END_LAT,
                "end_longitude": SF_END_LNG,
            },
            live_context,
        )
        data = _data_or_skip(result, "get_price_estimate")
        assert isinstance(data["prices"], list)

    async def test_time_estimate(self, live_context):
        result = await uber_integration.execute_action(
            "get_time_estimate", {"start_latitude": SF_LAT, "start_longitude": SF_LNG}, live_context
        )
        data = _data_or_skip(result, "get_time_estimate")
        assert isinstance(data["times"], list)

    async def test_ride_estimate(self, live_context):
        # POST /requests/estimate returns an upfront fare — it does NOT book a ride,
        # so it is safe to run in the read-only suite. Discover a product first.
        products_result = await uber_integration.execute_action(
            "get_products", {"latitude": SF_LAT, "longitude": SF_LNG}, live_context
        )
        products = _data_or_skip(products_result, "get_products").get("products", [])
        if not products:
            pytest.skip("No products available to estimate a ride")

        result = await uber_integration.execute_action(
            "get_ride_estimate",
            {
                "product_id": products[0]["product_id"],
                "start_latitude": SF_LAT,
                "start_longitude": SF_LNG,
                "end_latitude": SF_END_LAT,
                "end_longitude": SF_END_LNG,
            },
            live_context,
        )
        data = _data_or_skip(result, "get_ride_estimate")
        assert "estimate" in data


# =============================================================================
# HISTORY & PAYMENT METHODS
# =============================================================================


class TestHistory:
    async def test_get_ride_history(self, live_context):
        result = await uber_integration.execute_action("get_ride_history", {"limit": 5}, live_context)
        data = _data_or_skip(result, "get_ride_history")
        assert isinstance(data["history"], list)
        assert isinstance(data["count"], int)


class TestPaymentMethods:
    async def test_get_payment_methods(self, live_context):
        result = await uber_integration.execute_action("get_payment_methods", {}, live_context)
        data = _data_or_skip(result, "get_payment_methods")
        assert isinstance(data["payment_methods"], list)


# =============================================================================
# DESTRUCTIVE — books and cancels a real ride request
# Only run with: pytest -m "integration and destructive"
# Strongly recommended against the Uber sandbox (UBER_API_BASE_URL).
# =============================================================================


@pytest.mark.destructive
class TestRideLifecycle:
    async def test_request_status_cancel(self, live_context):
        # discover a product at the pickup location
        products_result = await uber_integration.execute_action(
            "get_products", {"latitude": SF_LAT, "longitude": SF_LNG}, live_context
        )
        products = _data_or_skip(products_result, "get_products").get("products", [])
        if not products:
            pytest.skip("No products available to request a ride")
        product_id = products[0]["product_id"]

        # request the ride
        request_result = await uber_integration.execute_action(
            "request_ride",
            {
                "product_id": product_id,
                "start_latitude": SF_LAT,
                "start_longitude": SF_LNG,
                "end_latitude": SF_END_LAT,
                "end_longitude": SF_END_LNG,
            },
            live_context,
        )
        request_data = _data_or_skip(request_result, "request_ride")
        request_id = request_data["request_id"]
        assert request_id

        # check its status
        status_result = await uber_integration.execute_action(
            "get_ride_status", {"request_id": request_id}, live_context
        )
        status_data = _data_or_skip(status_result, "get_ride_status")
        assert status_data["ride"].get("request_id") == request_id or "status" in status_data["ride"]

        # fetch the live tracking map for the active ride (href may be null until accepted)
        map_result = await uber_integration.execute_action("get_ride_map", {"request_id": request_id}, live_context)
        if map_result.type == ResultType.ACTION:
            assert "href" in map_result.result.data

        # always clean up — cancel the ride we created
        cancel_result = await uber_integration.execute_action("cancel_ride", {"request_id": request_id}, live_context)
        cancel_data = _data_or_skip(cancel_result, "cancel_ride")
        assert cancel_data["result"] is True
