import os
import pytest
from autohive_integrations_sdk import ExecutionContext
from fergus.fergus import fergus

pytestmark = pytest.mark.integration

FERGUS_API_TOKEN = os.getenv("FERGUS_API_TOKEN", "")
FERGUS_TEST_JOB_ID = os.getenv("FERGUS_TEST_JOB_ID", "")
FERGUS_TEST_CUSTOMER_ID = os.getenv("FERGUS_TEST_CUSTOMER_ID", "")
FERGUS_TEST_SITE_ID = os.getenv("FERGUS_TEST_SITE_ID", "")


@pytest.fixture
def live_context():
    if not FERGUS_API_TOKEN:
        pytest.skip("FERGUS_API_TOKEN not set")
    ctx = ExecutionContext.__new__(ExecutionContext)
    ctx.auth = {"api_token": FERGUS_API_TOKEN}
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
