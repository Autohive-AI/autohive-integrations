"""
Read-only end-to-end tests for the NZBN integration.

These tests call the real NZBN API and require NZBN_CLIENT_ID, NZBN_CLIENT_SECRET
and NZBN_SUBSCRIPTION_KEY in .env or the environment. Use sandbox credentials and
set NZBN_BASE_URL and NZBN_SCOPE to the sandbox values (see .env.example).

Run safely (all tests are read-only):
    pytest nzbn/tests/test_nzbn_integration.py -m "integration and not destructive"

The default pytest configuration and test_*_integration.py name exclude this
file from CI.
"""

import os
import sys
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

import aiohttp
import pytest
import pytest_asyncio
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nzbn.nzbn import nzbn

pytestmark = pytest.mark.integration

REQUIRED_ENV = ("NZBN_CLIENT_ID", "NZBN_CLIENT_SECRET", "NZBN_SUBSCRIPTION_KEY")
TEST_NZBN = os.environ.get("NZBN_TEST_NZBN", "")


@pytest_asyncio.fixture
async def live_context(env_credentials):
    missing = [name for name in REQUIRED_ENV if not env_credentials(name)]
    if missing:
        pytest.skip(f"{', '.join(missing)} not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {}

    async with aiohttp.ClientSession() as session:

        async def real_fetch(
            url, *, method="GET", json=None, data=None, headers=None, params=None, timeout=None, **kwargs
        ):
            client_timeout = aiohttp.ClientTimeout(total=timeout or 30)
            async with session.request(
                method,
                url,
                json=json,
                data=data,
                headers=headers,
                params=params,
                timeout=client_timeout,
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "json" in content_type:
                    body = await resp.json(content_type=None)
                else:
                    body = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", body)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(body), body)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

        ctx.fetch = AsyncMock(side_effect=real_fetch)
        yield ctx


@pytest_asyncio.fixture
async def company_nzbn(live_context):
    """NZBN of a registered company: NZBN_TEST_NZBN if set, otherwise the first search match."""
    if TEST_NZBN:
        return TEST_NZBN

    result = await nzbn.execute_action(
        "search_entities",
        {"search_term": "Limited", "entity_type": "LTD", "entity_status": "Registered", "page_size": 1},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result
    items = result.result.data["items"]
    if not items:
        pytest.skip("No registered company found in search results; set NZBN_TEST_NZBN")
    return items[0]["nzbn"]


async def run_action(name, inputs, context):
    result = await nzbn.execute_action(name, inputs, context)
    assert result.type == ResultType.ACTION, result.result
    data = result.result.data
    assert data["result"] is True
    return data


class TestSearchEntities:
    async def test_returns_matching_entities(self, live_context):
        data = await run_action(
            "search_entities",
            {"search_term": "Limited", "entity_type": "LTD", "page_size": 5},
            live_context,
        )

        assert data["items"]
        assert len(data["items"]) <= 5
        assert data["totalItems"] >= len(data["items"])
        assert all(item["nzbn"] for item in data["items"])
        assert all(item["entityTypeCode"] == "LTD" for item in data["items"])
        assert all(item.get("entityName") for item in data["items"])

    async def test_status_filter_is_applied(self, live_context):
        data = await run_action(
            "search_entities",
            {"search_term": "Limited", "entity_status": "Registered", "page_size": 5},
            live_context,
        )

        assert all(item["entityStatusDescription"] == "Registered" for item in data["items"])


class TestGetEntity:
    async def test_returns_requested_entity(self, live_context, company_nzbn):
        data = await run_action("get_entity", {"nzbn": company_nzbn}, live_context)

        assert data["entity"]["nzbn"] == company_nzbn
        assert data["entity"]["entityName"]


class TestGetEntitySummary:
    async def test_returns_summary_fields(self, live_context, company_nzbn):
        data = await run_action("get_entity_summary", {"nzbn": company_nzbn}, live_context)

        summary = data["summary"]
        assert summary["nzbn"] == company_nzbn
        assert summary["entityName"]
        assert isinstance(summary["registeredOffice"], str)


class TestGetEntityAddresses:
    async def test_returns_all_addresses_without_type(self, live_context, company_nzbn):
        data = await run_action("get_entity_addresses", {"nzbn": company_nzbn}, live_context)

        assert data["addresses"]
        assert "REGISTERED" in {address["addressType"] for address in data["addresses"]}

    async def test_type_filter_returns_only_that_type(self, live_context, company_nzbn):
        data = await run_action(
            "get_entity_addresses",
            {"nzbn": company_nzbn, "address_type": "REGISTERED"},
            live_context,
        )

        assert data["addresses"]
        assert all(address["addressType"] == "REGISTERED" for address in data["addresses"])


class TestEntityDetailLists:
    @pytest.mark.parametrize(
        ("action", "key"),
        [
            ("get_entity_roles", "roles"),
            ("get_entity_trading_names", "tradingNames"),
            ("get_entity_gst_numbers", "gstNumbers"),
            ("get_entity_industry_classifications", "industryClassifications"),
        ],
    )
    async def test_returns_list(self, live_context, company_nzbn, action, key):
        data = await run_action(action, {"nzbn": company_nzbn}, live_context)

        assert isinstance(data[key], list)


class TestGetCompanyDetails:
    async def test_returns_company_details(self, live_context, company_nzbn):
        data = await run_action("get_company_details", {"nzbn": company_nzbn}, live_context)

        assert isinstance(data["companyDetails"], dict)


class TestGetChanges:
    async def test_returns_changes_in_date_range(self, live_context):
        end = date.today()
        start = end - timedelta(days=7)
        data = await run_action(
            "get_changes",
            {
                "change_event_type": "NewRegistration",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "page_size": 5,
            },
            live_context,
        )

        assert isinstance(data["changes"], list)
        assert len(data["changes"]) <= 5
        assert data["totalItems"] >= len(data["changes"])
