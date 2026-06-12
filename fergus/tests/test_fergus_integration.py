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
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("jobs") is not None


@pytest.mark.asyncio
async def test_list_users_live(live_context):
    result = await fergus.execute_action("list_users", {"page_size": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("users") is not None


@pytest.mark.asyncio
async def test_search_customers_live(live_context):
    result = await fergus.execute_action("search_customers", {"page_size": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("customers") is not None


@pytest.mark.asyncio
async def test_list_sites_live(live_context):
    result = await fergus.execute_action("list_sites", {"page_size": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("sites") is not None


@pytest.mark.asyncio
async def test_get_job_live(live_context):
    if not FERGUS_TEST_JOB_ID:
        pytest.skip("FERGUS_TEST_JOB_ID not set")
    result = await fergus.execute_action("get_job", {"job_id": int(FERGUS_TEST_JOB_ID)}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("job") is not None


@pytest.mark.asyncio
async def test_get_customer_live(live_context):
    if not FERGUS_TEST_CUSTOMER_ID:
        pytest.skip("FERGUS_TEST_CUSTOMER_ID not set")
    result = await fergus.execute_action("get_customer", {"customer_id": int(FERGUS_TEST_CUSTOMER_ID)}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("customer") is not None


# ---- Destructive Tests ----


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_job_lifecycle_live(live_context):
    """create_job → update_job → finalise_job lifecycle against the real Fergus API.

    Requires FERGUS_TEST_CUSTOMER_ID and FERGUS_TEST_SITE_ID — these must already
    exist in the connected Fergus account. The job is finalised at the end (Fergus
    does not expose a delete endpoint, so finalised is the closest cleanup state).
    """
    if not FERGUS_TEST_CUSTOMER_ID or not FERGUS_TEST_SITE_ID:
        pytest.skip("FERGUS_TEST_CUSTOMER_ID and FERGUS_TEST_SITE_ID required for job lifecycle test")

    # Create
    create_result = await fergus.execute_action(
        "create_job",
        {
            "job_type": "Charge Up",
            "title": "Autohive Integration Test Job",
            "description": "Created by integration test — safe to delete",
            "customer_id": int(FERGUS_TEST_CUSTOMER_ID),
            "site_id": int(FERGUS_TEST_SITE_ID),
        },
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message
    job_id = create_result.result.data["job"]["id"]
    assert job_id

    # Update
    update_result = await fergus.execute_action(
        "update_job",
        {"job_id": job_id, "title": "Autohive Integration Test Job (updated)"},
        live_context,
    )
    assert update_result.type == ResultType.ACTION, update_result.result.message

    # Finalise (closest to cleanup — Fergus has no delete endpoint)
    finalise_result = await fergus.execute_action("finalise_job", {"job_id": job_id}, live_context)
    assert finalise_result.type == ResultType.ACTION, finalise_result.result.message
