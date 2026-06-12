import os
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from fergus.fergus import fergus

pytestmark = pytest.mark.integration

FERGUS_API_TOKEN = os.getenv("FERGUS_API_TOKEN", "")
FERGUS_TEST_JOB_ID = os.getenv("FERGUS_TEST_JOB_ID", "")
FERGUS_TEST_CUSTOMER_ID = os.getenv("FERGUS_TEST_CUSTOMER_ID", "")
FERGUS_TEST_SITE_ID = os.getenv("FERGUS_TEST_SITE_ID", "")


@pytest.fixture
def live_context(make_context):
    if not FERGUS_API_TOKEN:
        pytest.skip("FERGUS_API_TOKEN not set")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        payload = kwargs.get("data", body)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=payload,
                headers=dict(headers or {}),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"api_token": FERGUS_API_TOKEN})
    ctx.fetch.side_effect = real_fetch
    return ctx


@pytest.mark.asyncio
async def test_list_jobs_live(live_context):
    result = await fergus.execute_action("list_jobs", {"page_size": 5}, live_context)
    assert result.result.data.get("jobs") is not None


@pytest.mark.asyncio
async def test_list_users_live(live_context):
    result = await fergus.execute_action("list_users", {"page_size": 5}, live_context)
    assert result.result.data.get("users") is not None


@pytest.mark.asyncio
async def test_search_customers_live(live_context):
    result = await fergus.execute_action("search_customers", {"page_size": 5}, live_context)
    assert result.result.data.get("customers") is not None


@pytest.mark.asyncio
async def test_list_sites_live(live_context):
    result = await fergus.execute_action("list_sites", {"page_size": 5}, live_context)
    assert result.result.data.get("sites") is not None


@pytest.mark.asyncio
async def test_get_job_live(live_context):
    if not FERGUS_TEST_JOB_ID:
        pytest.skip("FERGUS_TEST_JOB_ID not set")
    result = await fergus.execute_action("get_job", {"job_id": int(FERGUS_TEST_JOB_ID)}, live_context)
    assert result.result.data.get("job") is not None


@pytest.mark.asyncio
async def test_get_customer_live(live_context):
    if not FERGUS_TEST_CUSTOMER_ID:
        pytest.skip("FERGUS_TEST_CUSTOMER_ID not set")
    result = await fergus.execute_action("get_customer", {"customer_id": int(FERGUS_TEST_CUSTOMER_ID)}, live_context)
    assert result.result.data.get("customer") is not None
